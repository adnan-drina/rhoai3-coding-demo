#!/usr/bin/env python3
"""CS-7 fail-closed: every skill listed in a tip skill-bundle MUST resolve.

Official Hermes skips missing bundle skills — FORBIDDEN under our doctrine
(Architect E-20260812T064637Z). Pre-dispatch / validate-contracts must REFUSE
when any bundle-listed skill lacks `.hermes/skills/<name>/SKILL.md`.

Usage:
  assert-bundle-skills-exist.py <root> [--bundle m3-implementer]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def parse_skills(path: Path) -> tuple[str, list[str]]:
    text = path.read_text(encoding="utf-8")
    name = path.stem
    skills: list[str] = []
    in_skills = False
    for ln in text.splitlines():
        m = re.match(r"^name:\s*(.+)$", ln)
        if m:
            name = m.group(1).strip().strip("\"'")
        if re.match(r"^skills:\s*$", ln):
            in_skills = True
            continue
        if in_skills:
            sm = re.match(r"^- (\S+)\s*$", ln)
            if sm:
                skills.append(sm.group(1))
                continue
            if ln.strip() and not ln.startswith("- "):
                in_skills = False
    return name, skills


def resolve_skill_md(skills_root: Path, leaf: str) -> Path:
    """Resolve <leaf>/SKILL.md under the R-SK.7 category tree.

    Skills live at `.hermes/skills/<category>/<leaf>/SKILL.md`. Bundles list
    bare leaf names (that is the attach identifier), so resolution must search
    the category dirs. The pre-category flat layout is still accepted so an
    older seat does not hard-fail on layout alone.
    """
    flat = skills_root / leaf / "SKILL.md"
    if flat.is_file():
        return flat
    hits = sorted(skills_root.glob(f"*/{leaf}/SKILL.md"))
    return hits[0] if hits else flat


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--bundle", action="append", default=[])
    args = ap.parse_args()
    root = Path(args.root).resolve()
    bdir = root / ".hermes" / "home" / "skill-bundles"
    skills_root = root / ".hermes" / "skills"
    if not bdir.is_dir():
        print(f"FAIL: missing bundles dir {bdir}", file=sys.stderr)
        return 1
    paths = sorted(bdir.glob("*.yaml"))
    if args.bundle:
        want = set(args.bundle)
        paths = [p for p in paths if p.stem in want]
        missing_named = want - {p.stem for p in paths}
        if missing_named:
            print(
                f"FAIL: bundle yaml missing for {sorted(missing_named)}",
                file=sys.stderr,
            )
            return 1
    if not paths:
        print(f"FAIL: no bundle yaml under {bdir}", file=sys.stderr)
        return 1

    bad = 0
    for path in paths:
        name, skills = parse_skills(path)
        if not skills:
            print(f"FAIL: bundle {name} has empty skills[]", file=sys.stderr)
            bad = 1
            continue
        for sk in skills:
            skill_md = resolve_skill_md(skills_root, sk)
            if not skill_md.is_file():
                print(
                    f"FAIL: bundle {name} lists skill `{sk}` but "
                    f"{skill_md.relative_to(root)} missing (CS-7 fail-closed)",
                    file=sys.stderr,
                )
                bad = 1
            else:
                print(f"OK: bundle {name} → skill `{sk}` resolves")
    if bad:
        return 1
    print(f"OK: bundle exists-assert PASS ({len(paths)} bundle(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
