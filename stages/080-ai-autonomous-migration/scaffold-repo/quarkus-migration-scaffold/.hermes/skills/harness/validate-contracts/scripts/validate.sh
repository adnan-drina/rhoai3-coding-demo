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
  none. The scaffold root is found by walking up to migration.yaml (SR-2);
  the skills root is ${ROOT}/.hermes/skills. The suite cd's to the scaffold
  root before running. There are no section selectors and no output-format flags.

  -h, --help   print this usage and exit 0

Sections covered (in order):
  no .hermes.md / HERMES.md override      check-spec-readiness (+ S.6)
  check-domain-parity admission (W2 S10)         G-1 PIT dry-run parse
  B-5 product mode cannot ACCEPT from fixtures
  AR-3.6 G-1 acceptance operand           scan-with-mta findings schema
  AR-3.6 G-1 acceptance operand           scan-with-mta findings schema
  inventory-entry-points smoke            enforce-authority-boundary (AD-H S16)
  ack/comment authority (S16.5/AR-1.1-1.2) write-fence proving-min (S16.4/F2)
  ground-in-harvest (AD-H S17)          check-release-readiness (AD-H S18)
  workspace recovery proving-min (S5.1/F4) external_dirs (AD-S relocate)
  kanban-body (W2 S6.1)                   story-sizing operand_count
  wall-as-terminal exit-eval              checkpoint lag check
  #1b test-compile gate on checkpoint      body-digest immutability
  T-8 dual-oracle refuse                   L2 mint oracles (SR-13)
  A-3c AC oracles + operand_class set
  EX-5 constraint layers (L1-3 overlays)
  BV19-3 link graph is the phase DAG
  LG4 no scaffold tmp/ or authoring ledger
  SR-12 scaffold-root allow-list            LG7 no eval of phase-dispatch parser
  AD-S S.4 .specify absent from golden     A-1 speckit overlay resolve
  AD-H §7 root scripts/ absent from golden
  WC-5 mta_rescan proves analyzer ran
  L7 park-on-block-loop self-test
  LG9a pre-commit-index-suite script present
  record-run-evidence (AD-H S19)   R-M3.6 dependency_wait hold
  CS-7 m3-implementer bundle assert        BANK-DEST-INV-HARDINVOKE-1 (RW-2)
  AD-011 skill extension overlay           R-SK.12 script CLI contract
  CS-7 bundle exists-assert                CS-9 skill conformance
  R-M3.9-13 wall-fit + JDBC

Examples:
  bash .hermes/skills/harness/validate-contracts/scripts/validate.sh
  bash .hermes/skills/harness/validate-contracts/scripts/validate.sh --help

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
# EX-3: this package lives under .hermes/skills/harness/ (enforcement/ dissolved).
# SR-2: scaffold root is the migration.yaml walk, never a parent-count.
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HARNESS="$(cd "${SKILL_DIR}/.." && pwd)"
resolve_migration_root() {
  local d
  d="$(cd "$(dirname "$0")" && pwd)"
  while [ "$d" != "/" ]; do
    if [ -f "$d/migration.yaml" ]; then
      printf '%s\n' "$d"
      return 0
    fi
    d="$(dirname "$d")"
  done
  echo "cannot find project root (migration.yaml) walking up from $(dirname "$0") (SR-2)" >&2
  return 1
}
ROOT="$(resolve_migration_root)" || exit 1
SKILLS="$(cd "${ROOT}/.hermes/skills" && pwd)"
cd "${ROOT}"
rc=0

echo "== no .hermes.md / HERMES.md override (was scaffold-invariants) =="
bash "${HARNESS}/validate-contracts/scripts/check-no-hermes-context-override.sh" || rc=1

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

echo "== B-5 product mode cannot ACCEPT from fixtures =="
b5_out="$(python3 "${SKILLS}/gates/check-domain-parity/scripts/g1-characterization.py" "${ROOT}" --product 2>/dev/null || true)"
if printf '%s\n' "${b5_out}" | grep -q 'INCONCLUSIVE_FIXTURE' \
  && ! printf '%s\n' "${b5_out}" | grep -qE '(^| )ACCEPT($| )'; then
  echo "OK: G-1 --product on golden is INCONCLUSIVE_FIXTURE (B-5)"
else
  echo "FAIL: G-1 --product must not score ACCEPT (got: ${b5_out})" >&2
  rc=1
fi
python3 - "${SKILLS}/gates/check-domain-parity/scripts" "${ROOT}" <<'PY' || rc=1
import sys
from pathlib import Path
scripts, root = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(scripts / "lib"))
from verdict import INCONCLUSIVE_FIXTURE, product_gate_verdict
fx = (
    root
    / ".hermes/skills/gates/check-release-readiness/fixtures/admission/g1-characterization/known-good"
)
got = product_gate_verdict("ACCEPT", fx)
assert got == INCONCLUSIVE_FIXTURE, got
print("OK: fixture ACCEPT remapped to INCONCLUSIVE_FIXTURE (B-5)")
PY
for gate in g2-harvest-fidelity g3-findings-delta g4-runtime-parity; do
  out="$(python3 "${SKILLS}/gates/check-domain-parity/scripts/${gate}.py" "${ROOT}" --product 2>/dev/null || true)"
  if printf '%s\n' "${out}" | grep -q 'INCONCLUSIVE_FIXTURE'; then
    echo "OK: ${gate} --product is INCONCLUSIVE_FIXTURE (B-5)"
  else
    echo "FAIL: ${gate} --product must be INCONCLUSIVE_FIXTURE (got: ${out})" >&2
    rc=1
  fi
done

# Parser/fixture only — not live specimen admission (Architect E-20260808T080815Z #3).
echo "== G-1 PIT dry-run parse (R1 pin; not live admission) =="
python3 "${SKILLS}/gates/check-domain-parity/scripts/parse-pit-mutations.py" \
  "${ROOT}/.hermes/skills/harness/validate-contracts/fixtures/pit-dry-run/mutations.xml" || rc=1
if python3 "${SKILLS}/gates/check-domain-parity/scripts/parse-pit-mutations.py" \
  "${ROOT}/.hermes/skills/harness/validate-contracts/fixtures/pit-dry-run/missing.xml" >/dev/null 2>&1; then
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
  .hermes/skills/gates/check-release-readiness/fixtures/admission/g3-findings-delta/known-good/mta-findings.json || rc=1

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
http=[e for e in d["entry_points"] if e.get("kind")=="http"]
assert http and http[0].get("http_method")=="GET"
assert http[0].get("http_path")=="/api/demo"
print("OK: inventory smoke", d["counts"], "route", http[0]["http_method"], http[0]["http_path"])
PY
# class-level @RequestMapping prefix joined onto method path
mkdir -p "${tmp}/pref/src"
cat > "${tmp}/pref/src/Owners.java" <<'EOF'
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RestController;
@RestController
@RequestMapping("/api/owners")
public class Owners {
  @RequestMapping(value = "/{id}", method = RequestMethod.GET)
  String get() { return ""; }
}
EOF
python3 "${SKILLS}/analysis/inventory-entry-points/scripts/inventory-entry-points.py" \
  "${tmp}/pref" -o "${tmp}/pref.json" || rc=1
python3 - <<PY || rc=1
import json
d=json.load(open("${tmp}/pref.json"))
http=[e for e in d["entry_points"] if e.get("kind")=="http"]
assert len(http)==1, http
assert http[0]["http_method"]=="GET"
assert http[0]["http_path"]=="/api/owners/{id}"
print("OK: inventory class-prefix join", http[0]["http_path"])
PY
rm -rf "${tmp}"

echo "== enforce-authority-boundary (AD-H §16) =="
bash "${HARNESS}/enforce-authority-boundary/scripts/check-acks.sh" M1 "${ROOT}" || rc=1
# M2 without ack must fail
if bash "${HARNESS}/enforce-authority-boundary/scripts/check-acks.sh" M2 "${ROOT}" >/dev/null 2>&1; then
  echo "FAIL: M2 should require m1-findings ack when absent" >&2
  rc=1
else
  echo "OK: M2 refuses without m1-findings ack"
fi
# check-role-writes.py retired (Architect E-20260813T144117Z) — scope refuse is
# check-write-fence.py --body (files_in_scope); global deny via write fence.

echo "== ack/comment authority (AD-H §16.5 / AR-1.1 / AR-1.2) =="
# fixture feed must refuse impersonating override
if python3 "${HARNESS}/enforce-authority-boundary/scripts/check-comment-authority.py" "${ROOT}" >/dev/null 2>&1; then
  echo "FAIL: AR-1.2 impersonating override fixture should refuse" >&2
  rc=1
else
  echo "OK: AR-1.2 impersonating comment refused"
fi
ar11_tmp="$(mktemp -d)"
mkdir -p "${ar11_tmp}/evidence/acks"
printf '%s\n' '{"kind":"migration-ack","ack_type":"brief-identity","status":"acknowledged","acknowledged_by":"planner (M2)","acknowledged_at":"2026-08-09T17:00:00Z"}' \
  > "${ar11_tmp}/evidence/acks/brief-identity.json"
if python3 "${HARNESS}/enforce-authority-boundary/scripts/check-ack-authority.py" "${ar11_tmp}" >/dev/null 2>&1; then
  echo "FAIL: AR-1.1 planner self-ACK should refuse" >&2
  rc=1
else
  echo "OK: AR-1.1 planner self-ACK refused"
fi
printf '%s\n' '{"kind":"migration-ack","ack_type":"brief-identity","status":"acknowledged","acknowledged_by":"Operator","acknowledged_at":"2026-08-10T00:00:00Z","task_id":"t_demo","artifact_digests":{"brief":"abc"}}' \
  > "${ar11_tmp}/evidence/acks/brief-identity.ack.json"
rm -f "${ar11_tmp}/evidence/acks/brief-identity.json"
python3 "${HARNESS}/enforce-authority-boundary/scripts/check-ack-authority.py" "${ar11_tmp}" || rc=1
# Deputy E-20260816T173510Z — block-mapping artifact_digests is valid YAML
cat > "${ar11_tmp}/evidence/acks/m1-findings.ack.yaml" <<'EOF'
kind: migration-ack
ack_type: m1-findings
status: acknowledged
acknowledged_by: Operator
acknowledged_at: 2026-08-16T00:00:00Z
task_id: t_demo
artifact_digests:
  evidence/mta-findings.json: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  evidence/findings-handoff.json: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
EOF
rm -f "${ar11_tmp}/evidence/acks/brief-identity.ack.json"
python3 "${HARNESS}/enforce-authority-boundary/scripts/check-ack-authority.py" "${ar11_tmp}" \
  && echo "OK: AR-1.1 block-mapping artifact_digests accepted" \
  || { echo "FAIL: AR-1.1 block-mapping artifact_digests refused" >&2; rc=1; }
# artifact_refs with sha256, no artifact_digests map
cat > "${ar11_tmp}/evidence/acks/m1-findings.ack.yaml" <<'EOF'
kind: migration-ack
ack_type: m1-findings
status: acknowledged
acknowledged_by: Operator
acknowledged_at: 2026-08-16T00:00:00Z
task_id: t_demo
artifact_refs:
  - path: evidence/mta-findings.json
    sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
EOF
python3 "${HARNESS}/enforce-authority-boundary/scripts/check-ack-authority.py" "${ar11_tmp}" \
  && echo "OK: AR-1.1 artifact_refs sha256 accepted" \
  || { echo "FAIL: AR-1.1 artifact_refs sha256 refused" >&2; rc=1; }
rm -rf "${ar11_tmp}"

echo "== write-fence proving-min (AD-H §16.4 / F2) =="
fence_tmp="$(mktemp -d)"
mkdir -p "${fence_tmp}/evidence/acks" "${fence_tmp}/evidence/verdicts" \
  "${fence_tmp}/.hermes/skills" "${fence_tmp}/.hermes/skills/harness/validate-contracts/fixtures" \
  "${fence_tmp}/src/main/java"
printf '%s\n' 'ok' > "${fence_tmp}/evidence/acks/README.md"
printf '%s\n' 'ok' > "${fence_tmp}/.hermes/skills/harness/validate-contracts/fixtures/keep.txt"
bash "${HARNESS}/enforce-authority-boundary/scripts/apply-write-fence.sh" "${fence_tmp}" lock || rc=1
if python3 "${HARNESS}/enforce-authority-boundary/scripts/probe-write-fence.py" "${fence_tmp}"; then
  echo "OK: F2 seat probe PASS on temp tree"
else
  echo "FAIL: F2 seat probe" >&2
  rc=1
fi
# scope refuse smoke
printf '%s\n' '{"files_in_scope":["src/main/java/Foo.java"]}' > "${fence_tmp}/body.json"
printf '%s\n' 'x' > "${fence_tmp}/src/main/java/OutOfScope.java"
if python3 "${HARNESS}/enforce-authority-boundary/scripts/check-write-fence.py" "${fence_tmp}" \
  --no-git-status --body "${fence_tmp}/body.json" \
  --writes src/main/java/OutOfScope.java evidence/acks/forged.json >/dev/null 2>&1; then
  echo "FAIL: write-fence should refuse OOS + ack forge" >&2
  rc=1
else
  echo "OK: write-fence refuses OOS + deny-path writes"
fi
# Z15-a — A-1 enforcement DENY must fire on dotted .hermes/ paths (norm() hole).
# Build path at runtime so dangling-refs lint does not see a missing leaf.
z15_enf=".hermes/skills/harness/${RANDOM}-tamper.py"
z15_verdict="evidence/verdicts/${RANDOM}-forged.json"
if python3 "${HARNESS}/enforce-authority-boundary/scripts/check-write-fence.py" "${fence_tmp}" \
  --no-git-status \
  --writes "${z15_enf}" "./${z15_verdict}" >/dev/null 2>&1; then
  echo "FAIL: write-fence should refuse .hermes/skills/harness + evidence/verdicts" >&2
  rc=1
else
  echo "OK: write-fence refuses .hermes/skills/harness + evidence/verdicts (Z15-a)"
fi
# Legitimate in-scope src write must still PASS
printf '%s\n' '{"files_in_scope":["src/main/java/Foo.java"]}' > "${fence_tmp}/body-ok.json"
if python3 "${HARNESS}/enforce-authority-boundary/scripts/check-write-fence.py" "${fence_tmp}" \
  --no-git-status --body "${fence_tmp}/body-ok.json" \
  --writes src/main/java/Foo.java >/dev/null 2>&1; then
  echo "OK: write-fence allows in-scope src write (Z15-a positive)"
else
  echo "FAIL: write-fence wrongly refused in-scope src write" >&2
  rc=1
fi
printf '%s\n' '{"files_writable":["src/main/java/Foo.java"]}' > "${fence_tmp}/body-writable.json"
if python3 "${HARNESS}/enforce-authority-boundary/scripts/check-write-fence.py" "${fence_tmp}" \
  --no-git-status --body "${fence_tmp}/body-writable.json" \
  --writes pom.xml >/dev/null 2>&1; then
  echo "FAIL: write-fence should refuse OOS pom.xml under files_writable (B-2)" >&2
  rc=1
else
  echo "OK: write-fence refuses OOS pom.xml under files_writable (B-2)"
fi
bash "${HARNESS}/enforce-authority-boundary/scripts/apply-write-fence.sh" "${fence_tmp}" unlock >/dev/null || true
rm -rf "${fence_tmp}"

