#!/usr/bin/env bash
# Create + dispatch a Hermes Kanban task for one M-phase from phase-dispatch.yaml.
# Cite: governance/contracts/devspaces-dispatcher-posture.md (B5 daemon/gateway;
# B6 promote vs park-at-birth). This script is the interim dispatcher half.
# Usage:
#   bash .hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh M1
#   bash .hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh M2 --parent t_xxx
#   bash .hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh M1 --dry-run
set -euo pipefail

case "${1:-}" in
  -h|--help)
    cat <<'USAGE'
dispatch-phase.sh — create + dispatch one M-phase Kanban task from phase-dispatch.yaml.

Usage:
  dispatch-phase.sh M1|M2a|M2b|M3|M4|M5|factory [--parent ID] [--dry-run]
  (bare M2 refused — use M2a then M2b)

This is an interface probe / help surface only when -h/--help is passed.
USAGE
    exit 0
    ;;
esac

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
python3 "${ROOT}/.hermes/enforcement/dispatch-phase/scripts/check-create-path-tip-sync.py" "${ROOT}" \
  || die "create-path tip sync failed (R0/R3)"
# Architect E-20260811T170706Z Class A — quarantine tombstones before any phase create
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/assert-quarantine-tombstones.py" "${ROOT}" \
  || die "quarantine tombstones resurrected — wipe + purge restorer (governance/contracts/quarantine-survives-dispatch.md)"
# S-008 / W4 — parent-chain triad resurrection order (distinct from tombstones)
python3 "${ROOT}/.hermes/enforcement/dispatch-phase/scripts/check-s008-resurrection-order.py" "${ROOT}" \
  || die "S-008 resurrection-order failed (governance/contracts/s008-quarantine-resurrection-order.md)"
python3 "${ROOT}/.hermes/enforcement/dispatch-phase/scripts/check-phase-attach-matrix.py" "${ROOT}" \
  || die "phase attach matrix failed"
python3 "${ROOT}/.hermes/enforcement/dispatch-phase/scripts/check-phase-body-script-refs.py" "${ROOT}" \
  || die "phase body script refs failed (R0 / Deputy E-20260811T112700Z)"
python3 "${ROOT}/.hermes/enforcement/dispatch-phase/scripts/check-phase-input-manifest.py" "${ROOT}" "${PHASE}" \
  || die "phase input manifests failed (R0 / Operator E-20260811T113700Z)"
python3 "${ROOT}/.hermes/enforcement/dispatch-phase/scripts/check-decision-complete-cards.py" "${ROOT}" \
  || die "decision-complete card lint failed (R0 / Architect E-20260811T122959Z)"
# Architect E-20260811T121308Z — provision-owns-tools: Spec Kit preseed before M2a
if [[ "${PHASE}" == "M2a" ]]; then
  python3 "${ROOT}/.hermes/enforcement/dispatch-phase/scripts/check-specify-preseed.py" "${ROOT}" \
    || die "Spec Kit preseed failed (R0 / provision-owns-tools) — run postStart init-workspace.sh; do not agent-init"
fi
# CS-2: sync retired — overlays modify-in-place under skill references/ (W3)
# CS-2: sync retired — overlays modify-in-place under skill references/ (W3)

