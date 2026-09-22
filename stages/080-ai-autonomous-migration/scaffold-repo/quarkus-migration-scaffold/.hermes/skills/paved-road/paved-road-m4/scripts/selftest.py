#!/usr/bin/env python3
"""paved-road-m4 selftest: sync; kind rules; the generated suite is generated then committed before any gate reads
the tree; green PASS; missing runner / oracles / verdict / red runner REFUSE; coverage."""
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
    # The parity phase is a tool, not a worker's judgement, and it runs BEFORE
    # the pre-verdict runner: the receipt it composes is one of the things the
    # verdict cites. v9's first M4 card is the control (t_32c82390): a worker
    # driving the comparators by hand ran the composer first and compared none
    # of the 34 admitted entry points.
    if [s.get("native") for s in doc["steps"] if s["backing"] == "native"] != [
            "run-parity.py", "commit-generated-tests.py", "run-m4-pre-verdict.sh"]:
        return _fail("M4 runs three native steps in order: the batch parity runner, the commit of the generated suite, "
                     "then the pre-verdict runner")
    parity = next(s for s in doc["steps"] if s.get("native") == "run-parity.py")
    if sorted(parity.get("keep") or []) != ["verification/parity/_run.json", "verification/parity/receipt.json"]:
        return _fail("the parity step must KEEP the receipt and the run record: %s" % parity.get("keep"))
    if not (HERE / "run-parity.py").is_file():
        return _fail("the parity step names a runner that is not in this skill's scripts/")
    # The generated product tests are generated after parity has run and
    # BEFORE the pre-verdict runner: the rebuild that runner drives is what
    # executes them, so a generator placed after it would leave the floors
    # measuring a suite that never ran. They are also the only thing the
    # m4-parity profile compiles, which is why the M3 loop never sees them.
    gen = "generate-product-tests"
    if gen not in ids:
        return _fail("M4 must generate the product acceptance tests (ADR-015): %s" % ids)
    if not (ids.index("parity") < ids.index(gen) < ids.index("pre-verdict")):
        return _fail("%s runs after the parity runner and before the pre-verdict runner: %s" % (gen, ids))
    gen_step = next(s for s in doc["steps"] if s["id"] == gen)
    if gen_step.get("backing") != "skill" or gen_step.get("skill") != gen:
        return _fail("the generator step is backed by the %s skill: %s" % (gen, gen_step))
    if gen_step.get("keep") != ["evidence/tests/generated-manifest.json"]:
        return _fail("the generator step must KEEP the manifest the floors consume: %s" % gen_step.get("keep"))
    # The generated files are written into a tree assert-retrievable-tree still
    # requires to be committed, so the road commits them -- between the
    # generator that wrote them and every gate that reads the tree. Without
    # this step the M4 verdict is composed over a tree nobody can retrieve, and
    # the gate refuses for the harness's own doing.
    commit = "commit-generated-tests"
    if commit not in ids:
        return _fail("M4 must commit the generated suite it wrote (ADR-015): %s" % ids)
    if not (ids.index(gen) < ids.index(commit) < ids.index("pre-verdict")):
        return _fail("%s runs after the generator and before the pre-verdict runner: %s" % (commit, ids))
    if ids.index(commit) >= ids.index("check-domain-parity"):
        return _fail("%s runs before the gates that read the tree: %s" % (commit, ids))
    commit_step = next(s for s in doc["steps"] if s["id"] == commit)
    if commit_step.get("backing") != "native" or commit_step.get("native") != "commit-generated-tests.py":
        return _fail("the commit step is the producer's own script, run natively: %s" % commit_step)
    if ids[-1] != "check-release-readiness":
        return _fail("the readiness lint must come last (it may agree or refuse, never author): %s" % ids)

    # kind rules refuse a road that would let the verdict be chosen rather than measured
    bad = json.loads(json.dumps(doc))
    bad["steps"] = [s for s in bad["steps"] if s["backing"] != "native"]
    if not any("pre-verdict runner" in e for e in validate_steps_doc(bad)):
        return _fail("a road with no pre-verdict runner must be refused")
    bad = json.loads(json.dumps(doc))
    runner = next(s for s in bad["steps"] if s.get("native") == "run-m4-pre-verdict.sh")
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
    # v9 t_caf2ad51: the runner ran once and passed; a grep over its path that
    # exited 1 while the worker read the script is not a run of the step.
    rc, blob = _run("read-after-runner")
    if rc != 0:
        return _fail("read-after-runner must PASS (a grep naming the runner is not a run of it): %s" % blob)
    for name, needle in (("verdict-before-runner", "run-m4-pre-verdict.sh"),
                         ("no-oracles", "capture-source-oracles"),
                         ("runner-red-no-rerun", "unmatched [exit 1]"),
                         ("missing-verdict", "m4-verdict.json")):
        rc, blob = _run(name)
        if rc != 1 or needle not in blob:
            return _fail("%s must REFUSE naming %s: %s" % (name, needle, blob[:300]))
    if coverage(GOLDEN_ROOT) != 0:
        return _fail("coverage lint failed")
    print("OK: paved-road-m4 selftest (sync; oracles first; the generated suite is generated then committed before any "
          "gate reads the tree; runner before the producer; compose-m4-verdict the only producer; lint last; green PASS; "
          "a read naming the runner is not a run of it; no runner / no oracles / red runner / missing verdict REFUSE; coverage)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
