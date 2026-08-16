#!/usr/bin/env bash
# GR2 / AD-016 — orchestrator-owned M3 mint from partition after M2 PLAN done.
# Worker M2 no longer runs create-m3; Lead/orchestrator runs this script.
#
# Usage:
#   bash .hermes/skills/harness/dispatch-phase/scripts/mint-m3-wave.sh \
#     --parent <m2_task_id> [--dry-run]
#
# Requires:
#   - evidence/briefs/partition.json (handover-mint receipt; Path-A authored refuse)
#   - evidence/bodies/m3-*.json (assembled from that receipt)
#   - wave-holder parent task id for created_cards attribution (must not be done)
set -euo pipefail

# SR-2: walk up to migration.yaml — never a parent-count.
resolve_migration_root() {
  local d
  d="$(cd "$(dirname "$0")" && pwd)"
  while [ "$d" != "/" ]; do
    if [ -f "$d/migration.yaml" ]; then
      printf '%s\n' "$d"
      return 0
    fi
    d="$(dirname "$d")"
  done
  echo "cannot find project root (migration.yaml) walking up from $(dirname "$0") (SR-2)" >&2
  return 1
}
ROOT="$(resolve_migration_root)" || exit 1
LINK_GRAPH="${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/read-link-graph.py"
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
[[ -f "${LINK_GRAPH}" ]] || die "missing ${LINK_GRAPH} (BV19-3)"

PARTITION="${ROOT}/evidence/briefs/partition.json"
[[ -f "${PARTITION}" ]] || die "missing ${PARTITION} — run handover-mint.py first"
python3 - "${PARTITION}" <<'PY' || die "PATH_A_PARTITION: evidence/briefs/partition.json is not a handover-mint receipt"
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
try:
    data = json.loads(p.read_text(encoding="utf-8"))
except Exception:
    sys.exit(1)
if not isinstance(data, dict) or data.get("source") != "handover-mint":
    sys.exit(1)
PY

CREATE="${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/create-m3-implementer.sh"
ASSERT="${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/assert-m2b-created-cards-claim.sh"
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

# Architect E-20260814T190216Z — PARK_AT_BIRTH is not durable when the parent
# is already done (HKN-2: dispatcher auto-promotes children). Fail-closed
# before any create, including --dry-run when hermes can answer.
_read_parent_status() {
  hermes kanban show "$1" --json 2>/dev/null \
    | python3 "${LINK_GRAPH}" --print status 2>/dev/null || true
}
if command -v hermes >/dev/null 2>&1; then
  _ps="$(_read_parent_status "${PARENT}")"
  if [[ "${_ps}" == "done" || "${_ps}" == "archived" ]]; then
    die "PARENT_DONE: ${PARENT} status=${_ps} — PARK_AT_BIRTH children auto-promote (HKN-2). Do not --parent a done card; mint under a still-open wave holder."
  fi
  if [[ -z "${_ps}" ]]; then
    die "PARENT_DONE: ${PARENT} status unreadable — fail-closed (cannot prove parent is not done)"
  fi
elif [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "mint-m3-wave: PARENT_DONE guard skipped (no hermes on PATH)" >&2
else
  die "hermes not on PATH"
fi

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
