"""V16-7 and V16-9 (tmp/v16-run-20260925/blockers.md): patch 0012.

V16-7, a cycle of distinct reads (v16 card t_ace5e152). The worker cycled 11
distinct read-only calls, ``grep -n "required\\|@NotNull" <generated DTO>``, one
per file, about 40 rounds each, with no edit and no new output: 454 requests,
50.4M tokens. The exact-call streak is consecutive only, and the V16-3 family
needs the same file and pattern. Patch 0012 halts when the same set of L >= 2
read-only calls (exact identities, nothing normalised) is repeated 3 more rounds
with no new output line and no evidence-changing call in between.

V16-9, identical refused calls (v16 card t_7ebb5deb). The same terminal call
was refused before execution 488 times by the K2 pre_tool_call hook
(``{"error": "path / resolves outside allow root"}``), and nothing halted.
Patch 0012 counts a pre-execution refusal as a failed call of that tool
(exact-failure and same-tool-failure families) and halts on the 3rd
consecutive identical refusal, naming the tool and the refusal.

End-to-end: real kanban dispatcher, real ``hermes -p implementer chat -q``
worker, real ``terminal`` tool and a real shell pre_tool_call hook, fake
provider on loopback. Controller tests drive the pinned guardrail directly.
"""

import json
import stat
import sys

from agent.tool_guardrails import ToolCallGuardrailConfig, ToolCallGuardrailController

from . import _harness as H
from .fake_openai_server import FakeProvider

DTO_DIR = "target/generated-sources/openapi/src/gen/java/org/springframework/samples/petclinic/rest/dto"
DTOS = ["OwnerDto", "OwnerFieldsDto", "PetDto", "PetFieldsDto", "PetTypeDto", "PetTypeFieldsDto",
        "SpecialtyDto", "VetDto", "VetFieldsDto", "VisitDto", "VisitFieldsDto"]
GREP = 'grep -n "required\\|@NotNull" {dir}/{name}.java'
MAX_TURNS = 60  # finite, so an unpatched runtime ends at the budget instead of running on
REFUSAL = "path / resolves outside allow root"
REFUSED_CMD = "grep -n quarkus.http src/main/resources/application.properties | sed 's/=.*/=<set>/'"
ALLOWED_CMD = "grep -n quarkus.http src/main/resources/application.properties"
COMPLETE = ("tool", "kanban_complete", {"summary": "done"})


def _dto(name):
    fields = [f"{name.lower()}Id", f"{name.lower()}Name", f"{name.lower()}Pets"]
    lines = [f"public class {name} {{"]
    for f in fields:
        lines += [f"  @NotNull", f"  @Schema(name = \"{f}\", required = true)", f"  private String {f};"]
    return "\n".join(lines) + "\n}\n"


def _repo(tmp_path, names=DTOS):
    repo = tmp_path / "modernized"
    (repo / DTO_DIR).mkdir(parents=True)
    for n in names:
        (repo / DTO_DIR / f"{n}.java").write_text(_dto(n))
    (repo / "src/main/resources").mkdir(parents=True)
    (repo / "src/main/resources/application.properties").write_text("quarkus.http.port=8080\n")
    return repo


def _start(monkeypatch, provider, repo, hook=None):
    H.clean_env(monkeypatch, provider)
    cfg = H.worker_config(repo)
    cfg["agent"] = {**(cfg.get("agent") or {}), "max_turns": MAX_TURNS}
    if hook:
        cfg["hooks"] = {"pre_tool_call": [{"command": str(hook), "matcher": "terminal"}]}
        cfg["hooks_auto_accept"] = True
    H.write_home(cfg)
    from hermes_cli import kanban_db as kb

    kb.init_db()
    conn = kb.connect()
    tid = kb.create_task(conn, title="v16 probe", body="probe", assignee="implementer",
                         workspace_kind="dir", workspace_path=str(repo))
    return kb, conn, tid


def _k2_hook(tmp_path):
    """A shell pre_tool_call hook with K2's refusal: any ``sed`` pipeline is
    refused as a path outside the allow root (the V16-10 misparse)."""
    hook = tmp_path / "k2_hook.py"
    hook.write_text(
        "#!" + sys.executable + "\n"
        "import json, sys\n"
        "d = json.load(sys.stdin)\n"
        "cmd = (d.get('tool_input') or {}).get('command', '')\n"
        "if 'sed ' in cmd:\n"
        f"    print(json.dumps({{'action': 'block', 'message': {REFUSAL!r}}}))\n"
        "else:\n"
        "    print('{}')\n")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    return hook


def _tools_seen(body):
    return sum(1 for m in body["messages"] if m.get("role") == "tool")


# ---- V16-7 -------------------------------------------------------------------

def test_recorded_eleven_file_cycle_halts_within_bound(tmp_path, monkeypatch):
    repo = _repo(tmp_path)

    def responder(body):
        n = _tools_seen(body)
        return ("tool", "terminal", {"command": GREP.format(dir=DTO_DIR, name=DTOS[n % len(DTOS)])})

    with FakeProvider(responder) as provider:
        kb, conn, tid = _start(monkeypatch, provider, repo)
        exit_code = H.dispatch_and_reap(kb, conn, tid)
        reqs = H.agent_requests(provider)
        # One round that shows each DTO, then three rounds that show nothing new.
        assert len(reqs) == 11 * 4, f"worker made {len(reqs)} agent model requests"
        assert exit_code == 0
        assert kb.detect_crashed_workers(conn) == []
        err = H.runs(conn, tid)[-1]["error"]
        assert err.startswith("STOP WORKER_TOOL_LOOP: tool terminal, guardrail "
                              "read_cycle_no_new_content_halt, count 3"), err
        assert "11 read-only calls" in err and "OwnerDto.java" in err, err
        assert "completed" not in [k for k, _ in H.events(conn, tid)]
        conn.close()


