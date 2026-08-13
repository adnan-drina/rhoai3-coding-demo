#!/usr/bin/env python3
"""AD-S S.4 — golden scaffold must not contain a committed/provisioned .specify/ tree.

Provision creates .specify/ only under live workspaces (/projects/*). Tip trees
must stay clean; replace the retired DO_NOT_COMMIT_SPECIFY note with this assert.

Usage:
  python3 check-specify-absent.py --root .
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exit: 0=absent, 1=.specify present, 2=usage",
    )
    ap.add_argument("--root", default=".", help="scaffold root")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"FAIL: bad root {root}", file=sys.stderr)
        return 2
    specify = root / ".specify"
    if specify.exists():
        print(
            f"FAIL: {specify} present — golden must not ship Spec Kit workspace "
            "(AD-S S.4; provision owns init under /projects/*)",
            file=sys.stderr,
        )
        return 1
    print("OK: .specify/ absent from golden root")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
