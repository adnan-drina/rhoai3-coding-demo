"""B3: HTTP 429 handling of a kanban worker (real worker, fake provider, small real delays).

Pinned behaviour measured here: one retry layer (primary OpenAI client runs
with SDK max_retries=0, agent/agent_runtime_helpers.py), 3 attempts per API
call (agent.api_max_retries default 3), Retry-After honoured (capped at 600 s),
otherwise jittered exponential backoff (2 s base, 60 s cap).
"""

from . import _harness as H
from .fake_openai_server import FakeProvider

THROTTLE = {"error": {"message": "Too many requests", "type": "rate_limit_exceeded"}}
COMPLETE = ("tool", "kanban_complete", {"summary": "B3 probe done"})


def _card(kb, conn, repo, title):
    return kb.create_task(conn, title=title, body="probe", assignee="implementer",
                          workspace_kind="dir", workspace_path=str(repo))


def _gaps(reqs):
    return [round(b["_t"] - a["_t"], 2) for a, b in zip(reqs, reqs[1:])]


def _setup(tmp_path, monkeypatch, provider):
    repo = tmp_path / "repo"
    repo.mkdir()
    H.clean_env(monkeypatch, provider)
    H.write_home(H.worker_config(repo))
    from hermes_cli import kanban_db as kb

    kb.init_db()
    return kb, kb.connect(), repo


def test_429_retry_after_respected(tmp_path, monkeypatch):
    script = [("http", 429, {"Retry-After": "1"}, THROTTLE)] * 2 + [COMPLETE, ("text", "done")]
    with FakeProvider(script) as provider:
        kb, conn, repo = _setup(tmp_path, monkeypatch, provider)
        tid = _card(kb, conn, repo, "B3 retry-after")
        H.dispatch_and_reap(kb, conn, tid)
        reqs = H.agent_requests(provider)
        gaps = _gaps(reqs[:3])
        assert all(1.0 <= g <= 1.6 for g in gaps), gaps          # waited Retry-After, not backoff
        assert len(reqs) == 4                                      # 2 refused + 1 accepted + 1 after tool
        assert kb.get_task(conn, tid).status == "done"
        assert kb.get_task(conn, tid).consecutive_failures == 0
        conn.close()


def test_429_without_retry_after_bounded_backoff(tmp_path, monkeypatch):
    script = [("http", 429, {}, THROTTLE)] * 2 + [COMPLETE, ("text", "done")]
    with FakeProvider(script) as provider:
        kb, conn, repo = _setup(tmp_path, monkeypatch, provider)
        tid = _card(kb, conn, repo, "B3 backoff")
        H.dispatch_and_reap(kb, conn, tid)
        reqs = H.agent_requests(provider)
        g1, g2 = _gaps(reqs[:3])
        # jittered_backoff: 2 s * 2^(n-1) + U[0, 50%]; exactly one HTTP request
        # per attempt (no nested SDK retries).
        assert 2.0 <= g1 <= 3.3, g1
        assert 4.0 <= g2 <= 6.3, g2
        assert len(reqs) == 4
        assert kb.get_task(conn, tid).status == "done"
        conn.close()


def test_persistent_429_named_terminal(tmp_path, monkeypatch):
    script = [("http", 429, {"Retry-After": "1"},
               {"error": {"message": "Too many tokens: quota exceeded", "type": "rate_limit_exceeded"}})]
    with FakeProvider(script) as provider:
        kb, conn, repo = _setup(tmp_path, monkeypatch, provider)
        tid = _card(kb, conn, repo, "B3 persistent")

        H.dispatch_and_reap(kb, conn, tid)
        assert len(H.agent_requests(provider)) == 3                # bounded: 3 attempts, then stop
        assert kb.detect_crashed_workers(conn) == []               # worker closed its own run
        task = kb.get_task(conn, tid)
        assert task.status == "ready" and task.consecutive_failures == 1
        run = H.runs(conn, tid)[-1]
        assert run["outcome"] == "crashed"
        assert run["error"].startswith("STOP MODEL_QUOTA:")
        assert "not a product-repair verdict" in run["error"]
        # The stop text must not trip the respawn guard's quota/auth pattern
        # (that would park the card in ready forever without counting failures).
        assert kb.check_respawn_guard(conn, tid) is None

        # Native breaker: one respawn, then blocked with the quota detail.
        H.dispatch_and_reap(kb, conn, tid)
        assert len(H.agent_requests(provider)) == 6
        assert kb.detect_crashed_workers(conn) == []
        task = kb.get_task(conn, tid)
        assert task.status == "blocked" and task.consecutive_failures == 2
        evs = H.events(conn, tid)
        gave_up = [p for k, p in evs if k == "gave_up"][-1]
        assert gave_up["model_stop"] == "MODEL_QUOTA" and gave_up["http_status"] == 429
        assert gave_up["api_attempts"] == 3 and gave_up["retry_after"] == "1"
        kinds = [k for k, _ in evs]
        assert "protocol_violation" not in kinds and "completed" not in kinds
        conn.close()
