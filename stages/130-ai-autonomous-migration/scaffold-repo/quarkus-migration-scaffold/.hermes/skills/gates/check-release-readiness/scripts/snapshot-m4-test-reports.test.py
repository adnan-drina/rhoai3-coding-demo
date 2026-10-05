#!/usr/bin/env python3
"""snapshot-m4-test-reports selftest: which evidence the floors get to read.

Two failures, opposite in shape, and both are real:

  dest-5   a rebuild deleted unread surefire XML. A populated snapshot is
           never overwritten with an empty ``target/``.
  ADR-015  the M4 pre-verdict runner rebuilds under ``m4-parity`` BEFORE it
           snapshots, so a snapshot taken at M3 -- before the generated parity
           cases existed -- would make the floors measure a suite that ran as
           one that never did. A fresher rebuild wins, by ``--fresh`` or by
           file times.

Covered: first snapshot; empty target/ keeps a populated snapshot; --fresh
replaces it; newer live reports replace it without the flag; a snapshot that is
already the freshest is kept; the receipt records when the CONTENT was taken,
from where, and how many files it holds.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "snapshot-m4-test-reports.py"
SNAP = Path("evidence") / "m4-pre-rebuild" / "test-reports"
MANIFEST = Path("evidence") / "m4-pre-rebuild" / "manifest.json"

FAILURES: list[str] = []


def fail(msg: str) -> int:
    FAILURES.append(msg)
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args, str(root)], text=True, capture_output=True)


def write_report(root: Path, fqcn: str, *, phase: str = "surefire", when: float | None = None) -> Path:
    p = root / "target" / ("%s-reports" % phase) / ("TEST-%s.xml" % fqcn)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<testsuite name="%s" tests="1"><testcase classname="%s" name="run"/></testsuite>\n' % (fqcn, fqcn),
                 encoding="utf-8")
    if when is not None:
        os.utime(p, (when, when))
    return p


def snapshot_classes(root: Path) -> set[str]:
    return {p.name for p in (root / SNAP).rglob("*.xml")}


def receipt(root: Path) -> dict:
    return json.loads((root / MANIFEST).read_text(encoding="utf-8"))


def case_first_and_empty(tmp: Path) -> int:
    rc = 0
    root = tmp / "first"
    write_report(root, "acme.LoopTest")
    if run(root).returncode != 0:
        return fail("the first snapshot must succeed")
    if snapshot_classes(root) != {"TEST-acme.LoopTest.xml"}:
        rc |= fail("the first snapshot must carry the live reports: %s" % snapshot_classes(root))
    doc = receipt(root)
    if doc["kept_existing_snapshot"] or doc["snapshot_of"]["files"] != 1:
        rc |= fail("the receipt must record a first snapshot of one file: %s" % doc)
    if doc["snapshot_of"]["sources"] != ["target/surefire-reports"]:
        rc |= fail("the receipt must name the source dirs it copied: %s" % doc["snapshot_of"])
    if not doc["snapshot_of"].get("epoch"):
        rc |= fail("the receipt must record when the content was taken: %s" % doc["snapshot_of"])
    taken = doc["snapshot_of"]["epoch"]

    # dest-5: an emptied target/ never overwrites a populated snapshot, and a
    # keep must not push the recorded time forward (that would hide a later
    # rebuild from the freshness comparison).
    for p in (root / "target").rglob("*.xml"):
        p.unlink()
    if run(root).returncode != 0:
        rc |= fail("a keep is not an error")
    if snapshot_classes(root) != {"TEST-acme.LoopTest.xml"}:
        rc |= fail("an empty target/ must not empty the snapshot: %s" % snapshot_classes(root))
    doc = receipt(root)
    if not doc["kept_existing_snapshot"] or doc["snapshot_of"]["epoch"] != taken:
        rc |= fail("a keep records the time the CONTENT was taken, not the time it ran: %s" % doc["snapshot_of"])
    return rc


def case_fresh_wins(tmp: Path) -> int:
    """ADR-015: the runner rebuilt under m4-parity, so its reports are the
    evidence — even though an M3 snapshot is already sitting there."""
    rc = 0
    root = tmp / "fresh"
    write_report(root, "acme.LoopTest")
    run(root)
    old = receipt(root)["snapshot_of"]["epoch"]

    # The rebuild: the generated parity case joins the reports, but their file
    # times are OLDER than the snapshot's, so the freshness rule alone would
    # keep the stale snapshot. Only the caller knows it just rebuilt, and
    # --fresh is how it says so.
    for p in (root / "target").rglob("*.xml"):
        p.unlink()
    stale = time.time() - 600
    write_report(root, "acme.generated.ParityTest", when=stale)
    write_report(root, "acme.LoopTest", when=stale)
    if run(root).returncode != 0:
        rc |= fail("the precondition run failed")
    if "TEST-acme.generated.ParityTest.xml" in snapshot_classes(root):
        rc |= fail("test setup: reports older than the snapshot must not win on file times alone")

    proc = run(root, "--fresh")
    if proc.returncode != 0:
        rc |= fail("--fresh must succeed: %s" % proc.stderr)
    if "TEST-acme.generated.ParityTest.xml" not in snapshot_classes(root):
        rc |= fail("--fresh must replace the snapshot with the rebuilt reports: %s" % snapshot_classes(root))
    doc = receipt(root)
    if doc["kept_existing_snapshot"] or "--fresh" not in doc["snapshot_of"]["reason"]:
        rc |= fail("the receipt must say the replacement was the caller's rebuild: %s" % doc["snapshot_of"])
    if doc["snapshot_of"]["epoch"] <= old:
        rc |= fail("a replacement must move the recorded time forward: %s" % doc["snapshot_of"])

    # nothing newer, no flag: the snapshot stands
    if run(root).returncode != 0:
        rc |= fail("a re-run must succeed")
    if not receipt(root)["kept_existing_snapshot"]:
        rc |= fail("a snapshot that is already the freshest evidence is kept")
    return rc


def case_newer_live_wins(tmp: Path) -> int:
    """Without the flag: the file times decide, so a rebuild anything else
    drove is still read rather than shadowed by an older snapshot."""
    rc = 0
    root = tmp / "newer"
    past = time.time() - 600
    write_report(root, "acme.LoopTest", when=past)
    run(root)
    if not receipt(root)["snapshot_of"]["epoch"]:
        return fail("test setup: the first snapshot must record its time")

    write_report(root, "acme.generated.ParityTest", when=time.time() + 60)
    if run(root).returncode != 0:
        rc |= fail("a replacement run must succeed")
    if "TEST-acme.generated.ParityTest.xml" not in snapshot_classes(root):
        rc |= fail("live reports newer than the snapshot must replace it: %s" % snapshot_classes(root))
    doc = receipt(root)
    if doc["kept_existing_snapshot"] or "newer" not in doc["snapshot_of"]["reason"]:
        rc |= fail("the receipt must say why the snapshot was replaced: %s" % doc["snapshot_of"])
    if doc["snapshot_of"]["files"] != 2:
        rc |= fail("the receipt must count what the snapshot holds: %s" % doc["snapshot_of"])
    return rc


def case_failsafe_phase(tmp: Path) -> int:
    rc = 0
    root = tmp / "failsafe"
    write_report(root, "acme.LoopTest")
    write_report(root, "acme.ThingIT", phase="failsafe")
    run(root)
    doc = receipt(root)
    if doc["snapshot_of"]["sources"] != ["target/surefire-reports", "target/failsafe-reports"]:
        rc |= fail("both phases must be recorded as sources: %s" % doc["snapshot_of"])
    if doc["snapshot_of"]["files"] != 2 or doc["live_missing"]:
        rc |= fail("both phases must be snapshotted: %s" % doc)
    return rc


def main() -> int:
    cases = (case_first_and_empty, case_fresh_wins, case_newer_live_wins, case_failsafe_phase)
    rc = 0
    with tempfile.TemporaryDirectory(prefix="snapshot-m4-") as td:
        tmp = Path(td)
        for case in cases:
            try:
                rc |= case(tmp)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                rc |= fail("%s raised %s" % (case.__name__, exc))
    if rc:
        print("FAIL: snapshot-m4-test-reports %d check(s) failed" % len(FAILURES), file=sys.stderr)
        return 1
    print("OK: snapshot-m4-test-reports %d case(s)" % len(cases))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
