#!/usr/bin/env bash
# Specimen-free harness validation — skill validate-contracts (AD-H §7).

case "${1:-}" in
  -h|--help)
    cat <<'USAGE'
validate.sh — specimen-free harness validation suite (skill validate-contracts, AD-H S7).

Runs every harness self-check in one pass. Each section prints its own verdict
lines; a single non-zero section makes the whole suite fail. Fixture
and temp-tree probes are used throughout so the suite never depends on a
particular specimen being present.

Arguments:
  none. The scaffold root and the skills root are both derived from this
  script's own location, and the suite cd's to the scaffold root before
  running. There are no section selectors and no output-format flags.

  -h, --help   print this usage and exit 0

Sections covered (in order):
  no .hermes.md / HERMES.md override      check-spec-readiness (+ S.6)
  check-domain-parity admission (W2 S10)         G-1 PIT dry-run parse
  AR-3.6 G-1 acceptance operand           scan-with-mta findings schema
  inventory-entry-points smoke            enforce-authority-boundary (AD-H S16)
  ack/comment authority (S16.5/AR-1.1-1.2) write-fence proving-min (S16.4/F2)
  ground-in-harvest (AD-H S17)          check-release-readiness (AD-H S18)
  workspace recovery proving-min (S5.1/F4) external_dirs (AD-S relocate)
  kanban-body (W2 S6.1)                   story-sizing operand_count
  wall-as-terminal exit-eval              checkpoint lag check
  #1b test-compile gate on checkpoint      body-digest immutability
  record-run-evidence (AD-H S19)   R-M3.5-8 POM / dependency_wait
  CS-7 m3-implementer bundle assert        BANK-DEST-INV-HARDINVOKE-1 (RW-2)
  AD-011 skill extension overlay           R-SK.12 script CLI contract
  CS-7 bundle exists-assert                CS-9 skill conformance
  R-M3.9-13 wall-fit + JDBC

Examples:
  bash .hermes/enforcement/validate-contracts/scripts/validate.sh
  bash .hermes/enforcement/validate-contracts/scripts/validate.sh --help

Exit codes:
  0  pass — every section passed ("OK: validate-contracts passed")
  1  BLOCK — one or more sections failed ("validate-contracts FAILED" on stderr)
  2  usage error (unexpected argument)
USAGE
    exit 0
    ;;
  "")
    ;;
  *)
    printf 'Error: this script takes no arguments. Received: "%s". Usage: %s [--help]\n' \
      "$1" "$(basename "$0")" >&2
    exit 2
    ;;
esac

set -euo pipefail
# Layout after Wave B: this package lives under .hermes/enforcement/, not
# .hermes/skills/harness/. Guidance skills remain under .hermes/skills/.
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENFORCEMENT="$(cd "${SKILL_DIR}/.." && pwd)"
ROOT="$(cd "${SKILL_DIR}/../../.." && pwd)"
SKILLS="$(cd "${ROOT}/.hermes/skills" && pwd)"
cd "${ROOT}"
rc=0

echo "== no .hermes.md / HERMES.md override (was scaffold-invariants) =="
bash "${ENFORCEMENT}/validate-contracts/scripts/check-no-hermes-context-override.sh" || rc=1

echo "== check-spec-readiness (+ §S.6) =="
bash "${SKILLS}/sdd/check-spec-readiness/scripts/check-readiness.sh" || rc=1
sdd_tmp="$(mktemp -d)"
mkdir -p "${sdd_tmp}/evidence/tasks" "${sdd_tmp}/evidence/briefs"
printf '%s\n' '## Non-Goals' '- NG-001: x' > "${sdd_tmp}/evidence/briefs/b.md"
printf '%s\n' '{"id":"t_a1b2c3d4e5","phase":"M3","replan":true,"ac_ids":["AC-1"],"files_in_scope":["src/"],"deps":[],"brief_id":"B-1"}' \
  > "${sdd_tmp}/evidence/tasks/bad.json"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-ordering.py" "${sdd_tmp}" >/dev/null 2>&1; then
  echo "FAIL: §S.6 should refuse IMPLEMENT replan" >&2
  rc=1
else
  echo "OK: §S.6 refuses IMPLEMENT replan"
fi
printf '%s\n' '{"id":"t_a1b2c3d4e5","phase":"M3","ac_ids":["AC-1"],"files_in_scope":["src/"],"deps":[],"brief_id":"B-1"}' \
  > "${sdd_tmp}/evidence/tasks/bad.json"
python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-ordering.py" "${sdd_tmp}" || rc=1
rm -rf "${sdd_tmp}"

echo "== check-domain-parity admission (W2 §10) =="
bash "${SKILLS}/gates/check-domain-parity/scripts/run-admission.sh" "${ROOT}" || rc=1

# Parser/fixture only — not live specimen admission (Architect E-20260808T080815Z #3).
echo "== G-1 PIT dry-run parse (R1 pin; not live admission) =="
python3 "${SKILLS}/gates/check-domain-parity/scripts/parse-pit-mutations.py" \
  "${ROOT}/governance/fixtures/pit-dry-run/mutations.xml" || rc=1
if python3 "${SKILLS}/gates/check-domain-parity/scripts/parse-pit-mutations.py" \
  "${ROOT}/governance/fixtures/pit-dry-run/missing.xml" >/dev/null 2>&1; then
  echo "FAIL: missing mutations.xml should refuse" >&2
  rc=1
else
  echo "OK: missing mutations.xml refused"
fi

echo "== AR-3.6 G-1 acceptance operand (probe ≠ acceptance) =="
# Fixture-driven: the golden scaffold ships no tests at all (they are purged as
# run-state contamination), so asserting against ${ROOT} could only ever prove
# "empty tree refuses". Build the three operand shapes in a temp tree instead —
# same pattern as every other check in this file.
g1op_tmp="$(mktemp -d)"
g1op="${SKILLS}/gates/check-domain-parity/scripts/check-g1-acceptance-operand.py"
mkdir -p "${g1op_tmp}/src/test/java/com/demo/harness"
# (a) no tests at all → refuse under either operand
if python3 "${g1op}" "${g1op_tmp}" >/dev/null 2>&1; then
  echo "FAIL: AR-3.6 empty test tree should refuse acceptance operand" >&2
  rc=1
else
  echo "OK: AR-3.6 empty test tree refused"
