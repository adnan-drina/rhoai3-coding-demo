#!/usr/bin/env python3
"""Deterministic bootstrap of the destination tree (SAD v3 §6, step 0).

1. import   copy the frozen analysis copy (src/, pom.xml, resources) into
            the destination root — only files the destination does not
            have yet (never overwrites an accepted loop step)
2. pom      ElementTree edits from the compat-mapping catalog + pins:
            drop the Spring Boot parent, import the pinned Quarkus BOM,
            map starters and JDBC drivers to extensions, drop the Spring
            Boot plugin, add the pinned Quarkus plugin, compiler/surefire
            pins, remove leftover org.springframework.boot dependencies
3. config   rename mapped property keys (line-based key=value; no regex)
4. main     delete the @SpringBootApplication class named by the JDK model
            ONLY when it is a trivial launcher (no fields, no other
            annotations, no method but main); a launcher that declares
            beans or configuration is kept and recorded as a block
5. receipt  evidence/producers/bootstrap.json with catalog + pins digests,
            every change made, and every block (MAIN_CLASS_NOT_TRIVIAL,
            UNMAPPED_DEPENDENCY). A block never removes anything: the
            dependency stays in the pom, the class stays in the tree, and
            admission refuses (BOOTSTRAP_BLOCKED) until a catalog row or an
            ADR resolves it.

Idempotent: a second run on an already-bootstrapped tree changes no file.
Exit 0 ok; 1 blocked (receipt written) or refused (catalog / pins / frozen copy missing).
"""
from __future__ import annotations

import argparse
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _ensure_hermes_lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()
from planner.canonical import digest, load_json, sha256_file, write_canonical  # noqa: E402
from planner.paths import BOM_MANAGED, BOOTSTRAP_RECEIPT, CATALOGS_DIR, DECISIONS, EVIDENCE_BUNDLE, producer_receipt  # noqa: E402
from planner.decisions import DecisionsError, datasource, load_decisions, retired_sources  # noqa: E402
from planner.pins import load_pins, pin  # noqa: E402

NS = "http://maven.apache.org/POM/4.0.0"
IMPORT_DIRS = ("src",)
IMPORT_FILES = ("pom.xml",)


def q(tag: str) -> str:
    return "{%s}%s" % (NS, tag)


def text(el: ET.Element | None, tag: str) -> str:
    if el is None:
        return ""
    c = el.find(q(tag))
    return (c.text or "").strip() if c is not None and c.text else ""


def sub(parent: ET.Element, tag: str, value: str | None = None) -> ET.Element:
    el = ET.SubElement(parent, q(tag))
    if value is not None:
        el.text = value
    return el


def find_or_add(parent: ET.Element, tag: str) -> ET.Element:
    el = parent.find(q(tag))
    if el is None:
        el = sub(parent, tag)
    return el


def import_source(copy: Path, root: Path, changes: list[dict], retired: dict[str, str] | None = None) -> None:
    """Copy frozen files the destination does not have. Never overwrite:
    after the baseline, every destination file is loop state. A path an
    accepted ADR retires (decisions.yaml retired_sources) is never imported."""
    retired = retired or {}
    for name in IMPORT_FILES:
        src = copy / name
        if src.is_file() and not (root / name).exists():
            shutil.copy2(src, root / name)
            changes.append({"op": "import", "path": name})
    for d in IMPORT_DIRS:
        src = copy / d
        if src.is_dir():
            for p in sorted(src.rglob("*")):
                if not p.is_file():
                    continue
                rel = p.relative_to(copy)
                dst = root / rel
                if dst.exists() or str(rel).replace("\\", "/") in retired:
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dst)
                changes.append({"op": "import", "path": str(rel).replace("\\", "/")})


def map_dependencies(deps: ET.Element, catalog: dict, changes: list[dict], blocks: list[dict]) -> tuple[list[str], dict[str, str]]:
    """Legacy dependencies → catalog rows: starters, JDBC drivers, documented
    removals (with replacements), javax→jakarta replacements; a Spring Boot
    dependency with no row blocks. Returns (artifacts to add, scopes)."""
    present = {(text(d, "groupId"), text(d, "artifactId")) for d in deps.findall(q("dependency"))}
    to_add: list[str] = list(catalog.get("always_add") or [])
    scoped: dict[str, str] = {}
    for d in list(deps.findall(q("dependency"))):
        ga = "%s:%s" % (text(d, "groupId"), text(d, "artifactId"))
        if ga in catalog["starters"]:
            to_add.extend(catalog["starters"][ga])
            deps.remove(d)
            changes.append({"op": "pom.map-starter", "from": ga, "to": list(catalog["starters"][ga])})
        elif ga in catalog["jdbc_drivers"]:
            to_add.append(catalog["jdbc_drivers"][ga])
            deps.remove(d)
            changes.append({"op": "pom.map-driver", "from": ga, "to": catalog["jdbc_drivers"][ga]})
        elif ga in (catalog.get("remove_dependencies") or {}) and ga != "note":
            row = catalog["remove_dependencies"][ga]
            to_add.extend(row.get("to") or [])
            for art in row.get("to") or []:
                if row.get("scope"):
                    scoped[art] = str(row["scope"])
            deps.remove(d)
            changes.append({"op": "pom.remove-dependency", "from": ga, "to": list(row.get("to") or []), "source": str(row.get("source") or "")})
        elif ga in (catalog.get("replace_dependencies") or {}) and ga != "note":
            new = str(catalog["replace_dependencies"][ga])
            g2, a2 = new.split(":", 1)
            find_or_add(d, "groupId").text = g2
            find_or_add(d, "artifactId").text = a2
            v = d.find(q("version"))
            if v is not None:
                d.remove(v)  # the BOM manages the jakarta artifact
            present.add((g2, a2))
            changes.append({"op": "pom.replace-dependency", "from": ga, "to": new})
        elif text(d, "groupId") in (catalog.get("remove_dependencies_matching_group") or []):
            # No catalog row: the dependency stays and the run blocks. Removing
            # it could silently drop runtime auto-configuration that still compiles.
            blocks.append({"class": "UNMAPPED_DEPENDENCY", "subject": ga, "detail": "no compat-mapping row for %s; add a documented row to compat-mapping.json (catalog change) or retire it by ADR before bootstrap can complete" % ga})
    return to_add, scoped


