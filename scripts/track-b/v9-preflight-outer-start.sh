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

# O-PLANCORPUS / O-DEFAULTAUDIT — archived-plan re-lint + defaults inventory
# before restart (live M3 flag parity; known-RED 6348afe-class must stay RED).
if [ "${V9_SKIP_PLAN_CORPUS:-0}" != "1" ]; then
  bash "${ROOT}/scripts/track-b/v10-plan-corpus-gate.sh"
fi

# O-EXECCORPUS — archived execution honesty replay (sfixnodelta / escalation-cause)
if [ "${V9_SKIP_EXEC_CORPUS:-0}" != "1" ]; then
  bash "${ROOT}/scripts/track-b/v10-exec-corpus-gate.sh"
fi

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

# O-HERMESPREFLIGHT — fail-closed pod↔worktree .hermes digest match.
# V9_AUTO_HERMES_SYNC=1 (default): tar-sync golden → pod before parity so a
# freshly provisioned workspace needs no hand sync (Wave-5 / O-HERMESSYNC).
if [ "${V9_SKIP_HERMES_PARITY:-0}" != "1" ]; then
  if [ "${V9_AUTO_HERMES_SYNC:-1}" = "1" ]; then
    if ! bash "${ROOT}/scripts/track-b/v10-hermes-parity.sh" >/tmp/v9-preflight-parity.out 2>&1; then
      echo "O-HERMESPREFLIGHT mismatch — auto-syncing golden .hermes (V9_AUTO_HERMES_SYNC=1)"
      cat /tmp/v9-preflight-parity.out | tail -12 || true
      bash "${ROOT}/scripts/track-b/v10-sync-hermes.sh"
    else
      cat /tmp/v9-preflight-parity.out | tail -6 || true
    fi
  fi
  bash "${ROOT}/scripts/track-b/v10-hermes-parity.sh"
fi

# O-GOLDENFRESH — publish-fp + three-way repo/published/pod (commit-lag class).
# Distinct from O-HERMESPREFLIGHT: catches unpublished golden SoT drift.
if [ "${V9_SKIP_GOLDEN_FRESH:-0}" != "1" ]; then
  bash "${ROOT}/scripts/track-b/v10-golden-fresh.sh"
fi

# O-M2CORPUS — archived M2 known-RED roadmap re-lint (pair O-PLANCORPUS)
if [ "${V9_SKIP_M2_CORPUS:-0}" != "1" ]; then
  bash "${ROOT}/scripts/track-b/v10-m2-corpus-gate.sh"
fi

echo "PREFLIGHT GREEN"

if [ "$DO_START" = "1" ]; then
  POD="$(qg_ws_pod)"
  NS="$(qg_ws_ns)"
  CTR="$(qg_ws_ctr)"
  # O-OUTERSTALE: lock-PID liveness (not pgrep -f; clears dead lock).
  if qg_remote_outer_alive; then
    echo already_running
    # O-MONSTART: still ensure dual-monitor is up when outer already runs
    if [ "${V9_SKIP_MONSTART:-0}" != "1" ]; then
      bash "${ROOT}/tmp/v10-v3-dual-monitor-start.sh" || true
    fi
    exit 0
  fi
  # O-OUTERSTART: oc-exec bash -lc can reap the background job when the remote
  # shell exits unless we disown; plain nohup alone was returning a dead PID.
  # Default M3_ALL=1 (whole-set author before M4). Honor host M3_ALL=0 for
  # emergency execute-only / first-M4 probes (O-STOPAFTEREXEC).
  # M3_ALL_OPERATOR_AUTO must stay unset when M3_ALL=1 (loud operator gate).
  # STOP_AFTER_M1=1 — exit after M1 ANALYZE+PROFILE GREEN (no M2).
  # STOP_AFTER_M2=1 — exit after M2 GREEN (no M3).
  # STOP_AFTER_STORY=S0N — exit after that story's M3 author GREEN (A/B runs).
  # STOP_AFTER_EXECUTE=S0N — exit after that story's M4/M5 ship (first-M4 A/B).
  _m3_all="${M3_ALL:-1}"
  _stop_m1="${STOP_AFTER_M1:-0}"
  _stop_m2="${STOP_AFTER_M2:-0}"
  _stop_story="${STOP_AFTER_STORY:-}"
  _stop_exec="${STOP_AFTER_EXECUTE:-}"
  _exec_only="${EXECUTE_ONLY_STORY:-}"
  # O-M3ROUTE / W4R7 operator: MiniMax-first default (matches outer-loop :-false).
  # Set WORKER_M3_FIRST=true only for explicit Qwen-draft A/B.
  _w_m3="${WORKER_M3_FIRST:-false}"
  # O-STOPMARKER: confirm-start clears deliberate .stopped (tip==HEAD).
  _clear_stopped="${CLEAR_STOPPED:-1}"
  _op_confirm="${OPERATOR_CONFIRM_START:-1}"
  oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
    cd /projects/modernized || exit 1
    rm -f /tmp/outer-loop-done
    # O-OUTERSTALE: drop dead lock PIDs before flock race with a new start
    for _lk in /tmp/outer-loop.lock /tmp/supervisor.lock; do
      if [ -f "$_lk" ]; then
        _pid=$(tr -dc "0-9" <"$_lk" 2>/dev/null || true)
        if [ -n "$_pid" ] && ! kill -0 "$_pid" 2>/dev/null; then
          rm -f "$_lk"
          echo "O-OUTERSTALE cleared dead pid=${_pid} ($_lk)"
        fi
      fi
    done
    : >> /tmp/outer-loop.log
    nohup env -u RUN_BASE -u RESUME_RUN_BASE -u RESUME_STORY -u M3_ALL_OPERATOR_AUTO \
      M3_ALL='"${_m3_all}"' WORKER_FIRST=true WORKER_M3_FIRST='"${_w_m3}"' OUTER_LOOP_PLAIN=1 \
      CLEAR_STOPPED='"${_clear_stopped}"' OPERATOR_CONFIRM_START='"${_op_confirm}"' \
      STOP_AFTER_M1='"${_stop_m1}"' STOP_AFTER_M2='"${_stop_m2}"' STOP_AFTER_STORY='"${_stop_story}"' \
      STOP_AFTER_EXECUTE='"${_stop_exec}"' EXECUTE_ONLY_STORY='"${_exec_only}"' \
      stdbuf -oL -eL .hermes/harness/outer-loop.sh >> /tmp/outer-loop.log 2>&1 &
    OPID=$!
    disown "$OPID" 2>/dev/null || true
    sleep 1
    if kill -0 "$OPID" 2>/dev/null; then
      echo started_pid=$OPID alive=1 m3_all='"${_m3_all}"' stop_m1='"${_stop_m1}"' exec_only='"${_exec_only}"' stop_exec='"${_stop_exec}"'
    else
      echo started_pid=$OPID alive=0
      exit 1
    fi
  '
  # O-MONSTART: host dual-monitor must start with outer so first M4 seats
  # are telemetered (O-TASKMUTATE / ttfw). Invisible to pod fingerprints.
  if [ "${V9_SKIP_MONSTART:-0}" != "1" ]; then
    if [ -x "${ROOT}/tmp/v10-v3-dual-monitor-start.sh" ] \
      || [ -f "${ROOT}/tmp/v10-v3-dual-monitor-start.sh" ]; then
      bash "${ROOT}/tmp/v10-v3-dual-monitor-start.sh"
    else
      echo "O-MONSTART: WARN missing tmp/v10-v3-dual-monitor-start.sh" >&2
    fi
  fi
fi
