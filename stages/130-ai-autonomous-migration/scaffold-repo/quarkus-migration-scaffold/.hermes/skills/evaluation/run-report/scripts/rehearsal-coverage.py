#!/usr/bin/env python3
"""Behaviour coverage by scenario kind (R-1, M-3): every (mode, kind, resource) cell of the run's own corpus and the
verdict a comparison of the current candidate gave it; cells nobody compared are listed, never assumed covered.

Usage: rehearsal-coverage.py --root . [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))
from planner.rehearsal_coverage import of_root  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = of_root(Path(a.root))
    if a.json:
        print(json.dumps(doc, indent=1, sort_keys=True))
        return 0
    s = doc["summary"]
    print("REHEARSAL COVERAGE: %d cell(s) -- %d PASS, %d FAIL, %d not compared" % (s["cells"], s["pass"], s["fail"], s["not_compared"]))
    for r in doc["cells"]:
        print("  %-8s %-26s %-14s %-13s %d/%d compared%s" % (r["mode"], r["kind"], r["resource"], r["state"], r["compared"],
              len(r["scenarios"]), ("  failing: " + ", ".join(r["failing"][:4])) if r["failing"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