def test_scoped_artifacts(catalog: dict) -> set[str]:
    """The artifacts the catalog declares test-scoped (the mapping's own list)."""
    return set(((catalog.get("test_scoped") or {}).get("artifacts")) or ("quarkus-junit5", "rest-assured"))


def add_mapped_artifacts(deps: ET.Element, catalog: dict, to_add: list[str], scoped: dict[str, str], changes: list[dict]) -> None:
    """Catalog artifacts added to <dependencies> when absent, with the group id
    the catalog gives them and the scope the catalog declares. Versions are not
    set here: the BOM manages what it manages and carry_versions measures the
    rest."""
    present = {(text(d, "groupId"), text(d, "artifactId")) for d in deps.findall(q("dependency"))}
    groups = catalog.get("starter_group_ids") or {}
    scoped_arts = test_scoped_artifacts(catalog)
    for art in sorted(set(to_add)):
        gid = groups.get(art, "io.quarkus")
        if (gid, art) in present:
            continue
        d = sub(deps, "dependency")
        sub(d, "groupId", gid)
        sub(d, "artifactId", art)
        if art in scoped_arts or scoped.get(art):
            sub(d, "scope", scoped.get(art) or "test")
        present.add((gid, art))
        changes.append({"op": "pom.add-extension", "gav": "%s:%s" % (gid, art)})


def bootstrap_pom(root: Path, catalog: dict, pins: dict, changes: list[dict], blocks: list[dict]) -> None:
    pom = root / "pom.xml"
    ET.register_namespace("", NS)
    tree = ET.parse(pom)
    project = tree.getroot()
    platform = pin(pins, "quarkus_platform")
    if not platform.get("version"):
        raise SystemExit("FAIL: BOOTSTRAP_UNPINNED pins.quarkus_platform has no version")
    # 1. parent
    parent = project.find(q("parent"))
    pr = catalog["parent_to_remove"]
    if parent is not None and text(parent, "groupId") == pr["group_id"] and text(parent, "artifactId") == pr["artifact_id"]:
        project.remove(parent)
        changes.append({"op": "pom.remove-parent", "artifact": "%s:%s" % (pr["group_id"], pr["artifact_id"])})
    # 2. properties: compiler release + plugin versions from pins
    props = find_or_add(project, "properties")
    wanted = {
        "maven.compiler.release": str((catalog.get("java_release") or pins.get("quarkus_platform", {}).get("java_release") or "21")),
        "quarkus.platform.group-id": platform["group_id"],
        "quarkus.platform.artifact-id": platform["bom_artifact_id"],
        "quarkus.platform.version": platform["version"],
        "compiler-plugin.version": str(pin(pins, "compiler_plugin").get("version") or ""),
        "surefire-plugin.version": str(pin(pins, "surefire_plugin").get("version") or ""),
    }
    for k, v in wanted.items():
        if not v:
            continue
        el = props.find(q(k))
        if el is None:
            sub(props, k, v)
            changes.append({"op": "pom.property", "key": k, "value": v})
        elif (el.text or "").strip() != v:
            el.text = v
            changes.append({"op": "pom.property", "key": k, "value": v})
    # 3. BOM import
    dm = find_or_add(project, "dependencyManagement")
    dm_deps = find_or_add(dm, "dependencies")
    has_bom = any(text(d, "groupId") == "${quarkus.platform.group-id}" and text(d, "artifactId") == "${quarkus.platform.artifact-id}" for d in dm_deps.findall(q("dependency")))
    if not has_bom:
        d = sub(dm_deps, "dependency")
        sub(d, "groupId", "${quarkus.platform.group-id}")
        sub(d, "artifactId", "${quarkus.platform.artifact-id}")
        sub(d, "version", "${quarkus.platform.version}")
        sub(d, "type", "pom")
        sub(d, "scope", "import")
        changes.append({"op": "pom.bom", "gav": "%s:%s:%s" % (platform["group_id"], platform["bom_artifact_id"], platform["version"])})
    # 4. dependencies: starters → extensions, drivers → jdbc extensions, remove org.springframework.boot
    deps = find_or_add(project, "dependencies")
    to_add, scoped = map_dependencies(deps, catalog, changes, blocks)
    add_mapped_artifacts(deps, catalog, to_add, scoped, changes)
    # 4b. versions: the removed Spring Boot parent managed versions; the
    # Quarkus BOM manages its own set (measured by probe-bom-managed.py).
    # A version-less dependency the BOM does not manage gets the version a
    # tooling pin decided for it, else the version the legacy build resolved
    # (build receipt managed_versions) — a decision or a measured fact, never
    # a guess — or blocks.
    carry_versions(root, platform, deps, blocks, changes, pins)
    # 5. plugins
    build = find_or_add(project, "build")
    plugins = find_or_add(build, "plugins")
    prm = catalog["plugin_to_remove"]
    for p in list(plugins.findall(q("plugin"))):
        if text(p, "groupId") == prm["group_id"] and text(p, "artifactId") == prm["artifact_id"]:
            plugins.remove(p)
            changes.append({"op": "pom.remove-plugin", "artifact": "%s:%s" % (prm["group_id"], prm["artifact_id"])})
    qp = catalog["plugin_to_add"]
    plugin_art = str(platform.get(qp["artifact_id_key"]) or "quarkus-maven-plugin")
    if not any(text(p, "artifactId") == plugin_art for p in plugins.findall(q("plugin"))):
        p = sub(plugins, "plugin")
        sub(p, "groupId", "${quarkus.platform.group-id}")
        sub(p, "artifactId", plugin_art)
        sub(p, "version", "${quarkus.platform.version}")
        sub(p, "extensions", "true")
        exs = sub(p, "executions")
        ex = sub(exs, "execution")
        goals = sub(ex, "goals")
        for g in qp["goals"]:
            sub(goals, "goal", g)
        changes.append({"op": "pom.add-plugin", "artifact": plugin_art})
    for art, key in (("maven-compiler-plugin", "compiler-plugin.version"), ("maven-surefire-plugin", "surefire-plugin.version")):
        if not wanted.get(key):
            continue
        existing = [p for p in plugins.findall(q("plugin")) if text(p, "artifactId") == art]
        if existing:
            v = find_or_add(existing[0], "version")
            if (v.text or "").strip() != "${%s}" % key:
                v.text = "${%s}" % key
                changes.append({"op": "pom.pin-plugin", "artifact": art})
        else:
            p = sub(plugins, "plugin")
            sub(p, "artifactId", art)
            sub(p, "version", "${%s}" % key)
            changes.append({"op": "pom.pin-plugin", "artifact": art})
    add_plugins(plugins, catalog, changes)
    apply_plugin_config(project, plugins, catalog, changes)
    ET.indent(tree, space="  ")
    tree.write(pom, encoding="utf-8", xml_declaration=True)


