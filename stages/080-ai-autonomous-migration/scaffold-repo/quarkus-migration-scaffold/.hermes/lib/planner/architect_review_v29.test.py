"""The architect's review of 0dd677ba / ed9d31ac (v29 I-11), as maintained regressions.

1. Repeated issuance in a replacement run must not archive that run's own edits as its predecessor's;
   a proven abandoned predecessor candidate is still archived before restoration; live and newer claims,
   retained candidates, unrelated edits and uncertain ownership never trigger cleanup.
2. Retiring an expired issuance must not delete a newer claim's projection published meanwhile; a missing
   or malformed run identity is never expired; an interrupted retirement resumes to one record.
3. Content-Type comparison is quote-aware: distinct quoted values stay distinct, equivalent spellings
   (case of names and of charset, optional whitespace, quoted/unquoted) compare equal, malformed input
   gains no equivalence.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/architect_review_v29.test.py
"""
from __future__ import annotations

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
from planner.paths import LOOP_ISSUED  # noqa: E402
from planner.worklist import canonical_diff, canonical_media_type  # noqa: E402


def backdate(p: Path, seconds: float) -> None:
    t = time.time() - seconds
    os.utime(p, (t, t))


class AbandonedCandidate(unittest.TestCase):
    def setUp(self):
        self.r = Run()
        self.r.release()

    def tearDown(self):
        self.r.close()

    def stopped_predecessor(self, text="<project>left by a stopped worker</project>\n"):
        r = self.r
        tid, old, iss = r.issue("build:rk:pom")
        rel = iss["allowed_paths"][0]
        r.edit(rel, text)
        time.sleep(0.05)
        r.native.end_run(tid, "ready", "gave_up")
        time.sleep(0.05)
        return tid, old, rel

    def test_current_run_edits_survive_a_repeated_issue(self):
        """The architect's reproducer: old run ends, the replacement run is issued, edits an allowed file,
        asks for its issue again -- the edit is its own, byte for byte."""
        r = self.r
        tid, old, rel = self.stopped_predecessor()
        run, lock = r.native.claim(tid)
        NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock)   # archives the predecessor's
        self.assertEqual([x["run"] for x in r.board.records(tid, NC.ABANDONED)], [old])
        live = "<project>legitimate current-run repair</project>\n"
        r.edit(rel, live)
        # issue's own rule is unchanged: a re-issue over unjudged edits refuses ISSUE_BASELINE_DRIFT (it never
        # blesses them as a baseline). What changed is that the edits stay, attributed to nobody else.
        for replay in (True, False):
            with self.assertRaises(Refusal) as cm:
                NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock, replay_unchanged=replay)
            self.assertEqual(cm.exception.code, "ISSUE_BASELINE_DRIFT")
            self.assertEqual((r.root / rel).read_text(), live)
            self.assertEqual([x["run"] for x in r.board.records(tid, NC.ABANDONED)], [old])   # attribution unchanged

    def test_a_proven_predecessor_candidate_is_archived_before_restoration(self):
        r = self.r
        tid, old, rel = self.stopped_predecessor("<project>abandoned bytes</project>\n")
        run, lock = r.native.claim(tid)
        NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock)
        rec = r.board.records(tid, NC.ABANDONED)[0]
        body = json.loads(r.board.attachment(tid, rec["attachment"])[0])
        import base64
        self.assertEqual(base64.b64decode(body["files"][rel]).decode(), "<project>abandoned bytes</project>\n")
        self.assertEqual(git(r.root, "status", "--porcelain", "--", rel), "")
        # restart-safe: the same edit set aside twice is one record (keyed by its digest)
        self.assertEqual(len(r.board.records(tid, NC.ABANDONED)), 1)

    def test_uncertain_ownership_never_triggers_cleanup(self):
        r = self.r
        tid, old, rel = self.stopped_predecessor()
        # written before the predecessor's run started: not provably its own
        backdate(r.root / rel, 3600)
        run, lock = r.native.claim(tid)
        with self.assertRaises(Refusal) as cm:
            NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock)
        self.assertEqual(cm.exception.code, "ISSUE_BASELINE_DRIFT")
        self.assertIn("stopped worker", (r.root / rel).read_text())       # nothing discarded
        self.assertEqual(r.board.records(tid, NC.ABANDONED), [])

    def test_a_predecessor_without_a_native_end_never_triggers_cleanup(self):
        r = self.r
        tid, old, rel = self.stopped_predecessor()
        r.native.runs_[old]["ended_at"] = None                            # the run table does not say it ended
        run, lock = r.native.claim(tid)
        with self.assertRaises(Refusal):
            NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock)
        self.assertEqual(r.board.records(tid, NC.ABANDONED), [])

    def test_a_deletion_carries_no_time_and_is_not_cleaned(self):
        r = self.r
        tid, old, iss = r.issue("build:rk:pom")
        rel = iss["allowed_paths"][0]
        (r.root / rel).unlink()
        r.native.end_run(tid, "ready", "crashed")
        run, lock = r.native.claim(tid)
        with self.assertRaises(Refusal):
            NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock)
        self.assertFalse((r.root / rel).exists())

    def test_retained_and_unrelated_edits_are_never_cleaned(self):
        r = self.r
        tid, old, rel = self.stopped_predecessor()
        r.edit("src/main/java/com/acme/shop/Unrelated.java", "class Unrelated {}\n")
        run, lock = r.native.claim(tid)
        with self.assertRaises(Refusal):
            NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock)
        self.assertTrue((r.root / "src/main/java/com/acme/shop/Unrelated.java").exists())
        self.assertIn("stopped worker", (r.root / rel).read_text())
        # a retained candidate is the card's own: never abandoned
        (r.root / "src/main/java/com/acme/shop/Unrelated.java").unlink()
        r.board.record(tid, "pending", "pending:held", candidate=r.tree())
        self.assertIsNone(NC.park_abandoned(r.root, r.board, task_id=tid, run_id=run))


