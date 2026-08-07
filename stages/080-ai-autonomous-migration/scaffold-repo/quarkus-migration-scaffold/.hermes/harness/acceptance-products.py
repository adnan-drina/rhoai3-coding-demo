#!/usr/bin/env python3
"""Count acceptance-collection items in a ship JSON body (V6 R4 / G-FAKE).

Reads stdin. Prints a non-negative integer:
  - len(array) if body is a JSON array of item-shaped dicts
  - len(obj[collection]) if body is an object with that key (named collection)
  - when collection is ``_array`` (Poll 81 / B1): **only** a top-level JSON
    array counts — ``{\"vetList\":[…]}`` wrappers return 0
  - 0 otherwise (bare status objects, string bodies, empty arrays,
    items without ids — run-4 / G-FAKE false greens)

Collection key and id fields come from migration.yaml acceptance.*
(O-ACCEPTGEN); defaults remain Coolstore products/itemId.

Exit 0 when JSON parses; exit 1 on invalid JSON / empty stdin.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SELF = Path(__file__).resolve().parent
if str(_SELF) not in sys.path:
    sys.path.insert(0, str(_SELF))

from acceptance_config import BARE_ARRAY, load as load_acceptance  # noqa: E402


def _item_ids(items: list, id_fields: list[str]) -> list:
    ids = []
    for p in items:
        if not isinstance(p, dict):
            continue
        for key in id_fields:
            if p.get(key) not in (None, ""):
                ids.append(p.get(key))
                break
    return ids


def item_count(data: object, collection: str, id_fields: list[str]) -> int:
    items: list | None = None
    if collection == BARE_ARRAY:
        # Bare-array contract: reject object wrappers (vetList etc.).
        if not isinstance(data, list):
            return 0
        items = data
    elif isinstance(data, list):
        # Named collection still accepts a top-level array (cart ship shape).
        items = data
    elif isinstance(data, dict):
        raw = data.get(collection)
        if isinstance(raw, list):
            items = raw
        else:
            return 0
    else:
        return 0

    if not items:
        return 0
    if not all(isinstance(p, dict) for p in items):
        return 0
    ids = _item_ids(items, id_fields)
    if len(ids) != len(items):
        return 0
    return len(items)


def product_count(data: object, collection: str = "products",
                  id_fields: list[str] | None = None) -> int:
    return item_count(data, collection, id_fields or ["itemId", "id", "item_id"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yaml", default="migration.yaml")
    ap.add_argument("--collection", default="")
    ap.add_argument("--id-fields", default="")
    args = ap.parse_args()
    cfg = load_acceptance(args.yaml)
    collection = args.collection or cfg["collection"]
    if args.id_fields:
        id_fields = [x.strip() for x in args.id_fields.split(",") if x.strip()]
    else:
        id_fields = list(cfg.get("idFields") or ["itemId", "id", "item_id"])

    raw = sys.stdin.read()
    if not raw.strip():
        print(0)
        return 1
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(0)
        return 1
    print(item_count(data, collection, id_fields))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
