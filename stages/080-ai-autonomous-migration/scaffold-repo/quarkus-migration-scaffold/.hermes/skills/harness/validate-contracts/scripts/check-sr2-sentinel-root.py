#!/usr/bin/env python3
"""SR-2 — refuse parent-count project-root resolution (BV19-8).

Walk up to migration.yaml. A hop count encodes tree depth at authoring time
and goes silently wrong when the tree moves (V18-F1; EX-3).

Scans .hermes **/*.sh and **/*.py (skip tmp, this file). Fail-closed on:

  * bash: cd/pwd whose path is only parent hops (2+) from dirname $0,
    SCRIPT_DIR, or SKILL_DIR
  * bash: ROOT/root/MODERNIZED_ROOT assigned from such a hop chain
  * python: Path.parents[N] with N>=2 (scaffold-root arithmetic)

Sibling lookups that continue to a named path (e.g. ../../other-skill/scripts)
are allowed. One hop to the skill directory (dirname $0/..) is allowed.

Usage:
  python3 check-sr2-sentinel-root.py --root .
  python3 check-sr2-sentinel-root.py --help
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SKIP_PARTS = frozenset({"__pycache__", ".git", "tmp"})
SELF_NAME = "check-sr2-sentinel-root.py"

# cd "$(dirname "$0")/../../.." — path is only parent hops (2+).
CD_DIRNAME_HOP = re.compile(
    r'cd\s+"\$\(dirname\s+"\$0"\)/(?:\.\./)+\.\."'
)
# cd "${SCRIPT_DIR}/../../../.." or cd "${SKILL_DIR}/../../.."
CD_VAR_HOP = re.compile(
    r'cd\s+"\$\{(?:SCRIPT_DIR|SKILL_DIR)\}/(?:\.\./)+\.\."'
)
# ${SKILL_DIR}/../../.. as a default path that *ends* on hops
# (ROOT="$(cd "${1:-${SKILL_DIR}/../../..}" && pwd)").
# Sibling lookups (${SCRIPT_DIR}/../../other-skill/scripts) do not match.
VAR_HOP = re.compile(
    r'\$\{(?:SCRIPT_DIR|SKILL_DIR)\}/(?:\.\./)+\.\.(?=["\'}\s)]|$)'
)

ROOT_ASSIGN = re.compile(
    r'(?:^|[^A-Za-z0-9_])(?:ROOT|root|MODERNIZED_ROOT)\s*=\s*.*(?:\.\./){2,}'
)

PY_PARENTS = re.compile(r"""\.parents\[\s*([2-9]|\d{2,})\s*\]""")

COMMENT_SH = re.compile(r"^\s*#")
COMMENT_PY = re.compile(r"^\s*#")


def skip_path(p: Path, root: Path) -> bool:
    try:
        rel = p.relative_to(root)
    except ValueError:
        return True
    if any(part in SKIP_PARTS for part in rel.parts):
        return True
    if p.name == SELF_NAME:
        return True
    return False


def line_comment(path: Path, line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if path.suffix == ".py":
        return bool(COMMENT_PY.match(line))
    return bool(COMMENT_SH.match(line))


def scan_file(path: Path) -> list[str]:
    errs: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return [f"SR-2:{path}:read {e}"]
    for i, line in enumerate(text.splitlines(), 1):
        if line_comment(path, line):
            continue
        if path.suffix == ".py":
            m = PY_PARENTS.search(line)
            if m:
                errs.append(
                    f"SR-2:{path}:{i}:parents[{m.group(1)}] "
                    f"(walk up to migration.yaml; never a parent-count)"
                )
            continue
        if (
            CD_DIRNAME_HOP.search(line)
            or CD_VAR_HOP.search(line)
            or VAR_HOP.search(line)
            or ROOT_ASSIGN.search(line)
        ):
            errs.append(
                f"SR-2:{path}:{i}:parent-count root "
                f"(walk up to migration.yaml; never a parent-count)"
            )
    return errs


def scan_tree(root: Path) -> list[str]:
    hermes = root / ".hermes"
    if not hermes.is_dir():
        return [f"SR-2: missing {hermes}"]
    errs: list[str] = []
    for p in sorted(hermes.rglob("*")):
        if not p.is_file() or p.suffix not in {".sh", ".py"}:
            continue
        if skip_path(p, root):
            continue
        errs.extend(scan_file(p))
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "SR-2: refuse parent-count project-root resolution. "
            "Anchor on migration.yaml."
        )
    )
    ap.add_argument("--root", default=".", help="scaffold root (default: .)")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    errs = scan_tree(root)
    for e in errs:
        print(e, file=sys.stderr)
    if errs:
        print(f"FAIL: SR-2 parent-count root sites={len(errs)}", file=sys.stderr)
        return 1
    print("OK: SR-2 no parent-count root resolution under .hermes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
