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
#      present AND mode=acceptance
#   5. when the measure is green and known: the packaging gate (full mvn verify)
#      and the startup gate (that artifact, the decided datasource, bounded) via
#      verify-runtime.py, then a re-measure so their obligations reach the list
#      (--no-runtime skips step 5; a simulator passes it)
# Maven reads the tree's own .mvn/maven.config (-s .mvn/settings.xml: the
# Red Hat GA repository); the bootstrap refuses when that wiring is absent.
# Every tool's outcome is recorded in run.json (mode + per-stage ms); verify.py
# marks a component unknown when its tool did not run. Never repairs anything.
# Diagnostic mode cannot feed advance.py (LOOP_DIAGNOSTIC_NOT_ACCEPTANCE).
set -euo pipefail
ROOT=""
RUNTIME=1
MODE="acceptance"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="${2:-}"; shift 2 ;;
    --mode) MODE="${2:-}"; shift 2 ;;
    --no-runtime) RUNTIME=0; shift ;;
    *) echo "usage: run-verify.sh --root <dest> [--mode acceptance|diagnostic] [--no-runtime]" >&2; exit 2 ;;
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
  GREEN="$(python3 - "${ROOT}" <<'PYEOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]) / "verification" / "loop" / "state.json"
m = (json.loads(p.read_text())).get("measure") or {} if p.is_file() else {}
print("yes" if m.get("known") and all(v == 0 for v in (m.get("tuple") or [1])) else "no")
PYEOF
)"
  if [[ "${GREEN}" == "yes" ]]; then
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
exit "${VERIFY_RC}"
