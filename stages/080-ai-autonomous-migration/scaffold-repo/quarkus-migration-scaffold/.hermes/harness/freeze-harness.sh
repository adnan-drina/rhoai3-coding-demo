#!/usr/bin/env bash
# O-KILLREL — stop Track B agents without matching absolute harness paths.
# Live argv is often: bash .hermes/harness/outer-loop.sh (relative, no leading /).
# Patterns must match the relative form used by outer-loop's self-guard.
set -euo pipefail
cd "${SENSOR_ROOT:-/projects/modernized}"

SELF_PAT='freeze-harnes[s]\.sh'
kill_pat() {
  local pat="$1"
  # shellcheck disable=SC2009
  ps -eo pid=,args= | while read -r pid args; do
    echo "$args" | grep -qE "$SELF_PAT" && continue
    echo "$args" | grep -qE "$pat" || continue
    kill -TERM "$pid" 2>/dev/null || true
  done
  sleep 1
  ps -eo pid=,args= | while read -r pid args; do
    echo "$args" | grep -qE "$SELF_PAT" && continue
    echo "$args" | grep -qE "$pat" || continue
    kill -KILL "$pid" 2>/dev/null || true
  done
}

# Character-class trick avoids matching this script's own argv text.
kill_pat 'harness/outer-loo[p]\.sh'
kill_pat 'harness/superviso[r]\.sh'
kill_pat 'venv/bin/python.*hermes cha[t]'
kill_pat '[o]pencode (run|serve)'

touch /tmp/supervisor-pause 2>/dev/null || true
echo "freeze-harness: agents signaled; /tmp/supervisor-pause touched"
pgrep -af 'harness/outer-loo[p]\.sh|harness/superviso[r]\.sh|hermes cha[t]|[o]pencode' \
  && echo "freeze-harness: WARNING still running" || echo "freeze-harness: clear"
