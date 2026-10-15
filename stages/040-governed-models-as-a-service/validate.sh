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
"$SCRIPT_DIR/validate-native.sh" || result=$?
if [[ "$result" == 0 ]]; then marker=pass; else marker=fail; fi
check 'Current native Stage040 readiness' "printf '%s' '$marker'" 'pass'
boundary=0
"$SCRIPT_DIR/validate-gateway-boundary.sh" >/dev/null 2>&1 || boundary=$?
if [[ "$boundary" == 0 ]]; then marker=pass; else marker=fail; fi
check 'MaaS gateway AdminNetworkPolicy boundary (validate-gateway-boundary.sh)' "printf '%s' '$marker'" 'pass'
validation_summary || exit 1
if [[ "$mode" == --functional ]]; then
  "$SCRIPT_DIR/validate-functional.sh"
else
  echo 'Scope: native readiness only; authenticated inference, streaming, traffic and user Studio acceptance remain separate.'
fi
