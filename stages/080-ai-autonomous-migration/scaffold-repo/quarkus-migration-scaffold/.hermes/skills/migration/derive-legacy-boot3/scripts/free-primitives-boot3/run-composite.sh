#!/usr/bin/env bash
# Free-primitives Boot 2→3 composite (W2 §12).
# Run with cwd = derived legacy tree (DERIVE_UPGRADE_CMD context).
#
# Env:
#   COMPOSITE_ROOT   tree to transform (default: cwd)
#   APPLY_LOG_PATH   where to write free-primitives-apply-log.json
#   SKIP_MTA_JAKARTA=1  force package-map fallback (skip mta-cli)
set -euo pipefail

# --dry-run as first arg or DRY_RUN=1: list rules that would run; no python.
if [[ "${1:-}" == "--dry-run" ]]; then
  shift
  DRY_RUN=1
fi
DRY_RUN="${DRY_RUN:-0}"

HERE="$(cd "$(dirname "$0")" && pwd)"
export COMPOSITE_ROOT="${COMPOSITE_ROOT:-$(pwd)}"
export PYTHONPATH="${HERE}${PYTHONPATH:+:$PYTHONPATH}"

echo "free-primitives-boot3: COMPOSITE_ROOT=${COMPOSITE_ROOT}"
echo "free-primitives-boot3: APPLY_LOG_PATH=${APPLY_LOG_PATH:-<default under COMPOSITE_ROOT>}"

RULES=(
  "${HERE}/rules/r00_javax_to_jakarta.py"
  "${HERE}/rules/r10_bump_boot_parent.py"
  "${HERE}/rules/r20_mysql_connector.py"
  "${HERE}/rules/r30_jaxb_api.py"
  "${HERE}/rules/r40_security6_wsca.py"
  "${HERE}/rules/r45_security6_matchers.py"
  "${HERE}/rules/r50_openapi_jakarta.py"
  "${HERE}/rules/r60_springfox_to_springdoc.py"
  "${HERE}/rules/r70_thymeleaf_spring6.py"
)

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "DRY-RUN: free-primitives-boot3 would run ${#RULES[@]} rules:"
  for script in "${RULES[@]}"; do
    echo "DRY-RUN:   $(basename "$script")"
  done
  exit 0
fi

# Fresh apply log for this invocation
if [ -n "${APPLY_LOG_PATH:-}" ]; then
  mkdir -p "$(dirname "${APPLY_LOG_PATH}")"
  rm -f "${APPLY_LOG_PATH}"
fi

run_rule() {
  local script="$1"
  echo "=== $(basename "$script") ==="
  python3 "$script"
}

# Order: jakarta → Boot bump → POM → Security (WSCA then matchers) → generator → thymeleaf
for script in "${RULES[@]}"; do
  run_rule "${script}"
done

echo "free-primitives-boot3: OK"
