#!/usr/bin/env bash
# kanban-track.sh — track Hermes Kanban progress in a Dev Spaces terminal.
#
# This is NOT a sixth authoritative surface and NOT Track B outer-loop.
# It only wraps Hermes-native verbs (watch / dispatch / log / daemon).
#
# Demo ordering (Stage 080 Act D): start watch BEFORE dispatch.
# Dev Spaces has no messaging gateway — dispatcher = `hermes kanban daemon --force`
# (escape hatch; do not also run gateway-embedded dispatch against the same board).
#
# Usage (from /projects/modernized):
#   bash .hermes/home/scripts/kanban-track.sh follow          # daemon + live watch
#   bash .hermes/home/scripts/kanban-track.sh watch           # live events only
#   bash .hermes/home/scripts/kanban-track.sh progress        # one-shot board + short log tails
#   bash .hermes/home/scripts/kanban-track.sh progress-follow # continuous worker log stream
#   bash .hermes/home/scripts/kanban-track.sh dispatch        # one claim/spawn tick
#   bash .hermes/home/scripts/kanban-track.sh status
#   bash .hermes/home/scripts/kanban-track.sh show <task_id>
#   bash .hermes/home/scripts/kanban-track.sh log  <task_id>
#   bash .hermes/home/scripts/kanban-track.sh tail <task_id>
#   bash .hermes/home/scripts/kanban-track.sh runs <task_id>
#
# Two-pane demo (recommended for audience):
#   terminal A:  …/kanban-track.sh watch
#   terminal B:  …/kanban-track.sh progress-follow   # or: tail <task_id>
#
# Env:
#   KANBAN_PROGRESS_LINES  lines shown by `progress` (default 60)
#
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/projects/modernized}"
HERMES_HOME="${HERMES_HOME:-${PROJECT_DIR}/.hermes/home}"
HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR:-/projects/.platform/hermes}"
INTERVAL="${KANBAN_WATCH_INTERVAL:-1}"
DISPATCH_MAX="${KANBAN_DISPATCH_MAX:-1}"
DAEMON_INTERVAL="${KANBAN_DAEMON_INTERVAL:-15}"
PROGRESS_LINES="${KANBAN_PROGRESS_LINES:-60}"
DAEMON_LOG="${HERMES_HOME}/kanban-daemon.log"
DAEMON_PIDFILE="${HERMES_HOME}/kanban-daemon.pid"

running_task_ids() {
  # Prefer `ls` column layout; fall back to `list`.
  local ids
  ids="$(hermes kanban ls 2>/dev/null | awk '/running/{print $2}' | head -10 || true)"
  if [[ -z "${ids}" ]]; then
    ids="$(hermes kanban list 2>/dev/null | awk '/running/{print $1}' | head -10 || true)"
  fi
  printf '%s' "${ids}"
}

die() { echo "kanban-track: $*" >&2; exit 1; }

need_hermes() {
  command -v hermes >/dev/null 2>&1 || die "hermes not on PATH (open migration workspace / ensure_hermes)"
}

cd_project() {
  [[ -d "${PROJECT_DIR}" ]] || die "PROJECT_DIR not a directory: ${PROJECT_DIR}"
  cd "${PROJECT_DIR}"
  export HERMES_HOME
  export HERMES_MANAGED_DIR
  mkdir -p "${HERMES_HOME}"
  python3 "${HERMES_HOME}/scripts/assert-managed-scope-active.py" \
    || die "Managed Scope inactive — export HERMES_MANAGED_DIR (official overlay; do not symlink into HERMES_HOME)"
}

daemon_running() {
  # Prefer pidfile when alive; fall back to process pattern used by phase-dispatch.
  if [[ -f "${DAEMON_PIDFILE}" ]]; then
    local pid
    pid="$(cat "${DAEMON_PIDFILE}" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "${pid}" 2>/dev/null; then
      return 0
    fi
  fi
  pgrep -f 'hermes kanban daemon' >/dev/null 2>&1
}