echo "== EX-3 write-set hook both directions (B-S2 pre_tool_call) =="
HOOK="${HARNESS}/enforce-authority-boundary/scripts/write-set-hook.py"
hook_tmp="$(mktemp -d)"
mkdir -p "${hook_tmp}/src/main/java"
(
  cd "${hook_tmp}"
  export HERMES_WRITE_SAFE_ROOT="${hook_tmp}"
  oos_rel=".hermes/${RANDOM}-tamper.py"
  if printf '%s\n' "{\"tool_name\":\"write_file\",\"tool_input\":{\"path\":\"${oos_rel}\"}}" \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: write-set hook should refuse in-repo OOS under .hermes/" >&2
    exit 1
  else
    echo "OK: write-set hook refuses in-repo OOS (B-S2)"
  fi
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"src/main/java/com/demo/Ok.java"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "OK: write-set hook allows in-scope src write"
  else
    echo "FAIL: write-set hook wrongly refused in-scope src write" >&2
    exit 1
  fi
  export HERMES_KANBAN_FILES_WRITABLE='["src/main/java/com/demo/Ok.java"]'
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"pom.xml"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: write-set hook should refuse OOS pom.xml (B-2)" >&2
    exit 1
  else
    echo "OK: write-set hook refuses OOS pom.xml (B-2)"
  fi
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"src/main/java/com/demo/Ok.java"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "OK: write-set hook allows files_writable src (B-2)"
  else
    echo "FAIL: write-set hook wrongly refused in-set src write" >&2
    exit 1
  fi
  unset HERMES_KANBAN_FILES_WRITABLE
  export HERMES_KANBAN_TASK="t_deadbeef"
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"pom.xml"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: write-set hook should fail-closed when task set but write-set missing" >&2
    exit 1
  else
    echo "OK: write-set hook fail-closed without published write-set (B-2)"
  fi
  # Architect E-20260816T185414Z — specs/ is a product write; missing write-set
  # must not let Spec Kit (or SPECIFY_FEATURE_DIRECTORY) through.
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"specs/001/spec.md"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: write-set hook should refuse specs/ when write-set missing" >&2
    exit 1
  else
    echo "OK: write-set hook fail-closed on specs/ without write-set (AD-013)"
  fi
  export HERMES_KANBAN_FILES_WRITABLE='[".specify/","specs/"]'
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"specs/001/spec.md"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "OK: M2 write-set allows specs/ (native speckit)"
  else
    echo "FAIL: M2 write-set refused specs/" >&2
    exit 1
  fi
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":".specify/feature.json"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "OK: M2 write-set allows .specify/ (native speckit)"
  else
    echo "FAIL: M2 write-set refused .specify/" >&2
    exit 1
  fi
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"src/main/java/x/App.java"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: M2 write-set should refuse src/" >&2
    exit 1
  else
    echo "OK: M2 write-set refuses src/"
  fi
  unset HERMES_KANBAN_FILES_WRITABLE
  export HERMES_KANBAN_TASK="t_daa654e9"
  export HERMES_KANBAN_FILES_WRITABLE='[]'
  if printf '%s\n' '{"tool_name":"write","tool_input":{"path":"migration.yaml"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: empty write-set must refuse Hermes write on migration.yaml" >&2
    exit 1
  else
    echo "OK: empty write-set refuses Hermes write on migration.yaml (091919Z)"
  fi
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"migration.yaml"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: empty write-set must refuse write_file on migration.yaml" >&2
    exit 1
  else
    echo "OK: empty write-set refuses write_file on migration.yaml (091919Z)"
  fi
  if printf '%s\n' '{"tool_name":"patch","tool_input":{"path":"migration.yaml"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: empty write-set must refuse patch on migration.yaml" >&2
    exit 1
  else
    echo "OK: empty write-set refuses patch on migration.yaml (091919Z)"
  fi
) || rc=1
rm -rf "${hook_tmp}"

echo "== C-2(a) single-persona assignee (product default) =="
python3 "${HARNESS}/dispatch-phase/scripts/check-seat-assignee-profiles.py" "${ROOT}" || rc=1
ex4_m3="$(python3 "${HARNESS}/dispatch-phase/scripts/resolve-seat-assignee.py" M3 --root "${ROOT}")"
if [ "${ex4_m3}" = "default" ]; then
  echo "OK: C-2(a) M3 cards resolve to assignee default"
else
  echo "FAIL: C-2(a) M3 assignee is ${ex4_m3:-empty}, want default" >&2
  rc=1
fi

echo "== EX-5 constraint layers (L1 deny · L2 write-safe-root · L3 local backend) =="
python3 "${HARNESS}/enforce-authority-boundary/scripts/check-ex5-constraint-layers.py" "${ROOT}" || rc=1

echo "== BV19-3 link graph is the phase DAG =="
python3 "${HARNESS}/dispatch-phase/scripts/check-link-graph.py" "${ROOT}" || rc=1
LINK_READER="${HARNESS}/dispatch-phase/scripts/read-link-graph.py"
LINK_FIX="${HARNESS}/dispatch-phase/fixtures/link-graph"
if python3 "${LINK_READER}" --json-file "${LINK_FIX}/child-with-parent.json" \
  --expect-parent t_m1aabbcc >/dev/null; then
  echo "OK: BV19-3 reader accepts child→parent link"
else
  echo "FAIL: BV19-3 reader should accept fixture parent link" >&2
  rc=1
fi
if python3 "${LINK_READER}" --json-file "${LINK_FIX}/root-wrapped.json" \
  --expect-no-parents --expect-child t_m2aabbcc >/dev/null; then
  echo "OK: BV19-3 reader accepts wrapped root + child"
else
  echo "FAIL: BV19-3 reader should accept wrapped root fixture" >&2
  rc=1
fi
if python3 "${LINK_READER}" --json-file "${LINK_FIX}/child-with-parent.json" \
  --expect-parent t_nope >/dev/null 2>&1; then
  echo "FAIL: BV19-3 reader should refuse a missing parent" >&2
  rc=1
else
  echo "OK: BV19-3 reader refuses missing parent (negative)"
fi
m2_rc=0
m2_noparent="$(bash "${HARNESS}/dispatch-phase/scripts/dispatch-phase.sh" M2 --dry-run 2>&1)" || m2_rc=$?
if [[ "${m2_rc}" -eq 0 ]]; then
  echo "FAIL: M2 without --parent should refuse (BV19-3)" >&2
  rc=1
elif printf '%s\n' "${m2_noparent}" | grep -q 'BV19-3: --parent REQUIRED'; then
  echo "OK: BV19-3 M2 without --parent refused"
else
  echo "FAIL: M2 without --parent must print BV19-3: --parent REQUIRED" >&2
  printf '%s\n' "${m2_noparent}" | tail -n 8 >&2
  rc=1
fi
help_lg="$(python3 "${LINK_READER}" --help 2>&1 || true)"
if printf '%s\n' "${help_lg}" | grep -E '^OK:|^PASS:' >/dev/null; then
  echo "FAIL: read-link-graph.py --help must not print OK:/PASS: (R-SK.12)" >&2
  rc=1
else
  echo "OK: BV19-3 reader --help has no verdict line"
fi

echo "== ground-in-harvest (AD-H §17) =="
python3 "${ROOT}/.hermes/skills/harness/ground-in-harvest/scripts/check-citation.py" "${ROOT}" || rc=1
gg_tmp="$(mktemp -d)"
mkdir -p "${gg_tmp}/evidence/tasks"
# invent-without-locus: writes without legacy_locus
printf '%s\n' '{"id":"T-bad","phase":"M3","role":"implementer","brief_id":"B-1","ac_ids":["AC-1"],"files_in_scope":["src/"],"deps":[],"writes":["src/X.java"]}' \
  > "${gg_tmp}/evidence/tasks/bad.json"
if python3 "${ROOT}/.hermes/skills/harness/ground-in-harvest/scripts/check-citation.py" "${gg_tmp}" >/dev/null 2>&1; then
  echo "FAIL: invent-without-locus should refuse" >&2
  rc=1
else
  echo "OK: invent-without-locus refused"
fi
# good non-trivial packet
printf '%s\n' '{"id":"t_a1b2c3d4e5","phase":"M3","role":"implementer","brief_id":"B-1","ac_ids":["AC-1"],"files_in_scope":["src/"],"deps":[],"legacy_locus":"projects/legacy/Foo.java:10-40","writes":["src/Foo.java"]}' \
  > "${gg_tmp}/evidence/tasks/bad.json"
python3 "${ROOT}/.hermes/skills/harness/ground-in-harvest/scripts/check-citation.py" "${gg_tmp}" || rc=1
# commit message lint
printf '%s\n' 't_a1b2c3d4e5: port Foo (brief B-1; legacy projects/legacy/Foo.java:10-40)' > "${gg_tmp}/msg.txt"
python3 "${ROOT}/.hermes/skills/harness/ground-in-harvest/scripts/check-citation.py" "${gg_tmp}" --commit-msg "${gg_tmp}/msg.txt" || rc=1
printf '%s\n' 'fix formatting' > "${gg_tmp}/msg-bad.txt"
if python3 "${ROOT}/.hermes/skills/harness/ground-in-harvest/scripts/check-citation.py" "${gg_tmp}" --commit-msg "${gg_tmp}/msg-bad.txt" >/dev/null 2>&1; then
  echo "FAIL: commit without task id should refuse" >&2
  rc=1
else
  echo "OK: commit without task id refused"
fi
rm -rf "${gg_tmp}"

echo "== check-release-readiness (AD-H §18) =="
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-phase-matrix.py" "${ROOT}" || rc=1
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${ROOT}" || rc=1
# B8 — check-semantics-manifest (.hermes/skills/gates/check-release-readiness/references/check-semantics-manifest.md)
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-semantics-manifest.py" "${ROOT}" || rc=1
# Quarkus platform pin ↔ pom (manage-quarkus-extensions) — Wave B: skip until bootstrap
if [ -f "${ROOT}/pom.xml" ]; then
  python3 "${SKILLS}/migration/manage-quarkus-extensions/scripts/check-pom-platform-pins.py" "${ROOT}" || rc=1
else
  echo "OK: no destination pom yet (bootstrap-quarkus-project skill)"
  [ -f "${ROOT}/.hermes/skills/migration/bootstrap-quarkus-project/SKILL.md" ] || {
    echo "FAIL: missing pom.xml and bootstrap-quarkus-project skill" >&2
    rc=1
  }
fi
# A-3 / H-3 — Jacoco dual Sonar paths + surefire argLine (idle without pom)
python3 "${SKILLS}/migration/manage-quarkus-extensions/scripts/check-pom-jacoco-wiring.py" "${ROOT}" || rc=1
# W3 — extension tooling typed preflight (CLI absent → MAVEN_FALLBACK exit 0)
python3 "${SKILLS}/migration/manage-quarkus-extensions/scripts/assert-extension-tooling.py" || rc=1
# A2 / runnable-db-security — fixture refuse paths (scaffold root may fail until B3)
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-runnable-db-config.py" \
  "${ROOT}/.hermes/skills/harness/validate-contracts/fixtures/runnable-db-security/bad-hsqldb-destination" >/dev/null 2>&1; then
  echo "FAIL: B7 HSQLDB destination should refuse" >&2
  rc=1
else
  echo "OK: B7 HSQLDB destination refused"
fi
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-empty-security.py" \
  "${ROOT}/.hermes/skills/harness/validate-contracts/fixtures/runnable-db-security/bad-placeholder-security" >/dev/null 2>&1; then
  echo "FAIL: AR-2.2 placeholder security should refuse" >&2
  rc=1
else
  echo "OK: AR-2.2 placeholder security refused"
fi
# EX-2: check-s008-resurrection-order.py retired (not in golden scaffold)
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-semantics-manifest.py" \
  "${ROOT}/.hermes/skills/gates/check-release-readiness/fixtures/check-semantics-manifest/bad-endpoint-smoke-overpromise" >/dev/null 2>&1; then
  echo "FAIL: B8 narrowed smoke should refuse endpoint_smoke id" >&2
  rc=1
else
  echo "OK: B8 endpoint_smoke over-promise refused"
fi
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-semantics-manifest.py" \
  "${ROOT}/.hermes/skills/gates/check-release-readiness/fixtures/check-semantics-manifest/good-endpoint-smoke-health" || rc=1
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-semantics-manifest.py" \
  "${ROOT}/.hermes/skills/gates/check-release-readiness/fixtures/check-semantics-manifest/bad-boot-health-skipped-package" >/dev/null 2>&1; then
  echo "FAIL: B8 boot_health skipped package should refuse" >&2
  rc=1
else
  echo "OK: B8 boot_health skipped package refused"
fi
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-semantics-manifest.py" \
  "${ROOT}/.hermes/skills/gates/check-release-readiness/fixtures/check-semantics-manifest/good-boot-health" || rc=1
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-semantics-manifest.py" \
  "${ROOT}/.hermes/skills/gates/check-release-readiness/fixtures/check-semantics-manifest/bad-g4-sample-as-product-closed" >/dev/null 2>&1; then
  echo "FAIL: B8 SAMPLE g4_hook→product closed should refuse" >&2
  rc=1
else
  echo "OK: B8 SAMPLE g4 product-closed refused"
fi
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-semantics-manifest.py" \
  "${ROOT}/.hermes/skills/gates/check-release-readiness/fixtures/check-semantics-manifest/bad-mvn-verify-no-clean" >/dev/null 2>&1; then
  echo "FAIL: B8 mvn_clean_verify without clean should refuse" >&2
  rc=1
else
  echo "OK: B8 mvn verify without clean refused"
fi
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-semantics-manifest.py" \
  "${ROOT}/.hermes/skills/gates/check-release-readiness/fixtures/check-semantics-manifest/bad-unit-it-zero-tests" >/dev/null 2>&1; then
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
# B-4 — waiver cannot author M5 ACCEPT
printf '%s\n' '{"phase":"M5","verdict":"ACCEPT","g1_kill_ratio":"pending_threshold","g1_kill_ratio_waiver":true,"ship":true,"routing":"close"}' \
  > "${vr_tmp}/evidence/verdicts/bad.json"
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: M5 ACCEPT with g1_kill_ratio_waiver should refuse (B-4)" >&2
  rc=1
else
  echo "OK: M5 ACCEPT via kill-ratio waiver refused (B-4)"
fi
# good M5 full with PASS+pin
printf '%s\n' '{"phase":"M5","verdict":"ACCEPT","g1_kill_ratio":"pass","g1_kill_ratio_threshold_pinned":true,"ship":true,"routing":"close"}' \
  > "${vr_tmp}/evidence/verdicts/bad.json"
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${vr_tmp}" || rc=1
# B-5 — INCONCLUSIVE_FIXTURE must never ship; ACCEPT must not embed it
printf '%s\n' '{"phase":"M5","verdict":"INCONCLUSIVE_FIXTURE","ship":true,"routing":"blocked"}' \
  > "${vr_tmp}/evidence/verdicts/bad.json"
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: INCONCLUSIVE_FIXTURE ship should refuse (B-5)" >&2
  rc=1
else
  echo "OK: INCONCLUSIVE_FIXTURE ship refused (B-5)"
fi
printf '%s\n' '{"phase":"M5","verdict":"ACCEPT","g1_kill_ratio":"pass","g1_kill_ratio_threshold_pinned":true,"ship":true,"routing":"close","g1_characterization":{"verdict":"INCONCLUSIVE_FIXTURE"}}' \
  > "${vr_tmp}/evidence/verdicts/bad.json"
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: ACCEPT embedding INCONCLUSIVE_FIXTURE should refuse (B-5)" >&2
  rc=1
else
  echo "OK: ACCEPT embedding INCONCLUSIVE_FIXTURE refused (B-5)"
fi
# single-unit composition reopen
printf '%s\n' '{"phase":"M5","verdict":"REFUSE","gate":"g4_runtime_parity","prior_verdict":"PROVISIONAL_ACCEPT","routing":"reopen_story"}' \
  > "${vr_tmp}/evidence/verdicts/bad.json"
python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${vr_tmp}" || rc=1
# shared-substrate reopen (fixture closure map)
mkdir -p "${vr_tmp}/evidence/slices"
cp "${ROOT}/.hermes/skills/harness/validate-contracts/fixtures/substrate-reopen/closure-map.json" \
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
# Self-reported waiver alone must refuse (Deputy E-20260813T144954Z P1 / B-4)
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
# Typed waiver ack must also refuse (B-4 / C-3(a) — no waiver path)
printf '%s\n' '{"phase":"M5","verdict":"ACCEPT","accept_kind":"full","g1_kill_ratio":"pending_threshold"}' \
  > "${vr_tmp}/evidence/verdicts/m5.json"
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-factory-m5.py" "${vr_tmp}" >/dev/null 2>&1; then
  echo "FAIL: factory with typed g1-kill-ratio-waiver ack should refuse (B-4)" >&2
  rc=1
else
  echo "OK: factory typed kill-ratio waiver refused (B-4)"
fi
rm -f "${vr_tmp}/evidence/acks/g1-kill-ratio-waiver-S-1.ack.yaml"
mkdir -p "${vr_tmp}/evidence/verdicts"
printf '%s\n' '{"schema":"migration/g1-kill-ratio-pin/v2-dual-denominator","status":"PINNED","g1_kill_ratio_threshold_pinned":true,"evaluation_against_measurement":{"pass":true}}' \
  > "${vr_tmp}/evidence/verdicts/g1-kill-ratio-pin.json"
