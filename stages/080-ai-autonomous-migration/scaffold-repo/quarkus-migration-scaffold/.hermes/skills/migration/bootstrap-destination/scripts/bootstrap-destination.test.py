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
            return _fail("reapply-catalog: %s%s" % (layout, p1.stdout, p1.stderr[-400:]))
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


def _datasource_case() -> int:
    """The decided datasource lands as unprefixed keys plus the documented
    extension; an undecided or mismatched one blocks instead of guessing."""
    import json
    def _with_db_assets(root: Path) -> Path:
        """The decision says the SOURCE assets own schema and seed, so the
        frozen source carries them and the bootstrap imports them."""
        d = root / ".derived" / "frozen-input" / "src" / "main" / "resources" / "db" / "postgresql"
        d.mkdir(parents=True, exist_ok=True)
        (d / "initDB.sql").write_text("CREATE TABLE owners (id INT PRIMARY KEY);\n", encoding="utf-8")
        (d / "populateDB.sql").write_text("INSERT INTO owners VALUES (1);\n", encoding="utf-8")
        return root

    with tempfile.TemporaryDirectory(prefix="ds-") as td:
        root = _with_db_assets(specimens.build_dest(Path(td) / "d", specimens.specimen("http"), decisions=specimens.admitted_decisions()))
        pipeline.assemble_bundle(root)
        p0 = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)], text=True, capture_output=True)
        if p0.returncode != 0:
            return _fail("bootstrap with a decided datasource must pass: %s%s" % (p0.stdout, p0.stderr[-400:]))
        props = (root / "src/main/resources/application.properties").read_text(encoding="utf-8")
        want = {
            "quarkus.datasource.db-kind=postgresql",
            "quarkus.datasource.jdbc.url=${FIXTURE_DB_URL}",
            "quarkus.datasource.username=${FIXTURE_DB_USER}",
            "quarkus.datasource.password=${FIXTURE_DB_PASSWORD}",
            "quarkus.hibernate-orm.database.generation=none",
        }
        lines = {l.strip() for l in props.splitlines()}
        if not want <= lines:
            return _fail("the effective datasource must be unprefixed in application.properties, missing %s" % sorted(want - lines))
        if "quarkus-jdbc-postgresql" not in (root / "pom.xml").read_text(encoding="utf-8"):
            return _fail("the documented JDBC extension for the decided db_kind must be in the pom")
        rec = load_json(root / "evidence/producers/bootstrap.json")
        ops = {c["op"] for c in rec["changes"]}
        if "properties.datasource-set" not in ops:
            return _fail("the receipt must record the datasource rendering: %s" % sorted(ops))
        # a second run changes nothing
        before = tree_hash(root)
        subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--reapply-catalog"], text=True, capture_output=True)
        if tree_hash(root) != before:
            return _fail("rendering the same decision twice must change nothing")
        # and the extension comes back when it is missing entirely
        import re as _re
        pom_p = root / "pom.xml"
        pom_txt = pom_p.read_text(encoding="utf-8")
        stripped = _re.sub(r"\s*<dependency>\s*<groupId>io\.quarkus</groupId>\s*<artifactId>quarkus-jdbc-postgresql</artifactId>\s*</dependency>", "", pom_txt, flags=_re.S)
        if stripped == pom_txt:
            return _fail("test setup: the JDBC extension element was not found to remove")
        pom_p.write_text(stripped, encoding="utf-8")
        pr = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--reapply-catalog"], text=True, capture_output=True)
        rec = load_json(root / "evidence/producers/bootstrap.json")
        added = [c for c in rec["changes"] if str(c.get("gav") or "") == "io.quarkus:quarkus-jdbc-postgresql"]
        if pr.returncode != 0 or "quarkus-jdbc-postgresql" not in pom_p.read_text(encoding="utf-8") or not added:
            return _fail("the JDBC extension for the decided engine must be restored and recorded: rc=%s %s" % (pr.returncode, pr.stderr[-200:]))
        pom_p.write_text(pom_txt, encoding="utf-8")

        # the M2 checker agrees with the rendered tree, and refuses each way it
        # can drift: a key removed, a literal credential, a second driver
        CHECK = HERE / "check-datasource-decision.py"
        pc = subprocess.run([sys.executable, str(CHECK), str(root)], text=True, capture_output=True)
        if pc.returncode != 0:
            return _fail("the M2 datasource checker must agree with the bootstrap it checks: %s%s" % (pc.stdout, pc.stderr[-300:]))
        prop_p = root / "src/main/resources/application.properties"
        prop_txt = prop_p.read_text(encoding="utf-8")
        prop_p.write_text(prop_txt.replace("quarkus.datasource.db-kind=postgresql", "%prod.quarkus.datasource.db-kind=postgresql"), encoding="utf-8")
        pc = subprocess.run([sys.executable, str(CHECK), str(root)], text=True, capture_output=True)
        if pc.returncode != 1 or "not set unprefixed" not in pc.stderr:
            return _fail("a db-kind that exists only under a profile must refuse: rc=%s %s" % (pc.returncode, pc.stderr[-300:]))
        # and a profile override that points at ANOTHER database must refuse,
        # because that is what the destination would actually use
        prop_p.write_text(prop_txt + "\n%prod.quarkus.datasource.jdbc.url=jdbc:postgresql://wrong-db:5432/wrong\n", encoding="utf-8")
        pc = subprocess.run([sys.executable, str(CHECK), str(root)], text=True, capture_output=True)
        if pc.returncode != 1 or "under the prod profile" not in pc.stderr:
            return _fail("an active-profile override pointing elsewhere must refuse: rc=%s %s" % (pc.returncode, pc.stderr[-400:]))
        # an override under a profile this run did not select is reported too
        prop_p.write_text(prop_txt + "\n%staging.quarkus.datasource.jdbc.url=jdbc:postgresql://other-db:5432/other\n", encoding="utf-8")
        pc = subprocess.run([sys.executable, str(CHECK), str(root)], text=True, capture_output=True)
        if pc.returncode != 1 or "another profile would configure a different database" not in pc.stderr:
            return _fail("a different profile pointing at another database must be reported: rc=%s %s" % (pc.returncode, pc.stderr[-400:]))
        prop_p.write_text(prop_txt, encoding="utf-8")
        prop_p.write_text(prop_txt.replace("${FIXTURE_DB_PASSWORD}", "hunter2"), encoding="utf-8")
        pc = subprocess.run([sys.executable, str(CHECK), str(root)], text=True, capture_output=True)
        if pc.returncode != 1 or "environment reference" not in pc.stderr:
            return _fail("a literal credential must refuse: rc=%s %s" % (pc.returncode, pc.stderr[-300:]))
        prop_p.write_text(prop_txt, encoding="utf-8")
        pom_p2 = root / "pom.xml"
        pom_keep = pom_p2.read_text(encoding="utf-8")
        pom_p2.write_text(pom_keep.replace("</dependencies>", "  <dependency>\n      <groupId>io.quarkus</groupId>\n      <artifactId>quarkus-jdbc-mysql</artifactId>\n    </dependency>\n  </dependencies>", 1), encoding="utf-8")
        pc = subprocess.run([sys.executable, str(CHECK), str(root)], text=True, capture_output=True)
        if pc.returncode != 1 or "decision drift" not in pc.stderr:
            return _fail("a second JDBC extension must refuse: rc=%s %s" % (pc.returncode, pc.stderr[-300:]))
        pom_p2.write_text(pom_keep, encoding="utf-8")

        # an engine the platform documents no extension for blocks, and says so
        bad = specimens.admitted_decisions()
        bad["datasource"] = dict(specimens.FIXTURE_DATASOURCE, db_kind="hsqldb", jdbc_extension="org.hsqldb:hsqldb")
        b = _with_db_assets(specimens.build_dest(Path(td) / "bad", specimens.specimen("http"), decisions=bad))
        pipeline.assemble_bundle(b)
        pb = subprocess.run([sys.executable, str(SCRIPT), "--root", str(b)], text=True, capture_output=True)
        if pb.returncode != 1 or "DATASOURCE_UNSUPPORTED" not in pb.stderr:
            return _fail("an undocumented db_kind must block: rc=%s %s" % (pb.returncode, pb.stderr[-300:]))

        # a decision naming the wrong extension for its engine blocks too
        wrong = specimens.admitted_decisions()
        wrong["datasource"] = dict(specimens.FIXTURE_DATASOURCE, jdbc_extension="io.quarkus:quarkus-jdbc-mysql")
        w = _with_db_assets(specimens.build_dest(Path(td) / "wrong", specimens.specimen("http"), decisions=wrong))
        pipeline.assemble_bundle(w)
        pw = subprocess.run([sys.executable, str(SCRIPT), "--root", str(w)], text=True, capture_output=True)
        if pw.returncode != 1 or "DATASOURCE_EXTENSION_MISMATCH" not in pw.stderr:
            return _fail("an extension that does not match the engine must block: rc=%s %s" % (pw.returncode, pw.stderr[-300:]))

        # an undecided datasource never reaches a worker: admission stays INCONCLUSIVE
        none = specimens.admitted_decisions()
        none.pop("datasource")
        n = _with_db_assets(specimens.build_dest(Path(td) / "none", specimens.specimen("http"), decisions=none))
        pipeline.assemble_bundle(n)
        pn = subprocess.run([sys.executable, str(SCRIPT), "--root", str(n)], text=True, capture_output=True)
        if pn.returncode != 1 or "DECISIONS_INVALID" not in pn.stderr:
            return _fail("a decisions.yaml with no datasource block must block: rc=%s %s" % (pn.returncode, pn.stderr[-300:]))
    return 0