fi
# (b) harness-only probe tests → refuse as acceptance
printf '%s\n' 'package com.demo.harness; class ProbeTest {}' \
  > "${g1op_tmp}/src/test/java/com/demo/harness/ProbeTest.java"
if python3 "${g1op}" "${g1op_tmp}" >/dev/null 2>&1; then
  echo "FAIL: probe-only tree should refuse acceptance operand" >&2
  rc=1
else
  echo "OK: AR-3.6 probe-only acceptance refused"
fi
# (c) same tree under tooling_smoke → permitted, explicitly NOT acceptance
if G1_OPERAND=tooling_smoke python3 "${g1op}" "${g1op_tmp}" >/dev/null; then
  echo "OK: AR-3.6 tooling_smoke harness path permitted (non-acceptance)"
else
  echo "FAIL: tooling_smoke should allow harness-only" >&2
  rc=1
fi
# (d) a real product test → acceptance operand satisfied
mkdir -p "${g1op_tmp}/src/test/java/com/example/app"
printf '%s\n' 'package com.example.app; class ServiceTest {}' \
  > "${g1op_tmp}/src/test/java/com/example/app/ServiceTest.java"
python3 "${g1op}" "${g1op_tmp}" >/dev/null || { echo "FAIL: product test should satisfy G-1 acceptance operand" >&2; rc=1; }
rm -rf "${g1op_tmp}"


echo "== scan-with-mta findings schema (fixture known-good) =="
python3 "${SKILLS}/analysis/scan-with-mta/scripts/validate-findings-schema.py" \
  governance/fixtures/admission/g3-findings-delta/known-good/mta-findings.json || rc=1

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
python3 "${SKILLS}/analysis/inventory-entry-points/scripts/inventory-entry-points.py" \
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

echo "== enforce-authority-boundary (AD-H §16) =="
bash "${ENFORCEMENT}/enforce-authority-boundary/scripts/check-acks.sh" M1 "${ROOT}" || rc=1
# M2 without ack must fail
if bash "${ENFORCEMENT}/enforce-authority-boundary/scripts/check-acks.sh" M2 "${ROOT}" >/dev/null 2>&1; then
  echo "FAIL: M2 should require m1-findings ack when absent" >&2
  rc=1
else
  echo "OK: M2 refuses without m1-findings ack"
fi
# check-role-writes.py retired (Architect E-20260813T144117Z) — scope refuse is
# check-write-fence.py --body (files_in_scope); global deny via write fence.

echo "== ack/comment authority (AD-H §16.5 / AR-1.1 / AR-1.2) =="
# fixture feed must refuse impersonating override
if python3 "${ENFORCEMENT}/enforce-authority-boundary/scripts/check-comment-authority.py" "${ROOT}" >/dev/null 2>&1; then
  echo "FAIL: AR-1.2 impersonating override fixture should refuse" >&2
  rc=1
else
  echo "OK: AR-1.2 impersonating comment refused"
fi
ar11_tmp="$(mktemp -d)"
mkdir -p "${ar11_tmp}/evidence/acks"
printf '%s\n' '{"kind":"migration-ack","ack_type":"brief-identity","status":"acknowledged","acknowledged_by":"planner (M2)","acknowledged_at":"2026-08-09T17:00:00Z"}' \
  > "${ar11_tmp}/evidence/acks/brief-identity.json"
if python3 "${ENFORCEMENT}/enforce-authority-boundary/scripts/check-ack-authority.py" "${ar11_tmp}" >/dev/null 2>&1; then
  echo "FAIL: AR-1.1 planner self-ACK should refuse" >&2
  rc=1
else
  echo "OK: AR-1.1 planner self-ACK refused"
fi
printf '%s\n' '{"kind":"migration-ack","ack_type":"brief-identity","status":"acknowledged","acknowledged_by":"Operator","acknowledged_at":"2026-08-10T00:00:00Z","task_id":"t_demo","artifact_digests":{"brief":"abc"}}' \
  > "${ar11_tmp}/evidence/acks/brief-identity.ack.json"
rm -f "${ar11_tmp}/evidence/acks/brief-identity.json"
python3 "${ENFORCEMENT}/enforce-authority-boundary/scripts/check-ack-authority.py" "${ar11_tmp}" || rc=1
rm -rf "${ar11_tmp}"

echo "== write-fence proving-min (AD-H §16.4 / F2) =="
fence_tmp="$(mktemp -d)"
mkdir -p "${fence_tmp}/evidence/acks" "${fence_tmp}/evidence/verdicts" \
  "${fence_tmp}/.hermes/skills" "${fence_tmp}/governance/fixtures" \
  "${fence_tmp}/src/main/java"
printf '%s\n' 'ok' > "${fence_tmp}/evidence/acks/README.md"
printf '%s\n' 'ok' > "${fence_tmp}/governance/fixtures/keep.txt"
bash "${ENFORCEMENT}/enforce-authority-boundary/scripts/apply-write-fence.sh" "${fence_tmp}" lock || rc=1
if python3 "${ENFORCEMENT}/enforce-authority-boundary/scripts/probe-write-fence.py" "${fence_tmp}"; then
  echo "OK: F2 seat probe PASS on temp tree"
else
  echo "FAIL: F2 seat probe" >&2
  rc=1
fi
# scope refuse smoke
printf '%s\n' '{"files_in_scope":["src/main/java/Foo.java"]}' > "${fence_tmp}/body.json"
printf '%s\n' 'x' > "${fence_tmp}/src/main/java/OutOfScope.java"
if python3 "${ENFORCEMENT}/enforce-authority-boundary/scripts/check-write-fence.py" "${fence_tmp}" \
  --no-git-status --body "${fence_tmp}/body.json" \
  --writes src/main/java/OutOfScope.java evidence/acks/forged.json >/dev/null 2>&1; then
  echo "FAIL: write-fence should refuse OOS + ack forge" >&2
  rc=1
else
  echo "OK: write-fence refuses OOS + deny-path writes"
fi
bash "${ENFORCEMENT}/enforce-authority-boundary/scripts/apply-write-fence.sh" "${fence_tmp}" unlock >/dev/null || true
rm -rf "${fence_tmp}"

