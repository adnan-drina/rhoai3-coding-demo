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
<testsuite name="com.demo.CatalogResourceTest" tests="2" failures="0" errors="0" skipped="0" time="0.1">
  <testcase name="listItems" classname="com.demo.CatalogResourceTest" time="0.05"/>
  <testcase name="readItem" classname="com.demo.CatalogResourceTest" time="0.05"/>
</testsuite>
"""


def run_py(script: Path, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), str(root), *args],
        text=True,
        capture_output=True,
    )


SKIPPED = """\
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.demo.CatalogResourceTest" tests="1" failures="0" errors="0" skipped="1" time="0.0">
  <testcase name="listItems" classname="com.demo.CatalogResourceTest" time="0.0">
    <skipped message="disabled while migrating"/>
  </testcase>
</testsuite>
"""
NO_CASES = """\
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.demo.CatalogResourceTest" tests="0" failures="0" errors="0" skipped="0" time="0.0"/>
"""


# Failsafe writes this beside (or instead of) per-case reports. It is a PHASE
# SUMMARY, not a malformed test report -- the v9 refusal that this gate now
# diagnoses instead of parsing as a suite. Namespaced, as Maven writes it.
FAILSAFE_SUMMARY_EMPTY = """\
<?xml version="1.0" encoding="UTF-8"?>
<failsafe-summary xmlns="http://maven.apache.org/surefire/maven-surefire-plugin/failsafe-summary"
                  result="254" timeout="false">
  <completed>0</completed>
  <errors>0</errors>
  <failures>0</failures>
  <skipped>0</skipped>
  <failureMessage>No tests to run.</failureMessage>
</failsafe-summary>
"""
NOT_A_REPORT = """\
<?xml version="1.0" encoding="UTF-8"?>
<checkstyle version="10.0"><file name="X.java"/></checkstyle>
"""


GENERATED_PASSING = """\
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.demo.catalog.parity.CatalogParityTest" tests="2" failures="0" errors="0" skipped="0" time="0.1">
  <testcase name="listItems" classname="com.demo.catalog.parity.CatalogParityTest" time="0.05"/>
  <testcase name="readItem" classname="com.demo.catalog.parity.CatalogParityTest" time="0.05"/>
