#!/usr/bin/env bash
# M-3 reference qualification runner (Stage 080 migration reliability roadmap).
#
# Runs, one at a time and each bounded by a timeout, the existing runtime/package
# tests that qualify the selected architecture's known-risk repairs on fixtures,
# plus the two application-level tests on the real v28 candidate tree:
#
#   reused  fragment-behaviour, fragment-cdi-package, repository-effects-runtime,
#           request-body-runtime, location-null-runtime, handler-location-package,
#           handler-validation-package, servlet-redirect-package, verify-runtime
#   new     reference-repository-strategy-runtime (controls, asserted)
#           reference-owner-path-runtime          (measurement of the candidate)
#
# and writes one machine-readable results JSON: every case with its test id,
# whether it executed, the measured outcome, the database and security mode, the
# artifact measured and the evidence.
#
# Exit: 0 every control passed and nothing was skipped; 1 a control failed or a
# suite errored; 2 something was skipped (a SKIP is never a PASS). Candidate
# mismatches are findings reported under "candidate"; they change the exit only
# with --require-candidate-match.
#
# Usage: reference-qualification.sh [--out DIR] [--bundle v28-dest.bundle]
#                                   [--suite-timeout SECONDS] [--require-candidate-match]
# Podman must already be reachable (this script never starts or stops a machine);
# otherwise every container suite is recorded SKIPPED with the reason.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT=""
BUNDLE="${REFQUAL_V28_BUNDLE:-}"
SUITE_TIMEOUT=900
REQUIRE_MATCH=0
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --bundle) BUNDLE="$2"; shift 2 ;;
    --suite-timeout) SUITE_TIMEOUT="$2"; shift 2 ;;
    --require-candidate-match) REQUIRE_MATCH=1; shift ;;
    -h|--help) sed -n '2,32p' "$0"; exit 0 ;;
    *) echo "reference-qualification.sh: unknown argument $1" >&2; exit 64 ;;
  esac
done
if [ -z "$OUT" ]; then
  OUT="$(mktemp -d "${TMPDIR:-/tmp}/reference-qualification.XXXXXX")"
fi
mkdir -p "$OUT"
PY="${PYTHON:-python3}"

export REFQUAL_HERE="$HERE" REFQUAL_OUT="$OUT" REFQUAL_V28_BUNDLE="$BUNDLE" \
       REFQUAL_SUITE_TIMEOUT="$SUITE_TIMEOUT" REFQUAL_REQUIRE_MATCH="$REQUIRE_MATCH"
exec "$PY" - <<'PYEOF'
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

here = Path(os.environ["REFQUAL_HERE"])
out = Path(os.environ["REFQUAL_OUT"])
timeout = int(os.environ["REFQUAL_SUITE_TIMEOUT"])
require_match = os.environ["REFQUAL_REQUIRE_MATCH"] == "1"
sys.path.insert(0, str(here))
import reference_qualification as rq  # noqa: E402
import test_runtime_fixture as rt  # noqa: E402

# test id, script, reused?, role, database, security mode, what it qualifies
SUITES = [
    ("fragment-behaviour", "fragment-behaviour.test.py", True, "control", "none (compiler model)", "n/a",
     "stub fragment bodies (throw, empty mutator, placeholder, hidden helper, delegation cycle) refused structurally; selected-behaviour rows rendered"),
    ("fragment-cdi-package", "fragment-cdi-package.test.py", True, "control", "none (augmentation)", "n/a",
     "duplicate beans refused by augmentation and the structural check; @Typed delegates wired to the generated repositories"),
    ("repository-effects-runtime", "repository-effects-runtime.test.py", True, "control", "postgresql", "n/a",
     "committed write effects read back; no-op writes, remove-first flush order, routed-back recursion and throwing placeholders rejected (specimen-agnostic twin)"),
    ("request-body-runtime", "request-body-runtime.test.py", True, "control", "none (in-memory store)", "n/a",
     "omitted/null/empty/invalid request-body cells under generateJsonCreator false/true"),
    ("location-null-runtime", "location-null-runtime.test.py", True, "control", "postgresql", "n/a",
     "Location built from a null id: bare build 500 after commit vs Spring's empty segment"),
    ("handler-location-package", "handler-location-package.test.py", True, "control", "none", "n/a",
     "@Context UriInfo handler parameter; Location under a non-root application path"),
    ("handler-validation-package", "handler-validation-package.test.py", True, "control", "none (in-memory store)", "n/a",
     "BindingResult translation polarity and ||, kept @Valid, errors header, generated body"),
    ("servlet-redirect-package", "servlet-redirect-package.test.py", True, "control", "none", "n/a",
     "servlet redirect recipe: absolute Location under the root path, SpEL field refused"),
    ("verify-runtime", "verify-runtime.test.py", True, "control", "none", "n/a",
     "boot gate binds evidence to the artifact it was asked to verify"),
    ("reference-repository-strategy-runtime", "reference-repository-strategy-runtime.test.py", False, "control",
     "postgresql", "disabled", "selected repository strategy on the real candidate: reference port accepted; routed-back, throwing, no-op, duplicate beans rejected"),
    ("reference-owner-path-runtime", "reference-owner-path-runtime.test.py", False, "measurement",
     "postgresql", "disabled+enabled", "Owner CRUD path, validation, collections, Location, root path, CORS, basic auth on the candidate vs the frozen source"),
]
NEEDS_PODMAN = {"repository-effects-runtime", "location-null-runtime", "reference-repository-strategy-runtime",
                "reference-owner-path-runtime"}

