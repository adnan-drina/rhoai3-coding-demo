#!/usr/bin/env python3
"""The harness-owned ``m4-parity`` block in the destination ``pom.xml``.

ONE definition of that block, imported by everything that writes or reads it:

  ``bootstrap-destination.py``   writes it into the pom it bootstraps, so the
      profile that compiles the generated parity tests is part of the
      COMMITTED tree. The generated cases are written at M4 and the tree must
      still be retrievable (``assert-retrievable-tree``) when the verdict is
      composed; a pom first edited at M4 makes that gate refuse for a reason
      that is the harness's own doing.
  ``generate-product-tests.py``  rewrites it at M4 (idempotently) and binds
      its digest in ``evidence/tests/generated-manifest.json``; ``--check``
      refuses when a byte of it moved. On a tree the bootstrap wrote, that
      rewrite finds the block byte-identical and changes nothing.

A second copy of the block text would be a second definition of "what makes
the generated tests runnable", which is the defect this module exists to make
impossible.

WHY THE BLOCK IS COMMENTS PLUS A PROFILE, and why it is handled as TEXT:
ElementTree drops XML comments on parse, so any producer that rewrites the pom
through ElementTree would silently delete the markers that say which profile
is the harness's. ``strip_profile_block`` removes the block before such a pass
and ``ensure_pom_profile`` writes it back verbatim afterwards.

WHY THE PROFILE ALSO CONFIGURES THE TEST PLUGIN, measured on destination v9
with the real platform build: ``mvn -Pm4-parity test`` failed in the generated
``@QuarkusTest`` classes' augmentation with every profile-guarded bean
``@Vetoed``, and then -- once the profile reached the test JVM -- with every
request answered 401. Two configurations the destination DECLARED did not
reach the surefire JVM:

  the decided build profiles   the destination BUILDS with the profiles
      decisions.yaml activates (the bootstrap writes them to
      ``.mvn/maven.config`` as ``-Dquarkus.profile`` and to
      ``application.properties``). ``@QuarkusTest`` augments under the TEST
      profile, which that key does not select, so each guarded implementation
      was vetoed and the suite measured a destination that has none.
  the captured security mode   the frozen source's own ``src/test/resources``
      are on the test classpath and set the source's security switch; under
      ``@QuarkusTest`` they override the destination's configuration, so the
      suite answered for a mode nobody captured.

Neither pin is a test-only override: each restates, where the test JVM reads
it, a value the destination already declares. Both are read from decisions and
from the generator's manifest -- never from a specimen literal.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# The phase rule, as paths. M4 only: a root Maven compiles unconditionally
# would put a parity finding into the M3 loop's measure.
DEFAULT_OUT = "src/parity-test/java"
DEFAULT_RESOURCES = "src/parity-test/resources"
LOOP_TEST_ROOTS = ("src/test/java", "src/test/resources")

# The harness-owned block in the destination pom.xml: exactly what is between
# these two comments is this producer's, and a re-run replaces exactly that.
POM = "pom.xml"
POM_PROFILE_ID = "m4-parity"
POM_BEGIN = "<!-- rhoai3:generated-tests:begin -->"
POM_END = "<!-- rhoai3:generated-tests:end -->"
# build-helper-maven-plugin adds the parity roots to the test compile and the
# test resources under this profile and under no other.
POM_PLUGIN_GROUP = "org.codehaus.mojo"
POM_PLUGIN_ARTIFACT = "build-helper-maven-plugin"
# probe-bom-managed.py measures the BOM's dependencyManagement, which never
# manages a BUILD PLUGIN, so it cannot answer for this artifact: the version
# is pinned here and recorded in the manifest. When a probe result does list
# it (a BOM that grows pluginManagement), the version is dropped and the BOM's
# is used -- the evidence decides, not this constant.
POM_PLUGIN_VERSION = "3.6.0"
BOM_MANAGED = Path("evidence") / "build" / "bom-managed.json"

# The plugins that run a test JVM. The profile configures the ones the road's
# pom actually declares -- surefire always (it is what ``mvn test`` runs),
# failsafe only when the destination carries it.
TEST_PLUGIN_GROUP = "org.apache.maven.plugins"
SUREFIRE_ARTIFACT = "maven-surefire-plugin"
FAILSAFE_ARTIFACT = "maven-failsafe-plugin"
TEST_PLUGINS = (SUREFIRE_ARTIFACT, FAILSAFE_ARTIFACT)
# The platform's own key for "which build profile the TEST augmentation uses".
# quarkus.profile does not select it, which is why the guards were inactive.
TEST_PROFILE_PROPERTY = "quarkus.test.profile"
# The mode the generated suite was written for, as the generator records it.
SECURITY_MODES = ("disabled", "enabled")
DEFAULT_SECURITY_MODE = "disabled"
GENERATED_MANIFEST = Path("evidence") / "tests" / "generated-manifest.json"
DECISIONS_FILE = Path("decisions.yaml")
# A systemPropertyVariables entry IS an XML element name. A declared switch
# key that is not one cannot be written, and a block that silently dropped it
# would leave the mode unpinned while claiming otherwise.
_XML_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")

_PROFILES_OPEN = "<profiles>"
_PROFILES_CLOSE = "</profiles>"


class Refuse(Exception):
    """A reason the tests may not be generated. Never a partial generation."""


def _load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _pom_text(root: Path) -> str:
    p = Path(root) / POM
    if not p.is_file():
        raise Refuse("no %s in %s; the generated tests need the %s profile that compiles and runs them"
                     % (POM, root, POM_PROFILE_ID))
    try:
        return p.read_text(encoding="utf-8")
    except OSError as exc:
        raise Refuse("%s could not be read: %s" % (POM, exc))


def _pom_marked_region(text: str) -> tuple[int, int] | None:
    """(start, end) of the marked block, markers included. Refuses a pom whose
    markers are unbalanced or out of order: that is not a block this producer
    may replace."""
    begins = [m.start() for m in re.finditer(re.escape(POM_BEGIN), text)]
    ends = [m.end() for m in re.finditer(re.escape(POM_END), text)]
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        raise Refuse("%s carries %d begin and %d end marker(s) for the generated-tests block; exactly one of each, in order, "
                     "is what a re-run may replace" % (POM, len(begins), len(ends)))
    return begins[0], ends[0]


def _pom_profile_ids(text: str) -> list[str]:
    """Every top-level profile id the pom declares, read from the XML (a text
    scan would count an id in a comment)."""
    try:
        project = ET.fromstring(text)
    except ET.ParseError as exc:
        raise Refuse("%s is not parseable XML: %s" % (POM, exc))
    ns = project.tag.split("}")[0][1:] if project.tag.startswith("{") else ""
    q = ("{%s}" % ns) if ns else ""
    ids: list[str] = []
    for profiles in project.findall("%sprofiles" % q):
        for profile in profiles.findall("%sprofile" % q):
            ids.append((profile.findtext("%sid" % q) or "").strip())
    return ids


# ---------------------------------------------------------------------------
# what the profile pins into the test JVM, and where each value comes from
# ---------------------------------------------------------------------------

def _planner_decisions() -> Any:
    """``planner.decisions``, or None when this module is used outside a
    ``.hermes`` tree (a fixture pom has no decisions to read)."""
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            break
    try:
        from planner import decisions as _decisions  # noqa: PLC0415
    except ImportError:
        return None
    return _decisions


def read_security_mode(root: Path) -> str:
    """The mode the generated suite on this tree was written FOR, from the
    generator's own manifest. The bootstrap has no ``--security-mode`` of its
    own: it must pin the mode the suite already carries, or the block it
    writes would differ from the one the generator wrote."""
    p = Path(root) / GENERATED_MANIFEST
    if p.is_file():
        try:
            mode = str((_load_json(p) or {}).get("security_mode") or "").strip()
        except (OSError, ValueError):
            mode = ""
        if mode in SECURITY_MODES:
            return mode
    return DEFAULT_SECURITY_MODE


def declared_pins(root: Path, security_mode: str = "") -> dict[str, Any]:
    """The two DECLARED values the test JVM must be given, read from
    decisions.yaml -- never from a specimen literal.

    ``test_profile``   the decided build profiles, comma-joined exactly as the
                       bootstrap writes them for ``quarkus.profile``.
    ``security_key``/``security_value``  the declared switch, set to the value
                       of the mode the suite was generated for.

    Whatever could not be read is a NOTE, not a silent omission: a suite whose
    mode nobody pinned is decided by whatever the test classpath happens to
    set, and the manifest has to say so."""
    root = Path(root)
    mode = str(security_mode or "").strip() or read_security_mode(root)
    pins: dict[str, Any] = {
        "test_profile": "",
        "build_profiles": [],
        "build_profiles_adr": "",
        "security_mode": mode,
        "security_key": "",
        "security_value": "",
        "security_adr": "",
        "security_pinned": False,
        "notes": [],
    }
    mod = _planner_decisions()
    if mod is None:
        pins["notes"].append("planner.decisions is not importable from here, so neither the decided build profiles nor the "
                             "security switch could be read; the %s profile pins neither" % POM_PROFILE_ID)
        return pins
    if not (root / DECISIONS_FILE).is_file():
        pins["notes"].append("no %s in this tree: the build profiles the test augmentation must activate are undeclared and "
                             "the security mode of the generated suite is UNPINNED" % DECISIONS_FILE.as_posix())
        return pins
    try:
        doc = mod.load_decisions(root)
    except mod.DecisionsError as exc:
        pins["notes"].append("%s could not be read (%s); the %s profile pins nothing from it"
                             % (DECISIONS_FILE.as_posix(), exc, POM_PROFILE_ID))
        return pins

    decided = mod.build_profiles(doc)
    active = [str(x) for x in (decided.get("active") or [])]
    if active:
        pins["build_profiles"] = active
        pins["build_profiles_adr"] = str(decided.get("adr") or "")
        pins["test_profile"] = ",".join(active)
    else:
        pins["notes"].append("decisions.yaml activates no build profile, so the test augmentation is left at the platform's "
                             "default; every bean guarded by a profile is then absent from the generated suite's run")

    sec = mod.security(doc)
    switch = (sec.get("switch") or {}) if sec else {}
    key = str(switch.get("key") or "").strip()
    value = str(switch.get("enabled_value" if mode == "enabled" else "disabled_value") or "").strip()
    if key and value:
        if not _XML_NAME.match(key):
            raise Refuse("the declared security switch key %r cannot be written as a systemPropertyVariables entry (it is not an "
                         "XML element name); the %s profile would otherwise claim to pin a mode it does not pin" % (key, POM_PROFILE_ID))
        pins["security_key"] = key
        pins["security_value"] = value
        pins["security_adr"] = str(sec.get("adr") or "")
        pins["security_pinned"] = True
    else:
        pins["notes"].append("decisions.yaml declares no usable security switch, so the %s-mode suite's security mode is "
                             "UNPINNED: whatever the test classpath sets decides it" % mode)
    return pins


def _pin_rows(pins: dict[str, Any]) -> list[tuple[str, str]]:
    """The properties this profile pins, in a fixed order."""
    rows: list[tuple[str, str]] = []
    if pins.get("test_profile"):
        rows.append((TEST_PROFILE_PROPERTY, str(pins["test_profile"])))
    if pins.get("security_key"):
        rows.append((str(pins["security_key"]), str(pins["security_value"])))
    return rows


def _xml_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _comment_safe(value: str) -> str:
    """A declared name goes into the block's COMMENT, and ``--`` inside an XML
    comment is not well-formed. Nothing declared is rejected for it: the
    comment is spelled so the pom stays parseable, and the pinned element
    below carries the value itself."""
    out = value
    while "--" in out:
        out = out.replace("--", "- -")
    return out


def _base_test_plugins(text: str) -> dict[str, tuple[str, dict[str, str]]]:
    """``artifactId -> (groupId, {property: value})`` for the test plugins the
    pom's OWN ``<build>`` declares, with whatever each already sets in
    ``systemPropertyVariables`` (wherever under the plugin it sets it: the
    failsafe configuration the platform guide documents lives inside an
    execution). The harness block is stripped first -- reading it back would
    make the block an input to itself."""
    stripped, _present = strip_profile_block(text)
    try:
        project = ET.fromstring(stripped)
    except ET.ParseError as exc:
        raise Refuse("%s is not parseable XML: %s" % (POM, exc))
    ns = project.tag.split("}")[0][1:] if project.tag.startswith("{") else ""
    q = ("{%s}" % ns) if ns else ""
    out: dict[str, tuple[str, dict[str, str]]] = {}
    for build in project.findall("%sbuild" % q):
        for plugins in build.findall("%splugins" % q):
            for p in plugins.findall("%splugin" % q):
                art = (p.findtext("%sartifactId" % q) or "").strip()
                if art not in TEST_PLUGINS:
                    continue
                group = (p.findtext("%sgroupId" % q) or "").strip() or TEST_PLUGIN_GROUP
                props: dict[str, str] = {}
                for spv in p.iter("%ssystemPropertyVariables" % q):
                    for child in spv:
                        name = child.tag.split("}")[-1]
                        if _XML_NAME.match(name):
                            props[name] = (child.text or "").strip()
                out[art] = (group, props)
    return out


def test_plugin_config(text: str, pins: dict[str, Any]) -> list[tuple[str, str, list[tuple[str, str]]]]:
    """``[(groupId, artifactId, [(property, value), ...])]`` -- what the
    profile configures, pinned properties first and then every property the
    base pom's own configuration of that plugin already sets.

    Restating the carried ones is deliberate: this profile's plugin
    configuration is the destination's, merged with the base build's, and a
    block that listed only the two pins would be read as the whole story by
    anyone comparing the two. Nothing in the base ``<build>`` is edited.

    Nothing to pin, nothing to configure: a tree that declares neither the
    build profiles nor a security switch gets the block it always got."""
    pin_rows = _pin_rows(pins)
    if not pin_rows:
        return []
    declared = _base_test_plugins(text)
    arts = [a for a in TEST_PLUGINS if a in declared] or [SUREFIRE_ARTIFACT]
    pinned = {name for name, _v in pin_rows}
    out: list[tuple[str, str, list[tuple[str, str]]]] = []
    for art in arts:
        group, carried = declared.get(art, (TEST_PLUGIN_GROUP, {}))
        rows = list(pin_rows) + [(n, carried[n]) for n in sorted(carried) if n not in pinned]
        out.append((group, art, rows))
    return out


def _pin_comment(pins: dict[str, Any], test_plugins: list[tuple[str, str, list[tuple[str, str]]]], i: str) -> list[str]:
    """The block says, in the pom, what the two pins ARE. A reader who finds a
    property set in a profile has to be able to tell a declared value restated
    where the test JVM reads it from a test-only override that makes the suite
    answer a question the destination does not."""
    if not test_plugins:
        return []
    lines = [
        "",
        i + "  THESE ARE NOT TEST-ONLY OVERRIDES. Each systemPropertyVariables",
        i + "  entry below restates, where the test JVM reads it, a value the",
        i + "  destination already declares:",
    ]
    if pins.get("test_profile"):
        lines += [
            "",
            i + "    %s" % TEST_PROFILE_PROPERTY,
            i + "      the destination's own build profiles (decisions.yaml",
            i + "      build_profiles%s), the same value the bootstrap writes as"
            % ((" " + _comment_safe(str(pins["build_profiles_adr"]))) if pins.get("build_profiles_adr") else ""),
            i + "      -Dquarkus.profile in .mvn/maven.config and as",
            i + "      quarkus.profile in application.properties. @QuarkusTest",
            i + "      augments under the TEST profile, which quarkus.profile does",
            i + "      not select, so without this every profile-guarded bean is",
            i + "      @Vetoed in the test augmentation.",
        ]
    if pins.get("security_key"):
        lines += [
            "",
            i + "    %s" % _comment_safe(str(pins["security_key"])),
            i + "      the source's declared security switch (decisions.yaml",
            i + "      security.switch%s), set to the value of the %s mode the"
            % ((" " + _comment_safe(str(pins["security_adr"]))) if pins.get("security_adr") else "",
               _comment_safe(str(pins.get("security_mode") or ""))),
            i + "      generated suite was captured and written for. The frozen",
            i + "      source's own test resources are on the test classpath and",
            i + "      would otherwise flip the mode under this suite, which would",
            i + "      then answer for a configuration nobody captured.",
        ]
    lines += [
        "",
        i + "  Every other entry is one the base build's own configuration of",
        i + "  that plugin already sets; it is restated here so this profile's",
        i + "  configuration adds to it and the base <build> stays untouched.",
    ]
    return lines


def _test_plugin_lines(test_plugins: list[tuple[str, str, list[tuple[str, str]]]], line: Any) -> list[str]:
    out: list[str] = []
    for group, artifact, rows in test_plugins:
        out += [
            line(3, "<plugin>"),
            line(4, "<groupId>%s</groupId>" % group),
            line(4, "<artifactId>%s</artifactId>" % artifact),
            line(4, "<configuration>"),
            line(5, "<systemPropertyVariables>"),
        ]
        out += [line(6, "<%s>%s</%s>" % (name, _xml_text(value), name)) for name, value in rows]
        out += [
            line(5, "</systemPropertyVariables>"),
            line(4, "</configuration>"),
            line(3, "</plugin>"),
        ]
    return out


def pom_profile_block(out_dir: str, resources_dir: str, version: str, pins: dict[str, Any] | None = None,
                      test_plugins: list[tuple[str, str, list[tuple[str, str]]]] | None = None,
                      indent: str = "    ") -> str:
    """The block, markers included, deterministic in its inputs."""
    step = "  "
    i = indent
    pins = pins or {}
    test_plugins = test_plugins or []

    def line(depth: int, text: str) -> str:
        return i + step * depth + text

    version_lines = [line(4, "<version>%s</version>" % version)] if version else []
    return "\n".join([
        i + POM_BEGIN,
        i + "<!--",
        i + "  Generated product parity tests (ADR-015), owned by the harness:",
        i + "  generate-product-tests.py writes exactly this block, and the M4",
        i + "  release floor refuses when a byte of it moved. Never edit it by",
        i + "  hand.",
        "",
        i + "  The generated cases live OUTSIDE src/test/java on purpose. They",
        i + "  measure parity, which is measured once, at M4; compiled into the",
        i + "  ordinary test root they would run in every M3 verify and a parity",
        i + "  finding would revert the step that was being verified. This",
        i + "  profile is what makes them runnable, and only the M4 pre-verdict",
        i + "  runner activates it (-P%s)." % POM_PROFILE_ID,
        *_pin_comment(pins, test_plugins, i),
        i + "-->",
        line(0, "<profile>"),
        line(1, "<id>%s</id>" % POM_PROFILE_ID),
        line(1, "<build>"),
        line(2, "<plugins>"),
        line(3, "<plugin>"),
        line(4, "<groupId>%s</groupId>" % POM_PLUGIN_GROUP),
        line(4, "<artifactId>%s</artifactId>" % POM_PLUGIN_ARTIFACT),
        *version_lines,
        line(4, "<executions>"),
        line(5, "<execution>"),
        line(6, "<id>rhoai3-parity-test-source</id>"),
        line(6, "<phase>generate-test-sources</phase>"),
        line(6, "<goals>"),
        line(7, "<goal>add-test-source</goal>"),
        line(6, "</goals>"),
        line(6, "<configuration>"),
        line(7, "<sources>"),
        line(8, "<source>%s</source>" % out_dir),
        line(7, "</sources>"),
        line(6, "</configuration>"),
        line(5, "</execution>"),
        line(5, "<execution>"),
        line(6, "<id>rhoai3-parity-test-resource</id>"),
        line(6, "<phase>generate-test-resources</phase>"),
        line(6, "<goals>"),
        line(7, "<goal>add-test-resource</goal>"),
        line(6, "</goals>"),
        line(6, "<configuration>"),
        line(7, "<resources>"),
        line(8, "<resource>"),
        line(9, "<directory>%s</directory>" % resources_dir),
        line(8, "</resource>"),
        line(7, "</resources>"),
        line(6, "</configuration>"),
        line(5, "</execution>"),
        line(4, "</executions>"),
        line(3, "</plugin>"),
        *_test_plugin_lines(test_plugins, line),
        line(2, "</plugins>"),
        line(1, "</build>"),
        line(0, "</profile>"),
        i + POM_END,
    ])


def pom_plugin_pin(root: Path) -> dict[str, Any]:
    """Whether the destination's own BOM evidence manages the plugin. It is
    read, never assumed: probe-bom-managed.py measures dependencyManagement,
    so the usual answer is 'no' and the version is pinned here."""
    managed = False
    evidence = "no %s; %s does not measure pluginManagement" % (BOM_MANAGED.as_posix(), "probe-bom-managed.py")
    p = Path(root) / BOM_MANAGED
    if p.is_file():
        try:
            doc = _load_json(p)
        except (OSError, ValueError) as exc:
            raise Refuse("%s could not be read: %s" % (BOM_MANAGED, exc))
        rows = (doc or {}).get("managed") or []
        managed = "%s:%s" % (POM_PLUGIN_GROUP, POM_PLUGIN_ARTIFACT) in {str(r) for r in rows}
        evidence = "%s (%d artifact(s))" % (BOM_MANAGED.as_posix(), len(rows))
    return {
        "group_id": POM_PLUGIN_GROUP,
        "artifact_id": POM_PLUGIN_ARTIFACT,
        "version": "" if managed else POM_PLUGIN_VERSION,
        "managed_by_bom": managed,
        "evidence": evidence,
    }


def ensure_pom_profile(root: Path, out_dir: str, resources_dir: str, security_mode: str = "") -> dict[str, Any]:
    """Write (or rewrite) the marked block, idempotently. The pom is a
    harness-owned change here: it is recorded and printed, never committed by
    THIS function -- the bootstrap commits the tree it writes, and at M4 the
    road's commit step commits what the generator wrote.

    ``security_mode`` is the mode the generated suite is written for. The
    generator passes its own; the bootstrap passes nothing and the mode is
    read from the generator's manifest, so both write the SAME block."""
    root = Path(root)
    text = _pom_text(root)
    region = _pom_marked_region(text)
    ids = [i for i in _pom_profile_ids(text) if i == POM_PROFILE_ID]
    if region is None and ids:
        raise Refuse("%s already declares a %r profile outside the %s markers; this producer will not take it over — "
                     "remove it, or move it under the markers deliberately" % (POM, POM_PROFILE_ID, POM_BEGIN))
    if region is not None and len(ids) > 1:
        raise Refuse("%s declares %d %r profiles and only the marked one is this producer's" % (POM, len(ids), POM_PROFILE_ID))

    plugin = pom_plugin_pin(root)
    pins = declared_pins(root, security_mode)
    test_plugins = test_plugin_config(text, pins)
    block = pom_profile_block(out_dir, resources_dir, plugin["version"], pins, test_plugins)
    if region is not None:
        start, end = region
        line_start = text.rfind("\n", 0, start) + 1
        new = text[:line_start] + block + text[end:]
        where = "replaced"
    elif _PROFILES_CLOSE in text:
        close = text.rindex(_PROFILES_CLOSE)
        line_start = text.rfind("\n", 0, close) + 1
        new = text[:line_start] + block + "\n" + text[line_start:]
        where = "added to <profiles>"
    elif "</project>" in text:
        close = text.rindex("</project>")
        line_start = text.rfind("\n", 0, close) + 1
        new = text[:line_start] + "  <profiles>\n" + block + "\n  </profiles>\n" + text[line_start:]
        where = "added with a new <profiles>"
    else:
        raise Refuse("%s has no </project>; it is not a pom this producer can extend" % POM)

    changed = new != text
    if changed:
        (root / POM).write_text(new, encoding="utf-8")
    region = _pom_marked_region(new)
    assert region is not None  # just written
    body = new[region[0]:region[1]]
    return {
        "path": POM,
        "profile_id": POM_PROFILE_ID,
        "begin_marker": POM_BEGIN,
        "end_marker": POM_END,
        "test_source": out_dir,
        "test_resources": resources_dir,
        "plugin": plugin,
        # what the profile hands the test JVM, and where each value came from
        "pins": pins,
        "test_plugins": [{"group_id": g, "artifact_id": a,
                          "system_properties": [{"name": n, "value": v} for n, v in rows]}
                         for g, a, rows in test_plugins],
        "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "changed": changed,
        "placement": where,
    }


