"""V16-3 part 2 (tmp/v16-run-20260925/architect-decision-v16-2-3-4.md, "V16-3"):
a bounded repetition family for read-only log context searches (patch 0011).

Incident (v16 card t_d3f89ded): after VERIFICATION_PENDING the worker made about
250 ``cat verification/build/package.log | grep -B <N> "Building spring-petclinic"``
calls, N from 10 to 2e10, over 35 minutes. Each call differed only in N, so the
exact-call guard (B11) never fired. The build log's match sits on line 4, so
every N >= 3 printed the same four lines.

A family is: same tool, same working directory, same command once ONLY grep's
context-size options (-A/-B/-C, -NUM and their long forms) are removed. A read
that shows an output line the family has not shown before is progress; five
reads in a row that show nothing new halt the worker, naming the family.
No other number is normalised, and there is no blanket call limit.

The first test is end to end: real kanban dispatcher, real
``hermes -p implementer chat -q`` worker, real ``terminal`` tool running the
real grep on a real log, scripted fake provider on loopback. The others drive
the pinned guardrail controller directly with the terminal result envelope.
"""

import json

from agent.tool_guardrails import ToolCallGuardrailConfig, ToolCallGuardrailController

from . import _harness as H
from .fake_openai_server import FakeProvider

PATTERN = "Building spring-petclinic"
LOG = "verification/build/package.log"
# The recorded expansion, 10 -> 2e9 (the dest went on to 2e10 with GNU grep;
# the macOS BSD grep used here is killed allocating 2e10 context lines).
SEQUENCE = [10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200, 300, 500, 1000, 2000,
            5000, 10000, 100000, 1000000, 10000000, 100000000, 1000000000, 2000000000]
BOUND = 5  # tool_loop_guardrails hard_stop_after.idempotent_no_progress (product default)


def _package_log(lines=146, match_at=4):
    out = []
    for i in range(1, lines + 1):
        if i == match_at:
            out.append("[INFO] Building spring-petclinic-rest 2.6.2")
        elif i == 120:
            out.append("[ERROR] Failed to execute goal io.quarkus:quarkus-maven-plugin:build")
        else:
            out.append(f"[INFO] line {i} of the package build")
    return "\n".join(out) + "\n"


def _grep(n):
    return {"command": f'cat {LOG} | grep -B {n} "{PATTERN}"'}


def test_recorded_expanding_grep_sequence_halts_within_bound(tmp_path, monkeypatch):
    def responder(body):
        n_tools = sum(1 for m in body["messages"] if m.get("role") == "tool")
        return ("tool", "terminal", _grep(SEQUENCE[min(n_tools, len(SEQUENCE) - 1)]))

    repo = tmp_path / "repo"
    (repo / "src/main/java").mkdir(parents=True)
    (repo / LOG).parent.mkdir(parents=True)
    (repo / LOG).write_text(_package_log())
    with FakeProvider(responder) as provider:
        H.clean_env(monkeypatch, provider)
        H.write_home(H.worker_config(repo))
        from hermes_cli import kanban_db as kb

        kb.init_db()
        conn = kb.connect()
        tid = kb.create_task(conn, title="V16-3 read loop", body="diagnose the package log",
                             assignee="implementer", workspace_kind="dir", workspace_path=str(repo))
        exit_code = H.dispatch_and_reap(kb, conn, tid)
        reqs = H.agent_requests(provider)
        # One read that shows the log, then five that show nothing new: halted
        # before a seventh model request.
        assert len(reqs) == 1 + BOUND, f"worker made {len(reqs)} agent model requests"
        assert exit_code == 0
        assert kb.detect_crashed_workers(conn) == []
        last = H.runs(conn, tid)[-1]
        assert last["outcome"] == "crashed"
        err = last["error"]
        assert err.startswith("STOP WORKER_TOOL_LOOP: tool terminal, guardrail "
                              "read_family_no_new_content_halt, count 5"), err
        assert PATTERN in err and LOG in err, err
        assert "retained candidate" in err, err
        assert "completed" not in [k for k, _ in H.events(conn, tid)]
        # The log itself is untouched.
        assert (repo / LOG).read_text() == _package_log()
        conn.close()


# ---- controller level: the terminal result envelope, no model ---------------

def _controller():
    return ToolCallGuardrailController(ToolCallGuardrailConfig(hard_stop_enabled=True))


def _envelope(output, exit_code=0):
    return json.dumps({"output": output, "exit_code": exit_code, "error": None})


