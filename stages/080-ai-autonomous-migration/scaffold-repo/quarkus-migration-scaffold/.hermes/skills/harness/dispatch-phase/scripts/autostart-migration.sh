#!/usr/bin/env bash
# dest-init consumer: mint M1 ANALYZE + M2 PLAN. Not M3. Not M4.
# Architect AUTOSTART-MIGRATION-DESIGN.md (195231ZA). Do not kanban daemon --force.
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
path_parent = os.path.dirname(path)
os.makedirs(path_parent, exist_ok=True)
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

M1_BODY='Follow paved-road-m1. skill_view subskills from steps.json. Attach the KEEP artifacts by running .hermes/kernel/kanban_attach.py via terminal (python3 .hermes/kernel/kanban_attach.py --task "$HERMES_KANBAN_TASK" --exec). That script fixes the file set and the 25 MiB cap, so the set is not your decision -- dest-13 attached the derivation manifest instead of the type graph and M2 had no input. The kanban_attach tool does not satisfy the paved-road audit. Happy-path terminator is kanban_request_review with reviewer set to reviewer (pass the reviewer parameter; without it the task is dispatched back to you and the paved-road audit never runs), not kanban_complete. kanban_block for external/platform (MaaS 500, missing key, GPU). Do not invent HTTP routes.'

M2_BODY='Follow paved-road-m2. skill_view subskills from steps.json (speckit-specify, then speckit-plan, then speckit-tasks). Stop. Never speckit-implement. If a named skill is missing, a named command fails, or a named path is absent: stop and kanban_block. Happy-path terminator is kanban_request_review with reviewer set to reviewer (pass the reviewer parameter; without it the task is dispatched back to you and the paved-road audit never runs), not kanban_complete. kanban_block for external/platform (MaaS 500, missing key, GPU). Do not hand-author tasks.md. Consume parent M1 kanban_attachments and evidence findings-handoff.json, entry-point-inventory.json, type-inventory.json, required-extensions.json, mta-findings.json. Author evidence/partition.json. HTTP stories require dest_file and legacy_source. Run check-partition-coverage.py and assert-m2-speckit-conformance.py via terminal -- both are mandated paved-road steps and the audit refuses without them. Convert with k4_convert.py --partition --tasks then mint with k4_mint.py --exec. No factory cards. No verdict token. Every Spec Kit artifact -- spec.md, plan.md, tasks.md, checklists, contracts -- lives under the Spec Kit 0.16.1 feature_directory named in .specify/feature.json (specs/<feature>/). Do not create or write anything under .specify/specs: setup-plan.sh and setup-tasks.sh resolve paths from feature.json, so a spec.md left under .specify/specs makes setup-tasks.sh exit 1. If they disagree, move the file to feature_directory -- do not repoint feature.json at .specify/specs, which would satisfy the readiness check while placing the plan in the tree the harness rejects.'

create_card() {
  local title="$1"
  shift
  "${HERMES}" kanban create --json "${title}" "$@"
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

M1_ID="$(python3 -c 'import json,sys
raw=sys.stdin.read()
blob=json.loads(raw[raw.find("{"):raw.rfind("}")+1] if "{" in raw else raw)
tid=blob.get("task_id") or blob.get("id") or (blob.get("task") or {}).get("id")
if not tid:
    raise SystemExit("missing id")
print(tid)
' <<<"${M1_JSON}")" || fail_status "M1 create JSON missing t_* id"

M2_JSON="$(
  create_card "M2 PLAN" \
    --assignee implementer \
    --workspace "dir:${ROOT}" \
    --max-retries 1 \
    --max-runtime 2h \
    --parent "${M1_ID}" \
    --skill paved-road-m2 \
    --idempotency-key m2-plan \
    --body "${M2_BODY}"
)" || fail_status "M2 create failed"

M2_ID="$(python3 -c 'import json,sys
raw=sys.stdin.read()
blob=json.loads(raw[raw.find("{"):raw.rfind("}")+1] if "{" in raw else raw)
tid=blob.get("task_id") or blob.get("id") or (blob.get("task") or {}).get("id")
if not tid:
    raise SystemExit("missing id")
print(tid)
' <<<"${M2_JSON}")" || fail_status "M2 create JSON missing t_* id"

export AUTOSTART_JSON
AUTOSTART_JSON="$(python3 -c 'import json,sys; print(json.dumps({
  "state": "minted",
  "reason": "M1+M2 minted",
  "m1_id": sys.argv[1],
  "m2_id": sys.argv[2],
  "argv_m1": ["hermes","kanban","create","--json","M1 ANALYZE","--idempotency-key","m1-analyze"],
  "argv_m2": ["hermes","kanban","create","--json","M2 PLAN","--idempotency-key","m2-plan","--parent",sys.argv[1]],
}))' "${M1_ID}" "${M2_ID}")"
write_status
echo "OK: autostart minted M1=${M1_ID} M2=${M2_ID}"