printf '%s\n' '{"phase":"M5","verdict":"ACCEPT","accept_kind":"full","g1_kill_ratio":"pass","g1_kill_ratio_threshold_pinned":true}' \
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
# Architect E-20260814T212425Z — missing hex-digest file fail-closed (was deferred)
printf '%s\n' '{"task_id":"t_a1b2c3d4e5","role":"implementer","phase":"M3","identity":{"transform_class":"HARVEST","g2_applicability":"not_applicable","operand_count":1,"sizing_basis":"operand_count","extensions_declared":[]},"files_in_scope":["src/Foo.java"],"exit_criteria":[{"check":"compile","cmd":"true","expect":"rc=0"},{"check":"skills","assert":"AD-002E: consult or skills_unused; silence invalid"},{"check":"endpoint_contract","assert":"fixture"}],"refs":[{"key":"brief_identity_ack","path":"evidence/acks/brief-identity.ack","sha256":"pending"},{"key":"legacy_locus","path":"projects/legacy/Foo.java","sha256":"0000000000000000000000000000000000000000000000000000000000000000"}]}' \
  > "${kb_tmp}/evidence/bodies/bad.json"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-kanban-body.py" "${kb_tmp}" >/dev/null 2>&1; then
  echo "FAIL: unresolvable legacy_locus hex digest should refuse" >&2
  rc=1
else
  echo "OK: BODY_REF_DIGEST refused unresolvable locus path"
fi
# Positive: harvest file exists, path is the hashed file (not dest-relative alias)
mkdir -p "${kb_tmp}/.derived/legacy-at-3" "${kb_tmp}/dest"
printf 'harvest-pom\n' > "${kb_tmp}/.derived/legacy-at-3/pom.xml"
printf 'dest-pom\n' > "${kb_tmp}/dest/pom.xml"
python3 - "${kb_tmp}" "${SKILLS}/sdd/check-spec-readiness/scripts" <<'PY' || rc=1
import hashlib, importlib.util, json, sys
from pathlib import Path
kb, scripts = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location(
    "assemble_m3", scripts / "assemble-m3-bodies-from-partition.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
from specimen_agnostic import refs_path_sha_errors
root = kb / "dest"
harvest = (kb / ".derived/legacy-at-3/pom.xml").resolve()
path, sha = mod._legacy_locus(root, "pom.xml")
if Path(path).resolve() != harvest:
    print(f"FAIL: _legacy_locus stamped {path!r} not harvest {harvest}", file=sys.stderr)
    raise SystemExit(1)
if sha != hashlib.sha256(harvest.read_bytes()).hexdigest():
    print("FAIL: _legacy_locus digest is not harvest", file=sys.stderr)
    raise SystemExit(1)
dest_sha = hashlib.sha256((root / "pom.xml").read_bytes()).hexdigest()
if not refs_path_sha_errors(root, [{"key": "legacy_locus", "path": "pom.xml", "sha256": sha}]):
    print("FAIL: dest-relative path + harvest digest should refuse", file=sys.stderr)
    raise SystemExit(1)
errs = refs_path_sha_errors(root, [{"key": "legacy_locus", "path": path, "sha256": sha}])
if errs:
    print("FAIL: harvest path+digest should pass:", errs, file=sys.stderr)
    raise SystemExit(1)
print("OK: assembler stamps hashed harvest path; dest-relative alias refused")
# check-kanban-body positive with harvest path
body = {
  "task_id": "t_a1b2c3d4e5",
  "role": "implementer",
  "phase": "M3",
  "identity": {"transform_class": "CONFIG", "g2_applicability": "not_applicable",
               "operand_count": 1, "sizing_basis": "operand_count",
               "operand_class": "build_config",
               "extensions_declared": [], "extensions_apply": []},
  "files_in_scope": ["pom.xml"],
  "files_writable": ["pom.xml"],
  "exit_criteria": [
    {"check": "build_resolves", "cmd": "mvn -q compile"},
    {"check": "skills", "assert": "AD-002E: consult or skills_unused; silence invalid"},
  ],
  "refs": [
    {"key": "brief_identity_ack", "path": "evidence/acks/brief-identity.ack", "sha256": "pending"},
    {"key": "legacy_locus", "path": path, "sha256": sha},
  ],
}
(kb / "pom.xml").write_text("dest-pom\n")
(kb / "evidence/bodies/bad.json").write_text(json.dumps(body) + "\n")
PY
python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-kanban-body.py" "${kb_tmp}" || rc=1
# Architect E-20260814T205052Z — DD3 declare/apply/own
python3 - "${kb_tmp}" "${SKILLS}/sdd/check-spec-readiness/scripts" <<'PY' || rc=1
import json, sys
from pathlib import Path
kb, scripts = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(scripts))
from specimen_agnostic import (
    declared_extensions_for_paths,
    stamp_dd3_extensions,
    writes_pom_xml,
)
# T-3 path heuristic
got = declared_extensions_for_paths(
    ["src/main/java/org/x/rest/PetResource.java", "src/main/java/org/x/repository/jpa/Pet.java"]
)
if got != ["quarkus-hibernate-orm", "quarkus-rest", "quarkus-rest-jackson"]:
    print(f"FAIL: declared_extensions_for_paths got {got}", file=sys.stderr)
    raise SystemExit(1)
if declared_extensions_for_paths(["pom.xml", "src/main/resources/application.properties"]):
    print("FAIL: pom/properties must declare []", file=sys.stderr)
    raise SystemExit(1)
if declared_extensions_for_paths(["src/main/java/org/x/repository/jdbc/VisitJdbc.java"]):
    print("FAIL: jdbc path must declare [] (T-3 JdbcTemplate)", file=sys.stderr)
    raise SystemExit(1)
print("OK: T-3 declared_extensions_for_paths")
pom = {
    "task_id": "t_aaaaaaaa",
    "identity": {"story_id": "story-001"},
    "files_writable": ["pom.xml"],
    "files_in_scope": ["pom.xml"],
}
rest = {
    "task_id": "t_bbbbbbbb",
    "identity": {"story_id": "story-003"},
    "files_writable": ["src/main/java/org/x/rest/PetResource.java"],
    "files_in_scope": ["src/main/java/org/x/rest/PetResource.java"],
}
stamp_dd3_extensions([pom, rest])
if pom["identity"]["extensions_declared"] != []:
    print("FAIL: pom writer declared should be []", file=sys.stderr)
    raise SystemExit(1)
if pom["identity"]["extensions_apply"] != ["quarkus-rest", "quarkus-rest-jackson"]:
    print(f"FAIL: apply union {pom['identity'].get('extensions_apply')}", file=sys.stderr)
    raise SystemExit(1)
if "extensions_apply" in rest["identity"]:
    print("FAIL: non-writer must omit extensions_apply", file=sys.stderr)
    raise SystemExit(1)
if rest["identity"]["extensions_declared"] != ["quarkus-rest", "quarkus-rest-jackson"]:
    print(f"FAIL: rest declared {rest['identity']['extensions_declared']}", file=sys.stderr)
    raise SystemExit(1)
two_pom = [
    {"identity": {"story_id": "a"}, "files_writable": ["pom.xml"]},
    {"identity": {"story_id": "b"}, "files_writable": ["pom.xml"]},
]
try:
    stamp_dd3_extensions(two_pom)
except ValueError:
    print("OK: stamp_dd3_extensions refuses two pom.xml writers")
else:
    print("FAIL: two pom writers should refuse", file=sys.stderr)
    raise SystemExit(1)
