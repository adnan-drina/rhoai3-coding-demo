#!/usr/bin/env python3
"""Per-unit role diff between two git tips (ADR-32 §Validation / PROFILE reproducibility).

Usage (in workspace or with ROOT override):
  python3 scripts/track-b/profile-desk/rolediff.py 54ee1d2 <new-tip>
  ROOT=/projects/modernized python3 rolediff.py ad533aa 71aeaa5
"""
from __future__ import annotations

import collections
import json
import os
import subprocess
import sys

ROOT = os.environ.get("ROOT", "/projects/modernized")


def load(ref: str) -> dict:
    return json.loads(
        subprocess.check_output(["git", "show", f"{ref}:migration/model.json"], cwd=ROOT)
    )


def roles(m: dict) -> dict:
    out = {}
    for u in m.get("units") or []:
        d = u.get("decision") if isinstance(u.get("decision"), dict) else None
        if d and d.get("role"):
            out[u.get("legacy_fqn") or u.get("key")] = d
    return out


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <tipA> <tipB>", file=sys.stderr)
        return 2
    a, b = sys.argv[1], sys.argv[2]
    ra, rb = roles(load(a)), roles(load(b))
    both = set(ra) & set(rb)
    agree = [k for k in both if ra[k]["role"] == rb[k]["role"]]
    dis = [k for k in both if ra[k]["role"] != rb[k]["role"]]
    print(
        "a=%d b=%d overlap=%d agree=%d disagree=%d %.1f%%"
        % (
            len(ra),
            len(rb),
            len(both),
            len(agree),
            len(dis),
            100.0 * len(agree) / max(1, len(both)),
        )
    )
    print(collections.Counter((ra[k]["role"], rb[k]["role"]) for k in dis))
    for k in sorted(dis):
        print(
            "%-34s %-8s -> %-8s | %s"
            % (
                k.rsplit(".", 1)[-1],
                ra[k]["role"],
                rb[k]["role"],
                str(rb[k].get("rationale", ""))[:80],
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
