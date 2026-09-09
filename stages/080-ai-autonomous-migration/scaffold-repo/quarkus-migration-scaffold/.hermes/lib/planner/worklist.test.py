#!/usr/bin/env python3
"""worklist unit selftest: ordering, clustering, measure, progress, conservation."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.worklist import KIND_RANK, cluster_items, compile_items, file_depths, incidents_from_findings, measure_of, path_class, progress, surefire_from_reports, test_items  # noqa: E402


def surefire_from_reports_ran_flag():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        return surefire_from_reports(Path(d)).get("ran")


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def main() -> int:
    if path_class("pom.xml") != "build" or path_class("src/main/resources/application.properties") != "config" or path_class("src/test/java/A.java") != "test" or path_class("src/main/java/A.java") != "source":
        return _fail("path classes")
    findings = {"violations": {
        "r-web": {"category": "mandatory", "incidents": [
            {"uri": "file:///x/src/main/java/a/B.java", "lineNumber": 3, "message": "m1", "variables": {"k": "1"}},
            {"uri": "file:///x/src/main/java/a/B.java", "lineNumber": 3, "message": "m2", "variables": {"k": "2"}},
            {"message": "global"},
            {"uri": "file:///x/src/main/java/a/B.java", "lineNumber": 3, "message": "m1", "variables": {"k": "1"}},
        ]},
        "r-pom": {"category": "mandatory", "incidents": [{"uri": "file:///x/pom.xml", "lineNumber": 1, "message": "p"}]},
        "r-opt": {"category": "optional", "incidents": [{"uri": "file:///x/src/main/java/a/C.java", "lineNumber": 1, "message": "o"}]},
        "rhoai3-canary-00001": {"category": "optional", "incidents": [{"uri": "file:///x/pom.xml", "lineNumber": 1, "message": "c"}]},
    }}
    items = incidents_from_findings(findings, ["/x"], "rhoai3-canary-00001")
    mand = [i for i in items if i["category"] == "mandatory"]
    ids = [i["id"] for i in mand]
    if len(mand) != 5 or len(set(ids)) != 4:
        return _fail("every incident is an item (exact repeat shares the id): %d items, %d ids" % (len(mand), len(set(ids))))
    # identity is line-free: the same obligation on another line is the same id
    moved = incidents_from_findings({"violations": {"r-web": {"category": "mandatory", "incidents": [{"uri": "file:///x/src/main/java/a/B.java", "lineNumber": 11, "message": "m1", "variables": {"k": "1"}}]}}}, ["/x"], "")
    if moved[0]["id"] not in set(ids) or moved[0]["line"] != 11:
        return _fail("line movement must keep the obligation id (and record the new line)")
    if not any(i["path"] == "GLOBAL" and i["kind"] == "build" for i in mand):
        return _fail("a global incident is kept as a build item")
    if any(i["rule_id"] == "rhoai3-canary-00001" for i in items):
        return _fail("canary is not work")
    # the destination rescan sees the frozen legacy copy and the BOM probe under .derived/: never work
    derived = incidents_from_findings({"violations": {"r-web": {"category": "mandatory", "incidents": [
        {"uri": "file:///x/.derived/frozen-input/src/main/java/a/B.java", "lineNumber": 3, "message": "m1"},
        {"uri": "file:///x/.derived/bom-probe/pom.xml", "lineNumber": 1, "message": "p"},
        {"uri": "file:///x/evidence/mta/report/index.html", "lineNumber": 1, "message": "h"},
        {"uri": "file:///x/src/main/java/a/B.java", "lineNumber": 3, "message": "m1"},
    ]}}}, ["/x"], "")
    if [i["path"] for i in derived] != ["src/main/java/a/B.java"]:
        return _fail("incidents outside the product tree must not become items: %s" % [i["path"] for i in derived])
    # compile items + tests
    comp = compile_items({"diagnostics": [{"kind": "ERROR", "path": "src/main/java/a/A.java", "line": 2, "code": "x", "message": "e"}, {"kind": "WARNING", "path": "src/main/java/a/A.java", "line": 2, "code": "w", "message": "w"}]})
    if len(comp) != 1 or comp[0]["kind"] != "compile":
        return _fail("only ERROR diagnostics are items")
    unres = compile_items({"diagnostics": [], "build_unresolvable": True, "reason": "no classpath"})
    if unres[0]["kind"] != "build" or unres[0]["path"] != "pom.xml":
        return _fail("unresolvable build is a pom item")
    tst = test_items({"failures": [{"classname": "a.ATest", "name": "t", "message": "m", "path": "src/test/java/a/ATest.java"}]})
    if tst[0]["kind"] != "test":
        return _fail("test items")
    if surefire_from_reports_ran_flag() is not False:
        return _fail("no surefire report must mean ran=False")
    # ordering: build < config < compile (leaf-first) < incident < test
    bundle = {"structure": {"types": [
        {"fqn": "a.A", "path": "src/main/java/a/A.java", "type_refs": ["a.B"]},
        {"fqn": "a.B", "path": "src/main/java/a/B.java", "type_refs": []},
    ]}}
    depths = file_depths(bundle)
    if depths["src/main/java/a/B.java"] != 0 or depths["src/main/java/a/A.java"] != 1:
        return _fail("depths %s" % depths)
    all_items = mand + comp + tst + compile_items({"diagnostics": [{"kind": "ERROR", "path": "src/main/java/a/B.java", "line": 9, "code": "x", "message": "e2"}]})
    clusters = cluster_items(all_items, depths, set())
    kinds = [c["kind"] for c in clusters]
    ranks = [KIND_RANK[k] for k in kinds]
    if ranks != sorted(ranks):
        return _fail("cluster order %s" % kinds)
    comp_paths = [c["path"] for c in clusters if c["kind"] == "compile"]
    if comp_paths != ["src/main/java/a/B.java", "src/main/java/a/A.java"]:
        return _fail("compile clusters must be leaf-first: %s" % comp_paths)
    b_cluster = next(c for c in clusters if c["path"] == "src/main/java/a/B.java")
    if b_cluster["kind"] != "compile" or len(b_cluster["items"]) != 4:
        return _fail("B.java clusters its compile error with its incidents: %s" % b_cluster)
    t_cluster = next(c for c in clusters if c["kind"] == "test")
    if t_cluster["write_set"] != ["src/main/java/a/A.java"] or t_cluster["status"] != "open":
        return _fail("a failing test scopes its production twin, never the test: %s" % t_cluster)
    orphan = cluster_items(test_items({"failures": [{"classname": "z.ZTest", "name": "t", "message": "m", "path": ""}]}), depths, set())
    if orphan[0]["write_set"] or orphan[0]["status"] != "blocked":
        return _fail("an unresolvable test failure is a typed blocker with no write set: %s" % orphan[0])
    # measure + progress
    m0 = measure_of(all_items, incidents_known=True, compile_known=True, tests_known=True, parity_known=False)
    if m0["tuple"] != [5, 2, 1] or not m0["known"] or m0["parity_mismatches"] is not None:
        return _fail("measure %s" % m0)
    m1 = measure_of([i for i in all_items if i["source"] != "javac"], incidents_known=True, compile_known=True, tests_known=True, parity_known=False)
    ok, why = progress(m0, m1, {i["id"] for i in all_items}, {i["id"] for i in all_items if i["source"] != "javac"})
    if not ok:
        return _fail("fewer compile errors must be progress: %s" % why)
    ok, why = progress(m0, m0, {i["id"] for i in all_items}, {i["id"] for i in all_items})
    if ok:
        return _fail("equal measure is not progress")
    # lexicographic: fewer incidents but more compile errors is progress; more incidents never is
    m2 = dict(m0, tuple=[4, 9, 1]); m3 = dict(m0, tuple=[6, 0, 0])
    if not progress(m0, m2, set(), set())[0] or progress(m0, m3, set(), set())[0]:
        return _fail("lexicographic order")
    ok, why = progress(m0, m2, {"inc:a"}, {"inc:a", "inc:new"})
    if ok or "new mandatory" not in why:
        return _fail("a new mandatory incident is never progress")
    unknown = measure_of(all_items, incidents_known=True, compile_known=False, tests_known=True, parity_known=False)
    if unknown["known"] or progress(m0, unknown, set(), set())[0]:
        return _fail("unknown measure never advances")
    if measure_of(all_items, incidents_known=False, compile_known=True, tests_known=True, parity_known=False)["known"]:
        return _fail("unknown incidents never advance")
    print("OK: worklist (lossless line-free incidents; canary excluded; only ERROR diagnostics; build→config→compile(leaf-first)→incident→test order; tests never writable; lexicographic 3-tuple progress; new-incident veto; unknown never advances)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
