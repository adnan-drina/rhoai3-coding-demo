#!/usr/bin/env bash
# Class A — arm BANK-CONV-LIVE-WD-1 on the dispatch path
# (Architect E-20260812T090529Z / Operator E-20260812T090441Z D4).
#
# Hermes `cron` often has no gateway in Dev Spaces seats, so the stuck-watchdog
# job never fires. Dispatch must start a seat-local poller that runs
# kanban-stuck-watchdog.py (which invokes check-conversation-liveness +
# classify-conv-live-stall on CONV-LIVE fail).
#
# Idempotent: if pidfile points at a live arm-conv-live poller, exit 0.
set -euo pipefail

ROOT="${ROOT:-/projects/modernized}"
export HERMES_HOME="${HERMES_HOME:-${ROOT}/.hermes/home}"
export HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR:-/projects/.platform/hermes}"
POLL_SEC="${CONV_LIVE_POLL_SEC:-120}"
RUN_DIR="${HERMES_HOME}/run"
LOG_DIR="${HERMES_HOME}/logs"
PIDFILE="${RUN_DIR}/conv-live-watchdog.pid"
LOG="${LOG_DIR}/conv-live-watchdog.log"
WD="${HERMES_HOME}/scripts/kanban-stuck-watchdog.py"

mkdir -p "${RUN_DIR}" "${LOG_DIR}"
[[ -f "${WD}" ]] || {
  echo "arm-conv-live-watchdog: missing ${WD}" >&2
  exit 1
}

if [[ -f "${PIDFILE}" ]]; then
  old="$(cat "${PIDFILE}" 2>/dev/null || true)"
  if [[ -n "${old:-}" ]] && kill -0 "${old}" 2>/dev/null; then
    if ps -p "${old}" -o args= 2>/dev/null | grep -q 'conv-live-watchdog-loop\|kanban-stuck-watchdog'; then
      echo "OK: CONV-LIVE watchdog already armed pid=${old} poll=${POLL_SEC}s"
      exit 0
    fi
  fi
fi

# Marker argv token for pidfile identity (must appear in ps args).
nohup bash -c '
set +e
marker=conv-live-watchdog-loop
ROOT="'"${ROOT}"'"
HERMES_HOME="'"${HERMES_HOME}"'"
export HERMES_HOME ROOT HERMES_MANAGED_DIR="'"${HERMES_MANAGED_DIR}"'"
WD="'"${WD}"'"
POLL="'"${POLL_SEC}"'"
LOG="'"${LOG}"'"
echo "[$marker] started pid=$$ poll=${POLL}s at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$LOG"
while true; do
  python3 "$WD" >>"$LOG" 2>&1 || true
  sleep "$POLL"
done
' >/dev/null 2>&1 &
echo $! >"${PIDFILE}"
sleep 0.3
if kill -0 "$(cat "${PIDFILE}")" 2>/dev/null; then
  echo "OK: CONV-LIVE watchdog armed pid=$(cat "${PIDFILE}") poll=${POLL_SEC}s log=${LOG}"
  exit 0
fi
echo "FAIL: CONV-LIVE watchdog failed to stay up" >&2
exit 1
