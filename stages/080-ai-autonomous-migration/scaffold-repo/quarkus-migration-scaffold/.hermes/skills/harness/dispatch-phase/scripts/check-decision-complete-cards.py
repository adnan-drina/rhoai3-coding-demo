#!/usr/bin/env python3
"""R0 — decision-complete card lint (Architect E-20260811T122959Z).

Card steps must state their own precondition + skip rule. Compound jump
conditionals that embed cross-step assumptions (e.g. retired R-M2.6
`spec.md` → jump to `/speckit-tasks`) are fail-closed.

Contract: .hermes/skills/sdd/check-spec-readiness/references/sdd-ordering.md (Spec Kit ladder; GR2)
(supersedes retired governance/retired/m2b-resume-ladder.md).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CONTRACT = ".hermes/skills/sdd/check-spec-readiness/references/sdd-ordering.md"


def extract_bodies(dispatch_sh: Path) -> dict[str, str]:
    text = dispatch_sh.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for m in re.finditer(
        r"^\s+(M[1-5][ab]?|factory)\)\s*\n.*?<<'EOF'\n(.*?)EOF",
        text,
        re.M | re.S,
    ):
        out[m.group(1)] = m.group(2)
    return out


def check_m2_ladder(body: str) -> list[str]:
    bad: list[str] = []
    # Forbidden inverted monolithic resume jump
    if re.search(r"jump\s+to\s+`?/speckit-tasks", body, re.I):
        bad.append(
            "M2 forbids compound 'jump to /speckit-tasks' (use per-artifact ladder)"
        )
    if re.search(
        r"spec\.md[^\n]{0,80}plan\.md[^\n]{0,80}(?:jump|skip re-partition|/speckit-tasks)",
        body,
        re.I | re.S,
    ):
        bad.append("M2 forbids compound spec.md+plan.md jump-over-plan resume")
    # Required per-artifact ladder markers (decision-complete)
    required = [
        (r"Skip iff.*spec\.md", "M2 must state skip-/speckit-specify iff spec.md"),
        (r"Skip iff.*plan\.md", "M2 must state skip-/speckit-plan iff plan.md"),
        (
            r"/speckit-tasks.*always last|always last.*/speckit-tasks",
            "M2 must keep /speckit-tasks always last",
        ),
        (
            r"Never.*jump over plan|Never.*jump over plan",
            "M2 must forbid jump-over-plan",
        ),
    ]
    for pat, label in required:
        if not re.search(pat, body, re.I | re.S):
            bad.append(f"FAIL decision-complete: {label}")
    return bad


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    contract = root / CONTRACT
    if not contract.is_file():
        print(f"FAIL: missing {CONTRACT}", file=sys.stderr)
        return 1
    dispatch = root / ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh"
    if not dispatch.is_file():
        print(f"FAIL: missing {dispatch}", file=sys.stderr)
        return 1
    bodies = extract_bodies(dispatch)
    bad = 0
    m2 = bodies.get("M2")
    if not m2:
        print("FAIL: M2 body missing from dispatch-phase.sh", file=sys.stderr)
        return 1
    for msg in check_m2_ladder(m2):
        print(f"FAIL: {msg}", file=sys.stderr)
        bad = 1
    if bad:
        print(
            "FAIL: decision-complete card lint (Architect E-122959Z / GR2)",
            file=sys.stderr,
        )
        return 1
    print(f"OK: decision-complete card lint (cites {CONTRACT})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
