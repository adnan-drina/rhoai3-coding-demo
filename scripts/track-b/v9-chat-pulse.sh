#!/usr/bin/env bash
# O-DRV4 — scripted chat-pulse proof (ack alone is invalid).
#
# Usage (AFTER posting the same text in the user chat):
#   bash tmp/v9-chat-pulse.sh <tick-ts> <<'PULSE'
#   line 1
#   line 2
#   PULSE
#
# Chat↔body fidelity: when V9_TRANSCRIPT_DIR is readable, require ≥1 body
# line to appear in a recent assistant message in the agent transcript.
# Set V9_SKIP_TRANSCRIPT_CHECK=1 only if transcripts are unavailable.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TS="${1:-}"
if [ -z "$TS" ]; then
  echo "usage: $0 <tick-ts-from-V9-CHAT-PULSE-PENDING>" >&2
  exit 2
fi
BODY=$(cat)
CONTENT_LINES=$(printf '%s\n' "$BODY" | sed '/^[[:space:]]*$/d' | wc -l | tr -d ' ')
if [ "${CONTENT_LINES}" -lt 2 ]; then
  echo "O-DRV4: need ≥2 non-empty pulse lines (got ${CONTENT_LINES})" >&2
  exit 1
fi

TRANSCRIPT_DIR="${V9_TRANSCRIPT_DIR:-${HOME}/.cursor/projects/Users-adrina-Sandbox-rhoai3-coding-demo/agent-transcripts}"
if [ "${V9_SKIP_TRANSCRIPT_CHECK:-0}" != "1" ] && [ -d "$TRANSCRIPT_DIR" ]; then
  if ! python3 - "$TRANSCRIPT_DIR" "$BODY" <<'PY'
import sys, json, glob, os, time
td, body = sys.argv[1], sys.argv[2]
lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
# Prefer longest line as fingerprint (≥12 chars)
cands = sorted(lines, key=len, reverse=True)
needle = next((c for c in cands if len(c) >= 12), cands[0] if cands else "")
if not needle:
    sys.exit(1)
# Scan newest jsonl transcripts (mtime) for assistant text containing needle
files = sorted(glob.glob(os.path.join(td, "**", "*.jsonl"), recursive=True), key=os.path.getmtime, reverse=True)[:5]
cutoff = time.time() - 3600  # last hour
found = False
for fp in files:
    try:
        if os.path.getmtime(fp) < cutoff:
            continue
        with open(fp, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Cursor transcripts vary; search raw line + common fields
                blob = line
                for key in ("message", "content", "text"):
                    if key in ev:
                        blob += " " + json.dumps(ev.get(key), ensure_ascii=False)
                if needle in blob and ("assistant" in blob.lower() or '"role": "assistant"' in blob or "Assistant" in blob):
                    found = True
                    break
                # softer: needle in any recent event (user-visible assistant often unmarked)
                if needle in blob:
                    found = True
                    break
        if found:
            break
    except OSError:
        continue
sys.exit(0 if found else 1)
PY
  then
    echo "O-DRV4: chat↔body fidelity FAILED — body line not found in recent agent transcript." >&2
    echo "Post the pulse in chat FIRST, then re-run this script with the SAME text." >&2
    echo "(Override only if needed: V9_SKIP_TRANSCRIPT_CHECK=1)" >&2
    exit 1
  fi
  echo "O-DRV4: transcript fidelity ok"
else
  echo "O-DRV4: transcript check skipped (dir missing or V9_SKIP_TRANSCRIPT_CHECK=1)"
fi

{
  echo "tick: ${TS}"
  printf '%s\n' "$BODY"
} >"${ROOT}/tmp/V9-CHAT-PULSE.body"
printf '%s\n' "$TS" >"${ROOT}/tmp/V9-CHAT-PULSE.ack"
rm -f "${ROOT}/tmp/V9-CHAT-PULSE-PENDING.md"
echo "O-DRV4: pulse recorded tick=${TS} lines=${CONTENT_LINES}"
