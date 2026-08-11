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
  echo "usage: dispatch-phase.sh M1|M2a|M2b|M3|M4|M5|factory [--parent ID] [--dry-run]" >&2
  echo "  (bare M2 refused — use M2a then M2b; R-AB.2 / pre-v12 R1)" >&2
  exit 2
}
if [[ "${PHASE}" == "M2" ]]; then
  echo "dispatch-phase: REFUSE bare M2 — dispatch M2a (partition) then M2b (SDD+create-m3); R-AB.2" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
DISPATCH_YAML="${ROOT}/.hermes/phase-dispatch.yaml"
export HERMES_HOME="${HERMES_HOME:-${ROOT}/.hermes/home}"
export HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR:-/projects/.platform/hermes}"
export HERMES_WRITE_SAFE_ROOT="${HERMES_WRITE_SAFE_ROOT:-${ROOT}}"

die() { echo "dispatch-phase: $*" >&2; exit 1; }

[[ -f "${DISPATCH_YAML}" ]] || die "missing ${DISPATCH_YAML}"
command -v python3 >/dev/null 2>&1 || die "python3 required"

# Pre-v12 R0/R3 — tip sync must be green before any phase create
python3 "${ROOT}/.hermes/skills/phase-dispatch/scripts/check-create-path-tip-sync.py" "${ROOT}" \
  || die "create-path tip sync failed (R0/R3)"
python3 "${ROOT}/.hermes/skills/phase-dispatch/scripts/sync-extension-overlays-into-skills.py" "${ROOT}" \
  || die "extension overlay sync failed"
python3 "${ROOT}/.hermes/skills/phase-dispatch/scripts/sync-extension-overlays-into-skills.py" "${ROOT}" --check \
  || die "extension overlay --check failed (R-M3.32)"

# R-HX.5 (Architect E-20260811T070102Z): do NOT copy Managed Scope config/.env
# into writable HERMES_HOME. Provider/auth stay platform-owned under
# HERMES_MANAGED_DIR. HERMES_HOME is for kanban DB / logs / sessions only.
ensure_hermes_home_config() {
  mkdir -p "${HERMES_HOME}"
  if [[ -f "${HERMES_HOME}/.env" || -f "${HERMES_HOME}/auth.json" ]]; then
    echo "dispatch-phase: WARN R-HX.5 — refuse secret-bearing files under HERMES_HOME (.env/auth.json); use Managed Scope only" >&2
  fi
  [[ -f "${HERMES_MANAGED_DIR}/config.yaml" ]] \
    || die "missing Managed Scope config: ${HERMES_MANAGED_DIR}/config.yaml"
  # Architect E-20260810T141120Z — provider knobs applied to Managed Scope only.
  local ensure_py="${ROOT}/.hermes/home/scripts/ensure-provider-max-tokens.py"
  if [[ -f "${ensure_py}" ]]; then
    if HERMES_HOME="${HERMES_HOME}" HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR}" \
      python3 "${ensure_py}" --apply \
        "${HERMES_MANAGED_DIR}/config.yaml" \
      2>/dev/null; then
      :
    else
      local venv_py="${HOME}/.hermes/hermes-agent/venv/bin/python"
      if [[ -x "${venv_py}" ]]; then
        HERMES_HOME="${HERMES_HOME}" HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR}" \
          "${venv_py}" "${ensure_py}" --apply \
          "${HERMES_MANAGED_DIR}/config.yaml" \
          || echo "dispatch-phase: WARN ensure-provider-max-tokens failed" >&2
      else
        echo "dispatch-phase: WARN ensure-provider-max-tokens skipped (no PyYAML)" >&2
      fi
    fi
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
2. Load/run **inventory-entry-points** - write `migration/entry-point-inventory.json` (**before** MTA handoff emit).
3. Load/run **mta-analysis** - `bash "${HERMES_SKILL_DIR}/scripts/mta-analyze-legacy.sh"` (never invent `--source`; use MTA_RUN_CWD + writable clone when freeze is a-w). Script normalizes findings and emits `migration/findings-handoff.json` (requires inventory).
4. Schema-validate findings + handoff (`check-findings-handoff.py`). **Do not** write stage-advance acks — Operator grants `migration/acks/m1-findings.ack.yaml` per `ack.md` / AR-1.1.

## Constraints
- workspace: dir:/projects/modernized
- Do not hand-edit destination app source.
- Do not run analyze as a detached shell outside this Kanban task.
- Do **not** grant `migration/acks/m1-findings.json` or any `acknowledged_by` worker role (AR-1.1).
- If blocked, report typed BLOCK and stop.

## Done when
- `migration/mta-findings.json` validates (`rhoai3.mta-findings/v1-provisional`) — evidence store
- `migration/entry-point-inventory.json` present
- `migration/findings-handoff.json` validates (`rhoai3.findings-handoff/v1`) — M2 planner input
- Stage-advance ack is **out of band** (Operator) — not a worker Done criterion
EOF
    TITLE="M1 ANALYZE: derive + MTA/kantra + inventory"
    ;;
  M2a)
    cat >"${BODY_FILE}" <<'EOF'
# M2a PLAN — partition + briefs only (R-AB.2 / pre-v12 R1)

