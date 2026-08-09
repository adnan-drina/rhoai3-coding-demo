#!/usr/bin/env bash
# Create + dispatch a Hermes Kanban task for one M-phase from phase-dispatch.yaml.
# Usage:
#   bash .hermes/skills/phase-dispatch/scripts/dispatch-phase.sh M1
#   bash .hermes/skills/phase-dispatch/scripts/dispatch-phase.sh M2 --parent t_xxx
#   bash .hermes/skills/phase-dispatch/scripts/dispatch-phase.sh M1 --dry-run
set -euo pipefail

PHASE="${1:-}"
shift || true
PARENTS=()
DRY_RUN=0
DISPATCH_MAX="${DISPATCH_MAX:-1}"
WORKSPACE_DIR="${WORKSPACE_DIR:-/projects/modernized}"
IDEM_PREFIX="${IDEM_PREFIX:-migration}"
IDEM_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --parent)
      PARENTS+=("$2")
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --idempotency-key)
      IDEM_OVERRIDE="$2"
      shift 2
      ;;
    *)
      echo "dispatch-phase: unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

[[ -n "${PHASE}" ]] || {
  echo "usage: dispatch-phase.sh M1|M2|M3|M4|M5|factory [--parent ID] [--dry-run]" >&2
  exit 2
}

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
DISPATCH_YAML="${ROOT}/.hermes/phase-dispatch.yaml"
export HERMES_HOME="${HERMES_HOME:-${ROOT}/.hermes/home}"
export HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR:-/projects/.platform/hermes}"
export HERMES_WRITE_SAFE_ROOT="${HERMES_WRITE_SAFE_ROOT:-${ROOT}}"

die() { echo "dispatch-phase: $*" >&2; exit 1; }

[[ -f "${DISPATCH_YAML}" ]] || die "missing ${DISPATCH_YAML}"
command -v python3 >/dev/null 2>&1 || die "python3 required"

# Relocated HERMES_HOME must carry managed model/auth — kanban workers often
# miss HERMES_MANAGED_DIR-only pins (clean-room finding 2026-08-09).
ensure_hermes_home_config() {
  mkdir -p "${HERMES_HOME}"
  if [[ -f "${HERMES_MANAGED_DIR}/config.yaml" && ! -f "${HERMES_HOME}/config.yaml" ]]; then
    cp -f "${HERMES_MANAGED_DIR}/config.yaml" "${HERMES_HOME}/config.yaml"
    echo "dispatch-phase: copied managed config.yaml → HERMES_HOME"
  fi
  if [[ -f "${HERMES_MANAGED_DIR}/.env" && ! -f "${HERMES_HOME}/.env" ]]; then
    cp -f "${HERMES_MANAGED_DIR}/.env" "${HERMES_HOME}/.env"
    chmod 600 "${HERMES_HOME}/.env"
    echo "dispatch-phase: copied managed .env → HERMES_HOME"
  fi
}

ensure_daemon() {
  if pgrep -f '/hermes-agent/hermes kanban daemon' >/dev/null 2>&1; then
    return 0
  fi
  # Dev Spaces: no messaging gateway — standalone daemon is required.
  nohup hermes kanban daemon --force --interval 15 --verbose \
    >"${HERMES_HOME}/kanban-daemon.log" 2>&1 &
  echo $! >"${HERMES_HOME}/kanban-daemon.pid"
  echo "dispatch-phase: started kanban daemon --force pid=$(cat "${HERMES_HOME}/kanban-daemon.pid")"
  sleep 1
}

# Parse phase seed from YAML (no PyYAML required).
eval "$(python3 - "${DISPATCH_YAML}" "${PHASE}" <<'PY'
import re, sys, json
path, phase = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read().splitlines()
# find phases: then phase key
in_phases = False
in_phase = False
role = ""
skills = []
max_rt = ""
indent_phase = None
i = 0
while i < len(text):
    ln = text[i]
    if re.match(r"^phases:\s*$", ln):
        in_phases = True
        i += 1
        continue
    if in_phases and re.match(r"^[A-Za-z]", ln) and not ln.startswith(" "):
        # left phases block (roles:/watchdog:)
        break
    m = re.match(r"^  ([A-Za-z0-9_]+):\s*$", ln)
    if in_phases and m:
        in_phase = m.group(1) == phase
        i += 1
        continue
    if in_phase:
        if re.match(r"^  [A-Za-z0-9_]+:\s*$", ln):
            break  # next phase
        rm = re.match(r"^    role:\s*(\S+)\s*$", ln)
        if rm:
            role = rm.group(1).strip()
        mm = re.match(r"^    max_runtime_seconds:\s*(\d+)\s*$", ln)
        if mm:
            max_rt = mm.group(1)
        if re.match(r"^    skills:\s*$", ln):
            i += 1
            while i < len(text):
                sm = re.match(r"^      -\s+(\S+)\s*$", text[i])
                if not sm:
                    break
                skills.append(sm.group(1))
                i += 1
            continue
    i += 1
if not role or not max_rt:
    print(f"print('die missing role/max_runtime for phase={phase!r}', file=__import__('sys').stderr); raise SystemExit(2)")
    raise SystemExit(2)
# emit bash assignments
def sh_escape(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"
print(f"ROLE={sh_escape(role)}")
print(f"MAX_RUNTIME={sh_escape(max_rt)}")
print("SKILLS=(" + " ".join(sh_escape(s) for s in skills) + ")")
print(f"TITLE={sh_escape(f'{phase} ({role}): migration phase seed')}")
PY
)"

IDEM_KEY="${IDEM_OVERRIDE:-${IDEM_PREFIX}-${PHASE}-v1}"

BODY_FILE="$(mktemp)"
trap 'rm -f "${BODY_FILE}"' EXIT

