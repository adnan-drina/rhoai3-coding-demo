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
bash "${LOOP}/run-verify.sh" --root "${ROOT}"
python3 "${LOOP}/advance.py" --root "${ROOT}" --baseline --no-mint
