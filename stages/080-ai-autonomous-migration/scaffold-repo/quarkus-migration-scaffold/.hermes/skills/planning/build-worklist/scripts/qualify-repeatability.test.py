#!/usr/bin/env python3
"""qualify-repeatability selftest: the recorded-evidence level of the driver
passes every case (the producer-replay cases are their own suites and run in
the release check on their own); then the M-7 additions:

- fresh MTA: with no CLI resolvable the case is NOT-RUN naming why; with a
  fake MTA CLI (the pinned 8.2.1 shape of mta-rescan-destination.test.py) the
  M1 MTA producer runs on two clean frozen copies and their semantic findings
  compare PASS (named non-admissible in the claim boundary); a CLI whose
  findings drift between runs is FAIL;
- --build-fresh: a fixture producer builds two roots; same source -> producers
  and plans PASS (planning graded PARTIAL: not the harness producer); a
  producer that drifts -> FAIL; a producer that produces nothing -> NOT-RUN;
- --patches: identical deterministic typed-repair patches PASS (root paths
  normalised, agent-authored records not compared); a different patch or a
  missing application FAIL; different executors or no records NOT-RUN;
- qualify-release.sh writes verdict.json with the claim grading and never
  grades a claim it did not measure.
"""
import contextlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DRIVER = Path(__file__).with_name("qualify-repeatability.py")
HERMES = Path(__file__).resolve().parents[4]
RELEASE = HERMES.parents[2] / "qualify-release.sh"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "report.json"
        p = subprocess.run([sys.executable, str(DRIVER), "--no-producers", "--out", str(out)], capture_output=True, text=True, timeout=900)
        if p.returncode != 0 or not out.is_file():
            print("FAIL: the driver failed: %s" % (p.stdout + p.stderr)[-800:], file=sys.stderr)
            return 1
        rep = json.loads(out.read_text())
    bad = [c for c in rep["cases"] if c["status"] != "PASS"]
    cmp_ = rep.get("initial_plan_comparison") or {}
    if bad or not cmp_.get("equal") or cmp_["a"]["plan_fingerprint"] != cmp_["b"]["plan_fingerprint"] \
            or cmp_["a"]["run_bound_revision_digest"] == cmp_["b"]["run_bound_revision_digest"] or not rep.get("synthetic_evidence"):
        print("FAIL: %s" % json.dumps(bad or cmp_)[:800], file=sys.stderr)
        return 1
    claims = (rep.get("claim_boundary") or {}).get("claims") or {}
    if any((claims.get(k) or {}).get("status") != "NOT-MEASURED" for k in
           ("repeatable_planning", "repeatable_transformations", "repeatable_migration")):
        print("FAIL: recorded evidence alone must grade every M-7 claim NOT-MEASURED: %s" % json.dumps(claims)[:600], file=sys.stderr)
        return 1
    for fn in (_fresh_mode_case, _mta_cases, _build_fresh_cases, _patch_cases_case, _release_runner_case):
        err = fn()
        if err:
            print("FAIL: %s: %s" % (fn.__name__, err), file=sys.stderr)
            return 1
    print("OK: qualify-repeatability (%d recorded-evidence cases pass; plan %s identical across two runs, run bindings distinct; "
          "--fresh equal on two derivations of one source and FAIL on two sources; fresh MTA NOT-RUN without a CLI, PASS on "
          "two fake-CLI analyses (non-admissible named), FAIL on drift; --build-fresh PASS/FAIL/NOT-RUN through a fixture "
          "producer; typed-repair patches equal PASS, unequal/missing FAIL, other executor/no records NOT-RUN; "
          "qualify-release.sh verdict grades only what ran)" % (len(rep["cases"]), cmp_["a"]["plan_fingerprint"][:16]))
    return 0


