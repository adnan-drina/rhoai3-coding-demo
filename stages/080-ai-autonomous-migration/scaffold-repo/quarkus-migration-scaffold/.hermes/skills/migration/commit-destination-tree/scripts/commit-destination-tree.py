#!/usr/bin/env python3
"""Commit dest product writes with a one-shot identity. Not M4. Not dest-push.

Architect ``101242ZA``: stamp card harvests ``src/`` / ``pom.xml`` / README.
Do not ``git config``. Do not ``Signed-off-by``. Do not dest-push.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

STAMP_NAME = "Hermes Kanban"
STAMP_EMAIL = "kanban@hermes.local"
OBJECT_PREFIXES = ("evidence/", ".hermes/", ".specify/", "target/")
OBJECT_EXACT = frozenset({".env"})


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
    )


def _rel_path(raw: str) -> str:
    rel = str(raw).replace("\\", "/").strip()
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def _refuse_object_path(rel: str) -> bool:
    rel = _rel_path(rel)
    if rel in OBJECT_EXACT or rel.endswith("/.env"):
        return True
    return any(rel == p[:-1] or rel.startswith(p) for p in OBJECT_PREFIXES)


def commit_tree(root: Path, files: list[str]) -> int:
    rels: list[str] = []
    for raw in files:
        rel = _rel_path(raw)
        if not rel:
            continue
        if _refuse_object_path(rel):
            return _fail("OBJECT path on stamp write-set: " + rel)
        rels.append(rel)
    if not rels:
        return _fail("empty files list")
    inside = _git(root, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return _fail("not a git work tree")
    existing = [p for p in rels if (root / p).exists()]
    if not existing:
        return _fail("none of the write-set paths exist")
    add = _git(root, "add", "--", *existing)
    if add.returncode != 0:
        return _fail("git add failed: " + (add.stderr or add.stdout).strip())
    staged = _git(root, "diff", "--cached", "--name-only")
    if staged.returncode != 0:
        return _fail("git diff --cached failed")
    if not staged.stdout.strip():
        print("OK: nothing to commit (index already matches write-set)", file=sys.stderr)
        return 0
    proc = _git(
        root,
        "-c",
        "user.name=" + STAMP_NAME,
        "-c",
        "user.email=" + STAMP_EMAIL,
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-m",
        "M3 STAMP_DESTINATION_TREE: harvest dest product tree",
    )
    if proc.returncode != 0:
        return _fail("git commit failed: " + (proc.stderr or proc.stdout).strip())
    print("OK: stamp commit (one-shot identity, no git config)", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    parser.add_argument("--files", nargs="+", required=True)
    args = parser.parse_args(argv)
    return commit_tree(Path(args.root).resolve(), list(args.files))


if __name__ == "__main__":
    raise SystemExit(main())
