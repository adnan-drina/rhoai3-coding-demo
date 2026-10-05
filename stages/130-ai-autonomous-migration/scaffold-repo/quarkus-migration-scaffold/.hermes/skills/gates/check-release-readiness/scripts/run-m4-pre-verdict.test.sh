#!/usr/bin/env bash
# Admission: scripts/ names both asserts + the detector; runner fail-closes;
# missing worker log is not a skip-as-pass (Operator E-20260825T074910ZO).
# dest-5-shaped ran:false / Token body / Failures:1 refuse (Operator 164058ZO).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

grep -q 'assert-pinned-gates-ran' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'assert-retrievable-tree' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'assert-no-fence-evasion' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'assert-g4-claim-consistency' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'snapshot-m4-test-reports' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'assert-surefire-results' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'assert-m4-card-body' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'check-product-tests' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'check-test-toolchain' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'verify-admission-receipt' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'run_feed_gate' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
# ADR-015: the generated parity tests execute HERE and nowhere else, and the
# runner checks they are still the bytes the harness wrote.
grep -q 'generate-product-tests' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'run_feed_gate generate-product-tests' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -qF -- '-P${PARITY_PROFILE}' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'PARITY_PROFILE="m4-parity"' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
# The rebuild must precede the snapshot, or the snapshot the floors read
# carries the M3 reports and none of the generated cases.
build_line="$(grep -n '^run_parity_build$' "${SCRIPT_DIR}/run-m4-pre-verdict.sh" | head -1 | cut -d: -f1)"
snap_line="$(grep -n 'python3 "${SNAP}"' "${SCRIPT_DIR}/run-m4-pre-verdict.sh" | head -1 | cut -d: -f1)"
if [[ -z "${build_line}" || -z "${snap_line}" || "${build_line}" -ge "${snap_line}" ]]; then
  echo "FAIL: the m4-parity rebuild must run before the report snapshot (${build_line} vs ${snap_line})" >&2
  exit 1
fi
# A rebuild that ran is the freshest evidence: the snapshot must be taken from
# THOSE reports, not from an M3 snapshot that predates the generated cases.
grep -q 'PARITY_BUILT=1' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'SNAP_FRESH="--fresh"' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'python3 "${SNAP}" ${SNAP_FRESH}' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
fresh_line="$(grep -n 'SNAP_FRESH="--fresh"' "${SCRIPT_DIR}/run-m4-pre-verdict.sh" | head -1 | cut -d: -f1)"
if [[ -z "${fresh_line}" || "${fresh_line}" -ge "${snap_line}" ]]; then
  echo "FAIL: the freshness decision must be made before the snapshot runs (${fresh_line} vs ${snap_line})" >&2
  exit 1
fi
grep -q -- '--fresh' "${SCRIPT_DIR}/snapshot-m4-test-reports.py"

gen_line="$(grep -n 'run_feed_gate generate-product-tests' "${SCRIPT_DIR}/run-m4-pre-verdict.sh" | head -1 | cut -d: -f1)"
pin_line0="$(grep -n 'python3 "${PINNED}"' "${SCRIPT_DIR}/run-m4-pre-verdict.sh" | head -1 | cut -d: -f1)"
if [[ -z "${gen_line}" || "${gen_line}" -ge "${pin_line0}" ]]; then
  echo "FAIL: generate-product-tests --check must feed before assert-pinned-gates-ran (${gen_line} vs ${pin_line0})" >&2
  exit 1
fi
feed_line="$(grep -n 'run_feed_gate check-domain-parity' "${SCRIPT_DIR}/run-m4-pre-verdict.sh" | head -1 | cut -d: -f1)"
pin_line="$(grep -n 'python3 "${PINNED}"' "${SCRIPT_DIR}/run-m4-pre-verdict.sh" | head -1 | cut -d: -f1)"
if [[ -z "${feed_line}" || -z "${pin_line}" || "${feed_line}" -ge "${pin_line}" ]]; then
  echo "FAIL: feeding gates must appear before assert-pinned-gates-ran (${feed_line} vs ${pin_line})" >&2
  exit 1
