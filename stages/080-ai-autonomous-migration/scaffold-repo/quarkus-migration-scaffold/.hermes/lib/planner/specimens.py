"""Synthetic specimen builders for planner tests (test support, not dest).

Builds a destination tree with M1 producer outputs and a fake frozen
legacy tree (pom, properties, stub sources) so the v3 chain — bundle,
bootstrap, verify, work list, admission, K4/K3 — runs without Java or
MTA. Two specimens:

- ``http``       Spring MVC + JPA (owners/pets share entities; vets separate)
- ``scheduled``  no HTTP: a @Scheduled job and a @KafkaListener

Everything is deterministic; builders take an ``order`` seed only to
shuffle list order for the shuffle-invariance test.
"""
from __future__ import annotations

import hashlib
import json
import random
import shutil
from pathlib import Path
from typing import Any

from planner.canonical import load_json, canonical_bytes, sha256_bytes, write_canonical
from planner.paths import (
    BOM_MANAGED,
    MTA_FINDINGS,
    PRODUCERS_DIR,
    SOURCE_MANIFEST,
    STRUCTURE,
)

GOLDEN = Path(__file__).resolve().parents[3]

SPRING = "org.springframework"
A_REST = SPRING + ".web.bind.annotation.RestController"
A_REQ = SPRING + ".web.bind.annotation.RequestMapping"
A_GET = SPRING + ".web.bind.annotation.GetMapping"
A_POST = SPRING + ".web.bind.annotation.PostMapping"
A_AUTOWIRED = SPRING + ".beans.factory.annotation.Autowired"
A_SERVICE = SPRING + ".stereotype.Service"
A_ENTITY = "jakarta.persistence.Entity"
A_ADVICE = SPRING + ".web.bind.annotation.ControllerAdvice"
A_APP = SPRING + ".boot.autoconfigure.SpringBootApplication"
A_SCHED = SPRING + ".scheduling.annotation.Scheduled"
A_KAFKA = SPRING + ".kafka.annotation.KafkaListener"
A_PRIMARY = SPRING + ".context.annotation.Primary"
S_JPA = SPRING + ".data.jpa.repository.JpaRepository"

ACCEPTED_ADRS = [
    {"id": "ADR-001", "title": "Destination platform", "status": "accepted"},
    {"id": "ADR-002", "title": "Attempt threshold", "status": "accepted"},
    {"id": "ADR-003", "title": "Not-applicable incidents", "status": "accepted"},
]


def _t(fqn: str, path: str, *, kind: str = "class", annotations: list[dict[str, Any]] | None = None, supertypes: list[str] | None = None, fields: list[dict[str, Any]] | None = None, constructors: list[dict[str, Any]] | None = None, methods: list[dict[str, Any]] | None = None, refs: list[str] | None = None, modifiers: list[str] | None = None, resolution: str = "full") -> dict[str, Any]:
    return {
        "fqn": fqn,
        "path": path,
        "kind": kind,
        "modifiers": modifiers or ["public"],
        "resolution": resolution,
        "annotations": annotations or [],
        "supertypes": supertypes or [],
        "fields": fields or [],
        "constructors": constructors or [],
        "methods": methods or [],
        "type_refs": sorted(set(refs or [])),
    }


def _ann(fqn: str, **values: Any) -> dict[str, Any]:
    return {"fqn": fqn, "values": {k: v for k, v in values.items()}}


def _m(name: str, sig: str | None = None, *, annotations: list[dict[str, Any]] | None = None, refs: list[str] | None = None, returns: str = "void") -> dict[str, Any]:
    return {"name": name, "signature": sig or ("%s()" % name), "annotations": annotations or [], "params": [], "returns": returns, "type_refs": sorted(set(refs or [])), "calls": []}


