#!/usr/bin/env bash
# Deputy E-20260813T220250Z F8 — run before M2b parent kanban_complete.
# Usage: assert-m2b-created-cards-claim.sh <root> <parent_task_id> [claimed_id…]
set -euo pipefail
ROOT="${1:?root}"
PARENT="${2:?parent}"
shift 2
CLAIMED=("$@")
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ${#CLAIMED[@]} -eq 0 ]]; then
  # default: all ids from derived stamp
  CLAIM_FILE="${ROOT}/evidence/derived/created-cards-${PARENT}.json"
  mapfile -t CLAIMED < <(python3 -c 'import json,sys; d=json.load(open(sys.argv[1]));
print("\n".join(c.get("id","") for c in (d.get("cards") or []) if isinstance(c,dict) and c.get("id")))' "${CLAIM_FILE}")
fi
exec python3 "${SCRIPT_DIR}/check-created-cards-claim.py" \
  --root "${ROOT}" --parent "${PARENT}" --claimed "${CLAIMED[@]}"
