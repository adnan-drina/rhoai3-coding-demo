#!/usr/bin/env python3
"""Fail if residual Hermes workers still cite terminal/abort tasks.

Architect E-20260811T173254Z Class A — tombstones do not close mid-run zombies.

Usage:
  python3 assert-no-residual-workers.py /projects/modernized
  python3 assert-no-residual-workers.py /projects/modernized --task t_b5019586
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

TASK_RE = re.compile(r"\b(t_[0-9a-f]{8})\b")
TERMINAL = frozenset({"done", "triage", "archived"})


def hermes_home(root: Path) -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    return root / ".hermes" / "home"


def live_by_task() -> dict[str, list[tuple[int, str]]]:
    out = subprocess.check_output(["ps", "-eo", "pid=,args="], text=True, errors="replace")
    found: dict[str, list[tuple[int, str]]] = {}
    for line in out.splitlines():
        line = line.strip()
        if not line or "hermes" not in line:
            continue
        if "kanban task" not in line and "work kanban task" not in line:
            continue
        if any(x in line for x in ("kill-and-verify", "assert-no-residual", "stamp-worker-pid", "tail ")):
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        m = TASK_RE.search(parts[1])
        if not m:
            continue
        found.setdefault(m.group(1), []).append((pid, parts[1][:180]))
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--task", action="append", dest="tasks")
    args = ap.parse_args()
    root = args.root.resolve()
    db = hermes_home(root) / "kanban.db"
    live = live_by_task()
    conn = sqlite3.connect(str(db)) if db.is_file() else None

    bad: list[str] = []
    check_ids = args.tasks or list(live.keys())
    for tid in sorted(set(check_ids)):
        procs = live.get(tid) or []
        if not procs:
            continue
        status = None
        if conn is not None:
            row = conn.execute("SELECT status FROM tasks WHERE id=?", (tid,)).fetchone()
            status = row[0] if row else None
        # Residual if task is terminal OR explicitly requested
        if args.tasks or (status in TERMINAL):
            for pid, cmd in procs:
                bad.append(f"{tid} status={status} pid={pid} cmd={cmd}")

    if conn is not None:
        conn.close()

    if bad:
        print("FAIL: residual Hermes workers on terminal/abort tasks:", file=sys.stderr)
        for b in bad:
            print(f"  {b}", file=sys.stderr)
        print(
            "Run: bash .hermes/home/scripts/kill-and-verify-task-worker.sh <task_id>",
            file=sys.stderr,
        )
        return 1
    print(f"OK: no residual workers (checked={len(set(check_ids))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