echo "== ground-in-harvest (AD-H §17) =="
python3 "${ENFORCEMENT}/ground-in-harvest/scripts/check-citation.py" "${ROOT}" || rc=1
gg_tmp="$(mktemp -d)"
mkdir -p "${gg_tmp}/evidence/tasks"
# invent-without-locus: writes without legacy_locus
printf '%s\n' '{"id":"T-bad","phase":"M3","role":"implementer","brief_id":"B-1","ac_ids":["AC-1"],"files_in_scope":["src/"],"deps":[],"writes":["src/X.java"]}' \
  > "${gg_tmp}/evidence/tasks/bad.json"
if python3 "${ENFORCEMENT}/ground-in-harvest/scripts/check-citation.py" "${gg_tmp}" >/dev/null 2>&1; then
  echo "FAIL: invent-without-locus should refuse" >&2
  rc=1
else
  echo "OK: invent-without-locus refused"
fi
# good non-trivial packet
printf '%s\n' '{"id":"t_a1b2c3d4e5","phase":"M3","role":"implementer","brief_id":"B-1","ac_ids":["AC-1"],"files_in_scope":["src/"],"deps":[],"legacy_locus":"projects/legacy/Foo.java:10-40","writes":["src/Foo.java"]}' \
  > "${gg_tmp}/evidence/tasks/bad.json"
python3 "${ENFORCEMENT}/ground-in-harvest/scripts/check-citation.py" "${gg_tmp}" || rc=1
# commit message lint
printf '%s\n' 't_a1b2c3d4e5: port Foo (brief B-1; legacy projects/legacy/Foo.java:10-40)' > "${gg_tmp}/msg.txt"
python3 "${ENFORCEMENT}/ground-in-harvest/scripts/check-citation.py" "${gg_tmp}" --commit-msg "${gg_tmp}/msg.txt" || rc=1
printf '%s\n' 'fix formatting' > "${gg_tmp}/msg-bad.txt"
if python3 "${ENFORCEMENT}/ground-in-harvest/scripts/check-citation.py" "${gg_tmp}" --commit-msg "${gg_tmp}/msg-bad.txt" >/dev/null 2>&1; then
  echo "FAIL: commit without task id should refuse" >&2
  rc=1
else
  echo "OK: commit without task id refused"
fi
rm -rf "${gg_tmp}"

echo "== check-release-readiness (AD-H §18) =="
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-phase-matrix.py" "${ROOT}" || rc=1
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${ROOT}" || rc=1
# B8 — check-semantics-manifest (governance/contracts/check-semantics-manifest.md)
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-semantics-manifest.py" "${ROOT}" || rc=1
# Quarkus platform pin ↔ pom (manage-quarkus-extensions) — Wave B: skip until bootstrap
if [ -f "${ROOT}/pom.xml" ]; then
  python3 "${SKILLS}/migration/manage-quarkus-extensions/scripts/check-pom-platform-pins.py" "${ROOT}" || rc=1
else
  echo "OK: no destination pom yet (BOOTSTRAP.md / bootstrap-quarkus-project)"
  [ -f "${ROOT}/BOOTSTRAP.md" ] || { echo "FAIL: missing pom.xml and BOOTSTRAP.md" >&2; rc=1; }
fi
# A2 / runnable-db-security — fixture refuse paths (scaffold root may fail until B3)
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-runnable-db-config.py" \
  "${ROOT}/governance/fixtures/runnable-db-security/bad-hsqldb-destination" >/dev/null 2>&1; then
  echo "FAIL: B7 HSQLDB destination should refuse" >&2
  rc=1
else
  echo "OK: B7 HSQLDB destination refused"
fi
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-empty-security.py" \
  "${ROOT}/governance/fixtures/runnable-db-security/bad-placeholder-security" >/dev/null 2>&1; then
  echo "FAIL: AR-2.2 placeholder security should refuse" >&2
  rc=1
else
  echo "OK: AR-2.2 placeholder security refused"
fi
# S-008 resurrection order (create/remint path)
python3 "${ENFORCEMENT}/dispatch-phase/scripts/check-s008-resurrection-order.py" "${ROOT}" || rc=1
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-semantics-manifest.py" \
  "${ROOT}/governance/fixtures/check-semantics-manifest/bad-endpoint-smoke-overpromise" >/dev/null 2>&1; then
  echo "FAIL: B8 narrowed smoke should refuse endpoint_smoke id" >&2
  rc=1
else
  echo "OK: B8 endpoint_smoke over-promise refused"
fi
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-semantics-manifest.py" \
  "${ROOT}/governance/fixtures/check-semantics-manifest/good-endpoint-smoke-health" || rc=1
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-semantics-manifest.py" \
  "${ROOT}/governance/fixtures/check-semantics-manifest/bad-boot-health-skipped-package" >/dev/null 2>&1; then
  echo "FAIL: B8 boot_health skipped package should refuse" >&2
  rc=1
else
  echo "OK: B8 boot_health skipped package refused"
fi
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-semantics-manifest.py" \
  "${ROOT}/governance/fixtures/check-semantics-manifest/good-boot-health" || rc=1
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-semantics-manifest.py" \
  "${ROOT}/governance/fixtures/check-semantics-manifest/bad-g4-sample-as-product-closed" >/dev/null 2>&1; then
  echo "FAIL: B8 SAMPLE g4_hook→product closed should refuse" >&2
  rc=1
else
  echo "OK: B8 SAMPLE g4 product-closed refused"
fi
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-semantics-manifest.py" \
  "${ROOT}/governance/fixtures/check-semantics-manifest/bad-mvn-verify-no-clean" >/dev/null 2>&1; then
  echo "FAIL: B8 mvn_clean_verify without clean should refuse" >&2
  rc=1
else
  echo "OK: B8 mvn verify without clean refused"
fi
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-semantics-manifest.py" \
  "${ROOT}/governance/fixtures/check-semantics-manifest/bad-unit-it-zero-tests" >/dev/null 2>&1; then
  echo "FAIL: B8 unit_it_contract zero tests PASS should refuse" >&2
  rc=1
else
  echo "OK: B8 unit_it zero-test PASS refused"
fi
vr_tmp="$(mktemp -d)"
mkdir -p "${vr_tmp}/evidence/verdicts"
printf '%s\n' '{"phase":"M5","verdict":"INCONCLUSIVE","ship":true}' > "${vr_tmp}/evidence/verdicts/bad.json"
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: INCONCLUSIVE ship should refuse" >&2
  rc=1
