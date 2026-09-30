#!/usr/bin/env python3
"""outcome-board/v2 M3 recovery (the v20 defects, 2026-09-27): readable and
unique ``M3 <ACTION>`` titles, runtime checks deferred to M4 and enforced
there, named not-accepted reasons, the per-unit verdict idempotency of
advance.py, park / restore-parked, and the repeated-refusal stop in
native_gate.py and the K2 hook.

SYNTHETIC evidence on the native_board.test.py harness (FakeNative board,
real git, the real K2 hook script). Evidence for v20:
tmp/v20-native-card-validation/v20-validation.md.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/native_m3_recovery.test.py
"""
from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("native_board_test", HERE / "native_board.test.py")
NB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(NB)

NC, OG, NP, Refusal, VERDICT = NB.NC, NB.OG, NB.NP, NB.Refusal, NB.VERDICT
Run, git, status, mirror_layout = NB.Run, NB.git, NB.status, NB.mirror_layout
KERNEL, SCRIPTS = NB.KERNEL, NB.LIB.parent / "skills" / "migration" / "fix-until-green" / "scripts"
DASH = "—"


def clean(r: Run) -> str:
    """Product changes against HEAD (the harness mirror under .hermes/ is not product)."""
    return git(r.root, "status", "--porcelain", "--", ".", ":!.hermes")


def with_check(run: Run, oid: str, check: str) -> None:
    """Give an outcome of the unpublished plan a requirement check (the plan
    semantics attach them from source requirements; the shop has none)."""
    plan = json.loads(run.plan_file.read_text())
    for n in plan["nodes"]:
        if n["outcome_id"] == oid:
            n["acceptance"] = dict(n.get("acceptance") or {}, requirement_checks=[check])
            n["requirements"] = ["req:%s" % check]
    plan.pop("digest", None)
    plan["digest"] = OG.plan_digest(plan)
    run.plan_file.write_text(json.dumps(plan))


class FakeChecks:
    """requirement_measurement stand-in: a check passes once it is switched on."""

    def __init__(self):
        self.passing: set[str] = set()
        self.orig = NC.requirement_measurement

    def __call__(self, root, plan, node, worklist, scenarios, tree):
        return {c: ({"status": "pass", "detail": "ok"} if c in self.passing else
                    {"status": "fail", "detail": "%s needs the running application" % c})
                for c in ((node.get("acceptance") or {}).get("requirement_checks") or [])}

    def __enter__(self):
        NC.requirement_measurement = self
        return self

    def __exit__(self, *a):
        NC.requirement_measurement = self.orig


# ===========================================================================
class Titles(unittest.TestCase):

    def test_m3_codes_unique_and_stable(self):
        plan = NB.derive()
        out = NC.native_plan(plan)
        titles = {n["outcome_id"]: n["title"] for n in out["nodes"]}
        self.assertEqual(titles["build:rk:pom"], "M3 BUILD %s pom.xml" % DASH)
        self.assertEqual(titles["config:rk:cfg"], "M3 CONFIGURE %s application.properties" % DASH)
        self.assertEqual(titles["source:rk:item"], "M3 COMPILE %s ItemController.java" % DASH)
        self.assertEqual(titles["behavior:http:com.acme.shop.web.OrderController"],
                         "M3 BEHAVIOR %s com.acme.shop.web.OrderController" % DASH)
        self.assertEqual(titles["runtime:package:rk:package:spel"], "M3 RUNTIME %s package and start" % DASH)
        self.assertEqual((titles["assess:m4:g1"], titles["deliver:prepare:c1"]), ("M4 ASSESS", "M5 PREFLIGHT"))
        for n in out["nodes"]:
            if n["role"] == "repair":
                self.assertTrue(n["title"].startswith("M3 "), n["title"])
        self.assertEqual(len(set(titles.values())), len(titles))
        # v20: two outcomes titled "Configuration: application.properties"
        twin = copy.deepcopy(plan)
        cfg = next(n for n in twin["nodes"] if n["outcome_id"] == "config:rk:cfg")
        twin["nodes"].append(dict(copy.deepcopy(cfg), outcome_id="config:rk:cfg2"))
        got = {n["outcome_id"]: n["title"] for n in NC.native_titles(twin)["nodes"]}
        base = "M3 CONFIGURE %s application.properties" % DASH
        self.assertEqual((got["config:rk:cfg"], got["config:rk:cfg2"]), (base + " (part 1 of 2)", base + " (part 2 of 2)"))
        # published titles are never rewritten; a later twin continues the numbering
        self.assertEqual(NC.native_titles(out), out)
        later = copy.deepcopy(out)
        later["nodes"].append(dict(copy.deepcopy(cfg), outcome_id="config:rk:cfg3"))
        got = {n["outcome_id"]: n["title"] for n in NC.native_titles(later)["nodes"]}
        self.assertEqual((got["config:rk:cfg"], got["config:rk:cfg3"]), (base, base + " (part 2 of 2)"))

    def test_published_cards_carry_the_titles(self):
        r = Run()
        try:
            got = sorted(t["title"] for t in r.native.tasks.values() if str(t.get("title", "")).startswith("M3 "))
            self.assertEqual(len(got), 8)
            self.assertEqual(len(set(got)), 8)
            self.assertEqual(r.native.task(r.tid("build:rk:pom"))["title"], "M3 BUILD %s pom.xml" % DASH)
        finally:
            r.close()


