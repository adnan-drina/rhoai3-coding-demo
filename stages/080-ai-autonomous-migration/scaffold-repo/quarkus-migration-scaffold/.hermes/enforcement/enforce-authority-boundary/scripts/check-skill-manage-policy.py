#!/usr/bin/env python3
"""AD-H §16.8 / AR-1.4 — single skill-edit prohibition for migration workers."""
from __future__ import annotations

import re
import sys
from pathlib import Path

NEVER_EDIT = re.compile(
    r"(?i)("
    r"never edit\b.{0,40}\.hermes/skills|"
    r"do not edit\b.{0,40}\.hermes/skills|"
    r"must not\b.{0,40}edit\b.{0,40}skills|"
    r"nobody\b.{0,20}\.hermes/skills"
    r")"
)
SKILL_MANAGE_MUTATE = re.compile(
    r"(?i)skill_manage\s*[:=]\s*(true|enabled|allow|readwrite|write)"
)
CONTRA_EDIT = re.compile(
    r"(?i)workers?\s+(may|should|must)\s+(edit|modify)\s+skills|"
    r"in-session\s+skill\s+edit\s+allowed"
)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    bad = 0

    policy_files = [
        root / "governance" / "contracts" / "task-authority.md",
        root / ".hermes" / "skills" / "harness" / "enforce-authority-boundary" / "SKILL.md",
        root / "AGENTS.md",
    ]
    policy_blob = ""
    for p in policy_files:
        if p.is_file():
            policy_blob += "\n" + p.read_text(encoding="utf-8", errors="replace")
    if not NEVER_EDIT.search(policy_blob):
        print(
            "FAIL: AR-1.4 missing never-edit-.hermes/skills worker policy",
            file=sys.stderr,
        )
        bad = 1

    # Fixture / prompt surfaces that must not enable mutating skill_manage
    scan_roots = [
        root / "governance" / "fixtures" / "authority",
        root / ".hermes" / "home" / "config",
    ]
    scanned = 0
    for base in scan_roots:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {
                ".md",
                ".yaml",
                ".yml",
                ".txt",
                ".json",
            }:
                continue
            scanned += 1
            text = path.read_text(encoding="utf-8", errors="replace")
            try:
                label = str(path.relative_to(root))
            except ValueError:
                label = str(path)
            if SKILL_MANAGE_MUTATE.search(text) or CONTRA_EDIT.search(text):
                print(f"FAIL: AR-1.4 {label}: mutating skill_manage / in-session edit", file=sys.stderr)
                bad = 1

    if bad:
        print("AR-1.4 skill-manage policy FAILED", file=sys.stderr)
        return 1
    print(f"OK: AR-1.4 skill-manage policy (fixture_surfaces={scanned})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
