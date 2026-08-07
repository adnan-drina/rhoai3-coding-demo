#!/usr/bin/env bash
# O-ESCTERM60 — commit a gated T-NNN / sensor-fix tip without re-running the
# commit-msg sensor under a short Hermes terminal timeout.
#
# Flow: run sensors.sh task once in this process, then SKIP_SENSOR_GATE=1 commit.
# Use this from Hermes/MiniMax instead of bare `git commit` (hook runs the full
# task sensor and often exceeds a 60s tool timeout → exit 124, tip never lands).
set -euo pipefail

usage() {
  echo "usage: commit-gated.sh '<subject>' [path ...]" >&2
  echo "  Runs .hermes/harness/sensors.sh task, then SKIP_SENSOR_GATE=1 git commit." >&2
  exit 2
}

[[ $# -ge 1 ]] || usage
MSG=$1
shift

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"

if [[ $# -gt 0 ]]; then
  git add -- "$@"
fi

# O-T1FINDINGS / O-SFIXSCOPE: never land findings inventory on a coding tip.
if git diff --cached --name-only | grep -qx 'migration/mta-findings-current.json'; then
  echo "commit-gated: unstaging migration/mta-findings-current.json (O-T1FINDINGS)" >&2
  git restore --staged -- migration/mta-findings-current.json || true
fi

if git diff --cached --quiet; then
  echo "commit-gated: nothing staged" >&2
  exit 1
fi

echo "commit-gated: running sensors.sh task …"
bash "$ROOT/.hermes/harness/sensors.sh" task

echo "commit-gated: SKIP_SENSOR_GATE=1 git commit"
SKIP_SENSOR_GATE=1 git commit -m "$MSG"
echo "commit-gated: OK — $(git log -1 --oneline)"
