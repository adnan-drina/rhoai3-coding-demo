#!/usr/bin/env python3
"""run-parity selftest: the parity phase is a tool, and it runs everything.

The control this file exists for is v9's first M4 card: the composer ran
before the comparisons, 24 of 34 admitted entry points ended "no parity
record" because compare-runtime-parity.py was never invoked, and the receipt
was composed anyway. Here the runner is given a destination and must, by
itself: replay every corpus scenario in corpus order, compare every entry
point that has a captured read oracle, name the ones it could not compare and
why, compose the receipt LAST, and record all of it in _run.json.

The other control is the exit code. A receipt that says FAIL is a measurement;
the runner that produced it did its job and exits 0. Only a child that could
not run (no corpus) exits 1.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run-parity.py"
CAPTURE_DIR = HERE.parents[2] / "gates" / "capture-source-oracles" / "scripts"
CAPTURE_READS = CAPTURE_DIR / "capture-source-oracles.py"
sys.path.insert(0, str(CAPTURE_DIR))
sys.path.insert(0, str(HERE.parents[3] / "lib"))
from _oracle_common import ORACLES, PARITY, http_observe, slug  # noqa: E402
from _scenarios import (SCENARIO_ORACLES, SCENARIO_PARITY, auth_headers, capture_receipt_path, corpus_digest,  # noqa: E402
                        corpus_path, normalized_identity, parity_receipt_path, request_of, scenario_oracles_dir,
                        scenario_parity_dir, scenario_slug)
from planner import pipeline, specimens  # noqa: E402
from planner.canonical import digest, load_json, write_canonical  # noqa: E402

CREATE_EP = "ep:org.acme.clinic.owner.OwnerController#create(Owner):http"
READ_EPS = ("ep:org.acme.clinic.owner.OwnerController#list():http",
            "ep:org.acme.clinic.pet.PetController#list():http",
            "ep:org.acme.clinic.vet.VetController#list():http")
NAVIGATION = PARITY / "navigation"
# The credential the ONE scenario that declares an effects identity navigates
# as. It is named here and held in the environment; nothing writes the value
# into a corpus, a capture or a record.
NAV_USER_ENV = "RUN_PARITY_NAV_USER"
NAV_PASS_ENV = "RUN_PARITY_NAV_PASS"
NAV_IDENTITY = {"kind": "basic", "user_env": NAV_USER_ENV, "password_env": NAV_PASS_ENV}
NAV_BASIC = "Basic " + base64.b64encode(b"nav-user:nav-secret").decode("ascii")

# --- the enabled security mode (ADR-014) ------------------------------------
# The enabled mode is its own evidence end to end: its own corpus, its own
# captures, its own parity records, its own receipt, its own run record. The
# identity its requests are made as arrives the only way a credential ever
# does -- by the NAME of an environment variable, held here and written
# nowhere.
ENABLED = "enabled"
ENABLED_CRED_ENV = "RUN_PARITY_ENABLED_CRED"
ENABLED_CRED_USER = "clinic-user"
ENABLED_CRED_PASSWORD = "clinic-secret"
ENABLED_IDENTITY = {"kind": "basic", "credential_ref": ENABLED_CRED_ENV}
ENABLED_BASIC = "Basic " + base64.b64encode(
    ("%s:%s" % (ENABLED_CRED_USER, ENABLED_CRED_PASSWORD)).encode()).decode("ascii")
ENABLED_CORPUS = {
    "schema": "rhoai3.scenario-corpus/v1",
    "approved_by": "operator:test",
    "initial_state": {"reset": "GET /__reset", "dataset": "empty"},
    "scenarios": [
        {"id": "sc:pets-as-clinic-user", "entry_point": CREATE_EP, "method": "GET", "path": "/api/pets",
         "identity": dict(ENABLED_IDENTITY), "body_absent": True, "reset_before": False, "effects": [],
         "normalization": []},
        {"id": "sc:vets-as-clinic-user", "entry_point": CREATE_EP, "method": "GET", "path": "/api/vets",
         "identity": dict(ENABLED_IDENTITY), "body_absent": True, "reset_before": False, "effects": [],
         "normalization": []},
    ],
}
# The switch the Operator declares, and the two settings that name its
# behaviours. The KEY is the specimen's; nothing in the harness knows it.
SWITCH_KEY = "acme.clinic.security.mode"
SWITCH_DISABLED = "permissive"
SWITCH_ENABLED = "enforcing"
SECURITY_DECISION = {
    "adr": "ADR-014",
    "switch": {"key": SWITCH_KEY, "disabled_value": SWITCH_DISABLED, "enabled_value": SWITCH_ENABLED},
    "identities": [{"name": "clinic-user", "credential_ref": ENABLED_CRED_ENV, "roles": ["USER"]}],
}
# What the run record held before ADR-014, and what this change adds to it.
# Pinned as a SET so a key that quietly appears (or disappears) in the default
# mode's record is a failure here rather than a surprise at M4.
RUN_KEYS_BEFORE = {"schema", "producer", "at", "root", "dest_url", "started_by_runner", "reset_cmd", "receipt_sha256",
                   "receipt_gaps", "issued", "binding", "corpus", "corpus_sha256", "corpus_error", "scenario_filter",
                   "scenarios", "read_oracles", "entry_points", "navigation", "compose", "receipt", "receipt_verdict",
                   "failures", "ok"}
RUN_KEYS_ADDED = {"security_mode", "dest_config", "dest_config_from_decisions", "dest_config_gap", "credential_refs",
                  "artifact", "orphaned",
                  # H5b: the destination log a 5xx verdict's exception is taken from ("" for a --dest-url run without --dest-log)
                  "dest_log"}


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _module(path: Path, name: str):
    """The runner as a module, so what it DERIVES can be measured without
    starting a destination to watch it be used."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class Service(BaseHTTPRequestHandler):
    """One tiny clinic. It requires a body to create, and it can be reset.

    ``drift`` makes one read answer differently, which is how a destination
    that really differs from the source is simulated."""

    owners: dict[str, dict] = {}
    drift = False
    # The legacy root address always answers the SAME first response -- 302 to
    # /ui/index.html -- in every mode, so the comparison passes throughout and
    # only what that address DOES changes. That is the whole point: a 302 to a
    # 404 is a PASSing comparison and a dead compatibility URL.
    root_mode = "ok"          # ok | dead | loop
    seen: list = []           # (path, Authorization) for every GET, in order

    def log_message(self, *a):  # noqa: D102 - quiet
        return

    def _send(self, code: int, payload=None, location: str | None = None):
        body = json.dumps(payload).encode() if payload is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if location:
            self.send_header("Location", location)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        type(self).seen.append((self.path, self.headers.get("Authorization") or ""))
        if self.path == "/__reset":
            type(self).owners = {}
            return self._send(200, {"reset": True})
        if self.path == "/":
            return self._send(302, None, location="/ui/index.html")
        if self.path == "/ui/index.html":
            if type(self).root_mode == "dead":
                return self._send(404, {"error": "no such page"})
            if type(self).root_mode == "loop":
                return self._send(302, None, location="/ui/other.html")
            return self._send(200, {"ui": "the replacement documentation UI"})
        if self.path == "/ui/other.html":
            return self._send(302, None, location="/ui/index.html")
        if self.path == "/api/owners":
            return self._send(200, sorted(self.owners))
        if self.path == "/api/pets":
            return self._send(200, ["basil"])
        if self.path == "/api/vets":
            return self._send(200, ["carter-drifted"] if type(self).drift else ["carter"])
        key = self.path.rsplit("/", 1)[-1]
        row = self.owners.get(key)
        return self._send(200, row) if row else self._send(404, {"error": "absent"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return self._send(400, {"error": "a body is required"})
        payload = json.loads(raw)
        type(self).owners[str(payload["id"])] = payload
        return self._send(201, payload)


CORPUS = {
    "schema": "rhoai3.scenario-corpus/v1",
    "approved_by": "operator:test",
    "initial_state": {"reset": "GET /__reset", "dataset": "empty"},
    "scenarios": [
        {"id": "sc:create-owner", "entry_point": CREATE_EP, "method": "POST", "path": "/api/owners",
         "headers": {"Content-Type": "application/json"},
         "body_file": "verification/scenarios/bodies/create-owner.json", "reset_before": True,
         "effects": [{"id": "eff:owner-7", "method": "GET", "path": "/api/owners/7"}], "normalization": []},
        # a second scenario on the same entry point: what a SCOPED run must
        # leave alone is only visible when there is something to leave alone
        {"id": "sc:create-owner-second", "entry_point": CREATE_EP, "method": "POST", "path": "/api/owners",
         "headers": {"Content-Type": "application/json"},
         "body_file": "verification/scenarios/bodies/create-owner-second.json", "reset_before": True,
         "effects": [{"id": "eff:owner-8", "method": "GET", "path": "/api/owners/8"}], "normalization": []},
        # the legacy root address: a redirect whose FIRST response the
        # comparison compares and whose TARGET only the navigation check can
        # reach. Two of them, because the navigation's credential rule has two
        # halves: nothing is sent unless the scenario declares an effects
        # identity, and then the same reference is.
        {"id": "sc:read-root", "entry_point": CREATE_EP, "method": "GET", "path": "/",
         "body_absent": True, "reset_before": False, "effects": [], "normalization": []},
        {"id": "sc:read-root-auth", "entry_point": CREATE_EP, "method": "GET", "path": "/",
         "body_absent": True, "reset_before": False, "effects_identity": dict(NAV_IDENTITY),
         "effects": [{"id": "eff:pets", "method": "GET", "path": "/api/pets"}], "normalization": []},
    ],
}


def _serve() -> tuple[HTTPServer, str]:
    srv = HTTPServer(("127.0.0.1", 0), Service)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def _reset_script(td: Path, base: str) -> Path:
    """The reset command the runner hands every scenario comparator."""
    p = td / "reset.py"
    p.write_text("import urllib.request\nurllib.request.urlopen(%r, timeout=10).read()\n" % (base + "/__reset"),
                 encoding="utf-8")
    return p


def _build(td: Path, base: str) -> Path:
    """A destination root whose M1 evidence was captured from the stub above."""
    root = specimens.build_dest(td / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
    specimens.prepare_loop(root)
    rec = pipeline.admit(root)
    if rec["status"] != "ADMITTED":
        raise SystemExit("fixture not admitted: %s" % rec["reasons"][:3])
    receipt_digest = load_json(root / "evidence/planning/admission-receipt.json")["receipt_digest"]
    bundle_sha = digest(load_json(root / "evidence/planning/evidence-bundle.json"))

    (root / "verification" / "scenarios" / "bodies").mkdir(parents=True, exist_ok=True)
    (root / "verification" / "scenarios" / "bodies" / "create-owner.json").write_text(
        json.dumps({"id": 7, "lastName": "Franklin"}), encoding="utf-8")
    (root / "verification" / "scenarios" / "bodies" / "create-owner-second.json").write_text(
        json.dumps({"id": 8, "lastName": "Rodriquez"}), encoding="utf-8")
    write_canonical(root / "verification" / "scenarios" / "corpus.json", CORPUS)
    corpus = load_json(root / "verification" / "scenarios" / "corpus.json")
    corpus_sha = corpus_digest(corpus)

    # The source is recorded the way capture-source-scenarios.py records it:
    # restore the initial state, probe what the source started from, replay the
    # complete request, read the effects back -- for each scenario in CORPUS
    # ORDER. The reads are captured after them, through the same running source,
    # so their oracles describe the state the replayed corpus leaves behind --
    # which is the state the destination is in when the runner reaches its read
    # comparisons.
    for sc, effect in zip(CORPUS["scenarios"], ("eff:owner-7", "eff:owner-8")):
        req = request_of(root, sc)
        path = "/api/owners/%s" % ("7" if effect.endswith("7") else "8")
        http_observe(base, "GET", "/__reset")
        before = http_observe(base, "GET", path)
        created = http_observe(base, "POST", "/api/owners", body=req["body"], headers=req["headers"])
        after = http_observe(base, "GET", path)
        if created.get("status") != 201:
            raise SystemExit("the stub source did not create: %s" % created)
        write_canonical(root / SCENARIO_ORACLES / (scenario_slug(str(sc["id"])) + ".json"), {
            "schema": "rhoai3.source-scenario/v1", "scenario": str(sc["id"]), "entry_point": CREATE_EP,
            "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "status": "CAPTURED", "reason": "",
            "evidence_bundle_sha256": bundle_sha, "source": {"base_url": base},
            "initial_state": dict(CORPUS["initial_state"]), "normalization": [], "reset_before": True,
            "request": {"request_sha256": req["request_sha256"]},
            "response": {"status": created["status"], "body_kind": created["body_kind"],
                         "body_sha256": created["body_sha256"], "headers": created["headers"]},
            "before": [{"id": effect, "method": "GET", "path": path,
                        "status": before["status"], "body_sha256": before["body_sha256"]}],
            "effects": [{"id": effect, "method": "GET", "path": path,
                         "status": after["status"], "body_sha256": after["body_sha256"]}],
        })
    # the legacy root address, captured the same way: the FIRST response, with
    # its Location, and (for the scenario that declares one) the effect
    # read-back taken as the identity it names
    root_sc = {sc["id"]: sc for sc in CORPUS["scenarios"]}
    for sid in ("sc:read-root", "sc:read-root-auth"):
        sc = root_sc[sid]
        req = request_of(root, sc)
        first = http_observe(base, "GET", "/")
        if first.get("status") != 302 or not (first.get("headers") or {}).get("Location"):
            raise SystemExit("the stub source must redirect from the root: %s" % first)
        oracle = {
            "schema": "rhoai3.source-scenario/v1", "scenario": sid, "entry_point": CREATE_EP,
            "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "status": "CAPTURED", "reason": "",
            "evidence_bundle_sha256": bundle_sha, "source": {"base_url": base},
            "initial_state": dict(CORPUS["initial_state"]), "normalization": [], "reset_before": False,
            "request": {"request_sha256": req["request_sha256"]},
            "response": {"status": first["status"], "body_kind": first["body_kind"],
                         "body_sha256": first["body_sha256"], "headers": first["headers"]},
            "before": [], "effects": [],
        }
        if sc.get("effects_identity"):
            oracle["effects_identity"] = dict(normalized_identity(sc["effects_identity"]))
            pets = http_observe(base, "GET", "/api/pets")
            oracle["effects"] = [{"id": "eff:pets", "method": "GET", "path": "/api/pets",
                                  "status": pets["status"], "body_sha256": pets["body_sha256"]}]
        write_canonical(root / SCENARIO_ORACLES / (scenario_slug(sid) + ".json"), oracle)
    proc = subprocess.run([sys.executable, str(CAPTURE_READS), "--root", str(root), "--base-url", base],
                          text=True, capture_output=True)
    if proc.returncode != 0:
        raise SystemExit("capturing the read oracles failed: %s%s" % (proc.stdout, proc.stderr))
    return root


def _build_enabled(root: Path, base: str) -> None:
    """The enabled mode's evidence, recorded the way the enabled-mode capture
    records it: its own corpus, its own captures, in its own directory, each
    file saying which mode it is of.

    The requests are made as the identity the corpus NAMES -- the credential is
    resolved from this environment at capture time, exactly as the comparator
    will resolve it at comparison time -- so what the destination is asked, and
    as whom, is the same question the source was asked."""
    receipt_digest = load_json(root / "evidence/planning/admission-receipt.json")["receipt_digest"]
    bundle_sha = digest(load_json(root / "evidence/planning/evidence-bundle.json"))
    write_canonical(root / corpus_path(ENABLED), ENABLED_CORPUS)
    corpus_sha = corpus_digest(load_json(root / corpus_path(ENABLED)))
    headers, gap = auth_headers(ENABLED_IDENTITY)
    if gap:
        raise SystemExit("the enabled fixture cannot authenticate: %s" % gap)
    for sc in ENABLED_CORPUS["scenarios"]:
        req = request_of(root, sc)
        got = http_observe(base, str(sc["method"]), str(sc["path"]), headers={**req["headers"], **headers})
        write_canonical(root / scenario_oracles_dir(ENABLED) / (scenario_slug(str(sc["id"])) + ".json"), {
            "schema": "rhoai3.source-scenario/v1", "scenario": str(sc["id"]), "entry_point": CREATE_EP,
            "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "status": "CAPTURED", "reason": "",
            "evidence_bundle_sha256": bundle_sha, "source": {"base_url": base},
            "initial_state": dict(ENABLED_CORPUS["initial_state"]), "normalization": [], "reset_before": False,
            "security_mode": ENABLED, "security_variant": "",
            "request": {"request_sha256": req["request_sha256"]},
            "response": {"status": got["status"], "body_kind": got["body_kind"],
                         "body_sha256": got["body_sha256"], "headers": got["headers"]},
            "before": [], "effects": [],
        })
    write_canonical(root / capture_receipt_path(ENABLED), {
        "schema": "rhoai3.source-capture/v1", "producer": "run-parity.test.py", "status": "ok", "reason": "",
        "security_mode": ENABLED, "security_variant": "", "corpus_sha256": corpus_sha,
        "captured": len(ENABLED_CORPUS["scenarios"]),
        "scenarios": [str(sc["id"]) for sc in ENABLED_CORPUS["scenarios"]],
        "credential_refs": [ENABLED_CRED_ENV], "source_config": {SWITCH_KEY: SWITCH_ENABLED},
        "receipt_sha256": receipt_digest, "evidence_bundle_sha256": bundle_sha,
    })


def _fake_artifact(root: Path) -> None:
    """A packaged application to identify the run by. A Quarkus fast-jar IS the
    quarkus-app directory, so the digest is over all of it -- the launcher and
    the library tree the runner would start."""
    app = root / "target" / "quarkus-app"
    (app / "lib" / "main").mkdir(parents=True, exist_ok=True)
    (app / "quarkus-run.jar").write_bytes(b"fixture launcher\n")
    (app / "lib" / "main" / "org.acme.clinic.jar").write_bytes(b"fixture dependency\n")


def _fake_java(bindir: Path, version: str) -> Path:
    """A `java` that prints a JDK banner on stderr, as the real launcher does,
    and starts nothing."""
    bindir.mkdir(parents=True, exist_ok=True)
    java = bindir / "java"
    java.write_text("#!/bin/sh\necho 'openjdk version \"%s\" 2024-01-16' >&2\nexit 0\n" % version, encoding="utf-8")
    java.chmod(0o755)
    return java


def _app_jar(root: Path, major: int) -> Path:
    """The application's own jar in a fast-jar layout, whose first class entry
    carries a crafted header: magic, minor 0, the given major."""
    app = root / "target" / "quarkus-app" / "app"
    app.mkdir(parents=True, exist_ok=True)
    jar = app / "fixture-app-1.0.jar"
    with zipfile.ZipFile(jar, "w") as zf:
        zf.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
        zf.writestr("org/acme/clinic/App.class", b"\xca\xfe\xba\xbe\x00\x00" + major.to_bytes(2, "big") + b"\x00" * 8)
    return jar


def _free_port() -> int:
    import socket
    with socket.socket() as so:
        so.bind(("127.0.0.1", 0))
        return so.getsockname()[1]


def _start_run(root: Path, env: dict, extra: tuple[str, ...] = ()) -> tuple[int, str, dict]:
    """The runner asked to START the destination itself (no --dest-url)."""
    proc = subprocess.run([sys.executable, str(RUNNER), "--root", str(root), "--port", str(_free_port()),
                           "--ready-timeout", "2", "--no-navigation", *extra],
                          text=True, capture_output=True, env=env, timeout=300)
    rec = root / PARITY / "_run.json"
    return proc.returncode, proc.stdout + proc.stderr, (load_json(rec) if rec.is_file() else {})


def _run(root: Path, base: str, reset: Path, scenarios: tuple[str, ...] = (), issued: str = "",
         extra: tuple[str, ...] = (), mode: str = "") -> tuple[int, str, dict]:
    scoped = [a for sid in scenarios for a in ("--scenario", sid)]
    bound = ["--issued", issued] if issued else []
    moded = ["--security-mode", mode] if mode else []
    proc = subprocess.run([sys.executable, str(RUNNER), "--root", str(root), "--dest-url", base,
                           "--reset-cmd", "%s %s" % (sys.executable, reset), *scoped, *bound, *moded, *extra],
                          text=True, capture_output=True)
    # one record per mode: the enabled run must not overwrite the evidence of
    # the run the M4 road left
    rec = root / PARITY / ("_run.json" if mode in ("", "disabled") else "_run-%s.json" % mode)
    run_doc = load_json(rec) if rec.is_file() else {}
    return proc.returncode, proc.stdout + proc.stderr, run_doc


def _server_error_case() -> int:
    """H5b: a 5xx verdict carries the destination's exception, taken from the
    destination log by the body's error id (anywhere in the log) or, without
    one, from the last ERROR/stack block appended in the request's window; the
    frames kept are the product's, resolved to files through the structure
    model; a 4xx difference gets nothing; the block is retained beside the
    record and only a bounded excerpt enters it."""
    from planner.paths import STRUCTURE
    from planner.server_error import RETAINED_DIR, annotate_record, log_blocks, server_error_status

    if [server_error_status(r) for r in ("status 500 vs 204; body a vs b", "status 404 vs 200", "status 503 vs 500",
                                          "header X a vs b; status 502 vs 201", "body a vs b")] != [(500, 204), None, None, (502, 201), None]:
        return _fail("only a 5xx the source did not answer is a server error")
    eid = "43525fec-1a2b-4c3d-9e8f-0123456789ab"
    product = ("com.acme.ledger.persistence.LedgerRepositoryImpl", "com.acme.ledger.service.LedgerService",
               "com.acme.ledger.web.AccountResource")
    with tempfile.TemporaryDirectory(prefix="server-error-") as td:
        root = Path(td)
        (root / STRUCTURE).parent.mkdir(parents=True)
        (root / STRUCTURE).write_text(json.dumps({"types": [
            {"fqn": fqn, "path": "src/main/java/%s.java" % fqn.replace(".", "/")} for fqn in product]}))
        log = root / "verification" / "parity" / "logs" / "destination.log"
        log.parent.mkdir(parents=True)
        startup = ("2026-09-21 10:00:01,000 INFO  [io.quarkus] (main) app 1.0 started in 2.1s. Listening on: http://0.0.0.0:8081\n"
                   "2026-09-21 10:00:02,000 WARN  [org.hib.orm.dep] (main) HHH90000025: a deprecation, not an error\n")
        block = ("2026-09-21 10:00:05,000 ERROR [io.qua.ver.htt.run.QuarkusErrorHandler] (executor-thread-1) HTTP Request to "
                 "/api/things/1 failed, error id: %s: jakarta.persistence.PersistenceException: org.hibernate.query.SemanticException: "
                 "Could not interpret path expression 'thing.visits'\n"
                 "\tat io.quarkus.arc.impl.AbstractSharedContext.get(AbstractSharedContext.java:50)\n"
                 "\tat org.hibernate.internal.SessionImpl.createQuery(SessionImpl.java:820)\n"
                 "\tat com.acme.ledger.persistence.LedgerRepositoryImpl.delete(LedgerRepositoryImpl.java:42)\n"
                 "\tat com.acme.ledger.persistence.LedgerRepositoryImpl_Subclass.delete$$superforward(Unknown Source)\n"
                 "\tat com.acme.ledger.service.LedgerService.delete(LedgerService.java:31)\n"
                 "\tat com.acme.ledger.web.AccountResource$1.lambda$delete$0(AccountResource.java:77)\n"
                 "\tat io.vertx.core.impl.ContextImpl.lambda$executeBlocking$0(ContextImpl.java:180)\n"
                 "Caused by: org.hibernate.query.SemanticException: Could not interpret path expression 'thing.visits'\n"
                 "\tat org.hibernate.query.hql.internal.BasicDotIdentifierConsumer.consume(BasicDotIdentifierConsumer.java:120)\n"
                 "\t... 40 more\n" % eid)
        after = "2026-09-21 10:00:06,000 INFO  [io.quarkus] (executor-thread-2) unrelated line after the request\n"
        log.write_text(startup + block + after)
        blocks = log_blocks(log.read_text())
        if len(blocks) != 4 or not blocks[2].startswith("2026-09-21 10:00:05,000 ERROR") or "... 40 more" not in blocks[2]:
            return _fail("the log is cut at header lines, frames and causes continuing the record: %d %r" % (len(blocks), [b[:40] for b in blocks]))
        rec_dir = root / "verification" / "parity" / "scenarios"
        rec_dir.mkdir(parents=True)
        base = {"schema": "rhoai3.scenario-parity/v1", "entry_point": "ep:x", "verdict": "FAIL"}
        # (a) error id in the body, the request window covering only the LATER lines: the id is still found in the whole log
        rec = rec_dir / "sc-delete-1.json"
        write_canonical(rec, dict(base, scenario="sc:delete-1", reason="status 500 vs 204; body aa vs bb (2 difference(s): extra at line 1; length)",
                                  observed={"status": 500, "body_sample": '{"details":"Error id %s","stack":""}' % eid}))
        window = (len(startup.encode()) + len(block.encode()), len((startup + block + after).encode()))
        se = annotate_record(root, rec, log, window)
        if not se or se.get("matched") != "error_id" or se.get("error_id") != eid:
            return _fail("the block is matched by the body's error id even outside the window: %s" % se)
        if se.get("exception") != "jakarta.persistence.PersistenceException" or "Could not interpret path expression" not in se.get("message", ""):
            return _fail("the exception and its message are the block's own: %s" % {k: se.get(k) for k in ("exception", "message")})
        files = [f["file"] for f in se["frames"]]
        if files != ["src/main/java/com/acme/ledger/persistence/LedgerRepositoryImpl.java",
                     "src/main/java/com/acme/ledger/service/LedgerService.java",
                     "src/main/java/com/acme/ledger/web/AccountResource.java"]:
            return _fail("only the product's frames are kept, in stack order -- a lambda in an inner class resolves to its outer "
                         "file, a container-generated subclass is the platform's: %s" % files)
        if se["frames"][0]["method"] != "delete" or se["frames"][0]["line"] != 42 or se.get("platform_frames_skipped") != 5:
            return _fail("the first product frame names the member and the line, the platform frames are counted: %s" % se["frames"][0])
        if se["causes"] != [{"exception": "org.hibernate.query.SemanticException", "message": "Could not interpret path expression 'thing.visits'"}]:
            return _fail("the cause chain is carried, bounded: %s" % se["causes"])
        doc = load_json(rec)
        if doc.get("server_error", {}).get("stack_sha256") != se["stack_sha256"] or len(doc["server_error"]["excerpt"]) > 12:
            return _fail("the record carries the digest and a bounded excerpt, never the whole block: %s" % doc.get("server_error"))
        kept = root / se["retained"]
        if kept.parent.name != RETAINED_DIR or kept.read_text() != block.rstrip("\n") or doc["server_error"]["log"] != "verification/parity/logs/destination.log":
            return _fail("the block is retained beside the record and the log is named: %s %s" % (se.get("retained"), se.get("log")))
        # (b) no error id in the body: the last ERROR/stack block appended in the request's window
        rec2 = rec_dir / "sc-delete-2.json"
        write_canonical(rec2, dict(base, scenario="sc:delete-2", reason="status 500 vs 204",
                                   observed={"status": 500, "body_sample": "Internal Server Error"}))
        se2 = annotate_record(root, rec2, log, (len(startup.encode()), window[1]))
        if not se2 or se2.get("matched") != "window" or se2.get("exception") != "jakarta.persistence.PersistenceException" or se2.get("error_id") != eid:
            return _fail("without an id the last ERROR block in the window is taken (and the id it carries is read from it): %s" % se2)
        # ... and a window with nothing at ERROR in it records the search, not an exception
        rec3 = rec_dir / "sc-delete-3.json"
        write_canonical(rec3, dict(base, scenario="sc:delete-3", reason="status 500 vs 204", observed={"status": 500, "body_sample": ""}))
        se3 = annotate_record(root, rec3, log, (window[0], window[1]))
        if not se3 or se3.get("matched") != "" or se3.get("exception") or "no exception block" not in se3.get("note", "") or se3.get("retained"):
            return _fail("a window holding nothing at ERROR records that the log has no block for the request: %s" % se3)
        # (c) a 4xx difference is not a server error, whatever is in the log
        rec4 = rec_dir / "sc-read-1.json"
        write_canonical(rec4, dict(base, scenario="sc:read-1", reason="status 404 vs 200; body aa vs bb",
                                   observed={"status": 404, "body_sample": '{"details":"Error id %s"}' % eid}))
        if annotate_record(root, rec4, log, (0, window[1])) is not None or "server_error" in load_json(rec4):
            return _fail("a 4xx difference gets no server_error")
        if annotate_record(root, rec_dir / "absent.json", log, (0, 1)) is not None:
            return _fail("no record, nothing to annotate")
    return 0


def main() -> int:
    if _server_error_case():
        return 1
    Service.owners = {}
    Service.drift = False
    Service.root_mode = "ok"
    Service.seen = []
    # the credential the ONE scenario that declares an effects identity
    # navigates as; every child process inherits it by NAME
    os.environ[NAV_USER_ENV] = "nav-user"
    os.environ[NAV_PASS_ENV] = "nav-secret"
    # the enabled mode's identity, held here under its NAME and written into no
    # corpus, capture, record or receipt
    os.environ[ENABLED_CRED_ENV] = "%s:%s" % (ENABLED_CRED_USER, ENABLED_CRED_PASSWORD)
    srv, base = _serve()
    try:
        with tempfile.TemporaryDirectory(prefix="run-parity-") as tmp:
            td = Path(tmp).resolve()
            reset = _reset_script(td, base)
            root = _build(td, base)
            # one packaged artifact, and the enabled mode's own evidence beside
            # the disabled mode's: ADR-014 is proved from ONE artifact restarted
            # with the switch changed, and from captures that never share a path
            _fake_artifact(root)
            _build_enabled(root, base)

            # --- the green run: everything compared, receipt composed last ---
            rc, blob, doc = _run(root, base, reset)
            if rc != 0:
                return _fail("a destination that matches the source must exit 0: %s" % blob[-1500:])
            if doc.get("schema") != "rhoai3.parity-run/v1" or doc.get("producer") != "run-parity.py":
                return _fail("_run.json schema: %s" % {k: doc.get(k) for k in ("schema", "producer")})
            if doc.get("started_by_runner") is not False or doc.get("dest_url") != base:
                return _fail("a destination passed with --dest-url is not started here: %s"
                             % {k: doc.get(k) for k in ("started_by_runner", "dest_url")})
            if not doc.get("corpus_sha256") or doc.get("corpus_error"):
                return _fail("the corpus must be bound by digest: %s" % {k: doc.get(k) for k in ("corpus_sha256", "corpus_error")})
            if str(reset) not in str(doc.get("reset_cmd") or ""):
                return _fail("the reset command must be on the record: %s" % doc.get("reset_cmd"))
            sc = doc["scenarios"]
            if [sc["declared"], sc["run"], sc["passed"], sc["failed"], sc["inconclusive"]] != [4, 4, 4, 0, 0]:
                return _fail("scenario counts %s (%s)" % (sc, blob[-800:]))
            if [r["id"] for r in sc["results"]] != ["sc:create-owner", "sc:create-owner-second", "sc:read-root",
                                                    "sc:read-root-auth"] or sc["results"][0]["rc"] != 0:
                return _fail("the per-scenario record must name every scenario in corpus order and its child's rc: %s" % sc["results"])
            if doc.get("scenario_filter") or not (doc.get("read_oracles") or {}).get("ran"):
                return _fail("an unfiltered run compares the read oracles and says so: %s"
                             % {k: doc.get(k) for k in ("scenario_filter", "read_oracles")})
            ep = doc["entry_points"]
            if [ep["admitted"], ep["compared"], ep["passed"], ep["skipped"]] != [4, 3, 3, 1]:
                return _fail("entry-point counts %s (%s)" % (ep, blob[-800:]))
            if sorted(r["entry_point"] for r in ep["results"]) != sorted(READ_EPS):
                return _fail("every entry point with a captured read oracle must be compared: %s" % ep["results"])
            if [r["entry_point"] for r in ep["not_compared"]] != [CREATE_EP] or "corpus" not in ep["not_compared"][0]["reason"]:
                return _fail("an entry point nobody could compare must be NAMED with its reason: %s" % ep["not_compared"])
            if doc["compose"]["rc"] != 0 or doc.get("receipt_verdict") != "PASS" or not doc.get("ok"):
                return _fail("the receipt must be composed last and PASS here: %s" % {k: doc.get(k) for k in ("compose", "receipt_verdict", "ok")})

            # --- ADR-014 regression: the default mode's record is what it was -
            # The mode is a scoping of the evidence, not a change to the M4
            # road. The default run must still read the same corpus, write the
            # same receipt and the same record, and carry the new keys at their
            # defaults -- the key SET is pinned so one that quietly appears or
            # disappears fails here rather than at M4.
            if set(doc) != RUN_KEYS_BEFORE | RUN_KEYS_ADDED:
                return _fail("the run record's shape changed: added %s, missing %s"
                             % (sorted(set(doc) - RUN_KEYS_BEFORE - RUN_KEYS_ADDED),
                                sorted((RUN_KEYS_BEFORE | RUN_KEYS_ADDED) - set(doc))))
            if (doc.get("security_mode") != "disabled" or doc.get("corpus") != "verification/scenarios/corpus.json"
                    or doc["receipt"]["path"] != "verification/parity/receipt.json"):
                return _fail("the default mode reads and writes exactly where it always did: %s"
                             % {k: doc.get(k) for k in ("security_mode", "corpus", "receipt")})
            if doc.get("dest_config") != {} or doc.get("dest_config_from_decisions") != [] or doc.get("dest_config_gap"):
                return _fail("a run nobody configured carries no configuration: %s"
                             % {k: doc.get(k) for k in ("dest_config", "dest_config_from_decisions", "dest_config_gap")})
            # the NAMES the replay may resolve a credential from, and no value
            if doc.get("credential_refs") != sorted([NAV_USER_ENV, NAV_PASS_ENV]):
                return _fail("the record names the credential variables the corpus declares: %s" % doc.get("credential_refs"))
            if not doc["artifact"]["sha256"] or doc["artifact"]["files"] != 2:
                return _fail("the record must identify the packaged artifact it measured: %s" % doc.get("artifact"))

            # the records the composer reads, written by the children
            for sid in ("sc:create-owner", "sc:create-owner-second", "sc:read-root", "sc:read-root-auth"):
                sp = root / SCENARIO_PARITY / (scenario_slug(sid) + ".json")
                if not sp.is_file() or load_json(sp)["verdict"] != "PASS":
                    return _fail("the scenario parity record must exist and PASS: %s" % sp)
            for e in READ_EPS:
                p = root / PARITY / (slug(e) + ".json")
                if not p.is_file() or load_json(p)["verdict"] != "PASS":
                    return _fail("no parity record for %s -- the v9 defect this runner exists to remove" % e)
            receipt = load_json(root / PARITY / "receipt.json")
            if receipt["verdict"] != "PASS" or receipt["total"] != 4 or receipt["not_passed"] != 0:
                return _fail("composed receipt %s" % {k: receipt.get(k) for k in ("verdict", "total", "not_passed")})

            # --- the bounded navigation check: a SEPARATE measurement -------
            # The comparison compared the first response and stopped there, as
            # it must. ADR-016 also asks whether that legacy address serves the
            # replacement UI, and only this walk can say.
            nav = doc["navigation"]
            if not nav.get("ran") or nav.get("max_hops") != 3:
                return _fail("the navigation check runs by default, with its hop bound on the record: %s" % nav)
            if [nav["checked"], nav["ok"], nav["dead"], nav["loop"], nav["too_many_hops"]] != [2, 2, 0, 0, 0]:
                return _fail("only the scenarios whose FIRST response was a redirect are navigated: %s" % nav)
            if [r["scenario"] for r in nav["results"]] != ["sc:read-root", "sc:read-root-auth"]:
                return _fail("the navigation results must name their scenarios in corpus order: %s" % nav["results"])
            rec = load_json(root / NAVIGATION / (scenario_slug("sc:read-root") + ".json"))
            if rec.get("schema") != "rhoai3.parity-navigation/v1" or rec.get("scenario") != "sc:read-root":
                return _fail("the navigation record schema: %s" % {k: rec.get(k) for k in ("schema", "scenario")})
            if rec.get("start") != base + "/ui/index.html" or rec.get("terminal") != "ok" or rec.get("final_status") != 200:
                return _fail("a 302 whose target answers 200 is ok, and the record names the address it walked: %s" % rec)
            if [h["url"] for h in rec["hops"]] != [base + "/ui/index.html"] or rec["hops"][0]["status"] != 200:
                return _fail("the record must show the walk, hop by hop: %s" % rec.get("hops"))
            if rec.get("identity") != {}:
                return _fail("a scenario that declares no effects identity navigates as nobody: %s" % rec.get("identity"))
            # H11: the final hop's page is recorded (status, content type, body
            # kind, digest) and compared with the source's when its capture
            # recorded one; this corpus has none, so nothing differs
            fin = rec.get("final") or {}
            if (fin.get("status") != 200 or fin.get("url") != base + "/ui/index.html" or not fin.get("content_type")
                    or not fin.get("body_kind") or not fin.get("body_sha256") or rec.get("source_final") != {} or rec.get("final_differs") != ""):
                return _fail("the navigation record names its final page and compares it with the source's: %s" % {k: rec.get(k) for k in ("final", "source_final", "final_differs")})
            from _oracle_common import final_page_differs  # noqa: E402
            if (final_page_differs(fin, {"status": 200, "content_type": "text/html", "body_kind": "html"}) !=
                    "content-type %s vs text/html; body-kind %s vs html" % (fin["content_type"], fin["body_kind"])):
                return _fail("a source final page of another kind is named as the difference: %s" % final_page_differs(fin, {"status": 200, "content_type": "text/html", "body_kind": "html"}))
            if final_page_differs(fin, {}) or final_page_differs(fin, dict(fin, body_sha256="other")):
                return _fail("no source walk, or the same kind of page with another digest, is no difference")
            auth_rec = load_json(root / NAVIGATION / (scenario_slug("sc:read-root-auth") + ".json"))
            if auth_rec.get("identity") != dict(normalized_identity(NAV_IDENTITY)) or auth_rec.get("terminal") != "ok":
                return _fail("a scenario that declares an effects identity navigates as that REFERENCE: %s" % auth_rec)
            row = next(r for r in receipt["entry_points"] if r["entry_point"] == CREATE_EP)
            if row["verdict"] != "PASS" or row.get("navigation") != "ok" or row.get("kind"):
                return _fail("a passing navigation is recorded on the row and changes no verdict: %s" % row)

            # --- deterministic: the same tree, the same records ---
            rc2, blob2, doc2 = _run(root, base, reset)
            a = {k: v for k, v in doc.items() if k != "at"}
            b = {k: v for k, v in doc2.items() if k != "at"}
            if rc2 != 0 or a != b:
                return _fail("the runner must be idempotent: rc=%s, %s" % (rc2, [k for k in a if a[k] != b.get(k)]))

            # --- scoped to one scenario: only that one is compared, and the
            #     receipt is still composed, from every record on disk ---
            rc5, blob5, doc5 = _run(root, base, reset, scenarios=("sc:create-owner-second",))
            if rc5 != 0:
                return _fail("a scoped run over a matching destination must exit 0: %s" % blob5[-1200:])
            sc5 = doc5["scenarios"]
            if doc5.get("scenario_filter") != ["sc:create-owner-second"] or [sc5["declared"], sc5["selected"], sc5["run"]] != [4, 1, 1]:
                return _fail("the filter must select from the corpus and say what it selected: %s | %s"
                             % (doc5.get("scenario_filter"), sc5))
            if [r["id"] for r in sc5["results"]] != ["sc:create-owner-second"]:
                return _fail("a scoped run must replay ONLY the scenarios it names: %s" % sc5["results"])
            if (doc5["read_oracles"]["ran"] or "skipped" not in doc5["read_oracles"]["reason"]
                    or doc5["entry_points"]["compared"] != 0 or doc5["entry_points"]["skipped"] != 4
                    or not all("skipped" in r["reason"] for r in doc5["entry_points"]["not_compared"])):
                return _fail("a scoped run skips the read oracles and NAMES every entry point it did not compare: %s | %s"
                             % (doc5.get("read_oracles"), doc5["entry_points"]))
            if doc5["compose"]["rc"] != 0 or doc5.get("receipt_verdict") != "PASS" or not doc5.get("ok"):
                return _fail("a scoped run still composes the receipt, over every record on disk: %s"
                             % {k: doc5.get(k) for k in ("compose", "receipt_verdict", "ok")})
            receipt5 = load_json(root / PARITY / "receipt.json")
            if receipt5["verdict"] != "PASS" or receipt5["total"] != 4:
                return _fail("the receipt a scoped run composes still states every entry point: %s"
                             % {k: receipt5.get(k) for k in ("verdict", "total", "not_passed")})

            # --- H3: a scoped run re-runs the READ ORACLES it is asked to,
            #     beside its scenarios, and no other --------------------------
            # dest v9 t_4d75569c: a card held a scenario obligation and a
            # read-oracle obligation on one entry point; the scoped acceptance
            # run skipped every read oracle, so the entry point's FAIL record
            # stayed exactly as the baseline had it and the card could never
            # discharge it. Here the vets read drifts, the scoped run names
            # that entry point, and the drift is measured -- while the other
            # read-oracle records are not rewritten.
            vet_ep = next(e for e in READ_EPS if "VetController" in e)
            others = {e: (root / PARITY / (slug(e) + ".json")).read_bytes() for e in READ_EPS if e != vet_ep}
            Service.drift = True
            rc6, blob6, doc6 = _run(root, base, reset, scenarios=("sc:create-owner-second",), extra=("--read-oracle", vet_ep))
            Service.drift = False
            if rc6 != 0:
                return _fail("a scoped run that re-runs one read oracle is a run, whatever the oracle says: %s" % blob6[-1200:])
            reads6 = doc6["read_oracles"]
            if reads6["ran"] or reads6.get("rerun") != [vet_ep] or reads6.get("requested") != [vet_ep]:
                return _fail("the record says the whole phase did not run and WHICH read oracle was re-run: %s" % reads6)
            if "except the read oracle(s) of %s" % vet_ep not in reads6["reason"]:
                return _fail("the reason names the exception: %s" % reads6["reason"])
            ep6 = doc6["entry_points"]
            if [ep6["compared"], ep6["failed"], ep6["skipped"]] != [1, 1, 3] or [r["entry_point"] for r in ep6["results"]] != [vet_ep]:
                return _fail("exactly the named read oracle is compared, and the drift is measured: %s" % ep6)
            if sorted(r["entry_point"] for r in ep6["not_compared"]) != sorted(e for e in READ_EPS + (CREATE_EP,) if e != vet_ep):
                return _fail("every other entry point is named as not compared: %s" % ep6["not_compared"])
            if load_json(root / PARITY / (slug(vet_ep) + ".json")).get("verdict") != "FAIL":
                return _fail("the re-run read oracle's record is this run's (FAIL under drift)")
            if any((root / PARITY / (slug(e) + ".json")).read_bytes() != b for e, b in others.items()):
                return _fail("a read oracle the scoped run was not asked for is never rewritten")
            # (the composer exits 1 around a FAIL by design; the verdict is the measurement)
            if not doc6["receipt"]["composed_by_this_run"] or doc6.get("receipt_verdict") != "FAIL" or not doc6.get("ok"):
                return _fail("the receipt is composed over the re-run record and carries its FAIL: %s"
                             % {k: doc6.get(k) for k in ("receipt", "receipt_verdict", "ok")})
            if "read oracle(s) re-run for the card: %s" % vet_ep not in blob6:
                return _fail("the summary says which read oracles were re-run: %s" % blob6[-600:])
            # the drift repaired: the same scoped run brings the record back to PASS
            rc7, blob7, doc7 = _run(root, base, reset, scenarios=("sc:create-owner-second",), extra=("--read-oracle", vet_ep))
            if rc7 != 0 or doc7["read_oracles"].get("rerun") != [vet_ep] or doc7.get("receipt_verdict") != "PASS":
                return _fail("the repaired read oracle comes back PASS through the same scoped run: %s %s" % (rc7, doc7.get("read_oracles")))
            if load_json(root / PARITY / (slug(vet_ep) + ".json")).get("verdict") != "PASS":
                return _fail("the re-run record is PASS again")
            # an entry point nobody admitted is refused, not skipped in silence
            rc8, blob8, doc8 = _run(root, base, reset, scenarios=("sc:create-owner-second",),
                                    extra=("--read-oracle", "ep:org.acme.Nobody#none():http"))
            if rc8 != 1 or not any("read-oracle filter" in f and "Nobody" in f for f in doc8.get("failures") or []):
                return _fail("an unadmitted --read-oracle refuses by name: rc=%s %s" % (rc8, doc8.get("failures")))
            # without a scenario filter the whole phase runs and the option adds nothing
            rc9, blob9, doc9 = _run(root, base, reset, extra=("--read-oracle", vet_ep))
            if rc9 != 0 or not doc9["read_oracles"]["ran"] or doc9["read_oracles"].get("rerun") != [] or doc9["entry_points"]["compared"] != 3:
                return _fail("an unfiltered run compares every read oracle; --read-oracle is then redundant and recorded as requested only: %s" % doc9.get("read_oracles"))

            # --- the records a scoped run did not write, and the ones that
            #     belong to nothing --------------------------------------
            # Composing over the records on disk is what keeps a scoped run
            # from erasing every other entry point's verdict, and it is why
            # leftovers matter. Measured on destination v9,
            # verification/parity/scenarios/ held cors-preflight-<digest>.json
            # and cors-actual-<digest>.json from an earlier naming scheme
            # beside the current sc_cors-preflight-<...>.json records: the
            # composer read them as scenarios of this corpus and the receipt
            # came back 33 INCONCLUSIVE of 34 after a scoped run that compared
            # one scenario and changed nothing else. So the runner moves what
            # does not belong aside -- never deletes it -- before the composer
            # reads the directory, and the rows for the scenarios this run did
            # not compare must be exactly the verdicts their records already
            # carried.
            untouched = {sid: (root / SCENARIO_PARITY / (scenario_slug(sid) + ".json")).read_bytes()
                         for sid in ("sc:create-owner", "sc:read-root", "sc:read-root-auth")}
            rows_before = {r["entry_point"]: r for r in load_json(root / PARITY / "receipt.json")["entry_points"]}
            leftovers = {"cors-preflight-7b1a3d9234cd.json": "cors-preflight-7b1a3d9234cd",
                         "cors-actual-7b1a3d9234cd.json": "cors-actual-7b1a3d9234cd",
                         # a scenario this corpus declares, under a file name
                         # that is not its slug: a second result for a scenario
                         # that has exactly one
                         "sc-create-owner-legacy.json": "sc:create-owner"}
            for name, sid in leftovers.items():
                write_canonical(root / SCENARIO_PARITY / name,
                                {"schema": "rhoai3.scenario-parity/v1", "scenario": sid, "entry_point": CREATE_EP,
                                 "receipt_sha256": doc["receipt_sha256"], "corpus_sha256": doc["corpus_sha256"],
                                 "security_mode": "disabled", "security_variant": "",
                                 "verdict": "INCONCLUSIVE", "reason": "no scenario %r in the corpus" % sid})
            rc12, blob12, doc12 = _run(root, base, reset, scenarios=("sc:create-owner-second",))
            orph = doc12["orphaned"]
            if rc12 != 0 or orph["pruned"] != 3 or not orph["dir"].startswith("verification/parity/_orphaned/"):
                return _fail("a scoped run moves every record that does not belong to this corpus aside: rc=%s %s"
                             % (rc12, orph))
            if sorted(r["path"].rsplit("/", 1)[-1] for r in orph["records"]) != sorted(leftovers):
                return _fail("the run record must name every record it moved, and nothing else: %s" % orph["records"])
            if any((root / SCENARIO_PARITY / name).exists() for name in leftovers):
                return _fail("a pruned record must not still be where the composer reads: %s" % sorted(leftovers))
            index = load_json(root / orph["dir"] / "_index.json")
            if index.get("schema") != "rhoai3.parity-orphans/v1" or index.get("from") != SCENARIO_PARITY.as_posix():
                return _fail("the index must say where the records came from: %s" % {k: index.get(k) for k in ("schema", "from")})
            for moved in index["records"]:
                if not (root / moved["moved_to"]).is_file() or not moved["reason"] or not moved["kind"]:
                    return _fail("nothing is deleted, and each record is kept with the reason it was set aside: %s" % moved)
            kinds = {r["path"].rsplit("/", 1)[-1]: r["kind"] for r in orph["records"]}
            if kinds.get("sc-create-owner-legacy.json") != "name-mismatch" or kinds.get("cors-actual-7b1a3d9234cd.json") != "undeclared-scenario":
                return _fail("each record is set aside for the reason it does not belong: %s" % kinds)
            # ...and the receipt this run composed is whole: the scenario it
            # compared, and every scenario it did not, from the records that
            # were already there and were not touched
            # both true at once: the receipt is THIS run's (bd45184c -- a
            # receipt counts only when this run composed it), and its rows for
            # the scenarios this run did not compare come from the records on
            # disk that belong to this corpus
            if (doc12["compose"]["rc"] != 0 or doc12.get("receipt_verdict") != "PASS" or not doc12.get("ok")
                    or not (doc12.get("receipt") or {}).get("composed_by_this_run")):
                return _fail("a scoped run over a pruned directory composes its own whole receipt: %s"
                             % {k: doc12.get(k) for k in ("compose", "receipt_verdict", "receipt", "ok")})
            receipt12 = load_json(root / PARITY / "receipt.json")
            if receipt12.get("orphaned_records") != [] or receipt12["total"] != 4 or receipt12["not_passed"] != 0:
                return _fail("nothing is left for the composer to call an orphan: %s"
                             % {k: receipt12.get(k) for k in ("orphaned_records", "total", "not_passed")})
            if {r["entry_point"]: r for r in receipt12["entry_points"]} != rows_before:
                return _fail("a scoped run must leave the rows it did not re-measure exactly as they were: %s"
                             % [r for r in receipt12["entry_points"] if rows_before.get(r["entry_point"]) != r])
            for sid, was in untouched.items():
                if (root / SCENARIO_PARITY / (scenario_slug(sid) + ".json")).read_bytes() != was:
                    return _fail("a scoped run rewrites no record it was not scoped to: %s" % sid)

            # a scenario nobody declared is a comparison that cannot be made
            rc6, blob6, doc6 = _run(root, base, reset, scenarios=("sc:not-in-the-corpus",))
            if rc6 != 1 or doc6["scenarios"]["run"] != 0 or not any("not declared" in f for f in doc6.get("failures") or []):
                return _fail("a filter naming an undeclared scenario must refuse and say so: rc=%s %s"
                             % (rc6, doc6.get("failures")))

            # --- --issued: the binding reaches both children and the record ---
            # On the acceptance path the work list has already been rebuilt on
            # the candidate, so the live seal cannot match it: the M4 road's
            # own comparison refuses (v9 card t_222c582a), and the same run
            # told which card it is for measures the candidate instead. What
            # proves the flag reached the children is that their records --
            # the scenario verdict and the receipt -- carry the binding.
            from planner.paths import ADMISSION_RECEIPT, LOOP_ISSUED, VERIFY_RUN, WORKLIST
            from _scenarios import product_tree_digest

            wl_bytes = (root / WORKLIST).read_bytes()
            wl = load_json(root / WORKLIST)
            wl["_rebuilt_on_the_candidate"] = True
            write_canonical(root / WORKLIST, wl)
            receipt_digest = load_json(root / ADMISSION_RECEIPT)["receipt_digest"]
            card = "t_222c582a"
            write_canonical(root / LOOP_ISSUED, {"schema": "rhoai3.loop-issued/v1", "cluster": "c:parity",
                                                 "task_id": card, "attempt": 4, "gate": "parity",
                                                 "receipt_sha256": receipt_digest, "items": ["parity:aaaa"],
                                                 "write_set": ["src/main/resources/application.properties"]})
            on_tree = product_tree_digest(root)
            write_canonical(root / VERIFY_RUN, {"schema": "rhoai3.verify-run/v1", "mode": "acceptance",
                                                "candidate_sha256": on_tree})
            scoped = ("sc:create-owner-second",)
            rc7, blob7, doc7 = _run(root, base, reset, scenarios=scoped)
            sv7 = load_json(root / SCENARIO_PARITY / (scenario_slug(scoped[0]) + ".json"))
            if doc7["scenarios"]["inconclusive"] != 1 or "worklist digest" not in sv7.get("reason", "") or doc7["compose"]["rc"] != 1:
                return _fail("the stale seal must refuse without --issued, or this control proves nothing: %s | %s"
                             % (sv7.get("reason"), {k: doc7.get(k) for k in ("scenarios", "compose")}))
            # ...and THAT is the false green: the composer refused, the receipt
            # the last run composed stayed on disk still saying PASS, and this
            # run reported "receipt PASS" at rc 0 while the only scenario it
            # compared was INCONCLUSIVE. A verdict this run did not produce is
            # not this run's measurement.
            if load_json(root / PARITY / "receipt.json").get("verdict") != "PASS":
                return _fail("the control needs the leftover receipt to still say PASS, or it proves nothing")
            if rc7 != 1:
                return _fail("a composer that refused is a child that could not run: rc=%s %s" % (rc7, blob7[-600:]))
            if doc7.get("receipt_verdict") is not None or (doc7.get("receipt") or {}).get("composed_by_this_run") is not False:
                return _fail("a receipt this run did not compose has no verdict to report: %s"
                             % {k: doc7.get(k) for k in ("receipt_verdict", "receipt")})
            if "refused" not in ((doc7.get("receipt") or {}).get("reason") or "") or not any(
                    "receipt not composed by this run" in f for f in doc7.get("failures") or []):
                return _fail("the record must say the receipt was not composed by this run, and why: %s | %s"
                             % (doc7.get("receipt"), doc7.get("failures")))
            if "NOT COMPOSED BY THIS RUN" not in blob7:
                return _fail("the runner must not print a verdict it did not measure: %s" % blob7[-600:])
            rc8, blob8, doc8 = _run(root, base, reset, scenarios=scoped, issued=str(root / LOOP_ISSUED))
            want = {"mode": "candidate", "candidate_sha256": on_tree, "issued_receipt_sha256": receipt_digest, "card": card}
            if rc8 != 0 or doc8.get("binding") != want or doc8.get("issued") != str(root / LOOP_ISSUED):
                return _fail("the run record must carry the binding it ran under: rc=%s %s %s"
                             % (rc8, doc8.get("binding"), blob8[-600:]))
            sv = load_json(root / SCENARIO_PARITY / (scenario_slug(scoped[0]) + ".json"))
            if sv.get("verdict") != "PASS" or sv.get("binding") != want:
                return _fail("the comparator child must have been told the binding: %s"
                             % {k: sv.get(k) for k in ("verdict", "binding", "reason")})
            rcpt = load_json(root / PARITY / "receipt.json")
            if rcpt.get("binding") != want or doc8.get("receipt_verdict") != "PASS":
                return _fail("the composer child must have been told the binding: %s / %s"
                             % (rcpt.get("binding"), doc8.get("receipt_verdict")))
            # A parity obligation whose entry point declares no scenario is a
            # READ oracle, and run-verify.sh compares the whole phase for it.
            # The flag has to reach that comparator too, or the stale seal
            # refuses every entry point and the card can never advance.
            rc11, blob11, doc11 = _run(root, base, reset, issued=str(root / LOOP_ISSUED))
            ev = load_json(root / PARITY / (slug(READ_EPS[0]) + ".json"))
            if rc11 != 0 or doc11["entry_points"]["compared"] != 3 or doc11["entry_points"]["passed"] != 3:
                return _fail("an unscoped candidate-bound run must compare the read oracles: rc=%s %s %s"
                             % (rc11, doc11.get("entry_points"), blob11[-600:]))
            if ev.get("verdict") != "PASS" or ev.get("binding") != want or ev.get("receipt_sha256") != receipt_digest:
                return _fail("the read-oracle comparator must have been told the binding: %s"
                             % {k: ev.get(k) for k in ("verdict", "binding", "receipt_sha256", "reason")})
            if doc11.get("receipt_verdict") != "PASS" or not (doc11.get("receipt") or {}).get("composed_by_this_run"):
                return _fail("the candidate-bound phase must compose its own receipt: %s"
                             % {k: doc11.get(k) for k in ("receipt_verdict", "receipt")})

            # an --issued path that names no card is refused once, by the runner
            rc9, blob9, doc9 = _run(root, base, reset, scenarios=scoped, issued=str(root / "verification" / "loop" / "nothing.json"))
            if rc9 != 1 or not any("issued binding" in f for f in doc9.get("failures") or []):
                return _fail("an --issued path with no card must refuse and say so: rc=%s %s" % (rc9, doc9.get("failures")))
            (root / WORKLIST).write_bytes(wl_bytes)
            (root / LOOP_ISSUED).unlink()
            rc10, blob10, doc10 = _run(root, base, reset)
            if rc10 != 0 or doc10.get("binding") != {"mode": "sealed"} or doc10.get("receipt_verdict") != "PASS":
                return _fail("with the seal restored and no --issued the M4 road is unchanged: rc=%s %s"
                             % (rc10, {k: doc10.get(k) for k in ("binding", "receipt_verdict")}))

            # --- the redirect target that does not do its job ---------------
            # In every one of these the FIRST response is unchanged: 302 to the
            # same address, so every scenario comparison still PASSes. What
            # changes is what that address does, and the comparison cannot see
            # it -- which is the whole reason the navigation is a separate
            # measurement.
            Service.root_mode = "dead"
            rcd, blobd, docd = _run(root, base, reset)
            navd = docd["navigation"]
            if rcd != 0:
                return _fail("a dead redirect target is a measurement, not a runner failure: rc=%s %s" % (rcd, blobd[-800:]))
            if [navd["checked"], navd["ok"], navd["dead"]] != [2, 0, 2]:
                return _fail("a 302 to a 404 must be recorded dead: %s" % navd)
            recd = load_json(root / NAVIGATION / (scenario_slug("sc:read-root") + ".json"))
            if recd["terminal"] != "dead" or recd["final_status"] != 404:
                return _fail("the record must say dead and the status it ended on: %s" % recd)
            svd = load_json(root / SCENARIO_PARITY / (scenario_slug("sc:read-root") + ".json"))
            if svd["verdict"] != "PASS":
                return _fail("the comparison compares the FIRST response and must still PASS: %s" % svd.get("reason"))
            rowd = next(r for r in load_json(root / PARITY / "receipt.json")["entry_points"]
                        if r["entry_point"] == CREATE_EP)
            if rowd["verdict"] != "PASS" or rowd.get("navigation") != "failed":
                return _fail("a PASSing comparison keeps its PASS while its navigation fails (ADR-020): %s" % rowd)
            obld = [o for o in load_json(root / PARITY / "receipt.json").get("navigation_obligations") or []
                    if o["entry_point"] == CREATE_EP]
            if len(obld) != 1 or obld[0]["kind"] != "navigation" or obld[0]["verdict"] != "FAIL":
                return _fail("a dead navigation is its own obligation row: %s" % obld)
            if "is dead on the destination (404)" not in obld[0]["reason"] or base + "/ui/index.html" not in obld[0]["reason"]:
                return _fail("the obligation must name the address and what became of it: %s" % obld[0]["reason"])
            if docd.get("receipt_verdict") != "FAIL":
                return _fail("the composed receipt carries the navigation FAIL: %s" % docd.get("receipt_verdict"))

            # a chain that comes back to an address it already asked
            Service.root_mode = "loop"
            rcl, blobl, docl = _run(root, base, reset)
            navl = docl["navigation"]
            if rcl != 0 or [navl["checked"], navl["loop"], navl["ok"]] != [2, 2, 0]:
                return _fail("a two-URL chain must be recorded loop: rc=%s %s" % (rcl, navl))
            recl = load_json(root / NAVIGATION / (scenario_slug("sc:read-root") + ".json"))
            if recl["terminal"] != "loop" or [h["url"] for h in recl["hops"]] != [base + "/ui/index.html", base + "/ui/other.html"]:
                return _fail("the loop record must show the walk that came back: %s" % recl)
            rowl = next(r for r in load_json(root / PARITY / "receipt.json")["entry_points"]
                        if r["entry_point"] == CREATE_EP)
            obll = [o for o in load_json(root / PARITY / "receipt.json").get("navigation_obligations") or []
                    if o["entry_point"] == CREATE_EP]
            if rowl["verdict"] != "PASS" or len(obll) != 1 or "is loop on the destination" not in obll[0]["reason"]:
                return _fail("a loop is the same separate obligation as a dead address: %s %s" % (rowl, obll))

            # --- --no-navigation: nobody looked, and the record says so ------
            Service.root_mode = "ok"
            Service.seen = []
            rcn, blobn, docn = _run(root, base, reset, extra=("--no-navigation",))
            if rcn != 0 or docn.get("navigation") != "skipped":
                return _fail("--no-navigation records navigation: skipped: rc=%s %r" % (rcn, docn.get("navigation")))
            if [q for q, _ in Service.seen if q.startswith("/ui/")]:
                return _fail("--no-navigation must walk nothing: %s" % [q for q, _ in Service.seen if q.startswith("/ui/")])

            # --- the credential rule, both halves ---------------------------
            # Nothing is sent unless the scenario declares an effects identity,
            # and then it is the SAME reference the read-backs are taken with.
            Service.seen = []
            rcc, blobc, docc = _run(root, base, reset)
            walked = [(q, a) for q, a in Service.seen if q.startswith("/ui/")]
            if rcc != 0 or len(walked) != 2:
                return _fail("both redirect targets are walked once: rc=%s %s" % (rcc, walked))
            if sorted(a for _, a in walked) != sorted(["", NAV_BASIC]):
                return _fail("exactly the scenario that declares an effects identity carries its credential, and the "
                             "other carries none: %s" % [(q, bool(a)) for q, a in walked])
            if docc["navigation"]["ok"] != 2:
                return _fail("the credential run must still be ok: %s" % docc["navigation"])

            # --- ADR-014: the enabled mode, measured from the same artifact --
            # The exit ADR-014 asks for is the enabled mode verified "from one
            # artifact, restarted with the switch changed at runtime", against
            # the ENABLED captures. So this run must be of the enabled mode
            # from end to end -- its corpus, its captures, its records, its
            # receipt, its own run record -- and must be able to be held
            # against the disabled run as one artifact measured twice.
            disabled_record = (root / PARITY / "_run.json").read_bytes()
            Service.seen = []
            rce, blobe, doce = _run(root, base, reset, mode="enabled")
            if rce != 0:
                return _fail("an enabled-mode run against a matching destination must exit 0: %s" % blobe[-1500:])
            if doce.get("security_mode") != "enabled" or doce.get("corpus") != "verification/scenarios-enabled/corpus.json":
                return _fail("the run must record the mode it is of and read that mode's corpus: %s"
                             % {k: doce.get(k) for k in ("security_mode", "corpus", "corpus_error")})
            sce = doce["scenarios"]
            if [sce["declared"], sce["selected"], sce["run"], sce["passed"]] != [2, 2, 2, 2]:
                return _fail("every scenario of the ENABLED corpus is replayed: %s (%s)" % (sce, blobe[-800:]))
            if [r["id"] for r in sce["results"]] != [str(s["id"]) for s in ENABLED_CORPUS["scenarios"]]:
                return _fail("the enabled corpus is replayed in ITS corpus order: %s" % sce["results"])
            # what proves --security-mode reached the children: their verdicts
            # say which mode they are of, and they are written in that mode's
            # own directory -- reuse is prevented by the path, not by memory
            for sc_row in ENABLED_CORPUS["scenarios"]:
                sid = str(sc_row["id"])
                sp = root / scenario_parity_dir(ENABLED) / (scenario_slug(sid) + ".json")
                if not sp.is_file():
                    return _fail("the enabled verdict must be written in the enabled mode's own directory: %s" % sp)
                sv_e = load_json(sp)
                if sv_e.get("verdict") != "PASS" or sv_e.get("security_mode") != "enabled":
                    return _fail("the comparator child must have been told the mode: %s"
                                 % {k: sv_e.get(k) for k in ("verdict", "security_mode", "reason")})
                if (root / SCENARIO_PARITY / (scenario_slug(sid) + ".json")).is_file():
                    return _fail("an enabled verdict must never land in the disabled mode's directory: %s" % sid)
            # the read oracles are DISABLED-mode captures: not re-measured, and
            # every entry point named with that reason rather than left to be
            # inferred from a count
            reads = doce["read_oracles"]
            if reads["ran"] or "disabled-mode captures" not in reads["reason"] or "not mode-scoped" not in reads["reason"]:
                return _fail("an enabled run must skip the read oracles and say WHY: %s" % reads)
            epe = doce["entry_points"]
            if epe["compared"] != 0 or epe["skipped"] != 4 or [r["reason"] for r in epe["not_compared"]] != [reads["reason"]] * 4:
                return _fail("every entry point must be named as not compared, with the reason: %s" % epe)
            # the destination was asked as the identity the corpus NAMES, with
            # the credential resolved from this environment at request time
            asked = [(q, a) for q, a in Service.seen if q in ("/api/pets", "/api/vets")]
            if len(asked) != 2 or sorted(a for _, a in asked) != [ENABLED_BASIC, ENABLED_BASIC]:
                return _fail("both enabled scenarios carry the identity the corpus names: %s"
                             % [(q, bool(a)) for q, a in asked])
            # the mode's own receipt, composed by this run, and the M4 road's
            # record untouched beside it
            if doce["receipt"]["path"] != "verification/parity/receipt-enabled.json" or not doce["receipt"]["composed_by_this_run"]:
                return _fail("the enabled run composes the ENABLED receipt: %s" % doce.get("receipt"))
            rcpt_e = load_json(root / parity_receipt_path(ENABLED))
            if rcpt_e.get("security_mode") != "enabled" or doce.get("receipt_verdict") != "PASS":
                return _fail("the composer child must have been told the mode: %s / %s"
                             % (rcpt_e.get("security_mode"), doce.get("receipt_verdict")))
            if load_json(root / PARITY / "receipt.json").get("security_mode") != "disabled":
                return _fail("the disabled receipt must still be the disabled mode's")
            if (root / PARITY / "_run.json").read_bytes() != disabled_record:
                return _fail("the enabled run must not overwrite the record the M4 road left")
            # ONE artifact, two modes: the digest is what SHOWS it
            if not doce["artifact"]["sha256"] or doce["artifact"]["sha256"] != doc["artifact"]["sha256"]:
                return _fail("both modes must be shown to have measured one artifact: %s vs %s"
                             % (doce.get("artifact"), doc.get("artifact")))

            # --- --from-decisions: the -D is the DECLARED switch -------------
            # decisions.yaml is sealed by the admission receipt, so the
            # derivation is exercised where it lives rather than by rewriting a
            # sealed file: the switch the Operator declared, at the setting each
            # mode declares for it, on the java command line of the artifact
            # this runner starts.
            rp = _module(RUNNER, "run_parity_under_test")
            sealed_decisions = (root / "decisions.yaml").read_bytes()
            try:
                decided_doc = specimens.full_decisions(
                    adrs=list(specimens.ACCEPTED_ADRS) + [{"id": "ADR-014", "title": "Security modes", "status": "accepted"}])
                decided_doc["security"] = SECURITY_DECISION
                (root / "decisions.yaml").write_text(specimens.decisions_yaml(decided_doc), encoding="utf-8")
                decided, why = rp.decided_security(root)
                if not decided or why:
                    return _fail("the declared security section must be readable: %s" % why)
                if rp.switch_config(decided, "enabled") != {SWITCH_KEY: SWITCH_ENABLED}:
                    return _fail("the enabled mode takes the switch's enabled_value: %s" % rp.switch_config(decided, "enabled"))
                if rp.switch_config(decided, "disabled") != {SWITCH_KEY: SWITCH_DISABLED}:
                    return _fail("the disabled mode takes the switch's disabled_value: %s" % rp.switch_config(decided, "disabled"))
                started = rp.Destination(root, 8099, "java", 1, rp.switch_config(decided, "enabled")).command()
                if started != ["java", "-D%s=%s" % (SWITCH_KEY, SWITCH_ENABLED), "-jar", "target/quarkus-app/quarkus-run.jar"]:
                    return _fail("the derived switch must be a system property on the artifact's command line: %s" % started)
                # a credential is never configuration: the refusal names the KEY
                conflicting = {"acme.clinic.admin.password": ENABLED_CRED_PASSWORD}
                if rp.credential_conflicts(conflicting, [ENABLED_CRED_ENV]) != ["acme.clinic.admin.password"]:
                    return _fail("a --dest-config value that IS a credential must be refused by key")
            finally:
                (root / "decisions.yaml").write_bytes(sealed_decisions)
            # ...and a run that asks for the declared switch where nothing is
            # declared refuses by NAMING what is missing, before it starts or
            # compares anything
            rcf, blobf, docf = _run(root, base, reset, mode="enabled", extra=("--from-decisions",))
            if rcf != 1 or docf["scenarios"]["run"] != 0 or docf["compose"]["rc"] is not None:
                return _fail("--from-decisions with no declared switch must refuse before anything runs: rc=%s %s"
                             % (rcf, {k: docf.get(k) for k in ("scenarios", "compose")}))
            if not docf.get("dest_config_gap") or not any("--from-decisions" in f and "decisions.yaml" in f
                                                          for f in docf.get("failures") or []):
                return _fail("the refusal must name the file that would have declared it: %s | %s"
                             % (docf.get("dest_config_gap"), docf.get("failures")))

            # --- a --dest-config that carries a credential: refused by KEY ---
            rcx, blobx, docx = _run(root, base, reset, mode="enabled",
                                    extra=("--dest-config", "acme.clinic.admin.password=" + ENABLED_CRED_PASSWORD))
            if rcx != 1 or docx["scenarios"]["run"] != 0:
                return _fail("a --dest-config carrying a credential must refuse before anything runs: rc=%s %s"
                             % (rcx, docx.get("scenarios")))
            if not any("acme.clinic.admin.password" in f and "credential" in f for f in docx.get("failures") or []):
                return _fail("the refusal must name the KEY: %s" % docx.get("failures"))
            if ENABLED_CRED_PASSWORD in blobx:
                return _fail("the refusal must never print what the key held")

            # --- a credential variable this workspace does not hold ----------
            # named by NAME, before anything is started: a request made as
            # nobody would record the destination's 401 as its answer
            held = os.environ.pop(ENABLED_CRED_ENV)
            try:
                Service.seen = []
                rcm, blobm, docm = _run(root, base, reset, mode="enabled")
                if rcm != 1 or docm["scenarios"]["run"] != 0 or docm["compose"]["rc"] is not None:
                    return _fail("a missing credential must refuse before anything runs: rc=%s %s"
                                 % (rcm, {k: docm.get(k) for k in ("scenarios", "compose")}))
                if not any(ENABLED_CRED_ENV in f for f in docm.get("failures") or []):
                    return _fail("the refusal must name the VARIABLE: %s" % docm.get("failures"))
                if [q for q, _ in Service.seen if q in ("/api/pets", "/api/vets")]:
                    return _fail("nothing may be replayed once a declared credential is absent: %s" % Service.seen)
            finally:
                os.environ[ENABLED_CRED_ENV] = held

            # --- a destination that really differs: FAIL is a measurement ---
            Service.drift = True
            rc3, blob3, doc3 = _run(root, base, reset)
            if rc3 != 0:
                return _fail("a receipt verdict of FAIL is not a runner failure: rc=%s %s" % (rc3, blob3[-1200:]))
            if doc3["entry_points"]["failed"] != 1 or doc3["receipt_verdict"] != "FAIL" or not doc3["ok"]:
                return _fail("a drifted read must be recorded FAIL and carried into the receipt: %s"
                             % {k: doc3.get(k) for k in ("entry_points", "receipt_verdict")})
            if load_json(root / PARITY / "receipt.json")["verdict"] != "FAIL":
                return _fail("the composed receipt must carry the FAIL")
            Service.drift = False

            # --- a child that could not run: no corpus → exit 1, and it says so ---
            (root / "verification" / "scenarios" / "corpus.json").unlink()
            rc4, blob4, doc4 = _run(root, base, reset)
            if rc4 != 1:
                return _fail("a missing corpus is a child that could not run: rc=%s" % rc4)
            if not doc4.get("corpus_error") or not any("corpus" in f for f in doc4.get("failures") or []):
                return _fail("the run record must name the missing corpus: %s" % {k: doc4.get(k) for k in ("corpus_error", "failures")})
            if doc4["scenarios"]["run"] != 0 or doc4["entry_points"]["compared"] != 3:
                return _fail("a missing corpus stops the scenarios, not the read comparisons: %s" % doc4)

            # --- the java that starts the destination (dest v9) --------------
            # The runner took the first `java` on PATH; on the Dev Spaces image
            # that is older than the build's, and the artifact died with
            # UnsupportedClassVersionError before anything answered. It now
            # resolves java exactly as the boot gate does, records it, and
            # refuses before starting when the packaged classes need newer.
            gate = rp._runtime_gate()
            jt = td / "jdks"
            j17 = _fake_java(jt / "jdk17" / "bin", "17.0.9")
            j21 = _fake_java(jt / "jdk21" / "bin", "21.0.4")
            order = [gate.resolve_java({"JAVA_HOME_21": str(jt / "jdk21"), "JAVA_HOME": str(jt / "jdk17")}),
                     gate.resolve_java({"JAVA_HOME_21": "", "JAVA_HOME": str(jt / "jdk17")}),
                     gate.resolve_java({})]
            if order != [(str(j21), "JAVA_HOME_21"), (str(j17), "JAVA_HOME"), ("java", "PATH")]:
                return _fail("java resolves $JAVA_HOME_21, then $JAVA_HOME, then PATH: %s" % order)
            if [gate.java_version(str(j))[:2] for j in (j17, j21)] != [
                    ('openjdk version "17.0.9" 2024-01-16', 17), ('openjdk version "21.0.4" 2024-01-16', 21)]:
                return _fail("the version is the banner's first line and its feature number: %s"
                             % [gate.java_version(str(j)) for j in (j17, j21)])
            if [gate.feature_of(x) for x in ('java version "1.8.0_402"', 'openjdk version "25-ea"', "nonsense")] != [8, 25, None]:
                return _fail("feature_of must read legacy and pre-release banners")
            jar = _app_jar(root, 65)
            if gate.artifact_class_major(root, gate.APP_DIR) != (65, "fixture-app-1.0.jar!org/acme/clinic/App.class"):
                return _fail("the artifact's class major is read from its first class entry: %s"
                             % (gate.artifact_class_major(root, gate.APP_DIR),))
            env17 = dict(os.environ, JAVA_HOME_21=str(jt / "jdk17"), JAVA_HOME=str(jt / "jdk21"))
            rcj, blobj, docj = _start_run(root, env17)
            want = ("REFUSE: PARITY_RUN the resolved java %s (openjdk version \"17.0.9\" 2024-01-16) cannot run classes "
                    "compiled for Java 21" % j17)
            if rcj != 1 or want not in blobj:
                return _fail("a runtime older than the artifact must refuse naming both: rc=%s %s" % (rcj, blobj[-800:]))
            jrec = (docj.get("destination") or {}).get("java") or {}
            if (jrec.get("binary"), jrec.get("source"), jrec.get("feature"), jrec.get("artifact_requires_java")) != (
                    str(j17), "JAVA_HOME_21", 17, 21) or not str(jrec.get("version") or "").startswith("openjdk version"):
                return _fail("_run.json destination.java records the resolved binary, its version and the need: %s" % jrec)
            if (docj.get("destination") or {}).get("argv") or docj["scenarios"]["run"] != 0 or docj["compose"]["rc"] is not None:
                return _fail("the refusal comes before anything is started: %s" % docj.get("destination"))
            if (root / PARITY / "logs" / "destination.log").exists():
                return _fail("nothing was started, so nothing was logged")
            # --java overrides the resolution; the class-version question is
            # then about THAT binary, and 21 can run Java 21 classes
            rco, bloblo, doco = _start_run(root, env17, ("--java", str(j21)))
            orec = (doco.get("destination") or {}).get("java") or {}
            if "cannot run classes" in bloblo or (orec.get("binary"), orec.get("source"), orec.get("feature")) != (
                    str(j21), "--java", 21):
                return _fail("--java overrides the resolved java and is recorded as such: %s | %s" % (orec, bloblo[-600:]))
            if (doco.get("destination") or {}).get("argv") and doco["destination"]["argv"][0] != str(j21):
                return _fail("the destination is started with the --java binary: %s" % doco["destination"]["argv"])
            # $JAVA_HOME is used when $JAVA_HOME_21 is not set
            env_home = {k: v for k, v in os.environ.items() if k != "JAVA_HOME_21"}
            env_home["JAVA_HOME"] = str(jt / "jdk21")
            rch, blobh, doch = _start_run(root, env_home)
            hrec = (doch.get("destination") or {}).get("java") or {}
            if "cannot run classes" in blobh or (hrec.get("binary"), hrec.get("source")) != (str(j21), "JAVA_HOME"):
                return _fail("$JAVA_HOME is the fallback when $JAVA_HOME_21 is unset: %s" % hrec)
            jar.unlink()
    finally:
        srv.shutdown()
    print("OK: run-parity selftest (H5b: a 5xx verdict carries the destination exception from its log -- by error id, else the last ERROR block in the request window -- with the product frames resolved to files, retained beside the record and digested on it; a 4xx gets nothing; every scenario in corpus order; every captured read oracle compared; the "
          "uncomparable named; receipt composed last; idempotent; --scenario replays only the scenarios it names, "
          "skips the read oracles by name and still composes the whole receipt, and refuses an undeclared id; "
          "--read-oracle (H3) re-runs exactly the named entry points' read oracles inside a scoped run, records them "
          "under read_oracles.rerun, names every other entry point as not compared and rewrites none of their records, "
          "refuses an unadmitted entry point, and is redundant without a scenario filter; "
          "a record that belongs to no scenario of this corpus -- the v9 cors-<digest>.json names from an earlier "
          "naming scheme, and a declared scenario under a name that is not its slug -- is MOVED ASIDE before the "
          "composer reads the directory, never deleted, with an index naming where each came from and why, and the "
          "move on _run.json; the scoped run that pruned them composes a whole receipt whose rows for the scenarios "
          "it did not compare are exactly the verdicts their records already carried, and it rewrote none of them; "
          "FAIL is a verdict not a runner failure; a missing corpus refuses; --issued carries the acceptance path's "
          "binding into BOTH comparators and the composer -- the scenario verdict, the read-oracle verdict and the "
          "composed receipt each record the candidate, the receipt the card was minted under and the card -- where the "
          "same run without it refuses on the work list rebuilt on that candidate, an --issued path naming no card "
          "refuses once in the run record, and with the seal restored the unbound run is the sealed M4 road again; "
          "a composer that REFUSED leaves the last run's receipt on disk still saying PASS, and the runner reports no "
          "verdict for it: receipt_verdict null, the record says it was not composed by this run and why, rc 1; "
          "the BOUNDED NAVIGATION runs beside the comparison and never inside it: every scenario whose first response "
          "on the destination was a redirect is walked on the destination only, at most --nav-max-hops hops, stopping "
          "at the first non-3xx, recorded per scenario under verification/parity/navigation -- a 302 to a 200 is ok "
          "and the receipt row says navigation: ok, a 302 to a 404 is dead and a two-URL chain is loop, and in both "
          "the comparison and its row still PASS while the navigation becomes its own FAIL obligation row naming the address; --no-navigation "
          "walks nothing and records navigation: skipped; and the walk carries no credential unless the scenario "
          "declares an effects identity, when it carries exactly that reference; "
          "ADR-014 -- the default mode's record is byte-for-byte the road it always was (its key set is pinned, its "
          "corpus, receipt and run record are where they were, and the new keys carry their defaults), while "
          "--security-mode enabled is the enabled mode end to end: the enabled corpus in ITS corpus order, verdicts "
          "written in the enabled mode's own directory and never in the disabled one, the mode on every child's record "
          "and on the composed receipt-enabled.json, the read oracles NOT re-measured with every entry point named for "
          "the reason they cannot be, the destination asked as the identity the corpus names with the credential "
          "resolved from the environment at request time, the disabled mode's own _run.json untouched beside it, and "
          "one artifact digest shown on both records; --from-decisions derives -DKEY=VALUE from the declared switch at "
          "each mode's own setting and puts it on the artifact's command line, and refuses by naming decisions.yaml "
          "where nothing is declared; a --dest-config whose VALUE is a credential refuses by KEY without printing it; "
          "and a declared credential this workspace does not hold refuses by NAME before anything is started or "
          "replayed; the destination's java is the boot gate's own -- $JAVA_HOME_21, then $JAVA_HOME, then PATH, "
          "--java overriding -- recorded with its version under destination.java, and a runtime older than the "
          "packaged classes (class file major - 44) refuses before anything is started, naming both)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
