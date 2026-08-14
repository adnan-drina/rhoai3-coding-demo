#!/usr/bin/env python3
"""Assert destination pom carries Jacoco / Sonar coverage wiring (A-3 / H-3).

When pom.xml exists, require:
  1. quarkus-jacoco dependency (BOM-managed; prefer test scope)
  2. sonar.coverage.jacoco.xmlReportPaths naming BOTH report paths
  3. surefire <argLine>${argLine}</argLine> (or @{argLine}) so the agent attaches

Idle (exit 0) when pom.xml is absent — golden scaffold is harness-only until
foundation authors the POM (bootstrap-quarkus-project / DD1).

Contract reference: manage-quarkus-extensions/references/rh-bom-and-mandatory-deps.md
Fragments: bootstrap-quarkus-project/references/foundation-jacoco-wiring.md

Usage:
  python3 check-pom-jacoco-wiring.py .
  python3 check-pom-jacoco-wiring.py /projects/modernized
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

EXIT_CODES = """Exit codes:
  0  pass — wiring present, or no pom yet (idle)
  1  BLOCK — pom present but Jacoco/Sonar/argLine wiring incomplete
  2  usage
"""

DUAL_PATHS = (
    "target/jacoco-report/jacoco.xml",
    "target/site/jacoco/jacoco.xml",
)


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        print(EXIT_CODES)
        return 0
    if len(sys.argv) > 2:
        print("usage: check-pom-jacoco-wiring.py [root]", file=sys.stderr)
        return 2

    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    pom = root / "pom.xml"
    if not pom.is_file():
        print("OK: no destination pom yet — Jacoco wiring lint idle")
        return 0

    text = pom.read_text(encoding="utf-8")
    bad = 0

    if not re.search(r"<artifactId>\s*quarkus-jacoco\s*</artifactId>", text):
        print(
            "FAIL: pom missing quarkus-jacoco (use Quarkus extension, not plain jacoco-maven-plugin)",
            file=sys.stderr,
        )
        bad = 1

    m = re.search(
        r"<sonar\.coverage\.jacoco\.xmlReportPaths>\s*([^<]+)\s*</sonar\.coverage\.jacoco\.xmlReportPaths>",
        text,
    )
    if not m:
        print(
            "FAIL: pom missing <sonar.coverage.jacoco.xmlReportPaths>",
            file=sys.stderr,
        )
        bad = 1
    else:
        paths = m.group(1).strip()
        for required in DUAL_PATHS:
            if required not in paths:
                print(
                    f"FAIL: sonar.coverage.jacoco.xmlReportPaths missing {required!r} "
                    f"(dual-path gotcha — QuarkusTest vs plain Surefire)",
                    file=sys.stderr,
                )
                bad = 1

    # Surefire must forward ${argLine} / @{argLine} so coverage agents attach.
    if not re.search(
        r"<argLine>\s*(\$\{argLine\}|@\{argLine\})\s*</argLine>",
        text,
    ):
        print(
            "FAIL: surefire missing <argLine>${argLine}</argLine> "
            "(or @{argLine}) — Jacoco agent never attaches",
            file=sys.stderr,
        )
        bad = 1

    if bad:
        return 1
    print("OK: pom Jacoco/Sonar dual-path + argLine wiring present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
