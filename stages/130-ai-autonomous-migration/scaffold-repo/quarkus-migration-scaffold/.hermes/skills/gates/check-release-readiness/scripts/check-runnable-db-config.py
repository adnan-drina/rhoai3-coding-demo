#!/usr/bin/env python3
"""AD-H §16.6 / AR-2.1 — refuse non-runnable default DB profiles.

Reads dest pom.xml, application*.properties, and dest SQL under
src/main/resources/. Idle when the dest shows no DB intent.

Requires one working schema mechanism, not a named one:
  Flyway complete (quarkus-flyway + migrate-at-start=true + V*__*.sql)
  when dest chose Flyway; otherwise schema generation + import/init SQL.
Do not inherit leftover Flyway from a specimen that never used it
(Review 213600Z / Lead LD-1).

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
  1  BLOCK — missing quarkus-jdbc-*, db-kind vs JDBC URL mismatch,
     destination hsqldb (tip-bank B7 / Quarkus 3.27+ dropped extension),
     or no working schema mechanism (Flyway complete if dest chose it,
     else schema generation + import/init SQL)
  2  usage / harness defect (bad or unknown argument)
"""

SCHEMA_GEN_RE = re.compile(
    r"(?m)^quarkus\.hibernate-orm\.database\.generation\s*=\s*(\S+)"
)
INITIAL_SQL_RE = re.compile(r"(?m)^quarkus\.datasource\.jdbc\.initial-sql\s*=")
LOAD_SCRIPT_RE = re.compile(
    r"(?m)^quarkus\.hibernate-orm\.sql-load-script\s*="
)
DATASOURCE_RE = re.compile(r"(?m)^quarkus\.datasource\.")
CREATING_GEN = frozenset(
    {
        "drop-and-create",
        "create",
        "update",
        "drop",
        "create-drop",
    }
)
REQUIRED = (
    "Flyway complete (quarkus-flyway + migrate-at-start=true + V*__*.sql) "
    "if dest chose Flyway; otherwise schema generation + import/init SQL"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def iter_init_sql(root: Path) -> list[Path]:
    res = root / "src" / "main" / "resources"
    if not res.is_dir():
        return []
    out: list[Path] = []
    for p in res.rglob("*"):
        if not p.is_file():
            continue
        name = p.name
        if (
            name == "import.sql"
            or name.endswith("initDB.sql")
            or name.endswith("populateDB.sql")
        ):
            out.append(p)
    return out


def schema_generation(blob: str) -> str | None:
    m = SCHEMA_GEN_RE.search(blob or "")
    if not m:
        return None
    return m.group(1).strip().strip("\"'")


def flyway_chosen(pom: str, mig: list[Path]) -> bool:
    return "quarkus-flyway" in pom or bool(mig)


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
    init_sql = iter_init_sql(root)

    activators: list[str] = []
    for p in sorted(props_files):
        if DATASOURCE_RE.search(read(p)):
            activators.append(f"{_rel(root, p)} quarkus.datasource.*")
    for p in mig:
        activators.append(_rel(root, p))
    for p in init_sql:
        activators.append(_rel(root, p))
    if INITIAL_SQL_RE.search(blob):
        activators.append("quarkus.datasource.jdbc.initial-sql")
    if LOAD_SCRIPT_RE.search(blob):
        activators.append("quarkus.hibernate-orm.sql-load-script")
    surface = "; ".join(activators) or "(none)"

    def refuse(detail: str) -> None:
        print(
            f"FAIL: AR-2.1 {detail} (Surface={surface}; idle→active). "
            f"Required: {REQUIRED}.",
            file=sys.stderr,
        )

    # Properties / SQL are active DB intent. POM-only jdbc/flyway deps
    # (foundation handoff) stay idle.
    active_db_intent = bool(activators)
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
    if "quarkus-jdbc-" not in pom:
        refuse("pom missing quarkus-jdbc-*")
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

    gen = schema_generation(blob)
    creating = bool(gen and gen.lower() in CREATING_GEN)
    has_seed = bool(
        init_sql or INITIAL_SQL_RE.search(blob) or LOAD_SCRIPT_RE.search(blob)
    )
    chose_flyway = flyway_chosen(pom, mig)

    if chose_flyway:
        if "quarkus-flyway" not in pom:
            refuse("dest chose Flyway (V*__*.sql) but pom missing quarkus-flyway")
            bad = 1
        if not re.search(
            r"(?m)^quarkus\.flyway\.migrate-at-start\s*=\s*true\s*$", blob
        ):
            refuse("quarkus.flyway.migrate-at-start=true required when dest chose Flyway")
            bad = 1
        if not mig:
            refuse("no Flyway V*__*.sql migrations found")
            bad = 1
        if not bad:
            print(f"OK: AR-2.1 runnable-db config (Flyway {len(mig)} migration file(s))")
            return 0
        print("AR-2.1 runnable-db config FAILED", file=sys.stderr)
        return 1

    if creating and "quarkus-hibernate-orm" not in pom:
        refuse("schema generation set but pom missing quarkus-hibernate-orm")
        bad = 1
    if not creating and not has_seed:
        refuse("no working schema mechanism")
        bad = 1
    elif creating and not has_seed:
        refuse("schema generation without import/init SQL")
        bad = 1

    if bad:
        print("AR-2.1 runnable-db config FAILED", file=sys.stderr)
        return 1
    print("OK: AR-2.1 runnable-db config (schema generation + import/init SQL)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
