#!/usr/bin/env python3
"""R-M3.11 — JDBC extractor deps preflight before first repository/jdbc write.

Architect E-20260810T184700Z / sibling of R-M3.5–7 persistence BOM.
"""
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED = (
    "spring-jdbc",
    "spring-data-jdbc-core",
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
            "FAIL: R-M3.11 JDBC deps incomplete — missing "
            + ", ".join(missing)
            + " (Architect E-20260810T184700Z). Typed dependency_wait; "
            "do not OOS-edit pom from a JDBC story.",
            file=sys.stderr,
        )
        return 2
    print("OK: R-M3.11 JDBC deps present (" + ", ".join(REQUIRED) + ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
