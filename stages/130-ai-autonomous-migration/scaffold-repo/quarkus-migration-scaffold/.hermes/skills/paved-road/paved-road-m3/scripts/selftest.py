#!/usr/bin/env python3
"""paved-road-m3 selftest: sync; kind rules; green PASS; reverted PASS; silent REFUSE; refused-advance REFUSE; no skill_view REFUSE; coverage."""
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
from paved_road import GOLDEN_ROOT, coverage, load_steps, loop_verdict_for, sync_audit, validate_steps_doc  # noqa: E402


def _run(name: str) -> tuple[int, str]:
    fx = FX / name
    proc = subprocess.run([sys.executable, str(SCRIPT), "--log", str(fx / "official.log"), "--root", str(fx)], text=True, capture_output=True)
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    rc, msg = sync_audit(SKILL)
    if rc != 0:
        return _fail(msg)
    doc = load_steps(SKILL / "steps.json")
    if doc["steps"][0].get("skill") != "fix-until-green":
        return _fail("M3 must start by viewing fix-until-green")
    if [s.get("native") for s in doc["steps"] if s["backing"] == "native"] != ["brief.py", "run-verify.sh", "advance.py"]:
        return _fail("M3 native order")
    prod = next(s for s in doc["steps"] if s.get("producer"))
    if prod.get("native") != "advance.py" or prod.get("verdict") is not True or "verification/loop/steps.json" not in prod.get("keep", []):
        return _fail("advance.py must be the producer, a verdict step, and KEEP the loop record")
    bad = json.loads(json.dumps(doc))
    bad["steps"].insert(1, {"id": "author-destination-pom", "backing": "skill", "skill": "author-destination-pom"})
    if not any("story-era" in e for e in validate_steps_doc(bad)):
        return _fail("a story-era pom skill as a loop step must be refused")
    bad = json.loads(json.dumps(doc))
    bad["steps"][0]["verdict"] = True
    if not any("verdict" in e for e in validate_steps_doc(bad)):
        return _fail("verdict is only for kernel/native steps")

    rc, blob = _run("green-m3")
    if rc != 0 or "verdict=accepted" not in blob:
        return _fail("green-m3 must PASS with the accepted verdict: %s" % blob)
    rc, blob = _run("reverted-m3")
    if rc != 0 or "verdict=rejected" not in blob:
        return _fail("reverted-m3 must PASS (a reverted attempt is a recorded outcome): %s" % blob)
    rc, blob = _run("silent-no-advance")
    if rc != 1 or "advance.py" not in blob or "silence" not in blob:
        return _fail("silent-no-advance must REFUSE naming advance.py: %s" % blob)
    rc, blob = _run("refused-no-verdict")
    if rc != 1 or "no loop verdict recorded" not in blob:
        return _fail("a refused advance is not a verdict: %s" % blob)
    if "ACCEPTED" not in (FX / "refused-no-verdict" / "official.log").read_text(encoding="utf-8"):
        return _fail("the refused fixture must carry the word ACCEPTED in prose (prose is not the grade)")
    rc, blob = _run("no-skill-view")
    if rc != 1 or "fix-until-green" not in blob:
        return _fail("no-skill-view must REFUSE naming the index skill: %s" % blob)
    if loop_verdict_for(FX / "green-m3", "t_nobody") != "":
        return _fail("an unknown card has no verdict")
    if coverage(GOLDEN_ROOT) != 0:
        return _fail("coverage lint failed")
    print("OK: paved-road-m3 selftest (sync; view-first; brief→verify→advance; advance is the verdict step; green PASS; reverted PASS; silent REFUSE; refused-advance REFUSE; no-skill-view REFUSE; coverage)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
