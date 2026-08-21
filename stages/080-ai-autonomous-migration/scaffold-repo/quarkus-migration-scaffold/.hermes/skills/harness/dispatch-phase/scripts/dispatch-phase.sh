#!/usr/bin/env bash
# Create + dispatch a Hermes Kanban task for one M-phase from phase-dispatch.yaml.
# Cite: platform/known-hermes-behaviours (B5 daemon/gateway;
# B6 promote vs park-at-birth). This script is the interim dispatcher half.
# Usage:
#   bash .hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh M1
#   bash .hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh M2 --parent t_xxx
#   bash .hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh M1 --dry-run
# BV19-3: --parent is required for every phase except M1 (the DAG root).
# After M2 done: holder session follows references/mint-m3-hermes.md (not mint-m3-wave.sh)
set -euo pipefail

case "${1:-}" in
  -h|--help)
    cat <<'USAGE'
dispatch-phase.sh — create + dispatch one M-phase Kanban task from phase-dispatch.yaml.

Usage:
  dispatch-phase.sh M1|M2|M3|M4|M5|factory [--parent ID] [--dry-run]
  (M2a/M2b retired GR2 — use M2; M3 mint is holder session / mint-m3-hermes.md)
  BV19-3: --parent required except M1.

This is an interface probe / help surface only when -h/--help is passed.

Env (v20-flow / Architect E-20260816T185414Z):
  DISPATCH_START_DAEMON=0  default — do not spawn `kanban daemon --force`
  DISPATCH_MAX=0           default — create parks the card; does not spawn
  DISPATCH_PARK_CHAIN=1    default — M1 create also parks M2 + M3 holder
                           (todo + --parent; omit --initial-status blocked).
                           Do not park M4/M5 on the holder (mint-complete
                           would unpark VERIFY). Set 0 for a single card.
  Set DISPATCH_START_DAEMON/DISPATCH_MAX to 1 only for a campaign that has claimed C-1(a).

Serial GO (one in-flight) AFTER create — native claim+spawn, not chat -q:
  hermes kanban dispatch --max 1
That is Hermes _default_spawn: status running + $HERMES_HOME/kanban/logs/<id>.log
Do NOT: hermes chat -q "work kanban task t_xxx"  (no claim, sqlite stays ready, no official log)
Do NOT: hermes kanban daemon --force            (deprecated; claim races)
USAGE
    exit 0
    ;;
esac

PHASE="${1:-}"
shift || true
PARENTS=()
DRY_RUN=0
DISPATCH_MAX="${DISPATCH_MAX:-0}"
DISPATCH_START_DAEMON="${DISPATCH_START_DAEMON:-0}"
DISPATCH_PARK_CHAIN="${DISPATCH_PARK_CHAIN:-1}"
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
  echo "  (M2a/M2b retired — use M2; M3 mint is holder session / mint-m3-hermes.md)" >&2
  exit 2
}
if [[ "${PHASE}" == "M2a" || "${PHASE}" == "M2b" ]]; then
  echo "dispatch-phase: REFUSE M2a/M2b — M2a/M2b split retired (GR2); dispatch M2 then holder mint-m3-hermes.md" >&2
  exit 2
fi

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
DISPATCH_YAML="${ROOT}/.hermes/phase-dispatch.yaml"
export HERMES_HOME="${HERMES_HOME:-${ROOT}/.hermes/home}"
export HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR:-/projects/.platform/hermes}"
export HERMES_WRITE_SAFE_ROOT="${HERMES_WRITE_SAFE_ROOT:-${ROOT}}"

die() { echo "dispatch-phase: $*" >&2; exit 1; }
[[ -f "${LINK_GRAPH}" ]] || die "missing ${LINK_GRAPH} (BV19-3)"

