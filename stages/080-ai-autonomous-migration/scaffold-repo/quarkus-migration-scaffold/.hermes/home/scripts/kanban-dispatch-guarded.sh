#!/usr/bin/env bash
# Guarded wrapper for `hermes kanban dispatch` (Architect E-20260811T205329Z).
# Pins Managed Scope, fail-closed asserts, then forwards args to hermes.
set -euo pipefail
ROOT="${ROOT:-/projects/modernized}"
PIN="${HERMES_MANAGED_DIR_PIN:-/projects/.platform/hermes}"
export HERMES_HOME="${HERMES_HOME:-${ROOT}/.hermes/home}"
export HERMES_WRITE_SAFE_ROOT="${HERMES_WRITE_SAFE_ROOT:-${ROOT}}"

if [[ -n "${HERMES_MANAGED_DIR:-}" && "${HERMES_MANAGED_DIR}" != "${PIN}" ]]; then
  echo "kanban-dispatch-guarded: REFUSE HERMES_MANAGED_DIR=${HERMES_MANAGED_DIR} != pin ${PIN}" >&2
  exit 1
fi
export HERMES_MANAGED_DIR="${PIN}"

ASSERT="${ROOT}/.hermes/home/scripts/assert-managed-scope-active.py"
[[ -f "${ASSERT}" ]] || { echo "kanban-dispatch-guarded: missing ${ASSERT}" >&2; exit 1; }
python3 "${ASSERT}" || {
  echo "kanban-dispatch-guarded: Managed Scope assert failed — refuse dispatch" >&2
  exit 1
}

# Architect E-20260812T090529Z Class A — BANK-CONV-LIVE-WD-1 must arm on
# dispatch path (Hermes gateway cron often down in Dev Spaces). Fail-closed.
ARM_CL="${ROOT}/.hermes/home/scripts/arm-conv-live-watchdog.sh"
[[ -x "${ARM_CL}" || -f "${ARM_CL}" ]] || {
  echo "kanban-dispatch-guarded: missing ${ARM_CL} (CONV-LIVE arm required)" >&2
  exit 1
}
bash "${ARM_CL}" || {
  echo "kanban-dispatch-guarded: CONV-LIVE arm failed — refuse dispatch" >&2
  exit 1
}

exec hermes kanban dispatch "$@"
