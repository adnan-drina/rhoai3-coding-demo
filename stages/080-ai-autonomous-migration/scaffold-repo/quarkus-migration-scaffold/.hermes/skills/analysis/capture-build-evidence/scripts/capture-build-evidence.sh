#!/usr/bin/env bash
# capture-build-evidence: warm-up (online) then offline compile on the
# frozen analysis copy. Records; never repairs. Failure is a recorded
# fact (outcome: failure), not a wrapper error.
set -euo pipefail

ROOT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="${2:-}"; shift 2 ;;
    -h|--help) echo "usage: capture-build-evidence.sh --root <dest>" >&2; exit 2 ;;
    *) echo "usage: capture-build-evidence.sh --root <dest>" >&2; exit 2 ;;
  esac
done
[[ -n "${ROOT}" && -d "${ROOT}" ]] || { echo "FAIL: --root must be an existing directory" >&2; exit 2; }
ROOT="$(cd "${ROOT}" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RECEIPT="${ROOT}/evidence/producers/freeze.json"
[[ -f "${RECEIPT}" ]] || { echo "FAIL: BUILD_NO_FREEZE missing ${RECEIPT}; run freeze-migration-input first" >&2; exit 1; }

COPY="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["analysis_copy"])' "${RECEIPT}")"
[[ -n "${COPY}" && -d "${COPY}" ]] || { echo "FAIL: BUILD_NO_ANALYSIS_COPY freeze receipt names no analysis_copy (pass --copy-to to freeze-migration-input)" >&2; exit 1; }
[[ -f "${COPY}/pom.xml" ]] || { echo "FAIL: BUILD_NO_POM ${COPY}/pom.xml missing (non-Maven legacy is not supported by this producer)" >&2; exit 1; }

RAW="${ROOT}/evidence/build"
rm -rf "${RAW}"
mkdir -p "${RAW}"

export JAVA_HOME="${JAVA_HOME_21:-${JAVA_HOME:-}}"
[[ -n "${JAVA_HOME}" ]] && export PATH="${JAVA_HOME}/bin:${PATH}"
java -version >"${RAW}/java-version.txt" 2>&1 || true
mvn -v >"${RAW}/mvn-version.txt" 2>&1 || true

# 1. warm-up (network) — recorded separately. dependency:go-offline alone is
#    not enough: measured live 2026-09-09, it returned 0 and the offline
#    compile still lacked spring-orm / spring-retry / byte-buddy. The warm-up
#    therefore also runs the measured goal itself online once; only the
#    offline pass below is the measurement.
set +e
( cd "${COPY}" && mvn -q -B dependency:go-offline && mvn -q -B compile ) >"${RAW}/warmup.log" 2>&1
echo $? >"${RAW}/warmup.rc"
# 1b. effective pom (network: the help plugin) — the legacy build's resolved
#     dependency versions as XML; the bootstrap carries them over for
#     dependencies the Quarkus BOM does not manage
( cd "${COPY}" && mvn -q -B help:effective-pom "-Doutput=${RAW}/effective-pom.xml" ) >"${RAW}/effective-pom.log" 2>&1
echo $? >"${RAW}/effective-pom.rc"
# 2. offline compile
( cd "${COPY}" && mvn -q -B -o compile ) >"${RAW}/compile.log" 2>&1
echo $? >"${RAW}/compile.rc"
# 3. classpath (offline)
( cd "${COPY}" && mvn -q -B -o dependency:build-classpath "-Dmdep.outputFile=${RAW}/classpath.txt" ) >"${RAW}/classpath.log" 2>&1
echo $? >"${RAW}/classpath.rc"
set -e
# 4. generated source roots after compile
( cd "${COPY}" && find target/generated-sources -maxdepth 1 -mindepth 1 -type d 2>/dev/null | sort ) >"${RAW}/generated-roots.txt" || true

python3 "${SCRIPT_DIR}/emit-build-receipt.py" --root "${ROOT}" --copy "${COPY}" --raw "${RAW}"
