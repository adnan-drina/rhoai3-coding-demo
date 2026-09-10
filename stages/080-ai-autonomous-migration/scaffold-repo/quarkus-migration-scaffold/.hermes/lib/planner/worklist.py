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

import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any

from planner.canonical import canonical_bytes, digest, load_json, sha256_bytes, sha256_file, sort_unique
from planner.paths import is_product_path, EVIDENCE_BUNDLE, LOOP_DEFERRED, LOOP_STEPS, MTA_RESCAN_FINDINGS, PARITY_DIR, VERIFY_DIAGNOSTICS, VERIFY_RUN, VERIFY_SUREFIRE, WORKLIST

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
        out.append({"id": "err:%s" % ident, "source": "javac", "kind": "build" if path == GLOBAL or path_class(path) == "build" else "compile", "category": "mandatory", "path": path, "line": line, "rule_id": str(d.get("code") or ""), "message_sha256": sha256_bytes(message.encode("utf-8")), "detail": message[:200]})
    if diags.get("build_unresolvable"):
        out.append({"id": "err:build-unresolvable", "source": "javac", "kind": "build", "category": "mandatory", "path": "pom.xml", "line": 0, "rule_id": "BUILD_UNRESOLVABLE", "message_sha256": sha256_bytes(str(diags.get("reason") or "").encode("utf-8")), "detail": str(diags.get("reason") or "")[:200], "message": str(diags.get("reason") or "")[:600]})
    return out


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


def cluster_items(items: list[dict[str, Any]], depths: dict[str, int], deferred: set[str]) -> list[dict[str, Any]]:
    by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in items:
        by_path[it["path"]].append(it)
    clusters: list[dict[str, Any]] = []
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


def progress(prev: dict[str, Any], cur: dict[str, Any], prev_ids: set[str], cur_ids: set[str]) -> tuple[bool, str]:
    """Accept iff strictly smaller lexicographically and no new mandatory obligation."""
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
    new_mandatory = sorted(i for i in cur_ids - prev_ids if i.startswith("inc:"))
    if new_mandatory:
        return False, "new mandatory obligation(s): %s" % ",".join(new_mandatory[:5])
    if b < a:
        return True, "measure %s < %s" % (b, a)
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
    mandatory = [i for i in incidents if i["category"] == "mandatory"]
    diag_run = run.get("diagnostics") or {}
    diags = load_json(diag_path) if diag_path.is_file() else None
    compile_known = isinstance(diags, dict) and bool(diag_run.get("ran")) and not diags.get("build_unresolvable")
    if not compile_known:
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
    items = sorted(mandatory + comp + tst + par, key=lambda i: i["id"])
    clusters = cluster_items(items, file_depths(bundle), deferred)
    open_clusters = [c for c in clusters if c["status"] == "open"]
    head = open_clusters[0]["id"] if open_clusters else ""
    doc = {
        "schema": SCHEMA,
        "evidence_bundle_sha256": digest(bundle),
        "candidate_sha256": str(run.get("candidate_sha256") or ""),
        "sources": {
            "incidents": incident_source,
            "diagnostics": {"path": str(VERIFY_DIAGNOSTICS), "sha256": sha256_file(diag_path), "rc": diag_run.get("rc")} if isinstance(diags, dict) else None,
            "surefire": {"path": str(VERIFY_SUREFIRE), "sha256": sha256_file(sure_path), "rc": tests_run.get("rc"), "reports": sure.get("reports")} if isinstance(sure, dict) else None,
            "parity": {"path": str(PARITY_DIR), "count": len(par), "known": parity_known},
            "run": {"path": str(VERIFY_RUN), "sha256": sha256_file(root / VERIFY_RUN)} if (root / VERIFY_RUN).is_file() else None,
        },
        "optional_incidents": sum(1 for i in incidents if i["category"] != "mandatory"),
        "items": items,
        "clusters": clusters,
        "deferred": sorted(deferred),
        "blocked_clusters": [c["id"] for c in clusters if c["status"] == "blocked"],
        "head": head,
        "measure": measure_of(items, incidents_known=incidents_known, compile_known=compile_known, tests_known=tests_known, parity_known=parity_known, blocked=blocked),
        "order_policy": "build → config → compile (leaf types first) → incident → test → parity; within a rank by dependency depth then path; tests are never in a write set",
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
