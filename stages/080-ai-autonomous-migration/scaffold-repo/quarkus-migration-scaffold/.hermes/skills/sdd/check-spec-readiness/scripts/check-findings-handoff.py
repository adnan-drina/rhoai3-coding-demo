#!/usr/bin/env python3
"""M2a/M2b gate shim — delegates to scan-with-mta check-findings-handoff.py.

M2a attaches check-spec-readiness (+ scan-with-mta after E-112700Z). Prefer invoking via
`${HERMES_SKILL_DIR:-.hermes/home/skills/software-development/check-spec-readiness}/scripts/…`
(Deputy E-20260811T113300Z runtime root). Canonical stays under scan-with-mta.

Exit: 0=pass; 1=FAIL→BLOCK; 2=missing script (lint/harness defect).
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

_here = Path(__file__).resolve()
_TARGET = Path("scan-with-mta") / "scripts" / "check-findings-handoff.py"


def _migration_root(start: Path) -> Path | None:
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent
    while True:
        if (cur / "migration.yaml").is_file():
            return cur
        if cur == cur.parent:
            return None
        cur = cur.parent


def _find_canonical() -> Path:
    mig = _migration_root(_here)
    if mig is not None:
        skills = mig / ".hermes" / "skills"
        for hit in sorted(skills.glob(str(Path("*") / _TARGET))):
            if hit.is_file():
                return hit
        flat = skills / _TARGET
        if flat.is_file():
            return flat
    return _here.parent / "missing-check-findings-handoff.py"


CANON = _find_canonical()

if not CANON.is_file():
    print(
        f"FAIL: exit=2 missing script — canonical check-findings-handoff at {CANON} "
        f"(lint/harness defect; do not invent)",
        file=sys.stderr,
    )
    raise SystemExit(2)

sys.argv[0] = str(CANON)
runpy.run_path(str(CANON), run_name="__main__")
