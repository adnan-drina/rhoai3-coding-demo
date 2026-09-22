#!/usr/bin/env bash
# build-worklist: first verification of the bootstrapped tree + the loop
# baseline. Runs the real verifier (JDK diagnostics, surefire, MTA rescan)
# through fix-until-green/run-verify.sh, then records step 0.
set -euo pipefail
ROOT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="${2:-}"; shift 2 ;;
    *) echo "usage: build-worklist.sh --root <dest>" >&2; exit 2 ;;
  esac
done
[[ -n "${ROOT}" && -d "${ROOT}" ]] || { echo "FAIL: --root must be an existing directory" >&2; exit 2; }
ROOT="$(cd "${ROOT}" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOOP="${SCRIPT_DIR}/../../../migration/fix-until-green/scripts"
[[ -f "${ROOT}/evidence/producers/bootstrap.json" ]] || { echo "FAIL: WORKLIST_NO_BOOTSTRAP run bootstrap-destination first" >&2; exit 1; }
run_phase() {
  local phase="$1" rc
  shift
  echo "WORKLIST_PHASE: ${phase} started"
  if "$@"; then
    echo "WORKLIST_PHASE: ${phase} passed"
  else
    rc=$?
    echo "FAIL: WORKLIST_PHASE phase=${phase} exit=${rc}; later phases did not run. Inspect this invocation's output and ${ROOT}/verification; do not run a second Maven build to diagnose the wrapper." >&2
    return "${rc}"
  fi
}
run_phase verify bash "${LOOP}/run-verify.sh" --root "${ROOT}"
run_phase baseline python3 "${LOOP}/advance.py" --root "${ROOT}" --baseline --no-mint
