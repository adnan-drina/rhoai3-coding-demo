#!/usr/bin/env python3
"""qualify-repeatability selftest: the recorded-evidence level of the driver
passes every case (the producer-replay cases are their own suites and run in
the release check on their own)."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

DRIVER = Path(__file__).with_name("qualify-repeatability.py")


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
    fresh = _fresh_mode_case()
    if fresh:
        print("FAIL: %s" % fresh, file=sys.stderr)
        return 1
    print("OK: qualify-repeatability (%d recorded-evidence cases pass; plan %s identical across two runs, run bindings distinct; "
          "--fresh equal on two derivations of one source with this golden's objectives and FAIL on two sources)"
          % (len(rep["cases"]), cmp_["a"]["plan_fingerprint"][:16]))
    return 0


def _fresh_mode_case() -> str:
    """--fresh on two derivations of one (synthetic) source: equal, with the
    golden's compatibility objectives composed; on two different sources: a
    FAIL naming the outcomes that differ, never normalised away."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("qualify_repeatability", DRIVER)
    qr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qr)
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


if __name__ == "__main__":
    raise SystemExit(main())
