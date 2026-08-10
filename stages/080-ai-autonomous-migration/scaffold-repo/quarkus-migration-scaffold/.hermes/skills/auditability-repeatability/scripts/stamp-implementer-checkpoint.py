#!/usr/bin/env python3
"""Mark dest path(s) completed on an implementer checkpoint (resume seam)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "rhoai3.implementer-checkpoint/v1"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checkpoint")
    ap.add_argument(
        "--completed",
        action="append",
        default=[],
        help="Dest-relative path completed (repeatable)",
    )
    args = ap.parse_args()
    path = Path(args.checkpoint)
    if not path.is_file():
        print(f"FAIL: checkpoint missing: {path}", file=sys.stderr)
        return 1
    if not args.completed:
        print("FAIL: pass --completed PATH", file=sys.stderr)
        return 1
    ck = json.loads(path.read_text(encoding="utf-8"))
    if ck.get("schema") != SCHEMA:
        print(f"FAIL: bad schema {ck.get('schema')!r}", file=sys.stderr)
        return 1
    work = list(ck.get("work_list") or [])
    done = list(ck.get("completed") or [])
    for raw in args.completed:
        p = raw.replace("\\", "/")
        if "/projects/modernized/" in p:
            p = p.split("/projects/modernized/", 1)[1]
        if p not in work:
            print(f"FAIL: {p} not in work_list", file=sys.stderr)
            return 1
        if p not in done:
            done.append(p)
    remaining = [p for p in work if p not in done]
    ck["completed"] = done
    ck["next"] = remaining[0] if remaining else None
    ck["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps(ck, indent=2) + "\n", encoding="utf-8")
    print(f"OK: completed={len(done)}/{len(work)} next={ck['next']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
