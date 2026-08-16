#!/usr/bin/env python3
"""B-16: print M3 attach skills from a typed body (one name per line).

Always includes check-spec-readiness (lint). Then identity.operand_skills
from the body. phase-dispatch.yaml skills[] is the allow-list on disk, not
the attach-all-five bundle.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LINT_SKILL = "check-spec-readiness"


def attach_skills(body: dict) -> list[str]:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    operand = ident.get("operand_skills") or []
    if isinstance(operand, str):
        operand = [operand]
    out: list[str] = []
    seen: set[str] = set()

    def add(name: object) -> None:
        n = str(name or "").strip()
        if n and n not in seen:
            seen.add(n)
            out.append(n)

    add(LINT_SKILL)
    if isinstance(operand, list):
        for s in operand:
            add(s)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Print B-16 M3 attach skills from a typed body JSON (one per line)."
    )
    p.add_argument("body", help="path to typed M3 body JSON")
    args = p.parse_args(argv)
    path = Path(args.body)
    if not path.is_file():
        print(f"FAIL: missing body {path}", file=sys.stderr)
        return 1
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: cannot read body: {exc}", file=sys.stderr)
        return 1
    if not isinstance(body, dict):
        print("FAIL: body is not an object", file=sys.stderr)
        return 1
    for name in attach_skills(body):
        print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
