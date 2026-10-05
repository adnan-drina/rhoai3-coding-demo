#!/usr/bin/env python3
"""Land-time tests for human_home (Architect 112249ZA)."""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from human_home import human_home


class TestHumanHome(unittest.TestCase):
    def test_returns_existing_directory(self):
        got = human_home()
        self.assertTrue(got.is_dir(), got)
        self.assertNotEqual(str(got), "")

    def test_ignores_home_env(self):
        previous = os.environ.get("HOME")
        os.environ["HOME"] = "/tmp/not-the-os-account-home"
        try:
            got = human_home()
        finally:
            if previous is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = previous
        self.assertNotEqual(got, Path("/tmp/not-the-os-account-home"))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
