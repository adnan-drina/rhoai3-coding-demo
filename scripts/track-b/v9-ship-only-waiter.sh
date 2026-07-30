#!/usr/bin/env bash
# Wait for a safe idle window, then SHIP_ONLY + record honest story-complete.
#
# Designed to run **inside** the DevWorkspace pod (cd /projects/modernized).
# Host can oc-cp this file and nohup it. Commit logic is in v9-record-ship-only.sh
# (reviewed); this script only orchestrates wait → ship → record.
#
# Safe triggers (any one) — never "outer process absent":
#   1. /tmp/outer-loop-done contains outer-complete
#   2. migration/story-state.csv has ${REQUIRE_STORY},complete (default S05)
#   3. outer-loop.log shows "all stories shipped" / outer-complete
#
# Usage (in pod):
#   REQUIRE_STORY=S05 RECORD_STORY=S04 bash v9-ship-only-waiter.sh
set -uo pipefail

LOG="${SHIP_ONLY_WAITER_LOG:-/tmp/v9-ship-only-waiter.log}"
REQUIRE_STORY="${REQUIRE_STORY:-S05}"
RECORD_STORY="${RECORD_STORY:-S04}"
MAX_WAIT_TICKS="${MAX_WAIT_TICKS:-180}"   # 60s each
SHIP_POLL_TICKS="${SHIP_POLL_TICKS:-50}" # 30s each
APP_ROOT="${APP_ROOT:-/projects/modernized}"
RECORD_SCRIPT="${RECORD_SCRIPT:-}"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >>"$LOG"; }

sup_busy() {
  pgrep -af 'harness/supervisor\.sh' \
    | grep -vE 'bash -lc|pgrep|SHIP_ONLY|v9-ship-only-waiter' \
    | grep -q .
}

ready_to_ship() {
  # Explicit completion evidence only (O-FALSECOMPLETE waiter hardening).
  # Paths overridable for fixtures (never treat "process absent" as ready).
  local done_f="${OUTER_LOOP_DONE:-/tmp/outer-loop-done}"
  local log_f="${OUTER_LOOP_LOG:-/tmp/outer-loop.log}"
  if [ -f "$done_f" ] && grep -q 'outer-complete' "$done_f" 2>/dev/null; then
    echo "outer-loop-done"
    return 0
  fi
  if [ -f migration/story-state.csv ] \
    && grep -q "^${REQUIRE_STORY},complete" migration/story-state.csv; then
    echo "story-state ${REQUIRE_STORY},complete"
    return 0
  fi
  if [ -f "$log_f" ] && tail -20 "$log_f" 2>/dev/null \
    | grep -qE 'outer-complete|all stories shipped'; then
    echo "outer-loop.log completion"
    return 0
  fi
  return 1
}

cd "$APP_ROOT"

# Fixture / dry-run: bash v9-ship-only-waiter.sh --check-ready
if [ "${1:-}" = "--check-ready" ]; then
  if WHY=$(ready_to_ship); then
    echo "READY: $WHY"
    exit 0
  fi
  echo "NOT_READY"
  exit 1
fi

: >>"$LOG"
log "waiter start pid=$$ require=${REQUIRE_STORY} record=${RECORD_STORY}"

READY_WHY=""
for i in $(seq 1 "$MAX_WAIT_TICKS"); do
  if sup_busy; then
    log "supervisor busy tick=$i"
    sleep 60
    continue
  fi
  if WHY=$(ready_to_ship); then
    READY_WHY=$WHY
    log "ready ($READY_WHY) — supervisor idle"
    break
  fi
  log "supervisor idle but ${REQUIRE_STORY} not complete — waiting (tick=$i)"
  sleep 60
done

if [ -z "$READY_WHY" ]; then
  log "REFUSE: wait budget exhausted without completion marker (not launching SHIP_ONLY)"
  exit 2
fi

# Re-check after loop — do not fall through into a live supervisor.
if sup_busy; then
  log "REFUSE: supervisor busy at launch gate"
  exit 2
fi

rm -f /tmp/supervisor-done
nohup env SHIP_ONLY=1 STORY_DEPLOY="${STORY_DEPLOY:-true}" WORKER_FIRST=true \
  bash .hermes/harness/supervisor.sh >>/tmp/ship-only.log 2>&1 &
log "ship-only pid=$! why=${READY_WHY}"

for j in $(seq 1 "$SHIP_POLL_TICKS"); do
  DONE=$(cat /tmp/supervisor-done 2>/dev/null || true)
  log "supervisor-done=${DONE:-"(none)"}"
  case "$DONE" in
    success*)
      REC="${RECORD_SCRIPT:-/tmp/v9-record-ship-only.sh}"
      if [ ! -x "$REC" ] && [ -f "$REC" ]; then chmod +x "$REC"; fi
      if [ ! -f "$REC" ]; then
        log "REFUSE: missing $REC — leaving supervisor-done for operator"
        exit 3
      fi
      RECORD_PUSH="${RECORD_PUSH:-0}" bash "$REC" "$RECORD_STORY" "$DONE" \
        >>"$LOG" 2>&1 || { log "record script failed"; exit 3; }
      log EARNED
      exit 0
      ;;
    factory-failed*|push-failed*|ship-blocked*)
      log "FAIL $DONE"
      exit 1
      ;;
  esac
  sleep 30
done
log TIMEOUT
exit 1
