#!/usr/bin/env python3
"""R-SK.5 conformance lint — AD-012 R-SK.1–4 + R-SK.7 (CS-9 vehicle).

Usage:
  check-skill-conformance.py <skill-dir> [<skill-dir>...]
  check-skill-conformance.py --all [--root DIR] [--flat-ok]

Exit: 0 all pass; 1 violations (printed SKILL:RULE:detail).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Architect amend E-20260812T104205Z — pair-as-category (no abstract patterns/)
CATEGORIES = {"analysis", "sdd", "gates", "harness", "spring-to-quarkus"}
ALLOWED_SUBDIRS = {"references", "templates", "scripts", "examples", "assets"}
REQ_SECTIONS = ["## When to Use", "## Procedure", "## Verification"]
OPT_SECTIONS = {"## Pitfalls", "## Example"}
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def frontmatter(text: str) -> str | None:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else None


def field(fm: str, key: str) -> str | None:
    m = re.search(rf"^[ \t]*{key}:\s*(.+)$", fm, re.M)
    return m.group(1).strip().strip("\"'") if m else None


def check(skill_dir: Path, flat_ok: bool) -> list[str]:
    errs: list[str] = []
    name = skill_dir.name
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return [f"{name}:R-SK.1:missing SKILL.md"]
    for child in skill_dir.iterdir():
        if child.name == "SKILL.md" or child.name.startswith("."):
            continue
        if child.is_dir() and child.name in ALLOWED_SUBDIRS:
            continue
        errs.append(
            f"{name}:R-SK.1:stray entry '{child.name}' "
            f"(allowed: SKILL.md + {sorted(ALLOWED_SUBDIRS)})"
        )
    text = md.read_text(encoding="utf-8")
    fm = frontmatter(text)
    if fm is None:
        return errs + [f"{name}:R-SK.2:no frontmatter"]
    if field(fm, "name") != name:
        errs.append(f"{name}:R-SK.2:name != leaf directory")
    desc = field(fm, "description") or ""
    if not desc:
        errs.append(f"{name}:R-SK.2:missing description")
    elif len(desc) > 60:
        errs.append(f"{name}:R-SK.2:description {len(desc)} chars (max 60)")
    ver = field(fm, "version") or ""
    if not SEMVER.match(ver):
        errs.append(f"{name}:R-SK.2:version '{ver}' not semver")
    for req in ("author", "license"):
        if not field(fm, req):
            errs.append(f"{name}:R-SK.2:missing {req}")
    if "metadata:" not in fm or "tags:" not in fm or "category:" not in fm:
        errs.append(f"{name}:R-SK.2:missing metadata.hermes.tags/category")
    cat = field(fm, "category")
    parent = skill_dir.parent.name
    if parent in CATEGORIES:
        if cat != parent:
            errs.append(
                f"{name}:R-SK.7:metadata category '{cat}' != directory '{parent}'"
            )
    elif not flat_ok:
        errs.append(
            f"{name}:R-SK.7:not under a category dir {sorted(CATEGORIES)}"
        )
    pos = -1
    for s in REQ_SECTIONS:
        p = text.find(s)
        if p < 0:
            errs.append(f"{name}:R-SK.3:missing '{s}'")
        elif p < pos:
            errs.append(f"{name}:R-SK.3:'{s}' out of order")
        else:
            pos = p
    if len(text.splitlines()) > 200:
        errs.append(
            f"{name}:R-SK.4:SKILL.md {len(text.splitlines())} lines "
            "(>200 — move depth to references/)"
        )
    return errs


def main() -> None:
    args = sys.argv[1:]
    flat_ok = "--flat-ok" in args
    args = [a for a in args if a != "--flat-ok"]
    if args and args[0] == "--all":
        root = (
            Path(args[args.index("--root") + 1])
            if "--root" in args
            else Path(".hermes/skills")
        )
        dirs = [p.parent for p in root.rglob("SKILL.md")]
    else:
        dirs = [Path(a) for a in args]
    if not dirs:
        print("usage: check-skill-conformance.py <skill-dir>|--all [--root DIR] [--flat-ok]", file=sys.stderr)
        sys.exit(2)
    all_errs: list[str] = []
    for d in dirs:
        all_errs += check(d, flat_ok)
    for e in all_errs:
        print(e)
    print(f"CHECKED={len(dirs)} VIOLATIONS={len(all_errs)}")
    sys.exit(1 if all_errs else 0)


if __name__ == "__main__":
    main()
