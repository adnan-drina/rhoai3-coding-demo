#!/usr/bin/env python3
"""M-5 lifecycle replay (MIGRATION-IMPROVEMENTS.md, M-5 exit): ONE replay of a
native card's lifecycle -- issue -> edit -> verify -> reject/accept -> review ->
continuation -- through interruption and restart, the concurrent interleavings
V29-2 names, and the agreement of void, deferral and admission, with the
budget conserved at every step. It complements the focused tests in
native_board.test.py (LifecycleReconciliation), worklist.test.py and the
comparator suites; it does not replace them.

SYNTHETIC evidence: native_board.test.py's FakeNative board harness (Run) with
real git; the loop's revert and admission are simulated where noted.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/lifecycle_replay.test.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("native_board_harness", HERE / "native_board.test.py")
NB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(NB)

from planner import native_control as NC  # noqa: E402
from planner.outcome_checks import Refusal  # noqa: E402
from planner.paths import ADMISSION_RECEIPT, LOOP_DEFERRED, LOOP_ISSUED, LOOP_STEPS, PARITY_DIR  # noqa: E402

A, B = "build:rk:pom", "config:rk:cfg"


class LifecycleReplay(unittest.TestCase):

    def setUp(self):
        self.r = NB.Run()
        self.r.release()

    def tearDown(self):
        self.r.close()

    # -- helpers -------------------------------------------------------------------
    def spent(self, tid):
        return NC.effective_budget(self.r.board, tid)

    def creates(self):
        return len([c for c in self.r.native.calls if c[0] == "create"])

    def projection(self, tid, run, cluster):
        p = self.r.root / LOOP_ISSUED
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"task_id": tid, "cluster": cluster,
                                 "idempotency_key": "outcome:v2:n1:%s:%s:issue1:r%d" % (A, cluster, run)}))
        return p

    def revert(self, rel):
        """What advance.py's _reject does after the native reject record: restore HEAD."""
        NB.git(self.r.root, "checkout", "HEAD", "--", rel)

    # -- the replay ----------------------------------------------------------------
    def test_one_card_through_rejection_interruption_review_and_recovery(self):
        r = self.r
        creates = self.creates()
        steps = r.root / LOOP_STEPS
        steps.parent.mkdir(parents=True, exist_ok=True)
        steps.write_text(json.dumps({"steps": [], "attempts": {}}))
        steps_bytes = steps.read_bytes()

        # 1. issue -> edit -> the worker re-reads its issue: its edits are kept, nothing is recorded
        ta, ra, ia = r.issue(A)
        rel, cluster = ia["allowed_paths"][0], ia["cluster"]
        r.edit(rel, "<project>attempt 1</project>\n")
        rep = NC.issue(r.root, r.board, task_id=ta, run_id=ra, replay_unchanged=True)
        self.assertTrue(rep["replayed"] and rep["in_progress"])
        self.assertEqual((r.root / rel).read_text(), "<project>attempt 1</project>\n")

        # 2. verify -> a GENUINE rejection -> the loop's revert -> the same card is re-issued (continuation)
        NC.record_verdict(r.root, r.board, task_id=ta, run_id=ra, verdict="REVERTED", candidate=r.tree(), attempt="a1",
                          reason="tests red")
        self.revert(rel)
        nxt = NC.issue(r.root, r.board, task_id=ta, run_id=ra)
        self.assertEqual((nxt["issue_id"], nxt["budget"]["spent"]), (2, 1))

        # 3. INTERRUPTION: a harness-caused rejection, then the worker is stopped before its revert; its
        #    projection is left behind
        r.edit(rel, "<project>attempt 2</project>\n")
        cand2 = r.tree()
        NC.record_verdict(r.root, r.board, task_id=ta, run_id=ra, verdict="REVERTED", candidate=cand2, attempt="a2",
                          reason="charset respelling (harness)")
        r.native.end_run(ta, "ready", "gave_up")
        stale = self.projection(ta, ra, cluster)

        # 4. RESTART: another card is issued; the rejected bytes are set aside onto A, B starts from HEAD
        committed = NC.commit_product_tree(r.root, NC._head(r.root))
        tb, rb, ib = r.issue(B)
        self.assertEqual(ib["baseline_tree"], committed)
        ab = r.board.records(ta, NC.ABANDONED)
        self.assertEqual((len(ab), ab[0]["run"]), (1, ra))
        self.assertEqual(json.loads(r.board.attachment(ta, ab[0]["attachment"])[0])["candidate"], cand2)
        self.assertEqual(r.board.records(tb, NC.ABANDONED), [])

        # 5. B: accept -> review requests changes (spends B's budget) -> rework accepted -> complete
        self.assertTrue(r.accept_on_run(tb, rb, ib, attempt="1")["outcome_accepted"])
        r.native.request_review(tb)
        r.native.claim_review(tb)
        r.native.request_changes(tb, "keep the source profile name")
        self.assertEqual(self.spent(tb)["spent"], 1)
        rb2, lock = r.native.claim(tb)
        ib2 = NC.issue(r.root, r.board, task_id=tb, run_id=rb2, claim_lock=lock)
        self.assertTrue(ib2["cluster"].startswith("rework:"))
        self.assertTrue(r.accept_on_run(tb, rb2, ib2, attempt="2", drop=False)["outcome_accepted"])
        r.review_and_complete(tb, rb2)
        review_spend = self.spent(tb)

        # 6. the Operator retires A's stale projection while a new claim lands between the record and the
        #    removal: the new claim keeps its own projection (V29-2)
        self.assertEqual(NC.issuance_state(r.root, r.board)["state"], "expired")
        record, seen = r.board.record, {}

        def claim_during_retirement(task, kind, key, **fields):
            got = record(task, kind, key, **fields)
            if kind == "issuance-retired":
                seen["run"], seen["lock"] = r.native.claim(ta)
                self.projection(ta, seen["run"], cluster)
            return got
        r.board.record = claim_during_retirement
        try:
            with self.assertRaises(Refusal) as cm:
                NC.retire_issuance(r.root, r.board, by="operator", reason="stale run %d" % ra)
        finally:
            r.board.record = record
        self.assertEqual(cm.exception.code, "ISSUANCE_CHANGED")
        ra3 = seen["run"]
        self.assertIn(":r%d" % ra3, json.loads(stale.read_text())["idempotency_key"])

        # 7. the new run of A spends its last attempt: the family is exhausted and the cluster deferred
        ia3 = NC.issue(r.root, r.board, task_id=ta, run_id=ra3, claim_lock=seen["lock"])
        self.assertEqual((ia3["cluster"], ia3["budget"]["spent"]), (cluster, 2))
        r.edit(rel, "<project>attempt 3</project>\n")
        NC.record_verdict(r.root, r.board, task_id=ta, run_id=ra3, verdict="REVERTED", candidate=r.tree(), attempt="a3",
                          reason="tests red")
        self.revert(rel)
        key, limit = ia["budget"]["key"], ia["budget"]["limit"]
        self.assertEqual(self.spent(ta)["spent"], limit)
        deferred = r.root / LOOP_DEFERRED
        deferred.write_text(json.dumps({"schema": "rhoai3.loop-deferred/v1", "clusters": [cluster], "reasons": {
            cluster: "%d of %d attempt(s) spent against %s; last: tests red" % (limit, limit, key)}}))
        seal = r.root / ADMISSION_RECEIPT
        seal.parent.mkdir(parents=True, exist_ok=True)
        seal.write_text(json.dumps({"status": "INCONCLUSIVE", "blocks": [{"class": "MANUAL_CLUSTER", "subject": cluster}]}))
        r.native.end_run(ta, "blocked", "needs_input")
        held = NC.reconcile_deferrals(r.root, r.board, task_id=ta, by="operator", reason="early")
        self.assertEqual((held["lifted"], len(held["kept"])), ([], 1))                # still exhausted: kept

        # 8. void the harness-caused rejection; interrupted between the void and the reconciliation; repeated
        from planner import pipeline, worklist as W
        orig = (pipeline.admit, W.build_worklist)
        admitted = []

        def admit(root, **k):
            admitted.append(1)
            seal.write_text(json.dumps({"status": "ADMITTED", "blocks": []}))
            return {"status": "ADMITTED"}
        pipeline.admit, W.build_worklist = admit, (lambda root, **k: None)
        try:
            a2 = "reject:%d:a2" % ra
            self.assertEqual(NC.void_rejects(r.board, task_id=ta, keys=[a2], reason="charset respelling", by="operator"), [a2])
            self.assertEqual(NC.void_rejects(r.board, task_id=ta, keys=[a2], reason="charset respelling", by="operator"), [])
            got = NC.reconcile_deferrals(r.root, r.board, task_id=ta, by="operator", reason="charset respelling")
            again = NC.reconcile_deferrals(r.root, r.board, task_id=ta, by="operator", reason="charset respelling")
        finally:
            pipeline.admit, W.build_worklist = orig
        self.assertEqual((got["lifted"], again["lifted"]), ([cluster], []))
        self.assertEqual(json.loads(deferred.read_text())["clusters"], [])
        self.assertEqual((json.loads(seal.read_text())["status"], len(admitted)), ("ADMITTED", 1))
        after = got["effective"]["after"]
        self.assertEqual((after["spent"], after["remaining"], after["limit"], after["voided"]), (2, 1, limit, 1))
        self.assertEqual(len(r.board.records(ta, "reject")), 3)                        # every rejection stays recorded
        self.assertEqual(self.spent(tb), review_spend)                                  # review spending conserved
        self.assertEqual(steps.read_bytes(), steps_bytes)                               # no legacy allowance
        self.assertEqual(self.creates(), creates)                                       # nothing minted

        # 9. the projection of the ended run 3 is now retired as history
        out = NC.retire_issuance(r.root, r.board, by="operator", reason="run %d ended" % ra3)
        self.assertFalse(stale.exists())
        self.assertTrue((r.root / out["retired"]).is_file())
        self.assertEqual(len(r.board.records(ta, "issuance-retired")), 2)

        # 10. explicit native unblock: the same card is issued the lifted cluster from the restored account
        r.native.tasks[ta]["status"] = "ready"                                         # (the fake has no unblock verb)
        ra4, lock4 = r.native.claim(ta)
        ia4 = NC.issue(r.root, r.board, task_id=ta, run_id=ra4, claim_lock=lock4)
        self.assertEqual((ia4["cluster"], ia4["budget"]["spent"], ia4["budget"]["exhausted"]), (cluster, 2, False))
        self.assertTrue(r.accept_on_run(ta, ra4, ia4, attempt="a4")["outcome_accepted"])
        r.review_and_complete(ta, ra4)
        self.assertEqual(NB.status(r, ta), "done")
        self.assertEqual(self.spent(ta)["spent"], 2)                                   # acceptance spends nothing

        # 11. a later comparison that cannot be authoritative cannot erase a known obligation
        sys.path.insert(0, str(HERE.parents[1] / "skills" / "gates" / "capture-source-oracles" / "scripts"))
        from _oracle_common import write_unauthoritative
        ep = "ep:com.acme.shop.web.ItemController#list():http"
        bundle = {"entry_points": [{"id": ep, "path": "src/main/java/com/acme/shop/web/ItemController.java"}]}
        v = r.root / PARITY_DIR / "scenarios" / "sc_items.json"
        v.parent.mkdir(parents=True, exist_ok=True)
        v.write_text(json.dumps({"schema": "rhoai3.scenario-parity/v1", "entry_point": ep, "scenario": "sc:items",
                                 "verdict": "FAIL", "reason": "status 500 vs 200"}))
        known = [i["id"] for i in W.parity_items(r.root, bundle, receipt={})]
        write_unauthoritative(v, {"schema": "rhoai3.scenario-parity/v1", "entry_point": ep, "scenario": "sc:items",
                                  "verdict": "INCONCLUSIVE", "reason": "receipt not authoritative: stale seal"})
        kept = W.parity_items(r.root, bundle, receipt={})
        self.assertEqual([i["id"] for i in kept], known)
        self.assertTrue(known and all(i["pending_remeasure"] for i in kept))


if __name__ == "__main__":
    unittest.main(verbosity=1)