def test_legitimate_read_of_eleven_new_files_does_not_halt(tmp_path, monkeypatch):
    repo = _repo(tmp_path)

    def responder(body):
        n = _tools_seen(body)
        if n < len(DTOS):
            return ("tool", "terminal", {"command": GREP.format(dir=DTO_DIR, name=DTOS[n])})
        return COMPLETE if n == len(DTOS) else ("text", "done")

    with FakeProvider(responder) as provider:
        kb, conn, tid = _start(monkeypatch, provider, repo)
        H.dispatch_and_reap(kb, conn, tid)
        assert kb.get_task(conn, tid).status == "done"
        assert [r["outcome"] for r in H.runs(conn, tid)] == ["completed"]
        conn.close()


# ---- V16-9 -------------------------------------------------------------------

def test_refusal_replay_halts_at_three(tmp_path, monkeypatch):
    repo = _repo(tmp_path, names=DTOS[:1])
    hook = _k2_hook(tmp_path)
    with FakeProvider(lambda body: ("tool", "terminal", {"command": REFUSED_CMD})) as provider:
        kb, conn, tid = _start(monkeypatch, provider, repo, hook=hook)
        exit_code = H.dispatch_and_reap(kb, conn, tid)
        reqs = H.agent_requests(provider)
        assert len(reqs) == 3, f"worker made {len(reqs)} agent model requests"
        # The refusal really came from the hook, before execution.
        last_tool = [m for m in reqs[-1]["messages"] if m.get("role") == "tool"][-1]
        assert REFUSAL in last_tool["content"]
        assert exit_code == 0
        err = H.runs(conn, tid)[-1]["error"]
        assert err.startswith("STOP WORKER_TOOL_LOOP: tool terminal, guardrail "
                              "identical_refusal_halt, count 3"), err
        assert REFUSAL in err, err
        conn.close()


def test_refused_call_then_changed_does_not_halt(tmp_path, monkeypatch):
    repo = _repo(tmp_path, names=DTOS[:1])
    hook = _k2_hook(tmp_path)

    def responder(body):
        n = _tools_seen(body)
        if n < 2:
            return ("tool", "terminal", {"command": REFUSED_CMD})
        if n == 2:
            return ("tool", "terminal", {"command": ALLOWED_CMD})
        return COMPLETE if n == 3 else ("text", "done")

    with FakeProvider(responder) as provider:
        kb, conn, tid = _start(monkeypatch, provider, repo, hook=hook)
        H.dispatch_and_reap(kb, conn, tid)
        assert kb.get_task(conn, tid).status == "done"
        assert [r["outcome"] for r in H.runs(conn, tid)] == ["completed"]
        conn.close()


# ---- controller level --------------------------------------------------------

def _controller():
    return ToolCallGuardrailController(ToolCallGuardrailConfig(hard_stop_enabled=True))


def _call(ctl, command, output, tool="terminal"):
    args = {"command": command} if tool == "terminal" else command
    env = json.dumps({"output": output, "exit_code": 0, "error": None})
    d = ctl.after_call(tool, args, env, failed=False)
    ctl.observe_call(tool, args, env)
    return d


def test_cycle_of_two_in_any_order_halts_and_an_edit_resets():
    ctl = _controller()
    a, b = "grep -n x A.java", "grep -n x B.java"
    _call(ctl, a, "1:x in A")
    _call(ctl, b, "1:x in B")
    for cmd in (a, b, b, a, a):  # five redundant reads: not yet three rounds each
        assert _call(ctl, cmd, "1:x in " + cmd[-6]).action == "allow"
    # An edit starts a new phase: the history and the seen output are dropped.
    assert ctl.after_call("write_file", {"path": "A.java", "content": "y"}, '{"ok": true}', failed=False).action == "allow"
    for cmd in (a, b, a, b, a):
        assert _call(ctl, cmd, "1:x in " + cmd[-6]).action == "allow"
    d = _call(ctl, b, "1:x in B")  # rounds 2,3 redundant after the edit's first round
    assert d.action == "allow"
    d = _call(ctl, a, "1:x in A")
    d = _call(ctl, b, "1:x in B")
    assert d.action == "halt" and d.code == "read_cycle_no_new_content_halt" and "2 read-only calls" in d.family


def test_reading_many_new_files_never_halts():
    ctl = _controller()
    for i in range(200):
        assert _call(ctl, f"grep -n required Dto{i}.java", f"{i}:required field{i}").action == "allow"
    assert ctl.halt_decision is None


def test_refusals_feed_the_same_tool_failure_family():
    ctl = _controller()
    decisions = []
    for i in range(8):  # eight different refused calls, two each is never 3 identical
        cmd = {"command": f"cat /etc/f{i // 2} | sed 's/a/b/'"}
        decisions.append(ctl.after_refusal("terminal", cmd, REFUSAL))
    assert decisions[-1].action == "halt" and decisions[-1].code == "same_tool_failure_halt"
    assert all(d.action != "halt" for d in decisions[:-1])


def test_executed_calls_keep_their_thresholds():
    ctl = _controller()
    args = {"command": "find src -name X.java"}
    for i in range(4):
        _call(ctl, args["command"], "")
    assert ctl.halt_decision is None  # identical executed calls still halt at 5, not 3
    _call(ctl, args["command"], "")
    assert ctl.halt_decision.code == "identical_call_streak_halt"
