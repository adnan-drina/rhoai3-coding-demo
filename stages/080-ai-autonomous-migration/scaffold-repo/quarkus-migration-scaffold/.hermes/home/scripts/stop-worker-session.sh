#!/usr/bin/env bash
# A-5 — operator-facing entry point to STOP a Hermes worker session.
#
# `hermes kanban block` alone does NOT stop the worker process (proven twice
# on v17: S-001 completed ~6h after block; S-008 already terminal). Use this
# script (or block-and-signal-worker.sh directly). Contract:
#   .hermes/platform/known-hermes-behaviours.md
set -euo pipefail

case "${1:-}" in
  -h|--help)
    cat <<'USAGE'
stop-worker-session.sh — hard-stop a Hermes worker for a kanban task.

Usage:
  bash .hermes/home/scripts/stop-worker-session.sh [--kind KIND] TASK_ID [reason…]

Wraps block-and-signal-worker.sh (board block + SIGTERM/SIGKILL + verify death).
Never claim containment from `hermes kanban block` alone.
USAGE
    exit 0
    ;;
esac

SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# A-5 is seat ops. A kanban worker that targets its own card must not
# SIGTERM itself (v32 M3 holder t_adbb6995: imagined OOB → self-kill).
# Outside the worker, HERMES_KANBAN_TASK is unset. Override: HERMES_SEAT_OPS=1.
TASK_FOR_REFUSE=""
for _a in "$@"; do
  case "${_a}" in
    t_*) TASK_FOR_REFUSE="${_a}"; break ;;
  esac
done
if [[ -n "${HERMES_KANBAN_TASK:-}" && -n "${TASK_FOR_REFUSE}" && "${HERMES_KANBAN_TASK}" == "${TASK_FOR_REFUSE}" && "${HERMES_SEAT_OPS:-}" != "1" ]]; then
  echo "stop-worker-session: refuse self-stop on ${TASK_FOR_REFUSE} (A-5 is seat ops). Use hermes kanban block. Seat ops: HERMES_SEAT_OPS=1." >&2
  exit 78
fi

exec bash "${SELF}/block-and-signal-worker.sh" "$@"
