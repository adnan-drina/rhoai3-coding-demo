"""Outcome board on the exact patched runtime: native publication, recovery,
dispatch hold and the dispatcher-tick continuation (C1; F2 on the real
dispatcher). Real `hermes kanban` CLI and kanban_db; no model is called.
"""
import json
import sqlite3
import subprocess

from . import _ob


def _db(home):
    con = sqlite3.connect(str(home / "kanban.db"))
    con.row_factory = sqlite3.Row
    return con


def _setup(tmp_path, monkeypatch):
    dest, plan = _ob.make_dest(tmp_path)
    home = dest / ".hermes" / "home"
    home.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    from hermes_cli import kanban_db as kb
    kb.init_db()
    conn = kb.connect()
    m2 = kb.create_task(conn, title="M2 PLAN", body="plan", assignee="implementer", workspace_kind="dir",
                        workspace_path=str(dest), idempotency_key="m2-plan")
    return dest, plan, home, kb, conn, m2


def _live(home, key):
    con = _db(home)
    try:
        return [dict(r) for r in con.execute("SELECT id, status FROM tasks WHERE idempotency_key=?", (key,))]
    finally:
        con.close()


def test_interrupted_publication_converges_and_archived_identity_stops(tmp_path, monkeypatch):
    dest, plan, home, kb, conn, m2 = _setup(tmp_path, monkeypatch)
    # crash (os._exit) after a native create and after an attach, then resume under the same command
    for point in ("after-create", "after-create", "after-attach"):
        p = _ob.publish(dest, tmp_path, m2, OB_FAULT=point)
        assert p.returncode == 97, (point, p.stdout, p.stderr)
    p = _ob.publish(dest, tmp_path, m2)
    assert p.returncode == 0, p.stderr
    assert "generation complete" in p.stdout
    from k4_graph import native_key
    for n in plan["nodes"]:
        rows = _live(home, native_key("q1", n))
        assert len(rows) == 1, (n["outcome_id"], rows)
        con = _db(home)
        atts = con.execute("SELECT COUNT(*) FROM task_attachments WHERE task_id=?", (rows[0]["id"],)).fetchone()[0]
        t = dict(con.execute("SELECT assignee, status, body FROM tasks WHERE id=?", (rows[0]["id"],)).fetchone())
        parents = [r[0] for r in con.execute("SELECT parent_id FROM task_links WHERE child_id=?", (rows[0]["id"],))]
        con.close()
        assert atts == 1, n["outcome_id"]
        assert t["assignee"] == (None if n["role"] == "deliver" else "implementer")
        assert t["status"] == "todo"                                   # the open M2 holds every executable node
        assert "```" not in t["body"]
        if n["role"] != "deliver":
            assert m2 in parents
    assert _ob.meta(dest, "m2_task") == m2                             # caller identity retained, recorded
    assert _ob.meta(dest, "publication_state") == "complete"
    rb = subprocess.run(["python3", str(_ob.GOLDEN / "kernel" / "k4_graph.py"), "--root", str(dest), "readback"],
                        env=_ob.env_for(dest, HERMES_KANBAN_TASK=m2), capture_output=True, text=True)
    assert rb.returncode == 0 and json.loads(rb.stdout)["gaps"] == [], rb.stdout + rb.stderr
    # an archived identity is never re-created: publication stops by name
    victim = _ob.task_of(dest, "config:rk:cfg")
    subprocess.run(_ob.HERMES_ARGV.split() + ["kanban", "archive", victim], check=True, capture_output=True, env=_ob.env_for(dest))
    p = _ob.publish(dest, tmp_path, m2)
    assert p.returncode == 1 and "PUBLICATION_ARCHIVED" in p.stderr, p.stderr
    assert len(_live(home, native_key("q1", {"outcome_id": "config:rk:cfg", "role": "repair"}))) == 1
    conn.close()


