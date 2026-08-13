#!/usr/bin/env python3
"""CS-7 fail-closed: every skill listed in a bundle YAML must resolve.

Official bundles skip missing skills — FORBIDDEN under our doctrine.
"""
from __future__ import annotations

import argparse
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


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "CS-7 fail-closed: every skill listed in a tip skill-bundle MUST "
            "resolve under the skills root. Exit 0 when all resolve; exit 1 "
            "when any listed skill is missing."
        ),
        epilog="Exit codes: 0=pass, 1=missing skill(s) or usage error.",
    )
    ap.add_argument(
        "--root",
        default=".hermes/skills",
        help="skills root (default: .hermes/skills)",
    )
    ap.add_argument(
        "--bundles",
        default=None,
        help="bundles dir (default: <skills-parent>/home/skill-bundles)",
    )
    args = ap.parse_args()
    root = Path(args.root)
    bdir = (
        Path(args.bundles)
        if args.bundles is not None
        else root.parent / "home" / "skill-bundles"
    )
    if not bdir.is_dir():
        # Real-run idle message: avoid OK:/PASS: so --help lints stay clean if
        # argparse ever falls through; stderr keeps humans informed.
        print(f"idle: no bundles dir {bdir}", file=sys.stderr)
        print(f"BUNDLES=0 VIOLATIONS=0")
        return 0
    errs: list[str] = []
    ymls = sorted(bdir.glob("*.yaml"))
    for yml in ymls:
        for leaf in parse_skills(yml):
            if resolve(leaf, root) is None:
                errs.append(f"{yml.name}: missing skill '{leaf}'")
    for e in errs:
        print(e)
    print(f"BUNDLES={len(ymls)} VIOLATIONS={len(errs)}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