</testsuite>
"""

# The generated parity root's default, and the one a manifest may move it to.
DEFAULT_GENERATED_ROOT = "src/parity-test/java"


def write_source(root: Path, dotted: str) -> None:
    path = root / "src" / "test" / "java" / (dotted.replace(".", "/") + ".java")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("class X {}\n", encoding="utf-8")


def write_generated_source(root: Path, dotted: str, out: str = DEFAULT_GENERATED_ROOT) -> None:
    """A case of the generated parity suite: same shape, another root."""
    path = root / Path(out) / (dotted.replace(".", "/") + ".java")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("class X {}\n", encoding="utf-8")


def write_generated_manifest(root: Path, out: str, cases: tuple[dict, ...] = ()) -> None:
    path = root / "evidence" / "tests" / "generated-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "schema": "rhoai3.generated-tests/v1",
            "out": out,
            "corpus_sha256": "",
            "cases": list(cases),
        }),
        encoding="utf-8",
    )


def write_xml(root: Path, name: str, body: str) -> None:
    path = root / "target" / "surefire-reports" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def write_failsafe_xml(root: Path, name: str, body: str) -> None:
    path = root / "target" / "failsafe-reports" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def write_pom(root: Path, body: str) -> None:
    (root / "pom.xml").write_text(body, encoding="utf-8")


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
            write_xml(root, "TEST-com.demo.CatalogResourceTest.xml", PASSING)
            self.assertEqual(run_py(SNAP, root).returncode, 0)
            proc = run_py(SURE, root)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_skipped_case_refuses(self) -> None:
        """A skipped case is not a passed case; @Disabled must not read green."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_xml(root, "TEST-com.demo.CatalogResourceTest.xml", SKIPPED)
            proc = run_py(SURE, root)
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("skipped case", proc.stderr)
            self.assertIn("CatalogResourceTest.listItems", proc.stderr)

    def test_no_executed_case_refuses(self) -> None:
        """Zero failures over zero executions is the same silence as no report."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_xml(root, "TEST-com.demo.CatalogResourceTest.xml", NO_CASES)
            proc = run_py(SURE, root)
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("no executed case", proc.stderr)

    def test_reports_must_belong_to_this_tree(self) -> None:
        """Green reports about classes this destination does not have prove nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_source(root, "com.demo.model.ValidatorTests")
            write_xml(root, "TEST-com.demo.CatalogResourceTest.xml", PASSING)
            proc = run_py(SURE, root)
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("no executed case belongs to a test source in this tree", proc.stderr)
            # the control: the same reports pass once the tree owns the class
            write_source(root, "com.demo.CatalogResourceTest")
            proc = run_py(SURE, root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("executed from this tree: com.demo.CatalogResourceTest", proc.stderr)
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


class EvidenceBasedDiagnosisTests(unittest.TestCase):
    """ADR-015: the verdict says WHAT the evidence shows, per phase.

    Four states on one renamed specimen (``com.demo.catalog``): (a) a phase with
    no sources and no report, (b) a phase with sources and no report, (c)
    reports that are red or skipped, (d) reports that are clean.
    """

    def test_a_empty_failsafe_phase_is_informational(self) -> None:
        """(a) No *IT.java and no failsafe report: the phase is legitimately
        empty. It is reported, not refused, because the other floor (AR-2.8)
        would still count the surefire executions."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_source(root, "com.demo.catalog.CatalogResourceTest")
            write_xml(root, "TEST-com.demo.CatalogResourceTest.xml", PASSING)
            write_source(root, "com.demo.CatalogResourceTest")
            proc = run_py(SURE, root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("empty failsafe phase", proc.stderr)
            self.assertIn("surefire executed 2 case(s)", proc.stderr)
            self.assertIn("*IT.java", proc.stderr)

    def test_a_failsafe_summary_is_not_a_malformed_report(self) -> None:
        """v9 regression: failsafe-summary.xml is a phase summary. Reading it
        as a suite produced 'no testsuite element'; it is now evidence about an
        empty phase, quoted with its counts."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_source(root, "com.demo.CatalogResourceTest")
            write_xml(root, "TEST-com.demo.CatalogResourceTest.xml", PASSING)
            write_failsafe_xml(root, "failsafe-summary.xml", FAILSAFE_SUMMARY_EMPTY)
            proc = run_py(SURE, root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("no testsuite element", proc.stderr)
            self.assertIn("empty failsafe phase", proc.stderr)
            self.assertIn("failsafe-summary.xml reports completed=0", proc.stderr)

    def test_a_empty_phases_everywhere_still_refuse(self) -> None:
        """The coupling: an empty phase is informational only beside a phase
        that executed something. Zero executed cases is the condition under
        which AR-2.8 also counts none, so it refuses here too."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_failsafe_xml(root, "failsafe-summary.xml", FAILSAFE_SUMMARY_EMPTY)
            proc = run_py(SURE, root)
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("no executed case", proc.stderr)
            self.assertIn("failsafe-summary.xml reports completed=0", proc.stderr)
            self.assertIn("No tests to run.", proc.stderr)

    def test_b_sources_without_report_name_the_pom_cause(self) -> None:
        """(b) *IT.java exists and the failsafe phase produced nothing: refuse,
        naming the source and the skip property the pom declares."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_source(root, "com.demo.catalog.CatalogResourceIT")
            write_source(root, "com.demo.CatalogResourceTest")
            write_xml(root, "TEST-com.demo.CatalogResourceTest.xml", PASSING)
            write_pom(root, "<project><properties><skipITs>true</skipITs></properties></project>")
            proc = run_py(SURE, root)
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("1 failsafe test source(s)", proc.stderr)
            self.assertIn("target/failsafe-reports", proc.stderr)
            self.assertIn("pom.xml declares <skipITs>true</skipITs>", proc.stderr)
            self.assertIn("src/test/java/com/demo/catalog/CatalogResourceIT.java", proc.stderr)

    def test_b_sources_without_report_quote_the_build_log(self) -> None:
        """The same refusal, with the cause read from a build log line."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_source(root, "com.demo.catalog.CatalogResourceTest")
            (root / "build.log").write_text(
                "[INFO] Scanning for projects...\n"
                "[INFO] mvn -B package -DskipTests\n"
                "[INFO] BUILD SUCCESS\n",
                encoding="utf-8",
            )
            proc = run_py(SURE, root)
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("fail closed", proc.stderr)
            self.assertIn("build.log:2", proc.stderr)
            self.assertIn("-DskipTests", proc.stderr)

    def test_b_named_build_log_is_read(self) -> None:
        """A log outside the default globs is read when the runner names it."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_source(root, "com.demo.catalog.CatalogResourceIT")
            write_source(root, "com.demo.CatalogResourceTest")
            write_xml(root, "TEST-com.demo.CatalogResourceTest.xml", PASSING)
            named = root / "logs" / "verify.txt"
            named.parent.mkdir(parents=True, exist_ok=True)
            named.write_text("[INFO] Tests are skipped.\n", encoding="utf-8")
            proc = run_py(SURE, root, "--build-log", str(named))
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("Tests are skipped", proc.stderr)

    def test_b_surefire_json_phase_ran_without_per_case_report(self) -> None:
        """A recorded phase that left no per-case report is named as the cause."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_source(root, "com.demo.catalog.CatalogResourceIT")
            write_source(root, "com.demo.CatalogResourceTest")
            write_xml(root, "TEST-com.demo.CatalogResourceTest.xml", PASSING)
            sf = root / "verification" / "build" / "surefire.json"
            sf.parent.mkdir(parents=True, exist_ok=True)
            sf.write_text(
                json.dumps({"schema": "rhoai3.surefire/v1", "ran": True, "tests": 7, "reports": 0}),
                encoding="utf-8",
            )
            proc = run_py(SURE, root)
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("records a test phase that RAN (tests=7", proc.stderr)

    def test_c_red_cases_are_named_with_their_report(self) -> None:
        """(c) Each red case is named, with the file the claim was read from."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_xml(root, "TEST-com.demo.HealthTest.xml", DEST5_FAILING)
            proc = run_py(SURE, root)
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("Failures=1", proc.stderr)
            self.assertIn("com.demo.HealthTest.healthEndpoint", proc.stderr)
            self.assertIn("target/surefire-reports/TEST-com.demo.HealthTest.xml", proc.stderr)
            self.assertIn("Status 404", proc.stderr)

    def test_c_skips_are_named_with_their_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_xml(root, "TEST-com.demo.CatalogResourceTest.xml", SKIPPED)
            proc = run_py(SURE, root)
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("skipped case", proc.stderr)
            self.assertIn("disabled while migrating", proc.stderr)
            self.assertIn("target/surefire-reports/TEST-com.demo.CatalogResourceTest.xml", proc.stderr)

    def test_d_clean_reports_pass_with_per_phase_counts(self) -> None:
        """(d) The pass states the counts and the files they were read from."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_source(root, "com.demo.CatalogResourceTest")
            write_xml(root, "TEST-com.demo.CatalogResourceTest.xml", PASSING)
            proc = run_py(SURE, root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("Tests=2 reports=1", proc.stderr)
            self.assertIn("read: target/surefire-reports, target/failsafe-reports", proc.stderr)
            self.assertIn("surefire: 1 source(s)", proc.stderr)
            self.assertIn("2 executed, 0 skipped, 0 failed/errored", proc.stderr)

    def test_unreadable_root_element_exits_two(self) -> None:
        """Neither a suite nor a phase summary: unreadable is never green."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_xml(root, "checkstyle-result.xml", NOT_A_REPORT)
            proc = run_py(SURE, root)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertIn("root element <checkstyle>", proc.stderr)

    def test_unparseable_xml_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_xml(root, "TEST-com.demo.CatalogResourceTest.xml", "<testsuite>")
            proc = run_py(SURE, root)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertIn("could not be parsed as XML", proc.stderr)


class TwoTestRootsTests(unittest.TestCase):
    """ADR-015: the floor pairs each phase against BOTH test roots.

    ``src/test/java`` is the loop's own; the generated parity suite lives in the
    root ``evidence/tests/generated-manifest.json``'s ``out`` names (default
    ``src/parity-test/java``) -- the same pair
    ``check-domain-parity/scripts/check-product-tests.py`` measures. Reading the
    first root alone made a tree whose only tests are generated read as a tree
    with no test source: every execution unbound, the phase called empty.
    """

    def test_generated_only_tree_passes_and_names_the_generated_root(self) -> None:
        """Only generated sources, clean reports: PASS, with the executions
        bound to the generated root the manifest names (not the default, so the
        manifest is demonstrably what decides it)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_generated_manifest(
                root,
                "src/it-parity/java",
                ({"scenario": "catalog:list", "class": "com.demo.catalog.parity.CatalogParityTest",
                  "method": "listItems", "entry_point": "catalog"},),
            )
            write_generated_source(root, "com.demo.catalog.parity.CatalogParityTest", "src/it-parity/java")
            write_xml(root, "TEST-com.demo.catalog.parity.CatalogParityTest.xml", GENERATED_PASSING)
            proc = run_py(SURE, root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("Tests=2 reports=1", proc.stderr)
            self.assertIn("executed from this tree: com.demo.catalog.parity.CatalogParityTest", proc.stderr)
            self.assertIn("src/it-parity/java", proc.stderr)
            self.assertIn("surefire: 1 source(s)", proc.stderr)
            # the defect: this tree used to read as "no src/test/java in this tree"
            self.assertNotIn("no test source under", proc.stderr)

    def test_generated_case_counts_exactly_like_a_retained_one(self) -> None:
        """One retained source, one generated source, a report for each: both
        are bound, both are counted, neither root is privileged."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_source(root, "com.demo.CatalogResourceTest")
            write_generated_source(root, "com.demo.catalog.parity.CatalogParityTest")
            write_xml(root, "TEST-com.demo.CatalogResourceTest.xml", PASSING)
            write_xml(root, "TEST-com.demo.catalog.parity.CatalogParityTest.xml", GENERATED_PASSING)
            proc = run_py(SURE, root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("Tests=4 reports=2", proc.stderr)
            self.assertIn("com.demo.CatalogResourceTest", proc.stderr)
            self.assertIn("com.demo.catalog.parity.CatalogParityTest", proc.stderr)
            self.assertIn("surefire: 2 source(s)", proc.stderr)
            self.assertIn("4 executed, 0 skipped, 0 failed/errored", proc.stderr)
            self.assertNotIn("no case named for", proc.stderr)

    def test_generated_sources_without_a_report_refuse_with_the_cause(self) -> None:
        """(b) over the generated root: the sources are there, the surefire
        phase produced nothing, and the refusal names the source in the
        generated root and the skip property the pom declares."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_generated_source(root, "com.demo.catalog.parity.CatalogParityTest")
            write_failsafe_xml(root, "failsafe-summary.xml", FAILSAFE_SUMMARY_EMPTY)
            write_pom(root, "<project><properties><skipTests>true</skipTests></properties></project>")
            proc = run_py(SURE, root)
            self.assertNotEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("1 surefire test source(s)", proc.stderr)
            self.assertIn("target/surefire-reports", proc.stderr)
            self.assertIn("pom.xml declares <skipTests>true</skipTests>", proc.stderr)
            self.assertIn(
                "src/parity-test/java/com/demo/catalog/parity/CatalogParityTest.java", proc.stderr)

    def test_neither_root_has_a_source_is_the_informational_empty_phase(self) -> None:
        """(a) unchanged, and now stated over both roots: no source in either
        one is reported with both names, never as a claim about one of them."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_xml(root, "TEST-com.demo.CatalogResourceTest.xml", PASSING)
            proc = run_py(SURE, root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("no test source under src/test/java or src/parity-test/java", proc.stderr)
            self.assertIn(
                "empty failsafe phase — no *IT.java under src/test/java or src/parity-test/java",
                proc.stderr)
            self.assertIn("test roots: src/test/java, src/parity-test/java", proc.stderr)


if __name__ == "__main__":
    unittest.main()
