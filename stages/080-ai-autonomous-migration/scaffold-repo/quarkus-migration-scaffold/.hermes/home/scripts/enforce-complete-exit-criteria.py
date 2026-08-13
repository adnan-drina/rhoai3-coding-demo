#!/usr/bin/env python3
"""Reclaim `done` cards whose complete-cmd receipt is red (auto-wire).

Architect E-20260811T175509Z Class A (BANK-COMPLETE-CMD-1) +
Architect E-20260811T200911Z auto-wire: Hermes accepts `kanban_complete`
without reading receipts. When `complete-exit-ok.json` exists with `ok=false`
(or complete-trigger exit-eval is red), reclaim done → needs_input.

Pre-Class-A `done` cards with **no** complete receipt are grandfathered
(missing receipt ≠ reclaim). Product PASS-with-notes may stamp
`complete-cmd-waiver.json` to skip reclaim.

Usage:
  python3 enforce-complete-exit-criteria.py /projects/modernized --task t_xxx
  python3 enforce-complete-exit-criteria.py /projects/modernized --sweep-done
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WAIVER_SCHEMA = "rhoai3.complete-cmd-waiver/v1"


def kanban_db(root: Path) -> Path:
    primary = root / ".hermes" / "home" / "kanban.db"
    if primary.is_file():
        return primary
    return root / ".hermes" / "home" / "kanban" / "kanban.db"


def run_dir(root: Path, task_id: str) -> Path:
    return root / "evidence" / "runs" / task_id


def has_waiver(root: Path, task_id: str) -> bool:
    p = run_dir(root, task_id) / "complete-cmd-waiver.json"
    if not p.is_file():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return data.get("schema") == WAIVER_SCHEMA and bool(data.get("ok"))


def receipt_verdict(root: Path, task_id: str) -> str:
    """Return green | red | absent | waiver."""
    if has_waiver(root, task_id):
        return "waiver"
    p = run_dir(root, task_id) / "complete-exit-ok.json"
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "red"
        return "green" if bool(data.get("ok")) else "red"
    ev = run_dir(root, task_id) / "exit-eval.json"
    if ev.is_file():
        try:
            data = json.loads(ev.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "absent"
        if str(data.get("trigger") or "") != "complete":
            return "absent"
        return "green" if bool(data.get("overall_ok")) else "red"
    return "absent"


def reclaim(root: Path, task_id: str, dry_run: bool) -> int:
    verdict = receipt_verdict(root, task_id)
    if verdict in {"green", "waiver"}:
        print(f"OK: {task_id} complete-cmd {verdict}")
        return 0
    if verdict == "absent":
        # Grandfather pre-Class-A dones / never-asserted completes
        print(f"OK: {task_id} no complete-cmd receipt (grandfather / not asserted)")
        return 0

    reason = (
        f"BANK-COMPLETE-CMD-1 reclaim: done with RED complete-exit receipt "
        f"(Architect E-20260811T200911Z auto-wire) @ "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )
    print(f"RECLAIM: {task_id} — {reason}")
    if dry_run:
        return 1

    cp = subprocess.run(
        [
            "hermes",
            "kanban",
            "block",
            task_id,
            "--kind",
            "needs_input",
            reason,
        ],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if cp.returncode == 0:
        sys.stdout.write(cp.stdout or "")
        return 1

    db = kanban_db(root)
    if not db.is_file():
        print(f"FAIL: hermes block rc={cp.returncode} and no kanban.db", file=sys.stderr)
        sys.stderr.write(cp.stderr or "")
        return 2
    conn = sqlite3.connect(str(db))
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)")}
        if "status" not in cols:
            print("FAIL: tasks.status missing", file=sys.stderr)
            return 2
        conn.execute("UPDATE tasks SET status=? WHERE id=?", ("blocked", task_id))
        try:
            conn.execute(
                "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?,?,?,?)",
                (
                    task_id,
                    "enforce-complete-exit",
                    reason,
                    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                ),
            )
        except sqlite3.Error:
            pass
        conn.commit()
    finally:
        conn.close()
    print(f"OK: sqlite reclaim {task_id} → blocked")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task", default="")
    ap.add_argument("--sweep-done", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if args.task:
        return reclaim(root, args.task, args.dry_run)
    if not args.sweep_done:
        print("FAIL: pass --task ID or --sweep-done", file=sys.stderr)
        return 2
    db = kanban_db(root)
    if not db.is_file():
        print(f"FAIL: no kanban db at {db}", file=sys.stderr)
        return 2
    conn = sqlite3.connect(str(db))
    # completed_at may exist; fall back to created_at
    cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)")}
    order = "completed_at" if "completed_at" in cols else "created_at"
    rows = conn.execute(
        f"SELECT id FROM tasks WHERE status='done' ORDER BY {order} DESC LIMIT 50"
    ).fetchall()
    conn.close()
    worst = 0
    for (tid,) in rows:
        rc = reclaim(root, tid, args.dry_run)
        if rc > worst:
            worst = rc
    if worst == 0:
        print("OK: sweep — no red complete-exit receipts on recent done cards")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
