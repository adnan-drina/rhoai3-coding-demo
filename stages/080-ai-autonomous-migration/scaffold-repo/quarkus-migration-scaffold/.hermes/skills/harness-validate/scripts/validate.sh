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

# Parser/fixture only — not live specimen admission (Architect E-20260808T080815Z #3).
echo "== G-1 PIT dry-run parse (R1 pin; not live admission) =="
python3 "${SKILLS}/domain-gates/scripts/parse-pit-mutations.py" \
  "${ROOT}/migration/fixtures/pit-dry-run/mutations.xml" || rc=1
if python3 "${SKILLS}/domain-gates/scripts/parse-pit-mutations.py" \
  "${ROOT}/migration/fixtures/pit-dry-run/missing.xml" >/dev/null 2>&1; then
  echo "FAIL: missing mutations.xml should refuse" >&2
  rc=1
else
  echo "OK: missing mutations.xml refused"
fi

echo "== AR-3.6 G-1 acceptance operand (probe ≠ acceptance) =="
# Scaffold tip currently has harness-only tests → must REFUSE as acceptance
if python3 "${SKILLS}/domain-gates/scripts/check-g1-acceptance-operand.py" "${ROOT}" >/dev/null 2>&1; then
  echo "FAIL: probe-only scaffold should refuse acceptance operand" >&2
  rc=1
else
  echo "OK: AR-3.6 probe-only acceptance refused"
fi
if G1_OPERAND=tooling_smoke python3 "${SKILLS}/domain-gates/scripts/check-g1-acceptance-operand.py" "${ROOT}"; then
  echo "OK: AR-3.6 tooling_smoke harness path permitted (non-acceptance)"
else
  echo "FAIL: tooling_smoke should allow harness-only" >&2
  rc=1
fi


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

echo "== ack/comment authority (AD-H §16.5 / AR-1.1 / AR-1.2) =="
# fixture feed must refuse impersonating override
if python3 "${SKILLS}/role-authority/scripts/check-comment-authority.py" "${ROOT}" >/dev/null 2>&1; then
  echo "FAIL: AR-1.2 impersonating override fixture should refuse" >&2
  rc=1
else
  echo "OK: AR-1.2 impersonating comment refused"
fi
ar11_tmp="$(mktemp -d)"
mkdir -p "${ar11_tmp}/migration/acks"
printf '%s\n' '{"kind":"migration-ack","ack_type":"brief-identity","status":"acknowledged","acknowledged_by":"planner (M2)","acknowledged_at":"2026-08-09T17:00:00Z"}' \
  > "${ar11_tmp}/migration/acks/brief-identity.json"
if python3 "${SKILLS}/role-authority/scripts/check-ack-authority.py" "${ar11_tmp}" >/dev/null 2>&1; then
  echo "FAIL: AR-1.1 planner self-ACK should refuse" >&2
  rc=1
else
  echo "OK: AR-1.1 planner self-ACK refused"
fi
printf '%s\n' '{"kind":"migration-ack","ack_type":"brief-identity","status":"acknowledged","acknowledged_by":"Operator","acknowledged_at":"2026-08-10T00:00:00Z","task_id":"t_demo","artifact_digests":{"brief":"abc"}}' \
  > "${ar11_tmp}/migration/acks/brief-identity.ack.json"
rm -f "${ar11_tmp}/migration/acks/brief-identity.json"
python3 "${SKILLS}/role-authority/scripts/check-ack-authority.py" "${ar11_tmp}" || rc=1
rm -rf "${ar11_tmp}"

echo "== write-fence proving-min (AD-H §16.4 / F2) =="
fence_tmp="$(mktemp -d)"
mkdir -p "${fence_tmp}/migration/acks" "${fence_tmp}/migration/verdicts" \
  "${fence_tmp}/.hermes/skills" "${fence_tmp}/migration/fixtures" \
  "${fence_tmp}/src/main/java"
