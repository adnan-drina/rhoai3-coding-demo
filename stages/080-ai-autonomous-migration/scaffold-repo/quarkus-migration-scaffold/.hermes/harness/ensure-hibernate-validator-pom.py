#!/usr/bin/env python3
"""O-VALDEPADD plugin: quarkus-hibernate-validator for jakarta.validation.

Invoked by ``ensure-harvest-ready.py`` (O-HARVESTREADY). Do not wire a second
supervisor call — register new capabilities on the orchestrator.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
POM = ROOT / "pom.xml"
HARNESS = Path(__file__).resolve().parent

_DEP = """    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-hibernate-validator</artifactId>
    </dependency>
"""


def has_jakarta_validation(root: Path) -> bool:
    sys.path.insert(0, str(HARNESS))
    try:
        from harvest_ready import SIGNAL_VALIDATION, collect_signals  # type: ignore

        return SIGNAL_VALIDATION in collect_signals(root)
    except ImportError:
        src = root / "src"
        if not src.is_dir():
            return False
        for p in src.rglob("*.java"):
            try:
                t = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if re.search(r"\bjakarta\.validation\b", t):
                return True
        return False


def pom_has_validator(pom_text: str) -> bool:
    return bool(
        re.search(
            r"(?i)hibernate-validator|quarkus-hibernate-validator|"
            r"<artifactId>\s*jakarta\.validation",
            pom_text,
        )
    )


def ensure_pom(pom_text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    if pom_has_validator(pom_text):
        notes.append("already-present")
        return pom_text, notes

    m = re.search(r"(?s)(<build>\s*<plugins>)", pom_text)
    if not m:
        notes.append("no-build-plugins")
        return pom_text, notes
    pre = pom_text[: m.start()]
    post = pom_text[m.start() :]
    idx = pre.rfind("</dependencies>")
    if idx < 0:
        notes.append("no-dependencies-close")
        return pom_text, notes
    pom_text = pre[:idx] + _DEP + pre[idx:] + post
    notes.append("quarkus-hibernate-validator-added")
    return pom_text, notes


def main() -> int:
    if not POM.is_file():
        print("skip:no-pom")
        return 0
    if not has_jakarta_validation(ROOT):
        print("skip:no-jakarta-validation")
        return 0
    pom = POM.read_text(encoding="utf-8", errors="replace")
    new_pom, notes = ensure_pom(pom)
    if new_pom != pom:
        POM.write_text(new_pom, encoding="utf-8")
    print("ok:" + ",".join(notes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