print("OK: stamp_dd3_extensions union + sole writer")
PY
# missing extensions_declared on pom writer
python3 - "${kb_tmp}" <<'PY'
import json, sys
from pathlib import Path
kb = Path(sys.argv[1])
body = json.loads((kb / "evidence/bodies/bad.json").read_text())
body["identity"].pop("extensions_declared", None)
body["identity"].pop("extensions_apply", None)
(kb / "evidence/bodies/bad.json").write_text(json.dumps(body) + "\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-kanban-body.py" "${kb_tmp}" >/dev/null 2>&1; then
  echo "FAIL: missing extensions_declared should refuse" >&2
  rc=1
else
  echo "OK: BODY_EXTENSIONS_DECLARED refused missing key"
fi
# pom writer with declared but missing apply
python3 - "${kb_tmp}" <<'PY'
import json, sys
from pathlib import Path
kb = Path(sys.argv[1])
body = json.loads((kb / "evidence/bodies/bad.json").read_text())
body["identity"]["extensions_declared"] = []
body["identity"].pop("extensions_apply", None)
(kb / "evidence/bodies/bad.json").write_text(json.dumps(body) + "\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-kanban-body.py" "${kb_tmp}" >/dev/null 2>&1; then
  echo "FAIL: pom writer missing extensions_apply should refuse" >&2
  rc=1
else
  echo "OK: BODY_EXTENSIONS_APPLY refused missing apply on pom writer"
fi
# non-writer with apply present
python3 - "${kb_tmp}" "${SKILLS}/sdd/check-spec-readiness/scripts" <<'PY' || rc=1
import hashlib, json, sys
from pathlib import Path
kb, scripts = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(scripts))
from specimen_agnostic import sha256_file
foo = kb / "projects/legacy/Foo.java"
foo.parent.mkdir(parents=True, exist_ok=True)
foo.write_text("class Foo {}\n")
sha = sha256_file(foo)
body = {
  "task_id": "t_c1c1c1c1c1",
  "role": "implementer",
  "phase": "M3",
  "identity": {
    "transform_class": "HARVEST", "g2_applicability": "not_applicable",
    "operand_count": 1, "sizing_basis": "operand_count",
    "extensions_declared": ["quarkus-rest"],
    "extensions_apply": ["quarkus-rest"],
  },
  "files_in_scope": ["src/Foo.java"],
  "files_writable": ["src/Foo.java"],
  "exit_criteria": [
    {"check": "compile", "cmd": "true", "expect": "rc=0"},
    {"check": "skills", "assert": "AD-002E: consult or skills_unused; silence invalid"},
    {"check": "endpoint_contract", "assert": "fixture"},
  ],
  "refs": [
    {"key": "brief_identity_ack", "path": "evidence/acks/brief-identity.ack", "sha256": "pending"},
    {"key": "legacy_locus", "path": str(foo), "sha256": sha},
  ],
}
(kb / "src").mkdir(exist_ok=True)
(kb / "src/Foo.java").write_text("class Foo {}\n")
(kb / "evidence/bodies/bad.json").write_text(json.dumps(body) + "\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-kanban-body.py" "${kb_tmp}" >/dev/null 2>&1; then
  echo "FAIL: non-writer extensions_apply should refuse" >&2
  rc=1
else
  echo "OK: BODY_EXTENSIONS_APPLY refused apply on non-writer"
fi
# apply != sibling union
python3 - "${kb_tmp}" "${SKILLS}/sdd/check-spec-readiness/scripts" <<'PY' || rc=1
import hashlib, json, sys
from pathlib import Path
kb = Path(sys.argv[1])
harvest = (kb / ".derived/legacy-at-3/pom.xml")
sha = hashlib.sha256(harvest.read_bytes()).hexdigest()
path = str(harvest.resolve())
writer = {
  "task_id": "t_d1d1d1d1d1",
  "role": "implementer",
  "phase": "M3",
  "identity": {
    "story_id": "story-001",
    "transform_class": "CONFIG", "g2_applicability": "not_applicable",
    "operand_count": 1, "sizing_basis": "operand_count",
    "operand_class": "build_config",
    "extensions_declared": [],
    "extensions_apply": [],
  },
  "files_in_scope": ["pom.xml"],
  "files_writable": ["pom.xml"],
  "exit_criteria": [
    {"check": "build_resolves", "cmd": "mvn -q compile"},
    {"check": "skills", "assert": "AD-002E: consult or skills_unused; silence invalid"},
  ],
  "refs": [
    {"key": "brief_identity_ack", "path": "evidence/acks/brief-identity.ack", "sha256": "pending"},
    {"key": "legacy_locus", "path": path, "sha256": sha},
  ],
}
sib = {
  "task_id": "t_e1e1e1e1e1",
  "role": "implementer",
  "phase": "M3",
  "identity": {
    "story_id": "story-003",
    "transform_class": "HARVEST", "g2_applicability": "not_applicable",
    "operand_count": 1, "sizing_basis": "operand_count",
    "extensions_declared": ["quarkus-rest"],
  },
  "files_in_scope": ["src/Foo.java"],
  "files_writable": ["src/Foo.java"],
  "exit_criteria": [
    {"check": "compile", "cmd": "true", "expect": "rc=0"},
    {"check": "skills", "assert": "AD-002E: consult or skills_unused; silence invalid"},
    {"check": "endpoint_contract", "assert": "fixture"},
  ],
  "refs": [
    {"key": "brief_identity_ack", "path": "evidence/acks/brief-identity.ack", "sha256": "pending"},
    {"key": "legacy_locus", "path": path, "sha256": sha},
  ],
}
(kb / "evidence/bodies/bad.json").write_text(json.dumps(writer) + "\n")
(kb / "evidence/bodies/sib.json").write_text(json.dumps(sib) + "\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-kanban-body.py" "${kb_tmp}" >/dev/null 2>&1; then
  echo "FAIL: extensions_apply not equal to sibling union should refuse" >&2
  rc=1
else
  echo "OK: BODY_EXTENSIONS_APPLY refused apply != union"
fi
rm -f "${kb_tmp}/evidence/bodies/sib.json"
# restore harvest-path positive body for any later use, then prose-sha test overwrites
python3 - "${kb_tmp}" <<'PY'
import hashlib, json, sys
from pathlib import Path
kb = Path(sys.argv[1])
harvest = (kb / ".derived/legacy-at-3/pom.xml")
sha = hashlib.sha256(harvest.read_bytes()).hexdigest()
path = str(harvest.resolve())
body = {
  "task_id": "t_a1b2c3d4e5",
  "role": "implementer",
  "phase": "M3",
  "identity": {"transform_class": "CONFIG", "g2_applicability": "not_applicable",
               "operand_count": 1, "sizing_basis": "operand_count",
               "operand_class": "build_config",
               "extensions_declared": [], "extensions_apply": []},
  "files_in_scope": ["pom.xml"],
  "files_writable": ["pom.xml"],
  "exit_criteria": [
    {"check": "build_resolves", "cmd": "mvn -q compile"},
    {"check": "skills", "assert": "AD-002E: consult or skills_unused; silence invalid"},
  ],
  "refs": [
    {"key": "brief_identity_ack", "path": "evidence/acks/brief-identity.ack", "sha256": "pending"},
    {"key": "legacy_locus", "path": path, "sha256": sha},
  ],
}
(kb / "evidence/bodies/bad.json").write_text(json.dumps(body) + "\n")
PY
# Deputy E-20260811T131200Z — prose in sha256 slots must refuse
printf '%s\n' '{"task_id":"t_a1b2c3d4e5","role":"implementer","phase":"M3","identity":{"transform_class":"HARVEST","g2_applicability":"not_applicable","operand_count":1,"sizing_basis":"operand_count","extensions_declared":[]},"files_in_scope":["src/Foo.java"],"exit_criteria":[{"check":"compile","cmd":"true","expect":"rc=0"},{"check":"skills","assert":"AD-002E: consult or skills_unused; silence invalid"},{"check":"endpoint_contract","assert":"fixture"}],"refs":[{"key":"brief_identity_ack","path":"evidence/acks/brief-identity.ack","sha256":"pending"},{"key":"legacy_locus","path":"projects/legacy/Foo.java","sha256":"see-harvest-referent"}]}' \
  > "${kb_tmp}/evidence/bodies/bad.json"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-kanban-body.py" "${kb_tmp}" >/dev/null 2>&1; then
  echo "FAIL: non-hex sha256 prose should refuse" >&2
  rc=1
else
  echo "OK: BODY_REF_SHA256 refused non-hex prose"
fi
# Architect E-20260814T205052Z — two stories claiming pom.xml → file_overlap
pc_tmp="$(mktemp -d)"
mkdir -p "${pc_tmp}/evidence/briefs"
printf '%s\n' '{"stories":[{"story_id":"story-001","files_in_scope":["pom.xml","src/Foo.java"]},{"story_id":"story-002","files_in_scope":["pom.xml"]}]}' \
  > "${pc_tmp}/evidence/briefs/partition.json"
printf '%s\n' '{"entry_points":[{"kind":"http","file":"src/Foo.java","symbol":"foo"}],"totals":{"http_endpoints":1}}' \
  > "${pc_tmp}/inventory.json"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-partition-coverage.py" \
    "${pc_tmp}" --partition evidence/briefs/partition.json --inventory inventory.json \
    >/tmp/pc-dd3.out 2>/tmp/pc-dd3.err; then
  echo "FAIL: two stories claiming pom.xml should refuse file_overlap" >&2
  cat /tmp/pc-dd3.out /tmp/pc-dd3.err >&2
  rc=1
else
  if grep -q 'file_overlap:pom.xml' /tmp/pc-dd3.err /tmp/pc-dd3.out; then
    echo "OK: PARTITION_COVERAGE refused two pom.xml writers (file_overlap)"
  else
    echo "FAIL: expected file_overlap:pom.xml in coverage gaps" >&2
    cat /tmp/pc-dd3.out /tmp/pc-dd3.err >&2
    rc=1
  fi
fi
rm -rf "${pc_tmp}"

# WC-8: missing findings → INCONCLUSIVE (never silent VALID)
pc_tmp="$(mktemp -d)"
mkdir -p "${pc_tmp}/evidence/briefs"
printf '%s\n' '{"stories":[{"story_id":"story-001","files_in_scope":["src/Foo.java"]}]}' \
  > "${pc_tmp}/evidence/briefs/partition.json"
printf '%s\n' '{"entry_points":[{"kind":"http","file":"src/Foo.java","symbol":"foo"}],"totals":{"http_endpoints":1}}' \
  > "${pc_tmp}/inventory.json"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-partition-coverage.py" \
    "${pc_tmp}" --partition evidence/briefs/partition.json --inventory inventory.json \
    >/tmp/pc-wc8-miss.out 2>/tmp/pc-wc8-miss.err; then
  echo "FAIL: missing findings should be INCONCLUSIVE, not VALID" >&2
  cat /tmp/pc-wc8-miss.out /tmp/pc-wc8-miss.err >&2
  rc=1
else
  if grep -q 'INCONCLUSIVE' /tmp/pc-wc8-miss.out /tmp/pc-wc8-miss.err \
     && grep -q 'mta_skipped_missing' /tmp/pc-wc8-miss.out /tmp/pc-wc8-miss.err; then
    echo "OK: PARTITION_COVERAGE missing findings is INCONCLUSIVE (WC-8)"
  else
    echo "FAIL: expected INCONCLUSIVE + mta_skipped_missing" >&2
    cat /tmp/pc-wc8-miss.out /tmp/pc-wc8-miss.err >&2
    rc=1
  fi
fi
# WC-8: envelope violations dict present, no story.rules → INVALID
mkdir -p "${pc_tmp}/evidence"
printf '%s\n' '{"schema":"rhoai3.mta-findings/v1-provisional","violations":{"springboot-to-quarkus-00000":{"ruleID":"springboot-to-quarkus-00000","category":"mandatory","incidents":[]}}}' \
  > "${pc_tmp}/evidence/mta-findings.json"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-partition-coverage.py" \
    "${pc_tmp}" --partition evidence/briefs/partition.json --inventory inventory.json \
    >/tmp/pc-wc8-unaddr.out 2>/tmp/pc-wc8-unaddr.err; then
  echo "FAIL: findings present with no story.rules should be INVALID" >&2
  cat /tmp/pc-wc8-unaddr.out /tmp/pc-wc8-unaddr.err >&2
  rc=1
else
  if grep -q 'INVALID' /tmp/pc-wc8-unaddr.out /tmp/pc-wc8-unaddr.err \
     && grep -q 'mta_unaddressed' /tmp/pc-wc8-unaddr.out /tmp/pc-wc8-unaddr.err; then
    echo "OK: PARTITION_COVERAGE unaddressed findings is INVALID (WC-8)"
  else
    echo "FAIL: expected INVALID + mta_unaddressed" >&2
    cat /tmp/pc-wc8-unaddr.out /tmp/pc-wc8-unaddr.err >&2
    rc=1
  fi
fi
# WC-8: story.rules covers the fired id → VALID
printf '%s\n' '{"stories":[{"story_id":"story-001","files_in_scope":["src/Foo.java"],"rules":["springboot-to-quarkus-00000"]}]}' \
  > "${pc_tmp}/evidence/briefs/partition.json"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-partition-coverage.py" \
    "${pc_tmp}" --partition evidence/briefs/partition.json --inventory inventory.json \
    >/tmp/pc-wc8-ok.out 2>/tmp/pc-wc8-ok.err; then
  if grep -q 'VALID' /tmp/pc-wc8-ok.out; then
    echo "OK: PARTITION_COVERAGE addressed findings is VALID (WC-8)"
  else
    echo "FAIL: expected VALID when story.rules covers findings" >&2
    cat /tmp/pc-wc8-ok.out /tmp/pc-wc8-ok.err >&2
    rc=1
  fi
else
  echo "FAIL: addressed findings should be VALID" >&2
  cat /tmp/pc-wc8-ok.out /tmp/pc-wc8-ok.err >&2
  rc=1
fi
rm -rf "${pc_tmp}"

# WC-2: normalize keeps unmatched/skipped/errors and writes rules-coverage.json
nf_tmp="$(mktemp -d)"
python3 - "${nf_tmp}" <<'PY'
import json, sys
from pathlib import Path
d = Path(sys.argv[1])
raw = [
  {
    "name": "quarkus/springboot",
    "violations": {
      "springboot-to-quarkus-00000": {
        "category": "mandatory",
        "incidents": [{"uri": "file://x", "lineNumber": 1, "message": "m", "codeSnip": "c"}],
      }
    },
    "unmatched": ["springboot-to-quarkus-00001"],
    "skipped": ["eap-00000"],
    "errors": {"broken-rule-00000": "failed to evaluate"},
  }
]
(d / "raw.json").write_text(json.dumps(raw) + "\n")
PY
if python3 "${SKILLS}/analysis/scan-with-mta/scripts/normalize-findings.py" \
    "${nf_tmp}/raw.json" "/projects/.tools/kantra/kantra" "quarkus" "legacy-at-3:deadbeef" \
    "${nf_tmp}/rules-coverage.json" "${nf_tmp}/static-report/index.html" \
    >/tmp/nf-wc2.out 2>/tmp/nf-wc2.err; then
  python3 - "${nf_tmp}" <<'PY' || rc=1
import json, sys
from pathlib import Path
d = Path(sys.argv[1])
env = json.loads((d / "raw.json").read_text())
cov = json.loads((d / "rules-coverage.json").read_text())
assert env["schema"] == "rhoai3.mta-findings/v1-provisional"
assert "springboot-to-quarkus-00000" in env["violations"]
assert env["rules_coverage"]["totals"]["fired"] == 1
assert env["rules_coverage"]["totals"]["unmatched"] == 1
assert env["rules_coverage"]["totals"]["skipped"] == 1
assert env["rules_coverage"]["totals"]["errors"] == 1
assert env["rules_coverage"]["static_report_present"] is False
rs = cov["rulesets"][0]
assert rs["unmatched"] == ["springboot-to-quarkus-00001"]
assert rs["skipped"] == ["eap-00000"]
assert "broken-rule-00000" in rs["errors"]
assert "unmatched" in env["raw_tool_keys"]
print("OK: normalize-findings keeps unmatched/skipped/errors (WC-2)")
PY
else
  echo "FAIL: normalize-findings WC-2 fixture" >&2
  cat /tmp/nf-wc2.out /tmp/nf-wc2.err >&2
  rc=1
fi
rm -rf "${nf_tmp}"
rm -rf "${kb_tmp}"

echo "== story-sizing operand_count (Architect E-110403Z) =="
python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-operand-count.py" "${ROOT}" \
  "${ROOT}/.hermes/skills/harness/validate-contracts/fixtures/story-sizing/ar-size-good.json" || rc=1
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-operand-count.py" "${ROOT}" \
  "${ROOT}/.hermes/skills/harness/validate-contracts/fixtures/story-sizing/ar-size-bad-missing.json" >/dev/null 2>&1; then
  echo "FAIL: missing operand_count should refuse" >&2
  rc=1
else
  echo "OK: missing operand_count refused"
fi
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-operand-count.py" "${ROOT}" \
  "${ROOT}/.hermes/skills/harness/validate-contracts/fixtures/story-sizing/ar-size-bad-overcap.json" >/dev/null 2>&1; then
  echo "FAIL: over-cap operand_count should refuse" >&2
  rc=1
else
  echo "OK: over-cap operand_count refused"
fi
python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-operand-count.py" "${ROOT}" \
  "${ROOT}/.hermes/skills/harness/validate-contracts/fixtures/story-sizing/ar-size-good.json" --wall-fit || rc=1
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-operand-count.py" "${ROOT}" \
  "${ROOT}/.hermes/skills/harness/validate-contracts/fixtures/story-sizing/ar-size-bad-wallfit.json" --wall-fit \
  >/dev/null 2>&1; then
  echo "FAIL: wall-fit 60@3600 should refuse" >&2
  rc=1
else
  echo "OK: wall-fit 60@3600 refused"
fi

echo "== wall-as-terminal exit-eval (Architect E-110403Z) =="
wall_tmp="$(mktemp -d)"
mkdir -p "${wall_tmp}/evidence/runs/t_fixture_wall"
cp "${ROOT}/.hermes/skills/harness/validate-contracts/fixtures/wall-exit-eval/ar-wall-good/exit-eval.json" \
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
if python3 "${HARNESS}/record-run-evidence/scripts/check-test-write-checkpoint-lag.py" \
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
if python3 "${HARNESS}/record-run-evidence/scripts/stamp-implementer-checkpoint.py" \
  "${tc_tmp}/evidence/runs/t_tcgate/checkpoint.json" \
  --completed src/test/java/com/demo/ATests.java >/dev/null 2>&1; then
  echo "FAIL: src/test stamp without pom/test-compile should refuse" >&2
  rc=1
else
  echo "OK: src/test checkpoint stamp refused without test-compile gate"
fi
# Fixture skip path still works for shape tests (env-gated; live seats FORBIDDEN)
if python3 "${HARNESS}/record-run-evidence/scripts/stamp-implementer-checkpoint.py" \
  "${tc_tmp}/evidence/runs/t_tcgate/checkpoint.json" \
  --completed src/test/java/com/demo/ATests.java --skip-test-compile-gate >/dev/null 2>&1; then
  echo "FAIL: --skip-test-compile-gate without fixture env should refuse" >&2
  rc=1
else
  echo "OK: live skip-test-compile-gate refused without fixture env"
fi
RHOAI3_FIXTURE_ALLOW_SKIP_TEST_COMPILE=1 \
python3 "${HARNESS}/record-run-evidence/scripts/stamp-implementer-checkpoint.py" \
  "${tc_tmp}/evidence/runs/t_tcgate/checkpoint.json" \
  --completed src/test/java/com/demo/ATests.java --skip-test-compile-gate || rc=1
python3 "${HARNESS}/record-run-evidence/scripts/check-implementer-checkpoint.py" \
  "${tc_tmp}/evidence/runs/t_tcgate/checkpoint.json" || rc=1
rm -rf "${tc_tmp}"

echo "== body-digest immutability (Architect E-111424Z) =="
DIGEST="$(python3 -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path('${ROOT}/.hermes/skills/harness/validate-contracts/fixtures/body-digest/ar-digest-good/body.json').read_bytes()).hexdigest())")"
python3 "${HARNESS}/record-run-evidence/scripts/check-body-digest-match.py" "${ROOT}" \
  --body "${ROOT}/.hermes/skills/harness/validate-contracts/fixtures/body-digest/ar-digest-good/body.json" \
  --expect "${DIGEST}" || rc=1
if python3 "${HARNESS}/record-run-evidence/scripts/check-body-digest-match.py" "${ROOT}" \
  --body "${ROOT}/.hermes/skills/harness/validate-contracts/fixtures/body-digest/ar-digest-good/body.json" \
  --expect deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef \
  >/dev/null 2>&1; then
  echo "FAIL: digest mismatch should refuse" >&2
  rc=1
else
  echo "OK: body digest mismatch refused"
fi

echo "== T-8 dual-oracle refuse (AR-4.4 / derive-story-oracles) =="
t8_tmp="$(mktemp -d)"
mkdir -p "${t8_tmp}/evidence/bodies"
# correct + wrong on build_config must FAIL
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "build_config", "story_id": "S-T8"},
  "files_writable": ["pom.xml"],
  "exit_criteria": [
    {"check": "build_resolves"},
    {"check": "http_semantics"},
  ],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-surgical-scopes.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "FAIL: dual-oracle (build_resolves+http_semantics on build_config) should refuse" >&2
  rc=1
else
  echo "OK: T-8 dual-oracle refused"
fi
# legal-only must PASS
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "build_config", "story_id": "S-T8b"},
  "files_writable": ["pom.xml"],
  "exit_criteria": [{"check": "build_resolves"}],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-surgical-scopes.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "OK: T-8 legal-only build_config exit passed"
else
  echo "FAIL: legal-only build_resolves should pass" >&2
  rc=1
fi
# persistence + mapping_valid PASS; persistence + http_semantics FAIL
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "persistence", "story_id": "S-T8p"},
  "files_writable": ["src/main/java/x/Repo.java"],
  "exit_criteria": [{"check": "mapping_valid"}],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-surgical-scopes.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "OK: T-8 legal-only persistence mapping_valid passed"
else
  echo "FAIL: legal-only mapping_valid should pass" >&2
  rc=1
fi
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "persistence", "story_id": "S-T8pw"},
  "files_writable": ["src/main/java/x/Repo.java"],
  "exit_criteria": [{"check": "mapping_valid"}, {"check": "http_semantics"}],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-surgical-scopes.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "FAIL: persistence+http_semantics should refuse" >&2
  rc=1
else
  echo "OK: T-8 persistence foreign http_semantics refused"
fi
# bootstrap + app_boots PASS; bootstrap + health_probe FAIL
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "bootstrap", "story_id": "S-T8bstrap"},
  "files_writable": ["src/main/java/x/App.java"],
  "exit_criteria": [{"check": "app_boots"}],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-surgical-scopes.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "OK: T-8 legal-only bootstrap app_boots passed"
else
  echo "FAIL: legal-only app_boots should pass" >&2
  rc=1
fi
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "bootstrap", "story_id": "S-T8bh"},
  "files_writable": ["src/main/java/x/App.java"],
  "exit_criteria": [{"check": "health_probe"}],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-surgical-scopes.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "FAIL: bootstrap+health_probe should refuse" >&2
  rc=1
else
  echo "OK: T-8 bootstrap foreign health_probe refused"
fi
# unknown class fail-closed (not full vocab)
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "not_a_class", "story_id": "S-T8u"},
  "files_writable": ["pom.xml"],
  "exit_criteria": [{"check": "http_semantics"}],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-surgical-scopes.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "FAIL: unknown operand_class should refuse (not inherit full vocab)" >&2
  rc=1
else
  echo "OK: T-8 unknown operand_class fail-closed"
fi
# T-8 AMEND: multi-class union is legal (rest+persistence)
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": ["rest", "persistence"], "story_id": "S-T8m"},
  "files_writable": [
    "src/main/java/x/OwnerRestController.java",
    "src/main/java/x/Owner.java",
  ],
  "exit_criteria": [
    {"check": "http_semantics", "cmd": "mvn -q test"},
    {"check": "mapping_valid", "cmd": "mvn -q verify"},
  ],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-surgical-scopes.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "OK: T-8 multi-class rest+persistence union passed"
else
  echo "FAIL: multi-class rest+persistence should pass AR-4.4 (T-8 AMEND)" >&2
  rc=1
fi
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "user_story", "story_id": "S-T8us"},
  "files_writable": ["src/main/java/x/OwnerRestController.java"],
  "exit_criteria": [
    {"check": "http_semantics", "cmd": "mvn -q test"},
  ],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-surgical-scopes.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "OK: T-8 user_story AC Maven test passed AR-4.4"
else
  echo "FAIL: user_story with AC mvn -q test should pass AR-4.4 (A-3c.2)" >&2
  rc=1
fi
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "user_story", "story_id": "S-T8us-curl"},
  "files_writable": ["src/main/java/x/OwnerRestController.java"],
  "exit_criteria": [
    {"check": "http_semantics", "cmd": "curl -sf http://127.0.0.1:8080/api/owners"},
  ],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-semantic-exits.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "FAIL: user_story AC curl should refuse (not a card exit)" >&2
  rc=1
else
  echo "OK: T-8 user_story AC curl refused"
fi
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "user_story", "story_id": "S-T8us-sh"},
  "files_writable": ["src/main/java/x/OwnerRestController.java"],
  "exit_criteria": [
    {"check": "http_semantics", "cmd": "./verify-ac.sh"},
  ],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-semantic-exits.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "FAIL: user_story AC script should refuse (not a card exit)" >&2
  rc=1
