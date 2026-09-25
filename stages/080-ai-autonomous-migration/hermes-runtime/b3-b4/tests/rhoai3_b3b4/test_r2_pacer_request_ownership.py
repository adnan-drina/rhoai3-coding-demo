"""R2 follow-up (V13-PACER-FINAL-REVIEW, "Follow-up at 86d153d5"): request ownership.

A reservation, its original deadline, its cancellation and its waiting status
belong to the request attempt that created them and are handed to the
transport hook explicitly (the attempt id travels on that attempt's own
request, and the hook strips it before sending):

(a) an auxiliary thread cannot consume the main request's reservation, and the
    main request keeps its original total-wait deadline (reviewer's 1,200 s case);
(b) a queued auxiliary request does not pause the stale watchdog of an
    already-sent, stalled main stream;
(c) a cancelled attempt passes the transport neither through its reservation
    nor after waiting, including cancellation from another thread and on the
    async hook;
plus the gateway process: its model calls are paced from the managed .env.

Fake provider on loopback; fake clock where the case is about time.
"""

import asyncio
import inspect
import os
import subprocess
import sys
import textwrap
import threading
import time

from . import _harness as H
from .fake_openai_server import FakeProvider
from .test_r2_request_pacer import _ledger_lines, _set_budget

HEADER = "x-rhoai3-pace-attempt"


def _reserve(request_pacer, **kw):
    """reserve() with a cancellation predicate where the runtime supports one."""
    if "cancelled" in inspect.signature(request_pacer.reserve).parameters:
        return request_pacer.reserve(**kw)
    kw.pop("cancelled", None)
    return request_pacer.reserve(**kw)


def _main_hook(request_pacer, label, attempt):
    """The main request's transport admission, handing over its attempt where
    the runtime has one (the pre-ownership runtime has no hand-off)."""
    if "attempt" in inspect.signature(request_pacer._hook_acquire).parameters:
        return request_pacer._hook_acquire(label, None, attempt)
    return request_pacer._hook_acquire(label, None)


def _cause(exc, cls):
    return exc if isinstance(exc, cls) else getattr(exc, "__cause__", None)


def test_auxiliary_cannot_consume_main_reservation_and_deadline_holds(tmp_path, monkeypatch):
    """Reviewer's case: reserve() waits 600 s; an auxiliary thread then asks the
    transport for a slot; the main request must still be admitted on its own
    reservation, within its original 900 s total bound (not 600 + 600)."""
    from agent import request_pacer

    limit = int(H.PROD_QUOTA["max_requests_per_window"])
    window = float(H.PROD_QUOTA["window_seconds"])
    max_wait = float(H.PROD_MAX_WAIT)
    ledger = tmp_path / "requests.log"
    _set_budget(monkeypatch, ledger, H.PROD_BUDGET, max_wait=H.PROD_MAX_WAIT)
    start = 1_000_000.0
    clock = {"t": start}
    sleeps = {}                                    # thread ident -> seconds slept

    def fake_sleep(seconds):
        ident = threading.get_ident()
        sleeps[ident] = sleeps.get(ident, 0.0) + seconds
        clock["t"] += seconds

    monkeypatch.setattr(request_pacer, "_now", lambda: clock["t"])
    monkeypatch.setattr(request_pacer, "_sleep", fake_sleep)
    # A full window: one slot frees at +600 s, the next at +1200 s, the rest at +3599 s.
    seed = [start - window + 600, start - window + 1200] + [start - 1] * (limit - 2)
    ledger.write_text("".join(f"{t:.6f} 1 seed\n" for t in seed))

    main = threading.get_ident()
    attempt = _reserve(request_pacer, cancelled=lambda: False)
    assert sleeps[main] == 600

    aux_result = {}

    def auxiliary():
        try:
            request_pacer._hook_acquire("auxiliary", None)
            aux_result["ok"] = True
        except Exception as exc:  # noqa: BLE001 — recorded, asserted below
            aux_result["error"] = exc

    t = threading.Thread(target=auxiliary)
    t.start()
    t.join(timeout=30)
    _main_hook(request_pacer, "main", attempt)

    labels = [l[2] for l in _ledger_lines(ledger)[limit:]]
    # The auxiliary call took (or waited for) its OWN slot; it did not consume
    # the main request's reservation.
    assert "auxiliary" in labels, f"auxiliary call took no slot of its own: {labels}"
    # The main request was admitted on its reservation: no second wait, no
    # second slot, total wait within the original deadline.
    assert sleeps[main] <= max_wait, f"main request waited {sleeps[main]} s > {max_wait} s"
    assert labels.count("reserve") == 1 and "main" not in labels, labels