printf '%s\n' 'ok' > "${fence_tmp}/migration/acks/README.md"
printf '%s\n' 'ok' > "${fence_tmp}/migration/fixtures/keep.txt"
bash "${SKILLS}/role-authority/scripts/apply-write-fence.sh" "${fence_tmp}" lock || rc=1
if python3 "${SKILLS}/role-authority/scripts/probe-write-fence.py" "${fence_tmp}"; then
  echo "OK: F2 seat probe PASS on temp tree"
else
  echo "FAIL: F2 seat probe" >&2
  rc=1
fi
# scope refuse smoke
printf '%s\n' '{"files_in_scope":["src/main/java/Foo.java"]}' > "${fence_tmp}/body.json"
printf '%s\n' 'x' > "${fence_tmp}/src/main/java/OutOfScope.java"
if python3 "${SKILLS}/role-authority/scripts/check-write-fence.py" "${fence_tmp}" \
  --no-git-status --body "${fence_tmp}/body.json" \
  --writes src/main/java/OutOfScope.java migration/acks/forged.json >/dev/null 2>&1; then
  echo "FAIL: write-fence should refuse OOS + ack forge" >&2
  rc=1
else
  echo "OK: write-fence refuses OOS + deny-path writes"
fi
bash "${SKILLS}/role-authority/scripts/apply-write-fence.sh" "${fence_tmp}" unlock >/dev/null || true
rm -rf "${fence_tmp}"

echo "== grounded-generation (AD-H §17) =="
python3 "${SKILLS}/grounded-generation/scripts/check-citation.py" "${ROOT}" || rc=1
gg_tmp="$(mktemp -d)"
mkdir -p "${gg_tmp}/migration/tasks"
# invent-without-locus: writes without legacy_locus
printf '%s\n' '{"id":"T-bad","phase":"M3","role":"implementer","brief_id":"B-1","ac_ids":["AC-1"],"files_in_scope":["src/"],"deps":[],"writes":["src/X.java"]}' \
  > "${gg_tmp}/migration/tasks/bad.json"
if python3 "${SKILLS}/grounded-generation/scripts/check-citation.py" "${gg_tmp}" >/dev/null 2>&1; then
  echo "FAIL: invent-without-locus should refuse" >&2
  rc=1
else
  echo "OK: invent-without-locus refused"
fi
# good non-trivial packet
printf '%s\n' '{"id":"T-1","phase":"M3","role":"implementer","brief_id":"B-1","ac_ids":["AC-1"],"files_in_scope":["src/"],"deps":[],"legacy_locus":"projects/legacy/Foo.java:10-40","writes":["src/Foo.java"]}' \
  > "${gg_tmp}/migration/tasks/bad.json"
python3 "${SKILLS}/grounded-generation/scripts/check-citation.py" "${gg_tmp}" || rc=1
# commit message lint
printf '%s\n' 'T-1: port Foo (brief B-1; legacy projects/legacy/Foo.java:10-40)' > "${gg_tmp}/msg.txt"
python3 "${SKILLS}/grounded-generation/scripts/check-citation.py" "${gg_tmp}" --commit-msg "${gg_tmp}/msg.txt" || rc=1
printf '%s\n' 'fix formatting' > "${gg_tmp}/msg-bad.txt"
if python3 "${SKILLS}/grounded-generation/scripts/check-citation.py" "${gg_tmp}" --commit-msg "${gg_tmp}/msg-bad.txt" >/dev/null 2>&1; then
  echo "FAIL: commit without task id should refuse" >&2
  rc=1
else
  echo "OK: commit without task id refused"
fi
rm -rf "${gg_tmp}"