# R-HX.5 + Hermes Managed Scope (official):
#   Providers/secrets live under HERMES_MANAGED_DIR and *overlay* HERMES_HOME.
#   Do NOT symlink or copy Managed config/.env into HERMES_HOME.
#   Docs: https://hermes-agent.nousresearch.com/docs/user-guide/managed-scope
# Workers that lack HERMES_MANAGED_DIR in-process stillborn (Operator URGENT
# t_c9b03f60 — bashrc-only export is not enough for non-login spawns).
ensure_hermes_home_config() {
  mkdir -p "${HERMES_HOME}"
  # Architect E-20260811T205329Z Class A — pin Managed Scope dir (refuse wrong exports).
  local _pin="${HERMES_MANAGED_DIR_PIN:-/projects/.platform/hermes}"
  if [[ -n "${HERMES_MANAGED_DIR:-}" && "${HERMES_MANAGED_DIR}" != "${_pin}" ]]; then
    die "HERMES_MANAGED_DIR=${HERMES_MANAGED_DIR} != pinned ${_pin} (Architect E-20260811T205329Z Class A)"
  fi
  export HERMES_MANAGED_DIR="${_pin}"
  if [[ -f "${HERMES_HOME}/.env" || -f "${HERMES_HOME}/auth.json" ]]; then
    echo "dispatch-phase: WARN R-HX.5 — refuse secret-bearing files under HERMES_HOME (.env/auth.json); use Managed Scope only" >&2
  fi
  [[ -f "${HERMES_MANAGED_DIR}/config.yaml" ]] \
    || die "missing Managed Scope config: ${HERMES_MANAGED_DIR}/config.yaml"
  python3 "${ROOT}/.hermes/home/scripts/assert-managed-scope-active.py" \
    || die "Managed Scope inactive/unpinned — refuse daemon/dispatch (managed-scope-at-spawn)"
  # skill_utils reads skills.external_dirs from HERMES_HOME/config.yaml (not Managed
  # Scope alone). Without this, kanban workers fail: Unknown skill(s) for tip skills
  # under .hermes/skills/ (v12 M1 t_bc2a6cc7). Non-secret discovery paths only —
  # model/provider stay in Managed Scope overlay (official; not a home copy).
  if [[ ! -f "${HERMES_HOME}/config.yaml" ]] || ! grep -q 'external_dirs' "${HERMES_HOME}/config.yaml" 2>/dev/null; then
    cat >"${HERMES_HOME}/config.yaml" <<EOF
skills:
  # Headless kanban: write_approval:true times out with no approver (Deputy
  # E-20260811T111800Z). Protect acks/golden via AR-1.1 + FS, not a global gate.
  write_approval: false
  inline_shell: false
  external_dirs:
    - ${ROOT}/.hermes/skills
    - ${HOME}/.hermes/skills
EOF
    echo "dispatch-phase: wrote HERMES_HOME/config.yaml skills.external_dirs (skill discovery)"
  fi
  # Rescope live home config if a prior create left write_approval:true
  if grep -q 'write_approval:[[:space:]]*true' "${HERMES_HOME}/config.yaml" 2>/dev/null; then
    python3 - "${HERMES_HOME}/config.yaml" <<'PY' || echo "dispatch-phase: WARN write_approval rescope failed" >&2
import pathlib, re, sys
p = pathlib.Path(sys.argv[1])
text = p.read_text(encoding="utf-8")
new = re.sub(r"(write_approval:\s*)true", r"\1false", text, count=1)
if new != text:
    p.write_text(new, encoding="utf-8")
    print("dispatch-phase: rescoped skills.write_approval true→false (headless)")
PY
  fi
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
  # Explicit export: nohup children must not depend on interactive bashrc.
  export HERMES_HOME="${HERMES_HOME:-${ROOT}/.hermes/home}"
  local _pin="${HERMES_MANAGED_DIR_PIN:-/projects/.platform/hermes}"
  if [[ -n "${HERMES_MANAGED_DIR:-}" && "${HERMES_MANAGED_DIR}" != "${_pin}" ]]; then
    die "HERMES_MANAGED_DIR=${HERMES_MANAGED_DIR} != pinned ${_pin} (Architect E-20260811T205329Z Class A)"
  fi
  export HERMES_MANAGED_DIR="${_pin}"
  python3 "${ROOT}/.hermes/home/scripts/assert-managed-scope-active.py" \
    || die "Managed Scope inactive/unpinned — refuse daemon start"
  nohup env \
    HERMES_HOME="${HERMES_HOME}" \
    HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR}" \
    hermes kanban daemon --force --interval 15 --verbose \
    >"${HERMES_HOME}/kanban-daemon.log" 2>&1 &
  echo $! >"${HERMES_HOME}/kanban-daemon.pid"
  echo "dispatch-phase: started kanban daemon --force pid=$(cat "${HERMES_HOME}/kanban-daemon.pid") managed=${HERMES_MANAGED_DIR}"
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
        # left phases block (watchdog:)
        break
    m = re.match(r"^  ([A-Za-z0-9_]+):\s*$", ln)
    if in_phases and m:
        in_phase = m.group(1) == phase
        i += 1
        continue
    if in_phase:
        if re.match(r"^  [A-Za-z0-9_]+:\s*$", ln):
            break  # next phase
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
if not max_rt:
    print(f"print('die missing max_runtime for phase={phase!r}', file=__import__('sys').stderr); raise SystemExit(2)")
    raise SystemExit(2)
