#!/usr/bin/env bash
# O-PLANCORPUS — standing archived-plan re-lint with live M3 gate flag parity.
#
# Re-lints committed fixtures under tests/fixtures/plan-corpus/ using the
# SAME flag set as outer-loop / supervisor M3:
#   --findings-scope --profile --story-deploy --story-scope
#
# Without --story-scope the same corpus produces ~17–19 incident-unowned
# LINTs on every version (including accepted plans) — a false confirmation.
# This script refuses to run if live harness sources omit any of those flags.
#
# Usage:
#   bash .hermes/harness/plan-corpus-lint.sh
#   bash .hermes/harness/plan-corpus-lint.sh --case s03-6348afe-class
#   bash .hermes/harness/plan-corpus-lint.sh --parity-demo   # prove scope omission noise
#
# Exit 0 = all selected cases match expect; non-zero on mismatch / wiring fail.
set -euo pipefail

HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LINT="${HARNESS_DIR}/plan-lint.py"
FIX_ROOT="${HARNESS_DIR}/tests/fixtures/plan-corpus"
MANIFEST="${FIX_ROOT}/manifest.env"
OUTER="${HARNESS_DIR}/outer-loop.sh"
SUP="${HARNESS_DIR}/supervisor.sh"

CASE_FILTER=""
PARITY_DEMO=0
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
    --parity-demo)
      PARITY_DEMO=1
      shift
      ;;
    -h|--help)
      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      shift
      ;;
  esac
done

[ -f "$MANIFEST" ] || { echo "O-PLANCORPUS: missing $MANIFEST" >&2; exit 2; }
# shellcheck source=/dev/null
source "$MANIFEST"

# --- Flag parity: live sources must declare the same flag names -------------
# Core (not bandage): corpus reads flag *names* from the live M3 gate source
# rather than inventing a parallel soft invocation.
require_live_flags() {
  # Outer-loop M3_LINT_CMD is the authoritative live gate (all four flags).
  # Supervisor re-lint must share findings-scope / story-deploy / story-scope
  # (profile is outer-only today; corpus still passes --profile for parity
  # with M3_LINT_CMD).
  local missing=0 f
  for f in --findings-scope --profile --story-deploy --story-scope; do
    if ! grep -q -- "$f" "$OUTER"; then
      echo "O-PLANCORPUS: outer-loop.sh missing live flag $f" >&2
      missing=1
    fi
  done
  for f in --findings-scope --story-deploy; do
    if ! grep -q -- "$f" "$SUP"; then
      echo "O-PLANCORPUS: supervisor.sh missing live flag $f" >&2
      missing=1
    fi
  done
  if ! grep -Eq -- 'story-scope|STORY_SCOPE_ARGS' "$SUP"; then
    echo "O-PLANCORPUS: supervisor.sh missing story-scope / STORY_SCOPE_ARGS" >&2
    missing=1
  fi
  [ "$missing" -eq 0 ] || return 1
  echo "O-PLANCORPUS: live-gate flag parity OK (${CORPUS_LIVE_FLAGS})"
}

