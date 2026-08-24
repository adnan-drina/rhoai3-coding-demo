#!/usr/bin/env bash
# Architect 151334ZA (a): runner-invoked M4 pre-verdict.
# Calls assert-retrievable-tree then assert-pinned-gates-ran.
# Fail closed. Not idle. Not K2. Not dest-push.
#
# Usage: run-m4-pre-verdict.sh <product-root>
# Env: M4_CARD_SKILLS — comma list; default is the bound gate leaves so
# missing env is not a skip.
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
DEFAULT_SKILLS="check-spec-readiness,check-domain-parity,check-release-readiness,assert-pinned-gates-ran,assert-retrievable-tree"
SKILLS="${M4_CARD_SKILLS:-${DEFAULT_SKILLS}}"

python3 "${TREE}" "${PRODUCT_ROOT}"
python3 "${PINNED}" "${PRODUCT_ROOT}" --skills "${SKILLS}"
echo "OK: run-m4-pre-verdict (assert-retrievable-tree + assert-pinned-gates-ran)"
