#!/usr/bin/env python3
"""D-1: the source capture engine and its seed, one rule for the derivation and the destination baseline.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/source_engine.test.py
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.source_engine import capture_engine, seed, source_profile_for  # noqa: E402


def source(td: Path, engines, profiles) -> Path:
    for e in engines:
        d = td / "src" / "main" / "resources" / "db" / e
        d.mkdir(parents=True, exist_ok=True)
        (d / "populateDB.sql").write_text("INSERT INTO t VALUES (1);\n")
    for e, suf in profiles:
        (td / "src" / "main" / "resources" / ("application-%s%s" % (e, suf))).write_text("x=1\n")
    return td


class Engine(unittest.TestCase):
    def check(self, dest, declared):
        with tempfile.TemporaryDirectory() as t:
            copy = source(Path(t), [declared, dest], [(dest, ".properties")])
            ds = {"db_kind": dest, "source_baseline_db_kind": declared}
            got = capture_engine(ds, copy)
            self.assertEqual((got["engine"], got["mode"]), (declared, "declared"))           # the default: ADR-017
            got = capture_engine(dict(ds, source_capture_engine="destination"), copy)
            self.assertEqual((got["engine"], got["mode"], got["profile"]), (dest, "destination", dest))
            self.assertEqual(got["profile_file"], "src/main/resources/application-%s.properties" % dest)
            self.assertEqual(seed(copy, got["engine"])[1], dest)                            # the seed follows the engine
        with tempfile.TemporaryDirectory() as t:
            copy = source(Path(t), [declared], [])                                          # no profile for the destination
            got = capture_engine({"db_kind": dest, "source_baseline_db_kind": declared, "source_capture_engine": "destination"}, copy)
            self.assertEqual((got["engine"], got["mode"]), (declared, "declared"))
            self.assertIn("ships no profile for the destination engine %s" % dest, got["why"])
            self.assertEqual(source_profile_for(copy, dest), "")

    def test_postgresql_over_hsqldb(self):
        self.check("postgresql", "hsqldb")

    def test_a_renamed_engine_pair(self):
        self.check("mariadb", "h2")

    def test_an_unknown_mode_is_the_declared_engine(self):
        self.assertEqual(capture_engine({"db_kind": "x", "source_baseline_db_kind": "y", "source_capture_engine": "both"})["engine"], "y")


if __name__ == "__main__":
    unittest.main()
