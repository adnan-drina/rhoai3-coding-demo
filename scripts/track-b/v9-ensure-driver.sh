#!/usr/bin/env bash
# Keep the Track B driver alive + recover oc login (watchdog target).
# Safe to run from launchd/cron every minute.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"
# shellcheck source=/dev/null
source "${ROOT}/scripts/lib.sh"
load_env >/dev/null 2>&1 || true

LOG="${V8_DRIVER_LOG:-/tmp/v8-driver-loop.out}"
PIDFILE="${ROOT}/tmp/V9-DRIVER.pid"
MARKER='bash scripts/track-b/v8-driver-loop.sh'

ensure_oc() {
  if oc whoami >/dev/null 2>&1; then
    return 0
  fi
  set -a
  # shellcheck disable=SC1091
  [ -f "${ROOT}/.env" ] && source "${ROOT}/.env"
  set +a
  if [ -n "${OPENSHIFT_API_URL:-}" ] && [ -n "${OPENSHIFT_USER:-}" ] && [ -n "${OPENSHIFT_PASSWORD:-}" ]; then
    echo "ensure-driver: oc unauthorized — re-login"
    oc login "$OPENSHIFT_API_URL" -u "$OPENSHIFT_USER" -p "$OPENSHIFT_PASSWORD" \
      --insecure-skip-tls-verify=true >/dev/null
  else
    echo "ensure-driver: oc down and .env missing OPENSHIFT_* — cannot recover" >&2
    return 1
  fi
}

driver_alive() {
  if [ -f "$PIDFILE" ]; then
    local pid
    pid=$(tr -d '[:space:]' <"$PIDFILE")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      # confirm it is the driver
      ps -p "$pid" -o command= 2>/dev/null | grep -q 'v8-driver-loop' && return 0
    fi
  fi
  pgrep -f "$MARKER" >/dev/null 2>&1
}

start_driver() {
  ensure_oc || true
  mkdir -p "${ROOT}/tmp"
  : >>"$LOG"
  nohup env V8_WS_POD="$(qg_ws_pod)" \
    V8_DRIVER_INTERVAL="${V8_DRIVER_INTERVAL:-120}" \
    V8_AUTO_RESTART="${V8_AUTO_RESTART:-0}" \
    bash "${ROOT}/scripts/track-b/v8-driver-loop.sh" >>"$LOG" 2>&1 &
  echo $! >"$PIDFILE"
  echo "ensure-driver: started pid=$(cat "$PIDFILE")"
}

if driver_alive; then
  ensure_oc || true
  echo "ensure-driver: driver UP"
  exit 0
fi
echo "ensure-driver: driver DOWN — restarting"
start_driver
