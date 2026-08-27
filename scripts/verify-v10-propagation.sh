#!/usr/bin/env bash
# v10 propagation bar — dest-side behaviour, not brittle grep -c == 1.
#
# Architect E-20260827T073749ZA: the 2026-08-26 evening bar red-lit a good
# cut because four rows were bar defects. Do not edit destfiles to satisfy
# exact counts. Two-sided: dest-9 (unpublished golden 96d6e790) MUST fail;
# dest-10 MUST pass. Usage: bash scripts/verify-v10-propagation.sh <pod>
#
# Do not dest-dispatch on green. GO-dispatch-m1 is Operator.
set -uo pipefail
NS=wksp-ai-developer
POD="${1:?usage: verify-v10-propagation.sh <pod>}"
M=/projects/modernized
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GITOPS_DESTINIT="${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml"
WORKSHOP_SMOKE="${REPO_ROOT}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/sdd/init-spec-workspace/scripts/assert-dest-init-smokes-mandated-tools.py"
PASS=0
FAIL=0

seat() {
  oc exec -n "$NS" "$POD" -c development-tooling -- bash -lc "$1" 2>/dev/null \
    | tr -d '\r' | sed -e 's/.*HasRichCommandDetection=True//' | tr -cd '[:print:]\n' | sed '/^[[:space:]]*$/d'
}
chk() {
  local n="$1" c="$2" e="$3" out
  out="$(seat "$c")"
  if printf '%s' "$out" | grep -qF "$e"; then
    PASS=$((PASS + 1))
    printf "  \033[0;32mpass\033[0m  %s\n" "$n"
  else
    FAIL=$((FAIL + 1))
    printf "  \033[0;31mFAIL\033[0m  %s  (got: %s)\n" "$n" "$(printf '%s' "$out" | head -1 | cut -c1-52)"
  fi
}
chk_local() {
  local n="$1" rc="$2"
  if [[ "$rc" -eq 0 ]]; then
    PASS=$((PASS + 1))
    printf "  \033[0;32mpass\033[0m  %s\n" "$n"
  else
    FAIL=$((FAIL + 1))
    printf "  \033[0;31mFAIL\033[0m  %s  (workshop rc=%s)\n" "$n" "$rc"
  fi
}

echo "════ v10 PROPAGATION BAR on $POD ════"

echo "── F4: M4 cannot author its own gate receipts ──"
# Behaviour: def + call (>=2). Exact grep -c == 1 contradicted the next row.
chk "k2 REFUSES an M4 receipt write" "cd $M && python3 -c \"
import re,sys
src=open('.hermes/kernel/pre_tool_call.sh').read()
sys.stdout.write('REFUSES' if 'is_gate_receipt_rel' in src and re.search(r'is_gate_receipt_rel\\\\(', src) and src.count('is_gate_receipt_rel')>=2 else 'no-fence')\"" REFUSES
chk "receipts carry argv/rc/producer" "grep -c 'producer=' $M/.hermes/skills/gates/assert-pinned-gates-ran/scripts/assert-pinned-gates-ran.py" 1
chk "pinned-gates suite green (behaviour)" "cd $M && python3 .hermes/skills/gates/assert-pinned-gates-ran/scripts/assert-pinned-gates-ran.test.py >/dev/null 2>&1 && echo OK" OK

echo "── W4: inventory and MTA must share harvest_referent ──"
chk "harvest-referent pair checker [P]" "test -f $M/.hermes/skills/analysis/inventory-legacy-surface/scripts/assert-harvest-referent-pair.py && echo OK" OK
chk "  its selftest green (behaviour)" "cd $M && python3 .hermes/skills/analysis/inventory-legacy-surface/scripts/assert-harvest-referent-pair-selftest.py >/dev/null 2>&1 && echo OK" OK

