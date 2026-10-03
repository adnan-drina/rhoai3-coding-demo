#!/usr/bin/env python3
"""D-1 (post-v32 qualification; fix-until-green B11): a stopped run's unjudged edits are the next run of the SAME
card's candidate. The respawned run's issue keeps them on the tree (no abandoned-candidate record, no
ISSUE_BASELINE_DRIFT) and the brief hands them over as candidate_on_tree. Everything else is unchanged: another
card's leftovers are set aside onto their proven owner (H-15), unprovable ownership stays the drift refusal, and a
candidate that no longer fits (HEAD moved under it, or this issue grants another write set) is set aside as before.

SYNTHETIC evidence: the native_board.test.py FakeNative board and shop plan, run once as written and once as a
renamed twin (every package, type, file and retry key renamed); cards are chosen by board state, never by name.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/retry_keeps_own_candidate.test.py
"""
from __future__ import annotations

import base64
import copy
import importlib.util
import json
import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_spec = importlib.util.spec_from_file_location("native_board_test", Path(__file__).with_name("native_board.test.py"))
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)
NC, Run, Refusal, git = T.NC, T.Run, T.Refusal, T.git
from planner import outcome_graph as OG  # noqa: E402

LOOP = Path(__file__).resolve().parents[2] / "skills" / "migration" / "fix-until-green" / "scripts"
sys.path.insert(0, str(LOOP))
from _loop_common import product_paths_changed  # noqa: E402  (what brief.py's candidate_on_tree lists)

# the renamed twin: identifiers only (build and configuration file names are the platform's, not the specimen's)
RENAMES = (("acme", "zenith"), ("shop", "ledger"), ("Item", "Entry"), ("item", "entry"), ("Order", "Invoice"),
           ("order", "invoice"), ("Admin", "Steward"), ("mapper", "shaper"), ("Mapper", "Shaper"))


def _rename(v):
    if isinstance(v, str):
        for a, b in RENAMES:
            v = v.replace(a, b)
        return v
    if isinstance(v, list):
        return [_rename(x) for x in v]
    if isinstance(v, dict):
        # schema keys stay; keys that are identifiers (paths, entry points, ids) are renamed with the values
        return {(_rename(k) if ("/" in k or ":" in k or "." in k) else k): _rename(x) for k, x in v.items()}
    return v


ORIGINAL = copy.deepcopy(T.SHOP)
TWIN = _rename(ORIGINAL)


