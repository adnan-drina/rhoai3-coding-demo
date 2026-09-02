#!/usr/bin/env python3
"""Selftest for A-gate: dest-9 fixture REFUSE; absent-run REFUSE; skill follow PASS.

Operator ``5e879430`` / ``Lead:assert-card-performed-ships-without-a-selftest``.
Architect ``170540ZA``: synthetic ``specify workflow run speckit`` exit 0
is not dest proof — that dispatch cannot run under hermes ``files: {}``.
Not dest.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "assert-card-performed.py"
FIXTURE = (
    HERE.parent / "fixtures" / "v9-m2-speckit-invoked-and-failed" / "t_af875a24.log"
)


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(log: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--log", str(log)],
        text=True,
        capture_output=True,
    )


def main() -> int:
    if not FIXTURE.is_file():
        return _fail("missing dest-9 M2 fixture %s" % FIXTURE)
    proc = _run(FIXTURE)
    blob = proc.stdout + proc.stderr
    if proc.returncode != 1:
        return _fail("v9 t_af875a24 must REFUSE: %s" % blob)
    if "Unknown skill" not in blob and "never succeeded" not in blob:
        return _fail("v9 fixture must name Unknown skill or never-succeeded: %s" % blob)

    with tempfile.TemporaryDirectory(prefix="card-performed-") as tmp:
        absent = Path(tmp) / "absent.log"
        absent.write_text(
            "reasoning: we should specify workflow run speckit next\n"
            "no terminal dollar line\n",
            encoding="utf-8",
        )
        proc = _run(absent)
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1:
            return _fail("log with no mandated run must REFUSE: %s" % blob)
        if "mandated action absent" not in blob:
            return _fail("absent-run must name mandated action absent: %s" % blob)

        fake_run = Path(tmp) / "workflow-ok.log"
        fake_run.write_text(
            "  ┊ 💻 $         specify workflow run speckit -i spec=x  1.0s [exit 0]\n",
            encoding="utf-8",
        )
        proc = _run(fake_run)
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1:
            return _fail(
                "synthetic workflow-run exit 0 must REFUSE under files:{}: %s"
                % blob
            )

        ok_log = Path(tmp) / "ok.log"
        ok_log.write_text(
            "  ┊ 📚 skill  speckit-specify\n"
            "author specs/001-migrate/spec.md\n",
            encoding="utf-8",
        )
        proc = _run(ok_log)
        blob = proc.stdout + proc.stderr
        if proc.returncode != 0:
            return _fail("skill-load event must PASS A-gate: %s" % blob)

        sdd_log = Path(tmp) / "sdd-load.log"
        sdd_log.write_text(
            "  ┊ 📚 skill  sdd/speckit-specify\n",
            encoding="utf-8",
        )
        proc = _run(sdd_log)
        if proc.returncode != 0:
            return _fail(
                "dest-13 sdd/ skill-load must PASS: %s%s"
                % (proc.stdout, proc.stderr)
            )

        path_only = Path(tmp) / "path-mention.log"
        path_only.write_text(
            "load .hermes/skills/speckit-specify/SKILL.md\n"
            "author .specify/specs/001-migrate/spec.md\n",
            encoding="utf-8",
        )
        proc = _run(path_only)
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1:
            return _fail("path mention without skill-load must REFUSE: %s" % blob)

        grep_only = Path(tmp) / "grep-skill-path.log"
        grep_only.write_text(
            "  ┊ 💻 $         grep speckit-specify/SKILL.md .hermes/skills -n  0.1s\n"
            "reasoning: found the path, skill followed\n",
            encoding="utf-8",
        )
        proc = _run(grep_only)
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1:
            return _fail(
                "grep of speckit-specify/SKILL.md must not PASS A-gate: %s" % blob
            )
        if "mandated action absent" not in blob:
            return _fail("grep-only log must name mandated action absent: %s" % blob)

        cat_only = Path(tmp) / "cat-skill-path.log"
        cat_only.write_text(
            "  ┊ 💻 $         cat .hermes/skills/speckit-specify/SKILL.md  0.1s\n",
            encoding="utf-8",
        )
        proc = _run(cat_only)
        if proc.returncode != 1:
            return _fail(
                "cat of SKILL.md path must not PASS A-gate: %s%s"
                % (proc.stdout, proc.stderr)
            )

    import os

    with tempfile.TemporaryDirectory(prefix="card-performed-profile-") as tmp:
        root = Path(tmp)
        (root / "kanban" / "logs").mkdir(parents=True)
        profile = root / "profiles" / "implementer"
        profile.mkdir(parents=True)
        ok = root / "kanban" / "logs" / "t_ok.log"
        ok.write_text("  ┊ 📚 skill  speckit-specify\n", encoding="utf-8")
        env = os.environ.copy()
        env["HERMES_HOME"] = str(profile)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "t_ok"],
            text=True,
            capture_output=True,
            env=env,
        )
        blob = proc.stdout + proc.stderr
        if proc.returncode != 0:
            return _fail("profile HERMES_HOME must resolve root log: %s" % blob)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "t_missing"],
            text=True,
            capture_output=True,
            env=env,
        )
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1:
            return _fail("absent root log must still REFUSE: %s" % blob)
        if "profiles/implementer/kanban" in blob:
            return _fail("refuse path must not be the profile home: %s" % blob)
        if str(root / "kanban" / "logs" / "t_missing.log") not in blob:
            return _fail("refuse path must be the resolved root log: %s" % blob)

    print(
        "OK: assert-card-performed selftest "
        "(v9 REFUSE; absent REFUSE; workflow-run REFUSE; skill follow PASS)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
