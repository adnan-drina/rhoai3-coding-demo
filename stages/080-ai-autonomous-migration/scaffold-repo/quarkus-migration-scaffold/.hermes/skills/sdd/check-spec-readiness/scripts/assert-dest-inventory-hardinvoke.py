#!/usr/bin/env python3
"""BANK-DEST-INV-HARDINVOKE-1 — R0 lint: mint Procedure + standing procedure.

REFUSE when mint-m3-hermes.md lacks the BANK-DEST-INV-HARDINVOKE-1
cite, or when the full obligation (destination_inventory + dependency_wait
REQUIRES) is absent from both the Procedure and the F6 standing contract.

Architect E-20260812T074514Z / Operator E-074401Z / F6 E-20260814T115900Z.

Usage:
  assert-dest-inventory-hardinvoke.py <root>
"""
from __future__ import annotations

import sys
from pathlib import Path

NEEDLE = "BANK-DEST-INV-HARDINVOKE-1"
CREATE = (
    Path(".hermes")
    / "skills"
    / "harness"
    / "dispatch-phase"
    / "references"
    / "mint-m3-hermes.md"
)
STANDING = (
    Path(".hermes")
    / "skills"
    / "harness"
    / "dispatch-phase"
    / "references"
    / "m3-implementer-standing.md"
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
            f"FAIL: DEST_INV_HARDINVOKE mint Procedure lacks `{NEEDLE}` obligation",
            file=sys.stderr,
        )
        return 1
    if "destination_inventory" not in text:
        print(
            "FAIL: DEST_INV_HARDINVOKE mint Procedure must mention destination_inventory",
            file=sys.stderr,
        )
        return 1

    standing_path = root / STANDING
    standing = standing_path.read_text(encoding="utf-8") if standing_path.is_file() else ""
    combined = text + "\n" + standing
    # Full cite law may live on the slim card *or* in F6 standing procedure.
    if "dependency_wait" not in combined or "REQUIRES" not in combined:
        print(
            "FAIL: DEST_INV_HARDINVOKE obligation must bind dependency_wait cite "
            "(mint-m3-hermes.md and/or m3-implementer-standing.md)",
            file=sys.stderr,
        )
        return 1
    if NEEDLE not in standing and "dependency_wait" not in text.split(NEEDLE, 1)[-1][:800]:
        # Prefer standing to carry the long form when card is slim (F6).
        print(
            "FAIL: DEST_INV_HARDINVOKE standing procedure missing "
            f"`{NEEDLE}` detail (F6)",
            file=sys.stderr,
        )
        return 1
    print(f"OK: DEST_INV_HARDINVOKE {NEEDLE} stamped in mint Procedure (+ standing)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
