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
"""
from __future__ import annotations

import hashlib
import json
import re
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


def pom_profile_block(out_dir: str, resources_dir: str, version: str, indent: str = "    ") -> str:
    """The block, markers included, deterministic in its inputs."""
    step = "  "
    i = indent

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


def ensure_pom_profile(root: Path, out_dir: str, resources_dir: str) -> dict[str, Any]:
    """Write (or rewrite) the marked block, idempotently. The pom is a
    harness-owned change here: it is recorded and printed, never committed by
    THIS function -- the bootstrap commits the tree it writes, and at M4 the
    road's commit step commits what the generator wrote."""
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
    block = pom_profile_block(out_dir, resources_dir, plugin["version"])
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