else
  echo "OK: INCONCLUSIVE ship refused"
fi
# §18.0 — ACCEPT+provisional footnote refused at M4
printf '%s\n' '{"phase":"M4","verdict":"ACCEPT","accept_kind":"provisional","g1_kill_ratio":"pending_threshold","ship":false}' \
  > "${vr_tmp}/evidence/verdicts/bad.json"
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: M4 ACCEPT+provisional footnote should refuse" >&2
  rc=1
else
  echo "OK: M4 ACCEPT+provisional footnote refused"
fi
# §18.0 — PROVISIONAL_ACCEPT must not ship
printf '%s\n' '{"phase":"M4","verdict":"PROVISIONAL_ACCEPT","g1_kill_ratio":"pending_threshold","ship":true}' \
  > "${vr_tmp}/evidence/verdicts/bad.json"
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: PROVISIONAL_ACCEPT ship should refuse" >&2
  rc=1
else
  echo "OK: PROVISIONAL_ACCEPT ship refused"
fi
# §18.0 — kill-ratio PASS without pin refused
printf '%s\n' '{"phase":"M4","verdict":"PROVISIONAL_ACCEPT","g1_kill_ratio":"PASS","ship":false}' \
  > "${vr_tmp}/evidence/verdicts/bad.json"
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: g1_kill_ratio=PASS without pin should refuse" >&2
  rc=1
else
  echo "OK: unpinned kill-ratio PASS refused"
fi
# good M4 PROVISIONAL_ACCEPT
printf '%s\n' '{"phase":"M4","verdict":"PROVISIONAL_ACCEPT","g1_kill_ratio":"pending_threshold","ship":false}' \
  > "${vr_tmp}/evidence/verdicts/bad.json"
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${vr_tmp}" || rc=1
# good M5 full with waiver (threshold not yet pinned)
printf '%s\n' '{"phase":"M5","verdict":"ACCEPT","g1_kill_ratio":"pending_threshold","g1_kill_ratio_waiver":true,"ship":true,"routing":"close"}' \
  > "${vr_tmp}/evidence/verdicts/bad.json"
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${vr_tmp}" || rc=1
# single-unit composition reopen
printf '%s\n' '{"phase":"M5","verdict":"REFUSE","gate":"g4_runtime_parity","prior_verdict":"PROVISIONAL_ACCEPT","routing":"reopen_story"}' \
  > "${vr_tmp}/evidence/verdicts/bad.json"
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${vr_tmp}" || rc=1
# shared-substrate reopen (fixture closure map)
mkdir -p "${vr_tmp}/evidence/slices"
cp "${ROOT}/governance/fixtures/substrate-reopen/closure-map.json" \
  "${vr_tmp}/evidence/slices/closure-map.json"
printf '%s\n' '{"phase":"M5","verdict":"REFUSE","gate":"g4_runtime_parity","story_id":"S-1","prior_verdict":"PROVISIONAL_ACCEPT","implicated_substrate":["com.example.shared.Entity"],"reopen_story_ids":["S-1","S-2"],"routing":"reopen_story"}' \
  > "${vr_tmp}/evidence/verdicts/bad.json"
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${vr_tmp}" || rc=1
# wrong reopen set refused
printf '%s\n' '{"phase":"M5","verdict":"REFUSE","gate":"g4_runtime_parity","story_id":"S-1","implicated_substrate":["com.example.shared.Entity"],"reopen_story_ids":["S-1"],"routing":"reopen_story"}' \
  > "${vr_tmp}/evidence/verdicts/bad.json"
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: under-sized reopen set should refuse" >&2
  rc=1
else
  echo "OK: under-sized substrate reopen set refused"
fi
printf '%s\n' '{"phase":"M4","verdict":"REFUSE","routing":"auto_fix"}' > "${vr_tmp}/evidence/verdicts/bad.json"
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${vr_tmp}" || rc=1
# factory M5 oracle
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-factory-m5.py" "${ROOT}" || rc=1
mkdir -p "${vr_tmp}/evidence/preflight" "${vr_tmp}/evidence/verdicts"
printf '%s\n' '{"phase":"factory","status":"factory_ready"}' > "${vr_tmp}/evidence/preflight/factory.json"
rm -f "${vr_tmp}/evidence/verdicts/"*.json
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-factory-m5.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: factory without M5 ACCEPT should refuse" >&2
  rc=1
else
  echo "OK: factory without M5 ACCEPT refused"
fi
printf '%s\n' '{"phase":"M5","verdict":"PROVISIONAL_ACCEPT","g1_kill_ratio":"pending_threshold"}' \
  > "${vr_tmp}/evidence/verdicts/m5.json"
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-factory-m5.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: factory with PROVISIONAL_ACCEPT should refuse" >&2
  rc=1
else
  echo "OK: factory PROVISIONAL_ACCEPT refused"
fi
printf '%s\n' '{"phase":"M5","verdict":"ACCEPT","g1_kill_ratio":"pending_threshold","g1_kill_ratio_waiver":true}' \
  > "${vr_tmp}/evidence/verdicts/m5.json"
# Self-reported waiver alone must refuse (Deputy E-20260813T144954Z P1)
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-factory-m5.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: factory with self-reported g1_kill_ratio_waiver should refuse" >&2
  rc=1
else
  echo "OK: factory self-reported kill-ratio waiver refused"
fi
# P0 — empty touch'd m5-accept.ack must NOT count as ACCEPT (Deputy E-20260813T151402Z)
rm -f "${vr_tmp}/evidence/verdicts/"*.json
mkdir -p "${vr_tmp}/evidence/acks"
: > "${vr_tmp}/evidence/acks/m5-accept.ack"
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-factory-m5.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: empty touch m5-accept.ack must not satisfy factory ship gate" >&2
  rc=1
else
  echo "OK: empty touch m5-accept.ack refused (P0)"