else
  echo "OK: T-8 user_story AC script refused"
fi
# AR-2.3–2.7 must follow T-8 class stamps (not filename RESTISH → create_fk)
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "persistence", "story_id": "S-T8p-sem"},
  "files_writable": ["src/main/java/x/JpaOwnerRepositoryImpl.java"],
  "exit_criteria": [{"check": "mapping_valid", "cmd": "mvn -q test"}],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-semantic-exits.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "OK: T-8 semantic-exits persistence mapping_valid (Repository path) passed"
else
  echo "FAIL: persistence mapping_valid should pass AR-2.3–2.7 (not require create_fk)" >&2
  rc=1
fi
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "rest", "story_id": "S-T8r-sem"},
  "files_writable": ["src/main/java/x/OwnerRestController.java"],
  "exit_criteria": [{"check": "http_semantics", "cmd": "mvn -q test"}],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-semantic-exits.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "OK: T-8 semantic-exits rest http_semantics without create_fk passed"
else
  echo "FAIL: rest http_semantics should pass AR-2.3–2.7 without create_fk" >&2
  rc=1
fi
# build_resolves cmd must be executable shell, not concern-table slash-OR gloss
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "build_config", "story_id": "S-T8br-bad"},
  "files_writable": ["pom.xml"],
  "exit_criteria": [{"check": "build_resolves", "cmd": "mvn compile / quarkus:build exit 0"}],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-semantic-exits.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "FAIL: build_resolves technique-table gloss should refuse" >&2
  rc=1
else
  echo "OK: T-8 semantic-exits build_resolves slash-OR gloss refused"
fi
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "build_config", "story_id": "S-T8br-ok"},
  "files_writable": ["pom.xml"],
  "exit_criteria": [{"check": "build_resolves", "cmd": "mvn -q compile"}],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-semantic-exits.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "OK: T-8 semantic-exits build_resolves mvn -q compile passed"
else
  echo "FAIL: build_resolves cmd 'mvn -q compile' should pass AR-2.3–2.7" >&2
  rc=1
fi
# SR-13: http_semantics technique prose in cmd must refuse (not only slash-OR)
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "rest", "story_id": "S-T8r-prose"},
  "files_writable": ["src/main/java/x/OwnerRestController.java"],
  "exit_criteria": [{"check": "http_semantics", "cmd": "@QuarkusTest + REST Assured status/body"}],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-semantic-exits.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "FAIL: http_semantics technique prose in cmd should refuse" >&2
  rc=1
else
  echo "OK: T-8 semantic-exits http_semantics prose cmd refused"
fi
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "rest", "story_id": "S-T8r-ok"},
  "files_writable": ["src/main/java/x/OwnerRestController.java"],
  "exit_criteria": [{"check": "http_semantics", "cmd": "mvn -q test"}],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-semantic-exits.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "OK: T-8 semantic-exits http_semantics mvn -q test passed"
else
  echo "FAIL: http_semantics cmd 'mvn -q test' should pass AR-2.3–2.7" >&2
  rc=1
fi
rm -rf "${t8_tmp}"
if [ -f "${ROOT}/governance/contracts/semantic-exits.md" ]; then
  echo "FAIL: semantic-exits.md still under contracts/ (T-8/GRT retire)" >&2
  rc=1
elif [ -f "${ROOT}/.hermes/skills/sdd/derive-story-oracles/SKILL.md" ]; then
  echo "OK: semantic-exits retired; derive-story-oracles present (T-8)"
else
  echo "FAIL: semantic-exits retirement incomplete" >&2
  rc=1
fi

echo "== L2 mint oracles (SR-13 discriminating exit / task_id / refs) =="
python3 - "${SKILLS}/sdd/check-spec-readiness/scripts" <<'PY' || rc=1
import hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

scripts = Path(sys.argv[1])
sys.path.insert(0, str(scripts))
from specimen_agnostic import (
    exit_cmd_discriminating_errors,
    minted_task_id_errors,
    proves_executable_errors,
    refs_path_sha_errors,
)

cli = scripts / "assert-mint-oracles.py"
failures: list[str] = []


def expect(cond: bool, msg: str) -> None:
    if cond:
        print(f"OK: {msg}")
        return
    failures.append(msg)
    print(f"FAIL: {msg}", file=sys.stderr)


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(cli), *args],
        capture_output=True,
        text=True,
    )


td = Path(tempfile.mkdtemp())
dest = td / "dest"
dest.mkdir()
(dest / "pom.xml").write_text(
    "<project><modelVersion>4.0.0</modelVersion>"
    "<groupId>x</groupId><artifactId>x</artifactId>"
    "<version>1</version></project>\n",
    encoding="utf-8",
)
harvest = td / "harvest-pom.xml"
harvest.write_text("harvest-bytes\n", encoding="utf-8")
hsha = hashlib.sha256(harvest.read_bytes()).hexdigest()


def body(**kw):
    b = {
        "phase": "M3",
        "task_id": "t_aabbccdd",
        "files_writable": ["src/main/java/x/Foo.java"],
        "exit_criteria": [{"check": "http_semantics", "cmd": "mvn -q test"}],
        "refs": [
            {
                "key": "brief_identity_ack",
                "path": "evidence/acks/brief-identity.ack",
                "sha256": "pending",
            },
            {
                "key": "legacy_locus",
                "path": str(harvest.resolve()),
                "sha256": hsha,
            },
        ],
    }
    b.update(kw)
    return b


errs = exit_cmd_discriminating_errors(dest, body())
expect(bool(errs) and "proving test" in errs[0], "vacuous mvn -q test refused")

errs = exit_cmd_discriminating_errors(
    dest,
    body(exit_criteria=[{"check": "http_semantics", "cmd": "true"}]),
)
expect(bool(errs) and "always succeeds" in errs[0], "cmd true refused")

errs = exit_cmd_discriminating_errors(
    dest,
    body(
        files_writable=["pom.xml"],
        exit_criteria=[{"check": "build_resolves", "cmd": "mvn -q compile"}],
    ),
)
expect(errs == [], "compile + writable pom can fail")

errs = exit_cmd_discriminating_errors(
    dest,
    body(
        exit_criteria=[
            {
                "check": "http_semantics",
                "cmd": "curl -sf http://127.0.0.1:8080/api/owners",
            }
        ]
    ),
)
expect(
    bool(errs) and "Maven vehicle" in errs[0],
    "AC curl is not a card exit",
)

errs = exit_cmd_discriminating_errors(
    dest,
    body(exit_criteria=[{"check": "http_semantics", "cmd": "./verify-ac.sh"}]),
)
expect(
    bool(errs) and "Maven vehicle" in errs[0],
    "script card exit refused",
)

errs = exit_cmd_discriminating_errors(
    dest,
    body(exit_criteria=[{"check": "http_semantics", "cmd": "mvn -q verify"}]),
)
expect(
    bool(errs) and "proving test" in errs[0],
    "mvn verify is L2a test-shaped",
)

errs = exit_cmd_discriminating_errors(
    dest,
    body(
        files_writable=["pom.xml"],
        exit_criteria=[{"check": "http_semantics", "cmd": "mvn -q test-compile"}],
    ),
)
expect(errs == [], "mvn test-compile is not L2a test-shaped (Issue 6)")

testp = dest / "src/test/java/x/ExistingTest.java"
testp.parent.mkdir(parents=True)
testp.write_text("class ExistingTest {}\n", encoding="utf-8")
errs = exit_cmd_discriminating_errors(dest, body())
expect(
    bool(errs) and "proving test" in errs[0],
    "L2a unrelated remaining test does not satisfy SR-13",
)
named = body(
    files_writable=[
        "src/main/java/x/Foo.java",
        "src/test/java/x/FooTest.java",
    ],
    exit_criteria=[
        {
            "check": "http_semantics",
            "cmd": "mvn -q test",
            "proves": ["src/test/java/x/FooTest.java"],
        }
    ],
)
errs = exit_cmd_discriminating_errors(dest, named)
expect(
    errs == [],
    "L2a named proving test in write-set passes despite unrelated dest test",
)
stolen = body(
    exit_criteria=[
        {
            "check": "http_semantics",
            "cmd": "mvn -q test",
            "proves": ["src/test/java/x/ExistingTest.java"],
        }
    ]
)
errs = exit_cmd_discriminating_errors(dest, stolen)
expect(
    bool(errs) and "files_writable" in errs[0],
    "L2a proves outside this write-set refused",
)
b1p = dest / "src/test/java/x/FooTest.java"
b1p.parent.mkdir(parents=True, exist_ok=True)
b1p.write_text("class FooTest { void restSemantics() { } }\n", encoding="utf-8")
errs = exit_cmd_discriminating_errors(dest, named)
expect(
    bool(errs) and "@Test" in " ".join(errs),
    "B-1 file with methods but no @Test fails the card",
)
b1p.write_text(
    "import org.junit.jupiter.api.Test;\n"
    "class FooTest { @Test void restSemantics() { } }\n",
    encoding="utf-8",
)
errs = exit_cmd_discriminating_errors(dest, named)
expect(errs == [], "B-1 existing @Test in write-set mints")
c_errs = proves_executable_errors(dest, named, stage="complete")
expect(
    bool(c_errs) and "surefire" in " ".join(c_errs).lower(),
    "B-1 complete requires surefire report",
)
sure = dest / "target" / "surefire-reports"
sure.mkdir(parents=True)
(sure / "TEST-x.FooTest.xml").write_text(
    '<?xml version="1.0"?><testsuite name="x.FooTest" tests="1">'
    '<testcase classname="x.FooTest" name="restSemantics"/></testsuite>\n',
    encoding="utf-8",
)
c_errs = proves_executable_errors(dest, named, stage="complete")
expect(c_errs == [], "B-1 complete with @Test + surefire passes")
b1p.unlink()
testp.unlink()

fit = Path(tempfile.mkdtemp())
(fit / "pom.xml").write_text(
    "<project><build><plugins><plugin>"
    "<artifactId>maven-surefire-plugin</artifactId>"
    "<configuration><failIfNoTests>true</failIfNoTests></configuration>"
    "</plugin></plugins></build></project>\n",
    encoding="utf-8",
)
errs = exit_cmd_discriminating_errors(fit, body())
expect(
    bool(errs) and "proving test" in errs[0],
    "failIfNoTests=true is not a mint recipe (L2a/L4)",
)

expect(
    bool(minted_task_id_errors({"task_id": "story-006"})),
    "story-006 task_id refused",
)
expect(
    minted_task_id_errors({"task_id": "t_aabbccdd"}) == [],
    "t_aabbccdd task_id passed",
)
expect(
    bool(
        minted_task_id_errors(
            {"task_id": "t_aabbccdd"}, expect_task_id="t_deadbeef"
        )
    ),
    "expect-task-id mismatch refused",
)
expect(
    bool(
        refs_path_sha_errors(
            dest,
            [{"key": "legacy_locus", "path": "pom.xml", "sha256": hsha}],
        )
    ),
    "dest-relative path + harvest digest refused",
)

bodies = td / "bodies"
bodies.mkdir()
(bodies / "vacuous.json").write_text(json.dumps(body()) + "\n", encoding="utf-8")
(bodies / "story-id.json").write_text(
    json.dumps(body(task_id="story-006")) + "\n", encoding="utf-8"
)
(bodies / "dest-rel.json").write_text(
    json.dumps(
        body(
            files_writable=["pom.xml"],
            exit_criteria=[
                {"check": "build_resolves", "cmd": "mvn -q compile"}
            ],
            refs=[
                {
                    "key": "brief_identity_ack",
                    "path": "evidence/acks/brief-identity.ack",
                    "sha256": "pending",
                },
                {
                    "key": "legacy_locus",
                    "path": "pom.xml",
                    "sha256": hsha,
                },
            ],
        )
    )
    + "\n",
    encoding="utf-8",
)

r = run([str(dest), "--body", str(bodies / "vacuous.json")])
expect(r.returncode == 1, "CLI vacuous mvn -q test refused")

good = body(
    files_writable=["pom.xml"],
    exit_criteria=[{"check": "build_resolves", "cmd": "mvn -q compile"}],
)
good_path = td / "good.json"
good_path.write_text(json.dumps(good) + "\n", encoding="utf-8")
r = run([str(dest), "--body", str(good_path)])
expect(r.returncode == 0, "CLI corrected compile+card+harvest passed")

r = run([str(dest), "--body", str(bodies / "story-id.json")])
expect(r.returncode == 1, "CLI story-006 task_id refused")

r = run([str(dest), "--corpus", str(bodies)])
expect(r.returncode == 0, "CLI corpus of 3 defectives refused all")

mixed = td / "mixed"
mixed.mkdir()
for p in bodies.iterdir():
    shutil.copy(p, mixed / p.name)
shutil.copy(good_path, mixed / "good.json")
r = run([str(dest), "--corpus", str(mixed)])
expect(
    r.returncode == 1,
    "CLI corpus with one corrected body is not vacuous-green",
)

r = run(["--help"])
help_txt = (r.stdout or "") + (r.stderr or "")
expect(
    not any(
        ln.strip().startswith(("OK:", "PASS:")) for ln in help_txt.splitlines()
    ),
    "--help has no OK:/PASS: verdict",
)

shutil.rmtree(td, ignore_errors=True)
shutil.rmtree(fit, ignore_errors=True)
if failures:
    raise SystemExit(1)
print("OK: L2 mint oracles both-ways")
PY

echo "== A-3c T-8 AMEND (AC oracles + operand_class set) =="
python3 - "${SKILLS}/sdd/check-spec-readiness/scripts" <<'PY' || rc=1
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

scripts = Path(sys.argv[1])
sys.path.insert(0, str(scripts))
from specimen_agnostic import (
    operand_classes_of,
    semantic_exit_cmd_ok,
    skills_for_operand_classes,
)

