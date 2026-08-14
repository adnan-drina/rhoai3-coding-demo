#!/usr/bin/env python3
"""Fail-closed: active contracts must not carry retired/superseded/obsolete status.

GR1 / Deputy E-20260814T081104Z — retired contracts live under
governance/retired/, not governance/contracts/.

Usage:
  python3 check-contract-lifecycle.py --root .
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Match Status lines that declare end-of-life (not "binding", "bound", etc.).
STATUS_EOL = re.compile(
    r"(?im)^\s*\*\*Status:\*\*\s*.*\b(retired|superseded|obsolete)\b"
)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exit: 0=clean, 1=tombstone in active contracts/, 2=usage",
    )
    ap.add_argument("--root", default=".", help="scaffold root")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    contracts = root / "governance" / "contracts"
    if not contracts.is_dir():
        print(f"FAIL: missing {contracts}", file=sys.stderr)
        return 2

    bad: list[str] = []
    for path in sorted(contracts.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if STATUS_EOL.search(text):
            bad.append(str(path.relative_to(root)))

    if bad:
        print(
            "FAIL: retired/superseded/obsolete contracts must live under "
            "governance/retired/ (GR1 E-20260814T081104Z):",
            file=sys.stderr,
        )
        for rel in bad:
            print(f"  {rel}", file=sys.stderr)
        return 1

    retired = root / "governance" / "retired"
    n_retired = (
        len(list(retired.glob("*.md"))) if retired.is_dir() else 0
    )
    print(
        f"OK: contract lifecycle — no EOL status under governance/contracts/ "
        f"(retired attic files={n_retired})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
