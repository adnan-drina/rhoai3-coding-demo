#!/usr/bin/env bash
# Host-side gate before starting / restarting outer-loop on the workspace.
# Usage:
#   bash scripts/track-b/v9-preflight-outer-start.sh          # honesty bank + lint
#   bash scripts/track-b/v9-preflight-outer-start.sh --restart  # ALL open ⬜ must be ✅
#   bash scripts/track-b/v9-preflight-outer-start.sh --start    # also oc-exec outer-loop
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"
# shellcheck source=/dev/null
source "${ROOT}/scripts/lib.sh"

RESTART=0
DO_START=0
for a in "$@"; do
  case "$a" in
    --restart) RESTART=1 ;;
    --start) DO_START=1 ;;
  esac
done

if [ "${V9_ALLOW_OPEN_BANK:-0}" != "1" ]; then
  if [ "$RESTART" = "1" ]; then
    bash "${ROOT}/scripts/track-b/v9-bank-gate.sh" all
  else
    bash "${ROOT}/scripts/track-b/v9-bank-gate.sh" honesty
  fi
fi

bash "${ROOT}/scripts/track-b/v9-coolstore-lint.sh"

# Block if advance pending
if [ -f "${ROOT}/tmp/V9-ADVANCE-PENDING.md" ]; then
  qg_die "V9-ADVANCE-PENDING.md present — clear with v9-advance-gate.sh clear S0N"
fi
# Block if debt / escalation / handfix pendings
for f in V9-DEBT-HOLD-PENDING.md V9-ESCALATION-PENDING.md V9-HANDFIX-PENDING.md; do
  if [ -f "${ROOT}/tmp/$f" ] && [ "${V9_ALLOW_PENDING_START:-0}" != "1" ]; then
    qg_die "tmp/$f present — resolve before outer-loop start"
  fi
done

load_env >/dev/null
if ! oc whoami >/dev/null 2>&1; then
  set -a; [ -f "${ROOT}/.env" ] && source "${ROOT}/.env"; set +a
  oc login "${OPENSHIFT_API_URL}" -u "${OPENSHIFT_USER}" -p "${OPENSHIFT_PASSWORD}" \
    --insecure-skip-tls-verify=true >/dev/null
fi
check_oc_logged_in

# O-FALSECOMPLETE — historical agent-authored story-complete subjects block restart
# until SHIP_ONLY re-earn. Skip with V9_ALLOW_STORY_COMPLETE_LINT=0 while a run
# is mid-flight and re-earn is already queued.
if [ "${V9_ALLOW_STORY_COMPLETE_LINT:-1}" = "1" ]; then
  bash "${ROOT}/scripts/track-b/v9-story-complete-lint.sh" --oc
fi

# O-SESSIONREG-PREFLIGHT / O-HERMES-CLI-PREFLIGHT (live workspace)
if [ "${V9_SKIP_ORCH_PREFLIGHT:-0}" != "1" ]; then
  qg_remote_orchestrator_preflight
fi

echo "PREFLIGHT GREEN"

if [ "$DO_START" = "1" ]; then
  POD="$(qg_ws_pod)"
  NS="$(qg_ws_ns)"
  CTR="$(qg_ws_ctr)"
  if qg_remote_pgrep_busy 'harness/outer-loop\.sh'; then
    echo already_running
    exit 0
  fi
  # O-OUTERSTART: oc-exec bash -lc can reap the background job when the remote
  # shell exits unless we disown; plain nohup alone was returning a dead PID.
  oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
    cd /projects/modernized || exit 1
    : >> /tmp/outer-loop.log
    nohup env -u RUN_BASE -u RESUME_RUN_BASE -u RESUME_STORY \
      WORKER_FIRST=true OUTER_LOOP_PLAIN=1 \
      stdbuf -oL -eL .hermes/harness/outer-loop.sh >> /tmp/outer-loop.log 2>&1 &
    OPID=$!
    disown "$OPID" 2>/dev/null || true
    sleep 1
    if kill -0 "$OPID" 2>/dev/null; then
      echo started_pid=$OPID alive=1
    else
      echo started_pid=$OPID alive=0
      exit 1
    fi
  '
fi
