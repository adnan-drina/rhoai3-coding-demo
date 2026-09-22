#!/usr/bin/env bash
# run-verify: the real tools behind verify.py on a destination tree.
#   --mode diagnostic  classpath + JDK diagnostics only (not an acceptance pass)
#   --mode acceptance  (default) full path: tests, MTA rescan, packaging/startup
#   0. warm-up (network, once per verification: dependency:go-offline, then
#      the measured goals online with results discarded) so a pom the loop
#      just changed can be measured offline; recorded
#   1. offline classpath (mvn -o dependency:build-classpath)
#   2. JdkDiagnostics over src/main with that classpath
#   3. mvn -o test only when compilation is clean AND mode=acceptance; FRESH
#      surefire reports (the old ones are deleted first) and the mvn exit
#      status recorded
#   4. destination MTA rescan (mta-rescan-destination.sh) when the CLI is
#      present AND mode=acceptance, on this candidate every time. The
#      first measure slot is measured or declared unknown: MTA analyses
#      source patterns, not bytecode (v9: incidents 4→0 at the first
#      accepted step while 233 compile errors remained). Diagnostic never
#      rescans; incidents stay unknown and cannot feed advance.
#   5. as soon as the measure is KNOWN and the compile count is zero
#      (runtime.trigger=compile-zero, recorded in run.json so the audit says
#      why the gate ran): the packaging gate (full mvn verify) and the startup
#      gate (that artifact, the decided datasource, bounded) via
#      verify-runtime.py, then a re-measure so their obligations reach the list
#      (--no-runtime skips step 5; a simulator passes it). MTA incidents and
#      failing tests do not stop Maven from producing an artifact, so waiting
#      for the whole tuple to be [0,0,0] only delayed the two gates a
#      coordinated multi-file unit is most likely to break.
#   6. the PARITY gate, for a card whose obligation is a parity mismatch
#      (verification/loop/issued.json carries gate=parity, or --parity says
#      so): run-parity.py scoped to the scenarios that card's obligations are
#      made of plus the read oracles of the entry points they belong to, then
#      a re-measure. And, under decisions.loop.runtime_feedback
#      v1, one UNSCOPED sweep on any card whose acceptance verification got the
#      startup gate to pass, bound to that card's candidate: a behavioural
#      failure then enters the next work-list rebuild as a parity obligation
#      immediately instead of waiting for M4 (eleven of the isolated
#      experiment's eighteen defects were invisible to the compiler and fell
#      out of one replay). The sweep is skipped when the tree's receipt is
#      already bound to this candidate digest, so it costs at most one run per
#      candidate. A parity repair leaves the
#      compile/test tuple untouched, so nothing else in this file can say
#      whether it landed -- only the comparison run again can (v9 card
#      t_77cae2b2: the CORS properties the brief asked for were REVERTED
#      because [0,0,0] did not decrease and the obligation was never
#      re-measured). It is not run for any other card: the comparison starts
#      the packaged destination and replays scenarios, and that cost buys
#      nothing on a compile card. The comparison is told which card it is for
#      (--issued): its verdicts are of the CANDIDATE, and step 4 above has
#      already rebuilt the work list on that candidate, so the live seal
#      cannot match it (v9 card t_222c582a).
# Maven reads the tree's own .mvn/maven.config (-s .mvn/settings.xml: the
# Red Hat GA repository); the bootstrap refuses when that wiring is absent.
# Every tool's outcome is recorded in run.json (mode + per-stage ms); verify.py
# marks a component unknown when its tool did not run. Never repairs anything.
# Diagnostic mode cannot feed advance.py (LOOP_DIAGNOSTIC_NOT_ACCEPTANCE).
set -euo pipefail
ROOT=""
RUNTIME=1
MODE="acceptance"
FORCE_PARITY=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="${2:-}"; shift 2 ;;
    --mode) MODE="${2:-}"; shift 2 ;;
    --no-runtime) RUNTIME=0; shift ;;
    --parity) FORCE_PARITY=true; shift ;;
    *) echo "usage: run-verify.sh --root <dest> [--mode acceptance|diagnostic] [--no-runtime] [--parity]" >&2; exit 2 ;;
  esac
