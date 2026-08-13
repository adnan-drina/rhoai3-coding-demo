#!/usr/bin/env python3
"""AD-002G P0.2 — phase-dispatch.yaml skills[] must match attach matrix law.

Exit 0 when M3 is exactly {check-spec-readiness, spring-to-quarkus-patterns} and
other phases include their required minimums. Drift → refuse create.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Architect AD-002G / SOLUTION-ARCHITECTURE phase attach matrix (initial).
REQUIRED_MIN: dict[str, frozenset[str]] = {
    "M1": frozenset({"derive-legacy-boot3", "scan-with-mta", "check-spec-readiness"}),
    # Wave B: enforce-authority-boundary is .hermes/enforcement/ path-invoke only.
    "M2": frozenset({"check-spec-readiness"}),
    # provision-owns-tools: no init-spec-workspace on M2a (Architect E-121308Z)
    "M2a": frozenset({"check-spec-readiness", "scan-with-mta", "speckit-specify"}),
    "M2b": frozenset({"check-spec-readiness", "scan-with-mta"}),
    "M3": frozenset({"check-spec-readiness", "spring-to-quarkus-patterns"}),
    "M4": frozenset({"check-spec-readiness", "check-domain-parity"}),
    "M5": frozenset({"check-spec-readiness", "check-domain-parity"}),
}
# M3 is exact-set (AD-002F slim). Other phases may attach additional helpers.
EXACT: frozenset[str] = frozenset({"M3"})


def parse_phase_skills(text: str) -> dict[str, list[str]]:
    phases: dict[str, list[str]] = {}
    cur: str | None = None
    in_skills = False
    for ln in text.splitlines():
        m = re.match(r"^  (M[1-5][ab]?|factory):\s*$", ln)
        if m:
            cur = m.group(1)
            if cur != "factory":
                phases.setdefault(cur, [])
            in_skills = False
            continue
        if cur and re.match(r"^  [A-Za-z0-9_]+:\s*$", ln):
            cur = None
            in_skills = False
            continue
        if cur is None:
            continue
        if re.match(r"^    skills:\s*$", ln):
            in_skills = True
            continue
        if in_skills:
            sm = re.match(r"^      - (\S+)\s*$", ln)
            if sm:
                phases[cur].append(sm.group(1))
                continue
            if ln.strip() and not ln.startswith("      "):
                in_skills = False
    return phases


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    path = root / ".hermes" / "phase-dispatch.yaml"
    if not path.is_file():
        print(f"PHASE_ATTACH: missing {path}", file=sys.stderr)
        return 1
    phases = parse_phase_skills(path.read_text(encoding="utf-8"))
    bad = 0
    for phase, required in REQUIRED_MIN.items():
        got = set(phases.get(phase) or [])
        if not got:
            print(f"PHASE_ATTACH: {phase} has empty/missing skills[]", file=sys.stderr)
            bad = 1
            continue
        missing = required - got
        if missing:
            print(
                f"PHASE_ATTACH: {phase} missing required {sorted(missing)} "
                f"(got {sorted(got)})",
                file=sys.stderr,
            )
            bad = 1
        if phase in EXACT and got != required:
            print(
                f"PHASE_ATTACH: {phase} must be exactly {sorted(required)} "
                f"(got {sorted(got)}) — AD-002F/G",
                file=sys.stderr,
            )
            bad = 1
    if bad:
        print("Phase attach matrix checks FAILED.", file=sys.stderr)
        return 1
    print(
        "OK: phase attach matrix "
        + ", ".join(f"{p}={phases.get(p)}" for p in sorted(REQUIRED_MIN))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