# emit bash assignments
def sh_escape(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"
print(f"MAX_RUNTIME={sh_escape(max_rt)}")
print("SKILLS=(" + " ".join(sh_escape(s) for s in skills) + ")")
print(f"TITLE={sh_escape(f'{phase}: migration phase seed')}")
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
Task-type: examining
orchestration: hermes_native (required)

## Job (in order)
1. Load/run **derive-legacy-boot3** - ensure `evidence/derived/legacy-at-3.json` and frozen harvest_referent.
2. Load/run **inventory-entry-points** - write `evidence/entry-point-inventory.json` (**before** MTA handoff emit).
3. Load/run **scan-with-mta** - `bash "${HERMES_SKILL_DIR}/scripts/mta-analyze-legacy.sh"` (never invent `--source`; use MTA_RUN_CWD + writable clone when freeze is a-w). Script normalizes findings and emits `evidence/findings-handoff.json` (requires inventory).
4. Schema-validate findings + handoff (runtime skill root / AD-H §7.1):
   `python3 "${HERMES_SKILL_DIR:-.hermes/home/skills/software-development/scan-with-mta}/scripts/check-findings-handoff.py" /projects/modernized`
   Exit: **0=pass**; **1=FAIL→typed BLOCK**; **2=missing script** (harness/lint defect — do not invent).
   **Do not** write stage-advance acks — Operator grants `evidence/acks/m1-findings.ack.yaml` per `ack.md` / AR-1.1.

## Constraints
- workspace: dir:/projects/modernized
- Do not hand-edit destination app source.
- Do not run analyze as a detached shell outside this Kanban task.
- Do **not** grant `evidence/acks/m1-findings.json` or any `acknowledged_by` worker role (AR-1.1).
- If blocked, report typed BLOCK and stop.

## Done when
- `evidence/mta-findings.json` validates (`rhoai3.mta-findings/v1-provisional`) — evidence store
- `evidence/entry-point-inventory.json` present
- `evidence/findings-handoff.json` validates (`rhoai3.findings-handoff/v1`) — M2 planner input
- Stage-advance ack is **out of band** (Operator) — not a worker Done criterion
EOF
    TITLE="M1 ANALYZE: derive + MTA/kantra + inventory"
    ;;
  M2a)
    cat >"${BODY_FILE}" <<'EOF'
# M2a PLAN — partition + briefs only (R-AB.2 / pre-v12 R1)

Phase: M2a per `.hermes/phase-dispatch.yaml`
Requires: Operator `evidence/acks/m1-findings.ack.yaml` + findings-handoff gate

## Execute-as-defined-or-stop (Operator E-20260811T113700Z)
Any obligation unexecutable as written (unresolvable gate script, missing
contract, absent required input) → typed **`needs_input` BLOCK**. Never silent
substitution / path invention / specimen-body priming. Measure the harness.

