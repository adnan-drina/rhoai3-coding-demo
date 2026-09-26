"""Automatic owner recovery on the exact patched runtime, through the protected
authority service, with the REAL classifier (planner.runtime_cause.classify).

Real `hermes kanban` board (kanban_db claims/blocks/completes stand in for the
dispatcher and the worker's terminators; no model is called). The authority is
a separate process (kernel/outcome_authority.py serve, private Hermes home);
every transition goes through it (RemoteCtx). The service itself is crashed
(OB_FAULT, os._exit) after the revision and again after the publication of the
repair, and restarted: exactly ONE repair card results.

Sequence: three prerequisite outcomes accepted (the owner committed ItemDto.java)
-> the dependent (ItemController) fails scenario items-list with an NPE thrown
in ItemDto, and the ACCEPTED baseline's record shows the identical failure
-> the authority classifies pre-existing-owner-defect, holds the candidate, spends
nothing -> the worker ends with kanban_block kind=dependency -> the repair card is
the dependent's parent and shares the owner's budget key -> the repair is NOT
accepted until items-list passes on its tree, then is -> the dependent is
dispatched again, gets its held candidate back, is re-verified on the repaired
baseline and accepted -> its completion continuation runs.
Then the counterexample (changed caller, unchanged callee, baseline PASSING)
on another dependent: an ordinary rejection with the attempt spent.
The scenario records are worker receipts (declared measurement trust)."""
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import _ob

SID = "items-list"
CALLEE = "src/main/java/com/acme/shop/dto/ItemDto.java"
CALLER = "src/main/java/com/acme/shop/web/ItemController.java"
ERROR = {"exception": "java.lang.NullPointerException",
         "frames": [{"class": "com.acme.shop.dto.ItemDto", "method": "getName", "file": CALLEE, "line": 12},
                    {"class": "com.acme.shop.web.ItemController", "method": "list", "file": CALLER, "line": 40}],
         "stack_sha256": "b" * 64}


