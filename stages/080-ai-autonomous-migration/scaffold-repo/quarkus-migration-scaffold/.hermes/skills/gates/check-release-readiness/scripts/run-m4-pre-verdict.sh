#!/usr/bin/env bash
# Architect 151334ZA (a): runner-invoked M4 pre-verdict.
# Run the generated product parity tests under the harness-owned m4-parity
# profile (ADR-015; nothing else compiles src/parity-test/java, and the M3
# loop must never run them), then:
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
# Env: M4_SKIP_PARITY_BUILD — skip the m4-parity rebuild (admission tests and
# trees with no generated suite). The floors still measure the gap: a
# generated case with no execution record covers no capability.
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
ADMIT="${SCRIPT_DIR}/../../../planning/admit-migration-plan/scripts/verify-admission-receipt.py"
DOMAIN="${SCRIPT_DIR}/../../check-domain-parity/scripts/check-product-tests.py"
TOOLCHAIN="${SCRIPT_DIR}/check-test-toolchain.py"
DETECTOR="${SCRIPT_DIR}/../../assert-no-fence-evasion/scripts/assert-no-fence-evasion.py"
G4="${SCRIPT_DIR}/assert-g4-claim-consistency.py"
RESOLVE="${SCRIPT_DIR}/resolve-m4-work-logs.py"
GENTESTS="${SCRIPT_DIR}/../../generate-product-tests/scripts/generate-product-tests.py"
PARITY_PROFILE="m4-parity"
PARITY_MARKER="rhoai3:generated-tests:begin"
DEFAULT_SKILLS="admit-migration-plan,check-domain-parity,check-release-readiness,assert-pinned-gates-ran,assert-retrievable-tree"
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

# The generated product parity tests (ADR-015) live in src/parity-test/java
# and NOTHING compiles them except the harness-owned m4-parity profile, so
# this phase is the one that executes them: under src/test/java every M3
# verify would run them and a parity finding would revert the step that was
# being verified. The rebuild runs BEFORE the snapshot so the snapshot the
# floors read (evidence/m4-pre-rebuild/test-reports) carries the generated
# cases' surefire XML. It never cleans: `mvn test` only rewrites the reports
# of the classes it re-runs, and dest-5's lesson was `mvn clean`.
# Never fail-fast here: a red generated case must reach the snapshot, where
# assert-surefire-results refuses it as the measurement it is.
# Set only when the m4-parity rebuild actually ran and exited 0: the snapshot
# is then taken --fresh, because the reports under target/ are the ones that
# include the generated cases and an M3 snapshot sitting in evidence/ would
# otherwise make the floors measure a suite that ran as one that never did.
PARITY_BUILT=0

run_parity_build() {
  if [[ -n "${M4_SKIP_PARITY_BUILD:-}" ]]; then
    echo "run-m4-pre-verdict: M4_SKIP_PARITY_BUILD set — the generated parity tests did not run here" >&2
    return 0
  fi
  if [[ ! -f "${PRODUCT_ROOT}/pom.xml" ]] || ! grep -q "${PARITY_MARKER}" "${PRODUCT_ROOT}/pom.xml"; then
    echo "run-m4-pre-verdict: no ${PARITY_PROFILE} block in pom.xml — nothing compiles the generated parity tests; the product-test floor measures that gap" >&2
    return 0
  fi
  if ! command -v mvn >/dev/null 2>&1; then
    echo "run-m4-pre-verdict: mvn is not on PATH — the generated parity tests did not run here; the product-test floor measures that gap" >&2
    return 0
  fi
  local rc=0
  # Maven reads the tree's own .mvn/maven.config (-s .mvn/settings.xml); the
  # profile is ADDED to whatever that configures, never instead of it.
  (
    export JAVA_HOME="${JAVA_HOME_21:-${JAVA_HOME:-}}"
    [[ -n "${JAVA_HOME}" ]] && export PATH="${JAVA_HOME}/bin:${PATH}"
    cd "${PRODUCT_ROOT}" && mvn -B "-P${PARITY_PROFILE}" test
  ) || rc=$?
  echo "run-m4-pre-verdict: mvn -P${PARITY_PROFILE} test rc=${rc} (the generated cases' reports are under target/; a red case is a parity finding the floors read, not a reason to stop before the snapshot)"
  if [[ "${rc}" -eq 0 ]]; then
    PARITY_BUILT=1
  fi
  return 0
}

run_parity_build
# Empty or --fresh; deliberately unquoted so an empty value passes no argument.
SNAP_FRESH=""
if [[ "${PARITY_BUILT}" -eq 1 ]]; then
  SNAP_FRESH="--fresh"
  echo "run-m4-pre-verdict: the ${PARITY_PROFILE} rebuild ran, so the snapshot is taken from THESE reports (--fresh)"
fi
# shellcheck disable=SC2086
python3 "${SNAP}" ${SNAP_FRESH} "${PRODUCT_ROOT}"
python3 "${SURE}" "${PRODUCT_ROOT}"
python3 "${BODY}"
run_gate assert-retrievable-tree python3 "${TREE}" "${PRODUCT_ROOT}"
# Feeding gates before assert-pinned-gates-ran (Architect 091125ZA).
run_feed_gate admit-migration-plan python3 "${ADMIT}" --root "${PRODUCT_ROOT}"
# The generated tests are the harness's, and --check says the bytes on disk
# and the m4-parity block in pom.xml are still the ones it wrote. A weakened
# expectation, a deleted case or a deleted profile is a floor failure carried
# into the verdict by its receipt, never an edit the phase accepts.
run_feed_gate generate-product-tests python3 "${GENTESTS}" --root "${PRODUCT_ROOT}" --check
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
echo "OK: run-m4-pre-verdict (${PARITY_PROFILE} rebuild + snapshot+surefire+card-body + assert-retrievable-tree + pinned feeding gates (generate-product-tests --check included) + assert-pinned-gates-ran + assert-g4-claim-consistency + assert-no-fence-evasion; scanned ${scanned} work log(s))"
