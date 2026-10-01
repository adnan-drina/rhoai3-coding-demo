#!/usr/bin/env python3
"""Attachment-backed control records (H-11 slice 2, v30 Kanban readability review 2026-10-01).

v30: 144 of 159 comments were `[native-control] {json}` records (94% of the thread's characters, the largest
55,495 chars); workers see the latest 30 comments capped at 2 KiB each. A card/v2 run writes each record as a
native attachment and comments one plain sentence plus a one-line reference. Readers take both forms in any
mix. These cases pin the compatibility contract; the whole native-board suite is also re-run with v2 records
(same lifecycle, budgets, ordering and acceptance decisions)."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from planner import native_control as NC  # noqa: E402
from planner.outcome_native import FakeNative  # noqa: E402

T = "t_1"


def board(fmt: str):
    native = FakeNative(Path(tempfile.mkdtemp(prefix="rec-v2-")))
    native.tasks[T] = {"id": T, "status": "running", "title": "x", "body": "", "idempotency_key": "k"}
    return NC.Board(native, author="implementer", record_format=fmt), native


ROWS = [{"check": "parity:sc:%d" % i, "state": ("pass", "fail", "unknown")[i % 3], "detail": "x" * 400} for i in range(90)]


class Records(unittest.TestCase):
    def test_a_v2_record_reads_back_as_the_same_logical_record_and_the_thread_shows_no_json(self):
        b1, _ = board("v1")
        b2, n2 = board("v2")
        r1 = b1.record(T, "schedule-measure", "schedule-measure:69:r2:b94d", run=69, revision=2, rows=ROWS)
        r2 = b2.record(T, "schedule-measure", "schedule-measure:69:r2:b94d", run=69, revision=2, rows=ROWS)
        self.assertEqual({k: v for k, v in r1.items() if k != "_id"}, {k: v for k, v in r2.items() if k != "_id"})
        body = n2.comment_rows(T)[0]["body"]
        self.assertNotIn("{", body)
        self.assertLess(len(body), 2048)                                  # fits the worker-context cap
        self.assertIn("30 passing, 30 failing, 30 not yet measurable", body)
        self.assertEqual(len(n2.attachments(T)), 1)

    def test_the_referencing_comment_id_orders_records_in_a_mixed_history(self):
        b, n = board("v1")
        b.record(T, "issue", "issue:1:1", run=1)
        b.record_format = "v2"
        b.record(T, "reject", "reject:1:1", run=1, reason="compile red")
        b.record_format = "v1"
        b.record(T, "accept-commit", "accept-commit:1:x", run=1, outcome_accepted=True, commit="abc")
        got = b.records(T)
        self.assertEqual([r["kind"] for r in got], ["issue", "reject", "accept-commit"])
        ids = [r["_id"] for r in got]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(ids, [c["id"] for c in n.comment_rows(T)])      # the comment id, never an attachment id
        self.assertEqual([r["kind"] for r in b.records(T, "reject")], ["reject"])

    def test_a_repeated_key_is_recorded_once(self):
        b, n = board("v2")
        a = b.record(T, "issue", "issue:1:1", run=1)
        again = b.record(T, "issue", "issue:1:1", run=1, extra="ignored")
        self.assertEqual(a, again)
        self.assertEqual((len(n.comment_rows(T)), len(n.attachments(T))), (1, 1))

    def test_missing_or_mismatched_evidence_refuses_never_disappears(self):
        b, n = board("v2")
        b.record(T, "issue", "issue:1:1", run=1)
        att = n.attachments(T)[0]
        Path(att["stored_path"]).write_bytes(b'{"key":"issue:1:1","kind":"issue","run":2,"v":1}')
        fresh = NC.Board(n, author="implementer")                          # no cache: reads the board
        with self.assertRaises(NC.Refusal) as cm:
            fresh.records(T)
        self.assertEqual(cm.exception.code, "RECORD_EVIDENCE_MISMATCH")
        n.attach_[T] = []
        with self.assertRaises(NC.Refusal) as cm:
            NC.Board(n).records(T)
        self.assertEqual(cm.exception.code, "RECORD_EVIDENCE_MISSING")

    def test_an_attachment_of_another_task_or_record_is_not_accepted(self):
        b, n = board("v2")
        b.record(T, "issue", "issue:1:1", run=1)
        ref = n.comment_rows(T)[0]["body"].splitlines()[-1]
        n.tasks["t_2"] = {"id": "t_2", "status": "todo", "title": "y", "body": "", "idempotency_key": "k2"}
        n.comment("t_2", "copied\n\n" + ref)
        with self.assertRaises(NC.Refusal) as cm:
            NC.Board(n).records("t_2")
        self.assertEqual(cm.exception.code, "RECORD_EVIDENCE_MISSING")    # resolved on its own task only

    def test_an_interrupted_write_has_no_effect_and_the_retry_reuses_the_attachment(self):
        b, n = board("v2")
        n.fail_after["comment"] = 0                                      # the comment write dies after the attach
        with self.assertRaises(Exception):
            b.record(T, "issue", "issue:1:1", run=1)
        self.assertEqual(b.records(T), [])                                # attachment alone: no record
        self.assertEqual(len(n.attachments(T)), 1)
        b.record(T, "issue", "issue:1:1", run=1)
        self.assertEqual(len(n.attachments(T)), 1)                        # identical bytes reused, not attached twice
        self.assertEqual([r["key"] for r in b.records(T)], ["issue:1:1"])

    def test_a_worker_cannot_write_a_reference_or_attach_a_record_file(self):
        hook = (HERE.parents[1] / "kernel" / "pre_tool_call.sh").read_text()
        self.assertIn("rec-[0-9a-f]{12}-[0-9a-f]{12}", hook)
        self.assertIn('"[native-control]" in json.dumps(inp)', hook)        # a ref line carries the marker too


class LifecycleUnderV2(unittest.TestCase):
    def test_the_native_board_suite_passes_with_v2_records(self):
        """Same lifecycle, budgets, ordering and acceptance decisions with attachment-backed records."""
        defaults = NC.Board.__init__.__kwdefaults__
        saved = defaults["record_format"]
        defaults["record_format"] = "v2"
        try:
            spec = importlib.util.spec_from_file_location("native_board_v2", HERE / "native_board.test.py")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
            result = unittest.TextTestRunner(verbosity=0, stream=open("/dev/null", "w")).run(
                unittest.defaultTestLoader.loadTestsFromModule(mod))
        finally:
            defaults["record_format"] = saved
        self.assertTrue(result.wasSuccessful(), [str(t) for t, _ in result.failures + result.errors])
        self.assertGreater(result.testsRun, 40)


if __name__ == "__main__":
    unittest.main()
