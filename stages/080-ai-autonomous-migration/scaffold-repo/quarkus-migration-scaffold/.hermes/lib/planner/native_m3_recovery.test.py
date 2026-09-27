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

NC, OG, Refusal, VERDICT = NB.NC, NB.OG, NB.Refusal, NB.VERDICT
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
        self.assertEqual(node["assess:m4:g1"]["acceptance"]["deferred_requirement_checks"],
                         [{"outcome": "build:rk:pom", "requirements": ["req:1"], "check": "parity:request-body"}])
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

    def test_different_refusals_do_not_add_up(self):
        for code in ("A", "B", "A", "B"):
            n = NC.note_refusal(self.r.root, self.tid, self.run, code)
        self.assertEqual(n, 1)
        self.assertIsNone(NC.refusal_stop(self.r.root, self.tid, self.run))


if __name__ == "__main__":
    unittest.main(verbosity=1)
