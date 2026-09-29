#!/usr/bin/env python3
"""V26-6 item 3: run-verify.sh's own record keeps the procedure's exit, the compilation
result and whether tests ran apart, bound to the terminal call that ran it.

v26 (three cards): workers ran `run-verify.sh | tail -40` and `mvn ... | grep; echo`, and
the terminal and the execution ledger recorded the filter's exit code."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("verify_record", HERE / "verify_record.py")
VR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(VR)
sys.path.insert(0, str(HERE.parents[2] / ".." / "lib"))
from paved_road import verifier_record_gap  # noqa: E402

VERIFY_CMD = "cd /projects/modernized && bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root . 2>&1 | tail -40"


class Env:
    """A destination root, a kanban home with this card's execution ledger, and the worker's env."""

    def __init__(self, td: str, card: str = "t_v", run: str = "5"):
        self.root = Path(td) / "dest"
        (self.root / "verification" / "loop").mkdir(parents=True)
        (self.root / "verification" / "build").mkdir(parents=True)
        self.home = Path(td) / "home"
        (self.home / "kanban" / "logs").mkdir(parents=True)
        self.card, self.run = card, run
        self.env = {"HERMES_HOME": str(self.home), "HERMES_KANBAN_TASK": card, "HERMES_KANBAN_RUN_ID": run}

    def call(self, cid: str, cmd: str = VERIFY_CMD) -> None:
        with open(self.home / "kanban" / "logs" / ("%s.exec.jsonl" % self.card), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"phase": "start", "task": self.card, "run": self.run, "tool_call_id": cid, "command": cmd}) + "\n")

    def build(self, *, tuple_=(0, 200, 0), known=True, mvn_failed=False, tests_ran=False, tests_rc=None, mode="acceptance"):
        (self.root / "verification" / "build" / "run.json").write_text(json.dumps(
            {"mode": mode, "candidate_sha256": "c" * 64, "maven_compile": {"failed": mvn_failed, "goal": "compile"},
             "tests": {"ran": tests_ran, "rc": tests_rc}}), encoding="utf-8")
        (self.root / "verification" / "loop" / "state.json").write_text(json.dumps(
            {"measure": {"tuple": list(tuple_), "known": known}}), encoding="utf-8")

    def __enter__(self):
        self._old = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        return self

    def __exit__(self, *exc):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class Record(unittest.TestCase):
    def test_a_completed_procedure_with_compile_errors_is_not_a_successful_build(self):
        with tempfile.TemporaryDirectory() as td, Env(td) as e:
            e.call("cv")
            VR.start(e.root, "acceptance")
            e.build(tuple_=(0, 200, 0))
            doc = VR.finish(e.root, 0)
        self.assertEqual((doc["procedure"], doc["compilation"], doc["compile_errors"]), ("completed", "failed", 200))
        self.assertEqual((doc["tests"], doc["tests_detail"]), ("not-run", "compilation is not clean"))
        self.assertEqual((doc["card"], doc["run"], doc["tool_call_id"], doc["status"]), ("t_v", "5", "cv", "finished"))
        self.assertIn("compilation FAILED (200 compile error(s)); tests not run", VR.line(doc))

    def test_maven_failing_where_the_checker_counts_zero_is_failed(self):
        with tempfile.TemporaryDirectory() as td, Env(td) as e:
            VR.start(e.root, "acceptance")
            e.build(tuple_=(0, 0, 0), mvn_failed=True)
            self.assertEqual(VR.finish(e.root, 0)["compilation"], "failed")

    def test_compiled_and_tests_ran_are_separate_facts(self):
        with tempfile.TemporaryDirectory() as td, Env(td) as e:
            VR.start(e.root, "acceptance")
            e.build(tuple_=(0, 0, 3), tests_ran=True, tests_rc=1)
            doc = VR.finish(e.root, 0)
        self.assertEqual((doc["compilation"], doc["tests"], doc["tests_rc"]), ("passed", "ran", 1))

    def test_diagnostic_mode_never_runs_tests(self):
        with tempfile.TemporaryDirectory() as td, Env(td) as e:
            VR.start(e.root, "diagnostic")
            e.build(tuple_=(0, 0, 0), mode="diagnostic")
            doc = VR.finish(e.root, 0)
        self.assertEqual((doc["tests"], doc["tests_detail"]), ("not-run", "diagnostic mode"))

    def test_a_failed_procedure_claims_nothing_about_compilation(self):
        with tempfile.TemporaryDirectory() as td, Env(td) as e:
            VR.start(e.root, "acceptance")
            e.build(tuple_=(0, 0, 0))
            doc = VR.finish(e.root, 1)
        self.assertEqual((doc["procedure"], doc["compilation"], doc["tests"]), ("failed", "unknown", "not-run"))
        self.assertEqual(doc["tests_detail"], "the procedure did not complete (exit 1)")

    def test_an_older_build_record_is_no_evidence(self):
        with tempfile.TemporaryDirectory() as td, Env(td) as e:
            e.build(tuple_=(0, 0, 0))
            old = time.time() - 3600
            os.utime(e.root / "verification" / "build" / "run.json", (old, old))
            VR.start(e.root, "acceptance")
            self.assertEqual(VR.finish(e.root, 0)["compilation"], "unknown")

    def test_an_unknown_measure_is_unknown(self):
        with tempfile.TemporaryDirectory() as td, Env(td) as e:
            VR.start(e.root, "acceptance")
            e.build(known=False)
            self.assertEqual(VR.finish(e.root, 0)["compilation"], "unknown")

    def test_the_record_binds_to_the_latest_invocation_and_counts_executions(self):
        with tempfile.TemporaryDirectory() as td, Env(td) as e:
            e.call("c1")
            VR.start(e.root, "acceptance")
            VR.finish(e.root, 0)
            e.call("c2")
            VR.start(e.root, "acceptance")
            doc = VR.finish(e.root, 0)
            self.assertEqual((doc["seq"], doc["tool_call_id"]), (2, "c2"))
            # an interrupted third execution leaves status started: nothing earlier stands for it
            e.call("c3")
            VR.start(e.root, "acceptance")
            gap = verifier_record_gap(e.root, "run-verify.sh", "t_v", "5", 3, "c3")
        self.assertIn("no recorded finish", gap)


class RealVerifierBehindAFilter(unittest.TestCase):
    """The shipped run-verify.sh, run the way v26 workers ran it: its failure on a tree it cannot
    verify, behind `| tail -1; echo done`, is a clean terminal exit, and the verifier's own record
    still carries the exit the script returns when nothing filters it."""

    def test_the_pipeline_exits_0_and_the_record_keeps_the_verifiers_exit(self):
        with tempfile.TemporaryDirectory() as td:
            e = Env(td)
            cmd = "bash %s --root %s 2>&1 | tail -1; echo done" % (HERE / "run-verify.sh", e.root)
            e.call("c0", "bash %s --root %s" % (HERE / "run-verify.sh", e.root))
            env = dict(os.environ, **e.env)
            bare = subprocess.run(["bash", str(HERE / "run-verify.sh"), "--root", str(e.root)], capture_output=True,
                                  text=True, env=env, timeout=120)
            self.assertNotEqual(bare.returncode, 0)
            e.call("cv")
            proc = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, env=env, timeout=120)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            doc = json.loads((e.root / "verification" / "loop" / "last-verify.json").read_text(encoding="utf-8"))
            self.assertEqual((doc["status"], doc["rc"], doc["procedure"], doc["tool_call_id"]),
                             ("finished", bare.returncode, "failed", "cv"))
            self.assertIn("VERIFY EXIT %d" % bare.returncode, proc.stdout)
            self.assertIn("the verifier itself exited %d" % bare.returncode,
                          verifier_record_gap(e.root, "run-verify.sh", "t_v", "5", 2, "cv"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
