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
  # Architect E-20260810T141120Z — provider knobs are tip/scaffold state.
  # Fresh workspaces lose hand-placed max_tokens; enforce before dispatch.
  local ensure_py="${ROOT}/.hermes/home/scripts/ensure-provider-max-tokens.py"
  if [[ -f "${ensure_py}" ]]; then
    if HERMES_HOME="${HERMES_HOME}" HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR}" \
      python3 "${ensure_py}" --apply \
        "${HERMES_MANAGED_DIR}/config.yaml" "${HERMES_HOME}/config.yaml" \
      2>/dev/null; then
      :
    else
      # Fallback: hermes venv often has PyYAML when system python3 does not.
      local venv_py="${HOME}/.hermes/hermes-agent/venv/bin/python"
      if [[ -x "${venv_py}" ]]; then
        HERMES_HOME="${HERMES_HOME}" HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR}" \
          "${venv_py}" "${ensure_py}" --apply \
          "${HERMES_MANAGED_DIR}/config.yaml" "${HERMES_HOME}/config.yaml" \
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
  M2)
    cat >"${BODY_FILE}" <<'EOF'
# M2 PLAN - Hermes-native (planner / spec-author) — original scope

Phase: M2 per `.hermes/phase-dispatch.yaml`
Requires: Operator `migration/acks/m1-findings.ack.yaml` (or `.ack.json`) + findings-handoff gate

## READ (planner context)
- `migration/findings-handoff.json` (required; schema rhoai3.findings-handoff/v1)
- `migration/acks/m1-findings.ack.yaml` (or `.ack.json`) — authoritative; refuse bare `m1-findings.json`
- `migration/entry-point-inventory.json` (controller names/counts; optional digest check via handoff)

## DO NOT
- Do **not** load `migration/mta-findings.json` or `mta-analyze-out/` into chat (evidence store — selective locus reads only after digest check)
- Never `/speckit.implement`
- Do **not** grant `migration/acks/brief-identity.json` or any worker `acknowledged_by` (AR-1.1) — Operator writes `brief-identity.ack.yaml`
- Do **not** re-list the full story partition in Reasoning after `migration/briefs/partition.json` exists — edit the file (R-M2.2 anti-narration)

## Job (in order)
1. Run `python3 .hermes/skills/mta-analysis/scripts/check-findings-handoff.py /projects/modernized` — typed BLOCK if FAIL.
2. **R-M2.6 resume-from-artifacts** (Architect E-20260810T153830Z): if
   `migration/briefs/partition.json` **and** Spec Kit `spec.md` exist
   (and `plan.md` when present) → **skip** re-partition / re-`/speckit.specify`
   / re-`/speckit.plan`; jump to `/speckit.tasks` → step 4. Do not rewrite
   write-once `partition.json`.
3. Else **Hard-invoke** `/speckit.specify` **before** freeform partition essays
   (then `/speckit.plan` → `/speckit.tasks`). Cite `migration/contracts/sdd-ordering.md`
   + `story-sizing.md`.
4. **Write-once** `migration/briefs/partition.json` (`rhoai3.partition/v1` — see
   `migration/schemas/partition.md`) with story IDs + layering from
   handoff/inventory. Prefer Spec Kit `spec.md` as the next durable artifact.
5. Create implementer Kanban cards from tasks.md using
   **`bash .hermes/skills/phase-dispatch/scripts/create-m3-implementer.sh`**
   (NOT bare `hermes kanban create` — that omits M3 skills; Review grounding
   study 20260809). Each child needs a typed body JSON under
   `migration/bodies/` that passes `check-kanban-body.py`.
6. Stop when briefs/tasks/bodies are stable — **Operator** grants
   `migration/acks/brief-identity.ack.yaml` (not a worker Done criterion).

## Done when
- `migration/briefs/partition.json` present (write-once seed)
- Spec Kit artifacts exist under Spec Kit paths / `migration/specs` as produced by slash-invoke
- M3 children created via `create-m3-implementer.sh` with max-runtime
- brief-identity stage-advance ack is **out of band** (Operator)

## Constraints
- workspace: dir:/projects/modernized
- Stop at tasks → create-m3-implementer.
- **M3 skill preload (P1-B fix):** every M3 child **must** be created via
  `create-m3-implementer.sh` so skills from `phase-dispatch.yaml` M3 are
  attached (`grounded-generation`, `spring-to-quarkus-patterns`, …).
- **AD-009:** every M3 child **must** set `--max-runtime` to M3
  `max_runtime_seconds` from `.hermes/phase-dispatch.yaml` (currently 2700).
  Creating children without max-runtime is forbidden (phantom unbounded sessions).
- **AD-009 circuit-breaker (M2 K=1):** on consecutive provider-stale / Broken
  pipe reclaim, run
  `python3 .hermes/home/scripts/apply-environmental-circuit-breaker.py --task-id $TASK --phase M2 --provider-stale-events N`
  then typed `kanban_block` — do **not** MiniMax. Unstamped crash loops are an
  IMPLEMENT gap.
- **Crash requeue ceiling (Architect E-20260810T142650Z):** on `crashed`, run
  `python3 .hermes/skills/validation-release-gates/scripts/apply-crash-requeue-policy.py . --task-id $TASK --k-crash 1 --cause harness_fault --stamp`
  (does **not** spend wall soft-K). Hard ceiling → typed block; never primary
  budget/`timed_out`.
- **AD-009 §3.1:** rc=0 without kanban terminal →
  `apply-protocol-untyped-terminal.py --task-id $TASK --block` (typed
  `protocol_untyped`; dual-annotate if environmental).
- **AD-009 hard budget:** `enforce-max-runtime-hard.py --apply` — elapsed >
  `max_runtime_seconds` is a control, not an advisory %.
- **Produce-not-verify:** do not `kanban_complete` by only verifying pre-seeded
  specs/plans/tasks from a prior card.
EOF
    TITLE="M2 PLAN: story partition + SDD"
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
