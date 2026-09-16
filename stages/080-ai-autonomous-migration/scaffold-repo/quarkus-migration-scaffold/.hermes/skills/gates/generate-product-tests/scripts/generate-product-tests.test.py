#!/usr/bin/env python3
"""generate-product-tests selftest: the harness owns the generated expectations.

The controls this file exists for:

  accounting    one method per QUALIFIED scenario and a named gap for every
                other one. A scenario that quietly produced no test and no gap
                is the failure mode the manifest exists to make impossible.
  ownership     the same inputs generate the same bytes twice, the manifest
                binds every one of them by digest, and ``--check`` refuses
                after a worker edits a generated expectation.
  agnostic      a renamed specimen -- different packages, types and routes --
                generates structurally identical output, and the generator
                source carries no specimen literal.
  plausible     the generated Java is balanced, carries @QuarkusTest and a
                REST Assured call chain, and (when a JDK is here) compiles
                against compile-only stubs for Quarkus, REST Assured and
                JUnit.

The fixture is built the way scenario-parity.test.py builds one -- a derived
corpus with its derivation receipt, request bodies, source captures with
before/after read-backs, and a qualification bound to each capture by digest.
It is written directly rather than through planner.specimens: this producer
reads only those four documents plus the evidence bundle, and a hand-built
tree lets the renamed-specimen control vary every name that matters.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
GENERATOR = HERE / "generate-product-tests.py"
CAPTURE_SCRIPTS = HERE.parents[1] / "capture-source-oracles" / "scripts"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(CAPTURE_SCRIPTS))

from _oracle_common import normalize_body  # noqa: E402
from _scenarios import SCENARIO_ORACLES, corpus_digest, request_of, scenario_slug  # noqa: E402

sys.path.insert(0, str(HERE.parents[3] / "lib"))
from planner.canonical import canonical_bytes, digest, load_json, sha256_bytes, write_canonical  # noqa: E402

MANIFEST = Path("evidence") / "tests" / "generated-manifest.json"
RESET_SCRIPT = Path(".hermes") / "skills" / "gates" / "capture-source-oracles" / "scripts" / "reset-parity-db.sh"
SOURCE_BASE = "http://src.example:9966/app"
SHA_RE = re.compile(r"\b[0-9a-f]{64}\b")

SPEC_A = {"pkg": "alpha.one", "sub": "alpha", "sub2": "entrance", "type": "AlphaResource",
          "root_type": "EntranceResource", "route": "/api/alphas", "res": "alpha"}
SPEC_B = {"pkg": "beta.two", "sub": "beta", "sub2": "doorway", "type": "BetaResource",
          "root_type": "DoorwayResource", "route": "/api/betas", "res": "beta"}

# A destination pom with no <profiles> of its own: the producer must add the
# marked block, and adding it twice must change nothing.
POM_FIXTURE = """<?xml version='1.0' encoding='utf-8'?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>fixture.dest</groupId>
  <artifactId>dest</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <build>
    <plugins>
      <plugin>
        <artifactId>maven-surefire-plugin</artifactId>
      </plugin>
    </plugins>
  </build>
</project>
"""

# The same pom with the test-plugin configuration the platform guide documents.
# The profile must not DROP what the base build already sets: it merges its two
# pins into its own copy and leaves <build> alone.
POM_FIXTURE_TESTCONFIG = POM_FIXTURE.replace("""      <plugin>
        <artifactId>maven-surefire-plugin</artifactId>
      </plugin>
""", """      <plugin>
        <artifactId>maven-surefire-plugin</artifactId>
        <version>${surefire-plugin.version}</version>
        <configuration>
          <systemPropertyVariables>
            <java.util.logging.manager>org.jboss.logmanager.LogManager</java.util.logging.manager>
            <maven.home>${maven.home}</maven.home>
          </systemPropertyVariables>
        </configuration>
      </plugin>
      <plugin>
        <artifactId>maven-failsafe-plugin</artifactId>
        <version>${surefire-plugin.version}</version>
        <executions>
          <execution>
            <goals><goal>integration-test</goal><goal>verify</goal></goals>
            <configuration>
              <systemPropertyVariables>
                <native.image.path>${project.build.directory}/runner</native.image.path>
                <java.util.logging.manager>org.jboss.logmanager.LogManager</java.util.logging.manager>
                <maven.home>${maven.home}</maven.home>
              </systemPropertyVariables>
            </configuration>
          </execution>
        </executions>
      </plugin>