# ===========================================================================
class DeferredChecks(unittest.TestCase):

    def test_placement(self):
        plan = NB.derive()
        for n in plan["nodes"]:
            if n["outcome_id"] == "build:rk:pom":
                n["acceptance"] = dict(n["acceptance"], requirement_checks=["parity:request-body", "source:keeps-api"])
                n["requirements"] = ["req:1"]
            if n["outcome_id"] == "behavior:http:com.acme.shop.web.ItemController":
                n["acceptance"] = dict(n["acceptance"], requirement_checks=["parity:item-get"])
        out = NC.native_plan(plan)
        node = {n["outcome_id"]: n for n in out["nodes"]}
        self.assertEqual(node["build:rk:pom"]["acceptance"]["requirement_checks"], ["source:keeps-api"])
        self.assertEqual(node["build:rk:pom"]["deferred_checks"], ["parity:request-body"])
        self.assertEqual(node["behavior:http:com.acme.shop.web.ItemController"]["acceptance"]["requirement_checks"],
                         ["parity:item-get"])                                # a behavior outcome measures it itself
        # v24: each early source outcome's full test suite is owned by M4, naming the outcome and its requirements
        sources = sorted(n["outcome_id"] for n in out["nodes"] if n.get("class") == "source" and n.get("role") == "repair")
        self.assertEqual(node["assess:m4:g1"]["acceptance"]["deferred_requirement_checks"],
                         sorted([{"outcome": "build:rk:pom", "requirements": ["req:1"], "check": "parity:request-body"}]
                                + [{"outcome": o, "requirements": sorted(node[o].get("requirements") or []), "check": "measure:tests"}
                                   for o in sources], key=lambda d: (d["outcome"], d["check"])))
        for o in sources:
            self.assertNotIn("measure:tests", node[o]["acceptance"]["checks"])
            self.assertIn("measure:tests", node[o]["deferred_checks"])
        self.assertEqual(NC.native_revision(out), out)                       # idempotent

    def test_deferred_check_gates_m4_and_becomes_a_followup(self):
        with FakeChecks() as fc:
            r = Run(publish=False)
            try:
                with_check(r, "build:rk:pom", "parity:request-body")
                r.out = r.publish()
                r.release()
                r.drop("inc:unlocatable:jndi")
                r.accept_all_repairs()                                        # the build card is accepted early
                self.assertEqual(status(r, r.tid("build:rk:pom")), "done")
                m4 = r.tid("assess:m4:g1")
                tid, run, out = r.assess("PROVISIONAL_ACCEPT")
                self.assertTrue(out["accepted"])
                with self.assertRaises(Refusal) as cm:
                    NC.check_terminator(r.root, r.board, task_id=m4, run_id=run, kind="request_review",
                                        profile="implementer", audit_green=lambda: True)
                self.assertEqual(cm.exception.code, "ASSESS_DEFERRED_CHECKS")
                self.assertIn("build:rk:pom|parity:request-body", cm.exception.detail)
                rep = NC.m4_repair(r.root, r.board, task_id=m4, run_id=run)
                self.assertEqual(len(rep["added"]), 1)
                fid = rep["added"][0]
                fnode = NC._node(r.plan(), fid)
                self.assertEqual((fnode["class"], fnode["acceptance"]["requirement_checks"]),
                                 ("behavior", ["parity:request-body"]))
                self.assertTrue(fnode["title"].startswith("M3 FOLLOW-UP %s " % DASH), fnode["title"])
                self.assertIn(r.tid(fid), r.native.task(m4)["parents"])
                r.native.block_dependency(m4)
                ftid, frun, fiss = r.issue(fid)
                acc = r.accept_on_run(ftid, frun, fiss, classes=("build", "compile", "tests", "runtime", "parity"), drop=False)
                self.assertFalse(acc["outcome_accepted"])                     # the check still fails, and says why
                self.assertTrue(any("parity:request-body is fail" in x for x in acc["not_accepted_because"]),
                                acc["not_accepted_because"])
                fc.passing.add("parity:request-body")
                iss2 = NC.issue(r.root, r.board, task_id=ftid, run_id=frun)
                acc = r.accept_on_run(ftid, frun, iss2, classes=("build", "compile", "tests", "runtime", "parity"),
                                      attempt="2", drop=False)
                self.assertTrue(acc["outcome_accepted"], acc)
                r.review_and_complete(ftid, frun)
                self.assertEqual(status(r, m4), "ready")
                tid, run2, out = r.assess("PROVISIONAL_ACCEPT")
                r.review_and_complete(m4, run2)
                self.assertEqual(status(r, r.tid("deliver:prepare:c1")), "ready")
            finally:
                r.close()


