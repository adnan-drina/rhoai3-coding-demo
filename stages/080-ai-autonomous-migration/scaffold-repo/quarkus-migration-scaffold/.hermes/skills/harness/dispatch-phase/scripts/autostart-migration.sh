#!/usr/bin/env bash
# Workspace-gated M1 autostart: create → check → dispatch.
# Architect BIND E-20260820T075106Z + AMEND E-20260820T140201Z.
# Do not kanban daemon --force. Do not dest-enable dispatch-phase as a skill pin.
# Refuse is parked-with-reason (exit 0 + marker), not workspace Unhealthy.
# persist-postStart secret dump is not this script.
set -euo pipefail

ROOT=""
SKIP_DISPATCH=0
EXPECTED_SHA=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --skip-dispatch) SKIP_DISPATCH=1; shift ;;
    --expected-sha) EXPECTED_SHA="$2"; shift 2 ;;
    -h|--help)
      cat <<'USAGE'
autostart-migration.sh --root DIR [--skip-dispatch] [--expected-sha 40hex]

create (DISPATCH_MAX=0) → HARNESS_REV + park-M3 gates → hermes kanban dispatch --max 1
AUTO_START_MIGRATION=0 skips. Refuse writes .hermes/AUTOSTART-STATUS and exits 0.
USAGE
      exit 0
      ;;
    *)
      echo "autostart-migration: unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

[[ -n "${ROOT}" ]] || { echo "autostart-migration: --root required" >&2; exit 2; }
ROOT="$(cd "${ROOT}" && pwd)"
export HERMES_HOME="${HERMES_HOME:-${ROOT}/.hermes/home}"
export HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR:-/projects/.platform/hermes}"
export PATH="${HOME}/.local/bin:${HERMES_MANAGED_DIR}/bin:${PATH}"

MARKER="${ROOT}/.hermes/AUTOSTART-STATUS"
T0_FILE="${ROOT}/.hermes/AUTOSTART-T0"
GATE="${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/assert-autostart-gates.py"
DISPATCH="${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh"
mkdir -p "${ROOT}/.hermes"

write_marker() {
  local state="$1"
  local reason="$2"
  # No column-0 heredoc (destfile YAML). printf only. No secrets.
  printf '%s\n' \
    "schema: rhoai3.autostart-status/v1" \
    "state: ${state}" \
    "reason: ${reason}" \
    "ts: $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    >"${MARKER}"
  echo "autostart-migration: ${state} — ${reason}"
}

want_start="$(printf '%s' "${AUTO_START_MIGRATION:-1}" | tr '[:upper:]' '[:lower:]')"
case "${want_start}" in
  0|false|off|no)
    write_marker SKIPPED "AUTO_START_MIGRATION=${AUTO_START_MIGRATION}"
    exit 0
    ;;
esac

if [[ -f "${MARKER}" ]] && grep -q '^state: DISPATCHED$' "${MARKER}"; then
  echo "autostart-migration: already DISPATCHED"
  exit 0
fi

if [[ ! -f "${GATE}" ]]; then
  write_marker REFUSED "missing assert-autostart-gates.py"
  exit 0
fi

gate_rev=(python3 "${GATE}" harness-rev --root "${ROOT}")
if [[ -n "${EXPECTED_SHA}" ]]; then
  gate_rev+=(--expected-sha "${EXPECTED_SHA}")
fi
if ! "${gate_rev[@]}"; then
  write_marker REFUSED "HARNESS_REV mismatch or missing"
  exit 0
fi

if [[ ! -f "${ROOT}/evidence/derived/phase-M1-task-id.txt" ]]; then
  if [[ ! -f "${DISPATCH}" ]]; then
    write_marker REFUSED "missing dispatch-phase.sh"
    exit 0
  fi
  if ! command -v hermes >/dev/null 2>&1 && [[ "${SKIP_DISPATCH}" -eq 0 ]]; then
    write_marker REFUSED "hermes absent on PATH"
    exit 0
  fi
  # Create parks. Do not spawn yet. Do not kanban daemon --force.
  if ! DISPATCH_MAX=0 DISPATCH_START_DAEMON=0 DISPATCH_PARK_CHAIN=1 \
    bash "${DISPATCH}" M1; then
    write_marker REFUSED "dispatch-phase.sh M1 create failed"
    exit 0
  fi
fi

if ! python3 "${GATE}" holder --root "${ROOT}"; then
  write_marker REFUSED "park-M3 discriminator (title or skill-pinned holder)"
  exit 0
fi

if [[ "${SKIP_DISPATCH}" -eq 1 ]]; then
  write_marker CHECKED "gates green; dispatch skipped (--skip-dispatch)"
  exit 0
fi

if ! command -v hermes >/dev/null 2>&1; then
  write_marker REFUSED "hermes absent; cannot dispatch"
  exit 0
fi

# t0 = M1 dispatch timestamp (machine-recorded).
date -u +%Y-%m-%dT%H:%M:%SZ >"${T0_FILE}"
if ! hermes kanban dispatch --max 1; then
  write_marker REFUSED "hermes kanban dispatch --max 1 failed (t0 stamped)"
  exit 0
fi
write_marker DISPATCHED "M1 dispatched; t0=${T0_FILE}"
exit 0
