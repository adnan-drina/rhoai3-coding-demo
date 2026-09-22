"""The work list: the only plan (SAD v3 §5).

Recomputed by tools after every change and never by a model:

- MTA mandatory incidents (destination rescan when present, else the
  frozen-source obligations from the evidence bundle),
- compiler diagnostics (JDK compiler API over the destination),
- failing tests (surefire reports),
- runtime-parity mismatches (source oracles vs destination).

Every item has a file locus. Items cluster by file. Clusters are ordered
by a fixed key: build file, then configuration, then compile errors in
dependency order (leaf types first, from the JDK model), then remaining
incidents, then tests, then parity. The head cluster is the next card.

The progress measure is the tuple (mandatory incidents, compile errors,
failing tests). The compile slot is an *observed* diagnostic count: the
JDK collector already requests 10,000 errors and still reports one
diagnostic when several sibling files share the same checked-exception
defect. That count cannot establish that only one defect remains.
Acceptance requires a strictly smaller tuple and no new mandatory
obligation, *or* a typed gate outcome (package/boot passing). Disappearance
alone is never ACCEPTED: whether an issued compile failure is still reported
is asked of its identity without the line (file, member, call site, exception), and
when it is gone without the count falling the compiler's next report decides
-- another member of the card's sealed family CONTINUES the card (RETAIN),
anything else is a typed diagnosis (EXPOSED). The family itself is the sites
of one signature that ONE accepted step introduced (build_checked_family_scope).
Parity is measured by M4 and reported beside the tuple, never inside it: a
parity obligation carries ``gate: parity`` and the scenarios it is made of, the
acceptance path re-runs that comparison for those scenarios, and the step is
accepted when the composed receipt records them PASS (v9 card t_77cae2b2: the
CORS repair the brief asked for was REVERTED because [0,0,0] did not decrease
and nothing ever re-compared the scenario).

Measurement contract: every component is known only when its tool ran in
this verification and produced a report (verification/build/run.json);
a missing report never means success. Obligation identity is line-free
(rule, file, variables, message) so ordinary line movement is not a new
obligation; the line stays on the item for the brief.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any

from planner.canonical import canonical_bytes, digest, load_json, sha256_bytes, sha256_file, sort_unique
from planner.dest_model import (DestModelUnavailable, above_members, dest_model, diagnostic_identity, fields_of, member_ids, model_at_commit,  # noqa: E501
                                 site_for_diagnostic, site_signature, source_write_members as _model_writes, types_of, unhandled_sites)
from planner.paths import is_product_path, LOOP_ACCEPTED, VERIFY_DIR, CATALOGS_DIR, EVIDENCE_BUNDLE, STRUCTURE, TYPE_INVENTORY, LOOP_DEFERRED, LOOP_ISSUED, LOOP_STEPS, MTA_RESCAN_FINDINGS, PARITY_DIR, VERIFY_BOOT, VERIFY_DIAGNOSTICS, VERIFY_PACKAGE, VERIFY_RUN, VERIFY_SUREFIRE, WORKLIST
import response_adapters as _adapters  # noqa: E402  (.hermes/lib, beside this package)

SCHEMA = "rhoai3.worklist/v1"
KIND_RANK = {"build": 0, "config": 1, "compile": 2, "incident": 3, "test": 4, "parity": 5}
MEASURE_KEYS = ("mandatory_incidents", "compile_errors", "failing_tests")
BUILD_FILES = ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")
GLOBAL = "GLOBAL"
UNKNOWN_DEPTH = 10_000


# ---------------------------------------------------------------------------
# path classes
# ---------------------------------------------------------------------------


def path_class(path: str) -> str:
    p = path.replace("\\", "/")
    name = p.rsplit("/", 1)[-1]
    if name in BUILD_FILES or p.startswith(".mvn/"):
        return "build"
    if p.startswith(("src/main/resources/", "src/test/resources/")) and (name.endswith((".properties", ".yml", ".yaml"))):
        # configuration under src/test/resources is migration work like its
        # src/main twin (the Quarkus property names change for tests too);
        # only test *code* judges the migration and stays unwritable.
        # Measured live 2026-09-09 (pilot v5): admission blocked SCOPE_UNDERIVED on
        # src/test/resources/application.properties (Spring log-level keys).
        return "config"
    if p.startswith("src/test/"):
        return "test"
    return "source"


# ---------------------------------------------------------------------------
# harness-owned generated roots (ADR-015 / ADR-019)
# ---------------------------------------------------------------------------

GENERATOR_OWNER = "generate-product-tests"
_GENERATOR_DECLARATION = Path(__file__).resolve().parents[2] / "skills" / "gates" / GENERATOR_OWNER / "scripts" / "parity_pom.py"


def _generator_declaration() -> Any:
    """The generator's own module (parity_pom), or None when it cannot be read."""
    import importlib.util

    if not _GENERATOR_DECLARATION.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("_rhoai3_generator_declaration", _GENERATOR_DECLARATION)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001 -- an unreadable declaration declares nothing
        return None
    return mod


def harness_owned_roots(root: Path | None) -> dict[str, Any]:
    """Where the harness writes product-tree files no worker may touch.

    The generated product tests (ADR-015) live in their own source root, and
    ADR-015/ADR-019 give workers no test-source write authority. The roots are
    the GENERATOR's declaration (parity_pom.DEFAULT_OUT / DEFAULT_RESOURCES)
    plus whatever its manifest records it wrote (``out``, ``resources``, the
    pom profile's roots, every listed file) -- never a literal here."""
    roots: set[str] = set()
    files: set[str] = set()
    declared: list[str] = []
    mod = _generator_declaration()
    manifest_rel = ""
    if mod is not None:
        for name in ("DEFAULT_OUT", "DEFAULT_RESOURCES"):
            v = str(getattr(mod, name, "") or "").strip().strip("/")
            if v:
                roots.add(v)
        manifest_rel = str(getattr(mod, "GENERATED_MANIFEST", "") or "")
        declared.append(_GENERATOR_DECLARATION.relative_to(_GENERATOR_DECLARATION.parents[4]).as_posix())
    if root is not None and manifest_rel and (Path(root) / manifest_rel).is_file():
        try:
            man = load_json(Path(root) / manifest_rel)
        except (OSError, ValueError):
            man = {}
        if isinstance(man, dict):
            prof = man.get("pom_profile") if isinstance(man.get("pom_profile"), dict) else {}
            for v in (man.get("out"), man.get("resources"), prof.get("test_source"), prof.get("test_resources")):
                v = str(v or "").strip().strip("/")
                if v:
                    roots.add(v)
            for f in man.get("files") or []:
                path = str((f or {}).get("path") or "") if isinstance(f, dict) else ""
                if path:
                    files.add(path)
            declared.append(manifest_rel)
    return {"roots": sorted(roots), "files": sorted(files), "owner": GENERATOR_OWNER, "declared_by": declared}


def is_harness_owned(path: str, owned: dict[str, Any]) -> bool:
    p = str(path or "").replace("\\", "/").lstrip("/")
    if not p:
        return False
    return p in set(owned.get("files") or []) or any(p == r or p.startswith(r + "/") for r in owned.get("roots") or [])


def _incident_kind(path: str) -> str:
    cls = path_class(path)
    if cls == "build":
        return "build"
    if cls == "config":
        return "config"
    return "incident"


# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------


def _locus_path(uri: str, roots: list[str]) -> str:
    p = str(uri or "")
    if p.startswith("file://"):
        p = p[len("file://"):]
    p = p.replace("\\", "/")
    for r in roots:
        r = r.replace("\\", "/").rstrip("/")
        if r and p.startswith(r + "/"):
            return p[len(r) + 1 :]
    for marker in ("/src/main/", "/src/test/", "/pom.xml"):
        i = p.find(marker)
        if i >= 0:
            return p[i + 1 :]
    return p.lstrip("/") if p else ""


def incidents_from_findings(findings: dict[str, Any], roots: list[str], canary_id: str) -> list[dict[str, Any]]:
    """Mandatory MTA incidents as items (content-addressed; nothing dropped)."""
    out: list[dict[str, Any]] = []
    violations = findings.get("violations") if isinstance(findings.get("violations"), dict) else {}
    for rid in sorted(violations):
        v = violations[rid]
        if not isinstance(v, dict):
            continue
        rule_id = str(v.get("ruleID") or rid)
        if canary_id and rule_id == canary_id:
            continue
        category = str(v.get("category") or "potential").lower()
        for inc in v.get("incidents") if isinstance(v.get("incidents"), list) else []:
            if not isinstance(inc, dict):
                inc = {"message": str(inc)}
            path = _locus_path(str(inc.get("uri") or ""), roots) or GLOBAL
            if path != GLOBAL and not is_product_path(path):
                continue  # harness state or the frozen legacy copy under .derived/: never a card
            try:
                line = int(inc.get("lineNumber") or 0)
            except (TypeError, ValueError):
                line = 0
            message = str(inc.get("message") or "")
            variables = inc.get("variables") if isinstance(inc.get("variables"), dict) else {}
            # line-free identity: an obligation that moves down a line is the same obligation
            ident = sha256_bytes(canonical_bytes({"rule": rule_id, "path": path, "variables": variables, "message": message}))[:16]
            out.append({
                "id": "inc:%s:%s" % (rule_id, ident),
                "source": "mta",
                "kind": _incident_kind(path) if path != GLOBAL else "build",
                "category": category,
                "path": path,
                "line": line,
                "rule_id": rule_id,
                "message_sha256": sha256_bytes(message.encode("utf-8")),
                "detail": message[:200],
            })
    return out


def pom_dependency_ids(root: Path) -> set[str]:
    """group:artifact of every declared dependency in the destination pom (no plugins, no management)."""
    p = Path(root) / "pom.xml"
    if not p.is_file():
        return set()
    try:
        tree = ET.parse(p)
    except ET.ParseError:
        return set()
    out: set[str] = set()
    for dep in tree.getroot().iter():
        tag = dep.tag.rsplit("}", 1)[-1]
        if tag != "dependency":
            continue
        g = a = ""
        for ch in dep:
            t = ch.tag.rsplit("}", 1)[-1]
            if t == "groupId":
                g = (ch.text or "").strip()
            elif t == "artifactId":
                a = (ch.text or "").strip()
        if g and a:
            out.add("%s:%s" % (g, a))
    return out


def apply_supersessions(items: list[dict[str, Any]], superseded: dict[str, dict[str, str]], waivers: list[dict[str, str]], present: set[str], *, platform: str = "") -> list[dict[str, Any]]:
    """Reclassify mandatory MTA incidents the platform supersedes (catalog, guarded
    by a present artifact) or an accepted ADR waives (decisions.not_applicable).
    Nothing is dropped: the item stays, with category superseded / waived and
    the authority that says so, and never counts as an obligation again."""
    for it in items:
        if it.get("source") != "mta" or it.get("category") != "mandatory":
            continue
        rid, path = str(it.get("rule_id") or ""), str(it.get("path") or "")
        sup = superseded.get(rid)
        if sup is not None and (not sup.get("requires_present") or sup["requires_present"] in present):
            it["category"] = "superseded"
            it["superseded_by"] = {"platform": platform, "requires_present": sup.get("requires_present", ""), "reason": sup.get("reason", "")}
            continue
        for w in waivers:
            if (w.get("item_id") and w["item_id"] == it.get("id")) or (w.get("rule_id") and w["rule_id"] == rid and (not w.get("path") or w["path"] == path)):
                it["category"] = "waived"
                it["waived_by"] = {"adr": w.get("adr", ""), "reason": w.get("reason", "")}
                break
    return items


