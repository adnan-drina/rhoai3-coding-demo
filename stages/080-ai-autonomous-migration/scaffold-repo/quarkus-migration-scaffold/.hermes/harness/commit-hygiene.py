#!/usr/bin/env python3
"""O-GITBAK / O-SIMPLEDTO / O-POMUNC / O-JDBCREGRESS / O-CDIPARTIAL /
O-TREEFIXSTUB / O-HERMSCOOP / O-DEBTTREE — refuse dishonest commits.

Exit 1 when HEAD (or given sha) commits:
  - debt: subject that also mutates src/ or pom.xml (O-DEBTTREE / ADR-48)
  - src/**/*.bak, *~, *.orig (O-GITBAK)
  - both dto/*.java and dto/*.bak in the same commit (O-SIMPLEDTO)
  - Java importing org.mapstruct / @Mapper while tree pom at sha lacks
    a mapstruct dependency (O-POMUNC)
    - pom.xml newly adds spring-jdbc / spring-tx / spring-orm vs parent
    while quarkus-maven-plugin is present (O-JDBCREGRESS). Pre-existing
    deps for honest Jdbc*RepositoryImpl CDI are allowed.
  - @ApplicationScoped (+siblings) still carrying @Autowired, or
    spring.jdbc|dao|orm / NamedParameterJdbcTemplate leftovers under a
    Quarkus pom without spring-jdbc (O-CDIPARTIAL / O-JDBCHARVESTAPI).
  - comment-only / REMOVED stubs under src/main, or deleted owned Target
    .java paths (O-TREEFIXSTUB — tree-fix must not stub-nuke).
  - any .hermes/ path (O-HERMSCOOP / O-M2-FREEZE-JUNK — golden harness
    must stay untracked; never scoop into app tips).
  - any migration/run-archives/** or run-archives/** (O-ARCHIVESCOOP /
    O-K12ARCH — forensic dumps false-trip K12 when scooped into T-NNN).
  - any __pycache__/ or *.pyc tip path (O-M3COMMITHYGIENE companion —
    bytecode must never ship in app tips).

Usage: commit-hygiene.py [sha]
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def _show_names(sha: str) -> list[str]:
    out = subprocess.check_output(
        ["git", "show", "--name-only", "--format=", sha], text=True
    )
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def _show_name_status(sha: str) -> list[tuple[str, str]]:
    """Return (status, path) pairs — status is A/M/D/R… from name-status."""
    out = subprocess.check_output(
        ["git", "show", "--name-status", "--format=", sha], text=True
    )
    rows: list[tuple[str, str]] = []
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        parts = ln.split("\t")
        if len(parts) < 2:
            continue
        # renames: R100\told\tnew — treat new path as the tip path
        status, path = parts[0][0], parts[-1]
        rows.append((status, path))
    return rows


def _show_file(sha: str, path: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f"{sha}:{path}"], text=True, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        return ""


def _pom_has_mapstruct(pom: str) -> bool:
    return bool(re.search(r"<artifactId>\s*mapstruct", pom, re.I))


def _subject(sha: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "log", "-1", "--format=%s", sha],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        return ""


def main() -> int:
    sha = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    names = _show_names(sha)
    if not names:
        return 0
    problems: list[str] = []

    # O-DEBTTREE / ADR-48: incident journal commits must not mutate app tree.
    subj = _subject(sha)
    if re.match(r"^debt:\s*", subj, re.I):
        app_touch = [
            n
            for n in names
            if n == "pom.xml"
            or n.startswith("src/")
            or "/src/" in n
        ]
        if app_touch:
            problems.append(
                "O-DEBTTREE:" + ",".join(app_touch[:8])
                + (f"…+{len(app_touch) - 8}" if len(app_touch) > 8 else "")
            )

    # O-HERMSCOOP / O-M2-FREEZE-JUNK: refuse tips that ADD/MODIFY golden harness.
    # Deletions (cleanup commits like 89bafd3) are allowed — they untrack scoop.
    hermes = [
        n
        for st, n in _show_name_status(sha)
        if (n == ".hermes" or n.startswith(".hermes/")) and st in ("A", "M", "R", "C")
    ]
    if hermes:
        problems.append(
            "O-HERMSCOOP:" + ",".join(hermes[:8])
            + (f"…+{len(hermes) - 8}" if len(hermes) > 8 else "")
        )

    # O-ARCHIVESCOOP / O-K12ARCH: refuse forensic archive scoops in app tips.
    archives = [
        n
        for st, n in _show_name_status(sha)
        if st in ("A", "M", "R", "C")
        and (
            n == "migration/run-archives"
            or n.startswith("migration/run-archives/")
            or n == "run-archives"
            or n.startswith("run-archives/")
        )
    ]
    if archives:
        problems.append(
            "O-ARCHIVESCOOP:" + ",".join(archives[:8])
            + (f"…+{len(archives) - 8}" if len(archives) > 8 else "")
        )

    # O-M3COMMITHYGIENE: refuse bytecode / cache artifacts in any tip.
    pyc = [
        n
        for n in names
        if n.endswith(".pyc")
        or "/__pycache__/" in n
        or n.endswith("/__pycache__")
        or n.startswith("__pycache__/")
    ]
    if pyc:
        problems.append(
            "O-M3COMMITHYGIENE:pyc:" + ",".join(pyc[:8])
            + (f"…+{len(pyc) - 8}" if len(pyc) > 8 else "")
        )

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
    # O-POMDISCARD: refuse tips that newly add panache/spring-data deps when
    # the tip (and tree) has no matching src Panache/Spring Data usage.
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
            # Orphan panache / spring-data dep without src usage
            orphan_arts = []
            for art, src_pat in (
                ("quarkus-hibernate-orm-panache", r"PanacheRepository|io\.quarkus\.hibernate\.orm\.panache"),
                ("spring-data", r"org\.springframework\.data"),
            ):
                pat = rf"<artifactId>\s*{re.escape(art)}[^<]*<"
                in_tip = bool(re.search(pat, pom_text, re.I))
                in_parent = bool(re.search(pat, parent_pom, re.I)) if parent_pom else False
                if in_tip and not in_parent:
                    # Any tip java file or tree src cite?
                    tip_java = [n for n in names if n.endswith(".java") and n.startswith("src/")]
                    has_src = False
                    for jn in tip_java:
                        body = _show_file(sha, jn)
                        if body and re.search(src_pat, body):
                            has_src = True
                            break
                    if not has_src:
                        # Also scan working tree (tip may be pom-only)
                        src_root = Path("src/main/java")
                        if src_root.is_dir():
                            for p in src_root.rglob("*.java"):
                                try:
                                    if re.search(src_pat, p.read_text(encoding="utf-8", errors="replace")):
                                        has_src = True
                                        break
                                except OSError:
                                    continue
                    if not has_src:
                        orphan_arts.append(art)
            if orphan_arts:
                problems.append("O-POMDISCARD:orphan-pom-deps:" + ",".join(orphan_arts))

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

    # O-CDIPARTIAL / O-JDBCHARVESTAPI — tip-accept refuse (O-HYGIENEWORKER).
    checker = Path(__file__).resolve().parent / "cdi-partial-check.py"
    if checker.is_file() and any(n.endswith(".java") for n in names):
        try:
            out = subprocess.check_output(
                [sys.executable, str(checker), "--sha", sha],
                text=True,
                stderr=subprocess.STDOUT,
            )
            # exit 0 → clean; check_output only returns on 0
            _ = out
        except subprocess.CalledProcessError as exc:
            for ln in (exc.output or "").splitlines():
                ln = ln.strip()
                if ln:
                    problems.append(ln)

    # O-TREEFIXSTUB — tip-accept refuse comment-only / REMOVED stubs and
    # deleted owned Targets (tree-fix false-green path).
    stub_checker = Path(__file__).resolve().parent / "tree-fix-stub-check.py"
    if stub_checker.is_file() and any(
        n.endswith(".java") and n.startswith("src/") for n in names
    ):
        try:
            subprocess.check_output(
                [sys.executable, str(stub_checker), "--sha", sha],
                text=True,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as exc:
            for ln in (exc.output or "").splitlines():
                ln = ln.strip()
                if ln:
                    problems.append(ln)

    # O-SDJPAHARVEST — tip-accept refuse hollow Panache / dropped domain extends.
    sdjpa_checker = Path(__file__).resolve().parent / "sdjpa-harvest-check.py"
    if sdjpa_checker.is_file() and any(
        n.endswith(".java") and n.startswith("src/") for n in names
    ):
        try:
            subprocess.check_output(
                [sys.executable, str(sdjpa_checker), "--sha", sha],
                text=True,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as exc:
            for ln in (exc.output or "").splitlines():
                ln = ln.strip()
                if ln:
                    problems.append(ln)

    if problems:
        print("\n".join(problems))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
