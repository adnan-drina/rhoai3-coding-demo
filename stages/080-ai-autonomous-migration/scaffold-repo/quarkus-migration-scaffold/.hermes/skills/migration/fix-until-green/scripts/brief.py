#!/usr/bin/env python3
"""Print the head cluster's brief: the only thing a worker edits.

The brief is derived from the sealed work list (never written by a
model): cluster id, kind, write set, and every item (rule / compiler
code, line, detail). Exit 0 with the brief; 1 when the work list has no
open cluster (the loop is done or fully deferred).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loop_common import ensure_hermes_lib  # noqa: E402

ensure_hermes_lib()
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.paths import LOOP_DIR, WORKLIST  # noqa: E402
from planner.worklist import head_cluster, items_of  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--cluster", default="", help="a specific cluster id (default: the head)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    doc = load_json(root / WORKLIST)
    cluster = next((c for c in doc["clusters"] if c["id"] == args.cluster), None) if args.cluster else head_cluster(doc)
    if cluster is None:
        print("REFUSE: LOOP_NO_OPEN_CLUSTER (work list head is empty)", file=sys.stderr)
        return 1
    brief = {
        "schema": "rhoai3.loop-brief/v1",
        "cluster": cluster,
        "items": items_of(doc, cluster),
        "measure": doc["measure"],
        "rule": "Edit only the write set. Do not edit tests. Do not touch pom.xml unless it is in the write set. Then run run-verify.sh and advance.py; the measure decides, not you.",
    }
    write_canonical(root / LOOP_DIR / ("brief-%s.json" % cluster["id"].replace(":", "-")), brief)
    print(json.dumps(brief, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