class Retirement(unittest.TestCase):
    def setUp(self):
        self.r = Run()
        self.r.release()
        self.p = self.r.root / LOOP_ISSUED
        self.p.parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.r.close()

    def projection(self, tid, run, extra=""):
        self.p.write_text(json.dumps({"task_id": tid, "cluster": "c:x",
                                      "idempotency_key": "outcome:v2:n1:o:c:x:issue1:r%d%s" % (run, extra)}))

    def test_a_new_claim_and_projection_during_retirement_survive(self):
        """The architect's reproducer: a claim and a new projection appear after the state check."""
        r = self.r
        tid, old, _ = r.issue("build:rk:pom")
        r.native.end_run(tid, "ready", "gave_up")
        self.projection(tid, old)
        real_rename, seen = os.rename, {}

        def rename(a, b):
            if str(a) == str(self.p) and "new" not in seen:           # the race lands between check and move
                run, _lock = r.native.claim(tid)
                self.projection(tid, run)
                seen["new"] = run
            return real_rename(a, b)
        os.rename = rename
        try:
            with self.assertRaises(Refusal) as cm:
                NC.retire_issuance(r.root, r.board, by="operator", reason="race")
        finally:
            os.rename = real_rename
        self.assertEqual(cm.exception.code, "ISSUANCE_CHANGED")
        doc = json.loads(self.p.read_text())
        self.assertTrue(doc["idempotency_key"].endswith(":r%d" % seen["new"]))    # the newer issuance survives
        self.assertEqual(r.board.records(tid, "issuance-retired"), [])
        self.assertEqual(list(self.p.parent.glob(self.p.name + NC.RETIRING + "*")), [])
        self.assertEqual(NC.issuance_state(r.root, r.board)["state"], "live")

    def test_a_missing_or_malformed_run_identity_is_never_expired(self):
        r = self.r
        tid, old, _ = r.issue("build:rk:pom")
        r.native.end_run(tid, "ready", "gave_up")
        for key in ("", "outcome:v2:n1:o:c:x", "outcome:v2:n1:o:c:x:issue1:rX"):
            self.p.write_text(json.dumps({"task_id": tid, "idempotency_key": key}))
            self.assertEqual(NC.issuance_state(r.root, r.board)["state"], "unbound", key)
            with self.assertRaises(Refusal):
                NC.retire_issuance(r.root, r.board, by="operator", reason="x")
            self.assertTrue(self.p.exists())
        self.projection(tid, 999)                                           # a run that is not this card's
        self.assertEqual(NC.issuance_state(r.root, r.board)["state"], "unbound")

    def test_an_interrupted_retirement_resumes_to_one_record_and_the_same_bytes(self):
        r = self.r
        tid, old, _ = r.issue("build:rk:pom")
        r.native.end_run(tid, "ready", "gave_up")
        self.projection(tid, old)
        body = self.p.read_bytes()
        real = NC._finish_retirement

        def crash(*a, **k):
            raise OSError("interrupted after the move")
        NC._finish_retirement = crash
        try:
            with self.assertRaises(OSError):
                NC.retire_issuance(r.root, r.board, by="operator", reason="x")
        finally:
            NC._finish_retirement = real
        self.assertFalse(self.p.exists())
        got = NC.retire_issuance(r.root, r.board, by="operator", reason="resume")
        self.assertEqual((r.root / got["retired"]).read_bytes(), body)
        self.assertEqual(len(r.board.records(tid, "issuance-retired")), 1)
        self.assertEqual(NC.retire_issuance(r.root, r.board, by="operator", reason="again")["state"], "none")
        self.assertEqual(len(r.board.records(tid, "issuance-retired")), 1)