def test_worker_identity_is_required_and_scrubbing_it_refuses(tmp_path, monkeypatch):
    dest, plan, home, kb, conn, m2 = _setup(tmp_path, monkeypatch)
    env = _ob.env_for(dest)
    env.pop("HERMES_KANBAN_TASK", None)
    p = subprocess.run(["python3", str(_ob.GOLDEN / "kernel" / "k4_graph.py"), "--root", str(dest), "publish",
                        "--plan-file", str(tmp_path / "plan.json"), "--hermes", _ob.HERMES_ARGV],
                       env=env, capture_output=True, text=True)
    assert p.returncode == 1 and "K4_GRAPH_CALLER" in p.stderr
    kb.complete_task(conn, m2, summary="closed")
    p = _ob.publish(dest, tmp_path, m2)
    assert p.returncode == 1 and "PUBLICATION_M2_CLOSED" in p.stderr   # never publish under a closed M2
    conn.close()


def test_unassigned_delivery_stage_is_not_dispatched(tmp_path, monkeypatch):
    dest, plan, home, kb, conn, m2 = _setup(tmp_path, monkeypatch)
    assert _ob.publish(dest, tmp_path, m2).returncode == 0
    # the assessment (M5 PREFLIGHT's only parent) is done: set directly, the board state this test needs
    with kb.write_txn(conn):
        conn.execute("UPDATE tasks SET status='done' WHERE id=?", (_ob.task_of(dest, "assess:m4:g1"),))
    prep = _ob.task_of(dest, "deliver:prepare:c1")
    kb.recompute_ready(conn)
    row = dict(conn.execute("SELECT status, assignee FROM tasks WHERE id=?", (prep,)).fetchone())
    assert row == {"status": "ready", "assignee": None}
    out = subprocess.run(_ob.HERMES_ARGV.split() + ["kanban", "dispatch", "--dry-run", "--json"],
                         capture_output=True, text=True, env=_ob.env_for(dest))
    res = json.loads(out.stdout[out.stdout.find("{"):])
    spawned = [s[0] if isinstance(s, list) else s for s in res.get("spawned") or []]
    assert prep not in json.dumps(spawned)
    assert prep in json.dumps(res.get("skipped_unassigned") or [])
    conn.close()


def test_dispatch_tick_reconciles_a_completion_whose_process_died(tmp_path, monkeypatch):
    """F2 on the real dispatcher: M2's release intent is written before the
    native completion; the completing process dies before any continuation;
    the next dispatcher tick (on_kanban_dispatch_tick shell hook) finishes it."""
    dest, plan, home, kb, conn, m2 = _setup(tmp_path, monkeypatch)
    assert _ob.publish(dest, tmp_path, m2).returncode == 0
    from agent import shell_hooks
    cfg = _ob.hook_config({}, dest, tick=True)
    specs = shell_hooks.register_from_config(cfg, accept_hooks=True)
    assert any(s.event == "on_kanban_dispatch_tick" for s in specs)
    # the pre-completion step the hook performs (intent first), in a separate process
    check = subprocess.run(["python3", "-c",
                            "import sys; sys.path[:0]=[%r,%r]; from planner.outcome_hook import terminator; "
                            "import json,os; print(json.dumps(terminator(%r, kind='complete', profile='reviewer', "
                            "env=dict(os.environ), audit_green=lambda: True)))"
                            % (str(_ob.GOLDEN / "kernel"), str(_ob.GOLDEN / "lib"), str(dest))],
                           env=_ob.env_for(dest, HERMES_KANBAN_TASK=m2, HERMES_KANBAN_RUN_ID="0"), capture_output=True, text=True)
    assert json.loads(check.stdout.strip().splitlines()[-1])["action"] == "allow", check.stdout + check.stderr
    assert _ob.meta(dest, "release_in_progress") == "1"
    kb.complete_task(conn, m2, summary="plan released")                 # ... and the completing process dies here
    assert _ob.meta(dest, "publication_state") == "complete"             # nothing reconciled yet
    kb.dispatch_once(conn, dry_run=True)                                 # the dispatcher's next tick (no spawn)
    assert _ob.meta(dest, "publication_state") == "released"
    assert _ob.meta(dest, "release_in_progress") == "0"
    con = _ob.store(dest)
    assert con.execute("SELECT state FROM intents WHERE intent_id='m2-release'").fetchone()[0] == "done"
    con.close()
    kb.dispatch_once(conn, dry_run=True)                                 # idempotent
    conn.close()
