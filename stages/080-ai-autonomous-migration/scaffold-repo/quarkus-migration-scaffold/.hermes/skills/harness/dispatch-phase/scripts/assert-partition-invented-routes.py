#!/usr/bin/env python3
"""Architect 067420Z — M2 reverse-diff sibling.

R-OF.1 (066500Z): official speckit.analyze never loads the inventory
(Research typed-negative). Fail-closed when union(stories[].endpoints)
has a route absent from the inventory named on the mint receipt. No new
extraction; does not grow handover-mint.py (freeze 1088). Compiled-tree
drift is assert-compiled-route-fidelity.py (KEEP 5724ea24).

Usage:
  python3 assert-partition-invented-routes.py <dest-or-scratch-root>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH")


def _load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"FAIL: {path} is not a JSON object")
    return data


def inventory_contract(inv: dict) -> set[str]:
    keys: set[str] = set()
    for ep in inv.get("entry_points") or []:
        if not isinstance(ep, dict) or ep.get("kind") != "http":
            continue
        route = str(ep.get("http_path") or "").strip()
        method = str(ep.get("http_method") or "").upper().strip()
        if not route:
            continue
        keys.add(route)
        if method:
            keys.add(f"{method} {route}")
    return keys


def invented_routes(part: dict, contract: set[str]) -> list[str]:
    found: list[str] = []
    for story in part.get("stories") or []:
        if not isinstance(story, dict):
            continue
        sid = str(story.get("story_id") or "?")
        for ep in story.get("endpoints") or []:
            if not isinstance(ep, str):
                continue
            raw = ep.strip()
            if not raw:
                continue
            if raw in contract:
                continue
            path = raw
            for method in METHODS:
                pref = method + " "
                if raw.upper().startswith(pref):
                    path = raw[len(pref) :].strip()
                    break
            if path in contract:
                continue
            found.append(f"{sid}:{raw}")
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    part_path = root / "evidence" / "briefs" / "partition.json"
    if not part_path.is_file():
        print(f"FAIL: missing {part_path}", file=sys.stderr)
        return 1
    part = _load(part_path)
    inv_rel = str(part.get("inventory") or "evidence/entry-point-inventory.json")
    inv_path = root / inv_rel
    if not inv_path.is_file():
        print(f"FAIL: missing inventory {inv_path}", file=sys.stderr)
        return 1
    contract = inventory_contract(_load(inv_path))
    if not contract:
        print("FAIL: inventory has no HTTP routes", file=sys.stderr)
        return 1
    invented = invented_routes(part, contract)
    if invented:
        print(
            "FAIL: invented plan routes vs inventory (067420Z reverse-diff): "
            + " ".join(invented),
            file=sys.stderr,
        )
        return 1
    print("OK: partition endpoints ⊆ inventory HTTP routes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
