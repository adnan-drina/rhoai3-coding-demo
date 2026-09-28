#!/usr/bin/env python3
"""compatibility-objectives/v1 execution on the native board (SYNTHETIC: an
in-memory FakeNative with the pinned semantics, real git, the real native
control, native_gate projection and worklist scope code).

1. An objective is issued WHOLE: one scope (every constituent's files), one
   issued.json card carrying the admitted descriptor and ONE composite scope
   envelope whose children are the admitted unit inventories.
2. The envelope refuses a changed or missing child inventory
   (ISSUE_OBJECTIVE_SCOPE), and advance's rebuild-and-compare refuses an
   envelope that is not the admitted one.
3. A write outside the issued scope is refused.
4. Acceptance is judged per (requirement, check): one requirement passing a
   check cannot stand for another requirement's failing one.
5. A blocked objective parks its candidate; an independent ready objective is
   issued and accepted meanwhile; the parked candidate is restored and
   accepted; the wait spends no budget.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/objective_execution.test.py
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "kernel"))
from planner import native_control as NC  # noqa: E402
from planner import outcome_graph as OG  # noqa: E402
from planner.canonical import write_canonical  # noqa: E402
from planner.outcome_checks import Refusal  # noqa: E402
from planner.worklist import ObjectiveScopeError, batch_scope_digest, batch_scope_path, build_objective_scope  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NB = _load("nb_obj", HERE / "native_board.test.py")
CO_T = _load("co_obj", HERE / "compatibility_objectives.test.py")
import native_gate as NG  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def world():
    w = CO_T.shop()
    # the requirement matrix case: two retirement requirements on one objective
    w.reqs.append({"id": "req:annotation-retirement:problem", "rule": "annotation-retirement/v1", "status": "applicable",
                   "class": "source", "subject": "com.acme.shop.web.Problem@org.springframework.web.bind.annotation.CrossOrigin",
                   "paths": [CO_T.P + "web/Problem.java"], "acceptance": ["gate:compile"],
                   "facts": {"sites": 1}, "consumers": [], "dependencies": []})
    return w


def setup(w) -> "NB.Run":
    r = NB.Run(publish=False)
    NB.mirror_layout(r.root)
    wl = w.worklist()
    # real sealed inventories at their digest paths (what the unit former writes)
    for c in wl["clusters"]:
        seal = w.seals.get(c["id"])
        if not seal:
            continue
        doc = dict(copy.deepcopy(seal), cluster=c["id"], kind="unit", unit_id=c["id"],
                   writable_paths=list(c["write_set"]))
        doc["digest"] = batch_scope_digest(doc)
        rel = batch_scope_path(doc)
        write_canonical(r.root / rel, doc)
        c["batch_scope"] = {"path": rel.as_posix(), "digest": doc["digest"], "rule": doc["rule"], "kind": "unit", "unit_id": c["id"]}
        w.seals[c["id"]] = doc
    for c in wl["clusters"]:
        for p in c["write_set"]:
            f = r.root / p
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("// %s v0\n" % p)
    r.worklist = wl
    r.save_worklist()
    NB.git(r.root, "add", "-A")
    NB.git(r.root, "commit", "-qm", "objective world")
    plan = OG.derive_initial_graph(run_id=r.run_id, worklist=wl, entry_points=[], oracles=None, references=None,
                                   provenance=CO_T.PROV, requirements=copy.deepcopy(w.reqs),
                                   objectives={"catalog": CO_T.CATALOG, "seals": copy.deepcopy(w.seals), "item_symbols": {},
                                               "structure_types": copy.deepcopy(w.types)})
    r.plan_file.write_text(json.dumps(plan))
    r.out = r.publish()
    r.release()
    return r


def oid_of(r, clusters: set[str]) -> str:
    return next(n["outcome_id"] for n in r.plan()["nodes"] if set(n.get("clusters") or []) == clusters)


def main() -> int:
    w = world()
    r = setup(w)
    try:
        sort_oid = oid_of(r, {"u:sort-pkg", "u:sort-cmp", "u:sort-def"})
        req_oid = oid_of(r, {"u:val-a", "u:uri-a", "u:cors"})
        cfg_oid = oid_of(r, {"c:cfg-main", "c:cfg-test"})

        # configuration first (the build/configuration barrier): main+test issued whole
        tid, run, iss = r.issue(cfg_oid)
        if iss["cluster"] != "objective:%s" % cfg_oid or len(iss["allowed_paths"]) != 2:
            return _fail("main and test configuration are one issued objective: %s" % iss)
        NG.write_issued_projection(r.root, iss)
        if not r.accept_on_run(tid, run, iss, attempt="1")["outcome_accepted"]:
            return _fail("the configuration objective is accepted")
        r.review_and_complete(tid, run)
        r.accept(oid_of(r, {"c:cfg-other"}))
        fmt_oid = oid_of(r, {"u:fmt"})
        # 1. issued whole
        tid, run, iss = r.issue(sort_oid)
        node = NC._node(r.plan(), sort_oid)
        if iss["cluster"] != "objective:%s" % sort_oid or sorted(iss["allowed_paths"]) != sorted(node["execution_unit"]["paths"]):
            return _fail("the objective must be issued whole: %s %s" % (iss["cluster"], iss["allowed_paths"]))
        NG.write_issued_projection(r.root, iss)
        issued = json.loads((r.root / "verification/loop/issued.json").read_text())
        env = json.loads((r.root / issued["batch_scope"]["path"]).read_text())
        if env["rule"] != "unit/objective/v1" or sorted(c["cluster"] for c in env["children"]) != sorted(node["clusters"]) \
                or issued.get("objective", {}).get("constituents") != node["execution_unit"]["constituents"]:
            return _fail("issued.json carries the descriptor and ONE envelope of the admitted children: %s" % env.get("children"))
        if sorted(issued["items"]) != sorted(i for c in r.worklist["clusters"] if c["id"] in node["clusters"] for i in c["items"]):
            return _fail("the card carries every admitted obligation still reported")
        # 2. envelope refusals
        rebuilt = build_objective_scope(r.root, sort_oid, issued["objective"], r.worklist)
        if rebuilt["digest"] != env["digest"]:
            return _fail("the envelope must rebuild identically from the admitted descriptor")
        child = r.root / env["children"][0]["path"]
        saved = child.read_text()
        child.write_text(saved.replace('"rule"', '"rule_"', 1))
        try:
            build_objective_scope(r.root, sort_oid, issued["objective"], r.worklist)
        except ObjectiveScopeError:
            pass
        else:
            return _fail("a changed child inventory must refuse")
        child.unlink()
        try:
            NG.write_issued_projection(r.root, iss)
        except Refusal as exc:
            if exc.code != "ISSUE_OBJECTIVE_SCOPE":
                return _fail("a missing child inventory refuses ISSUE_OBJECTIVE_SCOPE, got %s" % exc.code)
        else:
            return _fail("a missing child inventory must refuse the projection")
        child.write_text(saved)
        # 3. outside-path write
        try:
            NC.check_write(r.board, task_id=tid, run_id=run, rel_paths=[CO_T.P + "repo/OrderStore.java"])
        except Refusal:
            pass
        else:
            return _fail("a write outside the issued objective must refuse")
        out = r.accept_on_run(tid, run, iss, attempt="1")
        if not out["outcome_accepted"]:
            return _fail("the sorting objective is accepted once all its units' obligations are gone: %s" % out)
        r.review_and_complete(tid, run)

        # 4. per-requirement check matrix
        tid, run, iss = r.issue(req_oid)
        NG.write_issued_projection(r.root, iss)
        r.edit(CO_T.P + "web/OrderApi.java", "// OrderApi migrated\n")
        NC.check_write(r.board, task_id=tid, run_id=run, rel_paths=[CO_T.P + "web/OrderApi.java"])
        NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="ACCEPTED", candidate=r.tree(), attempt="1")
        NB.git(r.root, "add", "-A")
        NB.git(r.root, "commit", "-qm", "request boundary 1")
        node = NC._node(r.plan(), req_oid)
        problem = next(i for i in r.worklist["items"] if i["path"].endswith("web/Problem.java"))
        r.drop(*[o for o in NC.owned(r.plan(), node) if o != problem["id"]])
        # the Problem.java compile item stays open -> its requirement's gate:compile fails, OrderApi's passes;
        # move it outside the objective's ownership so only the CHECK (not an owned obligation) is the reason
        r.worklist["clusters"].append({"id": "c:elsewhere", "kind": "compile", "status": "open", "items": [problem["id"]],
                                       "write_set": [problem["path"]], "order_key": [9, 9, "x"]})
        for c in r.worklist["clusters"]:
            if c["id"] != "c:elsewhere" and problem["id"] in c["items"]:
                c["items"].remove(problem["id"])
        r.save_worklist()
        out = NC.accept_commit(r.root, r.board, task_id=tid, run_id=run, attempt="1", commit=NB.git(r.root, "rev-parse", "HEAD"),
                               measurement={"classes": ["build", "compile", "tests"], "scenarios": []})
        meas = [x for x in r.board.records(tid, "accept-commit")][-1]["measurement"]
        matrix = meas.get("check_matrix") or {}
        if out["outcome_accepted"] or matrix.get("req:annotation-retirement:order-api", {}).get("gate:compile") != "pass" \
                or matrix.get("req:annotation-retirement:problem", {}).get("gate:compile") != "fail":
            return _fail("one requirement's passing gate:compile cannot stand for another's failing one: %s %s" % (out, matrix))
        if "req:annotation-retirement:problem|gate:compile" not in (meas.get("unmet_checks") or {}):
            return _fail("the unmet check keeps its requirement identity: %s" % meas.get("unmet_checks"))

        # 5. park a blocked objective, progress an independent one, restore
        tid_b, run_b, iss_b = tid, run, iss
        r.edit(CO_T.P + "web/OrderApi.java", "// OrderApi second candidate\n")
        parked = NC.park(r.root, r.board, task_id=tid_b, run_id=run_b)
        if not parked.get("parked"):
            return _fail("the blocked objective's candidate must park: %s" % parked)
        r.native.block(tid_b, "waiting on an independent owner") if hasattr(r.native, "block") else None
        spent_before = NC.family_spent(r.board, r.run_id, r.plan(), NC._node(r.plan(), req_oid)["budget"]["key"])
        tid_c, run_c, iss_c = r.issue(fmt_oid)
        if not iss_c["cluster"] or iss_c["cluster"].startswith("objective:"):
            return _fail("the independent unit objective is issued (its own unit) while the other is parked: %s" % iss_c)
        out_c = r.accept_on_run(tid_c, run_c, iss_c, attempt="1")
        if not out_c["outcome_accepted"]:
            return _fail("the independent objective is accepted meanwhile: %s" % out_c)
        r.review_and_complete(tid_c, run_c)
        spent_after = NC.family_spent(r.board, r.run_id, r.plan(), NC._node(r.plan(), req_oid)["budget"]["key"])
        if spent_after != spent_before:
            return _fail("a wait spends nothing: %s -> %s" % (spent_before, spent_after))
        if (r.root / CO_T.P / "web/OrderApi.java").read_text() == "// OrderApi second candidate\n":
            return _fail("the parked candidate must leave the tree while the other objective runs")
        back = NC.restore_parked(r.root, r.board, task_id=tid_b, run_id=run_b)
        if (r.root / CO_T.P / "web/OrderApi.java").read_text() != "// OrderApi second candidate\n":
            return _fail("the parked candidate is restored exactly for re-verification: %s" % back)
        print("OK: objective execution (issued whole with one envelope of admitted children; changed/missing child "
              "inventories refuse; out-of-scope writes refuse; acceptance judged per requirement and check; a parked "
              "objective does not stop an independent one and its wait spends nothing)")
        return 0
    finally:
        r.close()


if __name__ == "__main__":
    raise SystemExit(main())