# O-M3CASEINPUTS — resolve findings/profile for a case.
# Prefer: (1) case-local migration/{mta-findings.json,architecture-profile.md}
#         (2) migration/m3-inputs.env pointers (FINDINGS_SRC / PROFILE_SRC)
#         (3) _shared stand-in defaults
# Paths in m3-inputs.env are relative to the case dir (or absolute).
resolve_case_inputs() { # $1=case-src-dir → sets RESOLVED_FINDINGS / RESOLVED_PROFILE / RESOLVED_INPUT_MODE
  local src="$1"
  local mig="${src}/migration"
  local envf="${mig}/m3-inputs.env"
  RESOLVED_FINDINGS=""
  RESOLVED_PROFILE=""
  RESOLVED_INPUT_MODE=""

  if [ -f "${mig}/mta-findings.json" ] && [ -f "${mig}/architecture-profile.md" ]; then
    RESOLVED_FINDINGS="${mig}/mta-findings.json"
    RESOLVED_PROFILE="${mig}/architecture-profile.md"
    RESOLVED_INPUT_MODE="case-local"
    return 0
  fi

  if [ -f "$envf" ]; then
    local FINDINGS_SRC="" PROFILE_SRC=""
    # shellcheck source=/dev/null
    source "$envf"
    if [ -n "${FINDINGS_SRC:-}" ] && [ -n "${PROFILE_SRC:-}" ]; then
      case "$FINDINGS_SRC" in
        /*) RESOLVED_FINDINGS="$FINDINGS_SRC" ;;
        *) RESOLVED_FINDINGS="${src}/${FINDINGS_SRC}" ;;
      esac
      case "$PROFILE_SRC" in
        /*) RESOLVED_PROFILE="$PROFILE_SRC" ;;
        *) RESOLVED_PROFILE="${src}/${PROFILE_SRC}" ;;
      esac
      if [ -f "$RESOLVED_FINDINGS" ] && [ -f "$RESOLVED_PROFILE" ]; then
        RESOLVED_INPUT_MODE="pointer:${FINDINGS_SRC}"
        return 0
      fi
      echo "O-M3CASEINPUTS: $envf points to missing inputs:" >&2
      echo "  FINDINGS_SRC=$FINDINGS_SRC → $RESOLVED_FINDINGS" >&2
      echo "  PROFILE_SRC=$PROFILE_SRC → $RESOLVED_PROFILE" >&2
      return 2
    fi
  fi

  RESOLVED_FINDINGS="${FIX_ROOT}/_shared/mta-findings.json"
  RESOLVED_PROFILE="${FIX_ROOT}/_shared/architecture-profile.md"
  RESOLVED_INPUT_MODE="shared-default"
  [ -f "$RESOLVED_FINDINGS" ] && [ -f "$RESOLVED_PROFILE" ] || {
    echo "O-M3CASEINPUTS: missing _shared stand-in inputs" >&2
    return 2
  }
}

stage_case() { # $1=case-id → prints workdir
  local case_id="$1"
  local src="${FIX_ROOT}/${case_id}"
  local work
  work="$(mktemp -d "${TMPDIR:-/tmp}/plan-corpus.XXXXXX")"
  [ -d "$src" ] || { echo "O-PLANCORPUS: missing case dir $src" >&2; return 2; }
  cp -a "$src/." "$work/"
  mkdir -p "$work/migration"
  resolve_case_inputs "$src" || { rm -rf "$work"; return 2; }
  cp -f "$RESOLVED_FINDINGS" "$work/migration/mta-findings.json"
  cp -f "$RESOLVED_PROFILE" "$work/migration/architecture-profile.md"
  echo "O-M3CASEINPUTS: case=$case_id mode=$RESOLVED_INPUT_MODE" >&2
  # Ensure Shape hard like live M3 (instruments suite may export WARN globally)
  export PLAN_LINT_REQUIRE_SHAPE="${PLAN_LINT_REQUIRE_SHAPE:-1}"
  unset PLAN_LINT_SHAPE_WARN || true
  echo "$work"
}

lint_count() { # stdin → count of LINT: lines
  grep -c '^LINT:' || true
}

class_hits() { # $1=out $2=class → count
  grep -c "LINT:$2" <<<"$1" || true
}

run_case() { # $1=case-id
  local case_id="$1"
  local key="${case_id//-/_}"
  local expect findings deploy scope expect_classes min_sj
  eval "expect=\${CORPUS_${key}_EXPECT:-}"
  eval "findings=\${CORPUS_${key}_FINDINGS:-}"
  eval "deploy=\${CORPUS_${key}_DEPLOY:-false}"
  eval "scope=\${CORPUS_${key}_SCOPE:-}"
  eval "expect_classes=\${CORPUS_${key}_EXPECT_CLASSES:-}"
  eval "min_sj=\${CORPUS_${key}_MIN_STRUCTJAVA:-0}"

  [ -n "$expect" ] || { echo "O-PLANCORPUS: no EXPECT for $case_id" >&2; return 2; }
  [ -n "$findings" ] || { echo "O-PLANCORPUS: no FINDINGS for $case_id" >&2; return 2; }
  [ -n "$scope" ] || { echo "O-PLANCORPUS: no SCOPE for $case_id (required — see README)" >&2; return 2; }

  local work out rc=0
  work="$(stage_case "$case_id")"
  (
    cd "$work"
    # Exact live-gate flag set (O-PLANCORPUS / Wave4 §1.2)
    PLAN_LINT_REQUIRE_SHAPE=1 PLAN_LINT_SHAPE_WARN=0 \
      python3 "$LINT" tasks.md migration/mta-findings.json \
        --findings-scope "$findings" \
        --profile migration/architecture-profile.md \
        --story-deploy "$deploy" \
        --story-scope "$scope" \
        > /tmp/plan-corpus-out.$$ 2>&1
  ) && rc=0 || rc=$?
  out="$(cat /tmp/plan-corpus-out.$$ 2>/dev/null || true)"
  rm -f /tmp/plan-corpus-out.$$
  local nlint
  nlint="$(printf '%s\n' "$out" | lint_count)"

  echo "---- case=$case_id expect=$expect rc=$rc lint_lines=$nlint"
  printf '%s\n' "$out" | sed 's/^/  /' | head -40

  if [ "$expect" = "red" ]; then
    [ "$rc" -ne 0 ] || { echo "FAIL $case_id: expected RED (rc≠0), got PLAN OK" >&2; rm -rf "$work"; return 1; }
    local cls missing=0
    for cls in $expect_classes; do
      local hits
      hits="$(class_hits "$out" "$cls")"
      if [ "${hits:-0}" -lt 1 ]; then
        echo "FAIL $case_id: missing LINT:$cls" >&2
        missing=1
      else
        echo "  hit $cls ×$hits"
      fi
    done
    if [ "${min_sj:-0}" -gt 0 ]; then
      local sj
      sj="$(class_hits "$out" "O-STRUCTJAVA")"
      if [ "${sj:-0}" -lt "$min_sj" ]; then
        echo "FAIL $case_id: O-STRUCTJAVA count=$sj want≥$min_sj" >&2
        missing=1
      fi
    fi
    rm -rf "$work"
    [ "$missing" -eq 0 ] || return 1
    echo "PASS $case_id (known-RED class signals present)"
    return 0
  fi

  if [ "$expect" = "green" ]; then
    if [ "$rc" -ne 0 ]; then
      echo "FAIL $case_id: expected PLAN OK, got rc=$rc" >&2
      rm -rf "$work"
      return 1
    fi
    if ! grep -q 'PLAN OK' <<<"$out"; then
      echo "FAIL $case_id: expected PLAN OK text" >&2
      rm -rf "$work"
      return 1
    fi
    rm -rf "$work"
    echo "PASS $case_id (PLAN OK)"
    return 0
  fi

  echo "FAIL $case_id: unknown EXPECT=$expect" >&2
  rm -rf "$work"
  return 2
}

parity_demo() {
  # Prove §1.2: omitting --story-scope floods incident-unowned on the RED case.
  local case_id="s03-6348afe-class"
  local key="${case_id//-/_}" findings deploy scope
  eval "findings=\${CORPUS_${key}_FINDINGS}"
  eval "deploy=\${CORPUS_${key}_DEPLOY}"
  eval "scope=\${CORPUS_${key}_SCOPE}"
  local work out_with out_without n_with n_without
  work="$(stage_case "$case_id")"
  (
    cd "$work"
    PLAN_LINT_REQUIRE_SHAPE=1 PLAN_LINT_SHAPE_WARN=0 \
      python3 "$LINT" tasks.md migration/mta-findings.json \
        --findings-scope "$findings" \
        --profile migration/architecture-profile.md \
        --story-deploy "$deploy" \
        --story-scope "$scope" > /tmp/pc-with.$$ 2>&1 || true
    PLAN_LINT_REQUIRE_SHAPE=1 PLAN_LINT_SHAPE_WARN=0 \
      python3 "$LINT" tasks.md migration/mta-findings.json \
        --findings-scope "$findings" \
        --profile migration/architecture-profile.md \
        --story-deploy "$deploy" > /tmp/pc-without.$$ 2>&1 || true
  )
  out_with="$(cat /tmp/pc-with.$$)"
  out_without="$(cat /tmp/pc-without.$$)"
  rm -f /tmp/pc-with.$$ /tmp/pc-without.$$
  n_with="$(printf '%s\n' "$out_with" | lint_count)"
  n_without="$(printf '%s\n' "$out_without" | lint_count)"
  rm -rf "$work"
  echo "O-PLANCORPUS parity-demo: with --story-scope LINT=$n_with; without LINT=$n_without"
  if [ "$n_without" -le "$n_with" ]; then
    echo "FAIL parity-demo: expected without-scope LINT count > with-scope ($n_without ≤ $n_with)" >&2
    return 1
  fi
  if [ "$n_without" -lt 10 ]; then
    echo "FAIL parity-demo: expected large without-scope flood (≥10), got $n_without" >&2
    return 1
  fi
  echo "PASS parity-demo (omitting --story-scope inflates LINT — false confirmation class)"
}

# --- main ------------------------------------------------------------------
require_live_flags

CASES=()
if [ -n "$CASE_FILTER" ]; then
  CASES=("$CASE_FILTER")
else
  for d in "$FIX_ROOT"/*/; do
    [ -d "$d" ] || continue
    base="$(basename "$d")"
    [ "$base" = "_shared" ] && continue
    [ -f "$d/tasks.md" ] || continue
    CASES+=("$base")
  done
fi

FAIL=0
for c in "${CASES[@]}"; do
  run_case "$c" || FAIL=$((FAIL + 1))
done

if [ "$PARITY_DEMO" = "1" ] || [ -z "$CASE_FILTER" ]; then
  parity_demo || FAIL=$((FAIL + 1))
fi

if [ "$FAIL" -ne 0 ]; then
  echo "O-PLANCORPUS FAIL ($FAIL case(s))" >&2
  exit 1
fi
echo "O-PLANCORPUS PASS (${#CASES[@]} case(s))"
exit 0
