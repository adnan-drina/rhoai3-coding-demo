#!/usr/bin/env python3
"""FAIL unless bare ``specify`` resolves speckit-specify when HOME is the profile.

Operator ``091320ZO``: ``init-workspace.sh`` set ``HOME=<project>`` for
``specify init`` only. At run time worker HOME is the profile home, where
``~/.hermes/skills`` has 0 speckit skills. Control: ``specify workflow run
speckit`` from a worker shell (no HOME= prefix) must still find
``speckit-specify``.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
INSTALL = SCRIPTS / "install-specify-shim.sh"


def _write_mock_specify(path: Path, probe_out: Path) -> None:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import os, pathlib, sys\n"
        "home = os.environ.get('HOME', '')\n"
        "pathlib.Path(%r).write_text(home, encoding='utf-8')\n"
        "skill = pathlib.Path(home) / '.hermes/skills/speckit-specify/SKILL.md'\n"
        "if not skill.is_file():\n"
        "    print('FAIL: speckit-specify missing under HOME=' + home, file=sys.stderr)\n"
        "    sys.exit(1)\n"
        "print('OK: found speckit-specify under HOME=' + home)\n"
        "sys.exit(0)\n" % str(probe_out),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def run_control(tmp: Path) -> int:
    project = tmp / "project"
    profile = tmp / "profile"
    mockdir = tmp / "mock"
    probe = tmp / "got-home"
    skill = project / ".hermes" / "skills" / "speckit-specify"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: speckit-specify\n---\n", encoding="utf-8"
    )
    profile.mkdir(parents=True)
    mockdir.mkdir(parents=True)
    mock = mockdir / "specify"
    _write_mock_specify(mock, probe)

    inst = subprocess.run(
        ["bash", str(INSTALL), str(project)],
        text=True,
        capture_output=True,
    )
    if inst.returncode != 0:
        print(
            "FAIL: install-specify-shim: %s%s" % (inst.stdout, inst.stderr),
            file=sys.stderr,
        )
        return 1

    shim = project / ".hermes" / "bin" / "specify"
    env = os.environ.copy()
    env["HOME"] = str(profile)
    env["PATH"] = (
        str(shim.parent)
        + os.pathsep
        + str(mockdir)
        + os.pathsep
        + env.get("PATH", "/usr/bin:/bin")
    )
    env["SPECIFY_REAL"] = str(mock)
    env.pop("SPECIFY_PROJECT_ROOT", None)

    proc = subprocess.run(
        ["specify", "workflow", "run", "speckit"],
        text=True,
        capture_output=True,
        env=env,
        cwd=str(profile),
    )
    blob = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        print(
            "FAIL: worker-shell specify rc=%s: %s" % (proc.returncode, blob),
            file=sys.stderr,
        )
        return 1
    got = probe.read_text(encoding="utf-8") if probe.is_file() else ""
    if Path(got).resolve() != project.resolve():
        print(
            "FAIL: specify child HOME=%r (want project %s). "
            "Profile HOME leaked — dest-6/dest-7 run-time defect."
            % (got, project),
            file=sys.stderr,
        )
        return 1
    # dest-7 shape: mock specify + profile HOME + no shim → skill missing
    env_bad = os.environ.copy()
    env_bad["HOME"] = str(profile)
    env_bad["PATH"] = str(mockdir) + os.pathsep + env_bad.get("PATH", "/usr/bin:/bin")
    env_bad.pop("SPECIFY_REAL", None)
    probe.unlink(missing_ok=True)
    bare = subprocess.run(
        [str(mock), "workflow", "run", "speckit"],
        text=True,
        capture_output=True,
        env=env_bad,
        cwd=str(profile),
    )
    if bare.returncode == 0:
        print(
            "FAIL: profile HOME without shim must miss speckit-specify: %s%s"
            % (bare.stdout, bare.stderr),
            file=sys.stderr,
        )
        return 1
    print("OK: worker-shell specify resolved speckit-specify (HOME=project child)")
    return 0


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="specify-run-"))
    try:
        return run_control(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
