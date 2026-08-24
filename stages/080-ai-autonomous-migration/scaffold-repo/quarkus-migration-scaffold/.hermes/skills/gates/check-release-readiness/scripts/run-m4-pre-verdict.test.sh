#!/usr/bin/env bash
# Admission: scripts/ names both asserts; runner fail-closes; refusals pass.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

grep -q 'assert-pinned-gates-ran' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
grep -q 'assert-retrievable-tree' "${SCRIPT_DIR}/run-m4-pre-verdict.sh"
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

bash "${SCRIPT_DIR}/run-m4-pre-verdict.sh" "$TMP"

echo 'class Dirty {}' > "$TMP/src/main/java/Dirty.java"
if bash "${SCRIPT_DIR}/run-m4-pre-verdict.sh" "$TMP"; then
  echo "FAIL: dirty src should refuse" >&2
  exit 1
fi
echo "OK: run-m4-pre-verdict admission"
