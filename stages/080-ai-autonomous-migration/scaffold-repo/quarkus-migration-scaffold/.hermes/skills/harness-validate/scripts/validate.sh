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
printf '%s\n' '{"task_id":"T-1","role":"implementer","phase":"M3","files_in_scope":["src/Foo.java"],"refs":[{"key":"brief_identity_ack","path":"migration/acks/brief-identity.ack","sha256":"abc"},{"key":"legacy_locus","path":"projects/legacy/Foo.java","sha256":"def"}]}' \
  > "${kb_tmp}/migration/bodies/bad.json"
python3 "${SKILLS}/sdd-readiness/scripts/check-kanban-body.py" "${kb_tmp}" || rc=1
rm -rf "${kb_tmp}"

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
printf '%s\n' '{"id":"T-1","phase":"M3","role":"implementer","status":"done","provenance":{"task_id":"T-1","worker_session_id":"sess1","soul_sha":"deadbeef","skill_tips":{"grounded-generation":"abc"},"model_id":"unknown","citations":{"brief_or_story_id":"B-1","legacy_locus":"projects/legacy/Foo.java:1-10"},"artifacts":[]}}' \
  > "${ap_tmp}/migration/tasks/bad.json"
if python3 "${SKILLS}/auditability-repeatability/scripts/check-provenance.py" "${ap_tmp}" >/dev/null 2>&1; then
  echo "FAIL: model_id=unknown without model_id_gap should refuse" >&2
  rc=1
else
  echo "OK: unknown model_id without gap refused"
fi
printf '%s\n' '{"id":"T-1","phase":"M3","role":"implementer","status":"done","provenance":{"task_id":"T-1","worker_session_id":"sess1","soul_sha":"deadbeef","skill_tips":{"grounded-generation":"abc"},"model_id":"unknown","model_id_gap":true,"citations":{"brief_or_story_id":"B-1","legacy_locus":"projects/legacy/Foo.java:1-10"},"artifacts":[]}}' \
  > "${ap_tmp}/migration/tasks/bad.json"
python3 "${SKILLS}/auditability-repeatability/scripts/check-provenance.py" "${ap_tmp}" || rc=1
rm -rf "${ap_tmp}"

if [ "${rc}" -ne 0 ]; then
  echo "harness-validate FAILED" >&2
  exit 1
fi
echo "OK: harness-validate passed"
