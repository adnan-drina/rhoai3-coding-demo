#!/usr/bin/env python3
"""Dest inventory hardinvoke is not a day-one gate.

v1 asserted mint-m3-hermes.md under dispatch-phase. That Procedure is out
of day-one. Fail-closed (never idle-green) until K4 lands converter docs.

Usage:
  assert-dest-inventory-hardinvoke.py <root>
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    print(
        "HARDINVOKE_RETIRED: dest inventory hardinvoke is not a day-one gate "
        f"(K4 HOLD) root={root}. Never idle-green.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
