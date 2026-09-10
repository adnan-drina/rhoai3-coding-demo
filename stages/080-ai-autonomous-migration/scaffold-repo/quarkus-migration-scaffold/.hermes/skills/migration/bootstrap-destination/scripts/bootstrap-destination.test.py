#!/usr/bin/env python3
"""bootstrap-destination selftest: trivial launcher deleted; launcher with behavior kept + block;
unmapped starter kept + block; second run preserves the whole tree; blocked receipt → admission INCONCLUSIVE;
--reapply-catalog carries a late catalog row into a bootstrapped tree without touching accepted work."""
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
    # the generated-source folder must be the one the mojo registers as a compile
    # source root, or Maven never compiles what the generator writes
    if names.get("sourceFolder") != "src/main/java":
        return _fail("plugin_config must pin the generated-source folder the mojo registers: %s" % names)
    if not any(c["op"] == "pom.plugin-version" for c in changes) or not any(c["op"] == "pom.plugin-config" for c in changes):
        return _fail("changes must record the plugin rewrite: %s" % changes)
    changes2: list = []
    mod.apply_plugin_config(project, plugins, catalog, changes2)
    if changes2:
        return _fail("a second application must change nothing: %s" % changes2)
    # compiler args are ensured, never duplicated; documented plugins are added once
    pom2 = """<project xmlns="http://maven.apache.org/POM/4.0.0"><build><plugins><plugin><artifactId>maven-compiler-plugin</artifactId><configuration><compilerArgs><arg>-Amapstruct.x=1</arg></compilerArgs></configuration></plugin></plugins></build></project>"""
    project = ET.fromstring(pom2); plugins = project.find(mod.q("build")).find(mod.q("plugins"))
    ch: list = []
    mod.add_plugins(plugins, catalog, ch); mod.apply_plugin_config(project, plugins, catalog, ch)
    args = [e.text for e in project.iter(mod.q("arg"))]
    arts = [mod.text(p, "artifactId") for p in plugins.findall(mod.q("plugin"))]
    if args.count("-parameters") != 1 or "-Amapstruct.x=1" not in args or "maven-failsafe-plugin" not in arts or "maven-surefire-plugin" not in arts:
        return _fail("compiler -parameters must be ensured beside existing args and failsafe/surefire added: %s %s" % (args, arts))
    fs = next(p for p in plugins.findall(mod.q("plugin")) if mod.text(p, "artifactId") == "maven-failsafe-plugin")
    if [g.text for g in fs.iter(mod.q("goal"))] != ["integration-test", "verify"] or fs.find(".//" + mod.q("java.util.logging.manager")) is None:
        return _fail("failsafe must carry its documented executions and system properties")
    ch2: list = []
    mod.add_plugins(plugins, catalog, ch2); mod.apply_plugin_config(project, plugins, catalog, ch2)
    if ch2 or [e.text for e in project.iter(mod.q("arg"))].count("-parameters") != 1:
        return _fail("plugin additions must be idempotent: %s" % ch2)
    # dependencies: documented removals/replacements (v6's accepted pom edits) beside the starter mapping
    pom3 = """<project xmlns="http://maven.apache.org/POM/4.0.0"><dependencies>
<dependency><groupId>io.springfox</groupId><artifactId>springfox-boot-starter</artifactId><version>3.0.0</version></dependency>
<dependency><groupId>javax.xml.bind</groupId><artifactId>jaxb-api</artifactId><version>2.3.0</version></dependency>
<dependency><groupId>org.springframework.security</groupId><artifactId>spring-security-test</artifactId><scope>test</scope></dependency>
<dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-web</artifactId></dependency>
<dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-nowhere</artifactId></dependency>
</dependencies></project>"""
    project = ET.fromstring(pom3); deps = project.find(mod.q("dependencies"))
    ch3: list = []; blocks: list = []
    to_add, scoped = mod.map_dependencies(deps, catalog, ch3, blocks)
    left = ["%s:%s" % (mod.text(d, "groupId"), mod.text(d, "artifactId")) for d in deps.findall(mod.q("dependency"))]
    if left != ["jakarta.xml.bind:jakarta.xml.bind-api", "org.springframework.boot:spring-boot-starter-nowhere"]:
        return _fail("removals leave nothing, replacements rename in place, an unmapped Spring Boot dependency stays and blocks: %s" % left)
    if next(d for d in deps.findall(mod.q("dependency")) if mod.text(d, "artifactId") == "jakarta.xml.bind-api").find(mod.q("version")) is not None:
        return _fail("a replaced artifact is BOM-managed: its version must go")
    if "quarkus-smallrye-openapi" not in to_add or "quarkus-test-security" not in to_add or scoped.get("quarkus-test-security") != "test" or "quarkus-rest" not in to_add:
        return _fail("documented replacements must be added (openapi, test-security in test scope, always_add quarkus-rest): %s %s" % (to_add, scoped))
    if not any(b["class"] == "UNMAPPED_DEPENDENCY" for b in blocks):
        return _fail("an unmapped Spring Boot dependency must block")
    return 0


