"""V15-1 change 2 (V15-1-DURABLE-QUOTA-DESIGN.md sections 3 and 6): reserved-and-
settled token accounting (patch 0010).

Every physical HTTP attempt reserves C (the served prompt+output bound) under
the ledger lock and is admitted only if
settled_in_window + open_reservations + C <= B. A valid terminal response
settles exactly once to its validated usage; a terminal response without
usage settles at C; an uncertain end keeps the reservation open (it never
ages out). No request-count ceiling in token mode. Fake provider only; the
real pinned client paths (primary, auxiliary sync/async, streaming) and the
real kanban dispatcher/worker.
"""

import asyncio
import os
import subprocess
import sys
import textwrap
import time

import pytest

from . import _harness as H
from .fake_openai_server import FakeProvider
from .test_r2_request_pacer import COMPLETE, _kanban

C = H.TOKEN_RESERVATION
B = H.TOKEN_BUDGET


def _aux(provider):
    from agent.auxiliary_client import _create_openai_client

    return _create_openai_client(api_key="sk-fake", base_url=provider.base_url)


def _call(client, **kw):
    return client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}], **kw)


def _cause(exc, cls):
    return exc if isinstance(exc, cls) else getattr(exc, "__cause__", None)


def test_usage_reconciliation_releases_only_the_difference(tmp_path, monkeypatch):
    """A completed 100K-token request releases only C - 100000; a duplicate
    terminal event does not release twice."""
    from agent import request_pacer

    ledger = tmp_path / "tokens.log"
    H.set_token_mode(monkeypatch, ledger)
    with FakeProvider([("text", "ok", {"prompt_tokens": 90_000, "completion_tokens": 10_000})]) as provider:
        _call(_aux(provider))
    res, sets = H.token_ledger(ledger)
    (rid, (amount, _)), = res.items()
    assert amount == C
    assert sets == [(rid, 100_000, "settled")]
    cfg = request_pacer.config()
    fh = request_pacer._open_locked(str(ledger))
    try:
        settled, open_sum, _r, _s = request_pacer._token_state(fh, time.time(), cfg.window)
    finally:
        fh.close()
    assert sum(c for _, c in settled) + open_sum == 100_000          # released exactly C - 100000
    # A duplicate terminal event for the same request writes nothing.
    assert request_pacer.settle(rid, {"prompt_tokens": 1, "completion_tokens": 1}) is None
    assert H.token_ledger(ledger)[1] == sets


def test_streaming_cumulative_frames_do_not_undercharge(tmp_path, monkeypatch):
    """Cumulative usage frames (50K, 80K, then 100K terminal) settle once at the
    terminal record, 100K -- neither the first frame nor their sum."""
    ledger = tmp_path / "tokens.log"
    H.set_token_mode(monkeypatch, ledger)
    frames = [{"prompt_tokens": 50_000, "completion_tokens": 0},
              {"prompt_tokens": 80_000, "completion_tokens": 0}]
    step = ("text", "streamed", {"prompt_tokens": 90_000, "completion_tokens": 10_000, "usage_frames": frames})
    with FakeProvider([step]) as provider:
        stream = _call(_aux(provider), stream=True, stream_options={"include_usage": True})
        for _ in stream:
            pass
    _res, sets = H.token_ledger(ledger)
    assert [(c, s) for _, c, s in sets] == [(100_000, "settled")]


def test_throughput_without_a_request_ceiling(tmp_path, monkeypatch):
    """More than 190 requests in one hour are all admitted while actual usage
    plus open reservations stays below B (synthetic accounting demonstration)."""
    from agent import request_pacer

    ledger = tmp_path / "tokens.log"
    H.set_token_mode(monkeypatch, ledger, max_wait=0)
    n = 250
    with FakeProvider([("text", "ok", {"prompt_tokens": 55_000, "completion_tokens": 4_000})]) as provider:
        client = _aux(provider)
        for _ in range(n):
            _call(client)
        assert len(provider.chat_requests()) == n
    res, sets = H.token_ledger(ledger)
    assert len(res) == n and len(sets) == n
    assert sum(c for _, c, _ in sets) == n * 59_000 < B
    ok, _ = request_pacer.capacity_available()
    assert ok