def _build_profile_case() -> int:
    """A profile the legacy activated, and sources still gated on it: the
    destination must say what happens to them, or the beans vanish silently."""
    import json
    import re as _re
    with tempfile.TemporaryDirectory(prefix="prof-") as td:
        root = specimens.build_dest(Path(td) / "d", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        frozen = root / ".derived" / "frozen-input"
        res = frozen / "src" / "main" / "resources"
        res.mkdir(parents=True, exist_ok=True)
        (res / "application.properties").write_text("spring.profiles.active=hsqldb,spring-data-jpa\n", encoding="utf-8")
        gated = frozen / "src" / "main" / "java" / "org" / "acme" / "clinic" / "owner" / "SpringDataOwnerRepository.java"
        gated.parent.mkdir(parents=True, exist_ok=True)
        gated.write_text("package org.acme.clinic.owner;\n"
                         "import org.springframework.context.annotation.Profile;\n"
                         "@Profile(\"spring-data-jpa\")\n"
                         "public interface SpringDataOwnerRepository {}\n", encoding="utf-8")
        pipeline.assemble_bundle(root)
        p0 = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)], text=True, capture_output=True)
        if p0.returncode != 1 or "BUILD_PROFILE_UNDECIDED" not in p0.stderr:
            return _fail("a profile the legacy activated, still gating a source, must block: rc=%s %s" % (p0.returncode, p0.stderr[-400:]))
        if "spring-data-jpa" not in p0.stderr:
            return _fail("the block must name the profile: %s" % p0.stderr[-200:])

        # decided: the destination builds with those profiles
        decided = specimens.admitted_decisions()
        decided["build_profiles"] = {"adr": "ADR-001", "active": ["prod", "spring-data-jpa"]}
        d2 = specimens.build_dest(Path(td) / "decided", specimens.specimen("http"), decisions=decided)
        f2 = d2 / ".derived" / "frozen-input"
        (f2 / "src" / "main" / "resources").mkdir(parents=True, exist_ok=True)
        (f2 / "src" / "main" / "resources" / "application.properties").write_text("spring.profiles.active=hsqldb,spring-data-jpa\n", encoding="utf-8")
        g2 = f2 / "src" / "main" / "java" / "org" / "acme" / "clinic" / "owner" / "SpringDataOwnerRepository.java"
        g2.parent.mkdir(parents=True, exist_ok=True)
        g2.write_text(gated.read_text(encoding="utf-8"), encoding="utf-8")
        pipeline.assemble_bundle(d2)
        p1 = subprocess.run([sys.executable, str(SCRIPT), "--root", str(d2)], text=True, capture_output=True)
        if p1.returncode != 0:
            return _fail("a decided build profile must pass: %s%s" % (p1.stdout, p1.stderr[-300:]))
        props = (d2 / "src/main/resources/application.properties").read_text(encoding="utf-8")
        if "quarkus.profile=prod,spring-data-jpa" not in props:
            return _fail("the decided profiles must reach the destination: %s" % props[-300:])
        rec = load_json(d2 / "evidence/producers/bootstrap.json")
        if not any(c["op"] == "properties.build-profile" for c in rec["changes"]):
            return _fail("the receipt must record which profiles were set")
        # the decided profiles must reach the build: every mvn reads
        # .mvn/maven.config, and its settings wiring is kept
        cfg = (d2 / ".mvn" / "maven.config").read_text(encoding="utf-8").splitlines() if (d2 / ".mvn" / "maven.config").is_file() else []
        if "-Dquarkus.profile=prod,spring-data-jpa" not in cfg:
            return _fail("the decided build profiles must reach the build through .mvn/maven.config: %s" % cfg)
        if sum(1 for ln in cfg if "-Dquarkus.profile=" in ln) != 1:
            return _fail("one build-profile argument, not a stack of them: %s" % cfg)
        if not any(c["op"] == "maven-config.build-profile" for c in rec["changes"]):
            return _fail("the receipt must record the build-profile wiring")
        before = tree_hash(d2)
        subprocess.run([sys.executable, str(SCRIPT), "--root", str(d2)], text=True, capture_output=True)
        if tree_hash(d2) != before:
            return _fail("setting the same profiles twice must change nothing")

        # decided the other way: the gates are retired. Enumerated, one row per
        # condition, bound to the inventory it was read from -- a bare
        # retire_gates flag retires nothing and leaves the condition unaccounted.
        REL = "src/main/java/org/acme/clinic/owner/SpringDataOwnerRepository.java"

        ROW = {"path": REL, "type": "SpringDataOwnerRepository", "member": "",
               "annotation": "Profile", "profile": "spring-data-jpa",
               "reason": "the alternative this selected between is retired"}

        def _run_retired(name, bp):
            dec = specimens.admitted_decisions()
            dec["build_profiles"] = bp
            d = specimens.build_dest(Path(td) / name, specimens.specimen("http"), decisions=dec)
            f = d / ".derived" / "frozen-input"
            (f / "src" / "main" / "resources").mkdir(parents=True, exist_ok=True)
            (f / "src" / "main" / "resources" / "application.properties").write_text("spring.profiles.active=hsqldb,spring-data-jpa\n", encoding="utf-8")
            g = f / REL
            g.parent.mkdir(parents=True, exist_ok=True)
            g.write_text(gated.read_text(encoding="utf-8"), encoding="utf-8")
            pipeline.assemble_bundle(d)
            return d, subprocess.run([sys.executable, str(SCRIPT), "--root", str(d)], text=True, capture_output=True)

        d3, p2 = _run_retired("retired-blanket", {"adr": "ADR-001", "active": [], "retire_gates": True})
        if p2.returncode == 0 or "BUILD_PROFILE_UNACCOUNTED" not in p2.stderr:
            return _fail("a blanket retire_gates retires nothing and must leave the condition unaccounted: %s" % p2.stderr[-300:])
        inv = hashlib.sha256((d3 / "evidence/type-inventory.json").read_bytes()).hexdigest()

        d4, p3 = _run_retired("retired-unbound", {"adr": "ADR-001", "active": [], "retire_gates": True, "retire": [ROW]})
        if p3.returncode == 0 or "PROFILE_RETIREMENT_UNBOUND" not in p3.stderr:
            return _fail("an enumeration bound to no inventory must refuse: %s" % p3.stderr[-300:])

        d5, p4 = _run_retired("retired-stale", {"adr": "ADR-001", "active": [], "retire_gates": True,
                                                "retire": [ROW], "inventory_sha256": "deadbeef" * 8})
        if p4.returncode == 0 or "PROFILE_RETIREMENT_STALE" not in p4.stderr:
            return _fail("an enumeration bound to another tree's inventory must refuse: %s" % p4.stderr[-300:])

        absent = dict(ROW, member="findByLastName")
        d6, p5 = _run_retired("retired-absent", {"adr": "ADR-001", "active": [], "retire_gates": True,
                                                 "retire": [absent], "inventory_sha256": inv})
        if p5.returncode == 0 or "PROFILE_RETIREMENT_ABSENT" not in p5.stderr:
            return _fail("a row that describes a condition this tree does not have must refuse: %s" % p5.stderr[-300:])

        d7, p6 = _run_retired("retired-enumerated", {"adr": "ADR-001", "active": [], "retire_gates": True,
                                                     "retire": [ROW], "inventory_sha256": inv})
        if p6.returncode != 0:
            return _fail("an enumerated retirement bound to this tree must pass: %s%s" % (p6.stdout, p6.stderr[-400:]))
        text = (d7 / REL).read_text(encoding="utf-8")
        if "@Profile" in text:
            return _fail("the enumerated condition must be gone from the destination: %s" % text)
        if "import org.springframework.context.annotation.Profile" in text:
            return _fail("the import is dead once the last condition in the file is gone: %s" % text)
        if text.count("{") != gated.read_text(encoding="utf-8").count("{"):
            return _fail("retirement must not disturb the rest of the file: %s" % text)
        if "quarkus.profile=" in (d7 / "src/main/resources/application.properties").read_text(encoding="utf-8"):
            return _fail("retiring the gates activates no profile")
        if (d7 / ".mvn" / "maven.config").is_file() and "-Dquarkus.profile=" in (d7 / ".mvn" / "maven.config").read_text(encoding="utf-8"):
            return _fail("retiring the gates wires no build profile either")
        rec = load_json(d7 / "evidence/producers/bootstrap.json")
        row = next((c for c in rec["changes"] if c["op"] == "source.retire-profile-condition"), None)
        if not row or row["path"] != REL or "spring-data-jpa" not in row["value"]:
            return _fail("the receipt must record exactly what was retired: %s" % row)

        # the proposer proposes and accepts nothing
        d8, _ = _run_retired("proposed", {"adr": "ADR-001", "active": ["prod"]})
        before = (d8 / "decisions.yaml").read_bytes()
        pp = subprocess.run([sys.executable, str(HERE / "propose-profile-retirement.py"), "--root", str(d8)],
                            text=True, capture_output=True)
        if pp.returncode != 0 or "profile: spring-data-jpa" not in pp.stdout or "inventory_sha256" not in pp.stdout:
            return _fail("the proposer must emit the rows and the binding: %s%s" % (pp.stdout[-300:], pp.stderr[-200:]))
        if (d8 / "decisions.yaml").read_bytes() != before:
            return _fail("the proposer must never write decisions.yaml")
    return 0


