#!/usr/bin/env python3
"""O-MAPPRESEED plugin: MapStruct deps + jakarta-cdi when @Mapper exists.

Invoked by ``ensure-harvest-ready.py`` (O-HARVESTREADY). Migration-general.
Do not add a parallel supervisor wire — register on the orchestrator.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
POM = ROOT / "pom.xml"
MAPPER_DIR = ROOT / "src/main/java"
VERSION = "1.6.3"


def has_mapper_java(root: Path) -> bool:
    for p in root.rglob("*.java"):
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "import org.mapstruct" in t or re.search(r"@Mapper\b", t):
            return True
    return False


def ensure_pom(pom_text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    if re.search(r"<artifactId>\s*mapstruct\s*<", pom_text, re.I):
        return pom_text, notes

    dep_block = f"""    <dependency>
      <groupId>org.mapstruct</groupId>
      <artifactId>mapstruct</artifactId>
      <version>{VERSION}</version>
    </dependency>
    <dependency>
      <groupId>org.mapstruct</groupId>
      <artifactId>mapstruct-processor</artifactId>
      <version>{VERSION}</version>
    </dependency>
"""
    # Insert before closing </dependencies> of project deps (last occurrence
    # before <build> is safer than first dependencyManagement close).
    m = re.search(r"(?s)(<build>\s*<plugins>)", pom_text)
    if not m:
        notes.append("no-build-plugins")
        return pom_text, notes
    # find last </dependencies> before <build>
    pre = pom_text[: m.start()]
    post = pom_text[m.start() :]
    idx = pre.rfind("</dependencies>")
    if idx < 0:
        notes.append("no-dependencies-close")
        return pom_text, notes
    pom_text = pre[:idx] + dep_block + pre[idx:] + post
    notes.append("deps-added")

    # annotationProcessorPaths on maven-compiler-plugin
    if "mapstruct-processor" not in pom_text[pom_text.find("maven-compiler-plugin") :]:
        ap = f"""          <annotationProcessorPaths>
            <path>
              <groupId>org.mapstruct</groupId>
              <artifactId>mapstruct-processor</artifactId>
              <version>{VERSION}</version>
            </path>
          </annotationProcessorPaths>
"""
        pom_text2, n = re.subn(
            r"(<plugin>\s*<artifactId>maven-compiler-plugin</artifactId>.*?<configuration>\s*)",
            r"\1" + ap,
            pom_text,
            count=1,
            flags=re.S,
        )
        if n:
            pom_text = pom_text2
            notes.append("annotationProcessorPaths-added")
        else:
            notes.append("compiler-plugin-patch-miss")
    return pom_text, notes


def patch_mappers(root: Path) -> int:
    n = 0
    for p in root.rglob("*.java"):
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not re.search(r"@Mapper\b", t):
            continue
        if 'componentModel' in t and 'jakarta-cdi' in t:
            continue
        # @Mapper → @Mapper(componentModel = "jakarta-cdi")
        # @Mapper(uses = X) → @Mapper(componentModel = "jakarta-cdi", uses = X)
        def repl(m: re.Match[str]) -> str:
            inner = m.group(1) or ""
            inner = inner.strip()
            if "componentModel" in inner:
                return m.group(0)
            if inner:
                return f'@Mapper(componentModel = "jakarta-cdi", {inner})'
            return '@Mapper(componentModel = "jakarta-cdi")'

        nt = re.sub(r"@Mapper\s*(?:\(([^)]*)\))?", repl, t, count=1)
        if nt != t:
            p.write_text(nt, encoding="utf-8")
            n += 1
    return n


def main() -> int:
    if not POM.is_file():
        print("skip:no-pom")
        return 0
    if not has_mapper_java(ROOT / "src"):
        print("skip:no-mapper-java")
        return 0
    pom = POM.read_text(encoding="utf-8", errors="replace")
    new_pom, notes = ensure_pom(pom)
    if new_pom != pom:
        POM.write_text(new_pom, encoding="utf-8")
    patched = patch_mappers(ROOT / "src")
    print("ok:" + ",".join(notes + ([f"mappers-cdi={patched}"] if patched else [])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
