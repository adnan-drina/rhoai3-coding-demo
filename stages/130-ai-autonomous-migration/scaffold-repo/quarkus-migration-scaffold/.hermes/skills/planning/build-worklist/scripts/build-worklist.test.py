#!/usr/bin/env python3
"""Execute the shipped wrapper with controlled verifier/baseline failures."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("build-worklist.sh")


class BuildWorklistPhases(unittest.TestCase):
    def run_wrapper(self, verify_rc=0, baseline_rc=0, bootstrap=True, plan_semantics=None, args_out=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "destination with spaces"
            scripts = root / ".hermes/skills/planning/build-worklist/scripts"
            scripts.mkdir(parents=True)
            shutil.copy2(SCRIPT, scripts)
            if plan_semantics is not None:
                # the real planner library decides the mode from decisions.yaml
                shutil.copytree(SCRIPT.parents[4] / "lib", root / ".hermes/lib",
                                ignore=shutil.ignore_patterns("__pycache__", "fixtures", "*.test.py"))
                shutil.copytree(SCRIPT.parents[4] / "planning", root / ".hermes/planning")
                if plan_semantics:
                    import sys
                    sys.path.insert(0, str(SCRIPT.parents[4] / "lib"))
                    from planner import specimens
                    doc = specimens.full_decisions()
                    doc["loop"] = {"plan_semantics": plan_semantics}
                    (root / "decisions.yaml").write_text(specimens.decisions_yaml(doc))
            loop = root / ".hermes/skills/migration/fix-until-green/scripts"
            loop.mkdir(parents=True)
            (loop / "run-verify.sh").write_text(
                '#!/bin/bash\necho verify >> "$TEST_PHASE_CALLS"\necho "$*" >> "$TEST_PHASE_CALLS.args"\nexit %d\n' % verify_rc)
            (loop / "advance.py").write_text(
                'import os,sys\nwith open(os.environ["TEST_PHASE_CALLS"], "a") as f: f.write("baseline\\n")\n'
                'sys.exit(%d)\n' % baseline_rc)
            if bootstrap:
                (root / "evidence/producers").mkdir(parents=True)
                (root / "evidence/producers/bootstrap.json").write_text("{}")
            calls = root / "calls"
            proc = subprocess.run(["bash", str(scripts / SCRIPT.name), "--root", str(root)],
                                  text=True, capture_output=True,
                                  env={**os.environ, "TEST_PHASE_CALLS": str(calls)})
            if args_out is not None:
                a = Path(str(calls) + ".args")
                args_out.extend(a.read_text().splitlines() if a.exists() else [])
            return proc, calls.read_text().splitlines() if calls.exists() else []

    def test_plan_semantics_v1_runs_the_initial_analysis_boundary(self):
        args = []
        proc, calls = self.run_wrapper(plan_semantics="v1", args_out=args)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(args), 1)
        self.assertTrue(args[0].endswith("--initial"), args)

    def test_without_the_decision_the_first_verification_is_unchanged(self):
        for mode in ("", "off"):
            args = []
            proc, _calls = self.run_wrapper(plan_semantics=mode, args_out=args)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("--initial", args[0], mode)

    def test_silent_verifier_failure_is_named_and_never_creates_baseline(self):
        proc, calls = self.run_wrapper(verify_rc=17)
        self.assertEqual(proc.returncode, 17)
        self.assertEqual(calls, ["verify"])
        self.assertIn("FAIL: WORKLIST_PHASE phase=verify exit=17", proc.stderr)
        self.assertNotIn("phase=baseline", proc.stderr)

    def test_baseline_failure_is_distinguished_without_reverification(self):
        proc, calls = self.run_wrapper(baseline_rc=23)
        self.assertEqual(proc.returncode, 23)
        self.assertEqual(calls, ["verify", "baseline"])
        self.assertIn("FAIL: WORKLIST_PHASE phase=baseline exit=23", proc.stderr)

    def test_success_runs_each_phase_once(self):
        proc, calls = self.run_wrapper()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(calls, ["verify", "baseline"])
        self.assertIn("WORKLIST_PHASE: baseline passed", proc.stdout)

    def test_missing_bootstrap_never_runs_tools(self):
        proc, calls = self.run_wrapper(bootstrap=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(calls, [])
        self.assertIn("WORKLIST_NO_BOOTSTRAP", proc.stderr)


if __name__ == "__main__":
    unittest.main()