echo "== validation-release-gates (AD-H §18) =="
python3 "${SKILLS}/validation-release-gates/scripts/check-phase-matrix.py" "${ROOT}" || rc=1
python3 "${SKILLS}/validation-release-gates/scripts/check-verdict-routing.py" "${ROOT}" || rc=1
vr_tmp="$(mktemp -d)"
mkdir -p "${vr_tmp}/migration/verdicts"
printf '%s\n' '{"phase":"M5","verdict":"INCONCLUSIVE","ship":true}' > "${vr_tmp}/migration/verdicts/bad.json"
if python3 "${SKILLS}/validation-release-gates/scripts/check-verdict-routing.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: INCONCLUSIVE ship should refuse" >&2
  rc=1
else
  echo "OK: INCONCLUSIVE ship refused"
fi
# §18.0 — ACCEPT+provisional footnote refused at M4
printf '%s\n' '{"phase":"M4","verdict":"ACCEPT","accept_kind":"provisional","g1_kill_ratio":"pending_threshold","ship":false}' \
  > "${vr_tmp}/migration/verdicts/bad.json"
if python3 "${SKILLS}/validation-release-gates/scripts/check-verdict-routing.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: M4 ACCEPT+provisional footnote should refuse" >&2
  rc=1
else
  echo "OK: M4 ACCEPT+provisional footnote refused"
fi
# §18.0 — PROVISIONAL_ACCEPT must not ship
printf '%s\n' '{"phase":"M4","verdict":"PROVISIONAL_ACCEPT","g1_kill_ratio":"pending_threshold","ship":true}' \
  > "${vr_tmp}/migration/verdicts/bad.json"
if python3 "${SKILLS}/validation-release-gates/scripts/check-verdict-routing.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: PROVISIONAL_ACCEPT ship should refuse" >&2
  rc=1
else
  echo "OK: PROVISIONAL_ACCEPT ship refused"
fi
# §18.0 — kill-ratio PASS without pin refused
printf '%s\n' '{"phase":"M4","verdict":"PROVISIONAL_ACCEPT","g1_kill_ratio":"PASS","ship":false}' \
  > "${vr_tmp}/migration/verdicts/bad.json"
if python3 "${SKILLS}/validation-release-gates/scripts/check-verdict-routing.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: g1_kill_ratio=PASS without pin should refuse" >&2
  rc=1
else
  echo "OK: unpinned kill-ratio PASS refused"
fi
# good M4 PROVISIONAL_ACCEPT
printf '%s\n' '{"phase":"M4","verdict":"PROVISIONAL_ACCEPT","g1_kill_ratio":"pending_threshold","ship":false}' \
  > "${vr_tmp}/migration/verdicts/bad.json"
python3 "${SKILLS}/validation-release-gates/scripts/check-verdict-routing.py" "${vr_tmp}" || rc=1
# good M5 full with waiver (threshold not yet pinned)
printf '%s\n' '{"phase":"M5","verdict":"ACCEPT","g1_kill_ratio":"pending_threshold","g1_kill_ratio_waiver":true,"ship":true,"routing":"close"}' \
  > "${vr_tmp}/migration/verdicts/bad.json"
python3 "${SKILLS}/validation-release-gates/scripts/check-verdict-routing.py" "${vr_tmp}" || rc=1
# single-unit composition reopen
printf '%s\n' '{"phase":"M5","verdict":"REFUSE","gate":"g4_runtime_parity","prior_verdict":"PROVISIONAL_ACCEPT","routing":"reopen_story"}' \
  > "${vr_tmp}/migration/verdicts/bad.json"
python3 "${SKILLS}/validation-release-gates/scripts/check-verdict-routing.py" "${vr_tmp}" || rc=1
# shared-substrate reopen (fixture closure map)
mkdir -p "${vr_tmp}/migration/slices"
cp "${ROOT}/migration/fixtures/substrate-reopen/closure-map.json" \
  "${vr_tmp}/migration/slices/closure-map.json"
printf '%s\n' '{"phase":"M5","verdict":"REFUSE","gate":"g4_runtime_parity","story_id":"S-1","prior_verdict":"PROVISIONAL_ACCEPT","implicated_substrate":["com.example.shared.Entity"],"reopen_story_ids":["S-1","S-2"],"routing":"reopen_story"}' \
  > "${vr_tmp}/migration/verdicts/bad.json"
