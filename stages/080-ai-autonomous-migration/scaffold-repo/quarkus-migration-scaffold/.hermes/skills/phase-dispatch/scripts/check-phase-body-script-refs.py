#!/usr/bin/env python3
"""R0 body-script lint — every script named in a phase seed body must resolve.

Deputy E-20260811T112700Z / R-HX.12 live specimen: bare `check-findings-handoff.py`
on M2a with mta-analysis not attached → worker could not skill_view the owning
skill. Fail-closed at create/dispatch when a body cites `*.py`/`*.sh` that is
not under an attached skill's `scripts/` (or an explicit `.hermes/skills/...`
path present on disk).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Same phase→skills parser contract as check-phase-attach-matrix.py
PHASE_KEY = re.compile(r"^  (M[1-5][ab]?|factory):\s*$")
SKILL_ITEM = re.compile(r"^      - (\S+)\s*$")
# Script refs in markdown bodies (bare name or path)
SCRIPT_REF = re.compile(
    r"(?:`|/|\s)((?:\.hermes/skills/[\w./-]+/scripts/)?[\w.-]+\.(?:py|sh))(?:`|\s|$)"
)


def parse_phase_skills(text: str) -> dict[str, list[str]]:
    phases: dict[str, list[str]] = {}
    cur: str | None = None
    in_skills = False
    for ln in text.splitlines():
        m = PHASE_KEY.match(ln)
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
            sm = SKILL_ITEM.match(ln)
            if sm:
                phases[cur].append(sm.group(1))
                continue
            if ln.strip() and not ln.startswith("      "):
                in_skills = False
    return phases


def extract_body_scripts(dispatch_sh: Path) -> dict[str, set[str]]:
    """Pull heredoc bodies per phase from dispatch-phase.sh (M1|M2a|…)."""
    text = dispatch_sh.read_text(encoding="utf-8")
    out: dict[str, set[str]] = {}
    # case arms: M2a) ... cat >... <<'EOF' ... EOF
    for m in re.finditer(
        r"^\s+(M[1-5][ab]?|factory)\)\s*\n.*?<<'EOF'\n(.*?)EOF",
        text,
        re.M | re.S,
    ):
        phase, body = m.group(1), m.group(2)
        refs = set(SCRIPT_REF.findall(body))
        if refs:
            out[phase] = refs
    return out


def resolve_ok(root: Path, phase: str, skills: list[str], ref: str) -> bool:
    if ref.startswith(".hermes/skills/") or ref.startswith("migration/"):
        return (root / ref).is_file()
    if ref.startswith(".hermes/home/scripts/"):
        return (root / ref).is_file()
    name = Path(ref).name
    # bare name — attached skill scripts, phase-dispatch harness, or home scripts
    home = root / ".hermes" / "home" / "scripts" / name
    if home.is_file():
        return True
    search_skills = list(skills) + ["phase-dispatch"]
    for sk in search_skills:
        cand = root / ".hermes" / "skills" / sk / "scripts" / name
        if cand.is_file():
            return True
    return False


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    yaml = root / ".hermes" / "phase-dispatch.yaml"
    dispatch = root / ".hermes" / "skills" / "phase-dispatch" / "scripts" / "dispatch-phase.sh"
    if not yaml.is_file() or not dispatch.is_file():
        print("BODY_SCRIPT_LINT: missing phase-dispatch.yaml or dispatch-phase.sh", file=sys.stderr)
        return 1
    phases = parse_phase_skills(yaml.read_text(encoding="utf-8"))
    bodies = extract_body_scripts(dispatch)
    bad = 0
    for phase, refs in sorted(bodies.items()):
        skills = phases.get(phase) or []
        for ref in sorted(refs):
            if resolve_ok(root, phase, skills, ref):
                print(f"OK: {phase} → {ref}")
            else:
                print(
                    f"FAIL: {phase} body cites {ref!r} but not under attached "
                    f"skills {skills}",
                    file=sys.stderr,
                )
                bad = 1
    if bad:
        print("FAIL: phase body script refs (R0 / Deputy E-20260811T112700Z)", file=sys.stderr)
        return 1
    print("OK: phase body script refs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
