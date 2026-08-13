#!/usr/bin/env python3
"""Assert destination pom quarkus.platform.* matches tooling-pins.md.

Contract: governance/contracts/tooling-pins.md
Skill: manage-quarkus-extensions (Architect E-20260813T162238Z — no version
literals in skills; pom ↔ pins lint).

Usage:
  python3 check-pom-platform-pins.py .
  python3 check-pom-platform-pins.py /projects/modernized
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

EXIT_CODES = """Exit codes:
  0  pass — pom platform group/artifact/version match tooling-pins
  1  BLOCK — mismatch or missing pin/pom properties
  2  usage
"""

PINS = "governance/contracts/tooling-pins.md"
PROP_KEYS = (
    "quarkus.platform.group-id",
    "quarkus.platform.artifact-id",
    "quarkus.platform.version",
)


def pom_props(pom: Path) -> dict[str, str]:
    text = pom.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for key in PROP_KEYS:
        m = re.search(
            rf"<{re.escape(key)}>\s*([^<]+)\s*</{re.escape(key)}>",
            text,
        )
        if m:
            out[key] = m.group(1).strip()
    return out


def pins_platform(pins: Path) -> dict[str, str]:
    text = pins.read_text(encoding="utf-8")
    # Expect a markdown row: | **Red Hat Quarkus platform** | group:artifact:version | ...
    m = re.search(
        r"\*\*Red Hat Quarkus platform\*\*\s*\|\s*`([^`]+)`",
        text,
    )
    if not m:
        # alternate: bare GAV in backticks on that row
        m = re.search(
            r"Red Hat Quarkus platform[^\n]*\|\s*`([^`]+)`",
            text,
            re.I,
        )
    if not m:
        return {}
    gav = m.group(1).strip()
    parts = gav.split(":")
    if len(parts) != 3:
        return {}
    return {
        "quarkus.platform.group-id": parts[0],
        "quarkus.platform.artifact-id": parts[1],
        "quarkus.platform.version": parts[2],
    }


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    pom = root / "pom.xml"
    pins = root / PINS
    if not pom.is_file():
        print(f"FAIL: missing {pom}", file=sys.stderr)
        return 1
    if not pins.is_file():
        print(f"FAIL: missing {PINS}", file=sys.stderr)
        return 1
    expected = pins_platform(pins)
    if not expected:
        print(
            f"FAIL: {PINS} missing **Red Hat Quarkus platform** GAV row",
            file=sys.stderr,
        )
        return 1
    actual = pom_props(pom)
    bad = 0
    for key in PROP_KEYS:
        a = actual.get(key)
        e = expected.get(key)
        if not a:
            print(f"FAIL: pom missing <{key}>", file=sys.stderr)
            bad = 1
            continue
        if a != e:
            print(
                f"FAIL: pom <{key}>={a!r} != tooling-pins {e!r}",
                file=sys.stderr,
            )
            bad = 1
    if bad:
        return 1
    # Community rewrite refuse
    blob = pom.read_text(encoding="utf-8")
    if "io.quarkus.platform" in blob and "com.redhat.quarkus.platform" in blob:
        # group-id property must not be community; scan property value only
        if actual.get("quarkus.platform.group-id") == "io.quarkus.platform":
            print(
                "FAIL: pom platform group-id is community io.quarkus.platform",
                file=sys.stderr,
            )
            return 1
    elif actual.get("quarkus.platform.group-id") == "io.quarkus.platform":
        print(
            "FAIL: pom platform group-id is community io.quarkus.platform",
            file=sys.stderr,
        )
        return 1
    print(f"OK: pom platform pins match {PINS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
