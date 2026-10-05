#!/usr/bin/env python3
"""v32 item 2 (harness half): a retry after a loop stop starts escalated (kernel/worker_launch.py).

The shim runs as the dispatcher would run it (HERMES_BIN, the worker argv of
hermes_cli/kanban_db.py _default_spawn) against a board database with the task_runs columns
the runtime writes; HERMES_REAL_BIN points at a stand-in that reports the argv and the one
variable it was started with.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/kernel/worker_launch.test.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import worker_launch as WL  # noqa: E402

PROFILES = HERE.parents[5] / "gitops/stages/050-advanced-app-platform/base/devspaces/model-profiles.json"
TASK = "t_9c1e"
HALT = ("STOP WORKER_TOOL_LOOP: tool terminal, guardrail identical_call_streak_halt, count 5, args_sha256 0f3a -- "
        "the worker was halted before another model request")
ITER = "Iteration budget exhausted (500/500) — task could not complete within the allowed iterations"
TOKENS = "RUN_TOKEN_BUDGET_EXHAUSTED: 12000417 of 12000000 input tokens -- this worker run read more prompt tokens"


def argv(task=TASK):
    return ["-p", "implementer", "--cli", "--accept-hooks", "--skills", "fix-until-green", "chat", "-q",
            "work kanban task %s" % task]


def escalating(model="m-thinking", turns=8, enabled=True):
    return {"default_model": model, "profiles": {model: {"loop_escalation": {"enabled": enabled, "max_turns": 8,
                                                                            "retry_start_turns": turns}}}}


class Launch(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.db = self.root / "kanban.db"
        conn = sqlite3.connect(str(self.db))
        conn.execute("CREATE TABLE task_runs (id INTEGER PRIMARY KEY, task_id TEXT, profile TEXT, status TEXT, "
                     "started_at INTEGER, ended_at INTEGER, outcome TEXT, summary TEXT, error TEXT)")
        conn.commit()
        conn.close()
        self.profile = self.root / "model-profile.json"
        self.use(escalating())

    def tearDown(self):
        self.td.cleanup()

    def use(self, doc):
        self.profile.write_text(json.dumps(doc))

    def run_row(self, rid, outcome=None, error=None, ended=True, task=TASK, summary=None):
        conn = sqlite3.connect(str(self.db))
        conn.execute("INSERT INTO task_runs (id, task_id, status, started_at, ended_at, outcome, summary, error) "
                     "VALUES (?,?,?,?,?,?,?,?)", (rid, task, outcome or "running", 1, 2 if ended else None, outcome,
                                                  summary, error))
        conn.commit()
        conn.close()

    def env(self, run, **extra):
        return dict({"HERMES_KANBAN_TASK": TASK, "HERMES_KANBAN_RUN_ID": str(run), "HERMES_KANBAN_DB": str(self.db)},
                    **extra)

    def started_with(self, run, args=None, **extra):
        env, _note = WL.launch_env(args or argv(), self.env(run, **extra), self.profile)
        return env.get(WL.ENV_OUT)

    def test_a_retry_after_each_loop_stop_starts_escalated(self):
        for rid, (outcome, error) in enumerate((("crashed", HALT), ("gave_up", HALT), ("timed_out", ITER),
                                                ("timed_out", TOKENS), ("gave_up", TOKENS)), start=1):
            with self.subTest(outcome=outcome, error=error[:30]):
                self.run_row(rid * 2, outcome, error)
                self.assertEqual(self.started_with(rid * 2 + 1), "8")

    def test_a_retry_after_any_other_end_starts_normally(self):
        for rid, (outcome, error, summary) in enumerate((
                ("crashed", "worker exited cleanly (rc=0) without calling kanban_complete or kanban_block — protocol "
                            "violation", None),
                ("timed_out", "elapsed 7209s > limit 7200s", None),
                ("blocked", None, "OWNER_REPAIR_PENDING: behavior depends on followup"),
                ("blocked", None, "quoting the predecessor: STOP WORKER_TOOL_LOOP was its end"),   # a summary is not a stop
                ("changes_requested", None, "keep the source profile name"),
                ("crashed", "HTTP 429 Too Many Requests", None)), start=1):
            with self.subTest(outcome=outcome):
                self.run_row(rid * 2, outcome, error, summary=summary)
                self.assertIsNone(self.started_with(rid * 2 + 1))

    def test_only_the_latest_ended_run_counts(self):
        self.run_row(4, "crashed", HALT)
        self.run_row(5, "changes_requested")
        self.assertIsNone(self.started_with(6))
        self.run_row(7, "crashed", HALT, task="t_other")              # another card's halt is not this card's
        self.assertIsNone(self.started_with(8))

    def test_a_first_run_starts_normally_and_drops_an_inherited_value(self):
        self.assertIsNone(self.started_with(1))
        self.assertIsNone(self.started_with(1, **{WL.ENV_OUT: "8"}))

    def test_a_profile_without_loop_escalation_never_starts_escalated(self):
        self.run_row(1, "crashed", HALT)
        for doc in ({"default_model": "m-plain", "profiles": {"m-plain": {"provider": "p"}}},
                    escalating(enabled=False), escalating(turns=0), escalating(turns=True)):
            with self.subTest(doc=doc):
                self.use(doc)
                self.assertIsNone(self.started_with(2))

    def test_the_platform_profiles_escalate_qwen38_retries_only(self):
        if not PROFILES.is_file():
            self.skipTest("the platform profile table is not in this checkout (a published golden)")
        table = json.loads(PROFILES.read_text())
        self.assertEqual(WL.retry_start_turns(dict(table, default_model="qwen3-8-27b-int4")), 8)
        self.assertEqual(WL.retry_start_turns(dict(table, default_model="qwen3-6-27b")), 0)

    def test_other_invocations_pass_through_unchanged(self):
        self.run_row(1, "crashed", HALT)
        env = self.env(2, **{WL.ENV_OUT: "3"})
        for args in (["kanban", "show", TASK, "--json"], argv(task="t_someone_else"), ["chat", "-q"]):
            with self.subTest(args=args):
                self.assertEqual(WL.launch_env(args, env, self.profile), (env, ""))

    def test_the_shim_execs_the_real_binary_with_the_same_argv(self):
        self.run_row(1, "timed_out", TOKENS)
        fake = self.root / "hermes"
        fake.write_text("#!%s\nimport json, os, sys\nprint(json.dumps({'argv': sys.argv[1:], 'turns': os.environ.get(%r)}))\n"
                        % (sys.executable, WL.ENV_OUT))
        fake.chmod(0o755)
        managed = self.root / "managed"
        managed.mkdir()
        (managed / "model-profile.json").write_text(self.profile.read_text())
        base = dict(os.environ, HERMES_REAL_BIN=str(fake), HERMES_MANAGED_DIR=str(managed))
        for run, args, want, note in ((2, argv(), "8", "retries run 1 of %s after a token-budget" % TASK),
                                      (2, ["kanban", "list", "--json"], None, "")):
            p = subprocess.run([sys.executable, str(HERE / "worker_launch.py"), *args], env=dict(base, **self.env(run)),
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(json.loads(p.stdout), {"argv": args, "turns": want})
            self.assertIn(note, p.stderr)
        # a profile that cannot be read never breaks the spawn
        (managed / "model-profile.json").write_text("{")
        p = subprocess.run([sys.executable, str(HERE / "worker_launch.py"), *argv()], env=dict(base, **self.env(2)),
                           capture_output=True, text=True)
        self.assertEqual(json.loads(p.stdout)["turns"], None)
        self.assertIn("started without a retry decision", p.stderr)


if __name__ == "__main__":
    unittest.main()
