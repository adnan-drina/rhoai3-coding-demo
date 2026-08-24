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

    def test_named_verdict_passes(self) -> None:
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
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_refusal_specimen_na_passes(self) -> None:
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
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_idle_refusal_without_reason_fails(self) -> None:
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
            path.write_text(json.dumps({"ran": False}) + "\n", encoding="utf-8")
            proc = run_pinned(root, ["--skills", "check-domain-parity"])
            self.assertNotEqual(proc.returncode, 0)

    def test_self_pin_writes_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = run_pinned(root, ["--skills", "assert-pinned-gates-ran"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            written = root / "evidence" / "verdicts" / "assert-pinned-gates-ran.json"
            self.assertTrue(written.is_file())
            doc = json.loads(written.read_text(encoding="utf-8"))
            self.assertEqual(doc.get("gate"), "assert-pinned-gates-ran")
            self.assertNotEqual(doc.get("verdict"), "PROVISIONAL_ACCEPT")


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
