"""R2: the declared per-run request allowance is enforced, not only checked (patch 0007).

Every model HTTP request of the run takes one slot from a shared
sliding-window ledger (RHOAI3_REQUEST_BUDGET / RHOAI3_REQUEST_LEDGER /
RHOAI3_REQUEST_BUDGET_MAX_WAIT). Fake provider only; the wait test uses a
fake clock. Requests are driven through the real pinned client factories
(``auxiliary_client._create_openai_client``) and the real kanban worker.
"""

import os
import subprocess
import sys
import textwrap
import time

from . import _harness as H
from .fake_openai_server import FakeProvider

COMPLETE = ("tool", "kanban_complete", {"summary": "R2 probe done"})
PARTIAL_ARGS = '{"path": "src/main/java/Pet.java", "content": "public class Pet {\\n  priv'


def _ledger_lines(path):
    try:
        with open(path) as fh:
            return [l.split() for l in fh if l.strip()]
    except FileNotFoundError:
        return []


def _set_budget(monkeypatch, ledger, budget, max_wait=None):
    monkeypatch.setenv("RHOAI3_REQUEST_BUDGET", budget)
    monkeypatch.setenv("RHOAI3_REQUEST_LEDGER", str(ledger))
    if max_wait is not None:
        monkeypatch.setenv("RHOAI3_REQUEST_BUDGET_MAX_WAIT", str(max_wait))


# A separate Hermes process issuing N model calls through the real aux client factory.
_CALLER = textwrap.dedent("""
    import sys
    from agent.auxiliary_client import _create_openai_client
    base_url, n = sys.argv[1], int(sys.argv[2])
    client = _create_openai_client(api_key="sk-fake", base_url=base_url)
    sent = refused = 0
    for _ in range(n):
        try:
            client.chat.completions.create(model="m", messages=[{"role": "user", "content": "hi"}])
            sent += 1
        except Exception as exc:
            refused += 1
    print(f"sent={sent} refused={refused}")
""")


