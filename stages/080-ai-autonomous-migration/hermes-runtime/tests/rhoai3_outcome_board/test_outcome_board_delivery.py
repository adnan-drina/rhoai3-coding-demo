"""Outcome board, review R3/R5 exits, with REAL kanban workers on the exact runtime.

Real dispatcher, real `hermes -p implementer|reviewer chat -q` workers, the
golden fail-closed pre_tool_call hook and the golden on_kanban_dispatch_tick
reconciler, a scripted fake provider (no model).

  accepted repair   the build outcome's worker commits through the loop's
                    acceptance stand-in and is KILLED right after the commit;
                    the dispatcher respawns it; the next run's issue recovers that
                    commit from Git; the re-measured tree finishes that
                    acceptance; the worker completes. No new card, no spend.
  REFUSE → reassess a real M4 worker records REFUSE; its reviewer completes it;
                    the dispatcher tick publishes the follow-up and successor;
                    a real M4 worker records PROVISIONAL_ACCEPT; the tick grants
                    M5 PREFLIGHT.
  M5                PREFLIGHT → reviewer → DEPLOY → reviewer → VALIDATE → reviewer,
                    each stage running its ACTUAL producer scripts, each reviewer
                    running the ACTUAL paved-road audit on the official log.

External effects are inert and identity-recording: `git push` goes to a local
bare repository; `oc` is a shim that answers only get/list for the pushed
revision and records every call (KUBECONFIG=/nonexistent besides); the Route
is a local HTTPS server on [::1]. Prerequisite outcomes other than the build
outcome and the follow-up are accepted in-process on the real board (labelled
below), not by workers.
"""
import hashlib
import json
import os
import re
import sqlite3
import ssl
import subprocess
import sys
import textwrap
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from tests.rhoai3_b3b4 import _harness as H
from tests.rhoai3_b3b4.fake_openai_server import FakeProvider

from . import _ob

J = "src/main/java/com/acme/shop/"
M5 = ".hermes/skills/paved-road/paved-road-m5"
PARITY_ITEM = {"id": "parity:items-list:body", "source": "parity", "kind": "parity", "category": "mandatory",
               "path": J + "web/ItemController.java", "line": 0, "rule_id": "",
               "entry_point": "ep:com.acme.shop.web.ItemController#list():http", "scenario": "items-list"}
PARITY_CLUSTER = {"id": "c:p-items", "kind": "parity", "items": [PARITY_ITEM["id"]], "path": PARITY_ITEM["path"],
                  "write_set": [PARITY_ITEM["path"]], "order_key": [5, 0, PARITY_ITEM["path"]], "status": "open", "gate": "parity"}

ADVANCE_SIM = textwrap.dedent('''
    """Stand-in for fix-until-green/advance.py around ITS OUTCOME BOARD CALLS ONLY:
    the real _outcome_bridge records the verdict; the commit is the loop's own.
    commit-and-die: accept-begin, commit, then SIGKILL this worker (the
    dispatcher-recorded pid) -- the crash window of review R5.
    finish <item>: the re-measured work list without <item>, then the bridge
    finishes a recovered acceptance exactly as advance.py does."""
    import json, os, signal, sqlite3, subprocess, sys
    from pathlib import Path
    root = Path(".").resolve()
    for p in ("skills/migration/fix-until-green/scripts", "lib", "kernel"):
        sys.path.insert(0, str(root / ".hermes" / p))
    import _outcome_bridge as B
    from planner.canonical import product_tree_sha256
    if sys.argv[1] == "commit-and-die":
        assert B.record(root, "ACCEPTED", product_tree_sha256(root)) == 0
        subprocess.run(["git", "-C", str(root), "commit", "-qam", "fix-until-green: accepted"], check=True)
        con = sqlite3.connect(os.environ["HERMES_KANBAN_DB"])
        pid = con.execute("SELECT worker_pid FROM tasks WHERE id=?", (os.environ["HERMES_KANBAN_TASK"],)).fetchone()[0]
        os.kill(int(pid), signal.SIGKILL)
    else:
        p = root / "evidence/planning/worklist.json"
        wl = json.loads(p.read_text())
        wl["items"] = [i for i in wl["items"] if i["id"] not in sys.argv[2:]]
        for c in wl["clusters"]:
            c["items"] = [i for i in c["items"] if i not in sys.argv[2:]]
        wl["clusters"] = [c for c in wl["clusters"] if c["items"]]
        p.write_text(json.dumps(wl))
        rc = B.resume_recovered(root, wl, {})
        print("resume_recovered rc=%s" % rc)
        sys.exit(0 if rc == 0 else 1)
''')

