#!/usr/bin/env python3
"""check-schedule/v1 executed through the EXISTING native lifecycle (roadmap
M-2 exit fixtures, executable half).

The composed desk plan of compatibility_objectives.test.py (a real
compatibility-objectives/v1 composition with its check schedule) is
published on the native_board.test.py harness (FakeNative board with the
pinned semantics, real git, the real native control, the real requirement
checks, work-list routing and orphan revision). Prerequisite cards are
completed natively; the cards under test are issued, measured, routed,
accepted and restarted through native_control.

1. A later repository-behaviour check is measured at its earliest card (the
   Order behaviour card) as soon as its prerequisites hold on the measured
   candidate; its FAIL is routed to the row's OWNER as an owed repair (the
   owner's follow-up, sharing the owner's family budget), which becomes a
   prerequisite of the measuring card, the other behaviour cards and M4. M4
   remains the backstop.
2. The server-error producer's repair cluster is issued before the dependent
   header comparison; the preflight is not held behind CRUD.
3. The shared producer's accepted repair marks every affected path; the
   Order path's pass never discharges the Item path.
4. A restart during a pending earliest measurement keeps the row pending with
   the missing prerequisite named; never PASS, never dropped.
5. qualify:repository-contract:<fragment> resolves to the M-3 strategy test,
   read-only; unknown with the missing input named when it cannot run here.
6. v29 r1: the Owner repository contract is scheduled at the Owner (and Pet)
   behaviour cards with its owner and named prerequisites.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/schedule_lifecycle.test.py
"""
from __future__ import annotations

import copy
import gzip
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NB = _load("nb_schedule", HERE / "native_board.test.py")
CO_T = _load("co_schedule", HERE / "compatibility_objectives.test.py")
NC, OG, Refusal = NB.NC, NB.OG, NB.Refusal
from planner import qualification_evidence as QE  # noqa: E402
from planner.worklist import PARITY_RECEIPT_SCHEMA, parity_receipt_file  # noqa: E402

B_ORDER, B_ITEM, B_STATUS = "behavior:http:" + CO_T.O, "behavior:http:" + CO_T.ITEM, "behavior:http:" + CO_T.STATUS
EFFECTS = "behavior:repository-effects:" + CO_T.FRAG_O
ORDER_FILE = CO_T.P + "web/OrderApi.java"
REPO_SCENARIOS = ["sc:auth-anonymous-read-orders-1", "sc:cors-actual-0a", "sc:create-orders", "sc:read-items-1",
                  "sc:read-orders", "sc:read-orders-1"]


class Desk:
    """The desk composition published natively; every non-behaviour card done."""

    def __init__(self):
        w, eps, oracles = CO_T.desk()
        self.r = r = NB.Run(publish=False)
        NB.mirror_layout(r.root)
        paths = {p for q in w.reqs for p in q.get("paths") or []} | {p for c in w.clusters for p in c["write_set"]}
        for p in sorted(paths):
            f = r.root / p
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("// %s v0\n" % p)
        r.worklist = w.worklist()
        r.save_worklist()
        NB.git(r.root, "add", "-A")
        NB.git(r.root, "commit", "-qm", "desk world")
        plan = OG.derive_initial_graph(run_id=r.run_id, worklist=w.worklist(), entry_points=eps, oracles=oracles,
                                       references=None, provenance=CO_T.PROV, requirements=copy.deepcopy(w.reqs),
                                       objectives={"catalog": CO_T.CATALOG, "seals": copy.deepcopy(w.seals),
                                                   "item_symbols": {}, "structure_types": copy.deepcopy(w.types)})
        assert not (plan.get("check_schedule") or {}).get("findings"), plan["check_schedule"]["findings"]
        r.plan_file.write_text(json.dumps(plan))
        r.out = r.publish()
        r.release()
        self.owner = plan["requirement_ownership"][CO_T.REPO_O]
        for n in OG.topo_order(r.plan()["nodes"]):
            if n["role"] == "repair" and n["class"] != "behavior":
                tid = r.tid(n["outcome_id"])
                r.native.claim(tid)
                r.native.complete(tid)
        # every compile finding is discharged: the application packages and starts
        r.worklist = {"items": [], "clusters": [], "unlocatable": [], "not_counted": [],
                      "measure": {"known": True, "tuple": [0, 0, 0]}}
        self.measured(started=True)

    # -- the measured candidate ------------------------------------------------
    def measured(self, *, started=True, items=(), clusters=(), scenarios=REPO_SCENARIOS):
        r = self.r
        tree = r.tree()
        r.worklist.update(candidate_sha256=tree, items=list(items), clusters=list(clusters),
                          runtime={"package": {"ran": True, "rc": 0},
                                   "boot": {"ran": started, "rc": 0 if started else None, "ready": started},
                                   "blockers": [], "ready": started})
        r.save_worklist()
        receipt = {"schema": PARITY_RECEIPT_SCHEMA, "security_mode": "disabled", "verdict": "FAIL",
                   "binding": {"candidate_sha256": tree},
                   "entry_points": [{"entry_point": "ep:x", "verdict": "PASS", "scenarios": list(scenarios)}]}
        p = r.root / parity_receipt_file("disabled")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(receipt))

    def close(self):
        self.r.close()


