#!/usr/bin/env python3
"""Decided repairs at bootstrap (ADR-019 §2, §3): the transformation engine.

An accepted ADR that already decided a repair is carried into a fresh run as
TRANSFORMATIONS, enumerated in a versioned specimen manifest that
``decisions.yaml`` ``decided_repairs`` names and pins by sha256. This module
applies them to the bootstrapped destination BEFORE the first loop baseline
and writes one receipt row per transformation to
``evidence/producers/decided-repairs.json``.

The engine knows kinds, never applications. Every name it touches -- a type,
a member, an annotation, a Maven coordinate, a property key -- comes from the
manifest; nothing here branches on a specimen identifier.

Kinds (each atomic: a refused transformation writes nothing):

  add_file                  a reviewed new file, added only where absent or
                            already byte-identical; different bytes are
                            REPAIR_FILE_CONFLICT
  replace_reviewed_file     a reviewed replacement of one source file: applied
                            only over the exact source bytes the review was
                            bound to, reused only while the independent review
                            record matches the installed bytes and the source
  java_annotation_expression
                            every annotation of one resolved type gets its
                            string attribute rewritten through a template that
                            keeps the ORIGINAL expression verbatim; located by
                            the JDK compiler's parse tree, bound to the source's
                            site inventory, and only the literal token changes
  java_member_annotation    one annotation added to one declaration (a type or
                            a field) plus the imports it needs
  pom_dependency            one dependency row (XML DOM); an existing row with a
                            different version/scope/type is a conflict
  property                  one key=value row; an existing different value --
                            unprefixed or under any profile -- is a conflict
  pom_retire_execution      one plugin execution removed, only when its goals,
                            phase and configuration equal the decided ones and
                            the preserved goals stay; anything else is
                            REPAIR_EXECUTION_MISMATCH

Every row carries: the ADR, the applicable source structure (expected and
observed digest, read from the FROZEN copy), the implementation version (and
the digests of this file and the Java tool), input and output digests, the
files and symbols it touched, and a status: applied / already-applied /
refused (with a typed class). A second run over the same tree changes no file
and records already-applied.

Standalone:
  python3 _decided_repairs.py --root DEST [--copy FROZEN] [--describe-source]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _hermes_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "lib" / ".hermes-lib").is_file():
            return parent
    raise SystemExit("FAIL: .hermes/lib marker missing")


if str(_hermes_root() / "lib") not in sys.path:
    sys.path.insert(0, str(_hermes_root() / "lib"))

from planner.canonical import digest, load_json, sha256_bytes, sha256_file, write_canonical  # noqa: E402
from planner.decided_repairs import CLASSIFICATION, MANIFEST_SCHEMA, RECEIPT_SCHEMA, section  # noqa: E402
from planner.decisions import accepted_adrs, build_profiles, retired_sources  # noqa: E402
from planner.paths import BOM_MANAGED, DECIDED_REPAIRS_RECEIPT, SCHEMAS_DIR  # noqa: E402
from planner.schema_lite import load_schema, validate  # noqa: E402

ENGINE_NAME = "decided-repairs"
ENGINE_VERSION = "1.0.0"
TOOL = Path(__file__).resolve().parent / "java-structure" / "JavaStructure.java"
APPLIED, ALREADY, REFUSED = "applied", "already-applied", "refused"
KINDS = ("add_file", "replace_reviewed_file", "java_annotation_expression", "java_member_annotation",
         "pom_dependency", "property", "pom_retire_execution")


class Refusal(Exception):
    def __init__(self, cls: str, detail: str) -> None:
        super().__init__("%s: %s" % (cls, detail))
        self.cls = cls
        self.detail = detail


def _sha_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def _file_sha(p: Path) -> str:
    return sha256_file(p) if p.is_file() else ""


def _rel(path: str) -> str:
    p = str(path or "").replace("\\", "/").lstrip("/")
    if not p or ".." in p.split("/"):
        raise Refusal("REPAIR_MANIFEST_INVALID", "unsafe or empty path %r" % path)
    return p


# ---------------------------------------------------------------------------
# the JDK compiler's parse tree
# ---------------------------------------------------------------------------
class JavaModel:
    """JavaStructure.java, compiled once per tool digest (cached beside the
    system temp directory, stamped by the tool's sha256)."""

    def __init__(self) -> None:
        self._classes = ""
        self._java = ""
        self._cache: dict[tuple[str, str, str], dict] = {}

    def _ensure(self) -> str:
        if self._classes:
            return self._classes
        java_home = os.environ.get("JAVA_HOME_21") or os.environ.get("JAVA_HOME") or ""
        bindir = Path(java_home) / "bin" if java_home else None
        javac = str(bindir / "javac") if bindir and (bindir / "javac").is_file() else shutil.which("javac")
        java = str(bindir / "java") if bindir and (bindir / "java").is_file() else shutil.which("java")
        if not javac or not java or not TOOL.is_file():
            raise Refusal("REPAIR_TOOL_MISSING", "a JDK (javac and java) and %s are required; Java declarations are never edited without the compiler's parse tree" % TOOL.name)
        tool_sha = sha256_file(TOOL)
        cache = Path(tempfile.gettempdir()) / ("rhoai3-java-structure-%s" % tool_sha[:24])
        stamp = cache / ".tool-sha256"
        if not (stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == tool_sha and (cache / "JavaStructure.class").is_file()):
            staging = Path(tempfile.mkdtemp(prefix="java-structure-build-"))
            p = subprocess.run([javac, "-d", str(staging), str(TOOL)], capture_output=True, text=True)
            if p.returncode != 0:
                shutil.rmtree(staging, ignore_errors=True)
                raise Refusal("REPAIR_TOOL_MISSING", "JavaStructure.java did not compile: %s" % (p.stderr or p.stdout)[-300:])
            (staging / ".tool-sha256").write_text(tool_sha + "\n", encoding="utf-8")
            shutil.rmtree(cache, ignore_errors=True)
            try:
                staging.rename(cache)
            except OSError:  # a concurrent run won the rename; its classes are the same tool
                shutil.rmtree(staging, ignore_errors=True)
        self._classes, self._java = str(cache), java
        return self._classes

    def files(self, base: Path, rels: list[str]) -> dict[str, dict]:
        """Structure per relative path. Cached by the file's CONTENT, so an
        edited file is always parsed again and an unchanged one never twice."""
        keys = {}
        for rel in rels:
            p = base / rel
            keys[rel] = (str(base), rel, sha256_file(p) if p.is_file() else "")
        missing = sorted(rel for rel, k in keys.items() if k not in self._cache)
        if missing:
            classes = self._ensure()
            with tempfile.TemporaryDirectory(prefix="java-structure-out-") as td:
                out = Path(td) / "structure.json"
                argfile = Path(td) / "files.txt"
                argfile.write_text("\n".join(missing) + "\n", encoding="utf-8")
                p = subprocess.run([self._java, "-cp", classes, "JavaStructure", "--root", str(base), "--out", str(out), "--files", str(argfile)],
                                   capture_output=True, text=True)
                if p.returncode != 0 or not out.is_file():
                    raise Refusal("REPAIR_TOOL_MISSING", "JavaStructure failed: %s" % (p.stderr or p.stdout)[-300:])
                doc = json.loads(out.read_text(encoding="utf-8"))
            for f in doc.get("files") or []:
                self._cache[keys[f["path"]]] = f
        return {rel: self._cache[k] for rel, k in keys.items()}

    def close(self) -> None:
        self._classes = ""
        self._cache.clear()


def java_files(base: Path, roots: list[str]) -> list[str]:
    out: list[str] = []
    for r in roots:
        d = base / r
        if d.is_dir():
            out.extend(p.relative_to(base).as_posix() for p in sorted(d.rglob("*.java")) if p.is_file())
    return out


def resolve_annotation(name: str, f: dict, target: str, base: Path, roots: list[str]) -> str:
    """How the Java Language Specification resolves an annotation's type name
    in this compilation unit, answered for one TARGET type:
    'yes' (it is the target), 'no' (it is another type) or 'unresolved' (the
    parse tree alone cannot tell, and the name could be the target).

    Order (JLS 6.4.1, 7.5): a qualified name is itself (its first segment may
    be an imported or declared simple name); a simple name is a single-type
    import, else a type declared in this file, else a type of the same
    package, else an on-demand import."""
    simple = target.rsplit(".", 1)[-1]
    pkg = str(f.get("package") or "")
    singles = {i["name"].rsplit(".", 1)[-1]: i["name"] for i in f.get("imports") or [] if not i["static"] and not i["on_demand"]}
    declared = {t["simple"]: t["fqn"] for t in f.get("types") or []}
    if "." in name:
        first, rest = name.split(".", 1)
        if first in singles:
            fqn = singles[first] + "." + rest
        elif first in declared:
            fqn = declared[first] + "." + rest
        else:
            fqn = name
        return "yes" if fqn == target else "no"
    if name in singles:
        return "yes" if singles[name] == target else "no"
    if name in declared:
        return "yes" if declared[name] == target else "no"
    same_pkg = any((base / r / pkg.replace(".", "/") / (name + ".java")).is_file() for r in roots)
    if same_pkg:
        return "yes" if (pkg + "." + name if pkg else name) == target else "no"
    if name != simple:
        return "no"
    demand = [i["name"] for i in f.get("imports") or [] if not i["static"] and i["on_demand"]]
    if target.rsplit(".", 1)[0] in demand:
        return "yes"
    return "unresolved"


def _units(text: str) -> bytes:
    return text.encode("utf-16-le")


def _pyidx(text: str, unit_offset: int) -> int:
    """UTF-16 unit offset (javac) -> Python index (code points)."""
    return len(_units(text)[: unit_offset * 2].decode("utf-16-le"))


def splice(text: str, edits: list[tuple[int, int, str]]) -> str:
    """Apply (start, end, replacement) edits given in javac's UTF-16 offsets."""
    u = _units(text)
    for start, end, repl in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        if start < 0 or end < start or end * 2 > len(u):
            raise Refusal("REPAIR_EDIT_UNPARSEABLE", "an edit range from the parse tree is outside the file")
        u = u[: start * 2] + _units(repl) + u[end * 2:]
    return u.decode("utf-16-le")


def java_string_literal(value: str) -> str:
    out = ['"']
    for ch in value:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20:
            out.append("\\u%04x" % ord(ch))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _indent_at(text: str, unit_offset: int) -> str:
    i = _pyidx(text, unit_offset)
    line_start = text.rfind("\n", 0, i) + 1
    j = line_start
    while j < len(text) and text[j] in " \t":
        j += 1
    return text[line_start:j]


# ---------------------------------------------------------------------------
# Maven POM (XML DOM)
# ---------------------------------------------------------------------------
def _ns(root: ET.Element) -> str:
    return root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else ""


def _q(ns: str, tag: str) -> str:
    return "{%s}%s" % (ns, tag) if ns else tag


def _txt(el: ET.Element | None, ns: str, tag: str) -> str:
    if el is None:
        return ""
    c = el.find(_q(ns, tag))
    return (c.text or "").strip() if c is not None and c.text else ""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def readable(el: ET.Element) -> Any:
    """An XML configuration as data: a leaf is its text; an element whose
    children all carry its own name minus a trailing 's' (rules/rule,
    limits/limit, goals/goal) is a list; anything else is a mapping."""
    kids = list(el)
    if not kids:
        return (el.text or "").strip()
    tag = _local(el.tag)
    names = {_local(k.tag) for k in kids}
    if tag.endswith("s") and names == {tag[:-1]}:
        return [readable(k) for k in kids]
    grouped: dict[str, list[Any]] = {}
    for k in kids:
        grouped.setdefault(_local(k.tag), []).append(readable(k))
    return {name: vals[0] if len(vals) == 1 else vals for name, vals in grouped.items()}


def parse_pom(pom: Path) -> tuple[ET.ElementTree, ET.Element, str]:
    if not pom.is_file():
        raise Refusal("REPAIR_POM_INVALID", "%s is absent" % pom.name)
    try:
        tree = ET.parse(pom)
    except ET.ParseError as exc:
        raise Refusal("REPAIR_POM_INVALID", "%s does not parse: %s" % (pom.name, exc))
    root = tree.getroot()
    ns = _ns(root)
    if ns:
        ET.register_namespace("", ns)
    return tree, root, ns


def write_pom(tree: ET.ElementTree, pom: Path) -> None:
    ET.indent(tree, space="  ")
    tree.write(pom, encoding="utf-8", xml_declaration=True)


def plugin_sites(project: ET.Element, ns: str, ga: str) -> list[tuple[str, ET.Element, ET.Element]]:
    """Every declaration of plugin ga: (where, plugins parent, plugin)."""
    g, a = ga.split(":", 1)
    containers: list[tuple[str, ET.Element | None]] = [
        ("build", project.find("%s/%s" % (_q(ns, "build"), _q(ns, "plugins")))),
        ("build.pluginManagement", project.find("%s/%s/%s" % (_q(ns, "build"), _q(ns, "pluginManagement"), _q(ns, "plugins")))),
    ]
    for prof in project.findall("%s/%s" % (_q(ns, "profiles"), _q(ns, "profile"))):
        pid = _txt(prof, ns, "id")
        containers.append(("profile:%s" % pid, prof.find("%s/%s" % (_q(ns, "build"), _q(ns, "plugins")))))
        containers.append(("profile:%s.pluginManagement" % pid, prof.find("%s/%s/%s" % (_q(ns, "build"), _q(ns, "pluginManagement"), _q(ns, "plugins")))))
    out = []
    for where, plugins in containers:
        if plugins is None:
            continue
        for p in plugins.findall(_q(ns, "plugin")):
            if (_txt(p, ns, "groupId") or "org.apache.maven.plugins") == g and _txt(p, ns, "artifactId") == a:
                out.append((where, plugins, p))
    return out


def executions(plugin: ET.Element, ns: str) -> list[tuple[ET.Element, dict[str, Any]]]:
    out = []
    exs = plugin.find(_q(ns, "executions"))
    for ex in (exs.findall(_q(ns, "execution")) if exs is not None else []):
        goals_el = ex.find(_q(ns, "goals"))
        conf = ex.find(_q(ns, "configuration"))
        out.append((ex, {
            "id": _txt(ex, ns, "id") or "default",
            "phase": _txt(ex, ns, "phase") or None,
            "goals": [(g.text or "").strip() for g in (goals_el.findall(_q(ns, "goal")) if goals_el is not None else [])],
            "configuration": readable(conf) if conf is not None else None,
        }))
    return out


def execution_structure(project: ET.Element, ns: str, t: dict) -> dict[str, Any]:
    """What the decided retirement looks at, as data."""
    ga = "%s:%s" % (t["plugin"]["groupId"], t["plugin"]["artifactId"])
    sites = plugin_sites(project, ns, ga)
    rows = []
    for where, _parent, p in sites:
        conf = p.find(_q(ns, "configuration"))
        rows.append({"where": where,
                     "plugin_configuration_keys": sorted(readable(conf).keys()) if conf is not None and isinstance(readable(conf), dict) else [],
                     "executions": [e for _el, e in executions(p, ns)]})
    return {"plugin": ga, "declarations": rows}


# ---------------------------------------------------------------------------
# properties (java.util.Properties line grammar, no regular expressions)
# ---------------------------------------------------------------------------
def _logical_lines(text: str) -> list[str]:
    out: list[str] = []
    buf = ""
    cont = False
    for raw in text.splitlines():
        line = raw.lstrip(" \t\f") if cont or not buf else raw
        if not cont:
            stripped = line.lstrip(" \t\f")
            if not stripped or stripped[0] in "#!":
                out.append("")
                continue
            line = stripped
        n = len(line) - len(line.rstrip("\\"))
        if n % 2 == 1:
            buf += line[:-1]
            cont = True
            continue
        out.append(buf + line)
        buf, cont = "", False
    if buf:
        out.append(buf)
    return out


def _unescape(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "u" and i + 5 < len(s):
                try:
                    out.append(chr(int(s[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
            out.append({"t": "\t", "n": "\n", "r": "\r", "f": "\f"}.get(n, n))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def properties_entries(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in _logical_lines(text):
        if not line:
            continue
        i, key_end = 0, None
        while i < len(line):
            c = line[i]
            if c == "\\":
                i += 2
                continue
            if c in "=: \t\f":
                key_end = i
                break
            i += 1
        if key_end is None:
            rows.append((_unescape(line), ""))
            continue
        key = line[:key_end]
        rest = line[key_end:]
        rest = rest.lstrip(" \t\f")
        if rest[:1] in ("=", ":"):
            rest = rest[1:].lstrip(" \t\f")
        rows.append((_unescape(key), _unescape(rest)))
    return rows


def _simple_token(s: str) -> bool:
    return bool(s) and all(c.isalnum() or c in "._-%/" for c in s)


# ---------------------------------------------------------------------------
# the engine
# ---------------------------------------------------------------------------
class Engine:
    def __init__(self, root: Path, copy: Path, manifest_path: Path, manifest: dict, accepted: set[str], decision: dict,
                 retired: set[str] | None = None) -> None:
        self.root = root
        # sources an accepted ADR retires are never in the destination, so they
        # are no part of the structure a decided repair applies to
        self.retired = set(retired or ())
        self.copy = copy
        self.manifest_path = manifest_path
        self.manifest = manifest
        self.accepted = accepted
        self.decision = decision
        self.java = JavaModel()
        self.reviews = {str(r.get("id")): r for r in manifest.get("review_records") or [] if isinstance(r, dict)}
        self.review_results: dict[str, dict] = {}
        self.coverage: list[dict] = []
        self.obligations: list[str] = []

    # -- helpers ----------------------------------------------------------
    def content(self, t: dict) -> bytes:
        src = self.root / _rel(t.get("content") or "")
        if not src.is_file():
            raise Refusal("REPAIR_CONTENT_MISSING", "the reviewed content %s is not in the tree" % t.get("content"))
        data = src.read_bytes()
        if sha256_bytes(data) != str(t.get("content_sha256") or ""):
            raise Refusal("REPAIR_CONTENT_DIGEST", "%s is %s, the manifest pins %s; the reviewed bytes changed"
                          % (t.get("content"), sha256_bytes(data)[:12], str(t.get("content_sha256") or "")[:12]))
        return data

    def review(self, t: dict, artifact_sha: str, source_sha: str) -> dict:
        """ADR-019 §2: an independent review is reused only for the exact
        reviewed artifact and its applicability contract. An ADR identifier is
        not a review record."""
        rid = str(t.get("review_record") or "")
        rec = self.reviews.get(rid)
        if not rid or rec is None:
            raise Refusal("REPAIR_REVIEW_MISSING", "%s requires an independent review record and the manifest names %s"
                          % (t["id"], ("%r, which it does not carry" % rid) if rid else "none"))
        author = str(rec.get("author") or "").strip()
        reviewer = str(rec.get("reviewer") or "").strip()
        if not reviewer or not author or reviewer == author:
            raise Refusal("REPAIR_REVIEW_NOT_INDEPENDENT", "review record %s names author %r and reviewer %r; an independent review needs two distinct seats"
                          % (rid, author, reviewer))
        if str(rec.get("adr") or "") != str(t.get("adr") or ""):
            raise Refusal("REPAIR_REVIEW_MISSING", "review record %s is for %s, the transformation is %s" % (rid, rec.get("adr"), t.get("adr")))
        arts = [a for a in rec.get("reviewed_artifacts") or [] if isinstance(a, dict)]
        art = next((a for a in arts if _rel(a.get("path") or "") == _rel(t["path"])), None)
        if art is None or str(art.get("sha256") or "") != artifact_sha:
            raise Refusal("REPAIR_REVIEW_ARTIFACT_MISMATCH", "review record %s reviewed %s; this transformation installs %s@%s, so the review does not cover these bytes"
                          % (rid, ("%s@%s" % (art.get("path"), str(art.get("sha256") or "")[:12])) if art else "no artifact at that path", t["path"], artifact_sha[:12]))
        appl = art.get("applicability") or {}
        if "source_sha256" in appl and str(appl.get("source_sha256") or "") != source_sha:
            raise Refusal("REPAIR_REVIEW_APPLICABILITY", "review record %s applies to source %s@%s; the frozen source has %s"
                          % (rid, appl.get("source_path"), str(appl.get("source_sha256") or "")[:12], source_sha[:12] or "(absent)"))
        result = self.review_results.setdefault(rid, {"id": rid, "adr": rec.get("adr"), "kind": rec.get("kind"), "author": author,
                                                       "reviewer": reviewer, "operator": rec.get("operator"),
                                                       "source": rec.get("source"), "artifacts": []})
        result["artifacts"].append({"path": _rel(t["path"]), "reviewed_sha256": artifact_sha, "applicability": appl,
                                    "result": "reused: installed bytes and applicability match the reviewed artifact"})
        return {"record": rid, "author": author, "reviewer": reviewer, "reviewed_sha256": artifact_sha}

    # -- kinds ------------------------------------------------------------
    def add_file(self, t: dict, row: dict) -> str:
        rel = _rel(t["path"])
        data = self.content(t)
        src = self.copy / rel
        observed = "present:" + sha256_file(src) if src.is_file() else "absent"
        row["applicability"] = {"expected": "absent", "observed": observed}
        if src.is_file() and sha256_file(src) != sha256_bytes(data):
            raise Refusal("REPAIR_NOT_APPLICABLE", "%s exists in the frozen source with other content, so it is not a new file" % rel)
        if t.get("review_record"):
            row["review"] = self.review(t, sha256_bytes(data), "")
        dst = self.root / rel
        row["inputs"] = {rel: _file_sha(dst), t["content"]: sha256_bytes(data)}
        row["files"] = [rel]
        row["symbols"] = [self.symbol_of(rel)]
        if dst.is_file():
            if dst.read_bytes() == data:
                row["outputs"] = {rel: sha256_bytes(data)}
                return ALREADY
            raise Refusal("REPAIR_FILE_CONFLICT", "%s already exists with other content (%s, the reviewed file is %s); it is never overwritten"
                          % (rel, sha256_file(dst)[:12], sha256_bytes(data)[:12]))
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        row["outputs"] = {rel: sha256_bytes(data)}
        return APPLIED

    def replace_reviewed_file(self, t: dict, row: dict) -> str:
        rel = _rel(t["path"])
        data = self.content(t)
        src = self.copy / rel
        want_src = str((t.get("applicability") or {}).get("source_sha256") or "")
        src_sha = _file_sha(src)
        row["applicability"] = {"expected": want_src, "observed": src_sha}
        if not want_src or src_sha != want_src:
            raise Refusal("REPAIR_NOT_APPLICABLE", "the replacement of %s applies to source bytes %s; the frozen source has %s"
                          % (rel, want_src[:12] or "(unstated)", src_sha[:12] or "(absent)"))
        row["review"] = self.review(t, sha256_bytes(data), src_sha)
        dst = self.root / rel
        before = _file_sha(dst)
        row["inputs"] = {rel: before, t["content"]: sha256_bytes(data)}
        row["files"] = [rel]
        row["symbols"] = [self.symbol_of(rel)]
        for ob in t.get("obligations") or []:
            self.obligations.append("%s (%s): %s" % (t["id"], t.get("adr"), ob))
        if before == sha256_bytes(data):
            status = ALREADY
        elif before == src_sha:
            dst.write_bytes(data)
            status = APPLIED
        else:
            raise Refusal("REPAIR_FILE_CONFLICT", "%s is neither the source bytes the review applies to (%s) nor the reviewed bytes (%s): %s"
                          % (rel, src_sha[:12], sha256_bytes(data)[:12], before[:12] or "(absent)"))
        installed = _file_sha(dst)
        if installed != sha256_bytes(data):
            raise Refusal("REPAIR_REVIEW_ARTIFACT_MISMATCH", "installed %s is %s, not the reviewed %s" % (rel, installed[:12], sha256_bytes(data)[:12]))
        row["outputs"] = {rel: installed}
        return status

    @staticmethod
    def symbol_of(rel: str) -> str:
        for r in ("src/main/java/", "src/test/java/"):
            if rel.startswith(r) and rel.endswith(".java"):
                return rel[len(r):-5].replace("/", ".")
        return rel

    def _sites(self, base: Path, roots: list[str], ann: str, attr: str) -> tuple[list[dict], dict[str, dict]]:
        files = self.java.files(base, [r for r in java_files(base, roots) if r not in self.retired])
        sites: list[dict] = []
        for rel, f in sorted(files.items()):
            if f.get("parse_errors"):
                raise Refusal("REPAIR_JAVA_UNPARSEABLE", "%s does not parse (%s); no declaration in it is edited"
                              % (rel, (f["parse_errors"][0] or {}).get("message", "")[:120]))
            for ty in f.get("types") or []:
                holders = [("type", "", ty)] + [(m["kind"], m["name"], m) for m in ty.get("members") or []]
                for kind, name, holder in holders:
                    for a in holder.get("annotations") or []:
                        res = resolve_annotation(a["name"], f, ann, base, roots)
                        if res == "no":
                            continue
                        if res == "unresolved":
                            raise Refusal("REPAIR_ANNOTATION_UNRESOLVED", "@%s on %s#%s in %s cannot be resolved to %s or excluded from the parse tree and imports"
                                          % (a["name"], ty["fqn"], name, rel, ann))
                        arg = next((x for x in a.get("args") or [] if x["name"] == attr), None)
                        sites.append({"path": rel, "type": ty["fqn"], "member_kind": kind, "member": name,
                                      "params": holder.get("params"), "annotation": a, "arg": arg})
        return sites, files

    def java_annotation_expression(self, t: dict, row: dict) -> str:
        roots = [str(r) for r in (t.get("roots") or ["src/main/java"])]
        ann, attr, template = str(t["annotation"]), str(t.get("attribute") or "value"), str(t["template"])
        if template.count("{expression}") != 1:
            raise Refusal("REPAIR_MANIFEST_INVALID", "%s: the template must contain {expression} exactly once" % t["id"])
        prefix, suffix = template.split("{expression}")

        def expr_of(s: dict, where: str) -> str:
            arg = s["arg"]
            if arg is None or arg.get("kind") != "string_literal":
                raise Refusal("REPAIR_ANNOTATION_VALUE_NOT_LITERAL", "%s: @%s on %s#%s has %s; only a string literal is rewritten, an expression built otherwise is never guessed at"
                              % (where, s["annotation"]["name"], s["type"], s["member"], "no %s" % attr if arg is None else "the %s %r" % (attr, arg.get("source"))))
            return str(arg["value"])

        src_sites, _ = self._sites(self.copy, roots, ann, attr)
        src_rows = sorted([{"path": s["path"], "type": s["type"], "member": s["member"], "member_kind": s["member_kind"],
                            "params": s["params"], "expression": expr_of(s, "frozen source")} for s in src_sites],
                          key=lambda r: json.dumps(r, sort_keys=True))
        appl = t.get("applicability") or {}
        observed = digest(src_rows)
        row["applicability"] = {"expected": appl.get("structure_sha256"), "observed": observed, "sites": len(src_rows)}
        if observed != appl.get("structure_sha256") or len(src_rows) != int(appl.get("sites", -1)):
            raise Refusal("REPAIR_NOT_APPLICABLE", "the frozen source carries %d @%s site(s) with structure %s; the decision was made for %s site(s) with %s"
                          % (len(src_rows), ann.rsplit(".", 1)[-1], observed[:12], appl.get("sites"), str(appl.get("structure_sha256") or "")[:12]))
        dst_sites, files = self._sites(self.root, roots, ann, attr)

        def key(s: dict) -> tuple:
            return (s["path"], s["type"], s["member_kind"], s["member"])

        expected: dict[tuple, list[str]] = {}
        for r in src_rows:
            expected.setdefault((r["path"], r["type"], r["member_kind"], r["member"]), []).append(r["expression"])
        edits: dict[str, list[tuple[int, int, str]]] = {}
        applied = already = 0
        symbols: set[str] = set()
        groups: dict[tuple, list[dict]] = {}
        for s in dst_sites:
            groups.setdefault(key(s), []).append(s)
        for k in sorted(set(expected) | set(groups)):
            want = list(expected.get(k, []))
            have = groups.get(k, [])
            pending = []
            for s in have:
                v = expr_of(s, "destination")
                orig = v[len(prefix):len(v) - len(suffix)] if (v.startswith(prefix) and v.endswith(suffix) and len(v) >= len(prefix) + len(suffix)) else None
                if orig is not None and orig in want:
                    want.remove(orig)
                    already += 1
                    continue
                pending.append((s, v))
            for s, v in pending:
                if v not in want:
                    raise Refusal("REPAIR_SITE_MISMATCH", "%s %s#%s carries @%s(%r), which is neither a source expression of that declaration nor its decided rewrite"
                                  % (k[0], k[1], k[3] or "<type>", s["annotation"]["name"], v))
                want.remove(v)
                edits.setdefault(s["path"], []).append((int(s["arg"]["start"]), int(s["arg"]["end"]), java_string_literal(prefix + v + suffix)))
                applied += 1
            if want:
                raise Refusal("REPAIR_SITE_MISMATCH", "%s %s#%s is missing @%s site(s) the source declares: %s" % (k[0], k[1], k[3] or "<type>", ann.rsplit(".", 1)[-1], want))
            symbols.add("%s#%s" % (k[1], k[3]) if k[3] else k[1])
        paths = sorted({k[0] for k in expected})
        row["files"] = paths
        row["symbols"] = sorted(symbols)
        row["inputs"] = {p: _file_sha(self.root / p) for p in paths}
        row["details"] = {"annotation": ann, "attribute": attr, "template": template, "sites": len(src_rows), "rewritten": applied, "already": already}
        self._write_java(edits)
        row["outputs"] = {p: _file_sha(self.root / p) for p in paths}
        return APPLIED if applied else ALREADY

    def _write_java(self, edits: dict[str, list[tuple[int, int, str]]]) -> None:
        originals: dict[str, str] = {}
        for rel, es in sorted(edits.items()):
            p = self.root / rel
            text = p.read_text(encoding="utf-8")
            originals[rel] = text
            p.write_text(splice(text, es), encoding="utf-8")
        if not originals:
            return
        after = self.java.files(self.root, sorted(originals))
        broke = [r for r, f in after.items() if f.get("parse_errors")]
        if broke:
            for rel, text in originals.items():
                (self.root / rel).write_text(text, encoding="utf-8")
            raise Refusal("REPAIR_EDIT_UNPARSEABLE", "the edit left %s unparseable; every file was restored" % ", ".join(broke))

    @staticmethod
    def _member_names(t: dict) -> tuple[str, str, str, str, list[str]]:
        tfqn = str(t["type"])
        member = str(t.get("member") or "")
        mkind = str(t.get("member_kind") or ("field" if member else "type"))
        root_dir = str(t.get("root") or "src/main/java")
        rel = "%s/%s.java" % (root_dir, tfqn.replace(".", "/"))
        return tfqn, member, mkind, rel, [root_dir]

    def _member_target(self, base: Path, t: dict) -> tuple[dict, dict, dict]:
        tfqn, member, mkind, rel, _roots = self._member_names(t)
        f = self.java.files(base, [rel]).get(rel) or {}
        if not f.get("exists"):
            raise Refusal("REPAIR_TARGET_MISSING", "%s is not in %s" % (rel, "the frozen source" if base == self.copy else "the destination"))
        if f.get("parse_errors"):
            raise Refusal("REPAIR_JAVA_UNPARSEABLE", "%s does not parse; it is not edited" % rel)
        ty = next((x for x in f.get("types") or [] if x["fqn"] == tfqn), None)
        if ty is None:
            raise Refusal("REPAIR_TARGET_MISSING", "%s declares no type %s" % (rel, tfqn))
        if mkind == "type":
            return f, ty, ty
        m = [x for x in ty.get("members") or [] if x["kind"] == mkind and x["name"] == member]
        if len(m) != 1:
            raise Refusal("REPAIR_TARGET_MISSING", "%s declares %d %s(s) named %s" % (tfqn, len(m), mkind, member))
        return f, ty, m[0]

    def member_structure(self, t: dict) -> str:
        """The applicable source structure of one member annotation: the
        declaration in the FROZEN source, its type, and the annotations it
        already carries (other than the decided one)."""
        tfqn, member, mkind, _rel_path, roots = self._member_names(t)
        ann = str(t["annotation"])
        sf, sty, sm = self._member_target(self.copy, t)
        return digest({"type": tfqn, "kind": sty["kind"], "member_kind": mkind, "member": member,
                       "member_type": sm.get("type") if mkind != "type" else None,
                       "annotations": sorted(a["name"] for a in sm.get("annotations") or []
                                             if resolve_annotation(a["name"], sf, ann, self.copy, roots) != "yes")})

    def java_member_annotation(self, t: dict, row: dict) -> str:
        tfqn, member, _mkind, rel, roots = self._member_names(t)
        ann = str(t["annotation"])
        text = str(t["text"]).strip()
        imports = [str(i) for i in t.get("imports") or []]
        if not text.startswith("@"):
            raise Refusal("REPAIR_MANIFEST_INVALID", "%s: the annotation text must start with @" % t["id"])
        observed = self.member_structure(t)
        want = (t.get("applicability") or {}).get("structure_sha256")
        row["applicability"] = {"expected": want, "observed": observed}
        if observed != want:
            raise Refusal("REPAIR_NOT_APPLICABLE", "%s#%s in the frozen source has structure %s; the decision was made for %s"
                          % (tfqn, member or "<type>", observed[:12], str(want or "")[:12]))
        f, _ty, m = self._member_target(self.root, t)
        row["files"] = [rel]
        row["symbols"] = ["%s#%s %s" % (tfqn, member, text.split("(", 1)[0]) if member else "%s %s" % (tfqn, text.split("(", 1)[0])]
        row["inputs"] = {rel: _file_sha(self.root / rel)}
        present = [a for a in m.get("annotations") or [] if resolve_annotation(a["name"], f, ann, self.root, roots) != "no"]
        for a in present:
            if resolve_annotation(a["name"], f, ann, self.root, roots) == "unresolved":
                raise Refusal("REPAIR_ANNOTATION_UNRESOLVED", "@%s on %s#%s cannot be told apart from %s" % (a["name"], tfqn, member, ann))
        edits: list[tuple[int, int, str]] = []
        status = ALREADY
        src_text = (self.root / rel).read_text(encoding="utf-8")
        if present:
            if len(present) > 1 or " ".join(present[0]["source"].split()) != " ".join(text.split()):
                raise Refusal("REPAIR_ANNOTATION_CONFLICT", "%s#%s already carries %s, not the decided %s"
                              % (tfqn, member or "<type>", " ".join(a["source"] for a in present), text))
        else:
            anns = m.get("annotations") or []
            if anns:
                last = anns[-1]
                indent = _indent_at(src_text, int(last["start"]))
                edits.append((int(last["end"]), int(last["end"]), "\n" + indent + text))
            else:
                start = int(m.get("modifiers_start", -1))
                if start < 0:
                    start = int(m.get("start"))
                indent = _indent_at(src_text, start)
                edits.append((start, start, text + "\n" + indent))
            status = APPLIED
        pkg = str(f.get("package") or "")
        singles = {i["name"] for i in f.get("imports") or [] if not i["static"] and not i["on_demand"]}
        single_simple = {n.rsplit(".", 1)[-1]: n for n in singles}
        demand = {i["name"] for i in f.get("imports") or [] if not i["static"] and i["on_demand"]}
        declared = {x["simple"]: x["fqn"] for x in f.get("types") or []}
        add: list[str] = []
        for imp in imports:
            simple, ipkg = imp.rsplit(".", 1)[-1], imp.rsplit(".", 1)[0]
            if imp in singles or ipkg in demand or ipkg == pkg:
                continue
            if simple in single_simple and single_simple[simple] != imp:
                raise Refusal("REPAIR_IMPORT_CONFLICT", "%s already imports %s; %s cannot be imported beside it" % (rel, single_simple[simple], imp))
            if simple in declared and declared[simple] != imp:
                raise Refusal("REPAIR_IMPORT_CONFLICT", "%s declares its own %s; %s cannot be imported" % (rel, simple, imp))
            add.append(imp)
        if add:
            imps = f.get("imports") or []
            lines = "".join("\nimport %s;" % i for i in sorted(add))
            if imps:
                at = max(int(i["end"]) for i in imps)
                edits.append((at, at, lines))
            elif int(f.get("package_end", -1)) >= 0:
                at = int(f["package_end"])
                edits.append((at, at, "\n" + lines))
            else:
                edits.append((0, 0, lines.lstrip("\n") + "\n\n"))
            status = APPLIED
        self._write_java({rel: edits} if edits else {})
        row["details"] = {"annotation": ann, "text": text, "imports_added": sorted(add)}
        row["outputs"] = {rel: _file_sha(self.root / rel)}
        return status

    def pom_dependency(self, t: dict, row: dict) -> str:
        g, a = str(t["groupId"]), str(t["artifactId"])
        ga = "%s:%s" % (g, a)
        want = {"version": str(t.get("version") or ""), "scope": str(t.get("scope") or "compile"),
                "type": str(t.get("type") or "jar"), "classifier": str(t.get("classifier") or "")}
        pom = self.root / "pom.xml"
        row["files"] = ["pom.xml"]
        row["symbols"] = ["dependency %s" % ga]
        row["inputs"] = {"pom.xml": _file_sha(pom)}
        row["applicability"] = {"expected": None, "observed": None}
        tree, project, ns = parse_pom(pom)
        deps = project.find(_q(ns, "dependencies"))
        found = []
        for d in (deps.findall(_q(ns, "dependency")) if deps is not None else []):
            if _txt(d, ns, "groupId") == g and _txt(d, ns, "artifactId") == a:
                found.append({"version": _txt(d, ns, "version"), "scope": _txt(d, ns, "scope") or "compile",
                              "type": _txt(d, ns, "type") or "jar", "classifier": _txt(d, ns, "classifier")})
        row["details"] = {"dependency": dict(want, groupId=g, artifactId=a)}
        if found:
            if found == [want]:
                row["outputs"] = {"pom.xml": _file_sha(pom)}
                return ALREADY
            raise Refusal("REPAIR_DEPENDENCY_CONFLICT", "%s is already declared as %s; the decision is %s" % (ga, found, want))
        if not want["version"]:
            probe = load_json(self.root / BOM_MANAGED) if (self.root / BOM_MANAGED).is_file() else None
            if probe is None or ga not in set(probe.get("managed") or []):
                raise Refusal("REPAIR_DEPENDENCY_UNMANAGED", "%s carries no version and %s" % (ga, "the platform BOM probe does not list it" if probe else "no BOM probe (%s) shows the platform manages it" % BOM_MANAGED))
        if deps is None:
            deps = ET.SubElement(project, _q(ns, "dependencies"))
        d = ET.SubElement(deps, _q(ns, "dependency"))
        for tag in ("groupId", "artifactId"):
            ET.SubElement(d, _q(ns, tag)).text = g if tag == "groupId" else a
        if want["version"]:
            ET.SubElement(d, _q(ns, "version")).text = want["version"]
        if want["type"] != "jar":
            ET.SubElement(d, _q(ns, "type")).text = want["type"]
        if want["classifier"]:
            ET.SubElement(d, _q(ns, "classifier")).text = want["classifier"]
        if want["scope"] != "compile":
            ET.SubElement(d, _q(ns, "scope")).text = want["scope"]
        write_pom(tree, pom)
        row["outputs"] = {"pom.xml": _file_sha(pom)}
        return APPLIED

    def property(self, t: dict, row: dict) -> str:
        rel = _rel(t.get("file") or "src/main/resources/application.properties")
        key, value = str(t["key"]), str(t["value"])
        if not _simple_token(key) or key.startswith("%") or any(c in value for c in "\n\r\\"):
            raise Refusal("REPAIR_MANIFEST_INVALID", "%s: a property row needs a plain key and a single-line value" % t["id"])
        row["files"] = [rel]
        row["symbols"] = ["property %s" % key]
        src = self.copy / rel
        src_text = src.read_text(encoding="utf-8", errors="replace") if src.is_file() else ""
        src_vals = [v for k, v in properties_entries(src_text) if k == key]
        appl = t.get("applicability") or {}
        row["applicability"] = {"expected": appl.get("source_value"), "observed": src_vals[-1] if src_vals else None}
        if "source_value" in appl and (not src_vals or src_vals[-1].strip() != str(appl["source_value"])):
            raise Refusal("REPAIR_NOT_APPLICABLE", "%s: the frozen source sets %s to %s, the decision was made for %r"
                          % (rel, key, src_vals[-1] if src_vals else "(nothing)", appl["source_value"]))
        p = self.root / rel
        text = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
        row["inputs"] = {rel: _file_sha(p)}
        existing = [(k, v) for k, v in properties_entries(text) if k == key or (k.startswith("%") and k.split(".", 1)[-1] == key and "." in k)]
        bad = [(k, v) for k, v in existing if v.strip() != value]
        if bad:
            raise Refusal("REPAIR_PROPERTY_CONFLICT", "%s already sets %s; the decision is %s=%s and an incompatible value is never overwritten"
                          % (rel, ", ".join("%s=%s" % kv for kv in bad), key, value))
        row["details"] = {"key": key, "value": value}
        if any(k == key for k, _v in existing):
            row["outputs"] = {rel: _file_sha(p)}
            return ALREADY
        p.parent.mkdir(parents=True, exist_ok=True)
        lead = "" if not text or text.endswith("\n") else "\n"
        p.write_text(text + lead + "# decided repair %s (%s)\n%s=%s\n" % (t["id"], t.get("adr"), key, value), encoding="utf-8")
        row["outputs"] = {rel: _file_sha(p)}
        return APPLIED

    def pom_retire_execution(self, t: dict, row: dict) -> str:
        ga = "%s:%s" % (t["plugin"]["groupId"], t["plugin"]["artifactId"])
        ex_want = t["execution"]
        want_id, want_goals = str(ex_want["id"]), [str(g) for g in ex_want["goals"]]
        want_phase = ex_want.get("phase")
        want_conf = t.get("configuration")
        preserve = [str(g) for g in t.get("preserve_goals") or []]
        row["files"] = ["pom.xml"]
        row["symbols"] = ["plugin %s execution %s" % (ga, want_id)]
        _st, sproj, sns = parse_pom(self.copy / "pom.xml")
        s_struct = execution_structure(sproj, sns, t)
        observed = digest(s_struct)
        want_sha = (t.get("applicability") or {}).get("structure_sha256")
        row["applicability"] = {"expected": want_sha, "observed": observed}
        if observed != want_sha:
            raise Refusal("REPAIR_NOT_APPLICABLE", "the frozen source declares %s as %s (structure %s); the decision was made for %s. A retirement decided for one configuration is never applied to another"
                          % (ga, json.dumps(s_struct["declarations"])[:300], observed[:12], str(want_sha or "")[:12]))
        pom = self.root / "pom.xml"
        row["inputs"] = {"pom.xml": _file_sha(pom)}
        tree, project, ns = parse_pom(pom)
        sites = plugin_sites(project, ns, ga)
        thresholds = {"plugin": ga, "execution": want_id, "goals": want_goals, "phase": want_phase, "configuration": want_conf}
        row["details"] = {"retired": thresholds, "preserved_goals": preserve}
        main = [s for s in sites if s[0] == "build"]
        if len(main) != 1:
            raise Refusal("REPAIR_EXECUTION_MISMATCH", "expected exactly one %s under build/plugins, found %d" % (ga, len(main)))
        plugin = main[0][2]
        conf = plugin.find(_q(ns, "configuration"))
        if conf is not None and isinstance(readable(conf), dict) and any(k in readable(conf) for k in (want_conf or {})):
            raise Refusal("REPAIR_EXECUTION_MISMATCH", "%s carries %s at plugin level, outside the decided execution" % (ga, sorted(set(readable(conf)) & set(want_conf or {}))))
        target = [(el, e) for el, e in executions(plugin, ns) if e["id"] == want_id]
        stray = []
        for where, _parent, p in sites:
            for el, e in executions(p, ns):
                if (p is plugin and e["id"] == want_id):
                    continue
                if set(e["goals"]) & set(want_goals):
                    stray.append("%s execution %s %s" % (where, e["id"], e["goals"]))
        if stray:
            raise Refusal("REPAIR_EXECUTION_MISMATCH", "the retired goal(s) %s are also bound elsewhere (%s); only the decided execution is retired, nothing broader"
                          % (want_goals, "; ".join(stray)))
        if len(target) > 1:
            raise Refusal("REPAIR_EXECUTION_MISMATCH", "%s declares %d executions with id %s" % (ga, len(target), want_id))
        status = ALREADY
        if target:
            el, e = target[0]
            got = {"goals": e["goals"], "phase": e["phase"], "configuration": e["configuration"]}
            exp = {"goals": want_goals, "phase": want_phase, "configuration": want_conf}
            if got != exp:
                raise Refusal("REPAIR_EXECUTION_MISMATCH", "%s execution %s is %s; the decision retires exactly %s" % (ga, want_id, json.dumps(got), json.dumps(exp)))
            plugin.find(_q(ns, "executions")).remove(el)
            status = APPLIED
        remaining = [g for _el, e in executions(plugin, ns) for g in e["goals"]]
        missing = [g for g in preserve if g not in remaining]
        if missing:
            raise Refusal("REPAIR_EXECUTION_MISMATCH", "%s would be left without %s; the decision keeps them" % (ga, missing))
        if status == APPLIED:
            write_pom(tree, pom)
        self.coverage.append({"id": t["id"], "adr": t.get("adr"), "plugin": ga, "execution": want_id,
                              "retired_thresholds": want_conf, "status": "retired-not-achieved",
                              "note": str(t.get("coverage_note") or "retirement is not achievement of the former thresholds; restoring them is an explicit follow-up")})
        row["outputs"] = {"pom.xml": _file_sha(pom)}
        return status

    # -- driver -----------------------------------------------------------
    def prefetch(self) -> None:
        """One compiler run per tree for every source root the manifest
        reads, instead of one per question."""
        roots: set[str] = set()
        for t in self.manifest.get("transformations") or []:
            if t.get("kind") == "java_annotation_expression":
                roots.update(str(r) for r in (t.get("roots") or ["src/main/java"]))
            elif t.get("kind") == "java_member_annotation":
                roots.add(str(t.get("root") or "src/main/java"))
        if not roots:
            return
        try:
            for base in (self.copy, self.root):
                self.java.files(base, [r for r in java_files(base, sorted(roots)) if r not in self.retired])
        except Refusal:
            pass  # each transformation asks again and refuses on its own row

    def run(self) -> tuple[list[dict], list[dict]]:
        rows: list[dict] = []
        blocks: list[dict] = []
        self.prefetch()
        for t in self.manifest.get("transformations") or []:
            row: dict[str, Any] = {"id": str(t.get("id") or ""), "adr": str(t.get("adr") or ""), "kind": str(t.get("kind") or ""),
                                   "implementation": {"name": ENGINE_NAME, "version": ENGINE_VERSION},
                                   "applicability": {}, "inputs": {}, "outputs": {}, "files": [], "symbols": [], "refusal": None}
            try:
                if not row["id"] or row["kind"] not in KINDS:
                    raise Refusal("REPAIR_MANIFEST_INVALID", "transformation %r has kind %r (known: %s)" % (row["id"], row["kind"], ", ".join(KINDS)))
                if row["adr"] not in self.accepted:
                    raise Refusal("REPAIR_ADR_NOT_ACCEPTED", "%s cites %r, which is not an accepted ADR" % (row["id"], row["adr"]))
                applies = [str(a) for a in self.decision.get("applies") or []]
                if applies and row["adr"] not in applies:
                    raise Refusal("REPAIR_ADR_NOT_ACCEPTED", "%s cites %s, which decisions.yaml decided_repairs.applies does not name" % (row["id"], row["adr"]))
                row["status"] = getattr(self, row["kind"])(t, row)
            except Refusal as r:
                row["status"] = REFUSED
                row["refusal"] = {"class": r.cls, "detail": r.detail}
                blocks.append({"class": r.cls, "subject": row["id"], "detail": "%s (%s): %s" % (row["id"], row["adr"], r.detail)})
            rows.append(row)
        return rows, blocks


def tool_digests() -> dict[str, str]:
    return {"engine_sha256": sha256_file(Path(__file__)), "java_tool_sha256": _file_sha(TOOL)}


def _pom_profiles(pom: Path) -> list[str]:
    try:
        _t, project, ns = parse_pom(pom)
    except Refusal:
        return []
    return [_txt(p, ns, "id") for p in project.findall("%s/%s" % (_q(ns, "profiles"), _q(ns, "profile"))) if _txt(p, ns, "id")]


def verify_effective(root: Path, rows: list[dict], manifest: dict, decisions_doc: dict) -> tuple[dict, list[dict]]:
    """ADR-019 §3: the retirement is verified on the EFFECTIVE Maven model, under
    the decided build profiles (.mvn/maven.config carries them) and under
    every Maven profile the pom declares, one at a time."""
    retire = {t["id"]: t for t in manifest.get("transformations") or [] if t.get("kind") == "pom_retire_execution"}
    todo = [r for r in rows if r["id"] in retire and r["status"] in (APPLIED, ALREADY)]
    if not todo:
        return {"checked": False, "reason": "no retirement to verify"}, []
    mvn = shutil.which("mvn")
    profiles = [""] + _pom_profiles(root / "pom.xml")
    decided = [str(p) for p in (build_profiles(decisions_doc).get("active") or [])] if decisions_doc else []
    result: dict[str, Any] = {"checked": True, "tool": mvn or "", "decided_build_profiles": decided, "maven_profiles": profiles, "runs": []}
    blocks: list[dict] = []
    if not mvn:
        result["checked"] = False
        blocks.append({"class": "REPAIR_EFFECTIVE_UNVERIFIED", "subject": "effective-pom",
                       "detail": "mvn is not on PATH, so the retirement cannot be verified on the effective build configuration"})
        return result, blocks
    for prof in profiles:
        with tempfile.TemporaryDirectory(prefix="effective-pom-") as td:
            out = Path(td) / "effective.xml"
            argv = [mvn, "-B", "-q", "help:effective-pom", "-Doutput=%s" % out]
            if decided:
                argv.append("-Dquarkus.profile=%s" % ",".join(decided))
            if prof:
                argv.append("-P%s" % prof)
            p = subprocess.run(argv, cwd=str(root), capture_output=True, text=True, timeout=900)
            run = {"maven_profile": prof or "(default)", "rc": p.returncode}
            if p.returncode != 0 or not out.is_file():
                run["error"] = (p.stdout + p.stderr)[-300:]
                result["runs"].append(run)
                blocks.append({"class": "REPAIR_EFFECTIVE_UNVERIFIED", "subject": "effective-pom",
                               "detail": "mvn help:effective-pom %s failed (rc %s): %s" % (prof or "(default)", p.returncode, run["error"][-160:])})
                continue
            _tree, project, ns = parse_pom(out)
        for r in todo:
            t = retire[r["id"]]
            ga = "%s:%s" % (t["plugin"]["groupId"], t["plugin"]["artifactId"])
            sites = [s for s in plugin_sites(project, ns, ga) if s[0] == "build"]
            goals = [g for _w, _pp, pl in sites for _el, e in executions(pl, ns) for g in e["goals"]]
            bad = [g for g in t["execution"]["goals"] if g in goals]
            lost = [g for g in t.get("preserve_goals") or [] if g not in goals]
            run.setdefault("plugins", []).append({"plugin": ga, "goals": goals, "retired_present": bad, "preserved_missing": lost})
            if not sites or bad or lost:
                blocks.append({"class": "REPAIR_EFFECTIVE_MISMATCH", "subject": r["id"],
                               "detail": "the effective build (%s) %s" % (prof or "default profile",
                                                                        "has no %s" % ga if not sites else "still binds %s" % bad if bad else "lost %s" % lost)})
        result["runs"].append(run)
    return result, blocks


def load_manifest(root: Path, sec: dict) -> tuple[Path, dict]:
    mp = root / _rel(sec.get("manifest") or "")
    if not mp.is_file():
        raise Refusal("REPAIR_MANIFEST_MISSING", "%s is absent" % sec.get("manifest"))
    if sha256_file(mp) != str(sec.get("manifest_sha256") or ""):
        raise Refusal("REPAIR_MANIFEST_DIGEST", "%s is %s; decisions.yaml pins %s" % (sec.get("manifest"), sha256_file(mp)[:12], str(sec.get("manifest_sha256") or "")[:12]))
    try:
        doc = load_json(mp)
    except ValueError as exc:
        raise Refusal("REPAIR_MANIFEST_INVALID", "%s: %s" % (sec.get("manifest"), exc))
    if doc.get("schema") != MANIFEST_SCHEMA:
        raise Refusal("REPAIR_MANIFEST_INVALID", "%s is not %s" % (sec.get("manifest"), MANIFEST_SCHEMA))
    schema_p = root / SCHEMAS_DIR / "decided-repairs-manifest.schema.json"
    if not schema_p.is_file():
        schema_p = _hermes_root() / "planning" / "schemas" / "decided-repairs-manifest.schema.json"
    errors = validate(doc, load_schema(schema_p))
    if errors:
        raise Refusal("REPAIR_MANIFEST_INVALID", "%s: %s" % (sec.get("manifest"), "; ".join(errors[:5])))
    ids = [str(t.get("id")) for t in doc.get("transformations") or []]
    if len(ids) != len(set(ids)):
        raise Refusal("REPAIR_MANIFEST_INVALID", "transformation ids repeat in %s" % sec.get("manifest"))
    return mp, doc


def inventory(rows: list[dict], previous: dict | None, run_no: int) -> list[dict]:
    prev = {str(i.get("id")): i for i in ((previous or {}).get("inventory") or [])}
    out = []
    for r in rows:
        p = prev.get(r["id"]) or {}
        first = p.get("first_applied_run")
        if first is None and r["status"] == APPLIED:
            first = run_no
        out.append({"id": r["id"], "adr": r["adr"], "kind": r["kind"], "files": r["files"], "symbols": r["symbols"],
                    "status": r["status"], "first_applied_run": first})
    return out


def apply_decided_repairs(root: Path, copy: Path, decisions_doc: dict | None, *, source_digest: str = "",
                          verify: bool = False) -> tuple[dict | None, list[dict]]:
    """Apply the decided repairs; write the receipt; return (receipt, blocks).
    (None, []) when decisions.yaml decides none."""
    root = Path(root)
    sec = section(decisions_doc)
    if not sec:
        return None, []
    receipt_p = root / DECIDED_REPAIRS_RECEIPT
    previous = load_json(receipt_p) if receipt_p.is_file() else None
    run_no = len((previous or {}).get("runs") or []) + 1
    rows: list[dict] = []
    blocks: list[dict] = []
    manifest: dict = {}
    mp: Path | None = None
    engine: Engine | None = None
    try:
        mp, manifest = load_manifest(root, sec)
        engine = Engine(root, Path(copy), mp, manifest, accepted_adrs(decisions_doc or {}), sec,
                        set(retired_sources(decisions_doc or {})))
        rows, blocks = engine.run()
    except Refusal as r:
        blocks.append({"class": r.cls, "subject": str(sec.get("manifest") or "decided_repairs"), "detail": r.detail})
    finally:
        if engine is not None:
            engine.java.close()
    effective: dict = {"checked": False, "reason": "not requested"}
    if verify and manifest:
        effective, eblocks = verify_effective(root, rows, manifest, decisions_doc or {})
        blocks.extend(eblocks)
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in (APPLIED, ALREADY, REFUSED)}
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "producer": ENGINE_NAME,
        "status": "ok" if not blocks else "refused",
        "classification": CLASSIFICATION,
        "decision": {"adr": str(sec.get("adr") or ""), "applies": [str(a) for a in sec.get("applies") or []],
                     "manifest": str(sec.get("manifest") or ""), "manifest_sha256": str(sec.get("manifest_sha256") or ""),
                     "specimen": str(manifest.get("specimen") or ""), "manifest_version": str(manifest.get("manifest_version") or "")},
        "implementation": dict({"name": ENGINE_NAME, "version": ENGINE_VERSION}, **tool_digests()),
        "source": {"analysis_copy": str(copy), "source_digest": source_digest},
        "rows": rows,
        "counts": counts,
        "inventory": inventory(rows, previous, run_no),
        "review_records": sorted((engine.review_results.values() if engine else []), key=lambda r: r["id"]),
        "coverage_account": {"retired_thresholds": engine.coverage if engine else []},
        "obligations": sorted(set((engine.obligations if engine else []) + [str(o) for o in manifest.get("standing_obligations") or []])),
        "effective_configuration": effective,
        "blocks": blocks,
        "runs": list((previous or {}).get("runs") or []) + [{
            "run": run_no, "at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "manifest_sha256": str(sec.get("manifest_sha256") or ""), "counts": counts, "status": "ok" if not blocks else "refused"}],
    }
    write_canonical(receipt_p, receipt)
    return receipt, blocks


def finalize_effective(root: Path, receipt: dict | None, decisions_doc: dict | None) -> list[dict]:
    """Run after the producer's LAST pom write: verify the retirements on the
    effective build model and fold the answer into the receipt."""
    if not receipt:
        return []
    root = Path(root)
    sec = section(decisions_doc)
    try:
        _mp, manifest = load_manifest(root, sec)
    except Refusal:
        return []
    effective, blocks = verify_effective(root, receipt.get("rows") or [], manifest, decisions_doc or {})
    receipt["effective_configuration"] = effective
    receipt["blocks"] = list(receipt.get("blocks") or []) + blocks
    receipt["status"] = "ok" if not receipt["blocks"] else "refused"
    if receipt.get("runs"):
        receipt["runs"][-1]["status"] = receipt["status"]
    write_canonical(root / DECIDED_REPAIRS_RECEIPT, receipt)
    return blocks


def bootstrap_record(root: Path, receipt: dict | None) -> dict:
    """What the bootstrap receipt carries about this step. The key is present
    on every bootstrap this engine ran in, so admission can tell a run that
    applied nothing because nothing was decided from a run that predates the
    capability."""
    if receipt is None:
        return {"declared": False}
    p = Path(root) / DECIDED_REPAIRS_RECEIPT
    return {"declared": True, "classification": receipt.get("classification"), "status": receipt.get("status"),
            "receipt": str(DECIDED_REPAIRS_RECEIPT), "receipt_sha256": sha256_file(p) if p.is_file() else "",
            "manifest_sha256": (receipt.get("decision") or {}).get("manifest_sha256"), "counts": receipt.get("counts"),
            "implementation": receipt.get("implementation")}


def describe_source(root: Path, copy: Path, manifest: dict, retired: set[str] | None = None) -> list[dict]:
    """The applicability digests the frozen source yields for each
    transformation (authoring aid: a manifest author reads these, checks them
    against the decision, and writes them into the manifest)."""
    out = []
    eng = Engine(root, copy, Path("-"), manifest, set(), {}, set(retired or ()))
    try:
        for t in manifest.get("transformations") or []:
            kind = t.get("kind")
            row: dict[str, Any] = {"id": t.get("id"), "kind": kind}
            try:
                if kind == "java_annotation_expression":
                    roots = [str(r) for r in (t.get("roots") or ["src/main/java"])]
                    sites, _ = eng._sites(copy, roots, str(t["annotation"]), str(t.get("attribute") or "value"))
                    rows = sorted([{"path": s["path"], "type": s["type"], "member": s["member"], "member_kind": s["member_kind"],
                                    "params": s["params"], "expression": (s["arg"] or {}).get("value")} for s in sites],
                                  key=lambda r: json.dumps(r, sort_keys=True))
                    row.update({"sites": len(rows), "structure_sha256": digest(rows)})
                elif kind == "java_member_annotation":
                    row["structure_sha256"] = eng.member_structure(t)
                elif kind == "pom_retire_execution":
                    _t, proj, ns = parse_pom(copy / "pom.xml")
                    s = execution_structure(proj, ns, t)
                    row.update({"structure_sha256": digest(s), "structure": s})
                elif kind == "replace_reviewed_file":
                    row["source_sha256"] = _file_sha(copy / _rel(t["path"]))
                elif kind == "property":
                    src = copy / _rel(t.get("file") or "src/main/resources/application.properties")
                    row["source_values"] = [v for k, v in (properties_entries(src.read_text(encoding="utf-8")) if src.is_file() else []) if k == t["key"]]
            except Refusal as r:
                row["refusal"] = "%s: %s" % (r.cls, r.detail)
            out.append(row)
    finally:
        eng.java.close()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--copy", default="", help="the frozen analysis copy (default: the freeze receipt's analysis_copy)")
    ap.add_argument("--describe-source", action="store_true", help="print the applicability each transformation observes in the frozen copy; writes nothing")
    ap.add_argument("--manifest", default="", help="with --describe-source: a manifest file to describe (default: the one decisions.yaml names)")
    ap.add_argument("--verify-effective", action="store_true", help="also verify retirements on mvn help:effective-pom")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    from planner.decisions import DecisionsError, load_decisions
    from planner.paths import producer_receipt

    copy = Path(args.copy).resolve() if args.copy else Path(str(load_json(producer_receipt(root, "freeze")).get("analysis_copy") or ""))
    if args.describe_source:
        mp = Path(args.manifest) if args.manifest else root / section(load_decisions(root))["manifest"]
        doc = load_decisions(root) if (root / "decisions.yaml").is_file() else {}
        print(json.dumps(describe_source(root, copy, load_json(mp), set(retired_sources(doc))), indent=2, sort_keys=True))
        return 0
    try:
        doc = load_decisions(root)
    except DecisionsError as exc:
        print("FAIL: DECISIONS_INVALID %s" % exc, file=sys.stderr)
        return 1
    # the harness-owned m4-parity block is comments plus a profile, and a DOM
    # pass drops comments: take it out first and write it back last, exactly
    # as the bootstrap producer does around its own pom passes
    gen = _hermes_root() / "skills" / "gates" / "generate-product-tests" / "scripts"
    if str(gen) not in sys.path:
        sys.path.insert(0, str(gen))
    import parity_pom

    had_block = parity_pom.strip_profile_block_file(root)
    try:
        receipt, blocks = apply_decided_repairs(root, copy, doc)
    finally:
        if had_block:
            parity_pom.ensure_pom_profile(root, parity_pom.DEFAULT_OUT, parity_pom.DEFAULT_RESOURCES)
    if args.verify_effective:
        blocks = blocks + finalize_effective(root, receipt, doc)
    if receipt is None:
        print("OK: no decided repairs in decisions.yaml")
        return 0
    for r in receipt["rows"]:
        print("  - %-15s %s %s" % (r["status"], r["id"], (r.get("refusal") or {}).get("class") or ""))
    if blocks:
        for b in blocks:
            print("  - %s %s: %s" % (b["class"], b["subject"], b["detail"]), file=sys.stderr)
        print("REFUSE: DECIDED_REPAIRS (%d block(s)) -> %s" % (len(blocks), DECIDED_REPAIRS_RECEIPT), file=sys.stderr)
        return 1
    print("OK: decided repairs %s -> %s" % (receipt["counts"], DECIDED_REPAIRS_RECEIPT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
