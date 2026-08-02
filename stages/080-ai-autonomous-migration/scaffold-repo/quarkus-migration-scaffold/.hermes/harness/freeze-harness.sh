#!/usr/bin/env bash
# O-FRZSIG (F-73/F1 / F-74) — freeze = signal, not slaughter.
# Default: set the pause marker the loops already honor at checkpoints
# (O-DEBTFRZ contract: do not continue to the next task). Kills NOTHING
# unless --hard, and then only REGISTERED task workers (never ship-loop
# hermes, never m5-evaluate). Mid-M5 freezes are deferred.
set -euo pipefail
cd "${SENSOR_ROOT:-/projects/modernized}"

HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=harness-kill.sh
. "$HERE/harness-kill.sh"

# One-marker rule: never fire hard (or even re-freeze loudly) mid M5 round.
if [[ -f /tmp/m5-round-active ]]; then
  touch /tmp/supervisor-pause-deferred
  echo "freeze-harness: deferred — /tmp/m5-round-active present (pause queued)"
  exit 0
fi

touch /tmp/supervisor-pause
echo "freeze-harness: pause marker set — loops stop at next checkpoint (no sessions killed)"

if [[ "${1:-}" == "--hard" ]]; then
  shopt -s nullglob
  for f in /tmp/sessions/T-*.pid; do
    [[ -f "$f" ]] || continue
    pid=$(tr -d '[:space:]' <"$f" || true)
    tag=$(basename "$f" .pid)
    # Skip protected tags even if mis-registered.
    case "$tag" in
      m5-evaluate|m5-*|preflight*|ship*|gatefix*) continue ;;
    esac
    harness_kill "$tag" "$pid" TERM freeze-hard
  done
  echo "freeze-harness: --hard TERM sent to registered T-* workers only (see /tmp/kill-ledger.log)"
fi
