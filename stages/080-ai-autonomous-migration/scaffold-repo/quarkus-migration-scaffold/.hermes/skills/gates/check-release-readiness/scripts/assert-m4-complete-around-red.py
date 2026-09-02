#!/usr/bin/env python3
"""Refuse an M4 ACCEPT destfile when a bound floor exited non-zero.

Architect ``130758ZA`` / Operator ``130951ZO``. dest-8 ``m4-verdict.json``
wrote ``PROVISIONAL_ACCEPT`` and called AR-2.8 ``idle`` after
``check-product-tests.py`` exit 1. This lint takes the *measured* floor rc
(``--floor-rc``); it does not re-run AR-2.8. ``idle`` is reserved for
genuine idles (floor rc 0).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ACCEPT_TOKENS = frozenset({"PROVISIONAL_ACCEPT", "ACCEPT", "SCOPED_ACCEPT"})


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def load_verdict(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("verdict is not an object")
    return data


def token_of(doc: dict) -> str:
    for key in ("verdict", "token", "result"):
        val = doc.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def failed_floor_recorded_as_idle(doc: dict, floor_name: str) -> bool:
    """True when a *value* claims the failed floor is idle.

    Architect ``193642ZA``: do not ``\"idle\" in json.dumps(doc).lower()`` —
    that matches the key name when every value is ``false``.
    """
    floors = doc.get("floors")
    if isinstance(floors, list):
        for row in floors:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or row.get("floor") or "")
            if name and name != floor_name:
                continue
            if row.get("idle") is True:
                return True
    if doc.get("idle") is True:
        return True
    for key in ("reason", "notes", "summary"):
        val = doc.get(key)
        if isinstance(val, str) and "idle" in val.lower():
            return True
    return False


def check(doc: dict, floor_rc: int, floor_name: str) -> list[str]:
    issues: list[str] = []
    token = token_of(doc)
    if floor_rc != 0 and token in ACCEPT_TOKENS:
        issues.append(
            "complete-around-red: %s is %s while %s floor-rc=%s"
            % (floor_name, token, floor_name, floor_rc)
        )
    if floor_rc != 0 and failed_floor_recorded_as_idle(doc, floor_name):
        issues.append(
            "failed floor recorded as idle: %s floor-rc=%s (idle is reserved "
            "for genuine idles)" % (floor_name, floor_rc)
        )
    return issues


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verdict", required=True, type=Path)
    ap.add_argument("--floor-rc", required=True, type=int)
    ap.add_argument("--floor-name", default="check-product-tests")
    args = ap.parse_args(argv)
    path = args.verdict
    if not path.is_file():
        return _fail("verdict file missing: " + str(path))
    try:
        doc = load_verdict(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return _fail("unreadable verdict: " + str(exc))
    issues = check(doc, args.floor_rc, args.floor_name)
    if issues:
        for issue in issues:
            print("FAIL: " + issue, file=sys.stderr)
        return 1
    print(
        "OK: M4 complete-around lint (%s floor-rc=%s token=%s)"
        % (args.floor_name, args.floor_rc, token_of(doc) or "<none>")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
