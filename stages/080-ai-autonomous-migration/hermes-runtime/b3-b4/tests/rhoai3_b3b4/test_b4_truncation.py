"""B4: a truncated tool call is never executed, and ends as a named failed run.

Real kanban dispatch -> real ``hermes -p implementer --cli chat -q`` worker
with the Stage 050 producer config. The fake provider streams a write_file
call whose arguments JSON is cut off, then finish_reason="length", on every
request. No real model.
"""

from . import _harness as H
from .fake_openai_server import FakeProvider

PARTIAL_ARGS = '{"path": "src/main/java/Pet.java", "content": "public class Pet {\\n  priv'


def test_truncated_tool_call_never_executes(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "src/main/java").mkdir(parents=True)
    with FakeProvider([("truncated_tool", "write_file", PARTIAL_ARGS)]) as provider:
        H.clean_env(monkeypatch, provider)
        H.write_home(H.worker_config(repo))
        from hermes_cli import kanban_db as kb

        kb.init_db()
        conn = kb.connect()
        tid = kb.create_task(conn, title="B4 truncation probe", body="write Pet.java",
                             assignee="implementer", workspace_kind="dir",
                             workspace_path=str(repo))
        exit_code = H.dispatch_and_reap(kb, conn, tid)

        # 1. Nothing was executed: no file, and no tool result in any request.
        assert not (repo / "src/main/java/Pet.java").exists()
        reqs = H.agent_requests(provider)
        assert all(not any(m.get("role") == "tool" for m in r["messages"]) for r in reqs)
        # 2. Bounded recovery at this pin: 1 + 4 retries, output cap boosted
        #    8192 -> 16384 -> 32768 (capped) on the retries.
        assert [r["max_tokens"] for r in reqs] == [8192, 16384, 32768, 32768, 32768]
        assert exit_code == 0

        # 3. Board: a named failed run, not a protocol violation.
        assert kb.detect_crashed_workers(conn) == []
        task = kb.get_task(conn, tid)
        assert task.status == "ready"
        assert task.consecutive_failures == 1
        run = H.runs(conn, tid)[-1]
        assert run["outcome"] == "crashed"
        assert run["error"].startswith(
            "STOP MODEL_OUTPUT_INCOMPLETE: finish_reason=length (tool_call_truncated), output_cap=8192")
        kinds = [k for k, _ in H.events(conn, tid)]
        assert "protocol_violation" not in kinds and "completed" not in kinds
        conn.close()
