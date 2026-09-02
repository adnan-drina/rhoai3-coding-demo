#!/usr/bin/env python3
"""Refuse an M4 verdict object that omits failed_floors or calls a fail idle.

Operator 143706ZO: dest-8 invented a shape with no failed-floor field.
This parser is the schema; check-release-readiness remains lint.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

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
ACCEPT_TOKENS = frozenset({"PROVISIONAL_ACCEPT", "ACCEPT", "SCOPED_ACCEPT"})


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def load_verdict(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("verdict is not an object")
    return data


def check(doc: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key in REQUIRED_FIELDS:
        if key not in doc:
            issues.append("M4_VERDICT_SCHEMA missing %s" % key)
    if issues:
        return issues

    if str(doc.get("gate") or "") != "M4_VERDICT":
        issues.append("M4_VERDICT_SCHEMA gate %r" % doc.get("gate"))
    if str(doc.get("phase") or "").upper() != "M4":
        issues.append("M4_VERDICT_SCHEMA phase %r" % doc.get("phase"))
    if doc.get("ship") is True:
        issues.append("M4_VERDICT_SCHEMA ship must be false at M4")

    failed = doc.get("failed_floors")
    if not isinstance(failed, list):
        issues.append("M4_VERDICT_SCHEMA failed_floors must be a list")
        return issues
    failed_names = [str(x).strip() for x in failed if str(x).strip()]

    floors = doc.get("floors")
    if not isinstance(floors, list) or not floors:
        issues.append("M4_VERDICT_SCHEMA floors must be a non-empty list")
        return issues

    seen: set[str] = set()
    reason = str(doc.get("reason") or "")
    for i, row in enumerate(floors):
        if not isinstance(row, dict):
            issues.append("M4_VERDICT_SCHEMA floors[%d] not an object" % i)
            continue
        for key in FLOOR_FIELDS:
            if key not in row:
                issues.append("M4_VERDICT_SCHEMA floors[%d] missing %s" % (i, key))
        name = str(row.get("name") or "").strip()
        rc = row.get("rc")
        idle = row.get("idle")
        if not name:
            issues.append("M4_VERDICT_SCHEMA floors[%d] name empty" % i)
            continue
        seen.add(name)
        if not isinstance(rc, int) or isinstance(rc, bool):
            issues.append("M4_VERDICT_SCHEMA floors[%d] rc must be int" % i)
            continue
        if idle is not True and idle is not False:
            issues.append("M4_VERDICT_SCHEMA floors[%d] idle must be bool" % i)
            continue
        if rc != 0 and idle is True:
            issues.append(
                "FAILED_FLOOR_AS_IDLE %s rc=%s idle=true" % (name, rc)
            )
        if rc != 0 and name not in failed_names:
            issues.append("M4_VERDICT_SCHEMA %s rc=%s missing from failed_floors" % (name, rc))
        if rc == 0 and name in failed_names:
            issues.append("M4_VERDICT_SCHEMA %s rc=0 must not be in failed_floors" % name)
        if idle is True and name in failed_names:
            issues.append("FAILED_FLOOR_AS_IDLE %s in failed_floors with idle=true" % name)
        if rc != 0 and "idle" in reason.lower():
            issues.append(
                "FAILED_FLOOR_AS_IDLE reason names idle while %s rc=%s" % (name, rc)
            )

    for name in failed_names:
        if name not in seen:
            issues.append("M4_VERDICT_SCHEMA failed_floors %s not in floors[]" % name)

    token = str(doc.get("verdict") or "").strip().upper().replace("-", "_")
    if failed_names and token in ACCEPT_TOKENS:
        issues.append(
            "ACCEPT_WITH_FAILED_FLOOR verdict=%s failed_floors=%s"
            % (token, failed_names)
        )
    if token == "ACCEPT":
        issues.append("M4_VERDICT_SCHEMA M4 must not emit ACCEPT")
    return issues


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("verdict", type=Path)
    args = ap.parse_args(argv)
    path = args.verdict
    if not path.is_file():
        return _fail("verdict file missing: " + str(path))
    try:
        doc = load_verdict(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return _fail("unreadable verdict: " + str(exc))
    issues = check(doc)
    if issues:
        for issue in issues:
            print("FAIL: " + issue, file=sys.stderr)
        return 1
    print(
        "OK: m4-verdict schema (failed_floors=%d floors=%d token=%s)"
        % (
            len(doc.get("failed_floors") or []),
            len(doc.get("floors") or []),
            doc.get("verdict"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
