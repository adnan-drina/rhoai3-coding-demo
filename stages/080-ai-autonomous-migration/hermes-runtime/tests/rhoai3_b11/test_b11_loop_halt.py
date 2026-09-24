"""RHOAI3 B11 qualification: successful identical tool-call loops must halt.

In-process tests against the real pinned AIAgent runtime
(run_conversation -> tool executor -> guardrail controller -> turn finalizer).
The model is a scripted fake (``agent.client.chat.completions.create`` side
effect, the same pattern as tests/run_agent/test_tool_call_guardrail_runtime.py);
tool dispatch is patched to return the pinned ``terminal`` result envelope
({"output", "exit_code", "error", ...}). No network, no real model.

Copy this directory to ``tests/rhoai3_b11/`` in the Hermes tree and run
``python -m pytest tests/rhoai3_b11``.
"""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from run_agent import AIAgent

# Mirrors the deployed worker config: hard stops on, product-default thresholds
# (hard_stop_after.idempotent_no_progress = 5).
HARD_STOP = {"tool_loop_guardrails": {"hard_stop_enabled": True}}
THRESHOLD = 5


def _tool_defs(*names):
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": f"{n} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for n in names
    ]


def _make_agent(*tool_names, max_iterations=20, config=None):
    config = HARD_STOP if config is None else config
    with (
        patch("run_agent.get_tool_definitions", return_value=_tool_defs(*tool_names)),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("hermes_cli.config.load_config", return_value=config),
        patch("hermes_cli.config.load_config_readonly", return_value=config),
        patch("run_agent.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://fake.invalid/v1",
            max_iterations=max_iterations,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
    agent.client = MagicMock()
    agent._cached_system_prompt = "You are helpful."
    agent._use_prompt_caching = False
    agent.compression_enabled = False
    agent.save_trajectories = False
    return agent


def _tool_call(name, args, call_id=None):
    return SimpleNamespace(
        id=call_id or f"call_{uuid.uuid4().hex[:8]}",
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


def _llm_tool_turn(name, args):
    msg = SimpleNamespace(content="", tool_calls=[_tool_call(name, args)])
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason="tool_calls")],
        model="fake/model",
        usage=None,
    )


def _llm_text_turn(text):
    msg = SimpleNamespace(content=text, tool_calls=None)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason="stop")],
        model="fake/model",
        usage=None,
    )


def _terminal_envelope(output, exit_code=0, **extra):
    """The foreground terminal result envelope at v2026.8.19 (tools/terminal_tool.py)."""
    data = {"output": output, "exit_code": exit_code, "error": None}
    data.update(extra)
    return json.dumps(data, ensure_ascii=False)


def _run(agent, llm_turns, tool_results):
    """Run one conversation turn with scripted LLM turns and tool results.

    ``llm_turns`` is a list of fake responses; after it is exhausted the fake
    model keeps repeating the last one (a model that never stops looping).
    ``tool_results`` maps a call index (0-based) to its raw result, or is a
    callable ``(index, name, args) -> str``.
    """
    llm_calls = []

    def fake_create(*_a, **_k):
        llm_calls.append(1)
        turn = llm_turns[min(len(llm_calls) - 1, len(llm_turns) - 1)]
        msg = turn.choices[0].message
        if msg.tool_calls:
            # A real provider issues a fresh tool_call id on every response.
            calls = [_tool_call(tc.function.name, json.loads(tc.function.arguments)) for tc in msg.tool_calls]
            msg = SimpleNamespace(content=msg.content, tool_calls=calls)
            turn = SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="tool_calls")],
                                   model=turn.model, usage=None)
        return turn

    agent.client.chat.completions.create.side_effect = fake_create
    executed = []

    def fake_dispatch(name, args, task_id, **kwargs):
        executed.append((name, args))
        idx = len(executed) - 1
        if callable(tool_results):
            return tool_results(idx, name, args)
        return tool_results[min(idx, len(tool_results) - 1)]

    with (
        patch("run_agent.handle_function_call", side_effect=fake_dispatch),
        patch.object(agent, "_persist_session"),
        patch.object(agent, "_save_trajectory"),
        patch.object(agent, "_cleanup_task_resources"),
    ):
        result = agent.run_conversation("work the task")
    return result, llm_calls, executed


