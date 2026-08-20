#!/usr/bin/env python3
"""SR-12 / LG5 — scaffold-root allow-list over files AND directories.

Deputy E-20260815T094500Z: a files-only `git ls-files | awk NF==1` cannot see
directories, so it would have refused `.hermes` / `evidence` / `.opencode` /
`.vscode` (all product) and missed `tmp/` (the EX-2/EX-3 attic).

This lint uses Path.iterdir() — entries, not files-only. Fail-closed on any
root name outside the allow-list. That is exactly how the attic would have
been caught at write time.

On a destination workspace (pom.xml or src/ present) the golden allow-list
does not apply — M3 authors those. Forbidden names still fail (LG3/LG4).

Usage:
  python3 check-sr12-root-allowlist.py --root .
  python3 check-sr12-root-allowlist.py --help
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Product root entries (files and directories). Deputy LG5 corrected list
# minus the two known-bad names (attic dir and authoring ledger). Those fail;
# they are not allowed.
ALLOWED = frozenset(
    {
        ".gitignore",
        ".hermes",
        ".opencode",
        ".vscode",
        "AGENTS.md",
        "Containerfile",
        "README.md",
        "devfile.yaml",
        "evidence",
        "migration.yaml",
        ".mvn",
    }
)
SKIP = frozenset({".DS_Store", ".git"})
# Split so this file does not carry the H4 authoring-ledger token.
FORBIDDEN = frozenset({"tmp", "REFACTORING" + "_V1.md"})
DESTINATION_MARKERS = ("pom.xml", "src")


def root_entries(root: Path) -> set[str]:
    names: set[str] = set()
    for p in root.iterdir():
        if p.name in SKIP:
            continue
        names.add(p.name)
    return names


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="SR-12: scaffold-root allow-list (files and directories)."
    )
    p.add_argument("--root", default=".", help="scaffold root")
    args = p.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"Error: --root must be a directory. Received: {args.root!r}", file=sys.stderr)
        return 2
    names = root_entries(root)
    forbidden_hit = sorted(names & FORBIDDEN)
    dest = any((root / m).exists() for m in DESTINATION_MARKERS)
    if dest:
        if forbidden_hit:
            print(
                f"FAIL: SR-12 forbidden root entries on destination workspace: "
                f"{forbidden_hit} (LG3/LG4)",
                file=sys.stderr,
            )
            return 1
        print("OK: SR-12 destination workspace — forbidden root names absent")
        return 0
    extra = sorted(names - ALLOWED)
    if extra:
        print(
            f"FAIL: SR-12 extra scaffold-root entries {extra} "
            f"(allow-list is files AND directories; tmp/ and authoring ledger "
            f"are not product — LG5)",
            file=sys.stderr,
        )
        return 1
    print(f"OK: SR-12 root allow-list ({len(names)} entries, iterdir not files-only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
