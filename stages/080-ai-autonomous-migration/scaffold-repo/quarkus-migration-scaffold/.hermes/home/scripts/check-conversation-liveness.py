#!/usr/bin/env python3
"""BANK-CONV-LIVE-WD-1 — conversation-liveness / post-tool stall detector.

Detects: task status=running with fresh heartbeat, but transcript size flat
AND no new agent.log "API call #N" for the worker session beyond --flat-sec.

This closes the null-hb / warm-hb blind spot: Hermes state ticks keep
last_heartbeat_at warm while conversation_loop is dead post-tool
(idle-no-request / stream-stale class evidenced run#60–#62).

Alert only — no board mutate (Lead reclaim). Architect E-20260811T213229Z bank;
morning BIND via E-20260812T054930Z gate order.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sqlite3
import sys
import time
from pathlib import Path

API_CALL_RE = re.compile(
    r"\[(?P<sid>\d{8}_\d{6}_[0-9a-f]+)\][^\n]*API call #(?P<n>\d+):",
    re.I,
)
SESSION_RE = re.compile(r"(\d{8}_\d{6}_[0-9a-f]+)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task-id", required=True)
    ap.add_argument(
        "--flat-sec",
        type=int,
        default=600,
        help="transcript+API flat threshold (default 10m)",
    )
    ap.add_argument(
        "--hb-fresh-sec",
        type=int,
        default=180,
        help="heartbeat considered fresh under this age",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    home = root / ".hermes" / "home"
    db = home / "kanban.db"
    log = home / "kanban" / "logs" / f"{args.task_id}.log"
    agent = home / "logs" / "agent.log"
    now = time.time()

    if not db.is_file():
        print("SKIP: no kanban.db")
        return 0
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "select status, worker_pid, last_heartbeat_at, current_run_id from tasks where id=?",
            (args.task_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        print(f"SKIP: unknown task {args.task_id}")
        return 0
    status, pid, hb, run_id = row
    if str(status).lower() != "running":
        print(f"OK: not running status={status}")
        return 0
    if hb is None:
        print("SKIP: null heartbeat (stillborn path owns this)")
        return 0
    try:
        hb_age = now - int(hb)
    except (TypeError, ValueError):
        print(f"SKIP: unparseable hb={hb!r}")
        return 0
    if hb_age > args.hb_fresh_sec:
        print(f"OK: hb not fresh age={hb_age:.0f}s (stuck/null-hb paths apply)")
        return 0

    if not log.is_file():
        print(f"SKIP: missing transcript {log}")
        return 0
    log_age = now - log.stat().st_mtime
    log_bytes = log.stat().st_size

    last_api_age = None
    last_api_n = None
    sid = None
    if agent.is_file():
        text = agent.read_text(encoding="utf-8", errors="replace")
        try:
            tail = log.read_text(encoding="utf-8", errors="replace")[-12000:]
            m = SESSION_RE.search(tail)
            if m:
                sid = m.group(1)
        except OSError:
            pass
        matches = list(API_CALL_RE.finditer(text))
        if sid:
            matches = [m for m in matches if m.group("sid") == sid] or matches
        if matches:
            last = matches[-1]
            last_api_n = int(last.group("n"))
            line_start = text.rfind("\n", 0, last.start()) + 1
            line = text[line_start : text.find("\n", last.start())]
            ts_m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
            if ts_m:
                try:
                    ts = dt.datetime.strptime(ts_m.group(1), "%Y-%m-%d %H:%M:%S").replace(
                        tzinfo=dt.timezone.utc
                    )
                    last_api_age = now - ts.timestamp()
                except ValueError:
                    last_api_age = None
            if last_api_age is None:
                last_api_age = now - agent.stat().st_mtime

    print(
        f"conv-live: task={args.task_id} run={run_id} pid={pid} hb_age={hb_age:.0f}s "
        f"log_bytes={log_bytes} log_age={log_age:.0f}s last_api=#{last_api_n} "
        f"last_api_age={None if last_api_age is None else int(last_api_age)}s sid={sid}"
    )

    flat = log_age >= args.flat_sec and (
        last_api_age is None or last_api_age >= args.flat_sec
    )
    if flat:
        print(
            f"FAIL: BANK-CONV-LIVE-WD-1 — running+fresh-hb but transcript flat "
            f"{log_age:.0f}s and API idle "
            f"{'unknown' if last_api_age is None else f'{last_api_age:.0f}s'} "
            f"(threshold {args.flat_sec}s). Lead: reclaim + stamp stall-terminal.",
            file=sys.stderr,
        )
        return 1
    print("OK: conversation progress within flat threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
