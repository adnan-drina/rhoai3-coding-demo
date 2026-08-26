#!/usr/bin/env python3
"""Selftest for A-gate: dest-9 fixture REFUSE; absent-run REFUSE; synthetic exit 0 PASS.

Operator ``5e879430`` / ``Lead:assert-card-performed-ships-without-a-selftest``.
Synthetic PASS is not dest proof — no dest log has ever carried
``specify workflow run speckit`` exit 0. Not dest.
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
    if "never succeeded" not in blob:
        return _fail("v9 fixture must name never-succeeded: %s" % blob)

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

        ok_log = Path(tmp) / "ok.log"
        ok_log.write_text(
            "  ┊ 💻 $         specify workflow run speckit -i spec=x  1.0s [exit 0]\n",
            encoding="utf-8",
        )
        proc = _run(ok_log)
        blob = proc.stdout + proc.stderr
        if proc.returncode != 0:
            return _fail("synthetic speckit exit 0 must PASS: %s" % blob)

    print("OK: assert-card-performed selftest (v9 REFUSE; absent REFUSE; synthetic PASS)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
