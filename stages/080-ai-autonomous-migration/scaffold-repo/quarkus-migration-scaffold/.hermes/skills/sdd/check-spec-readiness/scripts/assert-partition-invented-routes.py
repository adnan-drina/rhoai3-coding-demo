#!/usr/bin/env python3
"""Refuse HTTP paths a partition names that are not inventory rows.

Constitution VII / Architect E-20260825T202337ZA. Empty endpoints are legal
scaffolding iff the story names no HTTP path. `/q/health` is not a grounding
exception. dest REST prefix `/api` + an inventory path is dest layering.

Usage:
  python3 assert-partition-invented-routes.py /projects/modernized
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _ensure_hermes_lib() -> None:
    p = Path(__file__).resolve()
    for parent in p.parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            s = str(lib)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()

from http_join import invented_route_gaps  # noqa: E402
from specimen_agnostic import (  # noqa: E402
    load_json,
    resolve_inventory_path,
    resolve_partition_path,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--partition", default="")
    ap.add_argument("--inventory", default="")
    ap.add_argument(
        "--allow-specimen-fixture",
        action="store_true",
        help="Permit falling back to skill fixtures inventories",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()

    part_path, looked = resolve_partition_path(root, args.partition)
    partition = load_json(part_path) if part_path is not None else None
    if not isinstance(partition, dict) or not isinstance(partition.get("stories"), list):
        looked_s = "; ".join(looked) if looked else "(none)"
        print(
            "INVENTED_ROUTES: INCONCLUSIVE — missing/invalid partition.json "
            f"(looked: {looked_s})",
            file=sys.stderr,
        )
        return 1

    inv_path = resolve_inventory_path(
        root,
        args.inventory,
        allow_specimen_fixture=bool(args.allow_specimen_fixture),
    )
    inventory = load_json(inv_path) if inv_path else None
    if not isinstance(inventory, dict):
        print("INVENTED_ROUTES: INCONCLUSIVE — missing inventory", file=sys.stderr)
        return 1

    stories = [s for s in partition["stories"] if isinstance(s, dict)]
    gaps = invented_route_gaps(root, stories, inventory)
    if gaps:
        print(
            f"INVENTED_ROUTES: REFUSE stories={len(stories)} gaps={len(gaps)}",
            file=sys.stderr,
        )
        for g in gaps:
            print(f"  - {g}", file=sys.stderr)
        return 1
    print(f"INVENTED_ROUTES: PASS stories={len(stories)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