# ===========================================================================
class Satisfied(unittest.TestCase):
    """v21 t_23612034: a package unit's commit discharged every obligation a
    type-level outcome owned; its card got an empty issue and no road."""

    def setUp(self):
        self.r = Run()
        self.r.release()

    def tearDown(self):
        self.r.close()

    def subsume(self, oid):
        """Another outcome's fix removes this outcome's obligations (no edit of its own)."""
        self.r.drop(*NC.owned(self.r.plan(), NC._node(self.r.plan(), oid)))

    def test_discharged_elsewhere_is_accepted_and_reviewable(self):
        r = self.r
        r.accept("build:rk:pom")                                          # an acceptance measured on this tree
        self.subsume("config:rk:cfg")
        tid, run, iss = r.issue("config:rk:cfg")
        self.assertEqual((iss["cluster"], iss["allowed_paths"]), ("", []))
        self.assertTrue(iss["next"].startswith("SATISFIED: config:rk:cfg"), iss["next"])
        self.assertEqual(iss["satisfied"]["by"]["outcome"], "build:rk:pom")
        # v24 WP4 (v23 t_dddc1862): the sibling acceptance is a WITNESS that measured this tree, never the cause
        self.assertEqual(iss["satisfied"]["by"]["relation"], "witness")
        self.assertIn("already satisfied on this measured tree", iss["next"])
        self.assertIn("not the change that satisfied it", iss["next"])
        self.assertNotIn("discharged by", iss["next"])
        self.assertEqual(NC.outcome_acceptance(r.root, r.board, tid, r.plan(), NC._node(r.plan(), "config:rk:cfg"))[0], True)
        again = NC.issue(r.root, r.board, task_id=tid, run_id=run)       # a replayed issue records nothing twice
        self.assertTrue(again["next"].startswith("SATISFIED"))
        self.assertEqual(len([x for x in r.board.records(tid, "accept-commit") if x.get("satisfied_by")]), 1)
        rrun = r.review_and_complete(tid, run)                           # request_review and the reviewer's completion
        self.assertEqual(status(r, tid), "done")
        # the M3 audit grades the harness record for such a card (no loop step exists)
        spec = importlib.util.spec_from_file_location(
            "m3_audit", NB.LIB.parent / "skills" / "paved-road" / "paved-road-m3" / "scripts" / "assert-paved-road-audit.py")
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        orig = NC.board_for
        NC.board_for = lambda root, native=None: NC.Board(r.native, author="reviewer")
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = audit._satisfied_audit(tid, r.root, r.tmp / "not-an-official.log", r.tmp / "steps.json")
            self.assertEqual(rc, 0, out.getvalue())
            self.assertIn("artifact=satisfied", out.getvalue())
            r.edit("pom.xml", "<project>drift</project>\n")               # the tree moves: the record no longer holds
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(audit._satisfied_audit(tid, r.root, r.tmp / "x.log", r.tmp / "steps.json"), 1)
            other = r.tid("source:rk:item")                               # a loop card: the log audit decides
            self.assertIsNone(audit._satisfied_audit(other, r.root, r.tmp / "x.log", r.tmp / "steps.json"))
        finally:
            NC.board_for = orig

    def test_nothing_measured_on_this_tree_is_not_satisfied(self):
        r = self.r
        self.subsume("config:rk:cfg")                                      # no acceptance was ever measured on this tree
        tid, run, iss = r.issue("config:rk:cfg")
        self.assertIsNone(iss["satisfied"])
        self.assertTrue(iss["next"].startswith("NOTHING ISSUED: config:rk:cfg"), iss["next"])
        self.assertIn("nothing measured it", iss["next"])
        with self.assertRaises(Refusal) as cm:
            NC.check_terminator(r.root, r.board, task_id=tid, run_id=run, kind="request_review", profile="implementer",
                                audit_green=lambda: False)
        self.assertEqual(cm.exception.code, "OUTCOME_NOT_ACCEPTED")

    def test_an_outcome_with_open_work_is_issued_as_before(self):
        tid, run, iss = self.r.issue("build:rk:pom")
        self.assertEqual((iss["cluster"], iss["next"], iss["satisfied"]), ("c:pom", "", None))


# ===========================================================================
class UnresolvableYet(unittest.TestCase):
    """v21 t_0bc6319b: the fragment checks could only be UNKNOWN because
    SpringDataVisitRepositoryImpl could not resolve DataAccessException, owned
    by the dao unit that waits on this card -- a deadlock in the plan order."""

    def run_case(self, status, detail):
        orig = NC.requirement_measurement
        NC.requirement_measurement = lambda root, plan, node, wl, sc, tree: (
            {c: {"status": status, "detail": detail} for c in (node.get("acceptance") or {}).get("requirement_checks") or []})
        r = Run(publish=False)
        try:
            with_check(r, "build:rk:pom", "unit:fragment-implementation")
            r.out = r.publish()
            r.release()
            tid, run, iss = r.issue("build:rk:pom")
            acc = r.accept_on_run(tid, run, iss)
            m4 = r.tid("assess:m4:g1")
            return acc, [x for x in r.board.records(m4, "defer-check")], r, m4
        finally:
            NC.requirement_measurement = orig
            self.addCleanup(r.close)

    def test_a_check_unmeasurable_because_others_break_the_file_is_judged_at_m4(self):
        acc, deferred, r, m4 = self.run_case("unknown", "the compiler could not fully resolve src/X.java")
        self.assertTrue(acc["outcome_accepted"], acc)
        self.assertEqual([(d["outcome"], d["check"]) for d in deferred], [("build:rk:pom", "unit:fragment-implementation")])
        rows = NC.unmet_deferred(r.root, r.board, r.plan(), NC._node(r.plan(), "assess:m4:g1"), m4)
        self.assertTrue(any("build:rk:pom|unit:fragment-implementation" in x for x in rows), rows)   # M4 still judges it

    def test_an_unaccepted_acceptance_is_judged_again_on_the_unchanged_tree(self):
        # the Operator's correction lands after the acceptance was recorded: the next advance
        # re-judges it under the current rules, with no new commit and no attempt spent
        state = {"detail": "the destination model is unavailable"}
        orig = NC.requirement_measurement
        NC.requirement_measurement = lambda root, plan, node, wl, sc, tree: (
            {c: {"status": "unknown", "detail": state["detail"]} for c in (node.get("acceptance") or {}).get("requirement_checks") or []})
        r = Run(publish=False)
        self.addCleanup(r.close)
        try:
            with_check(r, "build:rk:pom", "unit:fragment-implementation")
            r.out = r.publish()
            r.release()
            tid, run, iss = r.issue("build:rk:pom")
            acc = r.accept_on_run(tid, run, iss)
            self.assertFalse(acc["outcome_accepted"])
            m = {"classes": ["build", "compile", "tests"], "scenarios": []}
            again = NC.evaluate_recovered(r.root, r.board, task_id=tid, run_id=run, measurement=m)
            self.assertFalse(again["outcome_accepted"])
            self.assertTrue(any("destination model is unavailable" in x for x in again["not_accepted_because"]), again)
            state["detail"] = "the compiler could not fully resolve src/X.java"      # decidable only at M4 now
            again = NC.evaluate_recovered(r.root, r.board, task_id=tid, run_id=run, measurement=m)
            self.assertTrue(again["outcome_accepted"], again)
            self.assertEqual(NC.outcome_acceptance(r.root, r.board, tid, r.plan(), NC._node(r.plan(), "build:rk:pom"))[0], True)
            r.edit("pom.xml", "<project>moved</project>\n")                           # a moved tree is never re-judged
            self.assertIsNone(NC.evaluate_recovered(r.root, r.board, task_id=tid, run_id=run, measurement=m))
        finally:
            NC.requirement_measurement = orig

    def test_a_failing_check_still_blocks(self):
        acc, deferred, _r, _m4 = self.run_case("fail", "@Typed names the wrong type")
        self.assertFalse(acc["outcome_accepted"])
        self.assertEqual(deferred, [])

    def test_another_unknown_still_blocks(self):
        acc, deferred, _r, _m4 = self.run_case("unknown", "the destination model is unavailable")
        self.assertFalse(acc["outcome_accepted"])
        self.assertEqual(deferred, [])


