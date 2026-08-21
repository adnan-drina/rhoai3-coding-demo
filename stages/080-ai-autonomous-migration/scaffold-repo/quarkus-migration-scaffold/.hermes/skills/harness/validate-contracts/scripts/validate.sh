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
# M2 without ack must fail on a tree with no findings-handoff (5.1 cannot issue)
if bash "${HARNESS}/enforce-authority-boundary/scripts/check-acks.sh" M2 "${ROOT}" >/dev/null 2>&1; then
  echo "FAIL: M2 should require m1-findings ack when absent" >&2
  rc=1
else
  echo "OK: M2 refuses without m1-findings ack"
fi
# 5.1 issuer refuses when the envelope is missing (no second checker)
iss51_empty="$(mktemp -d)"
mkdir -p "${iss51_empty}/.hermes/skills/analysis/scan-with-mta/scripts" \
  "${iss51_empty}/evidence/acks"
ln -s "${SKILLS}/analysis/scan-with-mta/scripts/check-findings-handoff.py" \
  "${iss51_empty}/.hermes/skills/analysis/scan-with-mta/scripts/check-findings-handoff.py"
if python3 "${HARNESS}/enforce-authority-boundary/scripts/issue-m1-findings-ack.py" \
  "${iss51_empty}" --task-id t_empty >/dev/null 2>&1; then
  echo "FAIL: 5.1 issuer must refuse without findings-handoff" >&2
  rc=1
else
  echo "OK: 5.1 issuer refuses without findings-handoff"
fi
if [ -f "${iss51_empty}/evidence/acks/m1-findings.ack.yaml" ]; then
  echo "FAIL: 5.1 issuer wrote yaml on rc≠0" >&2
  rc=1
fi
rm -rf "${iss51_empty}"
# 5.1 green path: envelope rc=0 ⇒ record; check-acks M2 proceeds; fence does not block
iss51="$(mktemp -d)"
python3 - "${iss51}" "${ROOT}" "${HARNESS}" <<'PY' || rc=1
import hashlib, json, shutil, subprocess, sys
from pathlib import Path

td, root, harness = map(Path, sys.argv[1:])
(td / "evidence" / "acks").mkdir(parents=True)
(td / "evidence" / "derived").mkdir(parents=True)
(td / ".hermes" / "skills" / "analysis" / "scan-with-mta" / "scripts").mkdir(parents=True)
(td / ".hermes" / "skills" / "harness" / "enforce-authority-boundary" / "scripts").mkdir(parents=True)
shutil.copy(
    root / ".hermes" / "phase-dispatch.yaml",
    td / ".hermes" / "phase-dispatch.yaml",
)
shutil.copy(
    root / ".hermes" / "skills" / "analysis" / "scan-with-mta" / "scripts" / "check-findings-handoff.py",
    td / ".hermes" / "skills" / "analysis" / "scan-with-mta" / "scripts" / "check-findings-handoff.py",
)
shutil.copy(
    harness / "enforce-authority-boundary" / "scripts" / "issue-m1-findings-ack.py",
    td / ".hermes" / "skills" / "harness" / "enforce-authority-boundary" / "scripts" / "issue-m1-findings-ack.py",
)
(td / "evidence" / "derived" / "phase-M1-task-id.txt").write_text("t_51fix\n", encoding="utf-8")

findings = {
    "violations": {
        "ee-to-quarkus-00001": {
            "ruleID": "ee-to-quarkus-00001",
            "description": "Replace javax with jakarta",
        }
    }
}
inv = {
    "counts": {"total": 1},
    "entry_points": [{"file": "Foo.java", "line": 1, "http_method": "GET", "http_path": "/api"}],
}
fp = td / "evidence" / "mta-findings.json"
ip = td / "evidence" / "entry-point-inventory.json"
fp.write_text(json.dumps(findings), encoding="utf-8")
ip.write_text(json.dumps(inv), encoding="utf-8")


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


handoff = {
    "schema": "rhoai3.findings-handoff/v1",
    "ack_obligation": True,
    "evidence": {"path": "evidence/mta-findings.json", "sha256": digest(fp)},
    "inventory": {
        "path": "evidence/entry-point-inventory.json",
        "sha256": digest(ip),
        "endpoint_count": 1,
    },
    "rules": [
        {
            "rule_id": "ee-to-quarkus-00001",
            "description": "Replace javax with jakarta",
            "disposition": "apply",
        }
    ],
}
(td / "evidence" / "findings-handoff.json").write_text(json.dumps(handoff), encoding="utf-8")

# lock acks dir the way apply-write-fence does (a-w, keep +x)
acks = td / "evidence" / "acks"
acks.chmod(0o555)
issuer = harness / "enforce-authority-boundary" / "scripts" / "issue-m1-findings-ack.py"
r = subprocess.run([sys.executable, str(issuer), str(td), "--task-id", "t_51fix"], capture_output=True, text=True)
if r.returncode != 0:
    print(r.stdout + r.stderr, file=sys.stderr)
    print("FAIL: 5.1 issuer on green envelope", file=sys.stderr)
    sys.exit(1)
ack = acks / "m1-findings.ack.yaml"
if not ack.is_file():
    print("FAIL: 5.1 missing yaml after green issuer", file=sys.stderr)
    sys.exit(1)
raw = ack.read_text(encoding="utf-8")
if "gate:check-findings-handoff" not in raw or "gate_rc: 0" not in raw:
    print("FAIL: 5.1 yaml missing gate signer / gate_rc", file=sys.stderr)
    sys.exit(1)
auth = subprocess.run(
    [sys.executable, str(harness / "enforce-authority-boundary" / "scripts" / "check-ack-authority.py"), str(td)],
    capture_output=True,
    text=True,
)
if auth.returncode != 0:
    print(auth.stdout + auth.stderr, file=sys.stderr)
    print("FAIL: 5.1 gate-record failed AR-1.1", file=sys.stderr)
    sys.exit(1)
# second call is idempotent
r2 = subprocess.run([sys.executable, str(issuer), str(td), "--task-id", "t_51fix"], capture_output=True, text=True)
if r2.returncode != 0:
    print(r2.stdout + r2.stderr, file=sys.stderr)
    print("FAIL: 5.1 issuer not idempotent", file=sys.stderr)
    sys.exit(1)
ack.chmod(0o644)
acks.chmod(0o755)
ack.unlink()
acks.chmod(0o555)
cks = subprocess.run(
    ["bash", str(harness / "enforce-authority-boundary" / "scripts" / "check-acks.sh"), "M2", str(td)],
    capture_output=True,
    text=True,
)
if cks.returncode != 0:
    print(cks.stdout + cks.stderr, file=sys.stderr)
    print("FAIL: check-acks M2 should auto-issue 5.1 record", file=sys.stderr)
    sys.exit(1)
if not ack.is_file():
    print("FAIL: check-acks M2 did not recreate 5.1 yaml", file=sys.stderr)
    sys.exit(1)
print("OK: 5.1 gate-record issued when findings-handoff rc=0")
PY
if bash "${HARNESS}/enforce-authority-boundary/scripts/check-acks.sh" M2 "${iss51}" >/dev/null; then
  echo "OK: M2 check-acks accepts 5.1 gate-record"
else
  echo "FAIL: M2 check-acks should accept 5.1 gate-record" >&2
  rc=1
fi
chmod -R u+w "${iss51}" 2>/dev/null || true
rm -rf "${iss51}"

echo "== M3 brief-identity 5.1 issuer (Operator 122824Z) =="
iss_m3="$(mktemp -d)"
python3 - "${iss_m3}" "${ROOT}" "${HARNESS}" "${SKILLS}" <<'PY' || rc=1
import hashlib, json, shutil, subprocess, sys
from pathlib import Path

td, root, harness, skills = map(Path, sys.argv[1:])
acks = td / "evidence" / "acks"
bodies = td / "evidence" / "bodies"
derived = td / "evidence" / "derived"
briefs = td / "evidence" / "briefs"
digest_dir = td / ".hermes" / "skills" / "harness" / "record-run-evidence" / "scripts"
issuer_dir = td / ".hermes" / "skills" / "harness" / "enforce-authority-boundary" / "scripts"
for p in (acks, bodies, derived, briefs, digest_dir, issuer_dir):
    p.mkdir(parents=True)
shutil.copy(root / ".hermes" / "phase-dispatch.yaml", td / ".hermes" / "phase-dispatch.yaml")
shutil.copy(
    skills / "harness" / "record-run-evidence" / "scripts" / "check-body-digest-match.py",
    digest_dir / "check-body-digest-match.py",
)
shutil.copy(
    harness / "enforce-authority-boundary" / "scripts" / "issue-m3-brief-identity-ack.py",
    issuer_dir / "issue-m3-brief-identity-ack.py",
)
shutil.copy(
    harness / "enforce-authority-boundary" / "scripts" / "check-ack-authority.py",
    issuer_dir / "check-ack-authority.py",
)
(briefs / "partition.json").write_text(
    json.dumps({"stories": [{"story_id": "s1"}, {"story_id": "s2"}]}),
    encoding="utf-8",
)
(derived / "created-story-cards.json").write_text(
    json.dumps({"cards": [{"id": "t_aaa", "story_id": "s1"}, {"id": "t_bbb", "story_id": "s2"}]}),
    encoding="utf-8",
)

def stamp(name: str, payload: str) -> str:
    path = bodies / name
    path.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (bodies / f"{name}.sha256.json").write_text(
        json.dumps({"schema": "rhoai3.body-digest/v1", "body_sha256": digest}),
        encoding="utf-8",
    )
    return digest

d1 = stamp("m3-s1.json", '{"story":"s1"}')
d2 = stamp("m3-s2.json", '{"story":"s2"}')
issuer = issuer_dir / "issue-m3-brief-identity-ack.py"

# mismatch: corrupt s2 sidecar
(bodies / "m3-s2.json.sha256.json").write_text(
    json.dumps({"schema": "rhoai3.body-digest/v1", "body_sha256": "0" * 64}),
    encoding="utf-8",
)
r_bad = subprocess.run(
    [sys.executable, str(issuer), str(td), "--task-id", "t_gate"],
    capture_output=True,
    text=True,
)
if r_bad.returncode == 0:
    print("FAIL: M3 issuer must refuse digest mismatch", file=sys.stderr)
    sys.exit(1)
err = (r_bad.stdout + r_bad.stderr)
if "evidence/bodies/m3-s2.json" not in err:
    print(err, file=sys.stderr)
    print("FAIL: M3 issuer must name the mismatching body", file=sys.stderr)
    sys.exit(1)
if (acks / "m3-brief-identity.ack.yaml").is_file():
    print("FAIL: M3 issuer wrote yaml on mismatch", file=sys.stderr)
    sys.exit(1)
print("OK: M3 brief-identity issuer names mismatching body")

# restore sidecar and issue
stamp("m3-s2.json", '{"story":"s2"}')
acks.chmod(0o555)
r_ok = subprocess.run(
    [sys.executable, str(issuer), str(td), "--task-id", "t_gate"],
    capture_output=True,
    text=True,
)
if r_ok.returncode != 0:
    print(r_ok.stdout + r_ok.stderr, file=sys.stderr)
    print("FAIL: M3 issuer on green bodies", file=sys.stderr)
    sys.exit(1)
ack = acks / "m3-brief-identity.ack.yaml"
canon = acks / "brief-identity.ack.yaml"
if not ack.is_file() or not canon.is_file():
    print("FAIL: M3 issuer missing yaml after green", file=sys.stderr)
    sys.exit(1)
raw = ack.read_text(encoding="utf-8")
if "gate:check-body-digest-match" not in raw or "gate_rc: 0" not in raw:
    print("FAIL: M3 yaml missing gate signer / gate_rc", file=sys.stderr)
    sys.exit(1)
if d1 not in raw or d2 not in raw:
    print("FAIL: M3 yaml missing body digests", file=sys.stderr)
    sys.exit(1)
auth = subprocess.run(
    [sys.executable, str(issuer_dir / "check-ack-authority.py"), str(td)],
    capture_output=True,
    text=True,
)
if auth.returncode != 0:
    print(auth.stdout + auth.stderr, file=sys.stderr)
    print("FAIL: M3 gate-record failed AR-1.1", file=sys.stderr)
    sys.exit(1)
print("OK: M3 brief-identity gate-record issued when body digests match")
PY
chmod -R u+w "${iss_m3}" 2>/dev/null || true
rm -rf "${iss_m3}"
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
# 5.1 gate-record signer is not a worker
cat > "${ar11_tmp}/evidence/acks/m1-findings.ack.yaml" <<'EOF'
kind: migration-ack
ack_type: m1-findings
status: acknowledged
acknowledged_by: gate:check-findings-handoff
acknowledged_at: 2026-08-19T00:00:00Z
task_id: t_demo
gate_rc: 0
artifact_digests:
  evidence/mta-findings.json: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  evidence/findings-handoff.json: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
EOF
python3 "${HARNESS}/enforce-authority-boundary/scripts/check-ack-authority.py" "${ar11_tmp}" \
  && echo "OK: AR-1.1 5.1 gate:check-findings-handoff accepted" \
  || { echo "FAIL: AR-1.1 5.1 gate signer refused" >&2; rc=1; }
cat > "${ar11_tmp}/evidence/acks/m1-findings.ack.yaml" <<'EOF'
kind: migration-ack
ack_type: m1-findings
status: acknowledged
acknowledged_by: gate:invented-envelope
acknowledged_at: 2026-08-19T00:00:00Z
task_id: t_demo
artifact_digests:
  evidence/mta-findings.json: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
EOF
if python3 "${HARNESS}/enforce-authority-boundary/scripts/check-ack-authority.py" "${ar11_tmp}" >/dev/null 2>&1; then
  echo "FAIL: AR-1.1 unknown gate: signer should refuse" >&2
  rc=1
else
  echo "OK: AR-1.1 unknown gate: signer refused"
fi
cat > "${ar11_tmp}/evidence/acks/m1-findings.ack.yaml" <<'EOF'
kind: migration-ack
ack_type: brief-identity
status: acknowledged
acknowledged_by: gate:check-body-digest-match
acknowledged_at: 2026-08-20T00:00:00Z
task_id: t_demo
gate_rc: 0
artifact_digests:
  evidence/bodies/m3-setup.json: cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
EOF
python3 "${HARNESS}/enforce-authority-boundary/scripts/check-ack-authority.py" "${ar11_tmp}" \
  && echo "OK: AR-1.1 5.1 gate:check-body-digest-match accepted" \
  || { echo "FAIL: AR-1.1 M3 gate signer refused" >&2; rc=1; }
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
  unset HERMES_KANBAN_FILES_WRITABLE HERMES_KANBAN_TASK HERMES_KANBAN_CARD_BODY \
    HERMES_KANBAN_CARD_JSON HERMES_KANBAN_PHASE HERMES_KANBAN_DB || true
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
  mkdir -p "${hook_tmp}/evidence/runtime/write-sets"
  printf '%s\n' '{"task_id":"t_deadbeef","files_writable":["pom.xml"]}' \
    > "${hook_tmp}/evidence/runtime/write-sets/t_deadbeef.json"
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"pom.xml"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: dest write-set cache must not allow pom.xml when env unset" >&2
    exit 1
  else
    echo "OK: write-set hook ignores dest cache (v24 env-only fence)"
  fi
  # I-5: native workers do not get FILES_WRITABLE; card markdown on kanban.db
  # is policy. Dest cache still must not win.
  python3 - <<PY
import sqlite3
from pathlib import Path
root = Path("${hook_tmp}")
db = root / "kanban.db"
con = sqlite3.connect(db)
con.execute(
    "CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT, "
    "status TEXT NOT NULL, created_at INTEGER NOT NULL, workspace_kind TEXT)"
)
body = """Typed body: evidence/bodies/m3-setup.json
## Files Writable
- pom.xml
- src/main/resources/application.properties
## Constraints
"""
con.execute(
    "INSERT INTO tasks (id, title, body, status, created_at, workspace_kind) "
    "VALUES (?, ?, ?, ?, 0, 'dir')",
    ("t_i5card", "M3 IMPLEMENT: setup — Shared Infrastructure", body, "running"),
)
con.commit()
con.close()
(root / "evidence/runtime/write-sets/t_i5card.json").write_text(
    '{"task_id":"t_i5card","files_writable":["src/hack.java"]}\n'
)
print("OK: scratch kanban.db fixture for I-5 card-body fallback")
PY
  unset HERMES_KANBAN_FILES_WRITABLE
  unset HERMES_KANBAN_CARD_JSON || true
  unset HERMES_KANBAN_CARD_BODY || true
  export HERMES_KANBAN_TASK="t_i5card"
  export HERMES_KANBAN_DB="${hook_tmp}/kanban.db"
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"pom.xml"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "OK: I-5 kanban.db card body allows pom.xml when env unset"
  else
    echo "FAIL: I-5 kanban.db card body should allow pom.xml" >&2
    exit 1
  fi
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"src/hack.java"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: I-5 kanban.db card body should refuse src/hack.java" >&2
    exit 1
  else
    echo "OK: I-5 kanban.db card body refuses OOS src/hack.java (dest cache ignored)"
  fi
  unset HERMES_KANBAN_DB
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
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"evidence/runtime/write-sets/t_deadbeef.json"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: write-set cache path must be deny-prefix" >&2
    exit 1
  else
    echo "OK: write-set hook denies write-set cache path (cache not worker-writable)"
  fi
  export HERMES_KANBAN_FILES_WRITABLE='["pom.xml"]'
  if printf '%s\n' '{"tool_name":"terminal","tool_input":{"command":"echo x > evidence/runtime/write-sets/t_deadbeef.json"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: terminal argv targeting write-sets must block" >&2
    exit 1
  else
    echo "OK: terminal argv targeting write-set cache is refused (defence-in-depth)"
  fi
  if printf '%s\n' '{"tool_name":"terminal","tool_input":{"command":"cat > ~/.m2/settings.xml <<EOF\n<settings/>\nEOF"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: terminal redirect to ~/.m2/settings.xml must block (resolved path)" >&2
    exit 1
  else
    echo "OK: terminal redirect to ~/.m2/settings.xml is refused (G2 resolved path)"
  fi
  if printf '%s\n' '{"tool_name":"terminal","tool_input":{"command":"cat > $HOME/.m2/settings.xml <<EOF\n<settings/>\nEOF"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: terminal redirect to \$HOME/.m2/settings.xml must block" >&2
    exit 1
  else
    echo "OK: terminal redirect to \$HOME/.m2/settings.xml is refused"
  fi
  export HERMES_KANBAN_FILES_WRITABLE='[".specify/","specs/"]'
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"evidence/type-inventory.json"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: M2 write_file type-inventory must refuse" >&2
    exit 1
  else
    echo "OK: write-set hook refuses type-inventory write_file on M2 write-set"
  fi
  if python3 -c 'import json,sys; sys.stdout.write(json.dumps({"tool_name":"terminal","tool_input":{"command":"python3 -c \"open('\''evidence/type-inventory.json'\'','\''w'\'').write('\''x'\'')\""}}))' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: python open(w) type-inventory via terminal must refuse" >&2
    exit 1
  else
    echo "OK: write-set hook refuses python open(w) type-inventory via terminal"
  fi
  if python3 -c 'import json,sys; sys.stdout.write(json.dumps({"tool_name":"execute_code","tool_input":{"code":"open('\''evidence/type-inventory.json'\'','\''w'\'').write('\''x'\'')"}}))' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: execute_code open(w) type-inventory must refuse" >&2
    exit 1
  else
    echo "OK: write-set hook refuses execute_code open(w) type-inventory"
  fi
  if python3 -c 'import json,sys; sys.stdout.write(json.dumps({"tool_name":"execute_code","tool_input":{"code":"print(open('\''evidence/type-inventory.json'\'').read())"}}))' \
    | python3 "${HOOK}" >/dev/null; then
    echo "OK: write-set hook allows execute_code read of type-inventory"
  else
    echo "FAIL: execute_code read of type-inventory must allow" >&2
    exit 1
  fi
  unset HERMES_KANBAN_FILES_WRITABLE
  unset HERMES_KANBAN_CARD_BODY || true
  unset HERMES_KANBAN_CARD_JSON || true
  mkdir -p "${hook_tmp}/.hermes/skills/harness/dispatch-phase/scripts"
  cp "${HARNESS}/dispatch-phase/scripts/read-phase-dispatch.py" \
    "${hook_tmp}/.hermes/skills/harness/dispatch-phase/scripts/"
  cat >"${hook_tmp}/.hermes/phase-dispatch.yaml" <<'YAML'
phases:
  M2:
    skills:
      - speckit-specify
    max_runtime_seconds: 3600
    files_writable:
      - .specify/
      - specs/
  M3:
    skills:
      - check-spec-readiness
    max_runtime_seconds: 2700
  M4:
    skills:
      - check-spec-readiness
    max_runtime_seconds: 1800
    files_writable: []
  M5:
    skills:
      - check-spec-readiness
    max_runtime_seconds: 2400
    files_writable: []
