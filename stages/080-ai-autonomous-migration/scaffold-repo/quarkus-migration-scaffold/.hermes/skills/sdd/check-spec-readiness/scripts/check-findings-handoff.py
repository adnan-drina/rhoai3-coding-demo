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

# Resolve the canonical implementation, which lives in a DIFFERENT skill.
# Layouts seen in the wild:
#   categorized: .hermes/skills/<category>/<leaf>/scripts/   (R-SK.7, current)
#   flat:        .hermes/skills/<leaf>/scripts/              (pre-category)
#   runtime:     HERMES_HOME/.../software-development/<leaf>/scripts/
# parents[2] alone assumes the flat layout and resolves to
# `skills/sdd/scan-with-mta/...`, which never exists under the category tree —
# the shim then always exited 2 and its callers read that as a harness defect.
_here = Path(__file__).resolve()
_TARGET = Path("scan-with-mta") / "scripts" / "check-findings-handoff.py"


def _find_canonical() -> Path:
    for up in (2, 3):
        try:
            parent = _here.parents[up]
        except IndexError:
            continue
        direct = parent / _TARGET
        if direct.is_file():
            return direct
        # categorized: search one category level down
        for hit in sorted(parent.glob(str(Path("*") / _TARGET))):
            if hit.is_file():
                return hit
    return _here.parents[2] / _TARGET


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