fi
mkdir -p "${vr_tmp}/evidence/acks"
cat > "${vr_tmp}/evidence/acks/g1-kill-ratio-waiver-S-1.ack.yaml" <<'ACK'
kind: migration-ack
ack_type: g1-kill-ratio-waiver
status: acknowledged
acknowledged_by: Operator
acknowledged_at: "2026-08-13T00:00:00Z"
ACK
# Proper M5 verdict + typed waiver → pass
printf '%s\n' '{"phase":"M5","verdict":"ACCEPT","accept_kind":"full","g1_kill_ratio":"pending_threshold"}' \
  > "${vr_tmp}/evidence/verdicts/m5.json"
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-factory-m5.py" "${vr_tmp}" || rc=1
# candidate→promote (finding 4)
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-candidate-promote.py" "${ROOT}" || rc=1
printf '%s\n' '{"phase":"factory","status":"push_main","promoted_to_main":true,"factory_result":"fail"}' \
  > "${vr_tmp}/evidence/preflight/factory.json"
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-candidate-promote.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: promote without candidate_sha / on factory fail should refuse" >&2
  rc=1
else
  echo "OK: illegal promote refused"
fi
printf '%s\n' '{"phase":"factory","status":"factory_ready","candidate_sha":"abcdef1","factory_result":"pass","promoted_to_main":false}' \
  > "${vr_tmp}/evidence/preflight/factory.json"
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-candidate-promote.py" "${vr_tmp}" || rc=1
# side-effect recovery idle + persisted-data idle
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-side-effect-recovery.py" "${ROOT}" || rc=1
python3 "${SKILLS}/gates/check-domain-parity/scripts/check-persisted-data-contract.py" "${ROOT}" || rc=1

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
if python3 "${SKILLS}/gates/check-release-readiness/scripts/restore-or-refuse-requeue.py" "${f4_tmp}" \
  --terminal crashed >/dev/null 2>&1; then
  echo "FAIL: dirty workspace should refuse requeue after crashed" >&2
  rc=1
else
  echo "OK: F4 dirty fixture refuses requeue (requeue≠restore)"
fi
# restore clears dirt
if python3 "${SKILLS}/gates/check-release-readiness/scripts/restore-or-refuse-requeue.py" "${f4_tmp}" \
  --terminal crashed --action restore --baseline HEAD; then
  echo "OK: F4 restore → workspace_clean"
else
  echo "FAIL: F4 restore should yield clean tree" >&2
  rc=1
fi
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-workspace-clean.py" "${f4_tmp}" || rc=1
unset HERMES_HOME
rm -rf "${f4_tmp}" "${f4_home}"

# SCOPED_ACCEPT gate (finding 3)
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-accept-scope.py" "${ROOT}" || rc=1
printf '%s\n' '{"phase":"M5","verdict":"ACCEPT","accept_kind":"full","entry_point_descope_count":2}' \
  > "${vr_tmp}/evidence/verdicts/m5.json"
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-accept-scope.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: full ACCEPT with descopes should refuse" >&2
  rc=1
else
  echo "OK: full ACCEPT with descopes refused"
fi
printf '%s\n' '{"phase":"M5","verdict":"SCOPED_ACCEPT","accept_kind":"scoped","entry_point_descope_count":2}' \
  > "${vr_tmp}/evidence/verdicts/m5.json"
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-accept-scope.py" "${vr_tmp}" || rc=1
rm -rf "${vr_tmp}"

echo "== external_dirs (AD-S relocate) =="
python3 "${SKILLS}/sdd/init-spec-workspace/scripts/check-external-dirs.py" "${ROOT}" || rc=1
ed_tmp="$(mktemp -d)"
mkdir -p "${ed_tmp}/.hermes/skills" "${ed_tmp}/cfg"
printf '%s\n' 'skills:' '  external_dirs:' '    - '"${ed_tmp}/.hermes/skills" > "${ed_tmp}/cfg/config.yaml"
if HERMES_HOME="${ed_tmp}/relocated" HERMES_CONFIG="${ed_tmp}/cfg/config.yaml" \
  python3 "${SKILLS}/sdd/init-spec-workspace/scripts/check-external-dirs.py" "${ed_tmp}" >/dev/null 2>&1; then
  echo "FAIL: relocated HERMES_HOME missing home skills should refuse" >&2
  rc=1
else
  echo "OK: external_dirs missing home skills refused"
fi
printf '%s\n' 'skills:' '  external_dirs:' '    - '"${ed_tmp}/.hermes/skills" '    - '"${HOME}/.hermes/skills" > "${ed_tmp}/cfg/config.yaml"
HERMES_HOME="${ed_tmp}/relocated" HERMES_CONFIG="${ed_tmp}/cfg/config.yaml" \
  python3 "${SKILLS}/sdd/init-spec-workspace/scripts/check-external-dirs.py" "${ed_tmp}" || rc=1
rm -rf "${ed_tmp}"

echo "== kanban-body (W2 §6.1) =="
python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-kanban-body.py" "${ROOT}" || rc=1
kb_tmp="$(mktemp -d)"
mkdir -p "${kb_tmp}/evidence/bodies"
printf '%s\n' '{"task_id":"t_a1b2c3d4e5","role":"implementer","phase":"M3","refs":[],"files_in_scope":["src/"]}' \
  > "${kb_tmp}/evidence/bodies/bad.json"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-kanban-body.py" "${kb_tmp}" >/dev/null 2>&1; then
  echo "FAIL: M3 body missing required refs should refuse" >&2
  rc=1
else
  echo "OK: BODY_REF_MISSING refused"
fi
printf '%s\n' '{"task_id":"t_a1b2c3d4e5","role":"implementer","phase":"M3","identity":{"transform_class":"HARVEST","g2_applicability":"not_applicable","operand_count":1,"sizing_basis":"operand_count"},"files_in_scope":["src/Foo.java"],"exit_criteria":[{"check":"compile","cmd":"true","expect":"rc=0"},{"check":"skills","assert":"AD-002E: consult or skills_unused; silence invalid"},{"check":"endpoint_contract","assert":"fixture"}],"refs":[{"key":"brief_identity_ack","path":"evidence/acks/brief-identity.ack","sha256":"pending"},{"key":"legacy_locus","path":"projects/legacy/Foo.java","sha256":"0000000000000000000000000000000000000000000000000000000000000000"}]}' \
  > "${kb_tmp}/evidence/bodies/bad.json"
