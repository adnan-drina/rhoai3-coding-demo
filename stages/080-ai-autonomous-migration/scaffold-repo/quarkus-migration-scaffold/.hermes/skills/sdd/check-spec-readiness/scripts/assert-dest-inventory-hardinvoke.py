#!/usr/bin/env python3
"""BANK-DEST-INV-HARDINVOKE-1 — R0 lint: create-m3 must stamp dest-inventory cite law.

REFUSE when create-m3-implementer.sh lacks the BANK-DEST-INV-HARDINVOKE-1
obligation (any dependency-absent / empty-destination conclusion requires citing
refs.destination_inventory). Architect E-20260812T074514Z / Operator E-074401Z.

Usage:
  assert-dest-inventory-hardinvoke.py <root>
"""
from __future__ import annotations

import sys
from pathlib import Path

NEEDLE = "BANK-DEST-INV-HARDINVOKE-1"
CREATE = (
    Path(".hermes")
    / "enforcement"
    / "dispatch-phase"
    / "scripts"
    / "create-m3-implementer.sh"
)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    path = root / CREATE
    if not path.is_file():
        print(f"FAIL: DEST_INV_HARDINVOKE missing {path}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    if NEEDLE not in text:
        print(
            f"FAIL: DEST_INV_HARDINVOKE create-m3 lacks `{NEEDLE}` obligation",
            file=sys.stderr,
        )
        return 1
    if "destination_inventory" not in text:
        print(
            "FAIL: DEST_INV_HARDINVOKE create-m3 must mention destination_inventory",
            file=sys.stderr,
        )
        return 1
    if "dependency_wait" not in text or "REQUIRES" not in text:
        # Soft: obligation should tie dependency_wait to citation
        if "dependency_wait" not in text.split(NEEDLE, 1)[-1][:500]:
            print(
                "FAIL: DEST_INV_HARDINVOKE obligation must bind dependency_wait cite",
                file=sys.stderr,
            )
            return 1
    print(f"OK: DEST_INV_HARDINVOKE {NEEDLE} stamped in create-m3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
