#!/usr/bin/env python3
"""S-010 Class A — scaffold must declare test toolchain (assertj + rest-assured).

Exit 0 when pom.xml includes both test-scoped deps (or BOM-imported GAVs).
Exit 1 (REFUSE) when either is missing — harness decision, not specimen rediscovery.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED = (
    ("io.rest-assured", "rest-assured"),
    ("org.assertj", "assertj-core"),
)


def has_dep(pom: str, group: str, artifact: str) -> bool:
    # Naive but durable for our scaffold poms: adjacent groupId/artifactId.
    pattern = (
        rf"<groupId>\s*{re.escape(group)}\s*</groupId>\s*"
        rf"<artifactId>\s*{re.escape(artifact)}\s*</artifactId>"
    )
    return re.search(pattern, pom, re.S) is not None


def assertj_has_version(pom: str) -> bool:
    """RH Quarkus BOM may not manage assertj — require an explicit version."""
    m = re.search(
        r"<groupId>\s*org\.assertj\s*</groupId>\s*"
        r"<artifactId>\s*assertj-core\s*</artifactId>\s*"
        r"(?:<version>\s*[^<]+\s*</version>\s*)?"
        r"<scope>\s*test\s*</scope>",
        pom,
        re.S,
    )
    if not m:
        # allow version after scope too
        m = re.search(
            r"<groupId>\s*org\.assertj\s*</groupId>\s*"
            r"<artifactId>\s*assertj-core\s*</artifactId>.*?</dependency>",
            pom,
            re.S,
        )
        if not m:
            return False
        return bool(re.search(r"<version>\s*[^<]+\s*</version>", m.group(0)))
    return "<version>" in m.group(0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    pom_path = root / "pom.xml"
    if not pom_path.is_file():
        print(f"FAIL: no pom.xml under {root}", file=sys.stderr)
        return 1
    pom = pom_path.read_text(encoding="utf-8", errors="replace")
    missing = [f"{g}:{a}" for g, a in REQUIRED if not has_dep(pom, g, a)]
    if missing:
        print(
            "FAIL: S-010 Class A test toolchain missing from pom.xml: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        print(
            "  harness must ship assertj-core + rest-assured (test scope); "
            "see .hermes/skills/migration/manage-quarkus-extensions/references/test-toolchain.md",
            file=sys.stderr,
        )
        return 1
    if not assertj_has_version(pom):
        print(
            "FAIL: org.assertj:assertj-core present but missing <version> "
            "(RH Quarkus BOM may not manage it)",
            file=sys.stderr,
        )
        return 1
    print("OK: test toolchain present (rest-assured + assertj-core@version)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
