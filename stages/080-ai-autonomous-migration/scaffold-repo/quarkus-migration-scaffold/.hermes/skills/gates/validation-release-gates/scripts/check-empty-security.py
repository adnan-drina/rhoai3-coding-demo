#!/usr/bin/env python3
"""AD-H §16.6 / AR-2.2 — refuse empty/placeholder security as completion."""
from __future__ import annotations

import re
import sys
from pathlib import Path

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
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
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

    security_enabled = bool(
        re.search(r"(?m)^petclinic\.security\.enable\s*=\s*true\s*$", props_blob)
        or re.search(r"(?m)^quarkus\.security\.jdbc\.enabled\s*=\s*true\s*$", props_blob)
        or "quarkus-elytron-security-jdbc" in pom
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