## Input manifest
### Required present
- evidence/acks/m1-findings.ack.yaml
- evidence/findings-handoff.json
- evidence/entry-point-inventory.json
- evidence/mta-findings.json
- governance/schemas/partition.md
### Forbidden absent
- evidence/bodies/*.json
- evidence/bodies/m3-*.json

## Job
0. **Spec Kit preseed verify-or-BLOCK** (Architect E-20260811T121308Z provision-owns-tools):
   Workspace provision (devfile postStart) owns `specify init` + Non-Goals override.
   **Agent has no init authority.** Prove with command evidence:
   `test -d .specify && test -f .specify/.rhoai3-ads-provisioned && ls -la .specify/templates/overrides/`
   If missing/invalid → typed **`needs_input` BLOCK** and STOP.
   **Forbidden:** inventing `.specify/`, manual `specify init`, copying overrides by hand.
1. Findings-handoff gate (runtime skill root — Deputy E-20260811T113300Z):
   `python3 "${HERMES_SKILL_DIR:-.hermes/home/skills/software-development/check-spec-readiness}/scripts/check-findings-handoff.py" /projects/modernized`
   (shim → scan-with-mta canonical). Exit: **0=pass**; **1=FAIL→typed BLOCK**; **2=missing script** → `needs_input` (lint/harness defect — do not invent paths).
2. **Spec Kit invoke-or-BLOCK** (Architect E-20260811T115316Z — not soft Prefer):
   - Hard-invoke attached skill `speckit-specify` via `skill_view` / `/speckit-specify`
     (discoverable under `/home/user/.hermes/skills/speckit-specify` when on `external_dirs`).
   - If Spec Kit cannot run as defined → typed **`needs_input` BLOCK** and STOP.
     **Do not** freeform-write `partition.json` as a silent substitute.
   - Evidence: Spec Kit seed (e.g. `specs/**/spec.md`) **or** a typed
     `needs_input` block comment — required before Done.
3. **Write-once** `evidence/briefs/partition.json` (`rhoai3.partition/v1`) **only after**
   Spec Kit seed (or Operator disposition of a typed BLOCK) — Input-manifest sources
   only; **not** `evidence/bodies/*`.
4. **Partition-coverage gate** (Architect E-20260811T133858Z): run
   `python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py . --write-receipt evidence/receipts/partition-coverage/latest.json`
   — must print `PARTITION_COVERAGE: VALID` (fail-closed). See
   `governance/contracts/partition-coverage.md`.
5. **STOP** — do **not** run `/speckit-tasks` or `create-m3-implementer.sh` here.
   Lead/Operator dispatch **M2b** next (parent = this task).

## Done when
- Spec Kit invoke evidenced (seed artifact) **or** typed `needs_input` BLOCK recorded
- `evidence/briefs/partition.json` present (write-once) only after Spec Kit path satisfied
- `check-partition-coverage.py` → **VALID** (+ receipt)
- **No** M3 children created on this card

## Constraints
- workspace: dir:/projects/modernized
- AD-009 hard budget / crash requeue / protocol_untyped as for prior M2 law
- Soft-K @2700 not used on M2a (max_runtime=3600); no MiniMax
- **Completion consumer (Operator E-20260811T120200Z):** never self-declare a binding
  Done criterion **N/A**. Before `kanban_complete`, run
  `python3 .hermes/enforcement/dispatch-phase/scripts/check-completion-na-reject.py --text "$YOUR_RESULT_SUMMARY"`.
  Exit 1 ⇒ typed `needs_input` (do not complete). Workers satisfy or BLOCK — never amend.
EOF
    TITLE="M2a PLAN: story partition + briefs"
    ;;
  M2b)
    cat >"${BODY_FILE}" <<'EOF'
# M2b PLAN — SDD emit + create-m3 children (R-AB.2 / pre-v12 R1)

Phase: M2b per `.hermes/phase-dispatch.yaml`
Requires: M2a partition present; m1-findings ack

## Execute-as-defined-or-stop (Operator E-20260811T113700Z)
Unexecutable obligation → typed **`needs_input` BLOCK**. Never silent substitution.

## Input manifest
### Required present
- evidence/acks/m1-findings.ack.yaml
- evidence/findings-handoff.json
- evidence/briefs/partition.json
- governance/schemas/partition.md
### Forbidden absent
- evidence/bodies/m3-*.json

## Job
1. Require `evidence/briefs/partition.json` — typed `needs_input` BLOCK if missing (run M2a first).
2. **Per-artifact Spec Kit resume ladder** (Architect E-20260811T122959Z — decision-complete;
   contract `governance/contracts/m2b-resume-ladder.md`; retired inverted v11 R-M2.6
   compound jump under M2a/M2b split — see retired `m2-resume-from-artifacts.md`):
   - **`/speckit-specify`:** precondition = no `specs/**/spec.md` (or workspace Spec Kit
     equiv). **Skip iff** `spec.md` already exists (M2a normally left it). Do **not**
     invent specs.
   - **`/speckit-plan`:** precondition = `spec.md` present. **Skip iff** `plan.md`
     already exists. Otherwise run `/speckit-plan` (cite `sdd-ordering.md` +
     `story-sizing.md`). **Never** jump over plan just because `spec.md` exists.
   - **`/speckit-tasks`:** always last. Precondition = `plan.md` present — else typed
     `needs_input` BLOCK. Then emit tasks artifacts.
3. Create implementer cards via **`create-m3-implementer.sh`** only (not bare create).
   **Required:** `--parent <this task id>` on every create (Operator E-20260811T133000Z #5).
   Bodies are generated here — do not consume golden specimen packets.
   Cards are **born blocked** (no auto-dispatch). Do **not** unblock/dispatch M3
   children from M2b (Deputy E-20260811T131900Z serial law).
   **Body refs (Deputy E-20260811T131200Z):**
   - `brief_identity_ack`: `sha256: "pending"` + intended future ack path
     (e.g. `evidence/acks/brief-identity-<story>.ack.yaml`). Do **not**
     substitute `partition.json` or invent prose digests.
   - `legacy_locus`: 64-hex of the primary legacy **file** (not a directory;
     not `see-harvest-referent` prose).
4. Before `kanban_complete`: run
   `bash .hermes/enforcement/dispatch-phase/scripts/assert-m2b-created-cards-claim.sh . $TASK_ID`
   (writes `evidence/runs/$TASK_ID/m2b-created-cards-ok.json`). Asserts
   **partition story_ids == created card story_ids** (F8a — not stamp self-check).
   Pass matching ids as `created_cards`. **`created_cards=[]` is REJECT** when
   derived claim is nonempty.
   **F8b machinery:** `python3 .hermes/home/scripts/enforce-m2b-created-cards-claim.py . --task $TASK_ID`
   reclaims `done` without the ok receipt — prose is not the gate.
5. Stop for Operator `brief-identity.ack.yaml`.

## Done when
- Spec Kit tasks artifacts present
- M3 children created via `create-m3-implementer.sh --parent $TASK_ID`
- `assert-m2b-created-cards-claim.sh` OK (partition set equality + receipt)
- brief-identity ack out of band (Operator)

## Constraints
- workspace: dir:/projects/modernized
- Do not rewrite write-once `partition.json`
- Prefer short tool results; avoid bulk-pasting bodies (context margin)
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
ground-in-harvest + spring-to-quarkus-patterns before edits. One task ⇒ one role.

## Typed body (required — not a pointer to tasks.md)
Write/attach `evidence/bodies/<task>.json` with:
- `task_id`, `task_type=implementing`, `phase=M3`
- `files_in_scope`: non-empty paths
- `refs[]` including `brief_identity_ack` (`pending` until Operator ack, then 64-hex)
  and `legacy_locus` (64-hex of primary legacy file)
- optional `spec_path` / `plan_path` / `tasks_path` digests
Validate: `python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-kanban-body.py /projects/modernized`

## Done when
- Scoped compile/tests for files_in_scope pass, or typed BLOCK with residue named
- Provenance record writable under evidence/tasks/ (AD-H §19)

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
Run required_checks from phase-dispatch.yaml. Write verdict JSON under evidence/verdicts/.

## Pre-v12 R2 — M4 floor (required)
1. `bash .hermes/skills/gates/check-release-readiness/scripts/run-m4-floor.sh /projects/modernized`
2. `python3 .hermes/skills/gates/check-release-readiness/scripts/check-m4-floor-receipts.py evidence/receipts/m4-floor/latest`
3. Bank receipts; do **not** claim PROVISIONAL_ACCEPT without boot_health + endpoint_smoke PASS (g4_hook may be INCONCLUSIVE / SAMPLE).
Contract: `governance/contracts/m4-floor-runner.md`. `ad010_demo=false` until Architect promotes.
EOF
    TITLE="M4 VERIFY: provisional accept"
    ;;
  M5)
    cat >"${BODY_FILE}" <<'EOF'
# M5 CLOSE - Hermes-native (validator)

Phase: M5 — full ACCEPT path. Re-run scan-with-mta as needed for findings-delta.
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
  --created-by dispatch-phase
  --body "$(cat "${BODY_FILE}")"
)
for s in "${SKILLS[@]}"; do
  CREATE_ARGS+=(--skill "${s}")
done
for p in "${PARENTS[@]:-}"; do
  [[ -n "${p}" ]] && CREATE_ARGS+=(--parent "${p}")
done

echo "dispatch-phase: phase=${PHASE} phase=${PHASE} max_runtime=${MAX_RUNTIME}s skills=${SKILLS[*]}"
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
mkdir -p "${ROOT}/evidence/derived"
echo "${TASK_ID}" >"${ROOT}/evidence/derived/phase-${PHASE}-task-id.txt"
# Operator E-20260811T114300Z — every dispatch must commission Review live adherence
# observation. Host Lead files ledger Need from this marker (same commit as dispatch).
{
  echo "schema: rhoai3.review-adhere-observe-need/v1"
  echo "task_id: ${TASK_ID}"
  echo "phase: ${PHASE}"
  echo "need: Review:adhere-observe-${TASK_ID}"
  echo "operator_event: E-20260811T114300Z"
  date -u +'ts: %Y-%m-%dT%H:%M:%SZ'
} >"${ROOT}/evidence/derived/review-adhere-observe-needed.yaml"
echo "REVIEW_ADHERE_OBSERVE=${TASK_ID}"
echo "dispatch-phase: created ${TASK_ID} (Review:adhere-observe-${TASK_ID} REQUIRED)"

hermes kanban dispatch --max "${DISPATCH_MAX}" --json || true
hermes kanban ls 2>&1 | head -40
echo "OK: ${PHASE} → ${TASK_ID} (Hermes-native). Track: hermes kanban watch / show ${TASK_ID}"
echo "OK: file ledger Need Review:adhere-observe-${TASK_ID} (host: .wake/file-review-adhere-observe.py)"