class Env:
    def __init__(self, tmp_path, monkeypatch):
        self.dest, self.plan = _ob.make_dest(tmp_path)
        self.home = self.dest / ".hermes" / "home"
        self.home.mkdir(parents=True)
        monkeypatch.setenv("HERMES_HOME", str(self.home))
        from hermes_cli import kanban_db as kb
        self.kb = kb
        kb.init_db()
        self.conn = kb.connect()
        self.m2 = kb.create_task(self.conn, title="M2 PLAN", body="plan", assignee="implementer", workspace_kind="dir",
                                 workspace_path=str(self.dest), idempotency_key="m2-plan")
        self.sock = Path(tempfile.mkdtemp(prefix="obr", dir="/tmp")) / "authority.sock"
        self.store_dir = (tmp_path / "svc-store").resolve()
        pins = json.loads((self.dest / ".hermes/pins.json").read_text())
        pins["pins"]["planner"]["outcome_board"]["authority_socket"] = str(self.sock)
        (self.dest / ".hermes/pins.json").write_text(json.dumps(pins))
        self.svc = None
        self.start()
        from planner import outcome_lifecycle as L
        from planner.outcome_native import KanbanNative
        self.L = L
        self.native = KanbanNative(str(self.home / "kanban.db"))

    def start(self, fault=""):
        if self.svc is not None and self.svc.poll() is None:
            self.svc.terminate()
            self.svc.wait(10)
        if self.sock.exists():
            self.sock.unlink()
        env = {k: v for k, v in os.environ.items() if not k.startswith("HERMES_") and k != "OB_FAULT"}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if fault:
            env["OB_FAULT"] = fault
        self.svc = subprocess.Popen([sys.executable, str(_ob.GOLDEN / "kernel/outcome_authority.py"), "serve",
                                     "--root", str(self.dest.resolve()), "--store-dir", str(self.store_dir),
                                     "--socket", str(self.sock), "--native-db", str((self.home / "kanban.db").resolve()),
                                     "--hermes", _ob.HERMES_ARGV], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        for _ in range(200):
            if self.sock.exists():
                return
            time.sleep(0.05)
        raise RuntimeError("service did not start")

    def ctx(self):
        return self.L.RemoteCtx(self.dest, str(self.sock), self.native)

    def tick(self):
        from planner.outcome_authority import call
        return call(str(self.sock), "tick", {})

    def tid(self, oid):
        from k4_graph import native_key
        node = next(n for n in self.store_plan()["nodes"] if n["outcome_id"] == oid)
        return [r[0] for r in self.conn.execute("SELECT id FROM tasks WHERE idempotency_key=? AND status!='archived'",
                                                (native_key("q1", node),))][0]

    def store_plan(self):
        import sqlite3
        con = sqlite3.connect(str(self.store_dir / "authority.sqlite3"))
        try:
            row = con.execute("SELECT doc FROM revisions WHERE state='published' ORDER BY rev DESC LIMIT 1").fetchone()
            return json.loads(row[0])
        finally:
            con.close()

    def claim(self, oid):
        tid = self.tid(oid)
        self.kb.recompute_ready(self.conn)
        t = self.kb.claim_task(self.conn, tid)
        assert t is not None, (oid, self.kb.get_task(self.conn, tid).status)
        dead = subprocess.Popen(["true"])
        dead.wait()
        self.conn.execute("UPDATE tasks SET worker_pid=? WHERE id=?", (dead.pid, tid))
        self.conn.commit()
        return tid, t.current_run_id, t.claim_lock

    def issue(self, oid):
        tid, run, lock = self.claim(oid)
        iss = self.L.issue(self.ctx(), task_id=tid, run_id=run, claim_lock=lock, pid=0, pgid=0)
        return tid, run, iss

    def worklist(self, mutate):
        p = self.dest / "evidence/planning/worklist.json"
        wl = json.loads(p.read_text())
        mutate(wl)
        p.write_text(json.dumps(wl))

    def drop(self, *ids):
        def m(wl):
            wl["items"] = [i for i in wl["items"] if i["id"] not in ids]
            for c in wl["clusters"]:
                c["items"] = [i for i in c["items"] if i not in ids]
            wl["clusters"] = [c for c in wl["clusters"] if c["items"]]
        self.worklist(m)

    def runtime_item(self, present):
        def m(wl):
            wl["items"] = [i for i in wl["items"] if i["id"] != "rt:items-list"]
            for c in wl["clusters"]:
                c["items"] = [i for i in c["items"] if i != "rt:items-list"]
            if present:
                wl["items"].append({"id": "rt:items-list", "source": "parity", "kind": "parity", "category": "mandatory",
                                    "scenario": SID, "entry_point": "com.acme.shop.web.ItemController#list():http", "path": ""})
                next(c for c in wl["clusters"] if c["id"] == "c:item")["items"].append("rt:items-list")
        self.worklist(m)

    def record(self, where, verdict, tree, error=None):
        d = self.dest / ("verification/loop/accepted/parity" if where == "baseline" else "verification/parity") / "scenarios"
        d.mkdir(parents=True, exist_ok=True)
        doc = {"scenario": SID, "verdict": verdict, "binding": {"candidate_sha256": tree}}
        if error:
            doc["server_error"] = error
        (d / (SID + ".json")).write_text(json.dumps(doc))

    def tree(self):
        from planner.canonical import product_tree_sha256
        return product_tree_sha256(self.dest)

    def edit(self, rel, text):
        (self.dest / rel).write_text(text)

    def accept(self, oid, *, edit=True, classes=("build", "compile", "tests"), before_commit=None):
        tid, run, iss = self.issue(oid)
        if edit:
            self.edit(iss["allowed_paths"][0], "// %s accepted by %s\n" % (iss["allowed_paths"][0], oid))
        if before_commit:
            before_commit()
        self.L.record_verdict(self.ctx(), task_id=tid, run_id=run, verdict="ACCEPTED", candidate="", attempt="a")
        _ob.git(self.dest, "commit", "-qam", "accept %s" % oid, "--allow-empty")
        node = next(n for n in self.store_plan()["nodes"] if n["outcome_id"] == oid)
        self.drop(*node["obligations"])
        out = self.L.accept_commit(self.ctx(), task_id=tid, run_id=run, attempt="a",
                                   commit=_ob.git(self.dest, "rev-parse", "HEAD"), measurement={"classes": list(classes)})
        if out["outcome_accepted"]:
            self.L.check_complete(self.ctx(), task_id=tid, run_id=run, profile="implementer", audit_green=True)
            self.kb.complete_task(self.conn, tid, summary="accepted")
            self.tick()
        return tid, run, out

    def close(self):
        if self.svc is not None and self.svc.poll() is None:
            self.svc.terminate()
            self.svc.wait(10)
        self.conn.close()


def _released(tmp_path, monkeypatch):
    e = Env(tmp_path, monkeypatch)
    p = _ob.publish(e.dest, tmp_path, e.m2)
    assert p.returncode == 0, p.stdout + p.stderr
    from planner import outcome_hook as HK
    d = HK.terminator(str(e.dest), kind="complete", profile="reviewer", env={"HERMES_KANBAN_TASK": e.m2, "HERMES_KANBAN_RUN_ID": "0"},
                      audit_green=lambda: True)
    assert d["action"] == "allow", d
    e.kb.complete_task(e.conn, e.m2, summary="M2 reviewed")
    e.tick()
    for oid in ("build:rk:pom", "config:rk:cfg", "source:u:dto-mapper"):
        _t, _r, out = e.accept(oid)
        assert out["outcome_accepted"], (oid, out)
    return e


def test_owner_recovery_end_to_end_on_the_service(tmp_path, monkeypatch):
    e = _released(tmp_path, monkeypatch)
    L = e.L
    try:
        owner, dep = "source:u:dto-mapper", "source:rk:item"
        tid, run, iss = e.issue(dep)
        e.record("baseline", "FAIL", iss["baseline_tree"], ERROR)
        e.edit(CALLER, "// caller changed by the dependent\n")
        e.record("live", "FAIL", e.tree(), ERROR)
        e.runtime_item(True)
        out = L.record_verdict(e.ctx(), task_id=tid, run_id=run, verdict="REVERTED", candidate="0" * 64, attempt="1",
                               reason="scenario items-list 500")
        assert (out["verdict"], out["owner"], out["spent"]) == ("OWNER_RECOVERY", owner, 0), out
        _ob.git(e.dest, "checkout", "--", CALLER)
        # the worker's terminator: complete is refused naming it; the dependency block is the native route
        try:
            L.check_complete(e.ctx(), task_id=tid, run_id=run, profile="implementer", audit_green=True)
            raise AssertionError("completion allowed while the owner repair is pending")
        except L.Refusal as exc:
            assert exc.code == "OWNER_REPAIR_PENDING" and "kanban_block kind=dependency" in exc.detail
        assert e.kb.block_task(e.conn, tid, reason="waits on the owner repair", kind="dependency")
        # the authority itself crashes after the revision, then after the publication; restarted each time
        for fault in ("reconcile-after-revision", "reconcile-after-publish"):
            e.start(fault=fault)
            try:
                e.tick()
            except Exception:
                pass
            assert e.svc.wait(10) == 97
        e.start()
        e.tick()
        e.tick()
        fid = L.owner_repair_id(owner, dep)
        from k4_graph import native_key
        node = next(n for n in e.store_plan()["nodes"] if n["outcome_id"] == fid)
        cards = [r[0] for r in e.conn.execute("SELECT id FROM tasks WHERE idempotency_key=?", (native_key("q1", node),))]
        assert len(cards) == 1, cards
        ftid = cards[0]
        parents = [r[0] for r in e.conn.execute("SELECT parent_id FROM task_links WHERE child_id=?", (tid,))]
        assert ftid in parents                                          # the dependent waits on the repair
        assert tid not in [r[0] for r in e.conn.execute("SELECT parent_id FROM task_links WHERE child_id=?", (ftid,))]
        assert e.kb.get_task(e.conn, tid).status == "todo"
        assert e.kb.get_task(e.conn, ftid).assignee == "implementer"
        # the repair: not accepted until the failing scenario passes on its tree
        tid_r, run_r, out = e.accept(fid, edit=False, before_commit=lambda: e.edit(CALLEE, "// null-safe\n"),
                                     classes=("compile", "tests"))
        assert not out["outcome_accepted"] and out["repair_evidence_gaps"], out
        e.kb.block_task(e.conn, tid_r, reason="scenario not yet passing", kind="dependency")

        def passing():
            e.edit(CALLEE, "// null-safe, measured\n")
            e.record("live", "PASS", e.tree())
        _t, _r, out = e.accept(fid, edit=False, before_commit=passing, classes=("compile", "tests"))
        assert out["outcome_accepted"], out
        # the dependent is dispatched again, restores its held candidate, is re-verified and accepted
        tid2, run2, iss2 = e.issue(dep)
        assert tid2 == tid and iss2["baseline_commit"] != iss["baseline_commit"]
        held = L.restore_held(e.ctx(), task_id=tid, run_id=run2)
        for rel, b64 in held["files"].items():
            (e.dest / rel).write_bytes(base64.b64decode(b64))
        assert "caller changed" in (e.dest / CALLER).read_text()
        e.record("live", "PASS", e.tree())
        L.record_verdict(e.ctx(), task_id=tid, run_id=run2, verdict="ACCEPTED", candidate="", attempt="2")
        _ob.git(e.dest, "commit", "-qam", "dependent on the repaired baseline")
        node = next(n for n in e.store_plan()["nodes"] if n["outcome_id"] == dep)
        e.drop(*node["obligations"])
        e.runtime_item(False)
        out = L.accept_commit(e.ctx(), task_id=tid, run_id=run2, attempt="2", commit=_ob.git(e.dest, "rev-parse", "HEAD"),
                              measurement={"classes": ["compile", "tests"]})
        assert out["outcome_accepted"], out
        intent = L.check_complete(e.ctx(), task_id=tid, run_id=run2, profile="implementer", audit_green=True)["intent"]
        e.kb.complete_task(e.conn, tid, summary="accepted on the repaired baseline")
        e.tick()
        import sqlite3
        con = sqlite3.connect(str(e.store_dir / "authority.sqlite3"))
        try:
            assert con.execute("SELECT state FROM intents WHERE intent_id=?", (intent,)).fetchone()[0] == "done"
            assert con.execute("SELECT COUNT(*) FROM intents WHERE kind='owner-repair'").fetchone()[0] == 1
            keys = dict(con.execute("SELECT outcome_id, budget_key FROM outcomes WHERE outcome_id IN (?,?)", (owner, fid)).fetchall())
            assert keys[owner] == keys[fid]
            spent_dep = con.execute("SELECT COUNT(*) FROM ledger l JOIN outcomes o ON o.budget_key=l.budget_key "
                                    "WHERE o.outcome_id=? AND l.kind='reject'", (dep,)).fetchone()[0]
            assert spent_dep == 0
        finally:
            con.close()
    finally:
        e.close()


def test_changed_caller_unchanged_callee_baseline_passing_spends_the_attempt(tmp_path, monkeypatch):
    e = _released(tmp_path, monkeypatch)
    L = e.L
    try:
        tid, run, iss = e.issue("source:rk:item")
        e.record("baseline", "PASS", iss["baseline_tree"])
        e.edit(CALLER, "// caller now passes invalid input to the unchanged callee\n")
        e.record("live", "FAIL", e.tree(), ERROR)
        e.runtime_item(True)
        out = L.record_verdict(e.ctx(), task_id=tid, run_id=run, verdict="REVERTED", candidate="", attempt="1", reason="500")
        assert (out["verdict"], out["spent"]) == ("REVERTED", 1), out
        e.tick()
        import sqlite3
        con = sqlite3.connect(str(e.store_dir / "authority.sqlite3"))
        try:
            assert con.execute("SELECT COUNT(*) FROM intents WHERE kind='owner-repair'").fetchone()[0] == 0
        finally:
            con.close()
    finally:
        e.close()