YAML
  export HERMES_KANBAN_TASK="t_m2yaml"
  export HERMES_KANBAN_PHASE=M2
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"specs/001/spec.md"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "OK: B2 yaml fallback allows M2 specs/ when env unset"
  else
    echo "FAIL: B2 yaml fallback refused M2 specs/" >&2
    exit 1
  fi
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"src/main/java/x/App.java"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: B2 yaml fallback should refuse src/ on M2" >&2
    exit 1
  else
    echo "OK: B2 yaml fallback refuses src/ on M2"
  fi
  export HERMES_KANBAN_PHASE=M3
  export HERMES_KANBAN_TASK="t_m3omit"
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"src/main/java/x/App.java"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: M3 yaml omit must deny-all dest product writes" >&2
    exit 1
  else
    echo "OK: M3 yaml omit is deny-all (no phase union)"
  fi
  export HERMES_KANBAN_PHASE=M4
  export HERMES_KANBAN_TASK="t_m4empty"
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"src/main/java/x/App.java"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: M4 published [] must refuse src/" >&2
    exit 1
  else
    echo "OK: M4 published [] refuses src/"
  fi
  unset HERMES_KANBAN_PHASE
  export HERMES_KANBAN_TASK="t_story"
  export HERMES_KANBAN_CARD_BODY="$(printf '%s\n' '## Files Writable' '- src/main/java/com/demo/resource/OwnerResource.java')"
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"src/main/java/com/demo/resource/OwnerResource.java"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "OK: B2 card Files Writable allows the story path"
  else
    echo "FAIL: B2 card Files Writable refused the story path" >&2
    exit 1
  fi
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"pom.xml"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: B2 card Files Writable should refuse pom.xml" >&2
    exit 1
  else
    echo "OK: B2 card Files Writable refuses pom.xml"
  fi
  export HERMES_KANBAN_PHASE=M2
  if printf '%s\n' '{"tool_name":"write_file","tool_input":{"path":"specs/001/spec.md"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "FAIL: published card must win over M2 yaml (no specs/ on the card)" >&2
    exit 1
  else
    echo "OK: published card wins over phase yaml"
  fi
  unset HERMES_KANBAN_PHASE
  unset HERMES_KANBAN_CARD_BODY
  # H-3: stdout/stderr redirects are not dest writes.
  export HERMES_KANBAN_FILES_WRITABLE='["specs/"]'
  if printf '%s\n' '{"tool_name":"terminal","tool_input":{"command":"ls specs/ >/dev/null"}}' \
    | python3 "${HOOK}" >/dev/null; then
    echo "OK: write-set hook allows /dev/null"
  else
    echo "FAIL: write-set hook refused ls >/dev/null (H-3)" >&2
    exit 1
  fi
  unset HERMES_KANBAN_FILES_WRITABLE
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
# LD-1 / LD-2 — one working schema mechanism; name idle→active (Review 213600Z)
rdb_tmp="$(mktemp -d)"
mkdir -p "${rdb_tmp}/good/src/main/resources" "${rdb_tmp}/bare/src/main/resources"
cat > "${rdb_tmp}/good/pom.xml" <<'XML'
<project>
  <dependencies>
    <dependency><artifactId>quarkus-jdbc-h2</artifactId></dependency>
    <dependency><artifactId>quarkus-hibernate-orm</artifactId></dependency>
  </dependencies>
</project>
XML
printf '%s\n' \
  'quarkus.datasource.db-kind=h2' \
  'quarkus.datasource.jdbc.url=jdbc:h2:mem:testdb' \
  'quarkus.hibernate-orm.database.generation=drop-and-create' \
  > "${rdb_tmp}/good/src/main/resources/application.properties"
printf '%s\n' 'INSERT INTO x(id) VALUES (1);' \
  > "${rdb_tmp}/good/src/main/resources/import.sql"
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-runnable-db-config.py" \
  "${rdb_tmp}/good" >/tmp/rdb-good.out 2>/tmp/rdb-good.err; then
  echo "OK: AR-2.1 schema generation + import.sql passes without Flyway"
else
  echo "FAIL: schema-gen + import.sql must PASS without quarkus-flyway" >&2
  cat /tmp/rdb-good.out /tmp/rdb-good.err >&2
  rc=1
fi
cp "${rdb_tmp}/good/pom.xml" "${rdb_tmp}/bare/pom.xml"
printf '%s\n' \
  'quarkus.datasource.db-kind=h2' \
  'quarkus.datasource.jdbc.url=jdbc:h2:mem:testdb' \
  > "${rdb_tmp}/bare/src/main/resources/application.properties"
if python3 "${SKILLS}/gates/check-release-readiness/scripts/check-runnable-db-config.py" \
  "${rdb_tmp}/bare" >/tmp/rdb-bare.out 2>/tmp/rdb-bare.err; then
  echo "FAIL: datasource with no schema mechanism must refuse" >&2
  cat /tmp/rdb-bare.out /tmp/rdb-bare.err >&2
  rc=1
elif grep -q 'idle→active' /tmp/rdb-bare.err \
  && grep -q 'application.properties quarkus.datasource' /tmp/rdb-bare.err \
  && grep -q 'no working schema mechanism' /tmp/rdb-bare.err; then
  echo "OK: AR-2.1 names idle→active surface when datasource has no schema mechanism"
else
  echo "FAIL: expected idle→active Surface on bare datasource refuse" >&2
  cat /tmp/rdb-bare.out /tmp/rdb-bare.err >&2
  rc=1
fi
rm -rf "${rdb_tmp}"
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
# Architect E-20260817T150714Z — HTTP locus is inventory.file, not dest Resource
harvest_java = (
    kb / ".derived/legacy-at-3/src/main/java/org/example/"
    "demo/rest/VetRestController.java"
)
harvest_java.parent.mkdir(parents=True, exist_ok=True)
harvest_java.write_text("class VetRestController {}\n")
inv = {
    "schema": "rhoai3.entry-point-inventory/v1",
    "entry_points": [
        {
            "kind": "http",
            "file": (
                "src/main/java/org/example/demo/rest/"
                "VetRestController.java"
            ),
            "symbol": "VetRestController#getVets",
            "http_method": "GET",
            "http_path": "/api/vets",
        }
    ],
}
(root / "evidence").mkdir(parents=True, exist_ok=True)
(root / "evidence/entry-point-inventory.json").write_text(json.dumps(inv) + "\n")
(root / "evidence/derived").mkdir(parents=True, exist_ok=True)
(root / "evidence/derived/legacy-at-3.json").write_text('{"harvest_referent":true}\n')
http_story = {
    "story_id": "US1",
    "kind": "user_story",
    "operand_class": ["rest", "user_story"],
    "files_in_scope": ["src/main/java/com/demo/resource/VetResource.java"],
    "files_writable": ["src/main/java/com/demo/resource/VetResource.java"],
    "endpoints": ["GET /api/vets"],
    "acceptance_criteria": [{"check": "build_resolves", "cmd": "mvn -q compile"}],
}
path_http, sha_http = mod._stamp_legacy_locus(http_story, root)
if Path(path_http).resolve() != harvest_java.resolve():
    print(
        f"FAIL: HTTP locus {path_http!r} not inventory harvest {harvest_java}",
        file=sys.stderr,
    )
    raise SystemExit(1)
setup_story = {
    "story_id": "setup",
    "kind": "setup",
    "operand_class": ["build_config"],
    "files_in_scope": ["pom.xml"],
    "endpoints": [],
}
path_setup, _ = mod._stamp_legacy_locus(setup_story, root)
ref_json = (root / "evidence/derived/legacy-at-3.json").resolve()
if Path(path_setup).resolve() != ref_json:
    print(f"FAIL: setup locus {path_setup!r} not harvest_referent", file=sys.stderr)
    raise SystemExit(1)