case "${PHASE}" in
  M1)
    cat >"${BODY_FILE}" <<'EOF'
# M1 ANALYZE - Hermes-native (evidence-analyst)

Phase: M1 per `.hermes/phase-dispatch.yaml`
Role: evidence-analyst
orchestration: hermes_native (required)

## Job (in order)
1. Load/run **derive-legacy-boot3** - ensure `migration/derived/legacy-at-3.json` and frozen harvest_referent.
2. Load/run **mta-analysis** - `bash "${HERMES_SKILL_DIR}/scripts/mta-analyze-legacy.sh"` (never invent `--source`; use MTA_RUN_CWD + writable clone when freeze is a-w).
3. Load/run **inventory-entry-points** - write `migration/entry-point-inventory.json`.
4. Schema-validate findings; grant `migration/acks/m1-findings.json` when OK.

## Constraints
- workspace: dir:/projects/modernized
- Do not hand-edit destination app source.
- Do not run analyze as a detached shell outside this Kanban task.
- If blocked, report typed BLOCK and stop.

## Done when
- `migration/mta-findings.json` validates (`rhoai3.mta-findings/v1-provisional`)
- `migration/acks/m1-findings.json` granted with violation_rules count
EOF
    TITLE="M1 ANALYZE: derive + MTA/kantra + inventory"
    ;;
  M2)
    cat >"${BODY_FILE}" <<'EOF'
# M2 PLAN - Hermes-native (planner / spec-author)

Phase: M2 per `.hermes/phase-dispatch.yaml`
Requires ack: migration/acks/m1-findings.json

## Job
1. Partition stories/briefs from findings + legacy structure.
2. Spec Kit: `/speckit.specify` → plan → tasks (optional analyze). **Never** `/speckit.implement`.
3. Create implementer Kanban cards from tasks.md (`hermes kanban create`).
4. Grant `migration/acks/brief-identity.json` when brief identity is stable.

## Constraints
- workspace: dir:/projects/modernized
- Stop at tasks → kanban_create.
EOF
    TITLE="M2 PLAN: story partition + SDD"
    ;;
  M3)
    cat >"${BODY_FILE}" <<'EOF'
# M3 IMPLEMENT - Hermes-native (implementer)

Phase: M3 per `.hermes/phase-dispatch.yaml`
Requires acks: m1-findings, brief-identity

## Job
Execute the bounded implementer card(s) for this story. Respect files_in_scope,
grounded-generation consult order, and domain gates. One task ⇒ one role.

## Constraints
- workspace: dir:/projects/modernized
- Do not re-plan scope. Typed BLOCK if inputs are wrong.
EOF
    TITLE="M3 IMPLEMENT: bounded transform"
    ;;
  M4)
    cat >"${BODY_FILE}" <<'EOF'
# M4 VERIFY - Hermes-native (validator)

Phase: M4 — verdict token PROVISIONAL_ACCEPT (accept_kind=provisional).
Run required_checks from phase-dispatch.yaml. Write verdict JSON under migration/verdicts/.
EOF
    TITLE="M4 VERIFY: provisional accept"
    ;;
  M5)
    cat >"${BODY_FILE}" <<'EOF'
# M5 CLOSE - Hermes-native (validator)

Phase: M5 — full ACCEPT path. Re-run mta-analysis as needed for findings-delta.
Write final verdict. Do not ship on INCONCLUSIVE.
EOF
    TITLE="M5 CLOSE: full accept"
    ;;
  factory)
    cat >"${BODY_FILE}" <<'EOF'
# factory - Hermes-native (validator)

Push/main factory bar. must_not_contradict_m5_accept. Refuse provisional-only.
EOF
    TITLE="factory: release bar"
    ;;
  *)
    die "unsupported phase: ${PHASE}"
    ;;
esac

ensure_hermes_home_config

CREATE_ARGS=(
  --json
  --assignee default
  --workspace "dir:${WORKSPACE_DIR}"
  --max-runtime "${MAX_RUNTIME}"
  --idempotency-key "${IDEM_KEY}"
  --created-by phase-dispatch
  --body "$(cat "${BODY_FILE}")"
)
for s in "${SKILLS[@]}"; do
  CREATE_ARGS+=(--skill "${s}")
done
for p in "${PARENTS[@]:-}"; do
  [[ -n "${p}" ]] && CREATE_ARGS+=(--parent "${p}")
done

echo "dispatch-phase: phase=${PHASE} role=${ROLE} max_runtime=${MAX_RUNTIME}s skills=${SKILLS[*]}"
echo "dispatch-phase: idempotency_key=${IDEM_KEY} workspace=dir:${WORKSPACE_DIR}"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "dispatch-phase: DRY_RUN — would create: ${TITLE}"
  printf '  %q' hermes kanban create "${CREATE_ARGS[@]}" "${TITLE}"
  echo
  exit 0
fi

command -v hermes >/dev/null 2>&1 || die "hermes not on PATH"
ensure_daemon
cd "${WORKSPACE_DIR}"
OUT="$(hermes kanban create "${CREATE_ARGS[@]}" "${TITLE}")"
echo "${OUT}"
TASK_ID="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("id") or "")' <<<"${OUT}")"
[[ -n "${TASK_ID}" ]] || die "kanban create returned no id"
mkdir -p "${ROOT}/migration/derived"
echo "${TASK_ID}" >"${ROOT}/migration/derived/phase-${PHASE}-task-id.txt"
echo "dispatch-phase: created ${TASK_ID}"

hermes kanban dispatch --max "${DISPATCH_MAX}" --json || true
hermes kanban ls 2>&1 | head -40
echo "OK: ${PHASE} → ${TASK_ID} (Hermes-native). Track: hermes kanban watch / show ${TASK_ID}"