spec = importlib.util.spec_from_file_location(
    "assemble_m3", scripts / "assemble-m3-bodies-from-partition.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
oc_mod = importlib.util.spec_from_file_location(
    "check_operand_count", scripts / "check-operand-count.py"
)
ocount = importlib.util.module_from_spec(oc_mod)
oc_mod.loader.exec_module(ocount)

failures: list[str] = []


def expect(cond: bool, msg: str) -> None:
    if cond:
        print(f"OK: {msg}")
        return
    failures.append(msg)
    print(f"FAIL: {msg}", file=sys.stderr)


expect(not semantic_exit_cmd_ok("http_semantics", "curl -sf http://127.0.0.1:8080/x"), "curl refused")
expect(not semantic_exit_cmd_ok("http_semantics", "./verify-ac.sh"), "script refused")
expect(semantic_exit_cmd_ok("http_semantics", "mvn -q verify"), "mvn verify ok")
expect(semantic_exit_cmd_ok("http_semantics", "mvn -q test-compile"), "mvn test-compile ok")
expect(not semantic_exit_cmd_ok("http_semantics", "true"), "true still refused")
expect(not semantic_exit_cmd_ok("http_semantics", "@QuarkusTest + REST Assured status/body"), "prose still refused")
expect(
    operand_classes_of({"identity": {"operand_class": ["rest", "persistence"]}})
    == ["rest", "persistence"],
    "operand_class list parses",
)
expect(
    operand_classes_of({"identity": {"operand_class": "['rest', 'persistence']"}})
    == ["rest", "persistence"],
    "str(list) accident parses",
)
expect(
    skills_for_operand_classes(["rest", "persistence"])
    == ["spring-to-quarkus-patterns", "form-entity-persistence"],
    "B-16 skills attach by class",
)

td = Path(tempfile.mkdtemp())
root = td / "dest"
harvest = td / ".derived" / "legacy-at-3" / "src/main/java/x/OwnerResource.java"
harvest.parent.mkdir(parents=True)
harvest.write_text("class OwnerResource {}\n", encoding="utf-8")
root.mkdir()
(root / "pom.xml").write_text("<project/>\n", encoding="utf-8")
test_src = root / "src/test/java/x/OwnerResourceTest.java"
test_src.parent.mkdir(parents=True)
test_src.write_text(
    "import org.junit.jupiter.api.Test;\n"
    "class OwnerResourceTest { @Test void httpSemantics() { } }\n",
    encoding="utf-8",
)

story = {
    "story_id": "story-owners",
    "operand_class": ["rest", "persistence"],
    "files_in_scope": [
        "src/main/java/x/OwnerResource.java",
        "src/main/java/x/Owner.java",
        "src/test/java/x/OwnerResourceTest.java",
    ],
    "acceptance_criteria": [
        {
            "check": "http_semantics",
            "cmd": "mvn -q test",
            "proves": ["src/test/java/x/OwnerResourceTest.java"],
        },
        {"check": "mapping_valid", "cmd": "mvn -q verify"},
    ],
}
body = mod.assemble_one(story, root, measured_operands=ocount.measured_operands)
cmds = [x.get("cmd") for x in body["exit_criteria"] if isinstance(x, dict)]
expect(body["identity"]["operand_class"] == ["rest", "persistence"], "assembler stamps class set")
expect(
    body["identity"]["operand_skills"]
    == ["spring-to-quarkus-patterns", "form-entity-persistence"],
    "assembler stamps B-16 skills",
)
expect("mvn -q test" in cmds, "AC Maven test stamped")
expect("mvn -q verify" in cmds, "AC Maven verify stamped")
expect(
    [x.get("check") for x in body["exit_criteria"] if isinstance(x, dict)].count(
        "http_semantics"
    )
    == 1,
    "no extra default http_semantics",
)

vacuous = dict(story)
vacuous["story_id"] = "story-true"
vacuous["acceptance_criteria"] = [
    {"check": "http_semantics", "cmd": "true"}
]
try:
    mod.assemble_one(vacuous, root, measured_operands=ocount.measured_operands)
except ValueError as exc:
    expect("discriminating" in str(exc) or "true" in str(exc), "vacuous true AC refused at assemble")
else:
    expect(False, "vacuous true AC refused at assemble")

bare = {
    "story_id": "story-bare-rest",
    "operand_class": "rest",
    "files_in_scope": ["src/main/java/x/OwnerResource.java"],
}
try:
    mod.assemble_one(bare, root, measured_operands=ocount.measured_operands)
except ValueError as exc:
    expect("OBJECT default" in str(exc), "rest without AC/tests refuses default mvn -q test")
else:
    expect(False, "rest without AC/tests refuses default mvn -q test")

scripted = dict(story)
scripted["story_id"] = "story-script"
scripted["acceptance_criteria"] = [
    {"check": "http_semantics", "cmd": "./verify-ac.sh"}
]
try:
    mod.assemble_one(scripted, root, measured_operands=ocount.measured_operands)
except ValueError as exc:
    expect("Maven vehicle" in str(exc) or "curl/scripts" in str(exc), "script AC refused at assemble")
else:
    expect(False, "script AC refused at assemble")

unknown = {
    "story_id": "story-unknown",
    "operand_class": "not_a_class",
    "files_in_scope": ["src/main/java/x/OwnerResource.java"],
    "acceptance_criteria": [
        {"check": "http_semantics", "cmd": "mvn -q test"}
    ],
}
try:
    mod.assemble_one(unknown, root, measured_operands=ocount.measured_operands)
except ValueError as exc:
    expect("unknown operand_class" in str(exc), "unknown class still fail-closed")
else:
    expect(False, "unknown class still fail-closed")

cfg_harvest = td / ".derived" / "legacy-at-3" / "pom.xml"
cfg_harvest.write_text("harvest-pom\n", encoding="utf-8")
cfg = {
    "story_id": "story-pom",
    "operand_class": "build_config",
    "files_in_scope": ["pom.xml"],
}
cfg_body = mod.assemble_one(cfg, root, measured_operands=ocount.measured_operands)
expect(
    cfg_body["exit_criteria"][0]["cmd"] == "mvn -q compile",
    "build_config still stamps compile (not test)",
)

if failures:
    raise SystemExit(1)
print("OK: A-3c Maven-only AC oracles + operand_class set")
PY

echo "== record-run-evidence (AD-H §19) =="
python3 "${HARNESS}/record-run-evidence/scripts/check-provenance.py" "${ROOT}" || rc=1
ap_tmp="$(mktemp -d)"
mkdir -p "${ap_tmp}/evidence/tasks"
printf '%s\n' '{"id":"t_a1b2c3d4e5","phase":"M3","role":"implementer","status":"done","brief_id":"B-1","ac_ids":["AC-1"],"files_in_scope":["src/"],"deps":[]}' \
  > "${ap_tmp}/evidence/tasks/bad.json"
if python3 "${HARNESS}/record-run-evidence/scripts/check-provenance.py" "${ap_tmp}" >/dev/null 2>&1; then
  echo "FAIL: complete IMPLEMENT without worker_session_id should refuse" >&2
  rc=1
else
  echo "OK: missing worker_session_id refused"
fi
printf '%s\n' '{"id":"t_a1b2c3d4e5","phase":"M3","role":"implementer","status":"done","provenance":{"task_id":"t_a1b2c3d4e5","task_run_id":"1","worker_session_id":"sess1","soul_path":"/tmp/no-such-soul.md","soul_sha":"deadbeef","skill_tips":{"ground-in-harvest":"abc"},"model_id":"unknown","citations":{"brief_or_story_id":"B-1","legacy_locus":"projects/legacy/Foo.java:1-10"},"artifacts":[]}}' \
  > "${ap_tmp}/evidence/tasks/bad.json"
if python3 "${HARNESS}/record-run-evidence/scripts/check-provenance.py" "${ap_tmp}" >/dev/null 2>&1; then
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
python3 "${HARNESS}/record-run-evidence/scripts/check-provenance.py" "${ap_tmp}" || rc=1
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

echo "== R-M3.6 dependency_wait hold stamp (DD4: R-M3.5/7 persistence BOM retired) =="
echo "OK: R-M3.5/7 persistence/compile preflights retired (DD3 story-owns-extensions)"
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
python3 "${HARNESS}/dispatch-phase/scripts/assert-bundle-skills-exist.py" \
  "${ROOT}" --bundle m3-implementer || rc=1

echo "== BANK-DEST-INV-HARDINVOKE-1 (RW-2) =="
python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-dest-inventory-hardinvoke.py" \
  "${ROOT}" || rc=1

echo "== Z3-a / A-6 migration.yaml package stamp (idle on golden) =="
python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-migration-yaml-stamp.py" \
  "${ROOT}" || rc=1

echo "== AD-011 skill extension overlay =="
if [ -f "${ROOT}/governance/contracts/ad011-skill-extension.md" ]; then
  echo "FAIL: ad011-skill-extension.md still active (GRT retire)" >&2
  rc=1
else
  echo "OK: AD-011 contract retired (GRT)"
fi
# Retired: workshop-extensions/ and extensions/ were ruled REMOVE in the
# tidy-up disposition (20260812-TIDYUP-DISPOSITION.md rows 16-17) — CS-2
# merged the overlays in-skill and demo users extend via the official
# external_dirs / taps / `hermes skills install` mechanisms. Both checks
# fail-closed on directories the harness deliberately deleted.
echo "== R-SK.13 scaffold hermeticity (no link to the authoring project) =="
python3 "${SKILL_DIR}/scripts/check-scaffold-hermeticity.py" --root "${ROOT}" || rc=1
echo "== R-SK.13 H4 negative (dev-env token in a .sh must BLOCK) =="
h4tmp="$(mktemp -d "${TMPDIR:-/tmp}/h4-hermeticity.XXXXXX")"
# Assemble the leak without putting the H4 token in this script's source.
h4tok="wake"
printf 'echo .%s/file-review-adhere-observe.py\n' "${h4tok}" >"${h4tmp}/leak.sh"
if python3 "${SKILL_DIR}/scripts/check-scaffold-hermeticity.py" --root "${h4tmp}" >/dev/null 2>"${h4tmp}/err"; then
  echo "FAIL: H4 did not refuse .${h4tok}/ in a .sh" >&2
  rc=1
elif ! grep -q ':H4:' "${h4tmp}/err"; then
  echo "FAIL: hermeticity failed but not as H4 ($(tr '\n' ' ' <"${h4tmp}/err"))" >&2
  rc=1
else
  echo "OK: H4 refused .${h4tok}/ in executable"
fi
rm -rf "${h4tmp}"
echo "== LG4 negative (scaffold tmp/ must BLOCK hermeticity) =="
lg4tmp="$(mktemp -d "${TMPDIR:-/tmp}/lg4-hermeticity.XXXXXX")"
mkdir "${lg4tmp}/tmp"
if python3 "${SKILL_DIR}/scripts/check-scaffold-hermeticity.py" --root "${lg4tmp}" >/dev/null 2>"${lg4tmp}/err"; then
  echo "FAIL: hermeticity should refuse a scaffold-root tmp/ (LG4)" >&2
  rc=1
else
  echo "OK: hermeticity refuses scaffold tmp/ (LG4)"
fi
rm -rf "${lg4tmp}"
echo "== LG3 negative (authoring ledger at scaffold root must BLOCK hermeticity) =="
lg3tmp="$(mktemp -d "${TMPDIR:-/tmp}/lg3-hermeticity.XXXXXX")"
lg3f="$(printf '%s_%s.md' REFACTORING V1)"
: >"${lg3tmp}/${lg3f}"
if python3 "${SKILL_DIR}/scripts/check-scaffold-hermeticity.py" --root "${lg3tmp}" >/dev/null 2>"${lg3tmp}/err"; then
  echo "FAIL: hermeticity should refuse a reintroduced authoring ledger (LG3)" >&2
  rc=1
else
  echo "OK: hermeticity refuses authoring ledger at scaffold root (LG3)"
fi
rm -rf "${lg3tmp}"
echo "== UPLIFT-7 golden cleanliness (no run-state in tip tree) =="
python3 "${SKILL_DIR}/scripts/check-golden-cleanliness.py" --root "${ROOT}" || rc=1
echo "== FP-1/FP-2 free-primitives apply-log invert + no-source refuse =="
FP_COMP="${SKILLS}/migration/derive-legacy-boot3/scripts/free-primitives-boot3/run-composite.sh"
fp1="$(mktemp -d "${TMPDIR:-/tmp}/fp1-nongolden.XXXXXX")"
printf '%s\n' '<project><modelVersion>4.0.0</modelVersion></project>' >"${fp1}/pom.xml"
mkdir -p "${fp1}/src"
printf '%s\n' 'class T {}' >"${fp1}/src/T.java"
if ! ( cd "${fp1}" && COMPOSITE_ROOT="${fp1}" bash "${FP_COMP}" >/dev/null 2>"${fp1}/err" ); then
  echo "FAIL: FP-1 composite should run on a tree with sources" >&2
  tail -n 20 "${fp1}/err" >&2 || true
  rc=1
elif [ -f "${fp1}/.rhoai3-free-primitives-apply-log.json" ]; then
  echo "FAIL: FP-1 wrote apply log beside a non-derived tree" >&2
  rc=1
else
  echo "OK: FP-1 non-derived tree has no beside-root apply log"
fi
rm -rf "${fp1}"
fp2="$(mktemp -d "${TMPDIR:-/tmp}/fp2-empty.XXXXXX")"
printf '%s\n' 'readme' >"${fp2}/README"
if ( cd "${fp2}" && COMPOSITE_ROOT="${fp2}" bash "${FP_COMP}" >/dev/null 2>"${fp2}/err" ); then
  echo "FAIL: FP-2 should refuse a tree with no candidate sources" >&2
  rc=1
elif [ -f "${fp2}/.rhoai3-free-primitives-apply-log.json" ]; then
  echo "FAIL: FP-2 wrote apply log on refuse" >&2
  rc=1
elif ! grep -q 'no_candidate_sources' "${fp2}/err"; then
  echo "FAIL: FP-2 refuse was not typed no_candidate_sources" >&2
  rc=1
else
  echo "OK: FP-2 refuses zero-source tree (no receipt)"
fi
rm -rf "${fp2}"
fpd="$(mktemp -d "${TMPDIR:-/tmp}/fp-derived.XXXXXX")"
printf '%s\n' '<project><modelVersion>4.0.0</modelVersion></project>' >"${fpd}/pom.xml"
printf '%s\n' 'schema: rhoai3.derived-tree/v1' >"${fpd}/.rhoai3-derived-tree"
if ! ( cd "${fpd}" && COMPOSITE_ROOT="${fpd}" bash "${FP_COMP}" >/dev/null 2>"${fpd}/err" ); then
  echo "FAIL: derived-marker tree should run" >&2
  tail -n 20 "${fpd}/err" >&2 || true
  rc=1
elif [ ! -f "${fpd}/.rhoai3-free-primitives-apply-log.json" ]; then
  echo "FAIL: derived-marker tree should write apply log beside root" >&2
  rc=1
else
  echo "OK: derived-marker tree writes apply log beside COMPOSITE_ROOT"
fi
rm -rf "${fpd}"
echo "== AD-S S.4 .specify absent from golden =="
python3 "${SKILL_DIR}/scripts/check-specify-absent.py" --root "${ROOT}" || rc=1
echo "== A-1/A-2/A-3 speckit overlay (stop-before-implement) =="
overlay="${SKILLS}/sdd/init-spec-workspace/assets/stop-before-implement.overlay.yml"
constitution="${SKILLS}/sdd/init-spec-workspace/assets/constitution.md"
if [ ! -f "${overlay}" ]; then
  echo "FAIL: missing speckit overlay asset" >&2
  rc=1
elif grep -q 'command: speckit.implement' "${overlay}"; then
  echo "FAIL: overlay invokes speckit.implement" >&2
  rc=1
elif ! grep -q 'remove: implement' "${overlay}"; then
  echo "FAIL: overlay missing remove: implement" >&2
  rc=1
elif ! grep -q 'remove: review-spec' "${overlay}" \
  || ! grep -q 'remove: review-plan' "${overlay}"; then
  echo "FAIL: overlay missing remove: review-spec/review-plan (163200Z unattended gates)" >&2
  rc=1
elif ! grep -q 'speckit.clarify' "${overlay}"; then
  echo "FAIL: overlay missing speckit.clarify" >&2
  rc=1
elif grep -q '_transcribed_http' "${overlay}"; then
  echo "FAIL: overlay cites handover-mint _transcribed_http (ingress-only SHA)" >&2
  rc=1
elif ! grep -q 'evidence/findings-handoff.json' "${overlay}"; then
  echo "FAIL: overlay missing M1 findings-handoff path" >&2
  rc=1
elif ! grep -q 'evidence/entry-point-inventory.json' "${overlay}"; then
  echo "FAIL: overlay missing M1 entry-point inventory path" >&2
  rc=1
else
  echo "OK: tip speckit overlay (clarify, no implement, no gates, M1 paths, ingress-only)"
fi
if [ ! -f "${constitution}" ]; then
  echo "FAIL: missing constitution asset" >&2
  rc=1
elif grep -q '\[PROJECT_NAME\]\|\[PRINCIPLE_1\|\[PLACEHOLDER\]' "${constitution}"; then
  echo "FAIL: constitution asset still has spec-kit placeholders" >&2
  rc=1
elif ! grep -q '3.27.3.SP1' "${constitution}" || ! grep -q 'Java 21' "${constitution}"; then
  echo "FAIL: constitution asset missing Quarkus 3.27.3.SP1 / Java 21" >&2
  rc=1
else
  echo "OK: constitution asset has zero placeholders (V20-3)"
fi
tasks_tpl="${SKILLS}/sdd/init-spec-workspace/assets/tasks-template.md"
if [ ! -f "${tasks_tpl}" ]; then
  echo "FAIL: missing unique-owner tasks-template asset" >&2
  rc=1
elif ! grep -q 'one creator phase per dest path' "${tasks_tpl}"; then
  echo "FAIL: tasks-template asset lacks unique-owner pin" >&2
  rc=1
else
  echo "OK: unique-owner tasks-template asset present"
fi
# Architect E-20260817T122644Z / Operator E-20260817T133449Z — DW env is the
# RHDH skeleton, not bootstrap-scaffold-repos golden. Do not re-edit 080
# scaffold/devfile.yaml for DEFAULT_EXTENSIONS.
rhdh_devfile="${ROOT}/../../../../gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/skeleton/devfile.yaml"
if [ ! -f "${rhdh_devfile}" ]; then
  echo "FAIL: missing RHDH app-migration skeleton devfile (${rhdh_devfile})" >&2
  rc=1
elif ! awk '/name: DEFAULT_EXTENSIONS/{f=1} f && /value:/{print; exit}' "${rhdh_devfile}" \
  | grep -q 'redhat-java.vsix'; then
  echo "FAIL: RHDH skeleton DEFAULT_EXTENSIONS missing redhat-java.vsix (122605Z delivery path)" >&2
  rc=1
else
  echo "OK: RHDH skeleton DEFAULT_EXTENSIONS includes redhat-java.vsix (DW factory path)"
fi
if command -v specify >/dev/null 2>&1; then
  ov_tmp="$(mktemp -d "${TMPDIR:-/tmp}/speckit-overlay.XXXXXX")"
  git -C "${ov_tmp}" init -q
  if (
    cd "${ov_tmp}"
    specify init --here --integration hermes --force --ignore-agent-tools >/dev/null 2>&1
    mkdir -p .specify/workflows/overlays/speckit
    cp "${overlay}" .specify/workflows/overlays/speckit/stop-before-implement.yml
    cp "${constitution}" .specify/memory/constitution.md
  ); then
    resolve_out="$(cd "${ov_tmp}" && specify workflow resolve speckit 2>&1)" || resolve_out="RESOLVE_FAILED"
    if echo "${resolve_out}" | grep -q 'RESOLVE_FAILED'; then
      echo "FAIL: specify workflow resolve speckit failed" >&2
      echo "${resolve_out}" >&2
      rc=1
    elif echo "${resolve_out}" | grep -E '^[[:space:]]+• implement:' >/dev/null; then
      echo "FAIL: resolved speckit still has implement step" >&2
      echo "${resolve_out}" >&2
      rc=1
    elif echo "${resolve_out}" | grep -E '^[[:space:]]+• review-spec:' >/dev/null \
      || echo "${resolve_out}" | grep -E '^[[:space:]]+• review-plan:' >/dev/null; then
      echo "FAIL: resolved speckit still has review-spec/review-plan gates" >&2
      echo "${resolve_out}" >&2
      rc=1
    elif ! echo "${resolve_out}" | grep -E '^[[:space:]]+• clarify:' >/dev/null; then
      echo "FAIL: resolved speckit missing clarify" >&2
      echo "${resolve_out}" >&2
      rc=1
    else
      echo "OK: specify workflow resolve speckit (no implement; no gates; clarify)"
    fi
  else
    echo "FAIL: specify init in overlay temp tree failed" >&2
    rc=1
  fi
  rm -rf "${ov_tmp}"
else
  echo "OK: specify CLI absent — overlay resolve deferred to a provisioned seat"
fi
echo "== A-4/A-5/A-8 handover-mint (tasks.md → receipt) =="
handover="${SKILLS}/harness/dispatch-phase/scripts/handover-mint.py"
fix="${SKILLS}/harness/dispatch-phase/fixtures/handover"
if [ ! -f "${handover}" ]; then
  echo "FAIL: missing handover-mint.py" >&2
  rc=1
else
  ho_tmp="$(mktemp -d "${TMPDIR:-/tmp}/handover-mint.XXXXXX")"
  python3 - "${handover}" "${fix}" "${ho_tmp}" "${SKILLS}/sdd/check-spec-readiness/scripts" <<'PY' || rc=1
import json, shutil, subprocess, sys
from pathlib import Path

handover, fixtures, tmp, ready = (Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
sys.path.insert(0, str(ready))


def run(args, **kw):
    return subprocess.run(
        [sys.executable, str(handover), *args],
        capture_output=True,
        text=True,
        **kw,
    )


def expect_fail(args, needle, label):
    cp = run(args)
    blob = (cp.stdout or "") + (cp.stderr or "")
    if cp.returncode == 0 or needle not in blob:
        print(f"FAIL: {label} expected refuse {needle!r} rc={cp.returncode}", file=sys.stderr)
        print(blob, file=sys.stderr)
        raise SystemExit(1)
    print(f"OK: {label}")


# good dry-run — captured attempt-2 speckit harvest (Architect E-20260817T082353Z /
# Operator E-20260817T120146Z). tasks.good.md retired as a positive PASS.
good_tasks = fixtures / "tasks.attempt-2-speckit.md"
good_inv = fixtures / "inventory.attempt-2.json"
good = tmp / "good"
good.mkdir()
cp = run(
    [
        str(good),
        "--dry-run",
        "--print-receipt",
        "--tasks",
        str(good_tasks),
        "--inventory",
        str(good_inv),
    ]
)
blob = (cp.stdout or "") + (cp.stderr or "")
if cp.returncode != 0:
    print("FAIL: good handover dry-run (attempt-2 harvest)", file=sys.stderr)
    print(blob, file=sys.stderr)
    raise SystemExit(1)
receipt = json.loads(cp.stdout[cp.stdout.index("{") :])
ids = [s["story_id"] for s in receipt["stories"]]
want_ids = ["setup", "foundational", "US1", "US2", "US3", "US4", "US5", "US6", "polish"]
if ids != want_ids:
    print(f"FAIL: story ids {ids}", file=sys.stderr)
    raise SystemExit(1)
if receipt.get("source") != "handover-mint" or receipt.get("pom_owner") != "setup":
    print(f"FAIL: receipt source/pom_owner {receipt.get('source')} {receipt.get('pom_owner')}", file=sys.stderr)
    raise SystemExit(1)
owners = {}
for s in receipt["stories"]:
    for f in s["files_in_scope"]:
        if f in owners:
            print(f"FAIL: overlap {f} {owners[f]}+{s['story_id']}", file=sys.stderr)
            raise SystemExit(1)
        owners[f] = s["story_id"]
if "pom.xml" in receipt["stories"][1]["files_in_scope"]:
    print("FAIL: foundational still lists pom.xml after unique-owner assignment", file=sys.stderr)
    raise SystemExit(1)
us = {s["story_id"]: s for s in receipt["stories"]}
if us["US1"]["parents"] != ["foundational"] or us["setup"]["parents"] != []:
    print(f"FAIL: parents not transcribed {us['US1']['parents']} {us['setup']['parents']}", file=sys.stderr)
    raise SystemExit(1)
if us["US1"]["workspace_kind"] != "worktree" or us["setup"]["workspace_kind"] != "dir":
    print("FAIL: worktree assignment", file=sys.stderr)
    raise SystemExit(1)
if not any("[P]" in line for line in us["US3"]["phase_checklist"]):
    print("FAIL: [P] missing from phase_checklist", file=sys.stderr)
    raise SystemExit(1)
n_eps = sum(len(s.get("endpoints") or []) for s in receipt["stories"])
if n_eps != 34:
    print(f"FAIL: attempt-2 harvest endpoints {n_eps} want 34", file=sys.stderr)
    raise SystemExit(1)
print("OK: handover-mint dry-run (attempt-2 harvest: ids, disjoint, pom_owner, parents, [P], worktree, 34 endpoints)")

# Native speckit specimen (attempt-1 harvest). A-4 must parse. US3 omitting
# Foundational is typed DEPENDENCIES (192444Z). Harvested inventory lacks
# structured http_path; A-8 join is tested separately (inventory.a8-routes.json).
native_tasks = fixtures / "tasks.native-speckit.md"
native_inv = fixtures / "inventory.native-speckit.json"
if native_tasks.is_file() and native_inv.is_file():
    (tmp / "native").mkdir(parents=True, exist_ok=True)
    cp = run(
        [
            str(tmp / "native"),
            "--dry-run",
            "--tasks",
            str(native_tasks),
            "--inventory",
            str(native_inv),
        ]
    )
    blob = (cp.stdout or "") + (cp.stderr or "")
    if "DEPENDENCIES_MISSING" in blob:
        print("FAIL: native speckit still DEPENDENCIES_MISSING", file=sys.stderr)
        print(blob, file=sys.stderr)
        raise SystemExit(1)
    if cp.returncode == 0:
        print("OK: native speckit handover-mint dry-run")
    elif "endpoints_uncovered" in blob:
        print("OK: native speckit parses A-4; harvested inventory has no http_path — uncovered is truthful (no filename mapper)")
    elif "DEPENDENCIES:" in blob and "Foundational must be in parents" in blob:
        print("OK: native speckit A-4 transcribed; US omitting Foundational is DEPENDENCIES (192444Z), not dest rewrite")
    else:
        print("FAIL: native speckit unexpected refuse", file=sys.stderr)
        print(blob, file=sys.stderr)
        raise SystemExit(1)
else:
    print("FAIL: missing tasks.native-speckit.md / inventory.native-speckit.json", file=sys.stderr)
    raise SystemExit(1)

# A-8: transcribed GET /api/owners covers GET even when inventory file is
# OwnerRestController.java and dest write-set is OwnerResource.java.
a8 = tmp / "a8"
a8.mkdir()
cp = run(
    [
        str(a8),
        "--dry-run",
        "--print-receipt",
        "--tasks",
        str(fixtures / "tasks.a8-routes.md"),
        "--inventory",
        str(fixtures / "inventory.a8-routes.json"),
    ]
)
blob = (cp.stdout or "") + (cp.stderr or "")
if cp.returncode != 0:
    print("FAIL: A-8 transcribed-route dry-run", file=sys.stderr)
    print(blob, file=sys.stderr)
    raise SystemExit(1)
a8_receipt = json.loads(cp.stdout[cp.stdout.index("{") :])
a8_us = {s["story_id"]: s for s in a8_receipt["stories"]}
if not any("GET /api/owners" in e or e.endswith("/api/owners") for e in a8_us["US1"].get("endpoints") or []):
    print(f"FAIL: A-8 US1 endpoints {a8_us['US1'].get('endpoints')}", file=sys.stderr)
    raise SystemExit(1)
print("OK: A-8 transcribed GET /api/owners covers legacy RestController inventory")

# Attempt-2 native shape: @Path("/owners") + GET /  (no GET /api/owners token).
# Inventory still records /api/owners. Join via inventory servlet-prefix LCP.
# Not a RestController→Resource filename mapper (223150Z offline loop).
jaxrs = tmp / "a8-jaxrs"
jaxrs.mkdir()
cp = run(
    [
        str(jaxrs),
        "--dry-run",
        "--print-receipt",
        "--tasks",
        str(fixtures / "tasks.a8-jaxrs-class-path.md"),
        "--inventory",
        str(fixtures / "inventory.a8-jaxrs-class-path.json"),
    ]
)
blob = (cp.stdout or "") + (cp.stderr or "")
if cp.returncode != 0:
    print("FAIL: A-8 JAX-RS @Path + inventory /api prefix dry-run", file=sys.stderr)
    print(blob, file=sys.stderr)
    raise SystemExit(1)
jaxrs_receipt = json.loads(cp.stdout[cp.stdout.index("{") :])
jaxrs_us = {s["story_id"]: s for s in jaxrs_receipt["stories"]}
if not any("GET /api/owners" in e or e.endswith("/api/owners") for e in jaxrs_us["US1"].get("endpoints") or []):
    print(f"FAIL: A-8 JAX-RS US1 endpoints {jaxrs_us['US1'].get('endpoints')}", file=sys.stderr)
    raise SystemExit(1)
if not any("GET /api/pets" in e or e.endswith("/api/pets") for e in jaxrs_us["US2"].get("endpoints") or []):
    print(f"FAIL: A-8 JAX-RS US2 endpoints {jaxrs_us['US2'].get('endpoints')}", file=sys.stderr)
    raise SystemExit(1)
print("OK: A-8 JAX-RS @Path(\"/owners\") covers inventory GET /api/owners")

# Attempt-2 harvest is the A-4/A-5 good-path (see dry-run above).

# Attempt-3 harvest (Architect E-20260817T013303Z / E-20260817T015216Z):
# P{N} from heading number; A-8 amend inherits earlier file @Path.
attempt3_tasks = fixtures / "tasks.attempt-3-speckit.md"
attempt3_inv = fixtures / "inventory.attempt-3.json"
if not attempt3_tasks.is_file() or not attempt3_inv.is_file():
    print("FAIL: missing tasks.attempt-3-speckit.md / inventory.attempt-3.json", file=sys.stderr)
    raise SystemExit(1)
import importlib.util
_hm_spec = importlib.util.spec_from_file_location("handover_mint_a3", handover)
_hm = importlib.util.module_from_spec(_hm_spec)
sys.modules["handover_mint_a3"] = _hm
_hm_spec.loader.exec_module(_hm)
_a3_text = attempt3_tasks.read_text(encoding="utf-8")
_a3_phases = _hm.parse_phases(_a3_text)
_hm.transcribe_parents(_a3_text, _a3_phases)
_a3_pom = _hm.assign_ownership(_a3_phases)
_a3_ids = [p.story_id for p in _a3_phases]
if _a3_ids != ["P1", "P2", "P3", "P4", "P5", "P6", "US1", "US2", "US3", "US4", "P11", "polish"]:
    print(f"FAIL: attempt-3 story ids {_a3_ids}", file=sys.stderr)
    raise SystemExit(1)
if _a3_pom != "P1":
    print(f"FAIL: attempt-3 pom_owner {_a3_pom} want P1", file=sys.stderr)
    raise SystemExit(1)
_us1 = next(p for p in _a3_phases if p.story_id == "US1")
if _us1.parents != ["P2", "P3", "P4", "P5", "P6"]:
    print(f"FAIL: attempt-3 US1 parents {_us1.parents}", file=sys.stderr)
    raise SystemExit(1)
_p2 = next(p for p in _a3_phases if p.story_id == "P2")
if any(_hm._is_pom(f) for f in _p2.files):
    print("FAIL: attempt-3 P2 still claims pom.xml (T008 must be amend)", file=sys.stderr)
    raise SystemExit(1)
print("OK: attempt-3 Phase-N ids/parents/pom_owner (A-5 T008 amend)")
a3 = tmp / "attempt-3"
a3.mkdir()
cp = run(
    [
        str(a3),
        "--dry-run",
        "--tasks",
        str(attempt3_tasks),
        "--inventory",
        str(attempt3_inv),
    ]
)
blob = (cp.stdout or "") + (cp.stderr or "")
if "PHASE_KIND" in blob:
    print("FAIL: attempt-3 still PHASE_KIND after Phase-N else-branch", file=sys.stderr)
    print(blob, file=sys.stderr)
    raise SystemExit(1)
if cp.returncode != 0:
    print("FAIL: attempt-3 harvest handover-mint dry-run", file=sys.stderr)
    print(blob, file=sys.stderr)
    raise SystemExit(1)
a3r = json.loads(cp.stdout[cp.stdout.index("{") :])
n_eps = sum(len(s.get("endpoints") or []) for s in a3r["stories"])
if n_eps != 34:
    print(f"FAIL: attempt-3 harvest endpoints {n_eps} want 34", file=sys.stderr)
    raise SystemExit(1)
print("OK: attempt-3 harvest handover-mint dry-run (34 endpoints, A-8 amend-inherits @Path)")

expect_fail(
    [
        str(tmp / "a8-post"),
        "--dry-run",
        "--tasks",
        str(fixtures / "tasks.a8-routes.md"),
        "--inventory",
        str(fixtures / "inventory.a8-uncovered-post.json"),
    ],
    "endpoints_uncovered",
    "A-8 GET transcription does not cover POST without path/method/symbol",
)

cp = run(
    [
        str(tmp / "overlap"),
        "--dry-run",
        "--tasks",
        str(fixtures / "tasks.overlap.md"),
        "--inventory",
        str(fixtures / "inventory.good.json"),
    ]
)
blob = (cp.stdout or "") + (cp.stderr or "")
if "FILE_OVERLAP" in blob:
    print(
        "FAIL: FILE_OVERLAP still fail-closed while serial (Architect E-20260817T131858Z)",
        file=sys.stderr,
    )
    print(blob, file=sys.stderr)
    raise SystemExit(1)
print("OK: overlapping write-sets not FILE_OVERLAP while serial")
expect_fail(
    [
        str(tmp / "nodeps"),
        "--dry-run",
        "--tasks",
        str(fixtures / "tasks.no-deps.md"),
        "--inventory",
        str(fixtures / "inventory.good.json"),
    ],
    "DEPENDENCIES_MISSING",
    "missing Dependencies section refused",
)

# uncovered endpoint (mutate the good-path harvest inventory)
uncovered = tmp / "uncovered"
uncovered.mkdir()
inv = json.loads(good_inv.read_text())
inv["entry_points"].append(
    {"kind": "http", "file": "src/main/java/app/OrphanResource.java", "symbol": "orphan"}
)
inv["counts"]["http"] = int(inv["counts"]["http"]) + 1
inv["counts"]["total"] = int(inv["counts"]["total"]) + 1
inv_path = uncovered / "inv.json"
inv_path.write_text(json.dumps(inv))
expect_fail(
    [
        str(uncovered),
        "--dry-run",
        "--tasks",
        str(good_tasks),
        "--inventory",
        str(inv_path),
    ],
    "endpoints_uncovered",
    "uncovered HTTP endpoint refused",
)

# Path-A partition as write input
pa = tmp / "patha"
pa.mkdir(parents=True)
(pa / "evidence" / "briefs").mkdir(parents=True)
(pa / "evidence" / "briefs" / "partition.json").write_text(
    json.dumps({"schema": "rhoai3.partition/v1", "stories": [{"story_id": "S-001"}]})
)
shutil.copy(good_tasks, pa / "tasks.md")
expect_fail(
    [
        str(pa),
        "--write",
        "--tasks",
        str(good_tasks),
        "--inventory",
        str(good_inv),
    ],
    "PATH_A_PARTITION",
    "Path-A partition.json as input refused",
)
print("OK: A-4/A-5/A-8 handover-mint negatives")
PY
  rm -rf "${ho_tmp}"
fi
echo "== AD-H §7 root scripts/ absent from golden =="
python3 "${SKILL_DIR}/scripts/check-scripts-absent.py" --root "${ROOT}" || rc=1

# GRT — pins.json present; yaml loader and .hermes/lib retired (PJ-1/2)
if [ ! -f "${ROOT}/.hermes/pins.json" ]; then
  echo "FAIL: missing .hermes/pins.json" >&2
  rc=1
else
  echo "OK: .hermes/pins.json present"
fi
if [ -f "${ROOT}/.hermes/pins.yaml" ]; then
  echo "FAIL: leftover pins.yaml on disk (retired; pins.json is the pin file)" >&2
  rc=1
fi
if [ -e "${ROOT}/.hermes/lib" ]; then
  echo "FAIL: leftover lib/ directory (retired with the yaml pin loader)" >&2
  rc=1
fi

echo "== GR1/GRT contract lifecycle (no EOL in .hermes references; no governance/contracts) =="
python3 "${SKILL_DIR}/scripts/check-contract-lifecycle.py" --root "${ROOT}" || rc=1
echo "== SR-2 sentinel root (no parent-count) =="
python3 "${SKILL_DIR}/scripts/check-sr2-sentinel-root.py" --root "${ROOT}" || rc=1
sr2_bad="$(mktemp -d)"
python3 - "${sr2_bad}" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1]) / ".hermes" / "bad-hop.sh"
p.parent.mkdir(parents=True, exist_ok=True)
# assembled so this file's source does not itself trip SR-2
p.write_text('ROOT="$(cd "$(dirname "$0")/' + "../" * 3 + '.." && pwd)"\n')
PY
if python3 "${SKILL_DIR}/scripts/check-sr2-sentinel-root.py" --root "${sr2_bad}" >/dev/null 2>&1; then
  echo "FAIL: SR-2 lint should refuse parent-count ROOT in temp tree" >&2
  rc=1