def parity_item(iid, scenario, ep, *, cause="response", server_error=False):
    it = {"id": iid, "category": "mandatory", "kind": "parity" if cause == "response" else "config", "source": "parity",
          "scenario": scenario, "entry_point": ep, "path": ORDER_FILE, "cause": cause, "advice": {}}
    if server_error:
        it["advice"]["server_error"] = {"exception": "java.lang.StackOverflowError", "locus_hints": []}
    return it


def cluster(cid, *ids):
    return {"id": cid, "items": list(ids), "kind": "parity", "path": ORDER_FILE, "status": "open", "write_set": [ORDER_FILE]}


# ===========================================================================
class EarliestMeasurement(unittest.TestCase):

    def test_repository_behaviour_is_measured_at_its_earliest_card_and_owed_by_its_owner(self):
        d = Desk()
        r = d.r
        try:
            plan = r.plan()
            row = next(x for x in NC.scheduled_rows(plan, B_ORDER) if x["check"] == EFFECTS)
            self.assertEqual((row["owner"], row["milestone"]), (d.owner, "persistence-and-one-http-path"))
            self.assertIn(EFFECTS, {x["check"] for x in NC.scheduled_rows(plan, B_ITEM)})
            self.assertNotIn(EFFECTS, {x["check"] for x in NC.scheduled_rows(plan, B_STATUS)})
            # the committed write of sc:create-orders fails on the measured candidate
            d.measured(items=[parity_item("parity:create", "sc:create-orders", CO_T.EP_ADD)],
                       clusters=[cluster("c:create", "parity:create")])
            owner_budget = dict(NC._node(plan, d.owner)["budget"])
            tid, run, lock = r.claim(B_ORDER)
            with self.assertRaises(Refusal) as cm:
                NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock)
            self.assertEqual(cm.exception.code, "OWNER_REPAIR_PENDING")
            self.assertIn(EFFECTS, cm.exception.detail)
            fid = "followup:%s:m3g1" % d.owner
            plan = r.plan()
            fnode = NC._node(plan, fid)
            ob = NC.SCHEDULED_OBLIGATION % (d.owner, EFFECTS)
            self.assertEqual(plan["ownership"][ob], fid)
            self.assertEqual(fnode["budget"], owner_budget)                     # the owner's family budget, never a fresh one
            self.assertEqual((fnode["class"], fnode["acceptance"]["requirement_checks"], fnode["requirements"]),
                             ("behavior", [EFFECTS], [CO_T.REPO_O]))
            self.assertEqual(fnode["schedule"], [{"check": EFFECTS, "measured_at": B_ORDER,
                                                  "milestone": "persistence-and-one-http-path"}])
            ftid, m4 = r.tid(fid), r.tid("assess:m4:g1")
            for t in (tid, r.tid(B_ITEM), r.tid(B_STATUS), m4):
                self.assertIn(ftid, r.native.task(t)["parents"])
            # M4 stays the backstop of the same row
            m4_rows = {(x["outcome"], x["check"]) for x in NC._node(plan, "assess:m4:g1")["acceptance"]["deferred_requirement_checks"]}
            self.assertIn((d.owner, EFFECTS), m4_rows)
            rec = r.board.records(tid, "schedule-measure")[-1]
            got = next(m for m in rec["rows"] if m["check"] == EFFECTS)
            self.assertEqual((got["state"], got["owner"], got["route"]), ("fail", d.owner, "owner"))
            self.assertIn("sc:create-orders", got["detail"])
            # the same scenario's plain comparison is this card's own immediate check: recorded, not moved away
            same = [m for m in rec["rows"] if m["check"] == "parity:sc:create-orders"]
            self.assertTrue(same and all(m["state"] == "fail" and m["route"].startswith("judged by") for m in same), same)
            self.assertEqual(NC.schedule_status(r.board, r.run_id, plan)["%s|%s" % (d.owner, EFFECTS)]["state"], "fail")
            self.assertEqual(len(r.board.records(tid, "schedule-route")), 1)
            r.native.block_dependency(tid)
            self.assertEqual(NC.family_spent(r.board, r.run_id, plan, owner_budget["key"]), 0)   # a wait spends nothing

            # the owner's follow-up repairs the repository; its acceptance measures the owed check itself
            ftid, frun, fiss = r.issue(fid)
            self.assertTrue(fiss["allowed_paths"] and set(fiss["allowed_paths"]) <= set(
                p for q in plan["requirements"] if q["id"] == CO_T.REPO_O for p in q["paths"]), fiss["allowed_paths"])
            acc = r.accept_on_run(ftid, frun, fiss, classes=("build", "compile", "tests"), scenarios=REPO_SCENARIOS, drop=False)
            self.assertFalse(acc["outcome_accepted"])                           # still failing: a budgeted rejection
            self.assertTrue(any(EFFECTS in x and "fail" in x for x in acc["not_accepted_because"]), acc)
            r.worklist["items"], r.worklist["clusters"] = [], []
            r.save_worklist()
            fiss = NC.issue(r.root, r.board, task_id=ftid, run_id=frun)
            acc = r.accept_on_run(ftid, frun, fiss, classes=("build", "compile", "tests"), scenarios=REPO_SCENARIOS,
                                  attempt="2", drop=False)
            self.assertTrue(acc["outcome_accepted"], acc)
            # 3. the shared producer's repair marks every affected path: Order, Item, the Item contract, the URI source
            self.assertEqual(sorted(acc["remeasure"]), sorted(a["outcome"] for a in NC._node(plan, d.owner)["causal_scope"]["affects"]))
            r.review_and_complete(ftid, frun)
            self.assertEqual(r.native.task(tid)["status"], "ready")            # native promotion, no Operator
            owed_item = NC.remeasure_owed(r.board, r.run_id, B_ITEM)
            owed_order = NC.remeasure_owed(r.board, r.run_id, B_ORDER)
            self.assertEqual(owed_item, ["parity:sc:read-items-1"])
            self.assertIn("parity:sc:create-orders", owed_order)
            # the Order card resumes: its earliest measurement now passes for the owner
            d.measured()
            tid2, run2, iss2 = r.issue(B_ORDER)
            rows = {m["check"]: m for m in r.board.records(tid2, "schedule-measure")[-1]["rows"]}
            self.assertEqual(rows[EFFECTS]["state"], "pass")
            self.assertEqual(len([n for n in r.plan()["nodes"] if n["outcome_id"].startswith("followup:")]), 1)
            # the Order path is measured on its own acceptance; that pass is evidence for Order only
            acc = r.accept_on_run(tid2, run2, iss2, classes=("build", "compile", "tests", "runtime", "parity"),
                                  scenarios=REPO_SCENARIOS, attempt="o1", edit=False, drop=False)
            passed = set(r.board.records(tid2, "accept-commit")[-1]["measurement"].get("checks") or [])
            self.assertIn("parity:sc:create-orders", passed)
            self.assertNotIn("parity:sc:create-orders", NC.remeasure_owed(r.board, r.run_id, B_ORDER))
            self.assertEqual(NC.remeasure_owed(r.board, r.run_id, B_ITEM), ["parity:sc:read-items-1"])
            inode = NC._node(r.plan(), B_ITEM)
            ev, why = NC._satisfied(r.root, r.board, r.run_id, r.plan(), inode, r.worklist, r.tree(), NC._head(r.root))
            self.assertIsNone(ev)
            self.assertTrue(any("remeasure owed" in x and "read-items-1" in x for x in why), why)
        finally:
            d.close()

    def test_a_header_only_difference_is_the_cards_own_cluster_not_a_producer_repair(self):
        """The repository effect is judged on status/body/committed-state findings: a CORS header difference on
        one of its scenarios is the card's own obligation (owned where it is) and does not FAIL the contract."""
        d = Desk()
        r = d.r
        try:
            items = [parity_item("parity:cors-actual", "sc:cors-actual-0a", CO_T.EP_LIST, cause="cors-response")]
            d.measured(items=items, clusters=[cluster("u:cors-actual", "parity:cors-actual")])
            tid, run, iss = r.issue(B_ORDER)
            self.assertEqual(iss["cluster"], "u:cors-actual")
            self.assertEqual(r.plan()["ownership"]["parity:cors-actual"], B_ORDER)   # the header obligation stays here
            rows = r.board.records(tid, "schedule-measure")[-1]["rows"]
            row = next(m for m in rows if m["check"] == EFFECTS)
            self.assertEqual(row["state"], "pass", row)
            # the plain comparison of that scenario is still a FAIL, judged by the card itself
            plain = [m for m in rows if m["check"] == "parity:sc:cors-actual-0a"]
            self.assertTrue(plain and all(m["state"] == "fail" and m["route"].startswith("judged by") for m in plain), plain)
            self.assertFalse([n for n in r.plan()["nodes"] if n["outcome_id"].startswith("followup:")])
        finally:
            d.close()

    def test_repository_effects_ignore_header_only_findings_but_not_status_body_or_server_errors(self):
        from planner import requirement_checks as RC
        req = next(q for q in CO_T.desk()[0].reqs if q["id"] == CO_T.REPO_O)

        def effects(*items):
            return RC.measure(Path("."), [req], worklist={"items": list(items), "measure": {"known": True}},
                              scenarios=REPO_SCENARIOS)[EFFECTS]["status"]
        cors = parity_item("i1", "sc:cors-actual-0a", CO_T.EP_LIST, cause="cors-response")
        ctype = parity_item("i2", "sc:read-orders", CO_T.EP_LIST, cause="content-type-parameter")
        self.assertEqual(effects(), RC.PASS)
        self.assertEqual(effects(cors, ctype), RC.PASS)
        self.assertEqual(effects(parity_item("i3", "sc:read-orders", CO_T.EP_LIST)), RC.FAIL)          # a body difference
        self.assertEqual(effects(parity_item("i4", "sc:cors-actual-0a", CO_T.EP_LIST, cause="cors-response",
                                             server_error=True)), RC.FAIL)                                 # it threw
        self.assertEqual(effects(dict(parity_item("i5", "", CO_T.EP_LIST), scenarios=["sc:create-orders"])), RC.FAIL)
        # the plain comparison of the header-only scenario is still its own FAIL
        plain = dict(req, acceptance=["parity:sc:cors-actual-0a"])
        self.assertEqual(RC.measure(Path("."), [plain], worklist={"items": [cors], "measure": {"known": True}},
                                    scenarios=REPO_SCENARIOS)["parity:sc:cors-actual-0a"]["status"], RC.FAIL)

    def _accept_order(self, d, tid, run, iss, *, items=(), clusters=(), started=True, attempt="1"):
        """The Order card's candidate committed and judged, the verification having measured it (started or not)."""
        r = d.r
        r.edit(iss["allowed_paths"][0], "// Order accepted %s\n" % attempt)
        NC.check_write(r.board, task_id=tid, run_id=run, rel_paths=list(iss["allowed_paths"]))
        NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="ACCEPTED", candidate=r.tree(), attempt=attempt)
        NB.git(r.root, "add", "-A")
        NB.git(r.root, "commit", "-qm", "order %s" % attempt)
        d.measured(started=started, items=items, clusters=clusters)
        return NC.accept_commit(r.root, r.board, task_id=tid, run_id=run, attempt=attempt,
                                commit=NB.git(r.root, "rev-parse", "HEAD"),
                                measurement={"classes": ["build", "compile", "tests", "runtime", "parity"],
                                             "scenarios": list(REPO_SCENARIOS)})

    def test_a_row_pending_at_issue_is_measured_on_the_accepted_candidate(self):
        d = Desk()
        r = d.r
        try:
            own = [parity_item("parity:read", "sc:read-orders", CO_T.EP_LIST)]
            d.measured(started=False, items=own, clusters=[cluster("c:read", "parity:read")])
            tid, run, iss = r.issue(B_ORDER)
            self.assertEqual({m["check"]: m["state"] for m in iss["schedule"]}[EFFECTS], "pending")
            acc = self._accept_order(d, tid, run, iss)                       # started, nothing open
            self.assertEqual({m["check"]: m["state"] for m in acc["schedule"]}[EFFECTS], "pass")
            recs = r.board.records(tid, "schedule-measure")
            self.assertEqual((len(recs), recs[-1]["at"]), (2, "accept"))
            st = NC.schedule_status(r.board, r.run_id, r.plan())["%s|%s" % (d.owner, EFFECTS)]
            self.assertEqual((st["state"], st["at"]), ("pass", B_ORDER))       # not left to M4
            # a replay of the same acceptance measurement records nothing new
            NC.schedule_at_issue(r.root, r.board, task_id=tid, run_id=run, run=r.run_id, plan=r.plan(), holder=B_ORDER,
                                 worklist=r.worklist, tree=r.tree(), accepted=recs[-1]["accept"])
            self.assertEqual(len(r.board.records(tid, "schedule-measure")), 2)
        finally:
            d.close()

    def test_a_failure_measured_at_acceptance_is_routed_to_the_owner_without_holding_the_accepted_card(self):
        d = Desk()
        r = d.r
        try:
            own = [parity_item("parity:read", "sc:read-orders", CO_T.EP_LIST)]
            d.measured(started=False, items=own, clusters=[cluster("c:read", "parity:read")])
            tid, run, iss = r.issue(B_ORDER)
            owner_budget = dict(NC._node(r.plan(), d.owner)["budget"])
            # the accepted candidate starts; a committed write another path owns still fails there
            other = parity_item("parity:item", "sc:read-items-1", CO_T.EP_ITEM)
            acc = self._accept_order(d, tid, run, iss, items=[other], clusters=[cluster("c:item", "parity:item")])
            fid = "followup:%s:m3g1" % d.owner
            self.assertEqual(acc["schedule_routed"], [fid])
            self.assertEqual({m["check"]: m["route"] for m in acc["schedule"]}[EFFECTS], "owner")
            plan = r.plan()
            self.assertEqual(NC._node(plan, fid)["budget"], owner_budget)
            ftid = r.tid(fid)
            self.assertNotIn(ftid, r.native.task(tid)["parents"])            # the accepted card is not held
            for t in (r.tid(B_ITEM), r.tid(B_STATUS), r.tid("assess:m4:g1")):
                self.assertIn(ftid, r.native.task(t)["parents"])
            self.assertEqual(len(r.board.records(tid, "schedule-route")), 1)
            # replay: already routed, nothing new
            key = r.board.records(tid, "schedule-measure")[-1]["accept"]
            NC.schedule_at_issue(r.root, r.board, task_id=tid, run_id=run, run=r.run_id, plan=r.plan(), holder=B_ORDER,
                                 worklist=r.worklist, tree=r.tree(), accepted=key)
            self.assertEqual(len([n for n in r.plan()["nodes"] if n["outcome_id"].startswith("followup:")]), 1)
            self.assertEqual(len(r.board.records(tid, "schedule-route")), 1)
        finally:
            d.close()

    def test_a_restart_during_a_pending_earliest_measurement_keeps_the_row_pending(self):
        d = Desk()
        r = d.r
        try:
            d.measured(started=False)                                        # packaged, not yet started
            tid, run, iss = r.issue(B_ORDER)                                 # issued: nothing to route
            key = "%s|%s" % (d.owner, EFFECTS)
            got = {m["check"]: m for m in iss["schedule"]}[EFFECTS]
            self.assertEqual(got["state"], "pending")
            self.assertTrue(any(m.startswith("application:started") for m in got["missing"]), got)
            self.assertTrue(any(m.startswith("database:working") for m in got["missing"]), got)
            r.native.end_run(tid, "ready")                                   # the worker dies; the dispatcher restarts it
            run2, lock2 = r.native.claim(tid)
            iss2 = NC.issue(r.root, r.board, task_id=tid, run_id=run2, claim_lock=lock2)
            got2 = {m["check"]: m for m in iss2["schedule"]}[EFFECTS]
            self.assertEqual((got2["state"], got2["missing"]), ("pending", got["missing"]))
            st = NC.schedule_status(r.board, r.run_id, r.plan())[key]
            self.assertEqual(st["state"], "pending")                          # never PASS, never dropped
            rec = next(m for m in r.board.records(tid, "schedule-measure")[-1]["rows"] if m["check"] == EFFECTS)
            self.assertEqual(rec["qualification"]["status"], "unknown")        # no qualification of OrderStore exists here
            self.assertIn((d.owner, EFFECTS), {(x["outcome"], x["check"]) for x in
                                              NC._node(r.plan(), "assess:m4:g1")["acceptance"]["deferred_requirement_checks"]})
            self.assertFalse([n for n in r.plan()["nodes"] if n["outcome_id"].startswith("followup:")])
            self.assertEqual(len(r.board.records(tid, "schedule-measure")), 2)  # one per run; a replay records nothing
            NC.issue(r.root, r.board, task_id=tid, run_id=run2, replay_unchanged=True)
            self.assertEqual(len(r.board.records(tid, "schedule-measure")), 2)
        finally:
            d.close()


