#!/usr/bin/env bash
# run-verify: the real tools behind verify.py on a destination tree.
#   0. warm-up (network, once per verification: dependency:go-offline, then
#      the measured goals online with results discarded) so a pom the loop
#      just changed can be measured offline; recorded
#   1. offline classpath (mvn -o dependency:build-classpath)
#   2. JdkDiagnostics over src/main with that classpath
#   3. mvn -o test only when compilation is clean; FRESH surefire reports
#      (the old ones are deleted first) and the mvn exit status recorded
#   4. destination MTA rescan (mta-rescan-destination.sh) when the CLI is present
# Maven reads the tree's own .mvn/maven.config (-s .mvn/settings.xml: the
# Red Hat GA repository); the bootstrap refuses when that wiring is absent.
# Every tool's outcome is recorded in run.json; verify.py marks a component
# unknown when its tool did not run. Never repairs anything.
set -euo pipefail
ROOT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="${2:-}"; shift 2 ;;
    *) echo "usage: run-verify.sh --root <dest>" >&2; exit 2 ;;
  esac
done
[[ -n "${ROOT}" && -d "${ROOT}" ]] || { echo "FAIL: --root must be an existing directory" >&2; exit 2; }
ROOT="$(cd "${ROOT}" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="${ROOT}/verification/build/.work"
rm -rf "${WORK}"; mkdir -p "${WORK}/classes"
export JAVA_HOME="${JAVA_HOME_21:-${JAVA_HOME:-}}"
[[ -n "${JAVA_HOME}" ]] && export PATH="${JAVA_HOME}/bin:${PATH}"
RELEASE="$(python3 -c 'import json,sys; p=json.load(open(sys.argv[1]))["pins"]; print(p.get("quarkus_platform",{}).get("java_release") or 21)' "${ROOT}/.hermes/pins.json")"
javac -d "${WORK}/classes" "${SCRIPT_DIR}/jdk-diagnostics/JdkDiagnostics.java" >"${WORK}/javac.log" 2>&1 || { echo "FAIL: VERIFY_TOOL_COMPILE" >&2; exit 1; }

RUN="${WORK}/run.json"
set +e
( cd "${ROOT}" && mvn -q -B dependency:go-offline ) >"${WORK}/warmup.log" 2>&1
WARM_RC=$?
( cd "${ROOT}" && mvn -q -B -o dependency:build-classpath "-Dmdep.outputFile=${WORK}/classpath.txt" ) >"${WORK}/classpath.log" 2>&1
CP_RC=$?
set -e
if [[ "${CP_RC}" -ne 0 && "${WARM_RC}" -ne 0 ]]; then
  # the warm-up failure names the unresolvable artifact; the offline log only says "offline"
  { echo "--- warm-up (rc ${WARM_RC}) ---"; cat "${WORK}/warmup.log"; echo "--- offline classpath (rc ${CP_RC}) ---"; cat "${WORK}/classpath.log"; } >"${WORK}/classpath.combined.log"
  mv "${WORK}/classpath.combined.log" "${WORK}/classpath.log"
fi
DIAG="${WORK}/diagnostics.json"
DIAG_RC=0
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
ERRORS="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["errors"] + (1 if d.get("build_unresolvable") else 0))' "${DIAG}")"

TEST_ARGS=()
TEST_RC=""
TEST_RAN=false
if [[ "${ERRORS}" == "0" ]]; then
  # fresh reports only: a stale surefire report must never be read as this run's result
  rm -rf "${ROOT}/target/surefire-reports"
  set +e
  ( cd "${ROOT}" && mvn -q -B -o test ) >"${WORK}/test.log" 2>&1
  TEST_RC=$?
  set -e
  TEST_RAN=true
  mkdir -p "${ROOT}/target/surefire-reports"
  TEST_ARGS=(--surefire-dir "${ROOT}/target/surefire-reports" --test-rc "${TEST_RC}")
fi

FIND_ARGS=()
RESCAN_RC=""
RESCAN_RAN=false
RESCAN="${SCRIPT_DIR}/../../../analysis/scan-with-mta/scripts/mta-rescan-destination.sh"
if command -v mta-cli >/dev/null 2>&1 || command -v kantra >/dev/null 2>&1; then
  set +e
  bash "${RESCAN}" "${ROOT}" >"${WORK}/rescan.log" 2>&1
  RESCAN_RC=$?
  set -e
  if [[ "${RESCAN_RC}" -eq 0 && -s "${ROOT}/verification/mta-rescan/findings.json" ]]; then
    RESCAN_RAN=true
    FIND_ARGS=(--findings "${ROOT}/verification/mta-rescan/findings.json")
  else
    echo "WARN: destination rescan failed (rc=${RESCAN_RC}, see ${WORK}/rescan.log); incidents are UNKNOWN for this verification" >&2
  fi
else
  echo "WARN: no MTA CLI on PATH; incidents are UNKNOWN for this verification (the loop cannot advance)" >&2
fi

python3 - "${RUN}" "${CP_RC}" "${DIAG_RC}" "${TEST_RAN}" "${TEST_RC}" "${RESCAN_RAN}" "${RESCAN_RC}" "${WARM_RC}" <<'PYEOF'
import json, sys
def rc(v):
    return int(v) if v not in ("", None) else None
json.dump({"schema": "rhoai3.verify-run/v1",
           "warmup": {"ran": True, "rc": rc(sys.argv[8])},
           "classpath": {"ran": True, "rc": rc(sys.argv[2])},
           "diagnostics": {"ran": True, "rc": rc(sys.argv[3])},
           "tests": {"ran": sys.argv[4] == "true", "rc": rc(sys.argv[5])},
           "rescan": {"ran": sys.argv[6] == "true", "rc": rc(sys.argv[7])}}, open(sys.argv[1], "w"))
PYEOF
python3 "${SCRIPT_DIR}/verify.py" --root "${ROOT}" --run "${RUN}" --diagnostics "${DIAG}" ${TEST_ARGS[@]+"${TEST_ARGS[@]}"} ${FIND_ARGS[@]+"${FIND_ARGS[@]}"}