done
[[ -n "${ROOT}" && -d "${ROOT}" ]] || { echo "FAIL: --root must be an existing directory" >&2; exit 2; }
[[ "${MODE}" == "acceptance" || "${MODE}" == "diagnostic" ]] || { echo "FAIL: --mode must be acceptance or diagnostic" >&2; exit 2; }
[[ "${MODE}" == "diagnostic" ]] && RUNTIME=0
ROOT="$(cd "${ROOT}" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="${ROOT}/verification/build/.work"
rm -rf "${WORK}"; mkdir -p "${WORK}/classes"
export JAVA_HOME="${JAVA_HOME_21:-${JAVA_HOME:-}}"
[[ -n "${JAVA_HOME}" ]] && export PATH="${JAVA_HOME}/bin:${PATH}"
RELEASE="$(python3 -c 'import json,sys; p=json.load(open(sys.argv[1]))["pins"]; print(p.get("quarkus_platform",{}).get("java_release") or 21)' "${ROOT}/.hermes/pins.json")"
javac -d "${WORK}/classes" "${SCRIPT_DIR}/jdk-diagnostics/JdkDiagnostics.java" >"${WORK}/javac.log" 2>&1 || { echo "FAIL: VERIFY_TOOL_COMPILE" >&2; exit 1; }
# H10 (dest v9 t_56adcd76): a mid-card verification NEVER re-seals admission
# (only advance, rewind, operator-step, refresh and resume do). The receipt's
# digest is taken here and compared at the end: a change means another
# process wrote it while this verification ran, and that is recorded in
# run.json (admission.resealed_during_verify) and said out loud rather than
# discovered as a parked card three minutes later.
ADMISSION_BEFORE="$(sha256sum "${ROOT}/evidence/planning/admission-receipt.json" 2>/dev/null | cut -c1-64)"

now_ms() { python3 -c 'import time; print(int(time.time() * 1000))'; }
T_ALL="$(now_ms)"

RUN="${WORK}/run.json"
set +e
# dependency:go-offline alone leaves compile-time artifacts and the surefire
# provider unfetched (measured live 2026-09-09); run the measured goals online
# once, results discarded, so the offline pass below never fails for want of
# an artifact the network could have supplied.
# Every goal the offline pass runs is run online first: build-classpath pulls
# test-scope transitives (quarkus-bootstrap-gradle-resolver, httpmime) that
# neither go-offline nor `mvn test` fetch (measured live 2026-09-09).
# The warm-up depends only on the build inputs (pom.xml, .mvn/); when they
# are the ones the last successful warm-up saw, the local repository already
# holds everything and the online pass is skipped (v7 item 9: ~60 s per card).
WARM_STAMP="${ROOT}/verification/build/warmup.stamp"
WARM_KEY="$(cat "${ROOT}/pom.xml" "${ROOT}"/.mvn/* 2>/dev/null | sha256sum | cut -c1-64)"
T0="$(now_ms)"
if [[ -f "${WARM_STAMP}" && "$(cat "${WARM_STAMP}")" == "${WARM_KEY}" ]]; then
  echo "warm-up skipped: build inputs unchanged since the last successful warm-up (${WARM_KEY:0:12})" >"${WORK}/warmup.log"
  WARM_RC=0
  WARM_SKIPPED=true
else
  ( cd "${ROOT}" && mvn -q -B dependency:go-offline && mvn -q -B dependency:build-classpath "-Dmdep.outputFile=${WORK}/classpath.warmup.txt" && mvn -q -B -Dmaven.test.failure.ignore=true test ) >"${WORK}/warmup.log" 2>&1
  WARM_RC=$?
  WARM_SKIPPED=false
  [[ "${WARM_RC}" -eq 0 ]] && printf "%s" "${WARM_KEY}" >"${WARM_STAMP}"
