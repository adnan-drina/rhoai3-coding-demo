#!/usr/bin/env python3
"""Seed one canonical speckit leaf; dest-13 dual sdd/ copy is removed. Not dest."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SEED = SCRIPTS / "seed-speckit-skills.py"


def _skill(path: Path, name: str) -> None:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text("---\nname: %s\n---\n" % name, encoding="utf-8")


def _run(root: Path, home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SEED), str(root), str(home)],
        text=True,
        capture_output=True,
    )


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="seed-speckit-"))
    try:
        home = tmp / "human"
        src = home / ".hermes" / "skills" / "speckit-specify"
        _skill(src, "speckit-specify")
        _skill(home / ".hermes" / "skills" / "speckit-plan", "speckit-plan")
        _skill(home / ".hermes" / "skills" / "speckit-tasks", "speckit-tasks")
        root = tmp / "ws"
        leftover = root / ".hermes" / "skills" / "sdd" / "speckit-specify"
        _skill(leftover, "speckit-specify")
        proc = _run(root, home)
        blob = proc.stdout + proc.stderr
        if proc.returncode != 0:
            print("FAIL: seed from human-home must PASS: %s" % blob, file=sys.stderr)
            return 1
        flat = root / ".hermes" / "skills" / "speckit-specify" / "SKILL.md"
        if not flat.is_file():
            print("FAIL: missing canonical leaf %s" % flat, file=sys.stderr)
            return 1
        if leftover.exists():
            print("FAIL: dest-13 sdd leftover must be removed: %s" % leftover, file=sys.stderr)
            return 1
        if "and " in proc.stdout and "sdd" in proc.stdout:
            print("FAIL: OK line must not claim both trees: %s" % proc.stdout, file=sys.stderr)
            return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("OK: seed-speckit-skills selftest (canonical leaf only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
