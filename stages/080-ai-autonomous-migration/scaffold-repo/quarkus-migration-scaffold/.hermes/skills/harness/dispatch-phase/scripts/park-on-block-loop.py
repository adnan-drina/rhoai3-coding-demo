#!/usr/bin/env python3
"""L7 — park cards after block_loop_detected into a dispatcher-refused status.

Hermes records `block_loop_detected` and (observed v18) leaves the card in
`blocked`. Promote lifts `todo`/`blocked` → `ready`, so the loop-breaker is
advisory unless status changes.

Official docs say the breaker routes to `triage`. Promote sources
`todo`/`blocked` only — triage is not auto-promoted. This script makes that
hold real: if the latest loop-break event is more recent than the latest
`unblocked`/`promoted`/`claimed` event, set `status='triage'`.

Does not patch Hermes. Residual risk: `kanban.auto_decompose` may fan triage
cards into children — that is a separate pin, not this hold.

Usage:
  python3 park-on-block-loop.py --db "$HERMES_HOME/kanban.db"
  python3 park-on-block-loop.py --self-test
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path

HOLD_STATUS = "triage"
LOOP_KIND = "block_loop_detected"
CLEAR_KINDS = frozenset({"unblocked", "promoted", "claimed"})


def _connect(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


def park(conn: sqlite3.Connection) -> list[str]:
    """Return task ids moved to HOLD_STATUS."""
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "tasks" not in tables or "task_events" not in tables:
        return []
    cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    if "id" not in cols or "status" not in cols:
        return []
    event_cols = {
        r[1] for r in conn.execute("PRAGMA table_info(task_events)").fetchall()
    }
    kind_col = "kind" if "kind" in event_cols else (
        "event_kind" if "event_kind" in event_cols else None
    )
    ts_col = (
        "created_at"
        if "created_at" in event_cols
        else ("ts" if "ts" in event_cols else None)
    )
    task_col = "task_id" if "task_id" in event_cols else None
    if not kind_col or not ts_col or not task_col:
        return []

    parked: list[str] = []
    skip = frozenset({HOLD_STATUS, "done", "archived", "running", "review"})
    rows = conn.execute("SELECT id, status FROM tasks").fetchall()
    for row in rows:
        tid = str(row["id"])
        status = str(row["status"] or "")
        if status in skip:
            continue
        loop = conn.execute(
            f"SELECT MAX({ts_col}) FROM task_events "
            f"WHERE {task_col}=? AND {kind_col}=?",
            (tid, LOOP_KIND),
        ).fetchone()[0]
        if not loop:
            continue
        cleared = conn.execute(
            f"SELECT MAX({ts_col}) FROM task_events "
            f"WHERE {task_col}=? AND {kind_col} IN ({','.join('?' * len(CLEAR_KINDS))})",
            (tid, *sorted(CLEAR_KINDS)),
        ).fetchone()[0]
        if cleared is not None and cleared >= loop:
            continue
        if status == HOLD_STATUS:
            continue
        conn.execute(
            "UPDATE tasks SET status=? WHERE id=?",
            (HOLD_STATUS, tid),
        )
        parked.append(tid)
    return parked


def simulate_promote(conn: sqlite3.Connection) -> list[str]:
    """Hermes promote: todo/blocked → ready. Returns ids it would lift."""
    lifted = [
        str(r["id"])
        for r in conn.execute(
            "SELECT id FROM tasks WHERE status IN ('todo', 'blocked')"
        ).fetchall()
    ]
    conn.execute(
        "UPDATE tasks SET status='ready' WHERE status IN ('todo', 'blocked')"
    )
    conn.commit()
    return lifted


def self_test() -> int:
    tmp = Path(tempfile.mkdtemp()) / "kanban.db"
    bootstrap = sqlite3.connect(str(tmp))
    bootstrap.executescript(
        """
        CREATE TABLE tasks (id TEXT PRIMARY KEY, status TEXT);
        CREATE TABLE task_events (
            id INTEGER PRIMARY KEY,
            task_id TEXT,
            kind TEXT,
            created_at TEXT
        );
        INSERT INTO tasks VALUES ('t_loop', 'blocked');
        INSERT INTO tasks VALUES ('t_plain', 'blocked');
        INSERT INTO task_events (task_id, kind, created_at)
            VALUES ('t_loop', 'block_loop_detected', '2026-08-14T20:30:31Z');
        INSERT INTO task_events (task_id, kind, created_at)
            VALUES ('t_plain', 'blocked', '2026-08-14T20:00:00Z');
        """
    )
    bootstrap.commit()
    bootstrap.close()
    conn = _connect(tmp)
    moved = park(conn)
    conn.commit()
    if moved != ["t_loop"]:
        print(
            f"SELFTEST_FAIL: expected park ['t_loop'], got {moved!r}",
            file=sys.stderr,
        )
        return 1
    st = {
        r["id"]: r["status"]
        for r in conn.execute("SELECT id, status FROM tasks")
    }
    if st["t_loop"] != HOLD_STATUS:
        print(
            f"SELFTEST_FAIL: t_loop status={st['t_loop']!r} want {HOLD_STATUS}",
            file=sys.stderr,
        )
        return 1
    if st["t_plain"] != "blocked":
        print(
            f"SELFTEST_FAIL: t_plain should stay blocked, got {st['t_plain']!r}",
            file=sys.stderr,
        )
        return 1
    lifted = simulate_promote(conn)
    if "t_loop" in lifted:
        print(
            "SELFTEST_FAIL: promote lifted loop-broken card (dispatcher hold failed)",
            file=sys.stderr,
        )
        return 1
    if "t_plain" not in lifted:
        print(
            "SELFTEST_FAIL: control card t_plain was not promotable",
            file=sys.stderr,
        )
        return 1
    after = {
        r["id"]: r["status"]
        for r in conn.execute("SELECT id, status FROM tasks")
    }
    if after["t_loop"] != HOLD_STATUS:
        print(
            f"SELFTEST_FAIL: after promote t_loop={after['t_loop']!r}",
            file=sys.stderr,
        )
        return 1
    # Negative claim: no ready loop-broken card
    ready = [
        r["id"]
        for r in conn.execute("SELECT id FROM tasks WHERE status='ready'")
    ]
    if "t_loop" in ready:
        print("SELFTEST_FAIL: t_loop became ready", file=sys.stderr)
        return 1
    conn.close()
    print("park-on-block-loop self-test passed (triage hold; promote skips)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--db",
        default="",
        help="path to kanban.db (default: $HERMES_HOME/kanban.db)",
    )
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="run the fixture negative test and exit",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print ids that would be parked; do not write",
    )
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    import os

    db_raw = args.db.strip() or os.environ.get("HERMES_KANBAN_DB", "")
    if not db_raw:
        home = os.environ.get("HERMES_HOME", "").strip()
        db_raw = str(Path(home) / "kanban.db") if home else ""
    if not db_raw:
        print("park-on-block-loop: idle (no --db / HERMES_HOME)", file=sys.stderr)
        return 0
    db = Path(db_raw).expanduser()
    if not db.is_file():
        print(f"park-on-block-loop: idle (no db at {db})", file=sys.stderr)
        return 0
    conn = _connect(db)
    try:
        if args.dry_run:
            conn.execute("BEGIN")
            moved = park(conn)
            conn.rollback()
            print(f"park-on-block-loop: dry-run would park {moved}")
            return 0
        moved = park(conn)
        if moved:
            conn.commit()
            print(f"park-on-block-loop: parked {moved} → {HOLD_STATUS}")
        else:
            print("park-on-block-loop: nothing to park")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
