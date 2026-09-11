#!/usr/bin/env python3
"""operator-step selftest: a change to a test source needs an ADR and a second seat.

A test source states what the destination must do. One seat editing both the
claim and its proof is not a reviewed intervention, so the tool refuses before
it commits anything. The control is the same change on a main source: it must
get past this guard, which is what proves the guard reads the path and not the
weather (ADR-008).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEP = HERE / "operator-step.py"

TEST_SRC = "src/test/java/a/ATest.java"
MAIN_SRC = "src/main/java/a/A.java"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def _tree(root: Path, changed: str) -> None:
    """A destination with a baseline step, no issued card, and one changed path."""
    for rel in (MAIN_SRC, TEST_SRC):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("class X {}\n", encoding="utf-8")
    loop = root / "verification" / "loop"
    loop.mkdir(parents=True, exist_ok=True)
    (loop / "deferred.json").write_text(json.dumps({
        "schema": "rhoai3.loop-deferred/v1", "clusters": ["c:deferred"],
        "reasons": {"c:deferred": "3 rejected attempt(s)"},
    }), encoding="utf-8")
    (loop / "steps.json").write_text(json.dumps({
        "schema": "rhoai3.loop-steps/v1",
        "steps": [{"cluster": "baseline", "verdict": "baseline", "measure": {"known": True, "tuple": [1, 0, 0]}}],
        "attempts": {"c:deferred": 3},
        "rejected": [{"cluster": "c:deferred", "card": "t_rejected", "reason": "attempt 3"}],
    }), encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "-c", "user.email=t@local", "-c", "user.name=t", "add", "-A")
    _git(root, "-c", "user.email=t@local", "-c", "user.name=t", "commit", "-q", "-m", "baseline")
    (root / changed).write_text("class X { int y; }\n", encoding="utf-8")


def _run(changed: str, *args: str) -> tuple[int, str, Path]:
    tmp = Path(tempfile.mkdtemp(prefix="operator-step-test-"))
    _tree(tmp, changed)
    proc = subprocess.run(
        [sys.executable, str(STEP), "--root", str(tmp), "--operator", "operator",
         "--reason", "port under ADR-008", "--verify-cmd", "true", "--no-mint", *args],
        text=True, capture_output=True)
    return proc.returncode, proc.stdout + proc.stderr, tmp


def main() -> int:
    for name, args, needle in (
        ("no ADR", ("--reviewer", "reviewer"), "names no ADR"),
        ("no reviewer", ("--adr", "ADR-008"), "names no reviewer"),
        ("reviewer is the operator", ("--adr", "ADR-008", "--reviewer", "operator"), "other than the operator"),
    ):
        rc, blob, tmp = _run(TEST_SRC, *args)
        if rc != 1 or needle not in blob:
            return _fail("a test-source change with %s must refuse naming %r: rc=%d %s" % (name, needle, rc, blob[:300]))
        if TEST_SRC not in blob:
            return _fail("the refusal must name the offending path: %s" % blob[:300])
        head = subprocess.run(["git", "-C", str(tmp), "log", "--oneline"], text=True, capture_output=True).stdout
        if len(head.strip().splitlines()) != 1:
            return _fail("the guard must refuse before committing anything: %s" % head)

    # A deferral is the loop's record that a human must decide. Clearing one
    # that is not open would silently invent that decision, and clearing one
    # before the tree measures green would lift it on an intention.
    rc, blob, tmp = _run(TEST_SRC, "--adr", "ADR-008", "--reviewer", "reviewer", "--clear-deferred", "c:never-deferred")
    if rc != 1 or "is not deferred" not in blob or "c:deferred" not in blob:
        return _fail("clearing a cluster that is not deferred must refuse and name the open deferrals: rc=%d %s" % (rc, blob[:300]))
    rc, blob, tmp = _run(MAIN_SRC, "--adr", "ADR-002", "--clear-deferred", "c:deferred")
    if rc == 0 or "measure not known" not in blob:
        return _fail("the main-source control must reach the re-measure: %s" % blob[:300])
    still = json.loads((tmp / "verification" / "loop" / "deferred.json").read_text())
    if still.get("clusters") != ["c:deferred"]:
        return _fail("a deferral must survive a step whose re-measure failed: %s" % still)
    kept = json.loads((tmp / "verification" / "loop" / "steps.json").read_text())
    if [r["card"] for r in kept.get("rejected") or []] != ["t_rejected"]:
        return _fail("the rejected rows are the record of what the cluster minted and must never be dropped: %s" % kept.get("rejected"))

    # A metadata-only disposition is for a cause removed OUTSIDE the product
    # tree; with a product change on disk it would record an intention.
    rc, blob, tmp = _run(MAIN_SRC, "--clear-deferred", "c:deferred", "--disposition-only")
    if rc != 1 or "has changes" not in blob:
        return _fail("--disposition-only with a product change must refuse: rc=%d %s" % (rc, blob[:300]))
    rc, blob, tmp = _run(MAIN_SRC, "--disposition-only")
    if rc != 1 or "name the cluster" not in blob:
        return _fail("--disposition-only records a clearance and needs --clear-deferred: rc=%d %s" % (rc, blob[:300]))

    # Control: the same change on a main source is not this guard's business. It
    # gets past it (and stops later, on the missing measure) — so a red above is
    # the path, not the tool refusing everything.
    rc, blob, tmp = _run(MAIN_SRC, "--adr", "ADR-004")
    if rc == 0 or "reviewer" in blob:
        return _fail("a main-source change must pass the reviewer guard: rc=%d %s" % (rc, blob[:300]))
    if "measure not known" not in blob:
        return _fail("the main-source control must stop on the re-measure, not earlier: %s" % blob[:300])
    log = subprocess.run(["git", "-C", str(tmp), "log", "--oneline"], text=True, capture_output=True).stdout
    if len(log.strip().splitlines()) != 2:
        return _fail("the main-source control must have committed the change: %s" % log)

    print("OK: operator-step selftest (test-source change refuses without an ADR, without a reviewer, and with the operator as reviewer, before committing; main-source control passes the guard and commits; a deferral that is not open refuses and one whose re-measure failed survives; a metadata-only disposition refuses with a product change or no cluster)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