print("OK: assembler HTTP locus is inventory harvest file; setup uses M1 referent")
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
got_ent = declared_extensions_for_paths(
    [
        "src/main/java/com/demo/entity/Owner.java",
        "src/main/java/com/demo/resource/PetResource.java",
    ]
)
if got_ent != ["quarkus-hibernate-orm", "quarkus-rest", "quarkus-rest-jackson"]:
    print(f"FAIL: entity/resource heuristic got {got_ent}", file=sys.stderr)
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
except ValueError as exc:
    msg = str(exc)
    if "files_writable" not in msg or "writes_pom_xml" not in msg:
        print(f"FAIL: two-pom refuse must name the body surface: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print("OK: stamp_dd3_extensions refuses two pom.xml writers")
else:
    print("FAIL: two pom writers should refuse", file=sys.stderr)
    raise SystemExit(1)
try:
    stamp_dd3_extensions(
        [{"identity": {"story_id": "us1"}, "files_writable": ["src/Foo.java"]}]
    )
except ValueError as exc:
    msg = str(exc)
    if "got 0" not in msg or "us1" not in msg or "files_writable" not in msg:
        print(f"FAIL: zero-writer refuse must name the body surface: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print("OK: stamp_dd3_extensions zero writer names body surface")
else:
    print("FAIL: zero pom writer should refuse", file=sys.stderr)
    raise SystemExit(1)
print("OK: stamp_dd3_extensions union + sole writer")
# M1 required-extensions union onto pom writer declared (apply == sibling union)
req = kb / "evidence" / "required-extensions.json"
req.parent.mkdir(parents=True, exist_ok=True)
req.write_text(
    json.dumps({
        "schema": "rhoai3.required-extensions/v2",
        "entries": [
            {"artifactId": "quarkus-hibernate-orm", "kind": "extension"},
            {"artifactId": "quarkus-hibernate-validator", "kind": "extension"},
        ],
    })
    + "\n"
)
pom_m1 = {
    "task_id": "t_setupm1",
    "identity": {"story_id": "setup"},
    "files_writable": ["pom.xml"],
    "files_in_scope": ["pom.xml"],
}
rest_m1 = {
    "task_id": "t_restm1",
    "identity": {"story_id": "US1"},
    "files_writable": ["src/main/java/org/x/rest/PetResource.java"],
    "files_in_scope": ["src/main/java/org/x/rest/PetResource.java"],
}
stamp_dd3_extensions([pom_m1, rest_m1], root=kb)
want_apply = [
    "quarkus-hibernate-orm",
    "quarkus-hibernate-validator",
    "quarkus-rest",
    "quarkus-rest-jackson",
]
if pom_m1["identity"]["extensions_declared"] != [
    "quarkus-hibernate-orm",
    "quarkus-hibernate-validator",
]:
    print(
        f"FAIL: pom declared with M1 {pom_m1['identity']['extensions_declared']}",
        file=sys.stderr,
    )
    raise SystemExit(1)
if pom_m1["identity"]["extensions_apply"] != want_apply:
    print(
        f"FAIL: apply with M1 {pom_m1['identity'].get('extensions_apply')}",
        file=sys.stderr,
    )
    raise SystemExit(1)
print("OK: stamp_dd3_extensions unions M1 required-extensions onto pom writer")
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
printf '%s\n' '{"stories":[{"story_id":"story-001","files_in_scope":["src/Foo.java"],"endpoints":["foo"]}]}' \
  > "${pc_tmp}/evidence/briefs/partition.json"
printf '%s\n' '{"entry_points":[{"kind":"http","file":"src/Foo.java","symbol":"foo","http_method":"GET","http_path":"/foo"}],"totals":{"http_endpoints":1}}' \
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
# WC-8: envelope violations dict present, no story.rules → still VALID
# (Architect E-20260817T154012Z — create-path is presence, not addressed)
mkdir -p "${pc_tmp}/evidence"
printf '%s\n' '{"schema":"rhoai3.mta-findings/v1-provisional","violations":{"springboot-to-quarkus-00000":{"ruleID":"springboot-to-quarkus-00000","category":"mandatory","incidents":[]}}}' \
  > "${pc_tmp}/evidence/mta-findings.json"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-partition-coverage.py" \
    "${pc_tmp}" --partition evidence/briefs/partition.json --inventory inventory.json \
    >/tmp/pc-wc8-unaddr.out 2>/tmp/pc-wc8-unaddr.err; then
  if grep -q 'VALID' /tmp/pc-wc8-unaddr.out \
     && ! grep -q 'mta_unaddressed' /tmp/pc-wc8-unaddr.out /tmp/pc-wc8-unaddr.err; then
    echo "OK: PARTITION_COVERAGE findings present without story.rules is VALID (presence-only)"
  else
    echo "FAIL: expected VALID without mta_unaddressed when findings are present" >&2
    cat /tmp/pc-wc8-unaddr.out /tmp/pc-wc8-unaddr.err >&2
    rc=1
  fi
else
  echo "FAIL: findings present without story.rules should be VALID at create" >&2
  cat /tmp/pc-wc8-unaddr.out /tmp/pc-wc8-unaddr.err >&2
  rc=1
fi

# Architect E-20260817T162352Z — dest-path deps + extends closure (not mint)
dep_tmp="$(mktemp -d)"
mkdir -p "${dep_tmp}/modernized/evidence/bodies" \
  "${dep_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/model" \
  "${dep_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/repository"
cat > "${dep_tmp}/modernized/migration.yaml" <<'YAML'
migration:
  legacyBasePackage: com.acme.legacy
  targetPackage: com.demo
  path_rewrites:
    - from: src/main/java/com/demo/
      to: src/main/java/com/acme/legacy/
YAML
printf '%s\n' 'package com.acme.legacy.model; public class Base { private Integer id; }' \
  > "${dep_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/model/Base.java"
printf '%s\n' 'package com.acme.legacy.model; public class Mid extends Base { private String name; }' \
  > "${dep_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/model/Mid.java"
printf '%s\n' 'package com.acme.legacy.model; public class Leaf extends Mid { }' \
  > "${dep_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/model/Leaf.java"
printf '%s\n' 'package com.acme.legacy.model; public class Side extends Base { }' \
  > "${dep_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/model/Side.java"
printf '%s\n' 'package com.acme.legacy.model; import java.util.Set; public class Holder extends Base { private Set<Side> sides; }' \
  > "${dep_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/model/Holder.java"
printf '%s\n' 'package com.acme.legacy.repository; import com.acme.legacy.model.Leaf; public interface GhostRepository { Leaf find(); }' \
  > "${dep_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/repository/GhostRepository.java"
python3 - <<PY
import json
from pathlib import Path
root = Path("${dep_tmp}/modernized")
body = {
  "identity": {"story_id": "foundational", "operand_count": 2},
  "files_in_scope": [
    "src/main/java/com/demo/model/Leaf.java",
    "src/main/java/com/demo/model/Holder.java",
  ],
  "files_writable": [
    "src/main/java/com/demo/model/Leaf.java",
    "src/main/java/com/demo/model/Holder.java",
  ],
}
(root / "evidence/bodies/m3-foundational.json").write_text(json.dumps(body) + "\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py" \
    "${dep_tmp}/modernized" --body evidence/bodies/m3-foundational.json --write \
    >/tmp/dep-close.out 2>/tmp/dep-close.err; then
  if python3 - "${dep_tmp}" <<'PY'
import json, sys
from pathlib import Path
b = json.loads((Path(sys.argv[1]) / "modernized/evidence/bodies/m3-foundational.json").read_text())
fw = b.get("files_writable") or []
want = {
  "src/main/java/com/demo/model/Base.java",
  "src/main/java/com/demo/model/Mid.java",
  "src/main/java/com/demo/model/Side.java",
}
missing = want - set(fw)
deps = b.get("dependencies") or []
legacy = [d.get("file") for d in deps if "acme/legacy" in str(d.get("file") or "")]
raise SystemExit(1 if missing or legacy else 0)
PY
  then
    echo "OK: stamp-body-dependencies dest-path closure adds extends twins"
  else
    echo "FAIL: expected dest Base/Mid/Side on files_writable and no legacy paths in deps" >&2
    cat /tmp/dep-close.out /tmp/dep-close.err >&2
    cat "${dep_tmp}/modernized/evidence/bodies/m3-foundational.json" >&2
    rc=1
  fi
else
  echo "FAIL: stamp-body-dependencies closure should exit 0" >&2
  cat /tmp/dep-close.out /tmp/dep-close.err >&2
  rc=1
fi
# Architect E-20260818T180200Z — deriver applies intra_package_maps (no specimen literals)
map_tmp="$(mktemp -d)"
mkdir -p "${map_tmp}/modernized/evidence/bodies" \
  "${map_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/beta"
cat > "${map_tmp}/modernized/migration.yaml" <<'YAML'
migration:
  legacyBasePackage: com.acme.legacy
  targetPackage: com.demo
  path_rewrites:
    - from: src/main/java/com/demo/
      to: src/main/java/com/acme/legacy/
  intra_package_maps:
    - from: alpha/
      to: beta/
YAML
printf '%s\n' 'package com.acme.legacy.beta; public class Base { private Integer id; }' \
  > "${map_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/beta/Base.java"
printf '%s\n' 'package com.acme.legacy.beta; public class Leaf extends Base { }' \
  > "${map_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/beta/Leaf.java"
python3 - <<PY
import json
from pathlib import Path
root = Path("${map_tmp}/modernized")
body = {
  "identity": {"story_id": "foundational", "operand_count": 1},
  "files_in_scope": ["src/main/java/com/demo/alpha/Leaf.java"],
  "files_writable": ["src/main/java/com/demo/alpha/Leaf.java"],
}
(root / "evidence/bodies/m3-foundational.json").write_text(json.dumps(body) + "\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py" \
    "${map_tmp}/modernized" --body evidence/bodies/m3-foundational.json --write \
    >/tmp/dep-map.out 2>/tmp/dep-map.err; then
  if python3 - "${map_tmp}" <<'PY'
import json, sys
from pathlib import Path
b = json.loads((Path(sys.argv[1]) / "modernized/evidence/bodies/m3-foundational.json").read_text())
fw = set(b.get("files_writable") or [])
ok = "src/main/java/com/demo/alpha/Base.java" in fw
legacy = [d.get("file") for d in (b.get("dependencies") or []) if "acme/legacy" in str(d.get("file") or "")]
raise SystemExit(0 if ok and not legacy else 1)
PY
  then
    echo "OK: intra_package_maps rewrite dest alpha/ onto legacy beta/ and close dest twins"
  else
    echo "FAIL: expected dest alpha/Base.java on files_writable via leaf maps" >&2
    cat /tmp/dep-map.out /tmp/dep-map.err >&2
    cat "${map_tmp}/modernized/evidence/bodies/m3-foundational.json" >&2
    rc=1
  fi
else
  echo "FAIL: mapped dest alpha/Leaf.java should stamp (not HOLE/VACUOUS)" >&2
  cat /tmp/dep-map.out /tmp/dep-map.err >&2
  rc=1
fi
rm -rf "${map_tmp}"

# E-20260819T104254Z — body write-set extras vs partition declared frame
ws_tmp="$(mktemp -d)"
mkdir -p "${ws_tmp}/evidence/briefs" "${ws_tmp}/evidence/bodies" "${ws_tmp}/evidence"
printf '%s\n' '{"stories":[{"story_id":"foundational","files_writable":["src/main/java/com/demo/model/Foo.java"],"endpoints":[{"http_method":"GET","http_path":"/foo"}]}]}' \
  > "${ws_tmp}/evidence/briefs/partition.json"
printf '%s\n' '{"phase":"M3","identity":{"story_id":"foundational"},"files_writable":["src/main/java/com/demo/model/Foo.java","src/main/java/com/demo/entity/Foo.java"],"files_in_scope":["src/main/java/com/demo/model/Foo.java","src/main/java/com/demo/entity/Foo.java"]}' \
  > "${ws_tmp}/evidence/bodies/m3-foundational.json"
printf '%s\n' '{"entry_points":[{"kind":"http","file":"src/Foo.java","symbol":"foo","http_method":"GET","http_path":"/foo"}],"totals":{"http_endpoints":1}}' \
  > "${ws_tmp}/inventory.json"
printf '%s\n' '{"schema":"rhoai3.mta-findings/v1-provisional","violations":{"springboot-to-quarkus-00000":{"ruleID":"springboot-to-quarkus-00000","category":"mandatory","incidents":[]}}}' \
  > "${ws_tmp}/evidence/mta-findings.json"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-partition-coverage.py" \
    "${ws_tmp}" --partition evidence/briefs/partition.json --inventory inventory.json \
    >/tmp/pc-ws.out 2>/tmp/pc-ws.err; then
  echo "FAIL: entity/ extra beside partition model/ should refuse writeset_not_subset" >&2
  cat /tmp/pc-ws.out /tmp/pc-ws.err >&2
  rc=1
else
  if grep -q 'writeset_not_subset:foundational' /tmp/pc-ws.err /tmp/pc-ws.out; then
    echo "OK: PARTITION_COVERAGE refused body write-set extras (writeset_not_subset)"
  else
    echo "FAIL: expected writeset_not_subset:foundational" >&2
    cat /tmp/pc-ws.out /tmp/pc-ws.err >&2
    rc=1
  fi
fi
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py" \
    "${ws_tmp}" --body evidence/bodies/m3-foundational.json --write \
    >/tmp/ws-extra.out 2>/tmp/ws-extra.err; then
  echo "FAIL: stamp-body-dependencies should refuse extras outside partition" >&2
  cat /tmp/ws-extra.out /tmp/ws-extra.err >&2
  rc=1
else
  if grep -q 'WRITESET_NOT_SUBSET' /tmp/ws-extra.err; then
    echo "OK: stamp-body-dependencies WRITESET_NOT_SUBSET on entity/ extra"
  else
    echo "FAIL: expected WRITESET_NOT_SUBSET" >&2
    cat /tmp/ws-extra.out /tmp/ws-extra.err >&2
    rc=1
  fi
fi
rm -rf "${ws_tmp}"

# V34-5 — partition owns leaves; stamp assigns inheritance-reachable supers
# onto that story's frame so DEPENDENCY_HOLE does not fire. Specimen-agnostic
# (no product type names). WRITESET_NOT_SUBSET above still refuses a
# non-inheritance entity/ extra beside model/.
inh_tmp="$(mktemp -d)"
mkdir -p "${inh_tmp}/modernized/evidence/bodies" \
  "${inh_tmp}/modernized/evidence/briefs" \
  "${inh_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/model"
cat > "${inh_tmp}/modernized/migration.yaml" <<'YAML'
migration:
  legacyBasePackage: com.acme.legacy
  targetPackage: com.demo
  path_rewrites:
    - from: src/main/java/com/demo/
      to: src/main/java/com/acme/legacy/
YAML
printf '%s\n' 'package com.acme.legacy.model; public class Base { private Integer id; }' \
  > "${inh_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/model/Base.java"
printf '%s\n' 'package com.acme.legacy.model; public class Mid extends Base { private String name; }' \
  > "${inh_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/model/Mid.java"
printf '%s\n' 'package com.acme.legacy.model; public class Leaf extends Mid { }' \
  > "${inh_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/model/Leaf.java"
python3 - <<PY
import json
from pathlib import Path
root = Path("${inh_tmp}/modernized")
leaf = "src/main/java/com/demo/model/Leaf.java"
part = {
  "schema": "rhoai3.handover-receipt/v1",
  "source": "handover-mint",
  "stories": [{"story_id": "foundational", "files_writable": [leaf], "files_in_scope": [leaf]}],
}
(root / "evidence/briefs/partition.json").write_text(json.dumps(part) + "\n")
body = {
  "identity": {"story_id": "foundational", "operand_count": 1},
  "files_in_scope": [leaf],
  "files_writable": [leaf],
}
(root / "evidence/bodies/m3-foundational.json").write_text(json.dumps(body) + "\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py" \
    "${inh_tmp}/modernized" --body evidence/bodies/m3-foundational.json --write \
    >/tmp/inh-close.out 2>/tmp/inh-close.err; then
  if python3 - "${inh_tmp}" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1]) / "modernized"
b = json.loads((root / "evidence/bodies/m3-foundational.json").read_text())
p = json.loads((root / "evidence/briefs/partition.json").read_text())
fw = set(b.get("files_writable") or [])
want = {
  "src/main/java/com/demo/model/Base.java",
  "src/main/java/com/demo/model/Mid.java",
}
missing = want - fw
story = (p.get("stories") or [{}])[0]
owned = set(story.get("files_writable") or [])
part_miss = want - owned
raise SystemExit(0 if not missing and not part_miss else 1)
PY
  then
    echo "OK: stamp assigns inheritance-reachable supers onto partition"
  else
    echo "FAIL: expected dest Base/Mid on body and partition files_writable" >&2
    cat /tmp/inh-close.out /tmp/inh-close.err >&2
    cat "${inh_tmp}/modernized/evidence/bodies/m3-foundational.json" >&2
    cat "${inh_tmp}/modernized/evidence/briefs/partition.json" >&2
    rc=1
  fi
else
  echo "FAIL: inheritance-reachable supers should stamp without DEPENDENCY_HOLE" >&2
  cat /tmp/inh-close.out /tmp/inh-close.err >&2
  rc=1
fi
rm -rf "${inh_tmp}"

# V34-5 AMEND — import-reachable dest twins (collaborators, not supers)
imp_tmp="$(mktemp -d)"
mkdir -p "${imp_tmp}/modernized/evidence/bodies" \
  "${imp_tmp}/modernized/evidence/briefs" \
  "${imp_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/model" \
  "${imp_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/dto"
cat > "${imp_tmp}/modernized/migration.yaml" <<'YAML'
migration:
  legacyBasePackage: com.acme.legacy
  targetPackage: com.demo
  path_rewrites:
    - from: src/main/java/com/demo/
      to: src/main/java/com/acme/legacy/
YAML
printf '%s\n' \
  'package com.acme.legacy.dto;' \
  'public class LeafDto { private String name; }' \
  > "${imp_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/dto/LeafDto.java"
printf '%s\n' \
  'package com.acme.legacy.model;' \
  'import com.acme.legacy.dto.LeafDto;' \
  'public class Leaf { private LeafDto dto; }' \
  > "${imp_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/model/Leaf.java"
python3 - <<PY
import json
from pathlib import Path
root = Path("${imp_tmp}/modernized")
leaf = "src/main/java/com/demo/model/Leaf.java"
part = {
  "schema": "rhoai3.handover-receipt/v1",
  "source": "handover-mint",
  "stories": [{"story_id": "foundational", "files_writable": [leaf], "files_in_scope": [leaf]}],
}
(root / "evidence/briefs/partition.json").write_text(json.dumps(part) + "\n")
body = {
  "identity": {"story_id": "foundational", "operand_count": 1},
  "files_in_scope": [leaf],
  "files_writable": [leaf],
}
(root / "evidence/bodies/m3-foundational.json").write_text(json.dumps(body) + "\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py" \
    "${imp_tmp}/modernized" --body evidence/bodies/m3-foundational.json --write \
    >/tmp/imp-close.out 2>/tmp/imp-close.err; then
  if python3 - "${imp_tmp}" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1]) / "modernized"
b = json.loads((root / "evidence/bodies/m3-foundational.json").read_text())
p = json.loads((root / "evidence/briefs/partition.json").read_text())
want = {"src/main/java/com/demo/dto/LeafDto.java"}
fw = set(b.get("files_writable") or [])
owned = set((p.get("stories") or [{}])[0].get("files_writable") or [])
deps = b.get("dependencies") or []
pre = [d for d in deps if isinstance(d, dict) and d.get("provider") == "pre-exists"]
raise SystemExit(0 if not (want - fw) and not (want - owned) and not pre else 1)
PY
  then
    echo "OK: stamp assigns import-reachable dest twins onto partition"
  else
    echo "FAIL: expected dest LeafDto on body and partition; no pre-exists" >&2
    cat /tmp/imp-close.out /tmp/imp-close.err >&2
    cat "${imp_tmp}/modernized/evidence/bodies/m3-foundational.json" >&2
    cat "${imp_tmp}/modernized/evidence/briefs/partition.json" >&2
    rc=1
  fi
else
  echo "FAIL: import-reachable dest twins should stamp without DEPENDENCY_HOLE" >&2
  cat /tmp/imp-close.out /tmp/imp-close.err >&2
  rc=1
fi
rm -rf "${imp_tmp}"

# Star-import simple names (import dto.*; used as a simple type)
star_tmp="$(mktemp -d)"
mkdir -p "${star_tmp}/modernized/evidence/bodies" \
  "${star_tmp}/modernized/evidence/briefs" \
  "${star_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/rest/dto"
cat > "${star_tmp}/modernized/migration.yaml" <<'YAML'
migration:
  legacyBasePackage: com.acme.legacy
  targetPackage: com.demo
  path_rewrites:
    - from: src/main/java/com/demo/
      to: src/main/java/com/acme/legacy/
YAML
printf '%s\n' \
  'package com.acme.legacy.rest.dto;' \
  'public class OwnerDto { private String name; }' \
  > "${star_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/rest/dto/OwnerDto.java"
printf '%s\n' \
  'package com.acme.legacy.rest;' \
  'import com.acme.legacy.rest.dto.*;' \
  'public class OwnerRest { OwnerDto d; }' \
  > "${star_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/rest/OwnerRest.java"
python3 - <<PY
import json
from pathlib import Path
root = Path("${star_tmp}/modernized")
leaf = "src/main/java/com/demo/rest/OwnerRest.java"
part = {
  "schema": "rhoai3.handover-receipt/v1",
  "source": "handover-mint",
  "stories": [{"story_id": "foundational", "files_writable": [leaf], "files_in_scope": [leaf]}],
}
(root / "evidence/briefs/partition.json").write_text(json.dumps(part) + "\n")
body = {
  "identity": {"story_id": "foundational", "operand_count": 1},
  "files_in_scope": [leaf],
  "files_writable": [leaf],
}
(root / "evidence/bodies/m3-foundational.json").write_text(json.dumps(body) + "\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py" \
    "${star_tmp}/modernized" --body evidence/bodies/m3-foundational.json --write \
    >/tmp/star-imp.out 2>/tmp/star-imp.err; then
  if python3 - "${star_tmp}" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1]) / "modernized"
b = json.loads((root / "evidence/bodies/m3-foundational.json").read_text())
p = json.loads((root / "evidence/briefs/partition.json").read_text())
want = {"src/main/java/com/demo/rest/dto/OwnerDto.java"}
fw = set(b.get("files_writable") or [])
owned = set((p.get("stories") or [{}])[0].get("files_writable") or [])
pre = [d for d in (b.get("dependencies") or []) if isinstance(d, dict) and d.get("provider") == "pre-exists"]
raise SystemExit(0 if not (want - fw) and not (want - owned) and not pre else 1)
PY
  then
    echo "OK: stamp assigns star-import dest twins onto partition"
  else
    echo "FAIL: expected dest OwnerDto via star-import; no pre-exists" >&2
    cat /tmp/star-imp.out /tmp/star-imp.err >&2
    cat "${star_tmp}/modernized/evidence/bodies/m3-foundational.json" >&2
    cat "${star_tmp}/modernized/evidence/briefs/partition.json" >&2
    rc=1
  fi
else
  echo "FAIL: star-import dest twins should stamp without DEPENDENCY_HOLE" >&2
  cat /tmp/star-imp.out /tmp/star-imp.err >&2
  rc=1
fi
rm -rf "${star_tmp}"

# M1 type-graph inventory (no --body)
tg_tmp="$(mktemp -d)"
mkdir -p "${tg_tmp}/modernized/evidence" \
  "${tg_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/rest/dto"
cat > "${tg_tmp}/modernized/migration.yaml" <<'YAML'
migration:
  legacyBasePackage: com.acme.legacy
  targetPackage: com.demo
  path_rewrites:
    - from: src/main/java/com/demo/
      to: src/main/java/com/acme/legacy/
YAML
printf '%s\n' \
  'package com.acme.legacy.rest.dto;' \
  'public class OwnerDto { private String name; }' \
  > "${tg_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/rest/dto/OwnerDto.java"
printf '%s\n' \
  'package com.acme.legacy.rest;' \
  'import com.acme.legacy.rest.dto.*;' \
  'public class OwnerRest { OwnerDto d; }' \
  > "${tg_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/rest/OwnerRest.java"
python3 - <<PY
import json
from pathlib import Path
root = Path("${tg_tmp}/modernized")
inv = {
  "schema": "rhoai3.entry-point-inventory/v1",
  "entry_points": [{
    "kind": "http",
    "file": "src/main/java/com/acme/legacy/rest/OwnerRest.java",
    "symbol": "OwnerRest#get",
    "http_method": "GET",
    "http_path": "/api/owners",
  }],
}
(root / "evidence/entry-point-inventory.json").write_text(json.dumps(inv) + "\n")
PY
if python3 "${SKILLS}/analysis/inventory-entry-points/scripts/inventory-type-graph.py" \
    --dest-root "${tg_tmp}/modernized" \
    --inventory evidence/entry-point-inventory.json \
    --legacy "${tg_tmp}/.derived/legacy-at-3" \
    -o evidence/type-inventory.json \
    >/tmp/tg-inv.out 2>/tmp/tg-inv.err; then
  if python3 - "${tg_tmp}" <<'PY'
import json, sys
from pathlib import Path
data = json.loads((Path(sys.argv[1]) / "modernized/evidence/type-inventory.json").read_text())
if data.get("schema") != "rhoai3.type-inventory/v1":
    raise SystemExit(1)
dests = {t.get("dest_file") for t in data.get("types") or []}
want = "src/main/java/com/demo/rest/dto/OwnerDto.java"
raise SystemExit(0 if want in dests else 1)
PY
  then
    echo "OK: type-inventory lists dest twins from entry files"
  else
    echo "FAIL: type-inventory missing dest OwnerDto" >&2
    cat /tmp/tg-inv.out /tmp/tg-inv.err >&2
    cat "${tg_tmp}/modernized/evidence/type-inventory.json" >&2
    rc=1
  fi
else
  echo "FAIL: inventory-type-graph.py should emit type-inventory.json" >&2
  cat /tmp/tg-inv.out /tmp/tg-inv.err >&2
  rc=1
fi
rm -rf "${tg_tmp}"

# Type-inventory dest twin absent from partition → types_uncovered
tcov_tmp="$(mktemp -d)"
mkdir -p "${tcov_tmp}/evidence/briefs"
python3 - "${tcov_tmp}" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
(root / "evidence/briefs/partition.json").write_text(json.dumps({
  "stories": [{
    "story_id": "US1",
    "files_writable": ["src/main/java/com/demo/resource/OwnerResource.java"],
    "files_in_scope": ["src/main/java/com/demo/resource/OwnerResource.java"],
    "endpoints": ["GET /api/owners"],
    "rules": ["springboot-to-quarkus-00000"],
  }]
}) + "\n")
(root / "inventory.json").write_text(json.dumps({
  "entry_points": [{
    "kind": "http",
    "file": "src/main/java/org/example/demo/rest/OwnerRest.java",
    "symbol": "OwnerRest#get",
    "http_method": "GET",
    "http_path": "/api/owners",
  }],
  "totals": {"http_endpoints": 1},
}) + "\n")
(root / "evidence/mta-findings.json").write_text(json.dumps({
  "schema": "rhoai3.mta-findings/v1-provisional",
  "violations": {"springboot-to-quarkus-00000": {"ruleID": "springboot-to-quarkus-00000", "category": "mandatory", "incidents": []}},
}) + "\n")
(root / "evidence/type-inventory.json").write_text(json.dumps({
  "schema": "rhoai3.type-inventory/v1",
  "types": [{
    "legacy_file": "src/main/java/org/example/demo/rest/dto/OwnerDto.java",
    "dest_file": "src/main/java/com/demo/dto/OwnerDto.java",
    "layer": "dto",
    "reached_from": ["src/main/java/org/example/demo/rest/OwnerRest.java"],
  }],
}) + "\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-partition-coverage.py" \
    "${tcov_tmp}" --partition evidence/briefs/partition.json --inventory inventory.json \
    >/tmp/pc-types.out 2>/tmp/pc-types.err; then
  echo "FAIL: uncovered type-inventory dest twin must be INVALID" >&2
  cat /tmp/pc-types.out /tmp/pc-types.err >&2
  rc=1
elif grep -q 'types_uncovered' /tmp/pc-types.out /tmp/pc-types.err; then
  echo "OK: PARTITION_COVERAGE types_uncovered when dest twin is unplanned"
else
  echo "FAIL: expected types_uncovered gap" >&2
  cat /tmp/pc-types.out /tmp/pc-types.err >&2
  rc=1
fi
rm -rf "${tcov_tmp}"

# Generated types: classify provider generated; skip DEST_MISS; require inputs
gen_tmp="$(mktemp -d)"
mkdir -p "${gen_tmp}/modernized/evidence/bodies" \
  "${gen_tmp}/modernized/evidence/briefs" \
  "${gen_tmp}/modernized/src/main/resources" \
  "${gen_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/mapper" \
  "${gen_tmp}/.derived/legacy-at-3/target/generated-sources/openapi/src/main/java/com/acme/legacy/rest/dto"
cat > "${gen_tmp}/modernized/migration.yaml" <<'YAML'
migration:
  legacyBasePackage: com.acme.legacy
  targetPackage: com.demo
  path_rewrites:
    - from: src/main/java/com/demo/
      to: src/main/java/com/acme/legacy/
YAML
cat > "${gen_tmp}/modernized/pom.xml" <<'XML'
<project>
  <build><plugins>
    <plugin>
      <artifactId>openapi-generator-maven-plugin</artifactId>
      <configuration>
        <inputSpec>src/main/resources/api-docs.yml</inputSpec>
        <modelPackage>com.acme.legacy.rest.dto</modelPackage>
        <output>target/generated-sources/openapi</output>
      </configuration>
    </plugin>
  </plugins></build>
</project>
XML
cp "${gen_tmp}/modernized/pom.xml" "${gen_tmp}/.derived/legacy-at-3/pom.xml"
printf '%s\n' 'openapi: 3.0.0' > "${gen_tmp}/modernized/src/main/resources/api-docs.yml"
printf '%s\n' \
  'package com.acme.legacy.rest.dto;' \
  '@javax.annotation.Generated("org.openapitools")' \
  'public class GenType { private String id; }' \
  > "${gen_tmp}/.derived/legacy-at-3/target/generated-sources/openapi/src/main/java/com/acme/legacy/rest/dto/GenType.java"
printf '%s\n' \
  'package com.acme.legacy.mapper;' \
  'import com.acme.legacy.rest.dto.GenType;' \
  'public class LeafMapper { private GenType t; }' \
  > "${gen_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/mapper/LeafMapper.java"
python3 - <<PY
import json
from pathlib import Path
root = Path("${gen_tmp}/modernized")
leaf = "src/main/java/com/demo/mapper/LeafMapper.java"
pom = "pom.xml"
spec = "src/main/resources/api-docs.yml"
part = {
  "schema": "rhoai3.handover-receipt/v1",
  "source": "handover-mint",
  "stories": [
    {"story_id": "setup", "files_writable": [pom, spec], "files_in_scope": [pom, spec]},
    {"story_id": "foundational", "files_writable": [leaf], "files_in_scope": [leaf]},
  ],
}
(root / "evidence/briefs/partition.json").write_text(json.dumps(part) + "\n")
body = {
  "identity": {"story_id": "foundational", "operand_count": 1},
  "files_in_scope": [leaf],
  "files_writable": [leaf],
}
(root / "evidence/bodies/m3-foundational.json").write_text(json.dumps(body) + "\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py" \
    "${gen_tmp}/modernized" --body evidence/bodies/m3-foundational.json --write \
    >/tmp/gen-stamp.out 2>/tmp/gen-stamp.err; then
  if python3 - "${gen_tmp}" <<'PY'
import json, sys
from pathlib import Path
b = json.loads((Path(sys.argv[1]) / "modernized/evidence/bodies/m3-foundational.json").read_text())
deps = b.get("dependencies") or []
got = [d for d in deps if isinstance(d, dict) and d.get("provider") == "generated"]
fw = set(b.get("files_writable") or [])
raise SystemExit(0 if got and not any("GenType.java" in x for x in fw) else 1)
PY
  then
    echo "OK: stamp classifies generated types"
  else
    echo "FAIL: expected provider generated and GenType not assigned" >&2
    cat /tmp/gen-stamp.out /tmp/gen-stamp.err >&2
    cat "${gen_tmp}/modernized/evidence/bodies/m3-foundational.json" >&2
    rc=1
  fi
else
  echo "FAIL: generated types should stamp without DEPENDENCY_HOLE" >&2
  cat /tmp/gen-stamp.out /tmp/gen-stamp.err >&2
  rc=1
fi
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-dependency-closure.py" \
    "${gen_tmp}/modernized" --body evidence/bodies/m3-foundational.json \
    >/tmp/gen-assert.out 2>/tmp/gen-assert.err; then
  echo "OK: generated DEST_MISS skipped when inputs owned"
else
  echo "FAIL: generated provider should skip DEST_MISS when spec+pom owned" >&2
  cat /tmp/gen-assert.out /tmp/gen-assert.err >&2
  rc=1
fi
# Same tree, spec dropped from the plan → GENERATOR_INPUTS
python3 - "${gen_tmp}" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1]) / "modernized"
part = json.loads((root / "evidence/briefs/partition.json").read_text())
part["stories"][0]["files_writable"] = ["pom.xml"]
part["stories"][0]["files_in_scope"] = ["pom.xml"]
(root / "evidence/briefs/partition.json").write_text(json.dumps(part) + "\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-dependency-closure.py" \
    "${gen_tmp}/modernized" --body evidence/bodies/m3-foundational.json \
    >/tmp/gen-miss.out 2>/tmp/gen-miss.err; then
  echo "FAIL: missing generator spec must GENERATOR_INPUTS" >&2
  cat /tmp/gen-miss.out /tmp/gen-miss.err >&2
  rc=1
elif grep -q 'GENERATOR_INPUTS' /tmp/gen-miss.err \
  && grep -q 'build_file=' /tmp/gen-miss.err; then
  echo "OK: GENERATOR_INPUTS when spec unowned"
else
  echo "FAIL: expected GENERATOR_INPUTS with F-5 build_file" >&2
  cat /tmp/gen-miss.out /tmp/gen-miss.err >&2
  rc=1
fi
rm -rf "${gen_tmp}"

# H-1: dest pom has no generator plugin; legacy-at-3 does. Handwritten
# type-inventory must not inherit legacy inputSpec (v40 api-docs.yml).
h1_tmp="$(mktemp -d)"
mkdir -p "${h1_tmp}/modernized/evidence/bodies" \
  "${h1_tmp}/modernized/evidence/briefs" \
  "${h1_tmp}/.derived/legacy-at-3/src/main/resources"
cat > "${h1_tmp}/modernized/pom.xml" <<'XML'
<project>
  <build><plugins>
    <plugin><artifactId>quarkus-maven-plugin</artifactId></plugin>
  </plugins></build>
</project>
XML
cat > "${h1_tmp}/.derived/legacy-at-3/pom.xml" <<'XML'
<project>
  <build><plugins>
    <plugin>
      <artifactId>openapi-generator-maven-plugin</artifactId>
      <configuration>
        <inputSpec>src/main/resources/api-docs.yml</inputSpec>
      </configuration>
    </plugin>
  </plugins></build>
</project>
XML
printf '%s\n' 'openapi: 3.0.0' > "${h1_tmp}/.derived/legacy-at-3/src/main/resources/api-docs.yml"
python3 - "${h1_tmp}" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1]) / "modernized"
leaf = "src/main/java/com/demo/mapper/LeafMapper.java"
part = {
  "schema": "rhoai3.handover-receipt/v1",
  "source": "handover-mint",
  "stories": [
    {"story_id": "setup", "files_writable": ["pom.xml"], "files_in_scope": ["pom.xml"]},
    {"story_id": "foundational", "files_writable": [leaf], "files_in_scope": [leaf]},
  ],
}
(root / "evidence/briefs/partition.json").write_text(json.dumps(part) + "\n")
(root / "evidence/type-inventory.json").parent.mkdir(parents=True, exist_ok=True)
(root / "evidence/type-inventory.json").write_text(json.dumps({
  "schema": "rhoai3.type-inventory/v1",
  "types": [{
    "dest_file": leaf,
    "generated": False,
    "layer": "mapper",
  }],
}) + "\n")
body = {
  "identity": {"story_id": "foundational", "operand_count": 1},
  "files_in_scope": [leaf],
  "files_writable": [leaf],
  "dependencies": [
    {"file": leaf, "provider": "source"},
  ],
}
(root / "evidence/bodies/m3-foundational.json").write_text(json.dumps(body) + "\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-dependency-closure.py" \
    "${h1_tmp}/modernized" --body evidence/bodies/m3-foundational.json \
    >/tmp/h1-assert.out 2>/tmp/h1-assert.err; then
  echo "OK: GENERATOR_INPUTS skipped when dest has no plugin"
else
  echo "FAIL: handwritten dest must not inherit legacy-at-3 GENERATOR_INPUTS" >&2
  cat /tmp/h1-assert.out /tmp/h1-assert.err >&2
  rc=1
fi
rm -rf "${h1_tmp}"

# Generated type-inventory rows are not types_uncovered
tgen_tmp="$(mktemp -d)"
mkdir -p "${tgen_tmp}/evidence/briefs"
python3 - "${tgen_tmp}" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
(root / "evidence/briefs/partition.json").write_text(json.dumps({
  "stories": [{
    "story_id": "US1",
    "files_writable": ["src/main/java/com/demo/resource/OwnerResource.java"],
    "files_in_scope": ["src/main/java/com/demo/resource/OwnerResource.java"],
    "endpoints": ["GET /api/owners"],
    "rules": ["springboot-to-quarkus-00000"],
  }]
}) + "\n")
(root / "inventory.json").write_text(json.dumps({
  "entry_points": [{
    "kind": "http",
    "file": "src/main/java/org/example/demo/rest/OwnerRest.java",
    "symbol": "OwnerRest#get",
    "http_method": "GET",
    "http_path": "/api/owners",
  }],
  "totals": {"http_endpoints": 1},
}) + "\n")
(root / "evidence/mta-findings.json").write_text(json.dumps({
  "schema": "rhoai3.mta-findings/v1-provisional",
  "violations": {"springboot-to-quarkus-00000": {"ruleID": "springboot-to-quarkus-00000", "category": "mandatory", "incidents": []}},
}) + "\n")
(root / "evidence/type-inventory.json").write_text(json.dumps({
  "schema": "rhoai3.type-inventory/v1",
  "types": [{
    "dest_file": "target/generated-sources/openapi/com/demo/dto/OwnerDto.java",
    "generated": False,
    "layer": "dto",
  }],
}) + "\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-partition-coverage.py" \
    "${tgen_tmp}" --partition evidence/briefs/partition.json --inventory inventory.json \
    >/tmp/pc-tgen.out 2>/tmp/pc-tgen.err; then
  if grep -q 'VALID' /tmp/pc-tgen.out && ! grep -q 'types_uncovered' /tmp/pc-tgen.out /tmp/pc-tgen.err; then
    echo "OK: PARTITION_COVERAGE skips generated type-inventory dest twins"
  else
    echo "FAIL: generated dest twins must not types_uncovered" >&2
    cat /tmp/pc-tgen.out /tmp/pc-tgen.err >&2
    rc=1
  fi
else
  echo "FAIL: generated type-inventory rows should be VALID skip" >&2
  cat /tmp/pc-tgen.out /tmp/pc-tgen.err >&2
  rc=1
fi
rm -rf "${tgen_tmp}"

# v41 attack: stored generated:true on a handwritten src/ twin must still uncover
tgen_lie_tmp="$(mktemp -d)"
mkdir -p "${tgen_lie_tmp}/evidence/briefs"
python3 - "${tgen_lie_tmp}" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
(root / "evidence/briefs/partition.json").write_text(json.dumps({
  "stories": [{
    "story_id": "US1",
    "files_writable": ["src/main/java/com/demo/resource/OwnerResource.java"],
    "files_in_scope": ["src/main/java/com/demo/resource/OwnerResource.java"],
    "endpoints": ["GET /api/owners"],
    "rules": ["springboot-to-quarkus-00000"],
  }]
}) + "\n")
(root / "inventory.json").write_text(json.dumps({
  "entry_points": [{
    "kind": "http",
    "file": "src/main/java/org/example/demo/rest/OwnerRest.java",
    "symbol": "OwnerRest#get",
    "http_method": "GET",
    "http_path": "/api/owners",
  }],
  "totals": {"http_endpoints": 1},
}) + "\n")
(root / "evidence/mta-findings.json").write_text(json.dumps({
  "schema": "rhoai3.mta-findings/v1-provisional",
  "violations": {"springboot-to-quarkus-00000": {"ruleID": "springboot-to-quarkus-00000", "category": "mandatory", "incidents": []}},
}) + "\n")
(root / "evidence/type-inventory.json").write_text(json.dumps({
  "schema": "rhoai3.type-inventory/v1",
  "types": [{
    "dest_file": "src/main/java/com/demo/service/AppService.java",
    "generated": True,
    "layer": "service",
  }],
}) + "\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-partition-coverage.py" \
    "${tgen_lie_tmp}" --partition evidence/briefs/partition.json --inventory inventory.json \
    >/tmp/pc-tgen-lie.out 2>/tmp/pc-tgen-lie.err; then
  echo "FAIL: handwritten dest twin with generated:true must still types_uncovered" >&2
  cat /tmp/pc-tgen-lie.out /tmp/pc-tgen-lie.err >&2
  rc=1
elif grep -q 'types_uncovered' /tmp/pc-tgen-lie.out /tmp/pc-tgen-lie.err \
  && grep -q 'AppService.java' /tmp/pc-tgen-lie.out /tmp/pc-tgen-lie.err; then
  echo "OK: PARTITION_COVERAGE still demands handwritten type when generated:true is stored"
else
  echo "FAIL: expected types_uncovered AppService.java despite stored generated:true" >&2
  cat /tmp/pc-tgen-lie.out /tmp/pc-tgen-lie.err >&2
  rc=1
fi
rm -rf "${tgen_lie_tmp}"

cp_tmp="$(mktemp -d)"
if python3 "${SKILLS}/harness/dispatch-phase/scripts/holder-checkpoint.py" \
    init --kind m2 --task-id t_m2fix --root "${cp_tmp}" \
    >/tmp/m2cp.out 2>/tmp/m2cp.err \
  && python3 "${SKILLS}/harness/dispatch-phase/scripts/holder-checkpoint.py" \
    stamp --kind m2 --task-id t_m2fix --root "${cp_tmp}" --next assemble \
    >/dev/null \
  && python3 "${SKILLS}/harness/dispatch-phase/scripts/holder-checkpoint.py" \
    check --kind m2 --task-id t_m2fix --root "${cp_tmp}" \
    >/tmp/m2cp-check.out 2>/tmp/m2cp-check.err; then
  if grep -q 'rhoai3.m2-checkpoint/v1' "${cp_tmp}/evidence/runs/t_m2fix/checkpoint.json" \
    && grep -q 'next=assemble' /tmp/m2cp-check.out; then
    echo "OK: M2 checkpoint init/stamp/check --kind m2"
  else
    echo "FAIL: M2 checkpoint schema or next missing" >&2
    cat /tmp/m2cp.out /tmp/m2cp.err /tmp/m2cp-check.out >&2
    rc=1
  fi
else
  echo "FAIL: holder-checkpoint --kind m2" >&2
  cat /tmp/m2cp.out /tmp/m2cp.err /tmp/m2cp-check.out /tmp/m2cp-check.err >&2
  rc=1
fi
if python3 "${SKILLS}/harness/dispatch-phase/scripts/holder-checkpoint.py" \
    init --kind m2 --task-id t_m2fix --root "${cp_tmp}" --next assemble \
    >/tmp/m2cp-initnext.out 2>/tmp/m2cp-initnext.err; then
  echo "FAIL: holder-checkpoint init --next must refuse" >&2
  cat /tmp/m2cp-initnext.out /tmp/m2cp-initnext.err >&2
  rc=1
elif grep -q 'init does not take --next' /tmp/m2cp-initnext.err; then
  echo "OK: holder-checkpoint init refuses --next"
else
  echo "FAIL: expected init does not take --next" >&2
  cat /tmp/m2cp-initnext.out /tmp/m2cp-initnext.err >&2
  rc=1
fi
rm -rf "${cp_tmp}"

# V34-2 — HARNESS_REV stamp
rev_tmp="$(mktemp -d)"
if python3 "${SKILLS}/harness/dispatch-phase/scripts/stamp-harness-rev.py" \
    --root "${rev_tmp}" --sha aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
    >/tmp/hrev.out 2>/tmp/hrev.err \
  && grep -qx 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "${rev_tmp}/.hermes/HARNESS_REV"; then
  echo "OK: stamp-harness-rev writes HARNESS_REV"
else
  echo "FAIL: stamp-harness-rev" >&2
  cat /tmp/hrev.out /tmp/hrev.err >&2
  rc=1
fi
rm -rf "${rev_tmp}"

# Architect 075106Z / 140201Z — autostart known-bad fixtures MUST refuse
as_tmp="$(mktemp -d)"
mkdir -p "${as_tmp}/.hermes/home"
printf '%s\n' 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' >"${as_tmp}/.hermes/HARNESS_REV"
if python3 "${SKILLS}/harness/dispatch-phase/scripts/assert-autostart-gates.py" \
    harness-rev --root "${as_tmp}" \
    --expected-sha aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
    >/tmp/as-rev.out 2>/tmp/as-rev.err; then
  echo "FAIL: autostart harness-rev mismatch did not refuse" >&2
  cat /tmp/as-rev.out /tmp/as-rev.err >&2
  rc=1
else
  echo "OK: autostart refuses HARNESS_REV mismatch"
fi
python3 - "${as_tmp}" <<'PY'
import sqlite3, sys
from pathlib import Path
root = Path(sys.argv[1])
db = root / ".hermes" / "home" / "kanban.db"
con = sqlite3.connect(db)
con.execute(
    "CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, "
    "skills TEXT, body TEXT, status TEXT, created_at INTEGER)"
)
con.execute(
    "INSERT INTO tasks (id, title, skills, body, status, created_at) "
    "VALUES (?,?,?,?,?,0)",
    ("t_hold", "M3 WAVE HOLDER: mint story children", '["dispatch-phase"]', "", "todo"),
)
con.commit()
con.close()
PY
if python3 "${SKILLS}/harness/dispatch-phase/scripts/assert-autostart-gates.py" \
    holder --root "${as_tmp}" \
    >/tmp/as-hold.out 2>/tmp/as-hold.err; then
  echo "FAIL: autostart skill-pinned holder did not refuse" >&2
  cat /tmp/as-hold.out /tmp/as-hold.err >&2
  rc=1
else
  echo "OK: autostart refuses skill-pinned WAVE HOLDER"
fi
python3 - "${as_tmp}" <<'PY'
import sqlite3, sys
from pathlib import Path
root = Path(sys.argv[1])
db = root / ".hermes" / "home" / "kanban.db"
con = sqlite3.connect(db)
con.execute("UPDATE tasks SET skills='[]' WHERE id='t_hold'")
con.commit()
con.close()
PY
if python3 "${SKILLS}/harness/dispatch-phase/scripts/assert-autostart-gates.py" \
    holder --root "${as_tmp}" \
    >/tmp/as-hold-ok.out 2>/tmp/as-hold-ok.err; then
  echo "OK: autostart holder skills=[] passes"
else
  echo "FAIL: autostart empty-skill holder should pass" >&2
  cat /tmp/as-hold-ok.out /tmp/as-hold-ok.err >&2
  rc=1
fi
if AUTO_START_MIGRATION=0 bash "${SKILLS}/harness/dispatch-phase/scripts/autostart-migration.sh" \
    --root "${as_tmp}" --skip-dispatch >/tmp/as-skip.out 2>/tmp/as-skip.err \
  && grep -q 'state: SKIPPED' "${as_tmp}/.hermes/AUTOSTART-STATUS"; then
  echo "OK: autostart AUTO_START_MIGRATION=0 writes SKIPPED marker"
else
  echo "FAIL: autostart skip marker" >&2
  cat /tmp/as-skip.out /tmp/as-skip.err >&2
  rc=1
fi
rm -rf "${as_tmp}"

# v37 dest-cite: pin probe must be hermes --version (binary-local). A usage dump
# from `hermes version` is argparse noise, not a version string. Probe-broken=2.
PIN_ASSERT="${SKILLS}/harness/dispatch-phase/scripts/assert-seat-hermes-pin.py"
if grep -q '\["hermes", "--version"\]' "${PIN_ASSERT}" \
  && ! grep -q '\["hermes", "version"\]' "${PIN_ASSERT}"; then
  echo "OK: seat Hermes pin probe is hermes --version not version subcommand"
else
  echo "FAIL: assert-seat-hermes-pin.py must probe hermes --version (v37 false-refusal)" >&2
  rc=1
fi
pin_tmp="$(mktemp -d "${TMPDIR:-/tmp}/pinprobe.XXXXXX")"
mkdir -p "${pin_tmp}/.hermes" "${pin_tmp}/bin"
cp "${ROOT}/.hermes/pins.json" "${pin_tmp}/.hermes/pins.json"
cat >"${pin_tmp}/bin/hermes" <<'FAKE'
#!/usr/bin/env bash
if [[ "${1:-}" == "--version" || "${1:-}" == "-V" ]]; then
  echo "Hermes Agent v0.20.4 (2026.8.18)"
  exit 0
fi
if [[ "${1:-}" == "version" ]]; then
  echo "usage: hermes [-h] [--version]" >&2
  echo "hermes: error: argument command: invalid choice: 'version'" >&2
  exit 2
fi
echo "usage: hermes [-h] [--version]" >&2
exit 2
FAKE
chmod +x "${pin_tmp}/bin/hermes"
if PATH="${pin_tmp}/bin:${PATH}" python3 "${PIN_ASSERT}" "${pin_tmp}" \
    >/tmp/pin-ok.out 2>/tmp/pin-ok.err; then
  echo "OK: seat Hermes pin matches fake --version v0.20.4"
else
  echo "FAIL: seat Hermes pin should match fake --version v0.20.4" >&2
  cat /tmp/pin-ok.out /tmp/pin-ok.err >&2
  rc=1
fi
cat >"${pin_tmp}/bin/hermes" <<'FAKE'
#!/usr/bin/env bash
# Replicate the v37 dest binary: argparse rejects the version subcommand.
echo "usage: hermes [-h] [--version]" >&2
echo "hermes: error: argument command: invalid choice: 'version'" >&2
exit 2
FAKE
chmod +x "${pin_tmp}/bin/hermes"
pin_noise_rc=0
PATH="${pin_tmp}/bin:${PATH}" python3 "${PIN_ASSERT}" "${pin_tmp}" \
  >/tmp/pin-noise.out 2>/tmp/pin-noise.err || pin_noise_rc=$?
if [[ "${pin_noise_rc}" -eq 2 ]] \
  && grep -q 'hermes --version unreadable' /tmp/pin-noise.err; then
  echo "OK: seat Hermes pin returns 2 on argparse usage dump"
else
  echo "FAIL: argparse usage dump must be unreadable (exit 2), not drift (exit 1)" >&2
  echo "rc=${pin_noise_rc}" >&2
  cat /tmp/pin-noise.out /tmp/pin-noise.err >&2
  rc=1
fi
cat >"${pin_tmp}/bin/hermes" <<'FAKE'
#!/usr/bin/env bash
if [[ "${1:-}" == "--version" || "${1:-}" == "-V" ]]; then
  echo "Hermes Agent v0.19.0 (stale)"
  exit 0
fi
exit 2
FAKE
chmod +x "${pin_tmp}/bin/hermes"
pin_drift_rc=0
PATH="${pin_tmp}/bin:${PATH}" python3 "${PIN_ASSERT}" "${pin_tmp}" \
  >/tmp/pin-drift.out 2>/tmp/pin-drift.err || pin_drift_rc=$?
if [[ "${pin_drift_rc}" -eq 1 ]]; then
  echo "OK: seat Hermes pin returns 1 on version drift"
else
  echo "FAIL: version drift must be exit 1" >&2
  echo "rc=${pin_drift_rc}" >&2
  cat /tmp/pin-drift.out /tmp/pin-drift.err >&2
  rc=1
fi
rm -rf "${pin_tmp}"

# v38 dest-cite: dest create runs this live. Laptop greps were GREEN while
# bare issue-m3-brief-identity-ack.py in M1/M2/holder failed R0 body-script lint.
if python3 "${SKILLS}/harness/dispatch-phase/scripts/check-phase-body-script-refs.py" "${ROOT}" \
    >/tmp/body-refs.out 2>/tmp/body-refs.err; then
  echo "OK: phase body script refs (live; dest create runs this)"
else
  echo "FAIL: phase body script refs (v38 dest-cite)" >&2
  cat /tmp/body-refs.out /tmp/body-refs.err >&2
  rc=1
fi

# Architect V34-6 — dest-home kanban pins in dispatch-phase write
if grep -q 'auto_decompose: false' "${SKILLS}/harness/dispatch-phase/scripts/dispatch-phase.sh"; then
  echo "OK: dest-home kanban auto_decompose false"
else
  echo "FAIL: dispatch-phase.sh missing dest-home auto_decompose false" >&2
  rc=1
fi

# E-20260819T173800Z — holder starves JSON (compose + pre-create wrapper + park)
cm_tmp="$(mktemp -d)"
mkdir -p "${cm_tmp}/evidence/bodies" "${cm_tmp}/evidence/briefs" \
  "${cm_tmp}/.hermes/skills/harness/dispatch-phase/scripts" \
  "${cm_tmp}/.hermes/home"
cp "${ROOT}/.hermes/phase-dispatch.yaml" "${cm_tmp}/.hermes/phase-dispatch.yaml"
cp "${SKILLS}/harness/dispatch-phase/scripts/read-phase-dispatch.py" \
  "${cm_tmp}/.hermes/skills/harness/dispatch-phase/scripts/read-phase-dispatch.py"
python3 - <<PY
import hashlib, json
from pathlib import Path
root = Path("${cm_tmp}")
sid = "setup"
heading = "Setup (Shared Infrastructure)"
paths = [f"src/main/java/com/demo/model/Type{i:02d}.java" for i in range(40)]
body = {
  "identity": {"story_id": sid, "operand_count": 1},
  "exit_criteria": ["build_resolves"],
  "files_writable": paths,
}
bp = root / "evidence/bodies/m3-setup.json"
raw = json.dumps(body) + "\n"
bp.write_text(raw)
digest = hashlib.sha256(raw.encode()).hexdigest()
(bp.with_suffix(bp.suffix + ".sha256.json")).write_text(
    json.dumps({"body_sha256": digest}) + "\n"
)
(root / "evidence/briefs/partition.json").write_text(json.dumps({
  "schema": "rhoai3.handover-receipt/v1",
  "source": "handover-mint",
  "stories": [{"story_id": sid, "heading": heading, "files_writable": paths[:1]}],
}) + "\n")
print(digest)
PY
if title="$(python3 "${SKILLS}/harness/dispatch-phase/scripts/compose-m3-card-markdown.py" \
    --root "${cm_tmp}" --body evidence/bodies/m3-setup.json --print-title)"; then
  if [ "${title}" = "M3 IMPLEMENT: setup — Shared Infrastructure" ] && \
     ! printf '%s' "${title}" | grep -q '{'; then
    echo "OK: compose-m3-card-markdown prints title without JSON"
  else
    echo "FAIL: compose title want house form, no JSON: ${title}" >&2
    rc=1
  fi
else
  echo "FAIL: compose --print-title" >&2
  rc=1
fi
if md="$(python3 "${SKILLS}/harness/dispatch-phase/scripts/compose-m3-card-markdown.py" \
    --root "${cm_tmp}" --body evidence/bodies/m3-setup.json)"; then
  if printf '%s' "${md}" | grep -q 'Typed body: evidence/bodies/m3-setup.json' && \
     printf '%s' "${md}" | grep -q 'see typed body (40 paths)' && \
     ! printf '%s' "${md}" | grep -q '^{' && \
     [ "${#md}" -le 1500 ]; then
    echo "OK: compose-m3-card-markdown stays under F6 budget without JSON dump"
  else
    echo "FAIL: compose markdown leaked JSON or exceeded F6" >&2
    printf '%s\n' "${md}" >&2
    rc=1
  fi
else
  echo "FAIL: compose markdown" >&2
  rc=1
fi
refuse="$(python3 "${SKILLS}/harness/dispatch-phase/scripts/run-pre-create-gates.py" \
    --root "${cm_tmp}" --body evidence/bodies/missing.json 2>/dev/null || true)"
if printf '%s\n' "${refuse}" | grep -q '^REFUSE:' && \
   [ "$(printf '%s\n' "${refuse}" | wc -l | tr -d ' ')" = 1 ] && \
   ! printf '%s' "${refuse}" | grep -q '{'; then
  echo "OK: run-pre-create-gates prints one REFUSE line without JSON"
else
  echo "FAIL: run-pre-create-gates should one-line REFUSE: ${refuse}" >&2
  rc=1
fi
park_db="${cm_tmp}/.hermes/home/kanban.db"
python3 - <<PY
import sqlite3
from pathlib import Path
db = Path("${park_db}")
con = sqlite3.connect(str(db))
con.execute("create table tasks (id text, status text)")
con.execute("create table task_links (parent_id text, child_id text)")
con.execute("insert into tasks values ('t_child','todo')")
con.execute("insert into task_links values ('t_holder','t_child')")
con.execute("insert into task_links values ('t_gate','t_child')")
con.commit()
PY
if python3 "${SKILLS}/harness/dispatch-phase/scripts/assert-story-parked.py" \
    "${cm_tmp}" --task-id t_child --ack-gate t_gate | grep -q '^OK: parked t_child'; then
  echo "OK: assert-story-parked one-line from sqlite"
else
  echo "FAIL: assert-story-parked should OK parked todo+ack parent" >&2
  rc=1
fi
rm -rf "${cm_tmp}"

# E-20260819T104826Z — sidecar-only restamp refuse; atomic card+sidecar restamp
rs_tmp="$(mktemp -d)"
mkdir -p "${rs_tmp}/evidence/bodies" "${rs_tmp}/.hermes/home"
printf '%s\n' '{"phase":"M3","identity":{"story_id":"polish"},"task_id":"t_aabbccdd"}' \
  > "${rs_tmp}/evidence/bodies/m3-polish.json"
if python3 "${SKILLS}/harness/record-run-evidence/scripts/stamp-body-digest.py" \
    "${rs_tmp}/evidence/bodies/m3-polish.json" \
    >/tmp/rs-stamp1.out 2>/tmp/rs-stamp1.err; then
  echo "OK: first stamp-body-digest creates sidecar"
else
  echo "FAIL: first stamp-body-digest should succeed" >&2
  cat /tmp/rs-stamp1.out /tmp/rs-stamp1.err >&2
  rc=1
fi
d1="$(python3 -c "import hashlib,pathlib; p=pathlib.Path('${rs_tmp}/evidence/bodies/m3-polish.json'); print(hashlib.sha256(p.read_bytes()).hexdigest())")"
if python3 "${SKILLS}/harness/record-run-evidence/scripts/stamp-body-digest.py" \
    "${rs_tmp}/evidence/bodies/m3-polish.json" \
    >/tmp/rs-stamp2.out 2>/tmp/rs-stamp2.err; then
  echo "FAIL: second stamp-body-digest without --allow-sidecar-only should refuse" >&2
  cat /tmp/rs-stamp2.out /tmp/rs-stamp2.err >&2
  rc=1
else
  if grep -q 'sidecar already exists' /tmp/rs-stamp2.err; then
    echo "OK: stamp-body-digest refuses sidecar-only restamp"
  else
    echo "FAIL: expected sidecar-already-exists refuse" >&2
    cat /tmp/rs-stamp2.out /tmp/rs-stamp2.err >&2
    rc=1
  fi
fi
python3 - "${rs_tmp}" "${d1}" <<'PY'
import json, sqlite3, sys
from pathlib import Path
root, d1 = Path(sys.argv[1]), sys.argv[2]
db = root / ".hermes/home/kanban.db"
conn = sqlite3.connect(str(db))
conn.execute("create table tasks (id text primary key, body text)")
card = (
    "Typed body: evidence/bodies/m3-polish.json\n"
    f"AR-4.3 digest: {d1}\n"
    f"Verify: python3 x --expect {d1} --body evidence/bodies/m3-polish.json .\n"
)
conn.execute("insert into tasks (id, body) values (?, ?)", ("t_aabbccdd", card))
conn.commit()
conn.close()
body = root / "evidence/bodies/m3-polish.json"
body.write_text(json.dumps({"phase": "M3", "identity": {"story_id": "polish"}, "task_id": "t_aabbccdd", "repaired": True}) + "\n")
PY
if python3 "${SKILLS}/harness/record-run-evidence/scripts/restamp-card-and-sidecar.py" \
    --root "${rs_tmp}" --body evidence/bodies/m3-polish.json --task-id t_aabbccdd \
    --kanban-db "${rs_tmp}/.hermes/home/kanban.db" \
    >/tmp/rs-atom.out 2>/tmp/rs-atom.err; then
  d2="$(python3 -c "import hashlib,pathlib; p=pathlib.Path('${rs_tmp}/evidence/bodies/m3-polish.json'); print(hashlib.sha256(p.read_bytes()).hexdigest())")"
  if python3 "${SKILLS}/harness/record-run-evidence/scripts/assert-card-body-digest-match.py" \
      "${rs_tmp}" --task-id t_aabbccdd --body evidence/bodies/m3-polish.json \
      >/tmp/rs-assert.out 2>/tmp/rs-assert.err; then
    echo "OK: restamp-card-and-sidecar updates card and sidecar together"
  else
    echo "FAIL: card↔sidecar assert after restamp" >&2
    cat /tmp/rs-atom.out /tmp/rs-atom.err /tmp/rs-assert.out /tmp/rs-assert.err >&2
    rc=1
  fi
else
  echo "FAIL: restamp-card-and-sidecar.py should exit 0" >&2
  cat /tmp/rs-atom.out /tmp/rs-atom.err >&2
  rc=1
fi
rm -rf "${rs_tmp}"

# V35-DIGEST nested task.body + sidecar↔file triple
python3 - "${SKILLS}/harness/record-run-evidence/scripts" <<'PY' || rc=1
import importlib.util
import sys
from pathlib import Path
scripts = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("restamp", scripts / "restamp-card-and-sidecar.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
md = "AR-4.3 digest: " + ("a" * 64)
got = mod.card_markdown_from_show({"task": {"body": md}})
if got != md:
    print(f"FAIL: nested task.body extract {got!r}", file=sys.stderr)
    raise SystemExit(1)
print("OK: restamp parses nested task.body")
PY

# V35-SERIAL identity.parents resolve + parked extra parent
ser_tmp="$(mktemp -d)"
mkdir -p "${ser_tmp}/evidence/bodies" "${ser_tmp}/evidence/derived" "${ser_tmp}/.hermes/home"
printf '%s\n' '{"identity":{"story_id":"US1","parents":["foundational"]}}' \
  > "${ser_tmp}/evidence/bodies/m3-US1.json"
printf '%s\n' '{"cards":[{"id":"t_found","story_id":"foundational"}]}' \
  > "${ser_tmp}/evidence/derived/created-story-cards.json"
if ids="$(python3 "${SKILLS}/harness/dispatch-phase/scripts/resolve-story-parent-ids.py" \
    --root "${ser_tmp}" --body evidence/bodies/m3-US1.json)" \
   && [ "${ids}" = "t_found" ]; then
  echo "OK: resolve-story-parent-ids identity.parents"
else
  echo "FAIL: resolve-story-parent-ids want t_found got ${ids-}" >&2
  rc=1
fi
python3 - <<PY
import sqlite3
from pathlib import Path
db = Path("${ser_tmp}/.hermes/home/kanban.db")
con = sqlite3.connect(str(db))
con.execute("create table tasks (id text, status text)")
con.execute("create table task_links (parent_id text, child_id text)")
con.execute("insert into tasks values ('t_us1','todo')")
con.execute("insert into task_links values ('t_holder','t_us1')")
con.execute("insert into task_links values ('t_gate','t_us1')")
con.execute("insert into task_links values ('t_found','t_us1')")
con.commit()
PY
if python3 "${SKILLS}/harness/dispatch-phase/scripts/assert-story-parked.py" \
    "${ser_tmp}" --task-id t_us1 --ack-gate t_gate --expect-parent t_found \
    | grep -q 'OK: parked t_us1'; then
  echo "OK: assert-story-parked identity parent"
else
  echo "FAIL: assert-story-parked should require identity parent" >&2
  rc=1
fi
if python3 "${SKILLS}/harness/dispatch-phase/scripts/assert-story-parked.py" \
    "${ser_tmp}" --task-id t_us1 --ack-gate t_gate --expect-max-runtime 2700 \
    >/tmp/parked-rt.out 2>/tmp/parked-rt.err; then
  echo "FAIL: parked should refuse missing max_runtime_seconds column" >&2
  rc=1
elif grep -q max_runtime_seconds /tmp/parked-rt.err /tmp/parked-rt.out; then
  echo "OK: assert-story-parked refuses missing max_runtime_seconds when flagged"
else
  echo "FAIL: expected missing max_runtime_seconds refuse" >&2
  cat /tmp/parked-rt.out /tmp/parked-rt.err >&2
  rc=1
fi
rm -rf "${ser_tmp}"

# V35-GEN-POST dest-only (legacy pom must not green dest) — case of V35-EXTENSIONS
gp_tmp="$(mktemp -d)"
mkdir -p "${gp_tmp}/src/main/resources" "${gp_tmp}/legacy"
printf '%s\n' '{"identity":{"story_id":"setup"},"files_writable":["pom.xml","src/main/resources/api-docs.yml"]}' \
  > "${gp_tmp}/body.json"
printf '%s\n' '<project></project>' > "${gp_tmp}/pom.xml"
printf '%s\n' 'openapi: 3.0.0' > "${gp_tmp}/src/main/resources/api-docs.yml"
printf '%s\n' '<project><plugin><artifactId>openapi-generator-maven-plugin</artifactId><inputSpec>src/main/resources/api-docs.yml</inputSpec></plugin></project>' \
  > "${gp_tmp}/legacy/pom.xml"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-dest-generator-configured.py" \
    "${gp_tmp}" --body "${gp_tmp}/body.json" >/tmp/gp.out 2>/tmp/gp.err; then
  echo "FAIL: dest pom without plugin should DEST_GENERATOR" >&2
  cat /tmp/gp.out /tmp/gp.err >&2
  rc=1
elif grep -q DEST_GENERATOR /tmp/gp.err && grep -q useJakartaEe /tmp/gp.err && grep -q '<library>native</library>' /tmp/gp.err; then
  echo "OK: GEN-POST dest pom without plugin refused (legacy ignored)"
  echo "OK: DEST_GENERATOR refusal emits required plugin configuration"
else
  echo "FAIL: expected DEST_GENERATOR with required plugin configuration" >&2
  cat /tmp/gp.out /tmp/gp.err >&2
  rc=1
fi
printf '%s\n' '<project><build><plugins><plugin><artifactId>openapi-generator-maven-plugin</artifactId><inputSpec>src/main/resources/api-docs.yml</inputSpec><library>native</library><configOptions><useJakartaEe>true</useJakartaEe></configOptions></plugin></plugins></build></project>' \
  > "${gp_tmp}/pom.xml"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-dest-generator-configured.py" \
    "${gp_tmp}" --body "${gp_tmp}/body.json" | grep -q 'OK: dest-generator'; then
  echo "OK: GEN-POST dest plugin + matching inputSpec"
else
  echo "FAIL: dest pom with plugin should pass" >&2
  rc=1
fi
rm -rf "${gp_tmp}"

# V35-EXTENSIONS dest pom must declare M1 required set (0 Java is irrelevant)
ex_tmp="$(mktemp -d)"
mkdir -p "${ex_tmp}/evidence"
printf '%s\n' '{"identity":{"story_id":"setup","extensions_apply":["quarkus-rest","quarkus-rest-jackson"]},"files_writable":["pom.xml"]}' \
  > "${ex_tmp}/body.json"
printf '%s\n' '{"schema":"rhoai3.required-extensions/v2","entries":[{"artifactId":"quarkus-hibernate-orm","kind":"extension"},{"artifactId":"quarkus-hibernate-validator","kind":"extension"},{"artifactId":"openapi-generator-maven-plugin","kind":"plugin"}]}' \
  > "${ex_tmp}/evidence/required-extensions.json"
printf '%s\n' '<project><dependencies><dependency><artifactId>quarkus-rest</artifactId></dependency><dependency><artifactId>quarkus-rest-jackson</artifactId></dependency></dependencies></project>' \
  > "${ex_tmp}/pom.xml"
printf '%s\n' '<project><plugin><artifactId>openapi-generator-maven-plugin</artifactId></plugin></project>' \
  > "${ex_tmp}/legacy-pom.xml"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-dest-pom-extensions.py" \
    "${ex_tmp}" --body "${ex_tmp}/body.json" >/tmp/ex.out 2>/tmp/ex.err; then
  echo "FAIL: REST-only dest pom should DEST_EXTENSIONS (hibernate missing)" >&2
  cat /tmp/ex.out /tmp/ex.err >&2
  rc=1
elif grep -q DEST_EXTENSIONS /tmp/ex.err; then
  echo "OK: EXTENSIONS dest REST-only pom refused (legacy plugin ignored)"
else
  echo "FAIL: expected DEST_EXTENSIONS" >&2
  cat /tmp/ex.out /tmp/ex.err >&2
  rc=1
fi
printf '%s\n' '<project><dependencies><dependency><artifactId>quarkus-rest</artifactId></dependency><dependency><artifactId>quarkus-rest-jackson</artifactId></dependency><dependency><artifactId>quarkus-hibernate-orm</artifactId></dependency><dependency><artifactId>quarkus-hibernate-validator</artifactId></dependency></dependencies><build><plugins><plugin><artifactId>openapi-generator-maven-plugin</artifactId><inputSpec>src/main/resources/api-docs.yml</inputSpec><library>native</library><configOptions><useJakartaEe>true</useJakartaEe></configOptions></plugin></plugins></build></project>' \
  > "${ex_tmp}/pom.xml"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-dest-pom-extensions.py" \
    "${ex_tmp}" --body "${ex_tmp}/body.json" | grep -q 'OK: dest pom declares'; then
  echo "OK: EXTENSIONS dest pom with hibernate-orm + validator + generator"
else
  echo "FAIL: dest pom with required extensions should pass" >&2
  rc=1
fi
# emit: quoted spring-data-jpa → native hibernate-orm, never quarkus-spring-*
mkdir -p "${ex_tmp}/evidence"
printf '%s\n' '{"schema":"rhoai3.findings-handoff/v1","rules":[{"rule_id":"springboot-jpa-to-quarkus-00000","disposition":"apply","description":"Replace the SpringBoot Data JPA artifact with Quarkus '\''spring-data-jpa'\'' extension"},{"rule_id":"springboot-di-to-quarkus-00000","disposition":"apply","description":"Replace Spring DI with Quarkus '\''spring-di'\'' extension"}],"totals":{"violations":2}}' \
  > "${ex_tmp}/evidence/findings-handoff.json"
printf '%s\n' '<project><dependency><artifactId>spring-boot-starter-validation</artifactId></dependency></project>' \
  > "${ex_tmp}/legacy.xml"
if python3 "${SKILLS}/analysis/scan-with-mta/scripts/emit-required-extensions.py" \
    "${ex_tmp}" --handoff "${ex_tmp}/evidence/findings-handoff.json" \
    --legacy-pom "${ex_tmp}/legacy.xml" --out "${ex_tmp}/evidence/required-extensions.json" \
    | grep -q 'OK: required-extensions'; then
  if grep -q quarkus-hibernate-orm "${ex_tmp}/evidence/required-extensions.json" \
     && grep -q quarkus-hibernate-validator "${ex_tmp}/evidence/required-extensions.json" \
     && ! grep -q quarkus-spring- "${ex_tmp}/evidence/required-extensions.json"; then
    echo "OK: M1 emit rewrites spring-data-jpa to hibernate-orm (T-3)"
  else
    echo "FAIL: emit should native-rewrite JPA and not emit quarkus-spring-*" >&2
    cat "${ex_tmp}/evidence/required-extensions.json" >&2
    rc=1
  fi
else
  echo "FAIL: emit-required-extensions should succeed" >&2
  rc=1
fi
rm -rf "${ex_tmp}"

# v37 overlay wave: one-source JDBC, kind, setup driver, topo, maven -s
if python3 "${SKILLS}/migration/manage-quarkus-extensions/scripts/spring_dep_map.py" --check \
    | grep -q 'OK: spring-dep-to-extension.md'; then
  echo "OK: spring_dep_map.py --check"
else
  echo "FAIL: spring_dep_map.py --check" >&2
  rc=1
fi
echo "== F-4 jdbc keys follow spring.profiles.active =="
python3 - "${SKILLS}/migration/manage-quarkus-extensions/scripts" <<'PY' || rc=1
import sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from spring_dep_map import scan_legacy_jdbc_keys
root = Path(tempfile.mkdtemp(prefix="jdbc-profile-"))
(root / "src" / "main" / "resources").mkdir(parents=True)
(root / "src" / "main" / "resources" / "application.properties").write_text(
    "spring.profiles.active=hsqldb,spring-data-jpa\n", encoding="utf-8"
)
(root / "src" / "main" / "resources" / "application-hsqldb.properties").write_text(
    "spring.datasource.url=jdbc:hsqldb:mem:testdb\n", encoding="utf-8"
)
(root / "src" / "main" / "resources" / "application-mysql.properties").write_text(
    "spring.datasource.url=jdbc:mysql://localhost/testdb\n", encoding="utf-8"
)
got = scan_legacy_jdbc_keys(root)
if got != ["jdbc:hsqldb"]:
    print(f"FAIL: F-4 jdbc keys {got} want ['jdbc:hsqldb']", file=sys.stderr)
    raise SystemExit(1)
print("OK: F-4 scan_legacy_jdbc_keys follows spring.profiles.active (not mysql rglob)")
PY

jdbc_tmp="$(mktemp -d)"
mkdir -p "${jdbc_tmp}/evidence" "${jdbc_tmp}/legacy"
printf '%s\n' '{"schema":"rhoai3.findings-handoff/v1","rules":[{"rule_id":"persistence-to-quarkus-00010","disposition":"apply","description":"Replace Spring persistence with Quarkus"}],"totals":{"violations":1}}' \
  > "${jdbc_tmp}/evidence/findings-handoff.json"
printf '%s\n' '<project><dependency><artifactId>spring-boot-starter-jdbc</artifactId></dependency></project>' \
  > "${jdbc_tmp}/legacy/pom.xml"
printf '%s\n' 'spring.datasource.url=jdbc:hsqldb:mem:testdb' \
  > "${jdbc_tmp}/legacy/application.properties"
if python3 "${SKILLS}/analysis/scan-with-mta/scripts/emit-required-extensions.py" \
    "${jdbc_tmp}" --handoff "${jdbc_tmp}/evidence/findings-handoff.json" \
    --legacy-pom "${jdbc_tmp}/legacy/pom.xml" --out "${jdbc_tmp}/evidence/required-extensions.json" \
    | grep -q 'OK: required-extensions'; then
  if grep -q quarkus-jdbc-h2 "${jdbc_tmp}/evidence/required-extensions.json" \
     && grep -q '"kind": "extension"' "${jdbc_tmp}/evidence/required-extensions.json" \
     && ! grep -q quarkus-jdbc-hsqldb "${jdbc_tmp}/evidence/required-extensions.json" \
     && ! grep -q '"extensions"' "${jdbc_tmp}/evidence/required-extensions.json"; then
    echo "OK: M1 emit expands jdbc:hsqldb to quarkus-jdbc-h2 via md table"
  else
    echo "FAIL: emit should map jdbc:hsqldb through the table to quarkus-jdbc-h2" >&2
    cat "${jdbc_tmp}/evidence/required-extensions.json" >&2
    rc=1
  fi
else
  echo "FAIL: emit with legacy jdbc:hsqldb URL should succeed" >&2
  rc=1
fi
rm -f "${jdbc_tmp}/legacy/application.properties"
if python3 "${SKILLS}/analysis/scan-with-mta/scripts/emit-required-extensions.py" \
    "${jdbc_tmp}" --handoff "${jdbc_tmp}/evidence/findings-handoff.json" \
    --legacy-pom "${jdbc_tmp}/legacy/pom.xml" --out "${jdbc_tmp}/evidence/required-extensions.json" \
    >/tmp/jdbc-miss.out 2>/tmp/jdbc-miss.err; then
  echo "FAIL: emit without legacy jdbc URL should JDBC_KIND" >&2
  rc=1
elif grep -q JDBC_KIND /tmp/jdbc-miss.err; then
  echo "OK: emit REFUSE JDBC_KIND when legacy URL missing (no dest db-kind fallback)"
else
  echo "FAIL: expected JDBC_KIND" >&2
  cat /tmp/jdbc-miss.out /tmp/jdbc-miss.err >&2
  rc=1
fi
rm -rf "${jdbc_tmp}"

plug_tmp="$(mktemp -d)"
mkdir -p "${plug_tmp}/evidence"
printf '%s\n' '{"identity":{"story_id":"setup","extensions_apply":[]},"files_writable":["pom.xml"]}' \
  > "${plug_tmp}/body.json"
printf '%s\n' '{"schema":"rhoai3.required-extensions/v2","entries":[{"artifactId":"openapi-generator-maven-plugin","kind":"plugin"}]}' \
  > "${plug_tmp}/evidence/required-extensions.json"
printf '%s\n' '<project><dependencies><dependency><artifactId>openapi-generator-maven-plugin</artifactId></dependency></dependencies></project>' \
  > "${plug_tmp}/pom.xml"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-dest-pom-extensions.py" \
    "${plug_tmp}" --body "${plug_tmp}/body.json" >/tmp/plug.out 2>/tmp/plug.err; then
  echo "FAIL: plugin as <dependency> should DEST_EXTENSIONS" >&2
  rc=1
elif grep -q DEST_EXTENSIONS /tmp/plug.err; then
  echo "OK: EXTENSIONS refuses plugin listed as a dependency"
else
  echo "FAIL: expected DEST_EXTENSIONS for plugin-as-dependency" >&2
  cat /tmp/plug.out /tmp/plug.err >&2
  rc=1
fi
rm -rf "${plug_tmp}"

sj_tmp="$(mktemp -d)"
mkdir -p "${sj_tmp}/src/main/resources"
printf '%s\n' 'quarkus.datasource.db-kind=h2' > "${sj_tmp}/src/main/resources/application.properties"
printf '%s\n' '<project><dependencies><dependency><artifactId>quarkus-rest</artifactId></dependency></dependencies></project>' \
  > "${sj_tmp}/pom.xml"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-setup-datasource-driver.py" \
    "${sj_tmp}" >/tmp/sj.out 2>/tmp/sj.err; then
  echo "FAIL: dest db-kind=h2 without jdbc driver should SETUP_JDBC" >&2
  rc=1
elif grep -q SETUP_JDBC /tmp/sj.err; then
  echo "OK: SETUP_JDBC refuses dest datasource without matching driver"
else
  echo "FAIL: expected SETUP_JDBC" >&2
  cat /tmp/sj.out /tmp/sj.err >&2
  rc=1
fi
printf '%s\n' '<project><dependencies><dependency><artifactId>quarkus-jdbc-h2</artifactId></dependency></dependencies></project>' \
  > "${sj_tmp}/pom.xml"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-setup-datasource-driver.py" \
    "${sj_tmp}" | grep -q 'OK: SETUP_JDBC'; then
  echo "OK: SETUP_JDBC dest pom has matching jdbc driver"
else
  echo "FAIL: dest pom with quarkus-jdbc-h2 should pass SETUP_JDBC" >&2
  rc=1
fi
rm -rf "${sj_tmp}"

mvn_tmp="$(mktemp -d)"
mkdir -p "${mvn_tmp}/.mvn"
printf '%s\n' '<settings><profile><id>red-hat-enterprise-maven-repository</id></profile></settings>' \
  > "${mvn_tmp}/.mvn/settings.xml"
printf '%s\n' '# no -s' > "${mvn_tmp}/.mvn/maven.config"
if python3 "${SKILLS}/migration/reference-rh-quarkus-pom/scripts/verify-maven-settings.py" \
    "${mvn_tmp}" --files-only >/tmp/mvnset.out 2>/tmp/mvnset.err; then
  echo "FAIL: maven.config without -s should MAVEN_REPOS" >&2
  rc=1
elif grep -q MAVEN_REPOS /tmp/mvnset.err; then
  echo "OK: MAVEN_REPOS refuses .mvn/settings.xml without maven.config -s"
else
  echo "FAIL: expected MAVEN_REPOS" >&2
  cat /tmp/mvnset.out /tmp/mvnset.err >&2
  rc=1
fi
printf '%s\n' '-s' '.mvn/settings.xml' > "${mvn_tmp}/.mvn/maven.config"
if python3 "${SKILLS}/migration/reference-rh-quarkus-pom/scripts/verify-maven-settings.py" \
    "${mvn_tmp}" --files-only | grep -q 'OK: MAVEN_REPOS'; then
  echo "OK: MAVEN_REPOS .mvn/maven.config -s + settings.xml"
else
  echo "FAIL: maven.config -s should pass files-only" >&2
  rc=1
fi
rm -rf "${mvn_tmp}"

topo_fix="${SKILLS}/sdd/check-spec-readiness/fixtures/partition-topo-v36-cyclic"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-partition-topological-order.py" \
    "${topo_fix}" >/tmp/topo.out 2>/tmp/topo.err; then
  echo "FAIL: v36 cyclic fixture must TOPOLOGICAL_ORDER" >&2
  rc=1
elif grep -q TOPOLOGICAL_ORDER /tmp/topo.err; then
  echo "OK: TOPOLOGICAL_ORDER refuses v36 cyclic foundational facade (143e7357)"
else
  echo "FAIL: expected TOPOLOGICAL_ORDER" >&2
  cat /tmp/topo.out /tmp/topo.err >&2
  rc=1
fi
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-partition-topological-order.py" \
    "${topo_fix}" --report-only | grep -q 'OK: topological report'; then
  echo "OK: topological report-only sweep of reconstructed 11 v36 cards"
else
  echo "FAIL: --report-only should print topological report" >&2
  rc=1
fi
topo_tmp="$(mktemp -d)"
cp -R "${topo_fix}/." "${topo_tmp}/"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/relocate-descendant-import-writesets.py" \
    "${topo_tmp}" --write | grep -q FACADE_RELOCATE; then
  if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-partition-topological-order.py" \
      "${topo_tmp}" | grep -q 'OK: partition topological order'; then
    echo "OK: relocate moves facade onto polish; topology then passes"
  else
    echo "FAIL: topology should pass after relocate" >&2
    rc=1
  fi
  if python3 - "${topo_tmp}" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
owners = {}
dup = []
for p in sorted((root / "evidence" / "bodies").glob("m3-*.json")):
    if p.name.endswith(".sha256.json"):
        continue
    doc = json.loads(p.read_text(encoding="utf-8"))
    body = doc.get("body") if isinstance(doc.get("body"), dict) else doc
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    sid = str(ident.get("story_id") or "")
    for rel in body.get("files_writable") or []:
        if not isinstance(rel, str) or not rel:
            continue
        if rel in owners and owners[rel] != sid:
            dup.append(f"{rel}:{owners[rel]}+{sid}")
        else:
            owners[rel] = sid
if dup:
    print("FAIL: " + " ".join(dup), file=sys.stderr)
    raise SystemExit(1)
print("OK")
PY
  then
    echo "OK: relocate unique-owns dest paths after facade move"
  else
    echo "FAIL: same dest path still on two bodies after relocate" >&2
    rc=1
  fi
else
  echo "FAIL: relocate should move the facade onto polish" >&2
  rc=1
fi
rm -rf "${topo_tmp}"

legacy_topo="$(mktemp -d)"
mkdir -p "${legacy_topo}/evidence/briefs" "${legacy_topo}/evidence/bodies" \
  "${legacy_topo}/evidence/derived/legacy-at-3/src/main/java/com/demo/service" \
  "${legacy_topo}/evidence/derived/legacy-at-3/src/main/java/com/demo/entity"
cp "${topo_fix}/evidence/briefs/partition.json" "${legacy_topo}/evidence/briefs/"
cp "${topo_fix}/evidence/bodies/"*.json "${legacy_topo}/evidence/bodies/"
cp "${topo_fix}/src/main/java/com/demo/service/"*.java \
  "${legacy_topo}/evidence/derived/legacy-at-3/src/main/java/com/demo/service/"
cp "${topo_fix}/src/main/java/com/demo/entity/"*.java \
  "${legacy_topo}/evidence/derived/legacy-at-3/src/main/java/com/demo/entity/"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/relocate-descendant-import-writesets.py" \
    "${legacy_topo}" --write | grep -q 'foundational->polish'; then
  echo "OK: relocate parses legacy twins when dest Java is absent"
else
  echo "FAIL: relocate should use legacy twins at mint (dest Java absent)" >&2
  rc=1
fi
rm -rf "${legacy_topo}"

mo_tmp="$(mktemp -d)"
mkdir -p "${mo_tmp}/evidence/briefs" "${mo_tmp}/evidence/bodies"
printf '%s\n' '{"stories":[{"story_id":"US1","kind":"us","files_writable":["src/main/java/x/Shared.java"]},{"story_id":"US2","kind":"us","files_writable":["src/main/java/x/Shared.java"]},{"story_id":"polish","kind":"polish","files_writable":[]}]}' > "${mo_tmp}/evidence/briefs/partition.json"
printf '%s\n' '{"identity":{"story_id":"US1","kind":"us"},"files_writable":["src/main/java/x/Shared.java"]}' > "${mo_tmp}/evidence/bodies/m3-US1.json"
printf '%s\n' '{"identity":{"story_id":"US2","kind":"us"},"files_writable":["src/main/java/x/Shared.java"]}' > "${mo_tmp}/evidence/bodies/m3-US2.json"
printf '%s\n' '{"identity":{"story_id":"polish","kind":"polish"},"files_writable":[]}' > "${mo_tmp}/evidence/bodies/m3-polish.json"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/relocate-descendant-import-writesets.py" \
    "${mo_tmp}" --write >/tmp/mo.out 2>/tmp/mo.err; then
  echo "FAIL: two bodies claiming one dest Java should MULTI_OWNER" >&2
  rc=1
elif grep -q 'MULTI_OWNER' /tmp/mo.err; then
  echo "OK: MULTI_OWNER refuses leftover dest-path claimants"
  python3 - "${SKILLS}/harness/dispatch-phase/scripts/scratch-assemble-mint.py" "${mo_tmp}" <<'PY' || rc=1
import importlib.util
import sys
from pathlib import Path
script, root = Path(sys.argv[1]), Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("scratch_assemble_mint", script)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
if mod._run_relocate(root) != 1:
    print("FAIL: scratch-assemble _run_relocate must fail MULTI_OWNER", file=sys.stderr)
    raise SystemExit(1)
print("OK: scratch-assemble _run_relocate fails MULTI_OWNER")
PY
else
  echo "FAIL: expected MULTI_OWNER" >&2
  cat /tmp/mo.out /tmp/mo.err >&2
  rc=1
fi
rm -rf "${mo_tmp}"


# V35-M2-UPTAKE
up_tmp="$(mktemp -d)"
mkdir -p "${up_tmp}/evidence"
printf '%s\n' '{"types":[{"generated":true,"name":"OwnerDto"}]}' > "${up_tmp}/evidence/type-inventory.json"
printf '%s\n' '# no generator' > "${up_tmp}/tasks.md"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-tasks-generator-uptake.py" \
    "${up_tmp}" --tasks "${up_tmp}/tasks.md" >/tmp/up.out 2>/tmp/up.err; then
  echo "FAIL: generated types without plugin token should M2_UPTAKE" >&2
  rc=1
elif grep -q M2_UPTAKE /tmp/up.err; then
  echo "OK: M2-UPTAKE refuses tasks.md without plugin token"
else
  echo "FAIL: expected M2_UPTAKE" >&2
  cat /tmp/up.out /tmp/up.err >&2
  rc=1
fi
printf '%s\n' 'configure openapi-generator-maven-plugin' > "${up_tmp}/tasks.md"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/assert-tasks-generator-uptake.py" \
    "${up_tmp}" --tasks "${up_tmp}/tasks.md" | grep -q 'OK: M2-UPTAKE'; then
  echo "OK: M2-UPTAKE plugin token present"
else
  echo "FAIL: tasks.md with plugin token should pass" >&2
  rc=1
fi
rm -rf "${up_tmp}"

python3 - <<PY
import json
from pathlib import Path
root = Path("${dep_tmp}/modernized")
body = {
  "identity": {"story_id": "leaf-only", "operand_count": 1},
  "files_in_scope": ["src/main/java/com/demo/model/Leaf.java"],
  "files_writable": ["src/main/java/com/demo/model/Leaf.java"],
}
# Force a dest-path repo hole: Leaf imports a repository with no owner.
(root / "evidence/bodies/m3-leaf.json").write_text(json.dumps(body) + "\n")
src = Path("${dep_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/model/Leaf.java")
src.write_text(
    "package com.acme.legacy.model;\n"
    "import com.acme.legacy.repository.GhostRepository;\n"
    "public class Leaf extends Mid { GhostRepository repo; }\n"
)
# Isolate from the closure body's write-set so GhostRepository stays unowned.
for p in (root / "evidence/bodies").glob("m3-foundational.json"):
    p.unlink()
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py" \
    "${dep_tmp}/modernized" --body evidence/bodies/m3-leaf.json --write \
    >/tmp/dep-hole.out 2>/tmp/dep-hole.err; then
  if python3 - "${dep_tmp}" <<'PY'
import json, sys
from pathlib import Path
b = json.loads((Path(sys.argv[1]) / "modernized/evidence/bodies/m3-leaf.json").read_text())
fw = set(b.get("files_writable") or [])
want = "src/main/java/com/demo/repository/GhostRepository.java"
pre = [
    d for d in (b.get("dependencies") or [])
    if isinstance(d, dict) and d.get("provider") == "pre-exists"
]
raise SystemExit(0 if want in fw and not pre else 1)
PY
  then
    echo "OK: stamp assigns unowned dest repository onto the importing story"
  else
    echo "FAIL: expected GhostRepository on leaf files_writable, not pre-exists" >&2
    cat /tmp/dep-hole.out /tmp/dep-hole.err >&2
    cat "${dep_tmp}/modernized/evidence/bodies/m3-leaf.json" >&2
    rc=1
  fi
else
  echo "FAIL: existing GhostRepository dest twin should assign, not hole" >&2
  cat /tmp/dep-hole.out /tmp/dep-hole.err >&2
  rc=1
fi
# True orphan: import a type with no legacy file — DEPENDENCY_HOLE, not pre-exists.
python3 - <<PY
from pathlib import Path
src = Path("${dep_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/model/Leaf.java")
src.write_text(
    "package com.acme.legacy.model;\n"
    "import com.acme.legacy.repository.AbsentRepository;\n"
    "public class Leaf extends Mid { AbsentRepository repo; }\n"
)
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py" \
    "${dep_tmp}/modernized" --body evidence/bodies/m3-leaf.json \
    >/tmp/dep-orphan.out 2>/tmp/dep-orphan.err; then
  echo "FAIL: missing dest twin should DEPENDENCY_HOLE" >&2
  cat /tmp/dep-orphan.out /tmp/dep-orphan.err >&2
  rc=1
else
  if grep -q 'DEPENDENCY_HOLE' /tmp/dep-orphan.err \
     && grep -q 'AbsentRepository.java' /tmp/dep-orphan.err; then
    echo "OK: DEPENDENCY_HOLE lists dest path for true orphan import"
  else
    echo "FAIL: expected dest AbsentRepository.java in DEPENDENCY_HOLE" >&2
    cat /tmp/dep-orphan.out /tmp/dep-orphan.err >&2
    rc=1
  fi
fi
rm -rf "${dep_tmp}"

# Architect E-20260817T164700Z — HTTP stamp sources = inventory files, not dest Resource
http_tmp="$(mktemp -d)"
mkdir -p "${http_tmp}/modernized/evidence/bodies" \
  "${http_tmp}/modernized/evidence/briefs" \
  "${http_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/rest" \
  "${http_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/model"
cat > "${http_tmp}/modernized/migration.yaml" <<'YAML'
migration:
  legacyBasePackage: com.acme.legacy
  targetPackage: com.demo
  path_rewrites:
    - from: src/main/java/com/demo/
      to: src/main/java/com/acme/legacy/
YAML
printf '%s\n' 'package com.acme.legacy.model;' 'public class Pet { }' \
  > "${http_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/model/Pet.java"
cat > "${http_tmp}/.derived/legacy-at-3/src/main/java/com/acme/legacy/rest/PetRestController.java" <<'JAVA'
package com.acme.legacy.rest;
import com.acme.legacy.model.Pet;
public class PetRestController { Pet p; }
JAVA
printf '%s\n' '{"source":"handover-mint","stories":[{"story_id":"US1","kind":"user_story","endpoints":["GET /api/pets"],"operand_class":["rest"]}]}' \
  > "${http_tmp}/modernized/evidence/briefs/partition.json"
printf '%s\n' '{"entry_points":[{"kind":"http","file":"src/main/java/com/acme/legacy/rest/PetRestController.java","symbol":"PetRestController#list","http_method":"GET","http_path":"/api/pets"}]}' \
  > "${http_tmp}/modernized/evidence/entry-point-inventory.json"
python3 - "${http_tmp}" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1]) / "modernized"
(root / "evidence/bodies/m3-foundational.json").write_text(json.dumps({
  "identity": {"story_id": "foundational"},
  "files_writable": ["src/main/java/com/demo/model/Pet.java"],
}) + "\n")
body = {
  "identity": {"story_id": "US1", "operand_class": ["rest"], "operand_count": 1},
  "files_in_scope": ["src/main/java/com/demo/resource/PetResource.java"],
  "files_writable": ["src/main/java/com/demo/resource/PetResource.java"],
  "refs": [{"key": "legacy_locus", "path": "evidence/derived/legacy-at-3.json", "sha256": "pending"}],
}
(root / "evidence/bodies/m3-US1.json").write_text(json.dumps(body) + "\n")
(root / "evidence/derived").mkdir(parents=True, exist_ok=True)
(root / "evidence/derived/legacy-at-3.json").write_text("{}\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py" \
    "${http_tmp}/modernized" --body evidence/bodies/m3-US1.json \
    >/tmp/dep-http.out 2>/tmp/dep-http.err; then
  if grep -q 'PetRestController.java' /tmp/dep-http.out \
     && grep -q 'src/main/java/com/demo/model/Pet.java' /tmp/dep-http.out \
     && ! grep -q 'PetResource.java' /tmp/dep-http.out; then
    echo "OK: HTTP stamp sources are inventory RestController files, not dest Resource"
  else
    echo "FAIL: expected inventory PetRestController parse root and dest Pet.java dep" >&2
    cat /tmp/dep-http.out /tmp/dep-http.err >&2
    rc=1
  fi
else
  echo "FAIL: HTTP inventory stamp sources should not be VACUOUS" >&2
  cat /tmp/dep-http.out /tmp/dep-http.err >&2
  rc=1
fi
rm -rf "${http_tmp}"

# Architect E-20260817T170100Z — dest-only polish create is not VACUOUS
dest_tmp="$(mktemp -d)"
mkdir -p "${dest_tmp}/modernized/evidence/bodies" \
  "${dest_tmp}/modernized/evidence/briefs" \
  "${dest_tmp}/modernized/evidence/derived"
cat > "${dest_tmp}/modernized/migration.yaml" <<'YAML'
migration:
  legacyBasePackage: com.acme.legacy
  targetPackage: com.demo
  path_rewrites:
    - from: src/main/java/com/demo/
      to: src/main/java/com/acme/legacy/
YAML
printf '%s\n' '{"source":"handover-mint","stories":[{"story_id":"polish","kind":"polish","endpoints":[],"operand_class":["src_code"]}]}' \
  > "${dest_tmp}/modernized/evidence/briefs/partition.json"
python3 - "${dest_tmp}" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1]) / "modernized"
body = {
  "identity": {"story_id": "polish", "kind": "polish", "operand_class": ["src_code"], "operand_count": 1},
  "files_writable": ["src/main/java/com/demo/config/HealthCheck.java"],
  "refs": [{"key": "legacy_locus", "path": "evidence/derived/legacy-at-3.json", "sha256": "pending"}],
}
(root / "evidence/bodies/m3-polish.json").write_text(json.dumps(body) + "\n")
(root / "evidence/derived/legacy-at-3.json").write_text("{}\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py" \
    "${dest_tmp}/modernized" --body evidence/bodies/m3-polish.json \
    >/tmp/dep-destonly.out 2>/tmp/dep-destonly.err; then
  if grep -q 'dest-only create' /tmp/dep-destonly.out /tmp/dep-destonly.err \
     && grep -q '"dependencies": \[\]' /tmp/dep-destonly.out; then
    echo "OK: dest-only polish HealthCheck stamps empty deps (not VACUOUS)"
  else
    echo "FAIL: expected dest-only empty-deps OK for polish HealthCheck" >&2
    cat /tmp/dep-destonly.out /tmp/dep-destonly.err >&2
    rc=1
  fi
else
  echo "FAIL: dest-only polish should not be VACUOUS" >&2
  cat /tmp/dep-destonly.out /tmp/dep-destonly.err >&2
  rc=1
fi
# HTTP + JSON locus + unresolved dest Resource must still VACUOUS
python3 - "${dest_tmp}" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1]) / "modernized"
(root / "evidence/briefs/partition.json").write_text(json.dumps({
  "source": "handover-mint",
  "stories": [{"story_id": "US1", "kind": "user_story", "endpoints": ["GET /api/pets"], "operand_class": ["rest"]}],
}) + "\n")
(root / "evidence/entry-point-inventory.json").write_text(json.dumps({"entry_points": []}) + "\n")
body = {
  "identity": {"story_id": "US1", "operand_class": ["rest"], "operand_count": 1},
  "files_writable": ["src/main/java/com/demo/resource/PetResource.java"],
  "refs": [{"key": "legacy_locus", "path": "evidence/derived/legacy-at-3.json", "sha256": "pending"}],
}
(root / "evidence/bodies/m3-US1.json").write_text(json.dumps(body) + "\n")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py" \
    "${dest_tmp}/modernized" --body evidence/bodies/m3-US1.json \
    >/tmp/dep-http-vac.out 2>/tmp/dep-http-vac.err; then
  echo "FAIL: HTTP unresolved dest Resource must still be VACUOUS" >&2
  cat /tmp/dep-http-vac.out /tmp/dep-http-vac.err >&2
  rc=1