def _caller(base_url, n):
    return subprocess.Popen([sys.executable, "-c", _CALLER, base_url, str(n)],
                            env=dict(os.environ), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _kanban(tmp_path, monkeypatch, provider):
    repo = tmp_path / "repo"
    (repo / "src/main/java").mkdir(parents=True)
    H.clean_env(monkeypatch, provider)
    H.write_home(H.worker_config(repo))
    from hermes_cli import kanban_db as kb

    kb.init_db()
    conn = kb.connect()
    tid = kb.create_task(conn, title="R2 probe", body="probe", assignee="implementer",
                         workspace_kind="dir", workspace_path=str(repo))
    return kb, conn, tid


def test_budget_counts_main_retries_and_auxiliary(tmp_path, monkeypatch):
    ledger = tmp_path / "control" / "requests.log"
    _set_budget(monkeypatch, ledger, "100/3600")
    # 429 (retried), truncated tool call (retried with a boosted cap), then complete.
    script = [("http", 429, {"Retry-After": "1"}, {"error": {"message": "slow down", "type": "x"}}),
              ("truncated_tool", "write_file", PARTIAL_ARGS), COMPLETE, ("text", "done")]
    with FakeProvider(script) as provider:
        kb, conn, tid = _kanban(tmp_path, monkeypatch, provider)
        H.dispatch_and_reap(kb, conn, tid)
        assert kb.get_task(conn, tid).status == "done"
        main_requests = len(provider.chat_requests())
        assert main_requests == 4
        assert [r.get("max_tokens") for r in provider.chat_requests()][:3] == [8192, 8192, 16384]
        # An auxiliary caller in another process shares the ledger.
        out, _ = _caller(provider.base_url, 2).communicate(timeout=120)
        assert "sent=2" in out
        lines = _ledger_lines(ledger)
        # One slot per HTTP request that reached the provider: the 429 attempt,
        # the truncated attempt, its boosted retry, the post-tool call, 2 aux calls.
        assert len(lines) == len(provider.chat_requests()) == main_requests + 2
        assert len({pid for _, pid, _ in lines}) == 2
        conn.close()


def test_budget_shared_across_two_processes(tmp_path, monkeypatch):
    ledger = tmp_path / "requests.log"
    _set_budget(monkeypatch, ledger, "5/3600", max_wait=0)
    with FakeProvider([("text", "x")]) as provider:
        monkeypatch.setenv("MAAS_API_KEY", "sk-fake")
        a, b = _caller(provider.base_url, 4), _caller(provider.base_url, 4)
        outs = [p.communicate(timeout=120)[0] for p in (a, b)]
        sent = sum(int(o.split("sent=")[1].split()[0]) for o in outs)
        assert sent == 5, outs
        assert len(provider.chat_requests()) == 5
        lines = _ledger_lines(ledger)
        assert len(lines) == 5
        assert len({pid for _, pid, _ in lines}) == 2


def test_budget_persists_across_restart(tmp_path, monkeypatch):
    ledger = tmp_path / "requests.log"
    _set_budget(monkeypatch, ledger, "3/3600", max_wait=0)
    with FakeProvider([("text", "x")]) as provider:
        first = _caller(provider.base_url, 3).communicate(timeout=120)[0]
        assert "sent=3 refused=0" in first
        # A new process (a restarted worker) sees the slots already spent.
        second = _caller(provider.base_url, 1).communicate(timeout=120)[0]
        assert "sent=0 refused=1" in second
        assert len(provider.chat_requests()) == 3


def test_budget_waits_for_oldest_slot(tmp_path, monkeypatch):
    from agent import request_pacer
    from agent.auxiliary_client import _create_openai_client

    ledger = tmp_path / "requests.log"
    _set_budget(monkeypatch, ledger, "2/100", max_wait=30)
    clock = {"t": 1_000_000.0}
    slept = []

    def fake_sleep(seconds):
        slept.append(seconds)
        clock["t"] += seconds

    monkeypatch.setattr(request_pacer, "_now", lambda: clock["t"])
    monkeypatch.setattr(request_pacer, "_sleep", fake_sleep)
    # Two slots already spent 95 s and 50 s ago: the oldest frees in 5 s.
    ledger.write_text(f"{clock['t'] - 95:.6f} 1 seed\n{clock['t'] - 50:.6f} 1 seed\n")
    with FakeProvider([("text", "x")]) as provider:
        client = _create_openai_client(api_key="sk-fake", base_url=provider.base_url)
        client.chat.completions.create(model="m", messages=[{"role": "user", "content": "hi"}])
        assert len(provider.chat_requests()) == 1
    assert 4.9 <= sum(slept) <= 6.1, slept
    lines = _ledger_lines(ledger)
    assert len(lines) == 3 and float(lines[-1][0]) >= 1_000_000.0 + 5


def test_budget_exhaustion_is_named_and_sends_nothing(tmp_path, monkeypatch):
    """The allowance stop is named and sends nothing. Since patch 0009 it is a
    structured local-budget deferral ending the run neutrally through the native
    rate-limit path (see test_v15_quota_recovery.py), not a failed run."""
    ledger = tmp_path / "control" / "requests.log"
    ledger.parent.mkdir(parents=True)
    now = time.time()
    ledger.write_text(f"{now - 10:.6f} 1 seed\n{now - 5:.6f} 1 seed\n")
    _set_budget(monkeypatch, ledger, "2/3600", max_wait=5)
    with FakeProvider([COMPLETE, ("text", "done")]) as provider:
        kb, conn, tid = _kanban(tmp_path, monkeypatch, provider)
        H.dispatch_and_reap(kb, conn, tid)
        assert provider.chat_requests() == []              # nothing was sent
        assert kb.detect_crashed_workers(conn) == []
        events = H.events(conn, tid)
        reasons = [p.get("reason") or "" for k, p in events if k == "local_budget_deferral"]
        assert reasons and reasons[-1].startswith(
            "STOP MODEL_REQUEST_BUDGET: 2 requests in 3600s already spent by this run; next slot at ")
        # Held by the deferral until capacity returns -- never by the
        # quota/auth blocker pattern (which would park it without a wake time).
        assert kb.check_respawn_guard(conn, tid) == "local_budget_wait"
        kinds = [k for k, _ in events]
        assert "protocol_violation" not in kinds and "completed" not in kinds
        assert len(_ledger_lines(ledger)) == 2             # no slot was taken
        conn.close()


def test_budget_unset_is_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv("RHOAI3_REQUEST_BUDGET", raising=False)
    monkeypatch.delenv("RHOAI3_REQUEST_LEDGER", raising=False)
    from agent import request_pacer

    assert request_pacer.config() is None
    with FakeProvider([COMPLETE, ("text", "done")]) as provider:
        kb, conn, tid = _kanban(tmp_path, monkeypatch, provider)
        H.dispatch_and_reap(kb, conn, tid)
        assert kb.get_task(conn, tid).status == "done"
        assert len(provider.chat_requests()) == 2
        conn.close()
    assert not list(tmp_path.rglob("requests.log"))


def test_main_path_waits_for_slot_and_completes(tmp_path, monkeypatch):
    """Real clock: a 2-per-4s budget forces the worker's main loop to wait; the
    wait happens before the streaming call (no stale abort, no failed run)."""
    ledger = tmp_path / "requests.log"
    _set_budget(monkeypatch, ledger, "2/4", max_wait=30)
    echo = ("tool", "terminal", {"command": "echo step"})
    with FakeProvider([echo, echo, COMPLETE, ("text", "done")]) as provider:
        kb, conn, tid = _kanban(tmp_path, monkeypatch, provider)
        H.dispatch_and_reap(kb, conn, tid)
        assert kb.get_task(conn, tid).status == "done"
        assert kb.get_task(conn, tid).consecutive_failures == 0
        reqs = provider.chat_requests()
        assert len(reqs) == 4
        ts = [float(l[0]) for l in _ledger_lines(ledger)]
        assert len(ts) == 4
        # No 4-second window ever held more than 2 requests.
        assert all(ts[i + 2] - ts[i] >= 4.0 for i in range(len(ts) - 2)), ts
        conn.close()


def test_budget_from_managed_env_reaches_worker(tmp_path, monkeypatch):
    """dest-init writes the pacer settings into the MANAGED .env
    ($HERMES_MANAGED_DIR/.env), not into the dispatcher's environment. The
    dispatched worker loads it at startup (hermes_cli/main.py ->
    env_loader.load_hermes_dotenv -> _apply_managed_env) and paces from it;
    the ledger's parent directory does not exist beforehand."""
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
    echo = ("tool", "terminal", {"command": "echo step"})
    with FakeProvider([echo, COMPLETE, ("text", "done")]) as provider:
        kb, conn, tid = _kanban(tmp_path, monkeypatch, provider)
        assert "RHOAI3_REQUEST_BUDGET" not in os.environ   # dispatcher never had it
        H.dispatch_and_reap(kb, conn, tid)
        assert kb.get_task(conn, tid).status == "done"
        lines = _ledger_lines(ledger)
        assert len(lines) == len(provider.chat_requests()) == 3
        conn.close()


def test_budget_total_wait_bound_under_contention(tmp_path, monkeypatch):
    """The production allowance and maximum wait (from the profile table). The
    window is full, and a competing process wins every expiring slot just
    before the waiting caller looks again. The caller must stop with
    RequestBudgetExhausted within the TOTAL maximum wait and send nothing
    (review V13-PACER-FINAL-REVIEW §2; before the fix it waited past 900 s)."""
    from agent import request_pacer
    from agent.auxiliary_client import _create_openai_client

    limit = int(H.PROD_QUOTA["max_requests_per_window"])
    window = float(H.PROD_QUOTA["window_seconds"])
    max_wait = float(H.PROD_MAX_WAIT)
    ledger = tmp_path / "requests.log"
    _set_budget(monkeypatch, ledger, H.PROD_BUDGET, max_wait=H.PROD_MAX_WAIT)
    start = 1_000_000.0
    spacing = window / limit
    clock = {"t": start}
    competitor_slots = []
    cfg = request_pacer.config()
    # A full window: one slot every `spacing` seconds, the oldest expiring first.
    ledger.write_text("".join(f"{start - (limit - 1 - i) * spacing:.6f} 1 seed\n" for i in range(limit)))

    def fake_sleep(seconds):
        clock["t"] += seconds
        # The competitor takes each slot the moment it expires.
        while True:
            granted, _ = request_pacer._try_take(cfg, "competitor", True)
            if not granted:
                break
            competitor_slots.append(clock["t"])
        assert clock["t"] - start <= max_wait + 1e-6, "waited past the total bound"

    monkeypatch.setattr(request_pacer, "_now", lambda: clock["t"])
    monkeypatch.setattr(request_pacer, "_sleep", fake_sleep)
    with FakeProvider([("text", "x")]) as provider:
        client = _create_openai_client(api_key="sk-fake", base_url=provider.base_url)
        try:
            client.chat.completions.create(model="m", messages=[{"role": "user", "content": "hi"}])
            raised = None
        except Exception as exc:  # the SDK wraps hook errors in APIConnectionError
            raised = exc if isinstance(exc, request_pacer.RequestBudgetExhausted) else exc.__cause__
        assert isinstance(raised, request_pacer.RequestBudgetExhausted), raised
        assert provider.chat_requests() == []
    assert clock["t"] - start <= max_wait
    assert raised.waited <= max_wait
    assert len(competitor_slots) >= 1                       # contention really happened
    assert str(raised).startswith(f"STOP MODEL_REQUEST_BUDGET: {limit} requests in {int(window)}s")


def test_budget_first_slot_beyond_wait_stops_immediately(tmp_path, monkeypatch):
    """Preserved: when the first predicted slot is already beyond the total
    allowance, the caller stops at once without sleeping or sending."""
    from agent import request_pacer
    from agent.auxiliary_client import _create_openai_client

    ledger = tmp_path / "requests.log"
    _set_budget(monkeypatch, ledger, "1/3600", max_wait=5)
    ledger.write_text(f"{time.time():.6f} 1 seed\n")
    slept = []
    monkeypatch.setattr(request_pacer, "_sleep", lambda s: slept.append(s))
    with FakeProvider([("text", "x")]) as provider:
        client = _create_openai_client(api_key="sk-fake", base_url=provider.base_url)
        try:
            client.chat.completions.create(model="m", messages=[{"role": "user", "content": "hi"}])
            raise AssertionError("expected RequestBudgetExhausted")
        except Exception as exc:
            cause = exc if isinstance(exc, request_pacer.RequestBudgetExhausted) else exc.__cause__
            assert isinstance(cause, request_pacer.RequestBudgetExhausted), exc
        assert provider.chat_requests() == []
    assert slept == []