cmd_ensure_daemon() {
  need_hermes
  cd_project
  if daemon_running; then
    echo "kanban-track: daemon already running (pidfile=${DAEMON_PIDFILE})"
    return 0
  fi
  # Dev Spaces: standalone dispatcher (no gateway). See hermes kanban docs --force.
  # Pin Managed Scope in child env — do not rely on interactive bashrc.
  nohup env \
    HERMES_HOME="${HERMES_HOME}" \
    HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR}" \
    hermes kanban daemon --force --interval "${DAEMON_INTERVAL}" --verbose \
    >"${DAEMON_LOG}" 2>&1 &
  echo $! >"${DAEMON_PIDFILE}"
  sleep 1
  if ! daemon_running; then
    die "daemon failed to stay up — see ${DAEMON_LOG}"
  fi
  echo "kanban-track: started daemon pid=$(cat "${DAEMON_PIDFILE}") managed=${HERMES_MANAGED_DIR} log=${DAEMON_LOG}"
}

print_board_snapshot() {
  # Hermes `kanban watch` seeds at MAX(event id) and does NOT replay history
  # (upstream hermes_cli/kanban.py _cmd_watch). Empty stream ≠ empty board.
  echo "kanban-track: board snapshot (watch will only print NEW events after this):"
  hermes kanban ls 2>&1 | head -40 || hermes kanban list 2>&1 | head -40 || true
  hermes kanban stats 2>&1 | head -20 || true
  # Surface running workers so the terminal is never a blank pane mid-run.
  local running
  running="$(running_task_ids)"
  if [[ -n "${running}" ]]; then
    echo "kanban-track: running task(s) — stream with progress-follow (or log/tail):"
    echo "  bash $0 progress-follow"
    for tid in ${running}; do
      echo "  bash $0 progress-follow ${tid}   # or: log|tail|show ${tid}"
    done
  else
    echo "kanban-track: no running tasks — dispatch or phase-dispatch to create events."
  fi
  echo "kanban-track: HERMES_HOME=${HERMES_HOME}"
}

cmd_watch() {
  need_hermes
  cd_project
  # Relocated board: without this, watch may bind empty ~/.hermes/kanban.db
  export HERMES_HOME
  echo "kanban-track: watching board events (interval=${INTERVAL}s). Ctrl-C stops watch only."
  echo "kanban-track: tip — start this BEFORE dispatch/phase-dispatch for the demo pane."
  print_board_snapshot
  echo "kanban-track: entering forward-only watch (Hermes does not replay past events)…"
  exec hermes kanban watch --interval "${INTERVAL}" "$@"
}

cmd_dispatch() {
  need_hermes
  cd_project
  hermes kanban dispatch --max "${DISPATCH_MAX}" --json "$@" || true
  hermes kanban ls 2>&1 | head -40 || hermes kanban list 2>&1 | head -40 || true
}

cmd_progress() {
  # One-shot: board + last lines of each running worker log (not a sixth surface).
  # For a continuous stream use progress-follow (worker log via tail -f; not hermes kanban tail).
  need_hermes
  cd_project
  export HERMES_HOME
  print_board_snapshot
  local running tid
  running="$(running_task_ids)"
  for tid in ${running}; do
    echo "======== log ${tid} (last ${PROGRESS_LINES} lines; stream with: $0 progress-follow ${tid}) ========"
    hermes kanban log "${tid}" --tail 4000 2>&1 | tail -n "${PROGRESS_LINES}" || true
  done
}