def _lines(text, n):
    return "\n".join(text.splitlines()[:n])


def _call(ctl, args, output, exit_code=0):
    """One executed terminal call, observed exactly as run_agent does."""
    decision = ctl.after_call("terminal", args, _envelope(output, exit_code), failed=exit_code != 0)
    ctl.observe_call("terminal", args, _envelope(output, exit_code))
    return decision


def test_family_ignores_only_context_options_and_halts_on_the_fifth_redundant_read():
    ctl = _controller()
    shown = _lines(_package_log(), 4)
    forms = ['grep -B 10 "{p}" {f}', 'grep -B20 "{p}" {f}', 'grep --before-context=30 "{p}" {f}',
             'grep --before-context 40 "{p}" {f}', 'grep -C 50 "{p}" {f}', 'grep -60 "{p}" {f}']
    decisions = [_call(ctl, {"command": f.format(p=PATTERN, f=LOG)}, shown) for f in forms]
    assert [d.action for d in decisions[:5]] == ["allow"] * 5
    assert decisions[5].action == "halt" and decisions[5].code == "read_family_no_new_content_halt"
    assert decisions[5].count == 5
    assert ctl.halt_decision is decisions[5]


def test_reads_that_show_new_content_are_not_collapsed():
    ctl = _controller()
    log = "\n".join(f"line {i}" for i in range(1, 2001))
    # grep -A N after an early match: every widening shows lines not shown before.
    for n in (10, 20, 40, 80, 160, 320, 640, 1280):
        d = _call(ctl, {"command": f'grep -A {n} "line 1$" app.log'}, _lines(log, n + 1))
        assert d.action == "allow"
    assert ctl.halt_decision is None


def test_different_semantic_numbers_are_different_families():
    ctl = _controller()
    same = "[INFO] Building spring-petclinic-rest 2.6.2"
    # -m (max count) is not a context option: each value is its own call family.
    for m in range(1, 9):
        assert _call(ctl, {"command": f'grep -m {m} "{PATTERN}" {LOG}'}, same).action == "allow"
    # Ports / identifiers inside the pattern are different searches (six, under
    # the separate same-tool failure bound of 8: no match exits 1).
    for port in range(8080, 8086):
        assert _call(ctl, {"command": f'grep -B 5 "port {port}" {LOG}'}, "", exit_code=1).action != "halt"
    # A different file or working directory is a different family.
    for i in range(8):
        assert _call(ctl, {"command": f'grep -B {10 + i} "{PATTERN}" build-{i}.log'}, same).action == "allow"
    for i in range(8):
        args = {"command": f'grep -B {10 + i} "{PATTERN}" {LOG}', "workdir": f"/w/{i}"}
        assert _call(ctl, args, same).action == "allow"
    assert ctl.halt_decision is None


def test_an_evidence_change_starts_a_new_phase():
    ctl = _controller()
    shown = _lines(_package_log(), 4)
    for n in (10, 20, 30, 40, 50):  # first shows the log, four redundant
        assert _call(ctl, {"command": f'grep -B {n} "{PATTERN}" {LOG}'}, shown).action == "allow"
    # A new verification run (not a read-only pipeline) may rewrite the log.
    assert _call(ctl, {"command": "bash run-verify.sh --mode acceptance"}, "PACKAGE FAIL").action == "allow"
    for n in (60, 70, 80, 90, 100):
        assert _call(ctl, {"command": f'grep -B {n} "{PATTERN}" {LOG}'}, shown).action == "allow"
    assert ctl.halt_decision is None


def test_interleaved_reads_do_not_reset_the_family():
    ctl = _controller()
    shown = _lines(_package_log(), 4)
    for n in (10, 20, 30):
        _call(ctl, {"command": f'grep -B {n} "{PATTERN}" {LOG}'}, shown)
    _call(ctl, {"command": f"wc -l {LOG}"}, f"146 {LOG}")
    _call(ctl, {"command": "pwd"}, "/projects/modernized")
    for n in (40, 50, 60):
        d = _call(ctl, {"command": f'grep -B {n} "{PATTERN}" {LOG}'}, shown)
    assert d.action == "halt" and d.code == "read_family_no_new_content_halt"


def test_exact_call_guard_is_kept():
    ctl = _controller()
    args = {"command": "find src/main/java -name PetDto.java"}
    for _ in range(5):
        _call(ctl, args, "")
    assert ctl.halt_decision is not None
    assert ctl.halt_decision.code == "identical_call_streak_halt"
