#!/usr/bin/env python3
"""Harness-driven checkpoint catch-up for src/test writes (Deputy E-121112Z).

Voluntary stamp decays. This script scans the checkpoint work_list for src/test
paths that already exist on disk but are not completed, runs the test-compile
gate once, then stamps them — so the #1b gate is not optional prose.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCHEMA = "rhoai3.implementer-checkpoint/v1"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checkpoint")
    ap.add_argument("--root", default=".")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="List lagging paths only; do not compile/stamp",
    )
    args = ap.parse_args()
    ck_path = Path(args.checkpoint)
    root = Path(args.root).resolve()
    if not ck_path.is_file():
        print(f"FAIL: checkpoint missing: {ck_path}", file=sys.stderr)
        return 1
    ck = json.loads(ck_path.read_text(encoding="utf-8"))
    if ck.get("schema") != SCHEMA:
        print(f"FAIL: bad schema {ck.get('schema')!r}", file=sys.stderr)
        return 1
    work = list(ck.get("work_list") or [])
    done = set(ck.get("completed") or [])
    lagging: list[str] = []
    for p in work:
        if not (p.startswith("src/test/") or "/src/test/" in p):
            continue
        if p in done:
            continue
        if (root / p).is_file():
            lagging.append(p)
    if not lagging:
        print("OK: no src/test disk lag vs checkpoint")
        return 0
    print(f"LAG: {len(lagging)} src/test path(s) on disk but not stamped:")
    for p in lagging:
        print(f"  - {p}")
    if args.dry_run:
        return 1
    scripts = Path(__file__).resolve().parent
    gate = scripts / "run-test-compile-gate.py"
    stamp = scripts / "stamp-implementer-checkpoint.py"
    cmd = [
        sys.executable,
        str(gate),
        str(root),
        "--task-id",
        str(ck.get("task_id") or "unknown"),
    ]
    for p in lagging:
        cmd.extend(["--paths", p])
    cp = subprocess.run(cmd, text=True, capture_output=True)
    sys.stdout.write(cp.stdout or "")
    sys.stderr.write(cp.stderr or "")
    if cp.returncode != 0:
        print(
            "FAIL: test-compile gate red — refuse to stamp lagging writes "
            "(Deputy E-121112Z / #1b-inv)",
            file=sys.stderr,
        )
        return 1
    stamp_cmd = [sys.executable, str(stamp), str(ck_path)]
    for p in lagging:
        stamp_cmd.extend(["--completed", p])
    # Gate already green this turn — stamp still re-runs gate (idempotent OK).
    sp = subprocess.run(stamp_cmd, text=True, capture_output=True)
    sys.stdout.write(sp.stdout or "")
    sys.stderr.write(sp.stderr or "")
    if sp.returncode != 0:
        print("FAIL: stamp after gate failed", file=sys.stderr)
        return 1
    print(f"OK: synced {len(lagging)} lagging src/test path(s) into checkpoint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
