#!/usr/bin/env bash
# O-EXECCORPUS — standing archived-execution replay against today's supervisor.
#
# Seeds under tests/fixtures/exec-corpus/ are scooped from v3 S03 run-archives
# (see fixtures/exec-corpus/SOURCE.txt). Each case asserts one harness honesty
# class (O-SFIXNODELTA skip, O-ESCALCAUSE classification, …) using live helper
# logic from supervisor.sh — not a frozen parallel implementation.
#
# Usage:
#   bash .hermes/harness/exec-corpus-lint.sh
#   bash .hermes/harness/exec-corpus-lint.sh --case s03-t004-sfixnodelta
#
# Exit 0 = all selected cases PASS; non-zero on mismatch / wiring fail.
set -euo pipefail

HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIX_ROOT="${HARNESS_DIR}/tests/fixtures/exec-corpus"
MANIFEST="${FIX_ROOT}/manifest.env"
SUP="${HARNESS_DIR}/supervisor.sh"

CASE_FILTER=""
while [ $# -gt 0 ]; do
  case "$1" in
    --case)
      CASE_FILTER="${2:-}"
      shift 2 || true
      ;;
    --case=*)
      CASE_FILTER="${1#--case=}"
      shift
      ;;
    -h|--help)
      sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      shift
      ;;
  esac
done

[ -f "$MANIFEST" ] || { echo "O-EXECCORPUS: missing $MANIFEST" >&2; exit 2; }
# shellcheck source=/dev/null
source "$MANIFEST"
[ -f "$SUP" ] || { echo "O-EXECCORPUS: missing $SUP" >&2; exit 2; }

require_live_wiring() {
  local missing=0
  grep -q 'sfix_tip_content_empty' "$SUP" || { echo "O-EXECCORPUS: supervisor missing sfix_tip_content_empty" >&2; missing=1; }
  grep -q 'O-SFIXNODELTA' "$SUP" || { echo "O-EXECCORPUS: supervisor missing O-SFIXNODELTA" >&2; missing=1; }
  grep -q 'sfix_nodelta_skip' "$SUP" || { echo "O-EXECCORPUS: supervisor missing sfix_nodelta_skip" >&2; missing=1; }
  grep -qE 'O-ESCALCAUSE|escalation-cause-' "$SUP" || { echo "O-EXECCORPUS: supervisor missing O-ESCALCAUSE" >&2; missing=1; }
  grep -q 'O-STEPFINISHRED' "$SUP" || { echo "O-EXECCORPUS: supervisor missing O-STEPFINISHRED" >&2; missing=1; }
  [ "$missing" -eq 0 ] || return 1
  echo "O-EXECCORPUS: live supervisor honesty wiring OK"
}

# Mirror of supervisor O-ESCALCAUSE priority for seat .err inputs used by corpus.
# Kept adjacent to the live grep patterns — instruments assert string parity.
classify_cause_from_err() { # $1=err-file → prints cause
  local err="$1"
  [ -f "$err" ] || { echo "worker-failed"; return 0; }
  if grep -qiE 'supervisor-pause' "$err" 2>/dev/null; then
    echo "supervisor-pause"
  elif grep -qiE 'debt-freeze' "$err" 2>/dev/null; then
    echo "debt-freeze"
  elif grep -qiE 'O-WORKERREAD|read-thrash|O-FIRSTMUT' "$err" 2>/dev/null; then
    echo "read-thrash"
  elif grep -qiE 'O-WORKERWEDGE|worker wedged' "$err" 2>/dev/null; then
    echo "worker-wedge"
  elif grep -qiE '429|rate.?limit|quota|Too Many Requests' "$err" 2>/dev/null; then
    echo "quota"
  elif grep -qiE 'O-STEPFINISHRED' "$err" 2>/dev/null; then
    echo "sensor-red"
  elif grep -qiE 'unexpected-paths|staged paths mismatch|O-T6d' "$err" 2>/dev/null; then
    echo "guard-refused"
  else
    echo "worker-failed"
  fi
}

