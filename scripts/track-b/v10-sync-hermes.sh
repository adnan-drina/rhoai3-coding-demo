#!/usr/bin/env bash
# Tar-sync golden scaffold .hermes → the Running DevWorkspace modernized tree.
# Idempotent. Wipes pod .hermes first so leftovers cannot poison digests.
# Usage:
#   V10_WS_NAME=petclinic-rest-v5 bash scripts/track-b/v10-sync-hermes.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/lib.sh"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"

load_env >/dev/null 2>&1 || true
check_oc_logged_in

WS_NAME="$(qg_ws_name)" || {
  echo "v10-sync-hermes: REFUSE — set V10_WS_NAME or ensure one Running DevWorkspace" >&2
  exit 1
}
NS="$(qg_ws_ns)"
CTR="$(qg_ws_ctr)"
SCAFFOLD="${HERMES_PARITY_ROOT:-${ROOT}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold}"
HARNESS_SRC="${SCAFFOLD}/.hermes"

if [[ ! -d "$HARNESS_SRC" ]]; then
  echo "v10-sync-hermes: missing golden .hermes at $HARNESS_SRC" >&2
  exit 1
fi

POD="$(qg_ws_pod)" || {
  echo "v10-sync-hermes: REFUSE — no Running pod for ${WS_NAME}" >&2
  exit 1
}

# ADR-27 / O-ADR27HOTFIX: never tar-replace .hermes while an LLM seat is
# mid-tool-call. Between typed seats (no live opencode/hermes *binary*),
# sync is allowed so a durable fix for an already-observed refuse/FAIL
# class can land without burning the rest of the story.
# Do NOT use `pgrep -f hermes|opencode` — that false-matches
# `.hermes/harness/outer-loop.sh` / `m3_task_loop.py` and blocked hot-fixes.
# Override mid-call only with V10_SYNC_FORCE=1 (documented emergency).
if [ "${V10_SYNC_FORCE:-0}" != "1" ]; then
  _seat=$(oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
    # Exact binary names only (O-ADR27HOTFIX).
    if pgrep -x opencode >/dev/null 2>&1 || pgrep -x hermes >/dev/null 2>&1; then
      echo BUSY; exit 0
    fi
    echo OK
  ' 2>/dev/null || echo OK)
  if [ "$_seat" = "BUSY" ]; then
    echo "v10-sync-hermes: REFUSE — LLM seat in flight (ADR-27). Wait between seats or use v10-m1-arch-revalidate.sh" >&2
    echo "  Emergency only: V10_SYNC_FORCE=1" >&2
    exit 2
  fi
fi

# O-FREEZEGOLDEN: refuse sync while a harness freeze lock is held (cold-run
# discipline). Lift explicitly: V10_FREEZE_LIFT=1 (or V10_SYNC_FORCE=1).
_FREEZE_LOCK="${ROOT}/tmp/M3-HARNESS-FREEZE.lock"
if [ -f "$_FREEZE_LOCK" ] \
  && [ "${V10_FREEZE_LIFT:-0}" != "1" ] \
  && [ "${V10_SYNC_FORCE:-0}" != "1" ]; then
  echo "v10-sync-hermes: REFUSE — O-FREEZEGOLDEN lock present (${_FREEZE_LOCK})" >&2
  echo "  Cold-run freeze: do not sync golden→pod until lift. Set V10_FREEZE_LIFT=1." >&2
  head -5 "$_FREEZE_LOCK" >&2 || true
  exit 3
fi

n_files="$(find "$HARNESS_SRC" -type f ! -name '._*' ! -name '.DS_Store' | wc -l | tr -d ' ')"
echo "v10-sync-hermes: ${WS_NAME} → ${NS}/${POD} (${n_files} golden files)"

oc exec -n "$NS" "$POD" -c "$CTR" -- \
  bash -lc 'cd /projects/modernized && rm -rf .hermes && mkdir -p .hermes'

( cd "$SCAFFOLD" && COPYFILE_DISABLE=1 tar cf - .hermes ) | oc exec -i -n "$NS" "$POD" -c "$CTR" -- \
  bash -lc 'cd /projects/modernized && tar xf - && find .hermes -name "._*" -delete 2>/dev/null || true'

# Clear start-blocking *runtime* markers. Do NOT remove migration/.stopped by
# default — a deliberate STOP_AFTER_M1 hold must survive harness sync
# (O-STOPMARKER / ADR-34 land during M1 hold). Opt-in wipe only:
#   V10_SYNC_CLEAR_STOP=1
# O-SYNCLOCKRM / W4-777: never unlink live flock paths. `rm` of
# /tmp/outer-loop.lock while an outer holds flock on the inode lets a second
# outer create a *new* lock file and start (dual-writer). Only clear stale PID
# locks (dead PID); leave held locks alone. debt-freeze/pause/done are OK.
oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
  clear_stale_pid_lock() {
    local lock="$1" pid=""
    [ -f "$lock" ] || return 0
    pid=$(tr -dc "0-9" <"$lock" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      echo "v10-sync-hermes: keeping live lock $lock pid=$pid (O-SYNCLOCKRM)"
      return 0
    fi
    rm -f "$lock"
    echo "v10-sync-hermes: cleared stale lock $lock pid=${pid:-empty}"
  }
  rm -f /tmp/outer-loop-done /tmp/debt-freeze /tmp/supervisor-pause \
        /tmp/worker-wedge-skip \
        /projects/modernized/migration/findings-delta.STALE \
        /projects/modernized/migration/.supervisor-pause 2>/dev/null || true
  clear_stale_pid_lock /tmp/outer-loop.lock
  clear_stale_pid_lock /tmp/supervisor.lock
  if [ "${V10_SYNC_CLEAR_STOP:-0}" = "1" ]; then
    rm -f /projects/modernized/migration/.stopped 2>/dev/null || true
    echo "v10-sync-hermes: cleared migration/.stopped (V10_SYNC_CLEAR_STOP=1)"
  elif [ -f /projects/modernized/migration/.stopped ]; then
    echo "v10-sync-hermes: keeping migration/.stopped (deliberate hold)"
  fi
  # Prefer KANTRA_HOME layout when helper exists.
  export KANTRA_HOME="${KANTRA_HOME:-/projects/.tools/kantra}"
  if command -v kantra-ensure >/dev/null 2>&1; then
    kantra-ensure || true
  fi
  if [ -x "${KANTRA_HOME}/kantra" ] || [ -f "${KANTRA_HOME}/kantra" ]; then
    echo "kantra-ok:${KANTRA_HOME}/kantra"
  elif [ -x /tmp/kantra/kantra ]; then
    echo "kantra-ok:/tmp/kantra/kantra"
  else
    echo "WARN: kantra binary still missing — M1 analyze will fail until installed"
  fi
'

qg_remote_orchestrator_preflight || {
  echo "v10-sync-hermes: WARN orchestrator preflight RED after sync" >&2
  exit 1
}

echo "v10-sync-hermes: OK"
