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

    invented_bin = SCRIPTS / "assert-partition-invented-routes.py"
    dest5 = FIXTURES / "partition-invented-health"
    proc = _run([sys.executable, str(invented_bin), str(dest5)])
    blob = proc.stdout + proc.stderr
    if proc.returncode == 0:
        return _fail("dest-5 T020 invented /q/health should REFUSE: %s" % blob)
    if "T020_POLISH" not in blob or "/q/health" not in blob:
        return _fail("dest-5 invented-route /q/health missing: %s" % blob)
    proc = _run([sys.executable, str(COVERAGE), str(dest5)])
    blob = proc.stdout + proc.stderr
    if proc.returncode == 0:
        return _fail("dest-5 coverage should REFUSE invented routes: %s" % blob)
    if "invented_route:T020_POLISH:/q/health" not in blob:
        return _fail("dest-5 coverage missed invented_route: %s" % blob)
    if "stale_ac:T010_US1:/api/greeting" not in blob:
        return _fail("dest-5 T010 stale AC /api/greeting missed: %s" % blob)

    dest6 = FIXTURES / "partition-dest6-grounded"
    invented_files_bin = SCRIPTS / "assert-partition-invented-files.py"
    dest9_files = FIXTURES / "partition-invented-dest-files"
    proc = _run([sys.executable, str(invented_files_bin), str(dest9_files)])
    blob = proc.stdout + proc.stderr
    if proc.returncode != 1:
        return _fail("dest-9 invented dest Java should REFUSE: %s" % blob)
    if "Application.java" not in blob or "GreetingResource.java" not in blob:
        return _fail("dest-9 invented dest Java names missing: %s" % blob)
    proc = _run([sys.executable, str(invented_files_bin), str(dest6)])
    blob = proc.stdout + proc.stderr
    if proc.returncode != 0:
        return _fail(
            "dest-6-grounded has no type-inventory; invented-files skip PASS: %s"
            % blob
        )

    proc = _run([sys.executable, str(invented_bin), str(dest6)])
    blob = proc.stdout + proc.stderr
    if proc.returncode != 0:
        return _fail(
            "dest-6 /api/greeting is dest layering (http_join); invented-routes "
            "must PASS: %s" % blob
        )
    proc = _run([sys.executable, str(COVERAGE), str(dest6)])
    blob = proc.stdout + proc.stderr
    if proc.returncode == 0:
        return _fail("dest-6 stale AC should REFUSE coverage: %s" % blob)
    if "stale_ac:us1_greeting:/api/greeting" not in blob:
        return _fail("dest-6 coverage missed stale_ac: %s" % blob)
    if "implicit_pom_parent_vacuous:us1_greeting:setup" not in blob:
        return _fail("dest-6 coverage missed implicit pom parent: %s" % blob)

    dest6_ok = FIXTURES / "partition-dest6-aligned"
    proc = _run([sys.executable, str(invented_bin), str(dest6_ok)])
    blob = proc.stdout + proc.stderr
    if proc.returncode != 0:
        return _fail("dest-6 aligned partition should PASS invented-routes: %s" % blob)
    proc = _run([sys.executable, str(COVERAGE), str(dest6_ok)])
    blob = proc.stdout + proc.stderr
    if proc.returncode != 0:
        return _fail("dest-6 aligned partition should PASS coverage: %s" % blob)

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

        import contextlib
        import io

        sha = "a" * 64
        m4_pom = {
            "task_id": "verdict",
            "role": "implementer",
            "phase": "M4",
            "refs": [
                {"key": "story_tip", "path": "evidence/tip.json", "sha256": sha}
            ],
            "identity": {
                "transform_class": "NONE",
                "g2_applicability": "not_applicable",
            },
            "files_writable": ["pom.xml"],
            "exit_criteria": [{"check": "verdict", "assert": "oracles only"}],
        }
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            ckb.check_body("m4-pom", m4_pom, tmp)
        if "must not implement" not in buf.getvalue():
            return _fail(
                "M4 pom.xml writeset missed BODY_SCOPE implement: %s" % buf.getvalue()
            )
        m4_ev = dict(m4_pom)
        m4_ev["files_writable"] = ["evidence/verdicts/"]
        buf2 = io.StringIO()
        with contextlib.redirect_stderr(buf2):
            ckb.check_body("m4-ev", m4_ev, tmp)
        if "must not implement" in buf2.getvalue():
            return _fail(
                "M4 evidence writeset still treated as implement: %s" % buf2.getvalue()
            )
        m4_tc = dict(m4_ev)
        m4_tc["exit_criteria"] = [
            {"check": "verdict", "assert": "oracles only"},
            {"check": "compile", "cmd": "mvn -q test-compile"},
        ]
        buf3 = io.StringIO()
        with contextlib.redirect_stderr(buf3):
            ckb.check_body("m4-tc", m4_tc, tmp)
        if "test-compile is not a card exit" not in buf3.getvalue():
            return _fail(
                "test-compile exit missed BODY_EXIT: %s" % buf3.getvalue()
            )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    k4 = KERNEL / "k4_selftest.py"
    proc = _run([sys.executable, str(k4)])
    if proc.returncode != 0:
        return _fail("k4_selftest: %s %s" % (proc.stdout, proc.stderr))

    speckit = SCRIPTS / "assert-m2-speckit-conformance.test.py"
    proc = _run([sys.executable, str(speckit)])
    if proc.returncode != 0:
        return _fail("assert-m2-speckit-conformance: %s %s" % (proc.stdout, proc.stderr))

    performed_test = SCRIPTS / "assert-card-performed.test.py"
    proc = _run([sys.executable, str(performed_test)])
    if proc.returncode != 0:
        return _fail(
            "assert-card-performed.test.py: %s %s" % (proc.stdout, proc.stderr)
        )

    lib = SKILL.parents[2] / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    from specimen_agnostic import stamp_dd3_extensions  # noqa: PLC0415

    setup = {"files_writable": ["pom.xml"], "identity": {}}
    us = {
        "files_writable": ["src/main/java/com/demo/GreetingResource.java"],
        "identity": {},
    }
    stamp_dd3_extensions([setup, us])
    if "extensions_apply" in us["identity"]:
        return _fail("W5: US story must not carry extensions_apply")
    apply = setup["identity"].get("extensions_apply") or []
    if "quarkus-rest" not in apply:
        return _fail("W5: pom writer must apply REST union, got %s" % apply)
    two_writers = [
        {"files_writable": ["pom.xml"], "identity": {}},
        {"files_writable": ["pom.xml", "src/main/java/X.java"], "identity": {}},
    ]
    try:
        stamp_dd3_extensions(two_writers)
        return _fail("W5: two pom writers must REFUSE")
    except ValueError:
        pass
    patterns = (
        SKILL.parents[1]
        / "migration"
        / "spring-to-quarkus-patterns"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    if "this story's `pom.xml` write" in patterns:
        return _fail("W5: spring-to-quarkus-patterns must not write pom on US stories")
    manage = (
        SKILL.parents[1] / "migration" / "manage-quarkus-extensions" / "SKILL.md"
    ).read_text(encoding="utf-8")
    if "adds it and owns" in manage:
        return _fail("W5: manage-quarkus-extensions must not add pom on the needing story")

    print("OK: batch-3 sdd/partition selftest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
