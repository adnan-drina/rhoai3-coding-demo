#!/usr/bin/env bash
# Detect hand fixes in the live app (dirty src/ while agents idle) without a
# matching harness durableize + re-run proof.
#
# Writes tmp/V9-HANDFIX-PENDING.md when dirty src/ and no worker/orch running.
# Clear via v9-clear-handfix.sh after durableize.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/lib.sh"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"
load_env >/dev/null 2>&1 || true

POD="$(qg_ws_pod)"
NS="$(qg_ws_ns)"
CTR="$(qg_ws_ctr)"
PENDING="${ROOT}/tmp/V9-HANDFIX-PENDING.md"

if ! oc whoami >/dev/null 2>&1; then
  echo "handfix-detect: oc not logged in — skip"
  exit 0
fi

SNAP=$(oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
  cd /projects/modernized || exit 0
  DIRTY=$(git status --porcelain -- src/ 2>/dev/null | head -40)
  H=$(pgrep -f "venv/bin/python.*hermes chat" >/dev/null && echo UP || echo DOWN)
  O=$(pgrep -x opencode >/dev/null && echo UP || echo DOWN)
  S=$(pgrep -f "harness/supervisor\.sh" >/dev/null && echo UP || echo DOWN)
  OL=$(pgrep -f "harness/outer-loop\.sh" >/dev/null && echo UP || echo DOWN)
  printf "agents=%s/%s/%s/%s\n" "$H" "$O" "$S" "$OL"
  if [ -n "$DIRTY" ]; then
    echo "DIRTY_BEGIN"
    printf "%s\n" "$DIRTY"
    echo "DIRTY_END"
  fi
  # O-HANDCOMMIT: committed remounts while idle are invisible to dirty-only detect.
  # Flag src/ commits in the last 30m when no supervisor attempt is open.
  RECENT=$(git log --since="30 minutes ago" --oneline -- src/ 2>/dev/null | head -8)
  if [ -n "$RECENT" ]; then
    echo "RECENT_BEGIN"
    printf "%s\n" "$RECENT"
    echo "RECENT_END"
  fi
' 2>/dev/null | qg_strip_oc_noise || true)

# If any agent is UP, dirty/recent commits are expected — not a hand-fix smell.
AGENTS=$(echo "$SNAP" | grep -E 'agents=(UP|DOWN)/' | head -1 || true)
if echo "$AGENTS" | grep -q 'UP'; then
  echo "handfix: agents busy ($AGENTS) — skip"
  rm -f "$PENDING"  # clear false positives from prior ticks
  exit 0
fi

HAS_DIRTY=0
HAS_RECENT=0
echo "$SNAP" | grep -q 'DIRTY_BEGIN' && HAS_DIRTY=1
echo "$SNAP" | grep -q 'RECENT_BEGIN' && HAS_RECENT=1

if [ "$HAS_DIRTY" -eq 0 ] && [ "$HAS_RECENT" -eq 0 ]; then
  rm -f "$PENDING"
  echo "handfix: clean src/ (no dirty, no recent commits)"
  exit 0
fi

DIRTY=$(echo "$SNAP" | sed -n '/DIRTY_BEGIN/,/DIRTY_END/p' | grep -v DIRTY_ || true)
RECENT=$(echo "$SNAP" | sed -n '/RECENT_BEGIN/,/RECENT_END/p' | grep -v RECENT_ || true)
{
  echo "# V9 HANDFIX PENDING (O-HAND / O-HANDCOMMIT) — temporary→durable→re-run"
  echo
  echo "- written: \`$(date -u +%Y-%m-%dT%H:%M:%SZ)\`"
  if [ "$HAS_DIRTY" -eq 1 ]; then
    echo "- agents idle with dirty \`src/\` — likely a hand / probe edit"
  fi
  if [ "$HAS_RECENT" -eq 1 ]; then
    echo "- agents idle with recent \`src/\` commits (30m) and no open supervisor — possible hand remount (O-HANDCOMMIT)"
  fi
  echo
  if [ "$HAS_DIRTY" -eq 1 ]; then
    echo "## Dirty paths"
    echo '```'
    echo "$DIRTY"
    echo '```'
    echo
  fi
  if [ "$HAS_RECENT" -eq 1 ]; then
    echo "## Recent src/ commits (30m)"
    echo '```'
    echo "$RECENT"
    echo '```'
    echo
  fi
  echo "## Required before clear"
  echo
  echo "1. Validate the probe (does it fix the failure class?)."
  echo "2. Durableize in harness/skills/sensors (bank ⬜→✅) — migration-general."
  echo "3. Re-run so the *process* applies the fix (abort/resume)."
  echo "4. Clear: \`bash scripts/track-b/v9-clear-handfix.sh --bank-id O-XXX --harness-sha <demo-sha> --rerun-note '...'\`"
} >"$PENDING"
echo "handfix: PENDING written → $PENDING"
exit 0
