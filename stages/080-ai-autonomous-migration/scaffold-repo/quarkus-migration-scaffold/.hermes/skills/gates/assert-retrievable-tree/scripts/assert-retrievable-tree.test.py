#!/usr/bin/env python3
"""assert-retrievable-tree selftest: the gate is not weakened for the harness.

M4 generates the product parity tests into ``src/parity-test/java`` (ADR-015),
and an untracked file there is dirt like any other: a verdict composed over a
tree nobody can retrieve says nothing about what was measured. The gate keeps
refusing it. What makes the tree retrievable is the road's commit step
(``commit-generated-tests.py``), not an exemption here.

Covered: a clean tree passes and writes its verdict; ``--check-only`` writes
none; an untracked generated file refuses and names it; a modified pom refuses;
committing exactly those files restores the pass.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "assert-retrievable-tree.py"
VERDICT = Path("evidence") / "verdicts" / "assert-retrievable-tree.json"

FAILURES: list[str] = []


def fail(msg: str) -> int:
    FAILURES.append(msg)
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


def run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args, str(root)], text=True, capture_output=True)


def tree(tmp: Path, name: str) -> Path:
    root = tmp / name
    (root / "src" / "main" / "java").mkdir(parents=True)
    (root / "src" / "main" / "java" / "App.java").write_text("class App {}\n", encoding="utf-8")
    (root / "pom.xml").write_text("<project/>\n", encoding="utf-8")
    git(root, "init", "-q")
    git(root, "config", "user.email", "dest@example.com")
    git(root, "config", "user.name", "dest")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    return root


def case_clean(tmp: Path) -> int:
    rc = 0
    root = tree(tmp, "clean")
    proc = run(root)
    if proc.returncode != 0:
        return fail("a committed tree must pass: %s%s" % (proc.stdout, proc.stderr))
    if not (root / VERDICT).is_file():
        rc |= fail("a pass must write its verdict")
    doc = json.loads((root / VERDICT).read_text(encoding="utf-8"))
    if doc.get("verdict") != "PASS" or doc.get("ship") is not False:
        rc |= fail("the verdict must be a non-shipping PASS: %s" % doc)
    (root / VERDICT).unlink()
    if run(root, "--check-only").returncode != 0 or (root / VERDICT).is_file():
        rc |= fail("--check-only must pass and write no verdict")
    return rc


def case_untracked_generated_file(tmp: Path) -> int:
    """ADR-015: the generated suite is dirt until something commits it."""
    rc = 0
    root = tree(tmp, "generated")
    generated = root / "src" / "parity-test" / "java" / "acme" / "generated" / "ParityTest.java"
    generated.parent.mkdir(parents=True)
    generated.write_text("class ParityTest {}\n", encoding="utf-8")
    proc = run(root)
    if proc.returncode != 1:
        rc |= fail("an untracked generated test must refuse: rc=%s %s%s" % (proc.returncode, proc.stdout, proc.stderr))
    if "src/parity-test/java/acme/generated/ParityTest.java" not in proc.stderr:
        rc |= fail("the refusal must name the file it is about: %s" % proc.stderr)
    if (root / VERDICT).is_file():
        rc |= fail("a refusal must write no PASS verdict")

    # what the commit step does, and the only thing that clears this
    git(root, "add", "--all", "--", "src/parity-test")
    git(root, "commit", "-q", "-m", "m4: generated product tests")
    if run(root).returncode != 0:
        rc |= fail("committing exactly the generated files must restore the pass")

    # a pom edited after the fact is refused the same way
    (root / "pom.xml").write_text("<project> </project>\n", encoding="utf-8")
    proc = run(root)
    if proc.returncode != 1 or "pom.xml" not in proc.stderr:
        rc |= fail("a modified pom.xml must refuse: rc=%s %s" % (proc.returncode, proc.stderr))
    return rc


def case_not_a_work_tree(tmp: Path) -> int:
    root = tmp / "bare"
    (root / "src").mkdir(parents=True)
    (root / "pom.xml").write_text("<project/>\n", encoding="utf-8")
    proc = run(root)
    if proc.returncode != 1 or "work tree" not in proc.stderr:
        return fail("a tree that is not under git must refuse: rc=%s %s" % (proc.returncode, proc.stderr))
    return 0


def main() -> int:
    cases = (case_clean, case_untracked_generated_file, case_not_a_work_tree)
    rc = 0
    with tempfile.TemporaryDirectory(prefix="assert-retrievable-tree-") as td:
        tmp = Path(td)
        for case in cases:
            try:
                rc |= case(tmp)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                rc |= fail("%s raised %s" % (case.__name__, exc))
    if rc:
        print("FAIL: assert-retrievable-tree %d check(s) failed" % len(FAILURES), file=sys.stderr)
        return 1
    print("OK: assert-retrievable-tree %d case(s)" % len(cases))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
