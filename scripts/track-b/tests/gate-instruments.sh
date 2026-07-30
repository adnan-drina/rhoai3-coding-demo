#!/usr/bin/env bash
# Fixture-driven cases for scripts/track-b quality gates (O-TBTEST).
# Run: bash scripts/track-b/tests/gate-instruments.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"
PASS=0
FAIL=0
ok() { PASS=$((PASS + 1)); echo "  OK  $*"; }
bad() { FAIL=$((FAIL + 1)); echo "  FAIL $*"; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "== O-HANDNOISE: strip_oc_noise + agents= match =="
NOISE=$'\]633;P;HasRichCommandDetection=True\007agents=UP/UP/UP/DOWN\nDIRTY_BEGIN\n M src/x.java\nDIRTY_END'
CLEAN=$(printf '%s' "$NOISE" | qg_strip_oc_noise)
if echo "$CLEAN" | grep -qE 'agents=(UP|DOWN)/'; then
  ok "agents= visible after strip"
else
  bad "agents= still masked: $(printf '%s' "$CLEAN" | head -c 80)"
fi
if echo "$CLEAN" | grep -q 'UP'; then
  ok "UP detectable for busy-skip"
else
  bad "UP not in cleaned snap"
fi

echo "== O-ADVTASK: story ADVANCE ignores task sections =="
GATE_DOC="$TMP/qg.md"
cat >"$GATE_DOC" <<'MD'
## 2026-07-30 — S03 T-004 detailed
- **Verdict:** ADVANCE

## 2026-07-30 — S03 story complete
- **Verdict:** ADVANCE
MD
# Temporarily point check at fixture
export GATE_DOC
if ! bash "${ROOT}/scripts/track-b/v9-advance-gate.sh" check S03 >/dev/null 2>&1; then
  bad "story-complete ADVANCE should GREEN"
else
  ok "story-complete ADVANCE greens"
fi
# task-only doc
cat >"$GATE_DOC" <<'MD'
## 2026-07-30 — S03 T-004 detailed
- **Verdict:** ADVANCE
MD
if bash "${ROOT}/scripts/track-b/v9-advance-gate.sh" check S03 >/dev/null 2>&1; then
  bad "task-only ADVANCE should RED"
else
  ok "task-only ADVANCE stays RED"
fi

echo "== O-DRV3EV: evidence paths must be cited =="
EVDIR="$TMP/evid"
mkdir -p "$EVDIR"
SHA=deadbeefdeadbeefdeadbeefdeadbeefdeadbeef
cat >"$EVDIR/${SHA}.stat" <<'ST'
src/main/java/com/demo/Foo.java | 10 ++++++
src/test/java/com/demo/FooTest.java | 20 ++++++++++++++++++++
ST
# hijack ROOT for evidence path — call python inline matching lib logic
BODY_OK="Reviewed src/main/java/com/demo/Foo.java and src/test/java/com/demo/FooTest.java"
BODY_BAD="Looks fine, big write-up with enough characters ........................"
# Use real helper with ROOT override via symlink layout
mkdir -p "$TMP/repo/tmp/V9-DIFF-EVIDENCE" "$TMP/repo/docs" "$TMP/repo/scripts/track-b"
cp "${ROOT}/scripts/track-b/lib-quality-gates.sh" "$TMP/repo/scripts/track-b/"
cp "$EVDIR/${SHA}.stat" "$TMP/repo/tmp/V9-DIFF-EVIDENCE/"
# shellcheck disable=SC1091
ROOT="$TMP/repo" source "$TMP/repo/scripts/track-b/lib-quality-gates.sh"
# qg_die uses exit — run validators in subshells
if ( qg_validate_diff_evidence "$SHA" "$BODY_OK" ) 2>/dev/null; then
  ok "cited paths pass"
else
  bad "cited paths should pass"
fi
if ( qg_validate_diff_evidence "$SHA" "$BODY_BAD" ) 2>/dev/null; then
  bad "uncited long body should FAIL"
else
  ok "uncited long body fails"
fi

echo "== O-FALSECOMPLETE: record-ship-only + waiter ready gate =="
REC="${ROOT}/scripts/track-b/v9-record-ship-only.sh"
WAIT="${ROOT}/scripts/track-b/v9-ship-only-waiter.sh"
GITR="$TMP/app"
mkdir -p "$GITR/migration"
(
  cd "$GITR"
  git init -q
  git config user.email t@t
  git config user.name t
  echo 'story,outcome,epoch' >migration/story-state.csv
  echo 'S04,complete,1' >>migration/story-state.csv
  git add migration/story-state.csv
  git commit -q -m init
  echo 'factory-failed deploy=3' >/tmp/v9-test-supervisor-done
  if SUPERVISOR_DONE=/tmp/v9-test-supervisor-done bash "$REC" S04 >/dev/null 2>&1; then
    bad "record should refuse factory-failed"
  else
    ok "record refuses non-success"
  fi
  echo 'success route=x.example http=200 products=4' >/tmp/v9-test-supervisor-done
  if SUPERVISOR_DONE=/tmp/v9-test-supervisor-done bash "$REC" S04 >/dev/null 2>&1; then
    SUBJ=$(git log -1 --format=%s)
    if printf '%s\n' "$SUBJ" | grep -Eq '^S04 story complete: success .+'; then
      ok "record writes harness story-complete subject"
    else
      bad "bad subject: $SUBJ"
    fi
  else
    bad "record should accept success*"
  fi
)
# waiter --check-ready: no completion → NOT_READY (isolate from host /tmp)
APP_ROOT="$GITR" REQUIRE_STORY=S05 \
  OUTER_LOOP_DONE="$TMP/no-done" OUTER_LOOP_LOG="$TMP/no-log" \
  bash "$WAIT" --check-ready >/dev/null 2>&1 \
  && bad "ready without S05 should fail" \
  || ok "ready refuses without S05 complete"
echo 'S05,complete,2' >>"$GITR/migration/story-state.csv"
APP_ROOT="$GITR" REQUIRE_STORY=S05 \
  OUTER_LOOP_DONE="$TMP/no-done" OUTER_LOOP_LOG="$TMP/no-log" \
  bash "$WAIT" --check-ready >/dev/null 2>&1 \
  && ok "ready when S05 complete in story-state" \
  || bad "ready should pass with S05,complete"

echo
echo "gate-instruments: ${PASS} passed, ${FAIL} failed"
[ "$FAIL" -eq 0 ]
