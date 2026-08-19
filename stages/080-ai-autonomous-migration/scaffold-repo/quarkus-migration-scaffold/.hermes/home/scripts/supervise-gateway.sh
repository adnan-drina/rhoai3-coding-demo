#!/usr/bin/env bash
# Keep `hermes gateway run` alive in a Dev Spaces dest (no systemd).
# Official: `hermes gateway start` is the service installer; this seat uses
# `gateway run`. `--external-supervisor` exits 75 on a requested restart —
# the wrapper must relaunch (hermes-cli extraction, cli-commands).
# Do not `kanban daemon --force`.
set -u
export HERMES_HOME="${HERMES_HOME:-/projects/modernized/.hermes/home}"
export HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR:-/projects/.platform/hermes}"
export PATH="${HOME}/.local/bin:${HERMES_MANAGED_DIR}/bin:${PATH}"
LOG="${HERMES_HOME}/gateway-supervise.log"
PIDFILE="${HERMES_HOME}/gateway-supervise.pid"
mkdir -p "${HERMES_HOME}"

alive() {
  local p
  p="$(cat "${PIDFILE}" 2>/dev/null || true)"
  [ -n "${p}" ] && kill -0 "${p}" 2>/dev/null
}

if [ "${1:-}" = "--ensure" ]; then
  if alive; then
    echo "supervise-gateway: already running pid=$(cat "${PIDFILE}")"
    exit 0
  fi
  nohup "$0" >>"${LOG}" 2>&1 &
  echo $! >"${PIDFILE}"
  echo "supervise-gateway: started pid=$(cat "${PIDFILE}") log=${LOG}"
  exit 0
fi

echo $$ >"${PIDFILE}"
while true; do
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) supervise-gateway: hermes gateway run --accept-hooks --external-supervisor"
  hermes gateway run --accept-hooks --external-supervisor
  rc=$?
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) supervise-gateway: gateway exited rc=${rc}"
  sleep 2
done
