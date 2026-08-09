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
#   bash .hermes/home/scripts/kanban-track.sh dispatch        # one claim/spawn tick
#   bash .hermes/home/scripts/kanban-track.sh status
#   bash .hermes/home/scripts/kanban-track.sh show <task_id>
#   bash .hermes/home/scripts/kanban-track.sh log  <task_id>
#   bash .hermes/home/scripts/kanban-track.sh tail <task_id>
#   bash .hermes/home/scripts/kanban-track.sh runs <task_id>
#
# Two-pane demo (recommended for audience):
#   terminal A:  …/kanban-track.sh watch
#   terminal B:  …/kanban-track.sh dispatch   # or phase-dispatch skill
#
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/projects/modernized}"
HERMES_HOME="${HERMES_HOME:-${PROJECT_DIR}/.hermes/home}"
INTERVAL="${KANBAN_WATCH_INTERVAL:-1}"
DISPATCH_MAX="${KANBAN_DISPATCH_MAX:-1}"
DAEMON_INTERVAL="${KANBAN_DAEMON_INTERVAL:-15}"
DAEMON_LOG="${HERMES_HOME}/kanban-daemon.log"
DAEMON_PIDFILE="${HERMES_HOME}/kanban-daemon.pid"

die() { echo "kanban-track: $*" >&2; exit 1; }

need_hermes() {
  command -v hermes >/dev/null 2>&1 || die "hermes not on PATH (open migration workspace / ensure_hermes)"
}

cd_project() {
  [[ -d "${PROJECT_DIR}" ]] || die "PROJECT_DIR not a directory: ${PROJECT_DIR}"
  cd "${PROJECT_DIR}"
  export HERMES_HOME
  mkdir -p "${HERMES_HOME}"
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
  nohup hermes kanban daemon --force --interval "${DAEMON_INTERVAL}" --verbose \
    >"${DAEMON_LOG}" 2>&1 &
  echo $! >"${DAEMON_PIDFILE}"
  sleep 1
  if ! daemon_running; then
    die "daemon failed to stay up — see ${DAEMON_LOG}"
  fi
  echo "kanban-track: started daemon pid=$(cat "${DAEMON_PIDFILE}") log=${DAEMON_LOG}"
}

cmd_watch() {
  need_hermes
  cd_project
  echo "kanban-track: watching board events (interval=${INTERVAL}s). Ctrl-C stops watch only."
  echo "kanban-track: tip — start this BEFORE dispatch/phase-dispatch for the demo pane."
  exec hermes kanban watch --interval "${INTERVAL}" "$@"
}

cmd_dispatch() {
  need_hermes
  cd_project
  hermes kanban dispatch --max "${DISPATCH_MAX}" --json "$@" || true
  hermes kanban ls 2>&1 | head -40 || hermes kanban list 2>&1 | head -40 || true
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
    dispatch|tick)  cmd_dispatch "$@" ;;
    ensure-daemon|daemon) cmd_ensure_daemon "$@" ;;
    status|ls|list) cmd_status "$@" ;;
    show)           cmd_show "$@" ;;
    log)            cmd_log "$@" ;;
    tail)           cmd_tail "$@" ;;
    runs)           cmd_runs "$@" ;;
    *)              die "unknown command: ${cmd} (try: follow|watch|dispatch|status|show|log|tail|runs)" ;;
  esac
}

main "$@"
