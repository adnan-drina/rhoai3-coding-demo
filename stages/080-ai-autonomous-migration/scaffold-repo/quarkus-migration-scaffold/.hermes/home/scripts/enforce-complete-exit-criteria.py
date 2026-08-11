#!/usr/bin/env python3
"""Reclaim `done` cards that completed without green cmd-shaped exit eval.

Architect E-20260811T175509Z Class A (BANK-COMPLETE-CMD-1): Hermes accepts
`kanban_complete` without evaluating exit_criteria. This enforcer fail-closes
after the fact: if a task is `done` but lacks `complete-exit-ok.json` with
ok=true (or exit-eval overall_ok for trigger=complete), revert to needs_input.

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


def kanban_db(root: Path) -> Path:
    return root / ".hermes" / "home" / "kanban" / "kanban.db"


def receipt_ok(root: Path, task_id: str) -> bool:
    p = root / "migration" / "runs" / task_id / "complete-exit-ok.json"
    if not p.is_file():
        # Fall back: exit-eval with trigger=complete and overall_ok
        ev = root / "migration" / "runs" / task_id / "exit-eval.json"
        if not ev.is_file():
            return False
        try:
            data = json.loads(ev.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return bool(data.get("overall_ok")) and str(data.get("trigger") or "") == "complete"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(data.get("ok"))


def reclaim(root: Path, task_id: str, dry_run: bool) -> int:
    if receipt_ok(root, task_id):
        print(f"OK: {task_id} has green complete-exit receipt")
        return 0
    reason = (
        f"BANK-COMPLETE-CMD-1 reclaim: done without green cmd exit_criteria "
        f"(Architect E-20260811T175509Z) @ "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )
    print(f"RECLAIM: {task_id} — {reason}")
    if dry_run:
        return 1
    # Prefer hermes CLI; fall back to sqlite
    cp = subprocess.run(
        ["hermes", "kanban", "block", task_id, "--reason", reason],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if cp.returncode == 0:
        sys.stdout.write(cp.stdout or "")
        return 1  # signal reclaim happened
    db = kanban_db(root)
    if not db.is_file():
        print(f"FAIL: hermes block rc={cp.returncode} and no kanban.db", file=sys.stderr)
        sys.stderr.write(cp.stderr or "")
        return 2
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
            (
                "needs_input",
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                task_id,
            ),
        )
        # best-effort comment table if present
        try:
            conn.execute(
                "INSERT INTO comments (task_id, text, created_at) VALUES (?,?,?)",
                (
                    task_id,
                    reason,
                    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                ),
            )
        except sqlite3.Error:
            pass
        conn.commit()
    finally:
        conn.close()
    print(f"OK: sqlite reclaim {task_id} → needs_input")
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
    rows = conn.execute(
        "SELECT id FROM tasks WHERE status='done' ORDER BY updated_at DESC LIMIT 50"
    ).fetchall()
    conn.close()
    worst = 0
    for (tid,) in rows:
        rc = reclaim(root, tid, args.dry_run)
        if rc > worst:
            worst = rc
    if worst == 0:
        print("OK: sweep — all recent done cards have green complete-exit")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
