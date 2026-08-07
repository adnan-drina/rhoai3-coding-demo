#!/usr/bin/env python3
"""O-NULLACTIONREOPEN — thin adapter over ADR-48 completion_authority.

Historically this module detected force-reopen history + already-complete
wording. ADR-48 REV-1 makes the rule structural: prose completion claims are
refused whenever ledger state ≠ ADVANCE (typed REOPEN leaves READY).

Exit codes (unchanged contract for supervisor):
  0 — accept the null_action file
  1 — reject completion claim (caller must continue)
  2 — usage / IO error
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HARNESS_DIR = Path(__file__).resolve().parent
if str(_HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(_HARNESS_DIR))

from completion_authority import resolve_null_action  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", required=True, help="task id")
    ap.add_argument("--reason-file", required=True, help="escalation-noaction path")
    ap.add_argument(
        "--ledger",
        default="migration/task-lifecycle.json",
        help="lifecycle ledger path",
    )
    ap.add_argument("--root", default=".", help="repo root")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    rf = Path(args.reason_file)
    if not rf.is_file():
        print(f"O-NULLACTIONREOPEN: reason file missing: {rf}", file=sys.stderr)
        return 2
    reason = rf.read_text(encoding="utf-8", errors="replace")
    verdict, detail = resolve_null_action(
        args.task,
        reason,
        ledger_path=root / args.ledger,
        root=root,
    )
    if verdict == "REJECT_COMPLETION_CLAIM":
        print(f"O-NULLACTIONREOPEN: {detail}", file=sys.stderr)
        return 1
    print(f"O-NULLACTIONREOPEN: accept ({verdict})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
