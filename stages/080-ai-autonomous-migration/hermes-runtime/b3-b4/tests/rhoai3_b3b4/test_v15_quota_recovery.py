"""V15-1 change 1 (tmp/v15-run-20260925/V15-1-DURABLE-QUOTA-DESIGN.md, section 2):
automatic recovery from a local request-allowance wait through the pinned
NATIVE temporary-rate-limit path (patch 0009).

The worker stops before sending, persists a structured ``local_budget_deferral``
bound to its run, and exits with ``KANBAN_RATE_LIMIT_EXIT_CODE``. The reaper
ends the run with the neutral ``rate_limited`` outcome (no failure counted or
reset; source phase kept). The respawn guard holds the same card until
``retry_not_before`` and a free slot in the shared ledger; then the native
dispatcher resumes it. Real kanban dispatcher and real
``hermes -p implementer chat -q`` workers; fake provider on loopback.
"""

import json
import os
import signal
import time
import types

from . import _harness as H
from .fake_openai_server import FakeProvider
from .test_r2_request_pacer import COMPLETE, _kanban, _ledger_lines, _set_budget


def _write_ledger(ledger, stamps):
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("".join(f"{t:.6f} 1 seed\n" for t in stamps))


def _shift_ledger(ledger, seconds):
    """Simulate the passing of time for the worker subprocesses (real clock)."""
    lines = [l.split(" ", 1) for l in ledger.read_text().splitlines() if l.strip()]
    ledger.write_text("".join(f"{float(t) - seconds:.6f} {rest}\n" for t, rest in lines))


def _elapse(conn, tid, ledger, seconds):
    """Simulate ``seconds`` of wall-clock time passing for the real-clock worker
    and dispatcher: every ledger entry and the persisted retry_not_before move
    back by the same amount (their relation to each other is unchanged)."""
    _shift_ledger(ledger, seconds)
    conn.execute(
        "UPDATE task_runs SET metadata = json_set(metadata, '$.retry_not_before', "
        "json_extract(metadata, '$.retry_not_before') - ?) "
        "WHERE task_id = ? AND outcome = 'rate_limited' "
        "AND json_extract(metadata, '$.retry_not_before') IS NOT NULL",
        (float(seconds), tid))
    conn.commit()


def _last_run(conn, tid):
    row = conn.execute("SELECT id, outcome, error, metadata FROM task_runs WHERE task_id = ? "
                       "ORDER BY id DESC LIMIT 1", (tid,)).fetchone()
    d = dict(row)
    d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
    return d


def _v15_ledger(ledger, now):
    """190-request-mode window as in v15: 190 slots spent in the last 34.4 min;
    the oldest frees 1,535 s from now (12:09:40 -> 12:35:15)."""
    limit = int(H.PROD_QUOTA["max_requests_per_window"])
    window = float(H.PROD_QUOTA["window_seconds"])
    oldest = now - (window - 1535.0)
    stamps = [oldest] + [now - 2064.0 + i * (2063.0 / (limit - 1)) for i in range(1, limit)]
    _write_ledger(ledger, stamps)
    return oldest + window


def test_v15_regression_neutral_deferral_then_same_card_resumes(tmp_path, monkeypatch):
    """Exact v15 shape: allowance exhausted, next slot 1,535 s away (> 900 s).
    One neutral deferred run, no three-second respawn, no gave_up, no counter
    change; at eligibility the same card resumes automatically and completes."""
    ledger = tmp_path / "state" / "requests.log"
    _set_budget(monkeypatch, ledger, H.PROD_BUDGET, max_wait=H.PROD_MAX_WAIT)
    with FakeProvider([COMPLETE, ("text", "done")]) as provider:
        kb, conn, tid = _kanban(tmp_path, monkeypatch, provider)
        now = time.time()
        eligible_at = _v15_ledger(ledger, now)
        exit_code = H.dispatch_and_reap(kb, conn, tid)
        assert exit_code == kb.KANBAN_RATE_LIMIT_EXIT_CODE
        assert kb.detect_crashed_workers(conn) == []        # not a crash
        task = kb.get_task(conn, tid)
        assert task.status == "ready" and task.consecutive_failures == 0
        run = _last_run(conn, tid)
        assert run["outcome"] == "rate_limited"
        assert run["metadata"]["local_budget_deferral"] is True
        assert abs(run["metadata"]["retry_not_before"] - eligible_at) < 2.0
        assert run["error"].startswith("LOCAL_BUDGET_WAIT:")
        assert provider.chat_requests() == []
        # The dispatcher does not respawn it (no three-second retry).
        res = kb.dispatch_once(conn)
        assert res.spawned == [] and (tid, "local_budget_wait") in res.respawn_guarded
        # Fake clock at eligibility: the guard releases the card only when the
        # shared ledger has a free slot at that time.
        from agent import request_pacer

        real_time, real_now = kb.time, request_pacer._now
        try:
            at = eligible_at - 60                            # 60 s before: still held
            kb.time = types.SimpleNamespace(**{**vars(time), "time": lambda: at})
            request_pacer._now = lambda: at
            assert kb.check_respawn_guard(conn, tid) == "local_budget_wait"
            at = eligible_at + 5                             # after: released
            assert kb.check_respawn_guard(conn, tid) is None
        finally:
            kb.time, request_pacer._now = real_time, real_now
        # Real resumption: let the window roll (shift the ledger) and tick.
        _elapse(conn, tid, ledger, eligible_at - time.time() + 5)
        exit_code = H.dispatch_and_reap(kb, conn, tid)      # the same card, no new task
        assert exit_code == 0
        task = kb.get_task(conn, tid)
        assert task.status == "done" and task.consecutive_failures == 0
        kinds = [k for k, _ in H.events(conn, tid)]
        assert "gave_up" not in kinds and "crashed" not in kinds and "protocol_violation" not in kinds
        assert len(provider.chat_requests()) == 2
        assert conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 1
        conn.close()


