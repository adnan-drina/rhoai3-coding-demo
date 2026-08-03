#!/usr/bin/env python3
"""O-CDIPARTIAL / O-JDBCHARVESTAPI / O-SPRINGRESIDUE — refuse incomplete convert.

Migration-general (any Spring Boot → Quarkus specimen):

  O-CDIPARTIAL — Target beans stamped @ApplicationScoped (or sibling CDI
  scopes) that still carry @Autowired / lack jakarta @Inject are NOT done.
  Refuse Already-satisfied / tip-accept / sensor GREEN on that smell.

  O-JDBCHARVESTAPI — under a Quarkus pom without spring-jdbc, harvested
  Targets must not keep org.springframework.jdbc|dao|orm imports or
  NamedParameterJdbcTemplate / SimpleJdbcInsert. Rewrite to Agroal /
  java.sql (or EntityManager) — never re-add spring-jdbc (O-JDBCREGRESS).

  O-SPRINGRESIDUE — after Class=infer / Port=reimplement convert, cheap
  pre-sensor: org.springframework under src/main/java must be 0 (comments
  stripped). Also flag invented *PersistenceException under spring.*
  packages (W4-085a substring invent, e.g. EmptyResultPersistenceException).

Usage:
  cdi-partial-check.py              # scan working tree src/main/java
  cdi-partial-check.py --sha HEAD   # scan files in that commit (+ tree pom)

Exit 0 = clean; exit 1 = violation(s) on stdout (one per line).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(".").resolve()
CDI_SCOPE = re.compile(
    r"@(?:ApplicationScoped|RequestScoped|SessionScoped|Singleton)\b"
)
AUTOWIRED = re.compile(r"@Autowired\b")
INJECT = re.compile(r"@Inject\b|jakarta\.inject\.Inject")
SPRING_JDBC_SMELL = re.compile(
    r"org\.springframework\.jdbc\b|"
    r"org\.springframework\.dao\b|"
    r"org\.springframework\.orm\b|"
    r"\bNamedParameterJdbcTemplate\b|"
    r"\bSimpleJdbcInsert\b|"
    r"\bJdbcTemplate\b"
)
# Any remaining Spring FQCN / import after convert (code only; comments stripped).
SPRING_ANY = re.compile(r"\borg\.springframework\b")
# Invented types: PersistenceException never lives under org.springframework.*.
INVENTED_SPRING_PE = re.compile(
    r"\borg\.springframework\.[A-Za-z0-9_.]+\.[A-Za-z0-9_]*PersistenceException\b"
)


def _strip_java_comments(text: str) -> str:
    """Remove // and /* */ comments so residual scans ignore prose."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _pom_text(sha: str | None) -> str:
    pom = ROOT / "pom.xml"
    if sha:
        try:
            return subprocess.check_output(
                ["git", "show", f"{sha}:pom.xml"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            pass
    if pom.is_file():
        return pom.read_text(encoding="utf-8", errors="replace")
    return ""


def _quarkus_no_spring_jdbc(pom: str) -> bool:
    if "quarkus-maven-plugin" not in pom:
        return False
    if re.search(r"<artifactId>\s*spring-jdbc\s*<", pom, re.I):
        return False
    if re.search(r"spring-boot", pom, re.I):
        return False
    return True


def _quarkus_native_no_spring(pom: str) -> bool:
    """True when destination is Quarkus without spring-boot / spring-data bridge."""
    if "quarkus-maven-plugin" not in pom:
        return False
    if re.search(r"spring-boot", pom, re.I):
        return False
    # quarkus-spring-data-jpa / spring-data-* keep org.springframework.data on purpose
    if re.search(r"<artifactId>\s*quarkus-spring-data", pom, re.I):
        return False
    if re.search(r"<artifactId>\s*spring-data-", pom, re.I):
        return False
    return True


def _iter_java_paths(sha: str | None) -> list[Path]:
    if sha:
        try:
            out = subprocess.check_output(
                ["git", "show", "--name-only", "--format=", sha], text=True
            )
        except subprocess.CalledProcessError:
            return []
        names = [
            ln.strip()
            for ln in out.splitlines()
            if ln.strip().endswith(".java") and ln.strip().startswith("src/")
        ]
        return [ROOT / n for n in names]
    root = ROOT / "src/main/java"
    if not root.is_dir():
        return []
    return list(root.rglob("*.java"))


def _read(path: Path, sha: str | None) -> str:
    if sha:
        rel = str(path.relative_to(ROOT)) if path.is_absolute() else str(path)
        try:
            return subprocess.check_output(
                ["git", "show", f"{sha}:{rel}"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def check(sha: str | None = None) -> list[str]:
    problems: list[str] = []
    pom = _pom_text(sha)
    no_spring_jdbc = _quarkus_no_spring_jdbc(pom)
    native_no_spring = _quarkus_native_no_spring(pom)
    for path in _iter_java_paths(sha):
        text = _read(path, sha)
        if not text:
            continue
        rel = str(path.relative_to(ROOT)) if path.is_absolute() else str(path)
        under_main = "/src/main/" in f"/{rel}" or rel.startswith("src/main/")
        code = _strip_java_comments(text)
        if CDI_SCOPE.search(text) and AUTOWIRED.search(text):
            problems.append(f"O-CDIPARTIAL:autowired-on-cdi:{rel}")
        elif (
            CDI_SCOPE.search(text)
            and re.search(
                r"org\.springframework\.beans\.factory\.annotation\.Autowired",
                text,
            )
            and not INJECT.search(text)
        ):
            problems.append(f"O-CDIPARTIAL:missing-inject:{rel}")
        if no_spring_jdbc and under_main and SPRING_JDBC_SMELL.search(code):
            problems.append(f"O-JDBCHARVESTAPI:spring-jdbc-api:{rel}")
        if under_main and INVENTED_SPRING_PE.search(code):
            problems.append(f"O-SPRINGRESIDUE:invented-spring-PersistenceException:{rel}")
        elif native_no_spring and under_main and SPRING_ANY.search(code):
            # Broader than O-JDBCHARVESTAPI — any org.springframework left after convert
            problems.append(f"O-SPRINGRESIDUE:org.springframework:{rel}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sha", default=None)
    args = ap.parse_args()
    problems = check(args.sha)
    if problems:
        print("\n".join(problems[:24]))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