python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-kanban-body.py" "${kb_tmp}" || rc=1
# Deputy E-20260811T131200Z — prose in sha256 slots must refuse
printf '%s\n' '{"task_id":"t_a1b2c3d4e5","role":"implementer","phase":"M3","identity":{"transform_class":"HARVEST","g2_applicability":"not_applicable","operand_count":1,"sizing_basis":"operand_count"},"files_in_scope":["src/Foo.java"],"exit_criteria":[{"check":"compile","cmd":"true","expect":"rc=0"},{"check":"skills","assert":"AD-002E: consult or skills_unused; silence invalid"},{"check":"endpoint_contract","assert":"fixture"}],"refs":[{"key":"brief_identity_ack","path":"evidence/acks/brief-identity.ack","sha256":"pending"},{"key":"legacy_locus","path":"projects/legacy/Foo.java","sha256":"see-harvest-referent"}]}' \
  > "${kb_tmp}/evidence/bodies/bad.json"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-kanban-body.py" "${kb_tmp}" >/dev/null 2>&1; then
  echo "FAIL: non-hex sha256 prose should refuse" >&2
  rc=1
else
  echo "OK: BODY_REF_SHA256 refused non-hex prose"
fi
rm -rf "${kb_tmp}"

echo "== story-sizing operand_count (Architect E-110403Z) =="
python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-operand-count.py" "${ROOT}" \
  "${ROOT}/governance/fixtures/story-sizing/ar-size-good.json" || rc=1
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-operand-count.py" "${ROOT}" \
  "${ROOT}/governance/fixtures/story-sizing/ar-size-bad-missing.json" >/dev/null 2>&1; then
  echo "FAIL: missing operand_count should refuse" >&2
  rc=1
else
  echo "OK: missing operand_count refused"
fi
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-operand-count.py" "${ROOT}" \
  "${ROOT}/governance/fixtures/story-sizing/ar-size-bad-overcap.json" >/dev/null 2>&1; then
  echo "FAIL: over-cap operand_count should refuse" >&2
  rc=1
else
  echo "OK: over-cap operand_count refused"
fi
python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-operand-count.py" "${ROOT}" \
  "${ROOT}/governance/fixtures/story-sizing/ar-size-good.json" --wall-fit || rc=1
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-operand-count.py" "${ROOT}" \
  "${ROOT}/governance/fixtures/story-sizing/ar-size-bad-wallfit.json" --wall-fit \
  >/dev/null 2>&1; then
  echo "FAIL: wall-fit 60@3600 should refuse" >&2
  rc=1
else
  echo "OK: wall-fit 60@3600 refused"
fi

echo "== wall-as-terminal exit-eval (Architect E-110403Z) =="
wall_tmp="$(mktemp -d)"
mkdir -p "${wall_tmp}/evidence/runs/t_fixture_wall"
cp "${ROOT}/governance/fixtures/wall-exit-eval/ar-wall-good/exit-eval.json" \
  "${wall_tmp}/evidence/runs/t_fixture_wall/exit-eval.json"
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-wall-exit-eval.py" "${wall_tmp}" \
  --task-id t_fixture_wall --trigger timed_out --require-test-compile || rc=1
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-wall-exit-eval.py" "${wall_tmp}" \
  --task-id t_missing --trigger timed_out >/dev/null 2>&1; then
  echo "FAIL: missing wall exit-eval should refuse" >&2
  rc=1
else
  echo "OK: missing wall exit-eval refused"
fi
rm -rf "${wall_tmp}"

echo "== checkpoint lag check (Deputy E-121112Z) =="
lag_tmp="$(mktemp -d)"
mkdir -p "${lag_tmp}/evidence/runs/t_lag" "${lag_tmp}/src/test/java/com/demo"
printf '%s\n' 'class ATests {}' > "${lag_tmp}/src/test/java/com/demo/ATests.java"
printf '%s\n' '{"schema":"rhoai3.implementer-checkpoint/v1","task_id":"t_lag","body_path":"x","body_sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","work_list":["src/test/java/com/demo/ATests.java"],"completed":[],"next":"src/test/java/com/demo/ATests.java","updated_at":"2026-08-10T00:00:00Z"}' \
  > "${lag_tmp}/evidence/runs/t_lag/checkpoint.json"
if python3 "${ENFORCEMENT}/record-run-evidence/scripts/check-test-write-checkpoint-lag.py" \
  "${lag_tmp}/evidence/runs/t_lag/checkpoint.json" --root "${lag_tmp}" >/dev/null 2>&1; then
  echo "FAIL: disk lag should refuse" >&2
  rc=1
else
  echo "OK: src/test checkpoint lag refused"
fi
rm -rf "${lag_tmp}"

echo "== #1b test-compile gate on checkpoint stamp (Deputy E-115113Z) =="
tc_tmp="$(mktemp -d)"
mkdir -p "${tc_tmp}/evidence/runs/t_tcgate"
printf '%s\n' '{"schema":"rhoai3.implementer-checkpoint/v1","task_id":"t_tcgate","body_path":"x","body_sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","work_list":["src/test/java/com/demo/ATests.java","src/main/java/com/demo/A.java"],"completed":[],"next":"src/test/java/com/demo/ATests.java","updated_at":"2026-08-10T00:00:00Z"}' \
  > "${tc_tmp}/evidence/runs/t_tcgate/checkpoint.json"
# No pom at tmp root → stamp must REFUSE (structural gate, not advisory)
if python3 "${ENFORCEMENT}/record-run-evidence/scripts/stamp-implementer-checkpoint.py" \
  "${tc_tmp}/evidence/runs/t_tcgate/checkpoint.json" \
  --completed src/test/java/com/demo/ATests.java >/dev/null 2>&1; then
  echo "FAIL: src/test stamp without pom/test-compile should refuse" >&2
  rc=1
else
  echo "OK: src/test checkpoint stamp refused without test-compile gate"
fi
# Fixture skip path still works for shape tests (env-gated; live seats FORBIDDEN)
if python3 "${ENFORCEMENT}/record-run-evidence/scripts/stamp-implementer-checkpoint.py" \
  "${tc_tmp}/evidence/runs/t_tcgate/checkpoint.json" \
  --completed src/test/java/com/demo/ATests.java --skip-test-compile-gate >/dev/null 2>&1; then
  echo "FAIL: --skip-test-compile-gate without fixture env should refuse" >&2
  rc=1
else
  echo "OK: live skip-test-compile-gate refused without fixture env"
fi
RHOAI3_FIXTURE_ALLOW_SKIP_TEST_COMPILE=1 \
python3 "${ENFORCEMENT}/record-run-evidence/scripts/stamp-implementer-checkpoint.py" \
  "${tc_tmp}/evidence/runs/t_tcgate/checkpoint.json" \
  --completed src/test/java/com/demo/ATests.java --skip-test-compile-gate || rc=1