else
  if grep -q 'DEPENDENCY_STAMP_VACUOUS' /tmp/dep-http-vac.err; then
    echo "OK: HTTP stories still refuse VACUOUS when dest Resource has no harvest"
  else
    echo "FAIL: expected DEPENDENCY_STAMP_VACUOUS for HTTP dest Resource" >&2
    cat /tmp/dep-http-vac.out /tmp/dep-http-vac.err >&2
    rc=1
  fi
fi
rm -rf "${dest_tmp}"

# WC-8: story.rules covers the fired id → VALID
printf '%s\n' '{"stories":[{"story_id":"story-001","files_in_scope":["src/Foo.java"],"endpoints":["foo"],"rules":["springboot-to-quarkus-00000"]}]}' \
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

# Architect E-20260817T152824Z — serial non-pom overlap is not FILE_OVERLAP
pc_tmp="$(mktemp -d)"
mkdir -p "${pc_tmp}/evidence/briefs" "${pc_tmp}/evidence"
printf '%s\n' '{"stories":[{"story_id":"setup","files_in_scope":["pom.xml","src/main/resources/application.properties"],"endpoints":[]},{"story_id":"US1","files_in_scope":["src/main/resources/application.properties","src/main/java/com/demo/resource/VetResource.java"],"endpoints":["GET /api/vets"],"rules":["springboot-to-quarkus-00000"]}]}' \
  > "${pc_tmp}/evidence/briefs/partition.json"
