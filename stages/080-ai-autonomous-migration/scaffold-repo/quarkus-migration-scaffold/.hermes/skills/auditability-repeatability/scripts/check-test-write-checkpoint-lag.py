#!/usr/bin/env python3
"""REFUSE when src/test files exist on disk but checkpoint was not stamped.

Proving-min for Deputy E-121112Z: the stamp action must not be skippable.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA = "rhoai3.implementer-checkpoint/v1"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checkpoint")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    ck_path = Path(args.checkpoint)
    root = Path(args.root).resolve()
    if not ck_path.is_file():
        print(f"FAIL: checkpoint missing: {ck_path}", file=sys.stderr)
        return 1
    ck = json.loads(ck_path.read_text(encoding="utf-8"))
    if ck.get("schema") != SCHEMA:
        print(f"FAIL: bad schema {ck.get('schema')!r}", file=sys.stderr)
        return 1
    work = list(ck.get("work_list") or [])
    done = set(ck.get("completed") or [])
    lagging = []
    for p in work:
        if not (p.startswith("src/test/") or "/src/test/" in p):
            continue
        if p in done:
            continue
        if (root / p).is_file():
            lagging.append(p)
    nxt = ck.get("next")
    if nxt and (root / str(nxt)).is_file() and nxt not in done:
        if nxt not in lagging:
            lagging.append(str(nxt))
    if lagging:
        print(
            "FAIL: src/test checkpoint lag — files on disk not stamped "
            f"(n={len(lagging)}). Run sync-checkpoint-from-test-writes.py. "
            f"paths={lagging[:8]}{'…' if len(lagging) > 8 else ''}",
            file=sys.stderr,
        )
        return 1
    print("OK: no src/test checkpoint lag")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