def read_pom_profile(root: Path) -> tuple[str, str]:
    """(digest, body) of the marked block on disk, for --check."""
    text = _pom_text(root)
    region = _pom_marked_region(text)
    if region is None:
        raise Refuse("%s carries no %s block; the %s profile that compiles and runs the generated tests is gone, so a "
                     "test phase would silently run none of them" % (POM, POM_BEGIN, POM_PROFILE_ID))
    body = text[region[0]:region[1]]
    return hashlib.sha256(body.encode("utf-8")).hexdigest(), body


STALE_BLOCK = "stale block: regenerate with --reapply-catalog"


def block_pin_gaps(root: Path, body: str, security_mode: str = "") -> list[str]:
    """Which DECLARED pin the block on disk does not carry.

    A block whose bytes match its own manifest can still be the block that was
    written before these pins existed -- and that block runs the generated
    suite with the guards inactive and the mode decided by the test classpath.
    The digest cannot see that; only the declaration can."""
    gaps: list[str] = []
    for name, value in _pin_rows(declared_pins(root, security_mode)):
        if ("<%s>%s</%s>" % (name, _xml_text(value), name)) not in body:
            gaps.append("%s=%s" % (name, value))
    return gaps


def block_sha256(text: str) -> str:
    """The digest of the marked block in ``text``, or "" when there is none.
    A producer that rewrites the pom uses it to record a CHANGE only when the
    block it writes back differs from the one it found."""
    region = _pom_marked_region(text)
    if region is None:
        return ""
    return hashlib.sha256(text[region[0]:region[1]].encode("utf-8")).hexdigest()


