"""RHOAI3 B11 qualification: a halted kanban worker ends, and is not a success.

End-to-end through the real pinned entry points, with a scripted fake
OpenAI-compatible provider on loopback (fake_openai_server.py):

  kanban_db.dispatch_once
    -> _default_spawn: ``hermes -p implementer --cli --accept-hooks
       chat -q "work kanban task <id>"`` (a real subprocess)
    -> real terminal tool running ``find`` in the task workspace
    -> tool-loop guardrail halt
    -> process exit, reaped and classified by the dispatcher.

No real model or network is used. Takes roughly 15-30 s (two worker runs).
"""

import json
import os
import time
from pathlib import Path

import pytest
import yaml

from .fake_openai_server import FakeProvider

LOOP_ARGS = {"command": "find src/main/java -name PetDto.java"}
WORKER_MAX_TURNS = 12  # finite so an unpatched runtime ends (at the budget) instead of hanging


def _agent_requests(provider):
    # Exclude auxiliary requests (session-title generation has no tools).
    return [r for r in provider.requests
            if r.get("_path", "").endswith("/chat/completions") and r.get("tools")]


def _wait_exit(pid, timeout=240):
    deadline = time.time() + timeout
    while time.time() < deadline:
        wpid, status = os.waitpid(pid, os.WNOHANG)
        if wpid:
            return status
        time.sleep(0.25)
    os.kill(pid, 9)
    raise AssertionError(f"worker pid {pid} did not exit within {timeout}s")


def _setup_home(provider, repo):
    home = Path(os.environ["HERMES_HOME"])
    cfg = {
        "model": {"provider": "custom", "base_url": provider.base_url, "default": "fake-model",
                  "api_key": "sk-fake-0000000000", "context_length": 131072},
        "agent": {"max_turns": WORKER_MAX_TURNS},
        "tool_loop_guardrails": {"hard_stop_enabled": True},
        "terminal": {"backend": "local", "cwd": str(repo)},
        "compression": {"enabled": False},
        "memory": {"memory_enabled": False, "user_profile_enabled": False},
    }
    profile = home / "profiles" / "implementer"
    profile.mkdir(parents=True, exist_ok=True)
    (profile / "config.yaml").write_text(yaml.safe_dump(cfg))
    (home / "config.yaml").write_text(yaml.safe_dump(cfg))


def _events(conn, tid):
    return [(r["kind"], json.loads(r["payload"]) if r["payload"] else {})
            for r in conn.execute("SELECT kind, payload FROM task_events WHERE task_id = ? ORDER BY id", (tid,))]


def _runs(conn, tid):
    return [dict(r) for r in conn.execute(
        "SELECT id, status, outcome, error FROM task_runs WHERE task_id = ? ORDER BY id", (tid,))]


def _dispatch_and_reap(kb, conn, tid):
    res = kb.dispatch_once(conn)
    assert [s[0] for s in res.spawned] == [tid], f"expected {tid} to be spawned, got {res}"
    pid = kb.get_task(conn, tid).worker_pid
    status = _wait_exit(pid)
    kb._record_worker_exit(pid, status)
    return os.waitstatus_to_exitcode(status)


def test_halt_ends_process_without_false_completion(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_KANBAN_CRASH_GRACE_SECONDS", "0")
    for key in [k for k in os.environ if k.endswith("_API_KEY")]:
        monkeypatch.delenv(key, raising=False)
    repo = tmp_path / "repo"
    (repo / "src/main/java").mkdir(parents=True)

    with FakeProvider([("tool", "terminal", LOOP_ARGS)]) as provider:
        _setup_home(provider, repo)
        from hermes_cli import kanban_db as kb

        kb.init_db()
        conn = kb.connect()
        tid = kb.create_task(conn, title="B11 loop probe", body="find the generated DTO",
                             assignee="implementer", workspace_kind="dir",
                             workspace_path=str(repo))

        # ---- run 1 ------------------------------------------------------
        exit_code = _dispatch_and_reap(kb, conn, tid)
        reqs = _agent_requests(provider)
        # The worker stopped after the 5th identical successful call: exactly
        # five agent model requests, none after the halting tool result.
        assert len(reqs) == 5, f"worker made {len(reqs)} agent model requests"
        last_msgs = reqs[-1]["messages"]
        assert sum(1 for m in last_msgs if m.get("role") == "tool") == 4
        # Process exit code at this pin: 0 (non-quiet `chat -q` path). The
        # board, not the exit code, carries the outcome — asserted below.
        assert exit_code == 0

        # Dispatcher tick after exit: nothing to classify (the worker already
        # closed its run), so no protocol_violation and no double count.
        assert kb.detect_crashed_workers(conn) == []
        task = kb.get_task(conn, tid)
        assert task.status == "ready"
        assert task.consecutive_failures == 1
        runs = _runs(conn, tid)
        assert runs[-1]["outcome"] == "crashed"
        assert runs[-1]["error"].startswith("STOP WORKER_TOOL_LOOP: tool terminal, guardrail identical_call_streak_halt, count 5")
        # No raw argv on the board, only its hash.
        assert "PetDto" not in runs[-1]["error"]
        kinds = [k for k, _ in _events(conn, tid)]
        assert "completed" not in kinds and "protocol_violation" not in kinds

        # ---- run 2: native respawn, then the circuit breaker --------------
        _dispatch_and_reap(kb, conn, tid)
        assert len(_agent_requests(provider)) == 10
        assert kb.detect_crashed_workers(conn) == []
        task = kb.get_task(conn, tid)
        # DEFAULT_FAILURE_LIMIT (2) == the deployed kanban.failure_limit.
        assert task.status == "blocked"
        assert task.consecutive_failures == 2
        events = _events(conn, tid)
        gave_up = [p for k, p in events if k == "gave_up"]
        assert gave_up and gave_up[-1]["trigger_outcome"] == "crashed"
        assert gave_up[-1]["guardrail"]["code"] == "identical_call_streak_halt"
        assert "completed" not in [k for k, _ in events]
        assert [r["outcome"] for r in _runs(conn, tid)] == ["crashed", "gave_up"]

        # A blocked card is not respawned by the dispatcher.
        res = kb.dispatch_once(conn)
        assert res.spawned == []
        conn.close()
