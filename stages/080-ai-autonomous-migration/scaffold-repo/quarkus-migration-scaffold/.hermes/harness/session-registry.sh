#!/usr/bin/env bash
# O-PIDREG / O-OCGROUP (F-74 F2/F3) — identity-based session lifecycle.
# Source from supervisor/outer-loop:
#   # shellcheck source=session-registry.sh
#   . "$(dirname "$0")/session-registry.sh"
#
# Every session launch: setsid → register pid → wait → group-TERM → unregister.
# Kill sites must never pkill -x opencode; unregistered opencode is a finding.
SESSIONS_DIR="${SESSIONS_DIR:-/tmp/sessions}"

# shellcheck source=harness-kill.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/harness-kill.sh"

session_register() { # tag pid
  local tag=$1 pid=$2
  mkdir -p "$SESSIONS_DIR"
  printf '%s\n' "$pid" >"$SESSIONS_DIR/${tag}.pid"
}

session_unregister() { # tag
  rm -f "$SESSIONS_DIR/${1}.pid"
}

# F3: reap the whole process group (opencode run → serve child).
session_reap_group() { # tag pid cause
  local tag=$1 pid=$2 cause=$3
  [[ -n "${pid:-}" && "$pid" =~ ^[0-9]+$ ]] || return 0
  if kill -0 "$pid" 2>/dev/null; then
    kill -TERM -- "-$pid" 2>/dev/null || harness_kill "$tag" "$pid" TERM "$cause"
    printf '%s tag=%s pid=%s sig=TERM cause=%s (group)\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$tag" "$pid" "$cause" \
      >>"${KILL_LEDGER:-/tmp/kill-ledger.log}" 2>/dev/null || true
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      kill -KILL -- "-$pid" 2>/dev/null || harness_kill "$tag" "$pid" KILL "${cause}-kill"
    fi
  fi
  session_unregister "$tag"
}

# Log unregistered opencode PIDs; never kill them (F-74).
session_log_unregistered_opencode() {
  local opid rpid reg pgid rpgid
  command -v pgrep >/dev/null 2>&1 || return 0
  for opid in $(pgrep -x opencode 2>/dev/null || true); do
    reg=0
    shopt -s nullglob
    for f in "$SESSIONS_DIR"/*.pid; do
      rpid=$(tr -d '[:space:]' <"$f" || true)
      [[ "$rpid" =~ ^[0-9]+$ ]] || continue
      if [[ "$opid" == "$rpid" ]]; then reg=1; break; fi
      pgid=$(ps -o pgid= -p "$opid" 2>/dev/null | tr -d ' ')
      rpgid=$(ps -o pgid= -p "$rpid" 2>/dev/null | tr -d ' ')
      if [[ -n "$pgid" && "$pgid" == "$rpgid" ]]; then reg=1; break; fi
    done
    shopt -u nullglob
    if [[ "$reg" -eq 0 ]]; then
      printf '%s O-PIDREG: unregistered opencode pid=%s — finding, not killing\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$opid" \
        >>"${SUPERVISOR_LOG:-/tmp/supervisor.log}" 2>/dev/null || true
      printf '%s tag=unregistered pid=%s sig=NONE cause=unregistered-opencode-finding\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$opid" \
        >>"${KILL_LEDGER:-/tmp/kill-ledger.log}" 2>/dev/null || true
    fi
  done
}

# Wait for registered sessions; on cap, reap registered groups only.
session_wait_registered() { # [cap_secs] [log_fn_name]
  local cap=${1:-900} logfn=${2:-:}
  local waited=0 any pid tag f
  mkdir -p "$SESSIONS_DIR"
  while true; do
    any=0
    shopt -s nullglob
    for f in "$SESSIONS_DIR"/*.pid; do
      pid=$(tr -d '[:space:]' <"$f" || true)
      tag=$(basename "$f" .pid)
      if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
        any=1
      else
        rm -f "$f"
      fi
    done
    shopt -u nullglob
    session_log_unregistered_opencode
    [[ "$any" -eq 0 ]] && return 0
    [[ "$waited" -eq 0 ]] && $logfn "registered session still running — waiting before next session (O-PIDREG)"
    sleep 30
    waited=$((waited + 30))
    if [[ "$waited" -ge "$cap" ]]; then
      $logfn "registered session still running after ${cap}s — reaping registered groups only (O-PIDREG/O-OCGROUP)"
      shopt -s nullglob
      for f in "$SESSIONS_DIR"/*.pid; do
        pid=$(tr -d '[:space:]' <"$f" || true)
        tag=$(basename "$f" .pid)
        session_reap_group "$tag" "$pid" "stale-session-reap"
      done
      shopt -u nullglob
      return 0
    fi
  done
}
