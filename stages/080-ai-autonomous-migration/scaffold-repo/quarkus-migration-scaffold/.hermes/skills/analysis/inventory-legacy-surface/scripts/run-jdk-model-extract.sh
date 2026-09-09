#!/usr/bin/env bash
# run-jdk-model-extract: structural extraction over the frozen analysis copy
# with the JDK's own compiler API (javax.lang.model + com.sun.source through
# JavacTask). No third-party dependency: the pinned toolchain JDK is the
# extractor. Fail-closed when the pin (pins.structure_extractor) is missing
# or the running JDK feature release differs from it. Mode full when the
# build receipt has a classpath, else javac attributes with error types and
# the mode is partial.
set -euo pipefail

ROOT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="${2:-}"; shift 2 ;;
    -h|--help) echo "usage: run-jdk-model-extract.sh --root <dest>" >&2; exit 2 ;;
    *) echo "usage: run-jdk-model-extract.sh --root <dest>" >&2; exit 2 ;;
  esac
done
[[ -n "${ROOT}" && -d "${ROOT}" ]] || { echo "FAIL: --root must be an existing directory" >&2; exit 2; }
ROOT="$(cd "${ROOT}" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NORMALIZE="${SCRIPT_DIR}/normalize-structure.py"
JAVA_SRC="${SCRIPT_DIR}/jdk-model/JdkModelExtract.java"
FREEZE="${ROOT}/evidence/producers/freeze.json"
BUILD="${ROOT}/evidence/producers/build.json"
[[ -f "${FREEZE}" ]] || { echo "FAIL: STRUCTURE_NO_FREEZE missing ${FREEZE}" >&2; exit 1; }

# Pin (never chosen here): pins.structure_extractor.version is "jdk-<feature>".
PIN_JSON="$(python3 - "${ROOT}/.hermes/pins.json" <<'PY'
import json, sys
pins = json.load(open(sys.argv[1]))["pins"]
p = pins.get("structure_extractor") or {}
status = "unpinned" if not p or str(p.get("status","")).lower() == "unpinned" or not p.get("version") else "pinned"
print(json.dumps({"status": status, "version": str(p.get("version") or ""), "release": p.get("source_release") or 17}))
PY
)"
PIN_STATUS="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["status"])' "${PIN_JSON}")"
if [[ "${PIN_STATUS}" != "pinned" ]]; then
  python3 "${NORMALIZE}" --root "${ROOT}" --refuse unpinned --reason "structure_extractor pin missing in .hermes/pins.json (the JDK feature release the extractor runs on; the planner never chooses it)" || true
  echo "FAIL: STRUCTURE_UNPINNED — .hermes/pins.json has no structure_extractor version; structural evidence cannot be produced" >&2
  exit 1
fi
V="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["version"])' "${PIN_JSON}")"
RELEASE="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["release"])' "${PIN_JSON}")"

COPY="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["analysis_copy"])' "${FREEZE}")"
[[ -n "${COPY}" && -d "${COPY}" ]] || { echo "FAIL: STRUCTURE_NO_ANALYSIS_COPY freeze receipt names no analysis_copy" >&2; exit 1; }

export JAVA_HOME="${JAVA_HOME_21:-${JAVA_HOME:-}}"
[[ -n "${JAVA_HOME}" ]] && export PATH="${JAVA_HOME}/bin:${PATH}"
command -v javac >/dev/null 2>&1 || {
  python3 "${NORMALIZE}" --root "${ROOT}" --refuse failed --reason "javac not on PATH (a JDK, not a JRE, is the extractor)" || true
  echo "FAIL: STRUCTURE_NO_JDK" >&2; exit 1; }
FEATURE="$(java -XshowSettings:properties -version 2>&1 | awk -F'= ' '/java.specification.version/ {print $2; exit}')"
RUNTIME="$(java -version 2>&1 | head -1)"
if [[ "jdk-${FEATURE}" != "${V}" ]]; then
  python3 "${NORMALIZE}" --root "${ROOT}" --refuse unpinned --reason "running JDK is jdk-${FEATURE} (${RUNTIME}) but pins.structure_extractor is ${V}; the pinned toolchain is the extractor" || true
  echo "FAIL: STRUCTURE_JDK_MISMATCH running jdk-${FEATURE} != pinned ${V}" >&2
  exit 1
fi
WORK="${ROOT}/evidence/structure/.work"
rm -rf "${WORK}"; mkdir -p "${WORK}/classes"
javac -d "${WORK}/classes" "${JAVA_SRC}" >"${WORK}/javac.log" 2>&1 || {
  python3 "${NORMALIZE}" --root "${ROOT}" --refuse failed --reason "JdkModelExtract.java did not compile on ${RUNTIME}: $(tail -2 "${WORK}/javac.log" | tr '\n' ' ')" || true
  echo "FAIL: STRUCTURE_EXTRACTOR_COMPILE" >&2; exit 1; }

CP_ARGS=()
CLASSPATH_FILE="${ROOT}/evidence/build/classpath.txt"
if [[ -f "${BUILD}" ]] && python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get("classpath_available") else 1)' "${BUILD}" && [[ -s "${CLASSPATH_FILE}" ]]; then
  CP_ARGS=(--classpath "${CLASSPATH_FILE}")
fi
RAW="${WORK}/structure.raw.json"
set +e
java -cp "${WORK}/classes" JdkModelExtract --source "${COPY}" --out "${RAW}" --release "${RELEASE}" ${CP_ARGS[@]+"${CP_ARGS[@]}"} 2>"${WORK}/extract.log"
RC=$?
set -e
if [[ "${RC}" -ne 0 || ! -s "${RAW}" ]]; then
  python3 "${NORMALIZE}" --root "${ROOT}" --refuse failed --reason "JdkModelExtract exited ${RC}: $(tail -3 "${WORK}/extract.log" | tr '\n' ' ')" || true
  echo "FAIL: STRUCTURE_EXTRACT_FAILED rc=${RC}" >&2; exit 1
fi
SRC_SHA="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "${JAVA_SRC}")"
python3 "${NORMALIZE}" --root "${ROOT}" --raw "${RAW}" --tool-version "${V}" --tool-sha256 "${SRC_SHA}" --runtime "${RUNTIME}"
