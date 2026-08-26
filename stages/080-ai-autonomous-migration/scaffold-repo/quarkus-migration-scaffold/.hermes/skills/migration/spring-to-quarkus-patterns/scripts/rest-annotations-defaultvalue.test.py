#!/usr/bin/env python3
"""Operator 125400ZO: JAX-RS defaultValue mapping in the REST card. Not dest."""
from __future__ import annotations

import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
REF = SKILL / "references" / "rest-annotations.md"
MD = SKILL / "SKILL.md"


def main() -> int:
    ref = REF.read_text(encoding="utf-8")
    md = MD.read_text(encoding="utf-8")
    bad = 0
    if "rest-query-default" not in ref:
        print("FAIL: rest-annotations.md missing rest-query-default", file=sys.stderr)
        bad = 1
    if "@DefaultValue" not in ref:
        print("FAIL: rest-annotations.md missing @DefaultValue", file=sys.stderr)
        bad = 1
    if "@QueryParam(defaultValue" not in ref:
        print(
            "FAIL: rest-annotations.md must REJECT @QueryParam(defaultValue",
            file=sys.stderr,
        )
        bad = 1
    if "@DefaultValue" not in md:
        print("FAIL: SKILL.md pitfalls must name @DefaultValue", file=sys.stderr)
        bad = 1
    if bad:
        return 1
    print("OK: rest-query-default maps RequestParam defaultValue to @DefaultValue")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
