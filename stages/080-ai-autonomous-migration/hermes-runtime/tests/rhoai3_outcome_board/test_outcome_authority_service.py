"""The protected authority service on the exact patched runtime (F1 integration).

The service runs as its own process (kernel/outcome_authority.py serve) with the
REAL `hermes kanban` CLI under a PRIVATE, empty HERMES_HOME and only the
recorded board database and attachment root shared. The M2 worker publishes
through the public entry point (k4_graph.py publish), which routes to the
service; the store never appears in the destination tree; the worker-side
read-back, the native rows and the attachment bytes are the ones the worker
reads. Same uid here: this qualifies the runtime integration (private home,
HERMES_KANBAN_DB + HERMES_KANBAN_ATTACHMENTS_ROOT), not the kernel boundary
(outcome-authority-two-uid.qualify.py and the live Dev Spaces qualification).
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from . import _ob


def _db(home):
    con = sqlite3.connect(str(home / "kanban.db"))
    con.row_factory = sqlite3.Row
    return con


def test_service_publishes_with_a_private_home_on_the_shared_board(tmp_path, monkeypatch):
    dest, plan = _ob.make_dest(tmp_path)
    home = dest / ".hermes" / "home"
    home.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    from hermes_cli import kanban_db as kb
    kb.init_db()
    conn = kb.connect()
    m2 = kb.create_task(conn, title="M2 PLAN", body="plan", assignee="implementer", workspace_kind="dir",
                        workspace_path=str(dest), idempotency_key="m2-plan")
    import tempfile
    sock_dir = Path(tempfile.mkdtemp(prefix="oba", dir="/tmp"))      # AF_UNIX paths are short (macOS: 104 bytes)
    sock = sock_dir / "authority.sock"
    store_dir = (tmp_path / "svc-store").resolve()
    pins = json.loads((dest / ".hermes" / "pins.json").read_text())
    pins["pins"]["planner"]["outcome_board"]["authority_socket"] = str(sock)
    (dest / ".hermes" / "pins.json").write_text(json.dumps(pins))
    env = {k: v for k, v in os.environ.items() if not k.startswith("HERMES_")}
    env.update(PYTHONDONTWRITEBYTECODE="1")
    svc = subprocess.Popen([sys.executable, str(_ob.GOLDEN / "kernel" / "outcome_authority.py"), "serve",
                            "--root", str(dest.resolve()), "--store-dir", str(store_dir), "--socket", str(sock),
                            "--native-db", str((home / "kanban.db").resolve()), "--hermes", _ob.HERMES_ARGV],
                           env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(200):
            if sock.exists():
                break
            time.sleep(0.05)
        p = _ob.publish(dest, tmp_path, m2)
        assert p.returncode == 0, p.stdout + p.stderr
        assert "generation complete" in p.stdout
        assert not (dest / "verification" / "outcome-board" / "authority.sqlite3").exists()
        assert (store_dir / "authority.sqlite3").is_file()
        # the private home stayed private: no board, no config read from the worker's home
        assert not (store_dir / "hermes-home" / "kanban.db").exists()
        from k4_graph import native_key
        con = _db(home)
        try:
            for n in plan["nodes"]:
                rows = [dict(r) for r in con.execute("SELECT id, status, assignee FROM tasks WHERE idempotency_key=?",
                                                     (native_key("q1", n),))]
                assert len(rows) == 1, (n["outcome_id"], rows)
                assert rows[0]["assignee"] == (None if n["role"] == "deliver" else "implementer")
                assert rows[0]["status"] == "todo"
                atts = [dict(a) for a in con.execute("SELECT stored_path FROM task_attachments WHERE task_id=?", (rows[0]["id"],))]
                assert len(atts) == 1
                assert atts[0]["stored_path"].startswith(str(home.resolve())), atts        # where the worker reads it
                assert os.path.isfile(atts[0]["stored_path"])
        finally:
            con.close()
        rb = subprocess.run(["python3", str(_ob.GOLDEN / "kernel" / "k4_graph.py"), "--root", str(dest), "readback"],
                            env=_ob.env_for(dest, HERMES_KANBAN_TASK=m2), capture_output=True, text=True)
        assert rb.returncode == 0 and json.loads(rb.stdout)["gaps"] == [], rb.stdout + rb.stderr
    finally:
        svc.terminate()
        out = svc.communicate(timeout=10)[0]
        conn.close()
    assert "serving" in out