printf '%s\n' '{"entry_points":[{"kind":"http","file":"src/main/java/org/example/demo/rest/VetRestController.java","symbol":"VetRestController#getVets","http_method":"GET","http_path":"/api/vets"}],"totals":{"http_endpoints":1}}' \
  > "${pc_tmp}/inventory.json"
printf '%s\n' '{"schema":"rhoai3.mta-findings/v1-provisional","violations":{"springboot-to-quarkus-00000":{"ruleID":"springboot-to-quarkus-00000","category":"mandatory","incidents":[]}}}' \
  > "${pc_tmp}/evidence/mta-findings.json"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-partition-coverage.py" \
    "${pc_tmp}" --partition evidence/briefs/partition.json --inventory inventory.json \
    >/tmp/pc-serial.out 2>/tmp/pc-serial.err; then
  if grep -q 'file_overlap:src/main/resources/application.properties' /tmp/pc-serial.out /tmp/pc-serial.err; then
    echo "FAIL: serial application.properties overlap should not be file_overlap" >&2
    cat /tmp/pc-serial.out /tmp/pc-serial.err >&2
    rc=1
  elif grep -q 'VALID' /tmp/pc-serial.out; then
    echo "OK: PARTITION_COVERAGE serial non-pom overlap + A-8 route join VALID"
  else
    echo "FAIL: expected VALID for serial overlap + route join" >&2
    cat /tmp/pc-serial.out /tmp/pc-serial.err >&2
    rc=1
  fi