def _retire_offsets_case() -> int:
    """The compiler counts UTF-16 code units; Python counts code points. One
    emoji in a comment moved every offset by one and the cut landed inside
    `public`, producing `@public class Config` with a receipt saying it had
    worked."""
    import hashlib
    import json as _json
    import shutil as _shutil

    if not _shutil.which("javac"):
        return 0
    sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
    import importlib.util

    spec = importlib.util.spec_from_file_location("_bd_case", SCRIPT)
    bd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bd)

    stub = ("package org.springframework.context.annotation;\nimport java.lang.annotation.*;\n"
            "@Retention(RetentionPolicy.RUNTIME) @Target({ElementType.TYPE, ElementType.METHOD})\n"
            "public @interface Profile { String[] value(); }\n")
    for comment, label in (("// ordinary", "ascii"), ("// \U0001f642", "astral")):
        with tempfile.TemporaryDirectory(prefix="retire-%s-" % label) as td:
            root = Path(td)
            (root / ".hermes").mkdir(parents=True)
            (root / ".hermes/pins.json").write_text('{"pins":{"quarkus_platform":{"java_release":21}}}')
            src = root / "src/main/java/p/Config.java"
            src.parent.mkdir(parents=True)
            src.write_text('package p;\nimport org.springframework.context.annotation.Profile;\n'
                           '%s\n@Profile("x")\npublic class Config {}\n' % comment, encoding="utf-8")
            st = root / ".stub/org/springframework/context/annotation/Profile.java"
            st.parent.mkdir(parents=True)
            st.write_text(stub)
            cls = root / ".cls"
            cls.mkdir()
            subprocess.run(["javac", "-d", str(cls), str(st)], check=True, capture_output=True)
            cp = root / "verification/build/.work/classpath.txt"
            cp.parent.mkdir(parents=True)
            cp.write_text(str(cls))
            (root / "evidence").mkdir(exist_ok=True)
            (root / "evidence/type-inventory.json").write_text("{}")
            rows, why = bd.all_profile_conditions(root)
            if why or len(rows) != 1:
                return _fail("%s: one condition, read from the model: %s %s" % (label, rows, why))
            inv = hashlib.sha256((root / "evidence/type-inventory.json").read_bytes()).hexdigest()
            dec = {"adrs": [{"id": "ADR-X", "status": "accepted"}],
                   "build_profiles": {"adr": "ADR-X", "active": ["prod"], "inventory_sha256": inv,
                                      "retire": [{k: rows[0][k] for k in ("path", "type", "member", "annotation", "profile")}]}}
            changes, blocks = [], []
            bd.apply_profile_retirement(root, dec, changes, blocks)
            if blocks:
                return _fail("%s: a resolved condition must retire cleanly: %s" % (label, blocks))
            out = subprocess.run(["javac", "-d", str(root / ".out"), "-classpath", str(cls), str(src)],
                                 capture_output=True, text=True)
            if out.returncode != 0:
                return _fail("%s: retirement must leave valid Java: %s\n%s" % (label, src.read_text(), out.stderr[:200]))
            if "@Profile" in src.read_text(encoding="utf-8"):
                return _fail("%s: the condition must be gone: %s" % (label, src.read_text()))
    return 0


