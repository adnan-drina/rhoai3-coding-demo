#!/usr/bin/env python3
"""After kanban_create: one-line park assert from sqlite (no show --json).

Refuse unless status=todo and parents include the unfinished ack_gate
plus any --expect-parent ids (V35-SERIAL identity.parents).
Do not print the card body or files_writable.

Usage:
  python3 assert-story-parked.py /projects/modernized \\
    --task-id t_xxx --ack-gate t_yyy [--expect-parent t_zzz]...
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def kanban_db(root: Path) -> Path:
    primary = root / ".hermes" / "home" / "kanban.db"
    if primary.is_file():
        return primary
    alt = root / ".hermes" / "home" / "kanban" / "kanban.db"
    return alt if alt.is_file() else primary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--ack-gate", required=True)
    ap.add_argument("--expect-parent", action="append", default=[], metavar="ID")
    ap.add_argument(
        "--expect-max-runtime",
        type=int,
        default=0,
        help="Refuse unless tasks.max_runtime_seconds equals this (M3 yaml 2700)",
    )
    ap.add_argument(
        "--expect-max-retries",
        type=int,
        default=0,
        help="Refuse unless tasks.max_retries equals this",
    )
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    db = kanban_db(root)
    if not db.is_file() or db.stat().st_size == 0:
        print(f"REFUSE: missing kanban.db {db}")
        return 1
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "select * from tasks where id=?",
            (args.task_id,),
        ).fetchone()
        if row is None:
            print(f"REFUSE: unknown task {args.task_id}")
            return 1
        keys = set(row.keys()) if hasattr(row, "keys") else set()
        status = str(row["status"] or "").strip().lower()
        if status != "todo":
            print(f"REFUSE: {args.task_id} status={status} want=todo")
            return 1
        if args.expect_max_runtime:
            if "max_runtime_seconds" not in keys:
                print("REFUSE: tasks table missing max_runtime_seconds")
                return 1
            got = row["max_runtime_seconds"]
            if int(got or 0) != int(args.expect_max_runtime):
                print(
                    f"REFUSE: {args.task_id} max_runtime_seconds={got} "
                    f"want={args.expect_max_runtime}"
                )
                return 1
        if args.expect_max_retries:
            col = "max_retries" if "max_retries" in keys else ""
            if not col:
                print("REFUSE: tasks table missing max_retries")
                return 1
            got = row[col]
            if int(got or 0) != int(args.expect_max_retries):
                print(
                    f"REFUSE: {args.task_id} max_retries={got} "
                    f"want={args.expect_max_retries}"
                )
                return 1
        parents = [
            str(r[0])
            for r in con.execute(
                "select parent_id from task_links where child_id=?",
                (args.task_id,),
            )
        ]
    finally:
        con.close()
    if args.ack_gate not in parents:
        print(f"REFUSE: {args.task_id} parents missing ack_gate {args.ack_gate}")
        return 1
    for pid in args.expect_parent:
        if pid not in parents:
            print(f"REFUSE: {args.task_id} parents missing identity parent {pid}")
            return 1
    extra = f" identity_parents={args.expect_parent}" if args.expect_parent else ""
    print(f"OK: parked {args.task_id} status=todo{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