def test_worst_case_194_fit_and_the_195th_waits_for_expiry(tmp_path, monkeypatch):
    """194 settled requests of C tokens fit below 51M; the 195th waits and is
    admitted only as eligible charge expires (fake clock)."""
    from agent import request_pacer

    ledger = tmp_path / "tokens.log"
    H.set_token_mode(monkeypatch, ledger, max_wait=0)
    clock = {"t": 1_000_000.0}
    monkeypatch.setattr(request_pacer, "_now", lambda: clock["t"])
    full = {"prompt_tokens": C - 4_096, "completion_tokens": 4_096}
    fits = B // C
    assert fits == 194
    with FakeProvider([("text", "ok", full)]) as provider:
        client = _aux(provider)
        for _ in range(fits):
            _call(client)
            clock["t"] += 1.0
        try:
            _call(client)
            raise AssertionError("the 195th worst-case request was admitted")
        except Exception as exc:
            stop = _cause(exc, request_pacer.RequestBudgetExhausted)
            assert isinstance(stop, request_pacer.RequestBudgetExhausted), exc
        assert len(provider.chat_requests()) == fits
        first_settle = min(float(l.split()[1]) for l in ledger.read_text().splitlines() if l.startswith("S "))
        assert stop.deferral["accounting_mode"] == "token"
        assert abs(stop.deferral["retry_not_before"] - (first_settle + H.TOKEN_WINDOW)) < 1e-3
        clock["t"] = first_settle + H.TOKEN_WINDOW - 1          # not yet expired
        with pytest.raises(Exception):
            _call(client)
        clock["t"] = first_settle + H.TOKEN_WINDOW + 1          # the oldest charge expired
        _call(client)
        assert len(provider.chat_requests()) == fits + 1


def test_missing_usage_and_uncertain_ends(tmp_path, monkeypatch):
    """Missing usage on a known terminal response charges C; an HTTP error
    response charges C; an interrupted stream grants no credit and its open
    reservation keeps counting through the window (retention: see
    test_open_reservation_retention_*); a cancelled request reserves nothing."""
    from agent import request_pacer

    ledger = tmp_path / "tokens.log"
    H.set_token_mode(monkeypatch, ledger)
    script = [("text", "no usage", {"no_usage": True}),
              ("http", 500, {}, {"error": {"message": "boom", "type": "server_error"}}),
              ("drop",)]
    with FakeProvider(script) as provider:
        client = _aux(provider)
        _call(client)                                            # terminal, no usage
        with pytest.raises(Exception):
            _call(client)                                        # HTTP 500: terminal, no usage
        for _ in _call(client, stream=True):                     # dropped stream (no terminal
            pass                                                 # chunk): uncertain end
        with request_pacer.cancel_check(lambda: True):           # cancelled before send
            with pytest.raises(Exception):
                _call(client)
        assert len(provider.chat_requests()) == 3
    res, sets = H.token_ledger(ledger)
    assert len(res) == 3                                         # the cancelled call reserved nothing
    assert [(c, s) for _, c, s in sets] == [(C, "missing_usage"), (C, "missing_usage")]
    open_rids = set(res) - {rid for rid, _, _ in sets}
    assert len(open_rids) == 1
    # One window later the settled charges have expired; the open reservation
    # still counts (it is held until reserved_at + hold + window).
    cfg = request_pacer.config()
    fh = request_pacer._open_locked(str(ledger))
    try:
        settled, open_sum, _r, _s = request_pacer._token_state(
            fh, time.time() + cfg.window + 1, cfg.window, cfg.hold)
    finally:
        fh.close()
    assert settled == [] and open_sum == C


def test_every_physical_attempt_reserves_separately(tmp_path, monkeypatch):
    """Kanban worker in token mode: a 429 retry, a truncation cap-boost retry, a
    stream reconnect and the completing calls each reserve separately; terminal
    responses settle (429 at C, the others to their usage), the dropped stream
    stays open (uncertain); the card completes."""
    ledger = tmp_path / "state" / "tokens.log"
    H.set_token_mode(monkeypatch, ledger)
    partial = '{"path": "src/main/java/Pet.java", "content": "public class Pet {\\n  priv'
    script = [("http", 429, {"Retry-After": "1"}, {"error": {"message": "slow down", "type": "x"}}),
              ("truncated_tool", "write_file", partial), ("drop",), COMPLETE, ("text", "done")]
    with FakeProvider(script) as provider:
        kb, conn, tid = _kanban(tmp_path, monkeypatch, provider)
        H.dispatch_and_reap(kb, conn, tid)
        assert kb.get_task(conn, tid).status == "done"
        reqs = provider.chat_requests()
        assert len(reqs) == 5
        assert all("x-rhoai3-pace-attempt" not in r["_headers"] for r in reqs)
        conn.close()
    res, sets = H.token_ledger(ledger)
    assert len(res) == 5 and all(a == C for a, _ in res.values())   # one reservation per physical request
    assert len(sets) == 4                                       # every terminal response settled once
    assert len(set(res) - {rid for rid, _, _ in sets}) == 1     # the dropped stream stays open
    charges = [c for _, c, _ in sets]
    assert charges[0] == C                                      # the 429: no usage -> full charge
    assert all(c < C for c in charges[1:])


