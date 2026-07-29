#!/usr/bin/env python3
"""Count catalog products in an acceptance-check JSON body (V6 R4).

Reads stdin. Prints a non-negative integer:
  - len(array) if the body is a JSON array
  - len(obj["products"]) if body is an object with a products array
  - 0 otherwise (including bare objects like {status, cartCount} — run-4 false green)

Exit 0 always when JSON parses; exit 1 on invalid JSON / empty stdin.
"""
from __future__ import annotations

import json
import sys


def product_count(data: object) -> int:
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        products = data.get("products")
        if isinstance(products, list):
            return len(products)
    return 0


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
