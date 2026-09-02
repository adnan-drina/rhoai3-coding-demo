#!/usr/bin/env python3
"""Validate skills against the agentskills.io specification.

Checks the constraints from https://agentskills.io/specification:
  name         required, <=64 chars, lowercase alnum + single hyphens,
               no leading/trailing hyphen, must match the directory name
  description  required, non-empty, <=1024 characters
  SKILL.md     recommended <500 lines (progressive-disclosure target)
  layout       SKILL.md present; reference files one level deep

Usage:
  validate-skills.py [PATH ...]     # skill dirs, or dirs of skill dirs
  validate-skills.py --all          # every skill under .agents/skills/

Exit: 0 clean, 1 violations found (warnings alone do not fail).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DESC_MAX = 1024
NAME_MAX = 64
LINES_TARGET = 500


def frontmatter(text: str) -> str | None:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else None


def field(fm: str, key: str) -> str:
    """Return a scalar or folded/literal block value, whitespace-collapsed."""
    m = re.search(rf"^{key}:\s*([>|][-+]?)?\s*(.*)$", fm, re.M)
    if not m:
        return ""
    if not m.group(1):
        return m.group(2).strip().strip("\"'")
    start = m.end()
    block = []
    for line in fm[start:].splitlines():
        if line.strip() and not line.startswith((" ", "\t")):
            break
        block.append(line.strip())
    return " ".join(" ".join(block).split())


def check(skill: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    md = skill / "SKILL.md"
    if not md.is_file():
        return [f"{skill.name}: no SKILL.md"], []

    text = md.read_text(encoding="utf-8")
    fm = frontmatter(text)
    if fm is None:
        return [f"{skill.name}: no YAML frontmatter"], []

    name = field(fm, "name")
    if not name:
        errors.append(f"{skill.name}: missing required field 'name'")
    else:
        if name != skill.name:
            errors.append(f"{skill.name}: name '{name}' != directory name")
        if len(name) > NAME_MAX:
            errors.append(f"{skill.name}: name {len(name)} chars > {NAME_MAX}")
        if not NAME_RE.fullmatch(name):
            errors.append(
                f"{skill.name}: name '{name}' violates pattern "
                "(lowercase alphanumerics, single hyphens, no leading/trailing)"
            )

    desc = field(fm, "description")
    if not desc:
        errors.append(f"{skill.name}: missing or empty required field 'description'")
    elif len(desc) > DESC_MAX:
        errors.append(f"{skill.name}: description {len(desc)} chars > {DESC_MAX}")

    lines = len(text.splitlines())
    if lines > LINES_TARGET:
        warnings.append(
            f"{skill.name}: SKILL.md {lines} lines > {LINES_TARGET} target "
            "(move depth into references/)"
        )

    for sub in ("references", "scripts", "assets", "templates", "examples"):
        d = skill / sub
        if d.is_dir():
            for nested in d.iterdir():
                if nested.is_dir():
                    warnings.append(
                        f"{skill.name}: {sub}/{nested.name}/ is nested deeper than "
                        "one level from SKILL.md"
                    )
    return errors, warnings


def collect(paths: list[Path]) -> list[Path]:
    skills: list[Path] = []
    for p in paths:
        if (p / "SKILL.md").is_file():
            skills.append(p)
        else:
            skills.extend(sorted(c.parent for c in p.glob("*/SKILL.md")))
    return skills


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--all"]
    paths = [Path(a) for a in args] or [Path(".agents/skills")]
    skills = collect(paths)
    if not skills:
        print("no skills found", file=sys.stderr)
        sys.exit(2)

    errors: list[str] = []
    warnings: list[str] = []
    for s in skills:
        e, w = check(s)
        errors += e
        warnings += w

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\nchecked={len(skills)} errors={len(errors)} warnings={len(warnings)}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