def test_genuine_failure_then_deferral_keeps_the_failure_count(tmp_path, monkeypatch):
    """A genuine crash counts 1; a later quota deferral neither increments nor
    clears it (implementer origin, real worker)."""
    ledger = tmp_path / "state" / "requests.log"
    _set_budget(monkeypatch, ledger, "2/3600", max_wait=5)
    with FakeProvider([("stall", 60.0)]) as provider:
        kb, conn, tid = _kanban(tmp_path, monkeypatch, provider)
        # 1. genuine crash: the worker is killed mid-request.
        res = kb.dispatch_once(conn)
        pid = kb.get_task(conn, tid).worker_pid
        deadline = time.time() + 60
        while not provider.chat_requests() and time.time() < deadline:
            time.sleep(0.1)
        os.kill(pid, signal.SIGKILL)
        kb._record_worker_exit(pid, H.wait_exit(pid))
        assert kb.detect_crashed_workers(conn) == [tid]
        assert kb.get_task(conn, tid).consecutive_failures == 1
        # 2. quota deferral on the next run.
        now = time.time()
        _write_ledger(ledger, [now - 100, now - 50])
        H.dispatch_and_reap(kb, conn, tid)
        assert kb.detect_crashed_workers(conn) == []
        task = kb.get_task(conn, tid)
        assert task.consecutive_failures == 1                # neither +1 nor reset
        assert _last_run(conn, tid)["outcome"] == "rate_limited"
        conn.close()


def test_reviewer_origin_deferral_returns_to_review(tmp_path, monkeypatch):
    """Reviewer origin: a review claim that defers returns to ``review`` (its
    source phase), neutrally. Uses the pinned claim/reap functions directly."""
    ledger = tmp_path / "state" / "requests.log"
    _set_budget(monkeypatch, ledger, "2/3600", max_wait=5)
    with FakeProvider([("text", "x")]) as provider:
        kb, conn, tid = _kanban(tmp_path, monkeypatch, provider)
        conn.execute("UPDATE tasks SET status = 'review', consecutive_failures = 1 WHERE id = ?", (tid,))
        conn.commit()
        claimed = kb.claim_review_task(conn, tid)
        assert claimed is not None
        task = kb.get_task(conn, tid)
        fake_pid = 999_999
        conn.execute("UPDATE tasks SET worker_pid = ?, started_at = ? WHERE id = ?",
                     (fake_pid, int(time.time()) - 60, tid))
        conn.commit()
        kb.record_local_budget_deferral(conn, tid, task.current_run_id, {
            "kind": "local_budget_deferral", "accounting_mode": "request",
            "retry_not_before": time.time() + 600, "model": "fake-model"})
        kb._record_worker_exit(fake_pid, 75 << 8)            # WEXITSTATUS 75
        assert kb.detect_crashed_workers(conn) == []
        task = kb.get_task(conn, tid)
        assert task.status == "review"
        assert task.consecutive_failures == 1
        assert _last_run(conn, tid)["outcome"] == "rate_limited"
        assert kb.check_respawn_guard(conn, tid, lane="review") == "local_budget_wait"
        conn.close()


