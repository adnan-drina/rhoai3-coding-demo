#!/usr/bin/env python3
"""Fail-closed: active doctrine/reference markdown must not carry EOL Status.

GR1 / GRT: retired prose lives under tmp/governance-retired/, not as active
references next to lints. Scans .hermes/**/references/*.md for EOL Status.

Usage:
  python3 check-contract-lifecycle.py --root .
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

STATUS_EOL = re.compile(
    r"(?im)^\s*\*\*Status:\*\*\s*.*\b(retired|superseded|obsolete)\b"
)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exit: 0=clean, 1=tombstone in active refs, 2=usage",
    )
    ap.add_argument("--root", default=".", help="scaffold root")
    args = ap.parse_args()
    root = Path(args.root).resolve()

    # Fail if legacy governance/contracts still present
    legacy = root / "governance" / "contracts"
    if legacy.is_dir() and any(legacy.glob("*.md")):
        print(
            f"FAIL: governance/contracts/ still has active markdown "
            f"(GRT: relocate or attic) under {legacy}",
            file=sys.stderr,
        )
        return 1

    bad: list[str] = []
    checked = 0
    for path in (root / ".hermes").rglob("references/*.md"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        checked += 1
        if STATUS_EOL.search(text):
            bad.append(str(path.relative_to(root)))

    if bad:
        print(
            "FAIL: retired/superseded/obsolete Status in active .hermes references "
            "(move to tmp/governance-retired/):",
            file=sys.stderr,
        )
        for rel in bad:
            print(f"  {rel}", file=sys.stderr)
        return 1

    # Attic is outside the hermetic seat (demo-repo tmp/). Do not hardcode host paths.
    n_attic = 0
    local_attic = root / "tmp" / "governance-retired"
    if local_attic.is_dir():
        n_attic = sum(1 for _ in local_attic.rglob("*.md"))
    print(
        f"OK: contract lifecycle — no EOL under .hermes/**/references/ "
        f"(checked={checked}; local_attic_md={n_attic})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