def _build_xml(parent: ET.Element, spec: dict) -> None:
    """Nested dict → child elements (a list value repeats the element)."""
    for tag, value in spec.items():
        if isinstance(value, dict):
            _build_xml(sub(parent, tag), value)
        elif isinstance(value, list):
            for v in value:
                if isinstance(v, dict):
                    _build_xml(sub(parent, tag), v)
                else:
                    sub(parent, tag, str(v))
        else:
            sub(parent, tag, str(value))


def add_plugins(plugins: ET.Element, catalog: dict, changes: list[dict]) -> None:
    """Catalog plugins_to_add: documented plugins the platform guide expects, added when absent."""
    rows = {k: v for k, v in (catalog.get("plugins_to_add") or {}).items() if k != "note" and isinstance(v, dict)}
    present = {text(p, "artifactId") for p in plugins.findall(q("plugin"))}
    for name, spec in rows.items():
        art = str(spec.get("artifactId") or name)
        if art in present:
            continue
        p = sub(plugins, "plugin")
        _build_xml(p, spec)
        changes.append({"op": "pom.add-plugin", "artifact": art, "source": "catalog plugins_to_add"})


def apply_plugin_config(project: ET.Element, plugins: ET.Element, catalog: dict, changes: list[dict]) -> None:
    """Catalog plugin_config: for a present source-generating plugin, pin the
    documented version (through its version property when it has one), set
    the configuration leaves wherever they appear under the plugin, and set /
    remove configOptions entries. Documented facts, never inference."""
    rows = {k: v for k, v in (catalog.get("plugin_config") or {}).items() if k != "note" and isinstance(v, dict)}
    if not rows:
        return
    props = find_or_add(project, "properties")
    for p in plugins.findall(q("plugin")):
        key = "%s:%s" % (text(p, "groupId") or "org.apache.maven.plugins", text(p, "artifactId"))
        row = rows.get(key)
        if not row:
            continue
        ver = str(row.get("version") or "")
        if ver:
            v = find_or_add(p, "version")
            cur = (v.text or "").strip()
            if cur.startswith("${") and cur.endswith("}"):
                pe = find_or_add(props, cur[2:-1])
                if (pe.text or "").strip() != ver:
                    pe.text = ver
                    changes.append({"op": "pom.plugin-version", "artifact": key, "property": cur[2:-1], "version": ver})
            elif cur != ver:
                v.text = ver
                changes.append({"op": "pom.plugin-version", "artifact": key, "version": ver})
        for leaf, value in (row.get("configuration") or {}).items():
            hits = [e for e in p.iter(q(leaf))]
            if not hits:
                conf = p.find(q("configuration"))
                if conf is None:
                    ex = p.find("%s/%s" % (q("executions"), q("execution")))
                    conf = find_or_add(ex if ex is not None else p, "configuration")
                hits = [sub(conf, leaf)]
            for e in hits:
                if (e.text or "").strip() != value:
                    e.text = value
                    changes.append({"op": "pom.plugin-config", "artifact": key, "leaf": leaf, "value": value})
        for container, wanted_children in (row.get("ensure_list") or {}).items():
            # e.g. compilerArgs: {arg: ["-parameters"]}: the container exists (or is
            # created under the plugin's configuration) and carries each listed child
            conts = [e for e in p.iter(q(container))]
            if not conts:
                conf = p.find(q("configuration")) or find_or_add(p, "configuration")
                conts = [sub(conf, container)]
            for cont in conts:
                for child, values in (wanted_children or {}).items():
                    have = {(e.text or "").strip() for e in cont.findall(q(child))}
                    for val in values:
                        if str(val) not in have:
                            sub(cont, child, str(val))
                            changes.append({"op": "pom.plugin-ensure", "artifact": key, "element": "%s/%s" % (container, child), "value": str(val)})
        opts_all = [e for e in p.iter(q("configOptions"))]
        if (row.get("configOptions") or row.get("remove_configOptions")) and not opts_all:
            conf = next(iter(p.iter(q("configuration"))), None) or find_or_add(p, "configuration")
            opts_all = [sub(conf, "configOptions")]
        for opts in opts_all:
            for name in row.get("remove_configOptions") or []:
                for e in list(opts.findall(q(name))):
                    opts.remove(e)
                    changes.append({"op": "pom.plugin-configOption-remove", "artifact": key, "option": name})
            for name, value in (row.get("configOptions") or {}).items():
                e = opts.find(q(name))
                if e is None:
                    e = sub(opts, name)
                if (e.text or "").strip() != value:
                    e.text = value
                    changes.append({"op": "pom.plugin-configOption", "artifact": key, "option": name, "value": value})


