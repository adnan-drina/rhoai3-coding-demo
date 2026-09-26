#!/usr/bin/env python3
"""requirement_checks: an outcome owning source requirements is accepted only
by a measurement that RECOMPUTES its requirement checks on the tree.

1. measure(): gate rows, open compile items, parity scenarios (measured and
   discharged vs open vs not measured), the repository-effects check (an
   unresolved write coverage is unknown, never PASS), and every check without
   a producer is unknown (fail closed).
2. The fragment checks run worklist._assess_implementations over the owed
   implementation the requirement names, on the real JDK model: stub bodies
   fail, a real implementation passes (renamed twin too).
3. End to end through outcome_lifecycle.accept_commit (the outcome board's
   acceptance path, qualification mode, FakeNative): an outcome that owns an
   annotation-retirement requirement is NOT accepted while the annotation is
   still on the file, although its finding obligations are gone and the
   compile/test classes were measured (an empty work list never discharges
   it); after the retirement it is accepted, and the recorded measurement
   carries the recomputed checks. An outcome owning a check with no producer
   is never accepted.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from planner import outcome_graph as OG  # noqa: E402
from planner import outcome_lifecycle as L  # noqa: E402
from planner import requirement_checks as RC  # noqa: E402

HERMES = HERE.parents[1]


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def unit_case() -> int:
    wl = {"items": [{"id": "par:1", "source": "parity", "scenario": "sc:open"}], "measure": {"known": True},
          "runtime": {"package": {"ran": True, "rc": 0}, "boot": {"ran": True, "rc": 1}}}
    req = {"id": "req:x", "acceptance": ["gate:compile", "gate:package", "gate:startup", "parity:sc:done", "parity:sc:open",
                                          "parity:sc:unmeasured", "unit:handler-validation-guards", "coverage:unresolved"]}
    got = {k: v["status"] for k, v in RC.measure(Path("."), [req], worklist=wl, scenarios=["sc:done", "sc:open"]).items()}
    want = {"gate:compile": "pass", "gate:package": "pass", "gate:startup": "fail", "parity:sc:done": "pass",
            "parity:sc:open": "fail", "parity:sc:unmeasured": "unknown", "unit:handler-validation-guards": "unknown",
            "coverage:unresolved": "unknown"}
    if got != want:
        return _fail("measure: %s != %s" % (got, want))
    wl2 = dict(wl, items=[{"id": "err:1", "source": "javac"}])
    if RC.measure(Path("."), [{"id": "r", "acceptance": ["gate:compile"]}], worklist=wl2, scenarios=[])["gate:compile"]["status"] != "fail":
        return _fail("an open compile item fails gate:compile")
    # repository effects: an unresolved write row is unknown even when its reads pass
    rep = {"id": "req:repo", "acceptance": ["behavior:repository-effects:p.Frag"],
           "facts": {"verification": [{"member": "p.Frag#findAll()", "status": "applicable", "scenarios": ["sc:done"]},
                                      {"member": "p.Frag#save(p.E)", "status": "unresolved", "scenarios": []}]}}
    st = RC.measure(Path("."), [rep], worklist=wl, scenarios=["sc:done"])["behavior:repository-effects:p.Frag"]
    if st["status"] != "unknown" or "save" not in st["detail"]:
        return _fail("an unresolved write coverage is an owned debt, never PASS: %s" % st)
    rep["facts"]["verification"][1] = {"member": "p.Frag#save(p.E)", "status": "applicable", "scenarios": ["sc:open"]}
    if RC.measure(Path("."), [rep], worklist=wl, scenarios=["sc:done", "sc:open"])["behavior:repository-effects:p.Frag"]["status"] != "fail":
        return _fail("a write scenario still open fails the repository effects")
    # _covers: requirement checks must all be recorded as passing
    node = {"class": "source", "acceptance": {"requirement_checks": ["gate:compile", "unit:handler-validation-guards"]}}
    m = {"classes": ["compile", "tests"], "checks": RC.passed(RC.measure(Path("."), [{"id": "r", "acceptance": node["acceptance"]["requirement_checks"]}],
                                                                        worklist=wl, scenarios=[]))}
    if L._covers(node, m):
        return _fail("a check with no producer must keep the requirement owner uncovered (fail closed)")
    return 0


def fragment_case() -> int:
    if not shutil.which("javac"):
        print("SKIP fragment_case: no javac (not run)")
        return 0
    fbt = _load("fbt", HERMES / "skills/migration/fix-until-green/scripts/fragment-behaviour.test.py")
    from planner import source_requirements as SR
    from planner.canonical import load_json
    catalog = load_json(HERMES / "planning/catalogs/compat-mapping.json")
    for n in (fbt.A, fbt.B):
        types, eps = fbt.source_types(n)
        doc = SR.derive(types=types, entry_points=eps, catalog=catalog, decisions={"build_profiles": {"adr": "x", "active": [n["profile"]]}},
                        oracles=None, structure_complete=True, generator=None)
        parent = "%s.%s.%s" % (n["base"], n["repo_pkg"], n["parent"])
        req = next(r for r in doc["requirements"] if r["rule"] == "repository-architecture/v1" and r["facts"]["fragment"] == parent)
        checks = ["unit:fragment-implementation", "unit:fragment-behaviour-bodies", "structure:single-injectable-implementation"]
        e = n["entity"]
        for body, want in ((fbt.bodies(n, q2="    public Collection<%s> %s() { throw new UnsupportedOperationException(); }\n" % (e, n["q2"])), "fail"),
                           (fbt.bodies(n), "pass")):
            with tempfile.TemporaryDirectory(prefix="rc-frag-") as d:
                root = fbt.make_root(d, n, body)
                got = RC.measure(root, [dict(req, acceptance=checks)], worklist={"items": [], "measure": {"known": True}}, scenarios=[])
                if {got[c]["status"] for c in checks} != {want}:
                    return _fail("[%s] fragment checks on the %s form: %s" % (n["base"], want, got))
    return 0


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout.strip()


def board_case() -> int:
    if not shutil.which("javac"):
        print("SKIP board_case: no javac (not run)")
        return 0
    ob = _load("obt", HERE / "outcome_board.test.py")
    ctrl = "src/main/java/com/acme/shop/web/ItemController.java"
    ann = "org.acme.compat.CrossFlag"
    for label, checks, retire_then_accept in (
            ("retirement", ["structure:annotation-absent:%s" % ann, "gate:compile"], True),
            ("no producer", ["structure:annotation-absent:%s" % ann, "unit:handler-validation-guards"], False)):
        run = ob.Run(publish=False)
        try:
            root = run.root
            pins = json.loads((root / ".hermes/pins.json").read_text())
            pins["pins"]["quarkus_platform"] = {"java_release": 21}
            (root / ".hermes/pins.json").write_text(json.dumps(pins))
            run.edit("src/main/java/org/acme/compat/CrossFlag.java", "package org.acme.compat;\npublic @interface CrossFlag { }\n")
            run.edit(ctrl, "package com.acme.shop.web;\n@org.acme.compat.CrossFlag\npublic class ItemController { }\n")
            git(root, "add", "-A")
            git(root, "commit", "-qm", "java baseline")
            req = {"id": "req:annotation-retirement:com.acme.shop.web.ItemController@%s" % ann, "rule": "annotation-retirement/v1",
                   "subject": "com.acme.shop.web.ItemController@%s" % ann, "status": "applicable", "class": "source", "phase": "m3",
                   "recipe": {"id": "retire-adapter-owned-annotation", "version": "1", "phase": "m3", "implementation": "decided-repairs"},
                   "evidence": [], "paths": [ctrl], "consumers": [], "acceptance": checks, "unknowns": [], "dependencies": [],
                   "facts": {}}
            run.plan = ob.derive(requirements=[req])
            run.publish()
            run.release()
            node = next(n for n in run.store.current_revision()["nodes"] if req["id"] in (n.get("requirements") or []))
            oid = node["outcome_id"]
            # its prerequisites first, exactly as the board would run them
            ancestors, frontier = set(), list(node.get("parents") or [])
            byid = {n["outcome_id"]: n for n in run.store.current_revision()["nodes"]}
            while frontier:
                p = frontier.pop()
                if p not in ancestors and p in byid:
                    ancestors.add(p)
                    frontier.extend(byid[p].get("parents") or [])
            for n in OG.topo_order(run.store.current_revision()["nodes"]):
                if n["outcome_id"] in ancestors and n["role"] == "repair":
                    cls = ("build", "compile", "tests") + {"runtime": ("runtime",), "behavior": ("runtime", "parity")}.get(n["class"], ())
                    run.accept(n["outcome_id"], classes=cls, scenarios=n.get("scenarios") or ())
            for attempt, text in (("1", None), ("2", "package com.acme.shop.web;\npublic class ItemController { }\n")):
                tid, rid, iss = run.issue(oid)
                ctx = run.ctx()
                if text is not None:
                    run.edit(ctrl, text)
                else:
                    run.edit(ctrl, "package com.acme.shop.web;\n@org.acme.compat.CrossFlag\npublic class ItemController { int v; }\n")
                L.check_write(ctx, task_id=tid, run_id=rid, rel_paths=[ctrl])
                L.record_verdict(ctx, task_id=tid, run_id=rid, verdict="ACCEPTED", candidate=ctx.product_tree(), attempt=attempt)
                git(root, "add", "-A")
                git(root, "commit", "-qm", "attempt %s" % attempt)
                run.drop(*node["obligations"])
                out = L.accept_commit(ctx, task_id=tid, run_id=rid, attempt=attempt, commit=git(root, "rev-parse", "HEAD"),
                                      measurement={"classes": ["compile", "tests"], "scenarios": []})
                meas = [r["doc"] for r in run.store.ledger("_measure")][-1]
                if attempt == "1":
                    if out["outcome_accepted"] or out["open_owned"]:
                        return _fail("[%s] the annotation is still there, the obligations are gone: not accepted, nothing "
                                     "owned open: %s" % (label, out))
                    if meas.get("check_status", {}).get("structure:annotation-absent:%s" % ann, {}).get("status") != "fail":
                        return _fail("[%s] the measurement records the failing recomputed check: %s" % (label, meas))
                else:
                    if bool(out["outcome_accepted"]) != retire_then_accept:
                        return _fail("[%s] after the retirement accepted=%s, expected %s (%s)" % (label, out["outcome_accepted"],
                                                                                              retire_then_accept, meas.get("check_status")))
                    if retire_then_accept and "structure:annotation-absent:%s" % ann not in (meas.get("checks") or []):
                        return _fail("[%s] the passing check is recorded on the measurement: %s" % (label, meas))
        finally:
            run.close()
    return 0


def main() -> int:
    for case in (unit_case, fragment_case, board_case):
        if case():
            return 1
    print("OK: requirement checks (recomputed per tree: gates, compile items, parity measured-and-discharged, repository "
          "effects with unresolved writes as owned debt, fragment bodies on the real model; no producer = unknown = never "
          "covered; accept_commit keeps a requirement owner open while its check fails and accepts it once it passes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
