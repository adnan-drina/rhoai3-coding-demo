#!/usr/bin/env python3
"""AD-H §5.1 — workspace_clean probe (git porcelain under ROOT).

Exit 0 when clean (or not a git repo and --allow-nongit).
Exit 1 when dirty. Prints dirty paths to stderr.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def porcelain(root: Path) -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain", "-uall"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ["__git_status_failed__"]
    paths: list[str] = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        rest = line[3:]
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        rest = rest.strip().strip('"')
        if rest:
            paths.append(rest)
    return paths


def is_git_repo(root: Path) -> bool:
    try:
        subprocess.check_output(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument(
        "--allow-nongit",
        action="store_true",
        help="Treat non-git roots as clean (fixture trees without .git)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()

    if not is_git_repo(root):
        if args.allow_nongit:
            print("OK: workspace_clean (non-git, --allow-nongit)")
            return 0
        print("FAIL: not a git worktree — cannot prove workspace_clean", file=sys.stderr)
        return 1

    dirty = porcelain(root)
    if dirty == ["__git_status_failed__"]:
        print("FAIL: git status failed", file=sys.stderr)
        return 1
    if dirty:
        print(f"FAIL: workspace dirty ({len(dirty)} path(s))", file=sys.stderr)
        for p in dirty[:40]:
            print(f"  dirty: {p}", file=sys.stderr)
        if len(dirty) > 40:
            print(f"  ... +{len(dirty) - 40} more", file=sys.stderr)
        return 1
    print("OK: workspace_clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
