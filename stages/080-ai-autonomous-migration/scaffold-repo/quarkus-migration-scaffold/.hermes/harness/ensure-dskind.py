#!/usr/bin/env python3
"""O-DSKIND: wire JDBC + profiled db-kind when Hibernate ORM lands.

Migration-general: any Spring Boot → Quarkus app that adds quarkus-hibernate-orm
(or @Entity) needs quarkus-jdbc-* + quarkus.datasource.db-kind before verify.
Without that, Quarkus raises ConfigurationException ("Datasource must be
defined") and milestone RED can false-skip sfix (O-SFIXDIMNONE).

Called from supervisor post_commit_verify before sensors (like O-DTOCOV).
Aligns with SHIPPING.md O-ENTITYDSPROD: postgresql default/prod; H2 in %dev/%test.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
POM = ROOT / "pom.xml"
PROPS = ROOT / "src" / "main" / "resources" / "application.properties"

H2_DEP = """    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-jdbc-h2</artifactId>
    </dependency>
"""
PG_DEP = """    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-jdbc-postgresql</artifactId>
    </dependency>
"""

PROFILE_BLOCK = """
# O-DSKIND / O-ENTITYDSPROD — harness ensure (hibernate on classpath)
quarkus.datasource.db-kind=postgresql
%dev.quarkus.datasource.db-kind=h2
%test.quarkus.datasource.db-kind=h2
%prod.quarkus.datasource.db-kind=postgresql
%dev.quarkus.datasource.jdbc.url=jdbc:h2:mem:migration
%dev.quarkus.datasource.username=sa
%dev.quarkus.datasource.password=
%test.quarkus.datasource.jdbc.url=jdbc:h2:mem:migration
%test.quarkus.datasource.username=sa
%test.quarkus.datasource.password=
%dev.quarkus.hibernate-orm.database.generation=drop-and-create
%test.quarkus.hibernate-orm.database.generation=drop-and-create
"""


def needs_jpa(root: Path, pom: str) -> bool:
    if re.search(r"<artifactId>\s*quarkus-hibernate-orm", pom):
        return True
    base = root / "src" / "main" / "java"
    if not base.is_dir():
        return False
    for p in base.rglob("*.java"):
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "@Entity" in t:
            return True
    return False


def ensure_pom(pom: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    out = pom
    for art, block, tag in (
        ("quarkus-jdbc-h2", H2_DEP, "jdbc-h2"),
        ("quarkus-jdbc-postgresql", PG_DEP, "jdbc-postgresql"),
    ):
        if f"<artifactId>{art}</artifactId>" in out:
            continue
        # Insert after hibernate-orm / hibernate-validator / last quarkus dep.
        m = re.search(
            r"(<artifactId>\s*quarkus-hibernate-orm(?:-panache)?\s*</artifactId>\s*</dependency>\s*)",
            out,
        )
        if not m:
            m = re.search(
                r"(<artifactId>\s*quarkus-hibernate-validator\s*</artifactId>\s*</dependency>\s*)",
                out,
            )
        if m:
            out = out[: m.end()] + block + out[m.end() :]
            notes.append(f"{tag}-added")
        else:
            notes.append(f"{tag}-no-anchor")
    return out, notes


def ensure_props(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    if re.search(r"(?m)^[ \t]*%?(dev|test|prod)\.?quarkus\.datasource\.db-kind=", text) or re.search(
        r"(?m)^[ \t]*quarkus\.datasource\.db-kind=", text
    ):
        # Profiled or default kind already present — do not rewrite operator/probe tips.
        return text, notes
    notes.append("db-kind-profiles-added")
    return text.rstrip() + "\n" + PROFILE_BLOCK.lstrip(), notes


def main() -> int:
    if not POM.is_file():
        print("skip:no-pom")
        return 0
    pom = POM.read_text(encoding="utf-8", errors="replace")
    if not needs_jpa(ROOT, pom):
        print("skip:no-jpa")
        return 0
    notes: list[str] = []
    new_pom, pn = ensure_pom(pom)
    notes.extend(pn)
    if new_pom != pom:
        POM.write_text(new_pom, encoding="utf-8")
        notes.append("pom-updated")
    if PROPS.is_file():
        props = PROPS.read_text(encoding="utf-8", errors="replace")
        new_props, pr = ensure_props(props)
        notes.extend(pr)
        if new_props != props:
            PROPS.write_text(new_props, encoding="utf-8")
            notes.append("props-updated")
    else:
        PROPS.parent.mkdir(parents=True, exist_ok=True)
        PROPS.write_text(PROFILE_BLOCK.lstrip(), encoding="utf-8")
        notes.append("props-created")
    if any(n.endswith("-updated") or n.endswith("-added") or n.endswith("-created") for n in notes):
        print("ok:dskind-updated," + ",".join(notes))
    else:
        print("ok:already," + (",".join(notes) if notes else "noop"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
