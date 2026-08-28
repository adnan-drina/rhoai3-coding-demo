#!/usr/bin/env python3
"""Pre-fix dest-6 shape fails; flat seed passes. Not dest."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ASSERT = SCRIPTS / "assert-specify-skills-root.py"


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ASSERT), str(root)],
        text=True,
        capture_output=True,
    )


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="specify-root-"))
    try:
        nested = tmp / ".hermes" / "skills" / "sdd" / "speckit-specify"
        nested.mkdir(parents=True)
        (nested / "SKILL.md").write_text("---\nname: speckit-specify\n---\n", encoding="utf-8")
        proc = _run(tmp)
        blob = proc.stdout + proc.stderr
        if proc.returncode == 0:
            print("FAIL: nested-only sdd/ copy must REFUSE: %s" % blob, file=sys.stderr)
            return 1
        if "sdd/ copy is not sufficient" not in blob:
            print("FAIL: missing nested-only message: %s" % blob, file=sys.stderr)
            return 1
        flat = tmp / ".hermes" / "skills" / "speckit-specify"
        flat.mkdir(parents=True)
        (flat / "SKILL.md").write_text("---\nname: speckit-specify\n---\n", encoding="utf-8")
        proc = _run(tmp)
        blob = proc.stdout + proc.stderr
        if proc.returncode == 0:
            print(
                "FAIL: dest-13 dual seed (flat + sdd/) must REFUSE: %s" % blob,
                file=sys.stderr,
            )
            return 1
        if "Ambiguous" not in blob and "dual-seeded" not in blob:
            print("FAIL: missing dual-seed Ambiguous message: %s" % blob, file=sys.stderr)
            return 1
        shutil.rmtree(nested)
        proc = _run(tmp)
        if proc.returncode != 0:
            print(
                "FAIL: flat project skills-root should PASS: %s %s"
                % (proc.stdout, proc.stderr),
                file=sys.stderr,
            )
            return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("OK: assert-specify-skills-root selftest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
