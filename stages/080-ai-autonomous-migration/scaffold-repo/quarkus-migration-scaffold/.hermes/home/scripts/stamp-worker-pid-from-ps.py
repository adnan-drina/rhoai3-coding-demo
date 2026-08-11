#!/usr/bin/env python3
"""Stamp tasks.worker_pid from live ps (Architect E-20260811T173254Z Class A).

Hermes spawn historically left worker_pid NULL — abort/terminal could not kill
by DB. After dispatch (or periodically while running), stamp from argv match.

Usage:
  python3 stamp-worker-pid-from-ps.py /projects/modernized [--task t_xxx]
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


def hermes_home(root: Path) -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    return root / ".hermes" / "home"


def live_workers() -> dict[str, int]:
    """Map task_id -> pid for hermes kanban task workers."""
    out = subprocess.check_output(["ps", "-eo", "pid=,args="], text=True, errors="replace")
    found: dict[str, int] = {}
    for line in out.splitlines():
        line = line.strip()
        if not line or "hermes" not in line:
            continue
        if "kanban task" not in line and "work kanban task" not in line:
            continue
        if "kill-and-verify" in line or "stamp-worker-pid" in line:
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
        tid = m.group(1)
        # Prefer lowest pid if duplicates
        if tid not in found or pid < found[tid]:
            found[tid] = pid
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--task", action="append", dest="tasks")
    args = ap.parse_args()
    root = args.root.resolve()
    db = hermes_home(root) / "kanban.db"
    if not db.is_file():
        print(f"FAIL: missing {db}", file=sys.stderr)
        return 2
    live = live_workers()
    want = set(args.tasks) if args.tasks else set(live.keys())
    conn = sqlite3.connect(str(db))
    stamped = 0
    for tid in sorted(want):
        pid = live.get(tid)
        if pid is None:
            print(f"MISS {tid} (no live hermes worker)")
            continue
        row = conn.execute(
            "SELECT status, worker_pid FROM tasks WHERE id=?", (tid,)
        ).fetchone()
        if not row:
            print(f"MISS_DB {tid}")
            continue
        conn.execute("UPDATE tasks SET worker_pid=? WHERE id=?", (pid, tid))
        print(f"STAMP {tid} worker_pid={pid} status={row[0]} prev={row[1]}")
        stamped += 1
    conn.commit()
    conn.close()
    print(f"OK: stamped {stamped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