def test_reservation_concurrency_across_processes(tmp_path, monkeypatch):
    """Sync auxiliary, async auxiliary and gateway processes compete for the
    last capacity (B = 2C): the lock admits exactly two reservations."""
    ledger = tmp_path / "tokens.log"
    H.set_token_mode(monkeypatch, ledger, budget=2 * C, max_wait=0)
    sync_call = textwrap.dedent("""
        import sys
        from agent.auxiliary_client import _create_openai_client
        c = _create_openai_client(api_key="k", base_url=sys.argv[1])
        try:
            c.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])
            print("sent")
        except Exception as e:
            print("refused", type(getattr(e, "__cause__", e)).__name__)
    """)
    async_call = textwrap.dedent("""
        import asyncio, sys, openai
        from agent import request_pacer
        async def main():
            c = request_pacer.attach(openai.AsyncOpenAI(api_key="k", base_url=sys.argv[1], max_retries=0))
            try:
                await c.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])
                print("sent")
            except Exception as e:
                print("refused", type(getattr(e, "__cause__", e)).__name__)
        asyncio.run(main())
    """)
    gateway_call = textwrap.dedent("""
        import sys
        import gateway.run  # noqa: F401
        from agent.auxiliary_client import call_llm
        try:
            call_llm(task="triage_specifier", provider="custom", model="m", base_url=sys.argv[1],
                     api_key="k", messages=[{"role": "user", "content": "x"}])
            print("sent")
        except Exception as e:
            print("refused", type(getattr(e, "__cause__", e)).__name__)
    """)
    with FakeProvider([("stall", 6.0)]) as provider:
        procs = [subprocess.Popen([sys.executable, "-c", code, provider.base_url], env=dict(os.environ),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for code in (sync_call, sync_call, async_call, gateway_call)]
        outs = [p.communicate(timeout=120)[0].strip() for p in procs]
        sent_to_provider = len(provider.chat_requests())
    assert sent_to_provider == 2, outs
    res, sets = H.token_ledger(ledger)
    assert len(res) == 2                                        # only reservations that fit
    assert sum("RequestBudgetExhausted" in o for o in outs) >= 1, outs


def test_governed_process_without_accounting_refuses_before_sending(tmp_path, monkeypatch):
    """A client path with the transport hook but without the settlement wiring,
    and mixed/incomplete profile settings, both refuse before any HTTP."""
    import openai

    from agent import request_pacer

    ledger = tmp_path / "tokens.log"
    H.set_token_mode(monkeypatch, ledger)
    with FakeProvider([("text", "x")]) as provider:
        raw = openai.OpenAI(api_key="k", base_url=provider.base_url, max_retries=0)
        raw._client.event_hooks["request"].append(request_pacer._sync_hook)   # hook only
        with pytest.raises(Exception) as err:
            _call(raw)
        assert isinstance(_cause(err.value, request_pacer.AccountingNotAttached),
                          request_pacer.AccountingNotAttached)
        # Mixed modes.
        monkeypatch.setenv("RHOAI3_REQUEST_BUDGET", "190/3600")
        with pytest.raises(request_pacer.AccountingConfigError):
            _aux(provider)
        monkeypatch.delenv("RHOAI3_REQUEST_BUDGET")
        # Reservation larger than the allowance.
        monkeypatch.setenv("RHOAI3_TOKEN_BUDGET", f"{C - 1}/3600")
        with pytest.raises(request_pacer.AccountingConfigError):
            _aux(provider)
        assert provider.chat_requests() == []


def test_token_mode_deferral_is_neutral_and_resumes(tmp_path, monkeypatch):
    """A token-mode allowance stop takes change 1's native path: neutral
    rate_limited run, no counter change, held until capacity is free."""
    import json

    ledger = tmp_path / "state" / "tokens.log"
    H.set_token_mode(monkeypatch, ledger, budget=2 * C, max_wait=5)
    now = time.time()
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        f"R {now - 100:.6f} 1 seed-a {C} seed\nS {now - 90:.6f} seed-a {C} settled\n"
        f"R {now - 80:.6f} 1 seed-b {C} seed\nS {now - 70:.6f} seed-b {C} settled\n")
    with FakeProvider([COMPLETE, ("text", "done")]) as provider:
        kb, conn, tid = _kanban(tmp_path, monkeypatch, provider)
        H.dispatch_and_reap(kb, conn, tid)
        assert kb.detect_crashed_workers(conn) == []
        task = kb.get_task(conn, tid)
        assert task.status == "ready" and task.consecutive_failures == 0
        run = conn.execute("SELECT outcome, metadata FROM task_runs WHERE task_id = ? ORDER BY id DESC LIMIT 1",
                           (tid,)).fetchone()
        meta = json.loads(run["metadata"])
        assert run["outcome"] == "rate_limited" and meta["accounting_mode"] == "token"
        assert abs(meta["retry_not_before"] - (now - 90 + H.TOKEN_WINDOW)) < 2.0
        assert kb.dispatch_once(conn).spawned == []
        assert provider.chat_requests() == []
        conn.close()


