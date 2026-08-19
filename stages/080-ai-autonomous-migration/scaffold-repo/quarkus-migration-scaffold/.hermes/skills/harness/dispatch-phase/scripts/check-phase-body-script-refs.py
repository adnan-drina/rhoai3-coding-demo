#!/usr/bin/env python3
"""R0 body-script lint — every script named in a phase seed body must resolve.

Deputy E-20260811T112700Z / R-HX.12: bare names + missing attach → skill_view fail.
Deputy E-20260811T113300Z: card anchors must resolve at RUNTIME skill root
(`.hermes/home/skills/software-development/<skill>/` via symlink) or via
`${HERMES_SKILL_DIR}` (AD-H §7.1) — scaffold-only `.hermes/skills/...` paths
404 when workers probe the Hermes discovery tree first.

Fail-closed at create/dispatch.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PHASE_KEY = re.compile(r"^  (M[1-5][ab]?|factory):\s*$")
SKILL_ITEM = re.compile(r"^      - (\S+)\s*$")
# Capture scaffold paths, runtime home paths, HERMES_SKILL_DIR forms, bare names
SCRIPT_REF = re.compile(
    r"(?:`|/|\s|=|\")"
    r"("
    r"(?:\$\{HERMES_SKILL_DIR(?::-[\w./-]+)?\}/scripts/[\w.-]+\.(?:py|sh))"
    r"|(?:\.hermes/home/skills/software-development/[\w.-]+/scripts/[\w.-]+\.(?:py|sh))"
    r"|(?:\.hermes/skills/[\w./-]+/scripts/[\w.-]+\.(?:py|sh))"
    r"|(?:\.hermes/home/scripts/[\w.-]+\.(?:py|sh))"
    r"|(?:[\w.-]+\.(?:py|sh))"
    r")"
    r"(?:`|\s|\"|$)"
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
    text = dispatch_sh.read_text(encoding="utf-8")
    out: dict[str, set[str]] = {}
    for m in re.finditer(
        r"^\s+(M[1-5][ab]?|factory)\)\s*\n"
        r"((?:(?!^\s+(?:M[1-5][ab]?|factory)\)).)*)",
        text,
        re.M | re.S,
    ):
        phase, block = m.group(1), m.group(2)
        hm = re.search(r"<<'EOF'\n(.*?)EOF", block, re.S)
        if not hm:
            continue
        refs = set(SCRIPT_REF.findall(hm.group(1)))
        if refs:
            out[phase] = refs
    return out


def skill_script_exists(root: Path, skill: str, name: str) -> bool:
    """Accept tip scaffold path OR runtime Hermes discovery symlink target.

    Skills live under categorized dirs (analysis/gates/migration/sdd/harness)
    after EX-3; dispatch-phase scripts live under skills/harness/.
    """
    candidates = [
        root / ".hermes" / "skills" / skill / "scripts" / name,
        root / ".hermes" / "enforcement" / skill / "scripts" / name,
    ]
    for cat in ("analysis", "gates", "migration", "sdd"):
        candidates.append(root / ".hermes" / "skills" / cat / skill / "scripts" / name)
    # Also accept any category depth-1 match (future categories).
    skills_root = root / ".hermes" / "skills"
    if skills_root.is_dir():
        for cat_dir in skills_root.iterdir():
            if cat_dir.is_dir():
                candidates.append(cat_dir / skill / "scripts" / name)
    for scaffold in candidates:
        if scaffold.is_file():
            return True
    runtime = (
        root
        / ".hermes"
        / "home"
        / "skills"
        / "software-development"
        / skill
        / "scripts"
        / name
    )
    return runtime.is_file()


def resolve_ok(root: Path, phase: str, skills: list[str], ref: str) -> bool:
    # ${HERMES_SKILL_DIR}/scripts/X or ${HERMES_SKILL_DIR:-default}/scripts/X
    m = re.match(
        r"\$\{HERMES_SKILL_DIR(?::-([\w./-]+))?\}/scripts/([\w.-]+\.(?:py|sh))$",
        ref,
    )
    if m:
        default_root, name = m.group(1), m.group(2)
        if default_root:
            # default may be .hermes/home/skills/software-development/<skill>
            parts = Path(default_root).parts
            if "software-development" in parts:
                idx = parts.index("software-development")
                if idx + 1 < len(parts):
                    sk = parts[idx + 1]
                    if skill_script_exists(root, sk, name):
                        return True
            # or absolute-ish skill dir name as last component
            sk = Path(default_root).name
            if skill_script_exists(root, sk, name):
                return True
        for sk in list(skills) + ["dispatch-phase"]:
            if skill_script_exists(root, sk, name):
                return True
        return False

    if ref.startswith(".hermes/home/skills/software-development/"):
        # .hermes/home/skills/software-development/<skill>/scripts/<name>
        parts = Path(ref).parts
        try:
            i = parts.index("software-development")
            sk, name = parts[i + 1], parts[-1]
        except (ValueError, IndexError):
            return False
        return skill_script_exists(root, sk, name)

    if ref.startswith(".hermes/skills/") or ref.startswith(("migration/", "governance/", "evidence/")):
        return (root / ref).is_file()
    if ref.startswith(".hermes/home/scripts/"):
        return (root / ref).is_file()

    name = Path(ref).name
    home = root / ".hermes" / "home" / "scripts" / name
    if home.is_file():
        return True
    for sk in list(skills) + ["dispatch-phase"]:
        if skill_script_exists(root, sk, name):
            return True
    return False


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    yaml = root / ".hermes" / "phase-dispatch.yaml"
    # CS-7 / enforcement home (post skills→enforcement move). Fallback: legacy
    # skills/ path if a seat still carries the pre-move layout.
    candidates = (
        root / ".hermes" / "skills" / "harness" / "dispatch-phase" / "scripts" / "dispatch-phase.sh",
        root / ".hermes" / "enforcement" / "dispatch-phase" / "scripts" / "dispatch-phase.sh",
        root / ".hermes" / "skills" / "dispatch-phase" / "scripts" / "dispatch-phase.sh",
    )
    dispatch = next((c for c in candidates if c.is_file()), candidates[0])
    if not yaml.is_file() or not dispatch.is_file():
        print(
            "BODY_SCRIPT_LINT: missing phase-dispatch.yaml or dispatch-phase.sh "
            f"(looked under enforcement/ and skills/; yaml={yaml.is_file()} "
            f"dispatch={dispatch})",
            file=sys.stderr,
        )
        return 1
    phases = parse_phase_skills(yaml.read_text(encoding="utf-8"))
    bodies = extract_body_scripts(dispatch)
    holder = (
        root
        / ".hermes"
        / "skills"
        / "harness"
        / "dispatch-phase"
        / "references"
        / "holder-card-body.md"
    )
    if holder.is_file():
        hrefs = set(SCRIPT_REF.findall(holder.read_text(encoding="utf-8")))
        if hrefs:
            bodies.setdefault("M3", set()).update(hrefs)
    bad = 0
    for phase, refs in sorted(bodies.items()):
        skills = phases.get(phase) or []
        for ref in sorted(refs):
            if resolve_ok(root, phase, skills, ref):
                print(f"OK: {phase} → {ref}")
            else:
                print(
                    f"FAIL: {phase} body cites {ref!r} but not under attached "
                    f"skills {skills} (scaffold or runtime software-development root)",
                    file=sys.stderr,
                )
                bad = 1
    if bad:
        print("FAIL: phase body script refs (R0 / Deputy E-20260811T113300Z)", file=sys.stderr)
        return 1
    print("OK: phase body script refs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
