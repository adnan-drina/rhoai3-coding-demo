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
        sid = s.get("story_id")
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
  # Identity is the JSON field, not the filename (SR-9).
  body="$(python3 - "${ROOT}/evidence/bodies" "${sid}" <<'PY'
import json, sys
from pathlib import Path
root, want = Path(sys.argv[1]), sys.argv[2]
if not root.is_dir():
    sys.exit(0)
for p in sorted(root.glob("*.json")):
    if p.name.endswith(".sha256.json"):
        continue
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    if isinstance(d.get("body"), dict):
        d = d["body"]
    ident = d.get("identity") if isinstance(d.get("identity"), dict) else {}
    sid = str(ident.get("story_id") or d.get("story_id") or "").strip()
    if sid == want:
        print(p)
        sys.exit(0)
PY
)"
  [[ -n "${body}" ]] || die "missing body JSON with identity.story_id=${sid} under evidence/bodies/"

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
