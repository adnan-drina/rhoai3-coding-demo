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
from planner.decisions import DecisionsError, load_decisions, retired_sources  # noqa: E402
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
    present = {(text(d, "groupId"), text(d, "artifactId")) for d in deps.findall(q("dependency"))}
    groups = catalog.get("starter_group_ids") or {}
    for art in sorted(set(to_add)):
        gid = groups.get(art, "io.quarkus")
        if (gid, art) in present:
            continue
        d = sub(deps, "dependency")
        sub(d, "groupId", gid)
        sub(d, "artifactId", art)
        if art in ("quarkus-junit5", "rest-assured") or scoped.get(art):
            sub(d, "scope", scoped.get(art) or "test")
        present.add((gid, art))
        changes.append({"op": "pom.add-extension", "gav": "%s:%s" % (gid, art)})
    # 4b. versions: the removed Spring Boot parent managed versions; the
    # Quarkus BOM manages its own set (measured by probe-bom-managed.py).
    # A version-less dependency the BOM does not manage gets the version the
    # legacy build resolved (build receipt managed_versions) — a measured
    # fact, never a guess — or blocks.
    carry_versions(root, platform, deps, blocks, changes)
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
    JakartaImports.java, compiled here). Production sources only; tests judge
    the migration and are not rewritten. Documented facts, applied by a tool."""
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
        argv = [java, "-cp", td, "JakartaImports", "--root", str(root)] + ["%s=%s" % (k, v) for k, v in sorted(renames.items())]
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


def carry_versions(root: Path, platform: dict, deps: ET.Element, blocks: list[dict], changes: list[dict]) -> None:
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
    for d in deps.findall(q("dependency")):
        if text(d, "version"):
            continue
        ga = "%s:%s" % (text(d, "groupId"), text(d, "artifactId"))
        if ga in managed:
            continue
        if any(b["subject"] == ga for b in blocks):
            continue  # already an UNMAPPED_DEPENDENCY block
        if ga in legacy:
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
    if blocks:
        receipt["blocks"] = list(receipt.get("blocks") or []) + blocks
        receipt["status"] = "blocked"
    write_canonical(receipt_p, receipt)
    if blocks:
        for b in blocks:
            print("  - %s %s: %s" % (b["class"], b["subject"], b["detail"]), file=sys.stderr)
        print("REFUSE: BOOTSTRAP_BLOCKED (%d block(s))" % len(blocks), file=sys.stderr)
        return 1
    print("OK: retire-only (%d file(s) retired, %d already recorded) → %s" % (len(changes), len(retired) - len(pending), BOOTSTRAP_RECEIPT))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--retire-only", action="store_true", help="Operator: apply decisions.yaml retired_sources to an already bootstrapped tree (an ADR accepted after M2); appends to the bootstrap receipt; the loop is then re-measured (fix-until-green/scripts/rewind.py --remeasure)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if args.retire_only:
        return retire_only(root)
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
