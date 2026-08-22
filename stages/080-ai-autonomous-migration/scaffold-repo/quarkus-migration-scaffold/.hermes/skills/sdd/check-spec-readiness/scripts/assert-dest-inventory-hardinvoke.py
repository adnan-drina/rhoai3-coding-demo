#!/usr/bin/env python3
"""BANK-DEST-INV-HARDINVOKE-1 — R0 lint (idle in v2 until K4).

v1 asserted mint-m3-hermes.md under dispatch-phase. That Procedure is out
of day-one. Idle (exit 0) until Gate P-kernel lands K4 converter docs.

Usage:
  assert-dest-inventory-hardinvoke.py <root>
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    print(
        "OK: DEST_INV_HARDINVOKE idle — mint Procedure out of day-one "
        f"(K4 HOLD) root={root}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
