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
    print("OK: qualify-repeatability (%d recorded-evidence cases pass; plan %s identical across two runs, run bindings distinct)"
          % (len(rep["cases"]), cmp_["a"]["plan_fingerprint"][:16]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
