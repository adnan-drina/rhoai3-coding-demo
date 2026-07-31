#!/usr/bin/env bash
# O-DRV3 — clear task analysis ONLY after:
#   1) a real V9-QUALITY-GATE.md review (substance + diff evidence), AND
#   2) an Implementing note in tmp/KAI-WAVE2-REVIEW.md citing this sha
#      (when that review doc exists — Wave-1 handshake).
#
# Usage:
#   bash scripts/track-b/v9-clear-task-analysis.sh <full-or-short-sha>
# Bare `echo SHA > tmp/V9-TASK-ANALYSIS.sha` does NOT clear.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"

SHA_IN="${1:-}"
[ -n "$SHA_IN" ] || qg_die "usage: $0 <sha-reviewed>"

PENDING="${ROOT}/tmp/V9-TASK-ANALYSIS-PENDING.md"
ESC_PENDING="${ROOT}/tmp/V9-ESCALATION-PENDING.md"
SHA="$SHA_IN"
if [ -f "$PENDING" ]; then
  HEAD=$(grep -oE '[0-9a-f]{40}' "$PENDING" | head -1 || true)
  if [ -n "$HEAD" ] && { [ "$SHA_IN" = "$HEAD" ] || [ "$SHA_IN" = "${HEAD:0:7}" ]; }; then
    SHA="$HEAD"
  fi
fi
if [ "${#SHA}" -lt 40 ]; then
  for f in "${ROOT}/tmp/V9-DIFF-EVIDENCE/"*.stat; do
    [ -f "$f" ] || continue
    base=$(basename "$f" .stat)
    if [ "${#base}" -eq 40 ] && { [ "$SHA" = "$base" ] || [ "$SHA" = "${base:0:7}" ]; }; then
      SHA="$base"
      break
    fi
  done
fi
[ "${#SHA}" -ge 7 ] || qg_die "invalid sha: $SHA_IN"

if [ -f "$ESC_PENDING" ]; then
  qg_die "V9-ESCALATION-PENDING exists — run v9-clear-escalation.sh before O-DRV3 clear"
fi

BODY=$(python3 - "$GATE_DOC" "$SHA" <<'PY'
import sys, re
path, sha = sys.argv[1], sys.argv[2]
short = sha[:7]
text = open(path, encoding="utf-8", errors="replace").read()
parts = re.split(r"(?m)^(## .+)$", text)
bodies = []
for i in range(1, len(parts), 2):
    header, body = parts[i], parts[i + 1] if i + 1 < len(parts) else ""
    blob = header + "\n" + body
    if sha in blob or short in blob:
        bodies.append(body)
if not bodies:
    sys.exit(2)
print(bodies[-1])  # most recent matching section
PY
) || qg_die "no tmp/docs-archive/V9-QUALITY-GATE.md section mentions sha $SHA — write the detailed gate entry first"

qg_validate_task_section "$BODY"
qg_validate_diff_evidence "$SHA" "$BODY"
qg_require_wave1_review_note "$SHA"

qg_write_validated_sha "${ROOT}/tmp/V9-TASK-ANALYSIS.sha" "$SHA"
rm -f "$PENDING"
echo "O-DRV3: cleared task analysis for $SHA (gate+diff+review-doc validated)"
