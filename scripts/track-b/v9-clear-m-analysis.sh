#!/usr/bin/env bash
# O-DRV5 — clear milestone analysis ONLY after:
#   1) a comprehensive gate entry with Verdict ADVANCE|HOLD|ABORT, AND
#   2) an Implementing note in tmp/KAI-WAVE4-REVIEW.md citing this sha
#      (when that review doc exists — Wave-1 handshake).
#
# Usage:
#   bash scripts/track-b/v9-clear-m-analysis.sh <sha> [--require-advance]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"

SHA_IN="${1:-}"
REQUIRE_ADVANCE=0
[ "${2:-}" = "--require-advance" ] && REQUIRE_ADVANCE=1
[ -n "$SHA_IN" ] || qg_die "usage: $0 <sha> [--require-advance]"

PENDING="${ROOT}/tmp/V9-M-ANALYSIS-PENDING.md"
SHA="$SHA_IN"
if [ -f "$PENDING" ]; then
  HEAD=$(grep -oE '[0-9a-f]{40}' "$PENDING" | head -1 || true)
  if [ -n "$HEAD" ] && { [ "$SHA_IN" = "$HEAD" ] || [ "$SHA_IN" = "${HEAD:0:7}" ]; }; then
    SHA="$HEAD"
  fi
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
print(bodies[-1])
PY
) || qg_die "no tmp/docs-archive/V9-QUALITY-GATE.md section mentions sha $SHA"

qg_validate_m_section "$BODY"
if [ "$REQUIRE_ADVANCE" = "1" ]; then
  echo "$BODY" | grep -qiE '\*\*Verdict:\*\*[[:space:]]*ADVANCE' \
    || qg_die "ADVANCE required but gate verdict is not ADVANCE"
fi
qg_require_wave1_review_note "$SHA"

qg_write_validated_sha "${ROOT}/tmp/V9-M-ANALYSIS.sha" "$SHA"
# Watermark outer M line if present in pending
if [ -f "$PENDING" ]; then
  OUTER=$(grep -E '^OUTER:' "$PENDING" | head -1 || true)
  [ -n "$OUTER" ] && printf '%s\n' "${OUTER#OUTER: }" > "${ROOT}/tmp/V9-OUTER-M-WATERMARK"
fi
rm -f "$PENDING"
echo "O-DRV5: cleared milestone analysis for $SHA (gate+verdict+review-doc validated)"
