#!/usr/bin/env python3
"""Run scoped test-compile gate (S-010 #1b + Architect E-20260811T175305Z Class A).

Delegates to run-scoped-compile-gate.py when --body is provided (required on live
implementer seats). Whole-tree mvn alone is no longer the acceptance signal.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task-id", required=True)
    ap.add_argument(
        "--body",
        required=True,
        help="Typed body JSON — scope filter uses files_writable",
    )
    ap.add_argument(
        "--paths",
        action="append",
        default=[],
        help="Dest paths this gate covers (recorded; repeatable)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    scoped = Path(__file__).resolve().parent / "run-scoped-compile-gate.py"
    cmd = [
        sys.executable,
        str(scoped),
        str(root),
        "--task-id",
        args.task_id,
        "--body",
        args.body,
        "--goal",
        "test-compile",
    ]
    cp = subprocess.run(cmd, text=True)
    return cp.returncode


if __name__ == "__main__":
    raise SystemExit(main())
