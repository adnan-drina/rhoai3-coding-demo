#!/usr/bin/env python3
"""Refuse M4 when surefire/failsafe XML reports failures or are absent.

Lead:m4-must-read-test-results-not-test-files — dest-5 M4 discussed
HealthTest 19× and never opened target/surefire-reports (Failures: 1).
Parse XML. Fail closed when no reports exist. Prefer the pre-rebuild
snapshot so a later mvn clean cannot hide the result.
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
    print(
        "OK: surefire-results (Failures=0 Errors=0 Tests=%d reports=%d)"
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