python3 "${SKILLS}/validation-release-gates/scripts/check-verdict-routing.py" "${vr_tmp}" || rc=1
# wrong reopen set refused
printf '%s\n' '{"phase":"M5","verdict":"REFUSE","gate":"g4_runtime_parity","story_id":"S-1","implicated_substrate":["com.example.shared.Entity"],"reopen_story_ids":["S-1"],"routing":"reopen_story"}' \
  > "${vr_tmp}/migration/verdicts/bad.json"
if python3 "${SKILLS}/validation-release-gates/scripts/check-verdict-routing.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: under-sized reopen set should refuse" >&2
  rc=1
else
  echo "OK: under-sized substrate reopen set refused"
fi
printf '%s\n' '{"phase":"M4","verdict":"REFUSE","routing":"auto_fix"}' > "${vr_tmp}/migration/verdicts/bad.json"
python3 "${SKILLS}/validation-release-gates/scripts/check-verdict-routing.py" "${vr_tmp}" || rc=1
# factory M5 oracle
python3 "${SKILLS}/validation-release-gates/scripts/check-factory-m5.py" "${ROOT}" || rc=1
mkdir -p "${vr_tmp}/migration/preflight" "${vr_tmp}/migration/verdicts"
printf '%s\n' '{"phase":"factory","status":"factory_ready"}' > "${vr_tmp}/migration/preflight/factory.json"
rm -f "${vr_tmp}/migration/verdicts/"*.json
if python3 "${SKILLS}/validation-release-gates/scripts/check-factory-m5.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: factory without M5 ACCEPT should refuse" >&2
  rc=1
else
  echo "OK: factory without M5 ACCEPT refused"
fi
printf '%s\n' '{"phase":"M5","verdict":"PROVISIONAL_ACCEPT","g1_kill_ratio":"pending_threshold"}' \
  > "${vr_tmp}/migration/verdicts/m5.json"
if python3 "${SKILLS}/validation-release-gates/scripts/check-factory-m5.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: factory with PROVISIONAL_ACCEPT should refuse" >&2
  rc=1
else
  echo "OK: factory PROVISIONAL_ACCEPT refused"
fi
printf '%s\n' '{"phase":"M5","verdict":"ACCEPT","g1_kill_ratio":"pending_threshold","g1_kill_ratio_waiver":true}' \
  > "${vr_tmp}/migration/verdicts/m5.json"
python3 "${SKILLS}/validation-release-gates/scripts/check-factory-m5.py" "${vr_tmp}" || rc=1
# candidate→promote (finding 4)
python3 "${SKILLS}/validation-release-gates/scripts/check-candidate-promote.py" "${ROOT}" || rc=1
printf '%s\n' '{"phase":"factory","status":"push_main","promoted_to_main":true,"factory_result":"fail"}' \
  > "${vr_tmp}/migration/preflight/factory.json"
if python3 "${SKILLS}/validation-release-gates/scripts/check-candidate-promote.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: promote without candidate_sha / on factory fail should refuse" >&2
  rc=1
else
  echo "OK: illegal promote refused"
fi
printf '%s\n' '{"phase":"factory","status":"factory_ready","candidate_sha":"abcdef1","factory_result":"pass","promoted_to_main":false}' \
  > "${vr_tmp}/migration/preflight/factory.json"
python3 "${SKILLS}/validation-release-gates/scripts/check-candidate-promote.py" "${vr_tmp}" || rc=1
# side-effect recovery idle + persisted-data idle
python3 "${SKILLS}/validation-release-gates/scripts/check-side-effect-recovery.py" "${ROOT}" || rc=1
python3 "${SKILLS}/domain-gates/scripts/check-persisted-data-contract.py" "${ROOT}" || rc=1

