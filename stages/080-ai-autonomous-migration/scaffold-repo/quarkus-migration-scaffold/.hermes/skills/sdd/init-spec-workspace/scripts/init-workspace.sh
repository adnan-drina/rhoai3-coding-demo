#!/usr/bin/env bash
# AD-S — provision-time spec-kit init for the migration workspace (modernized).
#
# Runs in /projects/modernized (or $1). Does NOT commit .specify/ into the
# golden scaffold — it creates .specify/ in the live workspace only.
#
#   specify init --here --integration hermes --force --ignore-agent-tools
#   + Non-Goals override from this skill's assets/spec-template.md
#   + external_dirs reminder when HERMES_HOME is relocated
#
# Idempotent: skips when .specify/.rhoai3-ads-provisioned exists.
set -euo pipefail

# --dry-run as first arg or DRY_RUN=1: print plan and exit 0 before installs.
if [[ "${1:-}" == "--dry-run" ]]; then
  shift
  DRY_RUN=1
fi
DRY_RUN="${DRY_RUN:-0}"

ROOT="$(cd "${1:-.}" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Skill root = parent of scripts/ (self-contained asset home — Deputy E-172448Z).
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ASSET_OVERRIDE="${SKILL_DIR}/assets/spec-template.md"
# Workspace tip may also carry the skill under ROOT/.hermes/skills/... when
# HERMES_SKILL_DIR is not this SCRIPT_DIR tree (relocated home copy).
if [ ! -f "${ASSET_OVERRIDE}" ]; then
  ALT="${ROOT}/.hermes/skills/sdd/init-spec-workspace/assets/spec-template.md"
  if [ -f "${ALT}" ]; then
    ASSET_OVERRIDE="${ALT}"
    SKILL_DIR="$(cd "$(dirname "${ALT}")/.." && pwd)"
  fi
fi
MARKER="${ROOT}/.specify/.rhoai3-ads-provisioned"
LOG_PREFIX="init-spec-workspace"

log() { echo "[${LOG_PREFIX}] $*" >&2; }
die() { echo "[${LOG_PREFIX}] ERROR: $*" >&2; exit 1; }

# UPLIFT-2: progress + human lines on stderr; one JSON object on stdout.
emit_ok() {
  local human="$1"
  shift
  python3 -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1]),separators=(",",":")))' "$1"
  printf '%s\n' "${human}" >&2
}

[ -d "${ROOT}" ] || die "missing root ${ROOT}"
[ -f "${ASSET_OVERRIDE}" ] || die "missing Non-Goals override asset at ${ASSET_OVERRIDE} (expected under init-spec-workspace/assets/)"

if [[ "${DRY_RUN}" == "1" ]]; then
  log "DRY-RUN: ROOT=${ROOT}"
  log "DRY-RUN: MARKER=${MARKER}"
  log "DRY-RUN: ASSET_OVERRIDE=${ASSET_OVERRIDE}"
  log "DRY-RUN: would run: specify init --here --integration hermes --force --ignore-agent-tools"
  log "DRY-RUN: would copy override → .specify/templates/overrides/spec-template.md"
  log "DRY-RUN: would write marker ${MARKER}"
  emit_ok "[${LOG_PREFIX}] DRY-RUN complete" "$(python3 -c 'import json,sys; print(json.dumps({"script":"init-workspace","ok":True,"dry_run":True,"root":sys.argv[1]}))' "${ROOT}")"
  exit 0
fi

if [ -f "${MARKER}" ]; then
  TS="$(cat "${MARKER}")"
  HUMAN="[${LOG_PREFIX}] already provisioned (${TS}) — skip"
  emit_ok "${HUMAN}" "$(python3 -c 'import json,sys; print(json.dumps({"script":"init-workspace","ok":True,"skipped":True,"root":sys.argv[1],"marker":sys.argv[2],"provisioned_at":sys.argv[3]}))' "${ROOT}" "${MARKER}" "${TS}")"
  exit 0
fi