python3 "${ENFORCEMENT}/record-run-evidence/scripts/check-implementer-checkpoint.py" \
  "${tc_tmp}/evidence/runs/t_tcgate/checkpoint.json" || rc=1
rm -rf "${tc_tmp}"

echo "== body-digest immutability (Architect E-111424Z) =="
DIGEST="$(python3 -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path('${ROOT}/governance/fixtures/body-digest/ar-digest-good/body.json').read_bytes()).hexdigest())")"
python3 "${ENFORCEMENT}/record-run-evidence/scripts/check-body-digest-match.py" "${ROOT}" \
  --body "${ROOT}/governance/fixtures/body-digest/ar-digest-good/body.json" \
  --expect "${DIGEST}" || rc=1
if python3 "${ENFORCEMENT}/record-run-evidence/scripts/check-body-digest-match.py" "${ROOT}" \
  --body "${ROOT}/governance/fixtures/body-digest/ar-digest-good/body.json" \
  --expect deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef \
  >/dev/null 2>&1; then
  echo "FAIL: digest mismatch should refuse" >&2
  rc=1
else
  echo "OK: body digest mismatch refused"
fi

echo "== record-run-evidence (AD-H §19) =="
python3 "${ENFORCEMENT}/record-run-evidence/scripts/check-provenance.py" "${ROOT}" || rc=1
ap_tmp="$(mktemp -d)"
mkdir -p "${ap_tmp}/evidence/tasks"
printf '%s\n' '{"id":"t_a1b2c3d4e5","phase":"M3","role":"implementer","status":"done","brief_id":"B-1","ac_ids":["AC-1"],"files_in_scope":["src/"],"deps":[]}' \
  > "${ap_tmp}/evidence/tasks/bad.json"
if python3 "${ENFORCEMENT}/record-run-evidence/scripts/check-provenance.py" "${ap_tmp}" >/dev/null 2>&1; then
  echo "FAIL: complete IMPLEMENT without worker_session_id should refuse" >&2
  rc=1
else
  echo "OK: missing worker_session_id refused"
fi
printf '%s\n' '{"id":"t_a1b2c3d4e5","phase":"M3","role":"implementer","status":"done","provenance":{"task_id":"t_a1b2c3d4e5","task_run_id":"1","worker_session_id":"sess1","soul_path":"/tmp/no-such-soul.md","soul_sha":"deadbeef","skill_tips":{"ground-in-harvest":"abc"},"model_id":"unknown","citations":{"brief_or_story_id":"B-1","legacy_locus":"projects/legacy/Foo.java:1-10"},"artifacts":[]}}' \
  > "${ap_tmp}/evidence/tasks/bad.json"
if python3 "${ENFORCEMENT}/record-run-evidence/scripts/check-provenance.py" "${ap_tmp}" >/dev/null 2>&1; then
  echo "FAIL: model_id=unknown without model_id_gap should refuse" >&2
  rc=1
else
  echo "OK: unknown model_id without gap refused"
fi
# Good fixture: write a real soul file and hash it
soul_tmp="$(mktemp)"
printf 'test soul\n' > "${soul_tmp}"
soul_sha="$(python3 -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path('${soul_tmp}').read_bytes()).hexdigest())")"
printf '%s\n' "{\"id\":\"t_a1b2c3d4e5\",\"phase\":\"M3\",\"role\":\"implementer\",\"status\":\"done\",\"provenance\":{\"task_id\":\"t_a1b2c3d4e5\",\"task_run_id\":\"1\",\"campaign_id\":\"fixture\",\"worker_session_id\":\"sess1\",\"soul_path\":\"${soul_tmp}\",\"soul_sha\":\"${soul_sha}\",\"skill_tips\":{\"ground-in-harvest\":\"abc\"},\"model_id\":\"unknown\",\"model_id_gap\":true,\"citations\":{\"brief_or_story_id\":\"B-1\",\"legacy_locus\":\"projects/legacy/Foo.java:1-10\"},\"artifacts\":[]}}" \
  > "${ap_tmp}/evidence/tasks/bad.json"
python3 "${ENFORCEMENT}/record-run-evidence/scripts/check-provenance.py" "${ap_tmp}" || rc=1
rm -f "${soul_tmp}"
# Interventions audit — a BOARD-SIDE reviewer tool, not part of this scaffold.
# HERMETICITY (Operator law): once scaffolded into a destination repo there is
# no link back to the authoring project, so this must never guess its way up
# the filesystem looking for it. Opt in explicitly via HARNESS_BOARD_TOOLS
# when running from the board; otherwise skip.
_AUDIT_IV="${HARNESS_BOARD_TOOLS:+${HARNESS_BOARD_TOOLS}/audit-interventions.py}"
if [ -f "${_AUDIT_IV}" ]; then
  python3 "${_AUDIT_IV}" "${ROOT}" || rc=1
else
  echo "OK: audit-interventions skipped (reviewer tool not on scaffold path)"
fi
rm -rf "${ap_tmp}"

echo "== R-M3.5–8 POM / dependency_wait handoff =="
if [ -f "${ROOT}/pom.xml" ]; then
  python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-persistence-bom.py" "${ROOT}" || rc=1
  python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-compile-deps-preflight.py" "${ROOT}" || rc=1
else
  echo "OK: persistence/compile preflights idle until bootstrap creates pom.xml"
fi
dep_tmp="$(mktemp -d)"
mkdir -p "${dep_tmp}/evidence/verdicts"
python3 "${SKILLS}/gates/check-release-readiness/scripts/apply-dependency-wait-hold.py" \
  "${dep_tmp}" --task-id t_fixture_dep_wait --stamp || rc=1
if [ ! -f "${dep_tmp}/evidence/verdicts/dependency-wait-hold-t_fixture_dep_wait.json" ]; then
  echo "FAIL: dependency-wait-hold stamp missing" >&2
  rc=1
else
  echo "OK: R-M3.6 dependency-wait-hold stamp"
fi
rm -rf "${dep_tmp}"