def rename_jakarta_imports(root: Path, catalog: dict, changes: list[dict], blocks: list[dict]) -> None:
    """Catalog package_renames (javax.* → jakarta.*) applied to import
    declarations through the JDK compiler's parse tree (scripts/jakarta-imports/
    JakartaImports.java, compiled here).

    Main AND test sources: renaming an import is a namespace migration, not a
    change to what a test asserts, and a test source that cannot compile makes
    the whole measure unknown (pilot v7, 2026-09-10). What a test asserts is
    still never rewritten -- by this tool or by a worker."""
    import shutil
    import subprocess
    import tempfile

    renames = {k: str(v) for k, v in (catalog.get("package_renames") or {}).items() if k != "note" and isinstance(v, str)}
    if not renames:
        return
    tool = Path(__file__).resolve().parent / "jakarta-imports" / "JakartaImports.java"
    javac, java = shutil.which("javac"), shutil.which("java")
    if not javac or not java or not tool.is_file():
        blocks.append({"class": "TOOL_MISSING", "subject": "jakarta-imports", "detail": "javac/java or %s not available; the Jakarta import rename could not run" % tool})
        return
    with tempfile.TemporaryDirectory(prefix="jakarta-") as td:
        cp = subprocess.run([javac, "-d", td, str(tool)], capture_output=True, text=True)
        if cp.returncode != 0:
            blocks.append({"class": "TOOL_MISSING", "subject": "jakarta-imports", "detail": "JakartaImports.java did not compile: %s" % cp.stderr.strip()[:300]})
            return
        argv = [java, "-cp", td, "JakartaImports", "--root", str(root), "--roots", "src/main/java,src/test/java"] + ["%s=%s" % (k, v) for k, v in sorted(renames.items())]
        run = subprocess.run(argv, capture_output=True, text=True)
        if run.returncode != 0:
            blocks.append({"class": "TOOL_MISSING", "subject": "jakarta-imports", "detail": "JakartaImports failed: %s" % run.stderr.strip()[:300]})
            return
    per_file: dict[str, int] = {}
    for line in run.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            per_file[parts[0]] = per_file.get(parts[0], 0) + 1
    for path, n in sorted(per_file.items()):
        changes.append({"op": "source.rename-imports", "path": path, "imports": n, "source": "compat-mapping.json package_renames (Jakarta EE 10 namespace)"})


def apply_datasource_decision(root: Path, catalog: dict, decisions_doc: dict, changes: list[dict], blocks: list[dict]) -> None:
    """Render the decided effective datasource (decisions.yaml datasource, ADR).

    Quarkus resolves the datasource at BUILD time, so a profile-prefixed key is
    not a configured datasource: pilot v7 reached an empty work list with only
    %hsqldb.* keys and failed augmentation with "Datasource <default> is not
    configured". The decision therefore lands as unprefixed keys in
    src/main/resources/application.properties, with credentials referenced by
    environment variable name, and the matching JDBC extension is added to the
    pom. The profile-prefixed families the legacy carried are left exactly where
    they are: they are the source's own record, not this destination's config."""
    ds = datasource(decisions_doc)
    if not ds:
        return  # missing_decisions already keeps admission INCONCLUSIVE
    kinds = (catalog.get("datasources") or {}).get("db_kinds") or {}
    kind = str(ds.get("db_kind"))
    row = kinds.get(kind)
    if not row:
        blocks.append({"class": "DATASOURCE_UNSUPPORTED", "subject": kind, "detail": "compat-mapping.json datasources.db_kinds has no row for db_kind %r; the destination platform documents no JDBC extension for it" % kind})
        return
    ext = str(row.get("extension") or "")
    if str(ds.get("jdbc_extension") or "") != ext:
        blocks.append({"class": "DATASOURCE_EXTENSION_MISMATCH", "subject": kind, "detail": "%s is documented for db_kind %s; decisions.yaml names %r" % (ext, kind, ds.get("jdbc_extension"))})
        return
    # 1. the extension
    pom = root / "pom.xml"
    ET.register_namespace("", NS)
    tree = ET.parse(pom)
    project = tree.getroot()
    deps = find_or_add(project, "dependencies")
    gid, aid = ext.split(":", 1)
    if not any(text(d, "groupId") == gid and text(d, "artifactId") == aid for d in deps.findall(q("dependency"))):
        d = sub(deps, "dependency")
        sub(d, "groupId", gid)
        sub(d, "artifactId", aid)
        ET.indent(tree, space="  ")
        tree.write(pom, encoding="utf-8", xml_declaration=True)
        changes.append({"op": "pom.add-datasource-extension", "gav": ext, "provenance": "decisions.yaml datasource (%s)" % ds.get("adr")})
    # 2. the effective keys
    wanted = {
        "quarkus.datasource.db-kind": kind,
        "quarkus.datasource.jdbc.url": "${%s}" % ds.get("jdbc_url_env"),
        "quarkus.datasource.username": "${%s}" % ds.get("username_env"),
        "quarkus.datasource.password": "${%s}" % ds.get("password_env"),
        "quarkus.hibernate-orm.database.generation": str(ds.get("hibernate_generation")),
    }
    prop = root / "src" / "main" / "resources" / "application.properties"
    prop.parent.mkdir(parents=True, exist_ok=True)
    lines = prop.read_text(encoding="utf-8", errors="replace").splitlines() if prop.is_file() else []
    seen: dict[str, int] = {}
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped and not stripped.startswith(("#", "!")) and "=" in stripped:
            seen.setdefault(stripped.partition("=")[0].strip(), i)
    added: list[str] = []
    for key, value in wanted.items():
        line = "%s=%s" % (key, value)
        i = seen.get(key)
        if i is None:
            added.append(line)
            changes.append({"op": "properties.datasource-set", "key": key, "provenance": "decisions.yaml datasource (%s)" % ds.get("adr")})
        elif lines[i].strip() != line:
            lines[i] = line
            changes.append({"op": "properties.datasource-set", "key": key, "provenance": "decisions.yaml datasource (%s)" % ds.get("adr")})
    if added:
        lines += ["", "# bootstrap: effective datasource decided in decisions.yaml (%s); credentials are" % ds.get("adr"),
                  "# environment references, and the engine change from %s is recorded in that ADR." % ds.get("source_baseline_db_kind"),
                  *added]
    prop.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def bootstrap_properties(root: Path, catalog: dict, changes: list[dict]) -> None:
    mapping = catalog.get("properties") or {}
    values = catalog.get("property_values") or {}
    prefixes = catalog.get("property_prefixes") or {}
    files: list[Path] = []
    for sub in (("src", "main", "resources"), ("src", "test", "resources")):
        res = root.joinpath(*sub)
        if res.is_dir():
            files.extend(sorted(res.glob("application*.properties")))
    for p in files:
        out_lines: list[str] = []
        changed = False
        for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw
            stripped = raw.strip()
            if stripped and not stripped.startswith(("#", "!")) and "=" in stripped:
                key, _, val = stripped.partition("=")
                key = key.strip()
                prefix = next((pre for pre in prefixes if key.startswith(pre) and len(key) > len(pre)), None)
                if key not in mapping and prefix is not None:
                    # documented key-family mapping (e.g. logging.level.<category>)
                    new_key = str(prefixes[prefix]["to"]).replace("{rest}", key[len(prefix):])
                    line = "%s=%s" % (new_key, val.strip())
                    changes.append({"op": "properties.rename", "file": str(p.relative_to(root)), "from": key, "to": new_key})
                    changed = True
                elif key in mapping:
                    new_key = mapping[key]
                    if new_key is None:
                        line = "# bootstrap: no Quarkus equivalent for %s (dropped)" % key
                        changes.append({"op": "properties.drop", "file": str(p.relative_to(root)), "key": key})
                    else:
                        v = val.strip()
                        v = values.get(new_key, {}).get(v, v)
                        line = "%s=%s" % (new_key, v)
                        changes.append({"op": "properties.rename", "file": str(p.relative_to(root)), "from": key, "to": new_key})
                    changed = True
            out_lines.append(line)
        if changed:
            p.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    if catalog.get("profile_files"):
        merge_profile_files(root, changes)


