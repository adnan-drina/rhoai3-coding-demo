#!/usr/bin/env python3
"""Admission tests for the two M4 pre-verdict asserts (Architect 142524ZA)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINNED = HERE / "assert-pinned-gates-ran.py"
TREE = (
    HERE.parent.parent
    / "assert-retrievable-tree"
    / "scripts"
    / "assert-retrievable-tree.py"
)


def run_pinned(root: Path, extra: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.pop("M4_CARD_SKILLS", None)
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(PINNED), str(root), *extra],
        text=True,
        capture_output=True,
        env=merged,
    )


def run_tree(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TREE), str(root)],
        text=True,
        capture_output=True,
    )


def git(root: Path, *args: str) -> None:
    subprocess.check_call(
        ["git", "-C", str(root), *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class PinnedGatesTests(unittest.TestCase):
    def test_m4_card_skills_env_is_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = run_pinned(
                root,
                ["--skills", "check-domain-parity"],
                env={"M4_CARD_SKILLS": "check-spec-readiness,assert-retrievable-tree"},
            )
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("M4_CARD_SKILLS override is OBJECT", proc.stderr)

    def test_missing_skills_list_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = os.environ.copy()
            env.pop("M4_CARD_SKILLS", None)
            proc = subprocess.run(
                [sys.executable, str(PINNED), str(root)],
                text=True,
                capture_output=True,
                env=env,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("missing list is fail-closed", proc.stderr)

    def test_silence_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = run_pinned(
                root, ["--skills", "check-domain-parity,spring-to-quarkus-patterns"]
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("check-domain-parity", proc.stderr)
            self.assertIn("silence fails", proc.stderr)

    def test_named_verdict_is_not_a_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "evidence" / "verdicts" / "m4.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "gate": "check-domain-parity",
                        "ran": True,
                        "verdict": "INCONCLUSIVE",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            proc = run_pinned(root, ["--skills", "check-domain-parity"])
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("self-attested", proc.stderr)

    def test_runner_receipt_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = (
                root
                / "evidence"
                / "receipts"
                / "gates"
                / "check-domain-parity.json"
            )
            path.parent.mkdir(parents=True)
            argv = ["python3", "check-domain-parity.py", str(root)]
            digest = __import__("hashlib").sha256(
                __import__("json")
                .dumps({"argv": argv, "extra": ""}, sort_keys=True, separators=(",", ":"))
                .encode()
            ).hexdigest()
            path.write_text(
                json.dumps(
                    {
                        "gate": "check-domain-parity",
                        "cmd": " ".join(argv),
                        "argv": argv,
                        "rc": 0,
                        "input_digest": digest,
                        "producer": "check-domain-parity.py",
                        "run_id": "test",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            proc = run_pinned(root, ["--skills", "check-domain-parity"])
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_dest5_ran_false_is_not_a_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = (
                root
                / "evidence"
                / "verdicts"
                / "refusals"
                / "check-domain-parity.json"
            )
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps({"ran": False, "reason": "specimen-n/a: no DB"}) + "\n",
                encoding="utf-8",
            )
            proc = run_pinned(root, ["--skills", "check-domain-parity"])
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("no run evidence", proc.stderr)

    def test_missing_ran_is_not_a_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "evidence" / "verdicts" / "m4.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps({"gate": "check-domain-parity", "verdict": "INCONCLUSIVE"})
                + "\n",
                encoding="utf-8",
            )
            proc = run_pinned(root, ["--skills", "check-domain-parity"])
            self.assertNotEqual(proc.returncode, 0)

    def test_provisional_accept_artifact_is_not_a_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "evidence" / "verdicts" / "check-release-readiness.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "gate": "check-release-readiness",
                        "ran": True,
                        "verdict": "PROVISIONAL_ACCEPT",
                        "ship": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            proc = run_pinned(root, ["--skills", "check-release-readiness"])
            self.assertNotEqual(proc.returncode, 0)

    def test_specimen_na_run_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            argv = ["python3", "check-domain-parity.py", str(root)]
            digest = __import__("hashlib").sha256(
                __import__("json")
                .dumps({"argv": argv, "extra": ""}, sort_keys=True, separators=(",", ":"))
                .encode()
            ).hexdigest()
            path = (
                root
                / "evidence"
                / "receipts"
                / "gates"
                / "check-domain-parity.json"
            )
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "gate": "check-domain-parity",
                        "cmd": " ".join(argv),
                        "argv": argv,
                        "rc": 0,
                        "input_digest": digest,
                        "producer": "check-domain-parity.py",
                        "run_id": "specimen-n/a: no DB",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            proc = run_pinned(root, ["--skills", "check-domain-parity"])
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_minted_on_this_card_verdict_is_not_a_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "evidence" / "verdicts" / "check-domain-parity.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "gate": "check-domain-parity",
                        "ran": True,
                        "verdict": "INCONCLUSIVE",
                        "task_id": "t_ecdb4eb9",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            proc = run_pinned(
                root,
                ["--skills", "check-domain-parity", "--card-id", "t_ecdb4eb9"],
            )
            self.assertNotEqual(proc.returncode, 0)

    def test_self_pin_writes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = run_pinned(root, ["--skills", "assert-pinned-gates-ran"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            written = (
                root / "evidence" / "receipts" / "gates" / "assert-pinned-gates-ran.json"
            )
            self.assertTrue(written.is_file())
            doc = json.loads(written.read_text(encoding="utf-8"))
            self.assertEqual(doc.get("gate"), "assert-pinned-gates-ran")
            self.assertIn("argv", doc)
            self.assertEqual(doc.get("producer"), "assert-pinned-gates-ran.py")


class PinnedGateWritersTests(unittest.TestCase):
    """Architect 091125ZA: every pinned leaf has a receipt-writing entrypoint."""

    GATES = Path(__file__).resolve().parents[2]
    PRE = (
        GATES
        / "check-release-readiness"
        / "scripts"
        / "run-m4-pre-verdict.sh"
    )

    def test_pinned_leaves_have_writers(self) -> None:
        spec = Path(__file__).resolve().parent / "assert-pinned-gates-ran.py"
        text = spec.read_text(encoding="utf-8")
        self.assertIn("PINNED_GATE_LEAVES", text)
        domain = (
            self.GATES / "check-domain-parity" / "scripts" / "check-product-tests.py"
        ).read_text(encoding="utf-8")
        release = (
            self.GATES
            / "check-release-readiness"
            / "scripts"
            / "check-test-toolchain.py"
        ).read_text(encoding="utf-8")
        spec_cov = (
            self.GATES.parent
            / "sdd"
            / "check-spec-readiness"
            / "scripts"
            / "check-partition-coverage.py"
        ).read_text(encoding="utf-8")
        pre = self.PRE.read_text(encoding="utf-8")
        self.assertIn("--write-receipt", domain)
        self.assertIn("check-domain-parity", domain)
        self.assertIn("--write-receipt", release)
        self.assertIn("check-release-readiness", release)
        self.assertIn("--write-receipt", spec_cov)
        self.assertIn("check-spec-readiness", spec_cov)
        self.assertIn("run_gate assert-retrievable-tree", pre)
        self.assertIn("write_self_verdict", spec.read_text(encoding="utf-8"))

    def test_pre_verdict_feeds_before_assert(self) -> None:
        pre = self.PRE.read_text(encoding="utf-8")
        feed = pre.find("run_feed_gate check-domain-parity")
        pin = pre.find('python3 "${PINNED}"')
        self.assertGreater(feed, 0)
        self.assertGreater(pin, feed)


class RetrievableTreeTests(unittest.TestCase):
    def _repo(self, tmp: str) -> Path:
        root = Path(tmp)
        git(root, "init", "-q")
        git(root, "config", "user.email", "test@example.com")
        git(root, "config", "user.name", "test")
        (root / "src" / "main" / "java").mkdir(parents=True)
        (root / "src" / "main" / "java" / "App.java").write_text(
            "class App {}\n", encoding="utf-8"
        )
        (root / "pom.xml").write_text("<project/>\n", encoding="utf-8")
        git(root, "add", "src", "pom.xml")
        git(root, "commit", "-q", "-m", "base")
        return root

    def test_clean_src_pom_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            proc = run_tree(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            written = root / "evidence" / "verdicts" / "assert-retrievable-tree.json"
            self.assertTrue(written.is_file())

    def test_untracked_src_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            (root / "src" / "test" / "java").mkdir(parents=True)
            (root / "src" / "test" / "java" / "NewTest.java").write_text(
                "class NewTest {}\n", encoding="utf-8"
            )
            proc = run_tree(root)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("untracked or uncommitted", proc.stderr)

    def test_dirty_env_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            (root / ".env").write_text("SECRET=1\n", encoding="utf-8")
            proc = run_tree(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