echo "== workspace recovery proving-min (AD-H §5.1 / F4) =="
f4_tmp="$(mktemp -d)"
f4_home="$(mktemp -d)"
export HERMES_HOME="${f4_home}"
git -C "${f4_tmp}" init -q
git -C "${f4_tmp}" config user.email "f4@example.com"
git -C "${f4_tmp}" config user.name "F4 Fixture"
printf '%s\n' 'base' > "${f4_tmp}/README.md"
git -C "${f4_tmp}" add README.md
git -C "${f4_tmp}" commit -q -m "baseline"
# dirty fixture must refuse requeue
printf '%s\n' 'dirt' > "${f4_tmp}/CRASH-RESIDUE.txt"
if python3 "${SKILLS}/validation-release-gates/scripts/restore-or-refuse-requeue.py" "${f4_tmp}" \
  --terminal crashed >/dev/null 2>&1; then
  echo "FAIL: dirty workspace should refuse requeue after crashed" >&2
  rc=1
else
  echo "OK: F4 dirty fixture refuses requeue (requeue≠restore)"
fi
# restore clears dirt
if python3 "${SKILLS}/validation-release-gates/scripts/restore-or-refuse-requeue.py" "${f4_tmp}" \
  --terminal crashed --action restore --baseline HEAD; then
  echo "OK: F4 restore → workspace_clean"
else
  echo "FAIL: F4 restore should yield clean tree" >&2
  rc=1
fi
python3 "${SKILLS}/validation-release-gates/scripts/check-workspace-clean.py" "${f4_tmp}" || rc=1
unset HERMES_HOME
rm -rf "${f4_tmp}" "${f4_home}"

# SCOPED_ACCEPT gate (finding 3)
python3 "${SKILLS}/validation-release-gates/scripts/check-accept-scope.py" "${ROOT}" || rc=1
printf '%s\n' '{"phase":"M5","verdict":"ACCEPT","accept_kind":"full","entry_point_descope_count":2}' \
  > "${vr_tmp}/migration/verdicts/m5.json"
if python3 "${SKILLS}/validation-release-gates/scripts/check-accept-scope.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: full ACCEPT with descopes should refuse" >&2
  rc=1
else
  echo "OK: full ACCEPT with descopes refused"
fi
printf '%s\n' '{"phase":"M5","verdict":"SCOPED_ACCEPT","accept_kind":"scoped","entry_point_descope_count":2}' \
  > "${vr_tmp}/migration/verdicts/m5.json"
python3 "${SKILLS}/validation-release-gates/scripts/check-accept-scope.py" "${vr_tmp}" || rc=1
rm -rf "${vr_tmp}"

echo "== external_dirs (AD-S relocate) =="
python3 "${SKILLS}/specify-workspace-init/scripts/check-external-dirs.py" "${ROOT}" || rc=1
ed_tmp="$(mktemp -d)"
mkdir -p "${ed_tmp}/.hermes/skills" "${ed_tmp}/cfg"
printf '%s\n' 'skills:' '  external_dirs:' '    - '"${ed_tmp}/.hermes/skills" > "${ed_tmp}/cfg/config.yaml"
if HERMES_HOME="${ed_tmp}/relocated" HERMES_CONFIG="${ed_tmp}/cfg/config.yaml" \
  python3 "${SKILLS}/specify-workspace-init/scripts/check-external-dirs.py" "${ed_tmp}" >/dev/null 2>&1; then
  echo "FAIL: relocated HERMES_HOME missing home skills should refuse" >&2
  rc=1
else
  echo "OK: external_dirs missing home skills refused"
fi
printf '%s\n' 'skills:' '  external_dirs:' '    - '"${ed_tmp}/.hermes/skills" '    - '"${HOME}/.hermes/skills" > "${ed_tmp}/cfg/config.yaml"
HERMES_HOME="${ed_tmp}/relocated" HERMES_CONFIG="${ed_tmp}/cfg/config.yaml" \
  python3 "${SKILLS}/specify-workspace-init/scripts/check-external-dirs.py" "${ed_tmp}" || rc=1
