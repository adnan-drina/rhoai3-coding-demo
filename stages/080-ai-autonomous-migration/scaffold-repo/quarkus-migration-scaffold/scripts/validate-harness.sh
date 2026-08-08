#!/usr/bin/env bash
# Single local entrypoint for harness readiness (pattern-steal P1).
# Runs without a provisioned specimen.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"
rc=0

echo "== check-no-hermes-context-override =="
bash scripts/check-no-hermes-context-override.sh || rc=1

echo "== check-sdd-readiness (+ §S.6 ordering) =="
bash scripts/check-sdd-readiness.sh || rc=1
# §S.6 fail-closed smoke (temp tree)
sdd_tmp="$(mktemp -d)"
mkdir -p "${sdd_tmp}/migration/tasks" "${sdd_tmp}/migration/briefs" "${sdd_tmp}/scripts"
cp scripts/check-sdd-ordering.py "${sdd_tmp}/scripts/"
printf '%s\n' '## Non-Goals' '- NG-001: x' > "${sdd_tmp}/migration/briefs/b.md"
printf '%s\n' '{"id":"T-1","phase":"M3","replan":true,"ac_ids":["AC-1"],"files_in_scope":["src/"],"deps":[],"brief_id":"B-1"}' \
  > "${sdd_tmp}/migration/tasks/bad.json"
if python3 "${sdd_tmp}/scripts/check-sdd-ordering.py" "${sdd_tmp}" >/dev/null 2>&1; then
  echo "FAIL: §S.6 should refuse IMPLEMENT replan" >&2
  rc=1
else
  echo "OK: §S.6 refuses IMPLEMENT replan"
fi
printf '%s\n' '{"id":"T-1","phase":"M3","ac_ids":["AC-1"],"files_in_scope":["src/"],"deps":[],"brief_id":"B-1"}' \
  > "${sdd_tmp}/migration/tasks/bad.json"
python3 "${sdd_tmp}/scripts/check-sdd-ordering.py" "${sdd_tmp}" || rc=1
rm -rf "${sdd_tmp}"

echo "== admission fixtures (W2 §10) =="
bash scripts/run-admission-fixtures.sh || rc=1

echo "== mta-findings schema (fixture known-good) =="
python3 scripts/validate-mta-findings-schema.py \
  migration/fixtures/admission/g3/known-good/mta-findings.json || rc=1

echo "== inventory scanner smoke (fixtures as near-empty tree) =="
tmp="$(mktemp -d)"
mkdir -p "${tmp}/src"
# one lifecycle + one HTTP mapping
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
python3 scripts/inventory-entry-points.py "${tmp}" -o "${tmp}/inv.json" || rc=1
python3 - <<PY || rc=1
import json
d=json.load(open("${tmp}/inv.json"))
assert d["execution_evidence"]["ran"] is True
assert d["counts"]["http"] >= 1
assert d["counts"]["non_http"] >= 1
print("OK: inventory smoke", d["counts"])
PY
rm -rf "${tmp}"

if [ "${rc}" -ne 0 ]; then
  echo "validate-harness FAILED" >&2
  exit 1
fi
echo "OK: validate-harness passed"
