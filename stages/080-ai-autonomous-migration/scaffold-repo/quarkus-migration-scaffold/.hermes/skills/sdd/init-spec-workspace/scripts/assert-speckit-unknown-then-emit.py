#!/usr/bin/env python3
"""Paired control: empty HOME Unknown skill(s), then helper emits tasks.md.

Operator ``201929ZO`` / Lead:speckit-skills-are-not-where-spec-kit-looks.
Do not close on ``specify workflow resolve``.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
HELPER = SCRIPTS / "specify-from-project.sh"


def _write_fake_specify(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import os, pathlib, sys
home = os.environ.get("HOME", "")
skill = pathlib.Path(home) / ".hermes/skills/speckit-specify/SKILL.md"
if not skill.is_file():
    print("Error: Unknown skill(s): speckit-specify", file=sys.stderr)
    sys.exit(1)
root = pathlib.Path(home)
spec = root / ".specify" / "specs" / "001-migrate"
spec.mkdir(parents=True, exist_ok=True)
(spec / "tasks.md").write_text("# Tasks\\n- [ ] `pom.xml`\\n", encoding="utf-8")
print("OK: specify workflow wrote tasks.md")
sys.exit(0)
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="speckit-unknown-") as raw:
        tmp = Path(raw)
        fake_dir = tmp / "bin"
        fake_dir.mkdir()
        fake = fake_dir / "specify"
        _write_fake_specify(fake)
        empty = tmp / "empty-home"
        empty.mkdir()
        env = os.environ.copy()
        env["PATH"] = str(fake_dir) + ":" + env.get("PATH", "")
        env.pop("HERMES_MANAGED_DIR", None)
        env["SPECIFY_REAL"] = str(fake)

        bare = subprocess.run(
            [str(fake), "workflow", "run", "speckit", "-i", "spec=x"],
            cwd=str(empty),
            env={**env, "HOME": str(empty)},
            text=True,
            capture_output=True,
        )
        blob = bare.stdout + bare.stderr
        if bare.returncode != 1 or "Unknown skill(s): speckit-specify" not in blob:
            print(
                "FAIL: empty HOME must Unknown skill(s) first: rc=%s %s"
                % (bare.returncode, blob),
                file=sys.stderr,
            )
            return 1

        project = tmp / "project"
        skill = project / ".hermes" / "skills" / "speckit-specify"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: speckit-specify\n---\n", encoding="utf-8"
        )
        via = subprocess.run(
            [
                "bash",
                str(HELPER),
                "--root",
                str(project),
                "workflow",
                "run",
                "speckit",
                "-i",
                "spec=x",
            ],
            env=env,
            text=True,
            capture_output=True,
        )
        blob = via.stdout + via.stderr
        tasks = project / ".specify" / "specs" / "001-migrate" / "tasks.md"
        receipt = (
            project / "evidence" / "receipts" / "speckit" / "workflow-run.json"
        )
        if via.returncode != 0:
            print("FAIL: helper must succeed after seed: %s" % blob, file=sys.stderr)
            return 1
        if not tasks.is_file() or not tasks.read_text().strip():
            print("FAIL: helper must emit tasks.md: %s" % blob, file=sys.stderr)
            return 1
        if not receipt.is_file():
            print("FAIL: helper must stamp speckit receipt: %s" % blob, file=sys.stderr)
            return 1
        doc = json.loads(receipt.read_text(encoding="utf-8"))
        if doc.get("producer") != "specify-from-project.sh" or doc.get("rc") != 0:
            print("FAIL: receipt producer/rc: %s" % doc, file=sys.stderr)
            return 1
    print("OK: speckit unknown-then-emit (tasks.md + helper receipt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
