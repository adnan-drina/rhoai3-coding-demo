#!/usr/bin/env bash
# Minimum M4/M5 gate runner floor (R-HX.9 Phase-2) — NOT full AD-010 release_qualified.
# Usage: run-m4-floor.sh <product-root> [base-url]
# Env: M4_PORT (default 8080), M4_SMOKE_PATHS (space-separated, default /q/health),
#      M4_SKIP_PACKAGE=1 to skip mvn package, M4_JAR override, JAVA_HOME
set -euo pipefail

PRODUCT_ROOT="${1:-}"
BASE_URL_OVERRIDE="${2:-}"
if [[ -z "${PRODUCT_ROOT}" || ! -d "${PRODUCT_ROOT}" ]]; then
  echo "usage: $0 <product-root> [base-url]" >&2
  exit 2
fi
PRODUCT_ROOT="$(cd "${PRODUCT_ROOT}" && pwd)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRITE_RECEIPT="${SCRIPT_DIR}/write-receipt.py"
CHECK_RECEIPTS="${SCRIPT_DIR}/check-m4-floor-receipts.py"
G4_EVAL="$(cd "${SCRIPT_DIR}/../../check-domain-parity/scripts" && pwd)/g4-runtime-parity.py"

RUN_ID="${M4_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
RECEIPT_DIR="${PRODUCT_ROOT}/evidence/receipts/m4-floor/${RUN_ID}"
mkdir -p "${RECEIPT_DIR}"
PORT="${M4_PORT:-8080}"
BASE_URL="${BASE_URL_OVERRIDE:-http://127.0.0.1:${PORT}}"
SMOKE_PATHS="${M4_SMOKE_PATHS:-/q/health}"
# B8 / check-semantics-manifest: health/root-only smoke must not claim endpoint_smoke
SMOKE_CHECK_ID="endpoint_smoke"
SMOKE_CLAIM=""
has_api=0
for _sp in ${SMOKE_PATHS}; do
  case "${_sp}" in
    /api|/*/api|/*/api/*|*/api) has_api=1 ;;
  esac
done
if [[ "${has_api}" != "1" ]]; then
  SMOKE_CHECK_ID="endpoint_smoke_health"
  SMOKE_CLAIM="health/root only"
fi
ROOT_PATH=""
if [[ -f "${PRODUCT_ROOT}/src/main/resources/application.properties" ]]; then
  ROOT_PATH="$(grep -E "^quarkus\.http\.root-path=" "${PRODUCT_ROOT}/src/main/resources/application.properties" | head -1 | cut -d= -f2- || true)"
fi
ROOT_PATH="${ROOT_PATH%/}"
PACKAGE_RC="skipped"
if [[ "${M4_SKIP_PACKAGE:-0}" != "1" ]]; then
  PACKAGE_RC="pending"
fi

log() { printf "[m4-floor] %s\n" "$*"; }