def test_queued_auxiliary_does_not_pause_stale_watchdog_of_main_stream(tmp_path, monkeypatch):
    """An already-sent main stream stalls (no bytes for 10 s) while an
    auxiliary request of the same process waits for a slot. The 2 s stale
    watchdog must still kill the stalled stream (well before the stall ends)."""
    from unittest.mock import patch

    from agent import request_pacer
    from agent.auxiliary_client import _create_openai_client
    from run_agent import AIAgent

    ledger = tmp_path / "requests.log"
    _set_budget(monkeypatch, ledger, "2/30", max_wait=120)
    monkeypatch.setenv("HERMES_LOCAL_STREAM_STALE_TIMEOUT", "2")
    monkeypatch.setenv("HERMES_STREAM_RETRIES", "0")
    ledger.write_text(f"{time.time():.6f} 1 seed\n")
    stop_aux = threading.Event()
    with FakeProvider([("stall", 10.0)]) as provider:
        with patch("hermes_cli.config.load_config", return_value={}), \
             patch("hermes_cli.config.load_config_readonly", return_value={}):
            agent = AIAgent(api_key="sk-fake-0000000000", base_url=provider.base_url,
                            provider="custom", model="fake-model", quiet_mode=True,
                            skip_context_files=True, skip_memory=True, max_iterations=3)
        api_kwargs = {"model": "fake-model", "messages": [{"role": "user", "content": "hi"}]}
        outcome = {}

        def main_stream():
            t0 = time.monotonic()
            try:
                agent._interruptible_streaming_api_call(api_kwargs)
                outcome["result"] = "returned"
            except Exception as exc:  # noqa: BLE001
                outcome["result"] = type(exc).__name__
            outcome["seconds"] = time.monotonic() - t0

        m = threading.Thread(target=main_stream)
        m.start()
        # Wait until the main request has been sent (it took the 2nd slot).
        deadline = time.monotonic() + 10
        while not provider.chat_requests() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert provider.chat_requests(), "main stream request never reached the provider"
        # Now an auxiliary request of the same process queues for a slot.
        aux_err = {}

        def auxiliary():
            client = _create_openai_client(api_key="sk-fake", base_url=provider.base_url)
            with request_pacer.cancel_check(stop_aux.is_set):
                try:
                    client.chat.completions.create(model="m", messages=[{"role": "user", "content": "s"}])
                except Exception as exc:  # noqa: BLE001
                    aux_err["e"] = exc

        a = threading.Thread(target=auxiliary)
        a.start()
        m.join(timeout=30)
        stop_aux.set()
        a.join(timeout=30)
    assert outcome.get("seconds") is not None
    assert outcome["seconds"] < 7.0, (
        f"stalled main stream was not detected as stale while an auxiliary request "
        f"waited: it ran {outcome['seconds']:.1f} s ({outcome.get('result')})")
    assert isinstance(_cause(aux_err.get("e"), request_pacer.RequestCancelledWhileWaiting),
                      request_pacer.RequestCancelledWhileWaiting)
    assert len(provider.chat_requests()) == 1        # the queued auxiliary never sent


def test_cancelled_attempt_cannot_use_its_reservation(tmp_path, monkeypatch):
    """Prepaid path: a reserved attempt cancelled from another thread cannot
    reach the transport; and the reviewer's direct check."""
    from agent import request_pacer
    from agent.auxiliary_client import _create_openai_client

    ledger = tmp_path / "requests.log"
    _set_budget(monkeypatch, ledger, "5/3600", max_wait=60)
    # Reviewer's check on the extracted module: with a prepaid slot present, an
    # already-cancelled admission must raise, not return normally.
    _reserve(request_pacer, cancelled=lambda: False)
    try:
        request_pacer._hook_acquire("already-cancelled", lambda: True)
        raised = None
    except request_pacer.RequestCancelledWhileWaiting as exc:
        raised = exc
    assert raised is not None, "an already-cancelled admission passed on a prepaid slot"

    cancelled = threading.Event()
    attempt = _reserve(request_pacer, cancelled=cancelled.is_set)
    threading.Thread(target=cancelled.set).start()
    time.sleep(0.2)
    with FakeProvider([("text", "x")]) as provider:
        client = _create_openai_client(api_key="sk-fake", base_url=provider.base_url)
        try:
            client.chat.completions.create(
                model="m", messages=[{"role": "user", "content": "x"}],
                extra_headers={request_pacer.ATTEMPT_HEADER: attempt.id})
            sent = True
        except Exception as exc:
            assert isinstance(_cause(exc, request_pacer.RequestCancelledWhileWaiting),
                              request_pacer.RequestCancelledWhileWaiting), exc
            sent = False
        assert not sent and provider.chat_requests() == []


