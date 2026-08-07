#!/usr/bin/env bash
# Free-primitives Boot 2→3 composite (W2 §12).
# Run with cwd = derived legacy tree (DERIVE_UPGRADE_CMD context).
#
# Env:
#   COMPOSITE_ROOT   tree to transform (default: cwd)
#   APPLY_LOG_PATH   where to write free-primitives-apply-log.json
#   SKIP_MTA_JAKARTA=1  force package-map fallback (skip mta-cli)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
export COMPOSITE_ROOT="${COMPOSITE_ROOT:-$(pwd)}"
export PYTHONPATH="${HERE}${PYTHONPATH:+:$PYTHONPATH}"

echo "free-primitives-boot3: COMPOSITE_ROOT=${COMPOSITE_ROOT}"
echo "free-primitives-boot3: APPLY_LOG_PATH=${APPLY_LOG_PATH:-<default under COMPOSITE_ROOT>}"

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

# Order: jakarta slice → parent bump → Boot-specific POM → Security → generator
run_rule "${HERE}/rules/r00_javax_to_jakarta.py"
run_rule "${HERE}/rules/r10_bump_boot_parent.py"
run_rule "${HERE}/rules/r20_mysql_connector.py"
run_rule "${HERE}/rules/r30_jaxb_api.py"
run_rule "${HERE}/rules/r40_security6_wsca.py"
run_rule "${HERE}/rules/r50_openapi_jakarta.py"

echo "free-primitives-boot3: OK"