def _datasource_checker_integration_case() -> int:
    """THE MISSING GATE: bootstrap and its own checker must agree on the tree
    bootstrap just wrote, for a specimen carrying the legacy's whole driver and
    profile mix -- and reapplying must change nothing.

    Measured on the live v8 run (2026-09-11): bootstrap PASSed, then
    check-datasource-decision.py REFUSED the same tree with two findings, and
    M2 blocked. A worker cannot resolve a contradiction between two parts of
    the harness, and identical retries cannot either. Unit coverage on each
    side separately never saw it."""
    for layout in ("separate-files", "inline"):
        rc = _datasource_checker_layout(layout)
        if rc:
            return rc
    return 0


def _datasource_checker_layout(layout: str) -> int:
    """One layout of the legacy's profile configuration.

    separate-files  application-<profile>.properties, as the real specimen
                    keeps them -- the bootstrap re-imports and re-merges these
                    on EVERY run, so the removal path repeats every time
    inline          %profile keys already in application.properties -- the
                    removal runs ONCE and later runs have nothing to remove,
                    which is where a note that is stripped but only rewritten
                    when something was removed disappears on run 2
    """
    CHECKER = HERE / "check-datasource-decision.py"
    LEGACY_PROPS = ("spring.profiles.active=hsqldb,spring-data-jpa\n"
                    "%hsqldb.quarkus.datasource.jdbc.url=jdbc:hsqldb:mem:petclinic\n"
                    "%mysql.quarkus.datasource.jdbc.url=jdbc:mysql://localhost:3306/petclinic\n"
                    "%mysql.quarkus.datasource.password=petclinic\n"
                    "%postgresql.quarkus.datasource.jdbc.url=jdbc:postgresql://localhost:5432/petclinic\n"
                    "%postgresql.quarkus.datasource.password=petclinic\n")
    with tempfile.TemporaryDirectory(prefix="ds-integ-") as td:
        decided = specimens.admitted_decisions()
        decided["build_profiles"] = {"adr": "ADR-001", "active": ["prod", "spring-data-jpa"]}
        root = specimens.build_dest(Path(td) / "d", specimens.specimen("http"), decisions=decided)
        frozen = root / ".derived" / "frozen-input"

        # the legacy's mix, where the legacy actually keeps it
        fpom = frozen / "pom.xml"
        xml = fpom.read_text(encoding="utf-8")
        drivers = ("  <dependencies>\n"
                   "    <dependency><groupId>mysql</groupId><artifactId>mysql-connector-java</artifactId></dependency>\n"
                   "    <dependency><groupId>org.postgresql</groupId><artifactId>postgresql</artifactId></dependency>\n")
        if "  <dependencies>\n" not in xml:
            return _fail("the frozen specimen pom has no dependencies block to extend")
        fpom.write_text(xml.replace("  <dependencies>\n", drivers, 1), encoding="utf-8")
        res = frozen / "src" / "main" / "resources"
        res.mkdir(parents=True, exist_ok=True)
        # The real specimen keeps each profile in its OWN Spring file, and the
        # bootstrap re-imports and re-merges them on every run. A fixture that
        # inlined them made the idempotence assertion hollow: nothing was left
        # to re-merge, so nothing could grow (measured live on v8, where the
        # file grew three comment lines per bootstrap).
        frozen_main = "spring.profiles.active=hsqldb,spring-data-jpa\n" if layout == "separate-files" else LEGACY_PROPS
        if layout == "separate-files":
            (res / "application.properties").write_text(frozen_main, encoding="utf-8")
            (res / "application-hsqldb.properties").write_text(
                "spring.datasource.url=jdbc:hsqldb:mem:petclinic\nspring.datasource.username=sa\n", encoding="utf-8")
            (res / "application-mysql.properties").write_text(
                "spring.datasource.url=jdbc:mysql://localhost:3306/petclinic\nspring.datasource.password=petclinic\n", encoding="utf-8")
            (res / "application-postgresql.properties").write_text(
                "spring.datasource.url=jdbc:postgresql://localhost:5432/petclinic\nspring.datasource.password=petclinic\n", encoding="utf-8")
        else:
            (res / "application.properties").write_text(LEGACY_PROPS, encoding="utf-8")
        db = res / "db" / "postgresql"
        db.mkdir(parents=True, exist_ok=True)
        (db / "initDB.sql").write_text("CREATE TABLE owners (id INT PRIMARY KEY);\n", encoding="utf-8")
        (db / "populateDB.sql").write_text("INSERT INTO owners VALUES (1);\n", encoding="utf-8")
        pipeline.assemble_bundle(root)

        p1 = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)], text=True, capture_output=True)
        if p1.returncode != 0:
            return _fail("[%s] bootstrap must pass on the legacy mix: %s%s" % (p1.stdout, p1.stderr[-400:]))
        c1 = subprocess.run([sys.executable, str(CHECKER), str(root)], text=True, capture_output=True)
        if c1.returncode != 0:
            return _fail("[%s] THE CONTRADICTION: bootstrap passed and its own checker refused the tree it wrote:\n%s"
                         % (layout, (c1.stdout + c1.stderr)[-700:]))

        prop = root / "src" / "main" / "resources" / "application.properties"
        text_now = prop.read_text(encoding="utf-8")
        for gone in ("%mysql.quarkus.datasource", "%hsqldb.quarkus.datasource", "%postgresql.quarkus.datasource"):
            if gone in text_now:
                return _fail("a datasource family for a profile this run never selects must not survive: %s" % gone)
        if "quarkus.datasource.db-kind=postgresql" not in text_now:
            return _fail("the decided datasource must still be there: %s" % text_now[-300:])
        if ".derived/frozen-input" not in text_now:
            return _fail("the removal must say where the legacy copy is preserved")
        if (frozen / "src/main/resources/application.properties").read_text(encoding="utf-8") != frozen_main:
            return _fail("[%s] the frozen legacy record must be untouched by the removal" % layout)
        pom_now = (root / "pom.xml").read_text(encoding="utf-8")
        if "quarkus-jdbc-mysql" in pom_now:
            return _fail("a JDBC extension for an undecided db-kind must not survive")
        if "quarkus-jdbc-postgresql" not in pom_now:
            return _fail("the decided JDBC extension must be in the pom")
        rec = load_json(root / "evidence/producers/bootstrap.json")
        ops = {c["op"] for c in rec["changes"]}
        for op in ("properties.remove-undecided-datasource-keys", "pom.remove-undecided-datasource-extension"):
            if op not in ops:
                return _fail("every removal is recorded against the decision that caused it; missing %s in %s" % (op, sorted(ops)))

        # REAPPLICATION CHANGES NOTHING -- twice, because a file that grows by
        # a fixed block each run is identical between no two consecutive runs
        before = tree_hash(root)
        for n in (2, 3):
            pn = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)], text=True, capture_output=True)
            if pn.returncode != 0:
                return _fail("bootstrap run %d must pass: %s%s" % (n, pn.stdout, pn.stderr[-300:]))
            prop_now = (root / "src/main/resources/application.properties").read_text(encoding="utf-8")
            if tree_hash(root) != before:
                return _fail("[%s] reapplying the bootstrap (run %d) must change nothing; properties tail:\n%s"
                             % (layout, n, prop_now[-400:]))
            if "[undecided-datasource]" not in prop_now:
                return _fail("[%s] run %d dropped the note that says why those families are gone; a reason that "
                             "survives only the run that wrote it is not a record" % (layout, n))
        c2 = subprocess.run([sys.executable, str(CHECKER), str(root)], text=True, capture_output=True)
        if c2.returncode != 0:
            return _fail("the checker must still pass after reapplication:\n%s" % (c2.stdout + c2.stderr)[-500:])
    return 0