# BV19-3: link / --parent is the phase DAG. M1 is the only root.
# Do not infer the previous phase from titles or phase-*-task-id.txt.
if [[ "${PHASE}" != "M1" ]]; then
  [[ ${#PARENTS[@]} -gt 0 ]] \
    || die "BV19-3: --parent REQUIRED for ${PHASE} (link is the phase DAG; M1 is the only root)"
fi

[[ -f "${DISPATCH_YAML}" ]] || die "missing ${DISPATCH_YAML}"
command -v python3 >/dev/null 2>&1 || die "python3 required"

# Pre-v12 R0/R3 — tip sync must be green before any phase create
python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/check-create-path-tip-sync.py" "${ROOT}" \
  || die "create-path tip sync failed (R0/R3)"
# Seat Hermes pin (111730Z / 132010Z) — live dispatch only; dry-run stays laptop-safe.
# Contract is binary-local (--help + VALID_INITIAL_STATUSES), not the public CLI page.
if [[ "${DRY_RUN}" -eq 0 ]]; then
  python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/assert-seat-hermes-pin.py" "${ROOT}" \
    || die "seat Hermes pin mismatch (pins.json v0.20.4; omit --initial-status yields ready)"
fi
# Architect E-20260811T170706Z Class A — quarantine tombstones before any phase create
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/assert-quarantine-tombstones.py" "${ROOT}" \
  || die "quarantine tombstones resurrected — wipe + purge restorer (write-fence / quarantine tombstones)"
# EX-2: S-008 resurrection-order scar retired (not in golden scaffold)
python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/check-phase-attach-matrix.py" "${ROOT}" \
  || die "phase attach matrix failed"
python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/check-phase-body-script-refs.py" "${ROOT}" \
  || die "phase body script refs failed (R0 / Deputy E-20260811T112700Z)"
python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/check-phase-input-manifest.py" "${ROOT}" "${PHASE}" \
  || die "phase input manifests failed (R0 / Operator E-20260811T113700Z)"
python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/check-decision-complete-cards.py" "${ROOT}" \
  || die "decision-complete card lint failed (R0 / Architect E-20260811T122959Z)"
# Architect E-20260811T121308Z — provision-owns-tools: Spec Kit preseed before M2
if [[ "${PHASE}" == "M2" ]]; then
  python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/check-specify-preseed.py" "${ROOT}" \
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
  # Research E-20260817T125528Z / Architect 131412Z — path-invoke only;
  # hide from skills_list() (token tax). Scripts still run by path.
  disabled:
    - dispatch-phase
    - enforce-authority-boundary
    - ground-in-harvest
    - record-run-evidence
    - validate-contracts
  external_dirs:
    - ${ROOT}/.hermes/skills
    - ${HOME}/.hermes/skills
kanban:
  # Architect V34-6: dest home must pin GitOps kanban keys. Official
  # auto_decompose default is true (holder-decompose hazard in triage).
  auto_decompose: false
  dispatch_in_gateway: true
  max_in_progress: 1
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
  python3 - "${HERMES_HOME}/config.yaml" <<'PY' || echo "dispatch-phase: WARN skills.disabled merge failed" >&2
import pathlib, sys
p = pathlib.Path(sys.argv[1])
need = [
    "dispatch-phase",
    "enforce-authority-boundary",
    "ground-in-harvest",
    "record-run-evidence",
    "validate-contracts",
]
text = p.read_text(encoding="utf-8") if p.is_file() else ""
if all(n in text for n in need) and "disabled:" in text:
    raise SystemExit(0)
try:
    import yaml  # type: ignore
except ImportError:
    yaml = None
if yaml is not None:
    data = yaml.safe_load(text) if text.strip() else {}
    if not isinstance(data, dict):
        data = {}
    skills = data.get("skills")
    if not isinstance(skills, dict):
        skills = {}
        data["skills"] = skills
    cur = [str(x) for x in (skills.get("disabled") or [])]
    for n in need:
        if n not in cur:
            cur.append(n)
    skills["disabled"] = cur
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    print("dispatch-phase: merged skills.disabled (125528Z)")
    raise SystemExit(0)
if "disabled:" not in text:
    block = (
        "  disabled:\n"
        "    - dispatch-phase\n"
        "    - enforce-authority-boundary\n"
        "    - ground-in-harvest\n"
        "    - record-run-evidence\n"
        "    - validate-contracts\n"
    )
    if "skills:" in text:
        text = text.replace("skills:\n", "skills:\n" + block, 1)
        p.write_text(text, encoding="utf-8")
        print("dispatch-phase: appended skills.disabled (125528Z)")
PY
  python3 - "${HERMES_HOME}/config.yaml" <<'PY' || echo "dispatch-phase: WARN kanban pin merge failed" >&2
import pathlib, sys
p = pathlib.Path(sys.argv[1])
want = {
    "auto_decompose": False,
    "dispatch_in_gateway": True,
    "max_in_progress": 1,
}
text = p.read_text(encoding="utf-8") if p.is_file() else ""
if all(
    f"{k}:" in text and str(v).lower() in text.lower()
    for k, v in (
        ("auto_decompose", "false"),
        ("dispatch_in_gateway", "true"),
        ("max_in_progress", "1"),
    )
) and "kanban:" in text:
    raise SystemExit(0)
try:
    import yaml  # type: ignore
except ImportError:
    yaml = None
if yaml is None:
    raise SystemExit(1)
data = yaml.safe_load(text) if text.strip() else {}
if not isinstance(data, dict):
    data = {}
kb = data.get("kanban")
if not isinstance(kb, dict):
    kb = {}
    data["kanban"] = kb
changed = False
for k, v in want.items():
    if kb.get(k) != v:
        kb[k] = v
        changed = True
if changed:
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    print("dispatch-phase: merged dest-home kanban pins (V34-6)")
PY
  local stamp_rev="${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/stamp-harness-rev.py"
  if [[ -f "${stamp_rev}" ]]; then
    python3 "${stamp_rev}" --root "${ROOT}" \
      || echo "dispatch-phase: WARN HARNESS_REV stamp failed" >&2
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
  if [[ "${DISPATCH_START_DAEMON}" != "1" ]]; then
    echo "dispatch-phase: daemon not started (DISPATCH_START_DAEMON=${DISPATCH_START_DAEMON}; Architect E-20260816T185414Z daemon never on v20-flow)"
    return 0
  fi
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

# Parse phase seed from YAML via JSON reader (LG7 — do not eval parser output).
PHASE_READER="${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/read-phase-dispatch.py"
MAX_RUNTIME="$(python3 "${PHASE_READER}" --yaml "${DISPATCH_YAML}" --phase "${PHASE}" --print max_runtime_seconds)" \
  || die "phase-dispatch parse failed for ${PHASE}"
MAX_RETRIES="$(python3 "${PHASE_READER}" --yaml "${DISPATCH_YAML}" --phase "${PHASE}" --print max_retries)" \
  || die "phase-dispatch max_retries parse failed for ${PHASE}"
TITLE="$(python3 "${PHASE_READER}" --yaml "${DISPATCH_YAML}" --phase "${PHASE}" --print title)" \
  || die "phase-dispatch title parse failed for ${PHASE}"
_SK_OUT="$(python3 "${PHASE_READER}" --yaml "${DISPATCH_YAML}" --phase "${PHASE}" --print skills)" \
  || die "phase-dispatch skills parse failed for ${PHASE}"
SKILLS=()
while IFS= read -r _sk; do
  [[ -n "${_sk}" ]] && SKILLS+=("${_sk}")
done <<< "${_SK_OUT}"
FW_JSON="$(python3 "${PHASE_READER}" --yaml "${DISPATCH_YAML}" --phase "${PHASE}" --print files_writable_json)" \
  || die "phase-dispatch files_writable parse failed for ${PHASE}"
# Quote labels so check-phase-input-manifest extract_body (^\s+M2\)) skips this
# guard and captures the card heredoc (Operator E-20260818T184010Z).
case "${PHASE}" in
  "M2")
    [[ "${FW_JSON}" != "null" && "${FW_JSON}" != "[]" ]] \
      || die "M2 files_writable unpublished/empty (I-4 / BIND 25a7c1e9)"
    ;;
  "M1"|"M4"|"M5")
    [[ "${FW_JSON}" != "null" ]] \
      || die "${PHASE} files_writable unpublished (I-4; [] is ok)"
    ;;
  "M3")
    [[ "${FW_JSON}" == "null" ]] \
      || die "M3 must omit files_writable (card-resolved; no phase union)"
    ;;
