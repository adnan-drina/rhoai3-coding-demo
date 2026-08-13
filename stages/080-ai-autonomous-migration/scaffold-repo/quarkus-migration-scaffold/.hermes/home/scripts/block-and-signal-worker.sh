#!/usr/bin/env bash
# Deputy E-20260811T131900Z / Operator E-20260811T133000Z banked #2 —
# board `hermes kanban block` alone does not stop an in-flight worker.
# Block, then SIGTERM→SIGKILL any worker process whose argv cites the task id.
#
# Usage:
#   bash .hermes/home/scripts/block-and-signal-worker.sh t_xxx "reason…"
#   bash .hermes/home/scripts/block-and-signal-worker.sh --kind needs_input t_xxx "reason…"
set -euo pipefail

KIND=""
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --kind) KIND="$2"; shift 2 ;;
    --) shift; ARGS+=("$@"); break ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
[[ ${#ARGS[@]} -ge 1 ]] || {
  echo "usage: block-and-signal-worker.sh [--kind KIND] TASK_ID [reason…]" >&2
  exit 2
}
TASK_ID="${ARGS[0]}"
REASON="${ARGS[*]:1}"
REASON="${REASON:-Lead/Deputy block-and-signal (Operator E-20260811T133000Z)}"

command -v hermes >/dev/null 2>&1 || {
  echo "block-and-signal-worker: hermes not on PATH" >&2
  exit 1
}

BLOCK_ARGS=(kanban block)
[[ -n "${KIND}" ]] && BLOCK_ARGS+=(--kind "${KIND}")
BLOCK_ARGS+=("${TASK_ID}" "${REASON}")
hermes "${BLOCK_ARGS[@]}" || {
  # todo cards may refuse block — still signal any live worker
  echo "block-and-signal-worker: hermes block rc=$? (continuing to signal)" >&2
}

# Match hermes worker argv that cites this task (chat -q work kanban task t_…)
mapfile -t PIDS < <(pgrep -f "kanban task ${TASK_ID}" 2>/dev/null || true)
if [[ ${#PIDS[@]} -eq 0 ]]; then
  # broader: any hermes process with the task id in argv
  mapfile -t PIDS < <(pgrep -f "${TASK_ID}" 2>/dev/null || true)
fi

signaled=0
for pid in "${PIDS[@]:-}"; do
  [[ -n "${pid}" ]] || continue
  # never kill ourselves / the block script
  [[ "${pid}" == "$$" ]] && continue
  cmd="$(ps -p "${pid}" -o args= 2>/dev/null || true)"
  # skip kanban watch / gateway / this script
  if [[ "${cmd}" == *block-and-signal-worker* ]] || [[ "${cmd}" == *"kanban watch"* ]]; then
    continue
  fi
  if [[ "${cmd}" != *"${TASK_ID}"* ]]; then
    continue
  fi
  echo "block-and-signal-worker: SIGTERM pid=${pid} cmd=${cmd}" >&2
  kill -TERM "${pid}" 2>/dev/null || true
  signaled=1
done

if [[ "${signaled}" -eq 1 ]]; then
  sleep 2
  for pid in "${PIDS[@]:-}"; do
    [[ -n "${pid}" ]] || continue
    if kill -0 "${pid}" 2>/dev/null; then
      cmd="$(ps -p "${pid}" -o args= 2>/dev/null || true)"
      [[ "${cmd}" == *"${TASK_ID}"* ]] || continue
      echo "block-and-signal-worker: SIGKILL pid=${pid}" >&2
      kill -KILL "${pid}" 2>/dev/null || true
    fi
  done
else
  echo "block-and-signal-worker: no live worker matched ${TASK_ID}" >&2
fi

# Architect E-20260811T173254Z — verify death (residual-worker Class A)
VERIFY="$(cd "$(dirname "$0")" && pwd)/kill-and-verify-task-worker.sh"
if [[ -f "${VERIFY}" ]]; then
  bash "${VERIFY}" "${TASK_ID}" || {
    echo "block-and-signal-worker: FAIL verify death for ${TASK_ID}" >&2
    exit 1
  }
fi

echo "OK: block-and-signal ${TASK_ID}"
