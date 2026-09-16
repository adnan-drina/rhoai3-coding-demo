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
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run-parity.py"
CAPTURE_DIR = HERE.parents[2] / "gates" / "capture-source-oracles" / "scripts"
CAPTURE_READS = CAPTURE_DIR / "capture-source-oracles.py"
sys.path.insert(0, str(CAPTURE_DIR))
sys.path.insert(0, str(HERE.parents[3] / "lib"))
from _oracle_common import ORACLES, PARITY, http_observe, slug  # noqa: E402
from _scenarios import (SCENARIO_ORACLES, SCENARIO_PARITY, corpus_digest, normalized_identity, request_of,  # noqa: E402
                        scenario_slug)
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


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


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


def _run(root: Path, base: str, reset: Path, scenarios: tuple[str, ...] = (), issued: str = "",
         extra: tuple[str, ...] = ()) -> tuple[int, str, dict]:
    scoped = [a for sid in scenarios for a in ("--scenario", sid)]
    bound = ["--issued", issued] if issued else []
    proc = subprocess.run([sys.executable, str(RUNNER), "--root", str(root), "--dest-url", base,
                           "--reset-cmd", "%s %s" % (sys.executable, reset), *scoped, *bound, *extra],
                          text=True, capture_output=True)
    run_doc = load_json(root / PARITY / "_run.json") if (root / PARITY / "_run.json").is_file() else {}
    return proc.returncode, proc.stdout + proc.stderr, run_doc


def main() -> int:
    Service.owners = {}
    Service.drift = False
    Service.root_mode = "ok"
    Service.seen = []
    # the credential the ONE scenario that declares an effects identity
    # navigates as; every child process inherits it by NAME
    os.environ[NAV_USER_ENV] = "nav-user"
    os.environ[NAV_PASS_ENV] = "nav-secret"
    srv, base = _serve()
    try:
        with tempfile.TemporaryDirectory(prefix="run-parity-") as tmp:
            td = Path(tmp).resolve()
            reset = _reset_script(td, base)
            root = _build(td, base)

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
            if rowd["verdict"] != "FAIL" or rowd.get("kind") != "navigation":
                return _fail("a PASSing comparison with a dead navigation is a FAIL typed navigation: %s" % rowd)
            if "is dead on the destination (404)" not in rowd["reason"] or base + "/ui/index.html" not in rowd["reason"]:
                return _fail("the row must name the address and what became of it: %s" % rowd["reason"])
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
            if rowl["verdict"] != "FAIL" or rowl.get("kind") != "navigation" or "is loop on the destination" not in rowl["reason"]:
                return _fail("a loop is the same refusal as a dead address: %s" % rowl)

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
    finally:
        srv.shutdown()
    print("OK: run-parity selftest (every scenario in corpus order; every captured read oracle compared; the "
          "uncomparable named; receipt composed last; idempotent; --scenario replays only the scenarios it names, "
          "skips the read oracles by name and still composes the whole receipt, and refuses an undeclared id; "
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
          "the comparison still PASSes while the row becomes FAIL typed navigation naming the address; --no-navigation "
          "walks nothing and records navigation: skipped; and the walk carries no credential unless the scenario "
          "declares an effects identity, when it carries exactly that reference)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
