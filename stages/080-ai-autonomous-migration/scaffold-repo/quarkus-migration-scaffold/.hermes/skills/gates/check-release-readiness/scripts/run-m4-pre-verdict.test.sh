#!/usr/bin/env bash
# Admission: scripts/ names both asserts + the detector; runner fail-closes;
# missing worker log is not a skip-as-pass (Operator E-20260825T074910ZO).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

grep -q 'assert-pinned-gates-ran' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'assert-retrievable-tree' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'assert-no-fence-evasion' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'assert-g4-claim-consistency' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'assert-pinned-gates-ran' "${SCRIPT_DIR}/run-m4-floor.sh"
grep -q 'assert-retrievable-tree' "${SCRIPT_DIR}/run-m4-floor.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git -C "$TMP" init -q
git -C "$TMP" config user.email test@example.com
git -C "$TMP" config user.name test
mkdir -p "$TMP/src/main/java"
echo 'class App {}' > "$TMP/src/main/java/App.java"
echo '<project/>' > "$TMP/pom.xml"
git -C "$TMP" add src pom.xml
git -C "$TMP" commit -q -m base
mkdir -p "$TMP/evidence/verdicts/refusals"
for g in check-spec-readiness check-domain-parity check-release-readiness; do
  printf '%s\n' '{"ran": false, "reason": "specimen-n/a: no DB"}' > "$TMP/evidence/verdicts/refusals/${g}.json"
done

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

bash "${SCRIPT_DIR}/run-m4-pre-verdict.sh" "$TMP"

printf '%s\n' '{"ran":false,"reason":"runtime parity (G-4) is N/A; M5 ACCEPT would require G-4"}' \
  > "$TMP/evidence/verdicts/refusals/check-domain-parity.json"
printf '%s\n' '{"verdict":"PROVISIONAL_ACCEPT","ship":false,"reason":"g4_hook=INCONCLUSIVE"}' \
  > "$TMP/evidence/verdicts/check-release-readiness.json"
if bash "${SCRIPT_DIR}/run-m4-pre-verdict.sh" "$TMP"; then
  echo "FAIL: G-4 N/A vs INCONCLUSIVE should refuse" >&2
  exit 1
fi
printf '%s\n' '{"ran": false, "reason": "specimen-n/a: no DB"}' \
  > "$TMP/evidence/verdicts/refusals/check-domain-parity.json"
rm -f "$TMP/evidence/verdicts/check-release-readiness.json"

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