""")

# A RENAMED specimen's decisions: other profile names, another switch key and
# two other settings. Nothing here is the pilot's, which is the control that
# the producer reads the declaration rather than a literal it knows.
FIXTURE_PROFILES = ["gamma", "delta-store"]
FIXTURE_SWITCH = {"key": "acme.guard.active", "disabled_value": "quiet", "enabled_value": "strict"}

FAILURES: list[str] = []


def fail(msg: str) -> int:
    FAILURES.append(msg)
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GENERATOR), "--root", str(root), *args], text=True, capture_output=True)


# ---------------------------------------------------------------------------
# the fixture
# ---------------------------------------------------------------------------

def _body(raw: str) -> tuple[bytes, str, str]:
    blob = raw.encode("utf-8")
    kind, sha, _ = normalize_body(blob, "application/json")
    return blob, kind, sha


def _headers(location: str | None = None, extra: dict[str, str | None] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "Location": location,
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE",
        "Access-Control-Allow-Headers": "content-type",
        "Access-Control-Expose-Headers": None,
        "Access-Control-Allow-Credentials": None,
        "Access-Control-Max-Age": None,
    }
    out.update(extra or {})
    return out


def scenarios_of(spec: dict[str, str]) -> list[dict[str, Any]]:
    """Six scenarios: a create with effects, an invalid create, a delete, a
    read whose first response is a redirect, and two the source did not
    demonstrate (one FAIL, one INCONCLUSIVE)."""
    r, route, pkg = spec["res"], spec["route"], spec["pkg"]
    api = "%s.%s.%s" % (pkg, spec["sub"], spec["type"])
    root_api = "%s.%s.%s" % (pkg, spec["sub2"], spec["root_type"])
    bodies = "verification/scenarios/bodies"
    return [
        {"id": "sc:create-%s" % r, "entry_point": "ep:%s#create(%sFields):http" % (api, spec["type"]),
         "method": "POST", "path": route, "headers": {"Content-Type": "application/json"},
         "body_file": "%s/create-%s.json" % (bodies, r), "reset_before": True,
         "effects": [{"id": "eff:%s-7" % r, "method": "GET", "path": "%s/7" % route}], "normalization": []},
        {"id": "sc:create-invalid-%s-name" % r, "entry_point": "ep:%s#create(%sFields):http" % (api, spec["type"]),
         "method": "POST", "path": route, "headers": {"Content-Type": "application/json"},
         "body_file": "%s/create-invalid-%s.json" % (bodies, r), "reset_before": True,
         "effects": [{"id": "eff:%s-99-absent" % r, "method": "GET", "path": "%s/99" % route}], "normalization": []},
        {"id": "sc:delete-%s-3" % r, "entry_point": "ep:%s#remove(int):http" % api,
         "method": "DELETE", "path": "%s/3" % route, "body_absent": True, "reset_before": True,
         "effects": [{"id": "eff:%s-3-gone" % r, "method": "GET", "path": "%s/3" % route}], "normalization": []},
        {"id": "sc:read-%s-root" % r, "entry_point": "ep:%s#enter():http" % root_api,
         "method": "GET", "path": "/", "body_absent": True, "reset_before": False,
         "effects": [], "normalization": []},
        {"id": "sc:update-%s-1" % r, "entry_point": "ep:%s#update(int,%sFields):http" % (api, spec["type"]),
         "method": "PUT", "path": "%s/1" % route, "headers": {"Content-Type": "application/json"},
         "body_file": "%s/update-%s.json" % (bodies, r), "reset_before": True,
         "effects": [{"id": "eff:%s-1" % r, "method": "GET", "path": "%s/1" % route}], "normalization": []},
        {"id": "sc:read-%s-list" % r, "entry_point": "ep:%s#list():http" % api,
         "method": "GET", "path": route, "body_absent": True, "reset_before": True,
         "effects": [], "normalization": []},
    ]


def write_decisions(root: Path, *, profiles: list[str] | None = None, switch: dict[str, str] | None = None) -> None:
    """decisions.yaml for the renamed specimen, plus the schema the loader
    validates against. What the m4-parity block pins comes from HERE, so a
    fixture that declares other names is the whole control."""
    sys.path.insert(0, str(HERE.parents[3] / "lib"))
    from planner.specimens import decisions_yaml, full_decisions  # noqa: PLC0415

    golden_planning = HERE.parents[4] / ".hermes" / "planning"
    shutil.copytree(golden_planning, root / ".hermes" / "planning", dirs_exist_ok=True)
    doc = full_decisions()
    if profiles:
        doc["build_profiles"] = {"adr": "ADR-001", "active": list(profiles)}
    if switch:
        doc["security"] = {"adr": "ADR-001", "switch": dict(switch),
                           "identities": [{"name": "seeded-keeper", "credential_ref": "ACME_KEEPER_CRED", "roles": ["keeper"]}]}
    (root / "decisions.yaml").write_text(decisions_yaml(doc), encoding="utf-8")


def build_root(root: Path, spec: dict[str, str], *, derived: bool = True, authenticated: bool = False,
               pom: str = POM_FIXTURE) -> Path:
    """A destination tree carrying exactly what this producer reads."""
    r, route = spec["res"], spec["route"]
    root.mkdir(parents=True, exist_ok=True)
    (root / RESET_SCRIPT).parent.mkdir(parents=True, exist_ok=True)
    (root / RESET_SCRIPT).write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (root / "pom.xml").write_text(pom, encoding="utf-8")

    scenarios = scenarios_of(spec)
    if authenticated:
        for sc in scenarios:
            sc["identity"] = {"kind": "basic", "user_env": "APP_USER", "password_env": "APP_PASSWORD"}

    bodies = {
        "create-%s.json" % r: '{"name": "%s-one", "tier": 2}' % r,
        "create-invalid-%s.json" % r: '{"name": "", "tier": 2}',
        "update-%s.json" % r: '{"name": "%s-two", "tier": 3}' % r,
    }
    bdir = root / "verification" / "scenarios" / "bodies"
    bdir.mkdir(parents=True, exist_ok=True)
    for name, text in bodies.items():
        (bdir / name).write_text(text, encoding="utf-8")

    bundle = {"schema": "rhoai3.evidence-bundle/v1", "source": {"digest": sha256_bytes(spec["pkg"].encode())},
              "entry_points": [{"id": sc["entry_point"], "kind": "http"} for sc in scenarios]}
    write_canonical(root / "evidence" / "planning" / "evidence-bundle.json", bundle)
    bundle_sha = digest(bundle)

    corpus: dict[str, Any] = {
        "schema": "rhoai3.scenario-corpus/v1",
        "initial_state": {"reset": "%s --root ." % RESET_SCRIPT.as_posix(), "dataset": "the seeded dataset"},
        "scenarios": scenarios,
    }
    if derived:
        corpus["derived_from"] = {"producer": "derive-source-scenarios.py", "evidence_bundle_sha256": bundle_sha}
    else:
        corpus["approved_by"] = "operator:fixture"
    corpus_p = root / "verification" / "scenarios" / "corpus.json"
    write_canonical(corpus_p, corpus)
    corpus = load_json(corpus_p)
    corpus_sha = corpus_digest(corpus)
    if derived:
        write_canonical(root / "verification" / "scenarios" / "_derive.json", {
            "schema": "rhoai3.scenario-derivation/v1", "status": "ok",
            "corpus_sha256": corpus_sha, "evidence_bundle_sha256": bundle_sha,
            "bodies": {"%s/%s" % ("verification/scenarios/bodies", n): sha256_bytes((bdir / n).read_bytes()) for n in bodies},
            "requests": {str(sc["id"]): request_of(root, sc)["request_sha256"] for sc in scenarios},
        })

    ok_body, ok_kind, ok_sha = _body('{"id": 7, "name": "%s-one", "tier": 2}' % r)
    absent_body, absent_kind, absent_sha = _body('{"error": "absent"}')
    invalid_body, invalid_kind, invalid_sha = _body('{"errors": [{"field": "name"}]}')
    item_body, item_kind, item_sha = _body('{"id": 3, "name": "%s-three", "tier": 1}' % r)
    empty_sha = hashlib.sha256(b"").hexdigest()

    captures: dict[str, dict[str, Any]] = {
        "sc:create-%s" % r: {
            "before": [{"id": "eff:%s-7" % r, "method": "GET", "path": "%s/7" % route, "status": 404,
                        "body_kind": absent_kind, "body_sha256": absent_sha}],
            "response": {"status": 201, "body_kind": ok_kind, "body_sha256": ok_sha,
                         "headers": _headers("%s%s/7" % (SOURCE_BASE, route))},
            "effects": [{"id": "eff:%s-7" % r, "method": "GET", "path": "%s/7" % route, "status": 200,
                         "body_kind": ok_kind, "body_sha256": ok_sha}],
        },
        "sc:create-invalid-%s-name" % r: {
            "before": [{"id": "eff:%s-99-absent" % r, "method": "GET", "path": "%s/99" % route, "status": 404,
                        "body_kind": absent_kind, "body_sha256": absent_sha}],
            "response": {"status": 400, "body_kind": invalid_kind, "body_sha256": invalid_sha,
                         "headers": _headers(None, {"errors": '[{"field":"name"}]'})},
            "effects": [{"id": "eff:%s-99-absent" % r, "method": "GET", "path": "%s/99" % route, "status": 404,
                         "body_kind": absent_kind, "body_sha256": absent_sha}],
        },
        "sc:delete-%s-3" % r: {
            "before": [{"id": "eff:%s-3-gone" % r, "method": "GET", "path": "%s/3" % route, "status": 200,
                        "body_kind": item_kind, "body_sha256": item_sha}],
            "response": {"status": 204, "body_kind": "bytes", "body_sha256": empty_sha, "headers": _headers()},
            "effects": [{"id": "eff:%s-3-gone" % r, "method": "GET", "path": "%s/3" % route, "status": 404,
                         "body_kind": absent_kind, "body_sha256": absent_sha}],
        },
        "sc:read-%s-root" % r: {
            "before": [],
            "response": {"status": 302, "body_kind": "bytes", "body_sha256": empty_sha,
                         "headers": _headers("%s/swagger-ui/index.html" % SOURCE_BASE)},
            "effects": [],
        },
        "sc:update-%s-1" % r: {
            "before": [{"id": "eff:%s-1" % r, "method": "GET", "path": "%s/1" % route, "status": 200,
                        "body_kind": item_kind, "body_sha256": item_sha}],
            "response": {"status": 500, "body_kind": "text", "body_sha256": empty_sha, "headers": _headers()},
            "effects": [{"id": "eff:%s-1" % r, "method": "GET", "path": "%s/1" % route, "status": 200,
                         "body_kind": item_kind, "body_sha256": item_sha}],
        },
        "sc:read-%s-list" % r: {
            "before": [],
            "response": {"status": 200, "body_kind": ok_kind, "body_sha256": ok_sha, "headers": _headers()},
            "effects": [],
        },
    }
    verdicts = {
        "sc:create-%s" % r: ("PASS", "positive", ""),
        "sc:create-invalid-%s-name" % r: ("PASS", "negative", ""),
        "sc:delete-%s-3" % r: ("PASS", "positive", ""),
        "sc:read-%s-root" % r: ("PASS", "positive", ""),
        "sc:update-%s-1" % r: ("FAIL", "positive", "expect_status: the source answered 500"),
        "sc:read-%s-list" % r: ("INCONCLUSIVE", "positive", "collection identity not derivable"),
    }

    records: dict[str, Any] = {}
    for sc in scenarios:
        sid = str(sc["id"])
        shape = captures[sid]
        rec = {
            "schema": "rhoai3.source-scenario/v1", "scenario": sid, "entry_point": sc["entry_point"],
            "receipt_sha256": "", "evidence_bundle_sha256": bundle_sha, "corpus_sha256": corpus_sha,
            "source": {"analysis_copy_digest": bundle_sha, "base_url": SOURCE_BASE},
            "initial_state": corpus["initial_state"], "normalization": [],
            "asserted_headers_extra": ["errors"],
            "reset_before": bool(sc.get("reset_before", True)),
            "status": "CAPTURED", "reason": "",
            "request": {k: request_of(root, sc)[k] for k in ("method", "path", "headers", "identity", "body_sha256",
                                                             "body_absent", "request_sha256")},
            "response": shape["response"], "before": shape["before"], "effects": shape["effects"],
        }
        out = root / SCENARIO_ORACLES / (scenario_slug(sid) + ".json")
        write_canonical(out, rec)
        capability, intent, reason = verdicts[sid]
        records[sid] = {
            "verdict": capability, "capability": capability, "intent": intent,
            "evidence": {"status": "USABLE" if capability != "INCONCLUSIVE" else "UNUSABLE", "reasons": []},
            "known_failures": [], "reason": reason, "checks": [],
            "capture_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
            "request_sha256": rec["request"]["request_sha256"],
            "evidence_bundle_sha256": bundle_sha, "corpus_sha256": corpus_sha,
        }
    write_canonical(root / SCENARIO_ORACLES / "_capture.json", {
        "schema": "rhoai3.source-capture/v1", "producer": "capture-source-scenarios.py", "status": "ok",
        "reason": "", "evidence_bundle_sha256": bundle_sha, "corpus_sha256": corpus_sha,
        "captured": len(scenarios), "requested": len(scenarios),
        "scenarios": sorted(str(sc["id"]) for sc in scenarios), "reads": True,
        "source": {"analysis_copy_digest": bundle_sha, "starts": 1},
    })
    write_canonical(root / SCENARIO_ORACLES / "_qualification.json", {
        "schema": "rhoai3.scenario-qualification/v1", "producer": "qualify-source-captures.py",
        "corpus_sha256": corpus_sha, "evidence_bundle_sha256": bundle_sha,
        "scenarios": records, "total": len(records),
        "not_passed": sum(1 for v in records.values() if v["capability"] != "PASS"),
        "verdict": "FAIL",
    })
    return root


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------

def case_accounting(tmp: Path) -> int:
    root = build_root(tmp / "accounting", SPEC_A)
    proc = run(root)
    if proc.returncode != 0:
        return fail("generation refused a bound fixture: %s%s" % (proc.stdout, proc.stderr))
    manifest = load_json(root / MANIFEST)
    if manifest.get("schema") != "rhoai3.generated-tests/v1":
        return fail("the manifest must carry the schema the floor consumes: %r" % manifest.get("schema"))
    cases = manifest["cases"]
    gaps = manifest["gaps"]
    if len(cases) != 4:
        return fail("one case per PASS scenario; got %d: %s" % (len(cases), [c["scenario"] for c in cases]))
    if sorted(g["scenario"] for g in gaps) != ["sc:read-alpha-list", "sc:update-alpha-1"]:
        return fail("every unqualified scenario must be a named gap; got %s" % [g["scenario"] for g in gaps])
    if not all(g["reason"] for g in gaps):
        return fail("a gap must carry the qualification's own reason: %s" % gaps)
    if len(cases) + len(gaps) != 6:
        return fail("the manifest must account for every scenario the corpus names")
    for key in ("evidence_bundle_sha256", "source_digest", "qualification_sha256", "security_mode",
                "generator_version", "reset_contract", "corpus_sha256"):
        if not manifest.get(key):
            return fail("the manifest must record %s (ADR-015 complete binding)" % key)
    if manifest["reset_contract"]["transactional"] is not False:
        return fail("the reset contract must state that a test transaction is not the reset")
    for case in cases:
        for key in ("scenario", "class", "method", "entry_point"):
            if not case.get(key):
                return fail("case %s has no %s; the floor consumes those four" % (case.get("scenario"), key))
        if not case["entry_point"].startswith("ep:"):
            return fail("a case must be linked to its entry point: %s" % case)

    # one test method per case, in the class the manifest names
    by_class: dict[str, list[dict]] = {}
    for case in cases:
        by_class.setdefault(case["class"], []).append(case)
    if sorted(by_class) != ["alpha.one.alpha.generated.AlphaResourceParityTest",
                            "alpha.one.entrance.generated.EntranceResourceParityTest"]:
        return fail("the class is the entry point's declaring type in its own .generated package: %s" % sorted(by_class))
    for fqcn, group in by_class.items():
        src = root / "src/parity-test/java" / (fqcn.replace(".", "/") + ".java")
        if not src.is_file():
            return fail("no source for the class the manifest names: %s" % fqcn)
        text = src.read_text(encoding="utf-8")
        for case in group:
            if ("void %s()" % case["method"]) not in text:
                return fail("%s does not declare %s" % (fqcn, case["method"]))
            if case["scenario"] not in text:
                return fail("%s does not name scenario %s" % (fqcn, case["scenario"]))
        if "@Transactional" in text:
            return fail("a test transaction does not roll back an HTTP write; %s must not use one" % fqcn)
        if "redirects().follow(false)" not in text:
            return fail("the first response is the observation; %s must not follow redirects" % fqcn)
        if "Mock" in text or "mock(" in text:
            return fail("%s must call the real application, not a substitute" % fqcn)
        if "@BeforeEach" not in text or "resetAndVerify" not in text:
            return fail("%s must reset and PROVE the recorded initial state before each case" % fqcn)

    # the recorded body bytes travel with the tests, bound by digest
    body = root / "src/parity-test/resources/generated/sc_create-alpha.body"
    if not body.is_file():
        return fail("the recorded request body must be copied beside the tests")
    listed = {row["path"]: row["sha256"] for row in manifest["files"]}
    if listed.get("src/parity-test/resources/generated/sc_create-alpha.body") != hashlib.sha256(body.read_bytes()).hexdigest():
        return fail("every generated file is listed with its digest: %s" % sorted(listed))
    if not any(p.endswith("ParitySupport.java") for p in listed):
        return fail("the shared support class must be generated and listed")

    # the source's values, not the destination's
    create = next(c for c in cases if c["scenario"] == "sc:create-alpha")
    text = (root / "src/parity-test/java/alpha/one/alpha/generated/AlphaResourceParityTest.java").read_text(encoding="utf-8")
    if "statusCode(201)" not in text:
        return fail("the recorded status is the assertion: %s" % create)
    if "%s/api/alphas/7" % SOURCE_BASE not in text:
        return fail("Location is asserted as recorded and mapped by origin at run time, never normalized")
    if create["required_headers"] != ["Location"]:
        return fail("a 201 requires Location coverage: %s" % create["required_headers"])
    if create["effects"] != ["eff:alpha-7"]:
        return fail("the declared effect is read back: %s" % create)
    return 0


def case_deterministic(tmp: Path) -> int:
    root = build_root(tmp / "deterministic", SPEC_A)
    if run(root).returncode != 0:
        return fail("first generation refused")
    first = _snapshot(root)
    if run(root).returncode != 0:
        return fail("second generation refused")
    second = _snapshot(root)
    if first != second:
        differing = sorted(set(first) ^ set(second)) or [k for k in first if first[k] != second.get(k)]
        return fail("generation is not deterministic; differing: %s" % differing[:5])
    for rel, text in first.items():
        if rel.endswith(".java") and re.search(r"\d{4}-\d{2}-\d{2}", text):
            return fail("%s carries a date; generated Java must not" % rel)
    return 0


def _snapshot(root: Path) -> dict[str, str]:
    out: dict[str, str] = {"pom.xml": (root / "pom.xml").read_text(encoding="utf-8")}
    for base in ("src/parity-test/java", "src/parity-test/resources", "evidence/tests"):
        d = root / base
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file():
                out[p.relative_to(root).as_posix()] = p.read_text(encoding="utf-8")
    return out


def case_pom_profile(tmp: Path) -> int:
    """The generated tests run in the M4 phase and nowhere else: they are
    written outside the loop's test roots, and the only thing that compiles
    them is the marked m4-parity block this producer owns in pom.xml."""
    rc = 0
    root = build_root(tmp / "pom", SPEC_A)
    proc = run(root)
    if proc.returncode != 0:
        return fail("generation refused a bound fixture: %s%s" % (proc.stdout, proc.stderr))
    pom = (root / "pom.xml").read_text(encoding="utf-8")
    for needle in ("<!-- rhoai3:generated-tests:begin -->", "<!-- rhoai3:generated-tests:end -->",
                   "<id>m4-parity</id>", "build-helper-maven-plugin", "add-test-source", "add-test-resource",
                   "<phase>generate-test-sources</phase>", "<phase>generate-test-resources</phase>",
                   "<source>src/parity-test/java</source>", "<directory>src/parity-test/resources</directory>"):
        if needle not in pom:
            rc |= fail("the pom block must carry %r: %s" % (needle, pom))
    if pom.count("<id>m4-parity</id>") != 1:
        rc |= fail("exactly one m4-parity profile: %s" % pom)
    # the plugin is pinned, because the BOM probe measures dependencyManagement
    # and never manages a build plugin
    if "<version>3.6.0</version>" not in pom:
        rc |= fail("the plugin must be pinned to a version the BOM does not manage: %s" % pom)
    try:
        ET.fromstring(pom)
    except ET.ParseError as exc:
        rc |= fail("the rewritten pom must stay parseable XML: %s" % exc)

    manifest = load_json(root / MANIFEST)
    body = pom[pom.index("<!-- rhoai3:generated-tests:begin -->"):
               pom.index("<!-- rhoai3:generated-tests:end -->") + len("<!-- rhoai3:generated-tests:end -->")]
    if manifest.get("pom_profile_sha256") != hashlib.sha256(body.encode("utf-8")).hexdigest():
        rc |= fail("the manifest must bind the block on disk: %s" % manifest.get("pom_profile_sha256"))
    pin = (manifest.get("pom_profile") or {}).get("plugin") or {}
    if pin.get("artifact_id") != "build-helper-maven-plugin" or pin.get("version") != "3.6.0":
        rc |= fail("the manifest must record the plugin pin and why: %s" % pin)
    if (manifest.get("pom_profile") or {}).get("test_source") != "src/parity-test/java":
        rc |= fail("the manifest must record the source root the profile adds: %s" % manifest.get("pom_profile"))

    # a re-run replaces exactly that block, and only it
    if run(root).returncode != 0:
        rc |= fail("a second generation refused")
    if (root / "pom.xml").read_text(encoding="utf-8") != pom:
        rc |= fail("the pom edit must be idempotent")

    # --check is the floor's question: the block is present and unchanged
    if run(root, "--check").returncode != 0:
        rc |= fail("--check must accept the block the generator just wrote")
    (root / "pom.xml").write_text(pom.replace("<source>src/parity-test/java</source>",
                                              "<source>src/test/java</source>"), encoding="utf-8")
    proc = run(root, "--check")
    if proc.returncode == 0 or "m4-parity block" not in proc.stderr:
        rc |= fail("--check must refuse an edited block: %s%s" % (proc.stdout, proc.stderr))
    (root / "pom.xml").write_text(pom.replace(body, ""), encoding="utf-8")
    proc = run(root, "--check")
    if proc.returncode == 0 or "carries no" not in proc.stderr:
        rc |= fail("--check must refuse a pom whose profile is gone: %s%s" % (proc.stdout, proc.stderr))
    (root / "pom.xml").write_text(pom, encoding="utf-8")
    if run(root, "--check").returncode != 0:
        rc |= fail("--check must accept the restored pom")

    # a profile this producer does not own is never taken over
    foreign = build_root(tmp / "pom-foreign", SPEC_A)
    (foreign / "pom.xml").write_text(POM_FIXTURE.replace(
        "</project>", "  <profiles>\n    <profile>\n      <id>m4-parity</id>\n    </profile>\n  </profiles>\n</project>"),
        encoding="utf-8")
    proc = run(foreign)
    if proc.returncode == 0 or "outside the" not in proc.stderr:
        rc |= fail("an m4-parity profile outside the markers must refuse: %s%s" % (proc.stdout, proc.stderr))

    # an existing <profiles> is extended, not replaced
    other = build_root(tmp / "pom-profiles", SPEC_A)
    (other / "pom.xml").write_text(POM_FIXTURE.replace(
        "</project>", "  <profiles>\n    <profile>\n      <id>native</id>\n    </profile>\n  </profiles>\n</project>"),
        encoding="utf-8")
    if run(other).returncode != 0:
        rc |= fail("a pom with its own <profiles> must be extended")
    text = (other / "pom.xml").read_text(encoding="utf-8")
    if "<id>native</id>" not in text or "<id>m4-parity</id>" not in text or text.count("<profiles>") != 1:
        rc |= fail("the existing profiles must survive and only one <profiles> may exist: %s" % text)

    # the phase rule, as a refusal: never the roots the M3 loop compiles
    for flag, value in (("--out", "src/test/java"), ("--resources", "src/test/resources")):
        proc = run(build_root(tmp / ("pom-loop-root" + flag.strip("-")), SPEC_A), flag, value)
        if proc.returncode == 0 or "M3 loop's test roots" not in proc.stderr:
            rc |= fail("%s %s must refuse: %s%s" % (flag, value, proc.stdout, proc.stderr))

    # no pom, no profile, no run: a refusal, not a silent generation
    nopom = build_root(tmp / "pom-missing", SPEC_A)
    (nopom / "pom.xml").unlink()
    proc = run(nopom)
    if proc.returncode == 0 or "no pom.xml" not in proc.stderr:
        rc |= fail("a tree with no pom.xml must refuse: %s%s" % (proc.stdout, proc.stderr))
    return rc


def case_check(tmp: Path) -> int:
    root = build_root(tmp / "check", SPEC_A)
    if run(root).returncode != 0:
        return fail("generation refused")
    proc = run(root, "--check")
    if proc.returncode != 0:
        return fail("--check must agree with what the generator just wrote: %s%s" % (proc.stdout, proc.stderr))

    target = root / "src/parity-test/java/alpha/one/alpha/generated/AlphaResourceParityTest.java"
    original = target.read_text(encoding="utf-8")
    target.write_text(original.replace("statusCode(201)", "statusCode(200)"), encoding="utf-8")
    proc = run(root, "--check")
    if proc.returncode == 0:
        return fail("--check accepted a weakened expectation")
    if "REFUSE: GENERATE_TESTS" not in proc.stderr:
        return fail("--check must refuse in the gate's own vocabulary: %s" % proc.stderr)
    target.write_text(original, encoding="utf-8")
    if run(root, "--check").returncode != 0:
        return fail("--check must accept the restored file")

    added = target.parent / "WorkerAddedParityTest.java"
    added.write_text("package alpha.one.alpha.generated;\npublic class WorkerAddedParityTest {}\n", encoding="utf-8")
    if run(root, "--check").returncode == 0:
        return fail("--check accepted an unlisted file in the generated package")
    added.unlink()

    (root / MANIFEST).unlink()
    proc = run(root, "--check")
    if proc.returncode == 0 or "never generated" not in proc.stderr:
        return fail("--check with no manifest must refuse and say so: %s" % proc.stderr)
    return 0


def case_refusals(tmp: Path) -> int:
    rc = 0
    root = build_root(tmp / "refuse-unbound", SPEC_A, derived=False)
    (root / "verification" / "scenarios" / "corpus.json").write_text(
        json.dumps({"schema": "rhoai3.scenario-corpus/v1", "scenarios": []}), encoding="utf-8")
    proc = run(root)
    if proc.returncode == 0 or "neither derived" not in proc.stderr:
        rc = fail("a corpus with no provenance must refuse: %s%s" % (proc.stdout, proc.stderr))

    root = build_root(tmp / "refuse-noqual", SPEC_A)
    (root / SCENARIO_ORACLES / "_qualification.json").unlink()
    proc = run(root)
    if proc.returncode == 0 or "qualify-source-captures" not in proc.stderr:
        rc = fail("unqualified captures must refuse: %s%s" % (proc.stdout, proc.stderr))

    root = build_root(tmp / "refuse-nocapture", SPEC_A)
    (root / SCENARIO_ORACLES / "_capture.json").unlink()
    proc = run(root)
    if proc.returncode == 0 or "never asked" not in proc.stderr:
        rc = fail("a missing capture receipt must refuse: %s%s" % (proc.stdout, proc.stderr))

    root = build_root(tmp / "refuse-stale", SPEC_A)
    p = root / SCENARIO_ORACLES / ("%s.json" % scenario_slug("sc:create-alpha"))
    doc = load_json(p)
    doc["response"]["status"] = 500
    write_canonical(p, doc)
    proc = run(root)
    if proc.returncode == 0 or "requalify after recapture" not in proc.stderr:
        rc = fail("a qualification that no longer judges the capture on disk must refuse: %s%s" % (proc.stdout, proc.stderr))

    root = build_root(tmp / "refuse-crosscorpus", SPEC_A)
    q = root / SCENARIO_ORACLES / "_qualification.json"
    doc = load_json(q)
    doc["corpus_sha256"] = "0" * 64
    write_canonical(q, doc)
    proc = run(root)
    if proc.returncode == 0 or "requalify the captures" not in proc.stderr:
        rc = fail("a qualification of another corpus must refuse: %s%s" % (proc.stdout, proc.stderr))

    root = build_root(tmp / "refuse-noreset", SPEC_A)
    (root / RESET_SCRIPT).unlink()
    proc = run(root)
    if proc.returncode == 0 or "reset contract" not in proc.stderr:
        rc = fail("a tree with no reset contract must refuse: %s%s" % (proc.stdout, proc.stderr))
    return rc


def case_security_mode(tmp: Path) -> int:
    root = build_root(tmp / "security-off", SPEC_A, authenticated=True)
    if run(root).returncode != 0:
        return fail("generation refused an authenticating fixture")
    manifest = load_json(root / MANIFEST)
    if manifest["cases"]:
        return fail("with --security-mode disabled an authenticating scenario cannot be replayed faithfully")
    if not all(g["kind"] == "security-mode" for g in manifest["gaps"] if g["capability"] == "PASS"):
        return fail("the reason must be named, not silent: %s" % manifest["gaps"])

    root = build_root(tmp / "security-on", SPEC_A, authenticated=True)
    if run(root, "--security-mode", "enabled").returncode != 0:
        return fail("generation refused with --security-mode enabled")
    manifest = load_json(root / MANIFEST)
    if len(manifest["cases"]) != 4:
        return fail("with credentials by reference every qualified scenario is generated: %s" % len(manifest["cases"]))
    if manifest["security_mode"] != "enabled":
        return fail("the manifest must record the security mode")
    refs = sorted({ref for c in manifest["cases"] for ref in c["credential_references"]})
    if refs != ["APP_PASSWORD", "APP_USER"]:
        return fail("the credential REFERENCES belong in the manifest: %s" % refs)
    text = (root / "src/parity-test/java/alpha/one/alpha/generated/AlphaResourceParityTest.java").read_text(encoding="utf-8")
    if "credential(\"APP_PASSWORD\")" not in text:
        return fail("the generated request must resolve credentials by reference")
    for secret in ("password=", "Basic ", "hunter2", ":admin"):
        if secret in text:
            return fail("a generated test must never carry a literal credential (%r)" % secret)
    return 0


def case_renamed_specimen(tmp: Path) -> int:
    a = build_root(tmp / "specimen-a", SPEC_A)
    b = build_root(tmp / "specimen-b", SPEC_B)
    if run(a).returncode != 0 or run(b).returncode != 0:
        return fail("generation refused one of the two specimens")
    left = {_rename(k): _rename(v) for k, v in _snapshot(a).items()}
    right = {_rename(k): _rename(v) for k, v in _snapshot(b).items()}
    if sorted(left) != sorted(right):
        return fail("a renamed specimen produced a different file set: %s vs %s" % (sorted(left), sorted(right)))
    for rel in sorted(left):
        if left[rel] != right[rel]:
            diff = [(i, x, y) for i, (x, y) in enumerate(zip(left[rel].splitlines(), right[rel].splitlines())) if x != y]
            return fail("a renamed specimen produced different %s: %s" % (rel, diff[:3]))
    return 0


_RENAMES = [("beta.two", "alpha.one"), ("beta/two", "alpha/one"), ("doorway", "entrance"), ("Doorway", "Entrance"),
            ("BetaResource", "AlphaResource"), ("betas", "alphas"), ("Beta", "Alpha"), ("beta", "alpha")]


def _rename(text: str) -> str:
    for old, new in _RENAMES:
        text = text.replace(old, new)
    return SHA_RE.sub("<sha256>", text)


def case_no_specimen_literal(tmp: Path) -> int:
    forbidden = ("petclinic", "PetClinic", "Franklin", "OwnerController", "/api/owners", "ownerId", "/api/pets", "/api/vets")
    rc = 0
    # The block writer and the commit step are this capability too: a specimen
    # literal in either is the same defect in a different file.
    for name in ("generate-product-tests.py", "parity_pom.py", "commit-generated-tests.py"):
        source = (HERE / name).read_text(encoding="utf-8")
        hit = [token for token in forbidden if token in source]
        if hit:
            rc |= fail("%s must be derived from the contract, never from a specimen: %s" % (name, hit))
    return rc


def case_java_plausible(tmp: Path) -> int:
    root = build_root(tmp / "plausible", SPEC_A)
    if run(root).returncode != 0:
        return fail("generation refused")
    manifest = load_json(root / MANIFEST)
    sources = [root / row["path"] for row in manifest["files"] if row["path"].endswith(".java")]
    if not sources:
        return fail("nothing generated")
    for src in sources:
        text = src.read_text(encoding="utf-8")
        if not text.startswith("// Generated by generate-product-tests.py"):
            return fail("%s must name its generator in a header comment" % src.name)
        if manifest["corpus_sha256"] not in text.splitlines()[2]:
            return fail("%s must name the corpus digest it was generated from" % src.name)
        code = _strip_literals(text)
        if code.count("{") != code.count("}"):
            return fail("%s has unbalanced braces (%d/%d)" % (src.name, code.count("{"), code.count("}")))
        if code.count("(") != code.count(")"):
            return fail("%s has unbalanced parentheses (%d/%d)" % (src.name, code.count("("), code.count(")")))
    tests = [s for s in sources if s.name.endswith("ParityTest.java")]
    for src in tests:
        text = src.read_text(encoding="utf-8")
        for needle in ("@QuarkusTest", "given()", ".when()", ".then()", "statusCode("):
            if needle not in text:
                return fail("%s does not read as a REST Assured @QuarkusTest: missing %r" % (src.name, needle))
    return case_javac(root, sources)


def _strip_literals(text: str) -> str:
    """Java with its comments, string and character literals removed, so a
    brace inside a message is not read as code."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            i = text.find("\n", i)
            if i < 0:
                break
        elif ch == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
        elif ch in ('"', "'"):
            quote = ch
            i += 1
            while i < n and text[i] != quote:
                i += 2 if text[i] == "\\" else 1
            i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


