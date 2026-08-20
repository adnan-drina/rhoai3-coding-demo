#!/usr/bin/env python3
"""R-SK.5 / R-SK.9 conformance lint — AD-012 (CS-9 vehicle).

Usage:
  check-skill-conformance.py <skill-dir> [<skill-dir>...]
  check-skill-conformance.py --all [--root DIR] [--flat-ok] [--skip-r-sk9] [--skip-specimen]

Exit: 0 all pass; 1 violations (printed SKILL:RULE:detail).

R-SK.5 specimen literals (Operator E-20260813T075411Z / Deputy E-20260813T122115Z):
  under --all, scan skills SKILL.md+references/templates and governance/contracts
  for petclinic/package/entity path literals unless Architect KEEP listed in
  references/r-sk5-specimen-keep.txt.

R-SK.9 (Architect E-20260812T190021Z): golden skills under a scaffold
`.hermes/skills` root must be card-attachable OR script/contract-invoked OR
provision-invoked (devfile/postStart). Optional Architect KEEP allowlist:
  <scaffold>/.hermes/skills/validate-contracts/references/r-sk9-architect-keep.txt
  (one skill leaf name per line; `#` comments; cite EID in trailing comment).
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

# Architect ratify E-20260812T104706Z — four guidance categories plus harness
# (EX-3: former .hermes/enforcement/ packs live under skills/harness/).
CATEGORIES = {"analysis", "sdd", "gates", "migration", "harness"}

# R-SK.10 — skill naming (AD-013 official-first + house pattern).
# Spec MUSTs (agentskills.io): charset a-z0-9-; ≤64; no edge/consecutive
# hyphens; name == directory; reserved words prohibited.
# House pattern (Architect A7 / Deputy E-20260813T140501Z): imperative
# verb-object, applied consistently. Gerund is Anthropic "Consider using",
# NOT a MUST — and imperative is an explicit acceptable alternative.
# Do not fail on non-gerund; the mint-boundary rename (t_4dc3ea97) brings
# leaves onto the house pattern. r-sk10-name-keep.txt holds N3 pair skills
# and other Architect-justified exceptions to N1/N2.
NAME_MAX = 64
NAME_CHARSET_RX = re.compile(r"^[a-z0-9-]+$")
NAME_RESERVED = {"anthropic", "claude"}
# Official description budget (skills spec allows up to 1024). The former
# 60-char house cap forced title-restating descriptions and actively fought
# the selection signal progressive disclosure depends on — raised, not removed.
DESC_MAX = 1024


def load_name_keep(root):
    """Architect-justified N1/N2 exception leaf names (R-SK.10 KEEP list)."""
    keep = set()
    here = Path(__file__).resolve().parent.parent / "references" / "r-sk10-name-keep.txt"
    for cand in (
        here,
        root / "harness" / "validate-contracts" / "references" / "r-sk10-name-keep.txt",
        root / "validate-contracts" / "references" / "r-sk10-name-keep.txt",
    ):
        if cand.is_file():
            for line in cand.read_text(encoding="utf-8").splitlines():
                line = line.split("#", 1)[0].strip()
                if line:
                    keep.add(line)
            break
    return keep


NAME_KEEP = set()

# R-SK.11 — OFFICIAL Agent Skills spec frontmatter (agentskills.io/specification).
# The spec defines exactly these frontmatter fields. Anything else belongs
# inside `metadata` (the spec's own example carries author/version there).
SPEC_FIELDS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}
COMPAT_MAX = 500
# Spec: "Keep your main SKILL.md under 500 lines" (progressive disclosure).
SKILL_MAX_LINES = 500
# Best practice: a description must say what the skill does AND when to use it.
WHEN_RX = re.compile(r"\b(when|before|after|during|use it|if )\b", re.I)


def check_spec_frontmatter(name, fm, text):
    """R-SK.11 official spec conformance for frontmatter + body budget."""
    errs = []
    top = []
    for line in fm.splitlines():
        m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):", line)
        if m:
            top.append(m.group(1))
    for key in top:
        if key not in SPEC_FIELDS:
            errs.append(
                f"{name}:R-SK.11:non-spec frontmatter field '{key}' — official "
                f"fields are {sorted(SPEC_FIELDS)}; move the rest under metadata"
            )
    # metadata: the spec calls for string values but explicitly blesses
    # client-specific extension under uniquely-named keys. Hermes documents
    # `metadata.hermes.{tags, category, ...}` as its own namespace, so a single
    # vendor-namespaced nested block is conformant-by-intent and stays. Only
    # flag a bare list directly under metadata, which no client can consume.
    mblock = re.search(r"^metadata:\s*$(.*?)(?=^\S|\Z)", fm + "\n", re.M | re.S)
    if mblock:
        for line in mblock.group(1).splitlines():
            if re.match(r"^\s{2}-\s", line):
                errs.append(
                    f"{name}:R-SK.11:metadata holds a bare list — spec requires "
                    f"a map of string keys to string values"
                )
                break
    compat = field(fm, "compatibility") or ""
    if compat and len(compat) > COMPAT_MAX:
        errs.append(f"{name}:R-SK.11:compatibility {len(compat)} chars (max {COMPAT_MAX})")
    nlines = len(text.splitlines())
    if nlines > SKILL_MAX_LINES:
        errs.append(
            f"{name}:R-SK.11:SKILL.md {nlines} lines (spec recommends < "
            f"{SKILL_MAX_LINES}) — move detail into references/"
        )
    desc = field(fm, "description") or ""
    if desc and not WHEN_RX.search(desc):
        errs.append(
            f"{name}:R-SK.11:description states what but not WHEN to use it — "
            f"official guidance requires both"
        )
    return errs


def check_name_rules(name):
    """R-SK.10 naming rules (spec MUSTs). Returns a list of violation strings."""
    errs = []
    if len(name) > NAME_MAX:
        errs.append(f"{name}:R-SK.10:name {len(name)} chars (max {NAME_MAX})")
    if not NAME_CHARSET_RX.match(name):
        errs.append(f"{name}:R-SK.10:charset — lowercase a-z, 0-9, '-' only")
    if name.startswith("-") or name.endswith("-"):
        errs.append(f"{name}:R-SK.10:must not start or end with a hyphen")
    if "--" in name:
        errs.append(f"{name}:R-SK.10:consecutive hyphens")
    for word in NAME_RESERVED:
        if word in name:
            errs.append(f"{name}:R-SK.10:reserved word '{word}'")
    # Gerund is NOT enforced (E-20260813T140501Z). House imperative consistency
    # is delivered by the rename mapping in skill-naming-convention.md.
    return errs
ALLOWED_SUBDIRS = {"references", "templates", "scripts", "examples", "assets", "fixtures"}
# House rule §K (Operator/Deputy E-20260814T104744Z): sole selection heading is
# ## When to Use (not ## Required When). Pitfalls sit after Procedure.
REQ_SECTIONS = [
    "## When to Use",
    "## Procedure",
    "## Pitfalls",
    "## Verification",
]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
SKILL_LIST_ITEM = re.compile(r"^\s*-\s+([A-Za-z0-9][A-Za-z0-9_-]*)\s*$")
# Guidance and harness packs under skills/<category>/leaf (EX-3: no enforcement/).
PATH_SKILL = re.compile(
    r"(?:\.hermes/)?(?:skills/(?:(analysis|sdd|gates|migration|harness)/)?)"
    r"([A-Za-z0-9_-]+)(?:/|\.md|\b)"
)


def frontmatter(text: str) -> str | None:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else None


def field(fm: str, key: str) -> str | None:
    m = re.search(rf"^[ \t]*{key}:\s*(.+)$", fm, re.M)
    return m.group(1).strip().strip("\"'") if m else None


R_SK4_NOTICES: list[str] = []


def load_r_sk4_exceptions(start: Path) -> dict[str, date]:
    """Leaf → expiry. Missing or expired entries are not exceptions."""
    found: Path | None = None
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent
    for parent in [cur, *cur.parents]:
        cand = (
            parent
            / ".hermes"
            / "skills"
            / "harness"
            / "validate-contracts"
            / "references"
            / "r-sk4-line-exceptions.txt"
        )
        if cand.is_file():
            found = cand
            break
        cand = parent / "references" / "r-sk4-line-exceptions.txt"
        if cand.is_file() and parent.name == "validate-contracts":
            found = cand
            break
    if found is None:
        return {}
    out: dict[str, date] = {}
    for ln in found.read_text(encoding="utf-8").splitlines():
        s = ln.split("#", 1)[0].strip()
        if not s:
            continue
        parts = s.split()
        if len(parts) < 2:
            continue
        name, raw = parts[0], parts[1]
        try:
            y, m, d = (int(x) for x in raw.split("-", 2))
            out[name] = date(y, m, d)
        except ValueError:
            continue
    return out


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
    errs.extend(check_name_rules(name))
    errs.extend(check_spec_frontmatter(name, fm, text))
    desc = field(fm, "description") or ""
    if not desc:
        errs.append(f"{name}:R-SK.2:missing description")
    elif len(desc) > DESC_MAX:
        errs.append(f"{name}:R-SK.2:description {len(desc)} chars (max {DESC_MAX})")
    ver = field(fm, "version") or ""
    if not SEMVER.match(ver):
        errs.append(f"{name}:R-SK.2:version '{ver}' not semver")
    for req in ("author", "license"):
        if not field(fm, req):
            errs.append(f"{name}:R-SK.2:missing {req}")
    if "metadata:" not in fm or "tags:" not in fm or "category:" not in fm:
        errs.append(f"{name}:R-SK.2:missing metadata.hermes.tags/category")
    # R-SK.14 Slice A — Architect E-20260813T145219Z / E-20260813T152211Z
    kind = field(fm, "kind")
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
    if kind not in {"guidance", "enforcement"}:
        errs.append(
            f"{name}:R-SK.14:metadata.hermes.kind must be "
            f"'guidance' or 'enforcement' (got {kind!r})"
        )
    if "## Required When" in text:
        errs.append(
            f"{name}:R-SK.3:use '## When to Use' not '## Required When' "
            f"(house rule §K)"
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
    nlines = len(text.splitlines())
    if nlines > 200:
        exceptions = load_r_sk4_exceptions(skill_dir)
        exp = exceptions.get(name)
        if exp is not None and date.today() <= exp:
            R_SK4_NOTICES.append(
                f"OK: {name}:R-SK.4 accepted exception {nlines} lines "
                f"(expires {exp.isoformat()})"
            )
        else:
            extra = ""
            if exp is not None:
                extra = f" (exception expired {exp.isoformat()})"
            errs.append(
                f"{name}:R-SK.4:SKILL.md {nlines} lines "
                f"(>200 — move depth to references/){extra}"
            )
    return errs


def scaffold_root_from_skills(skills_root: Path) -> Path | None:
    skills_root = skills_root.resolve()
    if skills_root.parent.name == ".hermes" and skills_root.name == "skills":
        return skills_root.parent.parent
    return None


def load_architect_keep(scaffold: Path) -> set[str]:
    keep: set[str] = set()
    candidates = [
        scaffold
        / ".hermes/skills/harness/validate-contracts/references/r-sk9-architect-keep.txt",
        scaffold
        / ".hermes/skills/validate-contracts/references/r-sk9-architect-keep.txt",
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
    """Collect leaf names from dispatch-phase `skills:` / `skills_by_role:` lists only."""
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
        scaffold / "governance" / "contracts",
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


# R-SK.5 specimen-literal choke-point (Operator E-20260813T075411Z /
# Deputy E-20260813T122115Z). Guidance under skills references + migration
# contracts must stay specimen-agnostic; Architect KEEP lines may cite EID.
# 2026-08-13: spaced Owner/Pet + enforcement/src scan (Deputy false-zero unpark).
SPECIMEN_LITERAL_RX = [
    re.compile(r"org\.springframework\.samples\.petclinic"),
    # Allow optional whitespace around / or unicode/ASCII arrows (was \bOwner/Pet\b
    # which missed "Owner / Pet" in S-008 contract — false green).
    re.compile(r"\bOwner\s*(?:/|→|->)\s*Pet\b"),
    re.compile(r"(?i)\bpetclinic\b"),
    re.compile(r"/owners/\{[^}]*\}/pets"),
    # Derived reference-app type names (Deputy E-20260813T144954Z P2)
    re.compile(r"\bClinicService\b"),
]


def load_specimen_keep(scaffold: Path) -> set[str]:
    """Allowlist entries: 'relpath:lineno' or 'relpath' (whole file)."""
    keep: set[str] = set()
    path = (
        scaffold
        / ".hermes/skills/harness/validate-contracts/references"
        / "r-sk5-specimen-keep.txt"
    )
    if not path.is_file():
        # flat layout fallback
        path = (
            scaffold
            / ".hermes/skills/validate-contracts/references"
            / "r-sk5-specimen-keep.txt"
        )
    if not path.is_file():
        return keep
    for ln in path.read_text(encoding="utf-8").splitlines():
        s = ln.split("#", 1)[0].strip()
        if s:
            keep.add(s)
    return keep


def _append_tree(
    scan: list[Path],
    root: Path,
    *,
    suffixes: set[str],
    skip_parts: frozenset[str] = frozenset({"__pycache__", "examples", "assets"}),
) -> None:
    if not root.is_dir():
        return
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix not in suffixes:
            continue
        if any(x in p.parts for x in skip_parts):
            continue
        scan.append(p)


def check_specimen_literals(scaffold: Path) -> list[str]:
    errs: list[str] = []
    keep = load_specimen_keep(scaffold)
    scan: list[Path] = []
    skills = scaffold / ".hermes" / "skills"
    if skills.is_dir():
        for p in skills.rglob("*"):
            if not p.is_file() or p.suffix not in {".md", ".txt", ".yaml", ".yml"}:
                continue
            rel_parts = p.relative_to(skills).parts
            if any(x in rel_parts for x in ("examples", "assets")):
                continue
            # SKILL.md + references/ (+ templates) only
            if p.name == "SKILL.md" or "references" in rel_parts or "templates" in rel_parts:
                scan.append(p)
    # R-SK.5 extension: gate LOGIC must be specimen-agnostic too. A hardcoded
    # specimen package in a gate is worse than one in prose — the gate silently
    # matches nothing on any other codebase and passes vacuously (found in
    # assert-dependency-closure.py, Deputy E-20260813T125813Z audit).
    if skills.is_dir():
        for p in skills.rglob("*"):
            if not p.is_file() or p.suffix not in {".py", ".sh"}:
                continue
            if "__pycache__" in p.parts:
                continue
            scan.append(p)
    contracts = scaffold / "governance" / "contracts"
    if contracts.is_dir():
        scan.extend(
            p
            for p in contracts.rglob("*")
            if p.is_file() and p.suffix in {".md", ".txt", ".yaml", ".yml"}
        )
    # R-SK.5 P2 — also scan Java fixtures (Deputy E-20260813T144954Z)
    fixtures = scaffold / "governance" / "fixtures"
    if fixtures.is_dir():
        scan.extend(
            p
            for p in fixtures.rglob("*")
            if p.is_file() and p.suffix in {".java", ".md", ".txt", ".yaml", ".yml"}
        )
    # Product/source tree when present (skeleton may be absent post-bootstrap)
    _append_tree(
        scan,
        scaffold / "src",
        suffixes={".java", ".kt", ".properties", ".yml", ".yaml", ".md", ".txt"},
    )
    # R-SK.5 P3 — root migration.yaml is the load-bearing specimen descriptor
    # (Deputy E-20260813T184217Z). Golden must stay empty/fake; scanning it
    # closes the third false-zero hole (after src/ and .java fixtures).
    # Stamped seats (app-migration template) intentionally carry specimen
    # contracts — out of R-SK.5 scope (specimen-layering; not Architect KEEP).
    def _migration_is_stamped(path: Path) -> bool:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        if "provisionedBy: app-migration" in raw:
            return True
        for ln in raw.splitlines():
            s = ln.split("#", 1)[0].strip()
            if s.startswith("legacyRepoUrl:"):
                val = s.split(":", 1)[1].strip().strip("'\"")
                if val:
                    return True
        return False

    for name in ("migration.yaml", "migration.yml"):
        mig = scaffold / name
        if mig.is_file() and not _migration_is_stamped(mig):
            scan.append(mig)
    for p in scan:
        try:
            rel = str(p.relative_to(scaffold)).replace("\\", "/")
        except ValueError:
            continue
        if rel in keep:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            key = f"{rel}:{i}"
            if key in keep or rel in keep:
                continue
            for rx in SPECIMEN_LITERAL_RX:
                m = rx.search(line)
                if m:
                    errs.append(
                        f"specimen:R-SK.5:{rel}:{i}:literal {m.group(0)!r} "
                        f"(specimen-agnostic law; Architect KEEP via "
                        f"r-sk5-specimen-keep.txt)"
                    )
                    break
    return errs


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "R-SK.5 / R-SK.9 / R-SK.10 / R-SK.11 skill conformance lint. "
            "Exit 0 all pass; exit 1 violations."
        ),
        epilog="Exit codes: 0=pass, 1=violations, 2=usage.",
    )
    ap.add_argument(
        "skills",
        nargs="*",
        help="skill directories (omit when using --all)",
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="scan every SKILL.md under --root",
    )
    ap.add_argument(
        "--root",
        default=".hermes/skills",
        help="skills root for --all (default: .hermes/skills)",
    )
    ap.add_argument("--flat-ok", action="store_true")
    ap.add_argument("--skip-r-sk9", action="store_true")
    ap.add_argument("--skip-specimen", action="store_true")
    args = ap.parse_args()

    skills_root: Path | None = None
    if args.all:
        skills_root = Path(args.root)
        dirs = [p.parent for p in skills_root.rglob("SKILL.md")]
    else:
        dirs = [Path(a) for a in args.skills]
    if not dirs:
        ap.error("provide skill dirs or --all")
    # de-dupe while preserving order
    seen: set[Path] = set()
    uniq: list[Path] = []
    for d in dirs:
        r = d.resolve()
        if r not in seen:
            seen.add(r)
            uniq.append(d)
    dirs = uniq
    global NAME_KEEP
    NAME_KEEP = load_name_keep(skills_root if skills_root is not None else dirs[0].parent)
    all_errs: list[str] = []
    for d in dirs:
        all_errs += check(d, args.flat_ok)
    if skills_root is not None:
        leftover = skills_root.resolve().parent / "enforcement"
        if leftover.exists():
            all_errs.append(
                "EX-3:.hermes/enforcement must not exist "
                "(category dissolved; packs live under .hermes/skills/harness/)"
            )
    if skills_root is not None and not args.skip_r_sk9:
        all_errs += check_r_sk9(skills_root, dirs)
    if skills_root is not None and not args.skip_specimen:
        scaffold = scaffold_root_from_skills(skills_root)
        if scaffold is not None:
            all_errs += check_specimen_literals(scaffold)
    for n in R_SK4_NOTICES:
        print(n)
    for e in all_errs:
        print(e)
    print(f"CHECKED={len(dirs)} VIOLATIONS={len(all_errs)}")
    sys.exit(1 if all_errs else 0)


if __name__ == "__main__":
    main()