cleanup() {
  if [[ -n "${APP_PID:-}" ]] && kill -0 "${APP_PID}" 2>/dev/null; then
    kill "${APP_PID}" 2>/dev/null || true
    wait "${APP_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# --- 1) package (optional) ---
if [[ "${M4_SKIP_PACKAGE:-0}" != "1" ]]; then
  log "mvn -q -DskipTests package"
  if (cd "${PRODUCT_ROOT}" && mvn -q -DskipTests package ${QUARKUS_PROFILE:+-Dquarkus.profile=${QUARKUS_PROFILE}}); then
    PACKAGE_RC="0"
  else
    PACKAGE_RC="1"
    python3 "${WRITE_RECEIPT}" --out "${RECEIPT_DIR}/boot_health.json" --check boot_health \
      --result FAIL --cmd "mvn -q -DskipTests package" --rc 1 --operand "${PRODUCT_ROOT}" \
      --note "package failed" --package-rc "${PACKAGE_RC}" --adequacy SEMANTIC
    python3 "${WRITE_RECEIPT}" --out "${RECEIPT_DIR}/${SMOKE_CHECK_ID}.json" --check "${SMOKE_CHECK_ID}" \
      --result FAIL --cmd "skipped" --rc 1 --note "boot failed" \
      --smoke-paths "${SMOKE_PATHS}" --claim "${SMOKE_CLAIM}" --adequacy SEMANTIC
    python3 "${WRITE_RECEIPT}" --out "${RECEIPT_DIR}/g4_hook.json" --check g4_hook \
      --result INCONCLUSIVE --cmd "skipped" --rc 0 --note "boot failed" \
      --g4-mode SAMPLE --adequacy ADMISSION
    echo "FAIL: package" >&2
    exit 1
  fi
fi

# --- start app unless BASE_URL already reachable ---
STARTED_LOCAL=0
if curl -sf "${BASE_URL}/q/health" >/dev/null 2>&1 || curl -sf "${BASE_URL}${ROOT_PATH}/q/health" >/dev/null 2>&1; then
  log "using already-running app at ${BASE_URL}"
else
  JAR="${M4_JAR:-}"
  if [[ -z "${JAR}" ]]; then
    JAR="$(find "${PRODUCT_ROOT}/target" -name "*-runner.jar" -o -name "quarkus-run.jar" 2>/dev/null | head -1 || true)"
  fi
  if [[ -z "${JAR}" || ! -f "${JAR}" ]]; then
    python3 "${WRITE_RECEIPT}" --out "${RECEIPT_DIR}/boot_health.json" --check boot_health \
      --result FAIL --cmd "find runner jar" --rc 1 --operand "${PRODUCT_ROOT}/target" \
      --note "no quarkus runner jar" --package-rc "${PACKAGE_RC}" --adequacy SEMANTIC
    python3 "${WRITE_RECEIPT}" --out "${RECEIPT_DIR}/${SMOKE_CHECK_ID}.json" --check "${SMOKE_CHECK_ID}" \
      --result FAIL --cmd "skipped" --rc 1 --smoke-paths "${SMOKE_PATHS}" --claim "${SMOKE_CLAIM}" --adequacy SEMANTIC
    python3 "${WRITE_RECEIPT}" --out "${RECEIPT_DIR}/g4_hook.json" --check g4_hook \
      --result INCONCLUSIVE --cmd "skipped" --rc 0 --g4-mode SAMPLE --adequacy ADMISSION
    echo "FAIL: no runner jar" >&2
    exit 1
  fi
  log "starting ${JAR} on ${PORT}"
  # System properties must precede -jar for Quarkus
  (cd "${PRODUCT_ROOT}" && java -Dquarkus.http.port="${PORT}" ${QUARKUS_PROFILE:+-Dquarkus.profile=${QUARKUS_PROFILE}} -jar "${JAR}" >"${RECEIPT_DIR}/app.log" 2>&1) &
  APP_PID=$!
  STARTED_LOCAL=1
  ok=0
  for _ in $(seq 1 60); do
    if curl -sf "http://127.0.0.1:${PORT}/q/health" >/dev/null 2>&1 \
      || curl -sf "http://127.0.0.1:${PORT}${ROOT_PATH}/q/health" >/dev/null 2>&1; then
      ok=1
      break
    fi
    if ! kill -0 "${APP_PID}" 2>/dev/null; then
      break
    fi
    sleep 2
  done
  BASE_URL="http://127.0.0.1:${PORT}"
  if [[ "${ok}" != "1" ]]; then
    python3 "${WRITE_RECEIPT}" --out "${RECEIPT_DIR}/boot_health.json" --check boot_health \
      --result FAIL --cmd "java -jar ${JAR}" --rc 1 --operand "${BASE_URL}/q/health" \
      --note "health never became ready; see app.log" --package-rc "${PACKAGE_RC}" --health-status fail --adequacy SEMANTIC
    python3 "${WRITE_RECEIPT}" --out "${RECEIPT_DIR}/${SMOKE_CHECK_ID}.json" --check "${SMOKE_CHECK_ID}" \
      --result FAIL --cmd "skipped" --rc 1 --smoke-paths "${SMOKE_PATHS}" --claim "${SMOKE_CLAIM}" --adequacy SEMANTIC
    python3 "${WRITE_RECEIPT}" --out "${RECEIPT_DIR}/g4_hook.json" --check g4_hook \
      --result INCONCLUSIVE --cmd "skipped" --rc 0 --g4-mode SAMPLE --adequacy ADMISSION
    echo "FAIL: boot_health" >&2
    exit 1
  fi
fi

HEALTH_URL="${BASE_URL}/q/health"
if ! curl -sf "${HEALTH_URL}" >/dev/null 2>&1; then
  HEALTH_URL="${BASE_URL}${ROOT_PATH}/q/health"
fi
if curl -sf "${HEALTH_URL}" >/dev/null 2>&1; then
  python3 "${WRITE_RECEIPT}" --out "${RECEIPT_DIR}/boot_health.json" --check boot_health \
    --result PASS --cmd "curl -sf ${HEALTH_URL}" --rc 0 --operand "${HEALTH_URL}" \
    --package-rc "${PACKAGE_RC}" --health-status ok --adequacy SEMANTIC
else
  python3 "${WRITE_RECEIPT}" --out "${RECEIPT_DIR}/boot_health.json" --check boot_health \
    --result FAIL --cmd "curl -sf ${HEALTH_URL}" --rc 1 --operand "${HEALTH_URL}" \
    --package-rc "${PACKAGE_RC}" --health-status fail --adequacy SEMANTIC
  python3 "${WRITE_RECEIPT}" --out "${RECEIPT_DIR}/${SMOKE_CHECK_ID}.json" --check "${SMOKE_CHECK_ID}" \
    --result FAIL --cmd "skipped" --rc 1 --smoke-paths "${SMOKE_PATHS}" --claim "${SMOKE_CLAIM}" --adequacy SEMANTIC
  python3 "${WRITE_RECEIPT}" --out "${RECEIPT_DIR}/g4_hook.json" --check g4_hook \
    --result INCONCLUSIVE --cmd "skipped" --rc 0 --g4-mode SAMPLE --adequacy ADMISSION
  echo "FAIL: boot_health curl" >&2
  exit 1
fi

# --- 2) endpoint smoke ---
smoke_rc=0
smoke_note=""
declare -a smoke_hits=()
for path in ${SMOKE_PATHS}; do
  url="${BASE_URL}${path}"
  # also try with root-path if plain fails
  code="$(curl -s -o /dev/null -w "%{http_code}" "${url}" || true)"
  if [[ "${code}" == "000" || "${code}" == "404" ]] && [[ -n "${ROOT_PATH}" ]]; then
    url="${BASE_URL}${ROOT_PATH}${path}"
    code="$(curl -s -o /dev/null -w "%{http_code}" "${url}" || true)"
  fi
  smoke_hits+=("${path}:${code}")
  if [[ "${code}" != "200" && "${code}" != "401" && "${code}" != "403" ]]; then
    # 401/403 count as reachable for secured endpoints
    if [[ "${code}" -ge 500 || "${code}" == "000" ]]; then
      smoke_rc=1
      smoke_note="bad status ${code} for ${url}"
    fi
  fi
done
if [[ "${smoke_rc}" == "0" ]]; then
  python3 "${WRITE_RECEIPT}" --out "${RECEIPT_DIR}/${SMOKE_CHECK_ID}.json" --check "${SMOKE_CHECK_ID}" \
    --result PASS --cmd "curl smoke ${SMOKE_PATHS}" --rc 0 \
    --operand "${BASE_URL}" --note "hits=${smoke_hits[*]}" \
    --smoke-paths "${SMOKE_PATHS}" --claim "${SMOKE_CLAIM}" --adequacy SEMANTIC
else
  python3 "${WRITE_RECEIPT}" --out "${RECEIPT_DIR}/${SMOKE_CHECK_ID}.json" --check "${SMOKE_CHECK_ID}" \
    --result FAIL --cmd "curl smoke ${SMOKE_PATHS}" --rc 1 \
    --operand "${BASE_URL}" --note "${smoke_note}; hits=${smoke_hits[*]}" \
    --smoke-paths "${SMOKE_PATHS}" --claim "${SMOKE_CLAIM}" --adequacy SEMANTIC
fi

# --- 3) G-4 hook ---
PARITY_DIR="${M4_PARITY_DIR:-${PRODUCT_ROOT}/.hermes/skills/gates/check-release-readiness/fixtures/admission/g4-runtime-parity}"
G4_RESULT="INCONCLUSIVE"
G4_NOTE="no product parity.json; SAMPLE fixture admission only"
if [[ -f "${PRODUCT_ROOT}/migration/parity.json" ]]; then
  # thin product parity file → evaluate single dir
  tmp="$(mktemp -d)"
  mkdir -p "${tmp}/known-run"
  cp "${PRODUCT_ROOT}/migration/parity.json" "${tmp}/known-run/parity.json"
  # reuse evaluator internals via python one-liner
  G4_RESULT="$(python3 - <<PY
import sys
from pathlib import Path
sys.path.insert(0, "${SCRIPT_DIR}/../../check-domain-parity/scripts")
# import by path
import importlib.util
spec = importlib.util.spec_from_file_location("g4", "${G4_EVAL}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(mod.evaluate(Path("${tmp}/known-run")))
PY
)"
  G4_NOTE="evaluated product migration/parity.json (g4_mode=SAMPLE)"
elif [[ -d "${PARITY_DIR}/known-good" ]]; then
  # tip/scaffold admission fixtures — prove evaluator wiring, not product parity
  if python3 "${G4_EVAL}" "${PRODUCT_ROOT}" >/dev/null 2>&1 \
    || python3 "${G4_EVAL}" "$(
         d="${SCRIPT_DIR}"
         while [ "$d" != "/" ]; do
           if [ -f "$d/migration.yaml" ]; then printf '%s\n' "$d"; break; fi
           d="$(dirname "$d")"
         done
       )" >/dev/null 2>&1; then
    G4_RESULT="INCONCLUSIVE"
    G4_NOTE="admission fixtures evaluated; product G-4 still SAMPLE/INCONCLUSIVE until harvested parity"
  else
    # still INCONCLUSIVE — floor does not claim ACCEPT from tip fixtures alone
    G4_RESULT="INCONCLUSIVE"
    G4_NOTE="g4 evaluator invoked; no product parity harvest"
  fi
fi
# Map ACCEPT from SAMPLE product harvest to PASS for receipt consumer? Keep literal.
# Floor consumer allows INCONCLUSIVE for g4_hook; REFUSE fails.
case "${G4_RESULT}" in
  ACCEPT) recv=PASS ;;
  REFUSE) recv=REFUSE ;;
  *) recv=INCONCLUSIVE ;;
esac
python3 "${WRITE_RECEIPT}" --out "${RECEIPT_DIR}/g4_hook.json" --check g4_hook \
  --result "${recv}" --cmd "g4-runtime-parity.py" --rc 0 \
  --operand "${PARITY_DIR}" --note "${G4_NOTE}; evaluator=${G4_RESULT}; g4_mode=SAMPLE" \
  --g4-mode SAMPLE --adequacy ADMISSION

# symlink latest
ln -sfn "${RUN_ID}" "${PRODUCT_ROOT}/evidence/receipts/m4-floor/latest" 2>/dev/null || true

log "receipts in ${RECEIPT_DIR}"
python3 "${CHECK_RECEIPTS}" "${RECEIPT_DIR}"
log "done (started_local=${STARTED_LOCAL})"