STUBS: dict[str, str] = {
    "io/quarkus/test/junit/QuarkusTest.java":
        "package io.quarkus.test.junit;\npublic @interface QuarkusTest {}\n",
    "org/junit/jupiter/api/Test.java":
        "package org.junit.jupiter.api;\npublic @interface Test {}\n",
    "org/junit/jupiter/api/BeforeEach.java":
        "package org.junit.jupiter.api;\npublic @interface BeforeEach {}\n",
    "org/junit/jupiter/api/TestInfo.java":
        "package org.junit.jupiter.api;\n"
        "public interface TestInfo {\n"
        "    java.util.Optional<java.lang.reflect.Method> getTestMethod();\n"
        "}\n",
    "io/restassured/RestAssured.java":
        "package io.restassured;\n"
        "import io.restassured.specification.RequestSpecification;\n"
        "public class RestAssured {\n"
        "    public static String baseURI = \"http://localhost\";\n"
        "    public static int port = 8081;\n"
        "    public static String basePath = \"\";\n"
        "    public static RequestSpecification given() { return null; }\n"
        "}\n",
    "io/restassured/specification/RequestSpecification.java":
        "package io.restassured.specification;\n"
        "public interface RequestSpecification {\n"
        "    RedirectSpecification redirects();\n"
        "    RequestSpecification header(String name, String value);\n"
        "    RequestSpecification body(byte[] body);\n"
        "    AuthenticationSpecification auth();\n"
        "    RequestSender when();\n"
        "}\n",
    "io/restassured/specification/RedirectSpecification.java":
        "package io.restassured.specification;\n"
        "public interface RedirectSpecification {\n"
        "    RequestSpecification follow(boolean follow);\n"
        "}\n",
    "io/restassured/specification/AuthenticationSpecification.java":
        "package io.restassured.specification;\n"
        "public interface AuthenticationSpecification {\n"
        "    PreemptiveAuthSpec preemptive();\n"
        "}\n",
    "io/restassured/specification/PreemptiveAuthSpec.java":
        "package io.restassured.specification;\n"
        "public interface PreemptiveAuthSpec {\n"
        "    RequestSpecification basic(String user, String password);\n"
        "}\n",
    "io/restassured/specification/RequestSender.java":
        "package io.restassured.specification;\n"
        "import io.restassured.response.Response;\n"
        "public interface RequestSender {\n"
        "    Response get(String path, Object... params);\n"
        "    Response post(String path, Object... params);\n"
        "    Response put(String path, Object... params);\n"
        "    Response patch(String path, Object... params);\n"
        "    Response delete(String path, Object... params);\n"
        "    Response head(String path, Object... params);\n"
        "    Response options(String path, Object... params);\n"
        "    Response request(String method, String path, Object... params);\n"
        "}\n",
    "io/restassured/response/Response.java":
        "package io.restassured.response;\n"
        "public interface Response {\n"
        "    ValidatableResponse then();\n"
        "    byte[] asByteArray();\n"
        "    String getHeader(String name);\n"
        "    int getStatusCode();\n"
        "}\n",
    "io/restassured/response/ValidatableResponse.java":
        "package io.restassured.response;\n"
        "public interface ValidatableResponse {\n"
        "    ValidatableResponse statusCode(int expected);\n"
        "    ExtractableResponse<Response> extract();\n"
        "}\n",
    "io/restassured/response/ExtractableResponse.java":
        "package io.restassured.response;\n"
        "public interface ExtractableResponse<T> {\n"
        "    T response();\n"
        "}\n",
}


