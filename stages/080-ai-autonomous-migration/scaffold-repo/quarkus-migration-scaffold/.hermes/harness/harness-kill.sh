#!/usr/bin/env bash
# O-KILLLEDGER (F-73/F5) — every harness kill writes tag/pid/signal/cause.
# Source:  # shellcheck source=harness-kill.sh
#          . "$(dirname "$0")/harness-kill.sh"
# Direct:  bash harness-kill.sh <tag> <pid> <SIG> <cause>
KILL_LEDGER="${KILL_LEDGER:-/tmp/kill-ledger.log}"

harness_kill() { # tag pid sig cause
  local tag=$1 pid=$2 sig=$3 cause=$4
  [[ -n "${pid:-}" && "$pid" =~ ^[0-9]+$ ]] || return 0
  kill "-$sig" "$pid" 2>/dev/null || return 0
  printf '%s tag=%s pid=%s sig=%s cause=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$tag" "$pid" "$sig" "$cause" \
    >> "$KILL_LEDGER" 2>/dev/null || true
}

# Process-group kill (opencode run → serve child). Prefers kill -- -pid.
harness_kill_group() { # tag pid sig cause
  local tag=$1 pid=$2 sig=$3 cause=$4
  [[ -n "${pid:-}" && "$pid" =~ ^[0-9]+$ ]] || return 0
  if kill "-$sig" -- "-$pid" 2>/dev/null; then
    printf '%s tag=%s pid=%s sig=%s cause=%s (group)\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$tag" "$pid" "$sig" "$cause" \
      >> "$KILL_LEDGER" 2>/dev/null || true
    return 0
  fi
  harness_kill "$tag" "$pid" "$sig" "$cause"
}

if [[ "${BASH_SOURCE[0]:-}" == "${0:-}" ]]; then
  set -euo pipefail
  [[ $# -ge 4 ]] || { echo "usage: harness-kill.sh <tag> <pid> <SIG> <cause>" >&2; exit 2; }
  harness_kill "$@"
fi