def _drop(client):
    for _ in _call(client, stream=True):
        pass


def _used(request_pacer, ledger, at):
    cfg = request_pacer.config()
    fh = request_pacer._open_locked(str(ledger))
    try:
        settled, open_sum, _r, _s = request_pacer._token_state(fh, at, cfg.window, cfg.hold)
    finally:
        fh.close()
    return sum(c for _, c in settled) + open_sum


def test_open_reservation_retention_counts_through_window(tmp_path, monkeypatch):
    """(a) A dropped stream's open reservation still counts at reserved_at +
    window (the architect's case: no speculative credit)."""
    from agent import request_pacer

    ledger = tmp_path / "tokens.log"
    H.set_token_mode(monkeypatch, ledger)
    clock = {"t": 1_000_000.0}
    monkeypatch.setattr(request_pacer, "_now", lambda: clock["t"])
    with FakeProvider([("drop",)]) as provider:
        _drop(_aux(provider))
    assert H.token_ledger(ledger)[1] == []                       # never settled
    t0 = clock["t"]
    assert _used(request_pacer, ledger, t0 + H.TOKEN_WINDOW) == C
    assert _used(request_pacer, ledger, t0 + H.TOKEN_WINDOW + H.TOKEN_HOLD - 1) == C


def test_open_reservation_retention_ends_after_hold_plus_window(tmp_path, monkeypatch):
    """(b) It stops counting after reserved_at + hold (900) + window."""
    from agent import request_pacer

    ledger = tmp_path / "tokens.log"
    H.set_token_mode(monkeypatch, ledger)
    clock = {"t": 1_000_000.0}
    monkeypatch.setattr(request_pacer, "_now", lambda: clock["t"])
    with FakeProvider([("drop",)]) as provider:
        _drop(_aux(provider))
    t0 = clock["t"]
    assert _used(request_pacer, ledger, t0 + H.TOKEN_HOLD + H.TOKEN_WINDOW + 1) == 0


def test_many_dropped_streams_do_not_exhaust_permanently(tmp_path, monkeypatch):
    """(c) 200 dropped streams spread over time: the allowance fills at 194
    open reservations, the 195th waits with a computable wake time, and
    capacity returns as the oldest open reservations pass hold + window --
    all 200 are eventually admitted."""
    from agent import request_pacer

    ledger = tmp_path / "tokens.log"
    H.set_token_mode(monkeypatch, ledger, max_wait=0)
    clock = {"t": 1_000_000.0}
    monkeypatch.setattr(request_pacer, "_now", lambda: clock["t"])
    admitted = refused = 0
    with FakeProvider([("drop",)]) as provider:
        client = _aux(provider)
        while admitted < 200:
            try:
                _drop(client)
                admitted += 1
                clock["t"] += 10.0                               # one drop every 10 s
            except Exception as exc:
                stop = _cause(exc, request_pacer.RequestBudgetExhausted)
                assert isinstance(stop, request_pacer.RequestBudgetExhausted), exc
                assert stop.uncertain is False                   # a wake time is known
                refused += 1
                clock["t"] = stop.next_slot_at + 0.001           # wait until it
        assert len(provider.chat_requests()) == 200
    assert refused >= 1                                          # it did fill up on the way
    res, sets = H.token_ledger(ledger)
    assert len(res) == 200 and sets == []                        # all open, none settled


def test_hold_shorter_than_request_timeout_is_refused(tmp_path, monkeypatch):
    """A hold below the configured request timeout is refused before sending."""
    from agent import request_pacer

    ledger = tmp_path / "tokens.log"
    H.set_token_mode(monkeypatch, ledger)
    monkeypatch.setenv("RHOAI3_TOKEN_RESERVATION_HOLD_SECONDS", "600")
    with pytest.raises(request_pacer.AccountingConfigError):
        request_pacer.config()


def test_default_hold_follows_the_longest_client_timeout(tmp_path, monkeypatch):
    """Unset hold defaults to the longest client request timeout the process
    honours (here HERMES_API_TIMEOUT=1800, as the producer's managed .env
    sets); an explicit hold below it is refused."""
    from agent import request_pacer

    ledger = tmp_path / "tokens.log"
    H.set_token_mode(monkeypatch, ledger)
    monkeypatch.delenv("RHOAI3_TOKEN_RESERVATION_HOLD_SECONDS")
    monkeypatch.setenv("HERMES_API_TIMEOUT", "1800")
    assert request_pacer.config().hold == 1800
    monkeypatch.setenv("RHOAI3_TOKEN_RESERVATION_HOLD_SECONDS", "900")
    with pytest.raises(request_pacer.AccountingConfigError):
        request_pacer.config()
