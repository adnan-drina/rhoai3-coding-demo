#!/usr/bin/env bash
# Single local entrypoint for harness readiness (pattern-steal P1).
# Runs without a provisioned specimen.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"
rc=0

echo "== check-no-hermes-context-override =="
bash scripts/check-no-hermes-context-override.sh || rc=1

echo "== check-sdd-readiness =="
bash scripts/check-sdd-readiness.sh || rc=1

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