# AD-012 / R-SK.5 + R-SK.7 + R-SK.9 skill conformance runs ONCE, below
# ("CS-9 skill conformance"), against the in-tree lint over the whole skills
# root. The former second invocation pointed at a platform-relocation path
# (a skill tree in the authoring repo) that was never committed on any
# branch, so it fail-closed unconditionally, and it scanned only the
# harness/ category rather than the skills root. Removed in the
# Clean-Architecture uplift — one check, one source of truth.

echo "== CS-7 m3-implementer bundle exists-assert (fail-closed) =="
python3 "${ENFORCEMENT}/dispatch-phase/scripts/assert-bundle-skills-exist.py" \
  "${ROOT}" --bundle m3-implementer || rc=1

echo "== BANK-DEST-INV-HARDINVOKE-1 (RW-2) =="
python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-dest-inventory-hardinvoke.py" \
  "${ROOT}" || rc=1

echo "== AD-011 skill extension overlay =="
if [ ! -f "${ROOT}/governance/contracts/ad011-skill-extension.md" ]; then
  echo "FAIL: missing ad011-skill-extension.md" >&2
  rc=1
else
  echo "OK: AD-011 contract present"
fi
# Retired: workshop-extensions/ and extensions/ were ruled REMOVE in the
# tidy-up disposition (20260812-TIDYUP-DISPOSITION.md rows 16-17) — CS-2
# merged the overlays in-skill and demo users extend via the official
# external_dirs / taps / `hermes skills install` mechanisms. Both checks
# fail-closed on directories the harness deliberately deleted.
echo "== R-SK.13 scaffold hermeticity (no link to the authoring project) =="
python3 "${SKILL_DIR}/scripts/check-scaffold-hermeticity.py" --root "${ROOT}" || rc=1
echo "== UPLIFT-7 golden cleanliness (no run-state in tip tree) =="
python3 "${SKILL_DIR}/scripts/check-golden-cleanliness.py" --root "${ROOT}" || rc=1
echo "== AD-S S.4 .specify absent from golden =="
python3 "${SKILL_DIR}/scripts/check-specify-absent.py" --root "${ROOT}" || rc=1
echo "== AD-H §7 root scripts/ absent from golden =="
python3 "${SKILL_DIR}/scripts/check-scripts-absent.py" --root "${ROOT}" || rc=1
echo "== dangling .hermes refs (Deputy E-174046Z relocation residue) =="
python3 "${SKILL_DIR}/scripts/check-dangling-hermes-refs.py" --root "${ROOT}" || rc=1
echo "== create-path tip sync (R0/R3) =="
python3 "${ROOT}/.hermes/enforcement/dispatch-phase/scripts/check-create-path-tip-sync.py" "${ROOT}" || rc=1
echo "== R-SK.12 script CLI contract (syntax + no false-green --help) =="
python3 "${SKILL_DIR}/scripts/check-script-cli-contract.py" --root "${ROOT}/.hermes/skills" || rc=1
python3 "${SKILL_DIR}/scripts/check-script-cli-contract.py" --root "${ROOT}/.hermes/enforcement" || rc=1
echo "== CS-7 bundle exists-assert =="
python3 "${SKILL_DIR}/scripts/check-bundle-manifest.py" --root "${ROOT}/.hermes/skills" --bundles "${ROOT}/.hermes/home/skill-bundles" || rc=1
echo "== CS-9 skill conformance (R-SK.7 categorized + R-SK.5 specimen literals) =="
if [ -f "${SKILL_DIR}/scripts/check-skill-conformance.py" ]; then
  python3 "${SKILL_DIR}/scripts/check-skill-conformance.py" --all --root "${ROOT}/.hermes/skills" || rc=1
else
  echo "FAIL: missing R-SK conformance lint at ${SKILL_DIR}/scripts/" >&2
  rc=1
fi
# retired: echo "== R-M3.32 skill-tree overlay sync =="
# CS-2: sync retired — overlays modify-in-place under skill references/ (W3)
# CS-2: sync retired — overlays modify-in-place under skill references/ (W3)
if [ ! -f "${ROOT}/.hermes/skills/migration/spring-to-quarkus-patterns/references/security-anti-essay.md" ]; then
  echo "FAIL: R-M3.32 security-anti-essay.md missing from Hermes skill tree" >&2
  rc=1
else
  echo "OK: security-anti-essay.md present in Hermes skill tree"
fi

echo "== R-M3.9–13 wall-fit + JDBC =="
if [ -f "${ROOT}/pom.xml" ]; then
  python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-jdbc-deps-preflight.py" "${ROOT}" || rc=1
else
  echo "OK: JDBC preflight idle until bootstrap creates pom.xml"
fi
# 42@3600 must refuse under retuned 90s/op (R-M3.9; S-003 class)
wf42="$(mktemp -d)"
python3 - <<PY || rc=1
import json, pathlib, subprocess, sys
root = pathlib.Path("${ROOT}")
fis = []
for i in range(42):
    fis.append(f"/projects/.derived/legacy-at-3/src/main/java/com/demo/R{i}.java")
    fis.append(f"/projects/modernized/src/main/java/com/demo/R{i}.java")
body = {
    "phase": "M3",
    "role": "implementer",
    "effort_class": "high",
    "runtime_budget_sec": 3600,
    "identity": {
        "story_id": "S-WF42",
        "transform_class": "HARVEST",
        "g2_applicability": "not_applicable",
        "operand_count": 42,
        "sizing_basis": "operand_count",
    },
    "files_in_scope": fis,
    "exit_criteria": [
        {"check": "compile", "cmd": "true", "expect": "rc=0"},
        {"check": "skills", "assert": "fixture"},
        {"check": "endpoint_contract", "assert": "fixture"},
    ],
}
path = pathlib.Path("${wf42}") / "body42.json"
path.write_text(json.dumps(body))
cp = subprocess.run(
    [sys.executable, str(root / ".hermes/skills/sdd/check-spec-readiness/scripts/check-operand-count.py"),
     str(root), str(path), "--wall-fit"],
    capture_output=True, text=True,
)
if cp.returncode == 0:
    print("FAIL: wall-fit 42@3600 should refuse under R-M3.9", file=sys.stderr)
    print(cp.stdout, cp.stderr, file=sys.stderr)
    sys.exit(1)
print("OK: wall-fit 42@3600 refused (R-M3.9)")
PY
rm -rf "${wf42}"

if [ "${rc}" -ne 0 ]; then
  echo "validate-contracts FAILED" >&2
  exit 1
fi
echo "OK: validate-contracts passed"