else
  echo "OK: SR-2 lint refuses parent-count ROOT (negative)"
fi
rm -rf "${sr2_bad}"
echo "== SR-12 root allow-list (files AND directories — LG5) =="
python3 "${SKILL_DIR}/scripts/check-sr12-root-allowlist.py" --root "${ROOT}" || rc=1
sr12_bad="$(mktemp -d "${TMPDIR:-/tmp}/sr12-allow.XXXXXX")"
mkdir "${sr12_bad}/tmp"
if python3 "${SKILL_DIR}/scripts/check-sr12-root-allowlist.py" --root "${sr12_bad}" >/dev/null 2>&1; then
  echo "FAIL: SR-12 should refuse a root tmp/ directory (files-only enumeration would miss it)" >&2
  rc=1
else
  echo "OK: SR-12 refuses root tmp/ via iterdir (LG5)"
fi
rm -rf "${sr12_bad}"
echo "== SR-8 path producers (declared producer, not a deny-list) =="
python3 "${SKILL_DIR}/scripts/check-sr8-path-producers.py" --root "${ROOT}" --mode golden || rc=1
sr8_bad="$(mktemp -d "${TMPDIR:-/tmp}/sr8-retired.XXXXXX")"
mkdir "${sr8_bad}/migration"
SR8_TABLE="${SKILL_DIR}/references/path-producers.json"
if python3 "${SKILL_DIR}/scripts/check-sr8-path-producers.py" --root "${sr8_bad}" --table "${SR8_TABLE}" --mode golden >/dev/null 2>&1; then
  echo "FAIL: SR-8 should refuse a resurrected migration/ directory (SR-8a)" >&2
  rc=1
