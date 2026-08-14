#!/usr/bin/env python3
"""AD-H §16.6 / AR-2.1 — refuse non-runnable default DB profiles.

Reads `<root>/pom.xml`, `<root>/src/main/resources/application*.properties`
and Flyway migrations under `<root>/src/main/resources/`. Idle when the
specimen shows no DB intent at all.

Usage:
  python3 check-runnable-db-config.py .
  python3 check-runnable-db-config.py /projects/modernized
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EXIT_CODES = """Exit codes:
  0  pass — runnable default DB profile, or gate idle (no DB intent in
     pom / properties / migrations)
  1  BLOCK — missing quarkus-jdbc-*/quarkus-flyway, db-kind vs JDBC URL
     mismatch, destination hsqldb (tip-bank B7 / Quarkus 3.27+ dropped
     extension), missing quarkus.flyway.migrate-at-start=true, or no Flyway
     V*__*.sql migrations
  2  usage / harness defect (bad or unknown argument)
"""


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="product root containing pom.xml and src/main/resources (default: .)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    pom = read(root / "pom.xml")
    props_files = list((root / "src/main/resources").glob("application*.properties"))
    blob = "\n".join(read(p) for p in sorted(props_files))
    mig = list((root / "src/main/resources").rglob("V*__*.sql"))
    init_sql = list((root / "src/main/resources").rglob("initDB.sql"))

    # Properties / migrations / init SQL are active DB intent.
    # POM-only jdbc/flyway deps (foundation handoff) stay idle — later stories
    # land datasource props + Flyway V* scripts without false-failing S-001.
    active_db_intent = bool(
        re.search(r"(?m)^quarkus\.datasource\.", blob)
        or mig
        or init_sql
    )
    pom_db_deps = "quarkus-jdbc-" in pom or "quarkus-flyway" in pom
    if not active_db_intent and not pom_db_deps:
        print("OK: AR-2.1 idle (no DB intent in pom/properties/migrations)")
        return 0
    if not active_db_intent and pom_db_deps:
        print(
            "OK: AR-2.1 idle (POM declares jdbc/flyway deps but no datasource "
            "properties or migrations yet — foundation handoff)"
        )
        return 0

    bad = 0
    for dep in ("quarkus-jdbc-", "quarkus-flyway"):
        if dep not in pom:
            print(f"FAIL: AR-2.1 pom missing {dep}*", file=sys.stderr)
            bad = 1

    # Tip-bank B7 / Operator E-20260813T111808Z — refuse HSQLDB as destination.
    # Quarkus 3.27+ dropped the HSQLDB JDBC extension; prose in persistence.md
    # is not enough — gate must fail closed or every fresh seat re-imports it.
    if "quarkus-jdbc-hsqldb" in pom:
        print(
            "FAIL: AR-2.1 / B7 pom declares quarkus-jdbc-hsqldb — "
            "extension dropped on Quarkus 3.27+; use h2/postgresql/mysql",
            file=sys.stderr,
        )
        bad = 1
    kinds = re.findall(r"(?m)^quarkus\.datasource\.db-kind\s*=\s*(\S+)", blob)
    urls = re.findall(r"(?m)^quarkus\.datasource\.jdbc\.url\s*=\s*(\S+)", blob)
    for kind in kinds:
        if kind.lower() == "hsqldb":
            print(
                "FAIL: AR-2.1 / B7 db-kind=hsqldb forbidden on Quarkus 3.27+ "
                "(map legacy HSQLDB → h2/postgresql/mysql)",
                file=sys.stderr,
            )
            bad = 1
    for url in urls:
        if "jdbc:hsqldb:" in url.lower():
            print(
                f"FAIL: AR-2.1 / B7 jdbc:hsqldb URL forbidden ({url}) — "
                "use jdbc:h2: / postgresql / mysql",
                file=sys.stderr,
            )
            bad = 1
    for kind in kinds:
        for url in urls:
            if kind == "h2" and "hsqldb" in url:
                print(
                    f"FAIL: AR-2.1 db-kind=h2 with hsqldb URL ({url})",
                    file=sys.stderr,
                )
                bad = 1
            if kind == "hsqldb" and url.startswith("jdbc:h2:"):
                print(
                    f"FAIL: AR-2.1 db-kind=hsqldb with h2 URL ({url})",
                    file=sys.stderr,
                )
                bad = 1

    if not re.search(r"(?m)^quarkus\.flyway\.migrate-at-start\s*=\s*true\s*$", blob):
        print("FAIL: AR-2.1 quarkus.flyway.migrate-at-start=true required", file=sys.stderr)
        bad = 1

    if not mig:
        if init_sql:
            print(
                "FAIL: AR-2.1 initDB.sql without Flyway V*__*.sql — not runnable path",
                file=sys.stderr,
            )
        else:
            print("FAIL: AR-2.1 no Flyway V*__*.sql migrations found", file=sys.stderr)
        bad = 1

    if bad:
        print("AR-2.1 runnable-db config FAILED", file=sys.stderr)
        return 1
    print(f"OK: AR-2.1 runnable-db config ({len(mig)} migration file(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
