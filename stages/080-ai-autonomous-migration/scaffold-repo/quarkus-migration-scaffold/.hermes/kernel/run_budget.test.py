#!/usr/bin/env python3
"""v32: the per-run token budget and the two in-workspace migration stops (kernel/run_budget.py).

Board and session databases are built with the columns the pinned runtime reads (task_runs,
tasks, sessions); the native writes go through a recording fake, and the retry-accounting
parity is checked against a stand-in hermes_cli.kanban_db -- and, when a Hermes source tree
is available (HERMES_AGENT_SRC, or /opt/hermes-agent in the workspace image), against the
runtime's own iteration-exhaustion call.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/kernel/run_budget.test.py
"""
from __future__ import annotations

import ast
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_budget as RB  # noqa: E402

REPO = HERE.parents[5]
PROFILES = REPO / "gitops/stages/050-advanced-app-platform/base/devspaces/model-profiles.json"
DEFAULTS = HERE.parents[1] / "run-defaults.json"
T0 = 1_790_000_000.0


def board(path: Path, tasks=(), runs=()) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, status TEXT, current_run_id INTEGER, worker_pid INTEGER, "
                 "created_at INTEGER, completed_at INTEGER)")
    conn.execute("CREATE TABLE task_runs (id INTEGER PRIMARY KEY, task_id TEXT, status TEXT, started_at INTEGER, "
                 "ended_at INTEGER, outcome TEXT, error TEXT, summary TEXT, worker_pid INTEGER)")
    for t in tasks:
        conn.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?)", (t["id"], t["status"], t.get("run"), t.get("pid"),
                                                              int(T0), t.get("completed_at")))
    for r in runs:
        conn.execute("INSERT INTO task_runs VALUES (?,?,?,?,?,?,?,?,?)", (r["id"], r["task"], r.get("status", "running"),
                     int(r.get("started", T0)), r.get("ended"), r.get("outcome"), r.get("error"), None, r.get("pid")))
    conn.commit()
    return conn


def sessions(path: Path, rows) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, parent_session_id TEXT, started_at REAL, "
                 "input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER, cache_write_tokens INTEGER)")
    for r in rows:
        conn.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)",
                     (r["id"], r.get("source", "kanban"), r.get("parent"), r.get("started", T0 + 10), r.get("input", 0),
                      r.get("output", 0), r.get("cache_read", 0), r.get("cache_write", 0)))
    conn.commit()
    conn.close()


class Native:
    def __init__(self):
        self.failures, self.blocks = [], []

    def record_run_failure(self, task, error):
        self.failures.append((task, error))

    def block(self, task, reason, run_id=None):
        self.blocks.append((task, reason, run_id))
        return True


def profile(limit=12_000_000, model="m-under-test"):
    prof = {"provider": "p"}
    if limit is not None:
        prof["run_input_token_budget"] = limit
    return {"default_model": model, "profiles": {model: prof}}


