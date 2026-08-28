#!/usr/bin/env python3
"""Stamp commit harvests src/pom; OBJECT paths refuse. Not dest."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
COMMIT = SCRIPTS / "commit-destination-tree.py"
ASSERT = (
    SCRIPTS.parents[2]
    / "gates"
    / "assert-retrievable-tree"
    / "scripts"
    / "assert-retrievable-tree.py"
)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
    )


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="stamp-tree-"))
    try:
        _git(tmp, "init", "-q")
        (tmp / "README.md").write_text("scaffold\n", encoding="utf-8")
        _git(tmp, "add", "--", "README.md")
        _git(
            tmp,
            "-c",
            "user.name=seed",
            "-c",
            "user.email=seed@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "-m",
            "seed",
        )
        (tmp / "pom.xml").write_text("<project/>\n", encoding="utf-8")
        src = tmp / "src" / "main" / "java" / "com" / "demo"
        src.mkdir(parents=True)
        (src / "Main.java").write_text("class Main {}\n", encoding="utf-8")
        (tmp / "evidence").mkdir()
        (tmp / "evidence" / "secret.txt").write_text("no\n", encoding="utf-8")
        obj = subprocess.run(
            [
                sys.executable,
                str(COMMIT),
                str(tmp),
                "--files",
                "evidence/secret.txt",
            ],
            text=True,
            capture_output=True,
        )
        if obj.returncode == 0:
            return _fail("OBJECT evidence/ path must REFUSE: %s" % obj.stdout)
        proc = subprocess.run(
            [
                sys.executable,
                str(COMMIT),
                str(tmp),
                "--files",
                "pom.xml",
                "src/main/java/com/demo/Main.java",
            ],
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            return _fail("stamp commit: %s%s" % (proc.stdout, proc.stderr))
        check = subprocess.run(
            [sys.executable, str(ASSERT), "--check-only", str(tmp)],
            text=True,
            capture_output=True,
        )
        if check.returncode != 0:
            return _fail("check-only after stamp: %s%s" % (check.stdout, check.stderr))
        if (tmp / "evidence" / "verdicts" / "assert-retrievable-tree.json").exists():
            return _fail("check-only must not write evidence/verdicts")
        log = _git(tmp, "log", "-1", "--format=%an %ae")
        if "kanban@hermes.local" not in log.stdout:
            return _fail("stamp identity missing: %s" % log.stdout)
        cfg = _git(tmp, "config", "--local", "--get", "user.email")
        if cfg.returncode == 0 and cfg.stdout.strip():
            return _fail("git config user.email was mutated: %s" % cfg.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("OK: commit-destination-tree selftest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