class MediaType(unittest.TestCase):
    def same(self, a, b):
        self.assertEqual(canonical_media_type(a), canonical_media_type(b), (a, b))

    def differ(self, a, b):
        self.assertNotEqual(canonical_media_type(a), canonical_media_type(b), (a, b))

    def test_the_architects_quoted_counterexample_stays_distinct(self):
        self.differ('application/example; note="A; X=Y"', 'application/example; note="A; x=Y"')

    def test_equivalent_spellings(self):
        self.same("application/json; charset=utf-8", "application/json;charset=UTF-8")    # v29
        self.same("Application/JSON ; CHARSET=utf-8", "application/json;charset=UTF-8")
        self.same('application/json; charset="UTF-8"', "application/json; charset=utf-8")
        self.same('text/plain; format="flowed"', "text/plain; format=flowed")

    def test_escapes_semicolons_and_case_sensitive_values(self):
        self.same('a/b; q="x\\"y"', 'a/b; q="x\\"y"')
        self.differ('a/b; q="x\\"y"', 'a/b; q="x\\y"')
        self.differ('a/b; q="x;y"', "a/b; q=x; y=")                  # a semicolon inside a value is the value's
        self.differ("text/plain; format=Flowed", "text/plain; format=flowed")
        self.differ("a/b; p=1; q=2", "a/b; q=2; p=1")                # order kept: nothing invented

    def test_malformed_input_gains_no_equivalence(self):
        self.differ('a/b; q="unterminated', 'a/b; q="unterminated"')
        self.differ("a/b; q = 1", "a/b; q=1")                         # no whitespace around '='
        self.same('a/b; q="unterminated', 'a/b; q="unterminated')    # only itself

    def test_canonical_diff_uses_it(self):
        self.assertEqual(canonical_diff("header content-type application/json; charset=utf-8 vs application/json"),
                         canonical_diff("header content-type application/json;charset=UTF-8 vs application/json"))
        self.assertNotEqual(canonical_diff('header content-type a/b; n="A; X=Y" vs a/b'),
                            canonical_diff('header content-type a/b; n="A; x=Y" vs a/b'))


if __name__ == "__main__":
    unittest.main(verbosity=1)