def _strip_emptied_profiles(text: str) -> str:
    """Remove a ``<profiles>`` wrapper that the block's removal left empty, so
    the next ``ensure_pom_profile`` rebuilds exactly what it built the first
    time. A wrapper that still holds a profile is left alone."""
    open_i = text.find(_PROFILES_OPEN)
    if open_i < 0:
        return text
    close_i = text.find(_PROFILES_CLOSE, open_i)
    if close_i < 0:
        return text
    if text[open_i + len(_PROFILES_OPEN):close_i].strip():
        return text
    line_start = text.rfind("\n", 0, open_i) + 1
    line_end = close_i + len(_PROFILES_CLOSE)
    if text[line_end:line_end + 1] == "\n":
        line_end += 1
    return text[:line_start] + text[line_end:]


def strip_profile_block(text: str) -> tuple[str, bool]:
    """(text without the marked block, whether there was one).

    For producers that rewrite the pom through ElementTree: the block is XML
    COMMENTS plus a profile and ET drops comments, so it is taken out before
    the parse and written back verbatim afterwards. Doing it the other way
    round loses the markers and the next run then refuses an ``m4-parity``
    profile it no longer recognises as its own."""
    region = _pom_marked_region(text)
    if region is None:
        return text, False
    start, end = region
    line_start = text.rfind("\n", 0, start) + 1
    line_end = end
    if text[line_end:line_end + 1] == "\n":
        line_end += 1
    return _strip_emptied_profiles(text[:line_start] + text[line_end:]), True


def strip_profile_block_file(root: Path) -> str:
    """Take the block out of ``root/pom.xml`` and return the digest it had (""
    when there was none), so the caller can tell a rewrite from a no-op."""
    pom = Path(root) / POM
    if not pom.is_file():
        return ""
    text = pom.read_text(encoding="utf-8")
    had = block_sha256(text)
    stripped, present = strip_profile_block(text)
    if present:
        pom.write_text(stripped, encoding="utf-8")
    return had
