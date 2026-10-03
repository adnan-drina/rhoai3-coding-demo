#!/usr/bin/env python3
"""v32: the Stage 050 producer installs the in-workspace stops and the worker launch shim.

Executes the producer's own `# >>> run budgets` block (from maas-api-key-provisioning.yaml)
against a disposable destination and Managed Scope:
  * a destination whose harness ships kernel/run_budget.py and kernel/worker_launch.py ->
    the enforcer is copied into Managed Scope and registered twice (pre_tool_call matcher .*,
    fail-open; on_kanban_dispatch_tick with the destination root and the stop records beside
    the request ledger), appended after any existing entry; the shim becomes the managed
    HERMES_BIN;
  * a selected profile without a positive run_input_token_budget -> refused by name;
  * a destination whose harness ships neither -> the hook config is untouched and no
    HERMES_BIN is written.
"""
from __future__ import annotations

import copy
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PRODUCER = Path(__file__).resolve().parent / "maas-api-key-provisioning.yaml"
PROFILES = Path(__file__).resolve().parent / "model-profiles.json"
KERNEL = Path(__file__).resolve().parents[5] / ("stages/080-ai-autonomous-migration/scaffold-repo/"
                                                 "quarkus-migration-scaffold/.hermes/kernel")
K2 = {"matcher": "write|terminal|kanban_complete", "command": "/m/agent-hooks/pre_tool_call.sh", "timeout": 5,
      "fail_closed": True}
RECONCILER = {"command": "python3 /d/.hermes/kernel/outcome_reconcile.py --root /d", "timeout": 120}


def block(name: str = "run budgets") -> str:
    text = PRODUCER.read_text()
    m = re.search(r"\n( *)# >>> %s\n(.*?)\n *# <<< %s" % (re.escape(name), re.escape(name)), text, re.S)
    if not m:
        raise SystemExit("FAIL: the producer's %s block is missing" % name)
    indent = len(m.group(1))
    return "\n".join(line[indent:] for line in m.group(2).splitlines())


class Producer(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.dest, self.managed = self.root / "dest", self.root / "managed"
        (self.dest / ".hermes" / "kernel").mkdir(parents=True)
        self.managed.mkdir()
        self.doc = json.loads(PROFILES.read_text())

    def tearDown(self):
        self.td.cleanup()

    def ship(self, *names):
        for n in names:
            shutil.copy2(KERNEL / n, self.dest / ".hermes" / "kernel" / n)

    def run_block(self, cfg, model=None, profiles=None):
        ns = {"os": __import__("os"), "shutil": shutil, "safe_root": str(self.dest), "cfg": cfg,
              "managed": str(self.managed), "hooks_dir": str(self.managed / "agent-hooks"),
              "MODEL_PROFILES": profiles or self.doc["profiles"], "DEFAULT_MODEL": model or self.doc["default_model"],
              "print": lambda *a: None}
        exec(block(), ns)
        return ns

    def test_a_shipped_harness_gets_both_stops_and_the_launch_shim(self):
        self.ship("run_budget.py", "worker_launch.py")
        for model in sorted(self.doc["profiles"]):
            with self.subTest(model=model):
                cfg = {"hooks": {"pre_tool_call": [dict(K2)], "on_kanban_dispatch_tick": [dict(RECONCILER)]}}
                ns = self.run_block(cfg, model=model)
                pre, tick = cfg["hooks"]["pre_tool_call"], cfg["hooks"]["on_kanban_dispatch_tick"]
                self.assertEqual((pre[0], tick[0]), (K2, RECONCILER))          # appended, the K2 entry stays first
                hook = self.managed / "agent-hooks" / "run_budget.py"
                self.assertEqual(hook.read_bytes(), (KERNEL / "run_budget.py").read_bytes())
                self.assertEqual(pre[1], {"matcher": ".*", "command": "%s %s pre-tool" % (sys.executable, hook), "timeout": 10})
                self.assertNotIn("fail_closed", pre[1])
                self.assertEqual(tick[1]["command"], "%s %s tick --root %s --stops %s" % (
                    sys.executable, hook, self.dest, "/projects/.platform/run-control-state/run-stops.jsonl"))
                shim = self.managed / "bin" / "hermes-worker-launch"
                self.assertEqual(ns["_launch_bin"], str(shim))
                self.assertEqual(shim.read_bytes(), (KERNEL / "worker_launch.py").read_bytes())
                self.assertTrue(shim.stat().st_mode & 0o111)

    def test_a_selected_profile_without_a_budget_is_refused(self):
        self.ship("run_budget.py")
        profiles = copy.deepcopy(self.doc["profiles"])
        for model in profiles:
            profiles[model].pop("run_input_token_budget")
        with self.assertRaises(SystemExit) as got:
            self.run_block({"hooks": {}}, profiles=profiles)
        self.assertIn("RUN_TOKEN_BUDGET", str(got.exception))

    def test_a_harness_without_them_is_untouched(self):
        cfg = {"hooks": {"pre_tool_call": [dict(K2)]}}
        ns = self.run_block(cfg)
        self.assertEqual(cfg, {"hooks": {"pre_tool_call": [K2]}})
        self.assertEqual(ns["_launch_bin"], "")
        self.assertFalse((self.managed / "bin").exists())

    def test_the_managed_env_routes_spawns_through_the_shim_only_when_shipped(self):
        text = PRODUCER.read_text()
        self.assertRegex(text, r'\n +if _launch_bin:\n +fh\.write\("HERMES_BIN=%s\\n" % _launch_bin\)')
        self.assertIn('fh.write("HERMES_REAL_BIN=/usr/local/bin/hermes\\n")', text)   # what the shim execs


if __name__ == "__main__":
    unittest.main()
