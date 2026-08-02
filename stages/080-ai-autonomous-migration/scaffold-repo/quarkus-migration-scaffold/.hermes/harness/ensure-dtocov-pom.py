#!/usr/bin/env python3
"""O-DTOCOV: ensure Sonar exclusions for OpenAPI-harvested **/dto/** trees.

Migration-general: any Spring Boot → Quarkus app that harvests generated-style
DTO beans under a `dto` package segment. Matches scaffold SHIPPING.md — do not
invent BaseDto hierarchies or ceremonial getter tests to green-wash Sonar.

Called from supervisor post_commit_verify before milestone/sonar when dto Java
exists under src/main/java.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
POM = ROOT / "pom.xml"
DTO_GLOB = "**/dto/**"
PROPS = (
    ("sonar.exclusions", DTO_GLOB),
    ("sonar.coverage.exclusions", DTO_GLOB),
    ("sonar.cpd.exclusions", DTO_GLOB),
)


def has_dto_java(root: Path) -> bool:
    base = root / "src" / "main" / "java"
    if not base.is_dir():
        return False
    for p in base.rglob("*.java"):
        parts = p.parts
        if "dto" in parts:
            return True
    return False


def _has_prop(pom_text: str, key: str, value: str) -> bool:
    pat = rf"<{re.escape(key)}>\s*{re.escape(value)}\s*</{re.escape(key)}>"
    return bool(re.search(pat, pom_text))


def ensure_pom(pom_text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    missing = [(k, v) for k, v in PROPS if not _has_prop(pom_text, k, v)]
    if not missing:
        return pom_text, notes

    insert_lines = []
    for key, val in missing:
        insert_lines.append(f"    <{key}>{val}</{key}>")
        notes.append(f"{key}-added")

    block = "\n".join(insert_lines) + "\n"
    # Prefer after sonar.coverage.jacoco.xmlReportPaths (scaffold convention).
    m = re.search(
        r"(<sonar\.coverage\.jacoco\.xmlReportPaths>[^<]+</sonar\.coverage\.jacoco\.xmlReportPaths>\s*)",
        pom_text,
    )
    if m:
        idx = m.end()
        return pom_text[:idx] + block + pom_text[idx:], notes

    m2 = re.search(r"(?s)(<properties>\s*)", pom_text)
    if not m2:
        notes.append("no-properties")
        return pom_text, notes
    idx = m2.end()
    return pom_text[:idx] + block + pom_text[idx:], notes


def main() -> int:
    if not POM.is_file():
        print("skip:no-pom")
        return 0
    if not has_dto_java(ROOT):
        print("skip:no-dto-java")
        return 0
    pom = POM.read_text(encoding="utf-8", errors="replace")
    new_pom, notes = ensure_pom(pom)
    if new_pom != pom:
        POM.write_text(new_pom, encoding="utf-8")
        print("ok:pom-updated," + ",".join(notes))
    else:
        print("ok:already," + ",".join(notes) if notes else "ok:already")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