# Refuse runs that would create .specify/ outside a live workspace (AD-S S.4).
# Mechanical assert (check-specify-absent.py) replaces the retired
# DO_NOT_COMMIT_SPECIFY note. Workspaces live under /projects/*; intentional
# dry-runs set FORCE_AD_S_PROVISION=1.
case "${ROOT}" in
  /projects/*) ;;
  *)
    if [ "${FORCE_AD_S_PROVISION:-}" != "1" ]; then
      die "refusing AD-S init in scaffold/source tree (workspace: /projects/*; dry-run: FORCE_AD_S_PROVISION=1)"
    fi
    ;;
esac

ensure_specify() {
  if command -v specify >/dev/null 2>&1; then
    return 0
  fi
  export PATH="${HOME}/.local/bin:${PATH}"
  if command -v specify >/dev/null 2>&1; then
    return 0
  fi
  if ! command -v uv >/dev/null 2>&1; then
    log "installing uv…"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
  fi
  command -v uv >/dev/null 2>&1 || die "uv not available after install"
  # R-HX.1 — pin Spec Kit (see governance/contracts/tooling-pins.md)
  local SPECIFY_PIN="${SPECIFY_CLI_VERSION:-0.16.1}"
  log "installing specify-cli==${SPECIFY_PIN} via uv tool…"
  uv tool install "specify-cli==${SPECIFY_PIN}"
  export PATH="${HOME}/.local/bin:${PATH}"
  command -v specify >/dev/null 2>&1 || die "specify not on PATH after uv tool install"
}

ensure_specify

cd "${ROOT}"
log "running: specify init --here --integration hermes --force --ignore-agent-tools"
# --ignore-agent-tools: workspace may not expose a hermes binary on PATH at
# postStart; Hermes skills still install under ~/.hermes/skills (AD-S / §9).
specify init --here --integration hermes --force --ignore-agent-tools

[ -d "${ROOT}/.specify" ] || die "specify init did not create .specify/"

mkdir -p "${ROOT}/.specify/templates/overrides"
cp "${ASSET_OVERRIDE}" "${ROOT}/.specify/templates/overrides/spec-template.md"
log "installed Non-Goals override → .specify/templates/overrides/spec-template.md"

# external_dirs: when HERMES_HOME is relocated away from ~/.hermes, spec-kit
# still writes skills to Path.home()/.hermes/skills — keep both on the list.
note_external_dirs() {
  local note="${ROOT}/.hermes/skills/sdd/init-spec-workspace/EXTERNAL_DIRS.note"
  mkdir -p "$(dirname "${note}")"
  cat > "${note}" <<'EOF'
AD-S / AD-002B — skills.external_dirs after specify init

spec-kit's Hermes integration installs skills under:
  ~/.hermes/skills/   (Path.home() — ignores $HERMES_HOME)

Project skills live under:
  <modernized>/.hermes/skills/

If Managed Scope relocates HERMES_HOME to .hermes/home/ (or /etc/hermes),
ensure the Hermes profile lists BOTH:
  - <modernized>/.hermes/skills
  - $HOME/.hermes/skills

Do not remove the Path.home() entry or /speckit-* skills become invisible.
EOF
  log "wrote ${note}"
}
note_external_dirs

# Enforce (not merely remind) when HERMES_HOME is relocated — Operator
# no-compromise E-20260808T075048Z / AD-S.
if [ -n "${HERMES_HOME:-}" ]; then
  default_hh="${HOME}/.hermes"
  if [ "$(cd "${HERMES_HOME}" 2>/dev/null && pwd -P)" != "$(cd "${default_hh}" 2>/dev/null && pwd -P)" ]; then
    python3 "$(cd "$(dirname "$0")" && pwd)/check-external-dirs.py" "${ROOT}" \
      || die "external_dirs assert failed (HERMES_HOME relocated)"
  fi
fi

# Stop rule stamp (also in AGENTS.md / skill)
cat > "${ROOT}/.specify/AD-S-STOP-RULE.md" <<'EOF'
# AD-S stop rule

After `/speckit-tasks` (optional `/speckit-analyze`), convert `tasks.md` into
Hermes `kanban_create()` calls.

**Never run `/speckit-implement`.** Kanban is the only executor (AD-006 / AD-H).
EOF

date -u +%Y-%m-%dT%H:%M:%SZ > "${MARKER}"
TS="$(cat "${MARKER}")"
HUMAN="[${LOG_PREFIX}] OK — AD-S provision complete (marker ${MARKER})"
emit_ok "${HUMAN}" "$(python3 -c 'import json,sys; print(json.dumps({"script":"init-workspace","ok":True,"skipped":False,"root":sys.argv[1],"marker":sys.argv[2],"provisioned_at":sys.argv[3]}))' "${ROOT}" "${MARKER}" "${TS}")"
log "Stop rule: /speckit-tasks → kanban_create(); NEVER /speckit-implement"