def test_dispatcher_restart_during_deferral_and_stop_prevents_dispatch(tmp_path, monkeypatch):
    """The reap record is lost (dispatcher restart): the persisted deferral still
    ends the run neutrally. A fresh connection sees the same due time. A manual
    stop (block) prevents later dispatch even after eligibility."""
    ledger = tmp_path / "state" / "requests.log"
    _set_budget(monkeypatch, ledger, "2/3600", max_wait=5)
    with FakeProvider([COMPLETE, ("text", "done")]) as provider:
        kb, conn, tid = _kanban(tmp_path, monkeypatch, provider)
        now = time.time()
        _write_ledger(ledger, [now - 100, now - 50])
        res = kb.dispatch_once(conn)
        pid = kb.get_task(conn, tid).worker_pid
        H.wait_exit(pid)                                    # reaped, but NOT recorded
        kb._recent_worker_exits.clear()                     # the dispatcher restarted
        assert kb.detect_crashed_workers(conn) == []
        task = kb.get_task(conn, tid)
        assert task.status == "ready" and task.consecutive_failures == 0
        due = _last_run(conn, tid)["metadata"]["retry_not_before"]
        conn.close()
        conn = kb.connect()                                 # restarted dispatcher
        assert _last_run(conn, tid)["metadata"]["retry_not_before"] == due
        assert kb.dispatch_once(conn).spawned == []
        # Stop: the operator blocks it; even with capacity free nothing spawns.
        kb.block_task(conn, tid, reason="operator stop")
        ledger.write_text("")
        assert kb.dispatch_once(conn).spawned == []
        assert provider.chat_requests() == []
        conn.close()


def test_candidate_edits_survive_the_pause(tmp_path, monkeypatch):
    """Changes made before the pause stay on the tree; the resumed run sees the
    quota-wait note and continues; no acceptance or rollback is manufactured."""
    ledger = tmp_path / "state" / "requests.log"
    _set_budget(monkeypatch, ledger, "1/3600", max_wait=5)
    edit = ("tool", "write_file", {"path": "src/Candidate.java", "content": "class Candidate {}\n"})
    with FakeProvider([edit, COMPLETE, ("text", "done")]) as provider:
        kb, conn, tid = _kanban(tmp_path, monkeypatch, provider)
        repo = tmp_path / "repo"
        H.dispatch_and_reap(kb, conn, tid)                  # 1 request (the edit), then the stop
        assert kb.detect_crashed_workers(conn) == []
        assert (repo / "src/Candidate.java").read_text() == "class Candidate {}\n"
        assert len(provider.chat_requests()) == 1
        assert _last_run(conn, tid)["outcome"] == "rate_limited"
        assert "LOCAL_BUDGET_WAIT" in (kb.get_task(conn, tid).last_failure_error or "")
        # The resumed worker's context (what kanban_show hands it) states the
        # quota wait and that the previous run's work stays on the tree.
        context = kb.build_worker_context(conn, tid)
        assert "LOCAL_BUDGET_WAIT" in context and "work stays on the tree" in context
        _elapse(conn, tid, ledger, 3600)
        H.dispatch_and_reap(kb, conn, tid)
        task = kb.get_task(conn, tid)
        assert task.status == "done" and task.consecutive_failures == 0
        assert (repo / "src/Candidate.java").read_text() == "class Candidate {}\n"
        conn.close()


def test_two_deferrals_consume_no_retry_but_a_crash_does(tmp_path, monkeypatch):
    """Two consecutive deferrals on a max_retries=1 card consume nothing (each
    run sends one request, then the 1-per-hour allowance defers it); a genuine
    crash on the third run then spends the retry and blocks it, as today."""
    ledger = tmp_path / "state" / "requests.log"
    _set_budget(monkeypatch, ledger, "1/3600", max_wait=5)
    echo = ("tool", "terminal", {"command": "echo step"})
    with FakeProvider([echo, echo, ("stall", 60.0)]) as provider:
        kb, conn, tid = _kanban(tmp_path, monkeypatch, provider)
        conn.execute("UPDATE tasks SET max_retries = 1 WHERE id = ?", (tid,))
        conn.commit()
        for n in (1, 2):
            assert H.dispatch_and_reap(kb, conn, tid) == kb.KANBAN_RATE_LIMIT_EXIT_CODE
            assert kb.detect_crashed_workers(conn) == []
            task = kb.get_task(conn, tid)
            assert task.status == "ready" and task.consecutive_failures == 0, n
            assert len(provider.chat_requests()) == n
            # Capacity returns after the window (simulated by shifting the ledger).
            _elapse(conn, tid, ledger, 3700)
        res = kb.dispatch_once(conn)
        assert [s[0] for s in res.spawned] == [tid]
        pid = kb.get_task(conn, tid).worker_pid
        deadline = time.time() + 60
        while len(provider.chat_requests()) < 3 and time.time() < deadline:
            time.sleep(0.1)
        os.kill(pid, signal.SIGKILL)
        kb._record_worker_exit(pid, H.wait_exit(pid))
        assert kb.detect_crashed_workers(conn) == [tid]
        task = kb.get_task(conn, tid)
        assert task.consecutive_failures == 1 and task.status == "blocked"
        conn.close()
