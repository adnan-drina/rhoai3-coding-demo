#!/usr/bin/env python3
"""R-M3.5 — require persistence stack in pom.xml for JPA successors.

Architect E-20260810T172800Z / migration/contracts/pom-persistence-handoff.md
"""
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED = (
    "quarkus-hibernate-orm",
    "quarkus-hibernate-validator",
)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    pom = root / "pom.xml"
    if not pom.is_file():
        print(f"FAIL: missing {pom}", file=sys.stderr)
        return 1
    text = pom.read_text(encoding="utf-8")
    missing = [a for a in REQUIRED if a not in text]
    if missing:
        print(
            "FAIL: R-M3.5 persistence BOM incomplete — missing "
            + ", ".join(missing)
            + " (Architect E-20260810T172800Z)",
            file=sys.stderr,
        )
        return 1
    print("OK: R-M3.5 persistence BOM present (" + ", ".join(REQUIRED) + ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