echo "── W1: dest-init proves the tools (dest = shim-only REFUSE) ──"
# Behaviour, not grep -c speckit-tasks == 1. Do NOT run dest selftest _gitops().
chk "empty dest-init REFUSES speckit-tasks" "cd $M && python3 -c '
import importlib.util,sys
p=\".hermes/skills/sdd/init-spec-workspace/scripts/assert-dest-init-smokes-mandated-tools.py\"
spec=importlib.util.spec_from_file_location(\"smoke\", p)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
gaps=m.check_text(\"\")
sys.stdout.write(\"GAPS\" if any(\"speckit-tasks\" in g for g in gaps) else \"no-gap\")
'" GAPS
chk "shim-only dest-init REFUSES (dest half)" "cd $M && python3 -c '
import importlib.util,sys
p=\".hermes/skills/sdd/init-spec-workspace/scripts/assert-dest-init-smokes-mandated-tools.py\"
spec=importlib.util.spec_from_file_location(\"smoke\", p)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
shim=\"specify_helper = os.path.join(project, \\\"specify-from-project.sh\\\")\\nprint(\\\"specify PATH shim\\\")\\n\"
gaps=m.check_text(shim)
sys.stdout.write(\"REFUSE\" if gaps else \"PASS\")
'" REFUSE

echo "── W1 workshop: GitOps dest-init must PASS (not on dest) ──"
if [[ -f "$WORKSHOP_SMOKE" && -f "$GITOPS_DESTINIT" ]]; then
  python3 "$WORKSHOP_SMOKE" "$GITOPS_DESTINIT" >/dev/null 2>&1
  chk_local "GitOps dest-init four-step smoke (workshop)" "$?"
else
  FAIL=$((FAIL + 1))
  printf "  \033[0;31mFAIL\033[0m  GitOps dest-init four-step smoke (workshop)  (missing checker or yaml)\n"
fi

echo "── W3: partition fidelity ──"
chk "HTTP story without dest_file REFUSES" "cd $M/.hermes/kernel && python3 -c \"
import sys
sys.path.insert(0,'.')
import k4_convert as K
s={'story_id':'T_X','kind':'us','endpoints':['GET /x'],'files_writable':['src/main/java/com/demo/X.java'],'parents':[],'skills':['spring-to-quarkus-patterns'],'acceptance_criteria':[{'description':'d','check':'test_suite_runs','cmd':'mvn -q test'}],'legacy_source':'src/main/java/a/B.java'}
p={'schema':'rhoai3.partition/v1','type_inventory_sha256':'x'*64,'stories':[s]}
i=[x for x in K.validate_inputs(p) if 'dest_file' in str(x).lower()]
print('REFUSED' if i else 'passed')
\"" REFUSED

echo "── W5: one pom owner ──"
chk "sole pom writer stated" "grep -c 'sole pom writer' $M/.hermes/skills/migration/author-destination-pom/SKILL.md" 1
chk "needing story declares, does not write" "grep -c extensions_declared $M/.hermes/skills/migration/spring-to-quarkus-patterns/SKILL.md" 1

echo "── W6: normative claims now have checks ──"
chk "trivial @QuarkusMain REFUSES (behaviour)" "cd $M && python3 .hermes/skills/migration/spring-to-quarkus-patterns/scripts/assert-no-trivial-quarkusmain.test.py >/dev/null 2>&1 && echo OK" OK
chk "inherited @Id REFUSES (behaviour)" "cd $M && python3 .hermes/skills/migration/form-entity-persistence/scripts/assert-inherited-id-not-redeclared.test.py >/dev/null 2>&1 && echo OK" OK

echo "── F3: pom writer carries the extension union ──"
chk "stamp_dd3_extensions called from K4" "grep -c stamp_dd3_extensions $M/.hermes/kernel/k4_convert.py" 2
chk "script-naming bar green" "cd $M && python3 .hermes/kernel/assert-skill-scripts-named.py --skills-root .hermes/skills >/dev/null 2>&1 && echo OK" OK
chk "init-spec names M2 provenance scripts" "grep -c assert-speckit-unknown-then-emit.py $M/.hermes/skills/sdd/init-spec-workspace/SKILL.md" 1
chk "assert-card-performed selftest green" "cd $M && python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-card-performed.test.py >/dev/null 2>&1 && echo OK" OK

echo "── hygiene: fixtures name the case, not the batch ──"
chk "fixtures named for the case" "test -d $M/.hermes/skills/migration/spring-to-quarkus-patterns/fixtures/cases/trivial-boot-main-refuses-quarkusmain && echo OK" OK
chk "golden/ and cases/ split" "test -d $M/.hermes/skills/migration/spring-to-quarkus-patterns/fixtures/cases && test -d $M/.hermes/skills/migration/spring-to-quarkus-patterns/fixtures/golden && echo OK" OK

echo "────────────────────────────────────────"
printf "  %s pass, %s fail\n" "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
