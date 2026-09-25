"""R2 (V13-PACER-FINAL-REVIEW §2 follow-up): a wait inside the transport hook.

An auxiliary call and a stream reconnect can wait for a slot inside the httpx
hook, after their request timers started. The wait must not be mistaken for a
stale provider stream, and a cancelled (or exhausted) wait must not leave a
request sending afterwards. Fake provider on loopback; small real delays.
"""

import threading
import time
from pathlib import Path

import yaml

from . import _harness as H
from .fake_openai_server import FakeProvider
from .test_r2_request_pacer import COMPLETE, _ledger_lines, _set_budget


def test_auxiliary_call_waits_in_hook_past_its_timeout(tmp_path, monkeypatch):
    """A 1 s request timeout does not cover the 3 s pacer wait: the call waits,
    then sends exactly one request."""
    from agent.auxiliary_client import _create_openai_client

    ledger = tmp_path / "requests.log"
    _set_budget(monkeypatch, ledger, "1/3", max_wait=30)
    ledger.write_text(f"{time.time():.6f} 1 seed\n")
    with FakeProvider([("text", "summary")]) as provider:
        client = _create_openai_client(api_key="sk-fake", base_url=provider.base_url)
        t0 = time.monotonic()
        client.chat.completions.create(model="m", messages=[{"role": "user", "content": "s"}], timeout=1.0)
        assert time.monotonic() - t0 >= 2.5
        assert len(provider.chat_requests()) == 1
    assert len(_ledger_lines(ledger)) == 2


def test_cancelled_wait_sends_nothing(tmp_path, monkeypatch):
    """A cancel check that turns true during the hook wait aborts it: nothing
    is sent, no slot is taken, and nothing arrives later."""
    from agent import request_pacer
    from agent.auxiliary_client import _create_openai_client

    ledger = tmp_path / "requests.log"
    _set_budget(monkeypatch, ledger, "1/60", max_wait=120)
    ledger.write_text(f"{time.time():.6f} 1 seed\n")
    cancelled = threading.Event()
    threading.Timer(1.5, cancelled.set).start()
    with FakeProvider([("text", "x")]) as provider:
        client = _create_openai_client(api_key="sk-fake", base_url=provider.base_url)
        with request_pacer.cancel_check(cancelled.is_set):
            try:
                client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])
                raise AssertionError("expected the cancelled wait to raise")
            except Exception as exc:
                cause = exc if isinstance(exc, request_pacer.RequestCancelledWhileWaiting) else exc.__cause__
                assert isinstance(cause, request_pacer.RequestCancelledWhileWaiting), exc
        time.sleep(1.5)                                   # nothing detached keeps sending
        assert provider.chat_requests() == []
    assert len(_ledger_lines(ledger)) == 1


def test_stream_reconnect_waits_in_hook_without_stale_kill(tmp_path, monkeypatch):
    """Kanban worker, stale-stream timeout 2 s. The first stream drops; the
    reconnect has to wait ~5 s for a slot (1 per 5 s) inside the transport
    hook. The watchdog must not treat that wait as a stale stream, the card
    completes, and every request that reached the provider took one slot."""
    repo = tmp_path / "repo"
    repo.mkdir()
    ledger = tmp_path / "state" / "requests.log"
    _set_budget(monkeypatch, ledger, "1/5", max_wait=60)
    # A 2 s stale-stream timeout. The producer's qwen3 model id carries a
    # 180 s reasoning floor (agent/reasoning_timeouts.py), so this test runs
    # the same config under a non-reasoning model id.
    cfg = H.worker_config(repo)
    cfg["model"]["default"] = "fake-model"
    prov = cfg["providers"][cfg["model"]["provider"]]
    prov["models"] = {"fake-model": {**next(iter(prov["models"].values())), "stale_timeout_seconds": 2}}
    cfg["providers"]["custom"]["stale_timeout_seconds"] = 2
    with FakeProvider([("drop",), COMPLETE, ("text", "done")]) as provider:
        H.clean_env(monkeypatch, provider)
        home = Path(H.write_home(cfg))
        from hermes_cli import kanban_db as kb

        kb.init_db()
        conn = kb.connect()
        tid = kb.create_task(conn, title="R2 reconnect", body="probe", assignee="implementer",
                             workspace_kind="dir", workspace_path=str(repo))
        H.dispatch_and_reap(kb, conn, tid)
        assert kb.get_task(conn, tid).status == "done"
        reqs = provider.chat_requests()
        assert len(reqs) == 3                              # drop, its reconnect, after the tool
        gaps = [b["_t"] - a["_t"] for a, b in zip(reqs, reqs[1:])]
        assert gaps[0] >= 4.5, gaps                        # the reconnect waited for its slot
        assert len(_ledger_lines(ledger)) == 3
        log = Path(kb.worker_log_path(tid)).read_text()
        assert "No response from provider" not in log and "no output from provider" not in log
        conn.close()
        time.sleep(1.0)
        assert len(provider.chat_requests()) == 3          # nothing sent after the worker ended
