#!/usr/bin/env python3
"""CS-7 fail-closed: every skill listed in a bundle YAML must resolve.

Official bundles skip missing skills — FORBIDDEN under our doctrine.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def parse_skills(path: Path) -> list[str]:
    skills: list[str] = []
    in_skills = False
    for ln in path.read_text(encoding="utf-8").splitlines():
        if re.match(r"^skills:\s*$", ln):
            in_skills = True
            continue
        if in_skills:
            sm = re.match(r"^- (\S+)\s*$", ln)
            if sm:
                skills.append(sm.group(1))
                continue
            if ln.strip() and not ln.startswith(" ") and not ln.startswith("-"):
                in_skills = False
    return skills


def resolve(leaf: str, root: Path) -> Path | None:
    flat = root / leaf / "SKILL.md"
    if flat.is_file():
        return flat.parent
    for hit in root.rglob("SKILL.md"):
        if hit.parent.name == leaf:
            return hit.parent
    return None


def main() -> None:
    args = sys.argv[1:]
    root = Path(".hermes/skills")
    if "--root" in args:
        root = Path(args[args.index("--root") + 1])
    bdir = root.parent / "home" / "skill-bundles"
    if "--bundles" in args:
        bdir = Path(args[args.index("--bundles") + 1])
    if not bdir.is_dir():
        print(f"OK: no bundles dir {bdir}")
        sys.exit(0)
    errs: list[str] = []
    for yml in sorted(bdir.glob("*.yaml")):
        for leaf in parse_skills(yml):
            if resolve(leaf, root) is None:
                errs.append(f"{yml.name}: missing skill '{leaf}'")
    for e in errs:
        print(e)
    print(f"BUNDLES={len(list(bdir.glob('*.yaml')))} VIOLATIONS={len(errs)}")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