else
  echo "OK: SR-8 refuses retired migration/ (SR-8a)"
fi
rm -rf "${sr8_bad}"
echo "== LG7 phase-dispatch parser is JSON, not eval =="
READER="${HARNESS}/dispatch-phase/scripts/read-phase-dispatch.py"
if python3 "${READER}" --yaml "${ROOT}/.hermes/phase-dispatch.yaml" --phase M3 >/dev/null; then
  echo "OK: LG7 reader parses M3 from phase-dispatch.yaml"
else
  echo "FAIL: LG7 reader should parse M3" >&2
  rc=1
fi
m3wave="$(mktemp "${TMPDIR:-/tmp}/m3-wave.XXXXXX.yaml")"
cat >"${m3wave}" <<'Y'
phases:
  m3-wave:
    skills:
      - check-spec-readiness
    max_runtime_seconds: 90
Y
if python3 "${READER}" --yaml "${m3wave}" --phase m3-wave >/dev/null; then
  echo "OK: LG7 reader accepts hyphenated phase keys"
else
  echo "FAIL: LG7 reader should accept phase m3-wave (hyphen)" >&2
  rc=1
fi
rm -f "${m3wave}"
if grep -E 'eval "\$\(python3' \
  "${HARNESS}/dispatch-phase/scripts/dispatch-phase.sh" \
  "${HARNESS}/dispatch-phase/scripts/create-m3-implementer.sh" >/dev/null; then
  echo "FAIL: LG7 eval of python parser still present" >&2
  rc=1
else
  echo "OK: LG7 no eval of phase-dispatch parser"
fi
echo "== dangling .hermes refs (Deputy E-174046Z relocation residue) =="
python3 "${SKILL_DIR}/scripts/check-dangling-hermes-refs.py" --root "${ROOT}" || rc=1
echo "== WC-5 mta_rescan proves analyzer ran =="
python3 - "${SKILLS}/analysis/scan-with-mta/scripts/assert-mta-rescan.py" <<'PY' || rc=1
import json, subprocess, sys, tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

cli = Path(sys.argv[1])


def run(args):
    return subprocess.run(
        [sys.executable, str(cli), *args], capture_output=True, text=True
    )


failures = []


def expect(cond, msg):
    if cond:
        print(f"OK: {msg}")
        return
    failures.append(msg)
    print(f"FAIL: {msg}", file=sys.stderr)


td = Path(tempfile.mkdtemp())
r = run([str(td)])
expect(r.returncode == 1, "missing findings refuses")
handoff = td / "evidence" / "findings-handoff.json"
handoff.parent.mkdir(parents=True)
handoff.write_text("{}\n", encoding="utf-8")
r = run([str(td)])
expect(r.returncode == 1, "handoff presence is not a rescan")
findings = td / "evidence" / "mta-findings.json"
findings.write_text(
    json.dumps(
        {
            "normalized_at": "2026-08-16T00:00:00Z",
            "execution_evidence": {
                "analyzer_ran": False,
                "input_digest": "legacy-at-3:aaa",
            },
        }
    )
    + "\n",
    encoding="utf-8",
)
r = run([str(td)])
expect(r.returncode == 1, "analyzer_ran false refuses")
findings.write_text(
    json.dumps(
        {
            "normalized_at": "2026-08-16T12:00:00Z",
            "execution_evidence": {
                "analyzer_ran": True,
                "input_digest": "legacy-at-3:aaa",
            },
        }
    )
    + "\n",
    encoding="utf-8",
)
r = run([str(td), "--snapshot-m1", "--findings", str(findings)])
expect(r.returncode == 0, "M1 snapshot writes")
r = run([str(td)])
expect(r.returncode == 1, "copy of M1 (same digest) refuses")
m3 = td / "evidence" / "runs" / "t_m3" / "complete-exit-ok.json"
m3.parent.mkdir(parents=True)
m3.write_text(
    json.dumps({"stamped_at": "2026-08-16T11:00:00Z", "ok": True}) + "\n",
    encoding="utf-8",
)
findings.write_text(
    json.dumps(
        {
            "normalized_at": "2026-08-16T10:00:00Z",
            "execution_evidence": {
                "analyzer_ran": True,
                "input_digest": "legacy-at-3:bbb",
            },
        }
    )
    + "\n",
    encoding="utf-8",
)
r = run([str(td)])
expect(r.returncode == 1, "rescan stamp older than last M3 refuses")
findings.write_text(
    json.dumps(
        {
            "normalized_at": "2026-08-16T12:00:00Z",
            "execution_evidence": {
                "analyzer_ran": True,
                "input_digest": "legacy-at-3:bbb",
            },
        }
    )
    + "\n",
    encoding="utf-8",
)
r = run([str(td)])
expect(r.returncode == 0, "analyzer_ran + newer digest/timestamp passes")
if failures:
    raise SystemExit(1)
print("OK: WC-5 mta_rescan both directions")
PY

echo "== B-3 MapStruct doctrine pending (no v19-broken mandate) =="
DI_CFG="${SKILLS}/migration/spring-to-quarkus-patterns/references/di-config.md"
if grep -q 'doctrine pending R-SKILL-F' "${DI_CFG}" \
  && grep -q 'Do \*\*not\*\* mandate `componentModel = "cdi"`' "${DI_CFG}"; then
  echo "OK: B-3 di-config.md does not mandate the v19-broken MapStruct CDI shape"
else
  echo "FAIL: B-3 di-config.md must record measured CDI break and pending R-SKILL-F" >&2
  rc=1
fi

echo "== B-6 park-at-birth uses kind=dependency =="
CREATE_M3="${HARNESS}/dispatch-phase/scripts/create-m3-implementer.sh"
if grep -q 'block --kind needs_input' "${CREATE_M3}"; then
  echo "FAIL: B-6 create-m3 still parks with kind=needs_input (spends worker recurrence)" >&2
  rc=1
elif grep -q 'block --kind dependency' "${CREATE_M3}"; then
  echo "OK: B-6 park-at-birth uses kind=dependency"
else
  echo "FAIL: B-6 create-m3 missing harness park --kind dependency" >&2
  rc=1
fi

echo "== B-16 M3 attach from operand_skills =="
b16_body="$(mktemp "${TMPDIR:-/tmp}/b16-body.XXXXXX.json")"
printf '%s\n' '{"identity":{"operand_skills":["form-entity-persistence"]}}' >"${b16_body}"
b16_out="$(python3 "${HARNESS}/dispatch-phase/scripts/m3-attach-skills.py" "${b16_body}")"
if printf '%s\n' "${b16_out}" | grep -qx 'check-spec-readiness' \
  && printf '%s\n' "${b16_out}" | grep -qx 'form-entity-persistence' \
  && ! printf '%s\n' "${b16_out}" | grep -qx 'derive-story-oracles' \
  && ! printf '%s\n' "${b16_out}" | grep -qx 'configure-quarkus-profiles'; then
  echo "OK: B-16 attach is lint + operand_skills, not the five-wide bundle"
else
  echo "FAIL: B-16 attach set was: ${b16_out}" >&2
  rc=1
fi
rm -f "${b16_body}"

echo "== C-3(a) REFUSE mints a remediation receipt =="
c3_tmp="$(mktemp -d "${TMPDIR:-/tmp}/c3-refuse.XXXXXX")"
mkdir -p "${c3_tmp}/evidence/verdicts"
printf '%s\n' '{"phase":"M4","verdict":"REFUSE","gate":"g1_kill_ratio","reason":"not pinned","routing":"blocked"}' \
  > "${c3_tmp}/evidence/verdicts/refuse.json"
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-verdict-routing.py" "${c3_tmp}"; then
  c3_receipt="$(find "${c3_tmp}/evidence/derived/remediation" -name '*.json' 2>/dev/null | head -1)"
  if [ -n "${c3_receipt}" ] \
    && grep -q 'rhoai3.remediation-needed/v1' "${c3_receipt}" \
    && grep -q 'leave-triage' "${c3_receipt}"; then
    echo "OK: C-3(a) REFUSE wrote remediation receipt (leave-triage forbidden, not a path)"
  else
    echo "FAIL: C-3(a) expected remediation receipt under evidence/derived/remediation/" >&2
    rc=1
  fi
else
  echo "FAIL: C-3(a) legal REFUSE routing should pass and mint a receipt" >&2
  rc=1
fi
rm -rf "${c3_tmp}"

echo "== Phase 5 run-audit done-test (touch outside any claim window) =="
python3 - "${HARNESS}/record-run-evidence/scripts" <<'PY' || rc=1
import json, subprocess, sys, tempfile
from pathlib import Path

scripts = Path(sys.argv[1])
snap_py = scripts / "snapshot-run-audit.py"
an_py = scripts / "analyze-run-audit.py"
td = Path(tempfile.mkdtemp())
src = td / "src" / "main" / "java"
src.mkdir(parents=True)
touched = src / "Touched.java"
touched.write_text("class Touched {}\n", encoding="utf-8")
snap = td / "snap.json"
r = subprocess.run(
    [sys.executable, str(snap_py), str(td), "--out", str(snap)],
    capture_output=True,
    text=True,
)
if r.returncode != 0:
    print(f"FAIL: snapshot-run-audit: {r.stderr}", file=sys.stderr)
    raise SystemExit(1)
findings = td / "findings.json"
r = subprocess.run(
    [sys.executable, str(an_py), str(snap), "--out", str(findings)],
    capture_output=True,
    text=True,
)
if r.returncode != 0:
    print(f"FAIL: analyze-run-audit: {r.stderr}", file=sys.stderr)
    raise SystemExit(1)
doc = json.loads(findings.read_text(encoding="utf-8"))
hits = [f for f in doc.get("findings") or [] if f.get("kind") == "INTERVENTION"]
paths = {f.get("path") for f in hits}
want = "src/main/java/Touched.java"
if doc.get("intervention_count") == 1 and want in paths:
    print("OK: run-audit reports one INTERVENTION naming the out-of-window dest path")
else:
    print(
        f"FAIL: run-audit expected 1 INTERVENTION for {want}, got {doc}",
        file=sys.stderr,
    )
    raise SystemExit(1)
r = subprocess.run(
    [sys.executable, str(an_py), str(snap), "--baseline", str(snap), "--out", str(td / "self.json")],
    capture_output=True,
    text=True,
)
if r.returncode != 0:
    print(f"FAIL: analyze-run-audit --baseline: {r.stderr}", file=sys.stderr)
    raise SystemExit(1)
self_doc = json.loads((td / "self.json").read_text(encoding="utf-8"))
if self_doc.get("intervention_count") != 0:
    print(
        f"FAIL: t0-vs-self must be 0 INTERVENTION, got {self_doc}",
        file=sys.stderr,
    )
    raise SystemExit(1)
print("OK: run-audit t0-vs-self is 0 with --baseline")
PY

echo "== create-path tip sync (R0/R3) =="
python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/check-create-path-tip-sync.py" "${ROOT}" || rc=1
echo "== L7 park-on-block-loop self-test =="
python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/park-on-block-loop.py" --self-test || rc=1
echo "== LG9a pre-commit-index-suite script =="
if [ ! -f "${SKILL_DIR}/scripts/pre-commit-index-suite.sh" ]; then
  echo "FAIL: missing pre-commit-index-suite.sh (LG9a)" >&2
  rc=1
else
  echo "OK: LG9a pre-commit-index-suite.sh present"
fi
echo "== R-SK.12 script CLI contract (syntax + no false-green --help) =="
python3 "${SKILL_DIR}/scripts/check-script-cli-contract.py" --root "${ROOT}/.hermes/skills" || rc=1
echo "== CS-7 bundle exists-assert =="
python3 "${SKILL_DIR}/scripts/check-bundle-manifest.py" --root "${ROOT}/.hermes/skills" --bundles "${ROOT}/.hermes/home/skill-bundles" || rc=1
echo "== CS-9 skill conformance (R-SK.7 categorized + R-SK.5) =="
if [ -e "${ROOT}/.hermes/enforcement" ]; then
  echo "FAIL: EX-3 .hermes/enforcement/ must not exist (category dissolved)" >&2
  rc=1
else
  echo "OK: .hermes/enforcement/ absent (EX-3)"
fi
if [ -f "${SKILL_DIR}/scripts/check-skill-conformance.py" ]; then
  python3 "${SKILL_DIR}/scripts/check-skill-conformance.py" --all \
    --root "${ROOT}/.hermes/skills" || rc=1
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
