#!/usr/bin/env bash
# R2 / B3 — Last Restart Readiness (LRR). Prints GO/NO-GO with evidence.
# Does NOT start outer-loop. Asserts SC-0..SC-4 checkable facts from
# tmp/KAI-WAVE4-REVIEW.md V4 START CONDITIONS.
#
# Usage:
#   bash scripts/track-b/restart-readiness.sh
#   V10_WS_NAME=petclinic-rest-v4 bash scripts/track-b/restart-readiness.sh
#
# Env:
#   V10_WS_NAME — target DevWorkspace (required when multiple Running)
#   M3_ALL — expected start env (LRR requires =1)
#   M3_ALL_OPERATOR_AUTO — must be unset/empty/0 for GO (bypass is exception-only)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"

PRED_DOC="${ROOT}/docs/M3-ALL-PREDICTIONS-FROZEN.md"
CHANGE_MANIFEST="${ROOT}/docs/V10-CHANGE-MANIFEST.md"
SCAFFOLD="${ROOT}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"
FAILS=0
PASSES=0

_pass() { PASSES=$((PASSES + 1)); printf 'PASS  %s\n' "$1"; }
_fail() { FAILS=$((FAILS + 1)); printf 'FAIL  %s\n' "$1" >&2; }
_info() { printf 'INFO  %s\n' "$1"; }

echo "=== restart-readiness (R2 LRR) ==="
echo "ROOT=$ROOT"
echo "time=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# --- SC-0 supply chain ---
if [ -f "$PRED_DOC" ] && git -C "$ROOT" ls-files --error-unmatch "$PRED_DOC" >/dev/null 2>&1; then
  pred_hash="$(
    if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$PRED_DOC" | awk '{print $1}'
    else sha256sum "$PRED_DOC" | awk '{print $1}'; fi
  )"
  _pass "SC-0/SC-2a predictions committed: $PRED_DOC sha256=${pred_hash:0:12}…"
else
  _fail "SC-0/SC-2a predictions file missing or untracked: $PRED_DOC"
fi

# R3 / SC-1 — change manifest (UNDER-TEST / NOT-UNDER-TEST); silence forbidden
if [ -f "$CHANGE_MANIFEST" ] \
  && git -C "$ROOT" ls-files --error-unmatch "$CHANGE_MANIFEST" >/dev/null 2>&1; then
  if grep -qE '^## UNDER-TEST' "$CHANGE_MANIFEST" \
    && grep -qE '^## NOT-UNDER-TEST' "$CHANGE_MANIFEST" \
    && grep -qE 'R4|O-SFIX' "$CHANGE_MANIFEST" \
    && grep -qE 'O-LOGPROG|R6' "$CHANGE_MANIFEST" \
    && grep -qE 'A-1|R8' "$CHANGE_MANIFEST"; then
    man_hash="$(
      if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$CHANGE_MANIFEST" | awk '{print $1}'
      else sha256sum "$CHANGE_MANIFEST" | awk '{print $1}'; fi
    )"
    _pass "R3/SC-1 change manifest committed: $CHANGE_MANIFEST sha256=${man_hash:0:12}…"
  else
    _fail "R3/SC-1 $CHANGE_MANIFEST missing UNDER-TEST / NOT-UNDER-TEST or R4/R6/R8 deferrals"
  fi
else
  _fail "R3/SC-1 change manifest missing or untracked: $CHANGE_MANIFEST"
fi

if [ -d "${SCAFFOLD}/.hermes" ] \
  && [ -f "${SCAFFOLD}/.hermes/harness/oracle_derive.py" ] \
  && [ -f "${SCAFFOLD}/.hermes/harness/m3-all-lint.sh" ]; then
  _pass "SC-0 golden scaffold has oracle_derive.py + m3-all-lint.sh"
else
  _fail "SC-0 golden scaffold missing key M3-ALL modules"
fi

# Architect addition (W4-141): LRR asserts m2-compose exists and is wired
# before the M2 seat (O-M2COMPOSE) — readiness grows with each boundary lesson.
if [ -f "${SCAFFOLD}/.hermes/harness/m2-compose.py" ] \
  && grep -q 'm2_compose_bookkeeping\|O-M2COMPOSE' \
       "${SCAFFOLD}/.hermes/harness/outer-loop.sh" 2>/dev/null; then
  _pass "SC-0 O-M2COMPOSE m2-compose.py present + outer-loop wired"
else
  _fail "SC-0 O-M2COMPOSE missing m2-compose.py or outer-loop wire"
fi

# O-MONSTART — preflight --start must start host dual-monitor (checklist)
if grep -q 'O-MONSTART' "${ROOT}/scripts/track-b/v9-preflight-outer-start.sh" \
  && grep -qE 'v10-v3-dual-monitor-start\.sh|dual-monitor-start' \
       "${ROOT}/scripts/track-b/v9-preflight-outer-start.sh"; then
  _pass "SC-3 O-MONSTART preflight --start wires dual-monitor"
else
  _fail "SC-3 O-MONSTART missing from v9-preflight-outer-start.sh --start path"
fi

# Dirty .hermes under scaffold = improvement wave not banked in git.
# O-HERMESPARITYSEM: ignore .published-fp alone (stamp STAMPED_AT churn).
hermes_dirty="$(
  git -C "$ROOT" status --porcelain -- \
    'stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes' \
    | { grep -vE '\.published-fp$' || true; } \
    | wc -l | tr -d ' '
)"
if [ "${hermes_dirty:-0}" -eq 0 ]; then
  _pass "SC-0 golden .hermes clean in git (0 dirty paths; stamp-only ignored)"