def _fresh_mode_case() -> str:
    """--fresh on two derivations of one (synthetic) source: equal, with the
    golden's compatibility objectives composed; on two different sources: a
    FAIL naming the outcomes that differ, never normalised away."""
    qr = _load(DRIVER, "qualify_repeatability")
    with tempfile.TemporaryDirectory() as td:
        q = qr.Q(Path(td))
        a = q.dest("same-a", run_id="run-a")
        b = q.dest("same-b", seed=11, run_id="run-b")
        qr.fresh_cases(q, a, b)
        got, ev = q.cases[-1], q.evidence.get("fresh_comparison") or {}
        if got["status"] != qr.PASS or not ev.get("objectives") or ev.get("policy") != "compatibility-objectives/v1":
            return "two derivations of one source: %s %s" % (got, {k: ev.get(k) for k in ("policy", "objectives")})
        c = q.dest("other-source", base="org.other.clinic", run_id="run-c")
        qr.fresh_cases(q, a, c)
        if q.cases[-1]["status"] != qr.FAIL or not (q.evidence.get("fresh_comparison") or {}).get("membership_differences"):
            return "two different sources must FAIL with the differing outcomes named: %s" % q.cases[-1]
    return ""


# --- fresh MTA ---------------------------------------------------------------

DRIFT_WRAPPER = r'''#!/usr/bin/env python3
import json, os, subprocess, sys
from pathlib import Path
rc = subprocess.call([sys.executable, os.environ["FAKE_REAL"]] + sys.argv[1:])
if sys.argv[1:2] == ["analyze"] and rc == 0:
    c = Path(os.environ["FAKE_COUNTER"])
    n = int(c.read_text()) if c.exists() else 0
    c.write_text(str(n + 1))
    if n % 2:  # every second analysis reports the first incident one line lower
        rep = Path(sys.argv[sys.argv.index("--output") + 1])
        for name in ("output.json",):
            doc = json.loads((rep / name).read_text())
            for rs in doc:
                for v in rs["violations"].values():
                    v["incidents"][0]["lineNumber"] += 1
            (rep / name).write_text(json.dumps(doc))
        y = (rep / "output.yaml").read_text().replace("lineNumber: 1", "lineNumber: 2", 1)
        (rep / "output.yaml").write_text(y)
raise SystemExit(rc)
'''


@contextlib.contextmanager
def _env(**kv):
    old = {k: os.environ.get(k) for k in kv}
    try:
        for k, v in kv.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _clean_path() -> str:
    """PATH without any directory that holds a real MTA CLI or kantra."""
    return os.pathsep.join(d for d in os.environ.get("PATH", "").split(os.pathsep)
                           if d and not any(os.path.exists(os.path.join(d, n)) for n in ("mta-cli", "kantra")))


