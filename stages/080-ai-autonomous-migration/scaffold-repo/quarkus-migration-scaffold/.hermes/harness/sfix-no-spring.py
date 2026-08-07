#!/usr/bin/env python3
"""O-SFIXNOSPRING (F-21): sensor-fix must not reintroduce Spring.

Compares before..after commits. Exit 1 if the diff adds:
  - import org.springframework.* (Java) — except Spring Data API imports
    when pom already has a quarkus-spring-* extension (O-SFIXNOSPRINGSDATA /
    W3-70: key on any quarkus-spring-* , not only quarkus-spring-data-jpa)
  - spring-* Maven dependencies in pom.xml (not quarkus-spring-*)
Exit 0 if clean. Prints offending lines to stdout.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def _allows_spring_data() -> bool:
    """W3-70: allow spring-data imports only when a Quarkus Spring extension licenses them."""
    pom = Path("pom.xml")
    if not pom.is_file():
        return False
    try:
        text = pom.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return bool(re.search(r"<artifactId>\s*quarkus-spring-[a-z0-9-]+\s*<", text, re.I))


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: sfix-no-spring.py <before-sha> <after-sha>", file=sys.stderr)
        return 2
    before, after = sys.argv[1], sys.argv[2]
    diff = subprocess.check_output(
        ["git", "diff", f"{before}..{after}", "-U0", "--", "*.java", "pom.xml"],
        text=True,
        errors="replace",
    )
    allow_data = _allows_spring_data()
    bad: list[str] = []
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:]
        if re.search(r"\bimport\s+org\.springframework\.", body):
            # Quarkus Spring Data compatibility surface — not spring-di green-wash
            if allow_data and re.search(r"org\.springframework\.data\.", body):
                continue
            bad.append(body.strip())
        if re.search(r"<artifactId>\s*spring-[^<]+</artifactId>", body, re.I):
            bad.append(body.strip())
        if re.search(r"<groupId>\s*org\.springframework", body, re.I):
            bad.append(body.strip())
    if bad:
        print("O-SFIXNOSPRING: sensor-fix reintroduced Spring:")
        for b in bad[:20]:
            print(f"  + {b[:120]}")
        return 1
    print("O-SFIXNOSPRING: OK (no new Spring imports/deps)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
