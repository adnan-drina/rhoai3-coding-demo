#!/usr/bin/env python3
"""Batch 3 negative controls. Not pytest. Not dest.

Each row fails the pre-fix artefact shape and passes after.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
FIXTURES = SKILL / "fixtures"
KERNEL = SKILL.parents[2] / "kernel"
COVERAGE = SCRIPTS / "check-partition-coverage.py"
READINESS = SCRIPTS / "check-readiness.sh"
BODY = SCRIPTS / "check-kanban-body.py"


def _fail(msg: str) -> int:
    print("FAIL: %s" % msg, file=sys.stderr)
    return 1


def _run(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, text=True, capture_output=True
    )


def main() -> int:
    skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    if "story.endpoints" not in skill_md or "METHOD /path" not in skill_md:
        return _fail("A-8 story.endpoints not in SKILL.md (planner-readable)")

    named = FIXTURES / "partition-supersede-named-set"
    proc = _run([sys.executable, str(COVERAGE), str(named)])
    if proc.returncode != 0:
        return _fail("named-set briefs/ should PASS: %s %s" % (proc.stdout, proc.stderr))

    health = FIXTURES / "partition-health-unsatisfiable"
    proc = _run([sys.executable, str(COVERAGE), str(health)])
    blob = proc.stdout + proc.stderr
    if proc.returncode == 0:
        return _fail("health-unsatisfiable should REFUSE: %s" % blob)
    if "acceptance_unsatisfiable:polish:pom.xml" not in blob:
        return _fail("health-unsatisfiable missed pom gap: %s" % blob)
    if "unsatisfiable_acceptance_is_block_not_complete" not in blob:
        return _fail("health-unsatisfiable missed block hint: %s" % blob)

    tmp = Path(tempfile.mkdtemp(prefix="b3-sdd-"))
    try:
        prod = tmp / "producer"
        shutil.copytree(named, prod)
        src = prod / "evidence" / "briefs" / "partition.json"
        dst_dir = prod / "evidence"
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst_dir / "partition.json"))
        proc = _run([sys.executable, str(COVERAGE), str(prod)])
        if proc.returncode != 0:
            return _fail(
                "producer evidence/partition.json should PASS: %s %s"
                % (proc.stdout, proc.stderr)
            )

        empty = tmp / "empty"
        empty.mkdir()
        proc = _run([sys.executable, str(COVERAGE), str(empty)])
        miss = proc.stdout + proc.stderr
        if proc.returncode == 0:
            return _fail("missing partition should not be VALID: %s" % miss)
        if "evidence/partition.json" not in miss or "evidence/briefs/partition.json" not in miss:
            return _fail("missing partition must name both paths: %s" % miss)

        specs = tmp / "specs-root"
        (specs / "specs").mkdir(parents=True)
        (specs / "specs" / "no-heading.md").write_text("# Spec\n\nBody only.\n", encoding="utf-8")
        proc = _run(["bash", str(READINESS), "--root", str(specs)])
        if proc.returncode != 0:
            return _fail(
                "missing Non-Goals heading should PASS: %s %s" % (proc.stdout, proc.stderr)
            )
        (specs / "specs" / "empty-heading.md").write_text(
            "# Spec\n\n## Non-Goals\n\n## Next\n\nMore.\n", encoding="utf-8"
        )
        proc = _run(["bash", str(READINESS), "--root", str(specs)])
        ng = proc.stdout + proc.stderr
        if proc.returncode == 0:
            return _fail("empty Non-Goals heading should REFUSE: %s" % ng)
        if "Non-Goals is empty" not in ng:
            return _fail("empty Non-Goals message missing: %s" % ng)
        (specs / "specs" / "empty-heading.md").write_text(
            "# Spec\n\n## Non-Goals\n\n- no extra HTTP surface\n\n## Next\n\nMore.\n",
            encoding="utf-8",
        )
        proc = _run(["bash", str(READINESS), "--root", str(specs)])
        if proc.returncode != 0:
            return _fail(
                "Non-Goals with content should PASS: %s %s" % (proc.stdout, proc.stderr)
            )

        import importlib.util

        spec = importlib.util.spec_from_file_location("check_kanban_body", BODY)
        if spec is None or spec.loader is None:
            return _fail("cannot load check-kanban-body.py")
        ckb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ckb)

        if ckb.cmd_runs_tests("mvn -q test-compile"):
            return _fail("test-compile must not count as running tests")
        if not ckb.cmd_runs_tests("mvn -q test"):
            return _fail("mvn -q test must count as running tests")
        if not ckb.scope_touches_tests(["src/test/java/com/demo/HealthTest.java"]):
            return _fail("src/test path must touch tests")
        if ckb.scope_touches_tests(["src/main/java/com/demo/App.java"]):
            return _fail("src/main must not touch tests")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    k4 = KERNEL / "k4_selftest.py"
    proc = _run([sys.executable, str(k4)])
    if proc.returncode != 0:
        return _fail("k4_selftest: %s %s" % (proc.stdout, proc.stderr))

    print("OK: batch-3 sdd/partition selftest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
