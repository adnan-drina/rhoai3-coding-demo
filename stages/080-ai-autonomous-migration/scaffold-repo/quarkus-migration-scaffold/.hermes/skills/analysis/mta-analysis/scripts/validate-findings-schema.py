#!/usr/bin/env python3
"""Validate preserved mta-findings.json against provisional schema (W2 §11.5)."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def fail(msg: str) -> int:
    print(f"FAIL: {msg}", file=sys.stderr)
    return 1


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "migration/mta-findings.json")
    if not path.is_file():
        return fail(f"missing {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "rhoai3.mta-findings/v1-provisional":
        return fail("schema must be rhoai3.mta-findings/v1-provisional")
    ev = data.get("execution_evidence")
    if not isinstance(ev, dict):
        return fail("execution_evidence required")
    if "analyzer_ran" not in ev:
        return fail("execution_evidence.analyzer_ran required")
    if "violations" not in data or not isinstance(data["violations"], dict):
        return fail("violations map required")
    for rule, v in data["violations"].items():
        if not isinstance(v, dict):
            return fail(f"{rule}: not an object")
        if not (v.get("ruleID") or rule):
            return fail(f"{rule}: ruleID required")
        if not v.get("category"):
            return fail(f"{rule}: category required")
        incidents = v.get("incidents")
        if incidents is None:
            return fail(f"{rule}: incidents required (list, may be empty only if intentional)")
        if not isinstance(incidents, list):
            return fail(f"{rule}: incidents must be a list")
        for i, inc in enumerate(incidents):
            for key in ("uri", "lineNumber", "message", "codeSnip"):
                if key not in inc or inc[key] in (None, ""):
                    return fail(f"{rule} incident[{i}]: {key} required in preserved model")
    print(f"OK: {path} matches provisional mta-findings schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