fi
WARM_MS="$(( $(now_ms) - T0 ))"
T0="$(now_ms)"
( cd "${ROOT}" && mvn -q -B -o dependency:build-classpath "-Dmdep.outputFile=${WORK}/classpath.txt" ) >"${WORK}/classpath.log" 2>&1
CP_RC=$?
CP_MS="$(( $(now_ms) - T0 ))"
set -e
if [[ "${CP_RC}" -ne 0 && "${WARM_RC}" -ne 0 ]]; then
  # the warm-up failure names the unresolvable artifact; the offline log only says "offline"
  { echo "--- warm-up (rc ${WARM_RC}) ---"; cat "${WORK}/warmup.log"; echo "--- offline classpath (rc ${CP_RC}) ---"; cat "${WORK}/classpath.log"; } >"${WORK}/classpath.combined.log"
  mv "${WORK}/classpath.combined.log" "${WORK}/classpath.log"
fi
DIAG="${WORK}/diagnostics.json"
DIAG_RC=0
T0="$(now_ms)"
if [[ "${CP_RC}" -ne 0 || ! -s "${WORK}/classpath.txt" ]]; then
  python3 - "${DIAG}" "${WORK}/classpath.log" <<'PYEOF'
import json, sys
lines = open(sys.argv[2], encoding="utf-8", errors="replace").read().strip().splitlines()
errors = [l for l in lines if l.startswith("[ERROR]") and not l.startswith("[ERROR] [Help") and l.strip("[ERROR] ")]
tail = (errors or lines)[:12]
json.dump({"schema": "rhoai3.diagnostics/v1", "files": 0, "classpath_entries": 0, "success": False, "diagnostics": [], "errors": 0, "build_unresolvable": True, "reason": "mvn dependency:build-classpath failed: " + " | ".join(l[:240] for l in tail)}, open(sys.argv[1], "w"))
PYEOF
else
  set +e
  java -cp "${WORK}/classes" JdkDiagnostics --source "${ROOT}" --out "${DIAG}" --classpath "${WORK}/classpath.txt" --release "${RELEASE}" 2>"${WORK}/diag.log"
  DIAG_RC=$?
  set -e
  [[ "${DIAG_RC}" -eq 0 && -s "${DIAG}" ]] || { echo "FAIL: VERIFY_DIAGNOSTICS_RUN rc=${DIAG_RC}" >&2; exit 1; }
fi
DIAG_MS="$(( $(now_ms) - T0 ))"
ERRORS="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["errors"] + (1 if d.get("build_unresolvable") else 0))' "${DIAG}")"

TEST_ARGS=()
TEST_RC=""
TEST_RAN=false
TEST_MS=0
if [[ "${MODE}" == "acceptance" && "${ERRORS}" == "0" ]]; then
  # fresh reports only: a stale surefire report must never be read as this run's result
  rm -rf "${ROOT}/target/surefire-reports"
  T0="$(now_ms)"
  set +e
  ( cd "${ROOT}" && mvn -q -B -o test ) >"${WORK}/test.log" 2>&1
  TEST_RC=$?
  set -e
  TEST_RAN=true
  TEST_MS="$(( $(now_ms) - T0 ))"
  mkdir -p "${ROOT}/target/surefire-reports"
  TEST_ARGS=(--surefire-dir "${ROOT}/target/surefire-reports" --test-rc "${TEST_RC}")
fi

FIND_ARGS=()
RESCAN_RC=""
RESCAN_RAN=false
RESCAN_MS=0
RESCAN="${SCRIPT_DIR}/../../../analysis/scan-with-mta/scripts/mta-rescan-destination.sh"
if [[ "${MODE}" == "acceptance" ]] && { command -v mta-cli >/dev/null 2>&1 || command -v kantra >/dev/null 2>&1; }; then
  T0="$(now_ms)"
  set +e
  bash "${RESCAN}" "${ROOT}" >"${WORK}/rescan.log" 2>&1
  RESCAN_RC=$?
  set -e
  RESCAN_MS="$(( $(now_ms) - T0 ))"
  if [[ "${RESCAN_RC}" -eq 0 && -s "${ROOT}/verification/mta-rescan/findings.json" ]]; then
    RESCAN_RAN=true
    FIND_ARGS=(--findings "${ROOT}/verification/mta-rescan/findings.json")
  else
    echo "WARN: destination rescan failed (rc=${RESCAN_RC}, see ${WORK}/rescan.log); incidents are UNKNOWN for this verification" >&2
  fi