OC_SHIM = textwrap.dedent('''\
    #!/usr/bin/env python3
    """Inert, identity-recording stand-in for `oc` in this test: get/list only,
    answered from the revision that was pushed to the local bare remote."""
    import hashlib, json, subprocess, sys
    REMOTE, LOG, HOST, NAME = %r, %r, %r, %r
    args = sys.argv[1:]
    with open(LOG, "a") as fh:
        fh.write(json.dumps(args) + "\\n")
    if "get" not in args:
        sys.stderr.write("oc shim: refused %%r\\n" %% (args,)); sys.exit(3)
    head = subprocess.run(["git", "--git-dir", REMOTE, "rev-parse", "refs/heads/main"], capture_output=True, text=True).stdout.strip()
    digest = "sha256:" + hashlib.sha256(head.encode()).hexdigest() if head else ""
    kind = args[args.index("get") + 1]
    def out(o): print(json.dumps(o)); sys.exit(0)
    if kind == "pipelinerun":
        out({"items": [{"metadata": {"name": "app-push-1", "labels": {"tekton.dev/pipeline": "app-push"}},
                        "spec": {"params": [{"name": "revision", "value": head}]},
                        "status": {"conditions": [{"type": "Succeeded", "status": "True", "reason": "Succeeded"}]}}] if head else []})
    if kind == "taskrun":
        out({"items": [{"status": {"results": [{"name": "IMAGE_DIGEST", "value": digest}]}}]})
    if kind == "deployment":
        out({"spec": {"replicas": 1, "template": {"spec": {"containers": [{"name": NAME, "image": "registry.local/shop@" + digest}]}}},
             "status": {"readyReplicas": 1, "containerStatuses": [{"name": NAME, "ready": True, "imageID": "registry.local/shop@" + digest}]}})
    if kind == "pods":
        out({"items": []})
    if kind == "service":
        out({"metadata": {"name": NAME}})
    if kind == "endpoints":
        out({"subsets": [{"addresses": [{"ip": "10.0.0.7"}]}]})
    if kind == "route":
        out({"spec": {"host": HOST, "tls": {"termination": "edge"}}})
    sys.stderr.write("oc shim: unknown %%r\\n" %% (args,)); sys.exit(3)
''')


class _App(BaseHTTPRequestHandler):
    calls: list = []

    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        _App.calls.append(("GET", self.path))
        if self.path.startswith("/q/swagger-ui"):
            return self._send(200, b"<html>swagger</html>")
        if self.path.startswith("/q/openapi"):
            return self._send(200, b'{"openapi": "3.0.3", "paths": {"/api/items": {}}}')
        if self.path.startswith("/api/items"):
            return self._send(200, b'[]' if self.path == "/api/items" else b'{"id": 7}')
        return self._send(404)

    def do_POST(self):
        _App.calls.append(("POST", self.path))
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        return self._send(201, b'{"id": 7}', {"Location": "/api/items/7"})

    def do_DELETE(self):
        _App.calls.append(("DELETE", self.path))
        return self._send(204)


class _V6(HTTPServer):
    import socket
    address_family = socket.AF_INET6


def _https(tmp):
    cert, key = tmp / "cert.pem", tmp / "key.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=route.test", "-days", "1",
                    "-keyout", str(key), "-out", str(cert)], check=True, capture_output=True)
    srv = _V6(("::1", 0), _App)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(cert), str(key))
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "[::1]:%d" % srv.server_address[1]


