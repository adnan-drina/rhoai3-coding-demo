#!/usr/bin/env python3
"""Fail if m4-verdict-schema.md drifts from the parser's required fields."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
REF = SKILL / "references" / "m4-verdict-schema.md"

# Keep in lockstep with assert-m4-verdict-schema.py (hyphenated filename).
REQUIRED_FIELDS = (
    "gate",
    "phase",
    "ran",
    "verdict",
    "ship",
    "failed_floors",
    "floors",
)
FLOOR_FIELDS = ("name", "rc", "idle")
CODES = (
    "M4_VERDICT_SCHEMA",
    "FAILED_FLOOR_AS_IDLE",
    "ACCEPT_WITH_FAILED_FLOOR",
)


def main() -> int:
    if not REF.is_file():
        print("FAIL: missing %s" % REF, file=sys.stderr)
        return 1
    text = REF.read_text(encoding="utf-8")
    bad = 0
    for field in REQUIRED_FIELDS:
        if field not in text:
            print("FAIL: m4-verdict-schema.md missing field %s" % field, file=sys.stderr)
            bad = 1
    for field in FLOOR_FIELDS:
        if field not in text:
            print("FAIL: m4-verdict-schema.md missing floor field %s" % field, file=sys.stderr)
            bad = 1
    for code in CODES:
        if code not in text:
            print("FAIL: m4-verdict-schema.md missing code %s" % code, file=sys.stderr)
            bad = 1
    if "failed_floors" not in text:
        print("FAIL: reference must name failed_floors", file=sys.stderr)
        bad = 1
    if "assert-m4-verdict-schema.py" not in text:
        print("FAIL: reference must name the parser", file=sys.stderr)
        bad = 1
    if bad:
        return 1
    print("OK: m4-verdict-schema.md in sync with parser fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
