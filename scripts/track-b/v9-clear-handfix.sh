#!/usr/bin/env bash
# Clear O-HAND pending after durableize + re-run proof.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"

BANK_ID=""
HARNESS_SHA=""
RERUN=""
while [ $# -gt 0 ]; do
  case "$1" in
    --bank-id) BANK_ID="${2:-}"; shift 2 ;;
    --harness-sha) HARNESS_SHA="${2:-}"; shift 2 ;;
    --rerun-note) RERUN="${2:-}"; shift 2 ;;
    *) qg_die "usage: $0 --bank-id O-XXX --harness-sha <sha> --rerun-note '...'" ;;
  esac
done
[ -n "$BANK_ID" ] && [ -n "$HARNESS_SHA" ] && [ "${#RERUN}" -ge 15 ] \
  || qg_die "usage: $0 --bank-id O-XXX --harness-sha <sha> --rerun-note '...'"

PENDING="${ROOT}/tmp/V9-HANDFIX-PENDING.md"
[ -f "$PENDING" ] || qg_die "no handfix pending"

grep -qE "\|[[:space:]]*${BANK_ID}[[:space:]]*\|" "$BANK_DOC" \
  || qg_die "bank id $BANK_ID missing from V7 bank"

# Harness sha must exist in demo repo
git -C "$ROOT" cat-file -t "$HARNESS_SHA" 2>/dev/null | grep -qx commit \
  || qg_die "harness sha not a commit in demo repo: $HARNESS_SHA"

# Gate must mention handfix / durableize / bank id
grep -qiE "hand.?fix|durableize|temporary|probe" "$GATE_DOC" \
  || qg_die "${GATE_DOC:-docs/V10-QUALITY-GATE.md} lacks handfix/durableize notes"
grep -q "$BANK_ID" "$GATE_DOC" || qg_die "gate lacks bank id $BANK_ID"

{
  echo "- $(date -u +%Y-%m-%dT%H:%M:%SZ) bank=$BANK_ID harness=$HARNESS_SHA retest=$RERUN"
} >> "${ROOT}/tmp/V9-HANDFIX-CLEAR-LOG.md"
rm -f "$PENDING"
echo "O-HAND: cleared handfix pending"
