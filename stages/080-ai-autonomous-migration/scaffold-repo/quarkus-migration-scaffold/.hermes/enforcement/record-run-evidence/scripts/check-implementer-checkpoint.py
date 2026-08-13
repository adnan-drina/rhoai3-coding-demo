#!/usr/bin/env python3
"""Validate implementer checkpoint shape and resume invariants."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA = "rhoai3.implementer-checkpoint/v1"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checkpoint")
    ap.add_argument(
        "--require-incomplete",
        action="store_true",
        help="FAIL if next is null (expect resume work remaining)",
    )
    args = ap.parse_args()
    path = Path(args.checkpoint)
    if not path.is_file():
        print(f"FAIL: checkpoint missing: {path}", file=sys.stderr)
        return 1
    ck = json.loads(path.read_text(encoding="utf-8"))
    if ck.get("schema") != SCHEMA:
        print(f"FAIL: schema want {SCHEMA} got {ck.get('schema')!r}", file=sys.stderr)
        return 1
    for key in ("task_id", "body_path", "body_sha256", "work_list", "completed"):
        if key not in ck:
            print(f"FAIL: missing {key}", file=sys.stderr)
            return 1
    work = ck["work_list"]
    done = ck["completed"]
    if not isinstance(work, list) or not work:
        print("FAIL: work_list empty", file=sys.stderr)
        return 1
    if not isinstance(done, list):
        print("FAIL: completed not a list", file=sys.stderr)
        return 1
    if len(done) != len(set(done)):
        print("FAIL: completed has duplicates", file=sys.stderr)
        return 1
    for p in done:
        if p not in work:
            print(f"FAIL: completed path not in work_list: {p}", file=sys.stderr)
            return 1
    if len(ck.get("body_sha256") or "") != 64:
        print("FAIL: body_sha256 must be 64-char hex", file=sys.stderr)
        return 1
    remaining = [p for p in work if p not in done]
    nxt = ck.get("next")
    expect = remaining[0] if remaining else None
    if nxt != expect:
        print(
            f"FAIL: next={nxt!r} but expected {expect!r} from work_list\\completed",
            file=sys.stderr,
        )
        return 1
    if args.require_incomplete and nxt is None:
        print("FAIL: --require-incomplete but next is null", file=sys.stderr)
        return 1
    print(
        f"OK: checkpoint task={ck['task_id']} "
        f"completed={len(done)}/{len(work)} next={nxt}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