# ===========================================================================
class NotAccepted(unittest.TestCase):

    def test_reasons_are_named(self):
        r = Run()
        try:
            r.release()
            tid, run, iss = r.issue("build:rk:pom")
            acc = r.accept_on_run(tid, run, iss, drop=False, classes=("compile",))
            self.assertFalse(acc["outcome_accepted"])
            why = acc["not_accepted_because"]
            self.assertTrue(any(x.startswith("open obligation ") for x in why), why)
            self.assertIn("not measured: build", why)
        finally:
            r.close()


# ===========================================================================
class UnitIdempotency(unittest.TestCase):
    """advance.py answers "ACCEPTED already" for the issued UNIT only."""

    def test_a_planned_unit_is_judged_by_its_requirements_not_the_tuple(self):
        # v21 t_0bc6319b run 39: the owed fragment implementations compiled cleanly and were refused
        # "measure [0, 179, 0] did not decrease" three times -- the 179 were outside the unit's write set
        from planner.worklist import PLANNED_UNIT_GATE, progress
        m = lambda t: {"known": True, "tuple": t}
        ok, why = progress(m([0, 179, 0]), m([0, 179, 0]), set(), set(), gate=PLANNED_UNIT_GATE)
        self.assertTrue(ok, why)
        self.assertIn("requirement checks decide", why)
        ok, why = progress(m([0, 179, 0]), m([0, 180, 0]), set(), set(), gate=PLANNED_UNIT_GATE)
        self.assertFalse(ok)
        self.assertIn("may not make the measure worse", why)
        ok, why = progress(m([0, 179, 0]), m([0, 179, 0]), set(), {"inc:new|a#1"}, gate=PLANNED_UNIT_GATE)
        self.assertFalse(ok)                                               # a new mandatory obligation still vetoes
        ok, why = progress(m([0, 179, 0]), m([0, 179, 0]), set(), set())   # a finding cluster: unchanged
        self.assertFalse(ok)
        # the issued projection of a planned unit carries that gate
        sys.path.insert(0, str(KERNEL))
        import native_gate as G
        from planner.paths import LOOP_ISSUED
        r = Run()
        mirror_layout(r.root)
        try:
            r.release()
            tid, run, iss = r.issue("build:rk:pom")
            planned = dict(iss, cluster="planned:build:rk:pom:1", allowed_paths=["pom.xml"],
                           planned_unit={"kind": "build", "paths": ["pom.xml"], "refusal": ""})
            G.write_issued_projection(r.root, planned)
            self.assertEqual(json.loads((r.root / LOOP_ISSUED).read_text()).get("gate"), PLANNED_UNIT_GATE)
            G.write_issued_projection(r.root, iss)                         # a finding cluster keeps its own gate
            self.assertNotEqual(json.loads((r.root / LOOP_ISSUED).read_text()).get("gate"), PLANNED_UNIT_GATE)
        finally:
            r.close()

    def test_the_operator_voids_rejections_a_harness_defect_caused(self):
        r = Run()
        try:
            r.release()
            tid, run, iss = r.issue("build:rk:pom")
            node = NC._node(r.plan(), "build:rk:pom")
            for a in ("1", "2"):
                NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="REVERTED", candidate=r.tree(), attempt=a,
                                  reason="measure did not decrease")
            self.assertEqual(NC.budget_state(r.board, r.run_id, r.plan(), node)["spent"], 2)
            keys = [x["key"] for x in r.board.records(tid, "reject")]
            with self.assertRaises(Refusal) as cm:
                NC.void_rejects(r.board, task_id=tid, keys=keys[:1], reason="gate defect", by="implementer")
            self.assertEqual(cm.exception.code, "VOID_NOT_OPERATOR")
            with self.assertRaises(Refusal) as cm:
                NC.void_rejects(r.board, task_id=tid, keys=["reject:nope"], reason="gate defect", by="operator")
            self.assertEqual(cm.exception.code, "VOID_UNKNOWN_REJECT")
            self.assertEqual(NC.void_rejects(r.board, task_id=tid, keys=keys[:1], reason="gate defect", by="operator"), keys[:1])
            self.assertEqual(NC.void_rejects(r.board, task_id=tid, keys=keys[:1], reason="gate defect", by="operator"), [])
            self.assertEqual(NC.budget_state(r.board, r.run_id, r.plan(), node)["spent"], 1)   # the other still counts
            self.assertEqual(len(r.board.records(tid, "reject")), 2)                          # nothing is deleted
        finally:
            r.close()

    def test_a_recorded_rejection_reissues_the_same_card(self):
        # v21 t_0bc6319b run 38: advance.py on a clean tree answered "REVERTED already -- call
        # kanban_complete" (serial wording); K2 refused complete and review; the card blocked
        sys.path.insert(0, str(SCRIPTS))
        import advance as A
        import _outcome_bridge as B
        r = Run()
        mirror_layout(r.root)
        saved = {k: os.environ.get(k) for k in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID", "HERMES_KANBAN_DB")}
        orig = NC.board_for
        try:
            r.release()
            tid, run, iss = r.issue("build:rk:pom")
            r.native.sync()
            os.environ.update(HERMES_KANBAN_TASK=tid, HERMES_KANBAN_RUN_ID=str(run), HERMES_KANBAN_DB=r.native.db_path)
            NC.board_for = lambda root, native=None: NC.Board(r.native, author="implementer")
            steps = {"steps": [], "rejected": [{"card": tid, "cluster": "c:pom", "reason": "measure did not decrease"}]}
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = A._recorded_verdict(r.root, steps, tid, "c" * 64, mint=False, hermes="hermes")
            self.assertEqual(rc, 0, err.getvalue())
            self.assertIn("this outcome stays open on this card", err.getvalue())
            self.assertNotIn("kanban_complete", err.getvalue())
            self.assertIn("CONTINUE THIS CARD", out.getvalue())
            self.assertEqual([x["kind"] for x in r.board.records(tid)].count("issue"), 2)   # re-issued on the same card
            # v21 t_0bc6319b runs 44-47: a later acceptance supersedes the row -- no replay, judged normally
            r.board.record(tid, "reject", "reject:%d:x" % run, run=run)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(A._recorded_verdict(r.root, steps, tid, "c" * 64, mint=False, hermes="hermes"), 0)
            r.board.record(tid, "accept-commit", "accept-commit:%d:y" % run, run=run, outcome_accepted=False)
            self.assertIs(B.rejection_is_latest(r.root), False)
            self.assertIsNone(A._recorded_verdict(r.root, steps, tid, "c" * 64, mint=False, hermes="hermes"))
            r.board.record(tid, "reject", "reject:%d:z" % run, run=run)
            self.assertIs(B.rejection_is_latest(r.root), True)
            NC.void_rejects(r.board, task_id=tid, keys=["reject:%d:z" % run], reason="gate defect", by="operator")
            self.assertIs(B.rejection_is_latest(r.root), False)                           # a voided rejection is no verdict
        finally:
            NC.board_for = orig
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            r.close()

    def test_second_unit_on_the_same_card_is_judged(self):
        sys.path.insert(0, str(SCRIPTS))
        import advance as A
        from _loop_common import LOOP_ISSUED
        r = Run(publish=False)
        try:
            steps = {"steps": [{"card": "t_1", "cluster": "c:pom", "idempotency_key": "outcome:v2:1:build:c:pom:issue1:r1",
                                "verdict": "accepted", "commit": "a" * 40, "candidate_sha256": "b" * 64}]}
            p = r.root / LOOP_ISSUED
            p.parent.mkdir(parents=True, exist_ok=True)
            out = io.StringIO()
            p.write_text(json.dumps({"card_id": "t_1", "idempotency_key": "outcome:v2:1:build:c:pom:issue2:r1"}))
            with contextlib.redirect_stdout(out):
                self.assertIsNone(A._recorded_verdict(r.root, steps, "t_1", "c" * 64, mint=False, hermes="hermes"))
            p.write_text(json.dumps({"card_id": "t_1", "idempotency_key": "outcome:v2:1:build:c:pom:issue1:r1"}))
            with contextlib.redirect_stdout(out):
                self.assertEqual(A._recorded_verdict(r.root, steps, "t_1", "c" * 64, mint=False, hermes="hermes"), 0)
            self.assertIn("ACCEPTED already", out.getvalue())
            legacy = {"steps": [dict(steps["steps"][0], idempotency_key=None)]}   # a keyless row matches by card
            with contextlib.redirect_stdout(out):
                self.assertEqual(A._recorded_verdict(r.root, legacy, "t_1", "c" * 64, mint=False, hermes="hermes"), 0)
        finally:
            r.close()


# ===========================================================================
class Park(unittest.TestCase):

    def setUp(self):
        self.r = Run()
        self.r.release()

    def tearDown(self):
        self.r.close()

    def test_block_parks_then_restores_on_resume(self):
        r = self.r
        tid, run, iss = r.issue("build:rk:pom")
        r.edit("pom.xml", "<project>verified but unjudged</project>\n")
        with self.assertRaises(Refusal) as cm:
            NC.check_terminator(r.root, r.board, task_id=tid, run_id=run, kind="block", profile="implementer",
                                audit_green=lambda: False)
        self.assertEqual(cm.exception.code, "BLOCK_LEAVES_CANDIDATE")
        self.assertIn("native_gate.py --root . park", cm.exception.detail)
        got = NC.park(r.root, r.board, task_id=tid, run_id=run)
        self.assertEqual(got["parked"], ["pom.xml"])
        self.assertEqual(clean(r), "")           # the next card starts from HEAD
        self.assertIsNotNone(r.board.attachment(tid, got["attachment"]))
        self.assertEqual(NC.check_terminator(r.root, r.board, task_id=tid, run_id=run, kind="block", profile="implementer",
                                             audit_green=lambda: False)["code"], "BLOCK_ALLOWED")
        # another card issues cleanly on the restored tree (v20: ISSUE_BASELINE_DRIFT)
        r.native.end_run(tid, "blocked", "needs_input")
        otid, orun, oiss = r.issue("config:rk:cfg")
        self.assertEqual(oiss["outcome_id"], "config:rk:cfg")
        r.native.end_run(otid, "ready", "crashed")
        # the parked card resumes: its issue names the parked candidate, restore puts it back
        r.native.tasks[tid]["status"] = "ready"                              # the Operator unblocks it
        run2, lock2 = r.native.claim(tid)
        iss2 = NC.issue(r.root, r.board, task_id=tid, run_id=run2, claim_lock=lock2)
        self.assertTrue(iss2["parked_candidate"])
        back = NC.restore_parked(r.root, r.board, task_id=tid, run_id=run2)
        self.assertEqual(back["restored"], ["pom.xml"])
        self.assertEqual((r.root / "pom.xml").read_text(), "<project>verified but unjudged</project>\n")
        self.assertIsNone(NC.parked_pending(r.board, tid))
        with self.assertRaises(Refusal) as cm:
            NC.restore_parked(r.root, r.board, task_id=tid, run_id=run2)
        self.assertEqual(cm.exception.code, "RESTORE_NO_PARK")

    def test_block_on_a_clean_tree_is_allowed(self):
        r = self.r
        tid, run, iss = r.issue("build:rk:pom")
        self.assertEqual(NC.check_terminator(r.root, r.board, task_id=tid, run_id=run, kind="block", profile="implementer",
                                             audit_green=lambda: False)["code"], "BLOCK_ALLOWED")


# ===========================================================================
class RepeatedRefusal(unittest.TestCase):

    def setUp(self):
        self.r = Run()
        mirror_layout(self.r.root)
        self.r.release()
        self.tid, self.run, self.iss = self.r.issue("build:rk:pom")
        self.r.native.sync()

    def tearDown(self):
        self.r.close()

    def gate(self, *argv):
        sys.path.insert(0, str(KERNEL))
        import native_gate as G
        saved = {k: os.environ.get(k) for k in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID", "HERMES_KANBAN_DB")}
        os.environ.update(HERMES_KANBAN_TASK=self.tid, HERMES_KANBAN_RUN_ID=str(self.run), HERMES_KANBAN_DB=self.r.native.db_path)
        orig = NC.board_for
        NC.board_for = lambda root, native=None: NC.Board(self.r.native, author="implementer")
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                rc = G.main(["--root", str(self.r.root), *argv])
        finally:
            NC.board_for = orig
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return rc, json.loads(out.getvalue())

    def hook(self, tool, inp):
        e = dict(os.environ, HERMES_WRITE_SAFE_ROOT=str(self.r.root), K2_ALLOW_ROOT=str(self.r.root),
                 HERMES_PROFILE="implementer", HERMES_KANBAN_TASK=self.tid, HERMES_KANBAN_RUN_ID=str(self.run),
                 HERMES_KANBAN_DB=self.r.native.db_path, HERMES_HOME=str(self.r.tmp / "home"), PYTHONDONTWRITEBYTECODE="1")
        payload = {"hook_event_name": "pre_tool_call", "tool_name": tool, "tool_input": inp, "cwd": str(self.r.root)}
        p = subprocess.run(["bash", str(KERNEL / "pre_tool_call.sh")], input=json.dumps(payload), capture_output=True,
                           text=True, env=e, cwd=str(self.r.root))
        return json.loads(p.stdout or "{}")

    def test_third_identical_refusal_stops_the_run(self):
        r = self.r
        r.edit("pom.xml", "<project>candidate</project>\n")
        # restore-parked with nothing parked: the same refusal, three times
        for i in range(1, 3):
            rc, out = self.gate("restore-parked")
            self.assertEqual((rc, out["refused"]), (1, "RESTORE_NO_PARK"))
            self.assertEqual(self.hook("write_file", {"path": str(r.root / "pom.xml"), "content": "x"}), {})
        rc, out = self.gate("restore-parked")
        self.assertEqual((rc, out["refused"]), (1, "REPEATED_REFUSAL"))
        self.assertIn("kanban_block kind=needs_input", out["detail"])
        self.assertIn("candidate parked: pom.xml", out["detail"])             # this run's own candidate
        self.assertEqual(clean(r), "")
        # K2: every tool but the block is refused for this run
        for tool, inp in (("write_file", {"path": str(r.root / "pom.xml"), "content": "x"}),
                          ("terminal", {"command": "python3 .hermes/kernel/native_gate.py --root . issue"}),
                          ("kanban_request_review", {"reviewer": "reviewer", "summary": "x"})):
            self.assertIn("REPEATED_REFUSAL", self.hook(tool, inp).get("message", ""), tool)
        self.assertEqual(self.hook("kanban_block", {"reason": "RESTORE_NO_PARK repeated", "kind": "needs_input"}), {})
        self.assertEqual(NC.check_terminator(r.root, r.board, task_id=self.tid, run_id=self.run, kind="block",
                                             profile="implementer", audit_green=lambda: False)["code"], "BLOCK_ALLOWED")
        # the next run of the card starts fresh
        self.assertIsNone(NC.refusal_stop(r.root, self.tid, self.run + 1))

    def test_hook_refuses_a_block_that_leaves_a_candidate(self):
        # through the real K2 hook, not only check_terminator (the first qualification
        # on the pinned runtime found outcome_hook allowing every block before native control)
        r = self.r
        self.assertEqual(self.hook("kanban_block", {"reason": "x", "kind": "needs_input"}), {})
        r.edit("pom.xml", "<project>unjudged</project>\n")
        self.assertIn("BLOCK_LEAVES_CANDIDATE", self.hook("kanban_block", {"reason": "x", "kind": "needs_input"}).get("message", ""))
        rc, out = self.gate("park")
        self.assertEqual((rc, out["parked"]), (0, ["pom.xml"]))
        self.assertEqual(self.hook("kanban_block", {"reason": "x", "kind": "needs_input"}), {})

    def test_an_ended_session_is_told_to_end_and_never_touches_another_cards_edit(self):
        # v21 t_051c4490: after kanban_request_review the nudged session found the NEXT card's
        # edit in the shared tree and tried park, block, checkout and a file write
        r = self.r
        rc = self.gate("park")[0]                                          # nothing of this run to park
        self.assertEqual(rc, 0)
        r.native.end_run(self.tid, "ready", "review_requested")          # this run is over
        other, orun, oiss = r.issue("config:rk:cfg")                      # the next card edits its own file
        r.native.sync()
        r.edit(oiss["allowed_paths"][0], "# next card's edit in progress\n")
        for tool, inp in (("kanban_block", {"reason": "x", "kind": "needs_input"}),
                          ("terminal", {"command": "git checkout -- src/main/resources/application.properties"}),
                          ("write_file", {"path": str(r.root / "pom.xml"), "content": "x"}),
                          ("kanban_complete", {"summary": "x"})):
            self.assertIn("RUN_ENDED", self.hook(tool, inp).get("message", ""), tool)
        # the block rule and park never count another card's edit against this card
        self.assertEqual(NC.check_terminator(r.root, r.board, task_id=self.tid, run_id=self.run, kind="block",
                                             profile="implementer", audit_green=lambda: False)["code"], "BLOCK_ALLOWED")
        self.assertIn("next card's edit", (r.root / oiss["allowed_paths"][0]).read_text())
        # the live run of the next card is not affected
        saved = (self.tid, self.run)
        self.tid, self.run = other, orun
        try:
            self.assertNotIn("RUN_ENDED", self.hook("write_file", {"path": str(r.root / oiss["allowed_paths"][0]),
                                                                    "content": "x"}).get("message", ""))
        finally:
            self.tid, self.run = saved

    def test_park_holds_only_this_runs_paths(self):
        r = self.r
        r.edit("pom.xml", "<project>mine</project>\n")                    # issued to this run
        r.edit("src/main/resources/application.properties", "# not mine\n")  # another card's path
        with contextlib.redirect_stdout(io.StringIO()):
            got = NC.park(r.root, r.board, task_id=self.tid, run_id=self.run)
        self.assertEqual(got["parked"], ["pom.xml"])
        self.assertEqual((r.root / "src/main/resources/application.properties").read_text(), "# not mine\n")

    def test_different_refusals_do_not_add_up(self):
        for code in ("A", "B", "A", "B"):
            n = NC.note_refusal(self.r.root, self.tid, self.run, code)
        self.assertEqual(n, 1)
        self.assertIsNone(NC.refusal_stop(self.r.root, self.tid, self.run))


# ===========================================================================
class OrphanedObligations(unittest.TestCase):
    """v28: once compilation reached zero errors the package gate ran for the first time and failed at
    RootRestController.java (a SpEL field the accepted COMPILE card kept). No plan node owned that
    obligation; every M3 BEHAVIOR card was issued no write set, recorded a witness checkpoint, stayed
    PENDING and blocked asking the Operator. A behavior card now routes it by M4's rules before any scope:
    the follow-up of the file's accepted owner, sharing its budget, as a prerequisite of every waiting card."""
    ITEM_BEH = "behavior:http:com.acme.shop.web.ItemController"
    ORDER_BEH = "behavior:http:com.acme.shop.web.OrderController"
    ITEM_FILE = "src/main/java/com/acme/shop/web/ItemController.java"
    ORDER_FILE = "src/main/java/com/acme/shop/web/OrderController.java"
    LATE = "rt:package:late-expression"

    def build(self, *, requirement_on: str = ""):
        r = Run(publish=False)
        if requirement_on:
            with_check(r, requirement_on, "parity:late")
        r.out = r.publish()
        r.release()
        r.drop("inc:unlocatable:jndi")
        for n in OG.topo_order(r.plan()["nodes"]):
            if n["role"] != "repair" or n["class"] == "behavior":
                continue
            r.accept(n["outcome_id"], classes=("build", "compile", "tests") + (("runtime",) if n["class"] == "runtime" else ()),
                     scenarios=n.get("scenarios") or ())
        return r

    def late(self, r: Run, *, cluster: str, path: str, fresh: bool = True) -> None:
        """The package gate's failure, first measured after every compile card was accepted."""
        wl = r.worklist
        wl["items"].append({"id": self.LATE, "category": "mandatory", "kind": "compile", "source": "runtime", "path": path,
                            "message": "package gate failed: SpEL expressions are not supported"})
        c = next((c for c in wl["clusters"] if c["id"] == cluster), None)
        if c is None:
            c = {"id": cluster, "items": [], "kind": "compile", "path": path, "status": "open", "write_set": [path]}
            wl["clusters"].append(c)
        c["items"].append(self.LATE)
        wl["candidate_sha256"] = r.tree() if fresh else "0" * 64
        r.save_worklist()

    def test_the_owners_follow_up_becomes_every_waiting_cards_prerequisite(self):
        r = self.build()
        try:
            self.late(r, cluster="c:item", path=self.ITEM_FILE)            # the accepted source:rk:item formed c:item
            m4, other = r.tid("assess:m4:g1"), r.tid(self.ORDER_BEH)
            self.assertEqual(status(r, other), "ready")
            tid, run, lock = r.claim(self.ITEM_BEH)
            with self.assertRaises(Refusal) as cm:
                NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock)
            self.assertEqual(cm.exception.code, "OWNER_REPAIR_PENDING")
            fid = "followup:source:rk:item:m3g1"
            self.assertIn(fid, cm.exception.detail)
            self.assertIn("kanban_block kind=dependency", cm.exception.detail)
            plan = r.plan()
            fnode = NC._node(plan, fid)
            self.assertEqual((plan["revision"], plan["ownership"][self.LATE]), (2, fid))
            self.assertEqual(fnode["budget"], NC._node(plan, "source:rk:item")["budget"])    # never a fresh budget
            self.assertEqual((fnode["plan_paths"], fnode["clusters"]), ([self.ITEM_FILE], ["c:item"]))
            ftid = r.tid(fid)
            for t in (tid, other, m4):
                self.assertIn(ftid, r.native.task(t)["parents"])
            self.assertNotIn(tid, r.native.task(ftid)["parents"])
            self.assertEqual(status(r, other), "todo")                      # the sibling waits before it is dispatched
            self.assertEqual(NP.readback(r.board, plan), [])
            self.assertEqual(len(r.board.records(tid, "orphan-route")), 1)
            self.assertEqual(NC.check_terminator(r.root, r.board, task_id=tid, run_id=run, kind="block", profile="implementer",
                                                 audit_green=lambda: True)["action"], "allow")
            r.native.block_dependency(tid)
            # the follow-up is issued the owner's file and discharges the obligation there
            rtid, rrun, riss = r.issue(fid)
            self.assertEqual(riss["allowed_paths"], [self.ITEM_FILE])
            acc = r.accept_on_run(rtid, rrun, riss)
            self.assertTrue(acc["outcome_accepted"], acc)
            r.review_and_complete(rtid, rrun)
            self.assertEqual((status(r, tid), status(r, other)), ("ready", "ready"))   # native promotion, no Operator
            r.worklist["candidate_sha256"] = r.tree()
            r.save_worklist()
            r.issue(self.ORDER_BEH)                                          # nothing orphaned: no second revision
            self.assertEqual(r.plan()["revision"], 2)
        finally:
            r.close()

    def test_an_obligation_the_card_owns_is_issued_to_it(self):
        r = self.build(requirement_on=self.ORDER_BEH)
        try:
            self.late(r, cluster="c:late-order", path=self.ORDER_FILE)     # unclaimed cluster; its file is this card's
            tid, run, iss = r.issue(self.ORDER_BEH)
            self.assertEqual((iss["cluster"], iss["allowed_paths"]), ("c:late-order", [self.ORDER_FILE]))
            plan = r.plan()
            self.assertEqual((plan["revision"], plan["ownership"][self.LATE]), (2, self.ORDER_BEH))
            self.assertFalse([n for n in plan["nodes"] if n["outcome_id"].startswith("followup:")])
        finally:
            r.close()

    def test_an_obligation_without_an_owner_is_a_named_refusal(self):
        r = self.build()
        try:
            self.late(r, cluster="c:late", path="src/main/java/com/acme/shop/web/NobodysController.java")
            tid, run, lock = r.claim(self.ITEM_BEH)
            with self.assertRaises(Refusal) as cm:
                NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock)
            self.assertEqual(cm.exception.code, "ISSUE_ORPHANED_OBLIGATION")
            self.assertIn(self.LATE, cm.exception.detail)
            self.assertIn("kind=needs_input", cm.exception.detail)
            self.assertEqual(r.plan()["revision"], 1)
        finally:
            r.close()

    def test_a_work_list_of_another_tree_routes_nothing(self):
        r = self.build()
        try:
            self.late(r, cluster="c:item", path=self.ITEM_FILE, fresh=False)
            r.issue(self.ITEM_BEH)
            self.assertEqual(r.plan()["revision"], 1)
        finally:
            r.close()

    def test_owner_of_finding_resolves_a_cluster_one_outcome_formed(self):
        plan = NB.derive()
        got = OG.owner_of_finding(plan, {"id": "x", "cluster": "c:item", "path": self.ITEM_FILE})
        self.assertEqual(got, {"owner": "source:rk:item", "resolution": "cluster"})
        twin = copy.deepcopy(plan)
        next(n for n in twin["nodes"] if n["outcome_id"] == "source:rk:order")["clusters"].append("c:item")
        self.assertIsNone(OG.owner_of_finding(twin, {"id": "x", "cluster": "c:item", "path": self.ITEM_FILE})["owner"])

    def test_a_finding_at_the_cards_own_entry_point_is_issued_to_it(self):
        """v29 t_65445e69: its own endpoints' parity failures (a StackOverflowError in a repository the endpoint
        calls) had no plan owner by id; by entry point they were ambiguous between the card and an accepted
        controller objective, so issue refused ISSUE_ORPHANED_OBLIGATION and the card was stranded. The card that
        measures an entry point owns what fails there; the producing file is reached by amend-scope."""
        r = self.build()
        try:
            wl = r.worklist
            wl["items"].append({"id": "parity:item-list-500", "category": "mandatory", "kind": "parity", "source": "parity",
                                "scenario": "items-list", "entry_point": "com.acme.shop.web.ItemController#list():http", "path": ""})
            wl["clusters"].append({"id": "c:item-parity", "items": ["parity:item-list-500"], "kind": "parity", "path": self.ITEM_FILE,
                                   "status": "open", "write_set": [self.ITEM_FILE]})
            wl["candidate_sha256"] = r.tree()
            r.save_worklist()
            tid, run, iss = r.issue(self.ITEM_BEH)
            self.assertEqual((iss["cluster"], iss["allowed_paths"]), ("c:item-parity", [self.ITEM_FILE]))
            plan = r.plan()
            self.assertEqual(plan["ownership"]["parity:item-list-500"], self.ITEM_BEH)
            self.assertFalse([n for n in plan["nodes"] if n["outcome_id"].startswith("followup:")])
        finally:
            r.close()


if __name__ == "__main__":
    unittest.main(verbosity=1)
