#!/usr/bin/env bash
# O-STOPMARKER — write migration/.stopped for a deliberate terminal stop.
# Usage (from modernized root):
#   bash .hermes/harness/write-stopped.sh \
#     --reason "…" --authorizing "…" --expected-next "…"
# Optional: --kind deliberate-stop --related "O-STOPMARKER O-RESUMEPROV"
set -euo pipefail
KIND="deliberate-stop"
REASON=""
AUTH=""
EXPECTED=""
RELATED="O-STOPMARKER O-RESUMEPROV ADR-10 ADR-18"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --kind) KIND="${2:-deliberate-stop}"; shift 2 ;;
    --reason) REASON="${2:-}"; shift 2 ;;
    --authorizing) AUTH="${2:-}"; shift 2 ;;
    --expected-next) EXPECTED="${2:-}"; shift 2 ;;
    --related) RELATED="${2:-}"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
[ -n "$REASON" ] || { echo "REFUSE: --reason required" >&2; exit 2; }
[ -n "$AUTH" ] || { echo "REFUSE: --authorizing required" >&2; exit 2; }
[ -n "$EXPECTED" ] || { echo "REFUSE: --expected-next required" >&2; exit 2; }
mkdir -p migration
TIP=$(git rev-parse HEAD 2>/dev/null || echo unknown)
UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
cat > migration/.stopped <<EOF
kind: ${KIND}
utc: ${UTC}
authorizing: ${AUTH}
tip: ${TIP}
reason: ${REASON}
expected_next: ${EXPECTED}
related: ${RELATED}
EOF
echo "O-STOPMARKER wrote migration/.stopped tip=${TIP}"