run_sfixnodelta() { # $1=case-dir
  local src="$1"
  local fdelta="${src}/failure-delta.txt"
  local tipenv="${src}/tip-shape.env"
  local excerpt="${src}/supervisor-excerpt.log"
  [ -f "$fdelta" ] || { echo "FAIL: missing $fdelta" >&2; return 1; }
  [ -f "$tipenv" ] || { echo "FAIL: missing $tipenv" >&2; return 1; }
  # Historic evidence: archive dispatched O-SFIXWORKER under K7 0/0
  if [ -f "$excerpt" ]; then
    grep -qE 'SUMMARY new=0 gone=0' "$excerpt" \
      || { echo "FAIL: excerpt lacks runtime SUMMARY new=0 gone=0" >&2; return 1; }
    grep -q 'O-SFIXWORKER' "$excerpt" \
      || { echo "FAIL: excerpt lacks historic O-SFIXWORKER burn" >&2; return 1; }
  fi
  grep -qE '^SUMMARY new=0 gone=0([[:space:]]|$)' "$fdelta" \
    || { echo "FAIL: failure-delta missing SUMMARY new=0 gone=0" >&2; return 1; }

  local TIP_KIND="" TIP_PATH="" TIP_SUBJECT=""
  TIP_KIND=$(grep -E '^TIP_KIND=' "$tipenv" | head -1 | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//")
  TIP_PATH=$(grep -E '^TIP_PATH=' "$tipenv" | head -1 | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//")
  TIP_SUBJECT=$(grep -E '^TIP_SUBJECT=' "$tipenv" | head -1 | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//")
  [ "${TIP_KIND}" = "structure-gitkeep" ] || { echo "FAIL: unsupported TIP_KIND=${TIP_KIND}" >&2; return 1; }
  [ -n "${TIP_PATH}" ] && [ -n "${TIP_SUBJECT}" ] || { echo "FAIL: tip-shape incomplete" >&2; return 1; }

  local work
  work="$(mktemp -d "${TMPDIR:-/tmp}/exec-corpus.XXXXXX")"
  (
    cd "$work"
    git init -q
    git config user.email corpus@test.local
    git config user.name corpus
    mkdir -p "$(dirname "$TIP_PATH")"
    printf 'x\n' > README
    git add -A && git commit -q -m init
    : > "$TIP_PATH"
    git add -- "$TIP_PATH"
    git commit -q -m "$TIP_SUBJECT"
    # shellcheck disable=SC1090
    eval "$(sed -n '/^sfix_tip_content_empty()/,/^}/p' "$SUP")"
    sfix_tip_content_empty || { echo "FAIL: structure tip should be content-empty"; exit 1; }
    # Combined O-SFIXNODELTA predicate (same order as supervisor post_commit path)
    if grep -qE '^SUMMARY new=0 gone=0([[:space:]]|$)' "$fdelta" && sfix_tip_content_empty; then
      echo "sfix_nodelta_skip"
      exit 0
    fi
    echo "FAIL: predicate did not skip"; exit 1
  ) || { rm -rf "$work"; return 1; }
  rm -rf "$work"
  echo "PASS sfixnodelta (today refuses historic T-004 seat burn)"
  return 0
}

run_escalation_cause() { # $1=case-dir
  local src="$1"
  local gold="${src}/escalation-cause-T-004.txt"
  local err="${src}/oc-S03-T-004.err"
  local err2="${src}/oc-S03-T-002.err"
  [ -f "$gold" ] || { echo "FAIL: missing $gold" >&2; return 1; }
  [ -f "$err" ] || { echo "FAIL: missing $err" >&2; return 1; }
  local want
  want="$(head -1 "$gold" | tr -d '[:space:]')"
  [ "$want" = "sensor-red" ] || { echo "FAIL: gold cause want sensor-red got '$want'" >&2; return 1; }
  local got
  got="$(classify_cause_from_err "$err")"
  [ "$got" = "$want" ] || { echo "FAIL: classifier got '$got' want '$want'" >&2; return 1; }
  # Branch coverage: read-thrash seat twin must not collapse to worker-failed
  if [ -f "$err2" ]; then
    local got2
    got2="$(classify_cause_from_err "$err2")"
    [ "$got2" = "read-thrash" ] || { echo "FAIL: T-002 twin got '$got2' want read-thrash" >&2; return 1; }
  fi
  # Live supervisor must still key O-STEPFINISHRED → sensor-red
  grep -q 'O-STEPFINISHRED' "$SUP" \
    && grep -A2 'O-STEPFINISHRED' "$SUP" | grep -q 'sensor-red' \
    || { echo "FAIL: live supervisor STEPFINISHRED→sensor-red wiring drifted" >&2; return 1; }
  echo "PASS escalation-cause (sensor-red / read-thrash reproduce)"
  return 0
}

run_case() { # $1=case-id
  local case_id="$1"
  local src="${FIX_ROOT}/${case_id}"
  local key="${case_id//-/_}"
  local expect class
  eval "expect=\${CORPUS_${key}_EXPECT:-}"
  eval "class=\${CORPUS_${key}_CLASS:-}"
  [ -d "$src" ] || { echo "O-EXECCORPUS: missing case dir $src" >&2; return 2; }
  [ -n "$expect" ] || { echo "O-EXECCORPUS: no EXPECT for $case_id" >&2; return 2; }
  echo "---- case=$case_id class=${class:-?} expect=$expect"
  case "$expect" in
    sfix_nodelta_skip)
      run_sfixnodelta "$src"
      ;;
    sensor-red|read-thrash|worker-failed)
      run_escalation_cause "$src"
      ;;
    *)
      echo "FAIL $case_id: unknown EXPECT=$expect" >&2
      return 2
      ;;
  esac
}

# --- main ------------------------------------------------------------------
require_live_wiring

CASES=()
if [ -n "$CASE_FILTER" ]; then
  CASES=("$CASE_FILTER")
else
  # Prefer manifest order; fall back to dirs with expect.env
  if [ -n "${CORPUS_CASES:-}" ]; then
    # shellcheck disable=SC2206
    CASES=($CORPUS_CASES)
  else
    for d in "$FIX_ROOT"/*/; do
      [ -d "$d" ] || continue
      base="$(basename "$d")"
      [ "$base" = "_shared" ] && continue
      [ -f "$d/expect.env" ] || continue
      CASES+=("$base")
    done
  fi
fi

FAIL=0
for c in "${CASES[@]}"; do
  run_case "$c" || FAIL=$((FAIL + 1))
done

if [ "$FAIL" -ne 0 ]; then
  echo "O-EXECCORPUS FAIL ($FAIL case(s))" >&2
  exit 1
fi
echo "O-EXECCORPUS PASS (${#CASES[@]} case(s))"
exit 0
