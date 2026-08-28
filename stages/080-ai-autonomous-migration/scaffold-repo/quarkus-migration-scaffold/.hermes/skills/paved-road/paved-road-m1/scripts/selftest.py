#!/usr/bin/env python3
"""paved-road-m1 selftest: audit.json sync; green PASS; silence REFUSE."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPT = HERE / "assert-paved-road-audit.py"
GREEN = SKILL / "fixtures" / "green-m1"


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

    if not (GREEN / "official.log").is_file():
        return _fail("missing green fixture %s" % GREEN)
    green_txt = (GREEN / "official.log").read_text(encoding="utf-8")
    if "[exit 0]" in green_txt:
        return _fail("green fixture must omit [exit 0] (dispatcher success format)")
    proc = _run(GREEN / "official.log", GREEN)
    blob = proc.stdout + proc.stderr
    if proc.returncode != 0:
        return _fail("green-m1 must PASS: %s" % blob)

    with tempfile.TemporaryDirectory(prefix="paved-m1-") as tmp:
        empty = Path(tmp) / "empty.log"
        empty.write_text("reasoning: skip MTA\n", encoding="utf-8")
        proc = _run(empty, GREEN)
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1:
            return _fail("silence must REFUSE: %s" % blob)
        if "silence" not in blob and "absent" not in blob:
            return _fail("silence must name absence: %s" % blob)

    cov = coverage(GOLDEN_ROOT)
    if cov != 0:
        return _fail("coverage lint failed")

    print("OK: paved-road-m1 selftest (sync; green PASS dispatcher-format; silence REFUSE; coverage)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
