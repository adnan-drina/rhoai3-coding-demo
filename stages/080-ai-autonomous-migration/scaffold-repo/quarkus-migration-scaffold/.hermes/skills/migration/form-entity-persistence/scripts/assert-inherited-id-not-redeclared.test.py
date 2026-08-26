#!/usr/bin/env python3
"""W6: child @Id when mapped superclass already has one REFUSE. Not dest."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
BIN = HERE / "assert-inherited-id-not-redeclared.py"
FIX = SKILL / "fixtures"
REF = SKILL / "references" / "entity-mapping.md"


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BIN), str(root)],
        text=True,
        capture_output=True,
    )


def main() -> int:
    md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    ref = REF.read_text(encoding="utf-8")
    if "assert-inherited-id-not-redeclared.py" not in md:
        print("FAIL: SKILL.md must name assert-inherited-id-not-redeclared.py", file=sys.stderr)
        return 1
    if "inherited" not in ref.lower() or "exactly one" not in ref.lower():
        print("FAIL: entity-mapping.md must admit inherited @Id", file=sys.stderr)
        return 1

    bad = FIX / "subclass-redeclares-inherited-id-refuses"
    proc = run(bad)
    blob = proc.stdout + proc.stderr
    if proc.returncode != 1:
        print("FAIL: redeclared @Id must REFUSE: %s" % blob, file=sys.stderr)
        return 1
    if "INHERITED_ID_REDECLARED" not in blob or "Owner" not in blob:
        print("FAIL: refuse detail missing Owner: %s" % blob, file=sys.stderr)
        return 1

    good = FIX / "mapped-superclass-id-only-passes"
    proc = run(good)
    if proc.returncode != 0:
        print(
            "FAIL: BaseEntity-only @Id must PASS: %s%s" % (proc.stdout, proc.stderr),
            file=sys.stderr,
        )
        return 1

    print("OK: assert-inherited-id-not-redeclared (refuse child / pass inherited)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