def _tool(name, args):
    return ("tool", name, args)


def _term(cmd):
    return _tool("terminal", {"command": cmd})


GATE = "python3 .hermes/kernel/outcome_gate.py --root . "


class Script:
    """The scripted model: one sequence per (outcome, profile, run number)."""

    def __init__(self, dest, home, shim_dir):
        self.dest, self.home, self.shim = dest, home, shim_dir
        self.worklists = {}

    def _runs(self, tid):
        con = sqlite3.connect(str(self.home / "kanban.db"))
        try:
            return [r[0] for r in con.execute("SELECT profile FROM task_runs WHERE task_id=? ORDER BY id", (tid,))]
        finally:
            con.close()

    def _oid(self, tid):
        con = _ob.store(self.dest)
        try:
            row = con.execute("SELECT outcome_id FROM publication WHERE task_id=?", (tid,)).fetchone()
            return row[0] if row else ""
        finally:
            con.close()

    def seq(self, tid, oid, profile, nth):
        ex = "PATH=%s:$PATH KUBECONFIG=/nonexistent " % self.shim
        review = _tool("kanban_request_review", {"summary": "stage done", "reviewer": "reviewer"})
        audit = lambda steps: _term("python3 %s/scripts/assert-paved-road-audit.py --root . --steps %s/%s" % (M5, M5, steps))  # noqa: E731
        complete = _tool("kanban_complete", {"summary": "reviewed"})
        if oid in ("build:rk:pom", "config:rk:cfg"):
            path = {"build:rk:pom": "pom.xml", "config:rk:cfg": "src/main/resources/application.properties"}[oid]
            item = {"build:rk:pom": "inc:pom:quarkus-bom", "config:rk:cfg": "inc:cfg:server-port"}[oid]
            if nth == 1:
                return [_term(GATE + "issue"), _tool("write_file", {"path": str(self.dest / path), "content": "<fixed/>\n"}),
                        _term("python3 .derived/sim/advance_sim.py commit-and-die")]
            return [_term(GATE + "issue"), _term("python3 .derived/sim/advance_sim.py finish %s" % item),
                    _tool("kanban_complete", {"summary": "outcome accepted on the recovered commit"})]
        if oid.startswith("assess:"):
            if profile == "reviewer":
                return [complete]
            verdict = "REFUSE" if oid.endswith(":g1") else "PROVISIONAL_ACCEPT"
            return [_term(GATE + "issue"),
                    _tool("write_file", {"path": str(self.dest / "evidence/planning/worklist.json"), "content": self.worklists[oid]}),
                    _tool("write_file", {"path": str(self.dest / "evidence/verdicts/m4-verdict.json"), "content": json.dumps(
                        {"card_id": tid, "verdict": verdict, "parity_scenarios": ["items-list", "items-get-1", "items-get-missing", "orders-create"],
                         "qualifications": [{"id": "g1-kill-ratio", "class": "deferred", "satisfied": False}]})}),
                    _term(GATE + "assessment-record"), review]
        if oid == "deliver:prepare:c1":
            if profile == "reviewer":
                return [audit("steps-prepare.json"), complete]
            return [_term(GATE + "issue"), _term("python3 %s/scripts/prepare-release-candidate.py --root ." % M5), review]
        if oid == "deliver:push:c1":
            if profile == "reviewer":
                return [audit("steps-push.json"), complete]
            return [_term(GATE + "issue"), _term(GATE + "push --remote origin --ref refs/heads/main"),
                    _term(ex + "python3 %s/scripts/observe-app-push.py --root ." % M5),
                    _term(ex + "python3 %s/scripts/assert-deployed-app.py --root ." % M5), review]
        if oid == "deliver:accept:c1":
            if profile == "reviewer":
                return [audit("steps-accept.json"), complete]
            return [_term(GATE + "issue"), _term("python3 %s/scripts/live-acceptance.py --root ." % M5),
                    _term("python3 %s/scripts/compose-m5-verdict.py --root ." % M5),
                    _tool("skill_view", {"name": "check-release-readiness"}), review]
        return [_tool("kanban_block", {"reason": "unexpected card %s" % oid, "kind": "needs_input"})]

    def __call__(self, body):
        text = json.dumps(body["messages"])
        m = re.search(r"work kanban task (t_[0-9a-f]+)", text)
        tid = m.group(1) if m else ""
        n = sum(1 for msg in body["messages"] if msg.get("role") == "tool")
        runs = self._runs(tid)
        profile = runs[-1] if runs else "implementer"
        nth = sum(1 for p in runs if p == profile)
        seq = self.seq(tid, self._oid(tid), profile, nth)
        return seq[n] if n < len(seq) else ("text", "done")


