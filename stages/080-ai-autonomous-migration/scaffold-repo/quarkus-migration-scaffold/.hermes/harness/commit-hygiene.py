#!/usr/bin/env python3
"""O-GITBAK / O-SIMPLEDTO / O-POMUNC / O-JDBCREGRESS — refuse dishonest commits.

Exit 1 when HEAD (or given sha) commits:
  - src/**/*.bak, *~, *.orig (O-GITBAK)
  - both dto/*.java and dto/*.bak in the same commit (O-SIMPLEDTO)
  - Java importing org.mapstruct / @Mapper while tree pom at sha lacks
    a mapstruct dependency (O-POMUNC)
  - pom.xml newly adds spring-jdbc / spring-tx / spring-orm vs parent
    while quarkus-maven-plugin is present (O-JDBCREGRESS). Pre-existing
    deps for honest Jdbc*RepositoryImpl CDI are allowed.

Usage: commit-hygiene.py [sha]
"""
from __future__ import annotations

import re
import subprocess
import sys


def _show_names(sha: str) -> list[str]:
    out = subprocess.check_output(
        ["git", "show", "--name-only", "--format=", sha], text=True
    )
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def _show_file(sha: str, path: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f"{sha}:{path}"], text=True, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        return ""


def _pom_has_mapstruct(pom: str) -> bool:
    return bool(re.search(r"<artifactId>\s*mapstruct", pom, re.I))


def main() -> int:
    sha = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    names = _show_names(sha)
    if not names:
        return 0
    problems: list[str] = []

    bak = [
        n
        for n in names
        if n.startswith("src/")
        and (n.endswith(".bak") or n.endswith("~") or n.endswith(".orig"))
    ]
    if bak:
        problems.append("O-GITBAK:" + ",".join(bak[:8]))

    dto_java = [n for n in names if "/dto/" in n and n.endswith(".java")]
    dto_bak = [n for n in names if "/dto/" in n and n.endswith(".bak")]
    if dto_java and dto_bak:
        problems.append(
            "O-SIMPLEDTO:dto.java+dto.bak:" + ",".join(sorted(dto_bak)[:4])
        )

    mapstruct_java = []
    for n in names:
        if not n.endswith(".java"):
            continue
        body = _show_file(sha, n)
        if "import org.mapstruct" in body or re.search(r"@Mapper\b", body):
            mapstruct_java.append(n)
    if mapstruct_java:
        pom_text = _show_file(sha, "pom.xml")
        if not _pom_has_mapstruct(pom_text):
            problems.append(
                "O-POMUNC:mapstruct-import-without-pom:"
                + ",".join(mapstruct_java[:4])
            )

    # O-JDBCREGRESS: after Quarkus BOM, never *newly* introduce Spring
    # JDBC/ORM modules to greenwash a JDBC harvest (Wave2 T-009 MiniMax).
    # Compare to parent — pre-existing spring-jdbc for Jdbc*Impl is OK
    # (O-JDBCREGRESSFALSE: Gate fix r1 was falsely reset when pom touched).
    if "pom.xml" in names:
        pom_text = _show_file(sha, "pom.xml")
        parent = f"{sha}^"
        parent_pom = _show_file(parent, "pom.xml")
        if "quarkus-maven-plugin" in pom_text:
            bad = []
            for art in ("spring-jdbc", "spring-tx", "spring-orm"):
                pat = rf"<artifactId>\s*{re.escape(art)}\s*<"
                in_tip = bool(re.search(pat, pom_text, re.I))
                in_parent = bool(re.search(pat, parent_pom, re.I)) if parent_pom else False
                if in_tip and not in_parent:
                    bad.append(art)
            if bad:
                problems.append("O-JDBCREGRESS:spring-readd:" + ",".join(bad))

    # O-DUPPROP: refuse tips that leave duplicate keys in application.properties
    # (S07 T-002 era: petclinic.security.enable / quarkus.security.jdbc.* twice).
    # O-PRODSCHEMA: refuse unprofiled drop-and-create (W3-131/132).
    prop_paths = [
        n
        for n in names
        if n.endswith("application.properties")
        or n.endswith("application.yaml")
        or n.endswith("application.yml")
    ]
    for pp in prop_paths:
        body = _show_file(sha, pp)
        if not body or pp.endswith((".yaml", ".yml")):
            continue
        keys: list[str] = []
        for ln in body.splitlines():
            s = ln.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            keys.append(s.split("=", 1)[0].strip())
        dup = sorted({k for k in keys if keys.count(k) > 1})
        if dup:
            problems.append("O-DUPPROP:" + pp + ":" + ",".join(dup[:8]))
        if re.search(
            r"(?m)^[ \t]*quarkus\.hibernate-orm\.database\.generation=drop-and-create\b",
            body,
        ):
            problems.append("O-PRODSCHEMA:unprofiled-drop-and-create:" + pp)

    if problems:
        print("\n".join(problems))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
