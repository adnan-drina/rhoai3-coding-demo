#!/usr/bin/env bash
# GR2 / AD-016 — orchestrator-owned M3 mint from partition after M2 PLAN done.
# Worker M2 no longer runs create-m3; Lead/orchestrator runs this script.
#
# Usage:
#   bash .hermes/enforcement/dispatch-phase/scripts/mint-m3-wave.sh \
#     --parent <m2_task_id> [--dry-run]
#
# Requires:
#   - evidence/briefs/partition.json (write-once from M2)
#   - evidence/bodies/m3-*.json (or bodies generated here — one per partition story)
#   - M2 parent task id for created_cards attribution
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
PARENT=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --parent)
      PARENT="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      echo "mint-m3-wave: unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

[[ -n "${PARENT}" ]] || {
  echo "usage: mint-m3-wave.sh --parent <m2_task_id> [--dry-run]" >&2
  exit 2
}

die() { echo "mint-m3-wave: $*" >&2; exit 1; }

PARTITION="${ROOT}/evidence/briefs/partition.json"
[[ -f "${PARTITION}" ]] || die "missing ${PARTITION} — run M2 PLAN first"

CREATE="${ROOT}/.hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh"
ASSERT="${ROOT}/.hermes/enforcement/dispatch-phase/scripts/assert-m2b-created-cards-claim.sh"
[[ -x "${CREATE}" || -f "${CREATE}" ]] || die "missing ${CREATE}"
[[ -f "${ASSERT}" ]] || die "missing ${ASSERT}"

# Enumerate story ids from partition (python — no jq required).
mapfile -t STORY_IDS < <(python3 - "${PARTITION}" <<'PY'
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
stories = data.get("stories") or data.get("units") or []
ids = []
for s in stories:
    if isinstance(s, dict):
        sid = s.get("story_id") or s.get("id") or s.get("unit_id")
        if sid:
            ids.append(str(sid))
    elif isinstance(s, str):
        ids.append(s)
for sid in ids:
    print(sid)
PY
)

[[ ${#STORY_IDS[@]} -gt 0 ]] || die "partition has zero stories"

echo "mint-m3-wave: parent=${PARENT} stories=${#STORY_IDS[@]} dry_run=${DRY_RUN}" >&2

for sid in "${STORY_IDS[@]}"; do
  # Normalize S-001 → m3-s-001.json naming used by create path.
  slug="$(python3 -c "import re,sys; s=sys.argv[1].lower().replace('_','-'); print(re.sub(r'^s-','',s) if s.startswith('s-') else s)" "${sid}")"
  body=""
  for cand in \
    "${ROOT}/evidence/bodies/m3-${sid}.json" \
    "${ROOT}/evidence/bodies/m3-${sid,,}.json" \
    "${ROOT}/evidence/bodies/m3-s-${slug}.json" \
    "${ROOT}/evidence/bodies/m3-${slug}.json"
  do
    if [[ -f "${cand}" ]]; then
      body="${cand}"
      break
    fi
  done
  [[ -n "${body}" ]] || die "missing body JSON for story ${sid} under evidence/bodies/"

  title="M3 IMPLEMENT: ${sid}"
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "mint-m3-wave: DRY-RUN would create --title ${title} --body-json ${body} --parent ${PARENT}" >&2
    continue
  fi
  bash "${CREATE}" \
    --title "${title}" \
    --body-json "${body}" \
    --parent "${PARENT}" \
    || die "create-m3-implementer failed for ${sid}"
done

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "OK: mint-m3-wave dry-run (${#STORY_IDS[@]} stories) — orchestrator-owned mint (AD-016/GR2)"
  exit 0
fi

# F8a/F8b — partition set equality + m2b-created-cards-ok.json receipt (name retained).
bash "${ASSERT}" "${ROOT}" "${PARENT}" \
  || die "assert-m2b-created-cards-claim failed"

echo "OK: mint-m3-wave parent=${PARENT} stories=${#STORY_IDS[@]} (orchestrator-owned mint AD-016/GR2)"
