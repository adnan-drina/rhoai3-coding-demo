#!/usr/bin/env python3
"""B3 — refuse kanban create when declared skills intersect skills.disabled.

Create-time gate (Architect E-20260818T144100Z / BIND 25a7c1e9). HARD
regardless of I-10 B. Path-invoke still works; declaring a disabled name
on a card is the defect (`Unknown skill(s)`).

B3: declared skills not in skills.disabled ⇒ refuse (exit 1).

The ruled five always refuse. HERMES_HOME/config.yaml may add names; it
cannot undisable the five.

Usage:
  python3 assert-skills-not-disabled.py [root] [--skill NAME ...]
  python3 assert-skills-not-disabled.py [root] --from-phase M2
  python3 assert-skills-not-disabled.py --help
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

CANONICAL_DISABLED = (
    "dispatch-phase",
    "enforce-authority-boundary",
    "ground-in-harvest",
    "record-run-evidence",
    "validate-contracts",
)

PHASE_KEY = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
SKILL_ITEM = re.compile(r"^      -\s+(\S+)\s*$")


def _disabled_from_text(text: str) -> list[str]:
    names: list[str] = []
    in_skills = False
    in_disabled = False
    for ln in text.splitlines():
        if re.match(r"^skills:\s*$", ln):
            in_skills = True
            continue
        if in_skills and re.match(r"^  disabled:\s*$", ln):
            in_disabled = True
            continue
        if in_disabled:
            sm = re.match(r"^    -\s+(\S+)\s*$", ln)
            if sm:
                names.append(sm.group(1))
                continue
            break
        if in_skills and ln and not ln.startswith((" ", "\t")):
            break
    return names


def load_disabled(root: Path, config: str) -> set[str]:
    names = set(CANONICAL_DISABLED)
    candidates: list[Path] = []
    if config:
        candidates.append(Path(config))
    home = os.environ.get("HERMES_HOME", "").strip()
    if home:
        candidates.append(Path(home) / "config.yaml")
    candidates.append(root / ".hermes" / "home" / "config.yaml")
    for path in candidates:
        try:
            if path.is_file():
                names.update(_disabled_from_text(path.read_text(encoding="utf-8")))
                break
        except OSError:
            continue
    return names


def skills_from_phase(root: Path, phase: str) -> list[str]:
    yaml_path = root / ".hermes" / "phase-dispatch.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    in_phases = False
    in_phase = False
    skills: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if re.match(r"^phases:\s*$", ln):
            in_phases = True
            i += 1
            continue
        m = PHASE_KEY.match(ln)
        if in_phases and m:
            in_phase = m.group(1) == phase
            i += 1
            continue
        if in_phase:
            if PHASE_KEY.match(ln):
                break
            if re.match(r"^    skills:\s*$", ln):
                i += 1
                while i < len(lines):
                    sm = SKILL_ITEM.match(lines[i])
                    if not sm:
                        break
                    skills.append(sm.group(1))
                    i += 1
                continue
        i += 1
    return skills


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Refuse when declared --skill names intersect skills.disabled "
            "(canonical five plus HERMES_HOME config). Create-time B3 gate."
        )
    )
    p.add_argument("root", nargs="?", default=".", help="scaffold/dest root")
    p.add_argument(
        "--skill",
        action="append",
        default=[],
        help="declared skill (repeatable)",
    )
    p.add_argument(
        "--from-phase",
        default="",
        help="also load skills[] from .hermes/phase-dispatch.yaml",
    )
    p.add_argument("--config", default="", help="HERMES_HOME/config.yaml path")
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    declared: list[str] = []
    seen: set[str] = set()
    for name in args.skill:
        n = str(name or "").strip()
        if n and n not in seen:
            seen.add(n)
            declared.append(n)
    if args.from_phase.strip():
        for name in skills_from_phase(root, args.from_phase.strip()):
            if name not in seen:
                seen.add(name)
                declared.append(name)
    disabled = load_disabled(root, args.config)
    hit = [n for n in declared if n in disabled]
    if hit:
        print(
            "FAIL: declared skills in skills.disabled: " + ", ".join(hit),
            file=sys.stderr,
        )
        return 1
    print(
        "assert-skills-not-disabled: declared disjoint from disabled "
        f"n={len(declared)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
