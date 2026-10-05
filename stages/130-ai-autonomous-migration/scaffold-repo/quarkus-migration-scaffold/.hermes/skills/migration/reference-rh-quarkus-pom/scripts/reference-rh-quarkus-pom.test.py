#!/usr/bin/env python3
"""Operator 123728ZO: skill body must make exit 124 legible. Not dest."""
from __future__ import annotations

import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
MD = SKILL / "SKILL.md"
REPOS = SKILL / "references" / "maven-repos.md"


def main() -> int:
    text = MD.read_text(encoding="utf-8")
    repos = REPOS.read_text(encoding="utf-8")
    bad = 0
    for needle, where in (
        ("--files-only", text),
        ("120", text),
        ("124", text),
        ("timeout", text.lower()),
        ("--files-only", repos),
        ("124", repos),
    ):
        blob = where if where is text or where is repos else where
        if needle not in blob and needle not in blob.lower():
            print("FAIL: missing %r" % needle, file=sys.stderr)
            bad = 1
    if "timeout, not a REFUSE" not in text and "timeout, not a refusal" not in text.lower():
        print("FAIL: SKILL.md must say 124 is a timeout not a refusal", file=sys.stderr)
        bad = 1
    if bad:
        return 1
    print("OK: reference-rh-quarkus-pom names --files-only, >=120s, 124=timeout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
