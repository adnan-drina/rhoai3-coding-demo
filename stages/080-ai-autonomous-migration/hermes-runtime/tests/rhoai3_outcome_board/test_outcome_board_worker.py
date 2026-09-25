"""Outcome board with REAL kanban workers on the exact patched runtime (C1, C6).

Real dispatcher (kanban_db.dispatch_once), real `hermes -p <profile> chat -q`
workers with the golden kernel/pre_tool_call.sh registered fail-closed, the
golden on_kanban_dispatch_tick reconciler registered in the dispatcher
process, and a scripted fake provider (no model, no network model).

  M2 implementer   runs the K4 graph publisher from its terminal (identity
                   retained), then kanban_request_review (hook: read-back green)
  M2 reviewer      kanban_complete (hook: audit + publication + intent first)
  dispatcher tick  reconciles the M2 release
  outcome run 1    issue (run-bound), reads its brief attachment, prints its
                   run identity, writes the issued file, is REFUSED a file outside
                   the issue and REFUSED kanban_complete, records a pending
                   candidate, blocks
  outcome run 2    after unblock: a new native run re-issues with the retained
                   candidate and restores it; budget unchanged; blocks

Official logs ($HERMES_HOME/kanban/logs/<task>.log) are read and asserted on.
"""
import json
import os
import re
import sqlite3

from tests.rhoai3_b3b4 import _harness as H
from tests.rhoai3_b3b4.fake_openai_server import FakeProvider

from . import _ob

FOREIGN = "src/main/java/com/acme/shop/web/ItemController.java"
ISSUED_PATH = {"build:rk:pom": "pom.xml", "config:rk:cfg": "src/main/resources/application.properties"}


# The worker terminal runs `python3` as the terminal resolves it (K2 refuses an
# interpreter path outside the allow root). On this host that can be a python3
# whose USER site-packages carry PyYAML, which rejects the golden decisions.yaml
# that the harness's yamlite accepts; the test sets PYTHONNOUSERSITE=1 so the
# harness reads it as it does in the workspace image (see the report).
PY3 = "python3"


def _gate(cmd):
    return {"command": "%s .hermes/kernel/outcome_gate.py --root . %s" % (PY3, cmd)}


class Script:
    def __init__(self, dest, home):
        self.dest, self.home = dest, home

    def _run_profile(self, tid):
        con = sqlite3.connect(str(self.home / "kanban.db"))
        try:
            rows = con.execute("SELECT profile FROM task_runs WHERE task_id=? ORDER BY id", (tid,)).fetchall()
            return [r[0] for r in rows]
        finally:
            con.close()

    def _brief(self, tid):
        con = sqlite3.connect(str(self.home / "kanban.db"))
        try:
            return con.execute("SELECT stored_path FROM task_attachments WHERE task_id=? ORDER BY id", (tid,)).fetchone()[0]
        finally:
            con.close()

    def __call__(self, body):
        text = json.dumps(body["messages"])
        m = re.search(r"work kanban task (t_[0-9a-f]+)", text)
        tid = m.group(1) if m else ""
        n = sum(1 for msg in body["messages"] if msg.get("role") == "tool")
        runs = self._run_profile(tid)
        m2 = _ob.meta(self.dest, "m2_task") if (self.dest / "verification/outcome-board/authority.sqlite3").exists() else ""
        if not m2 or tid == m2:
            if runs and runs[-1] == "reviewer":
                seq = [("tool", "kanban_complete", {"summary": "graph published and read back"})]
            else:
                seq = [("tool", "terminal", {"command": "%s .hermes/kernel/k4_graph.py --root . publish "
                                                        "--plan-file evidence/planning/outcome-plan.json" % PY3}),
                       ("tool", "kanban_request_review", {"summary": "outcome graph published", "reviewer": "reviewer"})]
            return seq[n] if n < len(seq) else ("text", "done")
        con = _ob.store(self.dest)
        oid = con.execute("SELECT outcome_id FROM publication WHERE task_id=?", (tid,)).fetchone()[0]
        con.close()
        if len(runs) <= 1:
            seq = [("tool", "terminal", _gate("issue")),
                   ("tool", "terminal", {"command": "shasum -a 256 %s" % self._brief(tid)}),
                   ("tool", "terminal", {"command": "echo TASK=$HERMES_KANBAN_TASK RUN=$HERMES_KANBAN_RUN_ID"}),
                   ("tool", "write_file", {"path": str(self.dest / ISSUED_PATH[oid]), "content": "<candidate/>\n"}),
                   ("tool", "write_file", {"path": str(self.dest / FOREIGN), "content": "// not mine\n"}),
                   ("tool", "kanban_complete", {"summary": "trying to finish without acceptance"}),
                   ("tool", "terminal", _gate("verdict --verdict VERIFICATION_PENDING --attempt 1 --reason needs-prerequisite")),
                   ("tool", "kanban_block", {"reason": "VERIFICATION_PENDING: candidate retained", "kind": "needs_input"})]
        else:
            seq = [("tool", "terminal", _gate("issue")),
                   ("tool", "terminal", _gate("restore-pending")),
                   ("tool", "kanban_block", {"reason": "restored; waiting for verification", "kind": "needs_input"})]
        return seq[n] if n < len(seq) else ("text", "done")


