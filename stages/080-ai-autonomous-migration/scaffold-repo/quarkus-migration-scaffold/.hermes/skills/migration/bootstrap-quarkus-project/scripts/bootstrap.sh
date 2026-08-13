#!/usr/bin/env bash
# Bootstrap destination Quarkus app (CLI preferred, Maven :create fallback).
# Does not overwrite harness tree. Platform GAV from tooling-pins.md only.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../../.." && pwd)"
PINS="${ROOT}/governance/contracts/tooling-pins.md"
MODE="${BOOTSTRAP_MODE:-auto}"
ARTIFACT_ID="${BOOTSTRAP_ARTIFACT_ID:-quarkus-migration-app}"
GROUP_ID="${BOOTSTRAP_GROUP_ID:-com.demo}"
STAGING="${BOOTSTRAP_STAGING:-$(mktemp -d /tmp/qboot.XXXXXX)}"

die() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "missing command: $1"; }

case "${1:-}" in
  -h|--help)
    cat <<'USAGE'
bootstrap.sh — create destination Quarkus app (CLI preferred, Maven fallback).

Env:
  BOOTSTRAP_MODE=auto|cli|maven
  BOOTSTRAP_ARTIFACT_ID (default quarkus-migration-app)
  BOOTSTRAP_GROUP_ID (default com.demo)

Does not overwrite .hermes/, migration/, AGENTS.md, BOOTSTRAP.md.
USAGE
    exit 0
    ;;
esac

[[ -f "${PINS}" ]] || die "missing ${PINS}"

# Parse GAV via a small helper (avoid backticks in this shell script body).
GAV="$(python3 "${ROOT}/.hermes/skills/migration/bootstrap-quarkus-project/scripts/parse-platform-gav.py" "${PINS}")" \
  || die "could not parse platform GAV from tooling-pins.md"

IFS=':' read -r PLAT_GROUP PLAT_ART PLAT_VER <<<"${GAV}"
[[ -n "${PLAT_GROUP}" && -n "${PLAT_ART}" && -n "${PLAT_VER}" ]] || die "bad GAV ${GAV}"

cli_ok() {
  command -v quarkus >/dev/null 2>&1 || return 1
  local cfg="${HOME}/.quarkus/config.yaml"
  [[ -f "${cfg}" ]] || return 1
  python3 "${ROOT}/.hermes/skills/migration/bootstrap-quarkus-project/scripts/check-rh-registry-first.py" "${cfg}"
}

use_cli=0
case "${MODE}" in
  cli) cli_ok || die "BOOTSTRAP_MODE=cli but CLI/RH-registry prereqs failed"; use_cli=1 ;;
  maven) use_cli=0 ;;
  auto) if cli_ok; then use_cli=1; else use_cli=0; fi ;;
  *) die "unknown BOOTSTRAP_MODE=${MODE}" ;;
esac

mkdir -p "${STAGING}"
cd "${STAGING}"

if [[ "${use_cli}" -eq 1 ]]; then
  echo "bootstrap: using quarkus CLI (RH registry-first)"
  need quarkus
  quarkus create app "${GROUP_ID}:${ARTIFACT_ID}" \
    -P "${PLAT_GROUP}:${PLAT_ART}:${PLAT_VER}" \
    --no-code=false
else
  echo "bootstrap: using Maven quarkus:create (CLI absent or prereq fail)"
  need mvn
  mvn -B "io.quarkus:quarkus-maven-plugin:${PLAT_VER}:create" \
    -DprojectGroupId="${GROUP_ID}" \
    -DprojectArtifactId="${ARTIFACT_ID}" \
    -DplatformGroupId="${PLAT_GROUP}" \
    -DplatformArtifactId="${PLAT_ART}" \
    -DplatformVersion="${PLAT_VER}" \
    -Dextensions="rest-jackson"
fi

APP_DIR="${STAGING}/${ARTIFACT_ID}"
[[ -d "${APP_DIR}" ]] || APP_DIR="$(find "${STAGING}" -maxdepth 2 -type d -name "${ARTIFACT_ID}" | head -1)"
[[ -d "${APP_DIR}" ]] || die "create did not produce ${ARTIFACT_ID} under ${STAGING}"

rsync -a --exclude '.hermes' --exclude 'migration' --exclude 'AGENTS.md' \
  --exclude 'BOOTSTRAP.md' --exclude '.git' \
  "${APP_DIR}/" "${ROOT}/"

PIN_CHECK="${ROOT}/.hermes/skills/migration/manage-quarkus-extensions/scripts/check-pom-platform-pins.py"
[[ -f "${PIN_CHECK}" ]] || die "missing ${PIN_CHECK}"
echo "NEXT: apply harness pom patch (Java 21 / Jacoco / surefire) then:"
echo "  python3 ${PIN_CHECK} ${ROOT}"
echo "NEXT: evidence-driven extensions via manage-quarkus-extensions"
echo "bootstrap: staged from ${APP_DIR} into ${ROOT}"