def main() -> int:
    if _build_profile_case():
        return 1
    if _datasource_checker_integration_case() or _retire_offsets_case() or _plugin_config_case() or _profile_merge_case() or _jakarta_imports_case() or _version_precedence_case() or _reapply_catalog_case() or _datasource_case():
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
    print("OK: bootstrap-destination (trivial launcher deleted; second run preserves the tree; @Bean launcher kept + BOOTSTRAP_BLOCKED; unmapped starter kept + block; Maven settings wiring required; pinned version beats the legacy carry / VERSION_UNMANAGED / BOM_PROBE_MISSING; ADR-retired sources deleted with provenance / stale path blocks; reapply-catalog carries a late row and refuses without a receipt; the decided datasource lands unprefixed with its extension, and an undocumented / mismatched / absent one blocks; an undecided build profile blocks and a decided one reaches the destination; a profile condition nobody activates or enumerates is unaccounted; an enumerated retirement must be bound to this tree's inventory and describe conditions it actually has, and the proposer writes nothing; the legacy driver/profile mix goes bootstrap -> checker PASS in BOTH the separate-file and inline layouts, with removals recorded, the reason note surviving every run, and reapplication inert; a retirement is cut in UTF-16 offsets and leaves valid Java even when an astral character precedes the annotation)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