elif [[ "${MODE}" == "acceptance" ]]; then
  echo "WARN: no MTA CLI on PATH; incidents are UNKNOWN for this verification (the loop cannot advance)" >&2
fi

# Did Maven itself fail to COMPILE? The JDK checker is an offline oracle over a
# source set we choose; Maven compiles the source roots the pom registers. When
# the two disagree the checker can be greener than the build (measured live
# 2026-09-10 on pilot v7: the generator wrote DTOs to src/gen/java, the pom
# registered src/main/java, Maven failed at default-compile on missing DTOs and
# the checker -- which walked the generated tree directly -- reported zero
# errors). The measure treats that disagreement as unknown, never as clean.
MVN_COMPILE_FAILED=false
MVN_COMPILE_DETAIL=""
for L in "${WORK}/test.log" "${WORK}/warmup.log"; do
  [[ -s "${L}" ]] || continue
  if grep -qE "maven-compiler-plugin:[^ ]*:(compile|testCompile) \(default-(compile|testCompile)\).*Compilation failure" "${L}"; then
    MVN_COMPILE_FAILED=true
    MVN_COMPILE_DETAIL="$(grep -oE "maven-compiler-plugin:[^ ]*:(compile|testCompile) \(default-(compile|testCompile)\)" "${L}" | head -1)"
    break
  fi
done

TOTAL_MS="$(( $(now_ms) - T_ALL ))"
export VERIFY_MODE="${MODE}" WARM_RC CP_RC DIAG_RC TEST_RAN TEST_RC RESCAN_RAN RESCAN_RC WARM_SKIPPED
export WARM_MS CP_MS DIAG_MS TEST_MS RESCAN_MS TOTAL_MS
python3 - "${RUN}" "${MVN_COMPILE_FAILED}" "${MVN_COMPILE_DETAIL}" <<'PYEOF'
import json, os, sys
def rc(v):
    return int(v) if v not in ("", None) else None
def ms(k):
    v = os.environ.get(k) or "0"
    try:
        return int(v)
    except ValueError:
        return 0
doc = {"schema": "rhoai3.verify-run/v1",
       "mode": os.environ.get("VERIFY_MODE") or "acceptance",
       "warmup": {"ran": True, "rc": rc(os.environ.get("WARM_RC")), "skipped": os.environ.get("WARM_SKIPPED") == "true", "ms": ms("WARM_MS")},
       "classpath": {"ran": True, "rc": rc(os.environ.get("CP_RC")), "ms": ms("CP_MS")},
       "diagnostics": {"ran": True, "rc": rc(os.environ.get("DIAG_RC")), "ms": ms("DIAG_MS")},
       "tests": {"ran": os.environ.get("TEST_RAN") == "true", "rc": rc(os.environ.get("TEST_RC")), "ms": ms("TEST_MS")},
       "rescan": {"ran": os.environ.get("RESCAN_RAN") == "true", "rc": rc(os.environ.get("RESCAN_RC")), "ms": ms("RESCAN_MS")},
       "maven_compile": {"failed": sys.argv[2] == "true", "goal": sys.argv[3]},
       "stages_ms": {"warmup": ms("WARM_MS"), "classpath": ms("CP_MS"), "diagnostics": ms("DIAG_MS"), "tests": ms("TEST_MS"), "rescan": ms("RESCAN_MS"), "runtime": 0},
       "total_ms": ms("TOTAL_MS")}
json.dump(doc, open(sys.argv[1], "w"))
PYEOF
python3 "${SCRIPT_DIR}/verify.py" --root "${ROOT}" --run "${RUN}" --diagnostics "${DIAG}" ${TEST_ARGS[@]+"${TEST_ARGS[@]}"} ${FIND_ARGS[@]+"${FIND_ARGS[@]}"}
VERIFY_RC=$?

# 5. the transition out of the repair loop. An empty compile/test measure means
# the tree compiles and its tests pass; it does not mean the application can be
# built or started. When (and only when) the measure is green and known, run
# the full configured Maven lifecycle and then start that same artifact against
# the decided database, and re-measure so their obligations reach the work
# list. A gate that does not run stays unknown -- never initialised to zero.
# Diagnostic mode never runs this gate.
if [[ "${RUNTIME}" -eq 1 && "${VERIFY_RC}" -eq 0 ]]; then
  RT_TRIGGER="$(python3 - "${ROOT}" <<'PYEOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]) / "verification" / "loop" / "state.json"
