#!/usr/bin/env bash
# Refuse outer-loop / restart while open bank rows remain.
#
# Modes:
#   honesty — fail if honesty-blocking ⬜ rows (default for mid-run start)
#   all     — fail if ANY ⬜ row (wipe/restart / new run)
#   count   — print open ids and exit 0
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"

MODE="${1:-honesty}"
case "$MODE" in
  count)
    echo "open:"
    qg_open_bank_ids || true
    echo "honesty-open:"
    qg_honesty_open_ids || true
    exit 0
    ;;
  honesty)
    IDS=$(qg_honesty_open_ids || true)
    if [ -n "$IDS" ]; then
      echo "BANK GATE RED (honesty): open honesty-blocking ⬜ rows:" >&2
      echo "$IDS" | sed 's/^/  - /' >&2
      echo "Implement (⬜→✅) or HOLD — V9_ALLOW_OPEN_BANK=1 only for documented mid-run heal." >&2
      exit 1
    fi
    echo "BANK GATE GREEN (honesty): no honesty-blocking open rows"
    ;;
  all)
    IDS=$(qg_open_bank_ids || true)
    if [ -n "$IDS" ]; then
      echo "BANK GATE RED (all polish): open ⬜ rows before restart/new run:" >&2
      echo "$IDS" | sed 's/^/  - /' >&2
      exit 1
    fi
    echo "BANK GATE GREEN (all): no open polish rows"
    ;;
  *) qg_die "usage: $0 [honesty|all|count]" ;;
esac