cmd_progress_follow() {
  # Continuous worker *process* log (tool calls / reasoning transcript).
  # Not `hermes kanban tail` — that is the board event stream (claim/heartbeat/done).
  # Hermes CLI: `hermes kanban log <id> [--tail BYTES]` (no --follow); stream via tail -f.
  need_hermes
  cd_project
  export HERMES_HOME
  local want="${1:-}"; shift || true
  local running tid logfile
  running="$(running_task_ids)"
  if [[ -n "${want}" ]]; then
    tid="${want}"
  else
    # First running task; if several, say so and pin the first.
    # shellcheck disable=SC2086
    set -- ${running}
    tid="${1:-}"
    if [[ -z "${tid}" ]]; then
      print_board_snapshot
      die "no running task to follow — dispatch first, or: $0 progress-follow <task_id>"
    fi
    if [[ -n "${2:-}" ]]; then
      echo "kanban-track: multiple running tasks; following ${tid} (also: $*)"
      echo "kanban-track: pin with: $0 progress-follow <task_id>"
    fi
  fi
  # Default board layout; also try boards/*/logs if relocated.
  logfile="${HERMES_HOME}/kanban/logs/${tid}.log"
  if [[ ! -f "${logfile}" ]]; then
    logfile="$(find "${HERMES_HOME}/kanban" -type f -name "${tid}.log" 2>/dev/null | head -1 || true)"
  fi
  print_board_snapshot
  if [[ -n "${logfile}" && -f "${logfile}" ]]; then
    echo "kanban-track: streaming worker log ${logfile} (Ctrl-C stops stream only)…"
    echo "kanban-track: tip — board events are separate: hermes kanban watch / hermes kanban tail ${tid}"
    exec tail -n "${PROGRESS_LINES}" -f "${logfile}"
  fi
  echo "kanban-track: log file not found yet; dumping hermes kanban log ${tid} then waiting…"
  hermes kanban log "${tid}" --tail 65536 2>&1 || true
  # Wait briefly for dispatcher to create the file, then follow.
  local i
  for i in $(seq 1 30); do
    logfile="${HERMES_HOME}/kanban/logs/${tid}.log"
    [[ -f "${logfile}" ]] && break
    logfile="$(find "${HERMES_HOME}/kanban" -type f -name "${tid}.log" 2>/dev/null | head -1 || true)"
    [[ -n "${logfile}" && -f "${logfile}" ]] && break
    sleep 1
  done
  [[ -n "${logfile}" && -f "${logfile}" ]] || die "no worker log for ${tid} under ${HERMES_HOME}/kanban/"
  echo "kanban-track: streaming ${logfile}"
  exec tail -n 0 -f "${logfile}"
}

cmd_follow() {
  # Single terminal: keep dispatcher alive, stream events in the foreground.
  cmd_ensure_daemon
  cmd_watch "$@"
}

cmd_status() {
  need_hermes
  cd_project
  echo "=== hermes ==="
  hermes --version 2>&1 | head -3 || true
  echo "=== daemon ==="
  if daemon_running; then
    echo "running pid=$(cat "${DAEMON_PIDFILE}" 2>/dev/null || echo '?')"
    echo "log: ${DAEMON_LOG}  (tail -f that file for dispatcher ticks)"
  else
    echo "not running — start with: $0 ensure-daemon   or   $0 follow"
  fi
  echo "=== board ==="
  hermes kanban ls 2>&1 | head -50 || hermes kanban list 2>&1 | head -50 || true
  echo "=== stats ==="
  hermes kanban stats 2>&1 || true
}

cmd_show() {
  local id="${1:-}"; shift || true
  [[ -n "${id}" ]] || die "usage: $0 show <task_id>"
  need_hermes
  cd_project
  hermes kanban show "${id}" "$@"
}

cmd_log() {
  local id="${1:-}"; shift || true
  [[ -n "${id}" ]] || die "usage: $0 log <task_id>"
  need_hermes
  cd_project
  # Worker log under ~/.hermes/kanban/logs/ (HERMES_HOME relocated).
  hermes kanban log "${id}" "$@"
}

cmd_tail() {
  local id="${1:-}"; shift || true
  [[ -n "${id}" ]] || die "usage: $0 tail <task_id>"
  need_hermes
  cd_project
  hermes kanban tail "${id}" "$@"
}

cmd_runs() {
  local id="${1:-}"; shift || true
  [[ -n "${id}" ]] || die "usage: $0 runs <task_id>   # task_id required"
  need_hermes
  cd_project
  hermes kanban runs "${id}" "$@"
}

usage() {
  sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'
}

main() {
  local cmd="${1:-follow}"
  shift || true
  case "${cmd}" in
    -h|--help|help) usage ;;
    follow)         cmd_follow "$@" ;;
    watch)          cmd_watch "$@" ;;
    progress)       cmd_progress "$@" ;;
    progress-follow|plog|stream) cmd_progress_follow "$@" ;;
    dispatch|tick)  cmd_dispatch "$@" ;;
    ensure-daemon|daemon) cmd_ensure_daemon "$@" ;;
    status|ls|list) cmd_status "$@" ;;
    show)           cmd_show "$@" ;;
    log)            cmd_log "$@" ;;
    tail)           cmd_tail "$@" ;;
    runs)           cmd_runs "$@" ;;
    *)              die "unknown command: ${cmd} (try: follow|watch|progress|progress-follow|dispatch|status|show|log|tail|runs)" ;;
  esac
}

main "$@"
