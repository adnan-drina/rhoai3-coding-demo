#!/usr/bin/env python3
"""R-SK.5 / R-SK.9 conformance lint — AD-012 (CS-9 vehicle).

Usage:
  check-skill-conformance.py <skill-dir> [<skill-dir>...]
  check-skill-conformance.py --all [--root DIR] [--flat-ok] [--skip-r-sk9]

Exit: 0 all pass; 1 violations (printed SKILL:RULE:detail).

R-SK.9 (Architect E-20260812T190021Z): golden skills under a scaffold
`.hermes/skills` root must be card-attachable OR script/contract-invoked OR
provision-invoked (devfile/postStart). Optional Architect KEEP allowlist:
  <scaffold>/.hermes/skills/harness-validate/references/r-sk9-architect-keep.txt
  (one skill leaf name per line; `#` comments; cite EID in trailing comment).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Architect ratify E-20260812T104706Z — fixed five (migration/ fifth; not pair-named)
CATEGORIES = {"analysis", "sdd", "gates", "harness", "migration"}
ALLOWED_SUBDIRS = {"references", "templates", "scripts", "examples", "assets"}
REQ_SECTIONS = ["## When to Use", "## Procedure", "## Verification"]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
SKILL_LIST_ITEM = re.compile(r"^\s*-\s+([A-Za-z0-9][A-Za-z0-9_-]*)\s*$")
# First segment after skills/, or second when under an R-SK.7 category dir.
PATH_SKILL = re.compile(
    r"(?:\.hermes/)?skills/(?:(analysis|sdd|gates|harness|migration)/)?"
    r"([A-Za-z0-9_-]+)(?:/|\.md|\b)"
)


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


def scaffold_root_from_skills(skills_root: Path) -> Path | None:
    skills_root = skills_root.resolve()
    if skills_root.name == "skills" and skills_root.parent.name == ".hermes":
        return skills_root.parent.parent
    return None


def load_architect_keep(scaffold: Path) -> set[str]:
    keep: set[str] = set()
    candidates = [
        scaffold
        / ".hermes/skills/harness-validate/references/r-sk9-architect-keep.txt",
        scaffold / ".hermes/r-sk9-architect-keep.txt",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        for ln in path.read_text(encoding="utf-8").splitlines():
            s = ln.split("#", 1)[0].strip()
            if s:
                keep.add(s)
    return keep


def collect_attach_names(scaffold: Path) -> set[str]:
    """Collect leaf names from phase-dispatch `skills:` / `skills_by_role:` lists only."""
    names: set[str] = set()
    pd = scaffold / ".hermes/phase-dispatch.yaml"
    if not pd.is_file():
        return names
    in_skills = False
    skills_indent: int | None = None
    for ln in pd.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        indent = len(ln) - len(ln.lstrip(" "))
        m_key = re.match(r"^(\s*)(skills|skills_by_role)\s*:\s*$", ln)
        if m_key:
            in_skills = True
            skills_indent = len(m_key.group(1))
            continue
        if in_skills:
            if skills_indent is not None and indent <= skills_indent:
                in_skills = False
                skills_indent = None
                # fall through — this line may start another key
            else:
                # role map keys under skills_by_role (e.g. "      planner:")
                if re.match(r"^\s+[A-Za-z0-9_-]+\s*:\s*$", ln):
                    continue
                m = SKILL_LIST_ITEM.match(ln)
                if m:
                    names.add(m.group(1))
                continue
        # re-check if this line opens a skills block after close
        m_key = re.match(r"^(\s*)(skills|skills_by_role)\s*:\s*$", ln)
        if m_key:
            in_skills = True
            skills_indent = len(m_key.group(1))
    return names


def collect_path_invoked_names(scaffold: Path) -> set[str]:
    """Script / contract / provision invocations via path mentions."""
    names: set[str] = set()
    scan_roots = [
        scaffold / ".hermes",
        scaffold / "migration" / "contracts",
        scaffold / "AGENTS.md",
        scaffold / "devfile.yaml",
    ]
    files: list[Path] = []
    for root in scan_roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                rel = str(p.relative_to(scaffold))
                if rel.startswith(".hermes/home/") and p.suffix not in {
                    ".yaml",
                    ".yml",
                }:
                    continue
                if p.suffix in {
                    ".sh",
                    ".py",
                    ".yaml",
                    ".yml",
                    ".md",
                    ".json",
                } or p.name in {"devfile.yaml", "Devfile.yaml"}:
                    files.append(p)
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in PATH_SKILL.finditer(text):
            leaf = m.group(2)
            if leaf in {"scripts", "references", "templates", "examples", "assets"}:
                continue
            names.add(leaf)
    return names


def check_r_sk9(skills_root: Path, skill_dirs: list[Path]) -> list[str]:
    scaffold = scaffold_root_from_skills(skills_root)
    if scaffold is None:
        return []
    attach = collect_attach_names(scaffold)
    invoked = collect_path_invoked_names(scaffold)
    keep = load_architect_keep(scaffold)
    admitted = attach | invoked | keep
    errs: list[str] = []
    for d in skill_dirs:
        name = d.name
        if name in admitted:
            continue
        errs.append(
            f"{name}:R-SK.9:not attach/script/provision-invoked "
            f"(and not Architect-KEEP); remove from golden or cite keep-list "
            f"(E-20260812T190021Z)"
        )
    return errs


def main() -> None:
    args = sys.argv[1:]
    flat_ok = "--flat-ok" in args
    skip_r_sk9 = "--skip-r-sk9" in args
    args = [a for a in args if a not in {"--flat-ok", "--skip-r-sk9"}]
    skills_root: Path | None = None
    if args and args[0] == "--all":
        root = (
            Path(args[args.index("--root") + 1])
            if "--root" in args
            else Path(".hermes/skills")
        )
        skills_root = root
        dirs = [p.parent for p in root.rglob("SKILL.md")]
    else:
        dirs = [Path(a) for a in args]
    if not dirs:
        print(
            "usage: check-skill-conformance.py <skill-dir>|--all "
            "[--root DIR] [--flat-ok] [--skip-r-sk9]",
            file=sys.stderr,
        )
        sys.exit(2)
    all_errs: list[str] = []
    for d in dirs:
        all_errs += check(d, flat_ok)
    if skills_root is not None and not skip_r_sk9:
        all_errs += check_r_sk9(skills_root, dirs)
    for e in all_errs:
        print(e)
    print(f"CHECKED={len(dirs)} VIOLATIONS={len(all_errs)}")
    sys.exit(1 if all_errs else 0)


if __name__ == "__main__":
    main()
