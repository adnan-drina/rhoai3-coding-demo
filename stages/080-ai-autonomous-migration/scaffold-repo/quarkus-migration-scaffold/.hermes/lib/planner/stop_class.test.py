#!/usr/bin/env python3
"""M-5 stop classification over real v30/v31 native run rows (texts as the board recorded them).

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/stop_class.test.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.stop_class import classify, summarize  # noqa: E402


def c(outcome, text=""):
    got = classify({"outcome": outcome, "error": text})
    return got["class"], got["subtype"]


class Classes(unittest.TestCase):
    def test_v31_rows(self):
        self.assertEqual(c("blocked", "ISSUE_BASELINE_DRIFT: native_gate.py refuses to issue because the product tree differs "
                                      "from HEAD 480091b"), ("harness-refusal", "ISSUE_BASELINE_DRIFT"))
        self.assertEqual(c("blocked", "VERIFICATION_PENDING u:cd4a81a71d9f cause=unassessable-scope"),
                         ("harness-refusal", "VERIFICATION_PENDING"))
        self.assertEqual(c("blocked", "OWNER_REPAIR_PENDING: behavior:http:x depends on followup:y"), ("dependency-wait", ""))
        self.assertEqual(c("blocked", "native_gate.py issue refused: OWNER_REPAIR_PENDING. behavior"), ("dependency-wait", ""))
        self.assertEqual(c("blocked", "PARITY REFUSAL: sc:create-refused-pets and sc:update-pets-2 cannot be repaired within this "
                                      "card's write set"), ("worker-blocked", "scope"))
        self.assertEqual(c("blocked", "STOP RULE APPLIES: two acceptance runs with identical obligations"), ("worker-blocked", "diagnosis"))
        self.assertEqual(c("crashed", "worker exited cleanly (rc=0) without calling kanban_complete or kanban_block — protocol "
                                      "violation."), ("worker-crash", "protocol"))
        self.assertEqual(c("crashed", "STOP WORKER_TOOL_LOOP: tool terminal, guardrail identical_call_streak_halt, count 5"),
                         ("worker-crash", "tool-loop"))
        self.assertEqual(c("timed_out", "elapsed 7209s > limit 7200s"), ("worker-crash", "timeout"))
        self.assertEqual(c("review_requested", "M3 COMPILE — implement"), ("completed", ""))
        self.assertEqual(c("changes_requested", "keep the source profile name"), ("review-rework", ""))

    def test_v30_rows(self):
        self.assertEqual(c("gave_up", "STOP WORKER_TOOL_LOOP: tool read_file"), ("worker-crash", "tool-loop"))
        self.assertEqual(c("reclaimed", "manual_reclaim: operator I-3: run enumerated brief"), ("operator", "reclaim"))

    def test_provider_and_source_and_unknown(self):
        self.assertEqual(c("crashed", "HTTP 429 Too Many Requests from the model gateway"), ("provider", ""))
        self.assertEqual(c("rate_limited", ""), ("provider", ""))
        self.assertEqual(c("blocked", "SOURCE_CAPTURE_MISSING: no qualified capture for sc:x"), ("source-qualification", ""))
        self.assertEqual(c("weird_outcome", "x"), ("unclassified", "weird_outcome"))     # named, never folded

    def test_summary_counts_by_class_and_keeps_each_run(self):
        rows = [{"id": 1, "task_id": "t_a", "outcome": "crashed", "error": "STOP WORKER_TOOL_LOOP: x"},
                {"id": 2, "task_id": "t_b", "outcome": "blocked", "error": "ISSUE_BASELINE_DRIFT: y"},
                {"id": 3, "task_id": "t_c", "outcome": "blocked", "error": "ISSUE_BASELINE_DRIFT: y"},
                {"id": 4, "task_id": "t_d", "outcome": None, "status": "running"}]
        got = summarize(rows)
        self.assertEqual(got["by_class"]["harness-refusal"]["count"], 2)
        self.assertEqual(got["by_class"]["worker-crash"]["runs"], ["t_a/run 1 tool-loop"])
        self.assertNotIn("running", got["by_class"])


if __name__ == "__main__":
    unittest.main()