def _tool_messages(result):
    return [m for m in result["messages"] if m.get("role") == "tool"]


def _assert_streak_halt(result, llm_calls, executed, *, tool="terminal", expected_tools=THRESHOLD):
    assert len(executed) == expected_tools, (
        f"expected the worker to stop after {expected_tools} tool executions, "
        f"got {len(executed)}"
    )
    # One model request per executed tool call; NO request after the halting call.
    assert len(llm_calls) == expected_tools, (
        f"model was called {len(llm_calls)} times for {expected_tools} tool calls"
    )
    assert result["turn_exit_reason"] == "guardrail_halt"
    assert result["guardrail"]["code"] == "identical_call_streak_halt"
    assert result["guardrail"]["tool_name"] == tool
    assert result["guardrail"]["count"] == THRESHOLD
    assert "Tool loop hard stop" in _tool_messages(result)[-1]["content"]


def test_successful_empty_terminal_halts_at_five():
    agent = _make_agent("terminal")
    turn = _llm_tool_turn("terminal", {"command": "find src/main/java -name PetDto.java"})
    result, llm_calls, executed = _run(agent, [turn], [_terminal_envelope("")])
    _assert_streak_halt(result, llm_calls, executed)


def test_successful_large_terminal_halts_before_next_llm_call():
    agent = _make_agent("terminal")
    body = "public class Owner {\n" + ("    // unchanged line\n" * 60) + "}\n"
    turn = _llm_tool_turn("terminal", {"command": "cat src/main/java/Owner.java"})
    result, llm_calls, executed = _run(agent, [turn], [_terminal_envelope(body)])
    _assert_streak_halt(result, llm_calls, executed)
    contents = [m["content"] for m in _tool_messages(result)]
    # The full payload entered context once; repeats are reference stubs.
    assert body.strip() in json.loads(contents[0])["output"]
    assert all("byte-identical" in c for c in contents[1:])


def test_terminal_transport_timing_does_not_hide_loop():
    agent = _make_agent("terminal")
    body = "BUILD OUTPUT\n" * 80

    def result_for(idx, name, args):
        # Same application output every time; only per-call transport metadata
        # (spill path, its note, timing added by a transform hook) changes.
        spill = f"/home/user/.hermes/cache/terminal-output/out-17000000{idx:02d}-4242-{idx:x}.log"
        return _terminal_envelope(
            body,
            output_total_chars=len(body) * 3,
            full_output_path=spill,
            truncation_note=f"Output exceeded the capture window. Full output saved to {spill}",
            duration_ms=1000 + 37 * idx,
        )

    turn = _llm_tool_turn("terminal", {"command": "mvn -q test"})
    result, llm_calls, executed = _run(agent, [turn], result_for)
    _assert_streak_halt(result, llm_calls, executed)
    # Raw results differ (paths), so none of them may be replaced by a stub.
    assert not any("byte-identical" in m["content"] for m in _tool_messages(result))

    # Control: when the APPLICATION output changes, it is progress — no halt.
    agent = _make_agent("terminal")
    turns = [_llm_tool_turn("terminal", {"command": "mvn -q test"})] * 8 + [_llm_text_turn("done")]
    changing = lambda idx, name, args: _terminal_envelope(body + f"run {idx}\n", duration_ms=5)
    result, llm_calls, executed = _run(agent, turns, changing)
    assert result["turn_exit_reason"].startswith("text_response")
    assert "guardrail" not in result
    assert len(executed) == 8


def test_polling_with_deadline_is_bounded():
    # (a) No blanket terminal exemption: polling through `terminal` with an
    # unchanged answer is a loop like any other.
    agent = _make_agent("terminal")
    turn = _llm_tool_turn("terminal", {"command": "curl -s localhost:8080/q/health"})
    result, llm_calls, executed = _run(agent, [turn], [_terminal_envelope('{"status":"DOWN"}')])
    _assert_streak_halt(result, llm_calls, executed)

    # (b) The explicit poller (`process`, STALL_GUARD_REPEATABLE_TOOLS) keeps its
    # exemption from the identical-call halt, and is bounded by the turn's
    # explicit iteration budget instead of running forever.
    budget = 8
    agent = _make_agent("process", max_iterations=budget)
    poll = _llm_tool_turn("process", {"action": "poll", "session_id": "proc_1"})
    result, llm_calls, executed = _run(
        agent, [poll], [json.dumps({"status": "running", "output": ""})]
    )
    assert result.get("guardrail") is None
    assert result["turn_exit_reason"].startswith("max_iterations_reached")
    assert len(executed) == budget