m = (json.loads(p.read_text())).get("measure") or {} if p.is_file() else {}
t = list(m.get("tuple") or [])
# THE TRIGGER, named and recorded. The artifact is attemptable as soon as the
# COMPILER is satisfied: MTA incidents and failing tests do not stop Maven from
# producing one, and a packaging or startup regression is exactly what a
# coordinated multi-file unit can cause -- the cheapest moment to catch it is
# the checkpoint that produced it, not the end of the run. The measure must be
# KNOWN: an unrun compiler is not a compile count of zero.
# (tuple = [mandatory_incidents, compile_errors, failing_tests], worklist.MEASURE_KEYS)
print("compile-zero" if m.get("known") and len(t) > 1 and t[1] == 0 else "none")
PYEOF
)"
  export RT_TRIGGER
  python3 - "${RUN}" <<'PYEOF'
import json, os, sys
doc = json.load(open(sys.argv[1]))
doc.setdefault("runtime", {})["trigger"] = os.environ.get("RT_TRIGGER") or "none"
json.dump(doc, open(sys.argv[1], "w"))
PYEOF
  if [[ "${RT_TRIGGER}" != "none" ]]; then
    T0="$(now_ms)"
    set +e
    # a second tree in the same workspace must not start on the first one's
    # port: the boot gate would attribute a listener it did not start
    python3 "${SCRIPT_DIR}/verify-runtime.py" --root "${ROOT}" --port "${VERIFY_BOOT_PORT:-8081}"
    set -e
    RT_MS="$(( $(now_ms) - T0 ))"
    python3 - "${RUN}" "${RT_MS}" <<'PYEOF'
import json, sys
p = sys.argv[1]
ms = int(sys.argv[2])
doc = json.load(open(p))
doc.setdefault("stages_ms", {})["runtime"] = ms
doc["total_ms"] = int(doc.get("total_ms") or 0) + ms
json.dump(doc, open(p, "w"))
PYEOF
    python3 "${SCRIPT_DIR}/verify.py" --root "${ROOT}" --run "${RUN}" --diagnostics "${DIAG}" ${TEST_ARGS[@]+"${TEST_ARGS[@]}"} ${FIND_ARGS[@]+"${FIND_ARGS[@]}"}
    VERIFY_RC=$?
  fi
fi

# 6. the parity gate: the scenario comparison, re-run for THIS card. Asked of
# the issued card, not of the work list -- the obligation is discharged by its
# own scenarios coming back PASS, and no other card pays for it.
# No --dest-url: the startup gate STOPS the application it started
# (verify-runtime.py boot(), SIGTERM then SIGKILL on the process group), so
# there is nothing left running to compare against. The runner starts the same
# packaged artifact itself, against the decided datasource, and stops it again.
PARITY_RUN_PY="${SCRIPT_DIR}/../../../paved-road/paved-road-m4/scripts/run-parity.py"
PARITY_BEFORE="${ROOT}/verification/build/parity-before.json"
PARITY_RECEIPT="${ROOT}/verification/parity/receipt.json"
if [[ "${MODE}" == "acceptance" && "${RUNTIME}" -eq 1 && "${VERIFY_RC}" -eq 0 ]]; then
  PARITY_PLAN="$(python3 - "${ROOT}" "${FORCE_PARITY}" <<'PYEOF'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
force = sys.argv[2] == "true"
sys.path.insert(0, str(root / ".hermes" / "lib"))
from planner.paths import LOOP_ISSUED, PARITY_DIR, VERIFY_BOOT, VERIFY_RUN, WORKLIST  # noqa: E402

PARITY_RECEIPT = PARITY_DIR / "receipt.json"


def doc(rel):
    p = root / rel
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {}


issued = doc(LOOP_ISSUED)
boot = doc(VERIFY_BOOT)
booted = bool(boot.get("ran") and boot.get("rc") == 0 and boot.get("ready"))