class PerRun(unittest.TestCase):
    """RUN_TOKEN_BUDGET_EXHAUSTED: one worker run, enforced before each of its tool calls."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.home = self.root / "profiles" / "implementer"
        self.home.mkdir(parents=True)
        self.conn = board(self.root / "kanban.db",
                          tasks=[{"id": "t_card", "status": "running", "run": 7, "pid": 4242}],
                          runs=[{"id": 6, "task": "t_card", "started": T0 - 7200, "ended": T0 - 3600, "outcome": "crashed"},
                                {"id": 7, "task": "t_card", "started": T0, "pid": 4242}])
        self.env = {"HERMES_KANBAN_TASK": "t_card", "HERMES_KANBAN_RUN_ID": "7", "HERMES_HOME": str(self.home)}
        self.native, self.killed = Native(), []

    def tearDown(self):
        self.conn.close()
        self.td.cleanup()

    def tree(self, live_input):
        # the worker's root session, a compression child (live) and a delegated child; an earlier run's
        # session and another tree that started inside this run are not this run's
        sessions(self.home / "state.db", [
            {"id": "s-old", "started": T0 - 7000, "input": 50_000_000},
            {"id": "s-root", "started": T0 + 5, "input": 3_000_000, "cache_read": 1_000_000},
            {"id": "s-comp", "parent": "s-root", "started": T0 + 900, "input": live_input, "cache_write": 0},
            {"id": "s-dele", "parent": "s-root", "started": T0 + 950, "input": 500_000},
            {"id": "s-other", "started": T0 + 20, "input": 40_000_000},
        ])

    def check(self, tool="terminal", sid="s-comp", prof=None):
        return RB.check_tool_call({"tool_name": tool, "session_id": sid}, self.env, self.conn, self.native,
                                  self.killed.append, prof or profile(), parent_pid=999)

    def test_a_run_under_the_limit_is_unaffected(self):
        self.tree(live_input=7_000_000)                  # 3M + 1M cached + 7M + 0.5M = 11.5M < 12M
        self.assertEqual(RB.run_prompt_tokens(self.home / "state.db", "s-comp", T0), 11_500_000)
        self.assertIsNone(self.check())
        self.assertEqual((self.native.failures, self.killed), ([], []))

    def test_a_run_crossing_the_limit_ends_with_the_named_reason(self):
        self.tree(live_input=7_600_000)                  # 12.1M >= 12M
        got = self.check()
        self.assertEqual(got["action"], "block")
        self.assertTrue(got["message"].startswith("RUN_TOKEN_BUDGET_EXHAUSTED: 12100000 of 12000000 input tokens"))
        self.assertEqual(self.native.failures, [("t_card", got["message"])])
        self.assertEqual(self.killed, [4242])            # the dispatcher-recorded worker pid

    def test_the_root_session_and_any_descendant_count_the_same_tree(self):
        self.tree(live_input=7_600_000)
        for sid in ("s-root", "s-comp", "s-dele"):
            self.assertEqual(RB.run_prompt_tokens(self.home / "state.db", sid, T0), 12_100_000)
        self.assertEqual(RB.run_prompt_tokens(self.home / "state.db", "s-other", T0), 40_000_000)
        self.assertIsNone(RB.run_prompt_tokens(self.home / "state.db", "s-old", T0))    # not a session of this run

    def test_a_terminator_over_the_limit_still_ends_the_run_itself(self):
        self.tree(live_input=9_000_000)
        for tool in sorted(RB.TERMINATORS):
            self.assertIsNone(self.check(tool=tool))
        self.assertEqual(self.native.failures, [])

    def test_no_pinned_budget_or_no_live_run_records_nothing(self):
        self.tree(live_input=90_000_000)
        self.assertIsNone(self.check(prof=profile(limit=None)))
        self.conn.execute("UPDATE tasks SET current_run_id = 8")
        self.assertIsNone(self.check())                  # not this execution's live run
        self.assertEqual(self.native.failures, [])

    def test_a_worker_still_calling_tools_after_its_budget_stop_is_refused_again(self):
        self.conn.execute("UPDATE task_runs SET ended_at = ?, outcome = 'timed_out', error = ? WHERE id = 7",
                          (int(T0 + 1000), RB.run_reason(12_100_000, 12_000_000)))
        self.conn.execute("UPDATE tasks SET status = 'ready', current_run_id = NULL, worker_pid = NULL")
        got = self.check()
        self.assertEqual(got["action"], "block")
        self.assertIn("this worker run has ended", got["message"])
        self.assertEqual((self.killed, self.native.failures), ([999], []))      # re-signalled, not recorded twice

    def test_the_hook_entry_fails_open_and_writes_nothing_under_the_limit(self):
        self.tree(live_input=1_000)
        managed = self.root / "managed"
        managed.mkdir()
        (managed / "model-profile.json").write_text(json.dumps(profile()))
        self.conn.commit()
        env = dict(os.environ, HERMES_MANAGED_DIR=str(managed), HERMES_KANBAN_DB=str(self.root / "kanban.db"), **self.env)
        p = subprocess.run([sys.executable, str(HERE / "run_budget.py"), "pre-tool"], env=env, capture_output=True, text=True,
                           input=json.dumps({"hook_event_name": "pre_tool_call", "tool_name": "terminal", "session_id": "s-comp"}))
        self.assertEqual((p.returncode, p.stdout), (0, ""), p.stderr)
        env.pop("HERMES_KANBAN_DB")
        p = subprocess.run([sys.executable, str(HERE / "run_budget.py"), "pre-tool"], env=env, capture_output=True, text=True,
                           input="not json")
        self.assertEqual((p.returncode, p.stdout), (0, ""))


class RetryAccounting(unittest.TestCase):
    """The stop is recorded with the native call the runtime makes for an exhausted iteration budget."""

    WANT = {"outcome": "timed_out", "release_claim": True, "end_run": True}

    def test_the_native_record_is_the_iteration_exhaustion_call(self):
        calls = []
        kb = types.ModuleType("hermes_cli.kanban_db")
        kb.connect = lambda *a, **k: "conn"
        kb._record_task_failure = lambda conn, task, **kw: calls.append((conn, task, kw))
        pkg = types.ModuleType("hermes_cli")
        pkg.kanban_db = kb
        saved = {k: sys.modules.get(k) for k in ("hermes_cli", "hermes_cli.kanban_db")}
        sys.modules.update({"hermes_cli": pkg, "hermes_cli.kanban_db": kb})
        try:
            RB.HermesNative().record_run_failure("t_card", "RUN_TOKEN_BUDGET_EXHAUSTED: 2 of 1 input tokens")
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v
        self.assertEqual(calls, [("conn", "t_card", dict(self.WANT, error="RUN_TOKEN_BUDGET_EXHAUSTED: 2 of 1 input tokens"))])

    def test_parity_with_the_pinned_runtime_source_when_available(self):
        src = next((Path(p) for p in (os.environ.get("HERMES_AGENT_SRC") or "", "/opt/hermes-agent")
                    if p and (Path(p) / "agent/turn_finalizer.py").is_file()), None)
        if src is None:
            self.skipTest("no Hermes source tree (set HERMES_AGENT_SRC)")
        tree = ast.parse((src / "agent/turn_finalizer.py").read_text())
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_record_kanban_budget_exhausted")
        call = next(n for n in ast.walk(fn) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "_record_task_failure")
        kw = {k.arg: ast.literal_eval(k.value) for k in call.keywords if k.arg in self.WANT}
        self.assertEqual(kw, self.WANT)
        self.assertNotIn("failure_limit", {k.arg for k in call.keywords})


class MigrationStops(unittest.TestCase):
    """MIGRATION_TOKEN_BUDGET_EXHAUSTED and MIGRATION_NO_ACCEPTED_CHECKPOINT on the dispatcher tick."""

    LIMITS = {"run_input_token_budget": 250_000_000, "no_accepted_checkpoint_minutes": 240}

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.stops = self.root / "state" / "run-stops.jsonl"
        self.conn = board(self.root / "kanban.db",
                          tasks=[{"id": "t_a", "status": "done", "completed_at": int(T0 + 600)},
                                 {"id": "t_b", "status": "running", "run": 3, "pid": 5151},
                                 {"id": "t_c", "status": "ready"},
                                 {"id": "t_d", "status": "todo"}],
                          runs=[{"id": 1, "task": "t_a", "started": T0, "ended": T0 + 500, "outcome": "completed"},
                                {"id": 3, "task": "t_b", "started": T0 + 700, "pid": 5151}])
        self.native, self.killed = Native(), []

    def tearDown(self):
        self.conn.close()
        self.td.cleanup()

    def tick(self, used, now):
        return RB.tick(self.conn, self.native, self.killed.append, self.LIMITS, used, now, self.stops)

    def test_under_both_limits_nothing_happens(self):
        self.assertEqual(self.tick(249_999_999, T0 + 600 + 239 * 60), [])
        self.assertFalse(self.stops.exists())

    def test_the_token_budget_stops_the_run_with_its_name_and_holds_it(self):
        out = self.tick(250_000_001, T0 + 900)
        self.assertEqual(out[0]["fired"], RB.MIGRATION_TOKEN_CODE)
        self.assertTrue(out[0]["reason"].startswith("MIGRATION_TOKEN_BUDGET_EXHAUSTED: 250000001 of 250000000 input tokens"))
        self.assertEqual([(t, r) for t, _, r in self.native.blocks], [("t_b", 3), ("t_c", None)])   # running bound to its run
        self.assertEqual(self.killed, [5151])
        self.assertTrue(all(reason.startswith(RB.MIGRATION_TOKEN_CODE) for _, reason, _ in self.native.blocks))
        # a later tick holds the stop on a card that became ready, and records no second stop
        self.conn.execute("UPDATE tasks SET status = 'blocked' WHERE id IN ('t_b', 't_c')")
        self.conn.execute("UPDATE tasks SET status = 'ready' WHERE id = 't_d'")
        self.native.blocks.clear()
        self.tick(260_000_000, T0 + 960)
        self.assertEqual([t for t, _, _ in self.native.blocks], ["t_d"])
        self.assertEqual(len(RB.read_stops(self.stops)), 1)

    def test_a_lifted_token_stop_does_not_fire_again(self):
        self.tick(250_000_001, T0 + 900)
        self.assertEqual(RB.main(["lift", "--stops", str(self.stops), "--code", RB.MIGRATION_TOKEN_CODE, "--by", "operator"]), 0)
        self.native.blocks.clear()
        self.assertEqual(self.tick(300_000_000, T0 + 1000), [])
        self.assertEqual(self.native.blocks, [])

    def test_the_stall_stop_fires_after_n_minutes_without_an_accepted_card(self):
        self.assertEqual(self.tick(0, T0 + 600 + 239 * 60), [])           # 239 min since t_a was accepted
        out = self.tick(0, T0 + 600 + 240 * 60)
        self.assertEqual(out[0]["fired"], RB.STALL_CODE)
        self.assertTrue(out[0]["reason"].startswith("MIGRATION_NO_ACCEPTED_CHECKPOINT: no card accepted for 240 min "
                                                    "(limit 240 min"))
        self.assertIn("last accepted t_a", out[0]["reason"])
        self.assertEqual(sorted(t for t, _, _ in self.native.blocks), ["t_b", "t_c"])

    def test_the_stall_clock_starts_at_the_first_worker_run_and_rearms_after_a_lift(self):
        self.conn.execute("UPDATE tasks SET completed_at = NULL")
        self.assertEqual(self.tick(0, T0 + 239 * 60), [])                 # measured from run 1's start
        self.assertEqual(self.tick(0, T0 + 240 * 60)[0]["fired"], RB.STALL_CODE)
        lift_at = T0 + 300 * 60
        RB.append_stop(self.stops, {"event": "lift", "code": RB.STALL_CODE, "at": lift_at, "by": "operator"})
        self.assertEqual(self.tick(0, lift_at + 239 * 60), [])
        self.assertEqual(self.tick(0, lift_at + 240 * 60)[0]["fired"], RB.STALL_CODE)

    def test_nothing_fires_while_no_card_is_running_or_ready(self):
        self.conn.execute("UPDATE tasks SET status = 'blocked' WHERE status IN ('running', 'ready')")
        self.assertEqual(self.tick(999_999_999, T0 + 10_000 * 60), [])
        self.assertFalse(self.stops.exists())

    def test_lift_refuses_a_code_that_is_not_an_active_stop(self):
        self.assertEqual(RB.main(["lift", "--stops", str(self.stops), "--code", RB.STALL_CODE, "--by", "operator"]), 1)

    def test_the_migration_count_is_every_kanban_session_of_every_profile(self):
        home = self.root / "home"
        (home / "profiles" / "implementer").mkdir(parents=True)
        (home / "profiles" / "reviewer").mkdir(parents=True)
        sessions(home / "state.db", [{"id": "cli", "source": "cli", "input": 999}])
        sessions(home / "profiles" / "implementer" / "state.db", [{"id": "a", "input": 100, "cache_read": 20},
                                                                  {"id": "b", "input": 5, "cache_write": 1}])
        sessions(home / "profiles" / "reviewer" / "state.db", [{"id": "c", "input": 30}])
        dbs = RB.state_dbs(str(home / "profiles" / "implementer"))     # from a profile home or the base home alike
        self.assertEqual(len(dbs), 3)
        self.assertEqual(RB.migration_prompt_tokens(dbs), 156)


class DeclaredLimits(unittest.TestCase):
    def test_the_limits_are_the_initial_commit_never_the_working_tree(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            g = lambda *a: subprocess.run(["git", "-C", td, "-c", "user.email=t@t", "-c", "user.name=t", *a],  # noqa: E731
                                          check=True, capture_output=True)
            subprocess.run(["git", "init", "-q", td], check=True)
            (root / "run-defaults.json").write_text(json.dumps({"budget": dict(MigrationStops.LIMITS)}))
            g("add", "-A")
            g("commit", "-qm", "scaffold")
            (root / "run-defaults.json").write_text(json.dumps({"budget": {"run_input_token_budget": 10 ** 12}}))
            g("commit", "-qam", "a later raise")
            self.assertEqual(RB.declared_limits(root), (MigrationStops.LIMITS, ""))
            self.assertTrue(RB.declared_limits(root / "nowhere")[1])

    def test_the_golden_pins_both_run_level_stops(self):
        budget = json.loads(DEFAULTS.read_text())["budget"]
        self.assertEqual((budget["run_input_token_budget"], budget["no_accepted_checkpoint_minutes"]), (250_000_000, 240))
        for code in ("MIGRATION_TOKEN_BUDGET_EXHAUSTED", "MIGRATION_NO_ACCEPTED_CHECKPOINT"):
            self.assertTrue(any(code in s for s in budget["stopping_conditions"]), code)

    def test_every_platform_profile_pins_a_per_run_budget(self):
        if not PROFILES.is_file():
            self.skipTest("the platform profile table is not in this checkout (a published golden)")
        doc = json.loads(PROFILES.read_text())
        for model in doc["profiles"]:
            self.assertEqual(RB.run_limit(dict(doc, default_model=model)), 12_000_000, model)


if __name__ == "__main__":
    unittest.main()
