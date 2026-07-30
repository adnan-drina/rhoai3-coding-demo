#!/usr/bin/env bash
# O-DRV7 — clear MiniMax-over-Qwen escalation ONLY after RCA + durableize + retest note.
#
# Usage:
#   bash scripts/track-b/v9-clear-escalation.sh <task-id> \
#     --qwen-cause "..." --bank-id O-XXX --retest "..."
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"

TASK=""
QWEN_CAUSE=""
BANK_ID=""
RETEST=""
while [ $# -gt 0 ]; do
  case "$1" in
    --qwen-cause) QWEN_CAUSE="${2:-}"; shift 2 ;;
    --bank-id) BANK_ID="${2:-}"; shift 2 ;;
    --retest) RETEST="${2:-}"; shift 2 ;;
    -*) qg_die "unknown flag $1" ;;
    *) TASK="$1"; shift ;;
  esac
done

[ -n "$TASK" ] || qg_die "usage: $0 T-NNN --qwen-cause '...' --bank-id O-XXX --retest '...'"
[ "${#QWEN_CAUSE}" -ge 40 ] || qg_die "--qwen-cause too short (need ≥40 chars of real RCA)"
[ -n "$BANK_ID" ] || qg_die "--bank-id required (banked harness gap id)"
[ "${#RETEST}" -ge 20 ] || qg_die "--retest too short (owed proof or completed re-run note)"

PENDING="${ROOT}/tmp/V9-ESCALATION-PENDING.md"
[ -f "$PENDING" ] || qg_die "no escalation pending file"

# Gate must mention this task + Qwen / escalation RCA
qg_require_file "$GATE_DOC"
python3 - "$GATE_DOC" "$TASK" "$BANK_ID" <<'PY' || exit 1
import sys, re
path, task, bank = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8", errors="replace").read()
low = text.lower()
if task.lower() not in low and task.replace("-", "").lower() not in low.replace("-", ""):
    print(f"FAIL: gate doc does not mention {task}", file=sys.stderr); sys.exit(1)
if not re.search(r"qwen|/tmp/oc-t-|worker (failed|incomplete|rc=)|root cause", low):
    print("FAIL: gate lacks Qwen/worker root-cause language", file=sys.stderr); sys.exit(1)
if not re.search(r"minimax|escalat", low):
    print("FAIL: gate lacks MiniMax/escalation review", file=sys.stderr); sys.exit(1)
if bank.lower() not in low:
    print(f"FAIL: gate does not mention bank id {bank}", file=sys.stderr); sys.exit(1)
print("ok")
PY

# Bank row must exist (⬜ or ✅)
grep -qE "\|[[:space:]]*${BANK_ID}[[:space:]]*\|" "$BANK_DOC" \
  || qg_die "bank id $BANK_ID not found in ${BANK_DOC}"

{
  echo "# escalation clear record"
  echo "- task: $TASK"
  echo "- cleared: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- bank_id: $BANK_ID"
  echo "- qwen_cause: $QWEN_CAUSE"
  echo "- retest: $RETEST"
} >> "${ROOT}/tmp/V9-ESCALATION-CLEAR-LOG.md"

rm -f "$PENDING"
echo "O-DRV7: cleared escalation for $TASK (RCA+bank+retest recorded)"
