"""V16-3 part 1 (tmp/v16-run-20260925/architect-decision-v16-2-3-4.md, "V16-3"):
a persisted VERIFICATION_PENDING ends the worker's repair phase (patch 0011).

Runtime contract (agent/kanban_stop_request.py): the dispatcher gives each
worker run a per-run, initially absent path in ``HERMES_KANBAN_STOP_REQUEST``.
A tool the worker runs creates it with ``{"kind": "needs_input", "reason": ...}``.
After that tool result the runtime records the native ``needs_input`` block
once (bound to the run), refuses any later tool call, and ends the worker
before another model request. The candidate and every file stay where they are.
Only an unblock starts a new run (new run id, new absent path).

The golden side is simulated by three small scripts with the golden's names:
``advance.py`` retains the candidate under ``verification/loop/pending-files``,
restores the accepted file, records the pending row in
``verification/loop/steps.json`` and, when the environment offers the path,
raises the stop request. ``restore-pending.py`` puts the candidate back and
``run-verify.sh`` records a verification. Every script appends to
``verification/trace.log``. The model is scripted: before the prerequisite
exists it reproduces the incident (advance, then the expanding grep); after
the Operator prerequisite it runs restore, verify, advance and completes.
Real kanban dispatcher and real ``hermes -p implementer chat -q`` workers.
"""

import hashlib
import json
import os
import sys
import textwrap
from pathlib import Path

from . import _harness as H
from .fake_openai_server import FakeProvider

SRC = "src/main/java/org/springframework/samples/petclinic/rest/RootRestController.java"
ACCEPTED = "class RootRestController { /* accepted: SpEL @Value */ }\n"
CANDIDATE = "class RootRestController { /* candidate: ConfigProperty */ }\n"
CLUSTER = "c:488e7e2d2ac4"
PENDING_DIR = "verification/loop/pending-files/c_488e7e2d2ac4"
LOG = "verification/build/package.log"
PY = sys.executable

ADVANCE = textwrap.dedent(f'''
    import hashlib, json, os, shutil, sys
    from pathlib import Path
    root = Path(".")
    trace = root / "verification/trace.log"
    src, pend = root / "{SRC}", root / "{PENDING_DIR}" / "RootRestController.java"
    steps_p = root / "verification/loop/steps.json"
    steps = json.loads(steps_p.read_text()) if steps_p.exists() else {{"steps": [], "pending": []}}
    with trace.open("a") as fh:
        fh.write("advance run=%s\\n" % os.environ.get("HERMES_KANBAN_RUN_ID"))
    if (root / "verification/prereq").exists() and src.read_text() == {CANDIDATE!r}:
        steps["pending"] = []
        steps["steps"].append({{"cluster": "{CLUSTER}", "verdict": "ACCEPTED"}})
        steps_p.write_text(json.dumps(steps))
        print("ACCEPTED {CLUSTER}")
        sys.exit(0)
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    pend.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, pend)
    src.write_text({ACCEPTED!r})
    steps["pending"].append({{"cluster": "{CLUSTER}", "card": os.environ.get("HERMES_KANBAN_TASK"),
                             "candidate_sha256": digest}})
    steps_p.write_text(json.dumps(steps))
    reason = ("VERIFICATION_PENDING {CLUSTER} cause=unproven-repair card=%s: candidate retained "
              "(sha256 %s) under {PENDING_DIR}; needs an Operator prerequisite, then "
              "restore-pending.py, run-verify.sh --mode acceptance, advance.py"
              % (os.environ.get("HERMES_KANBAN_TASK"), digest[:16]))
    print(reason)
    req = os.environ.get("HERMES_KANBAN_STOP_REQUEST")
    if req:
        Path(req).write_text(json.dumps({{"kind": "needs_input", "reason": reason,
                                          "task": os.environ.get("HERMES_KANBAN_TASK")}}))
    sys.exit(1)
''')

RESTORE = textwrap.dedent(f'''
    import shutil
    from pathlib import Path
    shutil.copy("{PENDING_DIR}/RootRestController.java", "{SRC}")
    with open("verification/trace.log", "a") as fh:
        fh.write("restore\\n")
    print("RESTORED {CLUSTER}")
''')

VERIFY = textwrap.dedent('''
    echo verify >> verification/trace.log
    echo "VERIFY acceptance: package PASS"
''')


def _cmd(script, *args):
    return {"command": " ".join([script, *args])}


ADVANCE_CALL = _cmd(f"{PY} advance.py", "--root", ".", "--cluster", CLUSTER)
RESTORE_CALL = _cmd(f"{PY} restore-pending.py", "--root", ".", "--cluster", CLUSTER)
VERIFY_CALL = _cmd("bash run-verify.sh", "--root", ".", "--mode", "acceptance")
COMPLETE = ("tool", "kanban_complete", {"summary": "accepted after the Operator prerequisite"})
GREP_SEQ = [10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200, 300, 500, 1000]


def _repo(tmp_path):
    repo = tmp_path / "modernized"
    (repo / Path(SRC).parent).mkdir(parents=True)
    (repo / SRC).write_text(CANDIDATE)  # the worker's candidate is on the tree
    (repo / LOG).parent.mkdir(parents=True)
    (repo / LOG).write_text("[INFO] Scanning\n[INFO] ---\n[INFO] \n"
                            "[INFO] Building spring-petclinic-rest 2.6.2\n"
                            + "".join(f"[INFO] build line {i}\n" for i in range(5, 147)))
    (repo / "verification/loop").mkdir(parents=True, exist_ok=True)
    (repo / "advance.py").write_text(ADVANCE)
    (repo / "restore-pending.py").write_text(RESTORE)
    (repo / "run-verify.sh").write_text(VERIFY)
    return repo


