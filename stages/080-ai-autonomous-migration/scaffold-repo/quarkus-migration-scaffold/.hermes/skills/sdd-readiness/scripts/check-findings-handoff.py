#!/usr/bin/env python3
"""M2a/M2b gate shim — delegates to mta-analysis check-findings-handoff.py.

M2a attaches sdd-readiness (not mta-analysis). Workers resolve this path first
(Deputy E-20260811T112100Z). Canonical implementation stays under mta-analysis.
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
        f"FAIL: canonical check-findings-handoff missing at {CANON}",
        file=sys.stderr,
    )
    raise SystemExit(2)

sys.argv[0] = str(CANON)
runpy.run_path(str(CANON), run_name="__main__")