# ===========================================================================
class IssuanceOrder(unittest.TestCase):

    def test_the_server_error_producer_goes_before_the_dependent_header_and_the_preflight_is_not_held(self):
        d = Desk()
        r = d.r
        try:
            # the producer is not measured PASS: the scenarios that throw or differ were not compared on this
            # candidate, so its verdict is unknown -- not a FAIL to route, and not a pass either
            scen = [s for s in REPO_SCENARIOS if s not in ("sc:create-orders", "sc:cors-actual-0a")]
            items = [parity_item("parity:cors-actual", "sc:cors-actual-0a", CO_T.EP_LIST, cause="cors-response"),
                     parity_item("parity:cors-pre", "sc:cors-preflight-0a", CO_T.EP_ADD, cause="cors-response"),
                     parity_item("parity:create", "sc:create-orders", CO_T.EP_ADD, server_error=True)]
            clusters = [cluster("u:cors-actual", "parity:cors-actual"), cluster("u:cors-pre", "parity:cors-pre"),
                        cluster("c:create", "parity:create")]
            d.measured(items=items, clusters=clusters, scenarios=scen)
            tid, run, iss = r.issue(B_ORDER)
            self.assertEqual({m["check"]: m["state"] for m in iss["schedule"]}[EFFECTS], "unknown")
            self.assertEqual(iss["cluster"], "c:create")                     # the producer's repair first
            # the producer is still not PASS: the preflight (no `after`) comes before the dependent header comparison
            d.measured(items=items[:2], clusters=clusters[:2], scenarios=scen)
            iss = NC.issue(r.root, r.board, task_id=tid, run_id=run)
            self.assertEqual(iss["cluster"], "u:cors-pre")
            plan = r.plan()
            node = NC._node(plan, B_ORDER)
            rows = {x["check"]: x for x in node["check_plan"]}
            self.assertTrue(rows["parity:sc:cors-actual-0a"].get("after"))
            self.assertFalse(rows["parity:sc:cors-preflight-0a"].get("after"))
            # without a failing producer the work list's order stands
            order = NC.issue_order(plan, node, {k: "pass" for k in rows["parity:sc:cors-actual-0a"]["after"]})
            self.assertEqual(order, {"first": set(), "held": set()})
            wl = {"items": items[:2], "clusters": clusters[:2]}
            own = {"parity:cors-actual", "parity:cors-pre"}
            self.assertEqual(NC._allowed_paths(node, wl, own, order)[0], "u:cors-actual")
            failing = NC.issue_order(plan, node, {k: "fail" for k in rows["parity:sc:cors-actual-0a"]["after"]})
            self.assertIn("cors-actual-0a", failing["held"])
            self.assertNotIn("cors-preflight-0a", failing["held"] | failing["first"])
            self.assertEqual(NC._allowed_paths(node, wl, own, failing)[0], "u:cors-pre")
            # a header-only difference on a producer scenario is not the producer's repair
            self.assertIn("cors-actual-0a", failing["first"])
            self.assertEqual(NC._allowed_paths(node, {"items": items, "clusters": clusters}, own | {"parity:create"},
                                               failing)[0], "c:create")
        finally:
            d.close()