esac

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
2a. Walk types reachable from each inventory row file (no Kanban `--body`):
   `python3 .hermes/skills/analysis/inventory-entry-points/scripts/inventory-type-graph.py --dest-root /projects/modernized --inventory evidence/entry-point-inventory.json -o evidence/type-inventory.json`
3. Load/run **scan-with-mta** - `bash "${HERMES_SKILL_DIR}/scripts/mta-analyze-legacy.sh"` (never invent `--source`; use MTA_RUN_CWD + writable clone when freeze is a-w). Script normalizes findings and emits `evidence/findings-handoff.json` (requires inventory).
4. Schema-validate findings + handoff (runtime skill root / AD-H §7.1):
   `python3 "${HERMES_SKILL_DIR:-.hermes/home/skills/software-development/scan-with-mta}/scripts/check-findings-handoff.py" /projects/modernized`
   Exit: **0=pass**; **1=FAIL→typed BLOCK**; **2=missing script** (harness/lint defect — do not invent).
5. **5.1 gate-record** (Architect `E-20260819T121859Z`): after handoff rc=0, run
   `python3 .hermes/skills/harness/enforce-authority-boundary/scripts/issue-m1-findings-ack.py /projects/modernized`
   (`acknowledged_by: gate:check-findings-handoff`). Do **not** grant as Operator
   and do **not** write `acknowledged_by` worker. rc≠0 → typed BLOCK, not a
   human `needs_input` for the yaml. **M3 brief-identity** is the same
   5.1 pattern (`gate:check-body-digest-match`). M1 must not cite or run
   the M3 issuer.
   M1 ACK GATE complete is the **verifier card** running
   `python3 .hermes/skills/harness/dispatch-phase/scripts/check-m1-verifier.py /projects/modernized`
   (**refuse-on-nonzero**; see `references/m1-verifier.md`). This worker does not complete the gate.

