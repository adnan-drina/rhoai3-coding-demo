#!/usr/bin/env python3
"""Count catalog products in an acceptance-check JSON body (V6 R4 / G-FAKE).

Reads stdin. Prints a non-negative integer:
  - len(obj["products"]) if body is an object with a products array of
    product-shaped dicts (each with itemId or id)
  - len(array) if the body is a JSON array of such product objects
  - 0 otherwise (bare status objects, string bodies, empty arrays,
    products without ids — run-4 / G-FAKE false greens)

Exit 0 when JSON parses; exit 1 on invalid JSON / empty stdin.
"""
from __future__ import annotations

import json
import sys


def _product_ids(products: list) -> list:
    ids = []
    for p in products:
        if not isinstance(p, dict):
            continue
        for key in ("itemId", "id", "item_id"):
            if p.get(key) not in (None, ""):
                ids.append(p.get(key))
                break
    return ids


def product_count(data: object) -> int:
    products: list | None = None
    if isinstance(data, list):
        products = data
    elif isinstance(data, dict):
        raw = data.get("products")
        if isinstance(raw, list):
            products = raw
        else:
            return 0
    else:
        return 0

    if not products:
        return 0
    if not all(isinstance(p, dict) for p in products):
        return 0
    # G-FAKE: require stable product identity fields (not nameless maps)
    ids = _product_ids(products)
    if len(ids) != len(products):
        return 0
    return len(products)


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        print(0)
        return 1
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(0)
        return 1
    print(product_count(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
