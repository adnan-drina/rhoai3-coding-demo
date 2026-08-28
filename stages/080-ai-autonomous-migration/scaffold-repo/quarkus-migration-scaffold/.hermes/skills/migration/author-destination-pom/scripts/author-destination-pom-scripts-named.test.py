#!/usr/bin/env python3
"""Operator 145553ZO: author-destination-pom must name its worker scripts."""
from __future__ import annotations

import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
TEXT = (SKILL / "SKILL.md").read_text(encoding="utf-8")
REQUIRED = ("parse-platform-gav.py", "check-rh-registry-first.py")


def main() -> int:
    bad = 0
    for name in REQUIRED:
        if name not in TEXT:
            print("FAIL: SKILL.md does not name %s" % name, file=sys.stderr)
            bad = 1
        path = SKILL / "scripts" / name
        if not path.is_file():
            print("FAIL: missing %s" % path, file=sys.stderr)
            bad = 1
    if bad:
        return 1
    print("OK: author-destination-pom names parse-platform-gav and check-rh-registry-first")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