else
  _fail "SC-0 golden .hermes still dirty (${hermes_dirty} paths) — commit/push before GO"
fi

# Parity + golden-fresh (live cluster)
if [ "${V9_SKIP_HERMES_PARITY:-0}" = "1" ] || [ "${V9_SKIP_GOLDEN_FRESH:-0}" = "1" ]; then
  _fail "SC-0 V9_SKIP_HERMES_PARITY/GOLDEN_FRESH set — refuse skip-hatch GO"
else
  if bash "${ROOT}/scripts/track-b/v10-hermes-parity.sh" >/tmp/lrr-parity.out 2>&1; then
    _pass "SC-0/R1 hermes parity GREEN ($(grep -E 'DIGEST=' /tmp/lrr-parity.out | head -1))"
  else
    _fail "SC-0/R1 hermes parity RED (see /tmp/lrr-parity.out)"
    tail -8 /tmp/lrr-parity.out >&2 || true
  fi
  if bash "${ROOT}/scripts/track-b/v10-golden-fresh.sh" >/tmp/lrr-golden.out 2>&1; then
    _pass "SC-0 golden-fresh three-way GREEN"
  else
    _fail "SC-0 golden-fresh RED (see /tmp/lrr-golden.out)"
    tail -8 /tmp/lrr-golden.out >&2 || true
  fi
fi

# --- SC-2/SC-3 M3_ALL start env ---
if [ "${M3_ALL:-}" = "1" ]; then
  _pass "SC-3 M3_ALL=1 in LRR environment"
else
  _fail "SC-3 M3_ALL must be 1 in start env (got '${M3_ALL:-<unset>}')"
fi

case "${M3_ALL_OPERATOR_AUTO:-}" in
  ""|0|false|FALSE|no|NO)
    _pass "SC-3 M3_ALL_OPERATOR_AUTO unset/off (bypass not pinned)"
    ;;
  *)
    _fail "SC-3 M3_ALL_OPERATOR_AUTO='${M3_ALL_OPERATOR_AUTO}' — must be unset for v4 GO"
    ;;
esac

# Pin check: refuse real assignments only (not docs/comments mentioning the hatch).
pin_hits="$(
  git -C "$ROOT" grep -nE \
    '^[[:space:]]*(export[[:space:]]+)?M3_ALL_OPERATOR_AUTO=1([[:space:]]|$)' \
    -- 'env.example' 'scripts' 'stages/080-ai-autonomous-migration' 2>/dev/null \
    | grep -vE 'restart-readiness\.sh' || true
)"
if [ -n "${pin_hits}" ]; then
  _fail "SC-3 M3_ALL_OPERATOR_AUTO=1 pinned in tracked sources"
  printf '%s\n' "$pin_hits" | sed 's/^/        /' >&2
else
  _pass "SC-3 M3_ALL_OPERATOR_AUTO not pinned as an assignment in tracked sources"
fi

# --- Corpus / defaults gates (no outer start) ---
if bash "${ROOT}/scripts/track-b/v10-plan-corpus-gate.sh" >/tmp/lrr-plan-corpus.out 2>&1; then
  _pass "SC-2d plan-corpus gate GREEN"
else
  _fail "SC-2d plan-corpus gate RED (see /tmp/lrr-plan-corpus.out)"
fi

if bash "${ROOT}/scripts/track-b/v10-exec-corpus-gate.sh" >/tmp/lrr-exec-corpus.out 2>&1; then
  _pass "SC-2d exec-corpus gate GREEN"
else
  _fail "SC-2d exec-corpus gate RED (see /tmp/lrr-exec-corpus.out) — R4 follow-ons may still be open"
fi

if bash "${ROOT}/scripts/track-b/v10-m2-corpus-gate.sh" >/tmp/lrr-m2-corpus.out 2>&1; then
  _pass "SC-2d m2-corpus gate GREEN"
else
  _fail "SC-2d m2-corpus gate RED (see /tmp/lrr-m2-corpus.out)"
fi

# Seat budget + storykind wiring present
if [ -f "${SCAFFOLD}/.hermes/harness/seat-budget.py" ] \
  && grep -q 'O-SEATBUDGET\|seat-budget' "${SCAFFOLD}/.hermes/harness/roadmap-lint.py" 2>/dev/null; then
  _pass "SC-2c O-SEATBUDGET wired"
else
  _fail "SC-2c O-SEATBUDGET missing"
fi

# O-HERMESPARITYSEM present
if grep -q 'qg_hermes_list_semantic_files' "${ROOT}/scripts/track-b/v10-hermes-parity.sh" \
  && grep -q 'O-HERMESPARITYSEM' "${ROOT}/docs/V10-FUTURE-IMPROVEMENTS.md"; then
  _pass "SC-0 O-HERMESPARITYSEM semantic digest landed"
else
  _fail "SC-0 O-HERMESPARITYSEM missing"
fi

# Honesty bank (preflight subset) — informational if full bank still open
if bash "${ROOT}/scripts/track-b/v9-bank-gate.sh" honesty >/tmp/lrr-bank-honesty.out 2>&1; then
  _pass "honesty bank gate GREEN"
else
  _fail "honesty bank gate RED (see /tmp/lrr-bank-honesty.out)"
fi

echo "=== summary passes=${PASSES} fails=${FAILS} ==="
if [ "$FAILS" -eq 0 ]; then
  echo "LRR_VERDICT=GO"
  echo "Next: Grok certifies in WAVE4 → Opus verifies → operator triggers wave start."
  exit 0
fi
echo "LRR_VERDICT=NO-GO"
echo "Restart? NO until fails clear. Do not start outer-loop."
exit 1