def _mta_cases() -> str:
    qr = _load(DRIVER, "qualify_repeatability_mta")
    fake = _load(HERMES / "skills/analysis/scan-with-mta/scripts/mta-rescan-destination.test.py", "rescan_fake").FAKE
    with tempfile.TemporaryDirectory(prefix="q-mta-") as td:
        t = Path(td).resolve()
        legacy = t / "legacy"
        (legacy / "src/main/java/org/acme").mkdir(parents=True)
        (legacy / "src/main/java/org/acme/A.java").write_text("class A {}\n")
        (legacy / "src/main/java/org/acme/B.java").write_text("class B {}\n")
        (legacy / "pom.xml").write_text("<project/>\n")
        home = t / "home"
        (home / ".local/bin").mkdir(parents=True)
        (home / ".local/bin/kantra-assert-exec").write_text("#!/bin/sh\nexit 0\n")
        (home / ".local/bin/kantra-assert-exec").chmod(0o755)
        fakebin, driftbin = t / "fakebin", t / "driftbin"
        fakebin.mkdir()
        driftbin.mkdir()
        (fakebin / "mta-cli").write_text(fake)
        (fakebin / "mta-cli").chmod(0o755)
        (t / "real-fake.py").write_text(fake)
        (driftbin / "mta-cli").write_text(DRIFT_WRAPPER)
        (driftbin / "mta-cli").chmod(0o755)
        base = dict(MTA_CLI_HOME=str(t / "no-mta"), KANTRA_HOME=str(t / "no-kantra"), HUMAN_HOME=str(home),
                    JVM_MAX_MEM="1G", JAVA_HOME_21=None, MTA_RUN_CWD=None, FAKE_MODE=None,
                    FAKE_REAL=str(t / "real-fake.py"), FAKE_COUNTER=str(t / "counter"))
        clean = _clean_path()
        # 1. no CLI anywhere: NOT-RUN, with the reason
        with _env(PATH=clean, **base):
            q = qr.Q(t / "absent", source=legacy)
            (t / "absent").mkdir()
            q.case(qr.MTA_CASE, "producer-replay", lambda: qr.mta_probe(q))
        got = q.cases[-1]
        if got["status"] != qr.NOT_RUN or "no MTA CLI" not in got["detail"]:
            return "no CLI must be NOT-RUN naming why: %s" % got
        # 2. a CLI on PATH: two fresh analyses, semantic findings equal
        with _env(PATH=str(fakebin) + os.pathsep + clean, **base):
            q = qr.Q(t / "present", source=legacy)
            (t / "present").mkdir()
            q.case(qr.MTA_CASE, "producer-replay", lambda: qr.mta_probe(q))
            got, ev = q.cases[-1], q.evidence.get("mta_fresh") or {}
            if got["status"] != qr.PASS or not ev.get("equal") or ev.get("incidents") != [4, 4] or ev.get("admissible"):
                return "a present CLI must run twice and compare equal (non-admissible fake): %s %s" % (got, ev)
            bound = qr.claim_boundary(q)
            if not any("NON-ADMISSIBLE" in x for x in bound["does_not_cover"]) or \
                    not any(x.startswith("fresh producer execution: MTA CLI") for x in bound["covers"]):
                return "the claim boundary must name the fresh MTA run and its non-admissibility: %s" % bound
        # 3. findings that drift between two runs: FAIL
        with _env(PATH=str(driftbin) + os.pathsep + clean, **base):
            q = qr.Q(t / "drift", source=legacy)
            (t / "drift").mkdir()
            q.case(qr.MTA_CASE, "producer-replay", lambda: qr.mta_probe(q))
        got, ev = q.cases[-1], q.evidence.get("mta_fresh") or {}
        if got["status"] != qr.FAIL or ev.get("equal") is not False or not ev.get("only_a"):
            return "drifting findings must FAIL with the difference named: %s %s" % (got, ev)
    return ""


# --- --build-fresh -----------------------------------------------------------

FAKE_PRODUCER = r'''#!/usr/bin/env python3
"""Fixture producer with rehearse-legacy.sh's interface: builds a synthetic
M1 -> M2 root (planner.specimens) instead of running the real producers."""
import argparse, importlib.util, os, sys
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument("--legacy", required=True)
ap.add_argument("--root", required=True)
a = ap.parse_args()
root = Path(a.root)
c = Path(os.environ["FAKE_PRODUCER_COUNTER"])
n = int(c.read_text()) if c.exists() else 0
c.write_text(str(n + 1))
mode = os.environ.get("FAKE_PRODUCER_MODE", "")
if mode == "nothing":  # a host without the toolchain: nothing produced
    root.mkdir(parents=True, exist_ok=True)
    print("javac: command not found", file=sys.stderr)
    raise SystemExit(1)
spec = importlib.util.spec_from_file_location("qr", os.environ["FAKE_DRIVER"])
qr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qr)
base = "org.other.clinic" if (mode == "drift" and n % 2) else "org.acme.clinic"
qr.Q(root.parent).dest(root.name, base=base, seed=(11 if n % 2 else None))
'''


