#!/usr/bin/env python3
"""Synthetic fixtures: check-factory-m5 reuses canonical G-1 evaluation."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
HERMES = HERE.parents[3]
CHECKER = HERE / "check-factory-m5.py"
if str(HERMES / "lib") not in sys.path:
    sys.path.insert(0, str(HERMES / "lib"))

from planner.canonical import write_canonical  # noqa: E402


def _pin_data(candidate_sha="cc" * 20):
    sha = candidate_sha
    digest, tree = "e" * 64, "a" * 64
    return {
        "schema": "migration/g1-kill-ratio-pin/v2-dual-denominator",
        "status": "PINNED",
        "candidate_sha": sha,
        "identity": {"candidate_sha": sha, "tree_sha256": tree},
        "scope": "measured live PIT slice",
        "measurement": {
            "generated": 100, "attempted": 50, "killed": 40, "survived": 10, "timed_out": 0,
            "coverage_ratio": 0.5, "kill_attempted_ratio": 0.8, "kill_generated_ratio": 0.4,
            "source": "target/pit-reports/mutations.xml", "candidate_sha": sha,
            "mutations_xml_sha256": digest,
        },
        "provenance": {
            "schema": "migration/pit-measurement/v1",
            "candidate_sha": sha,
            "mutations_xml_sha256": digest,
            "tree_sha256": tree,
        },
        "threshold": {
            "coverage_min": 0.41, "kill_attempted_min": 0.60, "kill_generated_min": 0.38,
            "source": "declared_engineering_target", "rationale": "synthetic fixture floor",
            "folklore": False,
        },
        "evaluation_against_measurement": {"pass": True},
        "g1_kill_ratio": "PASS",
        "g1_kill_ratio_threshold_pinned": True,
    }


def _write_pin(root: Path, data: dict) -> None:
    (root / "evidence/derived").mkdir(parents=True, exist_ok=True)
    write_canonical(root / "evidence/derived/g1-kill-ratio-pin.json", data)
    sha = str(data.get("candidate_sha") or "").strip()
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    digest = str(measurement.get("mutations_xml_sha256") or "").strip()
    identity = data.get("identity") if isinstance(data.get("identity"), dict) else {}
    provenance = data.get("provenance") if isinstance(data.get("provenance"), dict) else {}
    tree = str(provenance.get("tree_sha256") or identity.get("tree_sha256") or "").strip()
    if sha and len(digest) == 64 and len(tree) == 64:
        write_canonical(root / "evidence/derived/pit-measurement.json", {
            "schema": "migration/pit-measurement/v1",
            "candidate_sha": sha,
            "mutations_xml_sha256": digest,
            "tree_sha256": tree,
            "source": "target/pit-reports/mutations.xml",
        })


def _factory_claim(root: Path) -> None:
    (root / "evidence/preflight").mkdir(parents=True, exist_ok=True)
    write_canonical(root / "evidence/preflight/factory.json", {
        "phase": "FACTORY", "status": "factory_ready",
    })


def _accept_verdict(root: Path, sha: str) -> None:
    (root / "evidence/verdicts").mkdir(parents=True, exist_ok=True)
    write_canonical(root / "evidence/verdicts/m5-verdict.json", {
        "schema": "rhoai3.m5-verdict/v1", "gate": "compose-m5-verdict",
        "phase": "M5", "verdict": "ACCEPT", "accept_kind": "full", "ship": True,
        "g1_kill_ratio": "PASS", "g1_kill_ratio_threshold_pinned": True,
        "candidate_sha": sha,
    })
    write_canonical(root / "verification/delivery/candidate.json", {
        "schema": "rhoai3.m5-candidate/v1", "candidate_sha": sha, "ok": True,
    })


def _run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), str(root)],
        capture_output=True, text=True, check=False,
    )


class FactoryM5G1(unittest.TestCase):
    def test_idle_without_factory_claim(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        proc = _run(root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("idle", proc.stdout)

    def test_schema_name_and_pass_token_are_not_pin_evidence(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        sha = "cc" * 20
        _factory_claim(root)
        _accept_verdict(root, sha)
        _write_pin(root, {
            "schema": "migration/g1-kill-ratio-pin/v2-dual-denominator",
            "g1_kill_ratio": "PASS",
            "g1_kill_ratio_threshold_pinned": True,
            "status": "PINNED",
        })
        proc = _run(root)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("verified G-1", proc.stderr)

    def test_verdict_fields_are_not_pin_evidence(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        sha = "cc" * 20
        _factory_claim(root)
        _accept_verdict(root, sha)
        proc = _run(root)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("verified G-1", proc.stderr)

    def test_foreign_pin_is_rejected(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        sha = "cc" * 20
        _factory_claim(root)
        _accept_verdict(root, sha)
        data = _pin_data(candidate_sha="ff" * 20)
        _write_pin(root, data)
        proc = _run(root)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("verified G-1", proc.stderr)

    def test_verified_bound_pin_passes_factory(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        sha = "cc" * 20
        _factory_claim(root)
        _accept_verdict(root, sha)
        _write_pin(root, _pin_data(candidate_sha=sha))
        proc = _run(root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("full ACCEPT", proc.stdout)


if __name__ == "__main__":
    unittest.main()