def case_javac(root: Path, sources: list[Path]) -> int:
    """The generated Java is not merely plausible: javac parses and resolves it
    against compile-only stubs for @QuarkusTest, REST Assured and JUnit."""
    if shutil.which("javac") is None:
        print("SKIP: no javac on PATH; the generated Java was checked for shape only")
        return 0
    stub_dir = root / ".work" / "stubs"
    for rel, text in STUBS.items():
        p = stub_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    classes = root / ".work" / "classes"
    classes.mkdir(parents=True, exist_ok=True)
    argv = ["javac", "-proc:none", "-nowarn", "-d", str(classes),
            *[str(p) for p in sorted(stub_dir.rglob("*.java"))], *[str(p) for p in sorted(sources)]]
    proc = subprocess.run(argv, text=True, capture_output=True)
    if proc.returncode != 0:
        return fail("javac refused the generated sources:\n%s" % (proc.stdout + proc.stderr)[:3000])
    return 0


def case_canonical_form(tmp: Path) -> int:
    """The Java canonicaliser and the comparator's must agree, or a matching
    body would read as a diff. javac + java, or a clear skip."""
    if shutil.which("javac") is None or shutil.which("java") is None:
        print("SKIP: no JDK on PATH; the canonical body form was not cross-checked")
        return 0
    root = build_root(tmp / "canonical", SPEC_A)
    if run(root).returncode != 0:
        return fail("generation refused")
    manifest = load_json(root / MANIFEST)
    support = next(root / row["path"] for row in manifest["files"] if row["path"].endswith("ParitySupport.java"))
    package = manifest["support_class"].rsplit(".", 1)[0]
    samples = ['{"b":1,"a":[true,null,"x"]}', '{"n":12.5,"z":0.0001,"big":1e+30,"neg":-0.0}',
               '{"u":"caf\\u00e9 \\ud83d\\ude00","esc":"a\\"b\\\\c\\n"}', '[]', '"plain"', '17']
    driver_pkg_dir = support.parent
    driver = driver_pkg_dir / "CanonicalProbe.java"
    driver.write_text(
        "package %s;\n" % package +
        "import java.nio.charset.StandardCharsets;\n"
        "public class CanonicalProbe {\n"
        "    public static void main(String[] args) throws Exception {\n"
        "        for (String arg : args) {\n"
        "            byte[] raw = arg.getBytes(StandardCharsets.UTF_8);\n"
        "            String text = new String(raw, StandardCharsets.UTF_8);\n"
        "            StringBuilder out = new StringBuilder();\n"
        "            Object value = new ParitySupport.Json(text).parse();\n"
        "            java.lang.reflect.Method m = ParitySupport.class.getDeclaredMethod(\n"
        "                \"writeCanonical\", Object.class, StringBuilder.class);\n"
        "            m.setAccessible(true);\n"
        "            m.invoke(null, value, out);\n"
        "            out.append('\\n');\n"
        "            System.out.println(ParitySupport.sha256Hex(out.toString().getBytes(StandardCharsets.UTF_8)));\n"
        "        }\n"
        "    }\n"
        "}\n", encoding="utf-8")
    classes = root / ".work" / "canonical"
    classes.mkdir(parents=True, exist_ok=True)
    stub_dir = root / ".work" / "stubs"
    for rel, text in STUBS.items():
        p = stub_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    proc = subprocess.run(["javac", "-proc:none", "-nowarn", "-d", str(classes),
                           *[str(p) for p in sorted(stub_dir.rglob("*.java"))], str(support), str(driver)],
                          text=True, capture_output=True)
    if proc.returncode != 0:
        return fail("the canonical probe would not compile:\n%s" % (proc.stdout + proc.stderr)[:2000])
    proc = subprocess.run(["java", "-cp", str(classes), "%s.CanonicalProbe" % package, *samples],
                          text=True, capture_output=True)
    if proc.returncode != 0:
        return fail("the canonical probe would not run: %s" % (proc.stdout + proc.stderr)[:1000])
    got = proc.stdout.split()
    want = [sha256_bytes(canonical_bytes(json.loads(s))) for s in samples]
    if got != want:
        mismatched = [(s, g, w) for s, g, w in zip(samples, got, want) if g != w]
        return fail("the generated canonical form is not the comparator's: %s" % mismatched)
    driver.unlink()
    return 0


