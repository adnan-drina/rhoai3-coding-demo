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
failing tests). A change is accepted only if the tuple strictly decreases
lexicographically and introduces no new mandatory obligation; strict
decrease is the termination argument. Parity is measured by M4 and
reported beside the tuple, never inside it.

Measurement contract: every component is known only when its tool ran in
this verification and produced a report (verification/build/run.json);
a missing report never means success. Obligation identity is line-free
(rule, file, variables, message) so ordinary line movement is not a new
obligation; the line stays on the item for the brief.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any

from planner.canonical import canonical_bytes, digest, load_json, sha256_bytes, sha256_file, sort_unique
from planner.paths import is_product_path, EVIDENCE_BUNDLE, LOOP_DEFERRED, LOOP_STEPS, MTA_RESCAN_FINDINGS, PARITY_DIR, VERIFY_BOOT, VERIFY_DIAGNOSTICS, VERIFY_PACKAGE, VERIFY_RUN, VERIFY_SUREFIRE, WORKLIST

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
    ("No implementation of interface", "missing-implementation"),
    ("UnableToParseMethodException", "underivable-query-method"),
    ("Unable to find datasource", "datasource-unconfigured"),
    ("is not configured", "datasource-unconfigured"),
    ("ConfigurationException", "configuration-invalid"),
    ("UnsatisfiedResolutionException", "unsatisfied-injection"),
    ("AmbiguousResolutionException", "ambiguous-injection"),
    ("DefinitionException", "definition-invalid"),
    ("Unsupported class file major version", "toolchain-class-version"),
    ("SQLGrammarException", "schema-missing-object"),
    ("relation \"", "schema-missing-object"),
    ("Table not found", "schema-missing-object"),
    ("does not exist", "schema-missing-object"),
)


def runtime_cause(text: str) -> str:
    for needle, cause in RUNTIME_CAUSES:
        if needle in (text or ""):
            return cause
    return "unclassified"