def incidents_from_bundle(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ob in bundle.get("obligations") or []:
        path = str(ob["locus"]["path"])
        for k in range(int(ob.get("multiplicity") or 1)):
            oid = ob["id"] if k == 0 else "%s#%d" % (ob["id"], k)
            out.append({
                "id": oid,
                "source": "mta",
                "kind": _incident_kind(path) if path != GLOBAL else "build",
                "category": str(ob.get("category") or "potential"),
                "path": path,
                "line": int(ob["locus"].get("line") or 0),
                "rule_id": str(ob["rule_id"]),
                "message_sha256": str(ob.get("message_sha256") or ""),
                "detail": "",
            })
    return out


def compile_items(diags: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in diags.get("diagnostics") or []:
        if str(d.get("kind") or "").upper() != "ERROR":
            continue
        path = str(d.get("path") or "") or GLOBAL
        line = int(d.get("line") or 0)
        message = str(d.get("message") or "")
        ident = sha256_bytes(canonical_bytes({"path": path, "line": line, "code": d.get("code"), "message": message}))[:16]
        if path.startswith("target/generated-sources/"):
            # generated code is owned by its generator's configuration in the
            # pom: the item's locus is pom.xml (a build item), the generated
            # file and the compiler's words travel in the message
            out.append({"id": "err:%s" % ident, "source": "javac", "kind": "build", "category": "mandatory", "path": "pom.xml", "line": 0,
                        "rule_id": "GENERATED_SOURCE_ERROR", "message_sha256": sha256_bytes(message.encode("utf-8")),
                        "detail": ("%s:%d: %s" % (path, line, message))[:200], "message": ("%s:%d: %s" % (path, line, message))[:600], "generated_path": path})
            continue
        out.append({"id": "err:%s" % ident, "source": "javac", "kind": "build" if path == GLOBAL or path_class(path) == "build" else "compile", "category": "mandatory", "path": path, "line": line, "rule_id": str(d.get("code") or ""), "message_sha256": sha256_bytes(message.encode("utf-8")), "detail": message[:200], "message": message[:600]})
    if diags.get("build_unresolvable"):
        out.append({"id": "err:build-unresolvable", "source": "javac", "kind": "build", "category": "mandatory", "path": "pom.xml", "line": 0, "rule_id": "BUILD_UNRESOLVABLE", "message_sha256": sha256_bytes(str(diags.get("reason") or "").encode("utf-8")), "detail": str(diags.get("reason") or "")[:200], "message": str(diags.get("reason") or "")[:600]})
    return out


# What a failed packaging or startup means, in the order the evidence is read.
# Each row is (signature, obligation kind, cluster kind, locus). The signatures
# come from the tools themselves, so the classification is deterministic and a
# controller gets the same obligation for the same failure every time.
RUNTIME_SIGNATURES = (
    # A property the platform could not resolve at startup. It is first because
    # it is the most specific thing a startup log can say about configuration:
    # a log that also carries a generic "is not configured" is still this
    # failure. application.properties is only the FALLBACK locus -- the
    # annotation that names the property is looked for first (see
    # config_value_decision).
    ("Failed to load config value", "application-configuration", "config", "src/main/resources/application.properties"),
    ("is not configured", "application-configuration", "config", "src/main/resources/application.properties"),
    ("ConfigurationException", "application-configuration", "config", "src/main/resources/application.properties"),
    ("Unable to find datasource", "application-configuration", "config", "src/main/resources/application.properties"),
    ("relation \"", "schema-initialization", "config", "src/main/resources/application.properties"),
    ("does not exist", "schema-initialization", "config", "src/main/resources/application.properties"),
    ("Table not found", "schema-initialization", "config", "src/main/resources/application.properties"),
    ("SQLGrammarException", "schema-initialization", "config", "src/main/resources/application.properties"),
    ("Unsupported class file major version", "build-configuration", "build", "pom.xml"),
    # An augmentation build step that throws is the platform telling the
    # destination its code and its extensions disagree. It names the type it
    # could not satisfy, so the obligation belongs at that type, not at pom.xml
    # (pilot v7: SpringDataJPAProcessor found no implementation of
    # VetRepository, which no compile error and no test could see).
    ("threw an exception", "application-configuration", "config", "src/main/resources/application.properties"),
    ("Failed to execute goal", "build-configuration", "build", "pom.xml"),
)
FQN_RE = re.compile(r"\b(?:[a-z][A-Za-z0-9_]*\.){2,}[A-Z][A-Za-z0-9_]*\b")

# A CLOSED vocabulary of causes, matched from the tools' own exception and
# marker strings. It is part of an obligation's identity, so that two genuinely
# different problems at one file are two obligations (a file can need a second
# repair after the first succeeds) while any rewording of the same problem
# stays one. Nothing here is derived from free text: an unmatched failure is
# always "unclassified", so no phrasing can mint a new obligation.
RUNTIME_CAUSES = (
    # More specific than the generic configuration markers below, so it is
    # matched first: the platform named the property it could not load.
    ("Failed to load config value", "config-value"),
    ("No implementation of interface", "missing-implementation"),
    ("UnableToParseMethodException", "underivable-query-method"),
    ("was not part of the Quarkus index", "unindexed-type"),
    ("SpEL expressions are not supported", "unsupported-spel"),
    ("Unable to find datasource", "datasource-unconfigured"),
    ("is not configured", "datasource-unconfigured"),
    ("ConfigurationException", "configuration-invalid"),
    ("UnsatisfiedResolutionException", "unsatisfied-injection"),
    ("AmbiguousResolutionException", "ambiguous-injection"),
    ("DefinitionException", "definition-invalid"),
    ("Unsupported class file major version", "toolchain-class-version"),
    # A QUERY the persistence provider refuses to parse or to resolve. Before
    # the schema rows on purpose: Hibernate 6 tightened HQL/JPQL and reports
    # its strictness failures with a message that also carries "does not
    # exist", so the generic schema row would file a query defect as a missing
    # table and send the worker to application.properties, where no query can
    # be repaired (the isolated experiment's WU-9: eight queries over four
    # fragments). The needles are the provider's OWN strings; the locus is the
    # fragment or repository the message names (runtime_locus →
    # named_source_types), never the properties file.
    ("QuerySyntaxException", "query-invalid"),
    ("SemanticException", "query-invalid"),
    ("could not resolve attribute", "query-invalid"),
    ("Could not resolve attribute", "query-invalid"),
    ("SQLGrammarException", "schema-missing-object"),
    ("relation \"", "schema-missing-object"),
    ("Table not found", "schema-missing-object"),
    ("does not exist", "schema-missing-object"),
)


# A failure that is about a SET, not a file. The platform names one member of
# the set and which one it names changes between runs: six builds of one
# unchanged v8 tree named Owner, User, Visit, PetType, Pet and Specialty in
# turn (2026-09-12). Pinning the obligation to the name of the moment churns
# its identity, its write set and its retry budget, and would send a worker to
# repair an arbitrary file. Recognised here by the PROCESSOR that raised it
# plus the closed-vocabulary cause; the members are not invented -- deriving
# the complete set belongs to a family planner, and until then this is a typed
# blocker, never a card.
RUNTIME_SET_WIDE = (
    ("io.quarkus.spring.data.deployment", "missing-implementation", "spring-data-fragment-implementations"),
)


# Which former may turn a set-wide scope into a mintable unit. Data, not a
# literal in the former: the row says "rule (b) can enumerate this set from
# the model". When the former returns nothing the typed blocker stands,
# unchanged -- a set the model cannot enumerate is still not a card.
RUNTIME_SET_WIDE_FORMER = {
    "spring-data-fragment-implementations": "unit/declaration-closure/v1",
}


def set_wide_scope(text: str, cause: str) -> str:
    """The scope id when this failure is about a set, else ""."""
    for marker, want_cause, scope in RUNTIME_SET_WIDE:
        if cause == want_cause and marker in (text or ""):
            return scope
    return ""


def named_source_types(text: str, root: Path | None) -> list[str]:
    """Every type the message names that this tree really has, as paths.

    The raw message stays the observation; this is what it pointed at."""
    if root is None:
        return []
    out: list[str] = []
    for fqn in FQN_RE.findall(text or ""):
        rel = "src/main/java/%s.java" % fqn.replace(".", "/")
        if (Path(root) / rel).is_file() and rel not in out:
            out.append(rel)
    return out


QUOTED_RE = re.compile(r"'([^']{8,120})'|\"([^\"]{8,120})\"")


def quoted_literal_locus(text: str, root: Path | None) -> str:
    """The one source file carrying a literal the message quotes, or ""."""
    if root is None:
        return ""
    base = Path(root) / "src" / "main"
    if not base.is_dir():
        return ""
    seen: list[str] = []
    for m in QUOTED_RE.finditer(text or ""):
        literal = (m.group(1) or m.group(2) or "").strip()
        if not literal or literal in seen or literal.startswith(("http", "/")):
            continue
        seen.append(literal)
        hits: list[str] = []
        for f in sorted(base.rglob("*")):
            if not f.is_file() or f.suffix not in (".java", ".properties", ".xml", ".yaml", ".yml"):
                continue
            try:
                if literal in f.read_text(encoding="utf-8", errors="replace"):
                    hits.append(f.relative_to(root).as_posix())
            except OSError:
                continue
            if len(hits) > 1:
                break
        if len(hits) == 1:
            return hits[0]
    return ""


def runtime_cause(text: str) -> str:
    for needle, cause in RUNTIME_CAUSES:
        if needle in (text or ""):
            return cause
    return "unclassified"


# Where a tool names the MEMBER it could not handle, that member is part of the
# obligation: a repository with three underivable methods is three repairs, and
# a loop that cannot see the first one revert the whole file's work every time
# (the reverted tree means each attempt must redo what the last one did). The
# patterns are structured, not free text -- the name comes from the code.
RUNTIME_MEMBER_RES = (
    re.compile(r"Method '([A-Za-z_][A-Za-z0-9_]*)' of repository"),
    re.compile(r"method '([A-Za-z_][A-Za-z0-9_]*)' of class"),
)


def runtime_member(text: str) -> str:
    for rx in RUNTIME_MEMBER_RES:
        m = rx.search(text or "")
        if m:
            return m.group(1)
    return ""


def member_signatures(root: Path | None, rel: str, member: str) -> list[str]:
    """Every signature of this member in the destination's own JDK model.

    The platform names a method, not a signature. When a name is overloaded the
    obligation stays ONE ambiguous diagnostic linked to both candidates rather
    than two invented failures or an arbitrary pick; the raw message is kept
    beside the resolution."""
    if root is None or not rel or not member:
        return []
    p = Path(root) / TYPE_INVENTORY
    if not p.is_file():
        return []
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return []
    out: list[str] = []
    for row in doc.get("types") or []:
        if str(row.get("dest_file") or row.get("file") or "") != rel:
            continue
        for meth in row.get("methods") or []:
            if str(meth.get("name") or "") == member:
                out.append(str(meth.get("signature") or member + "(?)"))
    return sorted(set(out))


# --- a config property the platform could not load -------------------------
#
# "Failed to load config value of type class java.lang.String for: X" is a
# question about WHERE X is read, and X is read from an ANNOTATION, not from
# application.properties. Sending the worker to the properties file is sending
# him where the defect cannot be (measured live on v9, 2026-09-14: a worker had
# replaced @Value("#{servletContext.contextPath}") with @Value(""), so the
# property name after "for:" was empty and the card was minted at
# application.properties, where nothing could be repaired).
#
# The sites are read from M1's structural model, never from the Java text: the
# JDK recorded each annotation with its resolved name and its values.
SPRING_VALUE_ANNOTATION = "org.springframework.beans.factory.annotation.Value"
MP_CONFIG_PROPERTY_ANNOTATION = "org.eclipse.microprofile.config.inject.ConfigProperty"
# the property name runs from "for:" to the end of that line, and may be empty
CONFIG_VALUE_FOR_RE = re.compile(r"Failed to load config value[^\n]*?\bfor:[ \t]*([^\n]*)")
# what the worker has to know to repair the site, whatever the specimen is
CONFIG_VALUE_LESSON = ("under quarkus-spring-di @Value(\"x\") READS config property x -- @Value(\"${x}\") and "
                       "@Value(\"${x:d}\") name that same property x -- so the annotation's value is a property "
                       "name, not a literal; the application's root path is the property quarkus.http.root-path")


def config_property_name(text: str) -> str:
    """The property name the platform printed after "for:" (may be "")."""
    m = CONFIG_VALUE_FOR_RE.search(text or "")
    return m.group(1).strip() if m else ""


def config_property_of(raw: Any) -> str:
    """The config property an annotation value resolves to.

    Spring's placeholder form and the bare form name the same property:
    ``${x}`` and ``${x:default}`` are both x, and under quarkus-spring-di a
    bare ``x`` is x as well."""
    v = str(raw if raw is not None else "").strip()
    if v.startswith("${") and v.endswith("}"):
        v = v[2:-1].split(":", 1)[0]
    return v.strip()


def _single_value(raw: Any) -> Any:
    """The one value of an annotation attribute, or None if it is not single.

    The JDK model records attribute values as a list, because an annotation
    attribute may be an array. A property name is a single value; an array is
    not one property and is left alone."""
    if isinstance(raw, list):
        return raw[0] if len(raw) == 1 else None
    return raw


def config_property_annotation(ann: dict[str, Any]) -> tuple[str, str] | None:
    """(property this annotation names, how to write it) or None.

    Only the two annotations that NAME a config property are read: Spring's
    @Value (which quarkus-spring-di maps onto MicroProfile Config) and
    MicroProfile's own @ConfigProperty."""
    if not isinstance(ann, dict):
        return None
    fqn = str(ann.get("fqn") or ann.get("name") or "")
    # The JDK model records the name AS WRITTEN beside the resolved one, because
    # a tree that cannot yet be compiled against its dependencies has no fqn for
    # the annotation and the written name is then all there is. It is used only
    # when the compiler gave nothing: a resolved foreign @Value is not this one.
    simple = fqn.rsplit(".", 1)[-1] or str(ann.get("simple") or "")
    # Which ATTRIBUTE each value was written for. The JDK model records that map
    # under `named`; M1's model records the same shape under `values`. A flat
    # list of literals cannot say which of them is the property name.
    values = ann.get("named") if isinstance(ann.get("named"), dict) else (
        ann.get("values") if isinstance(ann.get("values"), dict) else {})
    if fqn in (SPRING_VALUE_ANNOTATION, "Value") or (not fqn and simple == "Value"):
        raw, attr = _single_value(values.get("value")), "value"
    elif fqn in (MP_CONFIG_PROPERTY_ANNOTATION, "ConfigProperty") or (not fqn and simple == "ConfigProperty"):
        raw, attr = _single_value(values.get("name")), "name"
    else:
        return None
    if raw is None:
        return None
    written = "@%s(\"%s\")" % (simple, raw) if attr == "value" else "@%s(name = \"%s\")" % (simple, raw)
    return config_property_of(raw), written


def structure_types(root: Path | None) -> list[dict[str, Any]]:
    """M1's structural model of this tree, or [] when it is not here."""
    if root is None:
        return []
    p = Path(root) / STRUCTURE
    if not p.is_file():
        return []
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return []
    return [t for t in (doc.get("types") or []) if isinstance(t, dict)]


def structure_type_path(root: Path | None, typ: dict[str, Any]) -> str:
    """This type's source file, derived the way the other locators derive one:
    from the fully-qualified name when the tree really has that file, else the
    path the model itself recorded."""
    fqn = str(typ.get("fqn") or typ.get("name") or "")
    derived = ("src/main/java/%s.java" % fqn.replace(".", "/")) if fqn else ""
    claimed = str(typ.get("path") or "")
    if root is not None:
        if derived and (Path(root) / derived).is_file():
            return derived
        if claimed and (Path(root) / claimed).is_file():
            return claimed
    return claimed or derived


def _structure_config_sites(root: Path | None, prop: str) -> list[dict[str, str]]:
    """The sites M1's model of the FROZEN SOURCE has for this property."""
    out: list[dict[str, str]] = []
    for typ in structure_types(root):
        path = structure_type_path(root, typ)
        members: list[tuple[str, Any]] = [(str(f.get("name") or ""), f.get("annotations"))
                                          for f in typ.get("fields") or [] if isinstance(f, dict)]
        for holder in list(typ.get("methods") or []) + list(typ.get("constructors") or []):
            if not isinstance(holder, dict):
                continue
            for par in holder.get("params") or []:
                if isinstance(par, dict):
                    members.append((str(par.get("name") or ""), par.get("annotations")))
        for member, anns in members:
            for ann in anns or []:
                named = config_property_annotation(ann)
                if named is not None and named[0] == prop:
                    out.append({"path": path, "type": str(typ.get("fqn") or ""), "member": member, "annotation": named[1]})
    return sorted(out, key=lambda s: (s["path"], s["type"], s["member"], s["annotation"]))


def _dest_config_sites(model: dict[str, Any], prop: str) -> list[dict[str, str]]:
    """The sites the DESTINATION's own compiled model has for this property.

    Fields only: the tool records no annotations on parameters, so absence here
    is not evidence that nothing names the property."""
    out: list[dict[str, str]] = []
    for row in fields_of(model):
        for ann in row.get("annotations") or []:
            named = config_property_annotation(ann)
            if named is not None and named[0] == prop:
                out.append({"path": row["path"], "type": row["type"], "member": row["field"], "annotation": named[1]})
    return sorted(out, key=lambda s: (s["path"], s["type"], s["member"], s["annotation"]))


def config_value_sites(root: Path | None, prop: str) -> tuple[list[dict[str, str]], str, str]:
    """(every site whose annotation names THIS config property, which model
    answered, why that one).

    The DESTINATION is asked first. What an annotation says is a fact about the
    tree being measured, and M1's structural model is of the FROZEN SOURCE:
    measured on destination v9 (2026-09-14), the field still carried
    @Value("#{servletContext.contextPath}") there while a worker's edit had
    already made it @Value("") on disk, so the empty property name the platform
    printed matched nothing and the obligation was reported as unlocatable --
    while the worker on the card could name the file and the line.

    The frozen source's model answers when the destination cannot be modelled
    at all, and for the one thing the compiled model does not record -- an
    annotation on a method or constructor parameter -- when no FIELD of the
    destination names the property. Deterministic: sorted by file, type, member."""
    if root is None:
        return _structure_config_sites(root, prop), "structure", "there is no tree to model"
    try:
        model = dest_model(Path(root))
    except DestModelUnavailable as exc:
        return (_structure_config_sites(root, prop), "structure",
                "the destination tree could not be modelled: %s" % exc)
    sites = _dest_config_sites(model, prop)
    if sites:
        return sites, "dest-model", ""
    return (_structure_config_sites(root, prop), "structure",
            "the dest-model records annotations on FIELDS and no field of the destination names it, so the "
            "frozen source's model was asked about parameters too")


def config_value_decision(text: str, root: Path | None, fallback: str) -> tuple[str, str, str, bool, str]:
    """(locus, cluster kind, member, unlocated, what the worker must be told).

    A property is read at the annotation that names it; the properties file is
    only where a MISSING key would be supplied. An empty name is neither: no
    key can be added for it, and the annotation that produced it is in no
    model, so it is reported as a blocker rather than sent anywhere.

    The note names WHICH MODEL answered: the two can disagree about the same
    field, and the reader has to know which tree the locus is a fact about."""
    prop = config_property_name(text)
    quoted = "\"%s\"" % prop if prop else "EMPTY (nothing follows \"for:\")"
    sites, model, why = config_value_sites(root, prop)
    # short, because the brief is capped and the lesson must survive it; the
    # reason the fallback was taken goes on the blocker, which has room
    answered = "dest-model" if model == "dest-model" else "structure model"
    if sites:
        first = sites[0]  # the lowest path: deterministic when several read it
        others = ["%s.%s %s" % (s["type"], s["member"], s["annotation"]) for s in sites[1:]]
        note = "the config property the platform could not load is %s, and it is named by %s on %s.%s (located by the %s)" % (
            quoted, first["annotation"], first["type"], first["member"], answered)
        if others:
            note += "; the same property is also read at %s -- repair this one, the rest stay reported" % ", ".join(others)
        return first["path"], "compile", first["member"], False, note + "; " + CONFIG_VALUE_LESSON
    if prop:
        return (fallback, "config", "", False,
                "the config property the platform could not load is %s, and no @Value or @ConfigProperty in the "
                "%s names it, so it is a key %s must supply; %s" % (quoted, answered, fallback, CONFIG_VALUE_LESSON))
    return ("", "config", "", True,
            "the config property name the platform printed after \"for:\" is EMPTY: an empty config property name "
            "comes from an annotation the %s does not record%s" % (answered, ("; %s" % why) if why else ""))


def runtime_locus(text: str, root: Path | None) -> str:
    """The source file a runtime failure names, when the tree has it.

    A message that names a type is pointing at that type. Guessing is not
    involved: the path is derived from the fully-qualified name and only used
    when the file is really there.

    A failure that names NO file of this tree is left unlocated on purpose:
    sending the worker to application.properties for a repository problem is
    worse than saying plainly that the platform named nothing (pilot v7:
    "void was not part of the Quarkus index" from the Spring Data processor,
    which is about a repository method and mentions no type of ours)."""
    if root is None:
        return ""
    for fqn in FQN_RE.findall(text or ""):
        rel = "src/main/java/%s.java" % fqn.replace(".", "/")
        if (Path(root) / rel).is_file():
            return rel
    # Second strategy: a platform that quotes the offending VALUE has named the
    # file as surely as if it had named the type, provided exactly one source
    # carries that literal. Uniqueness is the whole check -- two matches is not
    # a location (measured live: "SpEL expressions are not supported ...
    # Offending value is '@Value(\"#{servletContext.contextPath}\")'" named no
    # type of ours and exactly one file had the string).
    return quoted_literal_locus(text, root)
# A failure the destination cannot repair by editing its own tree. It is a
# blocker, never a card: no amount of patching pom.xml makes an unreachable
# database reachable.
RUNTIME_ENVIRONMENT_SIGNATURES = (
    "Connection refused", "UnknownHostException", "password authentication failed",
    "Connection to localhost", "could not connect", "No such host is known",
)


def classify_runtime_failure(text: str) -> tuple[str, str, str]:
    """(obligation kind, cluster kind, locus) for a packaging/startup failure."""
    for needle, kind, cluster_kind, locus in RUNTIME_SIGNATURES:
        if needle in text:
            return kind, cluster_kind, locus
    return "build-configuration", "build", "pom.xml"


def runtime_environment_blocker(text: str) -> str:
    for needle in RUNTIME_ENVIRONMENT_SIGNATURES:
        if needle in text:
            return needle
    return ""


def runtime_items(package: dict[str, Any] | None, boot: dict[str, Any] | None, root: Path | None = None) -> list[dict[str, Any]]:
    """Obligations from the packaging and startup gates.

    They carry ``gate`` so acceptance can be phase-aware: repairing one of
    these can leave the compile/test tuple untouched, and the step is then
    accepted because its own gate went from failing to passing."""
    out: list[dict[str, Any]] = []
    for gate, doc in (("package", package), ("boot", boot)):
        if not isinstance(doc, dict) or not doc.get("ran"):
            continue
        if doc.get("blocker"):
            continue  # an environment blocker is not a repair obligation
        failed = bool(doc.get("rc")) or (gate == "boot" and not doc.get("ready"))
        if not failed:
            continue
        detail = str(doc.get("detail") or doc.get("failed_goal") or "")
        # the error lines when the runner captured them, else the tail: a
        # Maven log ends in a summary, and the failing build step is named
        # long before that
        log = str(doc.get("errors") or doc.get("log_tail") or "")
        text = detail + "\n" + log
        kind, cluster_kind, locus = classify_runtime_failure(text)
        fallback_locus = locus  # what the signature alone says, before any locator
        unlocated = False
        named = runtime_locus(text, root)
        if named:
            locus, cluster_kind = named, "compile"
        elif "threw an exception" in text and kind == "application-configuration":
            # An augmentation failure that names no file of ours cannot be made
            # into an actionable card: sending the worker to
            # application.properties (or to pom.xml) for a repository problem
            # is worse than saying plainly that nobody can locate it. It is
            # reported as a blocker instead, and a human reads the message
            # (pilot v7: "void was not part of the Quarkus index").
            unlocated = True
        # The identity is WHERE and WHAT, never the wording: the gate, the kind,
        # the cause from a closed vocabulary, and the file. A tool that
        # rephrases the same failure at the same place is the same obligation,
        # so a repair that only changes the message is not progress; but a file
        # whose first problem is fixed and whose SECOND problem then surfaces
        # gets a new obligation, because the cause differs (measured live:
        # "No implementation of interface" became UnableToParseMethodException
        # at the same repository once it became a Spring Data repository).
        cause = runtime_cause(text)
        member = runtime_member(text)
        note = ""
        if cause == "config-value":
            # A property is read at the annotation that names it. The message
            # names no type, so every locator above would either miss it or
            # (worse) leave the properties-file fallback standing, where no
            # worker can repair an annotation site.
            locus, cluster_kind, member, unlocated, note = config_value_decision(text, root, fallback_locus)
        # A set-wide cause keeps neither the file nor the member in its
        # identity: both are whichever one the platform reached first.
        scope = set_wide_scope(text, cause)
        observed = named_source_types(text, root)
        if scope:
            locus, member, unlocated = "", "", True
            ident = sha256_bytes(canonical_bytes({"gate": gate, "kind": kind, "cause": cause, "set_wide": scope}))[:16]
        else:
            ident = sha256_bytes(canonical_bytes({"gate": gate, "kind": kind, "cause": cause, "locus": locus, "member": member}))[:16]
        # a member the model names as a FIELD is not a method: asking the type
        # inventory for its signatures could only answer about something else
        sigs = [] if note else member_signatures(root, locus, member)
        out.append({
            "id": "rt:%s:%s" % (gate, ident), "source": "runtime", "gate": gate,
            "kind": cluster_kind, "obligation": kind, "cause": cause, "member": member,
            "set_wide": scope, "observed": observed,
            "unlocated": unlocated, "category": "mandatory",
            "signatures": sigs,
            "ambiguous_member": len(sigs) > 1,
            "path": locus, "line": 0, "rule_id": "RUNTIME_%s" % kind.replace("-", "_").upper(),
            "message_sha256": sha256_bytes((detail + log).encode("utf-8")),
            # what the tool said stays; what was derived from the structural
            # model is added, because it is what the worker has to be told
            "detail": ("%s -- %s" % (note, detail[:200]))[:600] if note else detail[:200],
            "message": ("%s gate failed (%s%s): %s\n%s%s" % (gate, kind, (" at %s" % member) if member else "", detail,
                                                             (note + "\n") if note else "", log))[:1200],
        })
    return out


def runtime_state(package: dict[str, Any] | None, boot: dict[str, Any] | None) -> dict[str, Any]:
    """Whether the packaged artifact was verified and started.

    Never initialised to a pass: a gate that did not run is unknown, and
    unknown keeps the closing card unminted."""
    reasons: list[str] = []
    pkg_ok = isinstance(package, dict) and bool(package.get("ran")) and package.get("rc") == 0
    boot_ok = isinstance(boot, dict) and bool(boot.get("ran")) and boot.get("rc") == 0 and bool(boot.get("ready"))
    if not isinstance(package, dict) or not package.get("ran"):
        reasons.append("the full Maven verification has not run on this tree; packaging is unknown, not clean")
    elif package.get("rc") != 0:
        reasons.append("the full Maven verification failed (%s)" % (package.get("failed_goal") or package.get("detail") or "see verification/build/package.json"))
    if not isinstance(boot, dict) or not boot.get("ran"):
        reasons.append("the packaged application has not been started against the decided database; startup is unknown, not clean")
    elif not boot_ok:
        reasons.append("the packaged application did not become ready (%s)" % (boot.get("detail") or boot.get("blocker") or "see verification/build/boot.json"))
    same_artifact = bool(pkg_ok and boot_ok and str(package.get("artifact_sha256") or "") and str(package.get("artifact_sha256")) == str(boot.get("artifact_sha256") or ""))
    if pkg_ok and boot_ok and not same_artifact:
        reasons.append("startup evidence is for a different artifact than the one packaging verified (%s vs %s)" % (str(boot.get("artifact_sha256"))[:12], str(package.get("artifact_sha256"))[:12]))
    blockers = [str(d.get("blocker")) for d in (package, boot) if isinstance(d, dict) and d.get("blocker")]
    return {
        "package": {"ran": bool(isinstance(package, dict) and package.get("ran")), "rc": (package or {}).get("rc"), "artifact_sha256": str((package or {}).get("artifact_sha256") or "")},
        "boot": {"ran": bool(isinstance(boot, dict) and boot.get("ran")), "rc": (boot or {}).get("rc"), "ready": bool((boot or {}).get("ready")), "artifact_sha256": str((boot or {}).get("artifact_sha256") or "")},
        "blockers": blockers,
        "ready": bool(pkg_ok and boot_ok and same_artifact),
        "reasons": reasons,
    }


def test_items(surefire: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in surefire.get("failures") or []:
        name = "%s#%s" % (f.get("classname"), f.get("name"))
        ident = sha256_bytes(canonical_bytes({"test": name}))[:16]
        # A failing test is an obligation on PRODUCTION code: the item's locus
        # is the test (for the brief) but its cluster write set is derived in
        # cluster_items from the production twin, never the test file.
        path = str(f.get("path") or "") or ("src/test/java/" + str(f.get("classname") or "").replace(".", "/") + ".java" if f.get("classname") else "src/test/java")
        out.append({"id": "test:%s" % ident, "source": "surefire", "kind": "test", "category": "mandatory", "path": path, "line": 0, "rule_id": "TEST_FAILURE", "message_sha256": sha256_bytes(str(f.get("message") or "").encode("utf-8")), "detail": name[:200], "test": name})
    return out


_CORS_HEADER = "Access-Control-"
APP_PROPERTIES = "src/main/resources/application.properties"


def classify_parity_diffs(reason: str) -> tuple[list[str], list[str]]:
    """Split a parity verdict's diffs into (cors, other).

    The comparator writes one diff per finding, "; "-joined: ``status A vs
    B``, ``body A vs B``, ``header NAME have vs want``, ``effect ID: ...``.
    A ``header Access-Control-*`` diff is the source's cross-origin behaviour
    the destination does not reproduce; ADR-019 repairs it with the
    source-preserving CORS response adapter plus its configuration, never at a
    controller. Everything else -- a Location, a header the source exposes
    (``errors``), a status, a body, an effect -- is the operation's own
    behaviour (``representation_diffs`` takes a Content-Type PARAMETER
    difference out of it as its own obligation)."""
    cors, other = [], []
    for d in _split_diffs(reason):
        if d.startswith("header " + _CORS_HEADER):
            cors.append(d)
        else:
            other.append(d)
    return cors, other


def _split_diffs(reason: str) -> list[str]:
    """The comparator's diffs, re-joined where a header value itself carried a
    ';' (a Content-Type parameter list): a fragment that does not start a new
    diff belongs to the one before it."""
    out: list[str] = []
    for frag in str(reason or "").split(";"):
        f = frag.strip()
        if not f:
            continue
        if out and not _DIFF_START_RE.match(f):
            out[-1] = out[-1] + ";" + frag.rstrip()
            continue
        out.append(f)
    return out


SCENARIO_CORPUS = Path("verification") / "scenarios" / "corpus.json"
# the corpus's scenario_type vocabulary (capture-source-oracles/_scenarios.py)
SCENARIO_BROWSER_PREFLIGHT = "browser-preflight"
SCENARIO_DIAGNOSTIC_PROBE = "diagnostic-probe"
# the scenario-id shape capture-source-oracles gives every cross-origin
# scenario it derives (cors-preflight-*, cors-actual-*, and the ADR-020
# variants), with or without the ``sc:`` prefix
_CORS_SCENARIO_RE = re.compile(r"^(?:sc:)?cors-")
_CORS_PREFLIGHT_RE = re.compile(r"^(?:sc:)?cors-(?:[a-z0-9]+-)*preflight-")
_CORS_PROBE_RE = re.compile(r"^(?:sc:)?cors-(?:[a-z0-9]+-)*probe-")
# a same-origin request is ordinary routing for the source, so its WHOLE
# response is the one the adapter must let routing produce (ADR-020)
_CORS_SAME_ORIGIN_RE = re.compile(r"^(?:sc:)?cors-[a-z0-9-]*same-origin")


def cors_scenarios(root: Path | None) -> dict[str, dict[str, Any]]:
    """{scenario id: {method, preflight}} for the corpus's cross-origin scenarios
    (a scenario naming a ``cors_policy``). {} when there is no corpus."""
    p = Path(root) / SCENARIO_CORPUS if root is not None else None
    if p is None or not p.is_file():
        return {}
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for sc in (doc.get("scenarios") or []) if isinstance(doc, dict) else []:
        if not isinstance(sc, dict) or not sc.get("cors_policy") or not sc.get("id"):
            continue
        hdrs = {str(k).lower() for k in (sc.get("headers") or {})}
        method = str(sc.get("method") or "").upper()
        stype = str(sc.get("scenario_type") or "")
        out[str(sc["id"])] = {"method": method, "type": stype,
                              "probe": stype == SCENARIO_DIAGNOSTIC_PROBE,
                              "preflight": stype == SCENARIO_BROWSER_PREFLIGHT or (
                                  not stype and method == "OPTIONS" and "access-control-request-method" in hdrs),
                              "same_origin": bool(sc.get("same_origin")) or str(sc.get("origin_kind") or "") == "same",
                              "has_body": bool(sc.get("body_file"))}
    return out


def corpus_requests(root: Path | None) -> dict[str, dict[str, Any]]:
    """{scenario id: {method, has_body, cross_origin}} for EVERY corpus scenario
    (the cross-origin ones and the controls alike). {} without a corpus."""
    p = Path(root) / SCENARIO_CORPUS if root is not None else None
    if p is None or not p.is_file():
        return {}
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for sc in (doc.get("scenarios") or []) if isinstance(doc, dict) else []:
        if not isinstance(sc, dict) or not sc.get("id"):
            continue
        out[_sid(str(sc["id"]))] = {"method": str(sc.get("method") or "").upper(), "has_body": bool(sc.get("body_file")),
                                    "cross_origin": bool(sc.get("cors_policy"))}
    return out


def _doc_method(doc: dict[str, Any], row: dict[str, Any] | None) -> str:
    req = doc.get("request") if isinstance(doc.get("request"), dict) else {}
    return str(req.get("method") or (row or {}).get("method") or "").upper()


def cors_typed_status(doc: dict[str, Any], diff: str) -> str:
    """H6a: why this status difference on a cross-origin ACTUAL request is a
    CORS-typed refusal -- the producer the capability's known responses name
    (response_adapters.CORS_REJECTIONS: the adapter's 403 with its body, the
    platform CORS filter's 403) -- or "" when the observed status is anything
    else. The status is read from the diff and the body from the record's
    own observation; nothing here is a literal of the planner's."""
    p = parse_parity_diff(diff)
    if p["kind"] != "status":
        return ""
    observed = doc.get("observed") if isinstance(doc.get("observed"), dict) else {}
    return _adapters.cors_rejection(p["have"], str(observed.get("body_sample") or ""))


def cors_scenario_split(scenario: str, doc: dict[str, Any], known: dict[str, dict[str, Any]],
                        cors: list[str], other: list[str],
                        controls: set[str] | None = None) -> tuple[list[str], list[str]]:
    """ADR-020 and H6a: in a CROSS-ORIGIN scenario the adapter's scope owns
    more than the Access-Control-* headers. For a preflight, a same-origin
    request, or an OPTIONS the source treated as ordinary routing, the whole
    response is (status, body, Allow, challenge): the platform answers a
    preflight before any endpoint, and a same-origin rejection is the CORS
    filter judging what the source never judged. "Stricter" never waives a
    measured difference there: those diffs become the PARITY_CORS obligation.

    A cross-origin ACTUAL request is answered by the operation itself once
    the CORS decision let it through, so its status is the adapter's only
    when it IS the CORS decision: a refusal the capability's known responses
    name (cors_typed_status). Any other status -- a 400, a 404, a 500 --
    routes exactly as it would without the Origin header, to the controller
    with the body and the other headers (v9 sc:create-owners: a 400 with an
    empty body where the source answered 201 was sent to the adapter, which
    had nothing to change). ``controls`` are the status diffs a
    NON-cross-origin scenario of the same entry point and method reported
    identically in this comparison: a status the operation answers without
    any Origin is never the CORS decision, whatever it is."""
    sid = str(scenario or "")
    row = known.get(sid) or known.get(sid[3:] if sid.startswith("sc:") else "sc:" + sid)
    if row is None and not _CORS_SCENARIO_RE.match(sid):
        return cors, other
    method = _doc_method(doc, row)
    whole = (bool((row or {}).get("preflight")) or bool((row or {}).get("same_origin")) or method == "OPTIONS"
             or _CORS_PREFLIGHT_RE.match(sid) is not None or _CORS_SAME_ORIGIN_RE.match(sid) is not None)
    status = [d for d in other if parse_parity_diff(d)["kind"] == "status"]
    if whole:
        # the complete response follows only a CORS-shaped difference (a status
        # or an Access-Control-* header): a body alone -- or a body and a
        # Content-Type parameter -- is the operation's own and the
        # representation obligation's, never the adapter's
        moved = [d for d in other] if (cors or status) else []
    else:
        moved = [d for d in status if d not in (controls or set()) and cors_typed_status(doc, d)]
    return cors + moved, [d for d in other if d not in moved]


def representation_diffs(diffs: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """(Content-Type PARAMETER differences, the rest).

    ADR-019: a charset difference is a response-REPRESENTATION obligation of its
    own -- its own scope, evidence and acceptance -- and never part of the CORS
    repair. Only a difference on the SAME media type whose parameters differ is
    taken; a different media type is the operation's behaviour and stays where
    it was."""
    rep: list[dict[str, Any]] = []
    rest: list[str] = []
    for d in diffs:
        p = parse_parity_diff(d)
        if p["kind"] == "header" and p["name"].lower() == "content-type":
            diff = _adapters.media_type_difference(p["have"], p["want"])
            if diff:
                rep.append(dict(diff, raw=p["raw"], have=p["have"], want=p["want"]))
                continue
        rest.append(d)
    return rep, rest


# ---------------------------------------------------------------------------
# parity advice: the exit conditions, quoted from the verdict's own diffs
# ---------------------------------------------------------------------------

# The comparator's diff grammar (_oracle_common.header_diffs,
# compare-scenario-parity.py): the DESTINATION's value is first, the SOURCE's
# second. Location carries the source's raw value after the mapped one.
_DIFF_STATUS_RE = re.compile(r"^status (?P<have>\S+) vs (?P<want>\S+)$")
_DIFF_HEADER_RE = re.compile(r"^header (?P<name>[A-Za-z0-9-]+) (?P<have>.*?) vs (?P<want>.*)$")
_DIFF_LOCATION_SOURCE_RE = re.compile(r"^(?P<want>.*?) \(source (?P<raw>.*)\)$")
_DIFF_START_RE = re.compile(r"^(status|header|body|effect)\b")

# The platform's CORS keys, by the header each one governs. With ADR-019 they
# are the platform's ENFORCEMENT half of the repair (rendered from the source
# policy by the capability); the source's per-handler shape is the adapter's.
CORS_PROPERTY = {
    "access-control-allow-origin": "quarkus.http.cors.origins",
    "access-control-allow-methods": "quarkus.http.cors.methods",
    "access-control-allow-headers": "quarkus.http.cors.headers",
    "access-control-expose-headers": "quarkus.http.cors.exposed-headers",
    "access-control-allow-credentials": "quarkus.http.cors.access-control-allow-credentials",
    "access-control-max-age": "quarkus.http.cors.access-control-max-age",
}
CORS_ENABLED = "quarkus.http.cors.enabled"
CORS_LINKS = ["https://quarkus.io/version/3.27/guides/security-cors",
              "https://quarkus.io/version/3.27/guides/http-reference#filters"]
CORS_CAUSE = "cors-response"
# H7: a request body refused by a GENERATED type's required-args constructor;
# the generator plugin's configuration in pom.xml is the producer
GENERATED_BODY_CAUSE = "generated-body-binding"
RULE_PARITY_GENERATED_BODY = "PARITY_GENERATED_BODY"
REPRESENTATION_CAUSE = "content-type-parameter"
RULE_PARITY_CORS = _adapters.CONTRACTS[_adapters.CORS]["rule_id"]
RULE_PARITY_CONTENT_TYPE = _adapters.CONTRACTS[_adapters.MEDIA_TYPE]["rule_id"]

# A path token that says the address is an API-documentation UI: the thing a
# migration replaces rather than reimplements. Technology tokens, never a
# specimen's own route.
_DOC_UI_TOKENS = ("swagger", "openapi", "api-docs", "apidocs", "redoc")
DOC_UI_LINKS = ["https://quarkus.io/version/3.27/guides/openapi-swaggerui"]
REDIRECT_LINKS = ["https://quarkus.io/version/3.27/guides/http-reference#configure-http-access"]


def parse_parity_diff(diff: str) -> dict[str, str]:
    """One comparator diff, taken apart: what the DESTINATION answered
    (``have``) and what the SOURCE answered (``want``). ``kind`` is status,
    header, body, effect or other; ``source`` carries a Location's raw
    pre-mapping value. Nothing here knows any specimen."""
    d = str(diff or "").strip()
    m = _DIFF_STATUS_RE.match(d)
    if m:
        return {"kind": "status", "name": "status", "have": m.group("have"), "want": m.group("want"), "source": "", "raw": d}
    m = _DIFF_HEADER_RE.match(d)
    if m:
        name, have, want, src = m.group("name"), m.group("have"), m.group("want"), ""
        loc = _DIFF_LOCATION_SOURCE_RE.match(want)
        if loc:
            want, src = loc.group("want"), loc.group("raw")
        return {"kind": "header", "name": name, "have": have, "want": want, "source": src, "raw": d}
    kind = "body" if d.startswith("body ") else ("effect" if d.startswith("effect ") else "other")
    return {"kind": kind, "name": kind, "have": "", "want": "", "source": "", "raw": d}


def _url_path(url: str) -> str:
    """The path of an absolute or relative URL, without importing a parser for
    one field (an unparseable value is returned as it stands)."""
    s = str(url or "")
    if "://" in s:
        s = s.split("://", 1)[1]
        s = s[s.find("/"):] if "/" in s else "/"
    return s.split("?", 1)[0].split("#", 1)[0]


def _doubled_segment(path: str) -> str:
    """The first path segment that repeats itself immediately -- the shape a
    root path prepended to a value that already carried it leaves behind."""
    segs = [s for s in _url_path(path).split("/") if s]
    for a, b in zip(segs, segs[1:]):
        if a == b:
            return a
    return ""


def cors_advice(diffs: list[str], source_policies: list[str], root: Path | None = None) -> dict[str, Any]:
    """The CORS card's exit conditions (ADR-019), built from this verdict's own
    diffs and the SOURCE policy.

    The repair is the harness's source-preserving CORS response adapter plus
    its configuration, installed by the capability at the path its naming
    contract fixes. Configuration alone cannot reproduce the source's shape
    (the platform echoes the origin, names its whole method list and always
    writes a credentials header), and a controller filter never sees the
    platform's early preflight answer. The permissions come from the source
    policy -- never from this one capture -- and the capture decides only what
    the response must look like."""
    parsed = [parse_parity_diff(d) for d in diffs]
    headers = [p for p in parsed if p["kind"] == "header"]
    observed: dict[str, dict[str, str]] = {}
    for p in headers:
        observed[p["name"]] = {"destination": p["have"], "source": p["want"]}
    exposed = next((p["want"] for p in headers if p["name"].lower() == "access-control-expose-headers"), "")
    quoted = "; ".join(p["raw"] for p in parsed) or "no recorded diff"
    owed = _adapters.contract(_adapters.CORS)
    rendered: dict[str, Any] = {}
    render_block = ""
    if root is not None:
        try:
            policy = _adapters.cors_policy(Path(root))
            rendered = {"properties": dict(_adapters.cors_properties(policy)),
                        "source_policies": policy["source_policies"],
                        "rules": len(policy["rules"]), "security": policy["security"]}
        except _adapters.Refuse as exc:
            render_block = str(exc)
    exit_conditions = [
        ("install the capability BEFORE editing anything by hand: `%s`. It writes the adapter %s (type %s, contract %s, "
         "the harness template byte-for-byte) and the rows it renders from the SOURCE policy into %s; both paths are in "
         "this card's sealed write set." % (owed["install"], owed["path"], owed["type"], owed["contract"], owed["config"])),
        ("the source policy decides routes, origins, methods and headers (M1's structural model: every @CrossOrigin, the "
         "handlers it covers, the source's security configuration)%s; this verdict's diffs (%s) decide only what the "
         "response must look like — one observed request never defines the permission policy."
         % (" — the receipt records %s" % ", ".join(source_policies) if source_policies else "", quoted)),
        ("the preflight the platform answers before any endpoint comes back in the source's shape: the source's "
         "Access-Control-Allow-Origin value, only the matched handler's methods, only the requested headers the "
         "policy allows, the source's max-age, and no Access-Control-Allow-Credentials unless the source sent one."),
        ("the preflight answering 200 is not success: the PAIRED actual request at this entry point must come back carrying "
         "the same permission headers%s." % (" and must expose exactly %s to the caller" % exposed if exposed else
                                             " and must expose to the caller every header the source's Access-Control-Expose-Headers named")),
        ("platform enforcement is preserved in BOTH security modes: a rejection stays a rejection (a 401 carries no CORS "
         "header when the source's security ran first), and a request without Origin or from the same origin is "
         "answered as the source answered it."),
        ("ADR-020: the COMPLETE source response of every cross-origin scenario is the expectation -- status, body, "
         "Allow and the authentication challenge included. A same-origin request is not judged by the platform's CORS "
         "filter and ends as ordinary routing ends (a 405 stays a 405, never a manufactured success); an anonymous "
         "preflight the source's security refused is the mechanism's own 401 and challenge; a response stricter than "
         "the source's is a difference like any other."),
        "`%s --check` exits 0 on the candidate: the adapter bytes and every rendered row are exactly what the capability renders." % owed["install"],
        "both scenarios at this entry point (the preflight and the actual request) come back PASS from their own parity verdicts, and no scenario that was PASS regresses.",
    ]
    out = {
        "description": ("the destination does not reproduce the source's cross-origin behaviour; the repair is the harness's "
                        "source-preserving CORS response adapter plus its configuration (ADR-019), never a controller "
                        "annotation and never configuration alone"),
        "diffs": [p["raw"] for p in parsed],
        "observed_headers": observed,
        "owed": owed,
        "write_set": [owed["path"], owed["config"]],
        "source_policies": list(source_policies),
        "exit": exit_conditions,
        "refused": [
            "restoring the removed @CrossOrigin, or any other controller annotation: it grants nothing here",
            "configuration alone, or a hand-written filter instead of the capability's adapter at its contract path",
            "a wildcard policy inferred from this capture, or any permission the source policy does not grant",
            "header rewriting that turns a rejected exchange into an allowed one, or echoing a rejected method or header",
            "comparator normalization or an altered source expectation",
            "changing Content-Type here: a representation difference is its own obligation (PARITY_CONTENT_TYPE)",
            "copying the experiment's filter",
        ],
        "links": CORS_LINKS,
    }
    if rendered:
        out["rendered"] = rendered
    if render_block:
        out["render_refused"] = render_block
    return out


def representation_advice(differences: list[dict[str, Any]]) -> dict[str, Any]:
    """The Content-Type card's exit conditions (ADR-019): its own obligation,
    scope, evidence and acceptance. Configuration or the serializer first; the
    adapter removes only the decided parameter for the decided media types."""
    owed = _adapters.contract(_adapters.MEDIA_TYPE)
    quoted = "; ".join(str(d.get("raw") or "") for d in differences) or "no recorded diff"
    try:
        decided: dict[str, Any] = _adapters.media_type_decision(differences)
        why = ""
    except _adapters.Refuse as exc:
        decided, why = {}, str(exc)
    exit_conditions = [
        ("prefer the platform's own answer: a response or serializer setting that makes the destination send the "
         "source's Content-Type (%s) for these responses, if one exists for the decided media type." % quoted),
        (("otherwise install the capability: `%s`. It writes %s (type %s, contract %s) and removes ONLY the parameter "
          "%s=%s from %s — every other parameter, media type and the body encoding are left as they are."
          % (owed["install"], owed["path"], owed["type"], owed["contract"], decided.get("parameter"), decided.get("value"),
             ", ".join(decided.get("media_types") or [])))
         if decided else "no adapter is authorized: %s" % why),
        "`%s --check` exits 0 on the candidate when the adapter is the repair." % owed["install"],
        "this scenario's own parity verdict comes back PASS, and no scenario that was PASS regresses.",
    ]
    return {
        "description": ("the destination's Content-Type differs from the source's only in its parameters; this is a "
                        "response-REPRESENTATION obligation of its own (ADR-019), not part of any CORS repair"),
        "diffs": [str(d.get("raw") or "") for d in differences],
        "decided": decided,
        "owed": owed,
        "write_set": [owed["path"], owed["config"]],
        "exit": exit_conditions,
        "refused": [
            "dropping all Content-Type parameters to obtain a pass",
            "removing a parameter the recorded difference did not decide, or from another media type",
            "changing the body or its encoding",
            "comparator normalization or an altered source expectation",
            "using a CORS card's scope for this change",
        ],
        "links": ["https://quarkus.io/version/3.27/guides/rest#content-types",
                  "https://quarkus.io/version/3.27/guides/http-reference#filters"],
    }


def response_advice(diffs: list[str], path: str) -> dict[str, Any]:
    """The controller card's exit conditions for a response difference, and —
    when the diffs describe a REDIRECT — ADR-016's ruling on it.

    A redirect is the source's own status and its literal Location with the
    origin mapped and nothing else changed. The root-path property already
    carries its slashes, so a root path prepended to a value that already had
    it leaves a doubled segment; the diff itself shows which."""
    parsed = [parse_parity_diff(d) for d in diffs]
    status = next((p for p in parsed if p["kind"] == "status"), None)
    location = next((p for p in parsed if p["kind"] == "header" and p["name"].lower() == "location"), None)
    quoted = "; ".join(p["raw"] for p in parsed) or "no recorded diff"
    out: dict[str, Any] = {
        "description": "the destination's response differs from the source's at this entry point; repair the operation, not the measurement",
        "diffs": [p["raw"] for p in parsed],
        "links": list(REDIRECT_LINKS),
    }
    redirect = bool(location) or bool(status and (str(status["have"]).startswith("3") or str(status["want"]).startswith("3")))
    if not redirect:
        out["exit"] = ["this scenario's own parity verdict comes back PASS with every diff gone: %s" % quoted]
        out["refused"] = [
            "normalizing the difference away in the corpus or the comparator instead of repairing the behaviour",
            "an expectation taken from anywhere but the captured source response",
        ]
        return out

    exit_conditions: list[str] = []
    refused = [
        "another redirect status because it is 'also a redirect': the source's status is the expectation",
        "following the redirect during parity, or comparing the page it lands on instead of the first response",
        "normalizing this difference away in the corpus or the comparator",
        "a compatibility address that answers 404 or an error: a dead URL is not a redirect",
        "restoring the documentation framework the migration retired",
    ]
    if status:
        exit_conditions.append("the request answers %s, the status the SOURCE answered; the destination answers %s today."
                               % (status["want"], status["have"]))
    if location:
        want, have, raw = location["want"], location["have"], location["source"]
        exit_conditions.append(
            "the Location is exactly %s — the source's own Location (%s) with the ORIGIN mapped and nothing else changed: no "
            "re-rooting, no normalization, no trailing-slash edit. The destination sends %s today."
            % (want, raw or want, have))
        doubled = _doubled_segment(have)
        if doubled and not _doubled_segment(want):
            exit_conditions.append(
                "the destination's Location repeats the segment %r. The root-path property already carries its slashes, so a "
                "value that is built on top of it must not include it a second time; the doubling is the defect, not the path."
                % doubled)
        target = _url_path(want)
        if any(tok in target.lower() for tok in _DOC_UI_TOKENS):
            exit_conditions.append(
                "%s is live in the PACKAGED production artifact: the replacement UI is included in the package "
                "(quarkus.swagger-ui.always-include=true) and addressed at that legacy path (quarkus.swagger-ui.path matching "
                "%s, written without repeating the root path), so the legacy address serves or redirects to it."
                % (target, target))
            exit_conditions.append(
                "a bounded navigation check from the packaged artifact reaches the real UI and the OpenAPI document; the "
                "address existing in configuration is not the same as it answering.")
            out["links"] = DOC_UI_LINKS + list(REDIRECT_LINKS)
    exit_conditions.append(
        "a property change lives in %s, outside this card's write set (%s): record it with amend-scope.py --path <file> "
        "--reason <why> BEFORE editing it." % (APP_PROPERTIES, path or GLOBAL))
    exit_conditions.append("this scenario's own parity verdict comes back PASS with every diff gone: %s" % quoted)
    out["description"] = ("the destination's redirect differs from the source's; the source's status and its literal Location "
                          "after origin mapping only are the expectation")
    out["exit"] = exit_conditions
    out["refused"] = refused
    return out


PARITY_RECEIPT = PARITY_DIR / "receipt.json"
PARITY_RECEIPT_SCHEMA = "rhoai3.parity-receipt/v1"


# every kind of parity obligation parity_items mints, so a later receipt can be
# asked about any of them by id
PARITY_KINDS = ("response", "cors", "navigation", "representation")


def parity_obligation_id(entry_point: str, scenario: str, what: str) -> str:
    """The identity of a parity obligation: the entry point, the scenario that
    measured it (empty for a read oracle) and WHICH of the two kinds of diff it
    carries. Line-free and message-free like every other obligation identity
    here, so a comparator that rewords its diff reports the same obligation."""
    return "parity:%s" % sha256_bytes(canonical_bytes({"ep": entry_point, "scenario": scenario, "what": what}))[:16]


def load_parity_receipt(root: Path) -> dict[str, Any]:
    p = Path(root) / PARITY_RECEIPT
    if not p.is_file():
        return {}
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def parity_state(receipt: dict[str, Any] | None) -> dict[str, Any]:
    """What a COMPOSED parity receipt says, keyed the way acceptance asks it.

    ``known`` is the measurement contract applied to parity: a receipt that was
    never composed (absent, another schema, no entry point row) measured
    nothing, and an unmeasured parity slot can neither discharge an obligation
    nor prove that no other scenario regressed.

    ``obligations`` inverts the receipt into the ids ``parity_items`` would mint
    from it: the id is a function of (entry point, scenario, kind), so an issued
    obligation can be looked up in a LATER receipt without anyone having
    recorded what it was made of. A scenario's verdict is the verdict of the
    entry point row that declares it -- the row is PASS only when every required
    scenario of that entry point passed (compose-parity-receipt.py)."""
    rows = (receipt or {}).get("entry_points") if isinstance(receipt, dict) else None
    if (not isinstance(receipt, dict) or str(receipt.get("schema") or "") != PARITY_RECEIPT_SCHEMA
            or not isinstance(rows, list) or not rows):
        return {"known": False, "verdict": "", "entry_points": {}, "scenarios": {}, "obligations": {}}
    eps: dict[str, str] = {}
    scen: dict[str, str] = {}
    obl: dict[str, dict[str, str]] = {}
    nav_failed = {str(r.get("entry_point") or "") for r in navigation_rows(receipt) if str(r.get("verdict") or "") == "FAIL"}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ep = str(row.get("entry_point") or "")
        if not ep:
            continue
        verdict = str(row.get("verdict") or "")
        eps[ep] = verdict
        names = [str(s) for s in (row.get("scenarios") or []) if str(s)]
        for sid in names:
            scen[sid] = verdict
        # "" is the read-oracle obligation of this entry point: the comparison
        # that replays a method and a path, which declares no scenario.
        for sid in sorted(set(names) | {""}):
            for what in PARITY_KINDS:
                v = verdict
                if what == "navigation" and (ep in nav_failed or str(row.get("navigation") or "") == "failed"):
                    v = "FAIL"  # the first response PASSes; the redirect target does not answer
                obl[parity_obligation_id(ep, sid, what)] = {"entry_point": ep, "scenario": sid,
                                                            "what": what, "verdict": v}
    return {"known": True, "verdict": str(receipt.get("verdict") or ""),
            "entry_points": eps, "scenarios": scen, "obligations": obl}


def navigation_rows(receipt: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The receipt's NAVIGATION obligations: ``navigation_obligations[]`` (the
    composer's field: kind navigation, verdict FAIL, entry_point, reason,
    navigation_failures, scenarios), and -- for a receipt composed before it
    existed -- entry-point rows of kind navigation. One per entry point."""
    if not isinstance(receipt, dict):
        return []
    out: dict[str, dict[str, Any]] = {}
    for row in list(receipt.get("navigation_obligations") or []) + [
            r for r in (receipt.get("entry_points") or []) if isinstance(r, dict) and str(r.get("kind") or "") == "navigation"]:
        if isinstance(row, dict) and str(row.get("entry_point") or "") and str(row.get("entry_point")) not in out:
            out[str(row["entry_point"])] = row
    return [out[k] for k in sorted(out)]


PARITY_UNMEASURED = "UNMEASURED"
REFRESH_PARITY = ".hermes/skills/migration/fix-until-green/scripts/refresh-accepted-parity.py"


def parity_unmeasured(receipt: dict[str, Any] | None) -> str:
    """Why the accepted parity baseline describes no tree at all ("" when it
    does): an Operator step or a rewind changed the product after the last
    comparison, so the receipt it would have frozen was another tree's."""
    if isinstance(receipt, dict) and str(receipt.get("verdict") or "") == PARITY_UNMEASURED:
        return str((receipt.get("unmeasured") or {}).get("reason") or "the accepted tree's parity was never measured")
    return ""


def _sid(s: Any) -> str:
    v = str(s or "")
    return v[3:] if v.startswith("sc:") else v


class _WholePhase(frozenset):
    """The re-measured set of a comparison that compared EVERYTHING: every
    scenario id and every entry point is in it. Iterates as empty (nothing to
    name), is truthy, and prints as itself."""

    def __contains__(self, item: object) -> bool:  # noqa: D401
        return True

    def __bool__(self) -> bool:
        return True

    def __repr__(self) -> str:
        return "PARITY_WHOLE_PHASE"


PARITY_WHOLE_PHASE: frozenset = _WholePhase()


def parity_discharge_scope(run: dict[str, Any] | None) -> set[str] | frozenset | None:
    """What an obligation's own record may be judged against: the scoped
    run's set, PARITY_WHOLE_PHASE when the comparison RAN unscoped (every
    record is this run's), None when it did not run."""
    par = (((run or {}).get("runtime") or {}).get("parity") or {}) if isinstance(run, dict) else {}
    if not par.get("ran"):
        return None
    scoped = parity_remeasured(run)
    return scoped if scoped is not None else PARITY_WHOLE_PHASE


def parity_remeasured(run: dict[str, Any] | None) -> set[str] | None:
    """What THIS verification's comparison re-ran, when it was scoped
    (run.json runtime.parity): the scenario ids (``scenarios``, without their
    ``sc:`` prefix) and the ENTRY POINTS whose read oracle the scoped run
    re-ran for the card (``read_oracles_rerun``, H3: their ``ep:`` ids, which
    no scenario id shares). None when it compared the whole phase (or did not
    run), which leaves every row to be judged.

    A read-oracle obligation names no scenario, so the entry point is the only
    identity a re-measurement of it can be counted under (dest v9 t_4d75569c:
    with the read oracles skipped, the entry point's FAIL record stayed as the
    baseline had it and the obligation could never be discharged)."""
    par = (((run or {}).get("runtime") or {}).get("parity") or {}) if isinstance(run, dict) else {}
    if not par.get("ran") or not par.get("scoped"):
        return None
    return ({_sid(x) for x in (par.get("scenarios") or []) if str(x)}
            | {str(e) for e in (par.get("read_oracles_rerun") or []) if str(e)})


def _recompose_partial_row(root: Path, row: dict[str, Any], old: dict[str, Any] | None, remeasured: set[str],
                           before: dict[str, Any]) -> dict[str, Any] | None:
    """H8: an entry point whose scenarios were PARTLY re-run. The composer
    reports it INCONCLUSIVE ("… is bound to receipt …" for every scenario the
    scoped run did not touch), and a row-level carry cannot take it (some of
    its scenarios WERE measured). Recompose it per scenario, by the composer's
    own row rule: a re-run scenario's verdict is its live record, a scenario
    not re-run keeps the accepted baseline's record; any FAIL makes the row
    FAIL (reason: the failures), else any scenario without a usable verdict
    makes it INCONCLUSIVE, else PASS. `carried_scenarios` says which were
    taken from the baseline. None when nothing can be recomposed (no root, or
    a re-run scenario came back without a PASS/FAIL record: that is a
    regression to be judged as composed)."""
    names = [str(s) for s in (row.get("scenarios") or []) if str(s)]
    live_dir, base_dir = Path(root) / PARITY_DIR, Path(root) / LOOP_ACCEPTED / "parity"
    verdicts: list[tuple[str, str, str, bool]] = []  # (sid, verdict, reason, carried)
    for sid in names:
        if _sid(sid) in remeasured:
            rec = scenario_record(live_dir, sid)
            v = str(rec.get("verdict") or "")
            if v not in ("PASS", "FAIL"):
                return None  # a re-run scenario without a verdict is judged as composed, never carried around
            verdicts.append((sid, v, str(rec.get("reason") or ""), False))
        else:
            rec = scenario_record(base_dir, sid)
            v = str(rec.get("verdict") or "")
            if v not in ("PASS", "FAIL"):
                verdicts.append((sid, "INCONCLUSIVE", "the accepted baseline holds no single record of %s" % sid, True))
            else:
                verdicts.append((sid, v, str(rec.get("reason") or ""), True))
    failures = ["%s: %s" % (sid, reason) for sid, v, reason, _c in verdicts if v == "FAIL"]
    gaps = [reason for _sid_, v, reason, _c in verdicts if v == "INCONCLUSIVE"]
    if failures:
        verdict, reason = "FAIL", "; ".join(failures)[:400]
    elif gaps:
        verdict, reason = "INCONCLUSIVE", "; ".join(gaps)[:400]
    else:
        verdict, reason = "PASS", "%d required scenario(s): %s" % (len(names), ", ".join(names))
    out = dict(row, verdict=verdict, reason=reason,
               carried_scenarios=[sid for sid, _v, _r, c in verdicts if c],
               scenario_verdicts={sid: v for sid, v, _r, _c in verdicts},
               carried_from={"receipt_sha256": str(before.get("receipt_sha256") or ""),
                             "binding": dict(before.get("binding") or {}) if isinstance(before.get("binding"), dict) else {},
                             "composed": {"verdict": row.get("verdict"), "reason": str(row.get("reason") or "")[:200]},
                             "per_scenario": True})
    if old is not None and old.get("navigation"):
        out.setdefault("navigation", old.get("navigation"))
    return out


def carry_unmeasured(before: dict[str, Any] | None, after: dict[str, Any] | None,
                     remeasured: set[str] | None, root: Path | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(the receipt acceptance judges, the rows it CARRIED from before).

    A scoped comparison re-runs only the card's own scenarios (and, H3, the
    read oracles of the card's own entry points); the composer then reports
    every other entry point INCONCLUSIVE, because its records are bound to the
    receipt the run started from. That is not a regression and not a
    measurement: such a row is CARRIED from the accepted baseline, marked
    ``carried_from``. Only a row that is INCONCLUSIVE, that names no scenario
    this run re-measured, whose entry point's read oracle this run did not
    re-run, and that the baseline has is carried; a row the run DID re-measure
    -- and every PASS or FAIL -- is judged exactly as composed, so a carry can
    neither turn a FAIL into a PASS nor hide a regression in a re-run scenario
    or read oracle. A whole-phase comparison carries nothing."""
    cur = dict(after or {})
    if remeasured is None or not cur or not isinstance(before, dict) or parity_unmeasured(before):
        return cur, []
    prior = {str(r.get("entry_point") or ""): r for r in (before.get("entry_points") or []) if isinstance(r, dict)}
    rows, carried = [], []
    for r in cur.get("entry_points") or []:
        if not isinstance(r, dict):
            rows.append(r)
            continue
        ep = str(r.get("entry_point") or "")
        names = {_sid(x) for x in (r.get("scenarios") or [])}
        old = prior.get(ep)
        if (str(r.get("verdict") or "") == "INCONCLUSIVE" and not (names & remeasured) and ep not in remeasured
                and old is not None and str(old.get("verdict") or "") in ("PASS", "FAIL")):
            row = dict(old, carried_from={"receipt_sha256": str(before.get("receipt_sha256") or ""),
                                          "binding": dict(before.get("binding") or {}) if isinstance(before.get("binding"), dict) else {},
                                          "composed": {"verdict": r.get("verdict"), "reason": str(r.get("reason") or "")[:200]}})
            rows.append(row)
            carried.append({"entry_point": ep, "verdict": row.get("verdict"), "scenarios": sorted(names)})
            continue
        if (str(r.get("verdict") or "") == "INCONCLUSIVE" and (names & remeasured) and (names - remeasured)
                and root is not None):
            # H8 (v9 t_3c2ed945): a PARTLY re-run entry point -- 7 scenarios,
            # the card's 2 re-run and PASS, 5 bound to the baseline receipt --
            # is recomposed per scenario, never left INCONCLUSIVE to revert a
            # correct repair, and never carried whole (its re-run scenarios
            # are judged from their own records)
            row = _recompose_partial_row(root, r, old, remeasured, before)
            if row is not None:
                rows.append(row)
                carried.append({"entry_point": ep, "verdict": row.get("verdict"), "scenarios": list(row.get("carried_scenarios") or []),
                                "rerun": sorted(names & remeasured), "per_scenario": True})
                continue
        rows.append(r)
    cur["entry_points"] = rows
    if carried:
        cur["carried"] = carried
        moved = {c["entry_point"] for c in carried}
        have = {str(n.get("entry_point") or "") for n in (cur.get("navigation_obligations") or []) if isinstance(n, dict)}
        extra = [dict(n, carried_from=str(before.get("receipt_sha256") or "")) for n in (before.get("navigation_obligations") or [])
                 if isinstance(n, dict) and str(n.get("entry_point") or "") in moved - have]
        if extra:
            cur["navigation_obligations"] = list(cur.get("navigation_obligations") or []) + extra
    return cur, carried


def judged_parity_receipt(root: Path, run: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(the parity receipt the loop reads, the rows carried into it) -- ONE
    answer for the work-list build and for acceptance (G2). After a SCOPED
    comparison the live receipt says INCONCLUSIVE for every entry point it did
    not re-run; the accepted baseline supplies those (carry_unmeasured), so a
    mid-card rebuild keeps the obligations nobody re-measured."""
    root = Path(root)
    live = load_parity_receipt(root)
    if run is None:
        run = load_json(root / VERIFY_RUN) if (root / VERIFY_RUN).is_file() else {}
    remeasured = parity_remeasured(run)
    if remeasured is None or not live:
        return live, []
    before = {}
    for p in (root / LOOP_ACCEPTED / "parity" / "receipt.json", root / VERIFY_DIR / "parity-before.json"):
        if p.is_file():
            try:
                before = load_json(p)
            except (OSError, ValueError):
                before = {}
            break
    return carry_unmeasured(before, live, remeasured, root)


class ParitySplitter:
    """How one scenario verdict's differences divide into obligations (F3,
    ADR-020): (cors, other, representation, withheld?) or None for a diagnostic
    probe. The work-list build and per-obligation acceptance (G1) use the
    same division, so an obligation is judged by exactly its own diffs."""

    def __init__(self, root: Path | None, receipt: dict[str, Any] | None,
                 docs: list[dict[str, Any]] | None = None) -> None:
        self.root = Path(root) if root is not None else None
        self.cross_origin = cors_scenarios(root)
        self.requests = corpus_requests(root)
        cors = (receipt or {}).get("cors") if isinstance(receipt, dict) else None
        outcomes = (cors or {}).get("outcomes") if isinstance(cors, dict) else None
        self.cors_outcomes = outcomes if isinstance(outcomes, dict) else {}
        self._controls: dict[tuple[str, str], set[str]] | None = None
        if docs is not None:
            self._controls = self._index(docs)

    def _index(self, docs: list[dict[str, Any]]) -> dict[tuple[str, str], set[str]]:
        """{(entry point, method): the status diffs its NON-cross-origin FAIL
        verdicts report} -- the controls of H6a's second rule."""
        out: dict[tuple[str, str], set[str]] = defaultdict(set)
        for doc in docs:
            if not isinstance(doc, dict) or str(doc.get("verdict") or "") != "FAIL" or not doc.get("entry_point"):
                continue
            sid = str(doc.get("scenario") or "")
            req = self.requests.get(_sid(sid)) or {}
            if sid and (sid in self.cross_origin or _sid(sid) in self.cross_origin or "sc:" + _sid(sid) in self.cross_origin
                        or req.get("cross_origin") or _CORS_SCENARIO_RE.match(sid)):
                continue
            method = _doc_method(doc, req)
            for d in _split_diffs(str(doc.get("reason") or "")):
                if parse_parity_diff(d)["kind"] == "status":
                    out[(str(doc["entry_point"]), method)].add(d)
        return out

    def controls(self, ep: str, method: str) -> set[str]:
        if self._controls is None:
            docs: list[dict[str, Any]] = []
            pdir = self.root / PARITY_DIR if self.root is not None else None
            if pdir is not None and pdir.is_dir():
                for p in sorted(pdir.glob("*.json")) + sorted((pdir / "scenarios").glob("*.json")):
                    try:
                        docs.append(load_json(p))
                    except (OSError, ValueError):
                        continue
            self._controls = self._index(docs)
        return set(self._controls.get((ep, method), set()))

    def split(self, scenario: str, ep: str, doc: dict[str, Any],
              notes: list[dict[str, Any]] | None = None) -> tuple[list[str], list[str], list[dict[str, Any]], bool] | None:
        notes = [] if notes is None else notes
        reason = str(doc.get("reason") or "")
        co = self.cross_origin
        row_info = co.get(scenario) or co.get(_sid(scenario)) or co.get("sc:" + _sid(scenario)) or {}
        if row_info.get("probe") or (not row_info and _CORS_PROBE_RE.match(scenario)):
            # a diagnostic probe (an authenticated OPTIONS no browser sends)
            # is compared and recorded, and owes no worker anything
            notes.append({"kind": "diagnostic-probe", "scenario": scenario, "entry_point": ep, "reason": reason[:300],
                          "detail": "a diagnostic probe is not browser coverage and mints no obligation (open architect point)"})
            return None
        withheld = False
        cors, other = classify_parity_diffs(reason)
        representation, other = representation_diffs(other)
        method = _doc_method(doc, row_info or self.requests.get(_sid(scenario)))
        cors, other = cors_scenario_split(scenario, doc, co, cors, other, self.controls(ep, method))
        access = str(((self.cors_outcomes.get(scenario) or self.cors_outcomes.get(_sid(scenario)) or {}).get("browser_access") or ""))
        if access == "prevents" and cors:
            # the SOURCE prevents this exchange: a destination that grants no
            # permission either matches it, and no permission is owed. A
            # destination that GRANTS what the source did not is still owed.
            granted = [d for d in cors if parse_parity_diff(d)["kind"] != "header"
                       or str(parse_parity_diff(d)["have"]).strip() not in ("", "None")]
            if len(granted) != len(cors):
                withheld = True
                notes.append({"kind": "cors-prevented", "scenario": scenario, "entry_point": ep,
                              "detail": "the source prevents this exchange; a permission the destination also withholds is not owed",
                              "diffs": [d for d in cors if d not in granted]})
            cors = granted
        effects = [d for d in other if parse_parity_diff(d)["kind"] == "effect"]
        results = doc.get("results") if isinstance(doc.get("results"), dict) else {}
        if effects and str(((results.get("source_effect") or {}) if isinstance(results.get("source_effect"), dict) else {}).get("verdict") or "") == "INCONCLUSIVE":
            # the source's own effect was never observed: what the destination
            # did to the state is a separate result, not a repair card (ADR-020)
            withheld = True
            notes.append({"kind": "source-effect-unobserved", "scenario": scenario, "entry_point": ep, "diffs": effects,
                          "detail": str((results.get("source_effect") or {}).get("reason") or "")[:300]})
            other = [d for d in other if d not in effects]
        return cors, other, representation, withheld

    def own(self, what: str, scenario: str, ep: str, doc: dict[str, Any]) -> list[str]:
        """The diffs of ``doc`` that belong to the obligation kind ``what``."""
        split = self.split(scenario, ep, doc)
        if split is None:
            return []
        cors, other, representation, _w = split
        return {"cors": cors, "response": other, "representation": [str(d.get("raw") or "") for d in representation]}.get(what, [])


def scenario_record(base: Path, scenario: str) -> dict[str, Any]:
    """The one scenario verdict under ``base``/scenarios for ``scenario``, or {}."""
    d = Path(base) / "scenarios"
    if not d.is_dir():
        return {}
    hits = []
    for p in sorted(d.glob("*.json")):
        try:
            doc = load_json(p)
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict) and _sid(doc.get("scenario")) == _sid(scenario):
            hits.append(doc)
    return hits[0] if len(hits) == 1 else {}


def read_oracle_record(base: Path, entry_point: str) -> dict[str, Any]:
    """The one READ-ORACLE verdict under ``base`` for ``entry_point`` (the
    comparator writes it at <slug>.json beside the receipt, schema
    rhoai3.parity/v1; the receipt itself names no entry point), or {}."""
    d = Path(base)
    if not d.is_dir():
        return {}
    hits = []
    for p in sorted(d.glob("*.json")):
        try:
            doc = load_json(p)
        except (OSError, ValueError):
            continue
        if (isinstance(doc, dict) and str(doc.get("entry_point") or "") == entry_point
                and not str(doc.get("scenario") or "")
                and str(doc.get("schema") or "") not in (PARITY_RECEIPT_SCHEMA, "rhoai3.scenario-parity/v1")):
            hits.append(doc)
    return hits[0] if len(hits) == 1 else {}


def parity_obligation_discharged(root: Path, row: dict[str, Any], remeasured: set[str] | None,
                                 receipt: dict[str, Any] | None = None) -> tuple[bool, str]:
    """G1: one obligation of a scenario whose differences F3 split across
    several obligations is discharged by ITS OWN differences being gone from
    the re-run scenario -- never by the scenario passing, which the other
    obligations' differences may still prevent. Strict otherwise: the scenario
    must have been re-run in this comparison, and every difference it still
    reports must be one the accepted baseline already reported, character for
    character (a body digest that moved is a new difference, whichever
    obligation it belongs to).

    H3: a READ-ORACLE obligation (no scenario: the method-and-path replay of
    the entry point) is judged by exactly the same rule over its own record --
    the entry point's read oracle must have been re-run in this comparison
    (``remeasured`` holds its ``ep:`` id), and its own kind of difference must
    be gone from that record with no difference introduced or reworded. A
    record that came back PASS is its own kind gone, for either shape; a
    reworded or persisting difference is not a discharge."""
    sid, what, ep = str(row.get("scenario") or ""), str(row.get("what") or ""), str(row.get("entry_point") or "")
    if what not in ("cors", "response", "representation"):
        return False, "only a scenario or read-oracle verdict can discharge part of itself"
    root = Path(root)
    # ``remeasured`` is the scoped run's set, PARITY_WHOLE_PHASE for a run that
    # compared everything, and None when nothing says what was re-run
    if sid:
        if remeasured is None or _sid(sid) not in remeasured:
            return False, "%s was not re-run in this comparison" % sid
        cur = scenario_record(root / PARITY_DIR, sid)
        prev = scenario_record(root / LOOP_ACCEPTED / "parity", sid)
        name = sid
    else:
        if not ep:
            return False, "the obligation names no entry point"
        if remeasured is None or ep not in remeasured:
            return False, "the read oracle of %s was not re-run in this comparison" % ep
        cur = read_oracle_record(root / PARITY_DIR, ep)
        prev = read_oracle_record(root / LOOP_ACCEPTED / "parity", ep)
        name = "the read oracle of %s" % ep
    if str(cur.get("verdict") or "") == "PASS":
        return True, "%s came back PASS in this comparison" % name
    if str(cur.get("verdict") or "") != "FAIL":
        return False, "%s came back %s" % (name, cur.get("verdict") or "with no single record")
    if str(prev.get("verdict") or "") not in ("FAIL", "PASS"):
        return False, "the accepted baseline holds no single record of %s" % name
    splitter = ParitySplitter(root, receipt)
    own = splitter.own(what, sid, ep, cur)
    if own:
        return False, "its own difference(s) remain: %s" % "; ".join(own)[:200]
    now = set(_split_diffs(str(cur.get("reason") or "")))
    was = set(_split_diffs(str(prev.get("reason") or ""))) if str(prev.get("verdict")) == "FAIL" else set()
    new = sorted(now - was)
    if new:
        return False, "the candidate changed or introduced %s in %s" % ("; ".join(new)[:200], name)
    return True, ("its own difference(s) are gone from the re-run %s; what remains (%s) belongs to other obligations "
                  "and is unchanged" % (name, "; ".join(sorted(now))[:160]))


BODY_DIFF_SHOWN = 5
_PATH_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _body_path_property(path: str) -> str:
    """The last PROPERTY name of a body path ($.pets[0].visits, /pets/0/visits
    -> visits); "" when the path names none."""
    toks = [t for t in _PATH_TOKEN_RE.findall(str(path or "")) if t not in ("root",)]
    return toks[-1] if toks else ""


def body_locus_hints(root: Path | None, body_diff: dict[str, Any]) -> list[dict[str, str]]:
    """Where a body difference may be PRODUCED, when that is cheap to name:
    for an ORDER-only difference at a collection property, the source-model
    getter of that property (the source model is the frozen structure; the
    destination keeps the same relative path). Nothing else is guessed."""
    if not isinstance(body_diff, dict) or not body_diff.get("order_only") or root is None:
        return []
    props = sorted({_body_path_property(d.get("path")) for d in (body_diff.get("differences") or [])
                    if isinstance(d, dict) and str(d.get("kind") or "") == "order"} - {""})
    if not props:
        return []
    out: list[dict[str, str]] = []
    for t in structure_types(Path(root)):
        path = structure_type_path(Path(root), t) or str(t.get("path") or "")
        for m in t.get("methods") or []:
            name = str((m or {}).get("name") or "")
            for prop in props:
                if name == "get" + prop[:1].upper() + prop[1:]:
                    out.append({"property": prop, "type": str(t.get("fqn") or ""), "member": name, "path": path,
                                "why": "the source orders %s in %s.%s; an order-only difference there is produced by "
                                       "that getter's translation, not by the controller" % (prop, t.get("fqn"), name)})
    return sorted(out, key=lambda h: (h["path"], h["member"]))[:3]


def body_diff_advice(root: Path | None, doc: dict[str, Any], item_id: str) -> dict[str, Any]:
    """The structured body difference the comparator recorded, bounded, with
    where its value may come from and how the card may reach that file."""
    bd = doc.get("body_diff") if isinstance(doc.get("body_diff"), dict) else None
    if not bd:
        return {}
    diffs = [d for d in (bd.get("differences") or []) if isinstance(d, dict)]
    hints = body_locus_hints(root, bd)
    out: dict[str, Any] = {
        "kind": str(bd.get("kind") or ""), "summary": str(bd.get("summary") or "")[:400],
        "order_only": bool(bd.get("order_only")), "differences": diffs[:BODY_DIFF_SHOWN],
        "differences_total": len(diffs), "truncated": bool(bd.get("truncated")) or len(diffs) > BODY_DIFF_SHOWN,
        "locus": ("a body difference is often produced OUTSIDE the controller -- a model getter, a mapper, the "
                  "serialization configuration. Read the differing path(s) above, find the file that produces that "
                  "value, and add it to this card's write set BEFORE editing it: python3 "
                  ".hermes/skills/migration/fix-until-green/scripts/amend-scope.py --root . --cluster <this cluster> "
                  "--card $HERMES_KANBAN_TASK --path <that file> --reason <what differs there> --evidence parity:%s"
                  % item_id),
    }
    if hints:
        out["locus_hints"] = hints
    return out


SERVER_ERROR_FRAMES_SHOWN = 5


def server_error_advice(root: Path | None, doc: dict[str, Any], item_id: str, diffs: list[str]) -> dict[str, Any]:
    """H5b: what the destination THREW behind a 5xx, and where.

    The verdict's own status difference says only ``status 500 vs 204``; the
    body the platform answers is an error id. The runner put the exception
    block it found in the destination's log on the verdict (``server_error``,
    bounded), and this turns it into the card's advice: the locus hints are
    the product files the stack's own frames name -- each frame's class
    resolved to a file through the destination model (never a literal) -- and
    the text says the failure is in that file: amend the scope and repair
    there. A verdict whose status difference is not a 5xx the source did not
    answer gets nothing here, whatever the record carries."""
    se = doc.get("server_error") if isinstance(doc.get("server_error"), dict) else None
    if not se:
        return {}
    status = next((parse_parity_diff(d) for d in diffs if parse_parity_diff(d)["kind"] == "status"), None)
    if status is None or not str(status["have"]).startswith("5") or str(status["want"]).startswith("5"):
        return {}
    from planner.server_error import product_file_resolver

    resolve = product_file_resolver(root)
    hints: list[dict[str, Any]] = []
    for f in list(se.get("frames") or [])[:SERVER_ERROR_FRAMES_SHOWN]:
        if not isinstance(f, dict):
            continue
        path = resolve(str(f.get("class") or "")) or str(f.get("file") or "")
        if not path or any(h["path"] == path for h in hints):
            continue
        hints.append({"path": path, "type": str(f.get("class") or ""), "member": str(f.get("method") or ""),
                      "line": int(f.get("line") or 0),
                      "why": "the destination's stack for this request passes through %s.%s (line %s) in this file; the "
                             "frames above it are the platform's" % (f.get("class"), f.get("method"), f.get("line") or "?")})
    exc = str(se.get("exception") or "")
    where = hints[0]["path"] if hints else ""
    out: dict[str, Any] = {
        "status": se.get("status"), "expected_status": se.get("expected_status"),
        "error_id": str(se.get("error_id") or ""), "exception": exc, "message": str(se.get("message") or "")[:300],
        "causes": [c for c in (se.get("causes") or []) if isinstance(c, dict)][:3],
        "matched": str(se.get("matched") or ""), "log": str(se.get("log") or ""), "retained": str(se.get("retained") or ""),
        "stack_sha256": str(se.get("stack_sha256") or ""), "locus_hints": hints,
    }
    if where:
        out["locus"] = (
            "the failure is in %s: the destination answered %s where the source answered %s because %s%s was thrown, and "
            "the first product frame of that stack is %s.%s (line %s). Amend the scope and repair THERE, not in the "
            "controller: python3 .hermes/skills/migration/fix-until-green/scripts/amend-scope.py --root . --cluster "
            "<this cluster> --card $HERMES_KANBAN_TASK --path %s --reason <what throws there> --evidence parity:%s"
            % (where, se.get("status"), se.get("expected_status"), exc or "an exception",
               (": " + out["message"]) if out["message"] else "",
               hints[0]["type"], hints[0]["member"], hints[0]["line"] or "?", where, item_id))
    elif exc:
        out["locus"] = (
            "the destination answered %s where the source answered %s because %s%s was thrown, and none of its frames "
            "resolves to a file of this tree (retained: %s). Read the retained block, name the product file that makes "
            "the failing call, and amend the scope to it with --evidence parity:%s before editing."
            % (se.get("status"), se.get("expected_status"), exc, (": " + out["message"]) if out["message"] else "",
               out["retained"] or out["log"], item_id))
    else:
        out["locus"] = ("the destination answered %s where the source answered %s and its log (%s) holds no exception "
                        "block for this request%s; the failing code is the operation's own path from the controller "
                        "down -- amend the scope to the file that fails, with --evidence parity:%s, before editing it."
                        % (se.get("status"), se.get("expected_status"), out["log"],
                           (": " + str(se.get("note"))) if se.get("note") else "", item_id))
    return out


_EP_ID_RE = re.compile(r"^ep:(?P<type>[^#]+)#(?P<member>.*?)(?::(?P<kind>[a-z]+))?$")
_REQUEST_BODY_ANN = "org.springframework.web.bind.annotation.RequestBody"
_EMPTY_SHA256 = sha256_bytes(b"")


def handler_parameters(root: Path | None) -> dict[str, Any]:
    """compat-mapping.json `handler_parameters`: the controller-method
    parameter kinds the Spring Web compatibility extension DOCUMENTS
    (annotations and types) and the rows for kinds a Spring handler commonly
    declares that the documentation does not list. Every row cites where it
    is documented; {} without a catalog or the block."""
    if root is None:
        return {}
    p = Path(root) / CATALOGS_DIR / "compat-mapping.json"
    if not p.is_file():
        return {}
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return {}
    block = doc.get("handler_parameters") if isinstance(doc, dict) else None
    if not isinstance(block, dict):
        return {}
    return {"note": str(block.get("note") or ""), "source": str(block.get("source") or ""),
            "supported_annotations": [str(x) for x in (block.get("supported_annotations") or [])],
            "supported_types": [str(x) for x in (block.get("supported_types") or [])],
            "undocumented": {str(k): dict(v) for k, v in (block.get("undocumented") or {}).items()
                             if k != "note" and isinstance(v, dict)}}


def _ann_fqns(anns: Any) -> list[str]:
    return [str(a.get("fqn") or a.get("name") or "") for a in (anns or []) if isinstance(a, dict)]


def _same_symbol(a: str, b: str) -> bool:
    """Equal qualified names, or a model's unqualified spelling of one."""
    if not a or not b:
        return False
    return a == b or ("." not in a and a == b.rsplit(".", 1)[-1]) or ("." not in b and b == a.rsplit(".", 1)[-1])


def entry_point_handler(root: Path | None, ep_row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """(the structure type, the method row) an entry point names, resolved
    through M1's structural model by the type and the member the bundle row
    carries (or the id spells: ep:<type>#<member>:<kind>); ({}, {}) when the
    model does not hold them."""
    type_fqn = str(ep_row.get("type") or "")
    member = str(ep_row.get("member") or "")
    if not type_fqn:
        m = _EP_ID_RE.match(str(ep_row.get("id") or ""))
        if m:
            type_fqn, member = m.group("type"), member or m.group("member")
    if not type_fqn:
        return {}, {}
    typ = next((t for t in structure_types(root) if str(t.get("fqn") or "") == type_fqn), None)
    if typ is None:
        return {}, {}
    methods = [m for m in (typ.get("methods") or []) if isinstance(m, dict)]
    name = member.split("(", 1)[0]
    exact = [m for m in methods if member and str(m.get("signature") or "") == member]
    named = [m for m in methods if str(m.get("name") or "") == name]
    hit = exact or named
    return typ, (hit[0] if len(hit) == 1 else {})


def corpus_body_keys(root: Path | None, scenario: str) -> dict[str, Any]:
    """The recorded request body of one corpus scenario, as the top-level keys
    of its JSON object: {file, keys} -- or {file, keys: None, reason} when the
    scenario names a body file this tree does not hold or one that is not a
    JSON object, and {} when the corpus does not name a body for it."""
    if root is None or not scenario:
        return {}
    p = Path(root) / SCENARIO_CORPUS
    if not p.is_file():
        return {}
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return {}
    for sc in (doc.get("scenarios") or []) if isinstance(doc, dict) else []:
        if not isinstance(sc, dict) or _sid(str(sc.get("id") or "")) != _sid(scenario):
            continue
        bf = str(sc.get("body_file") or "")
        if not bf:
            return {}
        bp = Path(bf) if Path(bf).is_absolute() else Path(root) / bf
        if not bp.is_file():
            return {"file": bf, "keys": None, "reason": "the corpus names a body file this tree does not hold"}
        try:
            body = json.loads(bp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"file": bf, "keys": None, "reason": "the recorded body is not JSON"}
        if not isinstance(body, dict):
            return {"file": bf, "keys": None, "reason": "the recorded body is not a JSON object"}
        return {"file": bf, "keys": sorted(str(k) for k in body)}
    return {}


OPENAPI_GENERATOR_ARTIFACT = "openapi-generator-maven-plugin"
_PLUGIN_LEAVES = ("generatorName", "library", "inputSpec", "modelPackage", "apiPackage", "output", "skipValidateSpec", "modelNamePrefix", "modelNameSuffix")


def generator_plugin_config(root: Path | None, artifact: str = OPENAPI_GENERATOR_ARTIFACT) -> dict[str, Any]:
    """The build's configuration of one source generator, read from pom.xml
    structurally (expat, with line numbers): the plugin's groupId/artifactId/
    version, the lines of its <plugin> and <configuration> elements, the
    configuration leaves the generator is driven by (generatorName, library,
    inputSpec, …) and its configOptions -- an execution's configuration
    merged over the plugin's. {} without a pom or without the plugin."""
    if root is None:
        return {}
    pom = Path(root) / "pom.xml"
    if not pom.is_file():
        return {}
    import xml.parsers.expat

    parser = xml.parsers.expat.ParserCreate()
    stack: list[str] = []
    text: list[str] = []
    plugins: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    opts_depth = 0

    def _in_plugin() -> bool:
        return cur is not None and "plugin" in stack

    def start(name: str, _attrs: dict) -> None:
        nonlocal cur, opts_depth
        stack.append(name)
        text.clear()
        if name == "plugin" and stack[-2:-1] == ["plugins"]:
            cur = {"line": parser.CurrentLineNumber, "groupId": "", "artifactId": "", "version": "",
                   "configuration_line": 0, "configuration": {}, "configOptions": {}, "config_lines": {}}
        elif cur is not None and name == "configuration":
            # the plugin's own configuration, or an execution's (which wins)
            if stack.count("execution") == 0 or not cur["configuration_line"]:
                cur["configuration_line"] = parser.CurrentLineNumber
        elif cur is not None and name == "configOptions":
            opts_depth = len(stack)

    def end(name: str) -> None:
        nonlocal cur, opts_depth
        value = "".join(text).strip()
        if cur is not None:
            depth = len(stack)
            if name in ("groupId", "artifactId", "version") and stack[-2:-1] == ["plugin"]:
                cur[name] = value
            elif opts_depth and depth == opts_depth + 1:
                cur["configOptions"][name] = value
            elif name in _PLUGIN_LEAVES and "configuration" in stack:
                cur["configuration"][name] = value
                cur["config_lines"][name] = parser.CurrentLineNumber
            if name == "configOptions":
                opts_depth = 0
            if name == "plugin" and stack[-2:-1] == ["plugins"]:
                plugins.append(cur)
                cur = None
        stack.pop()
        text.clear()

    def chars(data: str) -> None:
        text.append(data)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = chars
    try:
        parser.Parse(pom.read_bytes(), True)
    except xml.parsers.expat.ExpatError:
        return {}
    hit = next((p for p in plugins if p["artifactId"] == artifact), None)
    return dict(hit, path="pom.xml") if hit else {}


_MAVEN_PROPS = (("${project.basedir}/", ""), ("${basedir}/", ""), ("${project.build.directory}", "target"),
                ("${project.basedir}", ""), ("${basedir}", ""))


def _spec_path(root: Path, input_spec: str) -> Path | None:
    s = str(input_spec or "").strip()
    for k, v in _MAVEN_PROPS:
        s = s.replace(k, v)
    s = s.lstrip("/") if s.startswith("/") and not Path(s).is_file() else s
    p = Path(s) if Path(s).is_absolute() else Path(root) / s
    return p if p.is_file() else None


def _load_spec(p: Path) -> tuple[Any, str]:
    """(the parsed OpenAPI document, '') or (None, why): JSON, PyYAML when
    importable, else the planner's YAML subset -- never a guess."""
    text = p.read_text(encoding="utf-8", errors="replace")
    # a JSON document is a YAML document: read it as JSON first, whatever the suffix
    try:
        return json.loads(text), ""
    except ValueError as e:
        if p.suffix.lower() == ".json":
            return None, "the spec is not JSON: %s" % e
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text), ""
    except ImportError:
        pass
    except Exception as e:  # noqa: BLE001 - a YAML error of any class is "unreadable", said out loud
        return None, "the spec could not be parsed: %s" % str(e)[:120]
    try:
        from planner.yamlite import loads as _yl

        return _yl(text), ""
    except Exception as e:  # noqa: BLE001
        return None, "the spec could not be parsed by the planner's YAML subset (no PyYAML): %s" % str(e)[:120]


def spec_required_properties(root: Path | None, plugin: dict[str, Any], body_type: str) -> dict[str, Any]:
    """The `required` list of the spec schema a generated model comes from:
    the model's simple name minus the plugin's modelNamePrefix/modelNameSuffix
    (openapi-generator's documented naming), looked up under
    components.schemas (OpenAPI 3) or definitions (Swagger 2), with one level
    of allOf/$ref composition. {spec, schema, required} or {spec, schema,
    required: None, reason}."""
    if root is None or not plugin or not body_type:
        return {}
    cfg = plugin.get("configuration") or {}
    opts = plugin.get("configOptions") or {}
    p = _spec_path(Path(root), str(cfg.get("inputSpec") or ""))
    if p is None:
        return {"spec": str(cfg.get("inputSpec") or ""), "schema": "", "required": None, "reason": "the plugin's inputSpec is not a file of this tree"}
    simple = body_type.rsplit(".", 1)[-1]
    prefix = str(opts.get("modelNamePrefix") or cfg.get("modelNamePrefix") or "")
    suffix = str(opts.get("modelNameSuffix") or cfg.get("modelNameSuffix") or "")
    name = simple
    if prefix and name.startswith(prefix):
        name = name[len(prefix):]
    if suffix and name.endswith(suffix):
        name = name[:-len(suffix)]
    doc, why = _load_spec(p)
    rel = p.relative_to(root).as_posix() if str(p).startswith(str(root)) else str(p)
    if doc is None or not isinstance(doc, dict):
        return {"spec": rel, "schema": name, "required": None, "reason": why or "the spec is not a mapping"}
    schemas = ((doc.get("components") or {}).get("schemas") if isinstance(doc.get("components"), dict) else None) or doc.get("definitions") or {}
    if not isinstance(schemas, dict) or name not in schemas or not isinstance(schemas.get(name), dict):
        return {"spec": rel, "schema": name, "required": None, "reason": "the spec has no schema %s (modelNamePrefix=%r, modelNameSuffix=%r)" % (name, prefix, suffix)}

    def required_of(schema: dict[str, Any], depth: int = 0) -> list[str]:
        req = [str(x) for x in (schema.get("required") or []) if str(x)]
        if depth < 1:
            for part in (schema.get("allOf") or []) if isinstance(schema.get("allOf"), list) else []:
                if isinstance(part, dict):
                    ref = str(part.get("$ref") or "")
                    target = schemas.get(ref.rsplit("/", 1)[-1]) if ref else part
                    if isinstance(target, dict):
                        req += required_of(target, depth + 1)
        return req

    return {"spec": rel, "schema": name, "required": sorted(set(required_of(schemas[name])))}


def _last_issued_routing(root: Path, item_id: str) -> dict[str, Any]:
    """Where THIS obligation was last issued: the issued card, else the newest
    rejected row that carried it -- with its write set. {} when never issued."""
    for p, kind in ((Path(root) / LOOP_ISSUED, "issued"), (Path(root) / LOOP_STEPS, "rejected")):
        if not p.is_file():
            continue
        try:
            doc = load_json(p)
        except (OSError, ValueError):
            continue
        rows = [doc] if kind == "issued" else list(reversed([r for r in (doc.get("rejected") or []) if isinstance(r, dict)]))
        for r in rows:
            items = [str(x) for x in (r.get("items") or [])] or [str(x.get("id") or "") for x in (r.get("loci_before") or []) if isinstance(x, dict)]
            if item_id in items:
                return {"card": str(r.get("card") or r.get("task_id") or ""), "cluster": str(r.get("cluster") or ""),
                        "write_set": [str(w) for w in (r.get("write_set") or [])], "record": kind}
    return {}


def generated_body_binding(root: Path | None, body_type: str, scenario: str, item_id: str = "") -> dict[str, Any]:
    """H7: is the request body type GENERATED, and does its constructor
    require properties the recorded request does not send?

    Deterministic, from the tree: the type's file under a generated-sources
    root (Maven convention, from the model's own generated dirs), its
    constructors' @JsonProperty(required = true) parameters from the compiler
    model, the scenario's recorded body from the corpus, and the generator's
    configuration from pom.xml. The catalog's build_plugins row for that
    generator supplies the option and its documented words. {} for a type that
    is not generated; a generated type whose model or body could not be read
    says so under `inconclusive` and claims nothing."""
    if root is None or not body_type:
        return {}
    from planner.dest_model import DestModelUnavailable, creator_required_properties, generated_type_file, generated_type_model

    gp, gd = generated_type_file(Path(root), body_type)
    if gp is None:
        return {}
    out: dict[str, Any] = {"generated": True, "type": body_type, "generated_path": gp.relative_to(root).as_posix(),
                           "generated_root": gd.relative_to(root).as_posix() if gd else "", "missing_required": [],
                           "required": [], "inconclusive": ""}
    try:
        typ = generated_type_model(Path(root), body_type)
    except DestModelUnavailable as e:
        out["inconclusive"] = "the compiler model of the generated root could not be made: %s" % e
        typ = {}
    if typ:
        creators = creator_required_properties(typ)
        out["required"] = creators["required"]
        out["constructors"] = creators["constructors"]
        if typ.get("unresolved"):
            out["inconclusive"] = "javac reported an attribution error in the generated file; its constructor annotations are partial"
        elif creators["inconclusive"]:
            out["inconclusive"] = "the @JsonProperty on %s could not be resolved to literals" % ", ".join(creators["inconclusive"])
    elif not out["inconclusive"]:
        out["inconclusive"] = "the generated root's model holds no row for %s" % body_type
    body = corpus_body_keys(root, scenario)
    out["body_file"] = str(body.get("file") or "")
    out["body_keys"] = body.get("keys")
    plugin = generator_plugin_config(root)
    out["plugin"] = plugin
    catalog = _build_plugins_catalog(root)
    gen = str((plugin.get("configuration") or {}).get("generatorName") or "")
    row = ((catalog.get("%s:%s" % (plugin.get("groupId") or "org.openapitools", plugin.get("artifactId"))) or {}) if plugin else {}) or (
        catalog.get("org.openapitools:" + OPENAPI_GENERATOR_ARTIFACT) or {})
    grow = ((row.get("generators") or {}).get(gen) or {}) if gen else {}
    out["catalog_row"] = dict(grow, generator=gen, plugin_docs=str(row.get("docs") or ""),
                              option_location=str(row.get("option_location") or "")) if grow else {}
    # H8 routing stability: what the generator EMITS is decided by the pom on
    # disk, not by whatever build last wrote target/ (after a revert the
    # generated sources are the rejected candidate's). The option state in
    # the pom says whether a required-args constructor is expected; when the
    # generated file lacks one the pom did not stop, target/ is stale and the
    # spec's own `required` list is what that constructor enforces.
    opt = (grow.get("required_args_constructor") or {}) if grow else {}
    opt_name, stop_value = str(opt.get("option") or ""), str(opt.get("value_that_stops_it") or "")
    opt_state = str((plugin.get("configOptions") or {}).get(opt_name) or "").strip().lower() if opt_name else ""
    out["option"] = {"name": opt_name, "set_to": opt_state or "", "default": str(opt.get("default") or ""),
                     "stopped": bool(opt_name) and bool(stop_value) and opt_state == stop_value.lower()}
    creator_seen = any(c.get("json_creator") for c in (out.get("constructors") or []))
    out["creator_seen"] = creator_seen
    out["stale_generated"] = False
    out["required_from"] = "generated constructor" if out["required"] else ""
    if not out["required"] and not creator_seen and grow and opt_name and not out["option"]["stopped"] and not out["inconclusive"]:
        # the pom expects the constructor (option at its documented default,
        # or set to anything but the stopping value) and the generated file
        # has none: not this pom's output
        out["stale_generated"] = True
        spec = spec_required_properties(root, plugin, body_type)
        out["spec"] = spec
        if spec.get("required"):
            out["required"] = list(spec["required"])
            out["required_from"] = "spec schema %s (%s)" % (spec.get("schema"), spec.get("spec"))
        elif spec.get("required") == []:
            out["required_from"] = "spec schema %s (%s): no required property" % (spec.get("schema"), spec.get("spec"))
        else:
            out["inconclusive"] = ("target/generated-sources is not this pom's output (no required-args constructor in %s while "
                                   "%s is not %s in pom.xml, default %s) and %s" % (gp.name, opt_name or "the option", stop_value or "off",
                                                                                     opt.get("default") or "?", spec.get("reason") or "the spec could not be read"))
    if body.get("keys") is None:
        out["inconclusive"] = out["inconclusive"] or str(body.get("reason") or "the corpus records no body for this scenario")
    elif out["required"] and not out["inconclusive"]:
        out["missing_required"] = sorted(r for r in out["required"] if r not in set(body["keys"]))
    out["carried_routing"] = {}
    if out["stale_generated"] and not out["missing_required"] and out["inconclusive"] and item_id:
        last = _last_issued_routing(Path(root), item_id)
        if last.get("write_set") == ["pom.xml"]:
            # the last measurement of this obligation (its issued card) put it
            # on pom.xml; a stale target/ is no evidence against that
            out["carried_routing"] = dict(last, reason="target/generated-sources is stale and the spec could not be read; the routing "
                                                        "is the one this obligation was last issued on (%s %s); run-verify.sh regenerates "
                                                        "the sources from the pom on disk" % (last.get("record"), last.get("card")))
    return out


def _build_plugins_catalog(root: Path | None) -> dict[str, Any]:
    if root is None:
        return {}
    p = Path(root) / CATALOGS_DIR / "compat-mapping.json"
    if not p.is_file():
        return {}
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return {}
    block = doc.get("build_plugins") if isinstance(doc, dict) else None
    return {k: v for k, v in block.items() if k != "note" and isinstance(v, dict)} if isinstance(block, dict) else {}


def generated_body_text(gb: dict[str, Any], item_id: str) -> str:
    """The advice for a generated request body type, verbatim from the tree's
    facts and the catalog row -- the FIRST ACTION when properties are missing."""
    plugin = gb.get("plugin") or {}
    cfg = plugin.get("configuration") or {}
    row = gb.get("catalog_row") or {}
    who = ("%s:%s" % (plugin.get("groupId") or "?", plugin.get("artifactId") or "?")) if plugin else "a generator no pom.xml plugin declares"
    settings = ", ".join("%s=%s" % (k, cfg[k]) for k in ("generatorName", "library") if cfg.get(k)) or "generatorName unknown"
    spec = cfg.get("inputSpec") or "an unrecorded spec"
    head = ("the request body type %s is GENERATED by %s (%s) from %s into %s" % (
        gb.get("type"), who, settings, spec, gb.get("generated_path")))
    if gb.get("missing_required"):
        opt = row.get("required_args_constructor") or {}
        text = ("%s; its constructor requires %s (%s), which the "
                "source's recorded request %s does not send (its keys: %s). %s"
                % (head, ", ".join(gb["missing_required"]),
                   ("@JsonProperty(required = true) on a @JsonCreator constructor" if gb.get("creator_seen") else
                    "read from %s: target/generated-sources on disk is another build's output, and the pom on disk does not stop the required-args constructor" % (gb.get("required_from") or "the spec")),
                   gb.get("body_file") or "body", ", ".join(gb.get("body_keys") or []) or "none",
                   row.get("models") or ""))
        if opt:
            text += (" The documented option is `%s` (%s; default %s; %s): set <%s>%s</%s> under the plugin's <configOptions> "
                     "in pom.xml (line %s of the <configuration> at line %s). %s (%s)"
                     % (opt.get("option"), opt.get("description"), opt.get("default"), row.get("option_location") or "configOptions",
                        opt.get("option"), opt.get("value_that_stops_it"), opt.get("option"),
                        plugin.get("configuration_line") or "?", plugin.get("line") or "?", row.get("action") or "", row.get("source") or ""))
        elif row:
            text += " The catalog row for this generator documents no option that stops the required-args constructor (%s); the alternatives it gives: %s" % (
                row.get("source"), "; ".join("%s -- %s" % (o.get("option"), o.get("description")) for o in (row.get("related_options") or [])) or "none")
        else:
            text += (" No catalog row documents this generator's model options: read the generator's official reference and "
                     "cite the option that stops the required-args constructor before editing the pom.")
        if row.get("observation"):
            text += " Observation, not this obligation's: %s" % row["observation"]
        text += (" No controller edit can fix this: the body is refused before the handler. This obligation is on pom.xml "
                 "(a build card; pom.xml is its write set) and is discharged when run-verify.sh re-runs the scenario and it PASSes.")
        return text
    if gb.get("carried_routing"):
        opt = row.get("required_args_constructor") or {}
        return ("%s; %s. The last measurement put this obligation on pom.xml; the documented option is `%s` (%s; default %s): "
                "set <%s>%s</%s> under the plugin's <configOptions> if it is not set yet, then run-verify.sh -- it regenerates the "
                "sources from the pom on disk and re-measures. No controller edit can fix a body refused before the handler. (%s)"
                % (head, gb["carried_routing"].get("reason"), opt.get("option"), opt.get("description"), opt.get("default"),
                   opt.get("option"), opt.get("value_that_stops_it"), opt.get("option"), row.get("source") or ""))
    if gb.get("inconclusive"):
        return "%s; whether its constructor requires properties the request lacks could not be decided: %s. Nothing is claimed about it." % (head, gb["inconclusive"])
    return "%s; its constructor requires %s and the recorded request sends them all, so the generator is not what refuses this body." % (
        head, ", ".join(gb.get("required") or []) or "no property")


VERDICT_REQUEST_BODY = "request body"
VERDICT_SUPPORTED_ANNOTATION = "supported annotation"
VERDICT_SUPPORTED_TYPE = "supported type"
VERDICT_UNDOCUMENTED = "undocumented"
VERDICT_UNDOCUMENTED_NO_ROW = "undocumented (no catalog row: read the guide the block cites)"
VERDICT_NO_CATALOG = "unknown (no compat catalog in this tree)"


def classify_handler_parameter(par: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    """One handler parameter against the catalog's handler_parameters rows:
    name, type, annotations, the verdict (request body / supported annotation
    / supported type / undocumented), every undocumented row it matches --
    by its type or by an annotation it carries -- with the row's note, source
    and action, and ``line``: the whole classification rendered once, so the
    advice carries it verbatim and never says "see the catalog"."""
    ptype, pname, anns = str(par.get("type") or ""), str(par.get("name") or ""), _ann_fqns(par.get("annotations"))
    row: dict[str, Any] = {"name": pname, "type": ptype, "annotations": anns}
    cites: list[dict[str, str]] = []
    for key, rowdoc in catalog.get("undocumented", {}).items():
        by_type = _same_symbol(ptype, key)
        if by_type or any(_same_symbol(a, key) for a in anns):
            cites.append({"catalog": "compat-mapping.json", "block": "handler_parameters.undocumented", "key": key,
                          "kind": str(rowdoc.get("kind") or ("type" if by_type else "annotation")),
                          "matched": "type" if by_type else "annotation",
                          "source": str(rowdoc.get("source") or ""), "note": str(rowdoc.get("note") or ""),
                          "action": str(rowdoc.get("action") or "")})
    supported_ann = [a for a in anns if any(_same_symbol(a, k) for k in catalog.get("supported_annotations", []))]
    if any(_same_symbol(a, _REQUEST_BODY_ANN) for a in anns):
        row["binding"] = VERDICT_REQUEST_BODY
    elif supported_ann:
        row["binding"] = VERDICT_SUPPORTED_ANNOTATION
    elif any(_same_symbol(ptype, k) for k in catalog.get("supported_types", [])):
        row["binding"] = VERDICT_SUPPORTED_TYPE
    elif cites:
        row["binding"] = VERDICT_UNDOCUMENTED
    elif catalog:
        row["binding"] = VERDICT_UNDOCUMENTED_NO_ROW
    else:
        row["binding"] = VERDICT_NO_CATALOG
    if cites:
        row["catalog_rows"] = cites
    ann_txt = (" @" + " @".join(a.rsplit(".", 1)[-1] for a in anns)) if anns else ""
    if row["binding"] == VERDICT_REQUEST_BODY:
        verdict = "request body parameter (%s): @RequestBody is a supported annotation" % ptype
    elif row["binding"] == VERDICT_SUPPORTED_ANNOTATION:
        verdict = "supported annotation (%s)" % ", ".join("@" + a.rsplit(".", 1)[-1] for a in supported_ann)
    else:
        verdict = row["binding"]
    extra = "".join((" -- %s (%s)" % (c["note"], c["source"])) if c["matched"] == "type" else
                    ("; @%s on this parameter is undocumented -- %s (%s)" % (c["key"].rsplit(".", 1)[-1], c["note"], c["source"]))
                    for c in cites)
    row["line"] = "%s %s%s: %s%s" % (ptype, pname, ann_txt, verdict, extra)
    return row


def handler_first_action(params: list[dict[str, Any]], catalog: dict[str, Any], body_type: str,
                         handler_path: str) -> tuple[str, list[str]]:
    """(the ONE first action for this handler, the remaining undocumented kinds
    to repair in the same edit). Derived from the classification and the
    catalog rows' own ``action`` text, in this order: an undocumented parameter
    TYPE (the compat layer binds nothing to it), then an undocumented
    annotation, then -- every kind documented -- the body and content-type
    checks. The engine carries no framework prose beyond what a row states."""
    actions: list[str] = []
    seen: set[str] = set()
    for want_kind in ("type", "annotation"):
        for p in params:
            for c in p.get("catalog_rows") or []:
                if c["matched"] != want_kind or c["key"] in seen:
                    continue
                seen.add(c["key"])
                act = c["action"] or ("no action recorded on the catalog row: read %s and apply what it documents" % c["source"])
                if want_kind == "type":
                    actions.append("an undocumented parameter kind is present: %s (parameter %s) -- %s" % (c["key"], p["name"], act))
                else:
                    actions.append("an undocumented annotation is present: @%s on %s %s -- %s"
                                   % (c["key"].rsplit(".", 1)[-1], p["type"], p["name"], act))
    if actions:
        return actions[0], actions[1:]
    if not params:
        return ("the structure model shows no parameters for this handler: read its signature in %s ONCE, then classify each "
                "parameter against the rows above (supported annotations: %s; supported types: %s)"
                % (handler_path or "the handler file", ", ".join(a.rsplit(".", 1)[-1] for a in catalog.get("supported_annotations", [])) or "?",
                   ", ".join(t.rsplit(".", 1)[-1] for t in catalog.get("supported_types", [])) or "?"), [])
    no_row = [p for p in params if p["binding"] in (VERDICT_UNDOCUMENTED_NO_ROW, VERDICT_NO_CATALOG)]
    if no_row:
        return ("a parameter kind with no catalog row is present: %s -- read the guide the block cites (%s) for that kind and replace "
                "the parameter with what it documents" % (", ".join("%s %s" % (p["type"], p["name"]) for p in no_row),
                                                          catalog.get("source") or "the Spring Web compatibility guide"), [])
    return ("every parameter is a documented kind, so the refusal is in the body's binding or in content negotiation: compare the "
            "request's Content-Type against what the handler consumes, and the JSON shape and constraint annotations of %s "
            "against the body the scenario sends" % (body_type or "the request body type"), [])


def request_rejection_advice(root: Path | None, ep_row: dict[str, Any], doc: dict[str, Any], item_id: str,
                             diffs: list[str], request_row: dict[str, Any] | None = None) -> dict[str, Any]:
    """H6b: a 4xx the destination answered where the source answered 2xx/3xx,
    on a request that CARRIED A BODY -- the shape of a request refused before
    or at the handler boundary (v9 sc:create-owners and its control
    sc:update-owners-1: 400, empty body, no content type, nothing in the log
    at default level). The advice says what the evidence shows and where to
    look: the handler's parameter binding against the compat catalog -- the
    request body parameter, the validation annotations, every parameter kind
    the documentation does not list (from the catalog, resolved through the
    structure model for THIS handler's signature) and the content-type
    negotiation. Locus hints: the handler's file and, when the model shows
    it, the request body parameter's type. Nothing here for a 4xx the source
    answered with a 4xx, for a request without a body, or for a 5xx (that is
    server_error_advice's)."""
    status = next((parse_parity_diff(d) for d in diffs if parse_parity_diff(d)["kind"] == "status"), None)
    if status is None:
        return {}
    have, want = str(status["have"]), str(status["want"])
    if not have.startswith("4") or want[:1] not in ("2", "3"):
        return {}
    req = doc.get("request") if isinstance(doc.get("request"), dict) else {}
    if "body_absent" in req:
        carried = not bool(req.get("body_absent"))
    elif req.get("body_sha256"):
        carried = True
    else:
        carried = bool((request_row or {}).get("has_body"))
    if not carried:
        return {}
    observed = doc.get("observed") if isinstance(doc.get("observed"), dict) else {}
    sample = str(observed.get("body_sample") or "")
    sha = str(observed.get("body_sha256") or "")
    empty = not sample.strip() and sha in ("", _EMPTY_SHA256)
    ctype = ""
    for k, v in ((observed.get("headers") or {}) if isinstance(observed.get("headers"), dict) else {}).items():
        if str(k).lower() == "content-type":
            ctype = str(v or "")
    observed_body = "empty body" if empty else "%s body%s: %s" % (
        str(observed.get("body_kind") or "a"), (" " + ctype) if ctype else "", sample[:120].replace("\n", " "))
    catalog = handler_parameters(root)
    typ, method = entry_point_handler(root, ep_row)
    handler_path = str(ep_row.get("path") or "") or (structure_type_path(root, typ) if typ else "")
    params: list[dict[str, Any]] = []
    body_type = ""
    for par in (method.get("params") or []) if method else []:
        if not isinstance(par, dict):
            continue
        row = classify_handler_parameter(par, catalog)
        if row["binding"] == "request body":
            body_type = body_type or row["type"]
        params.append(row)
    hints: list[dict[str, str]] = []
    if handler_path:
        hints.append({"path": handler_path, "type": str(typ.get("fqn") or ep_row.get("type") or ""),
                      "member": str(method.get("signature") or method.get("name") or ep_row.get("member") or ""),
                      "why": "the handler this entry point names; its parameter list is what the compat layer binds before the body of the method runs"})
    dto = next((t for t in structure_types(root) if body_type and str(t.get("fqn") or "") == body_type), None) if body_type else None
    if dto is not None:
        dto_path = structure_type_path(root, dto)
        if dto_path and all(h["path"] != dto_path for h in hints):
            hints.append({"path": dto_path, "type": str(dto.get("fqn") or ""), "member": "",
                          "why": "the request body parameter's type: its constraint annotations and its JSON shape decide whether the body binds and validates"})
    cited: list[dict[str, str]] = []
    for p in params:
        for c in p.get("catalog_rows") or []:
            if all(c["key"] != x["key"] for x in cited):
                cited.append(c)
    handler_type = str(typ.get("fqn") or ep_row.get("type") or "")
    handler_member = str(method.get("signature") or method.get("name") or ep_row.get("member") or "")
    handler_key = "%s#%s" % (handler_type, handler_member)
    classification = [p["line"] for p in params]
    first, rest = handler_first_action(params, catalog, body_type, handler_path)
    # H7: a GENERATED body type whose constructor requires what the request
    # does not send is the generator's doing, not the handler's: the locus is
    # the plugin configuration in pom.xml and the first action is its option
    gb = generated_body_binding(root, body_type, str(doc.get("scenario") or ""), item_id)
    if gb:
        gb["text"] = generated_body_text(gb, item_id)
        if gb.get("missing_required") or gb.get("carried_routing"):
            rest = [first] + rest
            first = gb["text"]
            plugin = gb.get("plugin") or {}
            pom_hints = [{"path": "pom.xml", "type": "%s:%s" % (plugin.get("groupId") or "", plugin.get("artifactId") or ""),
                          "member": "configuration", "line": int(plugin.get("configuration_line") or 0),
                          "why": "the generator plugin's configuration: the option that stops the required-args constructor goes under its configOptions"}] if plugin else []
            spec = str((plugin.get("configuration") or {}).get("inputSpec") or "")
            if spec:
                pom_hints.append({"path": spec, "type": "", "member": "",
                                  "why": "the spec the body type is generated from: its schema's `required` list is what the constructor enforces (read it; change it only if the source's contract does not require the property either)"})
            pom_hints.append({"path": str(gb.get("generated_path") or ""), "type": body_type, "member": "<init>",
                              "why": "the generated type (READ ONLY: the next build rewrites it); its @JsonCreator constructor is the evidence"})
            hints = pom_hints + hints
    # THE ADVICE, self-contained: the classification of THIS handler's own
    # parameters (name, type, annotations, verdict, the catalog row's note and
    # source) and one first action derived from it. v9 t_d280284d read the
    # controller four times and the catalog never, because the text said
    # "compare ... against the compat catalog" and named no row.
    text = (
        "the destination refused the request before or at the handler boundary (status %s, %s) while the source accepted it "
        "(status %s). Nothing in the destination log at default level explains a 4xx: the answer is in the handler signature, "
        "not in a stack. Handler %s.%s%s. Parameters, classified against the compat catalog's handler_parameters rows%s: %s. "
        "The other boundary check is content-type negotiation: the request's Content-Type against what the handler consumes. "
        "FIRST ACTION: %s"
        % (have, observed_body, want, handler_type or "?", handler_member or "?",
           (" in %s" % handler_path) if handler_path else "",
           (" (%s)" % catalog.get("source")) if catalog.get("source") else "",
           "; ".join(classification) if classification else
           ("the structure model does not show this handler's parameters: read the signature in %s once" % (handler_path or "the handler file")),
           first))
    if rest:
        text += " NEXT, in the same edit: " + " | ".join(rest)
    out: dict[str, Any] = {
        "status": have, "expected_status": want, "observed_body": observed_body, "request_body": True,
        "handler_key": handler_key,
        "classification": classification,
        "first_action": first,
        "next_actions": rest,
        "generated_body": gb,
        "handler": {"type": str(typ.get("fqn") or ep_row.get("type") or ""),
                    "member": str(method.get("signature") or method.get("name") or ep_row.get("member") or ""),
                    "params": params},
        "body_type": body_type, "catalog_rows": cited,
        "catalog_source": catalog.get("source", ""),
        "locus_hints": hints,
        "locus": text + (" Amend the scope to any file outside the write set BEFORE editing it: python3 "
                         ".hermes/skills/migration/fix-until-green/scripts/amend-scope.py --root . --cluster <this cluster> "
                         "--card $HERMES_KANBAN_TASK --path <that file> --reason <what binds there> --evidence parity:%s" % item_id),
    }
    return out


def parity_scenarios_of(receipt: dict[str, Any] | None, entry_point: str, scenario: str) -> list[str]:
    """The scenario ids one obligation is made of: its own when it has one, and
    otherwise the ones the receipt's row for its entry point declares."""
    if scenario:
        return [scenario]
    for row in ((receipt or {}).get("entry_points") or []) if isinstance(receipt, dict) else []:
        if isinstance(row, dict) and str(row.get("entry_point") or "") == entry_point:
            return sorted({str(s) for s in (row.get("scenarios") or []) if str(s)})
    return []


def _source_cors_policies(root: Path) -> list[str]:
    """The CORS policies the FROZEN source declares, as the parity receipt
    recorded them. A missing or unreadable receipt is an empty list: the
    advice then quotes only the diffs, which are always present."""
    p = Path(root) / PARITY_DIR / "receipt.json"
    if not p.is_file():
        return []
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return []
    cors = doc.get("cors") if isinstance(doc, dict) else None
    policies = (cors or {}).get("source_policies") if isinstance(cors, dict) else None
    return [str(x) for x in policies] if isinstance(policies, list) else []


_MAPPING_ANNOTATIONS = {
    "org.springframework.web.bind.annotation.RequestMapping", "org.springframework.web.bind.annotation.GetMapping",
    "org.springframework.web.bind.annotation.PostMapping", "org.springframework.web.bind.annotation.PutMapping",
    "org.springframework.web.bind.annotation.DeleteMapping", "org.springframework.web.bind.annotation.PatchMapping",
    "jakarta.ws.rs.Path", "javax.ws.rs.Path",
}
_MAPPING_SIMPLE = {a.rsplit(".", 1)[-1] for a in _MAPPING_ANNOTATIONS}


def _mapping_paths(annotations: list[dict[str, Any]]) -> list[str]:
    """The URL paths a set of annotations map (value/path attributes of a
    Spring mapping annotation or a JAX-RS @Path), as written."""
    out: list[str] = []
    for a in annotations or []:
        if not isinstance(a, dict):
            continue
        fqn, simple = str(a.get("fqn") or ""), str(a.get("simple") or "")
        if fqn not in _MAPPING_ANNOTATIONS and not (not fqn and simple in _MAPPING_SIMPLE):
            continue
        named = a.get("named") if isinstance(a.get("named"), dict) else {}
        vals = [str(v) for k in ("value", "path") for v in (named.get(k) or [])]
        if not vals and not named:
            vals = [str(v) for v in (a.get("values") or [])]
        out.extend(vals if vals else [""])
    return out


def _norm_url_path(p: str) -> str:
    p = "/" + str(p or "").strip().strip("/")
    return p if p == "/" else p.rstrip("/")


def _served_paths(model: dict[str, Any]) -> dict[tuple[str, str], list[str]]:
    """{(type fqn, member signature): [URL paths]} for every handler a
    model's types declare: the class-level mapping prefix joined with each
    method's mapping paths (a method with no mapping maps nothing)."""
    out: dict[tuple[str, str], list[str]] = {}
    for t in model.get("types") or []:
        if not isinstance(t, dict):
            continue
        prefixes = _mapping_paths(t.get("annotations") or []) or [""]
        for m in t.get("declared") or []:
            if not isinstance(m, dict):
                continue
            leaves = _mapping_paths(m.get("annotations") or [])
            if not leaves:
                continue
            paths = sorted({_norm_url_path(pre.rstrip("/") + "/" + leaf.lstrip("/")) for pre in prefixes for leaf in leaves})
            out[(str(t.get("fqn") or ""), str(m.get("signature") or m.get("name") or ""))] = paths
    return out


def navigation_handlers_added(root: Path, base_ref: str, url_paths: list[str]) -> list[dict[str, Any]]:
    """H11 (v9 t_0527c69b): the handlers this CANDIDATE added at any of the
    navigation's URL paths -- a method with a mapping annotation on one of
    those paths that the accepted tree (``base_ref``) did not declare, or
    declared without that mapping. Structural, from the compiler model of both
    trees; the relative path variants (with and without a leading root
    segment) are compared by their tail so a mapping written without the root
    path is still the same address. [] when nothing was added there; raises
    DestModelUnavailable when either model cannot be made."""
    from planner.dest_model import dest_model, model_at_commit

    wanted = {_norm_url_path(p) for p in url_paths if str(p or "").strip()}
    if not wanted:
        return []
    now, base = _served_paths(dest_model(Path(root))), _served_paths(model_at_commit(Path(root), base_ref))
    path_of = {str(t.get("fqn") or ""): str(t.get("path") or "") for t in (dest_model(Path(root)).get("types") or []) if isinstance(t, dict)}
    hits: list[dict[str, Any]] = []
    for key, paths in now.items():
        before = set(base.get(key) or [])
        for p in paths:
            if p in before:
                continue
            match = next((w for w in wanted if w == p or w.endswith(p) and p != "/" or p.endswith(w) and w != "/"), "")
            if match:
                hits.append({"type": key[0], "member": key[1], "url_path": p, "navigation_path": match,
                             "file": "src/main/java/" + path_of.get(key[0], "") if path_of.get(key[0]) else ""})
    return sorted(hits, key=lambda h: (h["type"], h["member"], h["url_path"]))


def navigation_advice(failures: list[dict[str, Any]], path: str) -> dict[str, Any]:
    """The exit conditions for a redirect the destination answers correctly and
    an address it points at that does not answer at all.

    ADR-016 does not stop at the status and the literal Location: the legacy
    address must also SERVE the replacement UI or redirect to its effective
    address, and a bounded navigation must reach the real UI and a usable
    OpenAPI document in the PACKAGED production artifact without a redirect
    loop. A dead compatibility URL is refused by name. The comparison here
    PASSED -- the first response is the source's -- so nothing about the first
    response is to be changed; what failed is the destination of the redirect.

    Every value quoted is this measurement's own: the target, its path, the
    terminal state and the status the walk ended on."""
    rows = [f for f in (failures or []) if isinstance(f, dict)]
    quoted = "; ".join("%s is %s (%s)" % (str(f.get("target") or ""), str(f.get("terminal") or ""), f.get("final_status"))
                       for f in rows) or "no recorded navigation"
    target = next((str(f.get("target") or "") for f in rows if str(f.get("target") or "")), "")
    target_path = _url_path(target)
    final_diff = next((str(f.get("final_differs") or "") for f in rows if f.get("final_differs")), "")
    exit_conditions = [
        ("the legacy address %s ANSWERS: it serves the replacement UI itself, or redirects to the address that does. "
         "The bounded navigation from it ends %s today." % (target or "the redirect target", quoted)),
        # H11 (v9 t_0527c69b): the fix is CONFIGURATION, documented on the
        # platform, never product code that serves a substitute page
        ("THE FIX IS CONFIGURATION, in %s: `quarkus.swagger-ui.always-include=true` -- \"If this should be included every "
         "time. By default, this is only included when the application is running in dev mode.\" (default false; a "
         "build-time property) -- puts the platform's Swagger UI into the PACKAGED production artifact, where it is served "
         "at ${quarkus.http.non-application-root-path}/swagger-ui (/q/swagger-ui by default) and reads the OpenAPI "
         "document at %s (%s)." % (APP_PROPERTIES, "${quarkus.http.non-application-root-path}/openapi", DOC_UI_LINKS[0])),
        ("`quarkus.swagger-ui.path` -- \"The path where Swagger UI is available. The value / is not allowed as it blocks the "
         "application from serving anything else. By default, this value will be resolved as a path relative to "
         "${quarkus.http.non-application-root-path}.\" (default swagger-ui) -- addresses it at %s when the legacy address "
         "itself must serve it, written WITHOUT repeating the root path (the root-path property already carries its "
         "slashes). Otherwise the legacy address redirects to /q/swagger-ui, as the source-shaped controller already does."
         % (target_path or "the path the source's own Location names")),
        ("NEVER a handler in product code that answers the redirect target with a page of its own (an HTML stub, a "
         "meta-refresh, a second redirect to the OpenAPI document): ADR-016 asks for the REAL UI, and advance.py REVERTS a "
         "candidate that discharges this obligation with a handler it added at the target's path. The target must be "
         "served by the platform's UI or by code that was already there."),
        ("the bounded navigation check reaches the real UI and a usable OpenAPI document from the packaged artifact, "
         "within the hops it allows and without revisiting a URL, and its final page is the kind the source's final page "
         "is (content type and body kind are recorded and compared when the source capture recorded them)."
         + ((" Today: %s." % final_diff) if final_diff else "")),
        ("%s is outside this card's write set (%s): record it FIRST with amend-scope.py --root . --cluster <id> --card "
         "$HERMES_KANBAN_TASK --path %s --reason <the property> --evidence parity:<this obligation id>; the amendment is "
         "granted on this advice (the configuration locus), then add the property line." % (APP_PROPERTIES, path or GLOBAL, APP_PROPERTIES)),
        ("the first response is left exactly as it is: its status and its literal Location after origin mapping still "
         "come back PASS from this entry point's own parity verdict."),
    ]
    return {
        "description": ("the destination answers the redirect as the source did and the address it points at does not "
                        "answer; the legacy address must serve the replacement UI or redirect to its effective address -- "
                        "by configuration (quarkus.swagger-ui.always-include / quarkus.swagger-ui.path), never by a handler "
                        "that serves a substitute page"),
        "navigation": rows,
        "config_locus": APP_PROPERTIES,
        "properties": [{"name": "quarkus.swagger-ui.always-include", "value": "true", "default": "false",
                        "description": "If this should be included every time. By default, this is only included when the application is running in dev mode.",
                        "source": DOC_UI_LINKS[0]},
                       {"name": "quarkus.swagger-ui.path", "value": target_path or "", "default": "swagger-ui",
                        "description": "The path where Swagger UI is available. The value / is not allowed as it blocks the application from serving anything else. By default, this value will be resolved as a path relative to ${quarkus.http.non-application-root-path}.",
                        "source": DOC_UI_LINKS[0]}],
        "locus_hints": [{"path": APP_PROPERTIES, "type": "", "member": "quarkus.swagger-ui.always-include",
                         "why": "the configuration locus: the documented property that puts the platform's Swagger UI into the packaged artifact; amend the scope to this file on this obligation's evidence"}],
        "exit": exit_conditions,
        "refused": [
            "a dead compatibility URL: an address that answers 404 or an error is not a redirect target",
            "a redirect loop, or a chain that never settles within the hops the navigation check allows",
            "restoring the documentation framework the migration retired",
            ("a handler added in product code at the redirect target's path that serves a substitute page (an HTML stub, "
             "a meta-refresh, a redirect to the OpenAPI document): advance.py reverts it by name"),
            ("following the redirect inside the parity comparison, or normalizing the difference away in the corpus or "
             "the comparator: the navigation check is a SEPARATE measurement beside it"),
        ],
        "links": DOC_UI_LINKS + list(REDIRECT_LINKS),
    }


def parity_items(root: Path, bundle: dict[str, Any], notes: list[dict[str, Any]] | None = None,
                 receipt: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Obligations from M4's parity verdicts: the read-oracle verdicts in
    verification/parity/*.json and the SCENARIO verdicts in
    verification/parity/scenarios/*.json.

    One obligation per failed scenario (two scenarios on one entry point are
    two obligations), typed from the verdict's own diffs: CORS diffs become a
    PARITY_CORS obligation owed the source-preserving CORS response adapter
    (ADR-019) -- its locus is the adapter's contract path and its write set adds
    the configuration file; a Content-Type PARAMETER difference becomes its own
    PARITY_CONTENT_TYPE obligation owed the media-type adapter, never part of
    the CORS one; every other diff lands on the entry point's controller. A
    verdict carrying several kinds becomes several. The message carries the
    diffs, so the brief says WHAT differs, not just that something does. The
    parity receipt (a summary, no entry point) is not an obligation and is
    skipped by schema.

    Each obligation also carries ``advice``: the exit conditions the architect
    ruled for its kind, built from THIS verdict's diffs (cors_advice,
    representation_advice, response_advice). The brief hands a worklist item to
    the worker whole, so the advice travels with the card; nothing in it is
    written for a particular specimen -- every value in it is quoted from the
    evidence. An ``owed`` row names the adapter the obligation authorizes:
    contract, type, path, template digest. owed_adapter_units seals it.

    A NAVIGATION failure has no failing verdict file to read: its comparison
    PASSed, and what failed is the separate bounded navigation the composer
    judged. It is reported on the receipt's own entry-point row (verdict FAIL,
    kind ``navigation``), so it is read there and lands at the controller that
    answers the redirect, with ADR-016's exit conditions for a dead target."""
    out: list[dict[str, Any]] = []
    ep_path = {str(e["id"]): str(e.get("path") or "") for e in (bundle.get("entry_points") or [])}
    pdir = root / PARITY_DIR
    if not pdir.is_dir():
        return out
    source_policies = _source_cors_policies(root)
    receipt = judged_parity_receipt(root)[0] if receipt is None else receipt
    notes = [] if notes is None else notes
    docs: list[tuple[Path, dict[str, Any]]] = [(p, load_json(p)) for p in sorted(pdir.glob("*.json"))]
    sdir = pdir / "scenarios"
    if sdir.is_dir():
        docs += [(p, load_json(p)) for p in sorted(sdir.glob("*.json"))]
    splitter = ParitySplitter(root, receipt, [d for _p, d in docs])
    ep_rows = {str(e.get("id") or ""): e for e in (bundle.get("entry_points") or []) if isinstance(e, dict)}
    for p, doc in docs:
        if not isinstance(doc, dict) or str(doc.get("verdict")) != "FAIL":
            continue
        if str(doc.get("schema") or "") not in ("rhoai3.parity/v1", "rhoai3.scenario-parity/v1") or not doc.get("entry_point"):
            continue  # the receipt, or a document that names no operation
        ep = str(doc.get("entry_point") or "")
        scenario = str(doc.get("scenario") or "")
        reason = str(doc.get("reason") or "")
        split = splitter.split(scenario, ep, doc, notes)
        if split is None:
            continue  # a diagnostic probe: noted, owes nothing
        cors, other, representation, withheld = split
        if not cors and not other and not representation:
            if withheld:
                continue  # every difference was withheld, each with its note
            other = [reason or "parity FAIL without a recorded diff"]
        # ``gate`` makes acceptance phase-aware, exactly as it does for
        # packaging and startup: repairing a parity mismatch leaves the
        # compile/test tuple untouched, and the step is accepted because its own
        # gate -- the scenario comparison -- goes from failing to passing.
        # ``scenarios`` is what the gate has to re-run to say so, so the
        # acceptance path can scope the comparison to this card.
        base = {"source": "parity", "kind": "parity", "gate": "parity", "category": "mandatory", "line": 0,
                "entry_point": ep, "scenario": scenario, "verdict_file": p.relative_to(root).as_posix(),
                "scenarios": parity_scenarios_of(receipt, ep, scenario),
                "message_sha256": sha256_bytes(reason.encode("utf-8"))}
        if other:
            locus = ep_path.get(ep) or GLOBAL
            rid = parity_obligation_id(ep, scenario, "response")
            advice = response_advice(other, locus)
            body = body_diff_advice(root, doc, rid) if any(parse_parity_diff(d)["kind"] == "body" for d in other) else {}
            summary = ""
            if body:
                advice["body_diff"] = body
                summary = " Body: %s" % (body["summary"] or "; ".join(
                    "%s %s (%s vs %s)" % (d.get("kind"), d.get("path"), d.get("observed"), d.get("expected"))
                    for d in body["differences"][:2]))
                if body.get("locus_hints"):
                    summary += " Likely produced in %s." % ", ".join("%s (%s)" % (h["path"], h["member"]) for h in body["locus_hints"])
            server_error = server_error_advice(root, doc, rid, other)
            if server_error:
                advice["server_error"] = server_error
                summary += " Server error: %s%s." % (
                    server_error["exception"] or "no exception block in the destination log",
                    (" in %s" % ", ".join("%s (%s.%s:%s)" % (h["path"], h["type"].rsplit(".", 1)[-1], h["member"], h["line"])
                                          for h in server_error["locus_hints"])) if server_error["locus_hints"] else "")
            rejection = request_rejection_advice(root, ep_rows.get(ep) or {"id": ep, "path": locus}, doc, rid, other,
                                                 splitter.requests.get(_sid(scenario)) if scenario else None)
            if rejection:
                advice["request_rejection"] = rejection
                summary += " Refused at the handler boundary: status %s (%s) where the source answered %s; look at %s." % (
                    rejection["status"], rejection["observed_body"], rejection["expected_status"],
                    ", ".join(h["path"] for h in rejection["locus_hints"]) or "the handler")
            row = dict(base, id=rid, path=locus, rule_id="PARITY", cause="response")
            gb = (rejection or {}).get("generated_body") or {}
            if gb.get("missing_required") or gb.get("carried_routing"):
                # H7: the body is refused by a GENERATED type's constructor; the
                # producer is the generator plugin's configuration, so the
                # obligation is a BUILD item on pom.xml (write set pom.xml at
                # formation -- amend-scope never grants the build file) that
                # keeps its parity gate: the comparison still decides it
                plugin = gb.get("plugin") or {}
                row.update(path="pom.xml", kind="build", rule_id=RULE_PARITY_GENERATED_BODY, cause=GENERATED_BODY_CAUSE,
                           line=int(plugin.get("configuration_line") or plugin.get("line") or 0),
                           generated_type=str(gb.get("type") or ""), missing_required=list(gb["missing_required"]))
                summary = (" Generated body type %s requires %s, which the recorded request does not send: the generator's configuration in pom.xml is the locus, not the controller." % (
                    gb.get("type"), ", ".join(gb["missing_required"])) if gb.get("missing_required") else
                    " Generated body type %s: %s" % (gb.get("type"), (gb.get("carried_routing") or {}).get("reason")))
            out.append(dict(row,
                            detail=("%s: %s" % (scenario or ep, "; ".join(other)))[:200],
                            message=("%s differs from the source (%s): %s.%s" % (ep, scenario or "read oracle", "; ".join(other), summary))[:1200],
                            advice=advice))
        if cors:
            owed = _adapters.contract(_adapters.CORS)
            out.append(dict(base, id=parity_obligation_id(ep, scenario, "cors"), path=owed["path"], kind="config",
                            rule_id=RULE_PARITY_CORS, cause=CORS_CAUSE, owed=owed,
                            detail=("%s: CORS %s" % (scenario or ep, "; ".join(cors)))[:200],
                            message=("%s (%s): the destination does not reproduce the source's cross-origin behaviour (ADR-020: the complete "
                                     "response of a cross-origin scenario is compared; stricter is still a difference): %s. "
                                     "ADR-019: install the source-preserving CORS response adapter and its configuration "
                                     "through the capability (%s), which renders every permission from the SOURCE policy "
                                     "and writes %s and %s; the platform answers a preflight before any endpoint, so a "
                                     "controller change cannot reach it. Do not restore a removed @CrossOrigin; do not "
                                     "widen the policy to make a capture pass."
                                     % (ep, scenario or "read oracle", "; ".join(cors), owed["install"], owed["path"],
                                        owed["config"]))[:1200],
                            advice=cors_advice(cors, source_policies, root)))
        if representation:
            owed = dict(_adapters.contract(_adapters.MEDIA_TYPE),
                        differences=[{k: d[k] for k in ("media_type", "extra", "missing")} for d in representation])
            raws = "; ".join(str(d["raw"]) for d in representation)
            out.append(dict(base, id=parity_obligation_id(ep, scenario, "representation"), path=owed["path"], kind="config",
                            rule_id=RULE_PARITY_CONTENT_TYPE, cause=REPRESENTATION_CAUSE, owed=owed,
                            detail=("%s: %s" % (scenario or ep, raws))[:200],
                            message=("%s (%s): the destination's Content-Type differs from the source's only in its "
                                     "parameters: %s. ADR-019: a response-representation obligation of its own; prefer "
                                     "response or serializer configuration, otherwise the media-type adapter removes only "
                                     "the decided parameter (%s)." % (ep, scenario or "read oracle", raws, owed["install"]))[:1200],
                            advice=representation_advice(representation)))
    # obligations whose body differences point at the SAME producing file are
    # likely one root cause: each names the others (they stay separate cards)
    by_locus: dict[str, list[str]] = defaultdict(list)
    for it in out:
        for key in ("body_diff", "server_error", "request_rejection"):
            for h in ((it.get("advice") or {}).get(key) or {}).get("locus_hints") or []:
                by_locus[h["path"]].append(it["id"])
    for it in out:
        for key in ("body_diff", "server_error", "request_rejection"):
            bd = (it.get("advice") or {}).get(key) or {}
            same = sorted({o for h in bd.get("locus_hints") or [] for o in by_locus.get(h["path"], []) if o != it["id"]})
            if same:
                bd["same_locus_obligations"] = same
    # The receipt's own navigation verdicts: a comparison that PASSed and a
    # redirect target that is dead, loops, or never settles within the bounded
    # walk (ADR-016). There is no FAILing verdict file for these -- the
    # comparison passed, by design -- so the row is the evidence.
    for row in navigation_rows(receipt):
        if str(row.get("verdict") or "") != "FAIL":
            continue
        ep = str(row.get("entry_point") or "")
        if not ep:
            continue
        reason = str(row.get("reason") or "")
        fails = [f for f in (row.get("navigation_failures") or []) if isinstance(f, dict)]
        locus = ep_path.get(ep) or GLOBAL
        out.append({"source": "parity", "kind": "parity", "gate": "parity", "category": "mandatory", "line": 0,
                    "entry_point": ep, "scenario": "", "verdict_file": PARITY_RECEIPT.as_posix(),
                    "scenarios": sorted({str(x) for x in (row.get("scenarios") or []) if str(x)}) or parity_scenarios_of(receipt, ep, ""),
                    "message_sha256": sha256_bytes(reason.encode("utf-8")),
                    "id": parity_obligation_id(ep, "", "navigation"), "path": locus,
                    "rule_id": "PARITY", "cause": "redirect-target-dead",
                    "detail": ("%s: redirect target %s" % (ep, reason))[:200],
                    "message": ("%s answers the redirect the source answers, and the address it points at does not: %s. "
                                "ADR-016 asks for more than the status and the literal Location -- that legacy address "
                                "must serve the replacement UI or redirect to its effective address, and a bounded "
                                "navigation must reach the real UI and a usable OpenAPI document in the PACKAGED "
                                "production artifact without a redirect loop. Do not change the first response: it is "
                                "already the source's." % (ep, reason))[:1200],
                    "advice": navigation_advice(fails, locus)})
    return out


def surefire_from_reports(reports_dir: Path, test_root: Path | None = None) -> dict[str, Any]:
    """Parse surefire XML reports (ElementTree) into a canonical summary.
    ``ran`` is false when there are no reports: no report never means green."""
    failures: list[dict[str, Any]] = []
    tests = 0
    files = 0
    for p in sorted(Path(reports_dir).glob("TEST-*.xml")) if Path(reports_dir).is_dir() else []:
        files += 1
        try:
            tree = ET.parse(p)
        except ET.ParseError:
            failures.append({"classname": p.stem, "name": "(unparseable report)", "message": "surefire report is not XML", "path": ""})
            continue
        for tc in tree.getroot().iter("testcase"):
            tests += 1
            failed = None
            for tag in ("failure", "error"):
                el = tc.find(tag)
                if el is not None:
                    failed = el
                    break
            if failed is None:
                continue
            classname = str(tc.get("classname") or "")
            rel = "src/test/java/" + classname.replace(".", "/") + ".java"
            path = rel if (test_root is None or (test_root / rel).is_file()) else ""
            failures.append({"classname": classname, "name": str(tc.get("name") or ""), "message": str(failed.get("message") or "")[:300], "path": path})
    return {"schema": "rhoai3.surefire/v1", "reports": files, "tests": tests, "ran": files > 0, "failures": sorted(failures, key=lambda f: (f["classname"], f["name"]))}


# ---------------------------------------------------------------------------
# ordering
# ---------------------------------------------------------------------------


def file_depths(bundle: dict[str, Any]) -> dict[str, int]:
    """Leaf-first dependency depth per source file from the JDK model."""
    types = {str(t["fqn"]): t for t in (bundle.get("structure") or {}).get("types") or []}
    memo: dict[str, int] = {}

    def depth(fqn: str, stack: tuple[str, ...]) -> int:
        if fqn in memo:
            return memo[fqn]
        if fqn in stack:
            return 0
        refs = [str(r) for r in (types[fqn].get("type_refs") or []) if str(r) in types and str(r) != fqn]
        d = 0 if not refs else 1 + max(depth(r, stack + (fqn,)) for r in refs)
        memo[fqn] = d
        return d

    out: dict[str, int] = {}
    for fqn, t in types.items():
        path = str(t.get("path") or "")
        if not path:
            continue
        out[path] = min(out.get(path, UNKNOWN_DEPTH), depth(fqn, ()))
    return out


def _profile_of(path: str) -> str:
    """'hsqldb' for src/main/resources/application-hsqldb.properties, '' otherwise."""
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    if name.startswith("application-") and name.rsplit(".", 1)[-1] in ("properties", "yml", "yaml"):
        return name[len("application-"):].rsplit(".", 1)[0]
    return ""


SYMBOL_CLUSTER_MAX_FILES = 8
_SYM_RE = re.compile(r"symbol:\s+(?:class|variable|method|interface|enum)\s+([A-Za-z_$][\w$]*)")
_PKG_RE = re.compile(r"package ([\w.]+) does not exist")


def compile_token(item: dict[str, Any]) -> str:
    """The unresolved name a compile item is about (symbol or package), or ''."""
    if item.get("source") != "javac" or item.get("kind") != "compile":
        return ""
    msg = str(item.get("message") or item.get("detail") or "")
    m = _SYM_RE.search(msg) or _PKG_RE.search(msg)
    return m.group(1) if m else ""


def cluster_items(items: list[dict[str, Any]], depths: dict[str, int], deferred: set[str],
                  *, units: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    # Units (form_units, decisions.loop.unit_formation == "v1") claim their
    # items BEFORE the symbol-group and per-file passes; with none the
    # clustering below is byte-for-byte what it was, which is what lets the
    # former ship without disturbing a run that is already under way.
    units = list(units or [])
    taken: set[str] = {i for c in units for i in (c.get("items") or [])}
    # Compile items that are the same unresolved name in several files are one
    # obligation, not one per file: they get one card whose write set lists the
    # files (capped, so a card stays one model turn). Pilot v6: 829 errors were
    # 73 per-file cards; the same Spring symbol (DataAccessException ×124,
    # @Profile ×58, @Transactional ×36) recurs across most of them.
    by_token: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in items:
        tok = compile_token(it)
        if tok and it["id"] not in taken:
            by_token[tok].append(it)
    symbol_groups: list[tuple[str, list[dict[str, Any]]]] = []
    for tok in sorted(by_token):
        rows = [r for r in by_token[tok] if r["id"] not in taken]
        files = sorted({r["path"] for r in rows})
        if len(files) < 2:
            continue
        for i in range(0, len(files), SYMBOL_CLUSTER_MAX_FILES):
            chunk = set(files[i:i + SYMBOL_CLUSTER_MAX_FILES])
            part = [r for r in rows if r["path"] in chunk]
            label = tok if len(files) <= SYMBOL_CLUSTER_MAX_FILES else "%s#%d" % (tok, i // SYMBOL_CLUSTER_MAX_FILES + 1)
            symbol_groups.append((label, part))
            taken.update(r["id"] for r in part)
    by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in items:
        if it["id"] not in taken:
            by_path[it["path"]].append(it)
    clusters: list[dict[str, Any]] = list(units)
    for label, its in symbol_groups:
        its = sorted(its, key=lambda i: i["id"])
        files = sort_unique([i["path"] for i in its])
        cid = "c:%s" % sha256_bytes(("symbol:" + label).encode("utf-8"))[:12]
        clusters.append({
            "id": cid,
            "path": files[0],
            "label": label,
            "kind": "compile",
            "items": [i["id"] for i in its],
            "order_key": [KIND_RANK["compile"], min(depths.get(f, UNKNOWN_DEPTH) for f in files), files[0]],
            "status": "deferred" if cid in deferred else "open",
            "write_set": files,
            "block": "",
        })
    for path in sorted(by_path):
        its = sorted(by_path[path], key=lambda i: i["id"])
        kind = min((i["kind"] for i in its), key=lambda k: KIND_RANK[k])
        cid = "c:%s" % sha256_bytes(path.encode("utf-8"))[:12]
        if path == GLOBAL:
            write_set = ["pom.xml"]
        elif path_class(path) == "test":
            # tests judge the migration; they are never in a write set. The
            # production twin (src/main mirror of the test path) is the scope
            # when it exists in the model; otherwise the cluster is a typed
            # blocker (empty write set) for a human/ADR.
            twin = path.replace("src/test/java/", "src/main/java/", 1)
            for suffix in ("Test.java", "Tests.java", "IT.java"):
                if twin.endswith(suffix):
                    twin = twin[: -len(suffix)] + ".java"
                    break
            write_set = [twin] if twin in depths else []
        elif path_class(path) == "config" and _profile_of(path):
            # a Spring profile file (application-<profile>.properties): the
            # documented fix (springboot-properties-to-quarkus-00001, Quarkus
            # config guide) moves its keys into the single application.properties
            # under a %<profile>. prefix and removes the file, so the sibling
            # main file is in scope too (pilot v6 t_e6fa0117: the worker could
            # only edit the profile file itself and the incident stayed)
            write_set = sort_unique([path, path.rsplit("/", 1)[0] + "/application." + path.rsplit(".", 1)[-1]])
        else:
            write_set = sort_unique([path] + (["pom.xml"] if kind == "build" and path != "pom.xml" else []))
        clusters.append({
            "id": cid,
            "path": path,
            "kind": kind,
            "items": [i["id"] for i in its],
            "order_key": [KIND_RANK[kind], depths.get(path, UNKNOWN_DEPTH) if kind == "compile" else 0, path],
            "status": "deferred" if cid in deferred else ("blocked" if not write_set else "open"),
            "write_set": write_set,
            "block": "" if write_set else "no production scope can be derived for this locus; a human or ADR must own it (tests are never writable)",
        })
    clusters.sort(key=lambda c: (c["order_key"][0], c["order_key"][1], c["order_key"][2]))
    return clusters


def measure_of(items: list[dict[str, Any]], *, incidents_known: bool, compile_known: bool, tests_known: bool, parity_known: bool, blocked: list[str] | None = None) -> dict[str, Any]:
    m: dict[str, Any] = {
        "mandatory_incidents": sum(1 for i in items if i["source"] == "mta" and i["category"] == "mandatory") if incidents_known else None,
        "compile_errors": sum(1 for i in items if i["source"] == "javac") if compile_known else None,
        "failing_tests": sum(1 for i in items if i["source"] == "surefire") if tests_known else None,
        "parity_mismatches": sum(1 for i in items if i["source"] == "parity") if parity_known else None,
    }
    m["tuple"] = [m[k] for k in MEASURE_KEYS]
    m["known"] = all(m[k] is not None for k in MEASURE_KEYS)
    m["blocked"] = list(blocked or [])
    return m


class _Retain(str):
    """A third outcome beside accept and reject: keep the candidate, prove
    nothing, spend no attempt. Truthy comparisons treat it as "not accepted",
    and callers that know about it retain instead of reverting."""

    def __bool__(self) -> bool:  # noqa: D105 - "not accepted"
        return False


# Three ways of "not accepted, not rejected, no attempt spent". They are
# distinct because what happens next is distinct:
RETAIN = _Retain("retain")        # the compiler now names another member of THIS card's sealed family: continue in the same card
UNPROVEN = _Retain("unproven")    # a failing gate no longer names the issued obligation: retain and verify again
EXPOSED = _Retain("exposed")      # the compiler now names something no sealed scope of this card covers: a typed diagnosis


BATCH_SCOPE_DIR = Path("evidence") / "planning" / "batch-scope"


def batch_scope_path(scope: dict[str, Any]) -> Path:
    """Where an inventory lives: under its own digest, so it is immutable.

    A remeasurement of the same repository is a different inventory, not a
    replacement for the one a card was issued against (measured: changing the
    first member and remeasuring on the second rewrote the sealed file, and
    acceptance then refused its own card for a seal mismatch)."""
    return BATCH_SCOPE_DIR / str(scope.get("cluster") or "").replace(":", "-") / ("%s.json" % str(scope.get("digest") or "")[:32])
BATCH_RULE = "spring-data-repository-contract/v1"
CHECKED_FAMILY_RULE = "checked-exception-family/v1"
_DERIVABLE = re.compile(r"^(find|read|get|query|count|exists|stream)\w*By\w+$|^(count|exists)$")
_UNREPORTED = "compiler.err.unreported.exception"


def _repo_type(root: Path, rel: str) -> tuple[dict[str, Any] | None, str]:
    """The compiled type at `rel`, or (None, why-not). Never a guess."""
    try:
        model = dest_model(root)
    except DestModelUnavailable as exc:
        return None, str(exc)
    rows = types_of(model, rel)
    if not rows:
        return None, "the model has no type for %s" % rel
    return rows[0], ""


def unreported_item(item: dict[str, Any]) -> bool:
    """A measured javac diagnostic for an unhandled checked exception."""
    if str(item.get("source") or "") != "javac":
        return False
    code = str(item.get("rule_id") or item.get("code") or "")
    msg = str(item.get("message") or item.get("detail") or "")
    return code.startswith(_UNREPORTED) or "unreported exception" in msg


def introducing_step(root: Path, signature: str, *, limit: int = 12) -> dict[str, Any] | None:
    """The accepted step whose commit first carried unhandled `signature` sites.

    Walked newest first over the recorded step commits, each modelled by the
    compiler under this tree's configuration. The keys are the sites that
    step introduced: the family is bound to THAT transformation, never to
    every constructor of the same class the tree happens to contain (the
    regex inventory swept in sites no step had touched). Raises
    DestModelUnavailable when a commit cannot be modelled."""
    p = Path(root) / LOOP_STEPS
    steps = load_json(p) if p.is_file() else {}
    rows = [r for r in (steps.get("steps") or []) if str(r.get("commit") or "") and not r.get("rewound")][-limit:]
    for i in range(len(rows) - 1, 0, -1):
        after = model_at_commit(root, str(rows[i]["commit"]))
        before = model_at_commit(root, str(rows[i - 1]["commit"]))
        now = {x["key"] for x in unhandled_sites(after) if site_signature(x) == signature and x.get("state") == "unhandled"}
        was = {x["key"] for x in unhandled_sites(before) if site_signature(x) == signature}
        new = sorted(now - was)
        if new:
            return {"commit": str(rows[i]["commit"]), "parent": str(rows[i - 1]["commit"]),
                    "card": str(rows[i].get("card") or ""), "cluster": str(rows[i].get("cluster") or ""), "keys": new}
    return None


def _family_note(members: list[dict[str, Any]], intro: dict[str, Any]) -> str:
    callee = str(members[0].get("callee") or "") if members else ""
    exc = str(members[0].get("exception") or "") if members else ""
    consumers = sorted({str(m.get("consumer") or "") for m in members if m.get("consumer")})
    base = ("Every member listed calls %s, which throws the checked %s, since step %s (card %s). Repair each one so it no "
            "longer calls it -- no throws clause and no catch around it: the repair must not introduce a checked exception. "
            "Keep the operation the value fed (%s)." % (callee, exc, intro["commit"][:12], intro.get("card") or intro.get("cluster") or "?",
                                                         ", ".join(consumers) or "none recorded"))
    if any(c.endswith(".setLocation(java.net.URI)") for c in consumers):
        return ("Source-compatible Location construction without introduced checked exceptions. " + base +
                " The source built an ABSOLUTE Location from the request, under its context path; parity compares that form. "
                "Use a request-aware URI builder that keeps the application base and the source's own path template -- "
                "for example a JAX-RS @Context UriInfo parameter and uriInfo.getBaseUriBuilder().path(<the source's template>)"
                ".build(<id>). URI.create of a relative path compiles and is not the source's form.")
    return base


def build_checked_family_scope(root: Path, cluster: dict[str, Any], items: list[dict[str, Any]], bundle: dict[str, Any]) -> dict[str, Any] | None:
    """A SEALED repair family: the unhandled checked-exception sites ONE
    transformation introduced, as the compiler enumerates them.

    javac reports one such site per compilation, so the cluster it forms names
    one file while the defect may span several. The family is: the measured
    site's signature (callee + exception), the step that introduced it, and
    every site of that signature the step introduced and the tree still has.
    Measured failures stay in item_ids; the other members are inventory, not
    obligations. None when any of that cannot be established -- the cluster
    then stays what javac said it is."""
    measured = [i for i in items if str(i.get("id")) in set(cluster.get("items") or []) and unreported_item(i)]
    if not measured:
        return None
    try:
        model = dest_model(root)
    except DestModelUnavailable:
        return None
    anchors = [a for a in (site_for_diagnostic(model, i) for i in measured) if a is not None]
    if not anchors:
        return None
    signature = site_signature(anchors[0])
    try:
        intro = introducing_step(root, signature)
    except DestModelUnavailable:
        return None
    if intro is None:
        return None
    now = {x["key"]: x for x in unhandled_sites(model) if site_signature(x) == signature and x.get("state") == "unhandled"}
    keys = sorted(set(intro["keys"]) & set(now))
    if not any(a["key"] in keys for a in anchors):
        return None
    members = [{"member": k, "path": now[k]["path"], "type": now[k]["type"], "member_id": now[k]["member_id"],
                "callee": now[k].get("callee"), "exception": now[k].get("exception"),
                "occurrence": int(now[k].get("occurrence") or 0), "consumer": str(now[k].get("consumer") or "")} for k in keys]
    paths = sort_unique([m["path"] for m in members] + [str(i.get("path") or "") for i in measured if i.get("path")])
    doc = {
        "schema": "rhoai3.batch-scope/v3",
        "kind": "repair-family",
        "family": "checked-exception",
        "producer": "worklist.build_checked_family_scope",
        "tool": {"model": "jdk-dest-model", "version": "1.2.0"},
        "rule": CHECKED_FAMILY_RULE,
        "cluster": str(cluster.get("id") or ""),
        "repository": "",
        "signature": signature,
        "family_id": sha256_bytes(("%s@%s" % (signature, intro["commit"])).encode("utf-8"))[:12],
        "introduced_by": {k: intro[k] for k in ("commit", "parent", "card", "cluster")},
        "writable_paths": paths,
        "inputs": {"candidate_sha256": str((bundle or {}).get("candidate_sha256") or "")},
        "members": members,
        "measured": sorted(str(i.get("id")) for i in measured),
        "rule_note": _family_note(members, intro),
    }
    doc["digest"] = batch_scope_digest(doc)
    return doc


def assess_checked_family(root: Path, scope: dict[str, Any]) -> list[dict[str, Any]]:
    """Each family member, from the compiled tree:

    ok            the member no longer calls the checked callee at all, declares
                  no such exception, and still performs the operation the value
                  fed. Whether the replacement reproduces the source's VALUE (an
                  absolute Location under the context path) is parity's question.
    violates      the site is still unhandled; or the callee is still called with
                  its exception caught or declared (that introduces or hides a
                  checked exception instead of removing it); or the consumer is
                  gone (a Location is not repaired by deleting the header); or the
                  member or file is gone.
    inconclusive  the compiler could not resolve the file or decide the site."""
    try:
        model = dest_model(root)
    except DestModelUnavailable as exc:
        return [{"member": "*", "verdict": "inconclusive", "detail": "the destination model is unavailable: %s" % exc}]
    prefix = "src/main/java/"
    types = {(prefix + str(t.get("path") or ""), str(t.get("fqn") or "")): t for t in model.get("types") or []}
    sites = unhandled_sites(model)
    signature = str(scope.get("signature") or "")
    out: list[dict[str, Any]] = []
    for row in scope.get("members") or []:
        member, path, fqn, mid = str(row.get("member")), str(row.get("path") or ""), str(row.get("type") or ""), str(row.get("member_id") or "")
        base = {"member": member, "path": path, "rule": scope.get("rule")}
        if not path or not (Path(root) / path).is_file():
            out.append(dict(base, verdict="violates", detail="the file is gone; a family member is not discharged by deleting its file"))
            continue
        t = types.get((path, fqn))
        if t is None:
            out.append(dict(base, verdict="violates", detail="the type %s is gone from %s" % (fqn, path)))
            continue
        if str(t.get("resolution") or "") != "full":
            out.append(dict(base, verdict="inconclusive", detail="the compiler could not fully resolve %s" % path))
            continue
        here = [x for x in sites if x["path"] == path and x["type"] == fqn and x["member_id"] == mid and site_signature(x) == signature]
        if any(x.get("state") == "unhandled" for x in here):
            out.append(dict(base, verdict="violates", detail="%s still calls %s with %s unhandled" % (mid, row.get("callee"), row.get("exception"))))
            continue
        if here:
            out.append(dict(base, verdict="inconclusive", detail="the compiler could not decide whether the site in %s is handled" % mid))
            continue
        if mid.startswith("<"):
            out.append(dict(base, verdict="ok", detail="no unhandled site remains in %s" % mid))
            continue
        ids = member_ids(t)
        m = next((x for x in t.get("declared") or [] if ids.get(str(x.get("signature") or "")) == mid), None)
        if m is None:
            out.append(dict(base, verdict="violates", detail="the member %s is gone; its operation is not repaired by deleting it" % mid))
            continue
        if str(row.get("callee") or "") in (m.get("calls") or []):
            out.append(dict(base, verdict="violates", detail="%s still calls %s; catching or declaring %s is not the repair -- use a construction that cannot throw it" % (mid, row.get("callee"), row.get("exception"))))
            continue
        if str(row.get("exception") or "") in (m.get("throws_checked") or []):
            out.append(dict(base, verdict="violates", detail="%s now declares %s; the repair must not introduce a checked exception" % (mid, row.get("exception"))))
            continue
        consumer = str(row.get("consumer") or "")
        if consumer and consumer not in (m.get("calls") or []):
            out.append(dict(base, verdict="violates", detail="%s no longer calls %s; the operation the value fed must be preserved" % (mid, consumer)))
            continue
        out.append(dict(base, verdict="ok", detail=("%s no longer calls %s%s; the value it builds is compared by parity" %
                                                   (mid, row.get("callee"), (" and still calls " + consumer) if consumer else ""))))
    return out


def build_batch_scope(root: Path, cluster: dict[str, Any], items: list[dict[str, Any]], bundle: dict[str, Any]) -> dict[str, Any] | None:
    """A SEALED SCOPE INVENTORY for a repository repair: what the card may
    touch, and every member the declared rule applies to.

    The compiler supplies the members, their resolved signatures and what the
    type actually inherits. Nothing here becomes an obligation and nothing
    enters the measure: the measured failure stays in item_ids. What the
    inventory does is make the card's completion checkable — every member is
    assessed against the declared rule, and an already-correct one may stay
    exactly as it is (architect direction C, 2026-09-11).

    A compile card for an unhandled checked exception gets a repair-family
    inventory instead (build_checked_family_scope). Those extra sites are not
    invented diagnostics."""
    if cluster.get("_unit_seal"):
        return build_unit_scope(root, cluster, items, bundle)
    rows = [i for i in items if str(i.get("id")) in set(cluster.get("items") or []) and str(i.get("source")) == "runtime"]
    if not rows:
        return build_checked_family_scope(root, cluster, items, bundle)
    path = str(rows[0].get("path") or "")
    if not path.endswith("Repository.java"):
        return build_checked_family_scope(root, cluster, items, bundle)
    src = Path(root) / path
    if not src.is_file():
        return None
    typ, why = _repo_type(Path(root), path)
    members: list[dict[str, Any]] = []
    if typ is not None:
        for m in typ.get("declared") or []:
            name = str(m.get("name") or "")
            sig = str(m.get("signature") or "")
            if not name or name == "<init>":
                continue
            members.append({
                "member": name,
                "signature": sig,
                "signatures": sorted({str(x.get("signature")) for x in (typ.get("declared") or []) if str(x.get("name")) == name}),
                "ambiguous": sum(1 for x in (typ.get("declared") or []) if str(x.get("name")) == name) > 1,
                "resolution": str(m.get("resolution") or ""),
                "source_refs": _frozen_refs(root, name),
            })
    # What the repository reached AT SEAL TIME. A worker cannot widen its own
    # authority by adding a reference: this list is fixed when the card is
    # issued (measured: an unrelated SecurityConfig became amendable the moment
    # the candidate mentioned it).
    reaches = sorted({str(x) for x in ((typ or {}).get("supertypes") or [])} |
                     {str(r) for m in ((typ or {}).get("declared") or []) for r in (m.get("type_refs") or [])})
    doc = {
        "schema": "rhoai3.batch-scope/v3",
        "reaches": reaches,
        "producer": "worklist.build_batch_scope",
        "tool": {"model": "jdk-dest-model", "version": "1.0.0"},
        "rule": BATCH_RULE,
        "cluster": str(cluster.get("id") or ""),
        "repository": path,
        "type_fqn": str((typ or {}).get("fqn") or ""),
        "supertypes": list((typ or {}).get("supertypes") or []),
        "model_resolution": str((typ or {}).get("resolution") or "unavailable"),
        "model_note": why,
        "writable_paths": sorted(set(cluster.get("write_set") or [path])),
        "inputs": {
            "candidate_sha256": str((bundle or {}).get("candidate_sha256") or ""),
            "repository_sha256": sha256_file(src),
        },
        "members": sorted(members, key=lambda m: (m["member"], m["signature"])),
        "measured": sorted(str(i.get("id")) for i in rows),
    }
    doc["digest"] = batch_scope_digest(doc)
    return doc


def batch_scope_digest(doc: dict[str, Any]) -> str:
    """The seal, recomputed from content. The stored field is a convenience;
    a checker that trusted it would be trusting the file it is checking."""
    return sha256_bytes(canonical_bytes({k: v for k, v in (doc or {}).items() if k != "digest"}))


def _frozen_refs(root: Path, member: str, limit: int = 2) -> list[dict[str, str]]:
    """Where the FROZEN source implemented this member, and its query."""
    out: list[dict[str, str]] = []
    base = Path(root) / ".derived" / "frozen-input" / "src" / "main" / "java"
    if not base.is_dir():
        return out
    rx = re.compile(r"\b%s\s*\(" % re.escape(member))
    for f in sorted(base.rglob("*.java")):
        text = f.read_text(encoding="utf-8", errors="replace")
        m = rx.search(text)
        if not m:
            continue
        body = text[m.start(): m.start() + 900]
        row = {"path": f.relative_to(Path(root) / ".derived" / "frozen-input").as_posix()}
        q = re.search(r'"((?:SELECT|UPDATE|DELETE|INSERT)\s[^"]{4,300})"', body, re.I)
        if q:
            row["query"] = q.group(1)
        out.append(row)
        if len(out) >= limit:
            break
    return out


def assess_batch_scope(root: Path, scope: dict[str, Any]) -> list[dict[str, Any]]:
    """Assess every inventoried member against the declared rule, from the
    compiled tree.

    ok            the member satisfies the contract as it stands (it may be
                  untouched: being already correct is not a defect)
    violates      the member breaks the contract and the card is not finished
    inconclusive  the compiler could not resolve this, so nothing is claimed

    Inspecting a member earns nothing and changing one earns nothing; only the
    assessment counts, and a worker's prose cannot supply it. An inconclusive
    verdict is not a pass: the caller must refuse."""
    if str(scope.get("rule") or "") == CHECKED_FAMILY_RULE:
        return assess_checked_family(root, scope)
    if str(scope.get("kind") or "") == UNIT_KIND:
        return assess_unit(root, scope)
    path = str(scope.get("repository") or "")
    typ, why = _repo_type(Path(root), path)
    if typ is None:
        return [{"member": "*", "signature": "", "verdict": "inconclusive",
                 "detail": "the destination model is unavailable, so no member can be assessed: %s" % why}]
    if str(typ.get("resolution") or "") != "full":
        return [{"member": "*", "signature": "", "verdict": "inconclusive",
                 "detail": "the compiler could not fully resolve %s, so its members cannot be assessed" % path}]
    declared = {str(m.get("signature")): m for m in typ.get("declared") or []}
    # What the supertypes declare, AS SEEN FROM this type, whether or not this
    # type redeclares it. Matched on the substituted signature and never on the
    # name: customLookup(int) and customLookup(String) are two members, and a
    # deleted findAll(String) is not answered by an inherited findAll().
    above = above_members(typ)
    inherited_sigs = {str(r.get("as_member") or r.get("signature") or "") for r in above}
    inherited_owner = {str(r.get("as_member") or r.get("signature") or ""): str(r.get("from") or "a supertype") for r in above}
    writes, why_writes = _model_writes(root)
    out: list[dict[str, Any]] = []
    for row in scope.get("members") or []:
        member = str(row.get("member"))
        sig = str(row.get("signature") or "")
        if not sig:
            out.append({"member": member, "signature": "", "verdict": "inconclusive",
                        "detail": "the inventory carries no resolved signature for this member, so there is nothing exact to assess"})
            continue
        m = declared.get(sig)
        if m is None:
            # The member is not declared. Only the compiler may say it is
            # inherited, and only for THIS signature: a member is not answered
            # by a different overload of the same name.
            if not typ.get("inherited_known"):
                out.append({"member": member, "signature": sig, "verdict": "inconclusive",
                            "detail": "not declared, and what this type inherits could not be resolved"})
            elif sig in inherited_sigs:
                out.append({"member": member, "signature": sig, "verdict": "ok",
                            "detail": "not declared here; inherited from %s" % inherited_owner.get(sig, "a supertype")})
            else:
                out.append({"member": member, "signature": sig, "verdict": "violates", "rule": scope.get("rule"),
                            "detail": "the member is gone from this type and nothing it extends declares %s" % sig})
            continue
        if str(m.get("resolution") or "") != "full":
            out.append({"member": member, "signature": str(m.get("signature") or sig), "verdict": "inconclusive",
                        "detail": "the compiler could not resolve this declaration"})
            continue
        anns = {str(a.get("simple") or "") for a in m.get("annotations") or []}
        msig = str(m.get("signature") or sig)
        has_query = "Query" in anns
        modifying = "Modifying" in anns
        if m.get("has_body"):
            out.append({"member": member, "signature": msig, "verdict": "ok",
                        "detail": "implemented in place; no query is owed"})
            continue
        # Determinations that need nothing but this declaration come first.
        if msig in inherited_sigs:
            out.append({"member": member, "signature": msig, "verdict": "ok",
                        "detail": "redeclares %s, which the type inherits from %s; the platform answers it from there"
                                  % (msig, inherited_owner.get(msig, "a supertype"))})
            continue
        derivable = bool(_DERIVABLE.match(member))
        if member in writes:
            if has_query and not modifying:
                out.append({"member": member, "signature": msig, "verdict": "violates", "rule": scope.get("rule"),
                            "detail": "a source write answered with a query and no @Modifying"})
            else:
                out.append({"member": member, "signature": msig, "verdict": "ok", "detail": "write kept as a write"})
            continue
        if why_writes and not derivable:
            # Without the source model this member might have been a state
            # change, and a query on a write is exactly the defect SI-1 exists
            # to catch. Saying nothing is the only honest answer.
            out.append({"member": member, "signature": msig, "verdict": "inconclusive",
                        "detail": "whether the source implemented this as a state change could not be read: %s" % why_writes})
            continue
        if has_query:
            out.append({"member": member, "signature": msig, "verdict": "ok", "detail": "carries a query"})
            continue
        if derivable:
            out.append({"member": member, "signature": msig, "verdict": "ok", "detail": "derivable by name"})
            continue
        out.append({"member": member, "signature": msig, "verdict": "violates", "rule": scope.get("rule"),
                    "detail": "a finder the parser cannot derive from its name, that carries no query, and that the type does not inherit"})
    return out


# ---------------------------------------------------------------------------
# unit formation (architect ruling 1, design of 2026-09-15 §1)
# ---------------------------------------------------------------------------
#
# A unit is one COORDINATED repair: the files AND the symbols one change has
# to cover for the tree to compile again. Nothing here invents a fact. The
# only sources are javac identities (compile_items / compile_token /
# diagnostic_identity), the destination model (planner.dest_model, read-only),
# the versioned catalogs (planning/catalogs/compat-mapping.json) and
# decisions.yaml. No graph tool, no source-text scanning, no regex over bodies.
#
# Without a former, the 8-file chunking of SYMBOL_CLUSTER_MAX_FILES is what a
# multi-file repair gets, and neither half of a split `throws` surface
# compiles. The former runs only when decisions.loop.unit_formation is "v1";
# otherwise clustering is byte-for-byte what it was.

UNIT_SCHEMA = "rhoai3.batch-scope/v4"
UNIT_KIND = "unit"
RULE_DIAGNOSTIC_FAMILY = "unit/diagnostic-family/v1"
RULE_DECLARATION_CLOSURE = "unit/declaration-closure/v1"
RULE_PACKAGE_LEAF = "unit/package-leaf/v1"
RULE_CONFIG_CONSUMERS = "unit/config-consumers/v1"
# ADR-019: an obligation OWED a harness adapter (a fixed template at a
# contract path, plus rendered configuration). Formed in every formation mode,
# because the authority to create the adapter's file is the sealed obligation,
# not the unit former.
RULE_OWED_ADAPTER = "unit/owed-adapter/v1"
# Precedence when two rules claim the same item: (c) > (b) > (a) > (d),
# evaluated in this order, first claim wins, ties broken by the sorted family
# key. Deterministic because every input is sorted and content-addressed.
UNIT_RULES = (RULE_PACKAGE_LEAF, RULE_DECLARATION_CLOSURE, RULE_DIAGNOSTIC_FAMILY, RULE_CONFIG_CONSUMERS)

# The growth bound. 20 files covers a 15-file annotation family and a 13-file
# throws surface; 160 sites is one measurement's worth (107 was the largest
# observed); a package-leaf union of more than 8 symbols is not one repair.
UNIT_MAX_FILES = 20
UNIT_MAX_SITES = 160
UNIT_MAX_SYMBOLS = 8

UNIT_FORMATION_V1 = "v1"
UNIT_FORMATION_OFF = "off"
# the set-wide runtime scope rule (b) can enumerate a mintable unit for
FRAGMENT_SET = "spring-data-fragment-implementations"


def unit_formation_mode(decisions_doc: dict[str, Any] | None) -> str:
    """decisions.loop.unit_formation, normalised. Absent ⇒ off ⇒ today's
    clustering. planner.decisions owns the reading; this is the one caller."""
    from planner.decisions import unit_formation as _read

    return _read(decisions_doc or {})


def _issued_work(root: Path) -> str:
    """The card the run is in the middle of: the issued cluster, or a cluster
    whose VERIFICATION_PENDING candidate is uncleared. "" when neither."""
    root = Path(root)
    p = root / LOOP_ISSUED
    if p.is_file():
        try:
            cid = str((load_json(p) or {}).get("cluster") or "")
        except (OSError, ValueError):
            cid = ""
        if cid:
            return cid
    s = root / LOOP_STEPS
    if s.is_file():
        try:
            steps = load_json(s) or {}
        except (OSError, ValueError):
            steps = {}
        for row in steps.get("pending") or []:
            if isinstance(row, dict) and row.get("cluster") and not row.get("cleared") and not row.get("rewound"):
                return str(row["cluster"])
    return ""


def unit_formation_for(root: Path, decisions_doc: dict[str, Any] | None) -> tuple[str, str]:
    """(the mode this list is formed under, why it is not the decided one).

    Flipping the mode changes cluster ids, so the issued card would vanish from
    the work list and advance.py would refuse LOOP_NOT_ISSUED, discarding a
    worker's candidate. The flip is therefore refused while a card is issued or
    a pending row is open, with a typed blocker naming the card to finish
    first; the switch takes effect at a clean boundary."""
    wanted = unit_formation_mode(decisions_doc)
    root = Path(root)
    prev = ""
    p = root / WORKLIST
    if p.is_file():
        try:
            prev = str((load_json(p) or {}).get("unit_formation") or "")
        except (OSError, ValueError):
            prev = ""
    if prev not in (UNIT_FORMATION_V1, UNIT_FORMATION_OFF) or prev == wanted:
        return wanted, ""
    card = _issued_work(root)
    if not card:
        return wanted, ""
    return prev, ("UNIT_MODE_SWITCH: decisions.yaml asks for loop.unit_formation %r while this list was formed %r and "
                  "cluster %s is still issued or pending; the flip changes every cluster id, so the outstanding "
                  "candidate would be discarded as not-issued. Finish %s, then the switch takes effect at the next "
                  "clean boundary." % (wanted, prev, card, card))


# --- pure reads over the destination model ---------------------------------
#
# dest_model.py is read-only here: these are reads of the document the Java
# tool already emits, so jdk-dest-model's tool.version stays 1.2.0.

def _unit_types(model: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [t for t in ((model or {}).get("types") or []) if isinstance(t, dict)]


def _unit_path(typ: dict[str, Any]) -> str:
    return "src/main/java/" + str(typ.get("path") or "")


def _erased(ref: Any) -> str:
    """A type reference without its type arguments: JpaRepository<Vet,Integer>
    is the supertype JpaRepository."""
    s = str(ref or "")
    i = s.find("<")
    return s[:i] if i >= 0 else s


def unit_bound_imports(typ: dict[str, Any]) -> dict[str, str]:
    """simple name → FQN for the imports that BIND it. A wildcard import binds
    nothing: it is why two different `Context` types are two families."""
    out: dict[str, str] = {}
    for i in typ.get("imports") or []:
        s = str(i)
        if s.endswith(".*"):
            continue
        out[s.rsplit(".", 1)[-1]] = s
    return out


def unit_implementers(model: dict[str, Any] | None, fqn: str) -> list[dict[str, Any]]:
    """Types whose `supertypes` contain `fqn`. ONE HOP, never transitive: that
    is the primary growth bound."""
    return sorted((t for t in _unit_types(model) if fqn in [_erased(s) for s in (t.get("supertypes") or [])]),
                  key=lambda t: (_unit_path(t), str(t.get("fqn") or "")))


def unit_callers_of(model: dict[str, Any] | None, fqn: str, signature: str) -> list[dict[str, Any]]:
    """Every declared member whose resolved `calls` name `fqn.signature`."""
    want = "%s.%s" % (fqn, signature)
    out: list[dict[str, Any]] = []
    for t in _unit_types(model):
        ids = member_ids(t)
        for m in t.get("declared") or []:
            if not isinstance(m, dict):
                continue
            if want in [str(c) for c in (m.get("calls") or [])]:
                sig = str(m.get("signature") or "")
                out.append({"path": _unit_path(t), "type": str(t.get("fqn") or ""),
                            "member_id": ids.get(sig, str(m.get("name") or "")), "signature": sig})
    return sorted(out, key=lambda r: (r["path"], r["type"], r["member_id"]))


def call_owner(call: Any) -> str:
    """The type a resolved call names. jdk-dest-model writes a call as
    ``<owner fqn>.<signature>`` and a signature always carries its parameter
    list, so the owner is what stands before the last dot ahead of the "("."""
    head = str(call or "").split("(", 1)[0]
    return head.rsplit(".", 1)[0] if "." in head else ""


def unit_type_refs(typ: dict[str, Any]) -> set[str]:
    """Every type this declaration NAMES, in the shape the real extractor emits.

    The relationships the compiler states live at MEMBER level: jdk-dest-model
    writes ``mrow.put("type_refs", …)`` for a declared member's return, its
    parameters and its throws, ``mrow.put("calls", …)`` for the resolved
    callees, and ``fields[].type`` for a field; the type row itself carries
    `supertypes` and `imports` and no `type_refs` of its own (there is no
    ``row.put("type_refs", …)`` in DestModel.java). Asking the type level of a
    real model therefore returned nothing, and a package with a genuine outside
    consumer was classified as a leaf. The type-level key is still read because
    another producer's model may carry one, and dropping evidence is never the
    safe direction."""
    out: set[str] = set()
    if not isinstance(typ, dict):
        return out
    for r in typ.get("type_refs") or []:
        out.add(_erased(r))
    for s in typ.get("supertypes") or []:
        out.add(_erased(s))
    for i in typ.get("imports") or []:
        s = str(i)
        if not s.endswith(".*"):
            out.add(s)
    for m in typ.get("declared") or []:
        if not isinstance(m, dict):
            continue
        for r in m.get("type_refs") or []:
            out.add(_erased(r))
        for c in m.get("calls") or []:
            owner = call_owner(c)
            if owner:
                out.add(owner)
    for f in typ.get("fields") or []:
        if isinstance(f, dict) and f.get("type"):
            out.add(_erased(f.get("type")))
    return {r for r in out if r}


def unit_states_relationships(typ: dict[str, Any]) -> bool:
    """Whether this type row can be asked what it refers to at all.

    A partially resolved type is a type the compiler could not finish: its
    member refs and its resolved calls are whatever survived the failure. An
    ISOLATION claim ("nothing outside names what is inside") is a claim about
    absence, and absence in a row that states no relationships is not evidence
    of one. Fail closed: no relationship evidence, no leaf."""
    return isinstance(typ, dict) and str(typ.get("resolution") or "") == "full"


def unit_annotation_sites(model: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Every annotation the model recorded, one row per SITE — the
    generalisation of profile_conditions() to any annotation. `fqn` is the
    compiler's when it resolved one, else what the file's imports bind."""
    out: list[dict[str, Any]] = []
    for t in _unit_types(model):
        path, fqn = _unit_path(t), str(t.get("fqn") or "")
        bound = unit_bound_imports(t)
        res = str(t.get("resolution") or "")
        sites: list[tuple[str, Any, str]] = [("", t.get("annotations") or [], res)]
        for m in t.get("declared") or []:
            if isinstance(m, dict):
                sites.append((str(m.get("signature") or m.get("name") or ""), m.get("annotations") or [], str(m.get("resolution") or res)))
        for f in t.get("fields") or []:
            if isinstance(f, dict):
                sites.append((str(f.get("name") or ""), f.get("annotations") or [], res))
        for member, anns, mres in sites:
            for a in anns or []:
                if not isinstance(a, dict):
                    continue
                afqn = str(a.get("fqn") or "")
                simple = str(a.get("simple") or "") or afqn.rsplit(".", 1)[-1]
                out.append({"path": path, "type": fqn, "member": member, "simple": simple,
                            "fqn": afqn or bound.get(simple, ""), "resolution": mres})
    return sorted(out, key=lambda r: (r["path"], r["type"], r["member"], r["simple"]))


def unit_member_shape(member: dict[str, Any]) -> str:
    """A digest over a declared member's (signature, annotations, calls,
    throws_checked): what "this member changed" means without reading text."""
    m = member if isinstance(member, dict) else {}
    return sha256_bytes(canonical_bytes({
        "signature": str(m.get("signature") or ""),
        "annotations": sorted(str(a.get("simple") or a.get("fqn") or "") for a in (m.get("annotations") or []) if isinstance(a, dict)),
        "calls": sorted(str(c) for c in (m.get("calls") or [])),
        "throws_checked": sorted(str(x) for x in (m.get("throws_checked") or [])),
    }))[:16]


# --- the catalog rows a unit's targets are documented by --------------------

def symbol_renames(root: Path | None) -> dict[str, dict[str, Any]]:
    """compat-mapping.json `symbol_renames`: documented symbol-level targets.

    Every row is a documented mapping, never an inference — the same contract
    package_renames carries. It is what makes "the replacement this unit moves
    to" checkable: jakarta.ws.rs.core.Context has a row and jakarta.ws.rs.Context
    does not, so a candidate that invented the second one stays unexplained.

    Both sides of a row are QUALIFIED identities, and a row that is not is not
    a row. A simple name is a spelling, and a spelling cannot be resolved
    against a compiler model: `UriBuilder` with nothing importing it names no
    type, and a catalogue keyed by such a name would license exactly the
    unresolved match acceptance must refuse. Unqualified rows are dropped here,
    at the source, so no consumer can be the one that forgets."""
    if root is None:
        return {}
    p = Path(root) / CATALOGS_DIR / "compat-mapping.json"
    if not p.is_file():
        return {}
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return {}
    rows = doc.get("symbol_renames") or {}
    return {str(k): dict(v) for k, v in rows.items()
            if k != "note" and isinstance(v, dict) and v.get("to")
            and "." in str(k) and "." in str(v.get("to"))}


def package_renames_of(root: Path | None) -> dict[str, str]:
    if root is None:
        return {}
    p = Path(root) / CATALOGS_DIR / "compat-mapping.json"
    if not p.is_file():
        return {}
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in (doc.get("package_renames") or {}).items() if k != "note" and isinstance(v, str)}


def unit_target_symbols(symbols: list[dict[str, Any]], renames: dict[str, dict[str, Any]],
                        packages: dict[str, str]) -> list[dict[str, Any]]:
    """[{from, to, catalog_row}] — the documented replacement of each sealed
    symbol, when a catalog row records one. A symbol with no row contributes
    nothing: the unit then has no documented target, and the checkpoint has
    nothing to tolerate."""
    out: list[dict[str, Any]] = []
    for s in symbols:
        fqn = str(s.get("fqn") or "")
        if not fqn:
            continue
        row = renames.get(fqn)
        if row is not None:
            out.append({"from": fqn, "to": str(row.get("to") or ""),
                        "catalog_row": {"catalog": "compat-mapping.json", "block": "symbol_renames", "key": fqn,
                                        "kind": str(row.get("kind") or ""), "source": str(row.get("source") or "")}})
            continue
        for old in sorted(packages, key=len, reverse=True):
            if fqn == old or fqn.startswith(old + "."):
                out.append({"from": fqn, "to": packages[old] + fqn[len(old):],
                            "catalog_row": {"catalog": "compat-mapping.json", "block": "package_renames", "key": old,
                                            "kind": "package", "source": ""}})
                break
    return sorted(out, key=lambda r: (r["from"], r["to"]))


# --- the four rules --------------------------------------------------------

def _unit_member(path: str, *, type_fqn: str = "", member_id: str = "", occurrence: int = 0,
                 state: str = "", **extra: Any) -> dict[str, Any]:
    row = {"path": path, "type": type_fqn, "member_id": member_id, "occurrence": occurrence, "state": state}
    row.update({k: v for k, v in extra.items() if v})
    return row


def _annotation_simples(model: dict[str, Any] | None) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for r in unit_annotation_sites(model):
        out[r["path"]].add(r["simple"])
    return out


def resolve_compile_symbol(model: dict[str, Any] | None, item: dict[str, Any],
                           annotations: dict[str, set[str]] | None = None) -> tuple[str, str]:
    """(family key, symbol kind) for one compile item.

    The key is the resolved FQN when the declaring file's imports bind the
    token, else the bare token. That resolution is the whole point: two
    different `Context` types stay two families instead of collapsing into one
    (v9 card t_3903f495)."""
    tok = compile_token(item)
    if not tok:
        return "", ""
    msg = str(item.get("message") or item.get("detail") or "")
    if _PKG_RE.search(msg) and not _SYM_RE.search(msg):
        return tok, "package"
    path = str(item.get("path") or "")
    kind = "annotation" if tok in (annotations or {}).get(path, set()) else "type"
    for t in types_of(model, path) if model else []:
        bound = unit_bound_imports(t)
        if tok in bound:
            return bound[tok], kind
    return tok, kind


def diagnostic_families(items: list[dict[str, Any]], model: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Rule (a): every javac site that names one unresolved symbol or package,
    resolved through the declaring file's imports."""
    annotations = _annotation_simples(model)
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for it in items:
        key, kind = resolve_compile_symbol(model, it, annotations)
        if key:
            by_key[(key, kind)].append(it)
    out: list[dict[str, Any]] = []
    for (key, kind) in sorted(by_key):
        rows = sorted(by_key[(key, kind)], key=lambda i: str(i.get("id")))
        out.append({"key": key, "symbol_kind": kind, "items": rows,
                    "files": sort_unique([str(r.get("path") or "") for r in rows])})
    return out


def _family_members(family: dict[str, Any], model: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for it in family["items"]:
        path = str(it.get("path") or "")
        typ = next((t for t in (types_of(model, path) if model else [])), None)
        seen[path] = seen.get(path, 0) + 1
        rows.append(_unit_member(path, type_fqn=str((typ or {}).get("fqn") or ""),
                                 member_id="", occurrence=seen[path] - 1, state="reported",
                                 identity=str(it.get("identity") or ""), item=str(it.get("id") or "")))
    return rows


def _family_evidence(family: dict[str, Any]) -> list[dict[str, Any]]:
    out = [{"kind": "javac", "ref": "%s %s names %s" % (str(i.get("path") or ""), str(i.get("rule_id") or ""), family["key"])}
           for i in family["items"]]
    return out


def _declaring_throws(model: dict[str, Any] | None, exception_fqn: str) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """(type, declared member) for every member that DECLARES `exception_fqn`.

    A `throws` clause on an interface is a surface: the implementers and the
    callers are bound to it, and repairing one side alone does not compile."""
    out: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for t in _unit_types(model):
        for m in t.get("declared") or []:
            if isinstance(m, dict) and exception_fqn in [str(x) for x in (m.get("throws_checked") or [])]:
                out.append((t, m))
    return sorted(out, key=lambda r: (_unit_path(r[0]), str(r[1].get("signature") or "")))


def declaration_closure(model: dict[str, Any] | None, typ: dict[str, Any],
                        members: list[dict[str, Any]]) -> dict[str, Any]:
    """Rule (b): a declaration plus its DIRECT implementers and DIRECT callers.

    One hop only. The key is (declaring fqn, member signature set), which is
    stable under remeasurement because both come from the model."""
    fqn = str(typ.get("fqn") or "")
    sigs = sort_unique([str(m.get("signature") or "") for m in members])
    rows: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    ids = member_ids(typ)
    for m in members:
        sig = str(m.get("signature") or "")
        rows.append(_unit_member(_unit_path(typ), type_fqn=fqn, member_id=ids.get(sig, str(m.get("name") or "")),
                                 state="declares", signature=sig, shape=unit_member_shape(m)))
        evidence.append({"kind": "model", "ref": "%s declares %s" % (fqn, sig)})
    for impl in unit_implementers(model, fqn):
        iids = member_ids(impl)
        above = {str(r.get("as_member") or r.get("signature") or "") for r in above_members(impl)}
        for m in impl.get("declared") or []:
            if not isinstance(m, dict):
                continue
            sig = str(m.get("signature") or "")
            if sig in sigs or sig in above:
                rows.append(_unit_member(_unit_path(impl), type_fqn=str(impl.get("fqn") or ""),
                                         member_id=iids.get(sig, str(m.get("name") or "")), state="implements",
                                         signature=sig, shape=unit_member_shape(m), parent=fqn))
        evidence.append({"kind": "model", "ref": "%s implements %s" % (impl.get("fqn"), fqn)})
        if not any(r["path"] == _unit_path(impl) for r in rows):
            rows.append(_unit_member(_unit_path(impl), type_fqn=str(impl.get("fqn") or ""), state="implements",
                                     parent=fqn))
    for sig in sigs:
        for c in unit_callers_of(model, fqn, sig):
            rows.append(_unit_member(c["path"], type_fqn=c["type"], member_id=c["member_id"], state="calls",
                                     callee="%s.%s" % (fqn, sig)))
            evidence.append({"kind": "model", "ref": "%s.%s calls %s.%s" % (c["type"], c["member_id"], fqn, sig)})
    return {"key": "%s%s" % (fqn, "".join("#" + s for s in sigs)), "declaring": fqn, "signatures": sigs,
            "members": rows, "evidence": evidence,
            "files": sort_unique([r["path"] for r in rows])}


def fragment_parents(model: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The parents of a repository set the platform could not implement, and
    their implementers, enumerated from the model alone.

    A parent is a type this project declares that another project type extends,
    and that declares a member no implementer declares and no name-derivation
    answers. The platform names ONE member of that set and which one changes
    between runs, which is why the obligation carries no file; this is the
    family planner the RUNTIME_SET_WIDE comment said it was waiting for. It
    returns [] when the model cannot enumerate the set, and the typed blocker
    then stands unchanged."""
    types = _unit_types(model)
    by_fqn = {str(t.get("fqn") or ""): t for t in types}
    out: list[dict[str, Any]] = []
    for fqn in sorted(by_fqn):
        parent = by_fqn[fqn]
        impls = [t for t in unit_implementers(model, fqn) if str(t.get("fqn") or "") != fqn]
        if not impls:
            continue
        owed: list[dict[str, Any]] = []
        for m in parent.get("declared") or []:
            if not isinstance(m, dict) or m.get("has_body"):
                continue
            name, sig = str(m.get("name") or ""), str(m.get("signature") or "")
            if not name or name == "<init>" or _DERIVABLE.match(name):
                continue
            answered = False
            for impl in impls:
                if any(str(d.get("signature") or "") == sig and d.get("has_body") for d in (impl.get("declared") or []) if isinstance(d, dict)):
                    answered = True
                    break
                if any(str(r.get("as_member") or r.get("signature") or "") == sig and str(r.get("from") or "") != fqn
                       for r in above_members(impl)):
                    answered = True
                    break
            if not answered:
                owed.append({"signature": sig, "name": name})
        if owed:
            out.append({"parent": fqn, "path": _unit_path(parent), "members": owed,
                        "implementers": [{"fqn": str(t.get("fqn") or ""), "path": _unit_path(t)} for t in impls]})
    return out


# The naming contract a fragment implementation is authorized under. Spring
# Data finds a fragment's implementation by NAME: the class implementing
# interface `X` is `XImpl` in X's own package (Spring Data JPA reference,
# "Custom Implementations for Spring Data Repositories"), and the Quarkus
# Spring Data extension keeps that rule when it derives a repository. It is a
# framework fact, derived from the parent's OWN fully qualified name, so it
# names a specimen nowhere.
FRAGMENT_IMPL_CONTRACT = "spring-data-fragment-impl/v1"
FRAGMENT_IMPL_SOURCE = ("https://docs.spring.io/spring-data/jpa/reference/repositories/custom-implementations.html "
                        "(a fragment interface X is implemented by XImpl in X's own package)")


def unit_implementation_obligations(parents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The new implementation paths a fragment unit is OWED, named in advance.

    A repair that has to create a file cannot be authorized by the model: the
    model has no type for a file nobody has written, so `amend-scope.py`
    refused the adapter the card existed to produce. What authorizes it is the
    seal itself — the obligation (this parent declares a member no implementer
    answers) together with the naming contract (what the new type and its file
    must be called). The path is DERIVED from the parent's own fqn, so a
    worker cannot choose it, and the relationship it promises — the new type
    implements the parent — is verified from the model after the file exists
    (amend-scope's re-check and assess_unit's own)."""
    out: list[dict[str, Any]] = []
    for p in parents:
        parent = str(p.get("parent") or "")
        path = str(p.get("path") or "")
        if not parent or not path:
            continue
        simple = parent.rsplit(".", 1)[-1]
        out.append({
            "parent": parent,
            "parent_path": path,
            "type": parent + "Impl",
            "path": "%s/%sImpl.java" % (path.rsplit("/", 1)[0], simple),
            "members": sort_unique([str(m.get("signature") or "") for m in (p.get("members") or [])]),
            "contract": FRAGMENT_IMPL_CONTRACT,
            "source": FRAGMENT_IMPL_SOURCE,
        })
    return sorted(out, key=lambda r: (r["parent"], r["path"]))


def package_leaf_units(families: list[dict[str, Any]], model: dict[str, Any] | None,
                       claimed: set[str]) -> list[dict[str, Any]]:
    """Rule (c): the union of (a)-families confined to one package directory,
    where no type declared outside the union names a type declared in it.

    "Leaf" is decided by the relationships the compiler states about the types
    the union actually holds, never by a package NAME: a package nothing
    outside refers to is a leaf whatever it is called. Those relationships are
    read at the level the extractor writes them — a declared member's
    `type_refs` and resolved `calls`, a field's type, the supertypes and the
    imports (unit_type_refs) — because the type row of a real model carries no
    `type_refs` at all, and a planner that asked it there saw no consumer where
    there was one.

    Isolation is a claim about ABSENCE, so it is refused on missing evidence: a
    single outside type the compiler could not fully resolve is a type that
    cannot say what it names, and the union is not minted as a leaf."""
    by_dir: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fam in families:
        if any(str(i.get("id")) in claimed for i in fam["items"]):
            continue
        dirs = {p.rsplit("/", 1)[0] for p in fam["files"]}
        if len(dirs) == 1:
            by_dir[dirs.pop()].append(fam)
    out: list[dict[str, Any]] = []
    for directory in sorted(by_dir):
        fams = sorted(by_dir[directory], key=lambda f: f["key"])
        files = sort_unique([p for f in fams for p in f["files"]])
        inside = {str(t.get("fqn") or "") for t in _unit_types(model) if _unit_path(t) in set(files)}
        if not inside:
            continue
        outside = [t for t in _unit_types(model) if _unit_path(t) not in set(files)]
        if any(not unit_states_relationships(t) for t in outside):
            continue  # no relationship evidence: isolation cannot be established
        if any(r in inside for t in outside for r in unit_type_refs(t)):
            continue
        if len(files) < 2 and len(fams) < 2:
            continue
        out.append({"directory": directory, "families": fams, "files": files, "inside": sorted(inside)})
    return out


def config_consumer_units(items: list[dict[str, Any]], model: dict[str, Any] | None,
                          root: Path | None) -> list[dict[str, Any]]:
    """Rule (d): a configuration property and the code that reads it."""
    out: list[dict[str, Any]] = []
    for it in sorted(items, key=lambda i: str(i.get("id"))):
        if str(it.get("source") or "") != "runtime" or str(it.get("cause") or "") != "config-value":
            continue
        prop = config_property_name(str(it.get("message") or it.get("detail") or ""))
        if not prop:
            continue
        sites = _dest_config_sites(model, prop) if model else []
        files = sort_unique([s["path"] for s in sites] + unit_property_files(root, prop))
        if len(files) < 2:
            continue
        out.append({"property": prop, "sites": sites, "files": files, "item": it})
    return out


def unit_property_files(root: Path | None, prop: str) -> list[str]:
    """The .properties files under the main resource root that DECLARE `prop`
    (a `%profile.` prefix is the same key). Read as properties syntax, never
    as text near a name."""
    if root is None or not prop:
        return []
    base = Path(root) / "src" / "main" / "resources"
    if not base.is_dir():
        return []
    out: list[str] = []
    for p in sorted(base.glob("application*.properties")):
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s[0] in "#!":
                continue
            key = s.split("=", 1)[0].split(":", 1)[0].strip()
            if key.startswith("%") and "." in key:
                key = key.split(".", 1)[1]
            if key == prop:
                out.append(p.relative_to(Path(root)).as_posix())
                break
    return sort_unique(out)


# --- the bound, and the typed reason ---------------------------------------

def _unit_size(unit: dict[str, Any]) -> dict[str, int]:
    return {"files": len(unit.get("files") or []), "sites": len(unit.get("members") or []),
            "symbols": len(unit.get("symbols") or [])}


def _within(size: dict[str, int]) -> bool:
    return size["files"] <= UNIT_MAX_FILES and size["sites"] <= UNIT_MAX_SITES and size["symbols"] <= UNIT_MAX_SYMBOLS


def _bound_unit(unit: dict[str, Any]) -> dict[str, Any]:
    """Deterministic narrowing first, a typed blocker second.

    What narrowing may drop is now the whole question, because a narrowed unit
    that cannot compile is worse than no unit at all:

    * a CALLER of a sealed declaration is never dropped. It is bound to the
      declaration the unit changes — a signature it passes, an exception it
      catches — so a closure without it is a repair that does not build, and
      the bound is then a planning answer, not a slice. Rule (b) narrows by
      nothing and reaches UNIT_OVERSIZE instead.
    * a union (rules (c) and (a)) drops whole FAMILIES, lowest cardinality
      first, and every obligation it drops is RETAINED: the items go back
      unclaimed to the ordinary per-file pass, so the work list still carries
      them as their own items, and the seal records what left and why.
    * whatever survives keeps every file one of its OWN obligations names. An
      item whose file is not writable is an item the card cannot discharge, so
      the file stays in the write set and the size is judged after it.

    Never an arbitrary file-order chunk: SYMBOL_CLUSTER_MAX_FILES slicing is
    exactly what makes a coordinated `throws` repair unrepresentable, because
    neither half compiles."""
    before = _unit_size(unit)
    excluded: list[dict[str, Any]] = []
    if not _within(before) and unit["rule"] in (RULE_PACKAGE_LEAF, RULE_DIAGNOSTIC_FAMILY):
        groups = sorted(unit.get("groups") or [], key=lambda g: (len(g["members"]), g["key"]))
        while groups and not _within(_unit_size(unit)) and len(groups) > 1:
            dropped = groups.pop(0)
            unit["groups"] = groups
            unit["symbols"] = [s for s in unit["symbols"] if str(s.get("fqn")) != dropped["key"]]
            unit["members"] = [m for m in unit["members"] if m not in dropped["members"]]
            unit["items"] = [i for i in unit["items"] if i not in dropped["items"]]
            unit["files"] = sort_unique([m["path"] for m in unit["members"]])
            excluded.append({"family": dropped["key"], "sites": len(dropped["members"]),
                             "items": sort_unique([str(i.get("id") or "") for i in dropped["items"]])})
            unit["evidence"].append({"kind": "model", "ref": "UNIT_NARROWED: family %s (%d site(s)) dropped, the lowest cardinality in this union; its %d obligation(s) stay in the work list as their own items" % (dropped["key"], len(dropped["members"]), len(dropped["items"]))})
    # every file one of the unit's OWN obligations names stays writable: a
    # measured item with no writable file is an item the card cannot discharge
    obliged = sort_unique([str(i.get("path") or "") for i in (unit.get("items") or []) if i.get("path")])
    missing = [p for p in obliged if p not in set(unit["files"])]
    if missing:
        unit["files"] = sort_unique(list(unit["files"]) + missing)
        unit["evidence"].append({"kind": "javac", "ref": "%d file(s) kept in the write set because the unit still measures an obligation in them (%s)" % (len(missing), ", ".join(missing[:2]))})
    after = _unit_size(unit)
    unit["bounds"] = dict(after, max_files=UNIT_MAX_FILES, max_sites=UNIT_MAX_SITES, max_symbols=UNIT_MAX_SYMBOLS)
    if after != before:
        unit["bounds"]["narrowed"] = {"from": before, "to": after, "reason": "UNIT_NARROWED"}
    if excluded:
        unit["bounds"]["excluded"] = excluded
    if not _within(after):
        unit["block"] = ("UNIT_OVERSIZE: %s over %s reaches %d file(s)/%d site(s)/%d symbol(s) (max %d/%d/%d); "
                         "a repair this wide is a planning answer"
                         % (unit["rule"], unit["family_key"], after["files"], after["sites"], after["symbols"],
                            UNIT_MAX_FILES, UNIT_MAX_SITES, UNIT_MAX_SYMBOLS))
        if unit["rule"] == RULE_DECLARATION_CLOSURE:
            unit["block"] += ("; its callers are bound to the declaration it changes and dropping them would leave a "
                              "unit that cannot compile")
    return unit


# --- the former ------------------------------------------------------------

def unit_id_of(rule: str, family_key: str, members: list[dict[str, Any]]) -> str:
    """The budget's identity: a digest of (rule, family key, member keys). It
    survives remeasurement, attempt numbers and scope revisions, so one PROBLEM
    keeps one budget rather than gaining a fresh one per re-plan."""
    keys = sort_unique(["%s|%s|%s|%s" % (m.get("path"), m.get("type"), m.get("member_id"), m.get("state"))
                        for m in members])
    return "u:%s" % sha256_bytes(canonical_bytes({"rule": rule, "family_key": family_key, "members": keys}))[:12]


def _unit_cluster(unit: dict[str, Any], depths: dict[str, int], deferred: set[str]) -> dict[str, Any]:
    """A unit is an ORDINARY cluster: same dict shape, same order_key, same
    status vocabulary, same write_set, and a kind from KIND_RANK. That is what
    keeps K1, cards.CARD_SKILLS, REFERENCE_SKILLS and the board untouched."""
    files = list(unit["files"])
    kind = unit["kind"]
    cid = unit["unit_id"]
    completion = unit["completion"]
    status = "blocked" if unit.get("block") else ("deferred" if cid in deferred else "open")
    cluster = {
        "id": cid,
        "path": files[0] if files else GLOBAL,
        "label": unit["family_key"],
        "kind": kind,
        "items": [str(i.get("id")) for i in unit["items"]],
        "order_key": [KIND_RANK[kind], min([depths.get(f, UNKNOWN_DEPTH) for f in files] or [UNKNOWN_DEPTH]), files[0] if files else GLOBAL],
        "status": status,
        "write_set": files,
        "block": str(unit.get("block") or ""),
        "unit": {"unit_id": cid, "rule": unit["rule"], "family_key": unit["family_key"],
                 "symbols": unit["symbols"], "target_symbols": unit["target_symbols"],
                 "evidence": unit["evidence"][:12], "size": {k: unit["bounds"][k] for k in ("files", "sites", "symbols")},
                 "completion": [str(c.get("detail") or c.get("check")) for c in completion]},
    }
    if unit.get("implementation"):
        cluster["unit"]["implementation"] = unit["implementation"]
    if unit.get("gate"):
        cluster["gate"] = unit["gate"]
    cluster["_unit_seal"] = unit
    return cluster


def _unit_completion(unit: dict[str, Any]) -> list[dict[str, Any]]:
    """The typed checks, derived from the members, each with the tool that
    decides it. Nothing a worker writes can satisfy one."""
    # the LINE-FREE identity when the list stamped one (build_worklist does,
    # before clustering); the item id is the fallback, never the err: id's line
    identities = sort_unique([str(m.get("identity") or m.get("item") or "") for m in unit["members"]
                              if m.get("identity") or m.get("item")])
    out: list[dict[str, Any]] = []
    if identities:
        out.append({"check": "identities-gone", "tool": "javac", "identities": identities,
                    "detail": "every one of the %d javac identit%s this unit seals is no longer reported"
                              % (len(identities), "y" if len(identities) == 1 else "ies")})
    out.append({"check": "unit-assessment", "tool": "worklist.assess_unit",
                "detail": "assess_unit reports no member violates and none is inconclusive (an already-correct member earns nothing and costs nothing)"})
    for row in unit.get("implementation") or []:
        if row.get("verify") == "template":
            out.append({"check": "adapter", "tool": "worklist.assess_unit", "path": row["path"], "type": row["type"],
                        "contract": row["contract"],
                        "detail": "%s is the %s template byte-for-byte (sha256 %s), the model declares %s there, and %s "
                                  "carries exactly the %d row(s) the capability renders (%s --check)"
                                  % (row["path"], row["contract"], str(row["template_sha256"])[:12], row["type"],
                                     row["config"], len(row.get("properties") or []), row.get("install") or "")})
            continue
        out.append({"check": "implementation", "tool": "worklist.assess_unit", "parent": row["parent"],
                    "path": row["path"], "type": row["type"],
                    "detail": "%s is implemented by a concrete %s at %s (%s), and the model shows it implements the "
                              "parent" % (row["parent"], row["type"], row["path"], row["contract"])})
    if unit.get("gate"):
        out.append({"check": "gate", "tool": "run-verify.sh", "gate": unit["gate"],
                    "detail": "the %s gate passes on the verified artifact" % unit["gate"]})
    return out


def form_units(items: list[dict[str, Any]], depths: dict[str, int], deferred: set[str], *,
               model: dict[str, Any] | None = None, root: Path | None = None) -> tuple[list[dict[str, Any]], set[str]]:
    """The four typed rules, in precedence order, over one measurement.

    Returns (unit clusters, the item ids they took). Items a unit takes are
    removed from the per-file pass exactly as `taken` already does for symbol
    groups."""
    renames, packages = symbol_renames(root), package_renames_of(root)
    compile_rows = [i for i in items if str(i.get("source") or "") == "javac"]
    families = diagnostic_families(compile_rows, model)
    claimed: set[str] = set()
    units: list[dict[str, Any]] = []

    def take(unit: dict[str, Any]) -> None:
        unit["symbols"] = sorted(unit["symbols"], key=lambda s: (str(s.get("kind")), str(s.get("fqn")), str(s.get("signature") or "")))
        unit["target_symbols"] = unit_target_symbols(unit["symbols"], renames, packages)
        for t in unit["target_symbols"]:
            unit["evidence"].append({"kind": "catalog", "ref": "compat-mapping.json %s: %s -> %s"
                                                               % (t["catalog_row"]["block"], t["from"], t["to"])})
        _bound_unit(unit)
        unit["unit_id"] = unit_id_of(unit["rule"], unit["family_key"], unit["members"])
        unit["completion"] = _unit_completion(unit)
        claimed.update(str(i.get("id")) for i in unit["items"])
        units.append(unit)

    # (c) package-leaf — highest precedence: a leaf is one repair whatever its
    # families are called.
    for leaf in package_leaf_units(families, model, claimed):
        members: list[dict[str, Any]] = []
        evidence: list[dict[str, Any]] = [{"kind": "model", "ref": "no type declared outside %s names a type declared in it (type_refs)" % leaf["directory"]}]
        groups: list[dict[str, Any]] = []
        rows: list[dict[str, Any]] = []
        symbols: list[dict[str, Any]] = []
        for fam in leaf["families"]:
            fam_members = _family_members(fam, model)
            groups.append({"key": fam["key"], "members": fam_members, "items": fam["items"]})
            members.extend(fam_members)
            rows.extend(fam["items"])
            evidence.extend(_family_evidence(fam))
            symbols.append({"kind": fam["symbol_kind"], "fqn": fam["key"], "path": fam["files"][0]})
        take({"rule": RULE_PACKAGE_LEAF, "family_key": leaf["directory"], "kind": "compile",
              "items": rows, "files": leaf["files"], "members": members, "symbols": symbols,
              "evidence": evidence, "groups": groups, "gate": ""})

    # (b) declaration closure — the interface `throws` surface a diagnostic
    # names, and the set-wide runtime rows the model can enumerate.
    for fam in families:
        if any(str(i.get("id")) in claimed for i in fam["items"]):
            continue
        pairs = _declaring_throws(model, fam["key"])
        if not pairs:
            continue
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        holders: dict[str, dict[str, Any]] = {}
        for typ, m in pairs:
            by_type[str(typ.get("fqn") or "")].append(m)
            holders[str(typ.get("fqn") or "")] = typ
        # the SURFACE is the declaration others are bound to: an interface
        # first, then lexicographic. Repairing an implementation alone does not
        # compile, which is the whole reason this rule exists.
        for fqn in sorted(by_type, key=lambda f: (str(holders[f].get("kind") or "") != "interface", f)):
            closure = declaration_closure(model, holders[fqn], by_type[fqn])
            files = sort_unique(closure["files"] + fam["files"])
            members = closure["members"] + _family_members(fam, model)
            symbols = [{"kind": "member", "fqn": fqn, "signature": s, "path": _unit_path(holders[fqn])} for s in closure["signatures"]]
            symbols.append({"kind": fam["symbol_kind"], "fqn": fam["key"], "path": fam["files"][0]})
            take({"rule": RULE_DECLARATION_CLOSURE, "family_key": closure["key"], "kind": "compile",
                  "items": list(fam["items"]), "files": files, "members": members, "symbols": symbols,
                  "evidence": closure["evidence"] + _family_evidence(fam), "gate": ""})
            break

    for it in sorted([i for i in items if RUNTIME_SET_WIDE_FORMER.get(str(i.get("set_wide") or "")) == RULE_DECLARATION_CLOSURE],
                     key=lambda i: str(i.get("id"))):
        parents = fragment_parents(model)
        if not parents:
            continue  # the model cannot enumerate the set: the typed blocker stands
        members = []
        symbols = []
        evidence = [{"kind": "runtime", "ref": "%s %s set_wide=%s" % (it.get("id"), it.get("cause"), FRAGMENT_SET)}]
        files: list[str] = []
        for p in parents:
            files.append(p["path"])
            for m in p["members"]:
                members.append(_unit_member(p["path"], type_fqn=p["parent"], member_id=m["name"],
                                            state="declares", signature=m["signature"]))
                symbols.append({"kind": "member", "fqn": p["parent"], "signature": m["signature"], "path": p["path"]})
                evidence.append({"kind": "model", "ref": "%s declares %s and no implementer answers it" % (p["parent"], m["signature"])})
            for impl in p["implementers"]:
                # the children are INVENTORY, not write set: this repair adds an
                # implementation, it does not edit the interfaces that inherit
                # the parent. They are assessed (the inheritance must survive)
                # and they are reachable by a recorded revision if one is ever
                # needed, which is what amend-scope's implements-branch is for.
                members.append(_unit_member(impl["path"], type_fqn=impl["fqn"], state="implements",
                                            parent=p["parent"]))
                evidence.append({"kind": "model", "ref": "%s implements %s" % (impl["fqn"], p["parent"])})
        # the new file this repair OWES, named before it exists: the obligation
        # (a member no implementer answers) and the naming contract are what
        # authorize a path the model cannot yet have a type for. It is in the
        # write set from the start, because the file seal is what acceptance
        # enforces and a repair that may not write its own adapter is no repair.
        owed = unit_implementation_obligations(parents)
        for row in owed:
            files.append(row["path"])
            evidence.append({"kind": "catalog", "ref": "%s: %s implements %s at %s (%s)"
                                                      % (row["contract"], row["type"], row["parent"], row["path"], row["source"])})
        take({"rule": RULE_DECLARATION_CLOSURE,
              "family_key": "%s:%s" % (it.get("set_wide"), ",".join(sorted(p["parent"] for p in parents))),
              "kind": str(it.get("kind") or "config"), "items": [it], "files": sort_unique(files),
              "members": members, "symbols": symbols, "evidence": evidence, "gate": str(it.get("gate") or ""),
              "implementation": owed})

    # (a) diagnostic family — what is left, when it spans more than one file.
    for fam in families:
        if any(str(i.get("id")) in claimed for i in fam["items"]) or len(fam["files"]) < 2:
            continue
        fam_members = _family_members(fam, model)
        take({"rule": RULE_DIAGNOSTIC_FAMILY, "family_key": fam["key"], "kind": "compile",
              "items": list(fam["items"]), "files": list(fam["files"]), "members": fam_members,
              "symbols": [{"kind": fam["symbol_kind"], "fqn": fam["key"], "path": fam["files"][0]}],
              "evidence": _family_evidence(fam),
              "groups": [{"key": fam["key"], "members": fam_members, "items": fam["items"]}], "gate": ""})

    # (d) configuration + consumers.
    for cfg in config_consumer_units(items, model, root):
        if str(cfg["item"].get("id")) in claimed:
            continue
        members = [_unit_member(s["path"], type_fqn=s["type"], member_id=s["member"], state="reads",
                                consumer=s["annotation"]) for s in cfg["sites"]]
        members += [_unit_member(f, state="declares-property") for f in cfg["files"] if f.endswith(".properties")]
        evidence = [{"kind": "runtime", "ref": "%s %s for: %s" % (cfg["item"].get("id"), cfg["item"].get("cause"), cfg["property"])}]
        evidence += [{"kind": "model", "ref": "%s.%s reads %s" % (s["type"], s["member"], cfg["property"])} for s in cfg["sites"]]
        take({"rule": RULE_CONFIG_CONSUMERS, "family_key": cfg["property"], "kind": str(cfg["item"].get("kind") or "config"),
              "items": [cfg["item"]], "files": list(cfg["files"]), "members": members,
              "symbols": [{"kind": "property", "fqn": cfg["property"], "path": cfg["files"][0]}],
              "evidence": evidence, "gate": str(cfg["item"].get("gate") or "")})

    clusters = [_unit_cluster(u, depths, deferred) for u in units if u["items"]]
    return clusters, claimed


def owed_adapter_units(items: list[dict[str, Any]], root: Path | None, depths: dict[str, int],
                       deferred: set[str]) -> tuple[list[dict[str, Any]], set[str]]:
    """ADR-019: one sealed unit per harness adapter an obligation is OWED.

    Every item carrying an ``owed`` row for the same contract is one repair:
    the CORS adapter answers every CORS scenario at once, the media-type
    adapter every Content-Type parameter difference at once, and neither
    authorizes the other. The unit's write set is the adapter's contract path
    and the configuration file, sealed BEFORE editing; its implementation
    obligation names the type, the path, the template digest and the rows the
    capability renders from the evidence, and assess_unit checks all of them
    after the files exist. A rendering the evidence cannot support is a typed
    blocker on the unit, never a guess."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in items:
        owed = it.get("owed") if isinstance(it.get("owed"), dict) else None
        if owed and str(owed.get("contract") or "") and str(owed.get("kind") or "") in _adapters.KINDS:
            groups[str(owed["kind"])].append(it)
    units: list[dict[str, Any]] = []
    claimed: set[str] = set()
    for kind in sorted(groups):
        rows = sorted(groups[kind], key=lambda i: str(i.get("id")))
        c = _adapters.contract(kind)
        block = ""
        props: list[tuple[str, str]] = []
        basis: dict[str, Any] = {}
        try:
            if kind == _adapters.CORS:
                if root is None:
                    raise _adapters.Refuse("CORS_POLICY_UNKNOWN", "no destination root to read the source policy from")
                policy = _adapters.cors_policy(Path(root))
                props = _adapters.cors_properties(policy)
                basis = {"source_policies": policy["source_policies"], "rules": len(policy["rules"]),
                         "security": policy["security"]}
            else:
                diffs = [d for i in rows for d in ((i.get("owed") or {}).get("differences") or [])]
                decision = _adapters.media_type_decision(diffs)
                props = _adapters.media_type_properties(decision)
                basis = {"decided": decision}
        except _adapters.Refuse as exc:
            block = "ADAPTER_UNRENDERABLE: %s" % exc
        implementation = {
            "parent": "", "parent_path": "", "type": c["type"], "path": c["path"], "members": [],
            "contract": c["contract"], "source": c["source"], "verify": "template", "adapter": kind,
            "template_sha256": c["template_sha256"], "config": c["config"],
            "properties": [[k, v] for k, v in props], "basis": basis, "install": c["install"],
        }
        evidence = [{"kind": "runtime", "ref": "%s %s %s" % (i.get("id"), i.get("rule_id"), i.get("scenario") or i.get("entry_point"))}
                    for i in rows]
        evidence.append({"kind": "catalog", "ref": "%s: %s at %s (template sha256 %s; %s)"
                                                   % (c["contract"], c["type"], c["path"], c["template_sha256"][:12], c["source"])})
        unit = {"rule": RULE_OWED_ADAPTER, "family_key": c["contract"], "kind": "config", "items": rows,
                "files": sort_unique([c["path"], c["config"]]),
                "members": [_unit_member(c["config"], state="declares-property")],
                "symbols": [{"kind": "property", "fqn": _adapters.CONTRACTS[kind]["prefix"].rstrip("."), "path": c["config"]}],
                "target_symbols": [], "evidence": evidence, "gate": "parity", "implementation": [implementation]}
        _bound_unit(unit)
        if block:
            unit["block"] = block
        unit["unit_id"] = unit_id_of(unit["rule"], unit["family_key"], unit["members"])
        unit["completion"] = _unit_completion(unit)
        claimed.update(str(i.get("id")) for i in rows)
        units.append(unit)
    return [_unit_cluster(u, depths, deferred) for u in units], claimed


def build_unit_scope(root: Path, cluster: dict[str, Any], items: list[dict[str, Any]], bundle: dict[str, Any]) -> dict[str, Any] | None:
    """The SEALED unit inventory: files AND symbols, written once at a path
    named by its own digest.

    Two seals, two jobs. FILES are the hard boundary advance.py already
    enforces. SYMBOLS are the OBLIGATION boundary: which diagnostics the
    checkpoint may tolerate, what assess_unit must find discharged, what
    amend-scope accepts as a locus, what a CONTINUE may move to. They are
    sealed at issue from the model as it stood then, so a reference the worker
    writes during the card cannot widen them."""
    unit = cluster.get("_unit_seal")
    if not isinstance(unit, dict):
        return None
    measured = sorted(str(i.get("id")) for i in items if str(i.get("id")) in set(cluster.get("items") or []))
    doc = {
        "schema": UNIT_SCHEMA,
        "kind": UNIT_KIND,
        "producer": "worklist.build_unit_scope",
        "tool": {"model": "jdk-dest-model", "version": "1.2.0"},
        "rule": unit["rule"],
        "cluster": str(cluster.get("id") or ""),
        "unit_id": unit["unit_id"],
        "family_key": unit["family_key"],
        "writable_paths": sort_unique(list(cluster.get("write_set") or unit["files"])),
        "symbols": unit["symbols"],
        "target_symbols": unit["target_symbols"],
        "members": unit["members"],
        "evidence": unit["evidence"],
        "completion": unit["completion"],
        "bounds": unit["bounds"],
        "measured": measured,
        "inputs": {"candidate_sha256": str((bundle or {}).get("candidate_sha256") or "")},
    }
    # The implementation obligations, if the rule enumerated any: the parent
    # that is owed a concrete implementation, the type and path the naming
    # contract fixes for it, and where that contract is documented. This is the
    # only thing that authorizes a path no model can have a type for yet, and
    # it is sealed with the rest — a worker cannot add one afterwards.
    if unit.get("implementation"):
        doc["implementation_obligations"] = unit["implementation"]
    doc["digest"] = batch_scope_digest(doc)
    return doc


# A sealed symbol is not one kind of thing, and the assessment turns on which
# kind it is. A type, a package or an annotation the diagnostics named is a
# RETIRED symbol: the repair is done when the file stops naming it. A member
# symbol is a DECLARATION the unit is coordinated around — a `throws` surface,
# a fragment parent — and it is the thing the repair must PRESERVE. Asking a
# member symbol to disappear is how a child that correctly imports its required
# parent was told it "still names the retired symbol".
UNIT_RETIRED_KINDS = ("type", "package", "annotation")


def unit_retired_symbols(scope: dict[str, Any]) -> list[tuple[str, str]]:
    """(fqn, kind) for the sealed symbols a repair is done with — never the
    declarations it is built around (`member`), never a configuration key
    (`property`)."""
    rows = [(str(s.get("fqn") or ""), str(s.get("kind") or "")) for s in (scope.get("symbols") or [])
            if str(s.get("kind") or "") in UNIT_RETIRED_KINDS and s.get("fqn")]
    return sorted(set(rows))


def _names_retired(names: set[str], fqn: str, kind: str) -> bool:
    """Does this declaration still name the retired symbol? A package is named
    by anything declared under it; a type or an annotation by itself."""
    if kind == "package":
        return any(n == fqn or n.startswith(fqn + ".") for n in names)
    return fqn in names


def _implements(typ: dict[str, Any], parent: str) -> bool:
    return bool(parent) and parent in [_erased(s) for s in (typ.get("supertypes") or [])]


def _assess_implementations(root: Path, scope: dict[str, Any], model: dict[str, Any] | None,
                            by_path: dict[str, list[dict[str, Any]]], rule: str) -> list[dict[str, Any]]:
    """The recorded implementation obligations, verified from the model AFTER
    the files exist: the named type is there, it IMPLEMENTS the parent the seal
    names, and the owed members are concrete. A path authorized before creation
    is authorized on a promise, and this is where the promise is checked."""
    out: list[dict[str, Any]] = []
    for row in scope.get("implementation_obligations") or []:
        if not isinstance(row, dict):
            continue
        if row.get("verify") == "template":
            out.append(_assess_owed_adapter(Path(root), row, by_path, rule))
            continue
        path, parent, want = str(row.get("path") or ""), str(row.get("parent") or ""), str(row.get("type") or "")
        base = {"member": "%s#%s" % (path, want.rsplit(".", 1)[-1]), "path": path, "rule": rule,
                "state": "implementation", "parent": parent}
        if not path or not (Path(root) / path).is_file():
            out.append(dict(base, verdict="violates",
                            detail="%s is owed a concrete implementation and %s does not exist; the obligation is "
                                   "discharged by writing it, never by leaving it" % (parent, path)))
            continue
        here = by_path.get(path) or []
        if not here:
            out.append(dict(base, verdict="inconclusive", detail="the model has no type for %s" % path))
            continue
        typ = next((t for t in here if str(t.get("fqn") or "") == want), here[0])
        if str(typ.get("resolution") or "") != "full":
            out.append(dict(base, verdict="inconclusive", detail="the compiler could not fully resolve %s" % path))
            continue
        if not _implements(typ, parent):
            out.append(dict(base, verdict="violates",
                            detail="%s does not implement %s; the path was authorized on that relationship and the "
                                   "model does not state it" % (typ.get("fqn"), parent)))
            continue
        declared = {str(m.get("signature") or "") for m in (typ.get("declared") or [])
                    if isinstance(m, dict) and m.get("has_body")}
        missing = sorted(s for s in (row.get("members") or []) if str(s) not in declared)
        if missing:
            out.append(dict(base, verdict="violates",
                            detail="%s implements %s but declares no body for %s; an abstract answer answers nothing"
                                   % (typ.get("fqn"), parent, ", ".join(missing[:3]))))
            continue
        out.append(dict(base, verdict="ok",
                        detail="%s implements %s and declares %d concrete member(s) it owed"
                               % (typ.get("fqn"), parent, len(row.get("members") or []))))
    return out


def _assess_owed_adapter(root: Path, row: dict[str, Any], by_path: dict[str, list[dict[str, Any]]],
                         rule: str) -> dict[str, Any]:
    """An owed harness adapter, after the fact: the file is the template
    byte-for-byte (the sealed digest, and the template the harness ships now),
    the model declares the contract's type there, and the configuration carries
    exactly the sealed rendered rows -- no more of its own family, no fewer."""
    path, want, kind = str(row.get("path") or ""), str(row.get("type") or ""), str(row.get("adapter") or "")
    base = {"member": "%s#%s" % (path, want.rsplit(".", 1)[-1]), "path": path, "rule": rule, "state": "adapter",
            "contract": str(row.get("contract") or "")}
    if kind not in _adapters.KINDS:
        return dict(base, verdict="violates", detail="the sealed obligation names no known adapter (%r)" % kind)
    if str(row.get("template_sha256") or "") != _adapters.template_sha256(kind):
        return dict(base, verdict="inconclusive",
                    detail="the harness template changed since this unit was sealed (%s, now %s); re-plan the card"
                           % (str(row.get("template_sha256"))[:12], _adapters.template_sha256(kind)[:12]))
    props = [(str(k), str(v)) for k, v in (row.get("properties") or [])]
    problems = _adapters.verify(Path(root), kind, props)
    if problems:
        return dict(base, verdict="violates",
                    detail="the %s repair is not installed as the capability renders it: %s (run %s)"
                           % (row.get("contract"), "; ".join(problems[:3]), row.get("install") or "the installer"))
    here = by_path.get(path) or []
    if not here:
        return dict(base, verdict="inconclusive", detail="the model has no type for %s" % path)
    if not any(str(t.get("fqn") or "") == want for t in here):
        return dict(base, verdict="violates", detail="%s declares %s, not the contract's %s"
                    % (path, ", ".join(sorted(str(t.get("fqn")) for t in here)), want))
    return dict(base, verdict="ok", detail="%s is the %s template, declares %s, and %s carries the %d rendered row(s)"
                % (path, row.get("contract"), want, row.get("config"), len(props)))


def assess_unit(root: Path, scope: dict[str, Any]) -> list[dict[str, Any]]:
    """Every sealed member against the rule its unit declares, from the
    compiled tree. `inconclusive` is never a pass: the caller must refuse.

    The assessment is RULE-SPECIFIC, because the rules ask different things:

    * `unit/diagnostic-family` and `unit/package-leaf` retire a symbol, so a
      member is done when its file no longer names one and still declares what
      it declared;
    * `unit/declaration-closure` is built AROUND a declaration. The declaration
      and the inheritance are what must survive — a fragment parent is required
      by the children that extend it, and a child importing its parent is
      correct, not a residue. What it must gain is a concrete implementation of
      every member it owes; what it must not lose is a caller. The gate the
      unit carries is the other half, and `progress()` requires it.
    """
    rule = str(scope.get("rule") or "")
    if rule == CHECKED_FAMILY_RULE:
        return assess_checked_family(root, scope)
    if rule == BATCH_RULE:
        return assess_batch_scope(root, scope)
    try:
        model = dest_model(Path(root))
    except DestModelUnavailable as exc:
        return [{"member": "*", "verdict": "inconclusive", "detail": "the destination model is unavailable: %s" % exc}]
    types = {(_unit_path(t), str(t.get("fqn") or "")): t for t in _unit_types(model)}
    by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in _unit_types(model):
        by_path[_unit_path(t)].append(t)
    # only the symbols this rule RETIRES; a sealed declaration is preserved,
    # not made to disappear
    retired = unit_retired_symbols(scope)
    out: list[dict[str, Any]] = []
    for row in scope.get("members") or []:
        path, fqn, mid = str(row.get("path") or ""), str(row.get("type") or ""), str(row.get("member_id") or "")
        state, parent = str(row.get("state") or ""), str(row.get("parent") or "")
        name = "%s%s" % (path, ("#" + mid) if mid else "")
        base = {"member": name, "path": path, "rule": rule, "state": state}
        if not path or not (Path(root) / path).is_file():
            out.append(dict(base, verdict="violates", detail="the file is gone; a unit member is not discharged by deleting its file"))
            continue
        if not path.endswith(".java"):
            out.append(dict(base, verdict="ok", detail="a configuration locus; the property check is the unit's own"))
            continue
        here = by_path.get(path) or []
        if not here:
            out.append(dict(base, verdict="inconclusive", detail="the model has no type for %s" % path))
            continue
        typ = types.get((path, fqn)) or here[0]
        if str(typ.get("resolution") or "") != "full":
            out.append(dict(base, verdict="inconclusive", detail="the compiler could not fully resolve %s" % path))
            continue
        names: set[str] = set()
        for t in here:
            names |= unit_type_refs(t)
        still = sorted(s for s, kind in retired if _names_retired(names, s, kind))
        if mid:
            ids = member_ids(typ)
            member = next((m for m in typ.get("declared") or [] if ids.get(str(m.get("signature") or "")) == mid or str(m.get("name") or "") == mid), None)
            if member is None:
                out.append(dict(base, verdict="violates", detail="the member %s is gone; its operation is not repaired by deleting it" % mid))
                continue
            consumer = str(row.get("consumer") or "")
            if consumer and consumer not in (member.get("calls") or []) and not consumer.startswith("@"):
                out.append(dict(base, verdict="violates", detail="%s no longer calls %s; the operation the value fed must be preserved" % (mid, consumer)))
                continue
        # the INHERITANCE the closure was formed on: a row that implements a
        # sealed declaration must still implement it. Dropping the parent is
        # not a repair of the parent.
        if state == "implements" and parent and not any(_implements(t, parent) for t in here):
            out.append(dict(base, verdict="violates",
                            detail="%s no longer implements %s; the unit is coordinated around that declaration and "
                                   "severing it is not a repair of it" % (typ.get("fqn") or path, parent)))
            continue
        if still:
            out.append(dict(base, verdict="violates", detail="%s still names the retired symbol(s) %s" % (path, ", ".join(still))))
            continue
        out.append(dict(base, verdict="ok", detail="%s no longer names the unit's retired symbols and still declares what it declared" % path))
    out.extend(_assess_implementations(Path(root), scope, model, by_path, rule))
    return out


# --- what a unit's sealed symbols EXPLAIN at its checkpoint -----------------
#
# The partition the introduced-attribution veto uses, and the one the
# checkpoint's compile slot uses. It is one predicate with one definition, so
# the veto and the acceptance rule can never disagree about a diagnostic.

def _symbol_match(key: str, kind: str, fqn: str) -> bool:
    """Does the RESOLVED identity name this sealed symbol?

    Only a qualified identity can. The key is what the declaring file's imports
    bound the diagnostic's token to, asked of the compiler model; a token
    nothing bound is a SPELLING, and a spelling resolves to no type at all. An
    unbound `UriBuilder` is not jakarta.ws.rs.core.UriBuilder because it is
    spelled like its last segment — it is an unresolved name, and the whole
    reason this predicate exists is that acceptance must not take one for the
    other. jakarta.ws.rs.Context is likewise not jakarta.ws.rs.core.Context.

    A PACKAGE identity names every symbol declared under it; that is a
    qualified relation between two qualified names, not a resemblance."""
    if not key or not fqn or "." not in key:
        return False
    if key == fqn:
        return True
    if kind == "package":
        return fqn.startswith(key + ".")
    return False


def unit_explained_regressions(scope: dict[str, Any], items: list[dict[str, Any]],
                               model: dict[str, Any] | None = None,
                               identities: set[str] | None = None) -> tuple[list[dict[str, Any]], str]:
    """(the rows a unit's sealed symbols explain, why the tolerated set is refused).

    A currently reported compile diagnostic ``d`` is EXPLAINED iff all four:

    1. ``d.path`` is inside the file seal (``writable_paths``), and
    2. ``compile_token(d)`` RESOLVES, through the declaring file's imports in
       the compiler model -- the same resolution the former used -- to a
       QUALIFIED identity: a token nothing binds resolves to nothing and
       explains nothing, whatever it is spelled like, and
    3. that qualified identity names a symbol in ``scope.symbols`` (the unit is
       still working on it) or in ``scope.target_symbols`` (the replacement it
       is moving to), and
    4. in the target case, that row carries a ``catalog_row`` keyed by the
       qualified name: a DOCUMENTED mapping recorded at seal time, never a
       symbol the worker invented.

    Conditions 2 and 4 are the two counterexamples the architect reproduced.
    jakarta.ws.rs.core.Context has a compat-mapping row and jakarta.ws.rs.Context
    does not, so a candidate that invented the second one stays unexplained and
    REVERTED; and an unbound ``UriBuilder`` -- a file with no import for it at
    all -- is not the catalogued jakarta.ws.rs.core.UriBuilder, because a
    spelling is not an identity.

    Two guards on the tolerated set, both fail-closed:

    * without the destination model nothing resolves, so nothing is explained;
    * the tolerated set must be ONE symbol family (the unit's own). A unit that
      would tolerate two different families is laundering a second defect
      through its checkpoint, and the whole set is refused.

    ``identities`` narrows the question to the diagnostics acceptance is asking
    about (the introduced set); absent, every reported diagnostic is considered."""
    if not isinstance(scope, dict) or str(scope.get("kind") or "") != UNIT_KIND:
        return [], "the card carries no unit seal, so no symbol of it can explain anything"
    if model is None:
        return [], ("the destination model is unavailable, so no token can be resolved through the declaring file's "
                    "imports; a bare name matched by spelling is exactly the mistake this rule refuses (v9 t_3903f495)")
    paths = {str(p) for p in (scope.get("writable_paths") or [])}
    sealed = [(str(s.get("fqn") or ""), str(s.get("kind") or "")) for s in (scope.get("symbols") or []) if s.get("fqn")]
    # a catalogued target is a row keyed by a QUALIFIED name whose target is
    # qualified too: an unqualified row cannot document an identity, only a
    # spelling, and a checkpoint that tolerated one would tolerate a typo
    targets = [t for t in (scope.get("target_symbols") or [])
               if isinstance(t, dict) and "." in str(t.get("to") or "")
               and isinstance(t.get("catalog_row"), dict) and t["catalog_row"]
               and "." in str(t["catalog_row"].get("key") or "")]
    annotations = _annotation_simples(model)
    rows: list[dict[str, Any]] = []
    families: set[str] = set()
    for it in items or []:
        if str(it.get("source") or "") != "javac":
            continue
        ident = str(it.get("identity") or "")
        if identities is not None and ident not in identities:
            continue
        path = str(it.get("path") or "")
        if path not in paths:
            continue
        key, kind = resolve_compile_symbol(model, it, annotations)
        # an UNRESOLVED token explains nothing: nothing in the file binds it, so
        # it names no type, and matching it by spelling against a sealed symbol
        # or a catalogued target is the defect, not the rule
        if not key or "." not in key:
            continue
        hit = next((f for f, _k in sealed if _symbol_match(key, kind, f)), "")
        catalog_row: dict[str, Any] = {}
        if hit:
            symbol, why = hit, "sealed"
        else:
            row = next((t for t in targets if _symbol_match(key, kind, str(t.get("to") or ""))), None)
            if row is None:
                continue
            symbol, why, catalog_row = str(row.get("to") or ""), "target", dict(row.get("catalog_row") or {})
        families.add(symbol)
        rows.append({"identity": ident, "path": path, "code": str(it.get("rule_id") or ""),
                     "token": key, "symbol": symbol, "boundary": why, "catalog_row": catalog_row})
    if len({r["symbol"] for r in rows}) > 1:
        return [], ("the diagnostics this checkpoint would tolerate name %d different symbol families (%s); a unit may "
                    "only carry its OWN family through its checkpoint, and anything else is a second defect"
                    % (len(families), ", ".join(sorted(families)[:3])))
    return sorted(rows, key=lambda r: (r["path"], r["identity"])), ""


def unit_continue_scope(scope: dict[str, Any], items: list[dict[str, Any]]) -> set[str]:
    """The identities a unit card may CONTINUE to: a diagnostic reported now at
    a file the unit seals AND at a member row its inventory carries.

    This is what "the compiler names the next member of the same unit" means
    without reading a line number: the flow-analysis codes (an unhandled
    checked exception on a `throws` surface) are reported one site per
    compilation and carry no symbol token at all, so they are never explained
    by a symbol and the card continues on them instead."""
    if not isinstance(scope, dict) or str(scope.get("kind") or "") != UNIT_KIND:
        return set()
    paths = {str(p) for p in (scope.get("writable_paths") or [])}
    members = {str(m.get("path") or "") for m in (scope.get("members") or [])}
    out: set[str] = set()
    for it in items or []:
        if str(it.get("source") or "") != "javac" or not it.get("identity"):
            continue
        path = str(it.get("path") or "")
        if path in paths and path in members:
            out.add(str(it["identity"]))
    return out


def retry_key(cluster: dict[str, Any], items: list[dict[str, Any]] | None = None) -> str:
    """What a retry budget is counted against.

    Card identity and retry identity are not the same thing. A card is the
    work in front of a worker now; a budget is the patience the run has for
    one PROBLEM. So the key is the gate, the normalised cause and the file --
    never the member, the item set, the attempt number or the wording, all of
    which change while the same problem is being worked.

    Two different causes at one file are two problems and get their own
    budgets; the same cause reported about a different member does not
    replenish anything. Anything else that is not a
    runtime obligation keeps counting against its cluster id, which for a
    file cluster is already the path (worklist.cluster_items).

    A checked-exception family counts against the family: its signature and
    the step that introduced it. Exposing Pet after fixing Owner is the same
    family, the same key and the same budget."""
    ref = cluster.get("batch_scope") or {}
    # A unit counts against the PROBLEM, not the card: unit_id is a digest of
    # (rule, family key, member keys) and therefore survives remeasurement,
    # attempt numbers and scope revisions.
    if str(ref.get("kind") or "") == UNIT_KIND and ref.get("unit_id"):
        return "rk:unit:%s" % ref["unit_id"]
    if str(ref.get("rule") or "") == CHECKED_FAMILY_RULE and ref.get("family_id"):
        return "rk:compile:checked-family:%s" % ref["family_id"]
    rows = [i for i in (items or []) if str(i.get("id")) in set(cluster.get("items") or [])]
    runtime = [i for i in rows if str(i.get("source")) == "runtime"]
    if not runtime:
        return str(cluster.get("id") or "")
    gates = sorted({str(i.get("gate") or "") for i in runtime})
    causes = sorted({str(i.get("cause") or "") for i in runtime})
    paths = sorted({str(i.get("path") or "") for i in runtime})
    if len(gates) != 1 or len(causes) != 1 or len(paths) != 1:
        return str(cluster.get("id") or "")
    return "rk:%s:%s:%s" % (gates[0], causes[0], sha256_bytes(paths[0].encode("utf-8"))[:12])


def gate_items(worklist: dict[str, Any], gate: str) -> set[str]:
    """The ids of the obligations one gate currently holds.

    For ``parity`` those are the obligations the composed receipt's own
    verdicts produced in this measurement (parity_items), which is what the
    comparison the acceptance path re-ran reports NOW."""
    return {str(i["id"]) for i in (worklist.get("items") or []) if str(i.get("gate") or "") == gate}


def _gate_passing(runtime: dict[str, Any] | None, name: str) -> bool:
    row = (runtime.get(name) or {}) if isinstance(runtime, dict) else {}
    return bool(row.get("ran")) and row.get("rc") == 0 and (row.get("ready", True) is not False)


def _unit_progress(a: list[int], b: list[int], *, scope: dict[str, Any], assessment: list[dict[str, Any]] | None,
                   gate: str, prev_runtime: dict[str, Any] | None, cur_runtime: dict[str, Any] | None,
                   prev_parity: dict[str, Any] | None, cur_parity: dict[str, Any] | None,
                   issued_identities: set[str] | None, cur_identities: set[str] | None,
                   explained: set[str] | None, family_scope: set[str] | None) -> tuple[bool, str] | None:
    """A unit is judged at its CHECKPOINT, not per edit.

    A coordinated repair across several files passes through states in which
    the tuple is unchanged or briefly larger -- that is what "coordinated"
    means, and the loop never measured the intermediate states anyway
    (verify.py runs when the worker asks). What was not true before this
    branch is that the CHECKPOINT itself demanded a strictly smaller tuple, so
    a repair that had to move six controllers at once could not be accepted
    whatever it did.

    So the compile slot -- and only the compile slot -- may stand still or
    briefly rise, and only for diagnostics the unit's SEALED symbols explain
    (unit_explained_regressions). Everything else is exactly as strict as it
    was: no new mandatory obligation (vetoed by the caller before this runs),
    no regressed test or incident slot, no gate going backwards, every one of
    the unit's own sealed identities gone, and every sealed member assessed
    from the tree.

    Returns None when the verdict belongs to a branch below: a unit that
    carries a gate is discharged by that gate passing, which the phase-aware
    branches already decide -- these checks are added on top of them, not
    instead of them."""
    uid = str(scope.get("unit_id") or scope.get("cluster") or "this unit")
    rule = str(scope.get("rule") or "")
    # 1. no new mandatory obligation -- the caller's veto, unchanged, already run.
    # 2. the NON-compile slots may not regress. The relaxation is for the
    #    compile count only: a unit is never a licence to break a test or to
    #    reintroduce an MTA obligation.
    for idx, name in ((0, "mandatory-incident"), (2, "failing-test")):
        if b[idx] > a[idx]:
            return False, ("the %s slot regressed (%s from %s); a unit's checkpoint relaxes the COMPILE count only, and "
                           "never licenses a broken test or a reintroduced obligation" % (name, b, a))
    # 3. the gates may not go backwards, in either direction of the phase order.
    for name in ("package", "boot"):
        if _gate_passing(prev_runtime or {}, name) and not _gate_passing(cur_runtime or {}, name):
            return False, ("the %s gate was passing and is not any more; %s may not break a phase it did not repair"
                           % (name, uid))
    before, after = parity_state(prev_parity), parity_state(cur_parity)
    if before["known"] and after["known"]:
        regressed = sorted(ep for ep, v in before["entry_points"].items()
                           if v == "PASS" and after["entry_points"].get(ep, "") != "PASS")
        if regressed:
            return False, ("the parity comparison at %s was PASS before this candidate and is %s now; %s may not break a "
                           "scenario that was passing"
                           % (regressed[0], after["entry_points"].get(regressed[0]) or "no longer in the receipt", uid))
    # 4. the unit's OWN javac identities are gone. Asked of the line-free
    #    identity, as everywhere else: a moved site is the same site.
    still = sorted(set(issued_identities or ()) & set(cur_identities or ()))
    if still:
        return False, ("%s still reports %d of the diagnostic(s) it sealed (%s); a checkpoint discharges the whole unit, "
                       "not a part of it" % (uid, len(still), ", ".join(still[:2])))
    # 5. every sealed member, assessed from the TREE (assess_unit), not from
    #    anything the worker wrote. An already-correct member earns nothing and
    #    costs nothing; an inconclusive one is never a pass.
    rows = list(assessment or [])
    bad = [r for r in rows if r.get("verdict") == "violates"]
    if bad:
        return False, ("%d sealed member(s) of %s still violate %s: %s"
                       % (len(bad), uid, rule or "the unit's rule",
                          "; ".join("%s (%s)" % (r.get("member"), r.get("detail")) for r in bad[:3])))
    unknown = [r for r in rows if r.get("verdict") == "inconclusive"]
    if unknown:
        return UNPROVEN, ("%d sealed member(s) of %s could not be assessed against %s: %s. An assessment that could not "
                          "be made is not one that passed; the candidate is retained unaccepted and no attempt is spent"
                          % (len(unknown), uid, rule or "the unit's rule",
                             "; ".join("%s (%s)" % (r.get("member"), r.get("detail")) for r in unknown[:3])))
    # 6. where a GATE is the obligation, that gate passing is the discharge and
    #    the phase-aware branch below decides it, with everything above already
    #    required on top of it.
    if gate in ("package", "boot", "parity"):
        return None
    if issued_identities is None or cur_identities is None:
        return None  # no identities to partition: today's rules decide
    # 7. the compile slot.
    if b < a:
        return True, "measure %s < %s and every obligation %s sealed is discharged at its checkpoint" % (b, a, uid)
    now = sorted(set(cur_identities) - set(issued_identities))
    unexplained = [i for i in now if i not in set(explained or ())]
    if not unexplained:
        return True, ("the unit's obligations are discharged at its checkpoint; %d diagnostic(s) remain that its sealed "
                      "symbols explain (%s), recorded as explained_regressions"
                      % (len(now), ", ".join(now[:2]) or "none"))
    if family_scope is not None and now and set(now) <= set(family_scope):
        return RETAIN, ("every diagnostic %s sealed is gone and the compiler now reports %s, another member of the same "
                        "unit. Not ACCEPTED: the count did not fall. The candidate stays; repair the members it names "
                        "inside the sealed write set" % (uid, ", ".join(now[:2])))
    return EXPOSED, ("every diagnostic %s sealed is gone and the compiler now reports %s, which its sealed symbols do "
                     "not explain (the file seal, the sealed symbols and the catalogued targets are the boundary). "
                     "Not ACCEPTED; the candidate is preserved as a typed diagnosis"
                     % (uid, ", ".join(unexplained[:2]) or "an unplaced diagnostic"))


def progress(prev: dict[str, Any], cur: dict[str, Any], prev_ids: set[str], cur_ids: set[str],
             *, gate: str = "", prev_runtime: dict[str, Any] | None = None, cur_runtime: dict[str, Any] | None = None,
             issued_items: list[str] | None = None, prev_gate_items: set[str] | None = None,
             cur_gate_items: set[str] | None = None, cur_item_ids: set[str] | None = None,
             issued_identities: set[str] | None = None, cur_identities: set[str] | None = None,
             family_scope: set[str] | None = None,
             prev_parity: dict[str, Any] | None = None, cur_parity: dict[str, Any] | None = None,
             unit_scope: dict[str, Any] | None = None, unit_assessment: list[dict[str, Any]] | None = None,
             explained: set[str] | None = None, parity_remeasured: set[str] | None = None,
             parity_discharged: dict[str, tuple[bool, str]] | None = None) -> tuple[bool, str]:
    """Accept iff strictly smaller lexicographically and no new mandatory obligation.

    Phase-aware: a card issued for the ``package``, ``boot`` or ``parity`` gate
    is repairing something the compile/test tuple cannot see, so fixing it can
    leave the tuple unchanged. Such a step is accepted when its OWN gate goes
    from failing to passing and the tuple does not regress. The tuple still may
    not get worse, no new mandatory obligation may appear, and the other gates
    may not go backwards -- a repair is not a licence to break the phase before
    it. The parity gate is the scenario comparison M4 runs (run-parity.py), and
    ``prev_parity`` / ``cur_parity`` are the composed receipts before and after;
    it discharges an obligation only POSITIVELY, by the receipt recording its
    scenario as PASS -- or, per obligation, by its OWN re-run record
    (``parity_discharged``: a scenario obligation's scenario, a read-oracle
    obligation's read oracle) coming back PASS or losing its own kind of
    difference with nothing introduced -- because an obligation also
    disappears when its scenario became INCONCLUSIVE. A SCOPED comparison
    (``parity_remeasured``: its scenarios and the entry points whose read
    oracle it re-ran) carries what it did not re-run from ``prev_parity``.

    Compile-aware: javac reports one diagnostic at a time. When the issued
    compile failure disappears and the observed compile count does not
    decrease, that is incomplete coverage, not progress, and never ACCEPTED.
    "Still reported" is asked of the diagnostic's IDENTITY -- file, resolved
    member and call site, exception -- never of its line, so an edit that
    moves the site is not a repair (issued_identities / cur_identities). What
    the compiler reports instead decides the rest: inside this card's sealed
    family (family_scope) the card CONTINUES (RETAIN); anywhere else it is a
    typed diagnosis that preserves the candidate (EXPOSED).

    Unit-aware: a card carrying a sealed v4 UNIT inventory (``unit_scope``, with
    ``unit_assessment`` from assess_unit and ``explained`` from
    unit_explained_regressions) is judged at its CHECKPOINT -- see
    _unit_progress. Every other call site passes none of the three and is
    byte-for-byte unchanged."""
    if parity_remeasured is not None:
        # a SCOPED comparison: what it did not re-run is carried, not regressed
        cur_parity = carry_unmeasured(prev_parity, cur_parity, parity_remeasured)[0]
    if not cur.get("known"):
        return False, "measure not fully known (%s)" % "; ".join(cur.get("blocked") or ["compile/tests/incidents unverified"])
    if not prev.get("known"):
        # unknown ranks above every known measure (+inf): a candidate whose
        # every component the tools measured beats a baseline they could not
        # measure (an unresolvable bootstrap pom, a skipped rescan), provided
        # it adds no mandatory obligation
        new_mandatory = sorted(i for i in cur_ids - prev_ids if i.startswith("inc:"))
        if new_mandatory:
            return False, "new mandatory obligation(s): %s" % ",".join(new_mandatory[:5])
        return True, "measure %s became known (was: %s)" % (cur["tuple"], "; ".join(prev.get("blocked") or ["unknown"]))
    a, b = list(prev["tuple"]), list(cur["tuple"])
    # ids are obligation_keys() (rule|file#n); a content-hash id (old steps) is
    # compared as-is, so an old baseline still vetoes on a brand-new id.
    # A key on a new file is a RELOCATION, not a new obligation, when the
    # rule's total occurrence count did not grow: the documented merge of a
    # Spring profile file moves its keys (and the incidents on them) into
    # application.properties (pilot v6 t_2fdf0985 was vetoed for
    # localhost-jdbc-00002 following the datasource URL it had moved).
    def _rule(key: str) -> str:
        body = key[4:] if key.startswith("inc:") else key
        return body.split("|", 1)[0] if "|" in body else body
    prev_by_rule: dict[str, int] = {}
    cur_by_rule: dict[str, int] = {}
    for k in prev_ids:
        if k.startswith("inc:"):
            prev_by_rule[_rule(k)] = prev_by_rule.get(_rule(k), 0) + 1
    for k in cur_ids:
        if k.startswith("inc:"):
            cur_by_rule[_rule(k)] = cur_by_rule.get(_rule(k), 0) + 1
    new_mandatory = sorted(i for i in cur_ids - prev_ids if i.startswith("inc:") and cur_by_rule.get(_rule(i), 0) > prev_by_rule.get(_rule(i), 0))
    if new_mandatory:
        return False, "new mandatory obligation(s): %s" % ",".join(new_mandatory[:5])
    # The UNIT checkpoint, after the new-obligation veto (which is global and
    # therefore already forbids a new mandatory obligation outside the unit)
    # and before the generic b < a test, which is what it relaxes.
    if isinstance(unit_scope, dict) and str(unit_scope.get("kind") or "") == UNIT_KIND:
        verdict = _unit_progress(a, b, scope=unit_scope, assessment=unit_assessment, gate=gate,
                                 prev_runtime=prev_runtime, cur_runtime=cur_runtime,
                                 prev_parity=prev_parity, cur_parity=cur_parity,
                                 issued_identities=issued_identities, cur_identities=cur_identities,
                                 explained=explained, family_scope=family_scope)
        if verdict is not None:
            return verdict
    if b < a:
        return True, "measure %s < %s" % (b, a)
    if gate == "parity":
        # The parity gate is a comparison, not a build: the destination
        # answers differently from the source at a named entry point, and the
        # only thing that can say the repair landed is that comparison run
        # again. It is re-run by the acceptance path for this card's own
        # scenarios (run-verify.sh --mode acceptance → run-parity.py).
        if b > a:
            return False, "measure %s regressed from %s; a parity repair may not make compilation or tests worse" % (b, a)
        for name in ("package", "boot"):
            if _gate_passing(prev_runtime or {}, name) and not _gate_passing(cur_runtime or {}, name):
                return False, ("the %s gate was passing and is not any more; a parity repair may not break the phase "
                               "before it" % name)
        before = parity_state(prev_parity)
        after = parity_state(cur_parity)
        if parity_unmeasured(prev_parity):
            return UNPROVEN, ("the accepted tree has no parity baseline (%s): whether this candidate broke a passing "
                              "scenario cannot be asked. The candidate is retained unaccepted and no attempt is spent; "
                              "run the sealed comparison on the accepted tree and %s, then advance again"
                              % (parity_unmeasured(prev_parity), REFRESH_PARITY))
        if not after["known"] or not before["known"] or cur.get("parity_mismatches") is None:
            # The measurement contract, applied to parity: a receipt that was
            # not composed in this verification (the runner could not run, the
            # composer refused) measured nothing about this card's obligation,
            # and it cannot prove that no other scenario regressed either. That
            # is not a failed repair -- the candidate is retained, unaccepted,
            # and no attempt is spent.
            return UNPROVEN, ("the parity comparison is not a measurement here (receipt before: %s, after: %s, parity slot "
                              "of the measure: %s): nothing was compared, so this card's obligation is neither discharged "
                              "nor refuted. The candidate is retained unaccepted; run run-verify.sh --mode acceptance for "
                              "this card -- its acceptance path re-runs %s for the issued scenarios -- and advance again"
                              % ("composed" if before["known"] else "not composed",
                                 "composed" if after["known"] else "not composed",
                                 "unknown" if cur.get("parity_mismatches") is None else cur.get("parity_mismatches"),
                                 PARITY_RECEIPT.as_posix()))
        issued_par = {str(i) for i in (issued_items or []) if str(i).startswith("parity:")}
        still = sorted(issued_par & (cur_gate_items or set()))
        if still:
            return False, ("the parity obligation %s is still reported (its identity is the entry point, the scenario and "
                           "the kind of diff; a comparator that rewords its diff reports the same obligation)"
                           % ",".join(still[:2]))
        # A parity repair may not break another scenario. Asked of the receipt,
        # not of the obligation ids: a scenario that became INCONCLUSIVE mints
        # no obligation at all, and would be invisible to a comparison of ids.
        regressed = sorted(ep for ep, v in before["entry_points"].items()
                           if v == "PASS" and after["entry_points"].get(ep, "") != "PASS")
        if regressed:
            return False, ("the parity comparison at %s was PASS before this candidate and is %s now; a parity repair may "
                           "not break another scenario"
                           % (regressed[0], after["entry_points"].get(regressed[0]) or "no longer in the receipt"))
        appeared = sorted((cur_gate_items or set()) - (prev_gate_items or set()) - issued_par)
        if appeared:
            return False, ("this candidate reports parity obligation(s) the gate did not hold when the card was issued: %s"
                           % ",".join(appeared[:3]))
        if issued_par:
            not_passed = []
            for oid in sorted(issued_par):
                row = after["obligations"].get(oid)
                judged = (parity_discharged or {}).get(oid)
                if judged is not None:
                    # H8: EVERY obligation that has its own record -- a
                    # scenario's (PARITY, PARITY_CORS, PARITY_CONTENT_TYPE,
                    # PARITY_GENERATED_BODY) or a read oracle's -- is discharged
                    # by THAT record (parity_obligation_discharged), never by
                    # the entry-point row: a row partly re-run composes
                    # INCONCLUSIVE while the card's own scenarios came back PASS
                    # (v9 t_3c2ed945, a correct pom repair reverted)
                    if judged[0]:
                        continue
                    not_passed.append("%s (%s: %s)" % (oid, (row or {}).get("verdict") or "no row in the receipt", judged[1]))
                    continue
                if row is None or row.get("verdict") != "PASS":
                    not_passed.append("%s (%s)" % (oid, (row or {}).get("verdict") or "no row in the receipt"))
            if not_passed:
                return False, ("the parity obligation %s is still reported: its scenario did not come back PASS in %s"
                               % ("; ".join(not_passed[:2]), PARITY_RECEIPT.as_posix()))
            named = sorted({(after["obligations"][o].get("scenario") or after["obligations"][o].get("entry_point") or o)
                            for o in issued_par})
            return True, ("the parity comparison discharges %s: %s came back PASS in %s with the measure unchanged at %s"
                          % (",".join(sorted(issued_par)[:3]), ", ".join(named[:3]), PARITY_RECEIPT.as_posix(), b))
        return True, "the parity comparison reports no obligation for this card and no scenario regressed (measure %s)" % b
    if gate in ("package", "boot"):
        prev_rt = prev_runtime or {}
        cur_rt = cur_runtime or {}

        def _passing(rt: dict[str, Any], name: str) -> bool:
            return _gate_passing(rt, name)

        if b > a:
            return False, "measure %s regressed from %s; a %s repair may not make compilation or tests worse" % (b, a, gate)
        other = "package" if gate == "boot" else "boot"
        if _passing(prev_rt, other) and not _passing(cur_rt, other):
            return False, "the %s gate was passing and is not any more; a %s repair may not break the phase before it" % (other, gate)
        issued_now = {i for i in (issued_items or []) if str(i).startswith("rt:")}
        if _passing(cur_rt, gate) and not (issued_now & (cur_gate_items or set())):
            # the gate passing is the only thing that can discharge this card's
            # obligations, and it discharges all of them at once (a batch)
            if issued_now:
                return True, "the %s gate passes and discharges %s" % (gate, ",".join(sorted(issued_now)[:3]))
            return True, "the %s gate passes with the measure unchanged at %s" % (gate, b)
        if not _passing(cur_rt, gate):
            # A failing gate cannot discharge an obligation. This tool reports
            # ONE failure at a time, so an issued obligation's disappearance
            # from the output is not proof it was repaired: it may simply not
            # have been reached. Accepting on absence is the same error as
            # calling an unrun check clean, and it is how a half-repaired
            # repository could be promoted (architect review, 2026-09-11).
            #
            # So while the gate fails there are exactly two outcomes: the
            # obligation is still reported, which is proof the repair did not
            # land -- or it is not, which is unproven and the candidate is
            # RETAINED rather than accepted or thrown away.
            issued = {i for i in (issued_items or []) if str(i).startswith("rt:")}
            after = cur_gate_items or set()
            if issued and (issued & after):
                return False, "the %s obligation %s is still reported (its identity is the gate, the cause, the file and the member; a different message at the same place is the same obligation)" % (gate, ",".join(sorted(issued & after)[:2]))
            if issued:
                return UNPROVEN, ("the %s gate still fails and %s is no longer reported, which is not proof it was repaired: this tool "
                                "reports one failure at a time. The candidate is retained unaccepted; repair the members it now names "
                                "in the same candidate, and the gate passing discharges them together"
                                % (gate, ",".join(sorted(issued)[:2])))
            return False, "the %s gate is still not passing (%s)" % (gate, "; ".join((cur_rt.get("reasons") or [])[:2]) or "see its receipt")
    issued_err = {str(i) for i in (issued_items or []) if str(i).startswith("err:")}
    if issued_err and b == a:
        by_identity = issued_identities is not None and cur_identities is not None
        if by_identity:
            still = sorted(set(issued_identities or ()) & set(cur_identities or ()))
            if still:
                return False, ("the compile obligation %s is still reported (identity: file, member, call site and exception; "
                               "a moved line is the same site)" % ",".join(still[:2]))
            now = sorted(set(cur_identities or ()) - set(issued_identities or ()))
        else:
            still = sorted(issued_err & set(cur_item_ids or []))
            if still:
                return False, "the compile obligation %s is still reported" % ",".join(still[:2])
            now = []
        if family_scope is not None and now and set(now) <= set(family_scope):
            return RETAIN, ("the issued compile diagnostic is no longer reported and the compiler now reports %s, another "
                            "member of this card's sealed family. Not ACCEPTED: the count did not fall. The candidate stays; "
                            "repair the members it names in this card" % ",".join(now[:2]))
        return EXPOSED, ("the issued compile diagnostic is no longer reported, which is not proof it was repaired (the compiler "
                         "reports one error at a time), and what it reports now (%s) is outside every sealed scope of this card. "
                         "Not ACCEPTED; the candidate is preserved as a typed diagnosis" % (",".join(now[:2]) or "an unplaced diagnostic"))
    return False, "measure %s did not decrease from %s" % (b, a)


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------


def load_run(root: Path) -> dict[str, Any]:
    p = Path(root) / VERIFY_RUN
    return load_json(p) if p.is_file() else {}


def _guard_owned(clusters: list[dict[str, Any]], owned: dict[str, Any]) -> None:
    """The harness-owned rule as an invariant on every write set, whatever
    formed it: an owned path is dropped, and a cluster left with nothing
    writable is a typed blocker, never an open card."""
    for c in clusters:
        ws = list(c.get("write_set") or [])
        kept = [w for w in ws if not is_harness_owned(w, owned)]
        if kept == ws:
            continue
        c["write_set"] = kept
        c.setdefault("harness_owned_paths", sorted(set(ws) - set(kept)))
        if not kept and c.get("status") in ("open", "deferred"):
            c["status"] = "blocked"
            c["block"] = ("every path of this cluster is under a harness-owned generated root (%s); no worker may be "
                          "issued it (ADR-015, ADR-019)" % ", ".join(owned.get("roots") or []))


def build_worklist(root: Path, *, write: bool = True) -> dict[str, Any]:
    root = Path(root)
    bundle = load_json(root / EVIDENCE_BUNDLE)
    canary = str((bundle.get("migration") or {}).get("canary_rule_id") or "")
    run = load_run(root)
    findings_path = root / MTA_RESCAN_FINDINGS
    diag_path = root / VERIFY_DIAGNOSTICS
    sure_path = root / VERIFY_SUREFIRE
    defer_path = root / LOOP_DEFERRED
    deferred = set(load_json(defer_path).get("clusters") or []) if defer_path.is_file() else set()
    steps_exist = (root / LOOP_STEPS).is_file() and bool((load_json(root / LOOP_STEPS) or {}).get("steps"))
    roots = [str(root), "/projects/modernized"]
    blocked: list[str] = []
    rescan = run.get("rescan") or {}
    # A skipped rescan is unknown even when findings.json still exists.
    # MTA analyses source patterns, not bytecode: v9 incident count went
    # 4→0 at the first accepted step with 233 compile errors remaining.
    # Copying the last slot would hide that drop and would accept a
    # candidate that reintroduces a Spring API while errors remain.
    if findings_path.is_file() and rescan.get("ran"):
        incidents = incidents_from_findings(load_json(findings_path), roots, canary)
        incidents_known = True
        incident_source = {"kind": "destination-rescan",
                           "path": str(MTA_RESCAN_FINDINGS), "sha256": sha256_file(findings_path)}
    elif not steps_exist:
        # before the baseline the frozen-source obligations are the plan —
        # but only when the MTA producer actually ran: an absent scan is
        # zero obligations in the bundle, not zero obligations in the code.
        incidents = incidents_from_bundle(bundle)
        mta_status = str(((bundle.get("producers") or {}).get("mta") or {}).get("status") or "missing")
        incidents_known = mta_status == "ok"
        if not incidents_known:
            blocked.append("MTA producer status is %r in the evidence bundle; source obligations unknown" % mta_status)
        incident_source = {"kind": "frozen-source-obligations", "path": str(EVIDENCE_BUNDLE), "sha256": digest(bundle), "mta_status": mta_status}
    else:
        incidents = incidents_from_findings(load_json(findings_path), roots, canary) if findings_path.is_file() else []
        incidents_known = False
        blocked.append("MTA rescan did not run in this verification (rc %s); incidents unknown" % rescan.get("rc"))
        incident_source = {"kind": "stale", "path": str(MTA_RESCAN_FINDINGS), "sha256": sha256_file(findings_path) if findings_path.is_file() else ""}
    try:
        from planner.decisions import load_decisions, superseded_rules, waivers as _waivers

        decisions_doc = load_decisions(root)
    except (OSError, ValueError):
        decisions_doc = {}
    platform_id = str((decisions_doc.get("destination_platform") or {}).get("id") or "")
    apply_supersessions(incidents, superseded_rules(decisions_doc, root) if decisions_doc else {}, _waivers(decisions_doc) if decisions_doc else [], pom_dependency_ids(root), platform=platform_id)
    mandatory = [i for i in incidents if i["category"] == "mandatory"]
    not_counted = [{"id": i["id"], "rule_id": i.get("rule_id"), "path": i.get("path"), "category": i["category"], "by": i.get("superseded_by") or i.get("waived_by")} for i in incidents if i["category"] in ("superseded", "waived")]
    diag_run = run.get("diagnostics") or {}
    diags = load_json(diag_path) if diag_path.is_file() else None
    compile_known = isinstance(diags, dict) and bool(diag_run.get("ran")) and not diags.get("build_unresolvable")
    comp_probe = compile_items(diags) if isinstance(diags, dict) else []
    disagreed = False
    maven_compile = run.get("maven_compile") or {}
    if compile_known and maven_compile.get("failed") and not comp_probe:
        # the measure may never be greener than the build: Maven could not
        # compile and the checker found nothing, so the checker is reading a
        # source set the build does not compile (pilot v7, 2026-09-10: the
        # generator wrote its DTOs outside the registered source root)
        compile_known = False
        disagreed = True
        blocked.append("javac diagnostics disagree with Maven: %s reported a compilation failure and the checker found no error; the checker is not reading the source roots the build compiles" % (maven_compile.get("goal") or "maven-compiler-plugin"))
    if not compile_known and not disagreed:
        # an unresolvable build never ran the compiler over the sources: its
        # compile count is unknown, not "1" (pilot v6 attempt 3 was accepted
        # at [11, 1, 0] for a pom Maven could not resolve; the successor that
        # fixed resolution measured the real 829 errors and was reverted)
        if isinstance(diags, dict) and diags.get("build_unresolvable"):
            blocked.append("build unresolvable: %s" % str(diags.get("reason") or "no classpath")[:300])
        else:
            blocked.append("compiler diagnostics did not run in this verification")
    comp = compile_items(diags) if isinstance(diags, dict) else []
    tests_run = run.get("tests") or {}
    sure = load_json(sure_path) if sure_path.is_file() else None
    tst = test_items(sure) if isinstance(sure, dict) else []
    if compile_known and comp:
        tests_known = True  # tests cannot run on a tree that does not compile; the compile count carries the measure
        tst = []
    elif isinstance(sure, dict) and tests_run.get("ran") and sure.get("ran"):
        rc = tests_run.get("rc")
        tests_known = rc == 0 or bool(tst)
        if not tests_known:
            blocked.append("mvn test exited %s with no failing test recorded (test compilation or runner failure); tests unknown" % rc)
    else:
        tests_known = False
        blocked.append("tests did not run in this verification" if not tests_run.get("ran") else "no surefire report was produced; tests unknown")
    parity_notes: list[dict[str, Any]] = []
    judged_receipt, parity_carried = judged_parity_receipt(root, run)
    par = parity_items(root, bundle, parity_notes, receipt=judged_receipt)
    parity_known = (root / PARITY_DIR).is_dir() and (any((root / PARITY_DIR).glob("*.json")) or any((root / PARITY_DIR / "scenarios").glob("*.json")))
    unmeasured_parity = parity_unmeasured(load_parity_receipt(root))
    if unmeasured_parity:
        parity_known = False
    # Packaging and startup are transitions out of the compile/test loop, not
    # part of its tuple: their failures arrive as obligations with a gate, and
    # a gate that never ran stays unknown (pilot v7 reached [0,0,0] with a
    # destination that could not be built at all).
    package_doc = load_json(root / VERIFY_PACKAGE) if (root / VERIFY_PACKAGE).is_file() else None
    boot_doc = load_json(root / VERIFY_BOOT) if (root / VERIFY_BOOT).is_file() else None
    rt_all = runtime_items(package_doc, boot_doc, root)
    rt = [i for i in rt_all if not i.get("unlocated")]
    # A blocker no card can carry still has an identity, because an Operator
    # has to be able to investigate THIS one twice and no more. Without an id
    # a diagnosis has nothing to attach to and nothing to count against.
    unlocatable: list[dict[str, Any]] = []
    unlocated_blocks: list[tuple[str, str]] = []
    set_wide_rows = [i for i in rt_all if i.get("unlocated") and i.get("set_wide")]
    for i in rt_all:
        if i.get("unlocated"):
            detail = str(i.get("detail") or i.get("message") or "")[:400]
            if i.get("set_wide"):
                unlocated_blocks.append((str(i.get("id")), "the %s gate failed with a SET-WIDE cause (%s): the platform names one member of a failing set and "
                               "that name changes between runs, so no single-file card may be minted; it named %s here: %s"
                               % (i.get("gate"), i.get("set_wide"), ", ".join(i.get("observed") or []) or "no file of this tree", detail[:160])))
            else:
                unlocated_blocks.append((str(i.get("id")), "the %s gate failed with a message that names no file of this tree, so no card can carry it: %s"
                                         % (i.get("gate"), detail[:200])))
            unlocatable.append({"id": str(i.get("id")), "kind": "unlocatable", "gate": str(i.get("gate") or ""),
                                "cause": str(i.get("cause") or ""), "scope": str(i.get("set_wide") or ""),
                                "observed": list(i.get("observed") or []), "detail": detail})
    runtime = runtime_state(package_doc, boot_doc)
    for b in runtime["blockers"]:
        blocked.append("runtime gate blocked by the environment: %s" % b)
        unlocatable.append({"id": "fx:environment:%s" % sha256_bytes(str(b).encode("utf-8"))[:12],
                            "kind": "environment", "gate": "", "cause": "environment", "detail": str(b)[:400]})
    items = sorted(mandatory + comp + tst + par + rt, key=lambda i: i["id"])
    # ADR-015/ADR-019: nothing a worker could be issued may land in a
    # harness-owned generated root. Such findings stay VISIBLE -- recorded
    # here, owned by the generator -- and are never an obligation.
    owned_roots = harness_owned_roots(root)
    harness_owned = [i for i in items if is_harness_owned(str(i.get("path") or ""), owned_roots)]
    if harness_owned:
        gone = {str(i["id"]) for i in harness_owned}
        items = [i for i in items if str(i["id"]) not in gone]
    harness_findings = [{"id": str(i.get("id")), "source": str(i.get("source") or ""), "kind": str(i.get("kind") or ""),
                         "category": str(i.get("category") or ""), "rule_id": str(i.get("rule_id") or ""),
                         "path": str(i.get("path") or ""), "line": i.get("line") or 0,
                         "detail": str(i.get("detail") or i.get("message") or "")[:200],
                         "owner": owned_roots["owner"], "applicable_to_workers": False,
                         "reason": ("the path is under a harness-owned generated root (%s); workers have no write authority "
                                    "there (ADR-015, ADR-019), so this is a finding for the generator's owner, not a card"
                                    % ", ".join(owned_roots["roots"]))}
                        for i in sorted(harness_owned, key=lambda i: str(i.get("id")))]
    # A compile diagnostic's identity without its line: acceptance asks whether
    # the issued failure is "still reported" of this, never of the err: id
    # (which hashes the line). Only unhandled-checked-exception diagnostics
    # need the model to be placed; the rest are line-free without it.
    if any(unreported_item(i) for i in items):
        try:
            _model = dest_model(root)
        except DestModelUnavailable:
            _model = None
    else:
        _model = None
    for i in items:
        if str(i.get("source") or "") == "javac":
            i["identity"] = diagnostic_identity(_model if unreported_item(i) else None, i)
    # Unit formation is a decided mode, sealed by the admission receipt through
    # decisions.yaml. Absent ⇒ off ⇒ today's clustering; a flip while a card is
    # issued is refused, because it would change every cluster id under a live
    # candidate (UNIT_MODE_SWITCH).
    formation, mode_block = unit_formation_for(root, decisions_doc)
    if mode_block:
        blocked.append(mode_block)
    # ADR-019: an obligation owed a harness adapter is sealed in EVERY mode --
    # the adapter's new file is authorized by that seal, not by the former.
    units, owed_claimed = owed_adapter_units(items, root, file_depths(bundle), deferred)
    if formation == UNIT_FORMATION_V1:
        try:
            _unit_model = dest_model(root)
        except DestModelUnavailable as exc:
            _unit_model = None
            blocked.append("unit formation is v1 but the destination could not be modelled, so no unit can be formed: %s" % exc)
        if _unit_model is not None:
            formed, claimed = form_units([i for i in items if str(i.get("id")) not in owed_claimed] + set_wide_rows,
                                         file_depths(bundle), deferred, model=_unit_model, root=root)
            units = units + formed
            # A set-wide row the former could enumerate is an OBLIGATION now,
            # not a blocker: the members are the model's, not the name the
            # platform happened to reach first. One the former could not
            # enumerate stays exactly the typed blocker it was.
            promoted = [i for i in set_wide_rows if str(i.get("id")) in claimed]
            if promoted:
                items = sorted(items + promoted, key=lambda i: i["id"])
                done = {str(i.get("id")) for i in promoted}
                unlocatable = [u for u in unlocatable if str(u.get("id")) not in done]
                unlocated_blocks = [b for b in unlocated_blocks if b[0] not in done]
    blocked.extend(text for _id, text in unlocated_blocks)
    clusters = cluster_items(items, file_depths(bundle), deferred, units=units)
    _guard_owned(clusters, owned_roots)
    # A cluster made only of one gate's obligations carries that gate, so the
    # card, the issued record and acceptance all know which phase is being
    # repaired (a packaging repair can leave the compile/test tuple unchanged).
    by_id = {i["id"]: i for i in items}
    scopes: list[dict[str, Any]] = []
    for c in clusters:
        gates = {str(by_id[i].get("gate") or "") for i in c.get("items") or [] if i in by_id}
        if len(gates) == 1 and gates != {""}:
            c["gate"] = gates.pop()
        scope = build_batch_scope(root, c, items, {"candidate_sha256": str(run.get("candidate_sha256") or "")})
        # the formed unit's working copy stays out of the written document:
        # what the card is judged against is the SEALED inventory, at its own
        # digest path, and the cluster's compact `unit` block beside it
        c.pop("_unit_seal", None)
        if scope:
            scopes.append(scope)
            if str(scope.get("kind") or "") == UNIT_KIND:
                # the file seal IS the write set; the label is the family key
                c["write_set"] = list(scope.get("writable_paths") or c.get("write_set") or [])
                c["label"] = str(scope.get("family_key") or "")
            if str(scope.get("kind") or "") == "repair-family":
                c["write_set"] = list(scope.get("writable_paths") or c.get("write_set") or [])
                c["label"] = "%s family (%d site(s))" % (str(scope.get("signature") or scope.get("family") or "checked-exception"), len(scope.get("members") or []))
            c["batch_scope"] = {"path": batch_scope_path(scope).as_posix(),
                                "digest": scope["digest"], "rule": scope["rule"],
                                "kind": str(scope.get("kind") or "repository"),
                                "family_id": str(scope.get("family_id") or ""),
                                "unit_id": str(scope.get("unit_id") or ""),
                                "members": len(scope["members"])}
        c["retry_key"] = retry_key(c, items)
    _guard_owned(clusters, owned_roots)  # a sealed scope may not re-admit one either
    open_clusters = [c for c in clusters if c["status"] == "open"]
    head = open_clusters[0]["id"] if open_clusters else ""
    doc = {
        "schema": SCHEMA,
        # which rule formed this list; the audit reads it, and build_worklist
        # refuses to change it under an issued card
        "unit_formation": formation,
        "evidence_bundle_sha256": digest(bundle),
        "not_counted": not_counted,
        "candidate_sha256": str(run.get("candidate_sha256") or ""),
        "sources": {
            "incidents": incident_source,
            "diagnostics": {"path": str(VERIFY_DIAGNOSTICS), "sha256": sha256_file(diag_path), "rc": diag_run.get("rc")} if isinstance(diags, dict) else None,
            "surefire": {"path": str(VERIFY_SUREFIRE), "sha256": sha256_file(sure_path), "rc": tests_run.get("rc"), "reports": sure.get("reports")} if isinstance(sure, dict) else None,
            "parity": dict({"path": str(PARITY_DIR), "count": len(par), "known": parity_known, "notes": parity_notes,
                            "carried": parity_carried},
                           **({"unmeasured": unmeasured_parity, "refresh": REFRESH_PARITY} if unmeasured_parity else {})),
            "package": {"path": str(VERIFY_PACKAGE), "sha256": sha256_file(root / VERIFY_PACKAGE)} if package_doc is not None else None,
            "boot": {"path": str(VERIFY_BOOT), "sha256": sha256_file(root / VERIFY_BOOT)} if boot_doc is not None else None,
            "run": {"path": str(VERIFY_RUN), "sha256": sha256_file(root / VERIFY_RUN)} if (root / VERIFY_RUN).is_file() else None,
        },
        "optional_incidents": sum(1 for i in incidents if i["category"] != "mandatory"),
        # findings in harness-owned generated roots: accounted, owned by the
        # generator, never an obligation (ADR-015/ADR-019)
        "harness_owned": {"roots": owned_roots["roots"], "declared_by": owned_roots["declared_by"],
                          "owner": owned_roots["owner"], "findings": harness_findings},
        "runtime": runtime,
        "items": items,
        "clusters": clusters,
        "deferred": sorted(deferred),
        "blocked_clusters": [c["id"] for c in clusters if c["status"] == "blocked"],
        "unlocatable": unlocatable,
        "head": head,
        "measure": measure_of(items, incidents_known=incidents_known, compile_known=compile_known, tests_known=tests_known, parity_known=parity_known, blocked=blocked),
        "order_policy": "build → config → compile (leaf types first) → incident → test → parity; within a rank by dependency depth then path; tests are never in a write set. Packaging and startup obligations enter as build/config items carrying their gate; the closing card needs an empty list AND both gates passing on the same packaged artifact.",
    }
    if write:
        from planner.canonical import write_canonical

        by_cluster = {c["id"]: c for c in clusters}
        for scope in scopes:
            out = root / batch_scope_path(scope)
            out.parent.mkdir(parents=True, exist_ok=True)
            # An inventory is written ONCE, at a path named by its own seal.
            # A later measurement of the same repository produces a different
            # inventory at a different path, and the one the outstanding card
            # is judged against is still exactly where the card left it.
            if not out.is_file():
                write_canonical(out, scope)
            # the card's K1 ref digests the FILE; the seal acceptance checks
            # digests the CONTENT. They are different questions.
            ref = (by_cluster.get(scope["cluster"]) or {}).get("batch_scope")
            if ref is not None:
                ref["file_sha256"] = sha256_file(out)
        write_canonical(root / WORKLIST, doc)
    return doc


def head_cluster(doc: dict[str, Any]) -> dict[str, Any] | None:
    for c in doc.get("clusters") or []:
        if c["id"] == doc.get("head"):
            return c
    return None


def items_of(doc: dict[str, Any], cluster: dict[str, Any]) -> list[dict[str, Any]]:
    wanted = set(cluster.get("items") or [])
    return [i for i in doc.get("items") or [] if i["id"] in wanted]


def item_ids(doc: dict[str, Any]) -> set[str]:
    return {i["id"] for i in doc.get("items") or []}


def obligation_keys(doc: dict[str, Any]) -> set[str]:
    """The keys the 'no new mandatory obligation' veto compares: one per
    mandatory MTA incident, keyed by rule and file with an occurrence index
    ("inc:<rule>|<path>#<n>"). Content-hash ids (item_ids) distinguish two
    incidents of one rule in one file, but the hash also moves when a fix
    changes the rule's variables/message on the same locus — pilot v6 (card
    t_ac60cdd2) reverted a [23,675,0] → [10,1,0] candidate because the
    compiler-plugin rule's incident re-hashed after the plugin was patched.
    A new (rule, file) pair, or one more occurrence of an existing pair, is
    a new obligation; a re-hash is not."""
    counts: dict[str, int] = {}
    out: set[str] = set()
    for i in doc.get("items") or []:
        if i.get("source") != "mta" or i.get("category") != "mandatory":
            continue
        base = "inc:%s|%s" % (i.get("rule_id"), i.get("path"))
        counts[base] = counts.get(base, 0) + 1
        out.add("%s#%d" % (base, counts[base]))
    return out
