#!/usr/bin/env python3
"""Fail if partition-schema.md drifts from k4_schema.REMEDY / convert fields.

Operator 143201ZO §4.2: schema lives in one reference plus a sync test,
not as a second copy of k4_schema.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
REF = SKILL / "references" / "partition-schema.md"
KERNEL = SKILL.parents[2] / "kernel"
if str(KERNEL) not in sys.path:
    sys.path.insert(0, str(KERNEL))

from k4_producers import KIND_DEFAULTS, PRODUCERS  # noqa: E402
from k4_schema import REMEDY  # noqa: E402

PARTITION_CODES = (
    "K4_SCHEMA",
    "K4_SCOPE",
    "K4_SKILLS",
    "K4_PARENT",
    "K4_T0_3_SERVICE",
    "K4_PATH_TOKEN",
    "K4_PLANNING_DEFECT",
    "K4_LEGACY_SOURCE",
    "K4_DEST_FILE",
)

REQUIRED_FIELDS = (
    "type_inventory_sha256",
    "stories",
    "story_id",
    "files_writable",
    "parents",
    "endpoints",
    "legacy_source",
    "dest_file",
    "kind",
    "skills",
)


def main() -> int:
    if not REF.is_file():
        print("FAIL: missing %s" % REF, file=sys.stderr)
        return 1
    text = REF.read_text(encoding="utf-8")
    bad = 0
    for code in PARTITION_CODES:
        if code not in REMEDY:
            print("FAIL: k4_schema.REMEDY missing %s" % code, file=sys.stderr)
            bad = 1
            continue
        if code not in text:
            print(
                "FAIL: partition-schema.md missing code %s" % code,
                file=sys.stderr,
            )
            bad = 1
    for field in REQUIRED_FIELDS:
        if field not in text:
            print(
                "FAIL: partition-schema.md missing field %s" % field,
                file=sys.stderr,
            )
            bad = 1
    if "k4_schema.py" not in text:
        print("FAIL: reference must name k4_schema.py as authority", file=sys.stderr)
        bad = 1
    if "k4_producers.py" not in text or "KIND_DEFAULTS" not in text:
        print(
            "FAIL: partition-schema.md must name k4_producers.py KIND_DEFAULTS",
            file=sys.stderr,
        )
        bad = 1
    for name in PRODUCERS:
        if name not in text:
            print(
                "FAIL: partition-schema.md missing producer %s" % name,
                file=sys.stderr,
            )
            bad = 1
    for kind, skills in KIND_DEFAULTS.items():
        if kind not in text:
            print(
                "FAIL: partition-schema.md missing kind %s" % kind,
                file=sys.stderr,
            )
            bad = 1
        for skill in skills:
            if skill not in PRODUCERS:
                print(
                    "FAIL: KIND_DEFAULTS %s/%s not in PRODUCERS" % (kind, skill),
                    file=sys.stderr,
                )
                bad = 1
            if skill not in text:
                print(
                    "FAIL: partition-schema.md missing default skill %s" % skill,
                    file=sys.stderr,
                )
                bad = 1
    if "spring-to-quarkus-patterns" not in KIND_DEFAULTS.get("polish", []):
        print(
            "FAIL: polish KIND_DEFAULTS must include spring-to-quarkus-patterns",
            file=sys.stderr,
        )
        bad = 1
    if bad:
        return 1
    print("OK: partition-schema.md in sync with k4_schema.REMEDY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
