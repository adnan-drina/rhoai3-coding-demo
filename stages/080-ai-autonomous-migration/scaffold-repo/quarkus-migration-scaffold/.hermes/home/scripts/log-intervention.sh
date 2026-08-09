#!/usr/bin/env bash
# Append one intervention row to the clean-room ledger (AD-class auditability).
# Cited path: migration/interventions.jsonl (under PROJECT / modernized root).
#
# Usage:
#   bash .hermes/home/scripts/log-intervention.sh CLASS TYPE "detail" [json-extra]
#   CLASS = A (harness) | B (nourishment)
#   TYPE  = short snake token (e.g. findings_handoff_land, thin_card)
set -euo pipefail

CLASS="${1:?class A|B required}"
TYPE="${2:?type required}"
DETAIL="${3:?detail required}"
EXTRA_JSON="${4:-{}}"

PROJECT_ROOT="${PROJECT_ROOT:-/projects/modernized}"
if [[ ! -d "${PROJECT_ROOT}/migration" ]]; then
  PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
fi
LEDGER="${PROJECT_ROOT}/migration/interventions.jsonl"
mkdir -p "$(dirname "${LEDGER}")"

case "${CLASS}" in
  A|B) ;;
  *) echo "log-intervention: CLASS must be A or B" >&2; exit 2 ;;
esac

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
# Minimal JSON line; EXTRA_JSON must be a JSON object string.
# Always stamp immutable event_id (AD-010 finding 7 auditability).
python3 - "${LEDGER}" "${TS}" "${CLASS}" "${TYPE}" "${DETAIL}" "${EXTRA_JSON}" <<'PY'
import json, sys, uuid
path, ts, clas, typ, detail, extra = sys.argv[1:7]
try:
    extra_obj = json.loads(extra) if extra.strip() else {}
except Exception as e:
    print(f"log-intervention: bad EXTRA_JSON: {e}", file=sys.stderr)
    sys.exit(2)
if not isinstance(extra_obj, dict):
    print("log-intervention: EXTRA_JSON must be an object", file=sys.stderr)
    sys.exit(2)
if extra_obj.get("reconstructed") in (True, "true", "yes", 1):
    print(
        "log-intervention: reconstructed=true forbidden for live ledger "
        "(INCONCLUSIVE; AD-010 finding 7)",
        file=sys.stderr,
    )
    sys.exit(2)
row = {
    "ts": ts,
    "class": clas,
    "type": typ,
    "detail": detail,
    "event_id": extra_obj.pop("event_id", None) or f"evt_{uuid.uuid4().hex[:16]}",
    **extra_obj,
}
with open(path, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
print(
    f"log-intervention: appended class={clas} type={typ} "
    f"event_id={row['event_id']} -> {path}"
)
PY
