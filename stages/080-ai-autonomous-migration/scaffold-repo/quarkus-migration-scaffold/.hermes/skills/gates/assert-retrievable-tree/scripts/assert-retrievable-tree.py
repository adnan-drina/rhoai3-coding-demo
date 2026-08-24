#!/usr/bin/env python3
"""Refuse M4 PROVISIONAL_ACCEPT unless src/ and pom.xml are committed vs HEAD.

Architect ``142524ZA`` / Operator ``141853Z-op`` / ``145539Z-op``.
Exclusions: ``.env``, profile home, ``.hermes/home``, secrets — those paths
are not in the refuse set. Not an M5 candidate SHA. Not a dest-push.
M3 story-complete is hygiene, not a substitute for this M4 refuse.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SELF = "assert-retrievable-tree"
VERDICT_PATH = Path("evidence") / "verdicts" / (SELF + ".json")
SCOPED = ("src", "pom.xml")


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
    )


def dirty_scoped_paths(root: Path) -> list[str] | str:
    inside = _git(root, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return "not a git work tree"
    if not (root / "pom.xml").is_file():
        return "pom.xml missing"
    if not (root / "src").exists():
        return "src/ missing"
    proc = _git(
        root,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        *SCOPED,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "git status failed").strip()
        return err
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    return lines


def write_pass_verdict(root: Path) -> None:
    path = root / VERDICT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "gate": SELF,
        "ran": True,
        "verdict": "PASS",
        "reason": "src/ and pom.xml committed vs HEAD",
        "ship": False,
    }
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def check_root(root: Path) -> int:
    dirty = dirty_scoped_paths(root)
    if isinstance(dirty, str):
        return _fail(dirty)
    if dirty:
        return _fail(
            "src/ or pom.xml untracked or uncommitted vs HEAD: "
            + "; ".join(dirty)
            + " (not dest-push; not an M5 SHA)"
        )
    write_pass_verdict(root)
    print("OK: assert-retrievable-tree (src/ and pom.xml committed)", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        return _fail("usage: assert-retrievable-tree.py ROOT")
    root = Path(args[0]).resolve()
    if not root.is_dir():
        return _fail("root is not a directory: " + str(root))
    return check_root(root)


if __name__ == "__main__":
    sys.exit(main())