else
  echo "FAIL: serial non-pom overlap + A-8 route join should be VALID" >&2
  cat /tmp/pc-serial.out /tmp/pc-serial.err >&2
  rc=1
fi
# dest Resource filename must not cover inventory RestController without endpoints
printf '%s\n' '{"stories":[{"story_id":"US1","files_in_scope":["src/main/java/com/demo/resource/VetResource.java"],"endpoints":[],"rules":["springboot-to-quarkus-00000"]}]}' \
  > "${pc_tmp}/evidence/briefs/partition.json"
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-partition-coverage.py" \
    "${pc_tmp}" --partition evidence/briefs/partition.json --inventory inventory.json \
    >/tmp/pc-filejoin.out 2>/tmp/pc-filejoin.err; then
  echo "FAIL: dest Resource without endpoints should not cover inventory file" >&2
  cat /tmp/pc-filejoin.out /tmp/pc-filejoin.err >&2
  rc=1
else
  if grep -q 'endpoints_uncovered' /tmp/pc-filejoin.out /tmp/pc-filejoin.err; then
    echo "OK: PARTITION_COVERAGE does not join inventory.file to dest Resource"
  else
    echo "FAIL: expected endpoints_uncovered when only dest Resource is in write-set" >&2
    cat /tmp/pc-filejoin.out /tmp/pc-filejoin.err >&2
    rc=1
  fi
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
# test-only: http_semantics is foreign; test_suite_runs is legal
# (Architect E-20260819T155354Z — v33 holder A-8). Mixed rest+test keeps HTTP.
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "test", "story_id": "polish"},
  "files_writable": ["src/test/java/x/SuiteTest.java"],
  "exit_criteria": [{"check": "http_semantics", "cmd": "mvn -q test"}],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-surgical-scopes.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "FAIL: test+http_semantics should refuse" >&2
  rc=1
else
  echo "OK: T-8 test-only foreign http_semantics refused"
fi
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": "test", "story_id": "polish"},
  "files_writable": ["src/test/java/x/SuiteTest.java"],
  "exit_criteria": [{"check": "test_suite_runs", "cmd": "mvn -q test"}],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-surgical-scopes.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "OK: T-8 legal-only test test_suite_runs passed"
else
  echo "FAIL: legal-only test_suite_runs should pass" >&2
  rc=1
fi
python3 - <<PY
import json, pathlib
root = pathlib.Path("${t8_tmp}")
body = {
  "phase": "M3",
  "identity": {"operand_class": ["rest", "test", "user_story"], "story_id": "US1"},
  "files_writable": [
    "src/main/java/x/OwnerResource.java",
    "src/test/java/x/OwnerResourceTest.java",
  ],
  "exit_criteria": [{"check": "http_semantics", "cmd": "mvn -q test"}],
}
(root / "evidence/bodies/m3-dual-oracle.json").write_text(json.dumps(body), encoding="utf-8")
PY
if python3 "${SKILLS}/sdd/check-spec-readiness/scripts/check-surgical-scopes.py" "${t8_tmp}" \
  >/dev/null 2>&1; then
  echo "OK: T-8 rest+test keeps http_semantics"
else
  echo "FAIL: rest+test http_semantics should pass AR-4.4" >&2
  rc=1
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