rm -rf "${ed_tmp}"

echo "== kanban-body (W2 §6.1) =="
python3 "${SKILLS}/sdd-readiness/scripts/check-kanban-body.py" "${ROOT}" || rc=1
kb_tmp="$(mktemp -d)"
mkdir -p "${kb_tmp}/migration/bodies"
printf '%s\n' '{"task_id":"T-1","role":"implementer","phase":"M3","refs":[],"files_in_scope":["src/"]}' \
  > "${kb_tmp}/migration/bodies/bad.json"
if python3 "${SKILLS}/sdd-readiness/scripts/check-kanban-body.py" "${kb_tmp}" >/dev/null 2>&1; then
  echo "FAIL: M3 body missing required refs should refuse" >&2
  rc=1
else
  echo "OK: BODY_REF_MISSING refused"
fi
printf '%s\n' '{"task_id":"T-1","role":"implementer","phase":"M3","identity":{"transform_class":"HARVEST","g2_applicability":"not_applicable","operand_count":1,"sizing_basis":"operand_count"},"files_in_scope":["src/Foo.java"],"exit_criteria":[{"check":"compile","cmd":"true","expect":"rc=0"},{"check":"skills","assert":"AD-002E: consult or skills_unused; silence invalid"},{"check":"endpoint_contract","assert":"fixture"}],"refs":[{"key":"brief_identity_ack","path":"migration/acks/brief-identity.ack","sha256":"abc"},{"key":"legacy_locus","path":"projects/legacy/Foo.java","sha256":"def"}]}' \
  > "${kb_tmp}/migration/bodies/bad.json"
python3 "${SKILLS}/sdd-readiness/scripts/check-kanban-body.py" "${kb_tmp}" || rc=1
rm -rf "${kb_tmp}"

echo "== story-sizing operand_count (Architect E-110403Z) =="
python3 "${SKILLS}/sdd-readiness/scripts/check-operand-count.py" "${ROOT}" \
  "${ROOT}/migration/fixtures/story-sizing/ar-size-good.json" || rc=1
if python3 "${SKILLS}/sdd-readiness/scripts/check-operand-count.py" "${ROOT}" \
  "${ROOT}/migration/fixtures/story-sizing/ar-size-bad-missing.json" >/dev/null 2>&1; then
  echo "FAIL: missing operand_count should refuse" >&2
  rc=1
else
  echo "OK: missing operand_count refused"
fi
if python3 "${SKILLS}/sdd-readiness/scripts/check-operand-count.py" "${ROOT}" \
  "${ROOT}/migration/fixtures/story-sizing/ar-size-bad-overcap.json" >/dev/null 2>&1; then
  echo "FAIL: over-cap operand_count should refuse" >&2
  rc=1
else
  echo "OK: over-cap operand_count refused"
fi
python3 "${SKILLS}/sdd-readiness/scripts/check-operand-count.py" "${ROOT}" \
  "${ROOT}/migration/fixtures/story-sizing/ar-size-good.json" --wall-fit || rc=1
if python3 "${SKILLS}/sdd-readiness/scripts/check-operand-count.py" "${ROOT}" \
  "${ROOT}/migration/fixtures/story-sizing/ar-size-bad-wallfit.json" --wall-fit \
  >/dev/null 2>&1; then
  echo "FAIL: wall-fit 60@3600 should refuse" >&2
  rc=1
else
  echo "OK: wall-fit 60@3600 refused"
fi

echo "== wall-as-terminal exit-eval (Architect E-110403Z) =="
wall_tmp="$(mktemp -d)"
mkdir -p "${wall_tmp}/migration/runs/t_fixture_wall"
cp "${ROOT}/migration/fixtures/wall-exit-eval/ar-wall-good/exit-eval.json" \
  "${wall_tmp}/migration/runs/t_fixture_wall/exit-eval.json"
