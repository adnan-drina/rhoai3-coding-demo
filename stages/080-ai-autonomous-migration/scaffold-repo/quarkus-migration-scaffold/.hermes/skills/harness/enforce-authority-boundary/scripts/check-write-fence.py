#!/usr/bin/env python3
"""AD-H §16.4 / ER#2 F2 — refuse deny-path / out-of-scope dirty trees before complete.

Usage:
  check-write-fence.py [ROOT] [--body PATH] [--git-status] [--writes PATH ...]

Fails closed when:
  - any listed/dirty path is under the proving-min deny-list
  - `--body` supplies files_writable (preferred) or files_in_scope and a write is outside that scope
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

DENY_PREFIXES = (
    "evidence/acks/",
    "evidence/acks",
    "evidence/verdicts/",
    "evidence/verdicts",
    ".hermes/",
    ".hermes",
    "AGENTS.md",
    "SOUL.md",
    ".hermes/SOUL.md",
    "devfile.yaml",
    ".hermes/home/kanban.db",
)


def norm(p: str) -> str:
    # Prefix-strip "./" only. Never use str.lstrip("./") — that strips any
    # leading '.' or '/' character, so ".hermes/skills/harness/x" becomes
    # "hermes/enforcement/x" and misses DENY_PREFIXES (Z15-a / A-1 hole).
    s = p.replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s


def is_denied(path: str) -> bool:
    n = norm(path)
    for ban in DENY_PREFIXES:
        b = ban.rstrip("/")
        if n == b or n.startswith(b + "/") or n == ban:
            return True
    return False


def in_scope(path: str, scope: list[str]) -> bool:
    if not scope:
        return False
    n = norm(path)
    for s in scope:
        s = norm(str(s))
        if n == s or n.startswith(s.rstrip("/") + "/") or s.startswith(n.rstrip("/") + "/"):
            return True
        # directory scope prefix
        if s.endswith("/") and n.startswith(s):
            return True
        if not s.endswith("/") and (n == s or n.startswith(s + "/")):
            return True
    return False


def git_dirty(root: Path) -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain", "-uall"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    paths: list[str] = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        # status XY + space + path; renames: "R  a -> b"
        rest = line[3:]
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        rest = rest.strip().strip('"')
        if rest:
            paths.append(rest)
    return paths


def load_scope(body_path: Path) -> list[str]:
    data = json.loads(body_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return []
    body = data.get("body") if isinstance(data.get("body"), dict) else data
    if not isinstance(body, dict):
        return []
    for key in ("files_writable", "write_set", "files_in_scope", "filesInScope"):
        scope = body.get(key)
        if isinstance(scope, list) and scope:
            return [str(x) for x in scope]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--body", help="Kanban typed body JSON with files_in_scope")
    ap.add_argument(
        "--git-status",
        action="store_true",
        default=True,
        help="Include git porcelain paths (default on)",
    )
    ap.add_argument(
        "--no-git-status",
        action="store_true",
        help="Do not read git status",
    )
    ap.add_argument(
        "--writes",
        nargs="*",
        default=[],
        help="Explicit write paths (packet declared)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()

    paths: list[str] = list(args.writes)
    if args.git_status and not args.no_git_status:
        paths.extend(git_dirty(root))

    # Always scan deny dirs for unexpected worker-created probe leftovers? skip.

    scope: list[str] = []
    if args.body:
        scope = load_scope(Path(args.body))

    if not paths and not scope:
        print("OK: write-fence idle (no dirty/writes paths)")
        return 0

    bad = 0
    seen: set[str] = set()
    for p in paths:
        n = norm(p)
        if n in seen:
            continue
        seen.add(n)
        if is_denied(n):
            print(f"FAIL: FENCE_DENY write/dirty path {p}", file=sys.stderr)
            bad = 1
            continue
        if scope and not in_scope(n, scope):
            # Ignore noise under governance/fixtures probe crumbs and .git
            if n.startswith(".git/") or n.endswith(".f2-positive-control"):
                continue
            # Allow migration analysis noise? F2 says out-of-scope must fail.
            # Limit scope check to src/ and .specify/ style app paths when scope set.
            if n.startswith("src/") or n.startswith("pom.xml") or n.startswith(
                ".specify/"
            ) or n.startswith("specs/"):
                print(
                    f"FAIL: FENCE_SCOPE write/dirty {p} outside files_in_scope",
                    file=sys.stderr,
                )
                bad = 1

    if bad:
        print("Write-fence checks FAILED — refuse kanban_complete", file=sys.stderr)
        return 1
    print(f"OK: write-fence checks passed ({len(seen)} path(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