echo "== task_scoped_tests: evaluator scopes mvn test via proves FQCNs =="
python3 - "${SKILLS}" <<'PY' || rc=1
import importlib.util
import sys
from pathlib import Path

skills = Path(sys.argv[1])
eval_py = skills / "gates/check-release-readiness/scripts/evaluate-exit-criteria.py"
spec = skills / "sdd/check-spec-readiness/scripts"
sys.path.insert(0, str(spec))
mod_spec = importlib.util.spec_from_file_location("eec", eval_py)
mod = importlib.util.module_from_spec(mod_spec)
assert mod_spec.loader is not None
mod_spec.loader.exec_module(mod)
from specimen_agnostic import proving_test_rels, proves_to_fqcn, semantic_exit_cmd_is_maven

helpers = {
    "proving_test_rels": proving_test_rels,
    "proves_to_fqcn": proves_to_fqcn,
    "semantic_exit_cmd_is_maven": semantic_exit_cmd_is_maven,
}
item = {"proves": ["src/test/java/com/demo/HealthTest.java"]}
cmd, err = mod.scoped_maven_test_cmd("mvn -q test", item, helpers)
assert err is None, err
assert "-Dtest=com.demo.HealthTest" in cmd, cmd
assert cmd.endswith(" test"), cmd
_, err2 = mod.scoped_maven_test_cmd("mvn -q test", {}, helpers)
assert err2 and "unscoped" in err2, err2
kept, err3 = mod.scoped_maven_test_cmd(
    "mvn -q -Dtest=com.demo.HealthTest test", item, helpers
)
assert err3 is None and "-Dtest=com.demo.HealthTest" in kept
print("OK: task_scoped_tests proves FQCN rewrite / unscoped refuse")
PY
echo "== M2 reverse-diff sibling: invented endpoints refuse; claimed inventory ok =="
python3 - "${SKILLS}" <<'PY' || rc=1
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

skills = Path(sys.argv[1])
script = skills / "harness/dispatch-phase/scripts/assert-partition-invented-routes.py"
spec = importlib.util.spec_from_file_location("rev", script)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)
inv = {
    "entry_points": [
        {"kind": "http", "http_method": "GET", "http_path": "/api/owners"},
    ]
}
contract = mod.inventory_contract(inv)
assert "GET /api/owners" in contract
assert "/api/owners" in contract
ok_part = {"stories": [{"story_id": "US1", "endpoints": ["GET /api/owners"]}]}
assert mod.invented_routes(ok_part, contract) == []
bad_part = {"stories": [{"story_id": "US5", "endpoints": ["/"]}]}
assert mod.invented_routes(bad_part, contract) == ["US5:/"]
wrap = Path(tempfile.mkdtemp(prefix="rev-diff-"))
(wrap / "evidence/briefs").mkdir(parents=True)
(wrap / "evidence/entry-point-inventory.json").write_text(json.dumps(inv) + "\n")
(wrap / "evidence/briefs/partition.json").write_text(
    json.dumps({"inventory": "evidence/entry-point-inventory.json", "stories": bad_part["stories"]})
    + "\n"
)
import subprocess
cp = subprocess.run([sys.executable, str(script), str(wrap)], capture_output=True, text=True)
assert cp.returncode != 0, cp.stdout + cp.stderr
assert "US5:/" in (cp.stderr or ""), cp.stderr
import shutil
shutil.rmtree(wrap, ignore_errors=True)
print("OK: reverse-diff sibling refuses invented /")
PY

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
    filter_attach_skills_for_write_set,
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
expect(
    filter_attach_skills_for_write_set(
        ["manage-quarkus-extensions", "form-entity-persistence"],
        ["src/Foo.java"],
    )
    == ["form-entity-persistence"],
    "pom skills drop unless pom.xml write-set",
)
expect(
    filter_attach_skills_for_write_set(
        ["manage-quarkus-extensions", "reference-rh-quarkus-pom"],
        ["pom.xml"],
    )
    == ["manage-quarkus-extensions", "reference-rh-quarkus-pom"],
    "pom skills stay on the pom.xml writer",
)

td = Path(tempfile.mkdtemp())
root = td / "dest"
harvest = td / ".derived" / "legacy-at-3" / "src/main/java/x/OwnerResource.java"
harvest.parent.mkdir(parents=True)
harvest.write_text("class OwnerResource {}\n", encoding="utf-8")
root.mkdir()
(root / "pom.xml").write_text("<project/>\n", encoding="utf-8")
(root / "evidence").mkdir()
(root / "evidence/derived").mkdir()
(root / "evidence/derived/legacy-at-3.json").write_text(
    '{"harvest_referent":true}\n', encoding="utf-8"
)
(root / "evidence/entry-point-inventory.json").write_text(
    json.dumps(
        {
            "schema": "rhoai3.entry-point-inventory/v1",
            "entry_points": [
                {
                    "kind": "http",
                    "file": "src/main/java/x/OwnerResource.java",
                    "symbol": "OwnerResource#list",
                    "http_method": "GET",
                    "http_path": "/api/owners",
                }
            ],
        }
    )
    + "\n",
    encoding="utf-8",
)
test_src = root / "src/test/java/x/OwnerResourceTest.java"
test_src.parent.mkdir(parents=True)
test_src.write_text(
    "import org.junit.jupiter.api.Test;\n"
    "class OwnerResourceTest { @Test void httpSemantics() { } }\n",
    encoding="utf-8",
)

