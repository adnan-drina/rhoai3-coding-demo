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
exec bash "${SELF}/block-and-signal-worker.sh" "$@"