def http_types(base: str) -> list[dict[str, Any]]:
    p = "src/main/java/" + base.replace(".", "/")
    owner = base + ".owner"
    pet = base + ".pet"
    vet = base + ".vet"
    return [
        _t(base + ".PetClinicApplication", p + "/PetClinicApplication.java", annotations=[_ann(A_APP)]),
        _t(base + ".web.GlobalExceptionHandler", p + "/web/GlobalExceptionHandler.java", annotations=[_ann(A_ADVICE)]),
        _t(owner + ".OwnerController", p + "/owner/OwnerController.java", annotations=[_ann(A_REST), _ann(A_REQ, value=["/api/owners"])], fields=[{"name": "service", "type": owner + ".OwnerService", "annotations": [_ann(A_AUTOWIRED)]}], methods=[_m("list", "list()", annotations=[_ann(A_GET)], refs=[owner + ".Owner"]), _m("create", "create(Owner)", annotations=[_ann(A_POST)], refs=[owner + ".Owner"])], refs=[owner + ".OwnerService", owner + ".Owner"]),
        _t(owner + ".OwnerService", p + "/owner/OwnerService.java", kind="interface", methods=[_m("findAll", returns="java.util.List")], refs=[owner + ".Owner"]),
        _t(owner + ".OwnerServiceImpl", p + "/owner/OwnerServiceImpl.java", annotations=[_ann(A_SERVICE)], supertypes=[owner + ".OwnerService"], fields=[{"name": "repo", "type": owner + ".OwnerRepository", "annotations": [_ann(A_AUTOWIRED)]}], methods=[_m("findAll", returns="java.util.List", refs=[owner + ".Owner"])], refs=[owner + ".OwnerRepository", owner + ".Owner", base + ".common.Money"]),
        _t(owner + ".OwnerRepository", p + "/owner/OwnerRepository.java", kind="interface", supertypes=[S_JPA], refs=[owner + ".Owner"]),
        _t(owner + ".Owner", p + "/owner/Owner.java", annotations=[_ann(A_ENTITY)], refs=[pet + ".Pet"]),
        _t(pet + ".PetController", p + "/pet/PetController.java", annotations=[_ann(A_REST), _ann(A_REQ, value=["/api/pets"])], constructors=[{"params": [{"name": "service", "type": pet + ".PetService"}], "annotations": []}], methods=[_m("list", "list()", annotations=[_ann(A_GET, value=["/"])], refs=[pet + ".Pet"])], refs=[pet + ".PetService", pet + ".Pet"]),
        _t(pet + ".PetService", p + "/pet/PetService.java", annotations=[_ann(A_SERVICE)], fields=[{"name": "repo", "type": pet + ".PetRepository", "annotations": [_ann(A_AUTOWIRED)]}], refs=[pet + ".PetRepository", pet + ".Pet", owner + ".Owner", base + ".common.Money"]),
        _t(pet + ".PetRepository", p + "/pet/PetRepository.java", kind="interface", supertypes=[S_JPA], refs=[pet + ".Pet"]),
        _t(pet + ".Pet", p + "/pet/Pet.java", annotations=[_ann(A_ENTITY)], refs=[owner + ".Owner"]),
        _t(vet + ".VetController", p + "/vet/VetController.java", annotations=[_ann(A_REST), _ann(A_REQ, value=["/api/vets"])], fields=[{"name": "service", "type": vet + ".VetService", "annotations": [_ann(A_AUTOWIRED)]}], methods=[_m("list", "list()", annotations=[_ann(A_GET)], refs=[vet + ".Vet"])], refs=[vet + ".VetService", vet + ".Vet"]),
        _t(vet + ".VetService", p + "/vet/VetService.java", annotations=[_ann(A_SERVICE)], fields=[{"name": "repo", "type": vet + ".VetRepository", "annotations": [_ann(A_AUTOWIRED)]}], refs=[vet + ".VetRepository", vet + ".Vet", base + ".common.Money"]),
        _t(vet + ".VetRepository", p + "/vet/VetRepository.java", kind="interface", supertypes=[S_JPA], refs=[vet + ".Vet"]),
        _t(vet + ".Vet", p + "/vet/Vet.java", annotations=[_ann(A_ENTITY)]),
        _t(base + ".common.Money", p + "/common/Money.java", kind="record"),
        _t(base + ".legacy.OldReportWriter", p + "/legacy/OldReportWriter.java"),
        _t(base + ".owner.OwnerControllerTest", "src/test/java/" + base.replace(".", "/") + "/owner/OwnerControllerTest.java", refs=[owner + ".OwnerController"]),
    ]


