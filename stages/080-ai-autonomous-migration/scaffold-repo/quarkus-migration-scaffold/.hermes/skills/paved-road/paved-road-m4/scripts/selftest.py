#!/usr/bin/env python3
"""paved-road-m4 selftest: sync; kind rules; green PASS; missing runner / oracles / verdict / red runner REFUSE; coverage."""
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
    ids = [s["id"] for s in doc["steps"]]
    if ids[0] != "capture-source-oracles":
        return _fail("M4 must start with the source oracles: %s" % ids)
    prod = next(s for s in doc["steps"] if s.get("producer"))
    if prod.get("skill") != "compose-m4-verdict" or "evidence/verdicts/m4-verdict.json" not in prod.get("keep", []):
        return _fail("compose-m4-verdict must be the only producer and KEEP the verdict: %s" % prod)
    if [s.get("native") for s in doc["steps"] if s["backing"] == "native"] != ["run-m4-pre-verdict.sh"]:
        return _fail("M4 runs exactly one native step, the pre-verdict runner")
    if ids[-1] != "check-release-readiness":
        return _fail("the readiness lint must come last (it may agree or refuse, never author): %s" % ids)

    # kind rules refuse a road that would let the verdict be chosen rather than measured
    bad = json.loads(json.dumps(doc))
    bad["steps"] = [s for s in bad["steps"] if s["backing"] != "native"]
    if not any("pre-verdict runner" in e for e in validate_steps_doc(bad)):
        return _fail("a road with no pre-verdict runner must be refused")
    bad = json.loads(json.dumps(doc))
    runner = next(s for s in bad["steps"] if s["backing"] == "native")
    bad["steps"].remove(runner)
    bad["steps"].append(runner)
    if not any("must precede" in e for e in validate_steps_doc(bad)):
        return _fail("a runner after the producer must be refused (the verdict cites receipts it produces)")
    bad = json.loads(json.dumps(doc))
    for s in bad["steps"]:
        s.pop("producer", None)
    bad["steps"][1]["producer"] = True
    if not any("producer must be compose-m4-verdict" in e for e in validate_steps_doc(bad)):
        return _fail("a checker as producer must be refused")
    bad = json.loads(json.dumps(doc))
    bad["steps"] = bad["steps"][1:]
    if not any("must start with capture-source-oracles" in e for e in validate_steps_doc(bad)):
        return _fail("a road that does not start with the oracles must be refused")

    rc, blob = _run("green-m4")
    if rc != 0:
        return _fail("green-m4 must PASS: %s" % blob)
    for name, needle in (("verdict-before-runner", "run-m4-pre-verdict.sh"),
                         ("no-oracles", "capture-source-oracles"),
                         ("runner-red-no-rerun", "unmatched [exit 1]"),
                         ("missing-verdict", "m4-verdict.json")):
        rc, blob = _run(name)
        if rc != 1 or needle not in blob:
            return _fail("%s must REFUSE naming %s: %s" % (name, needle, blob[:300]))
    if coverage(GOLDEN_ROOT) != 0:
        return _fail("coverage lint failed")
    print("OK: paved-road-m4 selftest (sync; oracles first; runner before the producer; compose-m4-verdict the only producer; lint last; green PASS; no runner / no oracles / red runner / missing verdict REFUSE; coverage)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
