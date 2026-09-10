#!/usr/bin/env python3
"""bootstrap-destination selftest: trivial launcher deleted; launcher with behavior kept + block;
unmapped starter kept + block; second run preserves the whole tree; blocked receipt → admission INCONCLUSIVE."""
from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
SCRIPT = HERE / "bootstrap-destination.py"
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
from planner import pipeline, specimens  # noqa: E402
from planner.canonical import load_json  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if rel.startswith((".hermes/", "evidence/", "verification/", ".derived/", ".git/")) or not p.is_file():
            continue
        h.update(rel.encode()); h.update(b"\0"); h.update(p.read_bytes()); h.update(b"\0")
    return h.hexdigest()


def _plugin_config_case() -> int:
    import importlib.util
    import json
    import xml.etree.ElementTree as ET

    spec = importlib.util.spec_from_file_location("bootstrap_destination", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    catalog = json.loads((GOLDEN / ".hermes" / "planning" / "catalogs" / "compat-mapping.json").read_text(encoding="utf-8"))
    pom = """<project xmlns="http://maven.apache.org/POM/4.0.0"><properties><openapi-generator-maven-plugin.version>5.2.1</openapi-generator-maven-plugin.version></properties>
<build><plugins><plugin><groupId>org.openapitools</groupId><artifactId>openapi-generator-maven-plugin</artifactId><version>${openapi-generator-maven-plugin.version}</version>
<executions><execution><goals><goal>generate</goal></goals><configuration><inputSpec>x.yml</inputSpec><generatorName>spring</generatorName><library>spring-boot</library>
<configOptions><performBeanValidation>true</performBeanValidation><dateLibrary>java8</dateLibrary><java8>true</java8></configOptions></configuration></execution></executions></plugin>
<plugin><artifactId>maven-compiler-plugin</artifactId></plugin></plugins></build></project>"""
    project = ET.fromstring(pom)
    plugins = project.find(mod.q("build")).find(mod.q("plugins"))
    changes: list = []
    mod.apply_plugin_config(project, plugins, catalog, changes)
    ns = {"m": "http://maven.apache.org/POM/4.0.0"}
    ver = project.findtext("m:properties/m:openapi-generator-maven-plugin.version", "", ns)
    gen = project.findtext(".//m:generatorName", "", ns); lib = project.findtext(".//m:library", "", ns)
    opts = project.find(".//m:configOptions", ns)
    names = {e.tag.rsplit("}", 1)[-1]: (e.text or "") for e in opts}
    if ver != "7.25.0" or gen != "jaxrs-spec" or lib != "quarkus":
        return _fail("plugin_config must pin the version through its property and set the generator leaves: %s %s %s" % (ver, gen, lib))
    if names.get("useJakartaEe") != "true" or "performBeanValidation" in names or "java8" in names or names.get("dateLibrary") != "java8":
        return _fail("plugin_config must set/remove configOptions: %s" % names)
    if not any(c["op"] == "pom.plugin-version" for c in changes) or not any(c["op"] == "pom.plugin-config" for c in changes):
        return _fail("changes must record the plugin rewrite: %s" % changes)
    changes2: list = []
    mod.apply_plugin_config(project, plugins, catalog, changes2)
    if changes2:
        return _fail("a second application must change nothing: %s" % changes2)
    return 0


def main() -> int:
    if _plugin_config_case():
        return 1
    with tempfile.TemporaryDirectory(prefix="boot-") as tmp:
        t = Path(tmp).resolve()
        # 1. trivial launcher → deleted; full tree identical on a second run
        root = specimens.build_dest(t / "ok", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        pipeline.assemble_bundle(root)
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)], text=True, capture_output=True)
        if p.returncode != 0:
            return _fail("bootstrap: %s%s" % (p.stdout, p.stderr))
        if (root / "src/main/java/org/acme/clinic/PetClinicApplication.java").exists():
            return _fail("trivial launcher must be deleted")
        first = tree_hash(root)
        rec1 = load_json(root / "evidence/producers/bootstrap.json")
        # simulate an accepted loop edit, then re-run: the edit must survive (import never overwrites)
        target = root / "src/main/java/org/acme/clinic/vet/Vet.java"
        target.write_text(target.read_text() + "// accepted step\n", encoding="utf-8")
        after_edit = tree_hash(root)
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)], text=True, capture_output=True)
        if p.returncode != 0 or tree_hash(root) != after_edit:
            return _fail("second bootstrap must not change any file (import never overwrites, pom idempotent)")
        if rec1["status"] != "ok" or rec1.get("blocks"):
            return _fail("clean bootstrap receipt %s" % rec1["status"])
        if first == after_edit:
            return _fail("test setup: the edit must change the tree hash")
        # 2. launcher with a @Bean method → kept, block recorded, exit 1, admission INCONCLUSIVE
        spec = specimens.specimen("http")
        for ty in spec["types"]:
            if ty["fqn"].endswith("PetClinicApplication"):
                ty["methods"] = [{"name": "clock", "signature": "clock()", "annotations": [{"fqn": "org.springframework.context.annotation.Bean", "values": {}}], "params": [], "returns": "java.time.Clock", "type_refs": [], "calls": [], "resolution": "full"}]
        b = specimens.build_dest(t / "bean", spec, decisions=specimens.admitted_decisions())
        pipeline.assemble_bundle(b)
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(b)], text=True, capture_output=True)
        if p.returncode != 1 or "MAIN_CLASS_NOT_TRIVIAL" not in p.stderr:
            return _fail("launcher with a @Bean must block: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        if not (b / "src/main/java/org/acme/clinic/PetClinicApplication.java").exists():
            return _fail("launcher with behavior must be kept")
        rec = load_json(b / "evidence/producers/bootstrap.json")
        if rec["status"] != "blocked" or not any(x["class"] == "MAIN_CLASS_NOT_TRIVIAL" for x in rec["blocks"]):
            return _fail("blocked receipt %s" % rec["status"])
        specimens.verify(b, errors=[], failures=[], findings=load_json(b / "evidence/mta-findings.json"))
        rec_a = pipeline.admit(b)
        if rec_a["status"] != "INCONCLUSIVE" or not any(x["class"] == "BOOTSTRAP_BLOCKED" for x in rec_a["blocks"]):
            return _fail("blocked bootstrap must keep admission INCONCLUSIVE: %s" % rec_a["reasons"][:3])
        # 3. unmapped Spring Boot starter → stays in the pom, block recorded
        u = specimens.build_dest(t / "unmapped", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        pom = u / ".derived/frozen-input/pom.xml"
        pom.write_text(pom.read_text().replace("<artifactId>spring-boot-starter-actuator</artifactId>", "<artifactId>spring-boot-starter-mail</artifactId>"), encoding="utf-8")
        pipeline.assemble_bundle(u)
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(u)], text=True, capture_output=True)
        if p.returncode != 1 or "UNMAPPED_DEPENDENCY" not in p.stderr or "spring-boot-starter-mail" not in (u / "pom.xml").read_text():
            return _fail("unmapped starter must stay and block: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        # 4. Maven settings not wired → the pinned platform cannot resolve; block, never a silent offline failure later
        m = specimens.build_dest(t / "nosettings", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        pipeline.assemble_bundle(m)
        (m / ".mvn" / "maven.config").unlink()
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(m)], text=True, capture_output=True)
        if p.returncode != 1 or "MAVEN_SETTINGS_MISSING" not in p.stderr:
            return _fail("missing .mvn/maven.config must block: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        (m / ".mvn" / "maven.config").write_text("-s\n.mvn/settings.xml\n", encoding="utf-8")
        (m / ".mvn" / "settings.xml").write_text("<settings/>", encoding="utf-8")
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(m)], text=True, capture_output=True)
        if p.returncode != 1 or "red-hat-enterprise-maven-repository" not in p.stderr:
            return _fail("settings without the RH GA profile must block: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        # 4b. properties under src/test/resources are migrated like src/main, and logging.level.<cat> maps to the Quarkus category key
        tr = specimens.build_dest(t / "testres", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        tres = tr / ".derived/frozen-input/src/test/resources"
        tres.mkdir(parents=True, exist_ok=True)
        (tres / "application.properties").write_text("server.port=9966\nlogging.level.org.springframework=INFO\n#logging.level.org.hibernate.SQL=DEBUG\n", encoding="utf-8")
        pipeline.assemble_bundle(tr)
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(tr)], text=True, capture_output=True)
        got = (tr / "src/test/resources/application.properties").read_text(encoding="utf-8")
        if p.returncode != 0 or "quarkus.http.port=9966" not in got or 'quarkus.log.category."org.springframework".level=INFO' not in got or "#logging.level.org.hibernate.SQL=DEBUG" not in got:
            return _fail("test resources must be migrated (exact keys and the logging.level family; comments untouched): rc=%s %r" % (p.returncode, got))
        ren = [c for c in load_json(tr / "evidence/producers/bootstrap.json")["changes"] if c["op"] == "properties.rename" and c["file"].startswith("src/test/")]
        if len(ren) != 2:
            return _fail("test-resource renames must be recorded: %s" % ren)
        # 5. a version-less dependency the BOM does not manage: pinned to the legacy-resolved version (measured), else VERSION_UNMANAGED; no probe → BOM_PROBE_MISSING
        spec_v = specimens.specimen("http")
        spec_v["managed_versions"] = {"org.hsqldb:hsqldb": "2.7.2"}
        v = specimens.build_dest(t / "versions", spec_v, decisions=specimens.admitted_decisions())
        pom = v / ".derived/frozen-input/pom.xml"
        pom.write_text(pom.read_text().replace("</dependencies>", "    <dependency><groupId>org.hsqldb</groupId><artifactId>hsqldb</artifactId><scope>runtime</scope></dependency>\n    <dependency><groupId>com.jayway.jsonpath</groupId><artifactId>json-path</artifactId></dependency>\n  </dependencies>"), encoding="utf-8")
        pipeline.assemble_bundle(v)
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(v)], text=True, capture_output=True)
        rec = load_json(v / "evidence/producers/bootstrap.json")
        if p.returncode != 1 or [b["subject"] for b in rec["blocks"] if b["class"] == "VERSION_UNMANAGED"] != ["com.jayway.jsonpath:json-path"]:
            return _fail("unmanaged version without a legacy version must block: rc=%s %s" % (p.returncode, rec["blocks"]))
        pinned = [c for c in rec["changes"] if c["op"] == "pom.pin-legacy-version"]
        if [c["gav"] for c in pinned] != ["org.hsqldb:hsqldb:2.7.2"] or "<version>2.7.2</version>" not in (v / "pom.xml").read_text():
            return _fail("legacy-resolved version must be carried over: %s" % pinned)
        if any("<version>" in ln and "quarkus-spring-web" in ln for ln in (v / "pom.xml").read_text().splitlines()):
            return _fail("BOM-managed extensions stay version-less")
        (v / "evidence/build/bom-managed.json").unlink()
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(v)], text=True, capture_output=True)
        if p.returncode != 1 or "BOM_PROBE_MISSING" not in p.stderr:
            return _fail("missing BOM probe must block: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        # 6. a source an accepted ADR retires is deleted with ADR provenance, never re-imported; a stale path blocks
        adrs = list(specimens.ACCEPTED_ADRS) + [{"id": "ADR-009", "title": "Retire the vet cache", "status": "accepted"}]
        vet_path = "src/main/java/org/acme/clinic/vet/Vet.java"
        r = specimens.build_dest(t / "retire", specimens.specimen("http"), decisions=specimens.admitted_decisions(adrs=adrs, retired_sources=[{"path": vet_path, "adr": "ADR-009", "reason": "test"}]))
        pipeline.assemble_bundle(r)
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(r)], text=True, capture_output=True)
        rec = load_json(r / "evidence/producers/bootstrap.json")
        dels = [c for c in rec["changes"] if c["op"] in ("source.delete", "source.retire") and c["path"] == vet_path]
        if p.returncode != 0 or (r / vet_path).exists() or len(dels) != 1 or dels[0].get("adr") != "ADR-009" or rec.get("retired_sources") != {vet_path: "ADR-009"}:
            return _fail("retired source must be deleted with ADR provenance: rc=%s %s %s" % (p.returncode, p.stderr[-200:], dels))
        h = tree_hash(r)
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(r)], text=True, capture_output=True)
        if p.returncode != 0 or tree_hash(r) != h or (r / vet_path).exists():
            return _fail("second run must not re-import a retired source")
        (r / "decisions.yaml").write_text(specimens.decisions_yaml(specimens.admitted_decisions(adrs=adrs, retired_sources=[{"path": "src/main/java/org/acme/NoSuch.java", "adr": "ADR-009", "reason": "stale"}])), encoding="utf-8")
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(r)], text=True, capture_output=True)
        if p.returncode != 1 or "RETIRED_SOURCE_MISSING" not in p.stderr:
            return _fail("a retired path the legacy never had must block: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        (r / "decisions.yaml").write_text(specimens.decisions_yaml(specimens.admitted_decisions(retired_sources=[{"path": vet_path, "adr": "ADR-009", "reason": "not accepted"}])), encoding="utf-8")
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(r)], text=True, capture_output=True)
        if [c for c in load_json(r / "evidence/producers/bootstrap.json")["changes"] if c["op"] in ("source.delete", "source.retire") and c["path"] == vet_path]:
            return _fail("an ADR that is not accepted retires nothing")
    print("OK: bootstrap-destination (trivial launcher deleted; second run preserves the tree; @Bean launcher kept + BOOTSTRAP_BLOCKED; unmapped starter kept + block; Maven settings wiring required; legacy versions carried over / VERSION_UNMANAGED / BOM_PROBE_MISSING; ADR-retired sources deleted with provenance / stale path blocks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
