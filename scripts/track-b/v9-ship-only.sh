#!/usr/bin/env bash
# Re-earn M5 ship/acceptance via supervisor SHIP_ONLY=1 (O-FALSECOMPLETE).
# Does not rewrite story-state.csv; leaves /tmp/supervisor-done for
# v9-record-ship-only.sh (or the durable waiter).
#
# Usage:
#   bash scripts/track-b/v9-ship-only.sh [pod]
# Env: V8_WS_POD, STORY_DEPLOY (default true), SHIP_LOG
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"
# shellcheck source=/dev/null
source "${ROOT}/scripts/lib.sh"
load_env >/dev/null
check_oc_logged_in

POD="${1:-$(qg_ws_pod)}"
NS="$(qg_ws_ns)"
CTR="$(qg_ws_ctr)"
SHIP_LOG="${SHIP_LOG:-/tmp/ship-only.log}"

if qg_remote_pgrep_busy 'harness/supervisor\.sh'; then
  echo "REFUSE: supervisor already running in pod — wait for idle" >&2
  exit 2
fi

oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc "
set -euo pipefail
cd /projects/modernized || exit 1
rm -f /tmp/supervisor-done
: >> ${SHIP_LOG}
nohup env SHIP_ONLY=1 STORY_DEPLOY=\${STORY_DEPLOY:-true} WORKER_FIRST=true \
  bash /projects/modernized/.hermes/harness/supervisor.sh >> ${SHIP_LOG} 2>&1 &
echo started_pid=\$!
"
echo "ship-only started; expect /tmp/supervisor-done = success route=…"
echo "record with: bash scripts/track-b/v9-record-ship-only.sh S0N  (no auto-push)"
