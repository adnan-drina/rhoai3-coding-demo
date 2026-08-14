#!/usr/bin/env python3
"""AD-H §16.6 / AR-2.2 — refuse empty/placeholder security as completion.

Scans `<root>/src/main/java` for `*Security*.java` / `*Authentication*.java`
types plus `<root>/src/main/resources/application*.properties` and
`<root>/pom.xml`. Idle when no security types exist and security is not
enabled.

Usage:
  python3 check-empty-security.py .
  python3 check-empty-security.py /projects/modernized
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EXIT_CODES = """Exit codes:
  0  pass — functional security surface present, or gate idle (no security
     types and security not enabled)
  1  BLOCK — missing quarkus-security / quarkus-elytron-security-jdbc, no
     security types while security is enabled, or empty / placeholder /
     javadoc-only security classes (AR-2.2, R-M3.39)
  2  usage / harness defect (bad or unknown argument)
"""

PLACEHOLDER_MARKERS = (
    "structural placeholder",
    "this bean is inert",
    "exists solely as a documentation anchor",
    "until then this bean is inert",
    # R-M3.39 / v11 S-005 javadoc-only shells (Review E-20260811T054056Z)
    "security configuration is declarative",
    "no java-based filter chain",
    "no java class needed to express",
    "security is disabled by default in quarkus",
)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="product root containing src/ and pom.xml (default: .)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    sec = root / "src/main/java"
    props_blob = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((root / "src/main/resources").glob("application*.properties"))
        if p.is_file()
    )
    pom = (root / "pom.xml").read_text(encoding="utf-8") if (root / "pom.xml").is_file() else ""

    java_files: list[Path] = []
    if sec.is_dir():
        java_files = list(sec.rglob("*Security*.java")) + list(
            sec.rglob("*Authentication*.java")
        )

    # POM-only security deps (foundation / S-001 handoff) are NOT "enabled".
    # Enabled requires properties or security Java types; else gate stays idle
    # so later stories can land config/types without false-failing compile-only cards.
    security_enabled = bool(
        # R-SK.5: match any <app>.security.enable=true, not one specimen's
        # property name. A legacy app names this after itself; hardcoding
        # one made the gate blind to every other codebase.
        re.search(r"(?m)^[\w.-]+\.security\.enable\s*=\s*true\s*$", props_blob)
        or re.search(r"(?m)^quarkus\.security\.jdbc\.enabled\s*=\s*true\s*$", props_blob)
        or (
            "quarkus-elytron-security-jdbc" in pom
            and (
                bool(re.search(r"(?m)^quarkus\.security\.", props_blob))
                or bool(java_files)
            )
        )
        or bool(java_files)
    )

    if not java_files and not security_enabled:
        print("OK: AR-2.2 idle (no security types / security not enabled)")
        return 0

    bad = 0
    if "quarkus-security" not in pom:
        print("FAIL: AR-2.2 pom missing quarkus-security", file=sys.stderr)
        bad = 1
    if security_enabled and "quarkus-elytron-security-jdbc" not in pom:
        print("FAIL: AR-2.2 security enabled without quarkus-elytron-security-jdbc", file=sys.stderr)
        bad = 1

    if not java_files and security_enabled:
        print(
            "FAIL: AR-2.2 security enabled but no *Security*/*Authentication* types",
            file=sys.stderr,
        )
        bad = 1

    for path in java_files:
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(root)
        low = text.lower()
        if any(m in low for m in PLACEHOLDER_MARKERS):
            print(f"FAIL: AR-2.2 placeholder security class {rel}", file=sys.stderr)
            bad = 1
            continue
        if re.search(r"class\s+\w+[^{]*\{\s*\}", text, re.S):
            print(f"FAIL: AR-2.2 empty security class {rel}", file=sys.stderr)
            bad = 1
            continue
        # Brace body with only comments/whitespace → javadoc-only shell (R-M3.39)
        m = re.search(r"class\s+\w+[^{]*\{(.*)\}\s*\Z", text, re.S)
        if m is not None:
            body = m.group(1)
            stripped = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
            stripped = re.sub(r"//.*?$", "", stripped, flags=re.M)
            if stripped.strip() == "":
                print(f"FAIL: AR-2.2 javadoc-only security class {rel}", file=sys.stderr)
                bad = 1

    for path in sec.rglob("Roles.java") if sec.is_dir() else []:
        text = path.read_text(encoding="utf-8")
        if "static final String" not in text and "static final" not in text:
            print(
                f"FAIL: AR-2.2/AR-3.1 {path.relative_to(root)} lacks static final role constants",
                file=sys.stderr,
            )
            bad = 1

    if bad:
        print("AR-2.2 empty-security checks FAILED", file=sys.stderr)
        return 1
    print(f"OK: AR-2.2 security surface ({len(java_files)} class(es))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