# ===========================================================================
class Qualification(unittest.TestCase):

    def test_the_id_binds_to_the_m3_strategy_test_read_only(self):
        tid, frag = QE.covered_fragment()
        self.assertEqual(tid, "reference-repository-strategy-runtime")
        qid = QE.PREFIX + frag
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            got = QE.resolve(qid, root)
            self.assertEqual(got["status"], "unknown")
            self.assertTrue(got["test"].endswith("reference-repository-strategy-runtime.test.py"))
            self.assertIn("reference-qualification.sh", got["missing"][0])
            res = root / QE.RESULTS
            res.parent.mkdir(parents=True)

            def write(outcome, tree="t1"):
                res.write_text(json.dumps({"schema": QE.RESULTS_SCHEMA, "suites": [
                    {"test_id": tid, "outcome": outcome, "summary": "s", "reason": "SKIP: podman unavailable"}],
                    "cases": [{"test_id": tid + "::reference-port", "case": "repository-strategy:reference-port",
                               "outcome": "ACCEPTED", "artifact": {"candidate_tree": tree}}]}))
            write("SKIPPED")
            got = QE.resolve(qid, root, tree="t1")
            self.assertEqual(got["status"], "unknown")                       # a SKIP is never a pass
            self.assertIn("SKIPPED", got["missing"][0])
            write("PASS")
            got = QE.resolve(qid, root, tree="t1")
            self.assertEqual((got["status"], got["evidence"]["candidate_bound"]), ("qualified", True))
            self.assertIn("evidence only", got["authority"])
            self.assertFalse(QE.resolve(qid, root, tree="t2")["evidence"]["candidate_bound"])
            write("FAIL")
            self.assertEqual(QE.resolve(qid, root)["status"], "failed")
            other = QE.resolve(QE.PREFIX + CO_T.FRAG_O, root)
            self.assertEqual(other["status"], "unknown")
            self.assertIn("covers only", other["missing"][0])
            self.assertEqual(QE.resolve("qualify:other:x", root)["status"], "unknown")


