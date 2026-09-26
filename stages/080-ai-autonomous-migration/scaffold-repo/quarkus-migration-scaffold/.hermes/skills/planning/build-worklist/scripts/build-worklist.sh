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
# decisions.loop.plan_semantics v1: the first verification is the controlled
# initial-analysis boundary (run-verify.sh --initial): stale build outputs are
# removed before the baseline and every generated root is regenerated or the
# verification refuses. Absent keeps today's first verification.
VERIFY_ARGS=()
LIB="${SCRIPT_DIR}/../../../../lib"
if [[ -d "${LIB}/planner" ]] && [[ "$(python3 -c 'import sys; sys.path.insert(0, sys.argv[2])
from pathlib import Path
from planner.decisions import load_decisions, plan_semantics
try:
    d = load_decisions(Path(sys.argv[1]))
except Exception:
    d = {}
print(plan_semantics(d))' "${ROOT}" "${LIB}" 2>/dev/null || echo off)" == "v1" ]]; then
  VERIFY_ARGS+=(--initial)
fi
run_phase verify bash "${LOOP}/run-verify.sh" --root "${ROOT}" ${VERIFY_ARGS[@]+"${VERIFY_ARGS[@]}"}
run_phase baseline python3 "${LOOP}/advance.py" --root "${ROOT}" --baseline --no-mint
