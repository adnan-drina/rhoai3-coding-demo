#!/usr/bin/env bash
# Architect 151334ZA (a): runner-invoked M4 pre-verdict.
# Calls assert-retrievable-tree then assert-pinned-gates-ran then
# assert-no-fence-evasion (Operator E-20260825T074910ZO). Fail closed.
# Not idle. Not K2. Not dest-push. Not a card pin.
#
# Usage: run-m4-pre-verdict.sh <product-root>
# Env: M4_CARD_SKILLS — comma list; default is the bound gate leaves so
# missing env is not a skip.
# Env: FENCE_EVASION_LOG — worker log path. Else HERMES_KANBAN_TASK under
# HERMES_HOME/kanban/logs/<id>.log (default dest HERMES_HOME). Missing both
# is REFUSE, not a skip-as-pass.
set -euo pipefail

PRODUCT_ROOT="${1:-}"
if [[ -z "${PRODUCT_ROOT}" || ! -d "${PRODUCT_ROOT}" ]]; then
  echo "usage: $0 <product-root>" >&2
  exit 2
fi
PRODUCT_ROOT="$(cd "${PRODUCT_ROOT}" && pwd)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE="${SCRIPT_DIR}/../../assert-retrievable-tree/scripts/assert-retrievable-tree.py"
PINNED="${SCRIPT_DIR}/../../assert-pinned-gates-ran/scripts/assert-pinned-gates-ran.py"
DETECTOR="${SCRIPT_DIR}/../../assert-no-fence-evasion/scripts/assert-no-fence-evasion.py"
DEFAULT_SKILLS="check-spec-readiness,check-domain-parity,check-release-readiness,assert-pinned-gates-ran,assert-retrievable-tree"
SKILLS="${M4_CARD_SKILLS:-${DEFAULT_SKILLS}}"

resolve_fence_evasion_log() {
  if [[ -n "${FENCE_EVASION_LOG:-}" ]]; then
    printf '%s\n' "${FENCE_EVASION_LOG}"
    return 0
  fi
  if [[ -n "${HERMES_KANBAN_TASK:-}" ]]; then
    local home="${HERMES_HOME:-/projects/modernized/.hermes/home}"
    printf '%s\n' "${home}/kanban/logs/${HERMES_KANBAN_TASK}.log"
    return 0
  fi
  return 1
}

python3 "${TREE}" "${PRODUCT_ROOT}"
python3 "${PINNED}" "${PRODUCT_ROOT}" --skills "${SKILLS}"

LOG=""
if ! LOG="$(resolve_fence_evasion_log)"; then
  echo "run-m4-pre-verdict: REFUSE silent skip of assert-no-fence-evasion — set FENCE_EVASION_LOG or HERMES_KANBAN_TASK" >&2
  exit 2
fi
python3 "${DETECTOR}" "${LOG}"
echo "OK: run-m4-pre-verdict (assert-retrievable-tree + assert-pinned-gates-ran + assert-no-fence-evasion)"