def _responder(repo):
    def respond(body):
        n = sum(1 for m in body["messages"] if m.get("role") == "tool")
        if not (repo / "verification/prereq").exists():
            # The incident: advance.py returns VERIFICATION_PENDING, then the
            # model widens a grep over the package log.
            if n == 0:
                return ("tool", "terminal", ADVANCE_CALL)
            k = GREP_SEQ[min(n - 1, len(GREP_SEQ) - 1)]
            return ("tool", "terminal",
                    {"command": f'cat {LOG} | grep -B {k} "Building spring-petclinic"'})
        seq = [("tool", "terminal", RESTORE_CALL), ("tool", "terminal", VERIFY_CALL),
               ("tool", "terminal", ADVANCE_CALL), COMPLETE]
        return seq[n] if n < len(seq) else ("text", "done")
    return respond


def _start(tmp_path, monkeypatch, provider, repo):
    H.clean_env(monkeypatch, provider)
    H.write_home(H.worker_config(repo))
    from hermes_cli import kanban_db as kb

    kb.init_db()
    conn = kb.connect()
    tid = kb.create_task(conn, title="rest-root-controller-spel", body="repair RootRestController",
                         assignee="implementer", workspace_kind="dir", workspace_path=str(repo))
    return kb, conn, tid


def _task_row(conn, tid):
    return dict(conn.execute("SELECT status, block_kind, current_run_id, consecutive_failures "
                             "FROM tasks WHERE id = ?", (tid,)).fetchone())


def _run_pending(kb, conn, tid, provider, repo):
    """Run 1: advance.py -> VERIFICATION_PENDING. Returns the worker exit code."""
    exit_code = H.dispatch_and_reap(kb, conn, tid)
    return exit_code, len(H.agent_requests(provider))


def test_pending_blocks_once_keeps_candidate_and_is_not_retried(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    with FakeProvider(_responder(repo)) as provider:
        kb, conn, tid = _start(tmp_path, monkeypatch, provider, repo)
        exit_code, n_requests = _run_pending(kb, conn, tid, provider, repo)
        # The worker ended right after the advance.py result: one model request,
        # no grep loop, no further tool call.
        assert n_requests == 1, f"worker made {n_requests} agent model requests"
        assert (repo / "verification/trace.log").read_text().splitlines() == ["advance run=1"]
        assert exit_code == 0
        row = _task_row(conn, tid)
        assert (row["status"], row["block_kind"]) == ("blocked", "needs_input")
        assert row["consecutive_failures"] == 0
        kinds = [k for k, _ in H.events(conn, tid)]
        assert kinds.count("blocked") == 1, kinds
        assert kinds.count("worker_stop_request") == 1, kinds
        for bad in ("completed", "crashed", "gave_up", "protocol_violation"):
            assert bad not in kinds, kinds
        runs = H.runs(conn, tid)
        assert [r["outcome"] for r in runs] == ["blocked"]
        blocked = [p for k, p in H.events(conn, tid) if k == "blocked"][0]
        assert blocked["reason"].startswith(f"VERIFICATION_PENDING {CLUSTER}")
        stop = [p for k, p in H.events(conn, tid) if k == "worker_stop_request"][0]
        assert stop["kind"] == "needs_input" and stop["request"] == f"{tid}.run1.json"
        # The candidate is retained off-tree, byte for byte; the accepted file is on disk.
        assert (repo / PENDING_DIR / "RootRestController.java").read_text() == CANDIDATE
        assert (repo / SRC).read_text() == ACCEPTED
        steps = json.loads((repo / "verification/loop/steps.json").read_text())
        assert steps["pending"][0]["candidate_sha256"] == hashlib.sha256(CANDIDATE.encode()).hexdigest()
        # No same-state automatic retry: the dispatcher neither reaps nor respawns it.
        assert kb.detect_crashed_workers(conn) == []
        for _ in range(3):
            assert kb.dispatch_once(conn).spawned == []
        assert _task_row(conn, tid)["status"] == "blocked"
        assert len(H.agent_requests(provider)) == 1
        assert [k for k, _ in H.events(conn, tid)].count("blocked") == 1
        conn.close()


def test_operator_recovery_allows_restore_verify_advance(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    with FakeProvider(_responder(repo)) as provider:
        kb, conn, tid = _start(tmp_path, monkeypatch, provider, repo)
        _run_pending(kb, conn, tid, provider, repo)
        assert _task_row(conn, tid)["status"] == "blocked"

        # Operator prerequisite (the v16 operator-step beside the pending card),
        # then one native unblock.
        (repo / "verification/prereq").write_text("ADR-004 @Typed delegates\n")
        assert kb.unblock_task(conn, tid) is True

        exit_code = H.dispatch_and_reap(kb, conn, tid)
        assert exit_code == 0
        assert (repo / "verification/trace.log").read_text().splitlines() == [
            "advance run=1", "restore", "verify", "advance run=2"]
        row = _task_row(conn, tid)
        assert row["status"] == "done", row
        runs = H.runs(conn, tid)
        assert [r["outcome"] for r in runs] == ["blocked", "completed"]
        # The resumed run had its own, absent stop-request path; nothing stopped it.
        kinds = [k for k, _ in H.events(conn, tid)]
        assert kinds.count("blocked") == 1 and kinds.count("worker_stop_request") == 1
        assert (repo / SRC).read_text() == CANDIDATE
        assert json.loads((repo / "verification/loop/steps.json").read_text())["pending"] == []
        conn.close()
