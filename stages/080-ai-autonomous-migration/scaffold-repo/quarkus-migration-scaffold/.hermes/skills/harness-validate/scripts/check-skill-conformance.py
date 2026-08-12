#!/usr/bin/env python3
"""AD-012 / R-SK.5 — mechanical skill conformance lint (R-SK.1–4 + bundle YAML).

Validates tip `.hermes/skills/*/SKILL.md` against Architect-ratified AD-012:
  R-SK.1 layout (allowed root entries only)
  R-SK.2 frontmatter (name, description ≤60 imperative, version, metadata.hermes.*)
  R-SK.3 body section order (When to Use → Procedure → Pitfalls → Verification)
  R-SK.4 progressive disclosure (SKILL.md size soft bound; refs under references/)

Also validates `.hermes/home/skill-bundles/*.yaml` when present (CS-7 / R-SK.5):
  name, skills[], m<phase>-* naming for phase bundles.

Exit codes:
  0 — all checked skills PASS, or --report-only / soft mode with findings printed
  1 — one or more FAIL (strict mode; default when SKILL_CONFORMANCE_STRICT=1)

Chain-end CS-6 #2 flips soft→strict after the 14-skill hygiene wave. Mid-chain
default is report-only so harness-validate stays green without mass rewrite.

Usage:
  check-skill-conformance.py <root> [--strict] [--report-only] [--skill NAME]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ALLOWED_ROOT = frozenset(
    {"SKILL.md", "references", "templates", "scripts", "examples", "assets"}
)
# AD-012 amendment Architect E-20260812T064958Z: Pitfalls/Example optional.
REQUIRED_SECTIONS = (
    "## When to Use",
    "## Procedure",
    "## Verification",
)
OPTIONAL_SECTIONS = (
    "## Pitfalls",
    "## Example",
)
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
PHASE_BUNDLE_RE = re.compile(r"^m[0-9]+[a-z]*-")


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    raw = text[3:end].strip("\n")
    body = text[end + 4 :]  # after \n---
    data: dict[str, object] = {}
    cur_key: str | None = None
    cur_indent = 0
    stack: list[tuple[int, dict[str, object]]] = [(0, data)]
    for ln in raw.splitlines():
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        indent = len(ln) - len(ln.lstrip(" "))
        m = re.match(r"^(\s*)([A-Za-z0-9_.-]+):\s*(.*)$", ln)
        if not m:
            if cur_key and isinstance(stack[-1][1].get(cur_key), str):
                stack[-1][1][cur_key] = (
                    str(stack[-1][1][cur_key]) + " " + ln.strip()
                ).strip()
            continue
        ind, key, val = m.group(1), m.group(2), m.group(3).strip()
        indent = len(ind)
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if val == "" or val == "|" or val == ">":
            nested: dict[str, object] = {}
            parent[key] = nested
            stack.append((indent, nested))
            cur_key = None
            continue
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
        parent[key] = val
        cur_key = key
        cur_indent = indent
    # Fold multiline description blocks that used `>` / `|` as empty then prose
    # lines without keys — already appended above when cur_key set. Hermes often
    # uses `description: >` then indented lines; re-parse those:
    return _refold_multiline(raw, data), body


def _refold_multiline(raw: str, data: dict[str, object]) -> dict[str, object]:
    """Capture YAML `description: >` / `|` folded blocks into data['description']."""
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^description:\s*([>|]?)\s*$", lines[i])
        if m:
            fold = m.group(1)
            parts: list[str] = []
            i += 1
            while i < len(lines) and (
                lines[i].startswith("  ") or lines[i].startswith("\t")
            ):
                parts.append(lines[i].strip())
                i += 1
            joined = " ".join(parts) if fold in (">", "") else "\n".join(parts)
            data["description"] = joined.strip()
            continue
        i += 1
    # nested metadata.hermes
    hermes: dict[str, object] = {}
    in_meta = False
    in_hermes = False
    for ln in lines:
        if re.match(r"^metadata:\s*$", ln):
            in_meta = True
            in_hermes = False
            continue
        if in_meta and re.match(r"^  hermes:\s*$", ln):
            in_hermes = True
            continue
        if in_meta and re.match(r"^[A-Za-z]", ln):
            in_meta = False
            in_hermes = False
        if in_hermes:
            hm = re.match(r"^    ([A-Za-z0-9_-]+):\s*(.*)$", ln)
            if hm:
                hermes[hm.group(1)] = hm.group(2).strip().strip("\"'")
            elif re.match(r"^  [A-Za-z]", ln):
                in_hermes = False
    if hermes:
        meta = data.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
            data["metadata"] = meta
        meta["hermes"] = hermes
    return data


def description_text(data: dict[str, object]) -> str:
    d = data.get("description")
    if isinstance(d, str):
        return " ".join(d.split())
    return ""


def check_skill(skill_dir: Path) -> list[str]:
    fails: list[str] = []
    name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [f"{name}: missing SKILL.md (R-SK.1)"]

    for p in skill_dir.iterdir():
        if p.name.startswith("."):
            continue
        if p.name not in ALLOWED_ROOT:
            fails.append(f"{name}: stray root entry `{p.name}` (R-SK.1)")

    text = skill_md.read_text(encoding="utf-8")
    data, body = parse_frontmatter(text)

    fm_name = str(data.get("name") or "")
    if fm_name != name:
        fails.append(
            f"{name}: frontmatter name={fm_name!r} != directory (R-SK.2)"
        )

    desc = description_text(data)
    if not desc:
        fails.append(f"{name}: missing description (R-SK.2)")
    elif len(desc) > 60:
        fails.append(
            f"{name}: description length {len(desc)} > 60 (R-SK.2)"
        )

    ver = str(data.get("version") or "")
    if not ver or not SEMVER_RE.match(ver):
        fails.append(f"{name}: missing/invalid version semver (R-SK.2)")

    if not str(data.get("author") or "").strip():
        fails.append(f"{name}: missing author (R-SK.2)")
    if not str(data.get("license") or "").strip():
        fails.append(f"{name}: missing license (R-SK.2)")

    meta = data.get("metadata")
    hermes = meta.get("hermes") if isinstance(meta, dict) else None
    if not isinstance(hermes, dict):
        fails.append(f"{name}: missing metadata.hermes (R-SK.2)")
    else:
        if not hermes.get("tags"):
            fails.append(f"{name}: missing metadata.hermes.tags (R-SK.2)")
        if not hermes.get("category"):
            fails.append(f"{name}: missing metadata.hermes.category (R-SK.2)")

    positions: list[tuple[str, int]] = []
    for sec in REQUIRED_SECTIONS:
        idx = body.find(sec)
        if idx < 0:
            fails.append(f"{name}: missing section `{sec}` (R-SK.3)")
        else:
            positions.append((sec, idx))
    if len(positions) == len(REQUIRED_SECTIONS):
        ordered = sorted(positions, key=lambda x: x[1])
        if [s for s, _ in ordered] != list(REQUIRED_SECTIONS):
            fails.append(
                f"{name}: section order not When→Procedure→Verification "
                f"(got {[s for s, _ in ordered]}) (R-SK.3)"
            )
    # Optional sections must not precede Verification if present
    ver_idx = body.find("## Verification")
    if ver_idx >= 0:
        for sec in OPTIONAL_SECTIONS:
            idx = body.find(sec)
            if idx >= 0 and idx < ver_idx:
                fails.append(
                    f"{name}: optional `{sec}` must follow Verification (R-SK.3)"
                )

    # R-SK.4 soft: SKILL.md body (post-frontmatter) should stay lean
    if len(body) > 12_000:
        fails.append(
            f"{name}: SKILL.md body {len(body)} bytes > 12k soft bound (R-SK.4)"
        )

    return fails


def parse_bundle_yaml(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    out: dict[str, object] = {"skills": []}
    skills: list[str] = []
    in_skills = False
    for ln in text.splitlines():
        if re.match(r"^skills:\s*$", ln):
            in_skills = True
            continue
        if in_skills:
            sm = re.match(r"^- (\S+)\s*$", ln)
            if sm:
                skills.append(sm.group(1))
                continue
            if ln.strip() and not ln.startswith("- ") and not ln.startswith(" "):
                in_skills = False
        m = re.match(r"^(name|description|instruction):\s*(.*)$", ln)
        if m:
            out[m.group(1)] = m.group(2).strip().strip("\"'")
    out["skills"] = skills
    return out


def check_bundles(root: Path) -> list[str]:
    fails: list[str] = []
    bdir = root / ".hermes" / "home" / "skill-bundles"
    if not bdir.is_dir():
        return fails
    for path in sorted(bdir.glob("*.yaml")):
        data = parse_bundle_yaml(path)
        name = str(data.get("name") or path.stem)
        if name != path.stem:
            fails.append(
                f"bundle {path.name}: name={name!r} != filename stem (R-SK.5)"
            )
        if PHASE_BUNDLE_RE.match(name) is None and name.startswith("m"):
            # phase bundles must match m<phase>-*
            fails.append(
                f"bundle {name}: phase-like name must match m<phase>-* (CS-7)"
            )
        skills = data.get("skills") or []
        if not isinstance(skills, list) or not skills:
            fails.append(f"bundle {name}: empty skills[] (R-SK.5)")
        if not data.get("instruction"):
            fails.append(f"bundle {name}: missing instruction: (CS-7)")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--skill", action="append", default=[])
    args = ap.parse_args()
    root = Path(args.root).resolve()
    skills_root = root / ".hermes" / "skills"
    if not skills_root.is_dir():
        print(f"FAIL: missing {skills_root}", file=sys.stderr)
        return 1

    env_strict = os.environ.get("SKILL_CONFORMANCE_STRICT", "").lower() in (
        "1",
        "true",
        "yes",
    )
    strict = args.strict or (env_strict and not args.report_only)
    if args.report_only:
        strict = False

    targets = sorted(
        d
        for d in skills_root.iterdir()
        if d.is_dir() and (d / "SKILL.md").is_file()
    )
    if args.skill:
        want = set(args.skill)
        targets = [d for d in targets if d.name in want]

    all_fails: list[str] = []
    for d in targets:
        all_fails.extend(check_skill(d))
    all_fails.extend(check_bundles(root))

    if not all_fails:
        print(f"OK: skill conformance PASS ({len(targets)} skills)")
        return 0

    mode = "STRICT" if strict else "REPORT-ONLY (CS-6 #2 wave pending)"
    print(f"SKILL_CONFORMANCE {mode}: {len(all_fails)} finding(s)", file=sys.stderr)
    for f in all_fails:
        print(f"  FAIL: {f}", file=sys.stderr)
    if strict:
        return 1
    print(
        f"OK: skill conformance soft-pass ({len(all_fails)} debt; "
        "strict at chain-end CS-6 #2)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
