#!/usr/bin/env python3
"""F8b — reclaim M2b parent `done` without partition↔created receipt.

Deputy E-20260813T221456Z: prose in the card is not enforcement. This harness
script fails closed when an M2b parent is `done` without
`evidence/runs/<parent>/m2b-created-cards-ok.json` (ok=true) produced by
`assert-m2b-created-cards-claim.sh`.

Usage:
  python3 enforce-m2b-created-cards-claim.py /projects/modernized --task t_xxx
  python3 enforce-m2b-created-cards-claim.py /projects/modernized --sweep-done
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RECEIPT = "m2b-created-cards-ok.json"
SCHEMA = "rhoai3.m2b-created-cards-ok/v1"


def kanban_db(root: Path) -> Path:
    primary = root / ".hermes" / "home" / "kanban.db"
    if primary.is_file():
        return primary
    return root / ".hermes" / "home" / "kanban" / "kanban.db"


def receipt_ok(root: Path, task_id: str) -> bool:
    p = root / "evidence" / "runs" / task_id / RECEIPT
    if not p.is_file():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return data.get("schema") == SCHEMA and bool(data.get("ok"))


def looks_like_m2b(title: str, body: str) -> bool:
    blob = f"{title}\n{body}".lower()
    return "m2b" in blob and ("create-m3" in blob or "created_cards" in blob or "sdd" in blob)


def reclaim(root: Path, task_id: str, dry_run: bool) -> int:
    if receipt_ok(root, task_id):
        print(f"OK: {task_id} m2b-created-cards receipt green")
        return 0
    print(
        f"RECLAIM: {task_id} done without {RECEIPT} (F8b E-20260813T221456Z)",
        file=sys.stderr,
    )
    if dry_run:
        return 1
    # Prefer hermes CLI when present
    cp = subprocess.run(
        ["hermes", "kanban", "update", task_id, "--status", "blocked"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if cp.returncode != 0:
        # fallback: sqlite status flip if db exists
        db = kanban_db(root)
        if db.is_file():
            con = sqlite3.connect(str(db))
            try:
                con.execute(
                    "UPDATE tasks SET status=? WHERE id=?",
                    ("blocked", task_id),
                )
                con.commit()
            finally:
                con.close()
        else:
            print(cp.stderr or cp.stdout, file=sys.stderr)
            return 1
    stamp = {
        "schema": "rhoai3.m2b-created-cards-reclaim/v1",
        "task_id": task_id,
        "reason": "missing_or_red_m2b_created_cards_ok",
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out = root / "evidence" / "runs" / task_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "m2b-created-cards-reclaim.json").write_text(
        json.dumps(stamp, indent=2) + "\n", encoding="utf-8"
    )
    print(f"RECLAIMED: {task_id} → blocked")
    return 1


def sweep_done(root: Path, dry_run: bool) -> int:
    db = kanban_db(root)
    if not db.is_file():
        print(f"WARN: no kanban db at {db}", file=sys.stderr)
        return 0
    con = sqlite3.connect(str(db))
    try:
        rows = con.execute(
            "SELECT id, title, COALESCE(body,''), status FROM tasks WHERE status='done'"
        ).fetchall()
    except sqlite3.Error as e:
        print(f"WARN: kanban query failed: {e}", file=sys.stderr)
        return 0
    finally:
        con.close()
    rc = 0
    for tid, title, body, _status in rows:
        if not looks_like_m2b(str(title or ""), str(body or "")):
            continue
        if reclaim(root, str(tid), dry_run) != 0:
            rc = 1
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task", help="single parent task id")
    ap.add_argument("--sweep-done", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if args.task:
        return reclaim(root, args.task, args.dry_run)
    if args.sweep_done:
        return sweep_done(root, args.dry_run)
    print("FAIL: pass --task or --sweep-done", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
