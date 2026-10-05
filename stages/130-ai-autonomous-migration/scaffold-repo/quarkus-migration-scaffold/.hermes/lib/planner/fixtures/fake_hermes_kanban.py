#!/usr/bin/env python3
"""SYNTHETIC stand-in for the pinned ``hermes kanban`` CLI (create / attach /
assign / link / comment) over a SQLite file with the pinned kanban.db column
names -- the same schema FakeNative.sync mirrors -- so that a SEPARATE process
(the authority service under test) mutates a board the test and KanbanNative
read. Not native evidence: the exact-runtime tests use the real CLI.

Every invocation appends its HERMES_* environment to ``<db>.cli-env.jsonl`` so a
test can prove which Hermes home the caller used.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import time

SCHEMA = ("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, title TEXT, body TEXT, assignee TEXT, status TEXT,"
          " idempotency_key TEXT, skills TEXT, workspace_path TEXT, max_retries INTEGER, current_run_id INTEGER,"
          " claim_lock TEXT, worker_pid INTEGER, created_at INTEGER);"
          "CREATE TABLE IF NOT EXISTS task_links (parent_id TEXT, child_id TEXT);"
          "CREATE TABLE IF NOT EXISTS task_comments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, author TEXT,"
          " body TEXT, created_at INTEGER);"
          "CREATE TABLE IF NOT EXISTS task_attachments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, filename TEXT,"
          " stored_path TEXT, size INTEGER);"
          "CREATE TABLE IF NOT EXISTS task_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, status TEXT, claim_lock TEXT);")


def connect(db: str) -> sqlite3.Connection:
    con = sqlite3.connect(db, timeout=30, isolation_level=None)
    con.executescript(SCHEMA)
    return con


def main(argv: list[str]) -> int:
    db = os.environ.get("HERMES_KANBAN_DB") or ""
    if not db:
        print("no HERMES_KANBAN_DB", file=sys.stderr)
        return 2
    with open(db + ".cli-env.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({k: v for k, v in os.environ.items() if k.startswith("HERMES_")}, sort_keys=True) + "\n")
    if argv[:1] != ["kanban"]:
        return 2
    cmd, args = argv[1], argv[2:]
    con = connect(db)
    con.execute("BEGIN IMMEDIATE")
    try:
        if cmd == "create":
            title = args[0]
            opts: dict[str, list[str]] = {}
            i = 1
            while i < len(args):
                if args[i] == "--json":
                    i += 1
                    continue
                opts.setdefault(args[i], []).append(args[i + 1])
                i += 2
            key = opts["--idempotency-key"][0]
            row = con.execute("SELECT id FROM tasks WHERE idempotency_key=? AND status!='archived'", (key,)).fetchone()
            if row:
                tid = row[0]
            else:
                n = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] + 1
                tid = "t_%08x" % (0x2000 + n)
                parents = opts.get("--parent", [])
                open_parent = any((con.execute("SELECT status FROM tasks WHERE id=?", (p,)).fetchone() or ["todo"])[0]
                                  not in ("done", "archived") for p in parents)
                con.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (tid, title, opts["--body"][0], (opts.get("--assignee") or [None])[0],
                             "todo" if open_parent else "ready", key, json.dumps(opts.get("--skill", [])),
                             (opts.get("--workspace") or [""])[0], int(opts["--max-retries"][0]), None, None, None,
                             int(time.time() * 1000)))
                for p in parents:
                    con.execute("INSERT INTO task_links VALUES (?,?)", (p, tid))
            print(json.dumps({"id": tid}))
        elif cmd == "attach":
            tid, path = args[0], args[1]
            name = args[args.index("--name") + 1]
            root = os.environ.get("HERMES_KANBAN_ATTACHMENTS_ROOT") or os.path.join(os.path.dirname(db), "kanban", "attachments")
            d = os.path.join(root, tid)
            os.makedirs(d, exist_ok=True)
            dest = os.path.join(d, name)
            k = 1
            while os.path.exists(dest):
                dest = os.path.join(d, "%s (%d)%s" % (os.path.splitext(name)[0], k, os.path.splitext(name)[1]))
                k += 1
            shutil.copyfile(path, dest)
            cur = con.execute("INSERT INTO task_attachments(task_id, filename, stored_path, size) VALUES (?,?,?,?)",
                              (tid, os.path.basename(dest), dest, os.path.getsize(dest)))
            print("attachment %d stored" % cur.lastrowid)
        elif cmd == "assign":
            con.execute("UPDATE tasks SET assignee=? WHERE id=?", (args[1], args[0]))
        elif cmd == "link":
            con.execute("INSERT INTO task_links VALUES (?,?)", (args[0], args[1]))
        elif cmd == "comment":
            con.execute("INSERT INTO task_comments(task_id, author, body, created_at) VALUES (?,?,?,0)", (args[0], "cli", args[1]))
        else:
            con.execute("ROLLBACK")
            print("unsupported %s" % cmd, file=sys.stderr)
            return 2
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
