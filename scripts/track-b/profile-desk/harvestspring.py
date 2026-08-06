#!/usr/bin/env python3
"""HARVEST + non-own-root Spring import desk check (WARN aid; not a RED gate).

Own root is derived from the shared FQN prefix in model.json — never hardcoded.
Usage:
  ROOT=/projects/modernized LEGACY=/projects/legacy python3 harvestspring.py
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.environ.get("ROOT", "/projects/modernized")
LEGACY = os.environ.get("LEGACY", "/projects/legacy")


def main() -> int:
    m = json.load(open(f"{ROOT}/migration/model.json", encoding="utf-8"))
    units = {
        u["legacy_fqn"]: u
        for u in m.get("units") or []
        if u.get("decision") and u.get("legacy_fqn")
    }
    fqns = list(units)
    if not fqns:
        print("no decided units")
        return 1
    parts = [f.split(".") for f in fqns]
    own = ".".join(
        p
        for i, p in enumerate(parts[0])
        if all(len(q) > i and q[i] == p for q in parts)
    )

    def imports(rel: str):
        p = os.path.join(LEGACY, rel)
        if not os.path.isfile(p):
            return None
        return re.findall(
            r"^import\s+(org\.springframework\.[\w.]+);",
            open(p, errors="replace", encoding="utf-8").read(),
            re.M,
        )

    flag, clean = [], []
    redn = 0
    for f, u in units.items():
        imp = imports(u.get("legacy_path") or "")
        if imp is None:
            continue
        ext = [i for i in imp if not i.startswith(own)]
        role = u["decision"]["role"]
        if role == "HARVEST":
            (flag if ext else clean).append((f, ext))
        elif not imp:
            redn += 1
    print("own_root=%s" % own)
    print(
        "HARVEST flagged=%d clean=%d | REDESIGN_without_spring=%d"
        % (len(flag), len(clean), redn)
    )
    for f, e in flag:
        print(
            "FLAG %-30s %s"
            % (f.rsplit(".", 1)[-1], ",".join(sorted(set(e)))[:70])
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