def _build_fresh_cases() -> str:
    qr = _load(DRIVER, "qualify_repeatability_build")
    with tempfile.TemporaryDirectory(prefix="q-build-") as td:
        t = Path(td).resolve()
        source = t / "source"
        (source / "src/main/java/p").mkdir(parents=True)
        (source / "src/main/java/p/A.java").write_text("class A {}\n")
        prod = t / "fake-producer.py"
        prod.write_text(FAKE_PRODUCER)
        producer = [sys.executable, str(prod)]
        results = {}
        for mode in ("same", "drift", "nothing"):
            with _env(FAKE_PRODUCER_MODE=mode, FAKE_PRODUCER_COUNTER=str(t / ("counter-" + mode)), FAKE_DRIVER=str(DRIVER)):
                q = qr.Q(t / mode)
                (t / mode).mkdir()
                qr.build_cases(q, source, producer)
                results[mode] = (q, {c["case"]: c for c in q.cases})
        q, got = results["same"]
        if got.get(qr.BUILT_PRODUCERS_CASE, {}).get("status") != qr.PASS or got.get(qr.BUILT_CASE, {}).get("status") != qr.PASS:
            return "same source, same producer: producers and plans must PASS: %s" % json.dumps(got)[:600]
        ev = q.evidence.get("built_fresh_roots") or {}
        if ev.get("producer_is_harness_default") or not ev.get("not_executed") or ev["steps"]["a"].get("scan-with-mta") != "ok":
            return "the built-roots evidence must name the producer, the steps and what was not executed: %s" % ev
        if qr.BUILT_MTA_CASE not in got:
            return "the built roots' MTA findings must be compared when both roots hold them"
        planning = qr.claim_boundary(q)["claims"]["repeatable_planning"]
        if planning["status"] != "PARTIAL" or not any("caller-supplied producer" in m for m in planning["missing"]):
            return "a fixture producer can never grade planning MEASURED: %s" % planning
        _q, got = results["drift"]
        if got.get(qr.BUILT_CASE, {}).get("status") != qr.FAIL:
            return "a producer that drifts must FAIL the comparison: %s" % json.dumps(got)[:600]
        _q, got = results["nothing"]
        st = got.get(qr.BUILT_PRODUCERS_CASE, {})
        if st.get("status") != qr.NOT_RUN or "javac" not in st.get("detail", "") or qr.BUILT_CASE in got:
            return "a producer that produced nothing must be NOT-RUN with its reason and stop there: %s" % json.dumps(got)[:600]
    return ""


# --- --patches ---------------------------------------------------------------

PATCH = ("--- a/src/main/java/p/Ctl.java\n+++ b/src/main/java/p/Ctl.java\n@@ -1 +1 @@\n"
         "-// built at ROOT/src\n+// built at ROOT/src (repaired)\n")


def _application(root: Path, *, patch: str = PATCH, recipe: str = "handler-uri-parameter", exe: str = "e" * 64,
                 outcome: str = "applied", ms: int = 1000, cluster: str = "c:src/main/java/p/Ctl.java") -> None:
    att = root / "verification/loop/typed-repair" / cluster.replace(":", "-").replace("/", "_") / ("%s-%d" % (recipe, ms))
    (att / "out").mkdir(parents=True)
    (att / "out/patch.diff").write_text(patch.replace("ROOT", str(root)))
    rec = {"schema": "rhoai3.typed-repair-record/v1", "cluster": cluster, "at": "2026-10-0%dT00:00:00Z" % (ms % 9 + 1),
           "recipe": {"id": recipe, "version": "1", "operation": recipe}, "target": {"path": "src/main/java/p/Ctl.java"},
           "outcome": outcome, "changed_files": ["src/main/java/p/Ctl.java"] if outcome == "applied" else [],
           "executor": {"sha256": exe, "pinned": True}, "elapsed_ms": ms}
    (att / "record.json").write_text(json.dumps(rec))


