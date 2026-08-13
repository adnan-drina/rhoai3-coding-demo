#!/usr/bin/env bash
# AD-S — provision-time spec-kit init for the migration workspace (modernized).
#
# Runs in /projects/modernized (or $1). Does NOT commit .specify/ into the
# golden scaffold — it creates .specify/ in the live workspace only.
#
#   specify init --here --integration hermes --force --ignore-agent-tools
#   + Non-Goals override from .hermes/provision/spec-kit/overrides/
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
# Non-Goals override lives under the workspace project tree
# (`${ROOT}/.hermes/provision/...`), not relative to the skill script.
# Hermes may invoke this skill from `.hermes/skills/...` OR from
# `.hermes/home/skills/software-development/...` — walking up from
# SCRIPT_DIR mis-resolves PROJECT_HERMES in the latter case (v12 M2a
# t_44c55c31 exit 1 / Deputy E-120800Z).
ASSET_OVERRIDE="${ROOT}/.hermes/provision/spec-kit/overrides/spec-template.md"
if [ ! -f "${ASSET_OVERRIDE}" ]; then
  # Fallback: tip skill tree under .hermes/skills/... → ../../.. = .hermes
  PROJECT_HERMES="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
  if [ -f "${PROJECT_HERMES}/provision/spec-kit/overrides/spec-template.md" ]; then
    ASSET_OVERRIDE="${PROJECT_HERMES}/provision/spec-kit/overrides/spec-template.md"
  fi
fi
MARKER="${ROOT}/.specify/.rhoai3-ads-provisioned"
LOG_PREFIX="specify-workspace-init"

log() { echo "[${LOG_PREFIX}] $*"; }
die() { echo "[${LOG_PREFIX}] ERROR: $*" >&2; exit 1; }

[ -d "${ROOT}" ] || die "missing root ${ROOT}"
[ -f "${ASSET_OVERRIDE}" ] || die "missing Non-Goals override asset at ${ASSET_OVERRIDE} (expected under ${ROOT}/.hermes/provision/spec-kit/overrides/)"

if [[ "${DRY_RUN}" == "1" ]]; then
  log "DRY-RUN: ROOT=${ROOT}"
  log "DRY-RUN: MARKER=${MARKER}"
  log "DRY-RUN: ASSET_OVERRIDE=${ASSET_OVERRIDE}"
  log "DRY-RUN: would run: specify init --here --integration hermes --force --ignore-agent-tools"
  log "DRY-RUN: would copy override → .specify/templates/overrides/spec-template.md"
  log "DRY-RUN: would write marker ${MARKER}"
  exit 0
fi

if [ -f "${MARKER}" ]; then
  log "already provisioned ($(cat "${MARKER}")) — skip"
  exit 0
fi

# Refuse runs that would create .specify/ inside the golden scaffold source
# tree (AD-S S.4). Workspaces live under /projects/*; intentional dry-runs
# set FORCE_AD_S_PROVISION=1.
if [ -f "${ROOT}/.hermes/provision/spec-kit/DO_NOT_COMMIT_SPECIFY" ]; then
  case "${ROOT}" in
    /projects/*) ;;
    *)
      if [ "${FORCE_AD_S_PROVISION:-}" != "1" ]; then
        die "refusing AD-S init in scaffold/source tree (workspace: /projects/*; dry-run: FORCE_AD_S_PROVISION=1)"
      fi
      ;;
  esac
fi

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
  # R-HX.1 — pin Spec Kit (see migration/contracts/tooling-pins.md)
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
  local note="${ROOT}/.hermes/provision/spec-kit/EXTERNAL_DIRS.note"
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
log "OK — AD-S provision complete (marker ${MARKER})"
log "Stop rule: /speckit-tasks → kanban_create(); NEVER /speckit-implement"
