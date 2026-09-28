#!/usr/bin/env python3
"""M4 must not close over the enabled-only failure seen on v10."""
import json
import tempfile
import unittest
from pathlib import Path

from m4_parity import measure, verdict_issues


class ModeParity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def mode(self, mode, verdict, artifact="same-artifact"):
        suffix = "" if mode == "disabled" else "-enabled"
        directory = self.root / "verification/parity"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ("receipt%s.json" % suffix)).write_text(json.dumps({
            "schema": "rhoai3.parity-receipt/v1", "security_mode": mode, "verdict": verdict}))
        (directory / ("_run%s.json" % suffix)).write_text(json.dumps({
            "security_mode": mode, "ok": True, "scenario_filter": [],
            "receipt": {"composed_by_this_run": True}, "artifact": {"sha256": artifact}}))

    def verdict(self, token="PROVISIONAL_ACCEPT"):
        return {"verdict": token, "failed_floors": [], "floors": [],
                "parity_receipt_sha256_by_mode": measure(self.root)["receipt_sha256_by_mode"]}

    def test_enabled_failure_cannot_be_coverage_gap(self):
        self.mode("disabled", "INCONCLUSIVE")
        self.mode("enabled", "FAIL")
        self.assertEqual(measure(self.root)["rc"], 1)
        self.assertIn("ACCEPT_WITH_PARITY_FAILURE", " ".join(verdict_issues(self.verdict(), self.root)))
        self.assertFalse(verdict_issues(self.verdict("REFUSE"), self.root))

    def test_source_coverage_gap_does_not_become_product_failure(self):
        self.mode("disabled", "INCONCLUSIVE")
        self.mode("enabled", "INCONCLUSIVE")
        self.assertEqual(measure(self.root)["rc"], 0)
        self.assertFalse(verdict_issues(self.verdict(), self.root))

    def test_enabled_receipt_cannot_change_after_binding(self):
        self.mode("disabled", "PASS")
        self.mode("enabled", "PASS")
        bound = self.verdict()
        self.mode("enabled", "INCONCLUSIVE")
        self.assertIn("M4_MODE_PARITY_BINDING", " ".join(verdict_issues(bound, self.root)))

    def test_modes_require_same_artifact_and_complete_runs(self):
        self.mode("disabled", "PASS")
        self.mode("enabled", "PASS", artifact="other-artifact")
        self.assertEqual(measure(self.root)["rc"], 2)
        self.mode("enabled", "PASS")
        run = self.root / "verification/parity/_run-enabled.json"
        doc = json.loads(run.read_text())
        doc["scenario_filter"] = ["one-scenario"]
        run.write_text(json.dumps(doc))
        self.assertEqual(measure(self.root)["rc"], 2)

    def test_candidate_receipt_cannot_borrow_full_runner(self):
        self.mode("disabled", "INCONCLUSIVE")
        self.mode("enabled", "INCONCLUSIVE")
        self.assertEqual(measure(self.root)["rc"], 0)
        receipt = self.root / "verification/parity/receipt-enabled.json"
        doc = json.loads(receipt.read_text())
        doc["binding"] = {"mode": "candidate", "candidate_sha256": "b" * 64, "card": "t_candidate_b"}
        receipt.write_text(json.dumps(doc))
        result = measure(self.root)
        self.assertEqual(result["rc"], 2)
        self.assertTrue(any("candidate receipt is paired with a full-mode runner" in e for e in result["errors"]))

    def test_existing_enabled_capture_requires_enabled_measurement(self):
        self.mode("disabled", "PASS")
        capture = self.root / "verification/source-oracles/scenarios-enabled"
        capture.mkdir(parents=True)
        (capture / "scenario.json").write_text("{}")
        self.assertEqual(measure(self.root)["rc"], 2)
        self.assertTrue(verdict_issues(self.verdict(), self.root))

    def test_default_failure_cannot_close_either(self):
        self.mode("disabled", "FAIL")
        self.assertTrue(verdict_issues(self.verdict(), self.root))

    def test_read_oracle_only_disabled_is_not_full_mode_against_enabled(self):
        """Empty scenario_filter is not a full comparison. A disabled
        read-oracle-only run plus an enabled full run of the same artifact
        must not satisfy check-mode-parity."""
        self.mode("disabled", "PASS")
        self.mode("enabled", "PASS")
        run = self.root / "verification/parity/_run.json"
        doc = json.loads(run.read_text())
        doc["scenario_filter"] = []
        doc["scenarios"] = {"declared": 3, "selected": 0}
        doc["read_oracles"] = {"ran": False, "requested": ["ep:x.Vet#list():http"], "rerun": []}
        run.write_text(json.dumps(doc))
        result = measure(self.root)
        self.assertEqual(result["rc"], 2)
        self.assertTrue(any("full-mode" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