## Constraints
- workspace: dir:/projects/modernized
- Do not hand-edit destination app source.
- Do not run analyze as a detached shell outside this Kanban task.
- Do **not** grant `evidence/acks/m1-findings.json` or any `acknowledged_by` worker role (AR-1.1).
- If blocked, report typed BLOCK and stop.

## Done when
- `evidence/mta-findings.json` validates (`rhoai3.mta-findings/v1-provisional`) — evidence store
- `evidence/entry-point-inventory.json` present
- `evidence/type-inventory.json` present
- `evidence/findings-handoff.json` validates (`rhoai3.findings-handoff/v1`) — M2 planner input
- `evidence/required-extensions.json` present (`rhoai3.required-extensions/v2`) — dest pom apply set
- `evidence/acks/m1-findings.ack.yaml` exists as the 5.1 gate-record (issuer exit 0) — not an Operator GO
EOF
    TITLE="M1 ANALYZE: derive + MTA/kantra + inventory"
    ;;
  M2)
    cat >"${BODY_FILE}" <<'EOF'
# M2 PLAN — partition + Spec Kit (GR2 / AD-016)

Phase: M2 per `.hermes/phase-dispatch.yaml`
Requires: findings-handoff gate + 5.1 `m1-findings.ack.yaml` gate-record (not a human GO)
**Mint is the wave-holder Hermes session** — do **not** run a pillar-head
shell as the M3 create path. After Done, the holder follows
`.hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md`.