started = dt.datetime.now(dt.timezone.utc)
podman_ok, podman_why = rq.podman_ready()
suites, cases = [], []
for tid, script, reused, role, db, mode, what in SUITES:
    rec = {"test_id": tid, "script": script, "reused": reused, "role": role, "db": db, "mode": mode,
           "qualifies": what}
    if tid in NEEDS_PODMAN and not podman_ok:
        rec.update(executed=False, outcome="SKIPPED", reason="podman unavailable: %s" % podman_why, seconds=0.0)
        suites.append(rec)
        print("%-40s SKIPPED  %s" % (tid, rec["reason"]), flush=True)
        continue
    argv = [sys.executable, str(here / script)]
    res_path = out / ("%s.results.json" % tid)
    if tid.startswith("reference-"):
        argv += ["--results", str(res_path), "--keep", str(out / tid)]
    t0 = time.time()
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=dict(os.environ))
        rc, text = p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired as exc:
        rc, text = 124, "TIMEOUT after %ds\n%s" % (timeout, (exc.stdout or b"")[-2000:] if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
    secs = round(time.time() - t0, 1)
    (out / ("%s.log" % tid)).write_text(text, encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    skip = next((ln for ln in lines if ln.startswith("SKIP:")), "")
    ok_line = next((ln for ln in lines if ln.startswith("OK:") or ln.startswith("MEASURED:")), "")
    if rc == 124:
        outcome = "TIMEOUT"
    elif rc != 0:
        outcome = "FAIL"
    elif skip:
        outcome = "SKIPPED"
    elif ok_line.startswith("MEASURED:"):
        outcome = "MEASURED"
    elif ok_line:
        outcome = "PASS"
    else:
        outcome = "FAIL"
    rec.update(executed=outcome not in ("SKIPPED",), outcome=outcome, seconds=secs, exit_code=rc,
               summary=(skip or ok_line or (lines[-1] if lines else ""))[:1200], log=str(out / ("%s.log" % tid)))
    if skip:
        rec["reason"] = skip
    suites.append(rec)
    print("%-40s %-9s %6.1fs  %s" % (tid, outcome, secs, rec["summary"][:160]), flush=True)
    if res_path.is_file():
        detail = json.loads(res_path.read_text(encoding="utf-8"))
        for row in detail.get("rows") or []:
            cases.append(row)
    else:
        cases.append({"case": tid, "test_id": tid, "executed": rec["executed"], "outcome": outcome, "db": db,
                      "mode": mode, "artifact": {"fixture": "fixtures/%s" % tid if (rt.FIXTURES / tid).is_dir() else script},
                      "evidence": {"summary": rec["summary"], "log": rec["log"]}})

# the candidate's measured contract, grouped by what differs
owner = [c for c in cases if c["test_id"].startswith("reference-owner-path-runtime::")
         and c["case"] not in ("candidate-build", "package", "clean-generation", "source-engine-sensitivity")]
counts = {}
by_class = {}
for c in owner:
    counts[c["outcome"]] = counts.get(c["outcome"], 0) + 1
    if c["outcome"] == "MISMATCH":
        cls = tuple(c["evidence"].get("difference_classes") or [])
        by_class.setdefault(" + ".join(cls), []).append("%s[%s]" % (c["test_id"].split("::")[1], c["mode"]))
if owner:
    candidate = {"tree": (owner[0].get("artifact") or {}).get("candidate_tree"),
                 "measured_tree_note": "v28 2c798e60 + servlet-redirect-response recipe patch only",
                 "counts": counts, "mismatch_by_difference": by_class,
                 "verdict": "EQUIVALENT on the measured corpus" if not counts.get("MISMATCH") and counts.get("MATCH")
                 else "NOT EQUIVALENT (%d mismatching steps)" % counts.get("MISMATCH", 0)}
else:
    candidate = {"verdict": "NOT MEASURED"}

controls = [s for s in suites if s["role"] == "control"]
failed = [s["test_id"] for s in suites if s["outcome"] in ("FAIL", "TIMEOUT")]
skipped = [s["test_id"] for s in suites if s["outcome"] == "SKIPPED"]
if failed:
    status = "FAIL"
elif skipped:
    status = "INCOMPLETE (skipped: %s)" % ", ".join(skipped)
else:
    status = "CONTROLS PASS"
result = {
    "schema": "rhoai3.reference-qualification-results/v1",
    "note": "component qualification on fixtures plus one application-level measurement of a CANDIDATE tree; "
            "it does not prove full application behaviour. A SKIPPED suite is not a pass.",
    "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "finished_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "platform_pin": rt.pin(), "podman": {"ready": podman_ok, "reason": podman_why},
    "corpus_sha256": rq.corpus_sha256(),
    "status": status, "failed": failed, "skipped": skipped,
    "suites": suites, "candidate": candidate, "cases": cases,
}
(out / "results.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print("")
print("candidate: %s" % candidate["verdict"])
for k, v in sorted(by_class.items()):
    print("  %-40s %s" % (k, ", ".join(v)[:400]))
print("status: %s   results: %s" % (status, out / "results.json"))
if failed:
    sys.exit(1)
if skipped:
    sys.exit(2)
if require_match and candidate.get("counts", {}).get("MISMATCH"):
    sys.exit(1)
sys.exit(0)
PYEOF
