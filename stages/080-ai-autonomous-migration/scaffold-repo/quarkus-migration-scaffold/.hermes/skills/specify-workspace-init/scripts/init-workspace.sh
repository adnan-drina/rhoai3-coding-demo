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

ROOT="$(cd "${1:-.}" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Skill lives at .hermes/skills/specify-workspace-init/scripts — provision assets at repo .hermes/provision
PROJECT_HERMES="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
ASSET_OVERRIDE="${PROJECT_HERMES}/provision/spec-kit/overrides/spec-template.md"
MARKER="${ROOT}/.specify/.rhoai3-ads-provisioned"
LOG_PREFIX="specify-workspace-init"

log() { echo "[${LOG_PREFIX}] $*"; }
die() { echo "[${LOG_PREFIX}] ERROR: $*" >&2; exit 1; }

[ -d "${ROOT}" ] || die "missing root ${ROOT}"
[ -f "${ASSET_OVERRIDE}" ] || die "missing Non-Goals override asset at ${ASSET_OVERRIDE}"

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
  log "installing specify-cli via uv tool…"
  uv tool install specify-cli
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

Do not remove the Path.home() entry or /speckit.* skills become invisible.
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

After `/speckit.tasks` (optional `/speckit.analyze`), convert `tasks.md` into
Hermes `kanban_create()` calls.

**Never run `/speckit.implement`.** Kanban is the only executor (AD-006 / AD-H).
EOF

date -u +%Y-%m-%dT%H:%M:%SZ > "${MARKER}"
log "OK — AD-S provision complete (marker ${MARKER})"
log "Stop rule: /speckit.tasks → kanban_create(); NEVER /speckit.implement"