def _log(home, tid):
    return (home / "kanban" / "logs" / ("%s.log" % tid)).read_text(errors="replace")


def _seen(provider, tid):
    """What the worker's model saw: every tool result of that task's latest request."""
    reqs = [r for r in H.agent_requests(provider) if ("work kanban task %s" % tid) in json.dumps(r["messages"])]
    if not reqs:
        return ""
    return "\n".join(str(m.get("content")) for m in reqs[-1]["messages"] if m.get("role") == "tool")


def test_outcome_board_with_real_workers(tmp_path, monkeypatch):
    dest, plan = _ob.make_dest(tmp_path)
    (dest / "evidence" / "planning" / "outcome-plan.json").write_text((tmp_path / "plan.json").read_text())
    home = dest / ".hermes" / "home"
    home.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    for k, v in _ob.env_for(dest).items():
        if k in ("HERMES_BIN", "K2_ALLOW_ROOT", "HERMES_WRITE_SAFE_ROOT", "PYTHONDONTWRITEBYTECODE"):
            monkeypatch.setenv(k, v)
    # the M2 paved-road audit is not what this test qualifies; the hook's existing override stands in for its exit 0
    monkeypatch.setenv("K2_PAVED_ROAD_AUDIT_EXIT", "0")
    monkeypatch.setenv("PYTHONNOUSERSITE", "1")
    with FakeProvider(Script(dest, home)) as provider:
        H.clean_env(monkeypatch, provider)
        cfg = _ob.hook_config(H.worker_config(dest), dest, tick=True)
        cfg["skills"] = dict(cfg["skills"], external_dirs=[str(dest / ".hermes" / "skills")])  # as dest-init declares them
        H.write_home(cfg, "implementer")
        H.write_home(cfg, "reviewer")
        from agent import shell_hooks
        shell_hooks.register_from_config(cfg, accept_hooks=True)       # the dispatcher process's hooks
        from hermes_cli import kanban_db as kb
        kb.init_db()
        conn = kb.connect()
        m2 = kb.create_task(conn, title="M2 PLAN", body="plan the migration", assignee="implementer",
                            workspace_kind="dir", workspace_path=str(dest), idempotency_key="m2-plan")

        # ---- M2: publication from the worker's terminal, identity retained ----------
        H.dispatch_and_reap(kb, conn, m2)
        seen = _seen(provider, m2)
        assert "OK: K4 graph published" in seen, seen[-3000:]
        assert _ob.meta(dest, "m2_task") == m2
        assert _ob.meta(dest, "publication_state") == "complete"
        assert conn.execute("SELECT status FROM tasks WHERE id=?", (m2,)).fetchone()[0] == "review"
        # ---- M2 reviewer completes; the hook records the release intent first -------
        H.dispatch_and_reap(kb, conn, m2)
        assert conn.execute("SELECT status FROM tasks WHERE id=?", (m2,)).fetchone()[0] == "done", _log(home, m2)[-3000:]
        crumbs = (dest / "evidence/receipts/hook/complete-invocations.jsonl").read_text()
        assert "outcome_complete_allowed" in crumbs
        # ---- the next tick spawns the first released outcome AND reconciles the release
        res = kb.dispatch_once(conn, max_in_progress=1)   # the deployed serial cap (kanban.max_in_progress: 1)
        assert len(res.spawned) == 1, res
        tid = res.spawned[0][0]
        assert _ob.meta(dest, "publication_state") == "released"
        oid = _ob.store(dest).execute("SELECT outcome_id FROM publication WHERE task_id=?", (tid,)).fetchone()[0]
        assert oid in ISSUED_PATH, oid
        pid = kb.get_task(conn, tid).worker_pid
        status = H.wait_exit(pid)
        kb._record_worker_exit(pid, status)
        run1 = [r for r in H.runs(conn, tid)][-1]
        log1 = _log(home, tid)
        # run-bound issue: the authority's record names this native run
        con = _ob.store(dest)
        issues = [dict(r) for r in con.execute("SELECT run_id, allowed_paths, state FROM issues WHERE task_id=? ORDER BY issue_id", (tid,))]
        att = con.execute("SELECT attachment_sha256 FROM publication WHERE task_id=?", (tid,)).fetchone()[0]
        con.close()
        assert issues and issues[0]["run_id"] == run1["id"], (issues, run1, _seen(provider, tid)[-4000:], log1[-2500:])
        assert json.loads(issues[0]["allowed_paths"]) == [ISSUED_PATH[oid]]
        seen1 = _seen(provider, tid)
        assert ("TASK=%s RUN=%s" % (tid, run1["id"])) in seen1, seen1[-4000:]            # the worker's own native run identity
        assert att in seen1, seen1[-4000:]                                             # the worker read its brief's exact bytes
        # refused by the real hook: its loop-card guard reads issued.json, which under this protocol is the
        # projection of the authority's issue (the outcome branch would refuse the same path WRITE_OUTSIDE_ISSUE)
        assert ("WRITE_OUTSIDE_ISSUE" in seen1 or "outside this card write set (pom.xml)" in seen1
                or "outside this card write set (src/main/resources/application.properties)" in seen1), seen1[-4000:]
        assert "OUTCOME_NOT_ACCEPTED" in seen1, seen1[-4000:]
        assert "outcome_gate.py --root . issue" in log1 and "kanban_block" in log1 or "block" in log1, log1[-3000:]
        assert (dest / ISSUED_PATH[oid]).read_text() == "<candidate/>\n"
        assert (dest / FOREIGN).read_text() == "// %s v0\n" % FOREIGN
        assert conn.execute("SELECT status FROM tasks WHERE id=?", (tid,)).fetchone()[0] == "blocked"
        crumbs = (dest / "evidence/receipts/hook/complete-invocations.jsonl").read_text()
        assert "outcome_outcome_not_accepted" in crumbs

        # ---- restart: a new native run re-issues with the retained candidate ---------
        assert kb.unblock_task(conn, tid) is True
        res = kb.dispatch_once(conn, max_in_progress=1)   # the deployed serial cap (kanban.max_in_progress: 1)
        assert [s[0] for s in res.spawned] == [tid], res
        pid = kb.get_task(conn, tid).worker_pid
        status = H.wait_exit(pid)
        kb._record_worker_exit(pid, status)
        run2 = H.runs(conn, tid)[-1]
        assert run2["id"] != run1["id"]
        log2 = _log(home, tid)
        seen2 = _seen(provider, tid)
        assert re.search(r'retained_candidate\\*": true', seen2) and re.search(r'baseline_moved\\*": false', seen2), seen2[-4000:]
        assert "outcome_gate.py --root . restore-pending" in log2                 # the official log records the calls
        con = _ob.store(dest)
        issues = [dict(r) for r in con.execute("SELECT run_id, state FROM issues WHERE task_id=? ORDER BY issue_id", (tid,))]
        kinds = [r[0] for r in con.execute("SELECT kind FROM ledger WHERE outcome_id=? ORDER BY seq", (oid,))]
        spent = con.execute("SELECT COUNT(*) FROM ledger WHERE outcome_id=? AND kind='reject'", (oid,)).fetchone()[0]
        con.close()
        assert [i["run_id"] for i in issues][-1] == run2["id"]
        assert [i["state"] for i in issues if i["run_id"] == run1["id"]] == ["superseded"]
        assert kinds.count("pending") == 1 and kinds.count("restore") == 1, kinds
        assert spent == 0                                                              # a pending attempt spends nothing
        assert (dest / ISSUED_PATH[oid]).read_text() == "<candidate/>\n"
        # the board says what the authority says: one live card per outcome, read-back clean
        import subprocess
        rb = subprocess.run(["python3", str(_ob.GOLDEN / "kernel" / "k4_graph.py"), "--root", str(dest), "readback"],
                            env=_ob.env_for(dest, HERMES_KANBAN_TASK=m2), capture_output=True, text=True)
        assert json.loads(rb.stdout)["gaps"] == [], rb.stdout
        # evidence for the implementation report
        out = os.environ.get("RHOAI3_OB_EVIDENCE")
        if out:
            os.makedirs(out, exist_ok=True)
            for name, t in (("m2", m2), ("outcome", tid)):
                with open(os.path.join(out, "%s.log" % name), "w") as fh:
                    fh.write(_log(home, t))
            with open(os.path.join(out, "summary.json"), "w") as fh:
                json.dump({"m2": m2, "outcome_task": tid, "outcome": oid, "run1": run1["id"], "run2": run2["id"],
                           "issues": issues, "ledger_kinds": kinds, "attachment_sha256": att,
                           "requests": len(H.agent_requests(provider))}, fh, indent=2)
        conn.close()