def _seen(provider, tid):
    reqs = [r for r in H.agent_requests(provider) if ("work kanban task %s" % tid) in json.dumps(r["messages"])]
    return "\n".join(str(m.get("content")) for m in (reqs[-1]["messages"] if reqs else []) if m.get("role") == "tool")


def _spawn_reap(kb, conn, expect=None):
    res = kb.dispatch_once(conn, max_in_progress=1)
    assert len(res.spawned) == 1, res
    tid = res.spawned[0][0]
    if expect:
        assert tid == expect, (tid, expect)
    pid = kb.get_task(conn, tid).worker_pid
    status = H.wait_exit(pid)
    kb._record_worker_exit(pid, status)
    return tid


def _status(conn, tid):
    return conn.execute("SELECT status, assignee FROM tasks WHERE id=?", (tid,)).fetchone()


def _accept_in_process(dest, conn, kb, oid, classes, scenarios=()):
    """PREREQUISITE STATE ONLY (labelled): an outcome accepted on the real board by
    the lifecycle, with a real commit, in place of a worker."""
    from planner import outcome_lifecycle as L
    from planner.outcome_native import KanbanNative
    from planner.outcome_store import Store
    tid = _ob.task_of(dest, oid)
    kb.recompute_ready(conn)
    t = kb.claim_task(conn, tid)
    assert t is not None, (oid, _status(conn, tid))
    dead = subprocess.Popen(["true"])
    dead.wait()
    ctx = L.Ctx(dest, Store(dest), KanbanNative(_ob.meta(dest, "native_db")))
    iss = L.issue(ctx, task_id=tid, run_id=t.current_run_id, claim_lock=t.claim_lock, pid=dead.pid, pgid=0)
    for p in iss["allowed_paths"]:
        (dest / p).write_text("// accepted by %s\n" % oid)
    cand = ctx.product_tree()
    L.record_verdict(ctx, task_id=tid, run_id=t.current_run_id, verdict="ACCEPTED", candidate=cand, attempt="p")
    _ob.git(dest, "commit", "-qam", "accept %s" % oid, "--allow-empty")
    node = L._node(ctx.store.current_revision(), oid)
    wl = json.loads((dest / "evidence/planning/worklist.json").read_text())
    drop = set(node["obligations"]) | set(L._owned(ctx.store, oid))
    wl["items"] = [i for i in wl["items"] if i["id"] not in drop]
    for c in wl["clusters"]:
        c["items"] = [i for i in c["items"] if i not in drop]
    wl["clusters"] = [c for c in wl["clusters"] if c["items"]]
    (dest / "evidence/planning/worklist.json").write_text(json.dumps(wl))
    out = L.accept_commit(ctx, task_id=tid, run_id=t.current_run_id, attempt="p", commit=_ob.git(dest, "rev-parse", "HEAD"),
                          measurement={"classes": list(classes), "scenarios": list(scenarios)})
    assert out["outcome_accepted"], (oid, out)
    L.check_complete(ctx, task_id=tid, run_id=t.current_run_id, profile="implementer", audit_green=False)
    kb.complete_task(conn, tid, summary="accepted (prerequisite state)")


