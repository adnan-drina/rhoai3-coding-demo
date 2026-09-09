#!/usr/bin/env bash
# dest-init consumer: mint M1 ANALYZE (always) and, only when the planner
# activation gate has been passed (.hermes/pins.json pins.planner.activation
# == "activated"), M2 PLAN as a child of M1 with the fixed key m2-plan.
# Never M3. Never M4 (K4 mints those from an ADMITTED receipt). Never
# triage, specify, decompose, swarm, or kanban daemon --force.
set -euo pipefail

ROOT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="${2:-}"
      shift 2
      ;;
    -h|--help)
      echo "usage: autostart-migration.sh --root <project>" >&2
      exit 2
      ;;
    *)
      echo "usage: autostart-migration.sh --root <project>" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${ROOT}" || ! -d "${ROOT}" ]]; then
  echo "FAIL: --root must be an existing directory" >&2
  exit 2
fi

ROOT="$(cd "${ROOT}" && pwd)"
STATUS="${ROOT}/.hermes/AUTOSTART-STATUS"
mkdir -p "${ROOT}/.hermes"
export HERMES_HOME="${HERMES_HOME:-${ROOT}/.hermes/home}"
# Do not prepend HERMES_HOME/bin. hermes is /usr/local/bin/hermes on dest.
HERMES="$(command -v hermes || true)"

write_status() {
  python3 - "$STATUS" <<'PY'
import json, os, sys
path = sys.argv[1]
payload = json.loads(os.environ.get("AUTOSTART_JSON") or "{}")
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2)
    fh.write("\n")
PY
}

fail_status() {
  local reason="$1"
  export AUTOSTART_JSON
  AUTOSTART_JSON="$(python3 -c 'import json,sys; print(json.dumps({"state":"failed","reason":sys.argv[1]}))' "${reason}")"
  write_status
  echo "FAIL: autostart-migration: ${reason}" >&2
  exit 1
}

case "${AUTO_START_MIGRATION:-true}" in
  false|False|FALSE|0|off|OFF|no|NO)
    export AUTOSTART_JSON
    AUTOSTART_JSON="$(python3 -c 'import json; print(json.dumps({"state":"skipped","reason":"AUTO_START_MIGRATION off"}))')"
    write_status
    echo "OK: autostart skipped (AUTO_START_MIGRATION off)"
    exit 0
    ;;
esac

if [[ -z "${HERMES}" ]]; then
  fail_status "hermes not on PATH"
fi

# Planner activation (SAD §12). Read, never decided here.
PLANNER_ACTIVATION="$(python3 - "${ROOT}/.hermes/pins.json" <<'PY'
import json, sys
try:
    pins = json.load(open(sys.argv[1], encoding="utf-8")).get("pins") or {}
except Exception:
    pins = {}
p = pins.get("planner") or {}
print("activated" if str(p.get("activation") or "").strip().lower() == "activated" else "not-activated")
PY
)"

M1_BODY='Follow paved-road-m1. skill_view subskills from steps.json in order: freeze-migration-input, capture-build-evidence, inventory-legacy-surface, scan-with-mta, assemble-evidence-bundle. Attach the KEEP artifacts by running .hermes/kernel/kanban_attach.py via terminal (python3 .hermes/kernel/kanban_attach.py --task "$HERMES_KANBAN_TASK" --exec). That script fixes the file set and the 25 MiB cap, so the set is not your decision. The kanban_attach tool does not satisfy the paved-road audit. The original frozen legacy source is the only baseline; do not derive or upgrade it first. A producer that records status unpinned is evidence, not a defect to repair: kanban_block kind=needs_input naming the pin. Happy-path terminator is kanban_request_review with reviewer set to reviewer (pass the reviewer parameter; without it the task is dispatched back to you and the paved-road audit never runs), not kanban_complete. kanban_block for external/platform (MaaS 500, missing key, GPU). Do not invent HTTP routes.'

M2_BODY='Follow paved-road-m2. First step is the activation gate (python3 .hermes/skills/planning/admit-migration-plan/scripts/assert-planner-activated.py --root /projects/modernized); then skill_view bootstrap-destination, build-worklist and admit-migration-plan in that order, then python3 .hermes/kernel/k4_mint.py --root /projects/modernized --exec --verify-board, then skill_view verify-live-kanban-loop. The plan is the work list the tools compute; you never author it. An INCONCLUSIVE admission is a legal stop: kanban_block kind=needs_input naming the BLOCK classes; do not hand-author anything under evidence/planning or verification/, and never edit decisions.yaml. K4 mints exactly one card (the head cluster) and zero unless the receipt is ADMITTED. Happy-path terminator is kanban_request_review with reviewer set to reviewer and created_cards equal to the native t_* list from mint. Never kanban swarm, decompose, link, triage, or daemon --force.'

create_card() {
  local title="$1"
  shift
  "${HERMES}" kanban create --json "${title}" "$@"
}

parse_id() {
  python3 -c 'import json,sys
raw=sys.stdin.read()
blob=json.loads(raw[raw.find("{"):raw.rfind("}")+1] if "{" in raw else raw)
tid=blob.get("task_id") or blob.get("id") or (blob.get("task") or {}).get("id")
if not tid:
    raise SystemExit("missing id")
print(tid)
'
}

M1_JSON="$(
  create_card "M1 ANALYZE" \
    --assignee implementer \
    --workspace "dir:${ROOT}" \
    --max-retries 1 \
    --max-runtime 2h \
    --skill paved-road-m1 \
    --idempotency-key m1-analyze \
    --body "${M1_BODY}"
)" || fail_status "M1 create failed"
M1_ID="$(parse_id <<<"${M1_JSON}")" || fail_status "M1 create JSON missing t_* id"

M2_ID=""
if [[ "${PLANNER_ACTIVATION}" == "activated" ]]; then
  M2_JSON="$(
    create_card "M2 PLAN" \
      --assignee implementer \
      --workspace "dir:${ROOT}" \
      --parent "${M1_ID}" \
      --max-retries 1 \
      --max-runtime 2h \
      --skill paved-road-m2 \
      --idempotency-key m2-plan \
      --body "${M2_BODY}"
  )" || fail_status "M2 create failed"
  M2_ID="$(parse_id <<<"${M2_JSON}")" || fail_status "M2 create JSON missing t_* id"
fi

export AUTOSTART_JSON
AUTOSTART_JSON="$(python3 -c 'import json,sys; print(json.dumps({
  "state": "minted",
  "reason": ("M1 minted; M2 minted as child (planner activated)" if sys.argv[2] else "M1 minted; M2 not minted (planner activation gate not passed; SOLUTION-ARCHITECTURE section 12)"),
  "planner_activation": sys.argv[3],
  "m1_id": sys.argv[1],
  "m2_id": sys.argv[2],
  "argv_m1": ["hermes","kanban","create","--json","M1 ANALYZE","--idempotency-key","m1-analyze"],
  "argv_m2": (["hermes","kanban","create","--json","M2 PLAN","--parent",sys.argv[1],"--idempotency-key","m2-plan"] if sys.argv[2] else []),
}))' "${M1_ID}" "${M2_ID}" "${PLANNER_ACTIVATION}")"
write_status
if [[ -n "${M2_ID}" ]]; then
  echo "OK: autostart minted M1=${M1_ID} M2=${M2_ID} (planner activated)"
else
  echo "OK: autostart minted M1=${M1_ID} (M2 not minted: planner ${PLANNER_ACTIVATION})"
fi
