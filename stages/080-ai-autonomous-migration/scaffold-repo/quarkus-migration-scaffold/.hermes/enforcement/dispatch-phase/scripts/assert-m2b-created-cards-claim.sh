#!/usr/bin/env bash
# Deputy E-20260813T221456Z F8a/F8b — partition↔created set equality before M2b complete.
# Usage: assert-m2b-created-cards-claim.sh <root> <parent_task_id>
# Writes evidence/runs/<parent>/m2b-created-cards-ok.json on success (machinery gate).
set -euo pipefail
ROOT="${1:-.}"
PARENT="${2:-}"
[[ -n "${PARENT}" ]] || { echo "usage: $0 <root> <parent_task_id>" >&2; exit 2; }
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/check-created-cards-claim.py" \
  --root "${ROOT}" --parent "${PARENT}" --mode partition
mkdir -p "${ROOT}/evidence/runs/${PARENT}"
python3 - "${ROOT}/evidence/runs/${PARENT}/m2b-created-cards-ok.json" "${PARENT}" <<'PY'
import json, sys, datetime
path, parent = sys.argv[1:3]
payload = {
    "schema": "rhoai3.m2b-created-cards-ok/v1",
    "parent": parent,
    "ok": True,
    "mode": "partition",
    "stamped_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "notes": [
        "Deputy E-20260813T221456Z F8a — partition story_ids == created card story_ids",
        "F8b — enforce-m2b-created-cards-claim.py reclaims done without this receipt",
    ],
}
open(path, "w", encoding="utf-8").write(json.dumps(payload, indent=2) + "\n")
print(path)
PY