def test_cancelled_attempt_cannot_pass_after_waiting_sync_and_async(tmp_path, monkeypatch):
    """Waiting path: an attempt's second request (e.g. a stream reconnect) waits
    for a slot and is cancelled from another thread meanwhile; nothing is sent.
    Covers the sync hook and the async hook (AsyncOpenAI)."""
    import openai

    from agent import request_pacer
    from agent.auxiliary_client import _create_openai_client

    ledger = tmp_path / "requests.log"
    _set_budget(monkeypatch, ledger, "1/60", max_wait=120)
    with FakeProvider([("text", "x")]) as provider:
        for mode in ("sync", "async"):
            ledger.write_text("")
            cancelled = threading.Event()
            attempt = request_pacer.reserve(cancelled=cancelled.is_set)
            headers = {request_pacer.ATTEMPT_HEADER: attempt.id}
            before = len(provider.chat_requests())
            if mode == "sync":
                client = _create_openai_client(api_key="sk-fake", base_url=provider.base_url)
                client.chat.completions.create(model="m", messages=[{"role": "user", "content": "1"}],
                                               extra_headers=headers)       # consumes the reservation
                threading.Timer(1.0, cancelled.set).start()
                try:
                    client.chat.completions.create(model="m", messages=[{"role": "user", "content": "2"}],
                                                   extra_headers=headers)   # waits for a slot
                    raise AssertionError("cancelled sync attempt reached the transport")
                except Exception as exc:
                    assert isinstance(_cause(exc, request_pacer.RequestCancelledWhileWaiting),
                                      request_pacer.RequestCancelledWhileWaiting), exc
            else:
                aclient = request_pacer.attach(openai.AsyncOpenAI(
                    api_key="sk-fake", base_url=provider.base_url, max_retries=0))

                async def run():
                    await aclient.chat.completions.create(
                        model="m", messages=[{"role": "user", "content": "1"}], extra_headers=headers)
                    threading.Timer(1.0, cancelled.set).start()
                    try:
                        await aclient.chat.completions.create(
                            model="m", messages=[{"role": "user", "content": "2"}], extra_headers=headers)
                        raise AssertionError("cancelled async attempt reached the transport")
                    except Exception as exc:
                        assert isinstance(_cause(exc, request_pacer.RequestCancelledWhileWaiting),
                                          request_pacer.RequestCancelledWhileWaiting), exc
                    await aclient.close()

                asyncio.run(run())
            # Exactly the first request of the attempt was sent; the header never
            # reached the provider.
            sent = provider.chat_requests()[before:]
            assert len(sent) == 1, mode
            assert HEADER not in sent[0]["_headers"], mode
            attempt.close()


def test_gateway_process_calls_are_paced_from_managed_env(tmp_path, monkeypatch):
    """A gateway process loads the managed .env when gateway.run is imported
    (gateway/run.py -> load_hermes_dotenv -> _apply_managed_env); an auxiliary
    model call made in that process (the dispatcher's LLM features, e.g. the
    triage specifier, use call_llm) takes a slot from the run's ledger."""
    for key in ("RHOAI3_REQUEST_BUDGET", "RHOAI3_REQUEST_LEDGER", "RHOAI3_REQUEST_BUDGET_MAX_WAIT"):
        monkeypatch.delenv(key, raising=False)
    managed = tmp_path / "platform" / "hermes"
    managed.mkdir(parents=True)
    ledger = tmp_path / "platform" / "run-control-state" / "requests.log"
    (managed / ".env").write_text(
        f"RHOAI3_REQUEST_BUDGET={H.PROD_BUDGET}\n"
        f"RHOAI3_REQUEST_BUDGET_MAX_WAIT={H.PROD_MAX_WAIT}\n"
        f"RHOAI3_REQUEST_LEDGER={ledger}\n"
    )
    monkeypatch.setenv("HERMES_MANAGED_DIR", str(managed))
    script = textwrap.dedent("""
        import os, sys
        import gateway.run  # noqa: F401  — the gateway entry module; loads .env files
        assert os.environ.get("RHOAI3_REQUEST_LEDGER"), "managed .env not loaded"
        from agent.auxiliary_client import call_llm
        call_llm(task="triage_specifier", provider="custom", model="fake-model",
                 base_url=sys.argv[1], api_key="sk-fake",
                 messages=[{"role": "user", "content": "specify"}])
        print("gateway call ok")
    """)
    with FakeProvider([("text", "spec")]) as provider:
        proc = subprocess.run([sys.executable, "-c", script, provider.base_url],
                              env=dict(os.environ), capture_output=True, text=True, timeout=180)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "gateway call ok" in proc.stdout
        assert len(provider.chat_requests()) == 1
    assert len(_ledger_lines(ledger)) == 1
