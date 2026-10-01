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
from planner import measurement as ME  # noqa: E402
from planner import qualification_evidence as QE  # noqa: E402
from planner.paths import VERIFY_RUN  # noqa: E402
from planner.worklist import PARITY_RECEIPT_SCHEMA, SCENARIO_CORPORA, parity_receipt_file  # noqa: E402

B_ORDER, B_ITEM, B_STATUS = "behavior:http:" + CO_T.O, "behavior:http:" + CO_T.ITEM, "behavior:http:" + CO_T.STATUS
EFFECTS = "behavior:repository-effects:" + CO_T.FRAG_O
ORDER_FILE = CO_T.P + "web/OrderApi.java"
REPO_SCENARIOS = ["sc:auth-anonymous-read-orders-1", "sc:cors-actual-0a", "sc:create-orders", "sc:read-items-1",
                  "sc:read-orders", "sc:read-orders-1"]


class Desk:
    """The desk composition published natively; every non-behaviour card done."""

    def __init__(self):
        w, eps, oracles = CO_T.desk()
        # the shape the real producers give (source_requirements: a Location-building handler names the
        # scenarios that capture its Location; one bound corpus per mode): without them a planned
        # verification unit refuses VERIFICATION_SCOPE_UNRESOLVED, as it must (v29 Owner, 7d77d14f)
        for q in w.reqs:
            if q["id"] == "req:behavior-verification:" + CO_T.EP_ADD:
                q["facts"]["location"] = {"builds_location": True, "coverage": ["sc:create-orders"]}
        self.r = r = NB.Run(publish=False)
        NB.mirror_layout(r.root)
        corpus = r.root / SCENARIO_CORPORA[0]
        corpus.parent.mkdir(parents=True, exist_ok=True)
        corpus.write_text(json.dumps({"scenarios": [{"id": s} for s in sorted(
            {x for v in CO_T.ORDERS.values() for x in v} | set(REPO_SCENARIOS))]}))
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
    def measured(self, *, started=True, items=(), clusters=(), scenarios=REPO_SCENARIOS, record_fail=()):
        r = self.r
        tree = r.tree()
        r.worklist.update(candidate_sha256=tree, items=list(items), clusters=list(clusters),
                          runtime={"package": {"ran": True, "rc": 0},
                                   "boot": {"ran": started, "rc": 0 if started else None, "ready": started},
                                   "blockers": [], "ready": started})
        r.save_worklist()
        # what the comparator leaves (68152b24 / 945db1ab: a scenario passes only on its own record in its
        # mode's receipt bound to this candidate): a verdict record per compared scenario, FAIL where an open
        # finding names it, and the receipt row that declares it
        failing = {str(x) for i in items for x in [i.get("scenario")] + list(i.get("scenarios") or []) if x}
        failing |= {str(s) for s in record_fail}   # a comparison FAIL no work-list finding explains (H-13: unowned evidence)
        verdict = {s: ("FAIL" if s in failing else "PASS") for s in scenarios}
        receipt = {"schema": PARITY_RECEIPT_SCHEMA, "security_mode": "disabled",
                   "verdict": "FAIL" if "FAIL" in verdict.values() else "PASS",
                   "binding": {"mode": "candidate", "candidate_sha256": tree},
                   "entry_points": [{"entry_point": "ep:x:" + s, "verdict": v, "scenarios": [s]}
                                    for s, v in sorted(verdict.items())]}
        p = r.root / parity_receipt_file("disabled")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(receipt))
        sdir = r.root / "verification" / "parity" / "scenarios"
        sdir.mkdir(parents=True, exist_ok=True)
        for old in sdir.glob("*.json"):
            old.unlink()
        for s, v in verdict.items():
            (sdir / ("%s.json" % s.replace(":", "_"))).write_text(json.dumps(
                {"schema": "rhoai3.scenario-parity/v1", "scenario": s, "verdict": v, "security_mode": "disabled",
                 "binding": {"mode": "candidate", "candidate_sha256": tree}}))

    def accept_verified(self, tid, run, scope_by_mode, *, attempt):
        """run-verify's acceptance measurement of an issued verification scope: every issued scenario compared
        in its mode on this candidate (records + receipt), run.json naming each mode's assignment, and the
        acceptance judged on that execution record rather than on a worker's list."""
        r = self.r
        NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="ACCEPTED", candidate=r.tree(), attempt=attempt)
        NB.git(r.root, "add", "-A")
        NB.git(r.root, "commit", "-qm", "verify %s" % attempt, "--allow-empty")
        sids = [s for m in sorted(scope_by_mode) for s in scope_by_mode[m]]
        self.measured(scenarios=sids)
        r.worklist.update(measure={"known": True, "tuple": [0, 0, 0], "compile_errors": 0, "failing_tests": 0},
                          sources={"surefire": {"reports": 1}})
        r.save_worklist()
        run_doc = {"candidate_sha256": r.tree(), "mode": "acceptance", "classpath": {"ran": True, "rc": 0},
                   "diagnostics": {"ran": True}, "tests": {"ran": True, "rc": 0},
                   "runtime": {"parity": {"ran": True, "rc": 0, "trigger": "issued-card", "scoped": True,
                                          "scenarios": sids, "security_mode": "disabled",
                                          "modes": {m: {"rc": 0, "scenarios": list(v)} for m, v in scope_by_mode.items()}}}}
        (r.root / VERIFY_RUN).parent.mkdir(parents=True, exist_ok=True)
        (r.root / VERIFY_RUN).write_text(json.dumps(run_doc))
        ex = ME.execution(r.worklist, run_doc, "", r.root)
        return NC.accept_commit(r.root, r.board, task_id=tid, run_id=run, attempt=attempt,
                                commit=NB.git(r.root, "rev-parse", "HEAD"),
                                measurement={"classes": ME.classes(ex), "execution": ex,
                                             "scenarios": list(ex["stages"]["parity"].get("scenarios") or [])})

    def complete(self, oid):
        """An outcome accepted and reviewed earlier (native done)."""
        tid = self.r.tid(oid)
        self.r.native.claim(tid)
        self.r.native.complete(tid)
        return tid

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
            # a repository read the ACCEPTED Item card relied on regresses on the measured candidate: sc:read-items-1
            # comes back FAIL with no work-list finding, and no executable card judges it now (its judge, Item, is
            # done) -- unowned evidence, so the repository owner's follow-up is the repair route (H13-R1: a
            # record-only FAIL an OPEN card judges is that card's own repair --
            # test_a_record_only_failure_an_open_card_judges_stays_with_that_card)
            d.complete(B_ITEM)
            d.measured(record_fail=("sc:read-items-1",))
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
            for t in (tid, r.tid(B_STATUS), m4):
                self.assertIn(ftid, r.native.task(t)["parents"])
            # M4 stays the backstop of the same row
            m4_rows = {(x["outcome"], x["check"]) for x in NC._node(plan, "assess:m4:g1")["acceptance"]["deferred_requirement_checks"]}
            self.assertIn((d.owner, EFFECTS), m4_rows)
            rec = r.board.records(tid, "schedule-measure")[-1]
            got = next(m for m in rec["rows"] if m["check"] == EFFECTS)
            self.assertEqual((got["state"], got["owner"], got["route"]), ("fail", d.owner, "owner"))
            self.assertIn("sc:read-items-1", got["detail"])
            self.assertEqual(got["witnesses"]["record_only"], ["sc:read-items-1"])
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
            # the failing evidence is the comparator's record of the PREVIOUS tree (no work-list finding keeps it
            # open): on this edited, not re-compared candidate the effect is unknown or failed -- never discharged
            self.assertTrue(any(EFFECTS in x and ("fail" in x or "unknown" in x) for x in acc["not_accepted_because"]), acc)
            # the repaired candidate is compared again: nothing open, every repository scenario PASS on it
            d.measured()
            fiss = NC.issue(r.root, r.board, task_id=ftid, run_id=frun)
            # v30 H-10: the follow-up is ISSUED the scenarios its owed effects check judges, and its acceptance is
            # run-verify's comparison of exactly that scope (an empty scope once let it pass on a worker's list)
            fscope = (fiss.get("planned_unit") or {}).get("verification") or {}
            self.assertEqual(sorted(s for v in fscope["scenarios_by_mode"].values() for s in v),
                             sorted(s for q in plan["requirements"] if q["id"] == CO_T.REPO_O
                                    for v in q["facts"]["verification"] for s in v["scenarios"]))
            acc = d.accept_verified(ftid, frun, fscope["scenarios_by_mode"], attempt="2")
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
            # nothing is left to repair: the Order card is its verification-only unit, and the ISSUED scope is
            # the acceptance authority (945db1ab): worker receipts naming a subset leave it unaccepted
            self.assertEqual((iss2["allowed_paths"], iss2["cluster"].startswith("planned:")), ([], True))
            scope = iss2["planned_unit"]["verification"]["scenarios_by_mode"]
            self.assertEqual(sorted(scope), ["disabled"])
            self.assertIn("sc:create-orders", scope["disabled"])
            acc = r.accept_on_run(tid2, run2, iss2, classes=("build", "compile", "tests", "runtime", "parity"),
                                  scenarios=REPO_SCENARIOS, attempt="o0", edit=False, drop=False)
            self.assertFalse(acc["outcome_accepted"])
            self.assertTrue(any("runner did not compare" in x for x in acc["not_accepted_because"]), acc)
            # the Order path is measured on its own acceptance (run-verify compared the issued scope in its
            # mode); that pass is evidence for Order only
            iss2 = NC.issue(r.root, r.board, task_id=tid2, run_id=run2)
            self.assertEqual(iss2["planned_unit"]["verification"]["scenarios_by_mode"], scope)
            acc = d.accept_verified(tid2, run2, scope, attempt="o1")
            self.assertTrue(acc["outcome_accepted"], acc)
            # M-2 on the verification-only unit: the schedule measured at its issue (schedule_at_issue) passes
            # and at its acceptance neither refuses nor routes anything once the owner's repair holds
            self.assertEqual({m["check"]: m["state"] for m in iss2["schedule"]}[EFFECTS], "pass")
            # at acceptance the row is re-measured on the scope this unit compared: sc:read-items-1 (the Item
            # path) is not in it, so the row is unknown there -- never a FAIL routed, never a refusal
            got = {m["check"]: m["state"] for m in acc["schedule"]}[EFFECTS]
            self.assertEqual((got, acc["schedule_routed"]), ("unknown", []))
            self.assertNotIn("sc:read-items-1", scope["disabled"])
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

    def test_a_failure_owned_by_the_holder_is_routed_to_the_holder_not_to_a_follow_up(self):
        """H-13 (v30 t_557b0bed / t_b996bea6, architect decision 2026-10-01): the scheduled repository effect FAILS
        only through a scenario-less read-oracle body finding that covers one of its scenarios and is owned by the
        holder. No follow-up is minted (the holder would wait on it while the follow-up's acceptance waits on the
        holder's finding); the holder is issued its own cluster; the check stays FAIL and owed, and is measured
        PASS once the holder's repair is compared."""
        d = Desk()
        r = d.r
        try:
            finding = dict(parity_item("parity:h13-covered-body", "", CO_T.EP_LIST), scenarios=["sc:cors-actual-0a"])
            d.measured(items=[finding], clusters=[cluster("c:h13-body", finding["id"])])
            tid, run, iss = r.issue(B_ORDER)                                   # no OWNER_REPAIR_PENDING
            self.assertEqual(iss["cluster"], "c:h13-body")
            plan = r.plan()
            self.assertEqual(plan["ownership"][finding["id"]], B_ORDER)
            self.assertFalse([n for n in plan["nodes"] if n["outcome_id"].startswith("followup:")])
            self.assertNotIn(NC.SCHEDULED_OBLIGATION % (d.owner, EFFECTS), plan["ownership"])
            row = next(m for m in r.board.records(tid, "schedule-measure")[-1]["rows"] if m["check"] == EFFECTS)
            self.assertEqual((row["state"], row["repair_owners"]), ("fail", [B_ORDER]), row)   # measured truth unchanged
            self.assertTrue(row["route"].startswith("evidence owned by open outcomes"), row["route"])
            self.assertEqual([f["finding"] for f in row["witnesses"]["findings"]], [finding["id"]])
            self.assertEqual(row["witnesses"]["findings"][0]["via"], "coverage")
            # the holder repairs its own finding; the repaired candidate is compared: the owed check passes there
            d.measured()
            tid2, run2, iss2 = r.issue(B_ORDER)
            row = next(m for m in r.board.records(tid2, "schedule-measure")[-1]["rows"] if m["check"] == EFFECTS)
            self.assertEqual(row["state"], "pass", row)
        finally:
            d.close()

    def test_a_mixed_failure_mints_a_follow_up_that_waits_on_the_open_owner_not_the_reverse(self):
        """H-13 mixed ownership: one failing finding is the holder's, another failure no finding explains
        (record-only, unowned). A follow-up is minted for the unowned remainder; it WAITS ON the holder (whose
        finding its acceptance needs), the holder does not wait on it, the holder is not refused, and no
        acceptance cycle is published."""
        d = Desk()
        r = d.r
        try:
            finding = dict(parity_item("parity:h13-covered-body", "", CO_T.EP_LIST), scenarios=["sc:cors-actual-0a"])
            d.complete(B_ITEM)                                                 # read-items-1's judge is accepted
            d.measured(items=[finding], clusters=[cluster("c:h13-body", finding["id"])], record_fail=("sc:read-items-1",))
            tid, run, iss = r.issue(B_ORDER)                                   # the holder repairs its share first
            self.assertEqual(iss["cluster"], "c:h13-body")
            plan = r.plan()
            fid = "followup:%s:m3g1" % d.owner
            fnode, hnode = NC._node(plan, fid), NC._node(plan, B_ORDER)
            self.assertIsNotNone(fnode)
            self.assertIn(B_ORDER, fnode["parents"])
            self.assertNotIn(fid, hnode["parents"])
            self.assertNotIn(fid, NC._waits_on(plan, B_ORDER))
            self.assertEqual(NC.acceptance_cycles(plan, [(fid, B_ORDER)]), [])
            self.assertEqual(len(OG.topo_order(plan["nodes"])), len(plan["nodes"]))
            row = next(m for m in r.board.records(tid, "schedule-measure")[-1]["rows"] if m["check"] == EFFECTS)
            self.assertEqual((row["state"], row["route"], row["contributors"]), ("fail", "owner", [B_ORDER]), row)
            self.assertEqual(row["witnesses"]["record_only"], ["sc:read-items-1"])
        finally:
            d.close()

    def test_the_holder_owned_route_does_not_depend_on_names(self):
        """H-13 acceptance 1, renamed equivalent: other finding/cluster ids and another covered scenario of the
        same effects check take the same route (nothing keys on the v30 identifiers)."""
        for fid, cid, sc in (("parity:zz-renamed-0001", "c:renamed-body", "sc:read-orders"),
                             ("parity:aa-other-body", "u:other-unit", "sc:auth-anonymous-read-orders-1")):
            d = Desk()
            r = d.r
            try:
                ep = CO_T.EP_LIST if sc == "sc:read-orders" else CO_T.EP_GET
                finding = dict(parity_item(fid, "", ep), scenarios=[sc])
                d.measured(items=[finding], clusters=[cluster(cid, fid)])
                tid, run, iss = r.issue(B_ORDER)
                self.assertEqual(iss["cluster"], cid)
                self.assertFalse([n for n in r.plan()["nodes"] if n["outcome_id"].startswith("followup:")], fid)
                row = next(m for m in r.board.records(tid, "schedule-measure")[-1]["rows"] if m["check"] == EFFECTS)
                self.assertEqual((row["state"], row["repair_owners"]), ("fail", [B_ORDER]), row)
            finally:
                d.close()

    def test_two_open_owners_keep_their_findings_and_no_follow_up_is_minted(self):
        """H-13 acceptance 4: one failing finding is the holder's, the other belongs (by the deterministic
        finding resolver: its file's planned requirement) to another OPEN card not yet issued. Both stay with
        their owners, the check is FAIL with both as repair owners, nothing is minted, nothing is lost."""
        d = Desk()
        r = d.r
        try:
            item_file = CO_T.P + "web/ItemApi.java"
            f1 = dict(parity_item("parity:own-body", "", CO_T.EP_LIST), scenarios=["sc:cors-actual-0a"])
            f2 = dict(parity_item("parity:item-body", "", CO_T.EP_ITEM), scenarios=["sc:read-items-1"], path=item_file)
            d.measured(items=[f1, f2], clusters=[cluster("c:own", f1["id"]),
                                                 dict(cluster("c:item", f2["id"]), path=item_file, write_set=[item_file])])
            tid, run, iss = r.issue(B_ORDER)
            self.assertEqual(iss["cluster"], "c:own")
            plan = r.plan()
            self.assertFalse([n for n in plan["nodes"] if n["outcome_id"].startswith("followup:")])
            row = next(m for m in r.board.records(tid, "schedule-measure")[-1]["rows"] if m["check"] == EFFECTS)
            self.assertEqual((row["state"], row["repair_owners"]), ("fail", sorted([B_ORDER, B_ITEM])), row)
            self.assertEqual(sorted(f["finding"] for f in row["witnesses"]["findings"]), ["parity:item-body", "parity:own-body"])
            self.assertIn(B_ITEM, row["route"])
        finally:
            d.close()

    def test_unknown_evidence_is_verification_debt_never_a_repair_and_never_a_pass(self):
        """H-13 acceptance 6 with the architect's R1 ruling: the effects check FAILS through a holder-owned
        finding while another of its scenarios was not compared on this candidate. The missing comparison is
        a verification prerequisite (verification_owed), not an unowned product repair: no follow-up is
        minted for it, the row stays FAIL (never PASS) and names the debt."""
        d = Desk()
        r = d.r
        try:
            finding = dict(parity_item("parity:h13-covered-body", "", CO_T.EP_LIST), scenarios=["sc:cors-actual-0a"])
            d.measured(items=[finding], clusters=[cluster("c:h13-body", finding["id"])],
                       scenarios=[s for s in REPO_SCENARIOS if s != "sc:read-items-1"])
            tid, run, _iss = r.issue(B_ORDER)
            row = next(m for m in r.board.records(tid, "schedule-measure")[-1]["rows"] if m["check"] == EFFECTS)
            self.assertEqual(row["state"], "fail", row)
            self.assertEqual(row["verification_owed"], ["sc:read-items-1"])
            self.assertIn("verification owed", row["route"])
            self.assertFalse([n for n in r.plan()["nodes"] if n["outcome_id"].startswith("followup:")])
        finally:
            d.close()

    def test_a_record_only_failure_an_open_card_judges_stays_with_that_card(self):
        """H13-R1 (architect reproduction): the holder's body finding AND a record-only FAIL of
        sc:create-orders, which the holder's own immediate parity and Location checks judge. Both are the
        holder's repairs: no repository follow-up is created behind the holder (it would wait on the holder
        while the holder's acceptance needs that very scenario)."""
        d = Desk()
        r = d.r
        try:
            finding = dict(parity_item("parity:probe-body", "", CO_T.EP_LIST), scenarios=["sc:cors-actual-0a"])
            d.measured(items=[finding], clusters=[cluster("c:probe-body", finding["id"])], record_fail=("sc:create-orders",))
            tid, run, iss = r.issue(B_ORDER)
            self.assertFalse([n for n in r.plan()["nodes"] if n["outcome_id"].startswith("followup:")])
            row = next(m for m in r.board.records(tid, "schedule-measure")[-1]["rows"] if m["check"] == EFFECTS)
            self.assertEqual((row["state"], row["repair_owners"]), ("fail", [B_ORDER]), row)
            self.assertIn("scenario:sc:create-orders -> %s" % B_ORDER, row["route"])
            self.assertIn("sc:create-orders", NC.judged_now(r.plan(), NC._node(r.plan(), B_ORDER)))
        finally:
            d.close()

    def test_an_archived_or_missing_owner_is_not_an_open_owner(self):
        """H13-R2: a finding whose resolved owner is archived (or has no native task) cannot be repaired
        there; it is unowned (the owner's follow-up), never "owned by an open outcome"."""
        for how in ("archived",):
            d = Desk()
            r = d.r
            try:
                other = r.tid(B_ITEM)
                r.native.tasks[other]["status"] = "archived"
                item_file = CO_T.P + "web/ItemApi.java"
                f = dict(parity_item("parity:archived-owner", "", CO_T.EP_ITEM), scenarios=["sc:read-items-1"], path=item_file)
                d.measured(items=[f], clusters=[dict(cluster("c:archived", f["id"]), path=item_file, write_set=[item_file])])
                # the route is the owner's follow-up; its publication then fails closed on this board, whose
                # planned Item card is archived (read-back refuses an archived identity), never "owned"
                with self.assertRaises(Refusal) as cm:
                    r.issue(B_ORDER)
                self.assertEqual(cm.exception.code, "PUBLICATION_READBACK", cm.exception.detail)
                tid = r.tid(B_ORDER)
                row = next(m for m in r.board.records(tid, "schedule-measure")[-1]["rows"] if m["check"] == EFFECTS)
                self.assertEqual(row["route"], "owner", (how, row["route"]))
                self.assertEqual(row["repair_owners"], [])
            finally:
                d.close()

    def test_a_missing_native_task_is_not_an_open_owner(self):
        """H13-R2, missing variant at the router: the resolved owner has no native task."""
        d = Desk()
        r = d.r
        try:
            item_file = CO_T.P + "web/ItemApi.java"
            f = dict(parity_item("parity:missing-owner", "", CO_T.EP_ITEM), scenarios=["sc:read-items-1"], path=item_file)
            d.measured(items=[f], clusters=[dict(cluster("c:missing", f["id"]), path=item_file, write_set=[item_file])])
            plan = r.plan()
            row = next(x for x in NC.scheduled_rows(plan, B_ORDER) if x["check"] == EFFECTS)
            real = NC._native_status_fn(r.board, r.run_id)
            er = NC._effect_route(r.root, plan, dict(row, state="fail"), r.worklist, r.tree(), NC.measured_scenarios(r.root, r.tree()),
                                  lambda o: "missing" if o == B_ITEM else real(o))
            self.assertIn("parity:missing-owner", er["unowned"])
            self.assertFalse(er["complete"])
            self.assertEqual(real("no-such-outcome"), "missing")
        finally:
            d.close()

    def test_ambiguous_ownership_is_a_typed_unresolved_result_and_publishes_nothing(self):
        """H13-R2 (architect reproduction): two planned outcomes claim the finding's locus. No repair
        destination is chosen: the row stays FAIL with a typed unresolved route, nothing is published, the
        holder is not refused."""
        d = Desk()
        r = d.r
        try:
            plan = r.plan()
            NC._node(plan, B_ITEM)["plan_paths"].append(ORDER_FILE)
            f = dict(parity_item("parity:ambiguous-owner", "", CO_T.EP_LIST), scenarios=["sc:cors-actual-0a"])
            d.measured(items=[f], clusters=[cluster("c:ambiguous", f["id"])])
            tid, run, lock = r.claim(B_ORDER)
            out = NC.schedule_at_issue(r.root, r.board, task_id=tid, run_id=run, run=r.run_id, plan=plan,
                                       holder=B_ORDER, worklist=r.worklist, tree=r.tree())
            self.assertEqual(out["routed"], [])
            self.assertTrue(out["unrouted"] and out["unrouted"][0][1] == "ambiguous-ownership", out["unrouted"])
            row = next(m for m in out["rows"] if m["check"] == EFFECTS)
            self.assertEqual(row["state"], "fail")
            self.assertTrue(row["route"].startswith("unresolved: ambiguous ownership"), row["route"])
            self.assertFalse([n for n in r.plan()["nodes"] if n["outcome_id"].startswith("followup:")])
        finally:
            d.close()

    def test_routing_is_idempotent_on_replay(self):
        """H-13 acceptance 7: the same failure measured again (a repeated issue of the same run, as after a
        restart) takes the same route, mints nothing and changes no plan revision."""
        d = Desk()
        r = d.r
        try:
            finding = dict(parity_item("parity:h13-covered-body", "", CO_T.EP_LIST), scenarios=["sc:cors-actual-0a"])
            d.measured(items=[finding], clusters=[cluster("c:h13-body", finding["id"])])
            tid, run, iss = r.issue(B_ORDER)
            rev = r.plan()["revision"]
            again = NC.issue(r.root, r.board, task_id=tid, run_id=run)
            self.assertEqual(again["cluster"], iss["cluster"])
            self.assertEqual(r.plan()["revision"], rev)
            self.assertFalse([n for n in r.plan()["nodes"] if n["outcome_id"].startswith("followup:")])
            routes = [next(m for m in rec["rows"] if m["check"] == EFFECTS)["route"]
                      for rec in r.board.records(tid, "schedule-measure")]
            self.assertTrue(routes and len(set(routes)) == 1, routes)
        finally:
            d.close()

    def test_an_acceptance_cycle_is_named_before_publication(self):
        """H-13: the native parent graph can be acyclic while an acceptance dependency closes a cycle; both a
        direct and a transitive one are named (the router refuses such a revision before publication)."""
        plan = {"nodes": [{"outcome_id": "F", "parents": []}, {"outcome_id": "A", "parents": ["F"]},
                          {"outcome_id": "B", "parents": ["A"]}, {"outcome_id": "C", "parents": []}]}
        self.assertEqual(len(NC.acceptance_cycles(plan, [("F", "A")])), 1)          # A waits on F; F needs A's repair
        self.assertEqual(len(NC.acceptance_cycles(plan, [("F", "B")])), 1)          # B waits on F through A
        self.assertEqual(NC.acceptance_cycles(plan, [("F", "C")]), [])              # C does not wait on F
        self.assertEqual(NC.acceptance_cycles(plan, [("A", "F")]), [])              # the follow-up waiting on its owner is fine

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

        # every repository scenario was compared and recorded PASS (a header-only finding sits beside its own
        # FAIL record); an effect stands on that measured record, never on the absence of a finding
        td = tempfile.mkdtemp(prefix="sl-effects-")
        root = Path(td)
        sdir = root / "verification" / "parity" / "scenarios"
        sdir.mkdir(parents=True)

        def record(sid, verdict):
            (sdir / ("%s.json" % sid.replace(":", "_"))).write_text(json.dumps(
                {"schema": "rhoai3.scenario-parity/v1", "scenario": sid, "verdict": verdict}))
        for s in REPO_SCENARIOS:
            record(s, "PASS")

        def effects(*items, scenarios=REPO_SCENARIOS):
            return RC.measure(root, [req], worklist={"items": list(items), "measure": {"known": True}},
                              scenarios=scenarios)[EFFECTS]["status"]
        cors = parity_item("i1", "sc:cors-actual-0a", CO_T.EP_LIST, cause="cors-response")
        ctype = parity_item("i2", "sc:read-orders", CO_T.EP_LIST, cause="content-type-parameter")
        self.assertEqual(effects(), RC.PASS)
        self.assertEqual(effects(cors, ctype), RC.PASS)
        self.assertEqual(effects(parity_item("i3", "sc:read-orders", CO_T.EP_LIST)), RC.FAIL)          # a body difference
        self.assertEqual(effects(parity_item("i4", "sc:cors-actual-0a", CO_T.EP_LIST, cause="cors-response",
                                             server_error=True)), RC.FAIL)                                 # it threw
        self.assertEqual(effects(dict(parity_item("i5", "", CO_T.EP_LIST), scenarios=["sc:create-orders"])), RC.FAIL)
        # no finding open but the comparison did not establish the effect: unknown, never a discharged PASS
        record("sc:read-orders", "INCONCLUSIVE")
        self.assertEqual(effects(), RC.UNKNOWN)
        (sdir / "sc_read-orders.json").unlink()
        self.assertEqual(effects(), RC.UNKNOWN)                                                          # no record
        record("sc:read-orders", "PASS")
        self.assertEqual(effects(scenarios=[s for s in REPO_SCENARIOS if s != "sc:read-orders"]), RC.UNKNOWN)
        self.assertEqual(effects(), RC.PASS)
        # the plain comparison of the header-only scenario is still its own FAIL
        plain = dict(req, acceptance=["parity:sc:cors-actual-0a"])
        self.assertEqual(RC.measure(root, [plain], worklist={"items": [cors], "measure": {"known": True}},
                                    scenarios=REPO_SCENARIOS)["parity:sc:cors-actual-0a"]["status"], RC.FAIL)

    def _accept_order(self, d, tid, run, iss, *, items=(), clusters=(), started=True, attempt="1", record_fail=(),
                      scenarios=REPO_SCENARIOS):
        """The Order card's candidate committed and judged, the verification having measured it (started or not)."""
        r = d.r
        r.edit(iss["allowed_paths"][0], "// Order accepted %s\n" % attempt)
        NC.check_write(r.board, task_id=tid, run_id=run, rel_paths=list(iss["allowed_paths"]))
        NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="ACCEPTED", candidate=r.tree(), attempt=attempt)
        NB.git(r.root, "add", "-A")
        NB.git(r.root, "commit", "-qm", "order %s" % attempt)
        d.measured(started=started, items=items, clusters=clusters, record_fail=record_fail, scenarios=scenarios)
        return NC.accept_commit(r.root, r.board, task_id=tid, run_id=run, attempt=attempt,
                                commit=NB.git(r.root, "rev-parse", "HEAD"),
                                measurement={"classes": ["build", "compile", "tests", "runtime", "parity"],
                                             "scenarios": list(scenarios)})

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
            # the accepted candidate starts; a read the ACCEPTED Item card relied on regresses there (record-only,
            # no executable card judges it now): the owner's follow-up
            d.complete(B_ITEM)
            acc = self._accept_order(d, tid, run, iss, record_fail=("sc:read-items-1",))
            fid = "followup:%s:m3g1" % d.owner
            self.assertEqual(acc["schedule_routed"], [fid])
            self.assertEqual({m["check"]: m["route"] for m in acc["schedule"]}[EFFECTS], "owner")
            plan = r.plan()
            self.assertEqual(NC._node(plan, fid)["budget"], owner_budget)
            ftid = r.tid(fid)
            self.assertNotIn(ftid, r.native.task(tid)["parents"])            # the accepted card is not held
            for t in (r.tid(B_STATUS), r.tid("assess:m4:g1")):
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

    def test_a_fresh_measurement_on_the_same_tree_is_its_own_record(self):
        """H13-R3 (architect reproduction): pending at issue, then startup and parity evidence arrive on the
        UNCHANGED product tree. The fresh result is recorded (not lost under the pending record's key) and
        schedule_status reports it; an exact replay records nothing new."""
        for later, want in ((dict(started=True), "pass"),
                            (dict(started=True, record_fail=("sc:read-orders",)), "fail")):
            d = Desk()
            r = d.r
            try:
                d.measured(started=False)
                tid, run, iss = r.issue(B_ORDER)
                plan = r.plan()
                key = "%s|%s" % (d.owner, EFFECTS)
                self.assertEqual(NC.schedule_status(r.board, r.run_id, plan)[key]["state"], "pending")
                d.measured(**later)
                out = NC.schedule_at_issue(r.root, r.board, task_id=tid, run_id=run, run=r.run_id, plan=plan,
                                           holder=B_ORDER, worklist=r.worklist, tree=r.tree(), accepted="accept-commit:probe")
                self.assertEqual(next(m for m in out["rows"] if m["check"] == EFFECTS)["state"], want)
                self.assertEqual(NC.schedule_status(r.board, r.run_id, r.plan())[key]["state"], want)
                n = len(r.board.records(tid, "schedule-measure"))
                self.assertEqual(n, 2)
                NC.schedule_at_issue(r.root, r.board, task_id=tid, run_id=run, run=r.run_id, plan=r.plan(),
                                     holder=B_ORDER, worklist=r.worklist, tree=r.tree(), accepted="accept-commit:probe")
                self.assertEqual(len(r.board.records(tid, "schedule-measure")), n)          # exact replay: same key
            finally:
                d.close()

    def test_an_acceptance_is_not_usable_for_handoff_until_its_schedule_is_settled(self):
        """Decision 2: a crash between the acceptance record and its scheduled measurement leaves a positive
        acceptance whose scheduled checks are neither recorded nor routed. The handoff gate refuses it; the
        recovery exit (evaluate_recovered, run by advance) settles it; then the gate allows."""
        d = Desk()
        r = d.r
        try:
            own = [parity_item("parity:read", "sc:read-orders", CO_T.EP_LIST)]
            d.measured(items=own, clusters=[cluster("c:read", "parity:read")])
            tid, run, iss = r.issue(B_ORDER)
            real = NC._schedule_after_acceptance
            NC._schedule_after_acceptance = lambda *a, **k: None                  # the crash: nothing scheduled
            node = NC._node(r.plan(), B_ORDER)
            every = sorted(set(REPO_SCENARIOS) | {c[len("parity:"):] for c in node["acceptance"]["requirement_checks"]
                                                  if c.startswith("parity:sc:")})
            try:
                acc = self._accept_order(d, tid, run, iss, scenarios=every)
            finally:
                NC._schedule_after_acceptance = real
            self.assertTrue(acc["outcome_accepted"], acc)
            plan = r.plan()
            node = NC._node(plan, B_ORDER)
            ok, why = NC.outcome_acceptance(r.root, r.board, tid, plan, node)
            self.assertFalse(ok)
            self.assertIn("not recorded and routed yet", why)
            out = NC.evaluate_recovered(r.root, r.board, task_id=tid, run_id=run, measurement={})
            self.assertTrue(out and out.get("schedule_recovered"), out)
            ok, why = NC.outcome_acceptance(r.root, r.board, tid, plan, node)
            self.assertTrue(ok, why)
            self.assertIsNone(NC.evaluate_recovered(r.root, r.board, task_id=tid, run_id=run, measurement={}))
        finally:
            d.close()

    def test_routed_debt_survives_to_m4_fail_and_unknown_refuse_all_pass_clears(self):
        """Condition 8 (architect, 2026-10-01): a regression routed through H-13 keeps its debt to M4. The
        holder repairs its own finding and passes the REAL acceptance and review gates (its own contract),
        while the routed witness (sc:read-items-1, the accepted Item card's read) still fails: M4's deferred
        gate refuses on the current candidate with the witness FAIL, and separately with it UNKNOWN (not
        compared); a fresh all-PASS measurement clears that gate."""
        d = Desk()
        r = d.r
        try:
            d.complete(B_ITEM)
            body = dict(parity_item("parity:m4-body", "", CO_T.EP_LIST), scenarios=["sc:cors-actual-0a"])
            d.measured(items=[body], clusters=[cluster("c:m4-body", body["id"])], record_fail=("sc:read-items-1",))
            tid, run, iss = r.issue(B_ORDER)                                   # the holder repairs its share first
            fid = "followup:%s:m3g1" % d.owner
            plan = r.plan()
            self.assertIn(B_ORDER, NC._node(plan, fid)["parents"])
            node = NC._node(plan, B_ORDER)
            every = sorted(set(REPO_SCENARIOS) | {c[len("parity:"):] for c in node["acceptance"]["requirement_checks"]
                                                  if c.startswith("parity:sc:")})
            acc = self._accept_order(d, tid, run, iss, record_fail=("sc:read-items-1",), scenarios=every)
            self.assertTrue(acc["outcome_accepted"], acc)                      # its own contract holds
            got = {m["check"]: m for m in acc["schedule"]}[EFFECTS]
            self.assertEqual(got["state"], "fail")                             # the debt is not called PASS
            r.review_and_complete(tid, run)                                    # the real handoff + review gates
            self.assertEqual(r.native.task(tid)["status"], "done")
            m4 = NC._node(r.plan(), "assess:m4:g1")
            k = "%s|%s" % (d.owner, EFFECTS)
            self.assertIn(k, {"%s|%s" % (x["outcome"], x["check"]) for x in m4["acceptance"]["deferred_requirement_checks"]})

            def m4_effects(scen):
                return NC.deferred_checks_status(r.root, r.plan(), m4, scen, r.tree()).get(k, {}).get("status")
            # FAIL: the witness still fails on the current candidate
            d.measured(record_fail=("sc:read-items-1",), scenarios=every)
            self.assertEqual(m4_effects(every), "fail")
            # UNKNOWN: the witness was not compared on the current candidate
            partial = [s for s in every if s != "sc:read-items-1"]
            d.measured(scenarios=partial)
            self.assertEqual(m4_effects(partial), "unknown")
            # all PASS: the follow-up's repair holds, a fresh comparison of every scenario clears the row
            d.measured(scenarios=every)
            self.assertEqual(m4_effects(every), "pass")
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