def scheduled_types(base: str) -> list[dict[str, Any]]:
    p = "src/main/java/" + base.replace(".", "/")
    inv = base + ".inventory"
    ord_ = base + ".orders"
    return [
        _t(base + ".WarehouseApplication", p + "/WarehouseApplication.java", annotations=[_ann(A_APP)]),
        _t(inv + ".InventorySyncJob", p + "/inventory/InventorySyncJob.java", annotations=[_ann(A_SERVICE)], fields=[{"name": "repo", "type": inv + ".StockRepository", "annotations": [_ann(A_AUTOWIRED)]}], methods=[_m("sync", "sync()", annotations=[_ann(A_SCHED, cron=["0 * * * * *"])], refs=[inv + ".Stock"])], refs=[inv + ".StockRepository", inv + ".Stock"]),
        _t(inv + ".StockRepository", p + "/inventory/StockRepository.java", kind="interface", supertypes=[S_JPA], refs=[inv + ".Stock"]),
        _t(inv + ".Stock", p + "/inventory/Stock.java", annotations=[_ann(A_ENTITY)]),
        _t(ord_ + ".OrderListener", p + "/orders/OrderListener.java", annotations=[_ann(A_SERVICE)], fields=[{"name": "handler", "type": ord_ + ".OrderHandler", "annotations": [_ann(A_AUTOWIRED)]}], methods=[_m("onOrder", "onOrder(String)", annotations=[_ann(A_KAFKA, topics=["orders"])], refs=[ord_ + ".OrderHandler"])], refs=[ord_ + ".OrderHandler"]),
        _t(ord_ + ".OrderHandler", p + "/orders/OrderHandler.java", kind="interface"),
        _t(ord_ + ".DefaultOrderHandler", p + "/orders/DefaultOrderHandler.java", annotations=[_ann(A_SERVICE)], supertypes=[ord_ + ".OrderHandler"], refs=[ord_ + ".Order"]),
        _t(ord_ + ".AuditingOrderHandler", p + "/orders/AuditingOrderHandler.java", annotations=[_ann(A_SERVICE)], supertypes=[ord_ + ".OrderHandler"], refs=[ord_ + ".Order"]),
        _t(ord_ + ".Order", p + "/orders/Order.java", annotations=[_ann(A_ENTITY)]),
    ]


def specimen(name: str, base: str = "org.acme.clinic") -> dict[str, Any]:
    if name == "http":
        types = http_types(base)
        resources = ["src/main/resources/application.properties"]
        probe_beans = {"default": [
            {"name": "ownerServiceImpl", "type": base + ".owner.OwnerServiceImpl", "primary": False},
            {"name": "petService", "type": base + ".pet.PetService", "primary": False},
            {"name": "vetService", "type": base + ".vet.VetService", "primary": False},
        ]}
        findings = {
            "springboot-web-to-quarkus-00001": {"category": "mandatory", "effort": 3, "description": "Replace Spring MVC with JAX-RS", "incidents": [
                {"uri": "file:///analysis/src/main/java/%s/owner/OwnerController.java" % base.replace(".", "/"), "lineNumber": 12, "message": "x"},
                {"uri": "file:///analysis/src/main/java/%s/pet/PetController.java" % base.replace(".", "/"), "lineNumber": 9, "message": "x"},
                {"uri": "file:///analysis/src/main/java/%s/vet/VetController.java" % base.replace(".", "/"), "lineNumber": 9, "message": "x"},
            ]},
            "springboot-jpa-to-quarkus-00002": {"category": "mandatory", "effort": 1, "description": "Spring Data JPA (quarkus-spring-data-jpa supported subset)", "incidents": [
                {"uri": "file:///analysis/src/main/java/%s/owner/OwnerRepository.java" % base.replace(".", "/"), "lineNumber": 5, "message": "x"},
            ]},
            "javaee-pom-to-quarkus-00003": {"category": "mandatory", "effort": 1, "description": "pom", "incidents": [
                {"uri": "file:///analysis/pom.xml", "lineNumber": 30, "message": "x"},
            ]},
            "cloud-readiness-00004": {"category": "optional", "effort": 1, "description": "config", "incidents": [
                {"uri": "file:///analysis/src/main/resources/application.properties", "lineNumber": 1, "message": "x"},
            ]},
        }
    elif name == "scheduled":
        types = scheduled_types(base)
        resources = ["src/main/resources/application.properties"]
        probe_beans = {"default": [
            {"name": "inventorySyncJob", "type": base + ".inventory.InventorySyncJob", "primary": False},
            {"name": "defaultOrderHandler", "type": base + ".orders.DefaultOrderHandler", "primary": True},
            {"name": "auditingOrderHandler", "type": base + ".orders.AuditingOrderHandler", "primary": False},
        ]}
        findings = {
            "springboot-scheduling-00001": {"category": "mandatory", "effort": 1, "description": "Scheduled → Quarkus scheduler", "incidents": [
                {"uri": "file:///analysis/src/main/java/%s/inventory/InventorySyncJob.java" % base.replace(".", "/"), "lineNumber": 20, "message": "x"},
            ]},
            "springboot-kafka-00002": {"category": "mandatory", "effort": 3, "description": "KafkaListener → reactive messaging", "incidents": [
                {"uri": "file:///analysis/src/main/java/%s/orders/OrderListener.java" % base.replace(".", "/"), "lineNumber": 14, "message": "x"},
            ]},
        }
    else:
        raise ValueError(name)
    return {"name": name, "base": base, "types": types, "resources": resources, "probe_beans": probe_beans, "findings": findings}