# ===========================================================================
class V29(unittest.TestCase):

    def test_the_owner_repository_contract_is_scheduled_at_the_owner_card(self):
        doc = json.loads(gzip.open(HERE / "fixtures" / "v29-plan-r1-schedule.json.gz").read())
        plan = doc["plan"]
        from planner.compatibility_objectives import schedule_checks
        schedule_checks(plan)
        base = "org.springframework.samples.petclinic"
        owner_card = "behavior:http:%s.rest.OwnerRestController" % base
        pet_card = "behavior:http:%s.rest.PetRestController" % base
        chk = "behavior:repository-effects:%s.repository.OwnerRepository" % base
        row = next(x for x in NC.scheduled_rows(plan, owner_card) if x["check"] == chk)
        self.assertEqual(row["owner"], "objective:selected-repository-implementation:b9a186197ac6")
        self.assertEqual(row["qualification"], QE.PREFIX + "%s.repository.OwnerRepository" % base)
        self.assertTrue({"application:packaged", "application:started", "database:working"} <= set(row["requires"]))
        self.assertIn(chk, {x["check"] for x in NC.scheduled_rows(plan, pet_card)})
        self.assertEqual(QE.resolve(row["qualification"], Path(tempfile.gettempdir()) / "no-such-dest")["status"], "unknown")


if __name__ == "__main__":
    unittest.main(verbosity=1)
