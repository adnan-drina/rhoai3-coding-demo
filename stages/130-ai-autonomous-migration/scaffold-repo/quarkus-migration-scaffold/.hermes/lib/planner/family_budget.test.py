#!/usr/bin/env python3
"""v24 (architect decision 2026-09-28): on a governed outcome-board/v2 card the
M2-published shared-family budget is the ONE limit and native family_spent the
ONE count. Rejections on sibling cards accumulate; the third permits
continuation when the published limit is twelve; the twelfth exhausts; reviewer
change requests count, accepted checkpoints and waits do not; replay never
double-counts; the issue gate, the loop's projection and the brief agree; the
published total is unchanged; a card with no published budget refuses."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
HERMES = HERE.parent.parent
_spec = importlib.util.spec_from_file_location("native_board_harness_budget", HERE / "native_board.test.py")
NB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(NB)
sys.path.insert(0, str(HERMES / "kernel"))
sys.path.insert(0, str(HERMES / "skills" / "migration" / "fix-until-green" / "scripts"))
from planner import native_control as NC  # noqa: E402
from planner.outcome_checks import Refusal  # noqa: E402
import native_gate as NG  # noqa: E402

KEY, LIMIT = "rk:family:n1:shared-contracts", 12


def _run_with_family():
    """The shop plan with two sibling outcomes sharing one published family budget."""
    r = NB.Run(publish=False)
    plan = json.loads(r.plan_file.read_text())
    # the two outcomes that can be issued first (their only prerequisite is M2)
    sibs = [n for n in plan["nodes"] if n.get("role") == "repair" and n.get("parents") == ["control:m2"]][:2]
    assert len(sibs) == 2
    for n in sibs:
        n["budget"] = {"key": KEY, "limit": LIMIT}
    r.plan_file.write_text(json.dumps(plan))
    r.out = r.publish()
    r.release()
    r.drop("inc:unlocatable:jndi")
    return r, [n["outcome_id"] for n in sibs]


def _reject(r, tid, run, attempt):
    return NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="REVERTED",
                             candidate="%064d" % int(attempt) if str(attempt).isdigit() else "f" * 64, attempt=str(attempt), reason="red")


class FamilyBudget(unittest.TestCase):
    def setUp(self):
        self.r, (self.a, self.b) = _run_with_family()
        self.addCleanup(self.r.close)

    def spent(self):
        node = NC._node(self.r.plan(), self.a)
        return NC.budget_state(self.r.board, self.r.run_id, self.r.plan(), node)

    def test_siblings_accumulate_and_the_third_continues_and_the_twelfth_exhausts(self):
        r = self.r
        ta, ra, _ = r.issue(self.a)
        _reject(r, ta, ra, 1)
        tb, rb, _ = r.issue(self.b)
        _reject(r, tb, rb, 2)
        self.assertEqual(self.spent()["spent"], 2)                     # one family, two cards
        out = _reject(r, tb, rb, 3)
        self.assertEqual((out["spent"], out["limit"], out["exhausted"]), (3, LIMIT, False))
        NC.issue(r.root, r.board, task_id=tb, run_id=rb)              # the third permits continuation
        for i in range(4, LIMIT + 1):
            out = _reject(r, ta if i % 2 else tb, ra if i % 2 else rb, i)
        self.assertEqual((out["spent"], out["exhausted"]), (LIMIT, True))
        for tid, run in ((ta, ra), (tb, rb)):                          # no thirteenth attempt on either card
            with self.assertRaises(Refusal) as cm:
                NC.issue(r.root, r.board, task_id=tid, run_id=run)
            self.assertEqual(cm.exception.code, "ISSUE_BUDGET_EXHAUSTED")

    def test_change_requests_count_checkpoints_and_waits_do_not(self):
        r = self.r
        ta, ra, iss = r.issue(self.a)
        _reject(r, ta, ra, 1)
        # an accepted checkpoint that does not accept the outcome spends nothing
        r.accept_on_run(ta, ra, NC.issue(r.root, r.board, task_id=ta, run_id=ra), classes=("build", "compile"), drop=False,
                        attempt="cp")
        self.assertEqual(self.spent()["spent"], 1)
        # quota (rate_limited) and dependency waits spend nothing
        r.native.end_run(ta, "ready", "rate_limited")
        ra, _ = r.native.claim(ta)
        r.native.block_dependency(ta)
        self.assertEqual(self.spent()["spent"], 1)
        # a reviewer's change request is a charge
        tb, rb, _ = r.issue(self.b)
        r.native.request_review(tb)
        rrun, _ = r.native.claim_review(tb)
        r.native.request_changes(tb, "wrong shape")
        self.assertEqual(self.spent()["spent"], 2)

    def test_restart_and_replay_neither_lose_nor_double_count(self):
        r = self.r
        ta, ra, _ = r.issue(self.a)
        _reject(r, ta, ra, 1)
        _reject(r, ta, ra, 2)
        _reject(r, ta, ra, 2)                                          # the replayed verdict of the same attempt
        self.assertEqual(self.spent()["spent"], 2)
        r.native.end_run(ta, "ready", "crashed")                      # a restart of the worker
        ra2, _ = r.native.claim(ta)
        iss = NC.issue(r.root, r.board, task_id=ta, run_id=ra2)
        self.assertEqual((iss["budget"]["spent"], iss["budget"]["limit"]), (2, LIMIT))   # ten remain, nothing replenished

    def test_an_unchanged_reissue_records_nothing_new(self):
        # v26 t_7c356ade: seven issues in one run, nothing changed between them
        r = self.r
        NB.mirror_layout(r.root)
        ta, ra, first = r.issue(self.a)
        n = len(r.board.records(ta, "issue"))
        again = [NC.issue(r.root, r.board, task_id=ta, run_id=ra, replay_unchanged=True) for _ in range(6)]
        self.assertEqual(len(r.board.records(ta, "issue")), n)
        self.assertEqual({i["issue_id"] for i in again}, {first["issue_id"]})
        self.assertTrue(all(i["replayed"] for i in again))
        self.assertIn("ALREADY ISSUED", again[-1]["next"])
        self.assertEqual({(i["cluster"], tuple(i["allowed_paths"]), i["baseline_tree"], i["budget"]["key"], i["budget"]["spent"])
                          for i in again}, {(first["cluster"], tuple(first["allowed_paths"]), first["baseline_tree"],
                                             first["budget"]["key"], first["budget"]["spent"])})
        if first.get("cluster"):
            NG.write_issued_projection(r.root, first)
            one = (r.root / "verification/loop/issued.json").read_text()
            NG.write_issued_projection(r.root, again[-1])
            self.assertEqual((r.root / "verification/loop/issued.json").read_text(), one)
        # anything recorded since makes the next issue a new one, with its own key
        _reject(r, ta, ra, 1)
        nxt = NC.issue(r.root, r.board, task_id=ta, run_id=ra, replay_unchanged=True)
        self.assertFalse(nxt["replayed"])
        self.assertEqual(nxt["issue_id"], first["issue_id"] + 1)
        self.assertEqual(nxt["budget"]["spent"], 1)
        # the loop's own re-issue (the bridge's CONTINUE after a verdict) is always a new attempt
        cont = NC.issue(r.root, r.board, task_id=ta, run_id=ra)
        self.assertEqual((cont["replayed"], cont["issue_id"]), (False, nxt["issue_id"] + 1))

    def test_issue_projection_bridge_and_brief_show_the_same_numbers(self):
        r = self.r
        NB.mirror_layout(r.root)
        ta, ra, _ = r.issue(self.a)
        _reject(r, ta, ra, 1)
        _reject(r, ta, ra, 2)
        iss = NC.issue(r.root, r.board, task_id=ta, run_id=ra)
        if not iss.get("cluster"):
            self.skipTest("this shop outcome issues no product scope to project")
        NG.write_issued_projection(r.root, iss)
        issued = json.loads((r.root / "verification/loop/issued.json").read_text())
        self.assertEqual((issued["budget_authority"], issued["retry_key"]), ("native", KEY))
        self.assertEqual((issued["native_budget"]["spent"], issued["native_budget"]["limit"]), (2, LIMIT))
        import _outcome_bridge as B
        import brief as BR
        with patch.object(B, "_native", return_value=r.board), patch.object(B, "_ids", return_value=(ta, ra)):
            nb = B.native_budget(r.root)
        gb = BR._governing_budget(r.root, {}, iss["cluster"], KEY)
        self.assertEqual((nb["key"], nb["spent"], nb["limit"]), (KEY, 2, LIMIT))
        self.assertEqual((gb["retry_key"], gb["spent"], gb["limit"], gb["left"]), (KEY, 2, LIMIT, 10))
        self.assertEqual((iss["budget"]["spent"], iss["budget"]["limit"]), (2, LIMIT))

    def test_the_published_total_is_unchanged(self):
        plan = json.loads(self.r.plan_file.read_text())
        before = sum(int((n.get("budget") or {}).get("limit") or 0) for n in plan["nodes"] if n.get("role") == "repair")
        after = sum(int((n.get("budget") or {}).get("limit") or 0) for n in self.r.plan()["nodes"] if n.get("role") == "repair")
        self.assertEqual(before, after)


class UnpublishedBudget(unittest.TestCase):
    def test_a_governed_card_without_a_published_budget_refuses(self):
        r = NB.Run(publish=False)
        self.addCleanup(r.close)
        plan = json.loads(r.plan_file.read_text())
        victim = next(n for n in plan["nodes"] if n.get("role") == "repair" and n.get("parents") == ["control:m2"])
        victim["budget"] = {}
        r.plan_file.write_text(json.dumps(plan))
        r.out = r.publish()
        r.release()
        tid, run, _lock = r.claim(victim["outcome_id"])
        with self.assertRaises(Refusal) as cm:
            NC.issue(r.root, r.board, task_id=tid, run_id=run)
        self.assertEqual(cm.exception.code, "ISSUE_BUDGET_UNPUBLISHED")


if __name__ == "__main__":
    unittest.main(verbosity=1)