def test_accepted_repair_refuse_reassessment_and_m5_with_real_workers(tmp_path, monkeypatch):
    dest, plan = _ob.make_dest(tmp_path)
    home = dest / ".hermes" / "home"
    home.mkdir(parents=True)
    # delivery contract, inert remote, loop stand-in, oc shim, HTTPS route
    srv, host = _https(tmp_path)
    (dest / "delivery.yaml").write_text(textwrap.dedent('''\
        delivery:
          namespace: "shop-dev"
          repo: "shop"
          swagger_path: "/q/swagger-ui"
          openapi_path: "/q/openapi"
          reads:
            - id: "items"
              method: "GET"
              path: "/api/items"
          crud:
            create:
              method: "POST"
              path: "/api/items"
              body:
                name: "probe"
          auth:
            mode: "disabled"
        '''))
    (dest / ".derived" / "sim").mkdir(parents=True)
    (dest / ".derived" / "sim" / "advance_sim.py").write_text(ADVANCE_SIM)
    _ob.git(dest, "add", "-A")
    _ob.git(dest, "commit", "-qm", "delivery contract")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    _ob.git(dest, "remote", "add", "origin", str(remote))
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "oc").write_text(OC_SHIM % (str(remote), str(tmp_path / "oc-calls.jsonl"), host, "shop"))
    os.chmod(shim / "oc", 0o755)

    monkeypatch.setenv("HERMES_HOME", str(home))
    for k, v in _ob.env_for(dest).items():
        if k in ("HERMES_BIN", "K2_ALLOW_ROOT", "HERMES_WRITE_SAFE_ROOT", "PYTHONDONTWRITEBYTECODE"):
            monkeypatch.setenv(k, v)
    monkeypatch.setenv("PYTHONNOUSERSITE", "1")
    monkeypatch.setenv("KUBECONFIG", "/nonexistent")          # a stray real `oc` can reach nothing
    # M2/M4 roads need M1 evidence this fixture does not have: their audit exit is stood in
    monkeypatch.setenv("K2_PAVED_ROAD_AUDIT_EXIT", "0")
    script = Script(dest, home, shim)
    with FakeProvider(script) as provider:
        H.clean_env(monkeypatch, provider)
        cfg = _ob.hook_config(H.worker_config(dest), dest, tick=True)
        cfg["skills"] = dict(cfg["skills"], external_dirs=[str(dest / ".hermes" / "skills")])
        H.write_home(cfg, "implementer")
        H.write_home(cfg, "reviewer")
        from agent import shell_hooks
        shell_hooks.register_from_config(cfg, accept_hooks=True)
        from hermes_cli import kanban_db as kb
        kb.init_db()
        conn = kb.connect()
        m2 = kb.create_task(conn, title="M2 PLAN", body="plan", assignee="implementer", workspace_kind="dir",
                            workspace_path=str(dest), idempotency_key="m2-plan")
        # publication + release (qualified separately in the other two files)
        assert _ob.publish(dest, tmp_path, m2).returncode == 0
        chk = subprocess.run([sys.executable if False else "python3", "-c",
                              "import sys; sys.path[:0]=[%r,%r]; from planner.outcome_hook import terminator; import os,json;"
                              "print(json.dumps(terminator(%r, kind='complete', profile='reviewer', env=dict(os.environ), audit_green=lambda: True)))"
                              % (str(_ob.GOLDEN / "kernel"), str(_ob.GOLDEN / "lib"), str(dest))],
                             env=_ob.env_for(dest, HERMES_KANBAN_TASK=m2, HERMES_KANBAN_RUN_ID="0"), capture_output=True, text=True)
        assert json.loads(chk.stdout.strip().splitlines()[-1])["action"] == "allow", chk.stdout + chk.stderr
        kb.complete_task(conn, m2, summary="released")

        # ---- accepted repair with a worker killed right after its commit (R5) ------------
        t1 = _spawn_reap(kb, conn)
        oid1 = script._oid(t1)
        assert oid1 in ("build:rk:pom", "config:rk:cfg"), oid1
        assert _ob.meta(dest, "publication_state") == "released"      # the same tick reconciled the release
        commits_before = int(_ob.git(dest, "rev-list", "--count", "HEAD"))
        kb.detect_crashed_workers(conn)                                     # the dispatcher reaps the killed worker
        run1 = H.runs(conn, t1)[-1]
        assert run1["outcome"] == "crashed", run1
        con = _ob.store(dest)
        kinds1 = [r[0] for r in con.execute("SELECT kind FROM ledger WHERE outcome_id=? ORDER BY seq", (oid1,))]
        con.close()
        assert kinds1 == ["issue", "accept-begin"], kinds1                # committed, then killed before accept-commit
        kb.recompute_ready(conn)
        t1b = _spawn_reap(kb, conn, expect=t1)                              # the dispatcher respawns THE SAME card
        assert _status(conn, t1)[0] == "done", (_status(conn, t1), _seen(provider, t1)[-3000:])
        con = _ob.store(dest)
        kinds1 = [r[0] for r in con.execute("SELECT kind FROM ledger WHERE outcome_id=? ORDER BY seq", (oid1,))]
        rec = json.loads(con.execute("SELECT doc FROM ledger WHERE outcome_id=? AND kind='accept-commit'", (oid1,)).fetchone()[0])
        spent = con.execute("SELECT COUNT(*) FROM ledger WHERE kind='reject'").fetchone()[0]
        status1 = con.execute("SELECT status FROM outcomes WHERE outcome_id=?", (oid1,)).fetchone()[0]
        con.close()
        assert kinds1 == ["issue", "accept-begin", "accept-commit", "issue", "accept-evaluated"], kinds1  # recovered BEFORE the new issue
        assert rec["recovered"] is True and status1 == "accepted" and spent == 0
        assert int(_ob.git(dest, "rev-list", "--count", "HEAD")) == commits_before  # nothing committed twice
        assert t1b == t1

        # ---- the remaining repairs: prerequisite state, in-process (labelled) -----------
        from planner.outcome_graph import topo_order
        for n in topo_order(plan["nodes"]):
            if n["role"] != "repair" or n["outcome_id"] == oid1:
                continue
            cls = ("build", "compile", "tests") + {"runtime": ("runtime",), "behavior": ("runtime", "parity")}.get(n["class"], ())
            _accept_in_process(dest, conn, kb, n["outcome_id"], cls, n.get("scenarios") or ())
        kb.recompute_ready(conn)

        # ---- M4 REFUSE by a real worker, completed by a real reviewer ------------------------
        wl = json.loads((dest / "evidence/planning/worklist.json").read_text())
        wl["items"] = [i for i in wl["items"] if i["id"] != "inc:unlocatable:jndi"] + [PARITY_ITEM]
        wl["clusters"] = wl["clusters"] + [PARITY_CLUSTER]
        script.worklists["assess:m4:g1"] = json.dumps(wl)
        g1 = _ob.task_of(dest, "assess:m4:g1")
        _spawn_reap(kb, conn, expect=g1)
        assert _status(conn, g1)[0] == "review", _seen(provider, g1)[-3000:]
        _spawn_reap(kb, conn, expect=g1)                                    # the reviewer
        assert _status(conn, g1)[0] == "done", _seen(provider, g1)[-3000:]
        kb.dispatch_once(conn, max_in_progress=0, dry_run=True)             # a tick: the continuation publishes the repair
        con = _ob.store(dest)
        intent, isteps = con.execute("SELECT state, steps FROM intents WHERE intent_id='m4-assessed:assess:m4:g1'").fetchone()
        con.close()
        assert intent == "done", (intent, isteps)
        follow = "followup:behavior:http:com.acme.shop.web.ItemController:g2"
        assert _status(conn, _ob.task_of(dest, follow))[1] == "implementer"
        assert _status(conn, _ob.task_of(dest, "deliver:prepare:c1"))[1] is None        # M5 held on a REFUSE
        _accept_in_process(dest, conn, kb, follow, ("build", "compile", "tests", "runtime", "parity"), ("items-list",))
        kb.recompute_ready(conn)
        wl = json.loads((dest / "evidence/planning/worklist.json").read_text())
        script.worklists["assess:m4:g2"] = json.dumps(wl)
        g2 = _ob.task_of(dest, "assess:m4:g2")
        _spawn_reap(kb, conn, expect=g2)
        _spawn_reap(kb, conn, expect=g2)
        assert _status(conn, g2)[0] == "done", _seen(provider, g2)[-3000:]

        # ---- M5: real producers, real reviewer audits (the stand-in audit exit is removed) --
        monkeypatch.delenv("K2_PAVED_ROAD_AUDIT_EXIT")
        prep = _ob.task_of(dest, "deliver:prepare:c1")
        kb.dispatch_once(conn, max_in_progress=0, dry_run=True)             # tick: grant PREFLIGHT
        assert _status(conn, prep)[1] == "implementer", "PREFLIGHT not granted"
        for stage in ("prepare", "push", "accept"):
            tid = _ob.task_of(dest, "deliver:%s:c1" % stage)
            _spawn_reap(kb, conn, expect=tid)
            impl_seen = _seen(provider, tid)
            if os.environ.get("RHOAI3_OB_EVIDENCE"):
                os.makedirs(os.environ["RHOAI3_OB_EVIDENCE"], exist_ok=True)
                Path(os.environ["RHOAI3_OB_EVIDENCE"], "seen-%s.txt" % stage).write_text(impl_seen)
            assert _status(conn, tid)[0] == "review", (stage, impl_seen[-4000:])
            _spawn_reap(kb, conn, expect=tid)
            assert _status(conn, tid)[0] == "done", (stage, impl_seen[-6000:], _seen(provider, tid)[-3000:])
            kb.dispatch_once(conn, max_in_progress=0, dry_run=True)         # tick: the next stage's grant
        # ---- what the authority recorded, from the stages' own receipts -------------------
        con = _ob.store(dest)
        results = {r[0]: json.loads(r[1]) for r in con.execute("SELECT outcome_id, doc FROM ledger WHERE kind='stage-result'")}
        effects = [dict(r) for r in con.execute("SELECT kind, candidate, state, operation_id FROM effects")]
        con.close()
        head = _ob.git(dest, "rev-parse", "HEAD")
        assert set(results) == {"deliver:prepare:c1", "deliver:push:c1", "deliver:accept:c1"}
        assert all(r["candidate_sha"] == head for r in results.values())
        assert results["deliver:push:c1"]["image_digest"] == "sha256:" + hashlib.sha256(head.encode()).hexdigest()
        assert results["deliver:accept:c1"]["verdict"] == "INCONCLUSIVE" and results["deliver:accept:c1"]["ship"] is False
        assert effects == [{"kind": "push", "candidate": head, "state": "landed", "operation_id": "origin:refs/heads/main@%s" % head}]
        assert subprocess.run(["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"], capture_output=True,
                              text=True).stdout.strip() == head
        calls = [json.loads(line) for line in (tmp_path / "oc-calls.jsonl").read_text().splitlines()]
        assert calls and all("get" in c for c in calls)                    # the shim saw only reads
        assert ("POST", "/api/items") in _App.calls and ("DELETE", "/api/items/7") in _App.calls
        out = os.environ.get("RHOAI3_OB_EVIDENCE")
        if out:
            os.makedirs(out, exist_ok=True)
            for name, t in (("build-or-config", t1), ("m4-g1", g1), ("m4-g2", g2), ("m5-prepare", prep),
                            ("m5-push", _ob.task_of(dest, "deliver:push:c1")), ("m5-accept", _ob.task_of(dest, "deliver:accept:c1"))):
                p = home / "kanban" / "logs" / ("%s.log" % t)
                if p.is_file():
                    Path(out, "delivery-%s.log" % name).write_text(p.read_text(errors="replace"))
            Path(out, "delivery-summary.json").write_text(json.dumps(
                {"head": head, "stage_results": results, "effects": effects, "oc_calls": calls,
                 "recovered_accept": rec, "ledger_first_outcome": kinds1}, indent=2))
        srv.shutdown()
        conn.close()
