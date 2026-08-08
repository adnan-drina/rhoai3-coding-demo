#!/usr/bin/env bash
# Specimen-free harness validation — skill harness-validate (AD-H §7).
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "${SKILL_DIR}/../../.." && pwd)"
SKILLS="$(cd "${SKILL_DIR}/.." && pwd)"
cd "${ROOT}"
rc=0

echo "== scaffold-invariants =="
bash "${SKILLS}/scaffold-invariants/scripts/check-no-hermes-context-override.sh" || rc=1

echo "== sdd-readiness (+ §S.6) =="
bash "${SKILLS}/sdd-readiness/scripts/check-readiness.sh" || rc=1
sdd_tmp="$(mktemp -d)"
mkdir -p "${sdd_tmp}/migration/tasks" "${sdd_tmp}/migration/briefs"
printf '%s\n' '## Non-Goals' '- NG-001: x' > "${sdd_tmp}/migration/briefs/b.md"
printf '%s\n' '{"id":"T-1","phase":"M3","replan":true,"ac_ids":["AC-1"],"files_in_scope":["src/"],"deps":[],"brief_id":"B-1"}' \
  > "${sdd_tmp}/migration/tasks/bad.json"
if python3 "${SKILLS}/sdd-readiness/scripts/check-ordering.py" "${sdd_tmp}" >/dev/null 2>&1; then
  echo "FAIL: §S.6 should refuse IMPLEMENT replan" >&2
  rc=1
else
  echo "OK: §S.6 refuses IMPLEMENT replan"
fi
printf '%s\n' '{"id":"T-1","phase":"M3","ac_ids":["AC-1"],"files_in_scope":["src/"],"deps":[],"brief_id":"B-1"}' \
  > "${sdd_tmp}/migration/tasks/bad.json"
python3 "${SKILLS}/sdd-readiness/scripts/check-ordering.py" "${sdd_tmp}" || rc=1
rm -rf "${sdd_tmp}"

echo "== domain-gates admission (W2 §10) =="
bash "${SKILLS}/domain-gates/scripts/run-admission.sh" "${ROOT}" || rc=1

echo "== mta-analysis findings schema (fixture known-good) =="
python3 "${SKILLS}/mta-analysis/scripts/validate-findings-schema.py" \
  migration/fixtures/admission/g3-findings-delta/known-good/mta-findings.json || rc=1

echo "== inventory-entry-points smoke =="
tmp="$(mktemp -d)"
mkdir -p "${tmp}/src"
cat > "${tmp}/src/Demo.java" <<'EOF'
import javax.annotation.PostConstruct;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
@RestController
public class Demo {
  @PostConstruct void init() {}
  @GetMapping("/api/demo") String demo() { return "ok"; }
}
EOF
python3 "${SKILLS}/inventory-entry-points/scripts/inventory-entry-points.py" \
  "${tmp}" -o "${tmp}/inv.json" || rc=1
python3 - <<PY || rc=1
import json
d=json.load(open("${tmp}/inv.json"))
assert d["execution_evidence"]["ran"] is True
assert d["counts"]["http"] >= 1
assert d["counts"]["non_http"] >= 1
print("OK: inventory smoke", d["counts"])
PY
rm -rf "${tmp}"

echo "== role-authority (AD-H §16) =="
bash "${SKILLS}/role-authority/scripts/check-acks.sh" M1 "${ROOT}" || rc=1
# M2 without ack must fail
if bash "${SKILLS}/role-authority/scripts/check-acks.sh" M2 "${ROOT}" >/dev/null 2>&1; then
  echo "FAIL: M2 should require m1-findings ack when absent" >&2
  rc=1
else
  echo "OK: M2 refuses without m1-findings ack"
fi
python3 "${SKILLS}/role-authority/scripts/check-role-writes.py" "${ROOT}" || rc=1
# cross-role write smoke
rw_tmp="$(mktemp -d)"
mkdir -p "${rw_tmp}/migration/tasks"
printf '%s\n' '{"role":"planner","writes":["src/main/java/X.java"],"ac_ids":["AC-1"],"files_in_scope":[],"deps":[],"brief_id":"B-1"}' \
  > "${rw_tmp}/migration/tasks/bad.json"
if python3 "${SKILLS}/role-authority/scripts/check-role-writes.py" "${rw_tmp}" >/dev/null 2>&1; then
  echo "FAIL: planner write to src/ should refuse" >&2
  rc=1
else
  echo "OK: planner→src write refused"
fi
rm -rf "${rw_tmp}"

if [ "${rc}" -ne 0 ]; then
  echo "harness-validate FAILED" >&2
  exit 1
fi
echo "OK: harness-validate passed"