def _sha(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def _receipt(producer: str, status: str, tool: dict[str, Any], inputs: dict[str, Any], outputs: list[dict[str, str]], reasons: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    doc = {"schema": "rhoai3.producer-receipt/v1", "producer": producer, "status": status, "tool": tool, "inputs": inputs, "outputs": outputs, "reasons": reasons or []}
    doc.update(extra)
    return doc


LEGACY_POM = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>2.7.18</version>
  </parent>
  <groupId>org.acme</groupId>
  <artifactId>clinic</artifactId>
  <version>1.0.0</version>
  <properties>
    <java.version>17</java.version>
  </properties>
  <dependencies>
    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-web</artifactId></dependency>
    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-data-jpa</artifactId></dependency>
    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-actuator</artifactId></dependency>
    <dependency><groupId>org.postgresql</groupId><artifactId>postgresql</artifactId><scope>runtime</scope></dependency>
    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-test</artifactId><scope>test</scope></dependency>
  </dependencies>
  <build>
    <plugins>
      <plugin><groupId>org.springframework.boot</groupId><artifactId>spring-boot-maven-plugin</artifactId></plugin>
    </plugins>
  </build>
</project>
"""

LEGACY_PROPERTIES = """spring.application.name=clinic
server.port=8081
spring.datasource.url=jdbc:postgresql://localhost:5432/clinic
spring.datasource.username=clinic
spring.jpa.hibernate.ddl-auto=create-drop
spring.jpa.show-sql=true
spring.jpa.open-in-view=false
"""


def write_legacy_tree(copy: Path, spec: dict[str, Any]) -> None:
    """A fake frozen analysis copy: pom, properties, one stub file per type."""
    copy.mkdir(parents=True, exist_ok=True)
    (copy / "pom.xml").write_text(LEGACY_POM, encoding="utf-8")
    for r in spec["resources"]:
        target = copy / r
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(LEGACY_PROPERTIES, encoding="utf-8")
    for t in spec["types"]:
        target = copy / t["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        pkg, _, simple = t["fqn"].rpartition(".")
        target.write_text("package %s;\n\npublic %s %s {}\n" % (pkg, "interface" if t["kind"] == "interface" else "class", simple), encoding="utf-8")


def build_dest(
    root: Path,
    spec: dict[str, Any],
    *,
    decisions: dict[str, Any] | None = None,
    build_outcome: str = "success",
    drop_canary: bool = False,
    mta_admissible: bool = True,
    structure_status: str = "ok",
    seed: int | None = None,
    extra_findings: dict[str, Any] | None = None,
    golden: Path = GOLDEN,
    activation: str = "activated",
    pins_override: dict[str, Any] | None = None,
) -> Path:
    """Materialize a destination tree with M1 outputs for the specimen."""
    root = Path(root)
    rng = random.Random(seed) if seed is not None else None

    def shuffled(items: list[Any]) -> list[Any]:
        out = list(items)
        if rng is not None:
            rng.shuffle(out)
        return out

    shutil.copytree(golden / ".hermes" / "planning", root / ".hermes" / "planning", dirs_exist_ok=True)
    shutil.copytree(golden / ".mvn", root / ".mvn", dirs_exist_ok=True)  # Maven settings wiring (bootstrap precondition)
    # what the pinned BOM manages (probe-bom-managed.py output): every catalog
    # extension, so a version-less mapped extension is legal in the fixture
    catalog = load_json(golden / ".hermes" / "planning" / "catalogs" / "compat-mapping.json")
    ext = set(catalog.get("always_add") or [])
    for arts in (catalog.get("starters") or {}).values():
        ext.update(arts)
    ext.update((catalog.get("jdbc_drivers") or {}).values())
    groups = catalog.get("starter_group_ids") or {}
    golden_pins = load_json(golden / ".hermes" / "pins.json")["pins"]["quarkus_platform"]
    write_canonical(root / BOM_MANAGED, {"schema": "rhoai3.bom-managed/v1", "bom": {"group_id": golden_pins["group_id"], "artifact_id": golden_pins["bom_artifact_id"], "version": golden_pins["version"]}, "managed": sorted("%s:%s" % (groups.get(a, "io.quarkus"), a) for a in ext), "count": len(ext), "effective_pom_sha256": "f" * 64, "tool": "fixture"})
    (root / ".hermes").mkdir(parents=True, exist_ok=True)
    shutil.copy2(golden / ".hermes" / "pins.json", root / ".hermes" / "pins.json")
    # Fixture pins: the golden ships the planner NOT-ACTIVATED (fail-closed);
    # a fixture activates it so the loop itself is under test. Tool pins are
    # the golden ones (structure_extractor jdk-21 → fixture receipts say jdk-21).
    pins_doc = json.loads((root / ".hermes" / "pins.json").read_text(encoding="utf-8"))
    pins_doc["pins"]["planner"] = {"activation": activation}
    for k, v in (pins_override or {}).items():
        if v is None:
            pins_doc["pins"].pop(k, None)
        else:
            pins_doc["pins"][k] = v
    (root / ".hermes" / "pins.json").write_text(json.dumps(pins_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "fixtures", ".work")
    for sub in ("skills", "kernel", "lib"):
        shutil.copytree(golden / ".hermes" / sub, root / ".hermes" / sub, dirs_exist_ok=True, ignore=ignore)
    (root / "migration.yaml").write_text(
        "migration:\n  legacyRepoUrl: \"\"\n  target: quarkus\n  legacyBasePackage: \"%s\"\n"
        "analysis:\n  mode: containerless\n  custom_rules: .hermes/planning/mta-rules\n  canary_rule_id: rhoai3-canary-00001\n  targets:\n    - quarkus\n    - jakarta-ee9\n" % spec["base"],
        encoding="utf-8",
    )
    (root / ".gitignore").write_text("evidence/\nverification/\n.derived/\n.hermes/\ntarget/\n", encoding="utf-8")

    # frozen legacy copy (fake) + manifest
    copy = root / ".derived" / "frozen-input"
    write_legacy_tree(copy, spec)
    files: list[dict[str, str]] = [{"path": "pom.xml", "sha256": _sha("pom:" + spec["name"])}]
    for r in spec["resources"]:
        files.append({"path": r, "sha256": _sha(r)})
    for t in spec["types"]:
        files.append({"path": t["path"], "sha256": _sha(t["fqn"])})
    files.sort(key=lambda f: f["path"])
    manifest = {"schema": "rhoai3.source-manifest/v1", "root_kind": "frozen-legacy", "source_root": "/projects/legacy", "files": shuffled(files)}
    manifest["digest"] = sha256_bytes(canonical_bytes({"files": files}))
    write_canonical(root / SOURCE_MANIFEST, manifest)
    prod = root / PRODUCERS_DIR
    prod.mkdir(parents=True, exist_ok=True)
    write_canonical(prod / "freeze.json", _receipt("freeze", "ok", {"name": "freeze-migration-input", "version": "1", "pin_status": "not-applicable"}, {"source_root": "/projects/legacy"}, [{"path": str(SOURCE_MANIFEST), "sha256": manifest["digest"]}], analysis_copy=str(copy), source_digest=manifest["digest"]))
    write_canonical(prod / "build.json", _receipt("build", "ok" if build_outcome == "success" else "failed", {"name": "maven", "version": "3.9", "pin_status": "not-applicable"}, {"source_digest": manifest["digest"]}, [], outcome=build_outcome, classpath_available=build_outcome == "success", source_roots=["src/main/java"], generated_source_roots=[], toolchain={"java": "21", "maven": "3.9"}, warmup={"attempted": True, "outcome": "success"}, managed_versions=dict(spec.get("managed_versions") or {})))
    structure = {"schema": "rhoai3.structure/v1", "producer": {"tool": "jdk-model", "version": "jdk-21", "runtime": "fixture", "mode": "full" if build_outcome == "success" else "partial"}, "source_digest": manifest["digest"], "mode": "full" if build_outcome == "success" else "partial", "types": shuffled(spec["types"])}
    write_canonical(root / STRUCTURE, structure)
    write_canonical(prod / "jdk-model.json", _receipt("jdk-model", structure_status, {"name": "jdk-model", "version": "jdk-21", "pin_status": "pinned"}, {"source_digest": manifest["digest"]}, [{"path": str(STRUCTURE), "sha256": "x" * 64}], mode=structure["mode"]))

    violations = dict(spec["findings"])
    if extra_findings:
        violations.update(extra_findings)
    if not drop_canary:
        violations["rhoai3-canary-00001"] = {"category": "optional", "effort": 0, "description": "canary", "incidents": [{"uri": "file:///analysis/pom.xml", "lineNumber": 1, "message": "canary"}]}
    findings = {"schema": "rhoai3.mta-findings/v1-provisional", "execution_evidence": {"analyzer_ran": True, "cli": "/opt/mta-cli/mta-cli", "rule_set": ["quarkus", "jakarta-ee9"], "input_digest": "frozen:" + manifest["digest"]}, "violations": violations}
    (root / MTA_FINDINGS).parent.mkdir(parents=True, exist_ok=True)
    (root / MTA_FINDINGS).write_text(json.dumps(findings, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    frozen_sha = str(((load_json(root / ".hermes" / "pins.json").get("pins") or {}).get("mta_cli") or {}).get("artifact_sha256") or "") or ("a" * 64)
    write_canonical(prod / "mta.json", _receipt("mta", "ok", {"name": "mta-cli", "version": "8.2", "version_measured": "8.2.0", "pin_status": "pinned", "product_version_pin": "8.2", "admissible": mta_admissible, "provenance": "mta-cli-8.2-artifact" if mta_admissible else "kantra-fallback", "artifact_sha256": frozen_sha if mta_admissible else ("k" * 64)}, {"analysis_root": "/analysis", "digest": manifest["digest"]}, [{"path": str(MTA_FINDINGS), "sha256": "w" * 64}], targets=["quarkus", "jakarta-ee9"], custom_rules_digest=_sha("rules"), bundled_rules_digest=_sha("bundled"), exit_status=0, output_digest=_sha("out")))

    from planner.evidence import derive_entry_points, load_catalogs

    catalogs = load_catalogs(golden)
    eps = derive_entry_points({"types": sorted(spec["types"], key=lambda t: t["fqn"])}, catalogs)
    write_canonical(root / "evidence" / "entry-point-inventory.json", {"schema": "rhoai3.entry-point-inventory/v1", "root": "/analysis", "execution_evidence": {"scanner": "fixture", "java_files_seen": len(spec["types"]), "inputs_digest_sha256": manifest["digest"], "ran": True, "vacuous": False, "provenance": "jdk-model:fixture"}, "counts": {"total": len(eps), "http": sum(1 for e in eps if e["kind"] == "http"), "non_http": sum(1 for e in eps if e["kind"] != "http"), "by_subtype": {}}, "entry_points": [{"kind": "http" if e["kind"] == "http" else "non-http", "subtype": "spring-mvc-or-jaxrs" if e["kind"] == "http" else e["kind"], "file": e["path"], "line": 0, "symbol": e["type"].rsplit(".", 1)[-1], "evidence": e["evidence"], "http_method": e["http_method"], "http_path": e["http_path"], "entry_point_id": e["id"], "resolution": e["resolution"]} for e in eps]})
    write_canonical(root / "evidence" / "type-inventory.json", {"schema": "rhoai3.type-inventory/v1", "root": "/analysis", "execution_evidence": {"scanner": "fixture", "entry_files_seen": len({e["path"] for e in eps}), "types_seen": len(spec["types"]), "ran": True, "vacuous": False, "provenance": "jdk-model:fixture"}, "counts": {"total": len(spec["types"]), "by_layer": {}}, "types": [{"legacy_file": t["path"], "dest_file": t["path"], "layer": t["path"].rsplit("/", 2)[-2], "generated": False, "reached_from": [], "fqn": t["fqn"], "resolution": t["resolution"]} for t in sorted(spec["types"], key=lambda t: t["fqn"])]})

    if decisions is not None:
        (root / "decisions.yaml").write_text(decisions_yaml(decisions), encoding="utf-8")
    return root


FIXTURE_DATASOURCE = {
    "adr": "ADR-001",
    "db_kind": "postgresql",
    "db_version": "16-el9",   # a version, not a number: the fixture yaml writer quotes nothing numeric
    "jdbc_extension": "io.quarkus:quarkus-jdbc-postgresql",
    "profile": "prod",
    "instance": "fixture-isolated-postgres",
    "jdbc_url_env": "FIXTURE_DB_URL",
    "username_env": "FIXTURE_DB_USER",
    "password_env": "FIXTURE_DB_PASSWORD",
    "reset_procedure": "drop and recreate the schema, then apply schema_sql and seed_sql",
    "schema_owner": "source-assets",
    "schema_sql": "src/main/resources/db/postgresql/initDB.sql",
    "seed_sql": "src/main/resources/db/postgresql/populateDB.sql",
    "hibernate_generation": "none",
    "source_baseline_db_kind": "hsqldb",
}


def full_decisions(*, platform: str = "quarkus-rhbq-3.27", max_attempts: int | None = 2, not_applicable: list[dict[str, Any]] | None = None, adrs: list[dict[str, Any]] | None = None, retired_sources: list[dict[str, Any]] | None = None, datasource: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = {
        "schema": "rhoai3.decisions/v2",
        "adrs": adrs if adrs is not None else list(ACCEPTED_ADRS),
        "destination_platform": {"id": platform, "adr": "ADR-001"},
        "thresholds": {"max_attempts": max_attempts, "adr": "ADR-002"},
        "not_applicable": not_applicable or [],
        "datasource": dict(FIXTURE_DATASOURCE) if datasource is None else datasource,
    }
    if retired_sources:
        doc["retired_sources"] = retired_sources
    return doc


def runtime(root: Path, *, package_rc: int | None = 0, boot_ready: bool | None = True, blocker: str = "", detail: str = "", log: str = "", artifact: str = "") -> None:
    """Simulate the packaging and startup gates. ``None`` means the gate did not
    run, which the work list must treat as unknown -- never as a pass."""
    from planner.canonical import write_canonical as _w
    from planner.paths import VERIFY_BOOT, VERIFY_PACKAGE

    digest = artifact or "a" * 64
    if package_rc is None:
        (root / VERIFY_PACKAGE).unlink(missing_ok=True)
    else:
        doc = {"schema": "rhoai3.verify-package/v1", "gate": "package", "ran": True, "rc": int(package_rc),
               "artifact": "target/quarkus-app/quarkus-run.jar", "artifact_sha256": digest if package_rc == 0 else "",
               "failed_goal": detail if package_rc else "", "detail": detail if package_rc else "", "log_tail": log}
        if blocker and package_rc:
            doc["blocker"] = blocker
        _w(root / VERIFY_PACKAGE, doc)
    if boot_ready is None:
        (root / VERIFY_BOOT).unlink(missing_ok=True)
    else:
        doc = {"schema": "rhoai3.verify-boot/v1", "gate": "boot", "ran": True, "rc": 0 if boot_ready else 1,
               "ready": bool(boot_ready), "artifact_sha256": digest if boot_ready else "",
               "detail": "" if boot_ready else detail, "log_tail": "" if boot_ready else log}
        if blocker and not boot_ready:
            doc["blocker"] = blocker
        _w(root / VERIFY_BOOT, doc)


def admitted_decisions(name: str = "http", **kw: Any) -> dict[str, Any]:
    return full_decisions(**kw)


def _yaml_scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    return json.dumps(s) if (s == "" or any(c in s for c in ":#{}[],&*?|<>=!%@`'\"") or s.strip() != s) else s


def _yaml(obj: Any, indent: int = 0) -> list[str]:
    pad = "  " * indent
    lines: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, dict):
                lines.append("%s%s:" % (pad, k))
                lines.extend(_yaml(v, indent + 1) if v else ["%s  {}" % pad])
            elif isinstance(v, list):
                lines.append("%s%s:" % (pad, k))
                if not v:
                    lines[-1] = "%s%s: []" % (pad, k)
                for item in v:
                    if isinstance(item, dict):
                        inner = _yaml(item, indent + 2)
                        lines.append("%s  - %s" % (pad, inner[0].strip()))
                        lines.extend(inner[1:])
                    else:
                        lines.append("%s  - %s" % (pad, _yaml_scalar(item)))
            else:
                lines.append("%s%s: %s" % (pad, k, _yaml_scalar(v)))
    return lines


def decisions_yaml(doc: dict[str, Any]) -> str:
    return "\n".join(_yaml(doc)) + "\n"


# ---------------------------------------------------------------------------
# verification state helpers (what run-verify.sh would have produced)
# ---------------------------------------------------------------------------


def diagnostics_doc(errors: list[tuple], unresolvable: str | None = None) -> dict[str, Any]:
    if unresolvable:
        return {"schema": "rhoai3.diagnostics/v1", "files": 0, "classpath_entries": 0, "success": False, "errors": 0, "diagnostics": [], "build_unresolvable": True, "reason": unresolvable}
    rows = []
    for err in errors:
        path, line, message = err[0], err[1], err[2]
        code = err[3] if len(err) > 3 else "compiler.err.cant.resolve"
        rows.append({"kind": "ERROR", "path": path, "line": line, "code": code, "message": message})
    return {"schema": "rhoai3.diagnostics/v1", "files": 1, "classpath_entries": 1, "success": not errors, "errors": len(errors), "diagnostics": rows}


def surefire_doc(failures: list[tuple[str, str]]) -> dict[str, Any]:
    return {"schema": "rhoai3.surefire/v1", "reports": 1, "tests": max(1, len(failures)), "failures": [{"classname": c, "name": n, "message": "assertion", "path": ""} for c, n in failures]}


SIM = Path("verification") / "loop" / "sim"


def write_verified_state(root: Path, *, errors: list[tuple[str, int, str]] | None = None, failures: list[tuple[str, str]] | None = None, findings: dict[str, Any] | None = None, unresolvable: str | None = None, test_rc: int | None = None) -> dict[str, str]:
    """Simulate the tools' raw outputs under verification/loop/sim/ and return
    the verify.py arguments that consume them (never written into the
    verification/build/ reports directly — verify.py owns those)."""
    root = Path(root)
    sim = root / SIM
    sim.mkdir(parents=True, exist_ok=True)
    write_canonical(sim / "diagnostics.json", diagnostics_doc(errors or [], unresolvable))
    write_canonical(sim / "surefire.json", surefire_doc(failures or []))
    # the simulator stands in for a full run-verify pass, and says so: an
    # unstated mode is diagnostic and cannot promote (verify.py)
    args = ["--mode", "acceptance", "--diagnostics", str(sim / "diagnostics.json"), "--surefire-json", str(sim / "surefire.json"), "--test-rc", str(test_rc if test_rc is not None else (1 if failures else 0))]
    if findings is not None:
        write_canonical(sim / "findings.json", findings)
        args += ["--findings", str(sim / "findings.json")]
    return {"args": args}


def verify(root: Path, **kw: Any) -> "subprocess.CompletedProcess[str]":
    """write_verified_state + verify.py (test support)."""
    import subprocess
    import sys

    root = Path(root)
    state = write_verified_state(root, **kw)
    script = root / ".hermes" / "skills" / "migration" / "fix-until-green" / "scripts" / "verify.py"
    return subprocess.run([sys.executable, str(script), "--root", str(root), *state["args"]], text=True, capture_output=True)


def issue(root: Path) -> dict[str, Any]:
    """K4-convert the current state so an issued card exists (test support)."""
    import sys

    kernel = str(Path(root) / ".hermes" / "kernel")
    if kernel not in sys.path:
        sys.path.insert(0, kernel)
    from k4_convert import convert_admitted  # type: ignore

    result, issues = convert_admitted(Path(root))
    if issues or result is None:
        raise RuntimeError("issue: %s" % issues)
    return result["payloads"][0]


def prepare_loop(root: Path, *, errors: list[tuple[str, int, str]] | None = None, failures: list[tuple[str, str]] | None = None) -> None:
    """bundle → git baseline → bootstrap → simulated verification → work list → step 0 → admission.

    Test support only: what paved-road-m2 does on a card, with the tool
    outputs simulated.
    """
    import subprocess
    import sys

    from planner import pipeline
    from planner.canonical import load_json

    root = Path(root)
    skills = root / ".hermes" / "skills"
    pipeline.assemble_bundle(root)
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "scaffold"], check=True)
    subprocess.run([sys.executable, str(skills / "migration" / "bootstrap-destination" / "scripts" / "bootstrap-destination.py"), "--root", str(root)], check=True, capture_output=True)
    p = verify(root, errors=errors or [], failures=failures or [], findings=load_json(root / MTA_FINDINGS))
    if p.returncode != 0:
        raise RuntimeError("verify: %s%s" % (p.stdout, p.stderr))
    loop = skills / "migration" / "fix-until-green" / "scripts"
    p = subprocess.run([sys.executable, str(loop / "advance.py"), "--root", str(root), "--baseline", "--no-mint"], text=True, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError("baseline: %s%s" % (p.stdout, p.stderr))
    pipeline.admit(root)


def stable_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
