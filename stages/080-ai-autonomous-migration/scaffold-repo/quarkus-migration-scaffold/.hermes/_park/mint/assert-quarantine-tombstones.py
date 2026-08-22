#!/usr/bin/env python3
"""Fail-closed: tombstoned destination paths must stay absent.

Architect E-20260811T170706Z Class A — quarantine must survive dispatch.

Usage:
  python3 assert-quarantine-tombstones.py /projects/modernized
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA = "rhoai3.quarantine-tombstones/v1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    args = ap.parse_args()
    root = args.root.resolve()
    tomb_path = root / "evidence" / "quarantine" / "tombstones.json"
    if not tomb_path.is_file():
        print("OK: no tombstones.json (nothing to assert)")
        return 0
    try:
        data = json.loads(tomb_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"FAIL: cannot parse {tomb_path}: {exc}", file=sys.stderr)
        return 2
    if data.get("schema") and data.get("schema") != SCHEMA:
        print(
            f"FAIL: unexpected schema {data.get('schema')!r} (want {SCHEMA})",
            file=sys.stderr,
        )
        return 2
    resurrected: list[str] = []
    for t in data.get("tombstones") or []:
        if not isinstance(t, dict):
            continue
        rel = str(t.get("path") or "").strip().lstrip("./")
        if not rel:
            continue
        dest = root / rel
        if dest.exists():
            resurrected.append(rel)
    if resurrected:
        print(
            "FAIL: quarantine tombstones resurrected in destination "
            "(dispatch snapshot / sync defect):",
            file=sys.stderr,
        )
        for rel in resurrected:
            print(f"  PRESENT {rel}", file=sys.stderr)
        print(
            "Wipe again, re-register tombstones, purge restorer, then re-assert.",
            file=sys.stderr,
        )
        return 1
    n = len(data.get("tombstones") or [])
    print(f"OK: quarantine tombstones hold (n={n})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