python3 "${SKILLS}/validation-release-gates/scripts/check-wall-exit-eval.py" "${wall_tmp}" \
  --task-id t_fixture_wall --trigger timed_out --require-test-compile || rc=1
if python3 "${SKILLS}/validation-release-gates/scripts/check-wall-exit-eval.py" "${wall_tmp}" \
  --task-id t_missing --trigger timed_out >/dev/null 2>&1; then
  echo "FAIL: missing wall exit-eval should refuse" >&2
  rc=1
else
  echo "OK: missing wall exit-eval refused"
fi
rm -rf "${wall_tmp}"

echo "== checkpoint lag check (Deputy E-121112Z) =="
lag_tmp="$(mktemp -d)"
mkdir -p "${lag_tmp}/migration/runs/t_lag" "${lag_tmp}/src/test/java/com/demo"
printf '%s\n' 'class ATests {}' > "${lag_tmp}/src/test/java/com/demo/ATests.java"
printf '%s\n' '{"schema":"rhoai3.implementer-checkpoint/v1","task_id":"t_lag","body_path":"x","body_sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","work_list":["src/test/java/com/demo/ATests.java"],"completed":[],"next":"src/test/java/com/demo/ATests.java","updated_at":"2026-08-10T00:00:00Z"}' \
  > "${lag_tmp}/migration/runs/t_lag/checkpoint.json"
if python3 "${SKILLS}/auditability-repeatability/scripts/check-test-write-checkpoint-lag.py" \
  "${lag_tmp}/migration/runs/t_lag/checkpoint.json" --root "${lag_tmp}" >/dev/null 2>&1; then
  echo "FAIL: disk lag should refuse" >&2
  rc=1
else
  echo "OK: src/test checkpoint lag refused"
fi
rm -rf "${lag_tmp}"

echo "== #1b test-compile gate on checkpoint stamp (Deputy E-115113Z) =="
tc_tmp="$(mktemp -d)"
mkdir -p "${tc_tmp}/migration/runs/t_tcgate"
printf '%s\n' '{"schema":"rhoai3.implementer-checkpoint/v1","task_id":"t_tcgate","body_path":"x","body_sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","work_list":["src/test/java/com/demo/ATests.java","src/main/java/com/demo/A.java"],"completed":[],"next":"src/test/java/com/demo/ATests.java","updated_at":"2026-08-10T00:00:00Z"}' \
  > "${tc_tmp}/migration/runs/t_tcgate/checkpoint.json"
# No pom at tmp root → stamp must REFUSE (structural gate, not advisory)
if python3 "${SKILLS}/auditability-repeatability/scripts/stamp-implementer-checkpoint.py" \
  "${tc_tmp}/migration/runs/t_tcgate/checkpoint.json" \
  --completed src/test/java/com/demo/ATests.java >/dev/null 2>&1; then
  echo "FAIL: src/test stamp without pom/test-compile should refuse" >&2
  rc=1
else
  echo "OK: src/test checkpoint stamp refused without test-compile gate"
fi
# Fixture skip path still works for shape tests
python3 "${SKILLS}/auditability-repeatability/scripts/stamp-implementer-checkpoint.py" \
  "${tc_tmp}/migration/runs/t_tcgate/checkpoint.json" \
  --completed src/test/java/com/demo/ATests.java --skip-test-compile-gate || rc=1
python3 "${SKILLS}/auditability-repeatability/scripts/check-implementer-checkpoint.py" \
  "${tc_tmp}/migration/runs/t_tcgate/checkpoint.json" || rc=1
rm -rf "${tc_tmp}"

