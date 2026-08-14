#!/usr/bin/env python3
"""Assert destination pom quarkus.platform.* matches .hermes/pins.json.

Skill: manage-quarkus-extensions (Architect E-20260813T162238Z — no version
literals in skills; pom ↔ pins lint).

Usage:
  python3 check-pom-platform-pins.py .
  python3 check-pom-platform-pins.py /projects/modernized
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

EXIT_CODES = """Exit codes:
  0  pass — pom platform group/artifact/version match .hermes/pins.json
  1  BLOCK — mismatch or missing pin/pom properties
  2  usage
"""

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


def quarkus_platform_props(root: Path) -> dict[str, str]:
    path = root / ".hermes" / "pins.json"
    if not path.is_file():
        raise FileNotFoundError(str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    pins = data.get("pins") if isinstance(data, dict) else None
    if not isinstance(pins, dict):
        raise ValueError("pins.json missing pins object")
    qp = pins.get("quarkus_platform") or {}
    g = str(qp.get("group_id") or "").strip()
    a = str(qp.get("bom_artifact_id") or "").strip()
    v = str(qp.get("version") or "").strip()
    if not (g and a and v):
        raise ValueError("quarkus_platform incomplete in .hermes/pins.json")
    return {
        "quarkus.platform.group-id": g,
        "quarkus.platform.artifact-id": a,
        "quarkus.platform.version": v,
    }


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    pom = root / "pom.xml"
    if not pom.is_file():
        print(f"FAIL: missing {pom}", file=sys.stderr)
        return 1
    try:
        expected = quarkus_platform_props(root)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: cannot load .hermes/pins.json: {e}", file=sys.stderr)
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
                f"FAIL: pom <{key}>={a!r} != pins.json {e!r}",
                file=sys.stderr,
            )
            bad = 1
    if bad:
        return 1
    if actual.get("quarkus.platform.group-id") == "io.quarkus.platform":
        print(
            "FAIL: pom platform group-id is community io.quarkus.platform",
            file=sys.stderr,
        )
        return 1
    print("OK: pom platform pins match .hermes/pins.json")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        print(__doc__)
        print(EXIT_CODES)
        raise SystemExit(0)
    raise SystemExit(main())
