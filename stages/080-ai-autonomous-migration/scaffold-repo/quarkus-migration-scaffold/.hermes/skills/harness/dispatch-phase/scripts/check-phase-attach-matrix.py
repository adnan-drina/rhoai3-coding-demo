#!/usr/bin/env python3
"""AD-002G P0.2 — phase-dispatch.yaml skills[] must match attach matrix law.

Exit 0 when each phase lists its required minimums. M3 skills[] is the
**allowed attach pool** (B-16). The pool is a superset of
OPERAND_CLASS_SKILLS plus check-spec-readiness — not a second five-name
list. Extra helpers on non-exact phases are allowed.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

# Architect AD-002G / SOLUTION-ARCHITECTURE phase attach matrix (initial).
# M3 required names come from OPERAND_CLASS_SKILLS (one source), not a
# hardcoded five-wide copy here (Operator 50c3e13c).
REQUIRED_MIN: dict[str, frozenset[str]] = {
    "M1": frozenset({"derive-legacy-boot3", "scan-with-mta"}),
    # GR2 — unified M2 PLAN (partition + Spec Kit); mint via mint-m3-hermes.md
    # Operator 093930Z: check-spec-readiness / derive-story-oracles not M2-attached
    "M2": frozenset({"scan-with-mta", "speckit-specify"}),
    # RETIRED stubs (GR2) — attach-matrix still validates until F9 drops keys
    "M2a": frozenset({"scan-with-mta", "speckit-specify"}),
    "M2b": frozenset({"scan-with-mta"}),
    "M4": frozenset({"check-spec-readiness", "check-domain-parity"}),
    "M5": frozenset({"check-spec-readiness", "check-domain-parity"}),
}
# M3 yaml skills[] is the allow-list pool (B-16), not an exact attach set.
# Extra helpers may be listed. create-m3 subsets from identity.operand_skills.
EXACT: frozenset[str] = frozenset()
M3_LINT_SKILL = "check-spec-readiness"


def load_operand_class_skills(root: Path) -> dict[str, tuple[str, ...]]:
    path = (
        root
        / ".hermes"
        / "skills"
        / "sdd"
        / "check-spec-readiness"
        / "scripts"
        / "specimen_agnostic.py"
    )
    if not path.is_file():
        raise FileNotFoundError(f"missing {path}")
    spec = importlib.util.spec_from_file_location("_operand_class_skills", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mapping = getattr(mod, "OPERAND_CLASS_SKILLS", None)
    if not isinstance(mapping, dict):
        raise RuntimeError("OPERAND_CLASS_SKILLS missing")
    return mapping


def m3_recommender_vocab(root: Path) -> frozenset[str]:
    names: set[str] = {M3_LINT_SKILL}
    for skills in load_operand_class_skills(root).values():
        for skill in skills:
            n = str(skill).strip()
            if n:
                names.add(n)
    return frozenset(names)


def parse_bundle_skills(path: Path) -> list[str]:
    if not path.is_file():
        return []
    names: list[str] = []
    in_skills = False
    for ln in path.read_text(encoding="utf-8").splitlines():
        if re.match(r"^skills:\s*$", ln):
            in_skills = True
            continue
        if in_skills:
            sm = re.match(r"^- (\S+)\s*$", ln)
            if sm:
                names.append(sm.group(1))
                continue
            if ln.strip() and not ln.startswith("-") and not ln.startswith(" "):
                break
    return names


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
    try:
        vocab = m3_recommender_vocab(root)
    except (OSError, RuntimeError) as exc:
        print(f"PHASE_ATTACH: cannot load OPERAND_CLASS_SKILLS: {exc}", file=sys.stderr)
        return 1
    m3_got = set(phases.get("M3") or [])
    if not m3_got:
        print("PHASE_ATTACH: M3 has empty/missing skills[]", file=sys.stderr)
        bad = 1
    else:
        missing = vocab - m3_got
        if missing:
            print(
                f"PHASE_ATTACH: M3 yaml pool missing recommender names "
                f"{sorted(missing)} (got {sorted(m3_got)}; "
                f"OPERAND_CLASS_SKILLS is the source)",
                file=sys.stderr,
            )
            bad = 1
    bundle = root / ".hermes" / "home" / "skill-bundles" / "m3-implementer.yaml"
    bundle_skills = set(parse_bundle_skills(bundle))
    bundle_missing = vocab - bundle_skills
    if bundle_missing:
        print(
            f"PHASE_ATTACH: m3-implementer bundle missing recommender names "
            f"{sorted(bundle_missing)}",
            file=sys.stderr,
        )
        bad = 1
    if bad:
        print("Phase attach matrix checks FAILED.", file=sys.stderr)
        return 1
    shown = dict(REQUIRED_MIN)
    shown["M3"] = vocab
    print(
        "OK: phase attach matrix "
        + ", ".join(f"{p}={phases.get(p)}" for p in sorted(shown))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