def feedback_mode():
    """decisions.loop.runtime_feedback, normalised by planner.decisions.

    The FILE is read directly rather than through load_decisions: that helper
    validates every required decision, and this stage only asks which mode the
    run is in. The completeness of decisions.yaml is admission business
    (MISSING_DECISION), and it is sealed there, so nothing is skipped here.
    Anything unreadable is off -- the mode that changes nothing."""
    try:
        from planner.decisions import runtime_feedback
        from planner.paths import DECISIONS
        from planner.yamlite import load_yaml
        doc = load_yaml(root / DECISIONS)
        return runtime_feedback(doc if isinstance(doc, dict) else {})
    except Exception:
        return "off"


if not force and str(issued.get("gate") or "") != "parity":
    # RUNTIME FEEDBACK: no parity obligation on this card, but the destination
    # just started, so the whole scenario phase is comparable on this candidate
    # and the answer is worth more now than at M4.
    # (no apostrophes in this block: bash parses the body of a heredoc inside
    # a command substitution, and a lone quote would swallow the script)
    if feedback_mode() != "v1" or not booted:
        print("no")
        raise SystemExit(0)
    # the cost guard: a receipt already bound to THIS candidate digest measured
    # this exact tree, so the sweep would replay it for nothing
    want = str(doc(VERIFY_RUN).get("candidate_sha256") or "")
    binding = doc(PARITY_RECEIPT).get("binding") or {}
    if want and str(binding.get("mode") or "") == "candidate" and str(binding.get("candidate_sha256") or "") == want:
        print("done:the parity receipt is already bound to this candidate (%s); the sweep would replay it" % want[:12])
        raise SystemExit(0)
    print("sweep:")
    raise SystemExit(0)
if not booted:
    # the comparison runs the PACKAGED destination; with no artifact that
    # started and became ready there is nothing to compare, and a run that
    # cannot start one measures nothing
    print("skip:the startup gate did not pass in this verification")
    raise SystemExit(0)
wanted = {str(i) for i in (issued.get("items") or [])}
rows = [it for it in (doc(WORKLIST).get("items") or []) if str(it.get("id")) in wanted]
sids = sorted({str(s) for it in rows for s in (it.get("scenarios") or []) if str(s)})
# H3: the entry points the obligations of this card belong to. A scoped run
# re-runs their READ ORACLES beside the scenarios, because a read-oracle
# obligation (no scenario) is re-measured by nothing else (dest v9 t_4d75569c:
# the scoped run left the entry point FAIL record as the baseline had it, and
# the card could discharge its scenario obligation and never its read-oracle
# one). One per line after the head: an entry point id may hold any character
# but a newline. (No apostrophes in this block: see above.)
eps = sorted({str(it.get("entry_point") or "") for it in rows if str(it.get("entry_point") or "")})
print("run:" + ",".join(sids))
for ep in (eps if sids else []):
    print("oracle:" + ep)
