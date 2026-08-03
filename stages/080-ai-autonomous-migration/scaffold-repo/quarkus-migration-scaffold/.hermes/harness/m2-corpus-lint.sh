#!/usr/bin/env bash
# O-M2CORPUS — standing archived-roadmap re-lint with live roadmap-lint.
#
# Re-lints committed fixtures under tests/fixtures/m2-corpus/ using the
# SAME argv set as outer-loop M2:
#   roadmap-lint.py <roadmap> <findings-inventory> <legacy-dir> <architecture-profile>
#
# Known-RED cases must stay RED with the expected LINT classes. This turns
# a live M2 lint×2 FAIL into a permanent regression corpus (ADR-6 / pair
# O-PLANCORPUS).
#
# Usage:
#   bash .hermes/harness/m2-corpus-lint.sh
#   bash .hermes/harness/m2-corpus-lint.sh --case v4-m2-lintx2-10790d6
#
# Exit 0 = all selected cases match expect; non-zero on mismatch / wiring fail.
set -euo pipefail

HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LINT="${HARNESS_DIR}/roadmap-lint.py"
FIX_ROOT="${HARNESS_DIR}/tests/fixtures/m2-corpus"
MANIFEST="${FIX_ROOT}/manifest.env"
OUTER="${HARNESS_DIR}/outer-loop.sh"

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
      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      shift
      ;;
  esac
done

[ -f "$MANIFEST" ] || { echo "O-M2CORPUS: missing $MANIFEST" >&2; exit 2; }
# shellcheck source=/dev/null
source "$MANIFEST"

# Live wire: outer-loop must still invoke roadmap-lint with inventory+legacy+profile
if ! grep -q 'roadmap-lint.py' "$OUTER"; then
  echo "O-M2CORPUS: outer-loop.sh missing roadmap-lint.py invocation" >&2
  exit 2
fi
if ! grep -qE 'findings-inventory\.md.*/projects/legacy|architecture-profile\.md' "$OUTER"; then
  echo "O-M2CORPUS: outer-loop M2 lint argv parity missing (inventory/legacy/profile)" >&2
  exit 2
fi

PASS=0
FAIL=0
run_case() {
  local id="$1"
  local dir="${FIX_ROOT}/${id}"
  local expect_var="M2CORPUS_${id//-/_}_EXPECT"
  local classes_var="M2CORPUS_${id//-/_}_EXPECT_CLASSES"
  local expect="${!expect_var:-}"
  local classes="${!classes_var:-}"
  if [ -z "$expect" ]; then
    echo "FAIL $id — missing ${expect_var} in manifest.env" >&2
    FAIL=$((FAIL + 1))
    return
  fi
  if [ ! -f "${dir}/migration/roadmap.md" ]; then
    echo "FAIL $id — missing migration/roadmap.md" >&2
    FAIL=$((FAIL + 1))
    return
  fi
  if [ ! -f "${dir}/migration/findings-inventory.md" ] \
    || [ ! -f "${dir}/migration/architecture-profile.md" ]; then
    echo "FAIL $id — missing M1 inputs (findings-inventory / architecture-profile)" >&2
    FAIL=$((FAIL + 1))
    return
  fi
  local legacy="${dir}/legacy"
  [ -d "$legacy" ] || legacy="/tmp/m2-corpus-empty-legacy-$$"
  mkdir -p "$legacy"

  local out rc=0
  out="$(
    python3 "$LINT" \
      "${dir}/migration/roadmap.md" \
      "${dir}/migration/findings-inventory.md" \
      "$legacy" \
      "${dir}/migration/architecture-profile.md" 2>&1
  )" || rc=$?

  local got=green
  [ "$rc" -eq 0 ] || got=red

  if [ "$got" != "$expect" ]; then
    echo "FAIL $id — expect=$expect got=$got rc=$rc" >&2
    echo "$out" | head -20 >&2
    FAIL=$((FAIL + 1))
    return
  fi

  if [ "$expect" = "red" ] && [ -n "$classes" ]; then
    local missing="" c
    for c in $classes; do
      if ! echo "$out" | grep -qE "LINT:${c}:|LINT:${c} "; then
        # classes may be bare tokens inside LINT:<class>:
        if ! echo "$out" | grep -q "LINT:${c}"; then
          missing="${missing} ${c}"
        fi
      fi
    done
    if [ -n "$missing" ]; then
      echo "FAIL $id — known-RED missing expected classes:${missing}" >&2
      echo "$out" | head -20 >&2
      FAIL=$((FAIL + 1))
      return
    fi
  fi

  echo "PASS $id expect=$expect"
  PASS=$((PASS + 1))
}

cases=()
if [ -n "$CASE_FILTER" ]; then
  cases=("$CASE_FILTER")
else
  while IFS= read -r d; do
    [ -d "$d" ] || continue
    base="$(basename "$d")"
    [[ "$base" == _* ]] && continue
    cases+=("$base")
  done < <(find "$FIX_ROOT" -mindepth 1 -maxdepth 1 -type d | sort)
fi

[ "${#cases[@]}" -gt 0 ] || { echo "O-M2CORPUS: no cases under $FIX_ROOT" >&2; exit 2; }

for id in "${cases[@]}"; do
  run_case "$id"
done

echo "O-M2CORPUS PASS (${PASS} case(s))"
[ "$FAIL" -eq 0 ] || { echo "O-M2CORPUS FAIL count=$FAIL" >&2; exit 1; }
exit 0