def merge_profile_files(root: Path, changes: list[dict]) -> None:
    """Spring profile files → %<profile>.<key> lines in the sibling
    application.properties, then the file is removed (Quarkus config guide,
    profiles). Keys were mapped already. A key already present under the
    profile prefix is not duplicated; comments do not travel."""
    for sub_dir in (("src", "main", "resources"), ("src", "test", "resources")):
        res = root.joinpath(*sub_dir)
        if not res.is_dir():
            continue
        main = res / "application.properties"
        for p in sorted(res.glob("application-*.properties")):
            profile = p.name[len("application-"):-len(".properties")]
            if not profile:
                continue
            existing = main.read_text(encoding="utf-8", errors="replace") if main.is_file() else ""
            have = {ln.split("=", 1)[0].strip() for ln in existing.splitlines() if "=" in ln and not ln.strip().startswith(("#", "!"))}
            moved: list[str] = []
            for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
                ln = raw.strip()
                if not ln or ln.startswith(("#", "!")) or "=" not in ln:
                    continue
                key, _, val = ln.partition("=")
                key = key.strip()
                if key.startswith("%"):
                    new_key = key
                else:
                    new_key = "%%%s.%s" % (profile, key)
                if new_key in have:
                    continue
                moved.append("%s=%s" % (new_key, val.strip()))
                have.add(new_key)
            block = ("\n# bootstrap: merged from %s (Quarkus profile %s)\n" % (p.name, profile)) + "\n".join(moved) + "\n" if moved else ""
            if block:
                main.write_text((existing.rstrip("\n") + "\n" if existing else "") + block, encoding="utf-8")
            p.unlink()
            changes.append({"op": "properties.merge-profile", "file": str(p.relative_to(root)), "into": str(main.relative_to(root)), "profile": profile, "keys": len(moved)})


def trivial_launcher(t: dict) -> tuple[bool, str]:
    """True when the class is nothing but a launcher: no fields, no
    constructor parameters, no annotation but @SpringBootApplication, and no
    method other than main. Anything else may carry behavior (@Bean,
    @EnableXxx, custom configuration) and is kept."""
    anns = [str(a.get("fqn")) for a in (t.get("annotations") or [])]
    extra_anns = [a for a in anns if a != "org.springframework.boot.autoconfigure.SpringBootApplication"]
    if extra_anns:
        return False, "annotations %s" % ",".join(extra_anns)
    if t.get("fields"):
        return False, "declares field(s) %s" % ",".join(str(f.get("name")) for f in t["fields"])
    if any(c.get("params") for c in (t.get("constructors") or [])):
        return False, "constructor with parameters"
    others = [str(m.get("name")) for m in (t.get("methods") or []) if str(m.get("name")) != "main"]
    if others:
        return False, "method(s) %s (possible @Bean / configuration)" % ",".join(others)
    for m in t.get("methods") or []:
        if any(str(a.get("fqn")) != "" for a in (m.get("annotations") or [])):
            return False, "annotated method %s" % m.get("name")
    return True, ""


def bootstrap_main_class(root: Path, catalog: dict, bundle: dict, changes: list[dict], blocks: list[dict]) -> None:
    ann = catalog["main_class"]["annotation"]
    for t in (bundle.get("structure") or {}).get("types") or []:
        if not any(a.get("fqn") == ann for a in (t.get("annotations") or [])):
            continue
        path = root / str(t.get("path") or "")
        if not path.is_file():
            continue
        ok, why = trivial_launcher(t)
        if ok:
            path.unlink()
            changes.append({"op": "source.delete", "path": str(t.get("path")), "reason": "trivial @SpringBootApplication launcher (Quarkus has no main on the compat path)"})
        else:
            blocks.append({"class": "MAIN_CLASS_NOT_TRIVIAL", "subject": str(t.get("fqn")), "detail": "%s is not a trivial launcher (%s); kept in place — its @SpringBootApplication / SpringApplication.run become work-list items for a bounded human or ADR decision, never a silent delete" % (t.get("fqn"), why)})


def pinned_versions(pins: dict) -> dict[str, tuple[str, str]]:
    """Every tooling pin that names a coordinate and a version, as ga → (version, pin key).

    A pin is a decision about which version of an artifact this destination
    uses, recorded with its provenance. It therefore outranks the version the
    legacy build happened to resolve, which is only the fallback for artifacts
    nobody decided about."""
    out: dict[str, tuple[str, str]] = {}
    # load_pins returns the inner mapping (key → pin); a whole pins document is
    # accepted too, so a caller that read the file itself is not silently ignored
    table = pins.get("pins") if isinstance(pins, dict) and isinstance(pins.get("pins"), dict) else pins
    for key, spec in (table if isinstance(table, dict) else {}).items():
        if not isinstance(spec, dict):
            continue
        g, a, v = spec.get("group_id"), spec.get("artifact_id"), spec.get("version")
        if g and a and v:
            out["%s:%s" % (g, a)] = (str(v), str(key))
    return out


