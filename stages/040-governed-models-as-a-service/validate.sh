#!/usr/bin/env bash
# Read-only native readiness; real inference and Studio acceptance are separate.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export REPO_ROOT
source "$REPO_ROOT/scripts/shared/validate-lib.sh"
mode="${1:---readiness}"
[[ $# -le 1 && ( "$mode" == --readiness || "$mode" == --functional ) ]] || {
  echo 'Usage: validate.sh [--readiness|--functional]' >&2; exit 1;
}
result=0
python3 "$SCRIPT_DIR/validate-native.py" || result=$?
if [[ "$result" == 0 ]]; then marker=pass; else marker=fail; fi
check 'Current native Stage040 readiness' "printf '%s' '$marker'" 'pass'
validation_summary || exit 1
if [[ "$mode" == --functional ]]; then
  python3 "$SCRIPT_DIR/validate-functional.py"
else
  echo 'Scope: native readiness only; authenticated inference, streaming, traffic and user Studio acceptance remain separate.'
fi
