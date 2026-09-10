#!/usr/bin/env python3
"""Negative controls for M4 test-report snapshot + surefire parse."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP = HERE / "snapshot-m4-test-reports.py"
SURE = HERE / "assert-surefire-results.py"

DEST5_FAILING = """\
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.demo.HealthTest" tests="1" failures="1" errors="0" skipped="0" time="0.2">
  <testcase name="healthEndpoint" classname="com.demo.HealthTest" time="0.1">
    <failure message="Status 404"/>
  </testcase>
</testsuite>
"""
PASSING = """\
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.demo.GreetingResourceTest" tests="2" failures="0" errors="0" skipped="0" time="0.1">
  <testcase name="testHelloEndpoint" classname="com.demo.GreetingResourceTest" time="0.05"/>
  <testcase name="testGreetingEndpoint" classname="com.demo.GreetingResourceTest" time="0.05"/>
</testsuite>
"""


def run_py(script: Path, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), str(root)],
        text=True,
        capture_output=True,
    )


SKIPPED = """\
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.demo.GreetingResourceTest" tests="1" failures="0" errors="0" skipped="1" time="0.0">
  <testcase name="testHelloEndpoint" classname="com.demo.GreetingResourceTest" time="0.0">
    <skipped message="disabled while migrating"/>
  </testcase>
</testsuite>
"""
NO_CASES = """\
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.demo.GreetingResourceTest" tests="0" failures="0" errors="0" skipped="0" time="0.0"/>
"""


def write_source(root: Path, dotted: str) -> None:
    path = root / "src" / "test" / "java" / (dotted.replace(".", "/") + ".java")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("class X {}\n", encoding="utf-8")


def write_xml(root: Path, name: str, body: str) -> None:
    path = root / "target" / "surefire-reports" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


class SnapshotAndSurefireTests(unittest.TestCase):
    def test_absent_reports_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = run_py(SURE, root)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("fail closed", proc.stderr)

    def test_dest5_failures_one_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_xml(root, "TEST-com.demo.HealthTest.xml", DEST5_FAILING)
            self.assertEqual(run_py(SNAP, root).returncode, 0)
            proc = run_py(SURE, root)
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("Failures=1", proc.stderr)

    def test_passing_reports_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_xml(root, "TEST-com.demo.GreetingResourceTest.xml", PASSING)
            self.assertEqual(run_py(SNAP, root).returncode, 0)
            proc = run_py(SURE, root)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_skipped_case_refuses(self) -> None:
        """A skipped case is not a passed case; @Disabled must not read green."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_xml(root, "TEST-com.demo.GreetingResourceTest.xml", SKIPPED)
            proc = run_py(SURE, root)
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("skipped case", proc.stderr)
            self.assertIn("GreetingResourceTest.testHelloEndpoint", proc.stderr)

    def test_no_executed_case_refuses(self) -> None:
        """Zero failures over zero executions is the same silence as no report."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_xml(root, "TEST-com.demo.GreetingResourceTest.xml", NO_CASES)
            proc = run_py(SURE, root)
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("no executed case", proc.stderr)

    def test_reports_must_belong_to_this_tree(self) -> None:
        """Green reports about classes this destination does not have prove nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_source(root, "com.demo.model.ValidatorTests")
            write_xml(root, "TEST-com.demo.GreetingResourceTest.xml", PASSING)
            proc = run_py(SURE, root)
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("no executed case belongs to a test source in this tree", proc.stderr)
            # the control: the same reports pass once the tree owns the class
            write_source(root, "com.demo.GreetingResourceTest")
            proc = run_py(SURE, root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("executed from this tree: com.demo.GreetingResourceTest", proc.stderr)
            # a source the reports never name is stated, not assumed
            self.assertIn("no case named for com.demo.model.ValidatorTests", proc.stderr)

    def test_snapshot_survives_live_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_xml(root, "TEST-com.demo.HealthTest.xml", DEST5_FAILING)
            self.assertEqual(run_py(SNAP, root).returncode, 0)
            shutil.rmtree(root / "target")
            proc = run_py(SURE, root)
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("Failures=1", proc.stderr)
            manifest = json.loads(
                (root / "evidence" / "m4-pre-rebuild" / "manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertGreater(manifest["snapshot_xml"], 0)

    def test_second_snapshot_does_not_overwrite_with_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_xml(root, "TEST-com.demo.HealthTest.xml", DEST5_FAILING)
            self.assertEqual(run_py(SNAP, root).returncode, 0)
            shutil.rmtree(root / "target")
            proc = run_py(SNAP, root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            manifest = json.loads(
                (root / "evidence" / "m4-pre-rebuild" / "manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(manifest["kept_existing_snapshot"])
            self.assertNotEqual(run_py(SURE, root).returncode, 0)


if __name__ == "__main__":
    unittest.main()