def carry_versions(root: Path, platform: dict, deps: ET.Element, blocks: list[dict], changes: list[dict], pins: dict | None = None) -> None:
    probe_p = root / BOM_MANAGED
    bom_gav = "%s:%s:%s" % (platform.get("group_id"), platform.get("bom_artifact_id"), platform.get("version"))
    probe = load_json(probe_p) if probe_p.is_file() else None
    probe_bom = (probe or {}).get("bom") or {}
    probe_gav = "%s:%s:%s" % (probe_bom.get("group_id"), probe_bom.get("artifact_id"), probe_bom.get("version"))
    if not probe or probe_gav != bom_gav:
        blocks.append({"class": "BOM_PROBE_MISSING", "subject": bom_gav, "detail": "%s is %s; run scripts/probe-bom-managed.py --root first (it measures what the pinned BOM manages)" % (BOM_MANAGED, "absent" if not probe else "for " + probe_gav)})
        return
    managed = set(probe.get("managed") or [])
    build_p = producer_receipt(root, "build")
    legacy = (load_json(build_p).get("managed_versions") or {}) if build_p.is_file() else {}
    decided = pinned_versions(pins or {})
    for d in deps.findall(q("dependency")):
        ga = "%s:%s" % (text(d, "groupId"), text(d, "artifactId"))
        have = text(d, "version")
        if have:
            # A pin is a decision about which version this destination uses. A
            # literal version that disagrees with one is corrected, and both
            # values are recorded; a property reference is left to its property.
            if ga in decided and not have.startswith("${") and have != decided[ga][0]:
                version, key = decided[ga]
                find_or_add(d, "version").text = version
                changes.append({"op": "pom.repin-version", "gav": "%s:%s" % (ga, version), "was": have, "provenance": "pins.json %s" % key})
            continue
        if ga in managed:
            continue
        if any(b["subject"] == ga for b in blocks):
            continue  # already an UNMAPPED_DEPENDENCY block
        if ga in decided:
            version, key = decided[ga]
            sub(d, "version", version)
            changes.append({"op": "pom.pin-decided-version", "gav": "%s:%s" % (ga, version), "provenance": "pins.json %s" % key})
        elif ga in legacy:
            sub(d, "version", legacy[ga])
            changes.append({"op": "pom.pin-legacy-version", "gav": "%s:%s" % (ga, legacy[ga]), "provenance": "legacy effective pom (capture-build-evidence managed_versions)"})
        else:
            blocks.append({"class": "VERSION_UNMANAGED", "subject": ga, "detail": "%s has no version, the pinned BOM %s does not manage it, and the legacy build resolved no version for it; a catalog row or an ADR must name it" % (ga, bom_gav)})


def retire_sources(root: Path, copy: Path, retired: dict[str, str], changes: list[dict], blocks: list[dict]) -> None:
    """Delete exactly the files an accepted ADR retires. A retired path the
    frozen legacy never had is a stale decision and blocks (never silent)."""
    for rel, adr in sorted(retired.items()):
        dst = root / rel
        if dst.is_file():
            dst.unlink()
            changes.append({"op": "source.delete", "path": rel, "reason": "retired by %s (decisions.yaml retired_sources)" % adr, "adr": adr})
        elif (copy / rel).is_file():
            changes.append({"op": "source.retire", "path": rel, "reason": "not imported: retired by %s (decisions.yaml retired_sources)" % adr, "adr": adr})
        else:
            blocks.append({"class": "RETIRED_SOURCE_MISSING", "subject": rel, "detail": "%s retires %s but the frozen legacy source has no such file; fix the decision" % (adr, rel)})


def check_maven_settings(root: Path, catalog: dict, blocks: list[dict]) -> None:
    """The pinned platform resolves only from the repository the catalog names
    (Red Hat GA for RHBQ). Maven 3 does not auto-read .mvn/settings.xml, so
    the tree must wire it through .mvn/maven.config. Same file-shape contract
    as reference-rh-quarkus-pom/scripts/verify-maven-settings.py."""
    req = catalog.get("maven_settings") or {}
    profile = str(req.get("profile") or "")
    if not profile:
        return
    cfg = root / ".mvn" / "maven.config"
    settings = root / ".mvn" / "settings.xml"
    args = [a.strip() for a in cfg.read_text(encoding="utf-8").split()] if cfg.is_file() else []
    wired = any(a in ("-s", "--settings") and i + 1 < len(args) and args[i + 1] == ".mvn/settings.xml" for i, a in enumerate(args))
    if not wired:
        blocks.append({"class": "MAVEN_SETTINGS_MISSING", "subject": ".mvn/maven.config", "detail": ".mvn/maven.config must carry -s .mvn/settings.xml (Maven 3 does not auto-read .mvn/settings.xml); without it the pinned platform %s cannot resolve" % (req.get("reason") or profile)})
        return
    if not settings.is_file() or profile not in settings.read_text(encoding="utf-8"):
        blocks.append({"class": "MAVEN_SETTINGS_MISSING", "subject": ".mvn/settings.xml", "detail": ".mvn/settings.xml must declare the %s profile (%s)" % (profile, req.get("source") or "")})


def rewrite_blocks(receipt: dict, recomputed: tuple[str, ...], blocks: list[dict]) -> None:
    """An Operator mode re-answers exactly the questions it asks. The blocks of
    those classes are replaced by what it just measured; every other block on
    the receipt stands, because nothing here re-measured it. Status follows the
    blocks that remain, so a corrected decision clears its own refusal instead
    of leaving the receipt blocked forever."""
    kept = [b for b in (receipt.get("blocks") or []) if str(b.get("class")) not in recomputed]
    remaining = kept + list(blocks)
    receipt["blocks"] = remaining
    receipt["status"] = "blocked" if remaining else "ok"
    receipt["reasons"] = [str(b.get("detail") or "") for b in remaining]