Phase: M2a per `.hermes/phase-dispatch.yaml`
Requires: Operator `migration/acks/m1-findings.ack.yaml` + findings-handoff gate

## Job
1. `check-findings-handoff.py` — typed BLOCK if FAIL.
2. **Write-once** `migration/briefs/partition.json` (`rhoai3.partition/v1`).
3. Prefer Spec Kit `/speckit-specify` **before** freeform partition essays.
4. **STOP** — do **not** run `/speckit-tasks` or `create-m3-implementer.sh` here.
   Lead/Operator dispatch **M2b** next (parent = this task).

## Done when
- `migration/briefs/partition.json` present (write-once)
- Spec Kit `spec.md` seeded when produced by slash-invoke
- **No** M3 children created on this card

## Constraints
- workspace: dir:/projects/modernized
- AD-009 hard budget / crash requeue / protocol_untyped as for prior M2 law
- Soft-K @2700 not used on M2a (max_runtime=3600); no MiniMax
EOF
    TITLE="M2a PLAN: story partition + briefs"
    ;;
  M2b)
    cat >"${BODY_FILE}" <<'EOF'
# M2b PLAN — SDD emit + create-m3 children (R-AB.2 / pre-v12 R1)

Phase: M2b per `.hermes/phase-dispatch.yaml`
Requires: M2a partition present; m1-findings ack

## Job
1. Require `migration/briefs/partition.json` — typed BLOCK if missing (run M2a first).
2. **R-M2.6 resume-from-artifacts:** if Spec Kit `spec.md` (+ `plan.md` when present)
   exist → skip re-partition / re-specify; jump to `/speckit-tasks`.
3. Else `/speckit-plan` → `/speckit-tasks` (cite `sdd-ordering.md` + `story-sizing.md`).
4. Create implementer cards via **`create-m3-implementer.sh`** only (not bare create).
5. Stop for Operator `brief-identity.ack.yaml`.

## Done when
- Spec Kit tasks artifacts present
- M3 children created via `create-m3-implementer.sh` with max-runtime
- brief-identity ack out of band (Operator)

## Constraints
- workspace: dir:/projects/modernized
- Do not rewrite write-once `partition.json`
- AD-009 / crash requeue / protocol_untyped as prior M2 law; no MiniMax
EOF
    TITLE="M2b PLAN: SDD + create-m3 children"
    ;;
  M2)
    die "bare M2 refused — use M2a then M2b (R-AB.2)"
    ;;
  M3)
    cat >"${BODY_FILE}" <<'EOF'
# M3 IMPLEMENT - Hermes-native (implementer)

Phase: M3 per `.hermes/phase-dispatch.yaml`
Requires acks: m1-findings, brief-identity
Prefer create path: `create-m3-implementer.sh` (skills preloaded).

## Job
Execute only `files_in_scope` from the typed W2 §6 body. Consult
grounded-generation + spring-to-quarkus-patterns before edits. One task ⇒ one role.

## Typed body (required — not a pointer to tasks.md)
Write/attach `migration/bodies/<task>.json` with:
- `task_id`, `role=implementer`, `phase=M3`
- `files_in_scope`: non-empty paths
- `refs[]` including `brief_identity_ack`, `legacy_locus` (sha256 digests)
- optional `spec_path` / `plan_path` / `tasks_path` digests
Validate: `python3 .hermes/skills/sdd-readiness/scripts/check-kanban-body.py /projects/modernized`

## Done when
- Scoped compile/tests for files_in_scope pass, or typed BLOCK with residue named
- Provenance record writable under migration/tasks/ (AD-H §19)

## Constraints
- workspace: dir:/projects/modernized
- Do not re-plan scope. Typed BLOCK if inputs are wrong.
- **AD-009:** if provider-stale / consecutive failures hit the failure cap,
  typed BLOCK with `block_class=environmental_provider`. Prefer:
  `python3 .hermes/home/scripts/apply-environmental-circuit-breaker.py --task-id $TASK --phase M3 --provider-stale-events N`
  (or `stamp-environmental-provider-block.py`). Do **not** MiniMax-escalate
  (AD-008). Native reclaim is allowed until the cap (M3 K=2).
- **AD-009 §3.1 / hard budget:** silent exit → `protocol_untyped` stamp;
  over `max_runtime_seconds` → `enforce-max-runtime-hard.py --apply`.
EOF
    TITLE="M3 IMPLEMENT: bounded transform"
    ;;
  M4)
    cat >"${BODY_FILE}" <<'EOF'
# M4 VERIFY - Hermes-native (validator)

Phase: M4 — verdict token PROVISIONAL_ACCEPT (accept_kind=provisional).
Run required_checks from phase-dispatch.yaml. Write verdict JSON under migration/verdicts/.

## Pre-v12 R2 — M4 floor (required)
1. `bash .hermes/skills/validation-release-gates/scripts/run-m4-floor.sh /projects/modernized`
2. `python3 .hermes/skills/validation-release-gates/scripts/check-m4-floor-receipts.py migration/receipts/m4-floor/latest`
3. Bank receipts; do **not** claim PROVISIONAL_ACCEPT without boot_health + endpoint_smoke PASS (g4_hook may be INCONCLUSIVE / SAMPLE).
Contract: `migration/contracts/m4-floor-runner.md`. `ad010_demo=false` until Architect promotes.
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
