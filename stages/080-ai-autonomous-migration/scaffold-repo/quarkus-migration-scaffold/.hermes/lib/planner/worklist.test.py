#!/usr/bin/env python3
"""worklist unit selftest: ordering, clustering, measure, progress, conservation."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.cards import card_title
from planner.worklist import apply_supersessions
from planner.worklist import KIND_RANK, cluster_items, compile_items, file_depths, incidents_from_findings, measure_of, obligation_keys, path_class, progress, surefire_from_reports, test_items  # noqa: E402


def surefire_from_reports_ran_flag():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        return surefire_from_reports(Path(d)).get("ran")


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _gate_progress_case() -> int:
    """Acceptance inside a gate: what counts, and what only looks like it."""
    green = {"known": True, "tuple": [0, 0, 0]}
    worse = {"known": True, "tuple": [0, 1, 0]}
    failing = {"package": {"ran": True, "rc": 1}, "boot": {"ran": False, "rc": None, "ready": False}}
    passing = {"package": {"ran": True, "rc": 0}, "boot": {"ran": False, "rc": None, "ready": False}}
    both = {"package": {"ran": True, "rc": 0}, "boot": {"ran": True, "rc": 0, "ready": True}}
    boot_broken = {"package": {"ran": True, "rc": 0}, "boot": {"ran": True, "rc": 1, "ready": False}}
    A, B = "rt:package:aaaa", "rt:package:bbbb"

    ok, why = progress(green, green, set(), set(), gate="package", prev_runtime=failing, cur_runtime=passing,
                       issued_items=[A], prev_gate_items={A}, cur_gate_items=set())
    if not ok:
        return _fail("a gate that starts passing is progress: %s" % why)
    # the obligation this card was issued for is gone; the gate still fails elsewhere
    ok, why = progress(green, green, set(), set(), gate="package", prev_runtime=failing, cur_runtime=failing,
                       issued_items=[A], prev_gate_items={A}, cur_gate_items={B})
    if not ok or "is gone" not in why:
        return _fail("repairing this card's obligation while the gate fails elsewhere is progress: %s" % why)
    # the same obligation, reworded: its identity is gate+kind+locus, so it is still there
    ok, why = progress(green, green, set(), set(), gate="package", prev_runtime=failing, cur_runtime=failing,
                       issued_items=[A], prev_gate_items={A}, cur_gate_items={A})
    if ok or "still open" not in why:
        return _fail("a failure that only reads differently is not progress: %s" % why)
    # a repair that leaves the gate holding more than it did
    ok, why = progress(green, green, set(), set(), gate="package", prev_runtime=failing, cur_runtime=failing,
                       issued_items=[A], prev_gate_items={A}, cur_gate_items={B, "rt:package:cccc"})
    if ok or "not a smaller list" not in why:
        return _fail("a repair that multiplies the gate's obligations is not progress: %s" % why)
    # a gate repair may not break the phase before it
    ok, why = progress(green, green, set(), set(), gate="package", prev_runtime=both, cur_runtime=boot_broken,
                       issued_items=[A], prev_gate_items={A}, cur_gate_items=set())
    if ok or "may not break the phase before it" not in why:
        return _fail("breaking startup while repairing packaging is not progress: %s" % why)
    # and it may not make compilation or tests worse
    ok, why = progress(green, worse, set(), set(), gate="package", prev_runtime=failing, cur_runtime=passing,
                       issued_items=[A], prev_gate_items={A}, cur_gate_items=set())
    if ok or "regressed" not in why:
        return _fail("a gate repair may not regress the measure: %s" % why)
    # a card with no gate is judged by the measure alone
    ok, _ = progress(green, green, set(), set())
    if ok:
        return _fail("an ordinary card still needs a strictly smaller measure")
    return 0


def main() -> int:
    if _gate_progress_case():
        return 1

    if path_class("pom.xml") != "build" or path_class("src/main/resources/application.properties") != "config" or path_class("src/test/java/A.java") != "test" or path_class("src/main/java/A.java") != "source":
        return _fail("path classes")
    if path_class("src/test/resources/application.properties") != "config" or path_class("src/test/resources/data.sql") != "test":
        return _fail("test configuration files are config (migration work); other test files are not writable")
    cfg = cluster_items([{"id": "x", "source": "mta", "kind": "incident", "category": "mandatory", "path": "src/test/resources/application.properties", "line": 1, "rule_id": "r", "message_sha256": "", "detail": ""}], {}, set())
    if cfg[0]["status"] != "open" or cfg[0]["write_set"] != ["src/test/resources/application.properties"]:
        return _fail("a test properties file must be its own write set: %s" % cfg[0])
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
    gen = compile_items({"diagnostics": [{"kind": "ERROR", "path": "target/generated-sources/openapi/src/main/java/a/PetDto.java", "line": 9, "code": "compiler.err.doesnt.exist", "message": "package javax.validation does not exist"}]})
    if gen[0]["kind"] != "build" or gen[0]["path"] != "pom.xml" or gen[0]["rule_id"] != "GENERATED_SOURCE_ERROR" or "PetDto.java:9" not in gen[0]["message"] or gen[0]["generated_path"] != "target/generated-sources/openapi/src/main/java/a/PetDto.java":
        return _fail("an error in generated source is a build item on the pom carrying the generated path: %s" % gen[0])
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
    # veto identity: rule + file + occurrence; a re-hash of the same obligation (variables/message
    # changed by the fix) is NOT new, one more occurrence or a new (rule, file) pair IS
    def _doc(rows):
        return {"items": [{"source": "mta", "category": "mandatory", "rule_id": r, "path": pth, "id": "inc:%s:%s" % (r, h)} for r, pth, h in rows]}
    before = obligation_keys(_doc([("r1", "pom.xml", "aaaa"), ("r2", "pom.xml", "bbbb"), ("r2", "pom.xml", "cccc")]))
    rehashed = obligation_keys(_doc([("r1", "pom.xml", "ffff"), ("r2", "pom.xml", "bbbb"), ("r2", "pom.xml", "cccc")]))
    if rehashed != before or not progress(m0, m2, before, rehashed)[0]:
        return _fail("a re-hashed obligation on the same rule and file must not be new: %s" % (rehashed - before))
    more = obligation_keys(_doc([("r1", "pom.xml", "aaaa"), ("r2", "pom.xml", "bbbb"), ("r2", "pom.xml", "cccc"), ("r2", "pom.xml", "dddd")]))
    if progress(m0, m2, before, more)[0]:
        return _fail("one more occurrence of a rule on a file is a new obligation")
    # relocation: one fewer occurrence on the old file, one more on a new file (the rule's total did not grow) is NOT new
    other = obligation_keys(_doc([("r1", "pom.xml", "aaaa"), ("r2", "pom.xml", "bbbb"), ("r2", "src/main/java/A.java", "cccc")]))
    if not progress(m0, m2, before, other)[0]:
        return _fail("a relocated occurrence of a rule must not veto (the documented profile merge moves incidents with the keys)")
    # the same rule on a new file while every old occurrence stays IS new (the total grew)
    grown = obligation_keys(_doc([("r1", "pom.xml", "aaaa"), ("r2", "pom.xml", "bbbb"), ("r2", "pom.xml", "cccc"), ("r2", "src/main/java/A.java", "dddd")]))
    ok, why = progress(m0, m2, before, grown)
    if ok or "new mandatory" not in why or "A.java" not in why:
        return _fail("a rule spreading to a new file with its old occurrences intact is a new obligation: %s" % why)
    unknown = measure_of(all_items, incidents_known=True, compile_known=False, tests_known=True, parity_known=False)
    if unknown["known"] or progress(m0, unknown, set(), set())[0]:
        return _fail("unknown measure never advances")
    ok, why = progress(unknown, m0, set(), set())
    if not ok or "became known" not in why:
        return _fail("a known measure must beat an unknown baseline: %s" % why)
    if progress(unknown, m0, {"inc:a"}, {"inc:a", "inc:new"})[0]:
        return _fail("becoming known never excuses a new obligation")
    if compile_items({"diagnostics": [], "build_unresolvable": True, "reason": "missing version"})[0].get("message") != "missing version":
        return _fail("the unresolvable item must carry the resolver's reason for the brief")
    # the same unresolved symbol across files is one cluster with a multi-file write set (capped); a lone item stays per file
    def _c(path, sym, n):
        return {"id": "err:%s%d" % (sym, n), "source": "javac", "kind": "compile", "category": "mandatory", "path": path, "line": n, "rule_id": "compiler.err.cant.resolve.location", "message": "cannot find symbol\n  symbol:   class %s\n  location: class X" % sym}
    rows = [_c("src/main/java/a/A.java", "DataAccessException", 1), _c("src/main/java/b/B.java", "DataAccessException", 2), _c("src/main/java/b/B.java", "DataAccessException", 3), _c("src/main/java/c/C.java", "Lonely", 4)]
    cl = cluster_items(rows, {"src/main/java/a/A.java": 3, "src/main/java/b/B.java": 1, "src/main/java/c/C.java": 2}, set())
    sym = [c for c in cl if c.get("label") == "DataAccessException"]
    if len(sym) != 1 or sym[0]["write_set"] != ["src/main/java/a/A.java", "src/main/java/b/B.java"] or len(sym[0]["items"]) != 3 or sym[0]["order_key"][1] != 1:
        return _fail("a symbol seen in two files must be one cluster writing both, ordered by the shallowest file: %s" % sym)
    lone = [c for c in cl if c["path"] == "src/main/java/c/C.java"]
    if len(lone) != 1 or lone[0].get("label") or lone[0]["write_set"] != ["src/main/java/c/C.java"]:
        return _fail("a symbol seen in one file stays a per-file cluster: %s" % lone)
    many = [_c("src/main/java/p/F%02d.java" % i, "Profile", i) for i in range(10)]
    caps = [c for c in cluster_items(many, {}, set()) if c.get("label")]
    if [c["label"] for c in caps] != ["Profile#1", "Profile#2"] or len(caps[0]["write_set"]) != 8 or len(caps[1]["write_set"]) != 2:
        return _fail("a symbol across more than 8 files splits into capped clusters: %s" % [(c["label"], len(c["write_set"])) for c in caps])
    if card_title(sym[0], 1) != "M3 compile DataAccessException (3 items, 2 files, attempt 1)":
        return _fail("symbol clusters get a readable title: %s" % card_title(sym[0], 1))
    # a profile file's cluster writes the profile file AND the sibling application.properties (the documented merge)
    prof = cluster_items([{"id": "inc:p", "source": "mta", "kind": "config", "category": "mandatory", "path": "src/main/resources/application-hsqldb.properties", "line": 0, "rule_id": "springboot-properties-to-quarkus-00001"}], {}, set())
    if prof[0]["write_set"] != ["src/main/resources/application-hsqldb.properties", "src/main/resources/application.properties"]:
        return _fail("profile-file config cluster must scope the main properties file too: %s" % prof[0]["write_set"])
    plain = cluster_items([{"id": "inc:q", "source": "mta", "kind": "config", "category": "mandatory", "path": "src/main/resources/application.properties", "line": 3, "rule_id": "r"}], {}, set())
    if plain[0]["write_set"] != ["src/main/resources/application.properties"]:
        return _fail("the main properties file scopes only itself: %s" % plain[0]["write_set"])
    # the measure may never be greener than the build
    from planner.worklist import build_worklist as _bw  # noqa: F401  (import guard only)
    m_clean = measure_of([], incidents_known=True, compile_known=True, tests_known=True, parity_known=False)
    if not m_clean["known"] or m_clean["tuple"] != [0, 0, 0]:
        return _fail("a clean measure with every component known: %s" % m_clean)
    # supersession (catalog, guarded by a present artifact) and waiver (ADR) reclassify, never drop
    rows = [
        {"id": "inc:a", "source": "mta", "category": "mandatory", "rule_id": "springboot-web-to-quarkus-00010", "path": "pom.xml"},
        {"id": "inc:b", "source": "mta", "category": "mandatory", "rule_id": "jakarta-jaxrs-to-quarkus-00010", "path": "pom.xml"},
        {"id": "inc:c", "source": "mta", "category": "mandatory", "rule_id": "r-waived", "path": "src/main/java/A.java"},
        {"id": "inc:d", "source": "mta", "category": "mandatory", "rule_id": "r-waived", "path": "src/main/java/B.java"},
        {"id": "inc:e", "source": "mta", "category": "mandatory", "rule_id": "r-keep", "path": "pom.xml"},
    ]
    sup = {"springboot-web-to-quarkus-00010": {"requires_present": "io.quarkus:quarkus-rest-jackson", "reason": "renamed"},
           "jakarta-jaxrs-to-quarkus-00010": {"requires_present": "io.quarkus:quarkus-rest", "reason": "transitive"}}
    out = apply_supersessions(rows, sup, [{"rule_id": "r-waived", "path": "src/main/java/A.java", "adr": "ADR-009", "reason": "x"}], {"io.quarkus:quarkus-rest-jackson"}, platform="p")
    cats = {r["id"]: r["category"] for r in out}
    if cats != {"inc:a": "superseded", "inc:b": "mandatory", "inc:c": "waived", "inc:d": "mandatory", "inc:e": "mandatory"}:
        return _fail("supersession needs its artifact present; a waiver binds rule+path: %s" % cats)
    if out[0].get("superseded_by", {}).get("platform") != "p" or out[2].get("waived_by", {}).get("adr") != "ADR-009" or len(out) != 5:
        return _fail("reclassified items keep their authority and are never dropped")
    if measure_of(all_items, incidents_known=False, compile_known=True, tests_known=True, parity_known=False)["known"]:
        return _fail("unknown incidents never advance")
    print("OK: worklist (lossless line-free incidents; canary excluded; only ERROR diagnostics; build→config→compile(leaf-first)→incident→test order; tests never writable; lexicographic 3-tuple progress; new-incident veto; unknown never advances; gate progress is the issued obligation disappearing, never a reworded one)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