def retire_only(root: Path) -> int:
    """Apply retired_sources decided after the bootstrap ran: delete exactly
    those files from the destination tree (the frozen legacy copy is the
    existence oracle, as in the bootstrap) and append the changes to the
    bootstrap receipt so the retirement has the same provenance."""
    receipt_p = root / BOOTSTRAP_RECEIPT
    if not receipt_p.is_file():
        print("FAIL: BOOTSTRAP_NO_RECEIPT (the tree was never bootstrapped)", file=sys.stderr)
        return 1
    freeze_p = producer_receipt(root, "freeze")
    copy = Path(str(load_json(freeze_p).get("analysis_copy") or "")) if freeze_p.is_file() else Path("/nonexistent")
    try:
        retired = retired_sources(load_decisions(root))
    except DecisionsError as exc:
        print("FAIL: DECISIONS_INVALID %s" % exc, file=sys.stderr)
        return 1
    receipt = load_json(receipt_p)
    done = {str(c.get("path")) for c in (receipt.get("changes") or []) if str(c.get("op") or "").startswith("source.")}
    pending = {k: v for k, v in retired.items() if k not in done}
    changes: list[dict] = []
    blocks: list[dict] = []
    retire_sources(root, copy, pending, changes, blocks)
    receipt["changes"] = list(receipt.get("changes") or []) + changes
    receipt["retired_sources"] = retired
    rewrite_blocks(receipt, ("RETIRED_SOURCE_MISSING",), blocks)
    write_canonical(receipt_p, receipt)
    if blocks:
        for b in blocks:
            print("  - %s %s: %s" % (b["class"], b["subject"], b["detail"]), file=sys.stderr)
        print("REFUSE: BOOTSTRAP_BLOCKED (%d block(s))" % len(blocks), file=sys.stderr)
        return 1
    print("OK: retire-only (%d file(s) retired, %d already recorded) → %s" % (len(changes), len(retired) - len(pending), BOOTSTRAP_RECEIPT))
    return 0


def late_row_artifacts(receipt: dict, catalog: dict) -> tuple[list[str], dict[str, str]]:
    """What the catalog rows THIS destination consumed produce today.

    A mapping row is consumed once, at bootstrap, against a legacy dependency
    that is no longer in the destination pom. When such a row later gains an
    artifact, no amount of re-running the bootstrap will deliver it. So the
    receipt is the record of which rows applied here, and the catalog says what
    those rows produce now; the difference is what is missing.

    Adding every artifact the catalog mentions would be the wrong answer: a
    test-scoped artifact belongs to the row that asks for it, not to every
    destination (a specimen whose legacy never had the Spring security test
    starter must not acquire its replacement)."""
    to_add: list[str] = list(catalog.get("always_add") or [])
    scoped: dict[str, str] = {}
    rows = {
        "pom.map-starter": catalog.get("starters") or {},
        "pom.map-driver": catalog.get("jdbc_drivers") or {},
        "pom.remove-dependency": catalog.get("remove_dependencies") or {},
    }
    for c in receipt.get("changes") or []:
        row = rows.get(str(c.get("op") or "")) or {}
        entry = row.get(str(c.get("from") or ""))
        if entry is None:
            continue
        if isinstance(entry, str):
            to_add.append(entry)
            continue
        if isinstance(entry, dict):
            to_add.extend(entry.get("to") or [])
            for art in entry.get("to") or []:
                if entry.get("scope"):
                    scoped[art] = str(entry["scope"])
            continue
        to_add.extend(entry)
    return to_add, scoped


