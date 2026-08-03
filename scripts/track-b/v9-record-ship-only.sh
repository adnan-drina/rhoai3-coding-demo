#!/usr/bin/env bash
# Record a harness SHIP_ONLY outcome as an honest story-complete commit (O-FALSECOMPLETE).
#
# Call only after /tmp/supervisor-done matches success* from SHIP_ONLY=1.
# Does NOT push by default (avoids ceremonial factory pipelines).
#
# Usage (in app repo):
#   bash v9-record-ship-only.sh S04
#   bash v9-record-ship-only.sh S04 'success route=… http=200 products=4'
#
# Env:
#   SUPERVISOR_DONE — override path (default /tmp/supervisor-done)
#   RECORD_PUSH=1   — also git push (default 0)
set -euo pipefail

# Optional lib (pod copy may run without repo checkout of scripts/).
_LIB="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)/scripts/track-b/lib-quality-gates.sh"
if [ -f "${_LIB:-}" ]; then
  # shellcheck source=/dev/null
  source "$_LIB"
fi

SID="${1:-}"
[ -n "$SID" ] || { echo "usage: $0 S0N [supervisor-done-text]" >&2; exit 2; }
DONE_FILE="${SUPERVISOR_DONE:-/tmp/supervisor-done}"
OUT="${2:-}"
if [ -z "$OUT" ]; then
  [ -f "$DONE_FILE" ] || { echo "missing $DONE_FILE" >&2; exit 1; }
  OUT=$(cat "$DONE_FILE")
fi

case "$OUT" in
  success*|story-gate-passed) ;;
  *)
    echo "REFUSE: supervisor-done is not success*/story-gate-passed (got: $OUT)" >&2
    exit 1
    ;;
esac

MSG="${SID} story complete: ${OUT}"
if type qg_story_complete_ok >/dev/null 2>&1; then
  qg_story_complete_ok "$MSG" || {
    echo "REFUSE: subject fails story-complete lint: $MSG" >&2
    exit 1
  }
else
  printf '%s\n' "$MSG" | grep -Eq \
    '^S0[0-9] story complete: (success .+|story-gate-passed)$' || {
    echo "REFUSE: subject fails story-complete lint: $MSG" >&2
    exit 1
  }
fi

STATUS="migration/${SID}-ship-status.md"
{
  echo "# ${SID} ship status"
  echo
  echo "Harness SHIP_ONLY earned: \`${OUT}\`"
  echo
  echo "- recorded: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- subject: \`${MSG}\`"
} >"$STATUS"

git add "$STATUS"
git commit -m "$MSG"
if [ -f migration/story-state.csv ] && ! grep -q "^${SID},complete" migration/story-state.csv; then
  echo "${SID},complete,$(date -u +%s)" >>migration/story-state.csv
  git add migration/story-state.csv
  git commit -m "${SID} story-state: complete after SHIP_ONLY"
fi

if [ "${RECORD_PUSH:-0}" = "1" ]; then
  git push origin HEAD
fi
echo "recorded: $MSG"
