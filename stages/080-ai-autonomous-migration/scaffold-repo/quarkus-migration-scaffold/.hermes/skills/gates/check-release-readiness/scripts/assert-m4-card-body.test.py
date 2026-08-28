#!/usr/bin/env python3
"""Negative control: dest-5 M4 body with a pre-specified token must refuse."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "assert-m4-card-body.py"

DEST5 = (
    "Acceptance: O1/O2/O3. Token: PROVISIONAL_ACCEPT, ship: false. "
    "Do not repair HealthTest."
)
DEST4 = (
    "M4 acceptance; verdict is O1/O2/O3 over the built artefact. "
    "Do not name a verdict token."
)


def run_body(text: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("M4_CARD_BODY", None)
    env.pop("HERMES_KANBAN_TASK", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--body", text],
        text=True,
        capture_output=True,
        env=env,
    )


class M4CardBodyTests(unittest.TestCase):
    def test_dest5_token_refuses(self) -> None:
        proc = run_body(DEST5)
        self.assertNotEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("verdict token", proc.stderr)

    def test_dest4_acceptance_only_passes(self) -> None:
        proc = run_body(DEST4)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_missing_body_fail_closed(self) -> None:
        env = os.environ.copy()
        env.pop("M4_CARD_BODY", None)
        env.pop("HERMES_KANBAN_TASK", None)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)],
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("missing M4 card body", proc.stderr)

    def test_env_body_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "body.md"
            path.write_text(DEST5, encoding="utf-8")
            env = os.environ.copy()
            env.pop("M4_CARD_BODY", None)
            env.pop("HERMES_KANBAN_TASK", None)
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--body-file", str(path)],
                text=True,
                capture_output=True,
                env=env,
            )
            self.assertNotEqual(proc.returncode, 0)

    def test_ship_alone_refuses(self) -> None:
        proc = run_body("Acceptance only. ship: false")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("ship:", proc.stderr)


if __name__ == "__main__":
    unittest.main()