class _World(unittest.TestCase):
    world = ORIGINAL

    def setUp(self):
        T.SHOP = self.world
        self.r = Run()
        self.r.release()

    def tearDown(self):
        self.r.close()
        T.SHOP = ORIGINAL

    # -- board-state selection (no outcome id, path or name is assumed) --
    def ready_repairs(self):
        r = self.r
        return [n["outcome_id"] for n in OG.topo_order(r.plan()["nodes"])
                if n["role"] == "repair" and T.status(r, r.tid(n["outcome_id"])) == "ready"]

    def stopped(self, oid, *, outcome="gave_up", status="ready", n_files=2):
        """Card ``oid``'s run is issued, writes inside its write set, and is stopped by the runtime (no terminator)."""
        r = self.r
        tid, old, iss = r.issue(oid)
        self.assertTrue(iss["allowed_paths"], iss)
        edited = sorted(iss["allowed_paths"][:n_files])
        for rel in edited:
            r.edit(rel, "// %s: unjudged work of run %d\n" % (rel, old))
        time.sleep(0.05)
        r.native.end_run(tid, status, outcome)
        time.sleep(0.05)
        return tid, old, iss, edited

    def snapshot(self, paths):
        return {rel: (self.r.root / rel).read_bytes() for rel in paths}

    # -- the defect --------------------------------------------------------
    def test_same_card_retry_keeps_its_candidate(self):
        r = self.r
        oid = self.ready_repairs()[0]
        tid, old, first, edited = self.stopped(oid)
        before = self.snapshot(edited)
        committed = NC.commit_product_tree(r.root, NC._head(r.root))
        run, lock = r.native.claim(tid)
        out = NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock, replay_unchanged=True)
        # kept, not set aside; no drift refusal
        self.assertEqual(out["candidate_kept"]["paths"], edited)
        self.assertEqual(out["candidate_kept"]["run"], old)
        self.assertIsNone(out["candidate_set_aside"])
        self.assertTrue(out["next"].startswith("CANDIDATE KEPT"), out["next"])
        self.assertEqual(self.snapshot(edited), before)                              # byte for byte
        self.assertEqual(r.board.records(tid, NC.ABANDONED), [])
        # never blessed as the baseline: the issue is measured against HEAD's tree, and its record says what it kept
        self.assertEqual((out["baseline_tree"], out["baseline_commit"]), (committed, NC._head(r.root)))
        rec = [x for x in r.board.records(tid, "issue") if x["run"] == run][-1]
        self.assertEqual(rec["candidate_kept"], {"from_run": old, "paths": edited})
        self.assertTrue(set(edited) <= set(out["allowed_paths"]))
        # what the brief's candidate_on_tree lists
        self.assertEqual(product_paths_changed(r.root), edited)
        # the loop's projection is written for the kept issue exactly as for any issue
        import native_gate as NG
        T.mirror_layout(r.root)
        self.assertTrue(NG.write_issued_projection(r.root, out))
        # a repeated issue in this run is the in-progress rule (V29-3): refused, nothing set aside, bytes kept
        with self.assertRaises(Refusal) as cm:
            NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock, replay_unchanged=True)
        self.assertEqual(cm.exception.code, "ISSUE_BASELINE_DRIFT")
        self.assertEqual(self.snapshot(edited), before)
        self.assertEqual(r.board.records(tid, NC.ABANDONED), [])

    # -- unchanged paths ---------------------------------------------------
    def test_another_cards_leftover_is_still_set_aside_onto_its_owner(self):
        r = self.r
        a, b = self.ready_repairs()[:2]
        ta, ra, _ia, edited = self.stopped(a, outcome="crashed", status="blocked")
        before = self.snapshot(edited)
        tb, rb, ib = r.issue(b)
        self.assertIsNone(ib["candidate_kept"])
        ab = r.board.records(ta, NC.ABANDONED)
        self.assertEqual((len(ab), ab[0]["run"], ab[0]["paths"]), (1, ra, edited))   # onto the owner (H-15)
        files = json.loads(r.board.attachment(ta, ab[0]["attachment"])[0])["files"]
        self.assertEqual({k: base64.b64decode(v) for k, v in files.items()}, before)
        self.assertEqual(r.board.records(tb, NC.ABANDONED), [])
        self.assertEqual(NC._changed_vs_head(r.root)[1], [])

    def test_unprovable_ownership_is_unchanged(self):
        r = self.r
        oid = self.ready_repairs()[0]
        tid, old, _iss, edited = self.stopped(oid)
        t = time.time() - 3600                                                      # written before the run started
        os.utime(r.root / edited[0], (t, t))
        before = self.snapshot(edited)
        run, lock = r.native.claim(tid)
        with self.assertRaises(Refusal) as cm:
            NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock)
        self.assertEqual(cm.exception.code, "ISSUE_BASELINE_DRIFT")
        self.assertEqual(self.snapshot(edited), before)
        self.assertEqual(r.board.records(tid, NC.ABANDONED), [])

    def test_a_predecessor_without_a_native_end_is_unchanged(self):
        r = self.r
        oid = self.ready_repairs()[0]
        tid, old, _iss, edited = self.stopped(oid)
        r.native.runs_[old]["ended_at"] = None                                      # the run table does not say it ended
        before = self.snapshot(edited)
        run, lock = r.native.claim(tid)
        with self.assertRaises(Refusal) as cm:
            NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock)
        self.assertEqual(cm.exception.code, "ISSUE_BASELINE_DRIFT")
        self.assertEqual(self.snapshot(edited), before)
        self.assertEqual(r.board.records(tid, NC.ABANDONED), [])

    # -- the conservative choices ------------------------------------------
    def test_head_moved_under_the_stopped_run_sets_it_aside(self):
        r = self.r
        oid = self.ready_repairs()[0]
        tid, old, _iss, edited = self.stopped(oid)
        (r.root / "OPERATOR-NOTE.txt").write_text("an unrelated commit\n")
        git(r.root, "add", "OPERATOR-NOTE.txt")
        git(r.root, "commit", "-qm", "operator note")
        run, lock = r.native.claim(tid)
        out = NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock)
        self.assertIsNone(out["candidate_kept"])
        ab = r.board.records(tid, NC.ABANDONED)
        self.assertEqual((len(ab), ab[0]["run"], ab[0]["paths"]), (1, old, edited))
        self.assertEqual(NC._changed_vs_head(r.root)[1], [])

    def test_a_leftover_outside_the_new_write_set_is_set_aside(self):
        r = self.r
        oid = self.ready_repairs()[0]
        tid, old, first, edited = self.stopped(oid)
        before = self.snapshot(edited)
        granted = [p for p in first["allowed_paths"] if p != edited[-1]]            # the work list moved
        real = NC._allowed_paths

        def narrower(*a, **k):
            cluster, allowed = real(*a, **k)
            return cluster, [p for p in allowed if p in granted]
        from unittest import mock
        run, lock = r.native.claim(tid)
        with mock.patch.object(NC, "_allowed_paths", narrower):
            out = NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock)
        self.assertIsNone(out["candidate_kept"])
        self.assertIn(edited[-1], out["candidate_set_aside"]["why"])
        ab = r.board.records(tid, NC.ABANDONED)
        self.assertEqual((len(ab), ab[0]["run"], ab[0]["paths"]), (1, old, edited))   # the whole candidate, as before
        files = json.loads(r.board.attachment(tid, ab[0]["attachment"])[0])["files"]
        self.assertEqual({k: base64.b64decode(v) for k, v in files.items()}, before)
        self.assertEqual(NC._changed_vs_head(r.root)[1], [])
        rec = [x for x in r.board.records(tid, "issue") if x["run"] == run][-1]
        self.assertNotIn("candidate_kept", rec)


class Original(_World):
    world = ORIGINAL


class RenamedTwin(_World):
    world = TWIN

    def test_the_twin_is_renamed(self):
        paths = {p for c in self.world["worklist"]["clusters"] for p in c["write_set"]}
        self.assertFalse(any("acme" in p or "shop" in p or "Item" in p or "Order" in p for p in paths), paths)
        self.assertNotEqual(paths, {p for c in ORIGINAL["worklist"]["clusters"] for p in c["write_set"]})


del _World

if __name__ == "__main__":
    unittest.main(verbosity=1)