def _block_of(root: Path) -> str:
    pom = (root / "pom.xml").read_text(encoding="utf-8")
    begin, end = "<!-- rhoai3:generated-tests:begin -->", "<!-- rhoai3:generated-tests:end -->"
    return pom[pom.index(begin):pom.index(end) + len(end)]


def case_declared_pins(tmp: Path) -> int:
    """Measured on destination v9: the generated suite augmented with every
    profile-guarded bean @Vetoed, and once the profile reached the test JVM the
    frozen source's own test resources flipped the security switch and 17 of 18
    cases answered 401. Both values were DECLARED by the destination and
    neither reached surefire, so the block pins them.

    Every name asserted here comes from the fixture's decisions.yaml, never
    from the pilot: a producer that knew the specimen's profile names or its
    switch key would pass this case for the wrong reason."""
    rc = 0
    root = build_root(tmp / "pins", SPEC_A, pom=POM_FIXTURE_TESTCONFIG)
    write_decisions(root, profiles=FIXTURE_PROFILES, switch=FIXTURE_SWITCH)
    proc = run(root)
    if proc.returncode != 0:
        return fail("generation refused a fixture with decisions: %s%s" % (proc.stdout, proc.stderr))
    block = _block_of(root)

    want = ("<quarkus.test.profile>%s</quarkus.test.profile>" % ",".join(FIXTURE_PROFILES),
            "<%s>%s</%s>" % (FIXTURE_SWITCH["key"], FIXTURE_SWITCH["disabled_value"], FIXTURE_SWITCH["key"]))
    for needle in want:
        if needle not in block:
            rc |= fail("the block must pin %r: %s" % (needle, block))
    # the two pins are stated as what they are, not as test-only overrides
    if "NOT TEST-ONLY OVERRIDES" not in block:
        rc |= fail("the block must say the pins restate declared values: %s" % block)
    # what the base pom already sets is carried, never dropped
    for needle in ("<java.util.logging.manager>org.jboss.logmanager.LogManager</java.util.logging.manager>",
                   "<maven.home>${maven.home}</maven.home>"):
        if block.count(needle) != 2:
            rc |= fail("both test plugins must keep %r the base pom sets: %s" % (needle, block))
    if "<native.image.path>${project.build.directory}/runner</native.image.path>" not in block:
        rc |= fail("a property only failsafe sets must stay on failsafe: %s" % block)
    for artifact in ("maven-surefire-plugin", "maven-failsafe-plugin"):
        if "<artifactId>%s</artifactId>" % artifact not in block:
            rc |= fail("the profile must configure %s, which the base pom declares" % artifact)
    # and the base <build> is untouched: the pins live in the profile only
    base = (root / "pom.xml").read_text(encoding="utf-8").replace(block, "")
    if "quarkus.test.profile" in base or FIXTURE_SWITCH["key"] in base:
        rc |= fail("the pins must not be written into the base build: %s" % base)
    try:
        ET.fromstring((root / "pom.xml").read_text(encoding="utf-8"))
    except ET.ParseError as exc:
        rc |= fail("a pom carrying the pins must stay parseable XML: %s" % exc)

    manifest = load_json(root / MANIFEST)
    if manifest.get("security_mode_pinned") is not True:
        rc |= fail("the manifest must record that the mode is pinned: %s" % manifest.get("security_mode_pinned"))
    props = [(p["name"], p["value"])
             for row in manifest["pom_profile"]["test_plugins"] if row["artifact_id"] == "maven-surefire-plugin"
             for p in row["system_properties"]]
    if props[:2] != [("quarkus.test.profile", ",".join(FIXTURE_PROFILES)),
                     (FIXTURE_SWITCH["key"], FIXTURE_SWITCH["disabled_value"])]:
        rc |= fail("the manifest must record what the profile hands the test JVM: %s" % props)
    if manifest["pom_profile"]["pins"]["build_profiles"] != FIXTURE_PROFILES:
        rc |= fail("the manifest must name the decided profiles: %s" % manifest["pom_profile"]["pins"])

    # regeneration is idempotent, and --check accepts what was just written
    pom_now = (root / "pom.xml").read_text(encoding="utf-8")
    if run(root).returncode != 0 or (root / "pom.xml").read_text(encoding="utf-8") != pom_now:
        rc |= fail("a second generation must leave the pinned block byte-identical")
    if run(root, "--check").returncode != 0:
        rc |= fail("--check must accept the block the generator just wrote")

    # the mode is the one the suite was GENERATED for, not a default
    on = build_root(tmp / "pins-enabled", SPEC_A, authenticated=True, pom=POM_FIXTURE_TESTCONFIG)
    write_decisions(on, profiles=FIXTURE_PROFILES, switch=FIXTURE_SWITCH)
    if run(on, "--security-mode", "enabled").returncode != 0:
        rc |= fail("generation refused with --security-mode enabled")
    if ("<%s>%s</%s>" % (FIXTURE_SWITCH["key"], FIXTURE_SWITCH["enabled_value"], FIXTURE_SWITCH["key"])) not in _block_of(on):
        rc |= fail("the enabled-mode suite must pin the enabled setting: %s" % _block_of(on))

    # no security section: the switch is NOT pinned, and the manifest says so
    # rather than leaving the mode looking decided
    nosec = build_root(tmp / "pins-nosecurity", SPEC_A, pom=POM_FIXTURE_TESTCONFIG)
    write_decisions(nosec, profiles=FIXTURE_PROFILES)
    if run(nosec).returncode != 0:
        rc |= fail("generation refused a tree with no security section")
    nosec_block = _block_of(nosec)
    if FIXTURE_SWITCH["key"] in nosec_block:
        rc |= fail("an undeclared switch must not be pinned: %s" % nosec_block)
    if "<quarkus.test.profile>%s</quarkus.test.profile>" % ",".join(FIXTURE_PROFILES) not in nosec_block:
        rc |= fail("the profile pin does not depend on the security section: %s" % nosec_block)
    m2 = load_json(nosec / MANIFEST)
    if m2.get("security_mode_pinned") is not False:
        rc |= fail("the manifest must record that the mode is unpinned: %s" % m2.get("security_mode_pinned"))
    if not any("UNPINNED" in n for n in (m2.get("pin_notes") or [])):
        rc |= fail("the manifest must say WHY the mode is unpinned: %s" % m2.get("pin_notes"))

    # THE STALE BLOCK: bytes that match their own manifest and pin nothing.
    # The digest cannot see it -- a suite would run with the guards inactive
    # and the mode decided by the test classpath -- so the declaration is
    # asked, and --check refuses by name.
    stale = build_root(tmp / "pins-stale", SPEC_A, pom=POM_FIXTURE_TESTCONFIG)
    write_decisions(stale, profiles=FIXTURE_PROFILES, switch=FIXTURE_SWITCH)
    if run(stale).returncode != 0:
        rc |= fail("generation refused the stale-block fixture")
    old = build_root(tmp / "pins-old", SPEC_A, pom=POM_FIXTURE_TESTCONFIG)   # same tree, no decisions
    if run(old).returncode != 0:
        rc |= fail("generation refused the pre-pin fixture")
    old_block = _block_of(old)
    pom_text = (stale / "pom.xml").read_text(encoding="utf-8")
    (stale / "pom.xml").write_text(pom_text.replace(_block_of(stale), old_block), encoding="utf-8")
    m3 = load_json(stale / MANIFEST)
    m3["pom_profile_sha256"] = hashlib.sha256(old_block.encode("utf-8")).hexdigest()
    write_canonical(stale / MANIFEST, m3)
    proc = run(stale, "--check")
    if proc.returncode == 0:
        rc |= fail("--check accepted a block that pins neither declared value")
    elif "stale block: regenerate with --reapply-catalog" not in proc.stderr:
        rc |= fail("--check must refuse a stale block by name: %s" % proc.stderr)
    elif FIXTURE_SWITCH["key"] not in proc.stderr or ",".join(FIXTURE_PROFILES) not in proc.stderr:
        rc |= fail("the refusal must name the pins that are missing: %s" % proc.stderr)
    return rc


def main() -> int:
    cases = (case_accounting, case_deterministic, case_pom_profile, case_check, case_refusals, case_security_mode,
             case_declared_pins, case_renamed_specimen, case_no_specimen_literal, case_java_plausible,
             case_canonical_form)
    rc = 0
    with tempfile.TemporaryDirectory(prefix="generate-product-tests-") as td:
        tmp = Path(td)
        for case in cases:
            try:
                rc |= case(tmp)
            except Exception as exc:  # a case that cannot run is a failure, not a pass
                import traceback
                traceback.print_exc()
                rc |= fail("%s raised %s" % (case.__name__, exc))
    if rc:
        print("FAIL: generate-product-tests %d check(s) failed" % len(FAILURES), file=sys.stderr)
        return 1
    print("OK: generate-product-tests %d case(s)" % len(cases))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
