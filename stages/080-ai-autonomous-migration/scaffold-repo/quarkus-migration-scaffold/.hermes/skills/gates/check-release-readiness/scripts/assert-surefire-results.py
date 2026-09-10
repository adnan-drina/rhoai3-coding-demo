#!/usr/bin/env python3
"""Refuse M4 when the test evidence is absent, red, skipped, or about a tree
that is not this one.

Lead:m4-must-read-test-results-not-test-files — dest-5 M4 discussed
HealthTest 19x and never opened target/surefire-reports (Failures: 1).
Parse XML. Fail closed when no reports exist. Prefer the pre-rebuild
snapshot so a later mvn clean cannot hide the result.

Three further refusals, because "the reports are green" is a weaker claim than
it looks (pilot v7):

  * a skipped case is not a passed case. Zero failures over zero executions is
    the same silence as no report at all, and @Disabled reads as green here.
  * at least one executed case must belong to a test source that exists in this
    destination's src/test/java. Reports left by another tree, or by sources an
    ADR has since retired, prove nothing about what ships.
  * a test source in the tree that the reports never name is reported, because
    a test that compiles and never runs is the failure mode this gate exists
    for. Sources with no executable cases (abstract bases, test configuration)
    are named too -- the point is that the set is stated, never assumed.
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SNAP = Path("evidence") / "m4-pre-rebuild" / "test-reports"
LIVE = (
    Path("target") / "surefire-reports",
    Path("target") / "failsafe-reports",
)


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def iter_xml(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.rglob("*.xml") if p.is_file())


def report_dirs(root: Path) -> list[Path]:
    snap = root / SNAP
    if iter_xml(snap):
        return [snap]
    return [root / rel for rel in LIVE]


def test_sources(root: Path) -> set[str]:
    """Java sources under src/test/java, as dotted class names."""
    base = root / "src" / "test" / "java"
    if not base.is_dir():
        return set()
    return {p.relative_to(base).with_suffix("").as_posix().replace("/", ".") for p in base.rglob("*.java")}


def parse_suite(path: Path) -> tuple[int, int, int]:
    try:
        tree = ET.parse(path)
    except (OSError, ET.ParseError) as exc:
        raise ValueError("%s: %s" % (path, exc)) from exc
    root_el = tree.getroot()
    if root_el.tag == "testsuite":
        suites = [root_el]
    elif root_el.tag == "testsuites":
        suites = list(root_el.findall("testsuite"))
    else:
        suites = list(root_el.iter("testsuite"))
    if not suites:
        raise ValueError("%s: no testsuite element" % path)
    tests = failures = errors = 0
    for suite in suites:
        tests += int(suite.attrib.get("tests") or 0)
        failures += int(suite.attrib.get("failures") or 0)
        errors += int(suite.attrib.get("errors") or 0)
    return tests, failures, errors


def parse_cases(path: Path) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """(executed, skipped) cases as (classname, name) from one report."""
    executed: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []
    try:
        tree = ET.parse(path)
    except (OSError, ET.ParseError):
        return executed, skipped
    for tc in tree.getroot().iter("testcase"):
        row = (str(tc.get("classname") or ""), str(tc.get("name") or ""))
        (skipped if tc.find("skipped") is not None else executed).append(row)
    return executed, skipped


def check_root(root: Path) -> int:
    files: list[Path] = []
    for directory in report_dirs(root):
        files.extend(iter_xml(directory))
    if not files:
        return _fail(
            "no surefire/failsafe XML under evidence/m4-pre-rebuild/test-reports "
            "or target/ — fail closed (unread or already cleaned)"
        )
    tests = failures = errors = 0
    for path in files:
        try:
            t, f, e = parse_suite(path)
        except ValueError as exc:
            return _fail(str(exc))
        tests += t
        failures += f
        errors += e
    if failures > 0 or errors > 0:
        return _fail(
            "surefire/failsafe Failures=%d Errors=%d Tests=%d in %d report(s)"
            % (failures, errors, tests, len(files))
        )
    executed: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []
    for path in files:
        e, s = parse_cases(path)
        executed.extend(e)
        skipped.extend(s)
    if skipped:
        return _fail(
            "%d skipped case(s) — a skipped case is not a passed case: %s"
            % (len(skipped), ", ".join("%s.%s" % c for c in sorted(skipped)[:5]))
        )
    if not executed:
        return _fail(
            "%d report(s) and no executed case — zero failures over zero executions is not evidence"
            % len(files)
        )
    sources = test_sources(root)
    if sources:
        mine = sorted({c for c, _ in executed if c in sources})
        if not mine:
            return _fail(
                "no executed case belongs to a test source in this tree; the reports name %s "
                "while src/test/java holds %s"
                % (", ".join(sorted({c for c, _ in executed})[:3]), ", ".join(sorted(sources)[:3]))
            )
        silent = sorted(sources - {c for c, _ in executed})
        print(
            "OK: surefire-results (Failures=0 Errors=0 Skipped=0 Tests=%d reports=%d; executed from this tree: %s%s)"
            % (tests, len(files), ", ".join(mine), ("; no case named for %s" % ", ".join(silent)) if silent else ""),
            file=sys.stderr,
        )
        return 0
    print(
        "OK: surefire-results (Failures=0 Errors=0 Skipped=0 Tests=%d reports=%d; no src/test/java in this tree)"
        % (tests, len(files)),
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="product / dest root")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        return _fail("root is not a directory: " + str(root))
    return check_root(root)


if __name__ == "__main__":
    sys.exit(main())
