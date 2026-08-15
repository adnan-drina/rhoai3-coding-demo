#!/usr/bin/env python3
"""AD-009 §3 step 6 — hard-enforce max_runtime_seconds (not advisory %).

Scans HERMES_HOME/kanban.db for running tasks whose elapsed time exceeds
max_runtime_seconds. For each over-budget task:

  1. Write evidence/verdicts/max-runtime-<task_id>.json
     (block_class=max_runtime_exceeded)
  2. If --apply: hermes kanban block with typed reason (does not MiniMax)

Exit 0 when none over budget (or all handled). Exit 2 when any over budget
were found (even if only reported). Exit 1 on errors.

Observation-only stuck watchdog remains separate (kanban-stuck-watchdog.py).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def hermes_home(explicit: str, root: Path) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("HERMES_HOME", "").strip()
    if env:
        return Path(env).expanduser()
    return root / ".hermes" / "home"


def parse_epoch(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return ts
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return parse_epoch(int(text))
    try:
        from datetime import datetime as dt

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return dt.fromisoformat(text).timestamp()
    except ValueError:
        return None


def write_stamp(
    root: Path,
    *,
    task_id: str,
    max_runtime_seconds: int,
    elapsed_seconds: int,
    phase_hint: str,
) -> Path:
    out_dir = root / "evidence" / "verdicts"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = {
        "schema": "rhoai3.max-runtime-exceeded/v1",
        "ad": "AD-009",
        "block_class": "max_runtime_exceeded",
        "task_id": task_id,
        "phase_hint": phase_hint or None,
        "max_runtime_seconds": max_runtime_seconds,
        "elapsed_seconds": elapsed_seconds,
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "minimax_escalate": False,
        "note": (
            "Hard budget exceeded — advisory % is not a control; typed block "
            "required (AD-009 §3 step 6)"
        ),
    }
    path = out_dir / f"max-runtime-{task_id}.json"
    path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    return path


def list_over_budget(db_path: Path, now: float) -> list[dict]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cols = {r[1].lower(): r[1] for r in conn.execute("PRAGMA table_info(tasks)")}
        if "id" not in cols or "status" not in cols:
            raise SystemExit(f"enforce-max-runtime-hard: unexpected schema in {db_path}")
        id_c = cols["id"]
        status_c = cols["status"]
        max_c = cols.get("max_runtime_seconds")
        started_c = cols.get("started_at") or cols.get("updated_at")
        title_c = cols.get("title") or cols.get("name")
        if not max_c or not started_c:
            raise SystemExit(
                "enforce-max-runtime-hard: tasks table missing "
                "max_runtime_seconds/started_at"
            )
        q = (
            f'SELECT "{id_c}" AS id, "{status_c}" AS status, '
            f'"{max_c}" AS max_runtime_seconds, "{started_c}" AS started_at'
            + (f', "{title_c}" AS title' if title_c else ", '' AS title")
            + f' FROM tasks WHERE lower(cast("{status_c}" as text)) = ?'
        )
        rows = []
        for r in conn.execute(q, ("running",)):
            max_rt = r["max_runtime_seconds"]
            if max_rt is None:
                # Missing pin is itself a defect — report as over-budget with 0
                rows.append(
                    {
                        "id": str(r["id"]),
                        "max_runtime_seconds": 0,
                        "elapsed_seconds": 0,
                        "title": str(r["title"] or ""),
                        "missing_pin": True,
                    }
                )
                continue
            started = parse_epoch(r["started_at"])
            if started is None:
                continue
            elapsed = int(now - started)
            if elapsed > int(max_rt):
                rows.append(
                    {
                        "id": str(r["id"]),
                        "max_runtime_seconds": int(max_rt),
                        "elapsed_seconds": elapsed,
                        "title": str(r["title"] or ""),
                        "missing_pin": False,
                    }
                )
        return rows
    finally:
        conn.close()


def phase_hint(_title: str) -> str:
    # BV19-3: do not derive phase from the card title. The link graph is the DAG.
    return ""


def kanban_block(task_id: str, reason: str) -> None:
    subprocess.check_call(["hermes", "kanban", "block", task_id, reason])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/projects/modernized")
    ap.add_argument("--hermes-home", default="")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Stamp + hermes kanban block (default: report + stamp only)",
    )
    ap.add_argument(
        "--stamp",
        action="store_true",
        default=True,
        help="Write verdict stamps (default on)",
    )
    ap.add_argument("--no-stamp", action="store_true")
    args = ap.parse_args()
    root = Path(args.root)
    home = hermes_home(args.hermes_home, root)
    db_path = home / "kanban.db"
    if not db_path.is_file():
        print(f"AD-009: no kanban.db at {db_path} — nothing to enforce")
        return 0

    now = time.time()
    over = list_over_budget(db_path, now)
    if not over:
        print("AD-009: no running tasks over max_runtime_seconds")
        return 0

    do_stamp = args.stamp and not args.no_stamp
    for item in over:
        tid = item["id"]
        hint = phase_hint(item["title"])
        pct = (
            100.0 * item["elapsed_seconds"] / item["max_runtime_seconds"]
            if item["max_runtime_seconds"]
            else float("inf")
        )
        label = "MISSING_PIN" if item.get("missing_pin") else f"{pct:.0f}% of budget"
        print(
            f"AD-009 HARD BUDGET: task={tid} elapsed={item['elapsed_seconds']}s "
            f"max={item['max_runtime_seconds']}s ({label}) title={item['title']!r}"
        )
        path = None
        if do_stamp:
            path = write_stamp(
                root,
                task_id=tid,
                max_runtime_seconds=item["max_runtime_seconds"],
                elapsed_seconds=item["elapsed_seconds"],
                phase_hint=hint,
            )
            print(f"AD-009: stamped {path}")
        if args.apply:
            reason = (
                f"AD-009 block_class=max_runtime_exceeded "
                f"elapsed={item['elapsed_seconds']}s "
                f"max={item['max_runtime_seconds']}s"
                + (f" stamp={path.name}" if path else "")
            )
            try:
                kanban_block(tid, reason)
                print(f"AD-009: blocked {tid}")
            except (subprocess.CalledProcessError, FileNotFoundError) as exc:
                print(f"AD-009: block failed for {tid}: {exc}", file=sys.stderr)
                return 1

    print(
        "AD-009: hard enforce found over-budget task(s) — "
        "typed max_runtime_exceeded; do not MiniMax",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
