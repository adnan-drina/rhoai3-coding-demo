#!/usr/bin/env python3
"""F3 / release-plan item 4: ADR-026's committed-state read-back on PostgreSQL 16, through the ACTUAL path.

    compare-scenario-parity.py -> reset-parity-db.sh --query -> ResetDb --query  (and the real reset between)

on a disposable PostgreSQL 16 (test_runtime_fixture.postgres: the local image, never pulled, removed after).

The scenarios are the User-create shape, produced by the REAL derivation (derive-source-scenarios.py on the
request-model-derivation fixture): a create whose table no GET route reads, so its read-back is the committed
state -- COUNT(*) at the client-assigned key, the row's mapped columns as one value, COUNT(*) of the owned
collection's child rows -- plus its invalid-body twin read at the key THAT body names.

The source is captured on the same engine through the same query path (the reference application commits the
write), qualified by qualify-source-captures.py (committed_counts), and bound to the admission receipt and
corpus. The destination is a stateful loopback application writing through psql inside the container (its own
connection); the read-back is ResetDb's own JDBC connection. Asserted, in both security modes where declared:

  (a) a committed write read back                                  PASS
  (b) an invalid body, state unchanged                             PASS
  (c) a no-op write / a rolled-back write / a wrong stored value   FAIL, naming the step
  (d) a write left UNCOMMITTED in the writer's open transaction    FAIL: the read-back is another connection
  (e) the committed state unreadable after the request             INCONCLUSIVE, never a FAIL on a value
  source qualification (capture PASS), security mode and candidate binding recorded on the verdicts.

The one piece of test plumbing: the run-ownership check (planner.run_identity) requires the JDBC URL to name
the ASSIGNED service (fixture-isolated-postgres.fixture-ns:5432), which does not resolve on a workstation. The
URL carries pgjdbc's standard socketFactory parameter, a class that connects that address to the container's
loopback port; the URL the ownership check parses, and the credentials, are unchanged.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/skills/migration/fix-until-green/scripts/committed-state-postgres-runtime.test.py
(Skips, never passes, when podman, the PostgreSQL 16 image, java/javac or a local pgjdbc jar is missing.)
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
HERMES = GOLDEN / ".hermes"
CAPTURE_DIR = HERMES / "skills" / "gates" / "capture-source-oracles" / "scripts"
COMPARE = CAPTURE_DIR / "compare-scenario-parity.py"
RESET = CAPTURE_DIR / "reset-parity-db.sh"
QUALIFY = CAPTURE_DIR / "qualify-source-captures.py"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(CAPTURE_DIR))
sys.path.insert(0, str(HERMES / "lib"))
import test_runtime_fixture as F  # noqa: E402
from _oracle_common import http_observe  # noqa: E402
from _scenarios import (BINDING_CANDIDATE, capture_receipt_path, corpus_digest, corpus_path, product_tree_digest,  # noqa: E402
                        qualification_path, request_of, scenario_oracles_dir, scenario_parity_dir, scenario_slug)
from planner import pipeline, specimens  # noqa: E402
from planner.canonical import digest, load_json, write_canonical  # noqa: E402
from planner.paths import ADMISSION_RECEIPT, LOOP_ISSUED, VERIFY_RUN, WORKLIST  # noqa: E402

_spec = importlib.util.spec_from_file_location("rmd_fixture", CAPTURE_DIR / "request-model-derivation.test.py")
RMD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RMD)
N = RMD.PLAIN
ENABLED_CRED_ENV = "ADR026_ENABLED_CRED"
IDENTITY = {"kind": "basic", "credential_ref": ENABLED_CRED_ENV}
HOST = "fixture-isolated-postgres.fixture-ns"

SOCKET_FACTORY = r"""
import java.io.IOException;
import java.net.*;
import javax.net.SocketFactory;
/** Test plumbing: the ASSIGNED service name does not resolve on a workstation; connect it to the loopback port. */
public class LoopbackSocketFactory extends SocketFactory {
    private final int port;
    public LoopbackSocketFactory(String arg) { this.port = Integer.parseInt(arg); }
    public Socket createSocket() {
        return new Socket() {
            @Override public void connect(SocketAddress a, int t) throws IOException {
                super.connect(new InetSocketAddress(InetAddress.getLoopbackAddress(), port), t);
            }
        };
    }
    public Socket createSocket(String h, int p) throws IOException { Socket s = createSocket(); s.connect(null, 0); return s; }
    public Socket createSocket(String h, int p, InetAddress l, int lp) throws IOException { return createSocket(h, p); }
    public Socket createSocket(InetAddress h, int p) throws IOException { return createSocket("", p); }
    public Socket createSocket(InetAddress h, int p, InetAddress l, int lp) throws IOException { return createSocket("", p); }
}
"""

SCHEMA = ("CREATE TABLE %s (\n  %s VARCHAR(20) NOT NULL,\n  %s VARCHAR(20) NOT NULL,\n  PRIMARY KEY (%s)\n);\n"
          "CREATE TABLE %s (\n  id SERIAL PRIMARY KEY,\n  %s VARCHAR(30),\n  %s VARCHAR(20) NOT NULL\n);\n"
          % (N.accounts, N.handle_col, N.secret_col, N.handle_col, N.perk_table, N.perk_name, N.perk_col))
SEED = "INSERT INTO %s VALUES ('seeded.one', 'seedpass');\n" % N.accounts


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _pgjdbc() -> Path:
    base = Path.home() / ".m2" / "repository" / "org" / "postgresql" / "postgresql"
    jars = sorted(p for p in base.glob("42.*/postgresql-42.*.jar") if "sources" not in p.name and "javadoc" not in p.name)
    if not jars:
        raise F.Skip("no pgjdbc jar in the local Maven repository (%s)" % base)
    return jars[-1]


class Db:
    """psql INSIDE the container: the application's own connection, never the read-back's."""

    def __init__(self, pg: dict):
        self.pg = pg

    def argv(self, app: str = "fixture-app") -> list[str]:
        return ["podman", "exec", "-i", "-e", "PGPASSWORD=%s" % self.pg["password"], "-e", "PGAPPNAME=%s" % app,
                self.pg["container"], "psql", "-h", "127.0.0.1", "-U", self.pg["user"], "-d", "fixture",
                "-v", "ON_ERROR_STOP=1", "-q", "-A", "-t"]

    def sql(self, text: str) -> str:
        p = subprocess.run(self.argv() + ["-c", text], capture_output=True, text=True, timeout=60)
        if p.returncode != 0:
            raise RuntimeError("psql: %s" % (p.stderr or p.stdout)[-300:])
        return p.stdout.strip()


class App(BaseHTTPRequestHandler):
    """The destination (and, in mode 'commit', the reference source): POST <create path> writes the account
    and its perks through psql; the MODE decides what reaches the database."""

    db: Db = None
    route = ""
    mode = "commit"
    held: list = []

    def log_message(self, *a):
        return

    def _send(self, code, payload, errors=None):
        body = json.dumps(payload).encode()
        self.send_response(code)
        if errors is not None:
            # the source's field-error header (the petclinic BindingErrorsResponse shape)
            self.send_header("errors", json.dumps(errors))
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        cls = type(self)
        if self.path.split("?")[0] != cls.route:
            return self._send(404, {"error": "absent"})
        doc = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        key, secret = str(doc.get(N.handle) or ""), str(doc.get(N.secret) or "")
        if not key:
            return self._send(400, {"field": N.handle, "error": "must not be empty"},
                              errors=[{"objectName": N.Account, "fieldName": N.handle, "fieldValue": key,
                                       "errorMessage": "must not be empty"}])
        lit = lambda v: "'%s'" % str(v).replace("'", "''")
        stored = "WRONG" if cls.mode == "wrong" else secret
        writes = ["INSERT INTO %s (%s, %s) VALUES (%s, %s);" % (N.accounts, N.handle_col, N.secret_col, lit(key), lit(stored))]
        writes += ["INSERT INTO %s (%s, %s) VALUES (%s, %s);" % (N.perk_table, N.perk_name, N.perk_col, lit(p.get(N.perk_name)), lit(key))
                   for p in doc.get(N.perks) or []]
        if cls.mode in ("commit", "wrong", "unreadable"):
            cls.db.sql("BEGIN; %s COMMIT;" % " ".join(writes))
            if cls.mode == "unreadable":
                cls.db.sql("ALTER TABLE %s RENAME TO %s_gone;" % (N.perk_table, N.perk_table))
        elif cls.mode == "rollback":
            cls.db.sql("BEGIN; %s ROLLBACK;" % " ".join(writes))
        elif cls.mode == "uncommitted":
            proc = subprocess.Popen(cls.db.argv("adr026-uncommitted-writer"), stdin=subprocess.PIPE,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
            proc.stdin.write("BEGIN;\n%s\n" % "\n".join(writes))
            proc.stdin.flush()
            cls.held.append(proc)
            deadline = time.time() + 30
            while cls.db.sql("SELECT count(*) FROM pg_stat_activity WHERE application_name = 'adr026-uncommitted-writer' "
                             "AND state = 'idle in transaction' AND query LIKE 'INSERT%%'") != "1":
                if time.time() > deadline:
                    raise RuntimeError("the uncommitted writer never held its transaction open")
                time.sleep(0.2)
        # mode "noop": answers exactly as a write would and writes nothing
        return self._send(201, doc)


def release_held() -> None:
    for proc in App.held:
        try:
            proc.stdin.close()
        except OSError:
            pass
        proc.wait(timeout=60)
    App.held = []


def main() -> int:
    try:
        F.need_tools("podman", "java", "javac")
        jar = _pgjdbc()
        with F.postgres() as pg:
            return run(pg, jar)
    except F.Skip as exc:
        print("SKIP: %s" % exc)
        return 0


def run(pg: dict, pgjdbc: Path) -> int:
    port = int(pg["url"].rsplit(":", 1)[1].split("/", 1)[0])
    with tempfile.TemporaryDirectory(prefix="adr026-pg-") as td:
        t = Path(td)
        # -- the User-create shape, by the real derivation --------------------------------------------------
        droot, _ids = RMD.build(t / "derive", N)
        p = RMD._derive(droot)
        if p.returncode != 0:
            return _fail("the derivation fixture derives: %s" % (p.stdout + p.stderr)[-600:])
        derived = {s["id"]: s for s in load_json(droot / RMD.CORPUS_P)["scenarios"]}
        create = derived["sc:create-%s" % N.accounts]
        invalid = derived["sc:create-invalid-%s-%s" % (N.accounts, N.handle)]
        if [e.get("kind") for e in create["effects"]] != ["sql", "sql", "sql"] or create.get("effects_unobservable"):
            return _fail("the derived create is read back from the committed state only: %s" % create["effects"])
        rows_id, state_id, kids_id = [e["id"] for e in create["effects"]]

        # -- the destination tree: admitted, assigned its own parity database -------------------------------
        root = specimens.build_dest(t / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        specimens.prepare_loop(root)
        with (root / "migration.yaml").open("a") as f:
            f.write("\nresources:\n  run: fixture\n  namespace: fixture-ns\n"
                    "  parity_database:\n    instance: %s\n    database: fixture\n    port: 5432\n" % HOST)
        dbdir = root / "src" / "main" / "resources" / "db" / "postgresql"
        dbdir.mkdir(parents=True, exist_ok=True)
        (dbdir / "initDB.sql").write_text(SCHEMA, encoding="utf-8")
        (dbdir / "populateDB.sql").write_text(SEED, encoding="utf-8")
        if pipeline.admit(root)["status"] != "ADMITTED":
            return _fail("the destination fixture is admitted")
        for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
                                                     "commit", "-qm", "fixture"]):
            subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
        sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        receipt_digest = load_json(root / ADMISSION_RECEIPT)["receipt_digest"]
        bundle_sha = digest(load_json(root / "evidence" / "planning" / "evidence-bundle.json"))
        ep = sorted(str(e["id"]) for e in load_json(root / "evidence/planning/evidence-bundle.json")["entry_points"])[0]

        # the JDBC driver the reset uses, with the loopback socket factory beside it (see the docstring)
        (t / "sf").mkdir()
        (t / "sf" / "LoopbackSocketFactory.java").write_text(SOCKET_FACTORY, encoding="utf-8")
        subprocess.run(["javac", "-d", str(t / "sf"), str(t / "sf" / "LoopbackSocketFactory.java")], check=True, capture_output=True)
        driver = t / "pgjdbc-with-loopback.jar"
        shutil.copyfile(pgjdbc, driver)
        with zipfile.ZipFile(driver, "a") as z:
            for cls in (t / "sf").glob("*.class"):
                z.write(cls, cls.name)
        os.environ.update({
            "FIXTURE_DB_URL": "jdbc:postgresql://%s:5432/fixture?sslmode=disable&socketFactory=LoopbackSocketFactory"
                              "&socketFactoryArg=%d" % (HOST, port),
            "FIXTURE_DB_USER": pg["user"], "FIXTURE_DB_PASSWORD": pg["password"],
            "DEVWORKSPACE_NAME": "fixture", "DEVWORKSPACE_NAMESPACE": "fixture-ns", "MIGRATION_RUN_NAME": "fixture",
            "PARITY_RUN_RECEIPT": "run=fixture;namespace=fixture-ns;host=fixture-isolated-postgres;database=fixture;"
                                  "port=5432;workspace=fixture;engine=postgresql;scaffold=" + sha,
            ENABLED_CRED_ENV: "adr-user:adr-secret"})
        reset_argv = ["bash", str(RESET), "--root", str(root), "--driver", str(driver)]
        reset_cmd = " ".join(reset_argv)
        r = subprocess.run(reset_argv, text=True, capture_output=True)
        if r.returncode != 0 or "OK: reset" not in r.stdout:
            return _fail("the real reset restores the declared state on PostgreSQL 16: %s" % (r.stdout + r.stderr)[-600:])

        def query(sql: str) -> str | None:
            qf = t / "q.sql"
            qf.write_text(sql, encoding="utf-8")
            p = subprocess.run(reset_argv + ["--query", str(qf)], text=True, capture_output=True)
            lines = [ln for ln in p.stdout.splitlines() if ln.startswith("VALUE:")]
            return lines[0][len("VALUE:"):] if p.returncode == 0 and len(lines) == 1 else None

        db = Db(pg)
        App.db = db
        App.route = "/" + create["path"].lstrip("/")
        srv = ThreadingHTTPServer(("127.0.0.1", 0), App)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % srv.server_address[1]
        fails = 0
        try:
            for mode in ("disabled", "enabled"):
                pre = "" if mode == "disabled" else "sc:auth-"
                scs = []
                for sc in (create, invalid):
                    s = json.loads(json.dumps(sc))
                    s["id"] = pre + sc["id"][3:] if pre else sc["id"]
                    s["entry_point"] = ep
                    s["reset_before"] = True
                    if mode == "enabled":
                        s["identity"] = dict(IDENTITY)
                    (root / sc["body_file"]).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(droot / sc["body_file"], root / sc["body_file"])
                    scs.append(s)
                write_canonical(root / corpus_path(mode), {"schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
                                                           "initial_state": {"reset": "reset-parity-db.sh", "dataset": "one account"},
                                                           "scenarios": scs})
                csha = corpus_digest(load_json(root / corpus_path(mode)))
                extra = {} if mode == "disabled" else {"security_mode": "enabled", "security_variant": ""}
                # -- the source, captured on the same engine through the same query path ---------------------
                App.mode = "commit"
                for s in scs:
                    req = request_of(root, s)
                    if subprocess.run(reset_argv, capture_output=True).returncode != 0:
                        return _fail("reset before the capture")
                    before = [dict(e, value=query(e["query"])) for e in s["effects"]]
                    # the capture asserts the headers the source exposes (petclinic exposes its field-error header)
                    got = http_observe(base, s["method"], s["path"], body=req["body"], headers=req["headers"],
                                       assert_headers=["errors"])
                    after = [dict(e, value=query(e["query"])) for e in s["effects"]]
                    write_canonical(root / scenario_oracles_dir(mode) / (scenario_slug(s["id"]) + ".json"), dict({
                        "schema": "rhoai3.source-scenario/v1", "scenario": s["id"], "entry_point": ep,
                        "receipt_sha256": receipt_digest, "corpus_sha256": csha, "status": "CAPTURED", "reason": "",
                        "evidence_bundle_sha256": bundle_sha, "source": {"base_url": base},
                        "initial_state": {"reset": "reset-parity-db.sh", "dataset": "one account"}, "normalization": [],
                        "reset_before": True, "asserted_headers_extra": ["errors"],
                        "request": {"request_sha256": req["request_sha256"]},
                        "response": {"status": got["status"], "body_kind": got["body_kind"], "body_sha256": got["body_sha256"],
                                     "headers": got["headers"]},
                        "before": before, "effects": after}, **extra))
                cap = {s["id"]: load_json(root / scenario_oracles_dir(mode) / (scenario_slug(s["id"]) + ".json")) for s in scs}
                c_id, i_id = scs[0]["id"], scs[1]["id"]
                if [e["value"] for e in cap[c_id]["before"]] != ["0", "", "0"] or \
                        [e["value"] for e in cap[c_id]["effects"]] != ["1", "%s|1234" % N.v_newkey, "1"]:
                    return _fail("[%s] the reference write is captured 0 -> 1 row, its state, 0 -> 1 child: %s / %s"
                                 % (mode, cap[c_id]["before"], cap[c_id]["effects"]))
                write_canonical(root / capture_receipt_path(mode), dict({
                    "schema": "rhoai3.source-capture/v1", "producer": "committed-state-postgres-runtime.test.py", "status": "ok",
                    "reason": "", "evidence_bundle_sha256": bundle_sha, "corpus_sha256": csha, "receipt_sha256": receipt_digest,
                    "security_mode": mode, "source_config": {}, "credential_refs": [ENABLED_CRED_ENV] if mode == "enabled" else [],
                    "captured": 2, "requested": 2, "scenarios": [c_id, i_id], "reads": False,
                    "source": {"analysis_copy_digest": "fixture", "starts": 1}}, **({"security_variant": ""} if extra else {})))
                q = subprocess.run([sys.executable, str(QUALIFY), "--root", str(root), "--security-mode", mode],
                                   text=True, capture_output=True)
                qdoc = load_json(root / qualification_path(mode))
                caps = {k: v.get("capability") for k, v in (qdoc.get("scenarios") or {}).items()}
                if caps.get(c_id) != "PASS" or caps.get(i_id) != "PASS" or qdoc.get("security_mode") != mode \
                        or qdoc.get("corpus_sha256") not in (None, csha):
                    return _fail("[%s] the source capture qualifies (committed_counts, after_equals_before): %s %s"
                                 % (mode, caps, (q.stdout + q.stderr)[-400:]))

                # -- the destination, compared through the actual path --------------------------------------
                def compare(sid: str, app_mode: str, *more: str) -> dict:
                    App.mode = app_mode
                    try:
                        argv = [sys.executable, str(COMPARE), "--root", str(root), "--scenario", sid, "--dest-url", base,
                                "--reset-cmd", reset_cmd] + (["--security-mode", mode] if mode != "disabled" else []) + list(more)
                        subprocess.run(argv, text=True, capture_output=True, timeout=600)
                    finally:
                        release_held()
                        if app_mode == "unreadable":
                            db.sql("ALTER TABLE IF EXISTS %s_gone RENAME TO %s;" % (N.perk_table, N.perk_table))
                    return load_json(root / scenario_parity_dir(mode) / (scenario_slug(sid) + ".json"))

                def expect(name, v, verdict, needle=""):
                    nonlocal fails
                    ok = v.get("verdict") == verdict and needle in str(v.get("reason") or "") \
                        and v.get("security_mode", "disabled") == mode
                    print(("ok " if ok else "FAIL ") + "[%s] %s: %s %s" % (mode, name, v.get("verdict"), str(v.get("reason"))[:160]))
                    fails += 0 if ok else 1
                    return v

                v = expect("(a) committed write read back", compare(c_id, "commit"), "PASS")
                if [r["observed"].get("value") for r in v["effects"]] != ["1", "%s|1234" % N.v_newkey, "1"] \
                        or [r["kind"] for r in v["before"] + v["effects"]] != ["sql"] * 6:
                    fails += _fail("[%s] the committed state was read value for value: %s" % (mode, v["effects"]))
                if v.get("receipt_sha256") != receipt_digest or v.get("corpus_sha256") not in (None, csha):
                    fails += _fail("[%s] the verdict carries the source qualification's binding: %s" % (
                        mode, {k: v.get(k) for k in ("receipt_sha256", "corpus_sha256")}))
                expect("(b) invalid body, state unchanged", compare(i_id, "commit"), "PASS")
                expect("(c) no-op write", compare(c_id, "noop"), "FAIL", "%s: committed state '0' vs '1'" % rows_id)
                expect("(c) rolled-back write", compare(c_id, "rollback"), "FAIL", "%s: committed state '0' vs '1'" % rows_id)
                v = expect("(c) wrong stored value", compare(c_id, "wrong"), "FAIL", state_id)
                if rows_id in v.get("reason", ""):
                    fails += _fail("[%s] a wrong value is not a missing row: %s" % (mode, v["reason"]))
                v = expect("(d) write left uncommitted in the writer's own transaction", compare(c_id, "uncommitted"), "FAIL",
                           "%s: committed state '0' vs '1'" % rows_id)
                v = expect("(e) committed state unreadable after the request", compare(c_id, "unreadable"), "INCONCLUSIVE",
                           "%s: the committed state could not be read" % kids_id)
                if v.get("results", {}).get("destination_effect") != "INCONCLUSIVE" \
                        or any(r.get("observed", {}).get("value") is not None for r in v["effects"] if r["id"] == kids_id):
                    fails += _fail("[%s] an unread step is recorded as unread, never a value: %s" % (mode, v.get("results")))

            # -- candidate binding: the acceptance path's --issued, on the disabled create ------------------
            wl = load_json(root / WORKLIST)
            wl["_rebuilt_on_the_candidate"] = True
            write_canonical(root / WORKLIST, wl)
            card = "t_adr026pg"
            write_canonical(root / LOOP_ISSUED, {"schema": "rhoai3.loop-issued/v1", "cluster": "c:users", "task_id": card,
                                                 "gate": "parity", "receipt_sha256": receipt_digest,
                                                 "items": ["parity:0123456789abcdef"], "write_set": ["src/main/java/A.java"]})
            on_tree = product_tree_digest(root)
            write_canonical(root / VERIFY_RUN, {"schema": "rhoai3.verify-run/v1", "mode": "acceptance", "candidate_sha256": on_tree})
            App.mode = "commit"
            subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", create["id"], "--dest-url", base,
                            "--reset-cmd", reset_cmd, "--issued", str(root / LOOP_ISSUED)], text=True, capture_output=True)
            v = load_json(root / scenario_parity_dir("disabled") / (scenario_slug(create["id"]) + ".json"))
            want = {"mode": BINDING_CANDIDATE, "candidate_sha256": on_tree, "issued_receipt_sha256": receipt_digest, "card": card}
            ok = v.get("verdict") == "PASS" and v.get("binding") == want
            print(("ok " if ok else "FAIL ") + "candidate-bound committed-state PASS: %s %s" % (v.get("verdict"), v.get("binding")))
            fails += 0 if ok else 1
        finally:
            release_held()
            srv.shutdown()
        if fails:
            return _fail("%d ADR-026 PostgreSQL check(s) failed" % fails)
    print("OK: ADR-026 committed-state read-back on PostgreSQL 16 through compare-scenario-parity.py -> reset-parity-db.sh "
          "--query -> ResetDb --query, both security modes: committed write PASS, invalid body unchanged PASS, no-op / "
          "rolled-back / wrong value FAIL naming the step, an uncommitted write in the writer's own open transaction FAIL "
          "(the read-back is its own connection), an unreadable committed state INCONCLUSIVE; source captures qualified; "
          "verdicts bound to the admission receipt, mode and (with --issued) the candidate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