echo "== body-digest immutability (Architect E-111424Z) =="
DIGEST="$(python3 -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path('${ROOT}/migration/fixtures/body-digest/ar-digest-good/body.json').read_bytes()).hexdigest())")"
python3 "${SKILLS}/auditability-repeatability/scripts/check-body-digest-match.py" "${ROOT}" \
  --body "${ROOT}/migration/fixtures/body-digest/ar-digest-good/body.json" \
  --expect "${DIGEST}" || rc=1
if python3 "${SKILLS}/auditability-repeatability/scripts/check-body-digest-match.py" "${ROOT}" \
  --body "${ROOT}/migration/fixtures/body-digest/ar-digest-good/body.json" \
  --expect deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef \
  >/dev/null 2>&1; then
  echo "FAIL: digest mismatch should refuse" >&2
  rc=1
else
  echo "OK: body digest mismatch refused"
fi

echo "== auditability-repeatability (AD-H §19) =="
python3 "${SKILLS}/auditability-repeatability/scripts/check-provenance.py" "${ROOT}" || rc=1
ap_tmp="$(mktemp -d)"
mkdir -p "${ap_tmp}/migration/tasks"
printf '%s\n' '{"id":"T-1","phase":"M3","role":"implementer","status":"done","brief_id":"B-1","ac_ids":["AC-1"],"files_in_scope":["src/"],"deps":[]}' \
  > "${ap_tmp}/migration/tasks/bad.json"
if python3 "${SKILLS}/auditability-repeatability/scripts/check-provenance.py" "${ap_tmp}" >/dev/null 2>&1; then
  echo "FAIL: complete IMPLEMENT without worker_session_id should refuse" >&2
  rc=1
else
  echo "OK: missing worker_session_id refused"
fi
printf '%s\n' '{"id":"T-1","phase":"M3","role":"implementer","status":"done","provenance":{"task_id":"T-1","task_run_id":"1","worker_session_id":"sess1","soul_path":"/tmp/no-such-soul.md","soul_sha":"deadbeef","skill_tips":{"grounded-generation":"abc"},"model_id":"unknown","citations":{"brief_or_story_id":"B-1","legacy_locus":"projects/legacy/Foo.java:1-10"},"artifacts":[]}}' \
  > "${ap_tmp}/migration/tasks/bad.json"
if python3 "${SKILLS}/auditability-repeatability/scripts/check-provenance.py" "${ap_tmp}" >/dev/null 2>&1; then
  echo "FAIL: model_id=unknown without model_id_gap should refuse" >&2
  rc=1
else
  echo "OK: unknown model_id without gap refused"
fi
# Good fixture: write a real soul file and hash it
soul_tmp="$(mktemp)"
printf 'test soul\n' > "${soul_tmp}"
soul_sha="$(python3 -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path('${soul_tmp}').read_bytes()).hexdigest())")"
printf '%s\n' "{\"id\":\"T-1\",\"phase\":\"M3\",\"role\":\"implementer\",\"status\":\"done\",\"provenance\":{\"task_id\":\"T-1\",\"task_run_id\":\"1\",\"campaign_id\":\"fixture\",\"worker_session_id\":\"sess1\",\"soul_path\":\"${soul_tmp}\",\"soul_sha\":\"${soul_sha}\",\"skill_tips\":{\"grounded-generation\":\"abc\"},\"model_id\":\"unknown\",\"model_id_gap\":true,\"citations\":{\"brief_or_story_id\":\"B-1\",\"legacy_locus\":\"projects/legacy/Foo.java:1-10\"},\"artifacts\":[]}}" \
  > "${ap_tmp}/migration/tasks/bad.json"
python3 "${SKILLS}/auditability-repeatability/scripts/check-provenance.py" "${ap_tmp}" || rc=1
rm -f "${soul_tmp}"
# interventions audit
python3 "${ROOT}/.hermes/home/scripts/audit-interventions.py" "${ROOT}" || rc=1
rm -rf "${ap_tmp}"

if [ "${rc}" -ne 0 ]; then
  echo "harness-validate FAILED" >&2
  exit 1
fi
echo "OK: harness-validate passed"