fi
grep -q 'assert-pinned-gates-ran' "${SCRIPT_DIR}/run-m4-floor.sh"
grep -q 'assert-retrievable-tree' "${SCRIPT_DIR}/run-m4-floor.sh"
grep -q 'snapshot-m4-test-reports' "${SCRIPT_DIR}/run-m4-floor.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git -C "$TMP" init -q
git -C "$TMP" config user.email test@example.com
git -C "$TMP" config user.name test
mkdir -p "$TMP/src/main/java" "$TMP/target/surefire-reports" "$TMP/evidence/receipts/gates"
echo 'class App {}' > "$TMP/src/main/java/App.java"
echo '<project/>' > "$TMP/pom.xml"
git -C "$TMP" add src pom.xml
git -C "$TMP" commit -q -m base

# Architect 091125ZA: do not pre-seed gate receipts. Feeding gates must
# write evidence/receipts/gates/ themselves (or run_feed_gate records rc).

cat > "$TMP/target/surefire-reports/TEST-com.demo.GreetingResourceTest.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.demo.GreetingResourceTest" tests="2" failures="0" errors="0" skipped="0" time="0.1">
  <testcase name="testHelloEndpoint" classname="com.demo.GreetingResourceTest" time="0.05"/>
</testsuite>
XML

export M4_CARD_BODY='M4 acceptance; verdict is O1/O2/O3 over the built artefact.'

# dest-8 M4_CARD_SKILLS override is OBJECT (Architect 130758ZA).
if M4_CARD_SKILLS='admit-migration-plan,assert-retrievable-tree' \
  bash "${SCRIPT_DIR}/run-m4-pre-verdict.sh" "$TMP"; then
  echo "FAIL: M4_CARD_SKILLS override should refuse" >&2
  exit 1
fi
unset M4_CARD_SKILLS

# dest-5 Token body must refuse before the rest of the runner.
if M4_CARD_BODY='Token: PROVISIONAL_ACCEPT, ship: false' \
  bash "${SCRIPT_DIR}/run-m4-pre-verdict.sh" "$TMP"; then
  echo "FAIL: dest-5 Token body should refuse" >&2
  exit 1
fi

# dest-5 Failures:1 must refuse even after a later live clean.
mkdir -p "$TMP/target/surefire-reports"
cat > "$TMP/target/surefire-reports/TEST-com.demo.HealthTest.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.demo.HealthTest" tests="1" failures="1" errors="0" skipped="0" time="0.2">
  <testcase name="healthEndpoint" classname="com.demo.HealthTest" time="0.1">
    <failure message="Status 404"/>
  </testcase>
</testsuite>
XML
rm -rf "$TMP/evidence/m4-pre-rebuild"
if bash "${SCRIPT_DIR}/run-m4-pre-verdict.sh" "$TMP"; then
  echo "FAIL: dest-5 Failures:1 should refuse" >&2
  exit 1
fi
# Restore a clean suite and a first snapshot of it.
rm -f "$TMP/target/surefire-reports/TEST-com.demo.HealthTest.xml"
rm -rf "$TMP/evidence/m4-pre-rebuild"
cat > "$TMP/target/surefire-reports/TEST-com.demo.GreetingResourceTest.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.demo.GreetingResourceTest" tests="2" failures="0" errors="0" skipped="0" time="0.1">
  <testcase name="testHelloEndpoint" classname="com.demo.GreetingResourceTest" time="0.05"/>
</testsuite>
XML

# Missing log must fail closed (the silent-skip class Operator named).
unset FENCE_EVASION_LOG FENCE_EVASION_LOGS HERMES_KANBAN_TASK HERMES_KANBAN_SHOW || true
if bash "${SCRIPT_DIR}/run-m4-pre-verdict.sh" "$TMP"; then
  echo "FAIL: missing worker log should refuse" >&2
  exit 1
fi

# M4's own task id without a parent walk must not pass (Operator 105656ZO).
export HERMES_KANBAN_TASK=t_m4
if bash "${SCRIPT_DIR}/run-m4-pre-verdict.sh" "$TMP"; then
  echo "FAIL: M4 own log default should refuse" >&2
  exit 1