story = {
    "story_id": "story-owners",
    "kind": "user_story",
    "operand_class": ["rest", "persistence"],
    "endpoints": ["GET /api/owners"],
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
locus = next(r for r in body["refs"] if r.get("key") == "legacy_locus")
expect(
    Path(locus["path"]).resolve() == harvest.resolve(),
    "HTTP assemble stamps inventory harvest file not dest Resource",
)
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
    "kind": "setup",
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
elif ! grep -q 'never prefix /projects/modernized' "${overlay}"; then
  echo "FAIL: overlay missing repo-relative path restatement (131510Z)" >&2
  rc=1
elif ! grep -q 'CLASS-LEVEL ABSOLUTE' "${overlay}"; then
  echo "FAIL: overlay missing class-level @Path restatement (133010Z)" >&2
  rc=1
elif ! grep -q 'evidence/type-inventory.json' "${overlay}"; then
  echo "FAIL: overlay missing M1 type-inventory path" >&2
  rc=1
elif ! grep -q 'evidence/required-extensions.json' "${overlay}"; then
  echo "FAIL: overlay missing M1 required-extensions path" >&2
  rc=1
else
  echo "OK: tip speckit overlay (clarify, no implement, no gates, M1 paths, ingress-only, class-level @Path)"
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
elif ! grep -q 'The legacy HTTP contract is immutable' "${constitution}"; then
  echo "FAIL: constitution asset missing principle VII (067050Z)" >&2
  rc=1
else
  echo "OK: constitution asset has zero placeholders (V20-3) + principle VII"
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
if ! grep -q 'one user story per inventory HTTP shape' "${tasks_tpl}"; then
  echo "FAIL: tasks-template asset lacks HTTP-shape unique-owner pin (120010Z)" >&2
  rc=1
else
  echo "OK: HTTP-shape unique-owner tasks-template pin present"
fi
if ! grep -q '@Path("' "${tasks_tpl}"; then
  echo "FAIL: tasks-template asset lacks @Path emit pin (200540Z)" >&2
  rc=1
else
  echo "OK: tasks-template @Path emit pin present"
fi
if ! grep -q 'never a path prefix in a task line' "${tasks_tpl}"; then
  echo "FAIL: tasks-template asset lacks repo-relative path pin (131510Z)" >&2
  rc=1
else
  echo "OK: tasks-template repo-relative path pin present"
fi
if ! grep -q 'CLASS-LEVEL ABSOLUTE' "${tasks_tpl}"; then
  echo "FAIL: tasks-template asset lacks class-level @Path pin (133010Z)" >&2
  rc=1
else
  echo "OK: tasks-template class-level @Path pin present"
fi
if ! grep -q 'creates a Resource class' "${tasks_tpl}"; then
  echo "FAIL: tasks-template @Path MUST not scoped to class-creating tasks (140510Z)" >&2
  rc=1
else
  echo "OK: tasks-template @Path MUST scoped to class-creating tasks (140510Z)"
fi
if ! grep -q 'already carries the class-level path' "${tasks_tpl}"; then
  echo "FAIL: tasks-template T022 still has a foreign @Path literal (135010Z)" >&2
  rc=1
else
  echo "OK: tasks-template T022 foreign class path is prose (135010Z)"
fi
if ! grep -q 'only inside the story phase that owns' "${tasks_tpl}"; then
  echo "FAIL: tasks-template lacks owning-story-phase @Path pin (135010Z)" >&2
  rc=1
else
  echo "OK: tasks-template owning-story-phase @Path pin present"
fi
if ! grep -q 'NAMES a dest file must CREATE it' "${tasks_tpl}"; then
  echo "FAIL: tasks-template lacks polish Create-named-file pin (I-16 / 215010Z)" >&2
  rc=1
elif grep -q 'Verify quality gate' "${tasks_tpl}"; then
  echo "FAIL: tasks-template polish sample still Verifies pom.xml (I-16 / 215010Z)" >&2
  rc=1
else
  echo "OK: tasks-template polish names a dest file must Create it (I-16)"
fi
if ! grep -q 'evidence/type-inventory.json' "${tasks_tpl}"; then
  echo "FAIL: tasks-template lacks type-inventory dest-twin pin" >&2
  rc=1
elif ! grep -q 'configure the dest generator' "${tasks_tpl}"; then
  echo "FAIL: tasks-template lacks generated-types carry-spec pin" >&2
  rc=1
elif grep -q 'Create DTOs matching legacy API contracts' "${tasks_tpl}"; then
  echo "FAIL: tasks-template still dumps DTOs as a Foundational directory" >&2
  rc=1
elif grep -q 'itemType ends `Dto`' "${tasks_tpl}" || grep -q 'itemType ends Dto' "${tasks_tpl}"; then
  echo "FAIL: tasks-template still keys dest twins on a Dto name pattern" >&2
  rc=1
else
  echo "OK: tasks-template type-inventory dest-twin pin present"
fi
spec_tpl="${SKILLS}/sdd/init-spec-workspace/assets/spec-template.md"
if [ ! -f "${spec_tpl}" ]; then
  echo "FAIL: missing spec-template asset" >&2
  rc=1
elif ! grep -q 'enumerate every inventory http_path' "${spec_tpl}"; then
  echo "FAIL: spec-template asset lacks inventory-enumerate pin (203500Z)" >&2
  rc=1
else
  echo "OK: spec-template inventory-enumerate pin present"
fi
if ! grep -q 'one user story per inventory HTTP shape' "${spec_tpl}"; then
  echo "FAIL: spec-template asset lacks HTTP-shape unique-owner restatement (120010Z)" >&2
  rc=1
else
  echo "OK: spec-template HTTP-shape unique-owner restatement present"
fi
if ! grep -q 'Read inventory before specify' \
  "${SKILLS}/harness/dispatch-phase/scripts/dispatch-phase.sh"; then
  echo "FAIL: M2 body missing inventory-before-specify (203500Z)" >&2
  rc=1
else
  echo "OK: M2 body names inventory-before-specify"
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
if [ -f "${rhdh_devfile}" ] \
  && grep -q 'stamp-harness-rev.py' "${rhdh_devfile}" \
  && grep -q 'autostart-migration.sh' "${rhdh_devfile}"; then
  echo "OK: RHDH skeleton destfile stamps HARNESS_REV and calls autostart-migration.sh"
else
  echo "FAIL: RHDH skeleton destfile missing stamp-harness-rev or autostart-migration" >&2
  rc=1
fi
# Column-0 lines inside commandLine: | end the scalar (v25 factory parse fail).
# YAML keys at column 0 (events:) end the block; script at column 0 is the bomb.
if python3 - "${rhdh_devfile}" <<'PY'
import re
import sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
in_cl = False
bad = []
yaml_key = re.compile(r"^[A-Za-z][\w.-]*:\s*")
for i, line in enumerate(text.splitlines(), 1):
    if line.rstrip().endswith("commandLine: |"):
        in_cl = True
        continue
    if not in_cl or not line.strip():
        continue
    indent = len(line) - len(line.lstrip(" "))
    stripped = line.lstrip()
    if indent == 0:
        if yaml_key.match(line):
            in_cl = False
            continue
        bad.append(f"{i}:{line[:80]}")
        continue
    if indent <= 2 and stripped.startswith("- id:"):
        in_cl = False
if bad:
    print("FAIL: RHDH skeleton commandLine | has column-0 lines:", "; ".join(bad))
    sys.exit(1)
want = 'want="239F"'
if "23A7" in text:
    print("FAIL: RHDH skeleton still has port hex 23A7 (9127); dash_bind must match 9119 = 239F")
    sys.exit(1)
if want not in text:
    print("FAIL: RHDH skeleton dash_bind missing", want, "(9119 in /proc/net/tcp hex)")
    sys.exit(1)
print("OK: RHDH skeleton commandLine | has no column-0 lines; dash_bind port 239F")
PY
then
  :
else
  rc=1
fi
if command -v ruby >/dev/null 2>&1; then
  if ruby -ryaml -e 'YAML.load_file(ARGV[0]); puts "OK: RHDH skeleton YAML parses"' "${rhdh_devfile}"; then
    :
  else
    echo "FAIL: RHDH skeleton is not valid YAML" >&2
    rc=1
  fi
else
  echo "WARN: ruby missing — skipped YAML.parse of RHDH skeleton"
fi
# Operator E-20260818T153010Z — parse gate lives in nested tools until this
# call; dest seats without the nested repo skip it.
platform_root="$(cd "${ROOT}/../../../.." && pwd)"
_hr="harness-refactoring"
preflight="${platform_root}/${_hr}/tools/preflight-publish.sh"
if [ -x "${preflight}" ]; then
  if bash "${preflight}" "${platform_root}"; then
    echo "OK: preflight-publish parse gate"
  else
    echo "FAIL: preflight-publish parse gate" >&2
    rc=1
  fi
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

# Architect E-20260819T155354Z / Operator E-20260819T155515Z: test-only
# stamps test_suite_runs; mixed rest+test keeps http_semantics.
_polish = _hm.Phase(
    heading="Polish",
    kind=_hm.KIND_POLISH,
    story_id="polish",
    body="",
    files=["src/test/java/org/x/SuiteTest.java"],
)
_hm.stamp_oracles([_polish])
_pac = _polish.acceptance_criteria
if (
    _polish.operand_class != ["test"]
    or not _pac
    or _pac[0].get("check") != "test_suite_runs"
    or _pac[0].get("cmd") != "mvn -q test"
):
    print(
        f"FAIL: polish test-only stamp {_polish.operand_class} {_pac}",
        file=sys.stderr,
    )
    raise SystemExit(1)
print("OK: polish test-only stamps test_suite_runs")
_us_rt = _hm.Phase(
    heading="User Story 1",
    kind=_hm.KIND_USER_STORY,
    story_id="US1",
    body="",
    files=[
        "src/main/java/x/OwnerResource.java",
        "src/test/java/x/OwnerResourceTest.java",
    ],
    independent_test="Run src/test/java/x/OwnerResourceTest.java",
)
_hm.stamp_oracles([_us_rt])
_uac = _us_rt.acceptance_criteria
if (
    "rest" not in _us_rt.operand_class
    or "test" not in _us_rt.operand_class
    or not _uac
    or _uac[0].get("check") != "http_semantics"
):
    print(
        f"FAIL: rest+test must keep http_semantics {_us_rt.operand_class} {_uac}",
        file=sys.stderr,
    )
    raise SystemExit(1)
print("OK: rest+test keeps http_semantics")
try:
    _us_rest = _hm.Phase(
        heading="User Story 8",
        kind=_hm.KIND_USER_STORY,
        story_id="US8",
        body="",
        files=["src/main/java/x/RootResource.java"],
        independent_test="Manual curl of GET /",
    )
    _hm.stamp_oracles([_us_rest])
    print(
        f"FAIL: rest without test must ORACLE_UNMAPPED {_us_rest.acceptance_criteria}",
        file=sys.stderr,
    )
    raise SystemExit(1)
except _hm.HandoverError as exc:
    if exc.code != "ORACLE_UNMAPPED":
        print(f"FAIL: rest-without-test code {exc.code}: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print("OK: rest without test path is ORACLE_UNMAPPED")
try:
    _src = _hm.Phase(
        heading="Foundational",
        kind=_hm.KIND_FOUNDATIONAL,
        story_id="foundational",
        body="",
        files=["src/main/java/x/Helper.java"],
    )
    _hm.stamp_oracles([_src])
    print(
        f"FAIL: src_code-only must ORACLE_UNMAPPED {_src.acceptance_criteria}",
        file=sys.stderr,
    )
    raise SystemExit(1)
except _hm.HandoverError as exc:
    if exc.code != "ORACLE_UNMAPPED":
        print(f"FAIL: unmapped combo code {exc.code}: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print("OK: unmapped operand_class is ORACLE_UNMAPPED")
PY
  rm -rf "${ho_tmp}"
fi
echo "== F-1 pom phrasing + F-6 import-graph parents =="
python3 - "${handover}" "${SKILLS}/sdd/check-spec-readiness/scripts" <<'PY' || rc=1
import sys, tempfile
from pathlib import Path
handover, ready = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(ready))
sys.path.insert(0, str(handover.parent))
import importlib.util
spec = importlib.util.spec_from_file_location("handover_mint_f16", handover)
hm = importlib.util.module_from_spec(spec)
sys.modules["handover_mint_f16"] = hm
spec.loader.exec_module(hm)

def mini(pom_line: str) -> str:
    return f"""# Tasks

## Phase 1: Setup (Shared Infrastructure)
- [ ] T001 {pom_line}
- [ ] T002 Create src/main/resources/application.properties

## Phase 2: Foundational (Blocking Prerequisites)
- [ ] T007 Create Owner in src/main/java/org/x/model/Owner.java

## Phase 3: Polish
- [ ] T099 Create src/test/java/org/x/OwnerTest.java

## Dependencies
**Setup**: No dependencies
**Foundational**: depends on Setup
**Polish**: depends on all desired user stories
"""

phrasings = [
    "Add Quarkus extensions to pom.xml",
    "Add Quarkus extensions to `pom.xml`",
    "Create pom.xml with Red Hat BOM",
    "Configure pom.xml with compiler plugin",
    "Update pom.xml: add resteasy",
]
for phrase in phrasings:
    phases = hm.parse_phases(mini(phrase))
    owner = hm.assign_ownership(phases)
    writers = [p.story_id for p in phases if any(hm._is_pom(f) for f in p.files)]
    if owner != "setup" or writers != ["setup"]:
        print(f"FAIL: F-1 {phrase!r} owner={owner!r} writers={writers!r}", file=sys.stderr)
        raise SystemExit(1)
print("OK: F-1 five pom phrasings register exactly one setup owner")

root = Path(tempfile.mkdtemp(prefix="f6-parents-"))
owner_java = root / "src/main/java/org/x/model/Owner.java"
rest_java = root / "src/main/java/org/x/rest/OwnerResource.java"
owner_java.parent.mkdir(parents=True)
rest_java.parent.mkdir(parents=True)
owner_java.write_text(
    "package org.x.model;\npublic class Owner {}\n", encoding="utf-8"
)
rest_java.write_text(
    "package org.x.rest;\nimport org.x.model.Owner;\n"
    "public class OwnerResource { Owner o; }\n",
    encoding="utf-8",
)
tasks = """# Tasks

## Phase 1: Setup (Shared Infrastructure)
- [ ] T001 Create pom.xml
- [ ] T002 Create src/main/resources/application.properties

## Phase 2: Foundational (Blocking Prerequisites)
- [ ] T007 Create Owner in src/main/java/org/x/model/Owner.java

## Phase 3: Owner CRUD [US1]
- [ ] T020 Create OwnerResource in src/main/java/org/x/rest/OwnerResource.java

## Phase 4: Polish
- [ ] T099 Create src/test/java/org/x/OwnerResourceTest.java

## Dependencies
**Setup**: No dependencies
**Foundational**: depends on Setup
**Polish**: depends on all desired user stories
"""
(root / "src/test/java/org/x").mkdir(parents=True)
(root / "src/test/java/org/x/OwnerResourceTest.java").write_text(
    "package org.x;\npublic class OwnerResourceTest {}\n", encoding="utf-8"
)
(root / "src/main/resources").mkdir(parents=True)
(root / "src/main/resources/application.properties").write_text("", encoding="utf-8")
phases = hm.parse_phases(tasks)
if phases[2].story_id != "US1":
    print(f"FAIL: F-6 heading [US1] kinded {phases[2].story_id}", file=sys.stderr)
    raise SystemExit(1)
hm.transcribe_parents(tasks, phases)
if phases[2].parents:
    print(f"FAIL: F-6 expected empty prose parents, got {phases[2].parents}", file=sys.stderr)
    raise SystemExit(1)
hm.merge_import_parents(root, phases)
hm.assert_parents_resolved(phases)
if "foundational" not in phases[2].parents:
    print(f"FAIL: F-6 US1 parents {phases[2].parents} missing foundational", file=sys.stderr)
    raise SystemExit(1)
print("OK: F-6 import graph parents foundational without the prose phrase")

sib = Path(tempfile.mkdtemp(prefix="f6-sibling-"))
spec_java = sib / "src/main/java/org/x/mapper/SpecialtyMapper.java"
vet_java = sib / "src/main/java/org/x/mapper/VetMapper.java"
spec_java.parent.mkdir(parents=True, exist_ok=True)
vet_java.parent.mkdir(parents=True, exist_ok=True)
spec_java.write_text(
    "package org.x.mapper;\npublic class SpecialtyMapper {}\n", encoding="utf-8"
)
vet_java.write_text(
    "package org.x.mapper;\nimport org.x.mapper.SpecialtyMapper;\n"
    "public class VetMapper { SpecialtyMapper m; }\n",
    encoding="utf-8",
)
sib_tasks = """# Tasks

## Phase 1: Setup (Shared Infrastructure)
- [ ] T001 Create pom.xml
- [ ] T002 Create src/main/resources/application.properties

## Phase 2: Foundational (Blocking Prerequisites)
- [ ] T007 Create Owner in src/main/java/org/x/model/Owner.java

## Phase 3: Specialties [US4]
- [ ] T040 Create SpecialtyMapper in src/main/java/org/x/mapper/SpecialtyMapper.java

## Phase 4: Vets [US5]
- [ ] T041 Create VetMapper in src/main/java/org/x/mapper/VetMapper.java

## Phase 5: Polish
- [ ] T099 Create src/test/java/org/x/VetMapperTest.java

## Dependencies
**Setup**: No dependencies
**Foundational**: depends on Setup
**User Stories**: depend on Foundational
**Polish**: depends on all desired user stories
"""
(sib / "src/main/java/org/x/model").mkdir(parents=True)
(sib / "src/main/java/org/x/model/Owner.java").write_text(
    "package org.x.model;\npublic class Owner {}\n", encoding="utf-8"
)
(sib / "src/test/java/org/x").mkdir(parents=True)
(sib / "src/test/java/org/x/VetMapperTest.java").write_text(
    "package org.x;\npublic class VetMapperTest {}\n", encoding="utf-8"
)
(sib / "src/main/resources").mkdir(parents=True)
(sib / "src/main/resources/application.properties").write_text("", encoding="utf-8")
sib_ph = hm.parse_phases(sib_tasks)
hm.transcribe_parents(sib_tasks, sib_ph)
us4 = next(p for p in sib_ph if p.story_id == "US4")
us5 = next(p for p in sib_ph if p.story_id == "US5")
if "foundational" not in us4.parents or "foundational" not in us5.parents:
    print(f"FAIL: H-4 collective parents {us4.parents} {us5.parents}", file=sys.stderr)
    raise SystemExit(1)
hm.merge_import_parents(sib, sib_ph)
if "US4" not in us5.parents:
    print(f"FAIL: H-4 US5 parents {us5.parents} missing US4", file=sys.stderr)
    raise SystemExit(1)
if any("SpecialtyMapper.java" in f for f in us5.files):
    print(f"FAIL: H-4 relocated mapper onto US5 {us5.files}", file=sys.stderr)
    raise SystemExit(1)
if not any("SpecialtyMapper.java" in f for f in us4.files):
    print(f"FAIL: H-4 US4 lost SpecialtyMapper {us4.files}", file=sys.stderr)
    raise SystemExit(1)
print("OK: F-6 sibling import parents the owning story")

cyc = Path(tempfile.mkdtemp(prefix="cycle-import-"))
owner_us = cyc / "src/main/java/org/x/model/Owner.java"
facade = cyc / "src/main/java/org/x/Facade.java"
owner_us.parent.mkdir(parents=True, exist_ok=True)
facade.parent.mkdir(parents=True, exist_ok=True)
owner_us.write_text("package org.x.model;\npublic class Owner {}\n", encoding="utf-8")
facade.write_text(
    "package org.x;\nimport org.x.model.Owner;\n"
    "public class Facade { Owner o; }\n",
    encoding="utf-8",
)
cyc_tasks = """# Tasks

## Phase 1: Setup (Shared Infrastructure)
- [ ] T001 Create pom.xml
- [ ] T002 Create src/main/resources/application.properties

## Phase 2: Foundational (Blocking Prerequisites)
- [ ] T007 Create Facade in src/main/java/org/x/Facade.java

## Phase 3: Owner CRUD [US1]
- [ ] T020 Create Owner in src/main/java/org/x/model/Owner.java

## Phase 4: Polish
- [ ] T099 Create src/test/java/org/x/OwnerTest.java

## Dependencies
**Setup**: No dependencies
**Foundational**: depends on Setup
**User Stories**: depend on Foundational
**Polish**: depends on all desired user stories
"""
(cyc / "src/test/java/org/x").mkdir(parents=True)
(cyc / "src/test/java/org/x/OwnerTest.java").write_text(
    "package org.x;\npublic class OwnerTest {}\n", encoding="utf-8"
)
(cyc / "src/main/resources").mkdir(parents=True)
(cyc / "src/main/resources/application.properties").write_text("", encoding="utf-8")
cyc_ph = hm.parse_phases(cyc_tasks)
hm.transcribe_parents(cyc_tasks, cyc_ph)
hm.assert_foundational_no_service(cyc_ph)
try:
    hm.merge_import_parents(cyc, cyc_ph)
    print("FAIL: cyclic Facade→Owner must CYCLE_IMPORT", file=sys.stderr)
    raise SystemExit(1)
except hm.HandoverError as exc:
    if exc.code != "CYCLE_IMPORT":
        print(f"FAIL: expected CYCLE_IMPORT got {exc.code}: {exc}", file=sys.stderr)
        raise SystemExit(1)
    detail = str(exc)
    if "Parent the owning story" not in detail:
        print("FAIL: CYCLE_IMPORT must name parent-or-split remedy", file=sys.stderr)
        raise SystemExit(1)
    print("OK: CYCLE_IMPORT refuses cyclic import parent")

svc_tasks = """# Tasks

## Phase 1: Setup (Shared Infrastructure)
- [ ] T001 Create pom.xml
- [ ] T002 Create src/main/resources/application.properties

## Phase 2: Foundational (Blocking Prerequisites)
- [ ] T007 Create AppService in src/main/java/org/x/service/AppService.java

## Phase 3: Polish
- [ ] T099 Create src/test/java/org/x/AppServiceTest.java

## Dependencies
**Setup**: No dependencies
**Foundational**: depends on Setup
**Polish**: depends on all desired user stories
"""
try:
    svc_ph = hm.parse_phases(svc_tasks)
    hm.assert_foundational_no_service(svc_ph)
    print("FAIL: foundational AppService must T0_3_SERVICE", file=sys.stderr)
    raise SystemExit(1)
except hm.HandoverError as exc:
    if exc.code != "T0_3_SERVICE":
        print(f"FAIL: expected T0_3_SERVICE got {exc.code}: {exc}", file=sys.stderr)
        raise SystemExit(1)
    detail = str(exc)
    if "split per aggregate" not in detail:
        print("FAIL: T0_3_SERVICE must name split per aggregate", file=sys.stderr)
        raise SystemExit(1)
    if "polish or a user story" in detail.lower() or "put the facade on" in detail.lower():
        print("FAIL: T0_3_SERVICE names an unsatisfiable placement", file=sys.stderr)
        raise SystemExit(1)
    print("OK: T0_3_SERVICE refuses foundational *Service.java")
    print("OK: T0_3_SERVICE remedy is split per aggregate")

p5_tasks = """# Tasks

## Phase 1: Setup (Shared Infrastructure)
- [ ] T001 Create pom.xml
- [ ] T002 Create src/main/resources/application.properties

## Phase 2: Foundational (Blocking Prerequisites)
- [ ] T007 Create Owner in src/main/java/org/x/model/Owner.java

## Phase 5: Service Layer (API Contracts)
- [ ] T027 Create src/main/java/com/demo/service/AppService.java
- [ ] T028 Create src/main/java/com/demo/service/AppServiceImpl.java

## Phase 6: Polish
- [ ] T099 Create src/test/java/org/x/OwnerTest.java

## Dependencies
**Setup**: No dependencies
**Foundational**: depends on Setup
**Polish**: depends on all desired user stories
"""
p5_ph = hm.parse_phases(p5_tasks)
hm.assert_foundational_no_service(p5_ph)
p5 = next(p for p in p5_ph if p.story_id == "P5")
if p5.kind != hm.KIND_PHASE:
    print(f"FAIL: Phase 5 kinded {p5.kind}", file=sys.stderr)
    raise SystemExit(1)
print("OK: T0_3_SERVICE allows AppService on Phase 5")
mint_src = handover.read_text(encoding="utf-8")
idx = mint_src.find('"T0_3_SERVICE"')
if idx < 0:
    print("FAIL: LV-7c missing T0_3_SERVICE _die", file=sys.stderr)
    raise SystemExit(1)
blob = mint_src[idx:idx + 900]
if "split per aggregate" not in blob:
    print("FAIL: LV-7c T0_3_SERVICE must name split per aggregate", file=sys.stderr)
    raise SystemExit(1)
for bad in ("polish or a user story", "Put the facade on polish", "Put the facade on"):
    if bad in blob:
        print(f"FAIL: LV-7c T0_3_SERVICE names unsatisfiable placement {bad!r}", file=sys.stderr)
        raise SystemExit(1)
print("OK: LV-7c T0_3_SERVICE names no placement another gate refuses")
PY
if grep -q relocate-descendant-import-writesets.py \
    "${SKILLS}/harness/dispatch-phase/scripts/scratch-assemble-mint.py"; then
  echo "OK: scratch-assemble wires relocate-descendant MULTI_OWNER gate"
else
  echo "FAIL: scratch-assemble-mint.py must call relocate-descendant-import-writesets.py" >&2
  rc=1
fi
echo "== I-16 M2 scratch --write oracle (Verify-only polish must refuse) =="
SCRATCH_ORACLE="${SKILLS}/harness/dispatch-phase/scripts/scratch-assemble-mint.py"
SCRATCH_FIX="${SKILLS}/harness/dispatch-phase/fixtures/scratch-assemble/verify-only-polish"
I16_ADMIT="${SKILLS}/harness/dispatch-phase/fixtures/scratch-assemble/create-healthtest-admit"
POM_STRIP="${SKILLS}/harness/dispatch-phase/fixtures/scratch-assemble/dual-create-pom-refuse"
if [ ! -f "${SCRATCH_ORACLE}" ]; then
  echo "FAIL: missing scratch-assemble-mint.py" >&2
  rc=1
elif python3 "${SCRATCH_ORACLE}" "${SCRATCH_FIX}" --expect-fail; then
  echo "OK: Verify-only polish scratch --write refuses (PB-2 rehearsal)"
else
  echo "FAIL: Verify-only polish did not refuse scratch --write (221200Z)" >&2
  rc=1
fi
echo "== I-16 Create HealthTest polish must assemble; dual-Create pom strips to Setup =="
if python3 "${SCRATCH_ORACLE}" "${I16_ADMIT}" \
  && python3 "${SCRATCH_ORACLE}" "${POM_STRIP}" --assert-polish-excludes pom.xml; then
  echo "OK: Create HealthTest assembles; polish Create pom.xml is stripped to Setup"
else
  echo "FAIL: I-16 positive assemble / ownership-strip rehearsal (203811Z)" >&2
  rc=1
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
  "${HARNESS}/dispatch-phase/scripts/dispatch-phase.sh" >/dev/null; then
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

echo "== B-6 story park is ack_gate parent, not sticky-block =="
MINT_PROC="${HARNESS}/dispatch-phase/references/mint-m3-hermes.md"
if grep -q 'OBJECT Option B' "${MINT_PROC}" \
  && grep -q 'Sticky-block is' "${MINT_PROC}"; then
  echo "OK: B-6 story park is incomplete ack_gate parent (OBJECT Option B)"
else
  echo "FAIL: B-6 mint Procedure must OBJECT sticky-block on story cards" >&2
  rc=1
fi

echo "== B2/B3 holder kind map + one-three-one-rule path-invoke (I-11) =="
DP_SKILL="${HARNESS}/dispatch-phase/SKILL.md"
HOLDER_BODY="${HARNESS}/dispatch-phase/references/holder-card-body.md"
if grep -q 'Fail-closed kind map' "${DP_SKILL}" \
  && grep -q 'Do \*\*not\*\* pin `one-three-one-rule`' "${DP_SKILL}" \
  && grep -q 'Do \*\*not\*\* pin `dispatch-phase`' "${DP_SKILL}" \
  && ! grep -q -- '--skill dispatch-phase' "${DP_SKILL}" \
  && ! grep -q -- '--skill one-three-one-rule' "${DP_SKILL}" \
  && grep -q 'Do \*\*not\*\* pin `check-spec-readiness`' "${DP_SKILL}"; then
  echo "OK: dispatch-phase SKILL.md kind map + I-10 B / I-11 no holder skill pin"
else
  echo "FAIL: dispatch-phase SKILL.md missing kind map / I-10 B / I-11 (25a7c1e9)" >&2
  rc=1
fi
if grep -q 'Fail-closed kind map' "${MINT_PROC}" \
  && grep -q 'Do \*\*not\*\* pin `one-three-one-rule`' "${MINT_PROC}" \
  && grep -q 'Do \*\*not\*\* pin `dispatch-phase`' "${MINT_PROC}" \
  && grep -q 'Do \*\*not\*\* pin `check-spec-readiness`' "${MINT_PROC}"; then
  echo "OK: mint Procedure kind map + I-10 B / I-11 (no holder skill pin)"
else
  echo "FAIL: mint Procedure missing kind map / I-10 B / I-11" >&2
  rc=1
fi
if grep -q 'the park protection' "${MINT_PROC}" \
  && grep -q 'OBJECT requiring story' "${MINT_PROC}"; then
  echo "OK: mint Procedure story park is ack_gate parent not status==blocked (113650Z)"
else
  echo "FAIL: mint Procedure still treats story status==blocked as the v25 assert (113650Z retract)" >&2
  rc=1
fi
if [ ! -f "${HOLDER_BODY}" ]; then
  echo "FAIL: missing holder-card-body.md" >&2
  rc=1
elif ! grep -q 'Fail-closed kind map' "${HOLDER_BODY}" \
  || ! grep -q 'needs_input' "${HOLDER_BODY}" \
  || ! grep -q 'one-three-one-rule' "${HOLDER_BODY}" \
  || ! grep -q 'Do \*\*not\*\* pin `one-three-one-rule`' "${HOLDER_BODY}" \
  || ! grep -q 'Do \*\*not\*\* declare `dispatch-phase`' "${HOLDER_BODY}" \
  || ! grep -q 'Do \*\*not\*\* attach `check-spec-readiness`' "${HOLDER_BODY}"; then
  echo "FAIL: holder-card-body.md missing kind map / needs_input / I-10 B / I-11" >&2
  rc=1
else
  echo "OK: holder card body carries fail-closed kind map + I-10 B / I-11 path-invoke"
fi

echo "== B2 phase files_writable (M2/M4/M5 published; M3 omit) =="
PD_YAML="${ROOT}/.hermes/phase-dispatch.yaml"
PD_READ="${HARNESS}/dispatch-phase/scripts/read-phase-dispatch.py"
fw_m2="$(python3 "${PD_READ}" --yaml "${PD_YAML}" --phase M2 --print files_writable_json)"
fw_m3="$(python3 "${PD_READ}" --yaml "${PD_YAML}" --phase M3 --print files_writable_json)"
fw_m4="$(python3 "${PD_READ}" --yaml "${PD_YAML}" --phase M4 --print files_writable_json)"
fw_m5="$(python3 "${PD_READ}" --yaml "${PD_YAML}" --phase M5 --print files_writable_json)"
if [ "${fw_m2}" = '[".specify/","specs/"]' ]; then
  echo "OK: M2 files_writable is .specify/ + specs/"
else
  echo "FAIL: M2 files_writable expected [.specify/, specs/] got ${fw_m2}" >&2
  rc=1
fi
if [ "${fw_m3}" = "null" ]; then
  echo "OK: M3 omits files_writable (card-resolved)"
else
  echo "FAIL: M3 must omit files_writable, got ${fw_m3}" >&2
  rc=1
fi
if [ "${fw_m4}" = "[]" ] && [ "${fw_m5}" = "[]" ]; then
  echo "OK: M4/M5 files_writable published empty"
else
  echo "FAIL: M4/M5 files_writable expected [] got M4=${fw_m4} M5=${fw_m5}" >&2
  rc=1
fi
# extract_body first-matches unquoted `M2)`; the B2 guard must not shadow the heredoc.
if python3 "${HARNESS}/dispatch-phase/scripts/check-phase-input-manifest.py" "${ROOT}" M2; then
  echo "OK: M2 card body extractable (Input manifest; 184010Z unshadow)"
else
  echo "FAIL: M2 body missing / extract_body captured B2 guard (184010Z)" >&2
  rc=1
fi

echo "== B3 declared-vs-disabled refuse =="
B3="${HARNESS}/dispatch-phase/scripts/assert-skills-not-disabled.py"
if python3 "${B3}" "${ROOT}" --skill dispatch-phase >/dev/null 2>&1; then
  echo "FAIL: B3 must refuse --skill dispatch-phase" >&2
  rc=1
else
  echo "OK: B3 refuses a card declaring a disabled skill"
fi
if python3 "${B3}" "${ROOT}" --skill check-spec-readiness --skill one-three-one-rule >/dev/null; then
  echo "OK: B3 allows declared skills outside skills.disabled"
else
  echo "FAIL: B3 refused a non-disabled skill" >&2
  rc=1
fi
if python3 "${B3}" "${ROOT}" --from-phase M3 >/dev/null; then
  echo "OK: B3 --from-phase M3 (pool is not disabled)"
else
  echo "FAIL: B3 --from-phase M3 refused the allow-list pool" >&2
  rc=1
fi

echo "== F1 tasks-template mirror legacy sub-packages =="
TASKS_TPL="${ROOT}/.hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md"
if grep -q 'mirror the legacy sub-package' "${TASKS_TPL}" \
  && ! grep -q 'com/demo/entity/' "${TASKS_TPL}"; then
  echo "OK: tasks-template mirrors legacy sub-packages (no entity/ hardcode)"
else
  echo "FAIL: tasks-template missing mirror rule or still hardcodes entity/" >&2
  rc=1
fi

echo "== M1 verifier refuse-on-nonzero + seat Hermes pin (111730Z) =="
PINS="${ROOT}/.hermes/pins.json"
M1V="${HARNESS}/dispatch-phase/scripts/check-m1-verifier.py"
M1VD="${HARNESS}/dispatch-phase/references/m1-verifier.md"
if grep -q '"version": "v0.20.4"' "${PINS}" \
  && grep -q 'binary-local' "${PINS}"; then
  echo "OK: pins.json seat Hermes v0.20.4 binary-local contract"
else
  echo "FAIL: pins.json missing v0.20.4 / binary-local pin (132010Z)" >&2
  rc=1
fi
if grep -q '\["hermes", "--version"\]' "${HARNESS}/dispatch-phase/scripts/assert-seat-hermes-pin.py" \
  && ! grep -q '\["hermes", "version"\]' "${HARNESS}/dispatch-phase/scripts/assert-seat-hermes-pin.py"; then
  echo "OK: live pin assert probes hermes --version (v37 dest-cite)"
else
  echo "FAIL: assert-seat-hermes-pin.py still probes hermes version subcommand" >&2
  rc=1
fi
if grep -q 'refuse-on-nonzero' "${M1VD}" \
  && grep -q 'refuse-on-nonzero' "${M1V}" \
  && grep -q 'M1 ONLY' "${M1V}"; then
  echo "OK: M1 verifier refuse-on-nonzero (M1 only)"
else
  echo "FAIL: M1 verifier missing refuse-on-nonzero (095340Z)" >&2
  rc=1
fi
if grep -q 'assert-seat-hermes-pin.py' "${HARNESS}/dispatch-phase/scripts/dispatch-phase.sh"; then
  echo "OK: live dispatch asserts seat Hermes pin"
else
  echo "FAIL: dispatch-phase.sh missing assert-seat-hermes-pin.py (111730Z)" >&2
  rc=1
fi
m1v_tmp="$(mktemp -d "${TMPDIR:-/tmp}/m1v.XXXXXX")"
if python3 "${M1V}" "${m1v_tmp}" >/dev/null 2>&1; then
  echo "FAIL: M1 verifier exit 0 on empty root (must refuse-on-nonzero)" >&2
  rc=1
else
  echo "OK: M1 verifier refuse-on-nonzero on missing artifacts"
fi
rm -rf "${m1v_tmp}"

echo "== Card body contract on mint Procedure (035010Z / 224320Z) =="
if grep -q 'check-body-digest-match.py --expect' "${MINT_PROC}" \
  && grep -q 'skills = full m3-attach-skills.py stdout' "${MINT_PROC}" \
  && grep -q 'evidence/bodies/m3-' "${MINT_PROC}" \
  && grep -q 'AD-002E' "${MINT_PROC}"; then
  echo "OK: mint Procedure declares card body contract (path+digest+standing+attach-stdout)"
else
  echo "FAIL: mint Procedure missing card body contract (035010Z)" >&2
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

echo "== B-16 attach refuses names outside yaml pool =="
b16_bad="$(mktemp "${TMPDIR:-/tmp}/b16-bad.XXXXXX.json")"
printf '%s\n' '{"identity":{"operand_skills":["not-a-pool-skill"]}}' >"${b16_bad}"
if python3 "${HARNESS}/dispatch-phase/scripts/m3-attach-skills.py" "${b16_bad}" >/dev/null 2>&1; then
  echo "FAIL: B-16 attach must refuse names not in yaml M3.skills" >&2
  rc=1
else
  echo "OK: B-16 attach refuses names outside yaml pool"
fi
rm -f "${b16_bad}"

echo "== B-16 pom skills attach only on pom.xml writer =="
b16_fnd="$(mktemp "${TMPDIR:-/tmp}/b16-fnd.XXXXXX.json")"
printf '%s\n' '{"identity":{"operand_skills":["manage-quarkus-extensions","reference-rh-quarkus-pom","form-entity-persistence","spring-to-quarkus-patterns"]},"files_writable":["src/Foo.java"]}' >"${b16_fnd}"
b16_fnd_out="$(python3 "${HARNESS}/dispatch-phase/scripts/m3-attach-skills.py" "${b16_fnd}")"
if printf '%s\n' "${b16_fnd_out}" | grep -qx 'form-entity-persistence' \
  && printf '%s\n' "${b16_fnd_out}" | grep -qx 'spring-to-quarkus-patterns' \
  && ! printf '%s\n' "${b16_fnd_out}" | grep -qx 'manage-quarkus-extensions' \
  && ! printf '%s\n' "${b16_fnd_out}" | grep -qx 'reference-rh-quarkus-pom'; then
  echo "OK: B-16 attach drops pom skills when pom.xml is not writable"
else
  echo "FAIL: B-16 foundational-shaped attach was: ${b16_fnd_out}" >&2
  rc=1
fi
rm -f "${b16_fnd}"

echo "== B-16 yaml M3.skills covers recommender vocab =="
if python3 "${HARNESS}/dispatch-phase/scripts/check-phase-attach-matrix.py" "${ROOT}"; then
  echo "OK: phase attach matrix (M3 pool covers OPERAND_CLASS_SKILLS)"
else
  echo "FAIL: phase attach matrix (M3 pool must cover OPERAND_CLASS_SKILLS)" >&2
  rc=1
fi

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
