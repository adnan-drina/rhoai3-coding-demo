#!/usr/bin/env bash
# Block story advance without ADVANCE (or explicit HOLD/ABORT) in the quality gate.
#
# Modes:
#   check S0N     — exit 0 if gate has Verdict ADVANCE for that story
#   pending S0N   — write V9-ADVANCE-PENDING.md
#   clear S0N     — clear pending only if ADVANCE present
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"

MODE="${1:-}"
STORY="${2:-}"
PENDING="${ROOT}/tmp/V9-ADVANCE-PENDING.md"
[ -n "$MODE" ] && [ -n "$STORY" ] || qg_die "usage: $0 check|pending|clear S0N"

story_has_advance() {
  # O-ADVTASK: only story-level sections count — task sections that mention
  # S0N + ADVANCE (e.g. "S03 T-004 detailed") must NOT green the story gate.
  python3 - "$GATE_DOC" "$STORY" <<'PY'
import sys, re
path, story = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8", errors="replace").read()
parts = re.split(r"(?m)^(## .+)$", text)
story_mark = re.compile(
    r"story\s+complete|story\s+gate|full\s*-?\s*gate|\bship\b|"
    + re.escape(story) + r"\s+(HOLD|ABORT|ADVANCE)\b",
    re.I,
)
for i in range(1, len(parts), 2):
    header, body = parts[i], parts[i + 1] if i + 1 < len(parts) else ""
    if story not in header:
        continue
    if re.search(r"T-\d+", header):
        continue  # task-level section
    blob = header + "\n" + body[:1200]
    if not story_mark.search(blob):
        continue
    if re.search(r"\*\*Verdict:\*\*\s*ADVANCE", body, re.I):
        sys.exit(0)
sys.exit(1)
PY
}

case "$MODE" in
  check)
    if story_has_advance; then
      echo "ADVANCE GATE GREEN for $STORY"
      exit 0
    fi
    echo "ADVANCE GATE RED for $STORY — no **Verdict:** ADVANCE in ${GATE_DOC:-docs/V10-QUALITY-GATE.md}" >&2
    exit 1
    ;;
  pending)
    {
      echo "# V9 ADVANCE PENDING (O-ADV) — story advance blocked"
      echo
      echo "- story: \`$STORY\`"
      echo "- written: \`$(date -u +%Y-%m-%dT%H:%M:%SZ)\`"
      echo
      echo "Write a comprehensive gate section for $STORY with \`**Verdict:** ADVANCE\`"
      echo "(or HOLD/ABORT — do not clear on HOLD/ABORT; fix first)."
      echo "Clear: \`bash scripts/track-b/v9-advance-gate.sh clear $STORY\`"
    } >"$PENDING"
    echo "wrote $PENDING"
    ;;
  clear)
    story_has_advance || qg_die "cannot clear — no ADVANCE verdict for $STORY"
    rm -f "$PENDING"
    echo "O-ADV: cleared advance pending for $STORY"
    ;;
  *) qg_die "usage: $0 check|pending|clear S0N" ;;
esac
