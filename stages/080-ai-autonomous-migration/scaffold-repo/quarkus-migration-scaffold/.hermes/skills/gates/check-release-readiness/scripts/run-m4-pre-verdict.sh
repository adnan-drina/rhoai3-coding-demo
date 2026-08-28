#!/usr/bin/env bash
# Architect 151334ZA (a): runner-invoked M4 pre-verdict.
# Snapshot test reports, parse surefire, refuse a pre-specified verdict
# token, then assert-retrievable-tree, run pinned feeding gates (receipt
# writers), assert-pinned-gates-ran, assert-g4-claim-consistency,
# assert-no-fence-evasion.
# Fail closed. Not idle. Not K2. Not dest-push. Not a card pin.
# Architect 091125ZA: feeding gates must run before assert-pinned-gates-ran
# or the receipts dir is empty and the floor REFUSEs regardless of quality.
#
# Usage: run-m4-pre-verdict.sh <product-root>
# Env: M4_CARD_SKILLS — OBJECT when set (Architect 130758ZA dest-8
# override). Default bound-gate list is used when unset.
# Env: M4_CARD_BODY — M4 card body when kanban show is unavailable.
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
SNAP="${SCRIPT_DIR}/snapshot-m4-test-reports.py"
SURE="${SCRIPT_DIR}/assert-surefire-results.py"
BODY="${SCRIPT_DIR}/assert-m4-card-body.py"
TREE="${SCRIPT_DIR}/../../assert-retrievable-tree/scripts/assert-retrievable-tree.py"
PINNED="${SCRIPT_DIR}/../../assert-pinned-gates-ran/scripts/assert-pinned-gates-ran.py"
SPEC_COV="${SCRIPT_DIR}/../../../sdd/check-spec-readiness/scripts/check-partition-coverage.py"
DOMAIN="${SCRIPT_DIR}/../../check-domain-parity/scripts/check-product-tests.py"
TOOLCHAIN="${SCRIPT_DIR}/check-test-toolchain.py"
DETECTOR="${SCRIPT_DIR}/../../assert-no-fence-evasion/scripts/assert-no-fence-evasion.py"
G4="${SCRIPT_DIR}/assert-g4-claim-consistency.py"
RESOLVE="${SCRIPT_DIR}/resolve-m4-work-logs.py"
DEFAULT_SKILLS="check-spec-readiness,check-domain-parity,check-release-readiness,assert-pinned-gates-ran,assert-retrievable-tree"
RECEIPT="${SCRIPT_DIR}/../../assert-pinned-gates-ran/scripts/write-gate-receipt.py"
if [[ -n "${M4_CARD_SKILLS:-}" ]]; then
  echo "FAIL: M4_CARD_SKILLS override is OBJECT (Architect 130758ZA); do not widen or replace card pins" >&2
  exit 1
fi
SKILLS="${DEFAULT_SKILLS}"

run_gate() {
  local gate="$1"
  shift
  local rc=0
  "$@" || rc=$?
  python3 "${RECEIPT}" \
    --root "${PRODUCT_ROOT}" \
    --gate "${gate}" \
    --rc "${rc}" \
    --producer "$1" \
    --task-id "${HERMES_KANBAN_TASK:-}" \
    -- "$@"
  return "${rc}"
}

# Write a runner receipt even when the gate exits non-zero. Silence (no
# receipt) is the refuse; a measured rc belongs on the completion floors.
run_feed_gate() {
  local gate="$1"
  shift
  local rc=0
  "$@" || rc=$?
  python3 "${RECEIPT}" \
    --root "${PRODUCT_ROOT}" \
    --gate "${gate}" \
    --rc "${rc}" \
    --producer "$1" \
    --task-id "${HERMES_KANBAN_TASK:-}" \
    -- "$@"
  return 0
}

python3 "${SNAP}" "${PRODUCT_ROOT}"
python3 "${SURE}" "${PRODUCT_ROOT}"
python3 "${BODY}"
run_gate assert-retrievable-tree python3 "${TREE}" "${PRODUCT_ROOT}"
# Feeding gates before assert-pinned-gates-ran (Architect 091125ZA).
run_feed_gate check-spec-readiness python3 "${SPEC_COV}" "${PRODUCT_ROOT}" \
  --write-receipt evidence/receipts/partition-coverage/latest.json
run_feed_gate check-domain-parity python3 "${DOMAIN}" "${PRODUCT_ROOT}" --write-receipt
run_feed_gate check-release-readiness python3 "${TOOLCHAIN}" "${PRODUCT_ROOT}" --write-receipt
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
echo "OK: run-m4-pre-verdict (snapshot+surefire+card-body + assert-retrievable-tree + pinned feeding gates + assert-pinned-gates-ran + assert-g4-claim-consistency + assert-no-fence-evasion; scanned ${scanned} work log(s))"
