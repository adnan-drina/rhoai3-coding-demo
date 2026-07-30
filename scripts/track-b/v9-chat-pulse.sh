#!/usr/bin/env bash
# O-DRV4 — scripted chat-pulse proof (ack alone is invalid).
#
# Usage (after posting the same text in the user chat):
#   bash tmp/v9-chat-pulse.sh <tick-ts> <<'PULSE'
#   line 1
#   line 2
#   ...
#   PULSE
#
# Writes:
#   tmp/V9-CHAT-PULSE.body  (tick: <ts> + body)
#   tmp/V9-CHAT-PULSE.ack   (<ts>)
# and removes tmp/V9-CHAT-PULSE-PENDING.md
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." ROOT="$(cd "$(dirname "$0")/.." && pwd)"ROOT="$(cd "$(dirname "$0")/.." && pwd)" pwd)"
TS="${1:-}"
if [ -z "$TS" ]; then
  echo "usage: $0 <tick-ts-from-V9-CHAT-PULSE-PENDING>" >&2
  exit 2
fi
BODY=$(cat)
# trim trailing whitespace-only lines for count, keep content
CONTENT_LINES=$(printf '%s\n' "$BODY" | sed '/^[[:space:]]*$/d' | wc -l | tr -d ' ')
if [ "${CONTENT_LINES}" -lt 2 ]; then
  echo "O-DRV4: need ≥2 non-empty pulse lines (got ${CONTENT_LINES})" >&2
  exit 1
fi
{
  echo "tick: ${TS}"
  printf '%s\n' "$BODY"
} >"${ROOT}/tmp/V9-CHAT-PULSE.body"
printf '%s\n' "$TS" >"${ROOT}/tmp/V9-CHAT-PULSE.ack"
rm -f "${ROOT}/tmp/V9-CHAT-PULSE-PENDING.md"
echo "O-DRV4: pulse recorded tick=${TS} lines=${CONTENT_LINES}"
