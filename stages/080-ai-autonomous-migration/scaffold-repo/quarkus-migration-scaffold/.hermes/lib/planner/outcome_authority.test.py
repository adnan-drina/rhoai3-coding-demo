#!/usr/bin/env python3
"""Protocol selection (one source of truth) and the protected authority service (F1).

SELECTION. A governed run's protocol is its REQUEST (board_protocol in the
initial commit's run-budget.json) agreed by the platform's read-only contract.
Every row of the rule is exercised on a real git history and a real control
directory: legacy runs (no request) stay serial, a disagreement refuses with
its typed code and never routes to the serial loop, the request cannot be
rewritten in the working tree, and the golden defaults cannot select behind it.

SERVICE. The authority runs as a SEPARATE PROCESS (kernel/outcome_authority.py
serve) owning its store outside the destination tree; the worker side reaches it
only through the public entry points (k4_graph.py, outcome_gate.py, the K2
hook branch, outcome_reconcile.py). The native board is a SQLite file mutated by
a SYNTHETIC CLI (fixtures/fake_hermes_kanban.py) in the service's process.
This test runs both principals under ONE uid, so it proves the protocol and the
validation (decisions re-derived by the service; worker values replaced), not the
kernel boundary: authority_protected() is FALSE here by design, and the two-uid
kernel check is the separate container qualification.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/outcome_authority.test.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE.parent
HERMES = LIB.parent
KERNEL = HERMES / "kernel"
for p in (LIB, KERNEL):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import k4_graph as G  # noqa: E402
import outcome_gate  # noqa: E402
import outcome_reconcile as R  # noqa: E402
from planner import outcome_authority as A  # noqa: E402
from planner import outcome_graph as OG  # noqa: E402
from planner import outcome_hook as HK  # noqa: E402
from planner import outcome_lifecycle as L  # noqa: E402
from planner import outcome_protocol as P  # noqa: E402
from planner import run_control  # noqa: E402

FIX = HERE / "fixtures"
SHOP = json.loads((FIX / "outcome-initial-shop.json").read_text())
FAKE_CLI = FIX / "fake_hermes_kanban.py"
PY = sys.executable


def git(root, *a):
    return subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", *a],
                          capture_output=True, text=True, check=True).stdout.strip()


# ===========================================================================
# selection
# ===========================================================================

def governed(td: Path, *, request=None, has_request=True, contract_protocol=None, execution=None,
             trust=None, defaults_protocol=None, contract=True) -> Path:
    """A destination whose INITIAL commit declares run control, and the
    platform's control directory beside it."""
    root, control, state = td / "dest", td / "control", td / "state"
    for d in (root, control):
        d.mkdir(parents=True)
    decl = {"schema": "rhoai3.run-budget/v2", "run_id": "run-x",
            "run_control": {"contract": run_control.CONTRACT_SCHEMA, "root": str(control), "state": str(state)}}
    if has_request:
        decl["board_protocol"] = request
    (root / "run-budget.json").write_text(json.dumps(decl))
    conf = {"board_protocol": defaults_protocol} if defaults_protocol else {}
    (root / "run-defaults.json").write_text(json.dumps({"schema": "rhoai3.run-defaults/v1", "configuration": conf}))
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "scaffold")
    if contract:
        doc = {"schema": run_control.CONTRACT_SCHEMA, "run_id": "run-x", "scaffold_commit": git(root, "rev-parse", "HEAD"),
               "activation": "pilot", "authorized_by": "provision-migration-run:tr-1"}
        if contract_protocol is not None:
            doc["board_protocol"] = contract_protocol
        board = {}
        if execution is not None:
            board["execution"] = execution
        if trust is not None:
            board["measurement_trust"] = trust
        if board:
            doc["outcome_board"] = board
        (control / "contract.json").write_text(json.dumps(doc))
    return root