## Execute-as-defined-or-stop (Operator E-20260811T113700Z)
Any obligation unexecutable as written (unresolvable gate script, missing
contract, absent required input) → typed **`needs_input` BLOCK**. Never silent
substitution / path invention / specimen-body priming. Measure the harness.

## Input manifest
### Required present
- evidence/acks/m1-findings.ack.yaml
- evidence/findings-handoff.json
- evidence/required-extensions.json
- evidence/entry-point-inventory.json
- evidence/type-inventory.json
- evidence/mta-findings.json
- .hermes/skills/harness/enforce-authority-boundary/scripts/issue-m1-findings-ack.py
- .hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py
### Must not exist
- evidence/bodies/*.json
- evidence/bodies/m3-*.json

## Job
0. **Spec Kit preseed verify-or-BLOCK** (Architect E-20260811T121308Z provision-owns-tools):
   First init M2 checkpoint (V34-3):
   `python3 .hermes/skills/harness/dispatch-phase/scripts/holder-checkpoint.py init --kind m2 --root /projects/modernized`
   Stamp `--next` after each step (`preseed|findings|inventory|speckit|assemble|done`).
   Before Done: `python3 .hermes/skills/harness/dispatch-phase/scripts/holder-checkpoint.py check --kind m2 --root /projects/modernized`
   Workspace provision (devfile postStart) owns `specify init` + Non-Goals override.
   **Agent has no init authority.** Prove with command evidence:
   `test -d .specify && test -f .specify/.rhoai3-ads-provisioned && ls -la .specify/templates/overrides/`
   If missing/invalid → typed **`needs_input` BLOCK** and STOP.
   **Forbidden:** inventing `.specify/`, manual `specify init`, copying overrides by hand.
1. Findings-handoff gate (canonical scan-with-mta — Operator E-20260817T105440Z / row 6):
   `python3 "${HERMES_SKILL_DIR:-.hermes/home/skills/software-development/scan-with-mta}/scripts/check-findings-handoff.py" /projects/modernized`
   Exit: **0=pass**; **1=FAIL→typed BLOCK**; **2=missing script** → `needs_input` (lint/harness defect — do not invent paths).
   Then 5.1 record (Architect `E-20260819T121859Z`):
   `python3 .hermes/skills/harness/enforce-authority-boundary/scripts/issue-m1-findings-ack.py /projects/modernized`
   Exit **0** = `m1-findings.ack.yaml` is a gate-record. Exit **1** = handoff not green → typed BLOCK.
   Do **not** `needs_input` for a missing **human** yaml. **M3 brief-identity**
   is the same 5.1 pattern (`gate:check-body-digest-match`). M2 must not
   cite or run the M3 issuer.
2. **Read inventory before specify** (Architect E-20260817T203500Z):
   Open `evidence/entry-point-inventory.json`, `evidence/type-inventory.json`,
   and `evidence/required-extensions.json` **before** invoking
   `/speckit-specify`. Prove the read (tool evidence). Spec functional
   requirements MUST enumerate every inventory `http_path` (and `http_method`
   when present). Cover every **source** type-inventory `dest_file` in `tasks.md` (one
   creator phase per dest `.java` path). Generated types: carry the spec and
   configure the dest generator — do not Create their `.java`. Setup T001 /
   `extensions_apply` must name every artifactId in required-extensions.json
   (T-3 native rewrite; do not invent quarkus-spring-*). **Forbidden:** asserting a count ("all 34 endpoints") in
   place of the list; inventing routes not in the inventory.
3. **Spec Kit invoke-or-BLOCK** (Architect E-20260811T115316Z — not soft Prefer):
   - Hard-invoke attached skill `speckit-specify` via `skill_view` / `/speckit-specify`
     (discoverable under `/home/user/.hermes/skills/speckit-specify` when on `external_dirs`).
   - If Spec Kit cannot run as defined → typed **`needs_input` BLOCK** and STOP.
     **Do not** freeform-write `partition.json` as a silent substitute.
   - Evidence: Spec Kit seed (e.g. `specs/**/spec.md`) **or** a typed
     `needs_input` block comment — required before Done.
4. **Do not write** `evidence/briefs/partition.json` on this dest. Orchestrator
   `handover-mint.py` writes that file as a **receipt** from `tasks.md`
   (A-4/A-6). Path-A authoring is a fail-closed refuse.
5. **Scratch-assembly Done oracle** (Architect E-20260818T221200Z form a):
   After `tasks.md` exists, copy `tasks.md` + `evidence/` to a throwaway dir
   and run `handover-mint.py --write` **there**. Require exit 0.
   `python3 .hermes/skills/harness/dispatch-phase/scripts/scratch-assemble-mint.py /projects/modernized`
   Exit: **0=mintable**; **nonzero=typed `needs_input` BLOCK** (plan cannot assemble — do not dest-rewrite).
   After `--write`, the oracle fail-closes invented receipt endpoints
   (`assert-partition-invented-routes.py` — the only plan-level HTTP gate)
   and, when scratch has `legacy-at-3`, runs existing
   `python3 .hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py`
   + `python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-dependency-closure.py`
   on minted bodies (V34-8; no second gate), then
   `python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-partition-topological-order.py`
   (M2 must not complete with a partition the holder would refuse).
   Constitution VII is guidance, not a gate. Keep
   `assert-compiled-route-fidelity.py` for compiled-tree drift.
   **Forbidden:** `--dry-run` as this gate; authoring dest `partition.json`; growing `handover-mint.py`.
   Holder mint still follows `mint-m3-hermes.md` after Done.
6. **Per-artifact Spec Kit resume ladder** (Architect E-20260811T122959Z — decision-complete;
   contract `.hermes/skills/sdd/check-spec-readiness/references/sdd-ordering.md`; retired inverted v11 R-M2.6 and
   M2 unified PLAN — see `governance/retired/m2b-resume-ladder.md`):
   - **`/speckit-specify`:** precondition = no `specs/**/spec.md` (or workspace Spec Kit
     equiv). **Skip iff** `spec.md` already exists. Do **not** invent specs.
   - **`/speckit-plan`:** precondition = `spec.md` present. **Skip iff** `plan.md`
     already exists. Otherwise run `/speckit-plan` (cite `sdd-ordering.md` +
     `story-sizing.md`). **Never** jump over plan just because `spec.md` exists.
   - **`/speckit-clarify`:** between specify and plan when the overlay inserted it.
   - **`/speckit-tasks`:** always last. Precondition = `plan.md` present — else typed
     `needs_input` BLOCK. Emit `tasks.md` only — **no** `kanban create`, **no**
     typed M3 bodies, **no** `partition.json`.
7. **STOP** — do **not** create M3 Kanban children on this card and do
   **not** ask the demo user to run a mint script. The **holder** session
   follows `.hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md`
   (`165300Z`). Cards remain born-parked; serial GO separate.

## Done when
- Spec Kit invoke evidenced (seed + plan + tasks.md) **or** typed `needs_input` BLOCK recorded
- `spec.md` enumerates every inventory `http_path` (not a count)
- Resource task lines include literal `@Path("...")` for owned HTTP routes
- Scratch `handover-mint.py --write` exit 0 (`scratch-assemble-mint.py`) — dest `partition.json` untouched; invented endpoints refuse; type-inventory source dest twins covered when that file is present (skip dest twins generated_sources classifies as generated); type-closure (stamp + assert-dependency-closure) when scratch has legacy-at-3; scratch topological-order gate exit 0; scratch relocate-descendant MULTI_OWNER gate exit 0; `provider: generated` skips DEST_MISS and requires generator inputs owned; generated types require a generator plugin token in `tasks.md` (`python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-tasks-generator-uptake.py`)
- M2 `checkpoint.json` present (`holder-checkpoint.py check --kind m2`)
- **No** `partition.json` authored on this card (handover-mint writes the receipt)
- **No** M3 Kanban children created on this card

## Constraints
- workspace: dir:/projects/modernized
- Write-set (Architect E-20260816T185414Z / AD-013): `.specify/` and `specs/`
  only. Native Spec Kit writes those trees. Do **not** export
  `SPECIFY_FEATURE_DIRECTORY` to dodge `.specify/feature.json`. Do not write
  `src/` or `pom.xml` on this card.
- Do not author `partition.json` (handover-mint receipt only)
- Prefer short tool results; avoid bulk-pasting bodies (context margin)
- AD-009 hard budget / crash requeue / protocol_untyped as prior M2 law; no MiniMax
- Soft-K @2700 not used on M2 (max_runtime=3600); no MiniMax
- **Completion consumer (Operator E-20260811T120200Z):** never self-declare a binding
  Done criterion **N/A**. Before `kanban_complete`, run
  `python3 .hermes/skills/harness/dispatch-phase/scripts/check-completion-na-reject.py --text "$YOUR_RESULT_SUMMARY"`.
  Exit 1 ⇒ typed `needs_input` (do not complete). Workers satisfy or BLOCK — never amend.
EOF
    TITLE="M2 PLAN: partition + Spec Kit (holder mints M3)"
    ;;
  M3)
    # Architect 102636Z — park-at-birth M3 is the WAVE HOLDER (mint, do not
    # implement). Body is holder-card-body.md; no implementer skill pin.
    cat "${ROOT}/.hermes/skills/harness/dispatch-phase/references/holder-card-body.md" \
      >"${BODY_FILE}"
    TITLE="M3 WAVE HOLDER: mint story children"
    SKILLS=()
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
Contract: `.hermes/skills/gates/check-release-readiness/references/m4-floor-runner.md`. `ad010_demo=false` until Architect promotes.
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

# C-2(a) — single-persona. Product default is the worker identity (R-V14.10).
ASSIGNEE="$(
  python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/resolve-seat-assignee.py" "${PHASE}"
)"
[[ -n "${ASSIGNEE}" ]] \
  || die "C-2(a): assignee resolve failed for phase ${PHASE}"

CREATE_ARGS=(
  --json
  --assignee "${ASSIGNEE}"
  --workspace "dir:${WORKSPACE_DIR}"
  --max-runtime "${MAX_RUNTIME}"
  --max-retries "${MAX_RETRIES}"
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
# Park-at-birth: omit --initial-status (Architect 100812Z: todo+parent).
# M1 stays omit→ready. M3 phase stub is the WAVE HOLDER (102636Z).
if [[ -n "${DISPATCH_INITIAL_STATUS:-}" ]]; then
  CREATE_ARGS+=(--initial-status "${DISPATCH_INITIAL_STATUS}")
fi

echo "dispatch-phase: phase=${PHASE} assignee=${ASSIGNEE} max_runtime=${MAX_RUNTIME}s max_retries=${MAX_RETRIES} skills=${SKILLS[*]}"
echo "dispatch-phase: idempotency_key=${IDEM_KEY} workspace=dir:${WORKSPACE_DIR}"

B3_ARGS=("${ROOT}")
for s in "${SKILLS[@]}"; do
  [[ -n "${s}" ]] && B3_ARGS+=(--skill "${s}")
done
python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/assert-skills-not-disabled.py" \
  "${B3_ARGS[@]}" \
  || die "B3: declared skill is in skills.disabled"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "dispatch-phase: DRY_RUN — would create: ${TITLE}"
  printf '  %q' hermes kanban create "${CREATE_ARGS[@]}" "${TITLE}"
  echo
  if [[ "${PHASE}" == "M1" && "${DISPATCH_PARK_CHAIN}" == "1" ]]; then
    echo "dispatch-phase: DRY_RUN park-at-birth would then create M2 M3 (holder) todo+parent, omit --initial-status blocked"
  fi
  exit 0
fi

command -v hermes >/dev/null 2>&1 || die "hermes not on PATH"
hermes profile show "${ASSIGNEE}" >/dev/null 2>&1 \
  || die "C-2(a): assignee profile '${ASSIGNEE}' missing (dispatcher would silent-fail)"
# L7: native BLOCK_RECURRENCE_LIMIT → triage at v0.20.2 (R2).
ensure_daemon
cd "${WORKSPACE_DIR}"
OUT="$(hermes kanban create "${CREATE_ARGS[@]}" "${TITLE}")"
echo "${OUT}"
TASK_ID="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("id") or "")' <<<"${OUT}")"
[[ -n "${TASK_ID}" ]] || die "kanban create returned no id"
# BV19-3: the txt pointer is convenience, not the DAG. Read the link graph.
for p in "${PARENTS[@]:-}"; do
  [[ -n "${p}" ]] || continue
  hermes kanban show "${TASK_ID}" --json \
    | python3 "${LINK_GRAPH}" --expect-parent "${p}" \
    || die "BV19-3: ${TASK_ID} missing parent link ${p}"
done
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

# Architect 102636Z / 100812Z — park M2 + M3 WAVE HOLDER at M1 create
# (todo + --parent; omit --initial-status blocked). Do not park M4/M5 as
# children of the holder. Do not dest-enable the dispatch-phase skill pin.
# Children inherit DISPATCH_MAX=0.
if [[ "${PHASE}" == "M1" && "${DISPATCH_PARK_CHAIN}" == "1" ]]; then
  prev="${TASK_ID}"
  export DISPATCH_PARK_CHAIN=0
  unset DISPATCH_INITIAL_STATUS
  export DISPATCH_MAX=0
  export DISPATCH_START_DAEMON=0
  _self="$(cd "$(dirname "$0")" && pwd)/dispatch-phase.sh"
  for next in M2 M3; do
    echo "dispatch-phase: park-at-birth ${next} --parent ${prev}"
    "${_self}" "${next}" --parent "${prev}"
    prev="$(cat "${ROOT}/evidence/derived/phase-${next}-task-id.txt")"
    [[ -n "${prev}" ]] || die "park-at-birth: missing ${next} id after create"
  done
fi

if [[ "${FW_JSON}" != "null" ]]; then
  mkdir -p "${ROOT}/evidence/runtime/write-sets"
  python3 - "${ROOT}" "${TASK_ID}" "${PHASE}" "${FW_JSON}" <<'PY'
import json, sys
from pathlib import Path
root, task, phase, fw_json = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
fw = json.loads(fw_json)
if not isinstance(fw, list):
    raise SystemExit(f"dispatch-phase: {phase} files_writable is not a list")
doc = {
    "schema": "rhoai3.write-set-cache/v1",
    "authority": "cache-not-policy",
    "task_id": task,
    "files_writable": fw,
}
ws = root / "evidence" / "runtime" / "write-sets"
ws.mkdir(parents=True, exist_ok=True)
(ws / f"{task}.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
print(f"dispatch-phase: {phase} write-set cache {task} → {fw!r} (cache not policy)")
PY
else
  echo "dispatch-phase: ${PHASE} omits files_writable — no phase write-set cache (card-resolved)"
fi

if [[ "${DISPATCH_MAX}" -gt 0 ]]; then
  hermes kanban dispatch --max "${DISPATCH_MAX}" --json || true
else
  echo "dispatch-phase: dispatcher off (DISPATCH_MAX=${DISPATCH_MAX}; Architect E-20260816T185414Z)"
fi
hermes kanban ls 2>&1 | head -40
echo "OK: ${PHASE} → ${TASK_ID} (Hermes-native). Track: hermes kanban watch / show ${TASK_ID}"
echo "OK: file ledger Need Review:adhere-observe-${TASK_ID} (marker: evidence/derived/review-adhere-observe-needed.yaml)"
