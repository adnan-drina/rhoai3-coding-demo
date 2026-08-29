#!/usr/bin/env python3
"""paved-road-m2 selftest: dest-14 REFUSE; green PASS; audit.json sync."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPT = HERE / "assert-paved-road-audit.py"
DEST14 = SKILL / "fixtures" / "dest-14-m2-four-exit1"
GREEN = SKILL / "fixtures" / "green-m2"
SKILL_DIR_RED = SKILL / "fixtures" / "skill-dir-red-skill-view-green"
TWO_RUN_CLEAN = SKILL / "fixtures" / "two-run-prior-red-then-clean"
TWO_RUN_NO_RERUN = SKILL / "fixtures" / "two-run-prior-red-no-rerun"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _ensure_hermes_lib() -> None:
    p = Path(__file__).resolve()
    for parent in p.parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            s = str(lib)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()
from paved_road import GOLDEN_ROOT, coverage, sync_audit  # noqa: E402


def _run(log: Path, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--log", str(log), "--root", str(root)],
        text=True,
        capture_output=True,
    )


def main() -> int:
    rc, msg = sync_audit(SKILL)
    if rc != 0:
        return _fail(msg)

    log = DEST14 / "official.log"
    if not log.is_file():
        return _fail("missing dest-14 fixture %s" % log)
    text = log.read_text(encoding="utf-8")
    if text.count("[exit 1]") < 4:
        return _fail("dest-14 fixture must contain four [exit 1]")
    if (
        "preparing kanban_complete" not in text
        and "kanban_complete call succeeded" not in text
    ):
        return _fail("dest-14 fixture must contain kanban_complete")
    if "preparing kanban_block" in text:
        return _fail("dest-14 fixture must have zero preparing kanban_block")

    proc = _run(log, DEST14)
    blob = proc.stdout + proc.stderr
    if proc.returncode != 1:
        return _fail("dest-14 fixture must REFUSE: %s" % blob)
    if "unmatched [exit 1]" not in blob:
        return _fail("dest-14 refuse must name unmatched [exit 1]: %s" % blob)
    if "check-partition-coverage.py" not in blob:
        return _fail("dest-14 refuse must name check-partition-coverage.py: %s" % blob)
    if "assert-m2-speckit-conformance.py" not in blob:
        return _fail(
            "dest-14 refuse must name assert-m2-speckit-conformance.py: %s" % blob
        )
    if "mandated needle 'plan-migration-partition'" in blob:
        return _fail(
            "dest-14 must not refuse on skill-name path substring: %s" % blob
        )

    if not (GREEN / "official.log").is_file():
        return _fail("missing green fixture %s" % GREEN)
    green_txt = (GREEN / "official.log").read_text(encoding="utf-8")
    if "[exit 0]" in green_txt:
        return _fail("green fixture must omit [exit 0] (dispatcher success format)")
    proc = _run(GREEN / "official.log", GREEN)
    blob = proc.stdout + proc.stderr
    if proc.returncode != 0:
        return _fail("green-m2 must PASS: %s" % blob)

    if not (SKILL_DIR_RED / "official.log").is_file():
        return _fail("missing skill-dir-red fixture %s" % SKILL_DIR_RED)
    proc = _run(SKILL_DIR_RED / "official.log", SKILL_DIR_RED)
    blob = proc.stdout + proc.stderr
    if proc.returncode != 0:
        return _fail("skill-dir-red-skill-view-green must PASS: %s" % blob)

    if not (TWO_RUN_CLEAN / "official.log").is_file():
        return _fail("missing two-run-clean fixture %s" % TWO_RUN_CLEAN)
    two_txt = (TWO_RUN_CLEAN / "official.log").read_text(encoding="utf-8")
    if two_txt.count("Query: work kanban task") < 2:
        return _fail("two-run-clean fixture must contain two run markers")
    if "[exit 1]" not in two_txt:
        return _fail("two-run-clean fixture must retain the prior-run red")
    proc = _run(TWO_RUN_CLEAN / "official.log", TWO_RUN_CLEAN)
    blob = proc.stdout + proc.stderr
    if proc.returncode != 0:
        return _fail("two-run-prior-red-then-clean must PASS: %s" % blob)

    if not (TWO_RUN_NO_RERUN / "official.log").is_file():
        return _fail("missing two-run-no-rerun fixture %s" % TWO_RUN_NO_RERUN)
    proc = _run(TWO_RUN_NO_RERUN / "official.log", TWO_RUN_NO_RERUN)
    blob = proc.stdout + proc.stderr
    if proc.returncode != 1:
        return _fail("two-run-prior-red-no-rerun must REFUSE: %s" % blob)
    if "unmatched [exit 1]" not in blob:
        return _fail("two-run-no-rerun must name unmatched [exit 1]: %s" % blob)
    if "check-partition-coverage.py" not in blob:
        return _fail(
            "two-run-no-rerun must name check-partition-coverage.py: %s" % blob
        )

    cov = coverage(GOLDEN_ROOT)
    if cov != 0:
        return _fail("coverage lint failed")

    print(
        "OK: paved-road-m2 selftest "
        "(dest-14 REFUSE naming coverage/conformance; "
        "green PASS; skill-dir-red PASS; two-run last-wins PASS/REFUSE; "
        "sync; coverage)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
