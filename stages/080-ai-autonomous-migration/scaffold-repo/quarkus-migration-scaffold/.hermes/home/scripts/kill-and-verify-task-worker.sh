#!/usr/bin/env bash
# Architect E-20260811T173254Z Class A — residual-worker kill verified.
# Board status alone does NOT stop Hermes. Abort/terminal MUST kill+verify.
#
# Usage:
#   bash .hermes/home/scripts/kill-and-verify-task-worker.sh t_xxx
#   bash .hermes/home/scripts/kill-and-verify-task-worker.sh --protect 94748 t_xxx
set -euo pipefail

PROTECT=()
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --protect) PROTECT+=("$2"); shift 2 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
[[ ${#ARGS[@]} -ge 1 ]] || {
  echo "usage: kill-and-verify-task-worker.sh [--protect PID]… TASK_ID" >&2
  exit 2
}
TASK_ID="${ARGS[0]}"

is_protected() {
  local p="$1"
  for x in "${PROTECT[@]:-}"; do
    [[ "${p}" == "${x}" ]] && return 0
  done
  return 1
}

mapfile -t PIDS < <(pgrep -f "kanban task ${TASK_ID}" 2>/dev/null || true)
if [[ ${#PIDS[@]} -eq 0 ]]; then
  mapfile -t PIDS < <(pgrep -f "hermes .*${TASK_ID}" 2>/dev/null || true)
fi

signaled=0
for pid in "${PIDS[@]:-}"; do
  [[ -n "${pid}" ]] || continue
  [[ "${pid}" == "$$" ]] && continue
  is_protected "${pid}" && {
    echo "kill-and-verify: PROTECT pid=${pid} (skip)" >&2
    continue
  }
  cmd="$(ps -p "${pid}" -o args= 2>/dev/null || true)"
  [[ "${cmd}" == *"${TASK_ID}"* ]] || continue
  if [[ "${cmd}" == *kill-and-verify-task-worker* ]] || [[ "${cmd}" == *"kanban watch"* ]] || [[ "${cmd}" == *tail* ]]; then
    continue
  fi
  echo "kill-and-verify: SIGTERM pid=${pid} cmd=${cmd}" >&2
  kill -TERM "${pid}" 2>/dev/null || true
  signaled=1
done

if [[ "${signaled}" -eq 1 ]]; then
  sleep 2
  for pid in "${PIDS[@]:-}"; do
    [[ -n "${pid}" ]] || continue
    is_protected "${pid}" && continue
    if kill -0 "${pid}" 2>/dev/null; then
      cmd="$(ps -p "${pid}" -o args= 2>/dev/null || true)"
      [[ "${cmd}" == *"${TASK_ID}"* ]] || continue
      echo "kill-and-verify: SIGKILL pid=${pid}" >&2
      kill -KILL "${pid}" 2>/dev/null || true
    fi
  done
fi

# Verify death
alive=0
mapfile -t CHECK < <(pgrep -f "kanban task ${TASK_ID}" 2>/dev/null || true)
for pid in "${CHECK[@]:-}"; do
  [[ -n "${pid}" ]] || continue
  is_protected "${pid}" && continue
  cmd="$(ps -p "${pid}" -o args= 2>/dev/null || true)"
  if [[ "${cmd}" == *"hermes"* && "${cmd}" == *"${TASK_ID}"* && "${cmd}" != *tail* ]]; then
    echo "FAIL: residual worker still alive pid=${pid} cmd=${cmd}" >&2
    alive=1
  fi
done

if [[ "${alive}" -ne 0 ]]; then
  exit 1
fi
echo "OK: kill-and-verify ${TASK_ID} (no residual hermes worker)"