def _profile_merge_case() -> int:
    import importlib.util

    spec = importlib.util.spec_from_file_location("bootstrap_destination", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    with tempfile.TemporaryDirectory(prefix="prof-") as td:
        root = Path(td); res = root / "src" / "main" / "resources"; res.mkdir(parents=True)
        (res / "application.properties").write_text("quarkus.http.port=9966\n%mysql.quarkus.datasource.username=old\n", encoding="utf-8")
        (res / "application-mysql.properties").write_text("# db\nquarkus.datasource.jdbc.url=jdbc:mysql://h/db\nquarkus.datasource.username=pc\nspring.jpa.database=MYSQL\n", encoding="utf-8")
        (res / "application-hsqldb.properties").write_text("quarkus.datasource.jdbc.url=jdbc:hsqldb:mem:x\n", encoding="utf-8")
        ch: list = []
        mod.merge_profile_files(root, ch)
        text = (res / "application.properties").read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
        want = ["quarkus.http.port=9966", "%mysql.quarkus.datasource.username=old", "%hsqldb.quarkus.datasource.jdbc.url=jdbc:hsqldb:mem:x", "%mysql.quarkus.datasource.jdbc.url=jdbc:mysql://h/db", "%mysql.spring.jpa.database=MYSQL"]
        if lines != want:
            return _fail("profile merge must prefix every key, keep an existing %%profile key, skip comments, and process files in name order: %s" % lines)
        if (res / "application-mysql.properties").exists() or (res / "application-hsqldb.properties").exists():
            return _fail("merged profile files must be removed")
        if [c["op"] for c in ch] != ["properties.merge-profile", "properties.merge-profile"] or ch[1]["keys"] != 2:
            return _fail("changes must record each merge with its key count: %s" % ch)
    return 0


def _jakarta_imports_case() -> int:
    import importlib.util
    import json

    spec = importlib.util.spec_from_file_location("bootstrap_destination", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    catalog = json.loads((GOLDEN / ".hermes" / "planning" / "catalogs" / "compat-mapping.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="jak-") as td:
        root = Path(td); d = root / "src" / "main" / "java" / "a"; d.mkdir(parents=True)
        src = ("package a;\n\nimport java.util.List;\nimport javax.persistence.Id;\nimport javax.validation.constraints.*;\nimport javax.xml.parsers.DocumentBuilder;\n"
               "import static javax.persistence.GenerationType.IDENTITY;\n\n/** javax.persistence in a comment stays */\npublic class A { String s = \"javax.persistence\"; }\n")
        (d / "A.java").write_text(src, encoding="utf-8")
        t = root / "src" / "test" / "java" / "a"; t.mkdir(parents=True)
        (t / "ATest.java").write_text("package a;\nimport javax.persistence.Id;\nclass ATest {}\n", encoding="utf-8")
        ch: list = []; blocks: list = []
        mod.rename_jakarta_imports(root, catalog, ch, blocks)
        if blocks:
            return _fail("jakarta rename blocked: %s" % blocks)
        out = (d / "A.java").read_text(encoding="utf-8")
        if "import jakarta.persistence.Id;" not in out or "import jakarta.validation.constraints.*;" not in out or "import static jakarta.persistence.GenerationType.IDENTITY;" not in out:
            return _fail("javax imports (member, wildcard, static) must become jakarta: %s" % out)
        if "import javax.xml.parsers.DocumentBuilder;" not in out or "javax.persistence in a comment stays" not in out or 'String s = "javax.persistence"' not in out:
            return _fail("a package with no rename, comments and string literals must be untouched: %s" % out)
        if (t / "ATest.java").read_text(encoding="utf-8") != "package a;\nimport jakarta.persistence.Id;\nclass ATest {}\n":
            return _fail("test sources get the namespace rename too (a test that cannot compile makes the measure unknown)")
        paths = {c["path"]: c["imports"] for c in ch}
        if paths != {"src/main/java/a/A.java": 3, "src/test/java/a/ATest.java": 1}:
            return _fail("the receipt records every renamed file and its import count: %s" % paths)
        ch2: list = []
        mod.rename_jakarta_imports(root, catalog, ch2, blocks)
        if ch2 or blocks:
            return _fail("a second run changes nothing: %s %s" % (ch2, blocks))
    return 0


def _version_precedence_case() -> int:
    """A tooling pin that names an artifact decides its version; the legacy
    build's resolved version is the fallback for artifacts nobody decided
    about; an artifact with neither blocks."""
    import importlib.util
    import json
    import xml.etree.ElementTree as ET

    spec = importlib.util.spec_from_file_location("bootstrap_destination", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    with tempfile.TemporaryDirectory(prefix="vers-") as td:
        root = Path(td)
        (root / "evidence" / "producers").mkdir(parents=True)
        (root / ".derived").mkdir(parents=True, exist_ok=True)
        platform = {"group_id": "com.redhat.quarkus.platform", "bom_artifact_id": "quarkus-bom", "version": "9.9.9"}
        probe = root / mod.BOM_MANAGED
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text(json.dumps({"bom": {"group_id": platform["group_id"], "artifact_id": platform["bom_artifact_id"], "version": platform["version"]}, "managed": ["io.quarkus:quarkus-rest"]}), encoding="utf-8")
        (root / "evidence" / "producers" / "build.json").write_text(json.dumps({"managed_versions": {"org.assertj:assertj-core": "3.21.0", "org.acme:only-legacy": "1.0.0"}}), encoding="utf-8")
        # the shape load_pins returns: the inner mapping, key -> pin
        pins = {"assertj_core": {"group_id": "org.assertj", "artifact_id": "assertj-core", "version": "3.27.7"},
                "mapstruct": {"status": "unpinned"}}
        pom = """<project xmlns="http://maven.apache.org/POM/4.0.0"><dependencies>
<dependency><groupId>org.assertj</groupId><artifactId>assertj-core</artifactId><scope>test</scope></dependency>
<dependency><groupId>org.acme</groupId><artifactId>only-legacy</artifactId></dependency>
<dependency><groupId>io.quarkus</groupId><artifactId>quarkus-rest</artifactId></dependency>
<dependency><groupId>org.acme</groupId><artifactId>nobody-decided</artifactId></dependency>
<dependency><groupId>org.assertj</groupId><artifactId>assertj-core</artifactId><version>3.21.0</version><classifier>disagrees</classifier></dependency>
<dependency><groupId>org.acme</groupId><artifactId>by-property</artifactId><version>${acme.version}</version></dependency>
</dependencies></project>"""
        project = ET.fromstring(pom)
        deps = project.find(mod.q("dependencies"))
        ch: list = []; blocks: list = []
        mod.carry_versions(root, platform, deps, blocks, ch, pins)
        got = {mod.text(d, "artifactId"): mod.text(d, "version") for d in deps.findall(mod.q("dependency"))}
        if got.get("assertj-core") != "3.27.7":
            return _fail("a pin that names the artifact must decide its version: %s" % got)
        if got.get("only-legacy") != "1.0.0":
            return _fail("an artifact no pin names falls back to the legacy resolved version: %s" % got)
        if got.get("quarkus-rest"):
            return _fail("a BOM-managed artifact must stay version-less: %s" % got)
        if [b["class"] for b in blocks] != ["VERSION_UNMANAGED"] or blocks[0]["subject"] != "org.acme:nobody-decided":
            return _fail("an artifact with no pin, no BOM entry and no legacy version must block: %s" % blocks)
        vers = [mod.text(d, "version") for d in deps.findall(mod.q("dependency")) if mod.text(d, "artifactId") == "assertj-core"]
        if vers != ["3.27.7", "3.27.7"]:
            return _fail("a literal version that disagrees with the pin must be corrected: %s" % vers)
        if [mod.text(d, "version") for d in deps.findall(mod.q("dependency")) if mod.text(d, "artifactId") == "by-property"] != ["${acme.version}"]:
            return _fail("a version carried by a property must be left to its property")
        if not any(c["op"] == "pom.repin-version" and c.get("was") == "3.21.0" for c in ch):
            return _fail("the correction must record what it replaced: %s" % ch)
        provs = {c["gav"]: c["provenance"] for c in ch}
        if provs.get("org.assertj:assertj-core:3.27.7") != "pins.json assertj_core":
            return _fail("the change must record which pin decided: %s" % provs)
    return 0


def _reapply_catalog_case() -> int:
    """--reapply-catalog: a catalog row that arrived after the bootstrap ran
    reaches an already bootstrapped tree, and accepted work survives it."""
    import json
    import re
    with tempfile.TemporaryDirectory(prefix="reapply-") as td:
        root = specimens.build_dest(Path(td) / "d", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        pipeline.assemble_bundle(root)
        p0 = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)], text=True, capture_output=True)
        if p0.returncode != 0:
            return _fail("reapply: the bootstrap must pass first: %s%s" % (p0.stdout, p0.stderr))
        pom = root / "pom.xml"
        bootstrapped = pom.read_text(encoding="utf-8")
        if "assertj-core" not in bootstrapped:
            return _fail("test setup: the mapping must put the test-scoped assertion library in the pom")
        # wind the pom back to what a run bootstrapped BEFORE the catalog gained
        # these rows: no test-scoped assertion library, no generated-source
        # folder pinned. Then add an accepted card edit that must survive.
        wound = re.sub(r"\s*<dependency>\s*<groupId>org\.assertj</groupId>.*?</dependency>", "", bootstrapped, flags=re.S)
        wound = re.sub(r"\s*<sourceFolder>[^<]*</sourceFolder>", "", wound)
        wound = wound.replace("</dependencies>", "  <dependency>\n      <groupId>org.acme</groupId>\n      <artifactId>accepted-by-a-card</artifactId>\n      <version>1.2.3</version>\n    </dependency>\n  </dependencies>", 1)
        # the destination also carries the generator this specimen's pom did not:
        # its configuration is a catalog row too, and reapply must reach it
        wound = wound.replace("<plugins>", "<plugins>\n      <plugin>\n        <groupId>org.openapitools</groupId>\n        <artifactId>openapi-generator-maven-plugin</artifactId>\n        <version>5.2.1</version>\n        <executions><execution><goals><goal>generate</goal></goals><configuration><generatorName>spring</generatorName><configOptions><java8>true</java8></configOptions></configuration></execution></executions>\n      </plugin>", 1)
        pom.write_text(wound, encoding="utf-8")
        t = root / "src" / "test" / "java" / "org" / "acme"
        t.mkdir(parents=True, exist_ok=True)
        (t / "LegacyNamespaceTest.java").write_text("package org.acme;\nimport javax.validation.Validator;\nclass LegacyNamespaceTest { Validator v; }\n", encoding="utf-8")
        p1 = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--reapply-catalog"], text=True, capture_output=True)
        if p1.returncode != 0:
            return _fail("reapply-catalog: %s%s" % (p1.stdout, p1.stderr[-400:]))
        got = pom.read_text(encoding="utf-8")
        if "assertj-core" not in got or "<sourceFolder>src/main/java</sourceFolder>" not in got:
            return _fail("reapply-catalog must add the test-scoped artifact and pin the generated-source folder: %s" % got[-600:])
        if "accepted-by-a-card" not in got:
            return _fail("reapply-catalog must leave accepted card work in the pom alone")
        if "jakarta.validation.Validator" not in (t / "LegacyNamespaceTest.java").read_text(encoding="utf-8"):
            return _fail("reapply-catalog must apply the namespace rename to test sources")
        rec = load_json(root / "evidence/producers/bootstrap.json")
        ops = [c["op"] for c in rec["changes"]]
        # a stale refusal of the class this mode measures must clear when the
        # cause is gone, or a corrected decision leaves the receipt blocked
        # (and admission INCONCLUSIVE) for the rest of the run
        rec["blocks"] = [{"class": "VERSION_UNMANAGED", "subject": "old:gone", "detail": "stale"},
                         {"class": "MAIN_CLASS_NOT_TRIVIAL", "subject": "org.acme.App", "detail": "not this mode's question"}]
        rec["status"] = "blocked"
        (root / "evidence/producers/bootstrap.json").write_text(json.dumps(rec), encoding="utf-8")
        p1b = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--reapply-catalog"], text=True, capture_output=True)
        rec_b = load_json(root / "evidence/producers/bootstrap.json")
        classes = [b["class"] for b in rec_b.get("blocks") or []]
        if p1b.returncode != 0 or classes != ["MAIN_CLASS_NOT_TRIVIAL"] or rec_b["status"] != "blocked":
            return _fail("reapply must recompute its own block classes and leave the others: rc=%s %s %s" % (p1b.returncode, classes, rec_b["status"]))
        rec_b["blocks"] = []; rec_b["status"] = "blocked"
        (root / "evidence/producers/bootstrap.json").write_text(json.dumps(rec_b), encoding="utf-8")
        subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--reapply-catalog"], text=True, capture_output=True)
        if load_json(root / "evidence/producers/bootstrap.json")["status"] != "ok":
            return _fail("a receipt with no blocks left must go back to ok")
        rec = load_json(root / "evidence/producers/bootstrap.json")
        if rec["status"] != "ok" or "pom.add-extension" not in ops:
            return _fail("the reapplied changes must be appended to the bootstrap receipt: %s %s" % (rec["status"], sorted(set(ops))))
        before = tree_hash(root)
        p2 = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--reapply-catalog"], text=True, capture_output=True)
        if p2.returncode != 0 or tree_hash(root) != before:
            return _fail("a second reapply-catalog must change nothing: rc=%s" % p2.returncode)
        # control: the mode is refused where there is nothing to reapply to
        (root / "evidence/producers/bootstrap.json").unlink()
        p3 = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--reapply-catalog"], text=True, capture_output=True)
        if p3.returncode != 1 or "BOOTSTRAP_NO_RECEIPT" not in p3.stderr:
            return _fail("reapply-catalog on a tree that was never bootstrapped must refuse: rc=%s %s" % (p3.returncode, p3.stderr[-200:]))
    return 0


def main() -> int:
    if _plugin_config_case() or _profile_merge_case() or _jakarta_imports_case() or _version_precedence_case() or _reapply_catalog_case():
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
    print("OK: bootstrap-destination (trivial launcher deleted; second run preserves the tree; @Bean launcher kept + BOOTSTRAP_BLOCKED; unmapped starter kept + block; Maven settings wiring required; pinned version beats the legacy carry / VERSION_UNMANAGED / BOM_PROBE_MISSING; ADR-retired sources deleted with provenance / stale path blocks; reapply-catalog carries a late row and refuses without a receipt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
