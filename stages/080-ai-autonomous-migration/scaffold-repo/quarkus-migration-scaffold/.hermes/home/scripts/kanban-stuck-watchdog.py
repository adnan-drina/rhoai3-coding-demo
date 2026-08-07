"""Kanban stuck-task watchdog (AD-H §13) — the ONLY Hermes cron job.

no_agent cron script: exit 0 + empty stdout = silent tick; exit 0 + stdout =
local alert; non-zero exit = error alert (broken watchdog cannot be silent).

Detects one thing: a Kanban task in status `running` longer than
STUCK_SECONDS (default 1800). Does not restart, kill, or mutate state —
observer only. A second cron job requires an Architect decision stating why
this one is insufficient.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path


def hermes_home() -> Path:
    raw = os.environ.get("HERMES_HOME", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".hermes"


def stuck_seconds() -> int:
    try:
        return max(60, int(os.environ.get("STUCK_SECONDS", "1800")))
    except ValueError as exc:
        raise SystemExit(f"kanban-stuck-watchdog: bad STUCK_SECONDS: {exc}") from exc


def find_running_table(conn: sqlite3.Connection) -> tuple[str, str, str] | None:
    """Return (table, status_col, time_col) for a tasks-like table, or None."""
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    preferred = ("tasks", "kanban_tasks", "task", "items")
    ordered = [t for t in preferred if t in tables] + [
        t for t in tables if t not in preferred
    ]
    for table in ordered:
        cols = {
            r[1].lower(): r[1]
            for r in conn.execute(f'PRAGMA table_info("{table}")')
        }
        status_col = next(
            (cols[c] for c in ("status", "state", "column", "lane") if c in cols),
            None,
        )
        if not status_col:
            continue
        time_col = next(
            (
                cols[c]
                for c in (
                    "updated_at",
                    "updated",
                    "started_at",
                    "started",
                    "running_since",
                    "modified_at",
                    "mtime",
                    "created_at",
                    "created",
                )
                if c in cols
            ),
            None,
        )
        if time_col:
            return table, status_col, time_col
    return None


def parse_epoch(value: object, now: float) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        # ms vs s heuristic
        if ts > 1e12:
            ts /= 1000.0
        return ts
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return parse_epoch(int(text), now)
    try:
        # ISO-ish
        from datetime import datetime

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def main() -> int:
    home = hermes_home()
    db_path = Path(os.environ.get("KANBAN_DB", str(home / "kanban.db")))
    threshold = stuck_seconds()
    now = time.time()

    if not db_path.is_file():
        # No board yet — nothing stuck. Silent tick.
        return 0

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        print(f"kanban-stuck-watchdog: cannot open {db_path}: {exc}", file=sys.stderr)
        return 1

    try:
        found = find_running_table(conn)
        if found is None:
            print(
                f"kanban-stuck-watchdog: no tasks table with status+time columns in {db_path}",
                file=sys.stderr,
            )
            return 1
        table, status_col, time_col = found
        # Identify a human-readable id column if present
        cols = {
            r[1].lower(): r[1]
            for r in conn.execute(f'PRAGMA table_info("{table}")')
        }
        id_col = next(
            (cols[c] for c in ("id", "task_id", "uuid", "key", "name", "title") if c in cols),
            None,
        )
        select_cols = [status_col, time_col] + ([id_col] if id_col else [])
        q = (
            f'SELECT {", ".join(f"{c}" for c in select_cols)} '
            f'FROM "{table}" WHERE lower(cast("{status_col}" as text)) = ?'
        )
        rows = list(conn.execute(q, ("running",)))
    except sqlite3.Error as exc:
        print(f"kanban-stuck-watchdog: query failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    alerts: list[str] = []
    for row in rows:
        status_v, time_v = row[0], row[1]
        ident = row[2] if len(row) > 2 else "?"
        started = parse_epoch(time_v, now)
        if started is None:
            alerts.append(
                f"WATCHDOG: task {ident!s} status={status_v!s} has unparseable "
                f"{time_col}={time_v!r} (threshold {threshold}s)"
            )
            continue
        age = now - started
        if age >= threshold:
            alerts.append(
                f"WATCHDOG: Kanban task {ident!s} stuck in running for "
                f"{int(age)}s (threshold {threshold}s). Alert only — no action taken."
            )

    if alerts:
        print("\n".join(alerts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