class Selection(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ob-sel-")).resolve()
        self.n = 0

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def root(self, **kw) -> Path:
        self.n += 1
        return governed(self.tmp / ("c%d" % self.n), **kw)

    def sel(self, **kw):
        return P.select_protocol(self.root(**kw))

    def test_legacy_runs_without_a_request_stay_serial(self):
        # v12-v17: no request field, a contract without board_protocol
        s = self.sel(has_request=False)
        self.assertEqual((s.protocol, s.execution, s.errors), (P.SERIAL, P.DISABLED, []))
        self.assertTrue(s.governed)
        r = self.root(has_request=False)
        self.assertEqual(P.launch_gaps(r)[1], [])

    def test_serial_request_is_serial_with_or_without_a_contract_selection(self):
        for cp in (None, P.SERIAL):
            s = self.sel(request=P.SERIAL, contract_protocol=cp)
            self.assertEqual((s.protocol, s.errors), (P.SERIAL, []), cp)

    def test_outcome_request_with_outcome_selection(self):
        r = self.root(request=P.OUTCOME, contract_protocol=P.OUTCOME)
        s = P.select_protocol(r)
        self.assertEqual((s.protocol, s.execution, s.errors, s.requested, s.selected),
                         (P.OUTCOME, P.DISABLED, [], P.OUTCOME, P.OUTCOME))
        # disabled by default: a launch refuses; it never launches the serial loop instead
        self.assertEqual(P.launch_gaps(r)[1][0][0], "OUTCOME_EXECUTION_DISABLED")
        # qualification is never honoured on a governed run
        s = self.sel(request=P.OUTCOME, contract_protocol=P.OUTCOME, execution="qualification")
        self.assertEqual(P.execution_gate(self.root(request=P.OUTCOME, contract_protocol=P.OUTCOME,
                                                    execution="qualification"))[0][0], "OUTCOME_QUALIFICATION_REFUSED")

    def test_enabled_needs_the_protected_service_and_a_trust_decision(self):
        r = self.root(request=P.OUTCOME, contract_protocol=P.OUTCOME, execution="enabled")
        code, why = P.execution_gate(r)[0]
        self.assertEqual(code, "AUTHORITY_UNPROTECTED")
        self.assertIn("no authority service answers", why)
        # the trust decision alone does not open the gate either
        r = self.root(request=P.OUTCOME, contract_protocol=P.OUTCOME, execution="enabled", trust="cooperative-receipts")
        self.assertEqual(P.execution_gate(r)[0][0], "AUTHORITY_UNPROTECTED")

    def test_disagreements_refuse_and_route_away_from_the_serial_loop(self):
        cases = (
            (dict(request=P.OUTCOME), "PROTOCOL_UNBOUND"),                                  # v17's live shape
            (dict(request=P.OUTCOME, contract_protocol=P.SERIAL), "PROTOCOL_DOWNGRADED"),
            (dict(has_request=False, contract_protocol=P.OUTCOME), "PROTOCOL_UNREQUESTED"),
            (dict(request=P.SERIAL, contract_protocol=P.OUTCOME), "PROTOCOL_UNREQUESTED"),
            (dict(request=P.SERIAL, execution="enabled"), "PROTOCOL_UNREQUESTED"),
            (dict(request="board/v9", contract_protocol=P.OUTCOME), "PROTOCOL_UNKNOWN"),
            (dict(request=None, contract_protocol=P.OUTCOME), "PROTOCOL_UNKNOWN"),          # a null request is not serial
            (dict(request=P.OUTCOME, contract=False), "PROTOCOL_UNBOUND"),                  # no platform record at all
            (dict(request=P.SERIAL, defaults_protocol=P.OUTCOME), "PROTOCOL_UNREQUESTED"),   # golden defaults cannot select
        )
        for kw, code in cases:
            r = self.root(**kw)
            s = P.select_protocol(r)
            self.assertEqual(s.errors[0][0], code, kw)
            self.assertTrue(s.outcome, "%s must never route to the serial loop: %s" % (code, kw))
            self.assertEqual(P.launch_gaps(r)[1][0][0], code, kw)
            self.assertEqual(P.execution_gate(r)[0][0], code, kw)
            # K2 fails closed on every terminator and write
            for kind in ("complete", "block", "request_review"):
                d = HK.terminator(str(r), kind=kind, profile="implementer", env={}, audit_green=lambda: True)
                self.assertEqual((d or {}).get("code"), code, (kw, kind))
            self.assertEqual((HK.writes(str(r), rel_paths=["pom.xml"], env={}) or {}).get("code"), code, kw)
            # K4: the serial mint is never reached (routes to the graph, which refuses)
            import k4_mint
            with contextlib.redirect_stderr(io.StringIO()) as err, contextlib.redirect_stdout(io.StringIO()):
                rc = k4_mint.main(["--root", str(r), "--exec"])
            self.assertEqual(rc, 1, kw)
            self.assertIn(code, err.getvalue(), kw)

    def test_the_request_is_read_from_the_initial_commit_only(self):
        r = self.root(request=P.OUTCOME, contract_protocol=P.OUTCOME)
        # rewriting (or committing) a serial request later changes nothing
        decl = json.loads((r / "run-budget.json").read_text())
        decl["board_protocol"] = P.SERIAL
        (r / "run-budget.json").write_text(json.dumps(decl))
        git(r, "commit", "-qam", "downgrade attempt")
        s = P.select_protocol(r)
        self.assertEqual((s.protocol, s.requested, s.errors), (P.OUTCOME, P.OUTCOME, []))
        # a legacy run cannot acquire a request later either
        r = self.root(has_request=False)
        decl = json.loads((r / "run-budget.json").read_text())
        decl["board_protocol"] = P.OUTCOME
        (r / "run-budget.json").write_text(json.dumps(decl))
        git(r, "commit", "-qam", "upgrade attempt")
        self.assertEqual((P.select_protocol(r).protocol, P.select_protocol(r).errors), (P.SERIAL, []))

    def test_launch_check_cli(self):
        r = self.root(request=P.OUTCOME)
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            rc = P.main(["--root", str(r)])
        self.assertEqual(rc, 1)
        self.assertEqual(json.loads(out.getvalue())["launch_gaps"][0][0], "PROTOCOL_UNBOUND")
        r = self.root(has_request=False)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(P.main(["--root", str(r)]), 0)
        self.assertEqual(json.loads(out.getvalue())["protocol"], P.SERIAL)

    def test_local_fixtures_keep_their_selection(self):
        # a non-governed qualification fixture still selects through run-defaults + pins
        r = self.tmp / "local"
        (r / ".hermes").mkdir(parents=True)
        (r / "run-defaults.json").write_text(json.dumps({"configuration": {"board_protocol": P.OUTCOME}}))
        (r / ".hermes/pins.json").write_text(json.dumps({"pins": {"planner": {"outcome_board": {"execution": "qualification"}}}}))
        s = P.select_protocol(r)
        self.assertEqual((s.protocol, s.execution, s.governed, s.errors), (P.OUTCOME, P.QUALIFICATION, False, []))
        self.assertEqual(P.authority_endpoint(s), "")


# ===========================================================================
# protection facts (the decision behind authority_protected)
# ===========================================================================

class Protection(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ob-prot-")).resolve()
        self.root = self.tmp / "dest"
        self.root.mkdir()
        self.hello = {"schema": P.AUTHORITY_SCHEMA, "root": str(self.root), "uid": 4242,
                      "store_dir": "/nonexistent/outcome-authority", "store_path": "/nonexistent/outcome-authority/authority.sqlite3",
                      "code_sha256": "c" * 64}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def facts(self, **kw):
        h = dict(self.hello, **kw.pop("hello", {}))
        return P.protection_facts(h, self.root, uid=kw.pop("uid", 1000), stamp=kw.pop("stamp", "c" * 64),
                                  pinned=kw.pop("pinned", ""))

    def test_all_conditions_hold(self):
        ok, why = self.facts()
        self.assertTrue(ok, why)

    def test_each_condition_refuses(self):
        reach = self.tmp / "reachable"
        reach.mkdir()
        cases = (
            (dict(hello={"schema": "other"}), "not rhoai3"),
            (dict(hello={"root": "/elsewhere"}), "serves"),
            (dict(uid=4242), "calling uid"),
            (dict(hello={"store_dir": str(reach)}), "reachable"),
            (dict(hello={"store_path": "relative/path"}), "no absolute store path"),
            (dict(stamp=""), "names no"),
            (dict(stamp="d" * 64), "not the image-pinned"),
            (dict(pinned="e" * 64), "harness pins"),
        )
        for kw, text in cases:
            ok, why = self.facts(**kw)
            self.assertFalse(ok, kw)
            self.assertIn(text, why, kw)
        # a cooperative store planted in the tree shadows the service
        (self.root / P.STORE_DIR).mkdir(parents=True)
        (self.root / P.STORE_FILE).write_bytes(b"")
        ok, why = self.facts()
        self.assertFalse(ok)
        self.assertIn("shadows", why)

    def test_an_unreadable_path_is_unreachable(self):
        locked = self.tmp / "locked"
        (locked / "store").mkdir(parents=True)
        os.chmod(locked, 0)
        try:
            if os.getuid() == 0:
                self.skipTest("root reads through mode 000")
            ok, why = self.facts(hello={"store_dir": str(locked / "store"), "store_path": str(locked / "store" / "a.sqlite3")})
            self.assertTrue(ok, why)
        finally:
            os.chmod(locked, 0o700)

    def test_code_identity_is_the_code_set(self):
        a = A.code_identity(HERMES)
        self.assertEqual(a, A.code_identity(HERMES))
        rels = {p.relative_to(HERMES).as_posix() for p in A.code_files(HERMES)}
        for want in ("kernel/outcome_authority.py", "lib/planner/outcome_lifecycle.py", "kernel/k4_schema.py",
                     "skills/migration/fix-until-green/scripts/jdk-dest-model/DestModel.java"):
            self.assertIn(want, rels)
        self.assertFalse(any("__pycache__" in r or r.startswith("home/") for r in rels))


# ===========================================================================
# the service, as a separate process
# ===========================================================================

class Board:
    """The test's hand on the native board (dispatcher stand-in): claim,
    complete, archive -- in the SQLite file the service's CLI mutates."""

    def __init__(self, db: Path):
        self.db = str(db)
        sys.path.insert(0, str(FIX))
        import fake_hermes_kanban as F
        F.connect(self.db).close()

    def con(self):
        c = sqlite3.connect(self.db, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        return c

    def create(self, tid, title, assignee="implementer"):
        with contextlib.closing(self.con()) as c:
            c.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (tid, title, "body", assignee, "ready", "m2-plan", "[]", "", 1, None, None, None, 0))

    def claim(self, tid, pid):
        with contextlib.closing(self.con()) as c:
            cur = c.execute("INSERT INTO task_runs(task_id, status, claim_lock) VALUES (?,?,?)", (tid, "running", "x"))
            run = cur.lastrowid
            lock = "lock-%d" % run
            c.execute("UPDATE task_runs SET claim_lock=? WHERE id=?", (lock, run))
            c.execute("UPDATE tasks SET status='running', current_run_id=?, claim_lock=?, worker_pid=? WHERE id=?",
                      (run, lock, pid, tid))
        return run, lock

    def set(self, tid, **fields):
        with contextlib.closing(self.con()) as c:
            for k, v in fields.items():
                c.execute("UPDATE tasks SET %s=? WHERE id=?" % k, (v, tid))

    def end(self, tid, status="ready"):
        self.set(tid, status=status, current_run_id=None, claim_lock=None, worker_pid=None)
        with contextlib.closing(self.con()) as c:
            for child, in c.execute("SELECT child_id FROM task_links WHERE parent_id=?", (tid,)).fetchall():
                parents = [r[0] for r in c.execute("SELECT t.status FROM task_links l JOIN tasks t ON t.id=l.parent_id "
                                                   "WHERE l.child_id=?", (child,))]
                if all(s in ("done", "archived") for s in parents):
                    c.execute("UPDATE tasks SET status='ready' WHERE id=? AND status='todo'", (child,))

    def task(self, tid):
        with contextlib.closing(self.con()) as c:
            row = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
            return dict(row) if row else None

    def by_key(self, key):
        with contextlib.closing(self.con()) as c:
            return [r[0] for r in c.execute("SELECT id FROM tasks WHERE idempotency_key=?", (key,))]

    def comments(self, tid):
        with contextlib.closing(self.con()) as c:
            return [r[0] for r in c.execute("SELECT body FROM task_comments WHERE task_id=? ORDER BY id", (tid,))]


class ServiceRun:
    """A qualification destination whose authority is a SEPARATE service
    process (pins name a local socket), with a published shop graph."""

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ob-svc-")).resolve()
        self.root = self.tmp / "dest"
        self.home = self.root / ".hermes" / "home"
        self.home.mkdir(parents=True)
        self.sock = self.tmp / "run" / "authority.sock"
        self.store_dir = self.tmp / "svc-store"
        (self.root / "run-defaults.json").write_text(json.dumps({"schema": "rhoai3.run-defaults/v1", "budget": {},
                                                                 "configuration": {"board_protocol": P.OUTCOME}}))
        (self.root / ".hermes" / "pins.json").write_text(json.dumps({"pins": {"planner": {"outcome_board": {
            "execution": "qualification", "authority_socket": str(self.sock)}}}}))
        for name in ("lib", "kernel", "planning", "skills"):
            os.symlink(HERMES / name, self.root / ".hermes" / name)
        for c in SHOP["worklist"]["clusters"]:
            for p in c["write_set"]:
                f = self.root / p
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text("// %s v0\n" % p)
        self.worklist = copy.deepcopy(SHOP["worklist"])
        self.save_worklist()
        shutil.copy(HERMES.parent / "decisions.yaml", self.root / "decisions.yaml")
        (self.root / ".gitignore").write_text("verification/\nevidence/\n.hermes/home/\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "baseline")
        self.db = self.home / "kanban.db"
        self.board = Board(self.db)
        self.board.create("t_m2000001", "M2 PLAN")
        self.m2_run, self.m2_lock = self.board.claim("t_m2000001", os.getpid())
        self.m2 = "t_m2000001"
        self.plan = OG.derive_initial_graph(run_id="r1", worklist=SHOP["worklist"], entry_points=SHOP["entry_points"],
                                            oracles=SHOP["oracles"], references=SHOP["references"], provenance=SHOP["provenance"])
        self.plan_file = self.tmp / "plan.json"
        self.plan_file.write_text(json.dumps(self.plan))
        self.log = open(self.tmp / "service.log", "w")
        env = {k: v for k, v in os.environ.items() if not k.startswith("HERMES_")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["OB_IN_SERVICE"] = "1"      # lets a probe tell the service's subprocesses from the worker's
        self.proc = subprocess.Popen([PY, str(KERNEL / "outcome_authority.py"), "serve", "--root", str(self.root),
                                      "--store-dir", str(self.store_dir), "--socket", str(self.sock),
                                      "--native-db", str(self.db), "--hermes", "%s %s" % (PY, FAKE_CLI)],
                                     stdout=self.log, stderr=subprocess.STDOUT, env=env)
        for _ in range(200):
            if self.sock.exists():
                try:
                    A.hello(str(self.sock))
                    break
                except A.AuthorityError:
                    pass
            time.sleep(0.05)
        else:
            raise RuntimeError("service did not start: %s" % (self.tmp / "service.log").read_text())

    def close(self):
        self.proc.terminate()
        self.proc.wait(10)
        self.log.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def save_worklist(self):
        p = self.root / L.WORKLIST
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.worklist))

    def drop(self, *ids):
        self.worklist["items"] = [i for i in self.worklist["items"] if i["id"] not in ids]
        for c in self.worklist["clusters"]:
            c["items"] = [i for i in c["items"] if i not in ids]
        self.worklist["clusters"] = [c for c in self.worklist["clusters"] if c["items"]]
        self.save_worklist()

    @contextlib.contextmanager
    def worker(self, task, run=None, lock=None):
        """The environment the dispatcher gives a worker of ``task``."""
        t = self.board.task(task) or {}
        env = {"HERMES_KANBAN_TASK": task, "HERMES_KANBAN_RUN_ID": str(run or t.get("current_run_id") or 0),
               "HERMES_KANBAN_CLAIM_LOCK": lock or t.get("claim_lock") or "", "HERMES_KANBAN_DB": str(self.db)}
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            yield env
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def gate(self, *args, task=None, run=None, lock=None):
        with self.worker(task or self.m2, run, lock):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = outcome_gate.main(["--root", str(self.root), *args])
        return rc, json.loads(out.getvalue() or "{}")

    def call(self, name, **kw):
        return A.call(str(self.sock), "transition", {"name": name, "kwargs": kw})

    def status(self):
        return A.call(str(self.sock), "status", {})

    def tid(self, oid):
        key = G.native_key("r1", next(n for n in self.plan["nodes"] if n["outcome_id"] == oid))
        return self.board.by_key(key)[0]

    def publish(self):
        with self.worker(self.m2), contextlib.redirect_stderr(io.StringIO()) as err, contextlib.redirect_stdout(io.StringIO()):
            rc = G.main(["--root", str(self.root), "publish", "--plan-file", str(self.plan_file)])
        return rc, err.getvalue()

    def release(self):
        with self.worker(self.m2) as env:
            d = HK.terminator(str(self.root), kind="complete", profile="reviewer", env=env, audit_green=lambda: True)
        assert d["action"] == "allow", d
        self.board.end(self.m2, "done")
        self.tick()
        return d

    def tick(self):
        """The dispatcher's on_kanban_dispatch_tick hook: the observer reads (and
        ignores) its payload on stdin, then asks the service to reconcile."""
        stdin = sys.stdin
        sys.stdin = io.StringIO("{}")
        try:
            with contextlib.redirect_stderr(io.StringIO()) as err:
                R.main(["--root", str(self.root)])
        finally:
            sys.stdin = stdin
        return err.getvalue()


def _svc_env_clean() -> None:
    for k in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID", "HERMES_KANBAN_CLAIM_LOCK"):
        os.environ.pop(k, None)


class Service(unittest.TestCase):
    def setUp(self):
        _svc_env_clean()
        self.r = ServiceRun()
        rc, err = self.r.publish()
        self.assertEqual(rc, 0, err + (self.r.tmp / "service.log").read_text())

    def tearDown(self):
        self.r.close()

    def issue(self, oid):
        tid = self.r.tid(oid)
        self.r.board.set(tid, assignee="implementer")
        run, lock = self.r.board.claim(tid, os.getpid())
        rc, out = self.r.gate("issue", task=tid, run=run, lock=lock)
        self.assertEqual(rc, 0, out)
        return tid, run, lock, out

    # -- the store lives in the service, never in the tree ---------------------
    def test_publication_lives_in_the_service(self):
        r = self.r
        self.assertFalse((r.root / P.STORE_FILE).exists())
        self.assertFalse((r.root / P.STORE_DIR / "briefs").exists())       # briefs are the service's own files
        self.assertTrue((r.store_dir / "authority.sqlite3").is_file())
        st = r.status()
        self.assertEqual((st["published"], st["publication_state"], st["revision"]), (True, "complete", 1))
        self.assertTrue(P.store_present(r.root))
        # the pinned CLI ran with the service's PRIVATE Hermes home, never the worker's
        envs = [json.loads(l) for l in Path(str(r.db) + ".cli-env.jsonl").read_text().splitlines()]
        self.assertTrue(envs)
        self.assertTrue(all(e["HERMES_HOME"] == str(r.store_dir / "hermes-home") for e in envs), envs[:1])
        self.assertTrue(all(e["HERMES_KANBAN_DB"] == str(r.db) for e in envs))
        # every node is on the board with its brief attached where the worker reads it
        for n in r.plan["nodes"]:
            self.assertEqual(len(r.board.by_key(G.native_key("r1", n))), 1, n["outcome_id"])
        with contextlib.closing(r.board.con()) as c:
            paths = [row[0] for row in c.execute("SELECT stored_path FROM task_attachments")]
        self.assertTrue(paths and all(p.startswith(str(r.home / "kanban" / "attachments")) for p in paths))
        # a second publication is idempotent: no duplicate card
        self.assertEqual(r.publish()[0], 0)
        for n in r.plan["nodes"]:
            self.assertEqual(len(r.board.by_key(G.native_key("r1", n))), 1)

    def test_valid_path_reject_then_accept_on_one_card(self):
        r = self.r
        r.release()
        self.assertEqual(r.status()["publication_state"], "released")
        tid, run, lock, iss = self.issue("build:rk:pom")
        self.assertEqual(iss["allowed_paths"], ["pom.xml"])
        self.assertTrue((r.root / "verification/loop/issued.json").is_file())   # the projection, written by the caller
        # K2 through the service: in scope allowed, out of scope refused
        with r.worker(tid, run, lock) as env:
            self.assertEqual(HK.writes(str(r.root), rel_paths=["pom.xml"], env=env)["code"], "WRITE_IN_ISSUE")
            self.assertEqual(HK.writes(str(r.root), rel_paths=["src/main/resources/application.properties"], env=env)["code"],
                             "WRITE_OUTSIDE_ISSUE")
        # attempt 1 rejected: the SAME card stays open, spend 1
        (r.root / "pom.xml").write_text("<project>bad</project>\n")
        rc, out = r.gate("verdict", "--verdict", "REVERTED", "--attempt", "a1", "--reason", "measure rose", task=tid)
        self.assertEqual((rc, out["spent"]), (0, 1), out)
        git(r.root, "checkout", "--", "pom.xml")
        # attempt 2 accepted
        (r.root / "pom.xml").write_text("<project>quarkus</project>\n")
        rc, out = r.gate("verdict", "--verdict", "ACCEPTED", "--attempt", "a2", task=tid)
        self.assertEqual(rc, 0, out)
        git(r.root, "commit", "-qam", "accept pom")
        r.drop("inc:pom:quarkus-bom")
        rc, out = r.gate("accept-commit", "--attempt", "a2", "--commit", git(r.root, "rev-parse", "HEAD"),
                         "--classes", "build", task=tid)
        self.assertEqual((rc, out.get("outcome_accepted")), (0, True), out)
        with r.worker(tid, run, lock) as env:
            d = HK.terminator(str(r.root), kind="complete", profile="implementer", env=env, audit_green=lambda: True)
        self.assertEqual(d["code"], "COMPLETE_ALLOWED", d)
        rc, acc = r.gate("account", task=tid)
        self.assertEqual((acc["accepted_historically"], acc["unfinished"]), (1, 7), acc)
        self.assertTrue((r.root / L.ACCOUNT).is_file())                            # observer view, written by the caller
        # the measurement is recorded with who stands behind its heavy classes
        m = [row for row in self._ledger() if row["kind"] == "measurement"]
        self.assertEqual(m[-1]["doc"]["classes_asserted_by"], "worker-receipts")

    def _ledger(self):
        con = sqlite3.connect(str(self.r.store_dir / "authority.sqlite3"))
        try:
            return [{"kind": k, "doc": json.loads(d), "budget_key": b} for k, d, b in
                    con.execute("SELECT kind, doc, budget_key FROM ledger ORDER BY seq")]
        finally:
            con.close()

    # -- the worker's values are replaced by the service's measurements ---------
    def test_forged_candidates_and_replayed_attempt_keys_do_not_save_budget(self):
        r = self.r
        r.release()
        tid, run, lock, _ = self.issue("build:rk:pom")
        spent = []
        for body in ("<a/>", "<b/>"):
            (r.root / "pom.xml").write_text(body)
            # the worker names the SAME attempt and a forged candidate each time
            out = r.call("record_verdict", task_id=tid, run_id=run, verdict="REVERTED", candidate="0" * 64,
                         attempt="same", reason="x")
            spent.append(out["spent"])
        self.assertEqual(spent, [1, 2])
        rejects = [row for row in self._ledger() if row["kind"] == "reject"]
        self.assertTrue(all(row["doc"]["candidate"] != "0" * 64 for row in rejects))

    def test_scope_and_ancestry_are_measured_by_the_service(self):
        r = self.r
        r.release()
        tid, run, lock, _ = self.issue("build:rk:pom")
        # an edit outside the issue (the worker bypassed its own hook) cannot be accepted
        (r.root / "pom.xml").write_text("<project/>\n")
        (r.root / "src/main/resources/application.properties").write_text("x=1\n")
        rc, out = r.gate("verdict", "--verdict", "ACCEPTED", "--attempt", "a", task=tid)
        self.assertEqual((rc, out.get("refused")), (1, "ACCEPT_OUT_OF_SCOPE"), out)
        git(r.root, "checkout", "--", "src/main/resources/application.properties")
        rc, out = r.gate("verdict", "--verdict", "ACCEPTED", "--attempt", "a", task=tid)
        self.assertEqual(rc, 0, out)
        # a commit that is not a child of the issued baseline is not the acceptance
        git(r.root, "commit", "-qam", "one")
        (r.root / "README.side").write_text("x\n")
        git(r.root, "add", "README.side")
        git(r.root, "commit", "-qm", "two")
        git(r.root, "rm", "-q", "README.side")
        git(r.root, "commit", "-qm", "three")
        r.drop("inc:pom:quarkus-bom")
        rc, out = r.gate("accept-commit", "--attempt", "a", "--commit", git(r.root, "rev-parse", "HEAD"), "--classes", "build", task=tid)
        self.assertEqual((rc, out.get("refused")), (1, "ACCEPT_BASELINE_ANCESTRY"), out)

    # -- the store is out of reach; planting one refuses everything -------------
    def test_planted_consistent_store_is_refused(self):
        r = self.r
        r.release()
        tid, run, lock, _ = self.issue("build:rk:pom")
        # the worker copies the service's schema into the tree, consistently widened
        planted = r.root / P.STORE_FILE
        planted.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(r.store_dir / "authority.sqlite3", planted)
        con = sqlite3.connect(str(planted))
        con.execute("UPDATE issues SET allowed_paths=?", (json.dumps(["pom.xml", "src/x.java"]),))
        con.execute("DELETE FROM ledger WHERE kind='reject'")
        con.commit()
        con.close()
        with r.worker(tid, run, lock) as env:
            d = HK.writes(str(r.root), rel_paths=["src/x.java"], env=env)
            self.assertEqual(d["code"], "PROTOCOL_MIXED", d)
            d = HK.terminator(str(r.root), kind="complete", profile="implementer", env=env, audit_green=lambda: True)
            self.assertEqual(d["code"], "PROTOCOL_MIXED", d)
        rc, out = r.gate("issue", task=tid, run=run, lock=lock)
        self.assertEqual((rc, out.get("refused")), (1, "PROTOCOL_MIXED"), out)
        planted.unlink()
        # the service's own records are untouched and still decide
        with r.worker(tid, run, lock) as env:
            self.assertEqual(HK.writes(str(r.root), rel_paths=["src/x.java"], env=env)["code"], "WRITE_OUTSIDE_ISSUE")

    def test_lifecycle_tampering_grants_nothing(self):
        r = self.r
        # before M2 released nothing is issued, whatever the board says
        pom = r.tid("build:rk:pom")
        run, lock = r.board.claim(pom, os.getpid())
        rc, out = r.gate("issue", task=pom, run=run, lock=lock)
        self.assertEqual((rc, out.get("refused")), (1, "ISSUE_BEFORE_RELEASE"), out)
        r.board.end(pom)
        r.release()
        # a manually claimed M5 stage (worker edits the board) gets no grant
        prep = r.tid("deliver:prepare:c1")
        r.board.set(prep, assignee="implementer")
        run, lock = r.board.claim(prep, os.getpid())
        rc, out = r.gate("issue", task=prep, run=run, lock=lock)
        self.assertEqual((rc, out.get("refused")), (1, "ISSUE_UNGRANTED"), out)
        # a parent completed natively without domain acceptance does not release its child
        for oid in ("build:rk:pom", "config:rk:cfg"):
            self.r.board.end(r.tid(oid), "done")
        mapper = r.tid("source:u:dto-mapper")
        r.board.set(mapper, status="ready")
        run, lock = r.board.claim(mapper, os.getpid())
        rc, out = r.gate("issue", task=mapper, run=run, lock=lock)
        self.assertEqual((rc, out.get("refused")), (1, "ISSUE_PARENT_UNACCEPTED"), out)
        # a stale native run identity
        cfg = r.tid("config:rk:cfg")
        r.board.set(cfg, status="ready")
        run1, lock1 = r.board.claim(cfg, os.getpid())
        run2, lock2 = r.board.claim(cfg, os.getpid())
        rc, out = r.gate("issue", task=cfg, run=run1, lock=lock1)
        self.assertEqual((rc, out.get("refused")), (1, "ISSUE_STALE_RUN"), out)
        # an asserted stage result is refused (never signed)
        with self.assertRaises(A.AuthorityError) as cm:
            r.call("record_stage_result", task_id=prep, run_id=0, result={"ok": True, "ship": True})
        self.assertEqual(cm.exception.code, "STAGE_RESULT_ASSERTED")
        # an unknown transition, a bad request and a status call without a store are typed
        with self.assertRaises(A.AuthorityError) as cm:
            A.call(str(r.sock), "transition", {"name": "set_meta", "kwargs": {}})
        self.assertEqual(cm.exception.code, "AUTHORITY_BAD_REQUEST")

    def test_forged_heavy_receipts_are_the_declared_cooperative_limit(self):
        """What the service does NOT prove: the build/test/parity receipts and
        the rebuilt work list are the worker's. A worker that forges them for
        an in-scope, correctly committed candidate gets an acceptance -- which
        the record marks as worker-asserted. This is the open measurement-trust
        decision (enabled refuses MEASUREMENT_TRUST_UNDECIDED until declared)."""
        r = self.r
        r.release()
        tid, run, lock, _ = self.issue("build:rk:pom")
        (r.root / "pom.xml").write_text("<project>not really fixed</project>\n")
        rc, out = r.gate("verdict", "--verdict", "ACCEPTED", "--attempt", "f", task=tid)
        self.assertEqual(rc, 0, out)
        git(r.root, "commit", "-qam", "forged")
        r.drop("inc:pom:quarkus-bom")                                  # a forged measurement
        rc, out = r.gate("accept-commit", "--attempt", "f", "--commit", git(r.root, "rev-parse", "HEAD"),
                         "--classes", "build", task=tid)
        self.assertEqual((rc, out.get("outcome_accepted")), (0, True))
        m = [row for row in self._ledger() if row["kind"] == "measurement"][-1]
        self.assertEqual(m["doc"]["classes_asserted_by"], "worker-receipts")

    def test_repository_config_runs_nothing_in_the_service(self):
        """The worker owns .git/config and .gitattributes. An fsmonitor, a filter
        driver, a hook path or an external diff it configures must never run in
        the authority's principal. The probe script leaves a marker only when it
        runs with the service's environment (OB_IN_SERVICE=1)."""
        r = self.r
        marker = r.tmp / "pwned"
        probe = r.tmp / "probe.sh"
        probe.write_text("#!/bin/sh\n[ \"$OB_IN_SERVICE\" = 1 ] && echo \"$0 $*\" >> %s\ncat\n" % marker)
        probe.chmod(0o755)
        for k, v in (("core.fsmonitor", str(probe)), ("core.hooksPath", str(r.tmp)), ("diff.external", str(probe)),
                     ("filter.evil.clean", str(probe)), ("filter.evil.smudge", str(probe)),
                     ("remote.origin.uploadpack", str(probe)), ("remote.origin.url", str(r.root))):
            git(r.root, "config", k, v)
        (r.root / ".gitattributes").write_text("* filter=evil diff=evil\n")
        r.release()
        tid, run, lock, _ = self.issue("build:rk:pom")
        # a scope amendment (the transition that used to ask `git status`)
        out = r.call("amend_issue", task_id=tid, run_id=run, cluster="c:pom",
                     rel="src/main/resources/application.properties",
                     row={"reason": "the quarkus bom needs the port property", "locus": "application.properties:1"})
        self.assertIn("src/main/resources/application.properties", out["allowed_paths"])
        (r.root / "pom.xml").write_text("<project>x</project>\n")
        rc, out = r.gate("verdict", "--verdict", "ACCEPTED", "--attempt", "a", task=tid)
        self.assertEqual((rc, out.get("refused")), (1, "ACCEPT_OUT_OF_SCOPE"), out)   # .gitattributes is outside the issue
        (r.root / ".gitattributes").unlink()
        rc, out = r.gate("verdict", "--verdict", "ACCEPTED", "--attempt", "a", task=tid)
        self.assertEqual(rc, 0, out)
        git(r.root, "-c", "core.fsmonitor=", "commit", "-qam", "accept")
        r.drop("inc:pom:quarkus-bom")
        rc, out = r.gate("accept-commit", "--attempt", "a", "--commit", git(r.root, "rev-parse", "HEAD"), "--classes", "build", task=tid)
        self.assertEqual(rc, 0, out)
        r.tick()
        self.assertFalse(marker.exists(), marker.read_text() if marker.exists() else "")

    def test_not_protected_under_one_uid(self):
        ok, why = P.authority_protected(self.r.root, socket_path=str(self.r.sock))
        self.assertFalse(ok)
        self.assertIn("calling uid", why)


if __name__ == "__main__":
    unittest.main()
