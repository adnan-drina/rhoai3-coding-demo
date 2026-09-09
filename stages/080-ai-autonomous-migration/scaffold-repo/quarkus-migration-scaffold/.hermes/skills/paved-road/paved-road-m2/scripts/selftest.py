#!/usr/bin/env python3
"""paved-road-m2 selftest: sync; green PASS; red-no-rerun REFUSE; red-then-clean PASS; skill-dir red PASS; not-activated REFUSE."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPT = HERE / "assert-paved-road-audit.py"
FX = SKILL / "fixtures"


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
from paved_road import GOLDEN_ROOT, coverage, load_steps, sync_audit, validate_steps_doc  # noqa: E402


def _run(name: str) -> tuple[int, str]:
    fx = FX / name
    proc = subprocess.run([sys.executable, str(SCRIPT), "--log", str(fx / "official.log"), "--root", str(fx)], text=True, capture_output=True)
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    rc, msg = sync_audit(SKILL)
    if rc != 0:
        return _fail(msg)
    doc = load_steps(SKILL / "steps.json")
    first = doc["steps"][0]
    if first["backing"] != "native" or first["native"] != "assert-planner-activated.py":
        return _fail("M2 must start with the activation gate")
    if [s.get("skill") for s in doc["steps"] if s["backing"] == "skill"] != ["bootstrap-destination", "build-worklist", "admit-migration-plan", "verify-live-kanban-loop"]:
        return _fail("M2 skill steps")
    if [s.get("kernel") for s in doc["steps"] if s["backing"] == "kernel"] != ["k4_mint.py"]:
        return _fail("M2 kernel steps")
    if any("speckit" in json.dumps(s) or "partition" in json.dumps(s) for s in doc["steps"]):
        return _fail("M2 steps must carry no Spec Kit or partition residue")
    bad = json.loads(json.dumps(doc))
    bad["steps"].insert(0, {"id": "speckit-specify", "backing": "skill", "skill": "speckit-specify"})
    errs = validate_steps_doc(bad)
    if not any("activation" in e or "retired" in e for e in errs):
        return _fail("a Spec Kit step ahead of the gate must be refused: %s" % errs)

    rc, blob = _run("green-m2")
    if rc != 0:
        return _fail("green-m2 must PASS: %s" % blob)
    if "[exit 0]" in (FX / "green-m2" / "official.log").read_text(encoding="utf-8"):
        return _fail("green fixture must omit [exit 0]")
    rc, blob = _run("red-no-rerun")
    if rc != 1 or "unmatched [exit 1]" not in blob or "k4_mint.py" not in blob:
        return _fail("red-no-rerun must REFUSE naming k4_mint.py: %s" % blob)
    rc, blob = _run("red-then-clean")
    if rc != 0:
        return _fail("red-then-clean must PASS: %s" % blob)
    rc, blob = _run("skill-dir-red-skill-view-green")
    if rc != 0:
        return _fail("skill-dir-red-skill-view-green must PASS: %s" % blob)
    rc, blob = _run("not-activated")
    if rc != 1 or "assert-planner-activated.py" not in blob:
        return _fail("not-activated must REFUSE naming the gate: %s" % blob)
    if "kanban_block" not in (FX / "not-activated" / "official.log").read_text(encoding="utf-8"):
        return _fail("not-activated fixture must show kanban_block (the legal transitional stop)")
    if coverage(GOLDEN_ROOT) != 0:
        return _fail("coverage lint failed")
    print("OK: paved-road-m2 selftest (sync; gate first; green PASS; red-no-rerun REFUSE; red-then-clean PASS; skill-dir red PASS; not-activated REFUSE; coverage)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