def _patch_cases_case() -> str:
    qr = _load(DRIVER, "qualify_repeatability_patch")
    with tempfile.TemporaryDirectory(prefix="q-patch-") as td:
        t = Path(td).resolve()

        def run(name: str, setup_a, setup_b):
            a, b = t / name / "a", t / name / "b"
            a.mkdir(parents=True)
            b.mkdir(parents=True)
            setup_a(a)
            setup_b(b)
            q = qr.Q(t / name)
            qr.patch_cases(q, a, b)
            return q.cases[-1], q.evidence.get("patch_comparison") or {}

        def same(r):
            _application(r)
            # an agent-authored repair's record differs freely: never compared by patch
            _application(r, recipe="handler-validation-translation", patch="--- %s\n" % r.name)

        got, ev = run("equal", same, same)
        if got["status"] != qr.PASS or ev.get("applied") != 1 or len(ev.get("not_compared_agent_or_unclassified") or []) != 1:
            return "identical deterministic patches (root paths differ) must PASS: %s %s" % (got, ev)
        got, ev = run("unequal", _application, lambda r: _application(r, patch=PATCH.replace("repaired", "rewritten")))
        if got["status"] != qr.FAIL or not ev.get("differences"):
            return "a different staged patch must FAIL: %s" % got
        got, _ev = run("missing", _application, lambda r: None)
        if got["status"] != qr.FAIL or "only_in" not in got["detail"]:
            return "an application present in one run only must FAIL: %s" % got
        got, _ev = run("retry", lambda r: (_application(r, outcome="failed", ms=1), _application(r, ms=2)), _application)
        if got["status"] != qr.PASS:
            return "the final applied patch is compared, not the number of attempts: %s" % got
        got, _ev = run("executor", _application, lambda r: _application(r, exe="f" * 64))
        if got["status"] != qr.NOT_RUN or "different executors" not in got["detail"]:
            return "two executors are not the same frozen inputs (NOT-RUN): %s" % got
        got, _ev = run("none", lambda r: None, lambda r: None)
        if got["status"] != qr.NOT_RUN:
            return "no records must be NOT-RUN: %s" % got
    return ""


# --- qualify-release.sh ------------------------------------------------------

def _release_runner_case() -> str:
    """The checked-in runner, on one fast suite and the recorded-evidence
    driver: a PASS verdict that grades every M-7 claim NOT-MEASURED and
    carries the identity and the suite results; a failing suite makes it FAIL."""
    if not RELEASE.is_file():
        return "no %s" % RELEASE
    suite = HERMES / "skills/analysis/scan-with-mta/scripts/emit-required-extensions.test.py"
    with tempfile.TemporaryDirectory(prefix="q-release-") as td:
        t = Path(td)
        p = subprocess.run(["bash", str(RELEASE), "--out", str(t / "ok"), "--python", sys.executable, "--no-producers",
                            "--suite", str(suite)], capture_output=True, text=True, timeout=1800)
        v = json.loads((t / "ok/verdict.json").read_text()) if (t / "ok/verdict.json").is_file() else {}
        if p.returncode != 0 or v.get("verdict") != "PASS" or v["suites"]["pass"] != 1:
            return "one passing suite and a clean driver must PASS: rc=%s %s" % (p.returncode, (p.stdout + p.stderr)[-600:])
        if {k: c.get("status") for k, c in v["claims"].items()} != {
                "repeatable_planning": "NOT-MEASURED", "repeatable_transformations": "NOT-MEASURED",
                "repeatable_migration": "NOT-MEASURED"} or not v["identity"].get("commit"):
            return "the verdict must not grade an unmeasured claim and must carry the identity: %s" % json.dumps(v)[:600]
        bad = t / "bad.test.py"
        bad.write_text("import sys\nprint('FAIL: deliberately')\nsys.exit(1)\n")
        p = subprocess.run(["bash", str(RELEASE), "--out", str(t / "bad"), "--python", sys.executable, "--no-producers",
                            "--suite", str(bad)], capture_output=True, text=True, timeout=1800)
        v = json.loads((t / "bad/verdict.json").read_text()) if (t / "bad/verdict.json").is_file() else {}
        if p.returncode != 1 or v.get("verdict") != "FAIL" or len(v["suites"]["failed"]) != 1:
            return "a failing suite must FAIL the verdict: rc=%s %s" % (p.returncode, json.dumps(v)[:400])
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
