#!/usr/bin/env python3
"""O-NOPUSHPR — decide whether a missing new PipelineRun is fatal.

When git push advanced commits (push_uptodate != 1), a NEW PipelineRun is
required. Judging a stale prior Succeeded run is a false ship (V10 S06).

Usage:
  nopushpr-decide.py <push_uptodate:0|1> <prev_name> <current_name>
Prints one of: proceed | no-trigger | judge-existing
"""
from __future__ import annotations

import sys


def decide(push_uptodate: str, prev: str, name: str) -> str:
    if name and name != prev:
        return "proceed"
    if push_uptodate == "1":
        return "judge-existing"
    return "no-trigger"


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: nopushpr-decide.py <push_uptodate> <prev> <name>", file=sys.stderr)
        return 2
    print(decide(sys.argv[1], sys.argv[2], sys.argv[3]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
