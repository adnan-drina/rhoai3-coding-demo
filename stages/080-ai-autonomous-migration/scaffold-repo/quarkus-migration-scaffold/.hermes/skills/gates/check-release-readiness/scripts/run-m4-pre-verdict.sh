#!/usr/bin/env bash
# Architect 151334ZA (a): runner-invoked M4 pre-verdict.
# Calls assert-retrievable-tree then assert-pinned-gates-ran then
# assert-no-fence-evasion (Operator E-20260825T074910ZO). Fail closed.
# Not idle. Not K2. Not dest-push. Not a card pin.
#
# Usage: run-m4-pre-verdict.sh <product-root>
# Env: M4_CARD_SKILLS — comma list; default is the bound gate leaves so
# missing env is not a skip.
# Env: FENCE_EVASION_LOGS — colon/newline list of work logs (complete set).
# Env: FENCE_EVASION_LOG — single extra path; land-time only when no task id.
# Env: HERMES_KANBAN_TASK — walk parent-chain logs. Never scan this card
# alone (Operator E-20260825T105656ZO: that is the M4 verdict log).
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
G4="${SCRIPT_DIR}/assert-g4-claim-consistency.py"
RESOLVE="${SCRIPT_DIR}/resolve-m4-work-logs.py"
DEFAULT_SKILLS="check-spec-readiness,check-domain-parity,check-release-readiness,assert-pinned-gates-ran,assert-retrievable-tree"
SKILLS="${M4_CARD_SKILLS:-${DEFAULT_SKILLS}}"

python3 "${TREE}" "${PRODUCT_ROOT}"
python3 "${PINNED}" "${PRODUCT_ROOT}" --skills "${SKILLS}"
python3 "${G4}" "${PRODUCT_ROOT}"

LOGS_TEXT=""
if ! LOGS_TEXT="$(python3 "${RESOLVE}")"; then
  echo "run-m4-pre-verdict: REFUSE silent skip of assert-no-fence-evasion — work logs unresolved" >&2
  exit 2
fi
scanned=0
while IFS= read -r LOG; do
  [[ -n "${LOG}" ]] || continue
  echo "run-m4-pre-verdict: scanning ${LOG}"
  python3 "${DETECTOR}" "${LOG}"
  scanned=$((scanned + 1))
done <<< "${LOGS_TEXT}"
if [[ "${scanned}" -lt 1 ]]; then
  echo "run-m4-pre-verdict: REFUSE silent skip of assert-no-fence-evasion — empty work-log set" >&2
  exit 2
fi
echo "OK: run-m4-pre-verdict (assert-retrievable-tree + assert-pinned-gates-ran + assert-g4-claim-consistency + assert-no-fence-evasion; scanned ${scanned} work log(s))"
