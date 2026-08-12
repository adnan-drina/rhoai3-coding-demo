#!/usr/bin/env python3
"""R0 — decision-complete card lint (Architect E-20260811T122959Z).

Card steps must state their own precondition + skip rule. Compound jump
conditionals that embed cross-step assumptions (e.g. v11 R-M2.6
`spec.md` → jump to `/speckit-tasks`) are fail-closed.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


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


def check_m2b(body: str) -> list[str]:
    bad: list[str] = []
    # Forbidden inverted monolithic resume jump
    if re.search(r"jump\s+to\s+`?/speckit-tasks", body, re.I):
        bad.append("M2b forbids compound 'jump to /speckit-tasks' (use per-artifact ladder)")
    if re.search(
        r"spec\.md[^\n]{0,80}plan\.md[^\n]{0,80}(?:jump|skip re-partition|/speckit-tasks)",
        body,
        re.I | re.S,
    ):
        bad.append("M2b forbids compound spec.md+plan.md jump-over-plan resume")
    # Required per-artifact ladder markers (decision-complete)
    required = [
        (r"Skip iff.*spec\.md", "M2b must state skip-/speckit-specify iff spec.md"),
        (r"Skip iff.*plan\.md", "M2b must state skip-/speckit-plan iff plan.md"),
        (r"/speckit-tasks.*always last|always last.*/speckit-tasks", "M2b must keep /speckit-tasks always last"),
        (r"Never.*jump over plan|Never.*jump over plan", "M2b must forbid jump-over-plan"),
    ]
    for pat, label in required:
        if not re.search(pat, body, re.I | re.S):
            bad.append(f"FAIL decision-complete: {label}")
    return bad


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    dispatch = root / ".hermes/skills/harness/phase-dispatch/scripts/dispatch-phase.sh"
    if not dispatch.is_file():
        print(f"FAIL: missing {dispatch}", file=sys.stderr)
        return 1
    bodies = extract_bodies(dispatch)
    bad = 0
    m2b = bodies.get("M2b")
    if not m2b:
        print("FAIL: M2b body missing from dispatch-phase.sh", file=sys.stderr)
        return 1
    for msg in check_m2b(m2b):
        print(f"FAIL: {msg}", file=sys.stderr)
        bad = 1
    if bad:
        print("FAIL: decision-complete card lint (Architect E-122959Z)", file=sys.stderr)
        return 1
    print("OK: decision-complete card lint (M2b per-artifact resume ladder)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
