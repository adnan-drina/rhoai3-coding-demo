#!/usr/bin/env python3
"""Listed-but-missing extra external_dirs path must fail closed, naming it."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
CHECKER = SCRIPTS / "check-external-dirs.py"


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="ext-dirs-"))
    try:
        project = tmp / "modernized"
        skills = project / ".hermes" / "skills"
        skills.mkdir(parents=True)
        hh = tmp / "hermes-home"
        hh.mkdir()
        bogus = tmp / "no-such-external-dirs"
        cfg = hh / "config.yaml"
        cfg.write_text(
            "skills:\n"
            "  external_dirs:\n"
            f"    - {skills}\n"
            "    - /home/user/.hermes/skills\n"
            f"    - {bogus}\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["HERMES_HOME"] = str(hh)
        env.pop("HERMES_CONFIG", None)
        env.pop("HERMES_MANAGED_DIR", None)
        proc = subprocess.run(
            [sys.executable, str(CHECKER), str(project)],
            text=True,
            capture_output=True,
            env=env,
        )
        blob = proc.stdout + proc.stderr
        if proc.returncode == 0:
            print("FAIL: extra missing path must REFUSE: %s" % blob, file=sys.stderr)
            return 1
        if str(bogus) not in blob:
            print("FAIL: refusal must name the missing path: %s" % blob, file=sys.stderr)
            return 1
        cfg.write_text(
            "skills:\n"
            "  external_dirs:\n"
            f"    - {skills}\n"
            "    - /home/user/.hermes/skills\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, str(CHECKER), str(project)],
            text=True,
            capture_output=True,
            env=env,
        )
        if proc.returncode != 0:
            print(
                "FAIL: listed project+dest-user should PASS: %s %s"
                % (proc.stdout, proc.stderr),
                file=sys.stderr,
            )
            return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("OK: check-external-dirs selftest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