def reapply_catalog(root: Path) -> int:
    """Operator: apply catalog rows that changed after the bootstrap ran to an
    already bootstrapped tree — the documented plugins and their configuration,
    the artifacts the catalog declares test-scoped, versions carried from the
    legacy build, and the Jakarta namespace rename.

    Every step is idempotent by construction: set to the documented value, or
    add when absent. Accepted card work in the pom and in the sources is left
    alone. What is deliberately NOT re-run is anything that consumes the legacy
    pom or the frozen copy: source import, starter mapping, dependency removal,
    retirement. Those rows were consumed once, their inputs are gone from this
    pom, and re-running them would rewrite a tree the loop has already measured
    (retirement decided later has its own mode, --retire-only).

    Appends to the bootstrap receipt, so a catalog fact that arrived mid-run has
    the same provenance as one that was there at bootstrap."""
    receipt_p = root / BOOTSTRAP_RECEIPT
    if not receipt_p.is_file():
        print("FAIL: BOOTSTRAP_NO_RECEIPT (the tree was never bootstrapped)", file=sys.stderr)
        return 1
    cat_p = root / CATALOGS_DIR / "compat-mapping.json"
    if not cat_p.is_file():
        print("FAIL: BOOTSTRAP_NO_CATALOG %s" % cat_p, file=sys.stderr)
        return 1
    catalog = load_json(cat_p)
    pins = load_pins(root)
    platform = pin(pins, "quarkus_platform")
    pom = root / "pom.xml"
    if not pom.is_file():
        print("FAIL: BOOTSTRAP_NO_POM %s" % pom, file=sys.stderr)
        return 1
    receipt = load_json(receipt_p)
    changes: list[dict] = []
    blocks: list[dict] = []
    ET.register_namespace("", NS)
    try:
        tree = ET.parse(pom)
    except ET.ParseError as exc:
        print("FAIL: BOOTSTRAP_POM_PARSE %s" % exc, file=sys.stderr)
        return 1
    project = tree.getroot()
    deps = find_or_add(project, "dependencies")
    to_add, scoped = late_row_artifacts(receipt, catalog)
    add_mapped_artifacts(deps, catalog, to_add, scoped, changes)
    carry_versions(root, platform, deps, blocks, changes, pins)
    build = find_or_add(project, "build")
    plugins = find_or_add(build, "plugins")
    add_plugins(plugins, catalog, changes)
    apply_plugin_config(project, plugins, catalog, changes)
    ET.indent(tree, space="  ")
    tree.write(pom, encoding="utf-8", xml_declaration=True)
    if (root / DECISIONS).is_file():
        try:
            apply_datasource_decision(root, catalog, load_decisions(root), changes, blocks)
        except DecisionsError as exc:
            blocks.append({"class": "DECISIONS_INVALID", "subject": str(DECISIONS), "detail": str(exc)})
    rename_jakarta_imports(root, catalog, changes, blocks)
    receipt["changes"] = list(receipt.get("changes") or []) + changes
    receipt["inputs"] = dict(receipt.get("inputs") or {})
    receipt["inputs"]["catalog_sha256"] = sha256_file(cat_p)
    receipt["outputs"] = [{"path": "pom.xml", "sha256": sha256_file(pom)}]
    rewrite_blocks(receipt, ("VERSION_UNMANAGED", "BOM_PROBE_MISSING", "TOOL_MISSING", "DATASOURCE_UNSUPPORTED", "DATASOURCE_EXTENSION_MISMATCH", "DECISIONS_INVALID"), blocks)
    write_canonical(receipt_p, receipt)
    for c in changes:
        print("  - %s %s" % (c["op"], c.get("gav") or c.get("artifact") or c.get("path") or c.get("key") or ""))
    if blocks:
        for b in blocks:
            print("  - %s %s: %s" % (b["class"], b["subject"], b["detail"]), file=sys.stderr)
        print("REFUSE: BOOTSTRAP_BLOCKED (%d block(s))" % len(blocks), file=sys.stderr)
        return 1
    print("OK: reapply-catalog (%d change(s), catalog %s) → %s" % (len(changes), sha256_file(cat_p)[:12], BOOTSTRAP_RECEIPT))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--retire-only", action="store_true", help="Operator: apply decisions.yaml retired_sources to an already bootstrapped tree (an ADR accepted after M2); appends to the bootstrap receipt; the loop is then re-measured (fix-until-green/scripts/rewind.py --remeasure)")
    ap.add_argument("--reapply-catalog", action="store_true", help="Operator: apply catalog rows that changed after the bootstrap ran (plugins and their configuration, test-scoped artifacts, carried versions, the Jakarta rename) to an already bootstrapped tree; idempotent, appends to the receipt, re-measure afterwards")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if args.retire_only and args.reapply_catalog:
        print("FAIL: BOOTSTRAP_USAGE --retire-only and --reapply-catalog are separate interventions; run one, re-measure, then the other", file=sys.stderr)
        return 2
    if args.retire_only:
        return retire_only(root)
    if args.reapply_catalog:
        return reapply_catalog(root)
    freeze_p = producer_receipt(root, "freeze")
    if not freeze_p.is_file():
        print("FAIL: BOOTSTRAP_NO_FREEZE", file=sys.stderr)
        return 1
    freeze = load_json(freeze_p)
    copy = Path(str(freeze.get("analysis_copy") or ""))
    if not copy.is_dir() or not (copy / "pom.xml").is_file():
        print("FAIL: BOOTSTRAP_NO_ANALYSIS_COPY %s" % copy, file=sys.stderr)
        return 1
    cat_p = root / CATALOGS_DIR / "compat-mapping.json"
    if not cat_p.is_file():
        print("FAIL: BOOTSTRAP_NO_CATALOG %s" % cat_p, file=sys.stderr)
        return 1
    catalog = load_json(cat_p)
    bundle_p = root / EVIDENCE_BUNDLE
    if not bundle_p.is_file():
        print("FAIL: BOOTSTRAP_NO_BUNDLE (assemble-evidence-bundle did not run)", file=sys.stderr)
        return 1
    bundle = load_json(bundle_p)
    pins = load_pins(root)
    changes: list[dict] = []
    blocks: list[dict] = []
    retired: dict[str, str] = {}
    if (root / DECISIONS).is_file():
        try:
            retired = retired_sources(load_decisions(root))
        except DecisionsError as exc:
            blocks.append({"class": "DECISIONS_INVALID", "subject": str(DECISIONS), "detail": str(exc)})
    import_source(copy, root, changes, retired)
    retire_sources(root, copy, retired, changes, blocks)
    check_maven_settings(root, catalog, blocks)
    try:
        bootstrap_pom(root, catalog, pins, changes, blocks)
    except ET.ParseError as exc:
        print("FAIL: BOOTSTRAP_POM_PARSE %s" % exc, file=sys.stderr)
        return 1
    bootstrap_properties(root, catalog, changes)
    if (root / DECISIONS).is_file():
        try:
            apply_datasource_decision(root, catalog, load_decisions(root), changes, blocks)
        except DecisionsError as exc:
            blocks.append({"class": "DECISIONS_INVALID", "subject": str(DECISIONS), "detail": str(exc)})
    bootstrap_main_class(root, catalog, bundle, changes, blocks)
    rename_jakarta_imports(root, catalog, changes, blocks)
    receipt = {
        "schema": "rhoai3.producer-receipt/v1",
        "producer": "bootstrap",
        "status": "ok" if not blocks else "blocked",
        "tool": {"name": "bootstrap-destination", "version": "1.0.0", "pin_status": "not-applicable"},
        "inputs": {"source_digest": str(freeze.get("source_digest") or ""), "catalog_sha256": sha256_file(cat_p), "evidence_bundle_sha256": digest(bundle), "pins": {k: pin(pins, k) for k in ("quarkus_platform", "compiler_plugin", "surefire_plugin")}},
        "outputs": [{"path": "pom.xml", "sha256": sha256_file(root / "pom.xml")}],
        "reasons": [b["detail"] for b in blocks],
        "blocks": blocks,
        "changes": changes,
        "path": "spring-compat",
        "retired_sources": retired,
    }
    write_canonical(root / BOOTSTRAP_RECEIPT, receipt)
    if blocks:
        for b in blocks:
            print("  - %s %s: %s" % (b["class"], b["subject"], b["detail"]), file=sys.stderr)
        print("REFUSE: BOOTSTRAP_BLOCKED (%d block(s); %d change(s) recorded) → %s" % (len(blocks), len(changes), BOOTSTRAP_RECEIPT), file=sys.stderr)
        return 1
    print("OK: bootstrap (%d change(s)) → %s" % (len(changes), BOOTSTRAP_RECEIPT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