PYEOF
)" || PARITY_PLAN="skip:the issued card could not be read"
  # the plan's head is its first line; the lines after it name the read
  # oracles a scoped run re-runs for the card (oracle:<entry point>)
  PLAN_HEAD="${PARITY_PLAN%%$'\n'*}"
  PLAN_ORACLES=()
  while IFS= read -r plan_line; do
    [[ "${plan_line}" == oracle:* ]] && PLAN_ORACLES+=("${plan_line#oracle:}")
  done <<< "${PARITY_PLAN}"
  PARITY_PLAN="${PLAN_HEAD}"
  if [[ "${PARITY_PLAN}" == skip:* ]]; then
    echo "WARN: parity comparison not run (${PARITY_PLAN#skip:}); this card's parity obligation stays UNKNOWN and advance.py cannot accept it" >&2
  fi
  if [[ "${PARITY_PLAN}" == done:* ]]; then
    # not a failure and not this card's obligation: the cost guard. Said out
    # loud so the audit does not read a silent absence as a run.
    echo "parity: runtime-feedback sweep skipped -- ${PARITY_PLAN#done:}"
  fi
  if [[ "${PARITY_PLAN}" == run:* || "${PARITY_PLAN}" == sweep:* ]]; then
    # A card's own comparison is SCOPED to its scenarios; the runtime-feedback
    # sweep is the whole phase, because it is not answering one obligation --
    # it is asking what this candidate did to behaviour at all.
    if [[ "${PARITY_PLAN}" == sweep:* ]]; then
      SIDS=""
      PARITY_TRIGGER="runtime-feedback"
      echo "parity: runtime-feedback sweep (decisions.loop.runtime_feedback v1) -- the startup gate passed, comparing the whole phase on this candidate"
    else
      SIDS="${PARITY_PLAN#run:}"
      PARITY_TRIGGER="issued-card"
    fi
    PARITY_ARGS=()
    # The verdicts this comparison produces are of the CANDIDATE, not of the
    # accepted tree: verify.py above rebuilt the work list on it, so the live
    # seal's worklist digest is the accepted tree's and can never match. The
    # issued card is what the verdicts bind to instead (the candidate digest in
    # run.json, the receipt the card was minted under, the card). Without this,
    # measured on destination v9 card t_222c582a, every scenario came back
    # "receipt not authoritative: worklist digest ... != sealed ...", the
    # composer refused, the stale FAIL stayed on disk and the card was REVERTED
    # -- and so was every parity card.
    PARITY_ISSUED="${ROOT}/verification/loop/issued.json"
    if [[ -f "${PARITY_ISSUED}" ]]; then
      PARITY_ARGS+=(--issued "${PARITY_ISSUED}")
    else
      # --parity with no issued card: an Operator re-measuring the phase on a
      # tree nobody minted a card for. There is no candidate to bind to, and
      # the sealed road is the right one.
      echo "parity: no issued card; the comparison is bound to the seal, not to a candidate"
    fi
    if [[ -n "${SIDS}" ]]; then
      IFS=',' read -r -a SID_ARR <<< "${SIDS}"
      for s in "${SID_ARR[@]}"; do
        [[ -n "${s}" ]] && PARITY_ARGS+=(--scenario "${s}")
      done
      # ... and the read oracles of the card's own entry points, re-run beside
      # them so a read-oracle obligation is re-measured too (H3)
      for ep in ${PLAN_ORACLES[@]+"${PLAN_ORACLES[@]}"}; do
        [[ -n "${ep}" ]] && PARITY_ARGS+=(--read-oracle "${ep}")
      done
      [[ ${#PLAN_ORACLES[@]} -gt 0 ]] && echo "parity: re-running the read oracle(s) of ${#PLAN_ORACLES[@]} entry point(s) of this card beside its scenarios"
    elif [[ "${PARITY_TRIGGER}" == "issued-card" ]]; then
      # a parity obligation whose entry point declares no scenario is a read
      # oracle: it is re-measured by the unscoped run, which compares those
      echo "parity: the issued obligations name no scenario; comparing the whole phase (read oracles included)"
    fi
    # the receipt as it stood BEFORE this candidate's comparison: acceptance
    # asks of it what was already PASSing, so that a repair that breaks another
    # scenario is not accepted. It is the accepted tree's receipt, because the
    # accepted tree's records are what a rejection restored.
    rm -f "${PARITY_BEFORE}"
    [[ -f "${PARITY_RECEIPT}" ]] && cp "${PARITY_RECEIPT}" "${PARITY_BEFORE}"
    T0="$(now_ms)"
    set +e
    python3 "${PARITY_RUN_PY}" --root "${ROOT}" ${PARITY_ARGS[@]+"${PARITY_ARGS[@]}"} >"${WORK}/parity.log" 2>&1
    PARITY_RC=$?
    set -e
    PARITY_MS="$(( $(now_ms) - T0 ))"
    tail -20 "${WORK}/parity.log" || true
    export PARITY_RC PARITY_MS PARITY_SIDS="${SIDS}" PARITY_TRIGGER
    python3 - "${RUN}" "${ROOT}" <<'PYEOF'
import json, os, sys
from pathlib import Path
run_p, root = sys.argv[1], Path(sys.argv[2])
receipt = root / "verification" / "parity" / "receipt.json"
verdict = ""
if receipt.is_file():
    try:
        verdict = str((json.loads(receipt.read_text(encoding="utf-8")) or {}).get("verdict") or "")
    except ValueError:
        verdict = ""
ms = int(os.environ.get("PARITY_MS") or 0)
# which read oracles the runner's own record says it RE-RAN for the card (a
# verdict recorded): read from _run.json rather than from what was asked, so
# run.json says what was measured, never what was requested
rec_p = root / "verification" / "parity" / "_run.json"
reruns = []
if rec_p.is_file():
    try:
        reruns = [str(e) for e in ((json.loads(rec_p.read_text(encoding="utf-8")) or {}).get("read_oracles") or {}).get("rerun") or []]
    except ValueError:
        reruns = []
doc = json.load(open(run_p))
doc.setdefault("runtime", {})["parity"] = {
    "ran": True,
    "rc": int(os.environ.get("PARITY_RC") or 0),
    # WHY it ran: the issued card's own obligation, or the runtime-feedback
    # sweep. Both are of the candidate and both bind to the issued card; only
    # the first is scoped, and only the first discharges an obligation.
    "trigger": os.environ.get("PARITY_TRIGGER") or "issued-card",
    "scoped": bool([s for s in (os.environ.get("PARITY_SIDS") or "").split(",") if s]),
    "scenarios": [s for s in (os.environ.get("PARITY_SIDS") or "").split(",") if s],
    # H3: the entry points whose read oracle the scoped run re-ran for this
    # card; the work list and acceptance count them as re-measured
    "read_oracles_rerun": sorted(reruns),
    "receipt_verdict": verdict,
    "ms": ms,
}
doc.setdefault("stages_ms", {})["parity"] = ms
doc["total_ms"] = int(doc.get("total_ms") or 0) + ms
json.dump(doc, open(run_p, "w"))
PYEOF
    # re-measure: the comparison rewrote the verdicts the work list reads, so
    # the obligations it still reports are the ones this candidate left
    python3 "${SCRIPT_DIR}/verify.py" --root "${ROOT}" --run "${RUN}" --diagnostics "${DIAG}" ${TEST_ARGS[@]+"${TEST_ARGS[@]}"} ${FIND_ARGS[@]+"${FIND_ARGS[@]}"}
    VERIFY_RC=$?
  fi
fi
# The verify count for the issued card and the obligations the rebuilt work
# list still reports of it (recorded in verification/loop/verify-runs.json,
# rendered by brief.py as verify_runs): the stop rule in paved-road-m3 is
# applied from this line, not from the worker's own counting. Recorded only
# for a verification that measured (rc 0); a tool failure is not a run.
if [[ "${VERIFY_RC}" -eq 0 ]]; then
  python3 - "${ROOT}" "${MODE}" "${SCRIPT_DIR}" <<'PYEOF' || echo "WARN: verify count not recorded" >&2
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[3])
from _loop_common import record_verify_run
line = record_verify_run(Path(sys.argv[1]), mode=sys.argv[2]).get("line") or ""
if line:
    print(line)
PYEOF
fi
ADMISSION_AFTER="$(sha256sum "${ROOT}/evidence/planning/admission-receipt.json" 2>/dev/null | cut -c1-64)"
export ADMISSION_BEFORE ADMISSION_AFTER
python3 - "${ROOT}" <<'PYEOF' || true
import json, os, sys
from pathlib import Path
before, after = os.environ.get("ADMISSION_BEFORE") or "", os.environ.get("ADMISSION_AFTER") or ""
p = Path(sys.argv[1]) / "verification" / "build" / "run.json"
if p.is_file():
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        doc = None
    if isinstance(doc, dict):
        doc["admission"] = {"file_sha256_before": before, "file_sha256_after": after, "resealed_during_verify": bool(before) and before != after}
        p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if before and before != after:
    print("WARN: ADMISSION_RESEALED_DURING_VERIFY evidence/planning/admission-receipt.json changed while this verification ran "
          "(file %s -> %s). A verification never re-seals admission; another process did (a previous card's advance.py "
          "outliving its terminal timeout, an Operator step). The parity comparison binds to the receipt the issued card was "
          "minted under, so this card is still judged on its own evidence." % (before[:12], after[:12]), file=sys.stderr)
PYEOF
exit "${VERIFY_RC}"
