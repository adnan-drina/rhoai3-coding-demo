#!/usr/bin/env python3
"""Restore a VERIFICATION_PENDING candidate onto the product tree.

Does not accept the candidate. Does not run verification. After this:
run-verify.sh --mode acceptance, then advance.py. Exit 0 restored; 1 none;
2 usage.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loop_common import PendingRestoreError, load_issued, load_steps, pending_for, restore_pending_candidate  # noqa: E402
from planner.canonical import write_canonical  # noqa: E402
from planner.paths import LOOP_ISSUED  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--cluster", required=True)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    steps = load_steps(root)
    row = pending_for(steps, args.cluster)
    if row is None:
        print("FAIL: no VERIFICATION_PENDING candidate for %s" % args.cluster, file=sys.stderr)
        return 1
    try:
        restored = restore_pending_candidate(root, args.cluster, row)
    except PendingRestoreError as exc:
        print("FAIL: LOOP_PENDING_CANDIDATE_CHANGED %s" % exc, file=sys.stderr)
        return 1
    issued = row.get("issued") if isinstance(row.get("issued"), dict) else None
    if issued and issued.get("cluster") and not (root / LOOP_ISSUED).is_file():
        write_canonical(root / LOOP_ISSUED, issued)
    elif issued and issued.get("cluster") and load_issued(root) is None:
        write_canonical(root / LOOP_ISSUED, issued)
    print("OK: restored %d path(s) from pending cause=%s card=%s; run run-verify.sh --mode acceptance then advance.py"
          % (len(restored), row.get("cause"), row.get("card")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
