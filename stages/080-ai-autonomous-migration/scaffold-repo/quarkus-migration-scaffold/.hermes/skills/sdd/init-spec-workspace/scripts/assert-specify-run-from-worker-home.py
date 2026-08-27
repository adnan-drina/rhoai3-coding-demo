#!/usr/bin/env python3
"""FAIL unless speckit-specify resolves for a worker whose PATH shadows the shim.

Operator ``091320ZO`` / dest-9 ``t_af875a24``: ``init-workspace.sh`` set
``HOME=<project>`` for ``specify init`` only. Worker HOME is the profile
(or dest-user ``/home/user``), where ``~/.hermes/skills`` has 0 speckit
skills. dest-init installs a PATH shim, but dest-9 ``PATH`` starts with
``/home/user/.local/bin/specify`` (uv) which **shadows**
``/projects/.platform/hermes/bin/specify``. Control: PATH ``specify``
under that shadow must miss the skill; ``specify-from-project.sh --root``
must still find it. Do not dest-edit dest-9 PATH or ``external_dirs``.
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

    # dest-9: uv specify in $HOME/.local/bin is first on PATH and shadows
    # dest-init /projects/.platform/hermes/bin/specify (the shim).
    userbin = tmp / "user-local-bin"
    userbin.mkdir()
    probe9 = tmp / "got-home-9"
    user_specify = userbin / "specify"
    _write_mock_specify(user_specify, probe9)
    env9 = os.environ.copy()
    env9["HOME"] = str(profile)
    env9["PATH"] = (
        str(userbin)
        + os.pathsep
        + str(shim.parent)
        + os.pathsep
        + env9.get("PATH", "/usr/bin:/bin")
    )
    env9.pop("SPECIFY_REAL", None)
    env9.pop("SPECIFY_PROJECT_ROOT", None)
    shadowed = subprocess.run(
        ["specify", "workflow", "run", "speckit"],
        text=True,
        capture_output=True,
        env=env9,
        cwd=str(profile),
    )
    if shadowed.returncode == 0:
        print(
            "FAIL: dest-9 PATH shadow (user .local/bin first) must miss "
            "speckit-specify: %s%s" % (shadowed.stdout, shadowed.stderr),
            file=sys.stderr,
        )
        return 1
    helper = SCRIPTS / "specify-from-project.sh"
    via = subprocess.run(
        [
            "bash",
            str(helper),
            "--root",
            str(project),
            "workflow",
            "run",
            "speckit",
        ],
        text=True,
        capture_output=True,
        env=env9,
        cwd=str(profile),
    )
    blob9 = (via.stdout or "") + (via.stderr or "")
    if via.returncode != 0:
        print(
            "FAIL: specify-from-project.sh dest-9 shadow rc=%s: %s"
            % (via.returncode, blob9),
            file=sys.stderr,
        )
        return 1
    got9 = probe9.read_text(encoding="utf-8") if probe9.is_file() else ""
    if Path(got9).resolve() != project.resolve():
        print(
            "FAIL: helper HOME=%r (want project %s) under dest-9 PATH shadow"
            % (got9, project),
            file=sys.stderr,
        )
        return 1
    # dest-10: uv specify first on PATH; Hermes runtime specify is the
    # bridge. Helper must pick */.platform/hermes/bin/specify, not uv.
    platform_bin = tmp / "fake" / ".platform" / "hermes" / "bin"
    platform_bin.mkdir(parents=True)
    uv_fail = tmp / "uv-unknown-skill"
    uv_fail.mkdir()
    (uv_fail / "specify").write_text(
        "#!/bin/sh\n"
        "echo 'Unknown skill(s): speckit-specify' >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    (uv_fail / "specify").chmod(0o755)
    _write_mock_specify(platform_bin / "specify", tmp / "got-home-platform")
    env10 = os.environ.copy()
    env10["HOME"] = str(profile)
    env10["PATH"] = (
        str(uv_fail)
        + os.pathsep
        + str(platform_bin)
        + os.pathsep
        + env10.get("PATH", "/usr/bin:/bin")
    )
    env10.pop("SPECIFY_REAL", None)
    env10.pop("SPECIFY_PROJECT_ROOT", None)
    dest10 = subprocess.run(
        [
            "bash",
            str(helper),
            "--root",
            str(project),
            "workflow",
            "run",
            "speckit",
        ],
        text=True,
        capture_output=True,
        env=env10,
        cwd=str(profile),
    )
    blob10 = (dest10.stdout or "") + (dest10.stderr or "")
    if dest10.returncode != 0:
        print(
            "FAIL: helper must prefer .platform/hermes/bin specify over uv "
            "rc=%s: %s" % (dest10.returncode, blob10),
            file=sys.stderr,
        )
        return 1
    got10 = (
        (tmp / "got-home-platform").read_text(encoding="utf-8")
        if (tmp / "got-home-platform").is_file()
        else ""
    )
    if Path(got10).resolve() != project.resolve():
        print(
            "FAIL: dest-10 prefer-runtime HOME=%r (want project %s)"
            % (got10, project),
            file=sys.stderr,
        )
        return 1
    print(
        "OK: worker-shell specify resolved speckit-specify "
        "(HOME=project child; dest-9 PATH shadow needs specify-from-project.sh; "
        "dest-10 uv-first PATH prefers .platform/hermes/bin)"
    )
    return 0


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="specify-run-"))
    try:
        return run_control(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