def test_edit_then_reverify_is_progress():
    agent = _make_agent("terminal", "patch")
    verify = _llm_tool_turn("terminal", {"command": "mvn -q -Dtest=OwnerIT test"})
    edit = _llm_tool_turn("patch", {"path": "src/main/java/Owner.java", "old": "a", "new": "b"})
    # 4 identical failing-behaviour verifications (exit 0, same report), an
    # edit, then the re-verification returns a CHANGED report: progress. The
    # streak restarts, so it takes 5 more identical calls to halt.
    turns = [verify] * 4 + [edit] + [verify]
    before, after = "Tests run: 3, Failures: 1\n", "Tests run: 3, Failures: 0\n"

    def result_for(idx, name, args):
        if name == "patch":
            return json.dumps({"success": True, "diff": "-a\n+b\n"})
        return _terminal_envelope(before if idx < 4 else after)

    result, llm_calls, executed = _run(agent, turns, result_for)
    names = [n for n, _ in executed]
    assert names == ["terminal"] * 4 + ["patch"] + ["terminal"] * THRESHOLD
    assert len(llm_calls) == len(executed)
    assert result["turn_exit_reason"] == "guardrail_halt"
    assert result["guardrail"]["code"] == "identical_call_streak_halt"
    # No hard stop was appended before the post-edit streak reached 5.
    tool_msgs = _tool_messages(result)
    assert not any("Tool loop hard stop" in m["content"] for m in tool_msgs[:-1])


def test_compression_keeps_referenced_result_retrievable():
    """A reference stub must never point at a payload compression removed.

    Uses the pinned ContextCompressor's real deterministic prune pass to
    summarize the first (full) result, then repeats the identical read.
    """
    agent = _make_agent("terminal")
    args = {"command": "cat target/openapi/PetDto.java"}
    payload = "public record PetDto(Integer id, String name) {}\n" + ("// generated\n" * 60)
    raw = _terminal_envelope(payload)
    messages = [{"role": "user", "content": "work the task"}]

    def execute(call_id):
        tc = _tool_call("terminal", args, call_id)
        messages.append({
            "role": "assistant", "content": "",
            "tool_calls": [{"id": call_id, "type": "function",
                            "function": {"name": "terminal", "arguments": json.dumps(args)}}],
        })
        msg = SimpleNamespace(content="", tool_calls=[tc])
        with patch("run_agent.handle_function_call", return_value=raw):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")
        return messages[-1]["content"]

    def retrievable(content):
        # Either the fresh payload itself, a stub naming a tool_call_id whose
        # message still carries the payload, or a persisted spill path.
        if raw in content:
            return True
        for m in messages:
            if m.get("role") == "tool" and m.get("tool_call_id") in content and raw in (m.get("content") or ""):
                return True
        return "persisted to:" in content

    first = execute("call-1")
    assert payload.strip() in json.loads(first)["output"]

    # Compression boundary: the pinned compressor prunes call-1 (non-tail).
    messages.append({"role": "user", "content": "continue"})
    pruned, count = agent.context_compressor._prune_old_tool_results(messages, protect_tail_count=1)
    messages[:] = pruned
    assert count >= 1
    assert not any(raw in (m.get("content") or "") for m in messages if m.get("role") == "tool"), (
        "precondition: compression must have removed the original payload"
    )

    second = execute("call-2")
    assert retrievable(second), f"repeat result is not retrievable after compression: {second[:300]}"

    # Once rehydrated, later repeats may stub again — pointing at a retained payload.
    third = execute("call-3")
    assert retrievable(third)

    # Rehydration is not progress: the identical-call streak still halts at 5.
    execute("call-4")
    execute("call-5")
    halt = agent._tool_guardrail_halt_decision
    assert halt is not None and halt.code == "identical_call_streak_halt" and halt.count == THRESHOLD