def runtime_locus(text: str, root: Path | None) -> str:
    """The source file a runtime failure names, when the tree has it.

    A message that names a type is pointing at that type. Guessing is not
    involved: the path is derived from the fully-qualified name and only used
    when the file is really there."""
    if root is None:
        return ""
    for fqn in FQN_RE.findall(text or ""):
        rel = "src/main/java/%s.java" % fqn.replace(".", "/")
        if (Path(root) / rel).is_file():
            return rel
    return ""
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
        log = str(doc.get("log_tail") or "")
        kind, cluster_kind, locus = classify_runtime_failure(detail + "\n" + log)
        named = runtime_locus(detail + "\n" + log, root)
        if named:
            locus, cluster_kind = named, "compile"
        # The identity is WHERE and WHAT, never the wording: the gate, the kind,
        # the cause from a closed vocabulary, and the file. A tool that
        # rephrases the same failure at the same place is the same obligation,
        # so a repair that only changes the message is not progress; but a file
        # whose first problem is fixed and whose SECOND problem then surfaces
        # gets a new obligation, because the cause differs (measured live:
        # "No implementation of interface" became UnableToParseMethodException
        # at the same repository once it became a Spring Data repository).
        cause = runtime_cause(detail + "\n" + log)
        ident = sha256_bytes(canonical_bytes({"gate": gate, "kind": kind, "cause": cause, "locus": locus}))[:16]
        out.append({
            "id": "rt:%s:%s" % (gate, ident), "source": "runtime", "gate": gate,
            "kind": cluster_kind, "obligation": kind, "cause": cause, "category": "mandatory",
            "path": locus, "line": 0, "rule_id": "RUNTIME_%s" % kind.replace("-", "_").upper(),
            "message_sha256": sha256_bytes((detail + log).encode("utf-8")),
            "detail": detail[:200],
            "message": ("%s gate failed (%s): %s\n%s" % (gate, kind, detail, log))[:1200],
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


def parity_items(root: Path, bundle: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    ep_path = {str(e["id"]): str(e.get("path") or "") for e in (bundle.get("entry_points") or [])}
    pdir = root / PARITY_DIR
    if not pdir.is_dir():
        return out
    for p in sorted(pdir.glob("*.json")):
        doc = load_json(p)
        if not isinstance(doc, dict) or str(doc.get("verdict")) != "FAIL":
            continue
        ep = str(doc.get("entry_point") or "")
        out.append({"id": "parity:%s" % sha256_bytes(ep.encode("utf-8"))[:16], "source": "parity", "kind": "parity", "category": "mandatory", "path": ep_path.get(ep) or GLOBAL, "line": 0, "rule_id": "PARITY", "message_sha256": sha256_bytes(str(doc.get("reason") or "").encode("utf-8")), "detail": ep[:200]})
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


def cluster_items(items: list[dict[str, Any]], depths: dict[str, int], deferred: set[str]) -> list[dict[str, Any]]:
    # Compile items that are the same unresolved name in several files are one
    # obligation, not one per file: they get one card whose write set lists the
    # files (capped, so a card stays one model turn). Pilot v6: 829 errors were
    # 73 per-file cards; the same Spring symbol (DataAccessException ×124,
    # @Profile ×58, @Transactional ×36) recurs across most of them.
    by_token: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in items:
        tok = compile_token(it)
        if tok:
            by_token[tok].append(it)
    symbol_groups: list[tuple[str, list[dict[str, Any]]]] = []
    taken: set[str] = set()
    for tok in sorted(by_token):
        rows = by_token[tok]
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
    clusters: list[dict[str, Any]] = []
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


def gate_items(worklist: dict[str, Any], gate: str) -> set[str]:
    """The ids of the obligations one gate currently holds."""
    return {str(i["id"]) for i in (worklist.get("items") or []) if str(i.get("gate") or "") == gate}


def progress(prev: dict[str, Any], cur: dict[str, Any], prev_ids: set[str], cur_ids: set[str],
             *, gate: str = "", prev_runtime: dict[str, Any] | None = None, cur_runtime: dict[str, Any] | None = None,
             issued_items: list[str] | None = None, prev_gate_items: set[str] | None = None,
             cur_gate_items: set[str] | None = None) -> tuple[bool, str]:
    """Accept iff strictly smaller lexicographically and no new mandatory obligation.

    Phase-aware: a card issued for the ``package`` or ``boot`` gate is repairing
    something the compile/test tuple cannot see, so fixing it can leave the
    tuple unchanged. Such a step is accepted when its OWN gate goes from
    failing to passing and the tuple does not regress. The tuple still may not
    get worse, no new mandatory obligation may appear, and the other gate may
    not go backwards -- a repair is not a licence to break the phase before it."""
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
    if b < a:
        return True, "measure %s < %s" % (b, a)
    if gate in ("package", "boot"):
        prev_rt = prev_runtime or {}
        cur_rt = cur_runtime or {}

        def _passing(rt: dict[str, Any], name: str) -> bool:
            row = (rt.get(name) or {}) if isinstance(rt, dict) else {}
            return bool(row.get("ran")) and row.get("rc") == 0 and (row.get("ready", True) is not False)

        if b > a:
            return False, "measure %s regressed from %s; a %s repair may not make compilation or tests worse" % (b, a, gate)
        other = "package" if gate == "boot" else "boot"
        if _passing(prev_rt, other) and not _passing(cur_rt, other):
            return False, "the %s gate was passing and is not any more; a %s repair may not break the phase before it" % (other, gate)
        if _passing(cur_rt, gate) and not _passing(prev_rt, gate):
            return True, "the %s gate went from failing to passing with the measure unchanged at %s" % (gate, b)
        if not _passing(cur_rt, gate):
            # A gate can hold more than one obligation, and only one of them is
            # on this card. Repairing it is progress even while the gate still
            # fails on another -- provided THIS obligation is gone (its
            # identity is gate+kind+locus, so a reworded failure at the same
            # place is not gone) and the gate did not acquire more of them.
            issued = {i for i in (issued_items or []) if str(i).startswith("rt:")}
            before, after = prev_gate_items or set(), cur_gate_items or set()
            if issued and not (issued & after):
                if len(after) > len(before):
                    return False, "the %s obligation was repaired and the gate acquired %d more (%d → %d); that is not a smaller list" % (gate, len(after) - len(before), len(before), len(after))
                return True, "the %s obligation %s is gone and the gate holds no more than before (%d → %d)" % (gate, ",".join(sorted(issued)[:2]), len(before), len(after))
            if issued:
                return False, "the %s obligation %s is still open (its identity is the gate, the kind and the file; a different message at the same place is the same obligation)" % (gate, ",".join(sorted(issued)[:2]))
            return False, "the %s gate is still not passing (%s)" % (gate, "; ".join((cur_rt.get("reasons") or [])[:2]) or "see its receipt")
    return False, "measure %s did not decrease from %s" % (b, a)


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------


def load_run(root: Path) -> dict[str, Any]:
    p = Path(root) / VERIFY_RUN
    return load_json(p) if p.is_file() else {}


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
    if findings_path.is_file() and rescan.get("ran"):
        incidents = incidents_from_findings(load_json(findings_path), roots, canary)
        incidents_known = True
        incident_source = {"kind": "destination-rescan", "path": str(MTA_RESCAN_FINDINGS), "sha256": sha256_file(findings_path)}
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
    par = parity_items(root, bundle)
    parity_known = (root / PARITY_DIR).is_dir() and any((root / PARITY_DIR).glob("*.json"))
    # Packaging and startup are transitions out of the compile/test loop, not
    # part of its tuple: their failures arrive as obligations with a gate, and
    # a gate that never ran stays unknown (pilot v7 reached [0,0,0] with a
    # destination that could not be built at all).
    package_doc = load_json(root / VERIFY_PACKAGE) if (root / VERIFY_PACKAGE).is_file() else None
    boot_doc = load_json(root / VERIFY_BOOT) if (root / VERIFY_BOOT).is_file() else None
    rt = runtime_items(package_doc, boot_doc, root)
    runtime = runtime_state(package_doc, boot_doc)
    for b in runtime["blockers"]:
        blocked.append("runtime gate blocked by the environment: %s" % b)
    items = sorted(mandatory + comp + tst + par + rt, key=lambda i: i["id"])
    clusters = cluster_items(items, file_depths(bundle), deferred)
    # A cluster made only of one gate's obligations carries that gate, so the
    # card, the issued record and acceptance all know which phase is being
    # repaired (a packaging repair can leave the compile/test tuple unchanged).
    by_id = {i["id"]: i for i in items}
    for c in clusters:
        gates = {str(by_id[i].get("gate") or "") for i in c.get("items") or [] if i in by_id}
        if len(gates) == 1 and gates != {""}:
            c["gate"] = gates.pop()
    open_clusters = [c for c in clusters if c["status"] == "open"]
    head = open_clusters[0]["id"] if open_clusters else ""
    doc = {
        "schema": SCHEMA,
        "evidence_bundle_sha256": digest(bundle),
        "not_counted": not_counted,
        "candidate_sha256": str(run.get("candidate_sha256") or ""),
        "sources": {
            "incidents": incident_source,
            "diagnostics": {"path": str(VERIFY_DIAGNOSTICS), "sha256": sha256_file(diag_path), "rc": diag_run.get("rc")} if isinstance(diags, dict) else None,
            "surefire": {"path": str(VERIFY_SUREFIRE), "sha256": sha256_file(sure_path), "rc": tests_run.get("rc"), "reports": sure.get("reports")} if isinstance(sure, dict) else None,
            "parity": {"path": str(PARITY_DIR), "count": len(par), "known": parity_known},
            "package": {"path": str(VERIFY_PACKAGE), "sha256": sha256_file(root / VERIFY_PACKAGE)} if package_doc is not None else None,
            "boot": {"path": str(VERIFY_BOOT), "sha256": sha256_file(root / VERIFY_BOOT)} if boot_doc is not None else None,
            "run": {"path": str(VERIFY_RUN), "sha256": sha256_file(root / VERIFY_RUN)} if (root / VERIFY_RUN).is_file() else None,
        },
        "optional_incidents": sum(1 for i in incidents if i["category"] != "mandatory"),
        "runtime": runtime,
        "items": items,
        "clusters": clusters,
        "deferred": sorted(deferred),
        "blocked_clusters": [c["id"] for c in clusters if c["status"] == "blocked"],
        "head": head,
        "measure": measure_of(items, incidents_known=incidents_known, compile_known=compile_known, tests_known=tests_known, parity_known=parity_known, blocked=blocked),
        "order_policy": "build → config → compile (leaf types first) → incident → test → parity; within a rank by dependency depth then path; tests are never in a write set. Packaging and startup obligations enter as build/config items carrying their gate; the closing card needs an empty list AND both gates passing on the same packaged artifact.",
    }
    if write:
        from planner.canonical import write_canonical

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