fi
unset HERMES_KANBAN_TASK

# Benign opaque command, no refusal — advisory, exit 0.
printf '%s\n' "echo secret | base64 -d >/dev/null" > "$TMP/benign.log"
export FENCE_EVASION_LOG="$TMP/benign.log"

bash "${SCRIPT_DIR}/run-m4-pre-verdict.sh" "$TMP" 2>"$TMP/run.err"

# ADR-015, this tree: the pom carries no m4-parity block, so nothing compiles
# a generated suite. The runner says so and keeps going — the product-test
# floor is what measures the gap — and it never silently "passes" the build.
if grep -q -- "--fresh" "$TMP/run.err"; then
  echo "FAIL: a tree whose parity build never ran must not claim a fresh snapshot" >&2
  cat "$TMP/run.err" >&2
  exit 1
fi
grep -q "no m4-parity block in pom.xml" "$TMP/run.err" || {
  echo "FAIL: a pom with no m4-parity block must be named, not skipped in silence" >&2
  cat "$TMP/run.err" >&2
  exit 1
}
# The feeding gate leaves a receipt even when it refuses: silence is the
# refusal, a measured rc belongs on the completion floors.
GEN_RECEIPT="$TMP/evidence/receipts/gates/generate-product-tests.json"
[[ -f "${GEN_RECEIPT}" ]] || { echo "FAIL: no receipt for generate-product-tests --check" >&2; exit 1; }
grep -q '"gate": "generate-product-tests"' "${GEN_RECEIPT}" || {
  echo "FAIL: the receipt must name the gate" >&2; exit 1; }
grep -q '"rc": 1' "${GEN_RECEIPT}" || {
  echo "FAIL: --check on a tree with no generated manifest must be recorded as a refusal" >&2
  cat "${GEN_RECEIPT}" >&2
  exit 1
}

mkdir -p "$TMP/evidence/verdicts/refusals"
printf '%s\n' '{"ran":false,"reason":"runtime parity (G-4) is N/A; M5 ACCEPT would require G-4"}' \
  > "$TMP/evidence/verdicts/refusals/check-domain-parity.json"
printf '%s\n' '{"reason":"g4_hook=INCONCLUSIVE"}' \
  > "$TMP/evidence/verdicts/g4-hook-note.json"
if bash "${SCRIPT_DIR}/run-m4-pre-verdict.sh" "$TMP"; then
  echo "FAIL: G-4 N/A vs INCONCLUSIVE should refuse" >&2
  exit 1
fi
rm -f "$TMP/evidence/verdicts/g4-hook-note.json" \
  "$TMP/evidence/verdicts/refusals/check-domain-parity.json"

unset FENCE_EVASION_LOG
printf '%s\n' "echo secret | base64 -d >/dev/null" > "$TMP/work-a.log"
printf '%s\n' "echo secret | base64 -d >/dev/null" > "$TMP/work-b.log"
export FENCE_EVASION_LOGS="$TMP/work-a.log:$TMP/work-b.log"
bash "${SCRIPT_DIR}/run-m4-pre-verdict.sh" "$TMP"
printf '%s\n' "blocked: unproven command path" "echo L3Byb2plY3RzL2xlZ2FjeQ== | base64 -d" > "$TMP/evade.log"
export FENCE_EVASION_LOGS="$TMP/work-a.log:$TMP/evade.log"
if bash "${SCRIPT_DIR}/run-m4-pre-verdict.sh" "$TMP"; then
  echo "FAIL: evasion in a work log should refuse" >&2
  exit 1
fi
unset FENCE_EVASION_LOGS
export FENCE_EVASION_LOG="$TMP/benign.log"

echo 'class Dirty {}' > "$TMP/src/main/java/Dirty.java"
if bash "${SCRIPT_DIR}/run-m4-pre-verdict.sh" "$TMP"; then
  echo "FAIL: dirty src should refuse" >&2
  exit 1
fi
echo "OK: run-m4-pre-verdict admission"
