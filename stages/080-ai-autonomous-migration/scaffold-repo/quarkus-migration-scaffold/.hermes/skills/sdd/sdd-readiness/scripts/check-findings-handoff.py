#!/usr/bin/env python3
"""M2a/M2b gate shim — delegates to mta-analysis check-findings-handoff.py.

M2a attaches sdd-readiness (+ mta-analysis after E-112700Z). Prefer invoking via
`${HERMES_SKILL_DIR:-.hermes/home/skills/software-development/sdd-readiness}/scripts/…`
(Deputy E-20260811T113300Z runtime root). Canonical stays under mta-analysis.

Exit: 0=pass; 1=FAIL→BLOCK; 2=missing script (lint/harness defect).
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

# Sibling under the same skills parent:
#   .hermes/skills/{sdd-readiness,mta-analysis}/scripts/
#   or HERMES_HOME/.../software-development/{sdd-readiness,mta-analysis}/scripts/
_skills_parent = Path(__file__).resolve().parents[2]
CANON = _skills_parent / "mta-analysis" / "scripts" / "check-findings-handoff.py"

if not CANON.is_file():
    print(
        f"FAIL: exit=2 missing script — canonical check-findings-handoff at {CANON} "
        f"(lint/harness defect; do not invent)",
        file=sys.stderr,
    )
    raise SystemExit(2)

sys.argv[0] = str(CANON)
runpy.run_path(str(CANON), run_name="__main__")
