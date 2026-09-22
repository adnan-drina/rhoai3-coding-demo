#!/usr/bin/env python3
"""scenario-parity selftest: a recorded write is replayed, not approximated.

The control this file exists for: a stub service that answers 201 to a POST
WITH a body and 400 to the same POST without one. The old comparator sent no
body, so identical services compared FAIL. Here the replay must reconstruct the
request from the corpus, prove it against the recorded digest, and pass; and a
destination that answers the write but does not perform it must FAIL on its
effect check.
"""
from __future__ import annotations

import base64
import json
import shlex
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPTURE = HERE / "capture-source-oracles.py"
COMPARE = HERE / "compare-scenario-parity.py"
RECEIPT = HERE / "compose-parity-receipt.py"
QUALIFY = HERE / "qualify-source-captures.py"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3] / "lib"))
from _scenarios import (load_corpus, SCENARIO_ORACLES, SCENARIO_PARITY, capture_receipt_path, corpus_digest,  # noqa: E402
                        parity_receipt_path, qualification_path, request_of, scenario_oracles_dir,
                        scenario_parity_dir, scenario_slug)
from planner import pipeline, specimens  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


class Service(BaseHTTPRequestHandler):
    """A tiny owners service. It requires a body to create, and it really
    deletes. ``lie_on_delete`` answers 204 and keeps the row."""

    owners: dict[str, dict] = {}
    lie_on_delete = False
    omit_location = False

    def log_message(self, *a):  # noqa: D102 - quiet
        return

    def _send(self, code: int, payload=None, location: str | None = None):
        body = json.dumps(payload).encode() if payload is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if location and not type(self).omit_location:
            self.send_header("Location", location)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        key = self.path.rsplit("/", 1)[-1]
        if self.path == "/api/owners":
            return self._send(200, sorted(self.owners))
        row = self.owners.get(key)
        return self._send(200, row) if row else self._send(404, {"error": "absent"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return self._send(400, {"error": "a body is required"})
        payload = json.loads(raw)
        self.owners[str(payload["id"])] = payload
        return self._send(201, payload, location="/api/owners/%s" % payload["id"])

    def do_DELETE(self):
        key = self.path.rsplit("/", 1)[-1]
        if key in self.owners and not type(self).lie_on_delete:
            del self.owners[key]
        return self._send(204)


def serve() -> tuple[HTTPServer, str]:
    srv = HTTPServer(("127.0.0.1", 0), Service)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


CORPUS = {
    "schema": "rhoai3.scenario-corpus/v1",
    "approved_by": "operator:test",
    "initial_state": {"reset": "restart the service", "dataset": "empty"},
    "scenarios": [
        {"id": "sc:create-owner", "entry_point": "", "method": "POST", "path": "/api/owners",
         "headers": {"Content-Type": "application/json"}, "body_file": "verification/scenarios/bodies/create-owner.json",
         "reset_before": True, "effects": [{"id": "eff:owner-7", "method": "GET", "path": "/api/owners/7"}],
         "normalization": []},
        {"id": "sc:delete-owner", "entry_point": "", "method": "DELETE", "path": "/api/owners/7",
         "body_absent": True, "reset_before": True,
         "effects": [{"id": "eff:owner-7-gone", "method": "GET", "path": "/api/owners/7"}], "normalization": []},
    ],
}


def _capture(root: Path, base: str, sc_id: str, req_sha: str, response: dict, effects: list[dict], receipt_digest: str, corpus_sha: str, before: list[dict] | None = None) -> None:
    """Record a source capture the way the M1 producer would, including the
    state the source was in before the request."""
    from planner.canonical import digest as _digest
    write_canonical(root / SCENARIO_ORACLES / (scenario_slug(sc_id) + ".json"), {
        "schema": "rhoai3.source-scenario/v1", "scenario": sc_id, "entry_point": next(s["entry_point"] for s in CORPUS["scenarios"] if s["id"] == sc_id),
        "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "status": "CAPTURED", "reason": "",
        "evidence_bundle_sha256": _digest(load_json(root / "evidence" / "planning" / "evidence-bundle.json")),
        "source": {"base_url": base}, "initial_state": CORPUS["initial_state"], "normalization": [],
        "reset_before": True, "request": {"request_sha256": req_sha}, "response": response,
        "before": list(before or []), "effects": effects,
    })


def _no_corpus_case() -> int:
    """A specimen with no approved scenarios still finishes M1, and the
    absence is on the record rather than in nobody's head."""
    producer = HERE / "capture-source-scenarios.py"
    with tempfile.TemporaryDirectory(prefix="nocorpus-") as td:
        root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        specimens.prepare_loop(root)
        p = subprocess.run([sys.executable, str(producer), "--root", str(root)], text=True, capture_output=True)
        if p.returncode != 0 or "nothing captured" not in p.stdout:
            return _fail("no corpus must be idle, not a failure: rc=%s %s%s" % (p.returncode, p.stdout, p.stderr[:200]))
        rec = load_json(root / SCENARIO_ORACLES / "_capture.json")
        if rec["status"] != "idle" or rec["captured"] != 0 or "missing" not in rec["reason"]:
            return _fail("the receipt must say plainly that nothing was captured and why: %s" % rec)
    return 0


def _header_contract_case() -> int:
    """Response headers are compared only when the source capture recorded them."""
    from _oracle_common import header_diffs

    if header_diffs(None, {"Location": "/api/owners/7"}):
        return _fail("a legacy capture with no headers map must not invent expected headers")
    diffs = header_diffs({"Location": "/api/owners/7", "Access-Control-Allow-Origin": "*"},
                         {"Location": None, "Access-Control-Allow-Origin": None})
    if not any("Location" in d for d in diffs) or not any("Access-Control-Allow-Origin" in d for d in diffs):
        return _fail("an asserted Location or CORS header that is absent must FAIL: %s" % diffs)
    if header_diffs({"Location": "/api/owners/7"}, {"Location": "/api/owners/7"}):
        return _fail("matching asserted headers are not a diff")

    class Located(Service):
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

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            if not raw:
                return self._send(400, {"error": "a body is required"})
            payload = json.loads(raw)
            self.owners[str(payload["id"])] = payload
            return self._send(201, payload, location="/api/owners/%s" % payload["id"])

    with tempfile.TemporaryDirectory(prefix="hdr-") as td:
        t = Path(td)
        root = specimens.build_dest(t / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        specimens.prepare_loop(root)
        rec = pipeline.admit(root)
        if rec["status"] != "ADMITTED":
            return _fail("header fixture not admitted: %s" % rec["reasons"][:3])
        digest = load_json(root / "evidence/planning/admission-receipt.json")["receipt_digest"]
        ep = sorted(str(e["id"]) for e in load_json(root / "evidence/planning/evidence-bundle.json")["entry_points"])[0]
        corpus = json.loads(json.dumps(CORPUS))
        corpus["scenarios"] = [s for s in corpus["scenarios"] if s["id"] == "sc:create-owner"]
        corpus["scenarios"][0]["entry_point"] = ep
        (root / "verification" / "scenarios" / "bodies").mkdir(parents=True, exist_ok=True)
        (root / "verification" / "scenarios" / "bodies" / "create-owner.json").write_text(json.dumps({"id": 7, "lastName": "Franklin"}), encoding="utf-8")
        write_canonical(root / "verification" / "scenarios" / "corpus.json", corpus)
        corpus_sha = corpus_digest(load_json(root / "verification" / "scenarios" / "corpus.json"))
        req = request_of(root, corpus["scenarios"][0])
        Located.owners = {}
        src = HTTPServer(("127.0.0.1", 0), Located)
        threading.Thread(target=src.serve_forever, daemon=True).start()
        src_url = "http://127.0.0.1:%d" % src.server_address[1]
        from _oracle_common import http_observe
        before = http_observe(src_url, "GET", "/api/owners/7")
        create = http_observe(src_url, "POST", "/api/owners", body=req["body"], headers=req["headers"])
        after = http_observe(src_url, "GET", "/api/owners/7")
        src.shutdown()
        if (create.get("headers") or {}).get("Location") != "/api/owners/7":
            return _fail("new captures must record Location: %s" % create.get("headers"))
        _capture(root, src_url, "sc:create-owner", req["request_sha256"],
                 {"status": 201, "body_kind": create["body_kind"], "body_sha256": create["body_sha256"], "headers": create["headers"]},
                 [{"id": "eff:owner-7", "method": "GET", "path": "/api/owners/7", "status": after["status"], "body_sha256": after["body_sha256"]}],
                 digest, corpus_sha,
                 before=[{"id": "eff:owner-7", "method": "GET", "path": "/api/owners/7", "status": before["status"], "body_sha256": before["body_sha256"]}])
        Service.owners = {}
        Service.omit_location = True
        dest, dest_url = serve()
        p = subprocess.run([sys.executable, str(COMPARE), "--no-reset", "--root", str(root), "--scenario", "sc:create-owner", "--dest-url", dest_url],
                           text=True, capture_output=True)
        dest.shutdown()
        Service.omit_location = False
        if p.returncode != 1 or "header Location" not in (p.stdout + p.stderr):
            return _fail("a destination that omits the recorded Location must FAIL: rc=%s %s" % (p.returncode, (p.stdout + p.stderr)[-400:]))
        _capture(root, src_url, "sc:create-owner", req["request_sha256"],
                 {"status": 201, "body_kind": create["body_kind"], "body_sha256": create["body_sha256"]},
                 [{"id": "eff:owner-7", "method": "GET", "path": "/api/owners/7", "status": after["status"], "body_sha256": after["body_sha256"]}],
                 digest, corpus_sha,
                 before=[{"id": "eff:owner-7", "method": "GET", "path": "/api/owners/7", "status": before["status"], "body_sha256": before["body_sha256"]}])
        Service.owners = {}
        dest, dest_url = serve()
        p = subprocess.run([sys.executable, str(COMPARE), "--no-reset", "--root", str(root), "--scenario", "sc:create-owner", "--dest-url", dest_url],
                           text=True, capture_output=True)
        dest.shutdown()
        if p.returncode != 1 or "INCONCLUSIVE" not in p.stderr or "no header map" not in p.stderr:
            return _fail("a 201 compared against a capture with no header map is INCONCLUSIVE: rc=%s %s" % (p.returncode, (p.stdout + p.stderr)[-400:]))
    return 0


def _capture_contract_case() -> int:
    """The first response, redirects not followed; only the declared origins
    are mapped in Location; list headers are token sets; a required header map
    that is missing is INCONCLUSIVE; a preflight is not a write; CORS coverage
    is counted per policy."""
    from _oracle_common import header_diffs, http_observe, is_preflight, map_origin, required_headers
    from _scenarios import CorpusError, cors_coverage, source_cors_policies

    class Redirecting(BaseHTTPRequestHandler):
        def log_message(self, *a):  # noqa: D102
            pass

        def do_GET(self):  # noqa: N802
            if self.path == "/petclinic/":
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1:%d/petclinic/swagger-ui.html" % self.server.server_address[1])
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = b"<html>target</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = HTTPServer(("127.0.0.1", 0), Redirecting)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    obs = http_observe(base, "GET", "/petclinic/")
    srv.shutdown()
    if "raw" in obs:
        return _fail("http_observe must not hand back bytes unless asked")
    if obs.get("status") != 302 or obs.get("redirects_followed") is not False:
        return _fail("the capture is the FIRST response, not the redirect's target: %s" % obs)
    if (obs.get("headers") or {}).get("Location") != base + "/petclinic/swagger-ui.html":
        return _fail("the raw Location is recorded: %s" % obs.get("headers"))

    src, dst = "http://localhost:9966", "http://10.0.0.5:8080"
    want = {"Location": src + "/petclinic/api/owners/7"}
    if header_diffs(want, {"Location": dst + "/petclinic/api/owners/7"}, source_origin=src, dest_origin=dst):
        return _fail("the same absolute Location on the destination's own origin is equal")
    if not header_diffs(want, {"Location": dst + "/api/owners/7"}, source_origin=src, dest_origin=dst):
        return _fail("a Location that dropped the context path differs")
    if not header_diffs(want, {"Location": "/petclinic/api/owners/7"}, source_origin=src, dest_origin=dst):
        return _fail("a relative Location is not the source's absolute form")
    if not header_diffs(want, {"Location": "http://elsewhere:8080/petclinic/api/owners/7"}, source_origin=src, dest_origin=dst):
        return _fail("only the declared origins are mapped")
    if map_origin(src + "/a%20b?x=1#f", src, dst) != dst + "/a%20b?x=1#f" or map_origin(src + "evil.com/x", src, dst) != src + "evil.com/x":
        return _fail("the mapping keeps path, escaping, query and fragment, and matches the origin exactly")
    if header_diffs({"Access-Control-Allow-Methods": "GET,POST"}, {"Access-Control-Allow-Methods": "post, get"}):
        return _fail("a list-valued CORS header is a token set")
    if required_headers("POST", 201, {}) != ["Location"] or "Access-Control-Allow-Origin" not in required_headers("GET", 200, {"Origin": "http://a"}):
        return _fail("a 201 requires Location; a cross-origin exchange requires the permission headers")
    pre = {"Origin": "http://a", "Access-Control-Request-Method": "POST"}
    if not is_preflight("OPTIONS", pre) or "Access-Control-Allow-Methods" not in required_headers("OPTIONS", 200, pre):
        return _fail("an OPTIONS with Origin and Access-Control-Request-Method is a preflight")

    with tempfile.TemporaryDirectory(prefix="cors-") as td:
        root = Path(td)
        base_doc = {"schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator", "cors_policies": [{"id": "p1", "request_headers": ["Content-Type"]}],
                    "scenarios": []}
        def corpus(*scs):
            d = json.loads(json.dumps(base_doc))
            d["scenarios"] = list(scs)
            (root / "verification" / "scenarios").mkdir(parents=True, exist_ok=True)
            (root / "verification" / "scenarios" / "corpus.json").write_text(json.dumps(d), encoding="utf-8")
            return d
        actual = {"id": "a", "entry_point": "e", "method": "GET", "path": "/api/x", "body_absent": True, "headers": {"Origin": "http://a"}, "cors_policy": "p1"}
        preflight = {"id": "p", "entry_point": "e", "method": "OPTIONS", "path": "/api/x", "body_absent": True, "cors_policy": "p1",
                     "headers": {"Origin": "http://a", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}}
        for bad, needle in (
            (dict(preflight, headers={"Origin": "http://a"}), "Access-Control-Request-Method"),
            (dict(preflight, identity={"kind": "basic", "user_env": "U", "password_env": "P"}), "without credentials"),
            (dict(actual, cors_policy=None), "names no cors_policy"),
        ):
            corpus(bad)
            try:
                load_corpus(root)
                return _fail("the corpus must refuse: %s" % needle)
            except CorpusError as exc:
                if needle not in str(exc):
                    return _fail("the refusal names %r: %s" % (needle, exc))
        if cors_coverage(corpus(actual, preflight)) != []:
            return _fail("an actual exchange and a preflight with the needed request header cover the policy")
        if not any("no preflight" in g for g in cors_coverage(corpus(actual))):
            return _fail("a policy without a preflight is not covered")
        thin = dict(preflight, headers={"Origin": "http://a", "Access-Control-Request-Method": "POST"})
        if not any("content-type" in g for g in cors_coverage(corpus(actual, thin))):
            return _fail("a preflight that omits a needed request header does not cover the policy")
        if not any("the source declares" in g for g in cors_coverage(corpus(actual, preflight), ["crossorigin:abc"])):
            return _fail("a policy the source declares and the corpus does not name is a gap")
        pols, why = source_cors_policies(root)
        if pols or not why:
            return _fail("an absent source model is a reason, never 'no policies': %s %s" % (pols, why))
        ann = {"fqn": "org.springframework.web.bind.annotation.CrossOrigin", "values": {"exposedHeaders": ["errors, content-type"]}}
        other = {"fqn": "org.springframework.web.bind.annotation.CrossOrigin", "values": {"origins": ["http://x"]}}
        (root / "evidence" / "structure").mkdir(parents=True, exist_ok=True)
        (root / "evidence" / "structure" / "structure.json").write_text(json.dumps({"types": [
            {"fqn": "a.OwnerRestController", "annotations": [ann]}, {"fqn": "a.PetRestController", "annotations": [ann]},
            {"fqn": "a.VetRestController", "methods": [{"name": "m", "annotations": [other]}]},
            {"fqn": "a.WebConfig", "type_refs": ["org.springframework.web.servlet.config.annotation.CorsRegistry"]}]}), encoding="utf-8")
        pols, why = source_cors_policies(root)
        if len(pols) != 3 or why or not any(p.startswith("global:a.WebConfig") for p in pols):
            return _fail("one policy per distinct @CrossOrigin, and a CORS registry is a global one: %s %s" % (pols, why))
        # the headers the source EXPOSES are asserted, from the same model
        from _scenarios import source_exposed_headers
        exposed, why = source_exposed_headers(root)
        if exposed != ["content-type", "errors"] or why:
            return _fail("exposedHeaders are split and asserted: %s %s" % (exposed, why))
        from _oracle_common import asserted_headers
        class _Msg(dict):
            def get(self, k, d=None):
                return super().get(k.lower(), d)
        rec = asserted_headers(_Msg({"errors": "[{\"field\":\"telephone\"}]", "location": None}), exposed)
        if rec.get("errors") != "[{\"field\":\"telephone\"}]" or "content-type" not in rec:
            return _fail("an exposed header is recorded beside the CORS set: %s" % rec)
        # full bodies are retained as evidence beside a capture, bound by digest
        import hashlib as _hl
        from _oracle_common import RETAINED_BODY_CAP, normalize_body, retain_body
        with tempfile.TemporaryDirectory(prefix="retain-") as rd:
            previous = Service.owners
            Service.owners = {"11": {"lastName": "Probe", "id": 11}}
            service, url = serve()
            try:
                observed = http_observe(url, "GET", "/api/owners/11", keep_body=True)
            finally:
                service.shutdown()
                service.server_close()
                Service.owners = previous
            raw = observed["raw"]
            raw_sha = _hl.sha256(raw).hexdigest()
            if raw_sha == observed["body_sha256"]:
                return _fail("the JSON fixture must distinguish wire bytes from canonical parity bytes")
            ev = retain_body(Path(rd), "after-eff", raw, observed["body_sha256"])
            kept = Path(ev["body_file"]).read_bytes()
            if (kept != raw or ev["retained_sha256"] != raw_sha or ev["raw_body_sha256"] != raw_sha
                    or ev["body_sha256"] != normalize_body(kept, "application/json")[1]
                    or ev["truncated"] or ev["body_bytes"] != len(raw)):
                return _fail("retention binds wire bytes separately from the observed canonical JSON digest: %s" % ev)
            big = b"x" * (RETAINED_BODY_CAP + 5)
            ev2 = retain_body(Path(rd), "big", big, _hl.sha256(big).hexdigest())
            if (not ev2["truncated"] or ev2["retained_bytes"] != RETAINED_BODY_CAP or ev2["body_bytes"] != len(big)
                    or ev2["retained_sha256"] != _hl.sha256(Path(ev2["body_file"]).read_bytes()).hexdigest()
                    or ev2["raw_body_sha256"] != _hl.sha256(big).hexdigest()
                    or ev2["retained_sha256"] == ev2["raw_body_sha256"]):
                return _fail("a body over the cap is cut and says so: %s" % ev2)
        if header_diffs({"errors": "[x]"}, {"errors": None}) != ["header errors None vs [x]"]:
            return _fail("a recorded errors header the destination drops is a diff: %s" % header_diffs({"errors": "[x]"}, {"errors": None}))
    return 0


def _effectless_reset_case() -> int:
    """A scenario that declares no effect has no before-state to compare.

    Measured on v9's first M4 parity receipt: ``sc:cors-actual-*`` -- a GET
    with ``effects: []`` -- came back INCONCLUSIVE because the capture
    recorded no ``before``. It never could: the capture probes the scenario's
    OWN effects to record the state the source started from. Here the reset
    still runs (the request may depend on the seeded rows), the absence is
    stated on the verdict, and the comparison is the response itself: PASS
    against an identical destination, FAIL typed by the diffs against a
    divergent one. A scenario WITH effects and no before is still
    INCONCLUSIVE -- there the capture skipped probes it was asked to take."""
    corpus_doc = {
        "schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
        "initial_state": {"reset": "restart the service", "dataset": "one owner"},
        "scenarios": [
            {"id": "sc:list-owners", "entry_point": "", "method": "GET", "path": "/api/owners",
             "body_absent": True, "reset_before": True, "effects": [], "normalization": []},
            {"id": "sc:delete-owner", "entry_point": "", "method": "DELETE", "path": "/api/owners/7",
             "body_absent": True, "reset_before": True,
             "effects": [{"id": "eff:owner-7-gone", "method": "GET", "path": "/api/owners/7"}], "normalization": []},
        ],
    }
    with tempfile.TemporaryDirectory(prefix="effectless-") as td:
        t = Path(td)
        root = specimens.build_dest(t / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        specimens.prepare_loop(root)
        rec = pipeline.admit(root)
        if rec["status"] != "ADMITTED":
            return _fail("effect-less fixture not admitted: %s" % rec["reasons"][:3])
        receipt_digest = load_json(root / "evidence/planning/admission-receipt.json")["receipt_digest"]
        ep = sorted(str(e["id"]) for e in load_json(root / "evidence/planning/evidence-bundle.json")["entry_points"])[0]
        for sc in corpus_doc["scenarios"]:
            sc["entry_point"] = ep
        write_canonical(root / "verification" / "scenarios" / "corpus.json", corpus_doc)
        corpus_sha = corpus_digest(load_json(root / "verification" / "scenarios" / "corpus.json"))
        reqs = {sc["id"]: request_of(root, sc) for sc in corpus_doc["scenarios"]}
        from planner.canonical import digest as _digest
        bundle_sha = _digest(load_json(root / "evidence" / "planning" / "evidence-bundle.json"))

        def capture(sc_id: str, base: str, response: dict, effects: list[dict]) -> None:
            """A capture with NO ``before``: an effect-less scenario can have none."""
            write_canonical(root / SCENARIO_ORACLES / (scenario_slug(sc_id) + ".json"), {
                "schema": "rhoai3.source-scenario/v1", "scenario": sc_id, "entry_point": ep,
                "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "status": "CAPTURED", "reason": "",
                "evidence_bundle_sha256": bundle_sha, "source": {"base_url": base},
                "initial_state": corpus_doc["initial_state"], "normalization": [], "reset_before": True,
                "request": {"request_sha256": reqs[sc_id]["request_sha256"]}, "response": response,
                "before": [], "effects": effects,
            })

        # the source: one owner, read cross-origin-style by a plain GET
        Service.owners = {"7": {"id": 7, "lastName": "Franklin"}}
        Service.lie_on_delete = False
        src, src_url = serve()
        from _oracle_common import http_observe
        listed = http_observe(src_url, "GET", "/api/owners")
        capture("sc:list-owners", src_url, {"status": listed["status"], "body_kind": listed["body_kind"],
                                            "body_sha256": listed["body_sha256"], "headers": listed["headers"]}, [])
        deleted = http_observe(src_url, "DELETE", "/api/owners/7")
        gone = http_observe(src_url, "GET", "/api/owners/7")
        capture("sc:delete-owner", src_url, {"status": deleted["status"], "body_kind": deleted["body_kind"], "body_sha256": deleted["body_sha256"]},
                [{"id": "eff:owner-7-gone", "method": "GET", "path": "/api/owners/7", "status": gone["status"], "body_sha256": gone["body_sha256"]}])
        src.shutdown()

        marker = root / "reset-ran.txt"
        reset_cmd = "%s -c %s" % (shlex.quote(sys.executable), shlex.quote("open(%r, 'a').write('x')" % str(marker)))

        # an identical destination PASSes, the declared reset still ran, and
        # the verdict says plainly that there was no before-state to compare
        Service.owners = {"7": {"id": 7, "lastName": "Franklin"}}
        dest, dest_url = serve()
        p = subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", "sc:list-owners",
                            "--dest-url", dest_url, "--reset-cmd", reset_cmd], text=True, capture_output=True)
        v = load_json(root / SCENARIO_PARITY / (scenario_slug("sc:list-owners") + ".json"))
        if p.returncode != 0 or v["verdict"] != "PASS":
            return _fail("an effect-less scenario with no recorded before must compare on the response: rc=%s %s %s"
                         % (p.returncode, v.get("verdict"), (p.stdout + p.stderr)[-400:]))
        if not marker.is_file() or v["reset"].get("ran") is not True:
            return _fail("the declared reset still runs for an effect-less scenario: %s" % v.get("reset"))
        if not str(v.get("before_state") or "").startswith("none declared") or v["before"]:
            return _fail("the verdict states the absence rather than refusing over it: %s" % v.get("before_state"))
        dest.shutdown()

        # a destination whose list differs FAILs, typed by the diff
        Service.owners = {"9": {"id": 9, "lastName": "Davis"}}
        other, other_url = serve()
        p = subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", "sc:list-owners",
                            "--dest-url", other_url, "--reset-cmd", reset_cmd], text=True, capture_output=True)
        v = load_json(root / SCENARIO_PARITY / (scenario_slug("sc:list-owners") + ".json"))
        if p.returncode != 1 or v["verdict"] != "FAIL" or "body" not in v["reason"]:
            return _fail("a divergent effect-less read is a FAIL naming the diff, never INCONCLUSIVE: rc=%s %s %s"
                         % (p.returncode, v.get("verdict"), v.get("reason")))
        other.shutdown()

        # ... and a scenario WITH effects whose capture recorded no before
        # state is still INCONCLUSIVE: those probes were asked for
        Service.owners = {"7": {"id": 7, "lastName": "Franklin"}}
        dest2, dest2_url = serve()
        p = subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", "sc:delete-owner",
                            "--dest-url", dest2_url, "--reset-cmd", reset_cmd], text=True, capture_output=True)
        v = load_json(root / SCENARIO_PARITY / (scenario_slug("sc:delete-owner") + ".json"))
        if p.returncode != 1 or v["verdict"] != "INCONCLUSIVE" or "recorded no initial state" not in v["reason"]:
            return _fail("a scenario with effects and no before state is still INCONCLUSIVE: rc=%s %s %s"
                         % (p.returncode, v.get("verdict"), v.get("reason")))
        dest2.shutdown()
    return 0


def _security_mode_case() -> int:
    """The security mode binds qualification, comparison and the receipt.

    ADR-014: the frozen source is captured once with its security switch
    disabled and once with it enabled, and "mode/configuration identity must
    prevent cross-mode receipt reuse". The control here is that reuse made
    concrete -- the disabled-mode captures copied into the enabled-mode
    directory, which is what a hurried hand would do. Every consumer of that
    directory must refuse it: the qualification gate, the comparator (a
    destination started with security enabled graded against anonymous
    expectations is the defect ADR-014 exists for) and the receipt composer.
    The mode also has to be READABLE afterwards, so it is written into the
    qualification document and the receipt an M4 verdict quotes."""
    import shutil
    corpus_doc = {
        "schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
        "initial_state": {"reset": "restart the service", "dataset": "one owner"},
        "scenarios": [{"id": "sc:list-owners", "entry_point": "", "method": "GET", "path": "/api/owners",
                       "body_absent": True, "reset_before": True, "effects": [], "normalization": []}],
    }
    with tempfile.TemporaryDirectory(prefix="secmode-") as td:
        t = Path(td)
        root = specimens.build_dest(t / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        specimens.prepare_loop(root)
        rec = pipeline.admit(root)
        if rec["status"] != "ADMITTED":
            return _fail("security-mode fixture not admitted: %s" % rec["reasons"][:3])
        receipt_digest = load_json(root / "evidence/planning/admission-receipt.json")["receipt_digest"]
        ep = sorted(str(e["id"]) for e in load_json(root / "evidence/planning/evidence-bundle.json")["entry_points"])[0]
        corpus_doc["scenarios"][0]["entry_point"] = ep
        write_canonical(root / "verification" / "scenarios" / "corpus.json", corpus_doc)
        corpus_sha = corpus_digest(load_json(root / "verification" / "scenarios" / "corpus.json"))
        from planner.canonical import digest as _digest
        bundle_sha = _digest(load_json(root / "evidence" / "planning" / "evidence-bundle.json"))
        req = request_of(root, corpus_doc["scenarios"][0])

        # the disabled-mode capture, in the directory that mode has always used
        Service.owners = {"7": {"id": 7, "lastName": "Franklin"}}
        Service.lie_on_delete = False
        src, src_url = serve()
        from _oracle_common import http_observe
        listed = http_observe(src_url, "GET", "/api/owners")
        src.shutdown()
        write_canonical(root / scenario_oracles_dir("disabled") / (scenario_slug("sc:list-owners") + ".json"), {
            "schema": "rhoai3.source-scenario/v1", "scenario": "sc:list-owners", "entry_point": ep,
            "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "status": "CAPTURED", "reason": "",
            "evidence_bundle_sha256": bundle_sha, "source": {"base_url": src_url},
            "initial_state": corpus_doc["initial_state"], "normalization": [], "reset_before": True,
            "security_mode": "disabled",
            "request": {"request_sha256": req["request_sha256"]},
            "response": {"status": listed["status"], "body_kind": listed["body_kind"],
                         "body_sha256": listed["body_sha256"], "headers": listed["headers"]},
            "before": [], "effects": [],
        })
        write_canonical(root / capture_receipt_path("disabled"), {
            "schema": "rhoai3.source-capture/v1", "producer": "capture-source-scenarios.py", "at": "2026-09-15T00:00:00Z",
            "status": "ok", "reason": "", "evidence_bundle_sha256": bundle_sha, "corpus_sha256": corpus_sha,
            "receipt_sha256": receipt_digest, "receipt_note": "", "security_mode": "disabled", "source_config": {},
            "credential_refs": [], "captured": 1, "requested": 1, "scenarios": ["sc:list-owners"], "reads": False,
            "source": {"analysis_copy_digest": "fixture", "starts": 1}})

        # the qualification names the mode it judged
        p = subprocess.run([sys.executable, str(QUALIFY), "--root", str(root)], text=True, capture_output=True)
        qdoc = load_json(root / qualification_path("disabled"))
        if p.returncode != 0 or qdoc.get("security_mode") != "disabled":
            return _fail("the qualification must record the mode it judged: rc=%s %s" % (p.returncode, qdoc.get("security_mode")))

        # a comparison in the default mode still works, and says which mode it was
        Service.owners = {"7": {"id": 7, "lastName": "Franklin"}}
        dest, dest_url = serve()
        p = subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", "sc:list-owners",
                            "--dest-url", dest_url, "--no-reset"], text=True, capture_output=True)
        v = load_json(root / scenario_parity_dir("disabled") / (scenario_slug("sc:list-owners") + ".json"))
        if p.returncode != 0 or v["verdict"] != "PASS" or v.get("security_mode") != "disabled":
            return _fail("the default mode keeps its paths and names itself: rc=%s %s %s"
                         % (p.returncode, v.get("verdict"), v.get("security_mode")))

        # the receipt of that mode records it, so an M4 verdict can name the
        # mode it judged rather than leaving a reader to guess
        subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        rdoc = load_json(root / parity_receipt_path("disabled"))
        if rdoc.get("security_mode") != "disabled":
            return _fail("the parity receipt must record the mode it is of: %s" % rdoc.get("security_mode"))

        # cross-mode REUSE: the disabled captures copied into the enabled
        # directory. Every consumer refuses; none of them re-judges.
        # The corpus is copied with them, so what each consumer refuses is the
        # CAPTURE's mode and not a corpus nobody derived: every one of them
        # now reads the corpus of the mode it was asked for, and the enabled
        # run would otherwise stop at the missing enabled corpus first.
        shutil.copytree(str(root / scenario_oracles_dir("disabled")), str(root / scenario_oracles_dir("enabled")))
        shutil.copytree(str(root / "verification" / "scenarios"), str(root / "verification" / "scenarios-enabled"))
        p = subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", "sc:list-owners",
                            "--dest-url", dest_url, "--no-reset", "--security-mode", "enabled"], text=True, capture_output=True)
        if p.returncode != 1 or "REFUSE: SCENARIO_PARITY mode mismatch" not in p.stderr:
            return _fail("a capture from another mode must refuse the comparison: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        ev = load_json(root / scenario_parity_dir("enabled") / (scenario_slug("sc:list-owners") + ".json"))
        if ev["verdict"] != "INCONCLUSIVE" or ev.get("captured_security_mode") != "disabled" or ev.get("security_mode") != "enabled":
            return _fail("the refused comparison records both modes: %s" % {k: ev.get(k) for k in ("verdict", "security_mode", "captured_security_mode")})
        dest.shutdown()
        p = subprocess.run([sys.executable, str(QUALIFY), "--root", str(root), "--security-mode", "enabled"], text=True, capture_output=True)
        if p.returncode != 1 or "REFUSE: QUALIFY_CAPTURES mode mismatch" not in p.stderr:
            return _fail("the qualification gate must refuse another mode's captures: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        # the copy carried the disabled mode's qualification along with it;
        # the refusal must leave it exactly as it found it rather than
        # re-stamping another mode's verdicts as this one's
        copied = load_json(root / qualification_path("enabled"))
        if copied.get("security_mode") != "disabled":
            return _fail("a refusal to judge rewrites nothing: %s" % copied.get("security_mode"))
        p = subprocess.run([sys.executable, str(RECEIPT), "--root", str(root), "--security-mode", "enabled"], text=True, capture_output=True)
        if p.returncode != 1 or "REFUSE: PARITY_RECEIPT mode mismatch" not in p.stderr:
            return _fail("the receipt composer must refuse to mix modes: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        if (root / parity_receipt_path("enabled")).exists():
            return _fail("a refused receipt is not written")
    return 0


class GuardedService(BaseHTTPRequestHandler):
    """A service with its security switch ON: it refuses what it cannot
    authenticate, and answers what it can. A refused DELETE changes nothing."""

    expected = ""
    owners: dict = {}
    seen: list = []

    def _answer(self, code: int, payload=None) -> None:
        body = json.dumps(payload).encode() if payload is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _authenticated(self) -> bool:
        type(self).seen.append((self.command, self.path, bool(self.headers.get("Authorization"))))
        return self.headers.get("Authorization") == type(self).expected

    def do_GET(self):  # noqa: N802
        if not self._authenticated():
            return self._answer(401, {"error": "unauthorized"})
        return self._answer(200, sorted(type(self).owners))

    def do_DELETE(self):  # noqa: N802
        if not self._authenticated():
            return self._answer(401, {"error": "unauthorized"})
        type(self).owners.pop(self.path.rsplit("/", 1)[-1], None)
        return self._answer(204)

    def log_message(self, *a):  # noqa: D102
        return


def _effects_identity_parity_case() -> int:
    """The destination's read-backs are taken as the scenario's effects
    identity too.

    A refused write's state is only observable to an identity the policy
    accepts: the source capture's before/after rows were taken as that one,
    so probing the destination as the refused caller would compare a 200 the
    source recorded against a 401 the destination answered -- two different
    questions, reported as a destination defect. The controls: an identical
    guarded destination PASSes, its read-back probes carried the credential
    while the write itself stayed anonymous, and a capture that took the
    read-backs as somebody else is refused rather than compared."""
    import os
    from _oracle_common import http_observe
    from _scenarios import corpus_path
    from planner.canonical import digest as _digest

    ref, sid = "TEST_PARITY_EFFECTS_CREDENTIAL", "sc:auth-anonymous-delete-owners-7"
    user, secret = "an-identity-the-policy-allows", "n0t-in-the-evidence"
    token = "Basic %s" % base64.b64encode(("%s:%s" % (user, secret)).encode("utf-8")).decode("ascii")
    eff = {"id": "eff:owners-after-denied-delete", "method": "GET", "path": "/api/owners"}
    kept = os.environ.get(ref)
    os.environ[ref] = "%s:%s" % (user, secret)
    src_handler = type("SrcGuarded", (GuardedService,), {"expected": token, "owners": {"7": {"id": 7}}, "seen": []})
    dest_handler = type("DestGuarded", (GuardedService,), {"expected": token, "owners": {"7": {"id": 7}}, "seen": []})
    src = HTTPServer(("127.0.0.1", 0), src_handler)
    dest = HTTPServer(("127.0.0.1", 0), dest_handler)
    for s in (src, dest):
        threading.Thread(target=s.serve_forever, daemon=True).start()
    src_url = "http://127.0.0.1:%d" % src.server_address[1]
    dest_url = "http://127.0.0.1:%d" % dest.server_address[1]
    try:
        with tempfile.TemporaryDirectory(prefix="effects-identity-parity-") as td:
            root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
            specimens.prepare_loop(root)
            if pipeline.admit(root)["status"] != "ADMITTED":
                return _fail("the effects-identity fixture must be admitted")
            receipt_digest = load_json(root / "evidence/planning/admission-receipt.json")["receipt_digest"]
            bundle_sha = _digest(load_json(root / "evidence" / "planning" / "evidence-bundle.json"))
            ep = sorted(str(e["id"]) for e in load_json(root / "evidence/planning/evidence-bundle.json")["entry_points"])[0]
            sc = {"id": sid, "entry_point": ep, "method": "DELETE", "path": "/api/owners/7", "headers": {},
                  "identity": {"kind": "none"}, "body_absent": True, "reset_before": False,
                  "effects": [dict(eff)], "normalization": [],
                  "effects_identity": {"kind": "basic", "credential_ref": ref},
                  "qualify": {"intent": "negative", "expect_status_class": "4xx", "after_equals_before": True}}
            corpus_doc = {"schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
                          "initial_state": {"reset": "restart the service", "dataset": "one owner"},
                          "security_mode": "enabled", "scenarios": [sc]}
            write_canonical(root / corpus_path("enabled"), corpus_doc)
            corpus_sha = corpus_digest(load_json(root / corpus_path("enabled")))
            req = request_of(root, sc)

            # what the SOURCE did: the read-backs as the accepted identity,
            # the write itself as the caller the source refuses
            auth = {"Authorization": token}
            before = http_observe(src_url, "GET", eff["path"], headers=auth)
            refused = http_observe(src_url, "DELETE", sc["path"])
            after = http_observe(src_url, "GET", eff["path"], headers=auth)
            if (before["status"], refused["status"], after["status"]) != (200, 401, 200):
                return _fail("the fixture source must refuse the anonymous write and answer the authenticated read-backs: %s"
                             % [before["status"], refused["status"], after["status"]])
            capture = {
                "schema": "rhoai3.source-scenario/v1", "scenario": sid, "entry_point": ep,
                "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "status": "CAPTURED", "reason": "",
                "evidence_bundle_sha256": bundle_sha, "source": {"base_url": src_url},
                "initial_state": corpus_doc["initial_state"], "normalization": [], "reset_before": False,
                "security_mode": "enabled",
                "effects_identity": {"kind": "basic", "user_env": "", "password_env": "", "credential_ref": ref},
                "request": {"request_sha256": req["request_sha256"]},
                "response": {"status": refused["status"], "body_kind": refused["body_kind"],
                             "body_sha256": refused["body_sha256"], "headers": refused["headers"]},
                "before": [{"id": eff["id"], "method": "GET", "path": eff["path"], "status": before["status"],
                            "body_kind": before["body_kind"], "body_sha256": before["body_sha256"]}],
                "effects": [{"id": eff["id"], "method": "GET", "path": eff["path"], "status": after["status"],
                             "body_kind": after["body_kind"], "body_sha256": after["body_sha256"]}],
            }
            out = root / scenario_oracles_dir("enabled") / (scenario_slug(sid) + ".json")
            write_canonical(out, capture)

            dest_handler.seen = []
            p = subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", sid,
                                "--dest-url", dest_url, "--no-reset", "--security-mode", "enabled"], text=True, capture_output=True)
            v = load_json(root / scenario_parity_dir("enabled") / (scenario_slug(sid) + ".json"))
            if p.returncode != 0 or v["verdict"] != "PASS":
                return _fail("an identical guarded destination PASSes: rc=%s %s %s" % (p.returncode, v.get("verdict"), v.get("reason")))
            if v.get("effects_identity") != {"kind": "basic", "user_env": "", "password_env": "", "credential_ref": ref}:
                return _fail("the verdict records whose read-backs it took, by reference: %s" % v.get("effects_identity"))
            if ("DELETE", "/api/owners/7", False) not in dest_handler.seen:
                return _fail("the replayed write is the anonymous one the source sent: %s" % dest_handler.seen)
            if [row for row in dest_handler.seen if row[0] == "GET"] != [("GET", eff["path"], True)] * 2:
                return _fail("both read-backs are taken as the effects identity, or the destination answers 401 to a question "
                             "the source answered 200: %s" % dest_handler.seen)
            if secret in json.dumps(v) or token in json.dumps(v):
                return _fail("only the reference travels into the verdict")

            # a capture that took the read-backs as somebody else is not
            # compared at all: its rows answer another question
            capture.pop("effects_identity")
            write_canonical(out, capture)
            p = subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", sid,
                                "--dest-url", dest_url, "--no-reset", "--security-mode", "enabled"], text=True, capture_output=True)
            v = load_json(root / scenario_parity_dir("enabled") / (scenario_slug(sid) + ".json"))
            if p.returncode != 1 or v["verdict"] != "INCONCLUSIVE" or "credential_ref %s" % ref not in v["reason"]:
                return _fail("read-backs of two identities are not comparable, and the refusal names both: rc=%s %s"
                             % (p.returncode, v.get("reason")))
    finally:
        for s in (src, dest):
            s.shutdown()
        if kept is None:
            os.environ.pop(ref, None)
        else:
            os.environ[ref] = kept
    return 0


def _missing_exposed_model_case() -> int:
    """Missing or unreadable exposure evidence must refuse before source setup."""
    import contextlib
    import importlib.util
    import io
    from unittest.mock import patch
    from planner.paths import STRUCTURE, producer_receipt

    spec = importlib.util.spec_from_file_location("capture_scenarios_test", HERE / "capture-source-scenarios.py")
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)
    with tempfile.TemporaryDirectory(prefix="capture-model-") as td:
        root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        specimens.prepare_loop(root)
        frozen = root / "frozen"
        frozen.mkdir()
        (frozen / "pom.xml").write_text("<project/>")
        write_canonical(producer_receipt(root, "freeze"), {"analysis_copy": str(frozen), "source_digest": "fixture"})
        write_canonical(root / "verification/scenarios/corpus.json", {
            "schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
            "scenarios": [{"id": "sc:read", "entry_point": "ep:test", "method": "GET", "path": "/api/owners", "body_absent": True}]})
        model = root / STRUCTURE
        model.unlink(missing_ok=True)
        for malformed in (False, True):
            if malformed:
                model.parent.mkdir(parents=True, exist_ok=True)
                model.write_text("{invalid-json")
            errors = io.StringIO()
            with patch.object(producer, "SourceRuntime", side_effect=AssertionError("source must not start")) as runtime:
                with contextlib.redirect_stderr(errors):
                    result = producer.main(["--root", str(root), "--base-path", "/petclinic"])
                if result != 1 or runtime.called or "FAIL: SOURCE_SCENARIOS" not in errors.getvalue() or "nothing is captured" not in errors.getvalue():
                    return _fail("an unreadable exposure model refuses before source setup: %s" % errors.getvalue())
    return 0


def _stale_receipt_case() -> int:
    """A receipt that is not authoritative (the work list rebuilt after the
    seal, the normal state beside the M3 loop -- v9, 2026-09-14) does not stop
    the producer: the capture is bound to the frozen source and the corpus,
    the receipt digest is simply not recorded, and the gaps are noted."""
    import contextlib
    import importlib.util
    import io
    from unittest.mock import patch
    from planner.paths import producer_receipt

    spec = importlib.util.spec_from_file_location("capture_scenarios_stale", HERE / "capture-source-scenarios.py")
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)

    class Reached(Exception):
        pass

    with tempfile.TemporaryDirectory(prefix="capture-stale-") as td:
        root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        specimens.prepare_loop(root)
        if pipeline.admit(root)["status"] != "ADMITTED":
            return _fail("stale-receipt fixture not admitted")
        frozen = root / "frozen"
        frozen.mkdir()
        (frozen / "pom.xml").write_text("<project/>")
        write_canonical(producer_receipt(root, "freeze"), {"analysis_copy": str(frozen), "source_digest": "fixture"})
        write_canonical(root / "verification/scenarios/corpus.json", {
            "schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
            "scenarios": [{"id": "sc:read", "entry_point": "ep:test", "method": "GET", "path": "/api/owners", "body_absent": True}]})
        wl = root / "evidence" / "planning" / "worklist.json"
        touched = load_json(wl)
        touched["_rebuilt_after_seal"] = True
        write_canonical(wl, touched)
        if not verify_gaps(root):
            return _fail("the fixture receipt must be stale for this case")
        errors = io.StringIO()
        with patch.object(producer, "SourceRuntime", side_effect=Reached("the producer reached the source runtime")):
            with contextlib.redirect_stderr(errors):
                try:
                    producer.main(["--root", str(root), "--base-path", "/petclinic"])
                    return _fail("the fixture never reached the runtime: %s" % errors.getvalue())
                except Reached:
                    pass
        if "not authoritative" in errors.getvalue() or "admission receipt not recorded" not in errors.getvalue():
            return _fail("a stale receipt is a note, never a refusal: %s" % errors.getvalue())
        # the idle receipt path records the note too
        (root / "verification/scenarios/corpus.json").unlink()
        p = subprocess.run([sys.executable, str(HERE / "capture-source-scenarios.py"), "--root", str(root)], text=True, capture_output=True)
        rec = load_json(root / SCENARIO_ORACLES / "_capture.json")
        if p.returncode != 0 or rec["receipt_sha256"] != "" or "worklist digest" not in rec.get("receipt_note", "") or not rec["evidence_bundle_sha256"]:
            return _fail("the producer receipt says the admission receipt was not recorded and why: rc=%s %s" % (p.returncode, rec))
    return 0


def _acceptance_binding_case() -> int:
    """A verdict produced during an acceptance verify is of the CANDIDATE.

    Measured on destination v9, card t_222c582a (the PARITY_CORS obligation,
    attempt 4): the worker wrote the right CORS properties, the acceptance
    path re-ran the comparison, and the scenario came back INCONCLUSIVE with
    "receipt not authoritative: worklist digest 26403fd1ecb0 != sealed
    eceefe4d20b9". Nothing was wrong with the repair: run-verify.sh REBUILDS
    the work list on the candidate before the parity stage runs, so the live
    seal's worklist digest is the accepted tree's and can never match. The
    composer refused for the same reason, the stale FAIL stayed on disk, and
    advance.py reverted the card -- as it did every parity card.

    So: with --issued the comparison does not ask the live seal to match the
    rebuilt list, and binds the verdict to what CAN be bound -- the candidate
    this verification recorded, the receipt the card was minted under, and the
    card. Without it, nothing changes: the M4 road still refuses a stale seal.
    What cannot be bound is refused BY NAME: another receipt, another
    candidate, another card, no issued card at all."""
    from planner.canonical import digest as _digest
    from planner.paths import ADMISSION_RECEIPT, LOOP_ISSUED, VERIFY_RUN, WORKLIST
    from _scenarios import BINDING_CANDIDATE, candidate_binding, product_tree_digest

    corpus_doc = {
        "schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
        "initial_state": {"reset": "restart the service", "dataset": "one owner"},
        "scenarios": [{"id": "sc:list-owners", "entry_point": "", "method": "GET", "path": "/api/owners",
                       "body_absent": True, "reset_before": True, "effects": [], "normalization": []}],
    }
    with tempfile.TemporaryDirectory(prefix="acceptbind-") as td:
        root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        specimens.prepare_loop(root)
        if pipeline.admit(root)["status"] != "ADMITTED":
            return _fail("the acceptance-binding fixture must be admitted")
        receipt_digest = load_json(root / ADMISSION_RECEIPT)["receipt_digest"]
        bundle_sha = _digest(load_json(root / "evidence" / "planning" / "evidence-bundle.json"))
        ep = sorted(str(e["id"]) for e in load_json(root / "evidence/planning/evidence-bundle.json")["entry_points"])[0]
        corpus_doc["scenarios"][0]["entry_point"] = ep
        write_canonical(root / "verification" / "scenarios" / "corpus.json", corpus_doc)
        corpus_sha = corpus_digest(load_json(root / "verification" / "scenarios" / "corpus.json"))
        req = request_of(root, corpus_doc["scenarios"][0])
        slugged = scenario_slug("sc:list-owners") + ".json"

        # the source, captured at M1
        from _oracle_common import http_observe
        Service.owners = {"7": {"id": 7, "lastName": "Franklin"}}
        Service.lie_on_delete = False
        src, src_url = serve()
        listed = http_observe(src_url, "GET", "/api/owners")
        src.shutdown()
        write_canonical(root / SCENARIO_ORACLES / slugged, {
            "schema": "rhoai3.source-scenario/v1", "scenario": "sc:list-owners", "entry_point": ep,
            "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "status": "CAPTURED", "reason": "",
            "evidence_bundle_sha256": bundle_sha, "source": {"base_url": src_url},
            "initial_state": corpus_doc["initial_state"], "normalization": [], "reset_before": True,
            "request": {"request_sha256": req["request_sha256"]},
            "response": {"status": listed["status"], "body_kind": listed["body_kind"],
                         "body_sha256": listed["body_sha256"], "headers": listed["headers"]},
            "before": [], "effects": [],
        })

        # the acceptance path's own state: the work list has been rebuilt on
        # the candidate (so the seal is stale), a card is issued, and the
        # verification recorded which tree it measured
        wl = load_json(root / WORKLIST)
        wl["_rebuilt_on_the_candidate"] = True
        write_canonical(root / WORKLIST, wl)
        if not any("worklist digest" in g for g in verify_gaps(root)):
            return _fail("the fixture must reproduce the stale seal: %s" % verify_gaps(root))
        card = "t_222c582a"
        issued = {"schema": "rhoai3.loop-issued/v1", "cluster": "c:parity", "task_id": card, "attempt": 4,
                  "gate": "parity", "receipt_sha256": receipt_digest, "items": ["parity:0123456789abcdef"],
                  "write_set": ["src/main/resources/application.properties"]}
        write_canonical(root / LOOP_ISSUED, issued)
        on_tree = product_tree_digest(root)
        write_canonical(root / VERIFY_RUN, {"schema": "rhoai3.verify-run/v1", "mode": "acceptance",
                                            "candidate_sha256": on_tree})

        # the product-tree identity this binding is about is the loop's own:
        # one definition of what a product path is, one recipe, two callers
        sys.path.insert(0, str(HERE.parents[2] / "migration" / "fix-until-green" / "scripts"))
        from _loop_common import candidate_sha256 as loop_candidate_sha256
        if loop_candidate_sha256(root) != on_tree:
            return _fail("the candidate a comparison binds to must be the candidate the loop measures")

        Service.owners = {"7": {"id": 7, "lastName": "Franklin"}}
        dest, dest_url = serve()
        try:
            base = [sys.executable, str(COMPARE), "--root", str(root), "--scenario", "sc:list-owners",
                    "--dest-url", dest_url, "--no-reset"]
            issued_p = str(root / LOOP_ISSUED)

            # 1. the M4 road, unchanged: a stale seal refuses
            p = subprocess.run(base, text=True, capture_output=True)
            v = load_json(root / SCENARIO_PARITY / slugged)
            if p.returncode != 1 or v["verdict"] != "INCONCLUSIVE" or "worklist digest" not in v["reason"]:
                return _fail("without --issued a stale seal still refuses: rc=%s %s" % (p.returncode, v.get("reason")))
            if (v.get("binding") or {}).get("mode") != "sealed":
                return _fail("a verdict of the accepted tree is sealed-bound: %s" % v.get("binding"))

            # 2. the acceptance path: the same stale seal, and the comparison
            #    is a measurement of the candidate
            p = subprocess.run(base + ["--issued", issued_p], text=True, capture_output=True)
            v = load_json(root / SCENARIO_PARITY / slugged)
            if p.returncode != 0 or v["verdict"] != "PASS":
                return _fail("with --issued the rebuilt work list is not a refusal: rc=%s %s %s"
                             % (p.returncode, v.get("verdict"), (p.stdout + p.stderr)[-400:]))
            want = {"mode": BINDING_CANDIDATE, "candidate_sha256": on_tree,
                    "issued_receipt_sha256": receipt_digest, "card": card}
            if v.get("binding") != want or v.get("receipt_sha256") != receipt_digest:
                return _fail("the verdict records what it is bound to: %s / %s" % (v.get("binding"), v.get("receipt_sha256")))

            # 3. the receipt: the composer refuses the stale seal on the M4
            #    road and composes on the acceptance path, recording the same
            #    binding
            p = subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
            if p.returncode != 1 or "receipt not authoritative" not in p.stderr:
                return _fail("without --issued the composer still refuses a stale seal: rc=%s %s" % (p.returncode, p.stderr[-300:]))
            subprocess.run([sys.executable, str(RECEIPT), "--root", str(root), "--issued", issued_p], text=True, capture_output=True)
            rdoc = load_json(root / parity_receipt_path("disabled"))
            # the whole receipt is INCONCLUSIVE here -- this specimen's other
            # entry points have no read oracle -- but the scenario's own row is
            # the one the acceptance path asks about, and it was composed
            row = next(r for r in rdoc["entry_points"] if r["entry_point"] == ep)
            if row["verdict"] != "PASS" or row["scenarios"] != ["sc:list-owners"]:
                return _fail("the composer must compose the candidate's verdict: %s" % row)
            if rdoc.get("binding") != want or rdoc.get("receipt_sha256") != receipt_digest:
                return _fail("the receipt records what it is of: %s / %s" % (rdoc.get("binding"), rdoc.get("receipt_sha256")))

            # 4. a verdict measured for ANOTHER card satisfies nothing: the
            #    composer names the card rather than counting it as coverage
            foreign = load_json(root / SCENARIO_PARITY / slugged)
            foreign["binding"] = dict(want, card="t_somebodyelse")
            write_canonical(root / SCENARIO_PARITY / slugged, foreign)
            p = subprocess.run([sys.executable, str(RECEIPT), "--root", str(root), "--issued", issued_p], text=True, capture_output=True)
            rdoc = load_json(root / parity_receipt_path("disabled"))
            row = next(r for r in rdoc["entry_points"] if r["entry_point"] == ep)
            if p.returncode != 1 or row["verdict"] != "INCONCLUSIVE" or "t_somebodyelse" not in row["reason"]:
                return _fail("a verdict measured for another card must not satisfy coverage: rc=%s %s" % (p.returncode, row))
            # ... and one measured on another candidate, likewise
            foreign["binding"] = dict(want, candidate_sha256="0" * 64)
            write_canonical(root / SCENARIO_PARITY / slugged, foreign)
            subprocess.run([sys.executable, str(RECEIPT), "--root", str(root), "--issued", issued_p], text=True, capture_output=True)
            row = next(r for r in load_json(root / parity_receipt_path("disabled"))["entry_points"] if r["entry_point"] == ep)
            if row["verdict"] != "INCONCLUSIVE" or "the candidate" not in row["reason"]:
                return _fail("a verdict measured on another candidate must not satisfy coverage: %s" % row)

            # 5. what CANNOT be bound is refused by name, before anything is
            #    compared: another receipt, another candidate, no issued card
            for argv, needle in (
                (base + ["--issued", issued_p, "--issued-receipt", "0" * 64], "--issued-receipt"),
                (base + ["--issued", issued_p, "--candidate", "0" * 64], "--candidate"),
                (base + ["--issued", str(root / "verification" / "loop" / "nothing.json")], "issued card is absent"),
            ):
                p = subprocess.run(argv, text=True, capture_output=True)
                v = load_json(root / SCENARIO_PARITY / slugged)
                if p.returncode != 1 or v["verdict"] != "INCONCLUSIVE" or needle not in v["reason"]:
                    return _fail("the binding refuses %r by name: rc=%s %s" % (needle, p.returncode, v.get("reason")))

            # H10 (dest v9 t_56adcd76): the binding is to the receipt the card
            # was MINTED under (issued.json), never to whatever
            # admission-receipt.json says now -- a concurrent re-seal after the
            # mint is a NOTE, and the binding is still made
            write_canonical(root / LOOP_ISSUED, dict(issued, receipt_sha256="0" * 64))
            notes: list = []
            made, gaps = candidate_binding(root, issued_path=issued_p, notes=notes)
            if gaps or made.get("issued_receipt_sha256") != "0" * 64 or not any("names another receipt" in n and "minted under" in n for n in notes):
                return _fail("an issued card minted under another receipt binds to THAT receipt and notes the mismatch: %s %s %s" % (made, gaps, notes))
            write_canonical(root / LOOP_ISSUED, issued)

            # the candidate in run.json must be the tree being compared: an
            # edit after verification is not what the card was verified on
            props = root / "src" / "main" / "resources" / "application.properties"
            props.parent.mkdir(parents=True, exist_ok=True)
            props.write_text((props.read_text(encoding="utf-8") if props.is_file() else "") + "\n# edited after verification\n", encoding="utf-8")
            p = subprocess.run(base + ["--issued", issued_p], text=True, capture_output=True)
            v = load_json(root / SCENARIO_PARITY / slugged)
            if p.returncode != 1 or "is not the tree this comparison is about" not in v["reason"]:
                return _fail("a tree edited after verification refuses by name: rc=%s %s" % (p.returncode, v.get("reason")))
            if candidate_binding(root, issued_path=issued_p)[0]:
                return _fail("a binding that cannot be made is not returned anyway")
        finally:
            dest.shutdown()
    return 0


def _navigation_receipt_case() -> int:
    """A comparison that PASSed and a redirect target that answers nothing.

    ADR-016 does not stop at the status and the literal Location: that legacy
    address must also serve the replacement UI or redirect to its effective
    address, and a bounded navigation must reach it. The comparator compares
    the FIRST response and never follows a redirect -- by design -- so a 302
    to a 404 is a PASS there and nothing measured the rest of the ruling. The
    navigation record run-parity.py writes beside the comparison is what the
    composer reads; the address below belongs to no specimen."""
    import tempfile as _tempfile

    from _oracle_common import PARITY as _PARITY

    sid = "sc:read-legacy-root"
    target = "http://dest.example:8080/legacy-docs/index.html"
    with _tempfile.TemporaryDirectory(prefix="nav-receipt-") as td:
        root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        specimens.prepare_loop(root)
        rec = pipeline.admit(root)
        if rec["status"] != "ADMITTED":
            return _fail("fixture not admitted: %s" % rec["reasons"][:3])
        receipt_digest = load_json(root / "evidence/planning/admission-receipt.json")["receipt_digest"]
        ep = sorted(str(e["id"]) for e in load_json(root / "evidence/planning/evidence-bundle.json")["entry_points"])[0]
        corpus = {"schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
                  "initial_state": {"reset": "restart the service", "dataset": "empty"},
                  "scenarios": [{"id": sid, "entry_point": ep, "method": "GET", "path": "/", "body_absent": True,
                                 "reset_before": False, "effects": [], "normalization": []}]}
        write_canonical(root / "verification" / "scenarios" / "corpus.json", corpus)
        corpus_sha = corpus_digest(load_json(root / "verification" / "scenarios" / "corpus.json"))
        # the comparison PASSED: the destination answered the source's status
        # and the source's literal Location after origin mapping
        write_canonical(root / SCENARIO_PARITY / (scenario_slug(sid) + ".json"),
                        {"schema": "rhoai3.scenario-parity/v1", "scenario": sid, "entry_point": ep,
                         "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "verdict": "PASS",
                         "reason": ""})
        nav_p = root / _PARITY / "navigation" / (scenario_slug(sid) + ".json")

        docs: list = []

        def compose() -> dict:
            subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
            doc = load_json(root / "verification" / "parity" / "receipt.json")
            docs.append(doc)
            return next(r for r in doc["entry_points"] if r["entry_point"] == ep)

        write_canonical(nav_p, {"schema": "rhoai3.parity-navigation/v1", "scenario": sid, "entry_point": ep,
                                "start": target, "hops": [{"url": target, "status": 200}],
                                "final_status": 200, "terminal": "ok"})
        row = compose()
        if row["verdict"] != "PASS" or row.get("navigation") != "ok" or row.get("kind"):
            return _fail("a navigation that reached the UI leaves the verdict alone and is recorded on the row: %s" % row)

        for terminal, final in (("dead", 404), ("loop", 302), ("too-many-hops", 302)):
            write_canonical(nav_p, {"schema": "rhoai3.parity-navigation/v1", "scenario": sid, "entry_point": ep,
                                    "start": target, "hops": [{"url": target, "status": final}],
                                    "final_status": final, "terminal": terminal})
            row = compose()
            want = "redirect target %s is %s on the destination (%s)" % (target, terminal, final)
            fails = [{"scenario": sid, "target": target, "terminal": terminal, "final_status": final}]
            # ADR-020: the redirect keeps its PASS; reachability is its own row
            if row["verdict"] != "PASS" or row.get("kind") or row.get("navigation") != "failed":
                return _fail("a correct first response keeps its PASS while navigation fails separately (%s): %s"
                             % (terminal, row))
            if row.get("navigation_failures") != fails:
                return _fail("the row names the navigation failure beside its PASS: %s" % row.get("navigation_failures"))
            obligations = docs[-1].get("navigation_obligations") or []
            if obligations != [{"entry_point": ep, "kind": "navigation", "verdict": "FAIL", "scenarios": [sid],
                                "reason": want, "navigation_failures": fails}]:
                return _fail("the navigation failure is its own obligation row: %s" % obligations)
            if docs[-1]["verdict"] != "FAIL" or docs[-1]["not_passed"] != sum(1 for r in docs[-1]["entry_points"] if r["verdict"] != "PASS"):
                return _fail("the receipt fails on the obligation without counting the redirect as not passed: %s %s"
                             % (docs[-1]["verdict"], docs[-1]["not_passed"]))

        # a comparison that FAILED is not re-typed by a navigation: the diff
        # is what the card repairs, and it is still the diff
        write_canonical(root / SCENARIO_PARITY / (scenario_slug(sid) + ".json"),
                        {"schema": "rhoai3.scenario-parity/v1", "scenario": sid, "entry_point": ep,
                         "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "verdict": "FAIL",
                         "reason": "status 303 vs 302"})
        row = compose()
        if row["verdict"] != "FAIL" or row.get("kind") == "navigation" or "303" not in row["reason"]:
            return _fail("a failing comparison keeps its own diff and its own typing: %s" % row)
        if docs[-1].get("navigation_obligations"):
            return _fail("a failing comparison is not also a navigation obligation: %s" % docs[-1]["navigation_obligations"])
    return 0


def _diagnostic_probe_case() -> int:
    """ADR-021: a diagnostic probe gates nothing, and cannot be relabelled.

    A probe's mismatch is a diagnostic result -- visible under
    ``diagnostics``, zero obligations, no effect on the entry point's
    verdict, ``not_passed`` or the receipt -- while the same mismatch in a
    required contract scenario still fails. The classification is bound at
    capture and fixed by the first recorded result: a corpus that relabels a
    compared scenario (either way) is refused, by the comparator and by the
    composer, which then counts the scenario as required."""
    from _scenarios import classification_ledger_path
    sid_req, sid_probe = "sc:cors-actual-x", "sc:cors-probe-x"
    with tempfile.TemporaryDirectory(prefix="diag-probe-") as td:
        root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        specimens.prepare_loop(root)
        if pipeline.admit(root)["status"] != "ADMITTED":
            return _fail("the diagnostic fixture must be admitted")
        receipt_digest = load_json(root / "evidence/planning/admission-receipt.json")["receipt_digest"]
        ep = sorted(str(e["id"]) for e in load_json(root / "evidence/planning/evidence-bundle.json")["entry_points"])[0]
        origin = {"Origin": "http://parity.invalid:4200"}
        probe = {"id": sid_probe, "entry_point": ep, "method": "OPTIONS", "path": "/api/owners", "reset_before": False,
                 "headers": dict(origin, **{"Access-Control-Request-Method": "POST"}), "body_absent": True,
                 "identity": {"kind": "basic", "credential_ref": "TEST_PROBE_CREDENTIAL"}, "effects": [],
                 "normalization": [], "cors_policy": "cors:x", "scenario_type": "diagnostic-probe"}
        required = {"id": sid_req, "entry_point": ep, "method": "GET", "path": "/api/owners", "reset_before": False,
                    "headers": dict(origin), "body_absent": True, "effects": [], "normalization": [],
                    "cors_policy": "cors:x", "scenario_type": "cors-actual"}
        corpus = {"schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
                  "initial_state": {"reset": "restart", "dataset": "empty"},
                  "cors_policies": [{"id": "cors:x", "request_headers": []}], "scenarios": [required, probe]}
        cp = root / "verification" / "scenarios" / "corpus.json"
        write_canonical(cp, corpus)
        try:
            load_corpus(root)
        except Exception as exc:
            return _fail("the loader admits a credentialed OPTIONS typed as a diagnostic probe: %s" % exc)
        corpus_sha = corpus_digest(load_json(cp))

        def verdict(sid: str, v: str, stype: str) -> None:
            write_canonical(root / SCENARIO_PARITY / (scenario_slug(sid) + ".json"),
                            {"schema": "rhoai3.scenario-parity/v1", "scenario": sid, "entry_point": ep,
                             "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "verdict": v,
                             "reason": "" if v == "PASS" else "header Access-Control-Allow-Origin None vs *",
                             "scenario_type": stype})

        def compose() -> tuple[dict, dict]:
            subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
            doc = load_json(root / "verification" / "parity" / "receipt.json")
            return doc, next(r for r in doc["entry_points"] if r["entry_point"] == ep)

        verdict(sid_req, "PASS", "cors-actual")
        verdict(sid_probe, "FAIL", "diagnostic-probe")
        doc, row = compose()
        diag = (doc.get("diagnostics") or {}).get(sid_probe) or {}
        if row["verdict"] != "PASS" or sid_probe in row["scenarios"] or "FAIL" in row["reason"]:
            return _fail("a probe's mismatch does not touch its entry point's verdict: %s" % row)
        if (diag.get("verdict") != "FAIL" or diag.get("gating") is not False or diag.get("obligations") != 0
                or diag.get("browser_coverage") is not False):
            return _fail("the probe's result is visible as a non-gating diagnostic: %s" % diag)
        if doc["not_passed"] != sum(1 for r in doc["entry_points"] if r["verdict"] != "PASS") or sid_probe in json.dumps(doc["entry_points"]):
            return _fail("the probe is counted nowhere in the mandatory aggregation: %s" % doc["entry_points"])
        # the same mismatch in the required contract scenario still fails
        verdict(sid_req, "FAIL", "cors-actual")
        doc, row = compose()
        if row["verdict"] != "FAIL":
            return _fail("a required scenario's mismatch still fails: %s" % row)
        verdict(sid_req, "PASS", "cors-actual")

        # relabelling after a result exists is refused: the ledger fixed the
        # probe as a contract scenario the first time it was compared
        ledger = root / classification_ledger_path()
        write_canonical(ledger, {"schema": "rhoai3.scenario-classification/v1",
                                 "scenarios": {sid_probe: {"scenario_type": "", "gating": True}}})
        doc, row = compose()
        if (sid_probe not in row["scenarios"] or row["verdict"] == "PASS"
                or "fixed once a result exists" not in " ".join(row.get("classification_refusals") or [])):
            return _fail("a probe relabelled after a result is required again, with the refusal: %s" % row)
        if sid_probe in (doc.get("diagnostics") or {}):
            return _fail("a relabelled scenario gets no diagnostic exemption: %s" % doc.get("diagnostics"))
        # the comparator refuses it too, before any replay
        p = subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", sid_probe,
                            "--dest-url", "http://dest.invalid", "--no-reset"], text=True, capture_output=True)
        v = load_json(root / SCENARIO_PARITY / (scenario_slug(sid_probe) + ".json"))
        if p.returncode != 1 or v["verdict"] != "INCONCLUSIVE" or "fixed once a result exists" not in v["reason"]:
            return _fail("the comparator refuses a relabelled scenario: rc=%s %s" % (p.returncode, v.get("reason")))
        ledger.unlink()
        # ... and a capture taken under another classification is not compared
        req = request_of(root, probe)
        write_canonical(root / SCENARIO_ORACLES / (scenario_slug(sid_probe) + ".json"), {
            "schema": "rhoai3.source-scenario/v1", "scenario": sid_probe, "entry_point": ep,
            "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "status": "CAPTURED", "reason": "",
            "evidence_bundle_sha256": __import__("planner.canonical", fromlist=["digest"]).digest(
                load_json(root / "evidence" / "planning" / "evidence-bundle.json")),
            "source": {"base_url": "http://source.invalid"}, "scenario_type": "",
            "request": {"request_sha256": req["request_sha256"]},
            "response": {"status": 200, "body_kind": "empty", "body_sha256": "0" * 64, "headers": {}},
            "before": [], "effects": []})
        p = subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", sid_probe,
                            "--dest-url", "http://dest.invalid", "--no-reset"], text=True, capture_output=True)
        v = load_json(root / SCENARIO_PARITY / (scenario_slug(sid_probe) + ".json"))
        if p.returncode != 1 or "bound at capture" not in v["reason"]:
            return _fail("a capture taken under another classification is refused: rc=%s %s" % (p.returncode, v.get("reason")))
        if ledger.exists():
            return _fail("a refused comparison records no classification")
    return 0


def _body_diff_case() -> int:
    """H1a: a body mismatch says WHERE, not only that.

    The v9 Owner card had two digests and a 200-character sample, and the one
    real difference -- each pet's visits in the opposite order -- could not be
    located. The diff is structural: a list holding the same elements in
    another order is one ``order`` difference per list, collapsed to
    ``[*]`` in the summary; a changed value, a missing field and a non-JSON
    body are named at their path or line. The destination body is retained
    beside the verdict (capped, digested), the scenario and the read-oracle
    verdicts both carry ``body_diff``, and the receipt row points at it."""
    from _oracle_common import ORACLES as _ORACLES, PARITY as _PARITY, body_diff, normalize_body, retain_body, slug as _slug
    visits = lambda order: [{"date": d, "id": i} for d, i in order]  # noqa: E731
    src = [{"id": 1, "lastName": "Franklin", "pets": [{"name": "Leo", "visits": visits([("2013-01-04", 4), ("2013-01-01", 1)])}]},
           {"id": 2, "lastName": "Davis", "pets": [{"name": "Basil", "visits": visits([("2013-01-03", 3), ("2013-01-02", 2)])}]}]
    dst = json.loads(json.dumps(src))
    for owner in dst:
        owner["pets"][0]["visits"].reverse()
    enc = lambda v: json.dumps(v).encode("utf-8")  # noqa: E731
    d = body_diff(enc(src), enc(dst))
    if (d["kind"], d["order_only"], d["truncated"]) != ("json", True, False) or \
            [x["path"] for x in d["differences"]] != ["$[0].pets[0].visits", "$[1].pets[0].visits"] or \
            d["summary"] != "same elements, different order at $[*].pets[*].visits (2 lists)":
        return _fail("an order-only difference is one per list and collapsed in the summary: %s" % d)
    changed = json.loads(json.dumps(src))
    changed[1]["lastName"] = "Davies"
    del changed[0]["pets"][0]["name"]
    d = body_diff(enc(src), enc(changed))
    kinds = {(x["path"], x["kind"]) for x in d["differences"]}
    if d["order_only"] or kinds != {("$[1].lastName", "value"), ("$[0].pets[0].name", "missing")}:
        return _fail("a value change and a missing field are named at their paths: %s" % d)
    if not any(x["expected"] == "Davis" and x["observed"] == "Davies" for x in d["differences"]):
        return _fail("the values at a differing path are quoted, shortened: %s" % d["differences"])
    d = body_diff(b"<html>one</html>\nok", b"<html>two</html>\nok")
    if d["kind"] != "text" or d["differences"] != [{"path": "line 1", "kind": "value", "expected": "<html>one</html>",
                                                    "observed": "<html>two</html>"}]:
        return _fail("a non-JSON body is compared by line: %s" % d)
    d = body_diff(enc([1, 2]), enc({"a": 1}))
    if d["differences"] != [{"path": "$", "kind": "type", "expected": "array", "observed": "object"}]:
        return _fail("a type change is named: %s" % d)
    d = body_diff(enc({"k%03d" % i: i for i in range(80)}), enc({}))
    if not d["truncated"] or len(d["differences"]) != 50 or d.get("total") != 80:
        return _fail("a long diff is capped and says so: %s" % {k: d.get(k) for k in ("truncated", "total")})
    if body_diff(None, b"x", unavailable="gone")["kind"] != "unavailable":
        return _fail("no retained source body is a named unavailability")

    class Owners(BaseHTTPRequestHandler):
        payload = b""

        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(type(self).payload)))
            self.end_headers()
            self.wfile.write(type(self).payload)

        def log_message(self, *a):  # noqa: D102
            return

    Owners.payload = enc(dst)
    srv = HTTPServer(("127.0.0.1", 0), Owners)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d" % srv.server_address[1]
    try:
        with tempfile.TemporaryDirectory(prefix="body-diff-") as td:
            root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
            specimens.prepare_loop(root)
            if pipeline.admit(root)["status"] != "ADMITTED":
                return _fail("the body-diff fixture must be admitted")
            receipt_digest = load_json(root / "evidence/planning/admission-receipt.json")["receipt_digest"]
            from planner.canonical import digest as _digest
            bundle_sha = _digest(load_json(root / "evidence" / "planning" / "evidence-bundle.json"))
            eps = sorted(str(e["id"]) for e in load_json(root / "evidence/planning/evidence-bundle.json")["entry_points"])
            ep, read_ep = eps[0], eps[-1]
            sid = "sc:read-owners"
            sc = {"id": sid, "entry_point": ep, "method": "GET", "path": "/api/owners", "body_absent": True,
                  "reset_before": False, "effects": [], "normalization": []}
            write_canonical(root / "verification" / "scenarios" / "corpus.json",
                            {"schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
                             "initial_state": {"reset": "restart", "dataset": "two owners"}, "scenarios": [sc]})
            corpus_sha = corpus_digest(load_json(root / "verification" / "scenarios" / "corpus.json"))
            kind, sha, sample = normalize_body(enc(src), "application/json")
            ev = retain_body(root / SCENARIO_ORACLES / "bodies" / scenario_slug(sid), "response", enc(src), sha)
            ev["body_file"] = str(Path(ev["body_file"]).relative_to(root))
            write_canonical(root / SCENARIO_ORACLES / (scenario_slug(sid) + ".json"), {
                "schema": "rhoai3.source-scenario/v1", "scenario": sid, "entry_point": ep,
                "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "status": "CAPTURED", "reason": "",
                "evidence_bundle_sha256": bundle_sha, "source": {"base_url": "http://source.invalid"},
                "normalization": [], "reset_before": False, "request": {"request_sha256": request_of(root, sc)["request_sha256"]},
                "response": {"status": 200, "body_kind": kind, "body_sha256": sha, "headers": {}, "evidence": ev},
                "before": [], "effects": []})
            p = subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", sid, "--dest-url", url,
                                "--no-reset"], text=True, capture_output=True)
            v = load_json(root / SCENARIO_PARITY / (scenario_slug(sid) + ".json"))
            bd = v.get("body_diff") or {}
            if p.returncode != 1 or v["verdict"] != "FAIL" or not bd.get("order_only") or "different order at" not in v["reason"]:
                return _fail("the scenario verdict locates the order-only difference: rc=%s %s %s" % (p.returncode, v.get("reason"), bd))
            dev = v["observed"].get("evidence") or {}
            kept = Path(dev.get("body_file", ""))
            if not kept.is_file() or kept.read_bytes() != enc(dst) or len(dev.get("retained_sha256", "")) != 64:
                return _fail("the destination body is retained beside the verdict, digested: %s" % dev)
            if "_bodies" not in kept.as_posix() or enc(dst).decode() in json.dumps(v):
                return _fail("the destination body is never inside the verdict record: %s" % kept)
            subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
            row = next(r for r in load_json(root / _PARITY / "receipt.json")["entry_points"] if r["entry_point"] == ep)
            if row.get("body_diffs") != [{"scenario": sid, "summary": bd["summary"], "order_only": True, "kind": "json",
                                          "verdict_file": (SCENARIO_PARITY / (scenario_slug(sid) + ".json")).as_posix()}]:
                return _fail("the receipt row points at the diff: %s" % row.get("body_diffs"))
            # an identical destination: no diff, no retained body
            Owners.payload = enc(src)
            subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", sid, "--dest-url", url,
                            "--no-reset"], text=True, capture_output=True)
            v = load_json(root / SCENARIO_PARITY / (scenario_slug(sid) + ".json"))
            if v["verdict"] != "PASS" or "body_diff" in v or "evidence" in v["observed"]:
                return _fail("a matching body carries no diff: %s" % v)

            # the read-oracle comparator, the same way
            Owners.payload = enc(changed)
            rev = retain_body(root / _ORACLES / "bodies" / _slug(read_ep), "response", enc(src), sha)
            write_canonical(root / _ORACLES / (_slug(read_ep) + ".json"), {
                "schema": "rhoai3.source-oracle/v1", "entry_point": read_ep, "kind": "http", "status": "CAPTURED",
                "reason": "", "receipt_sha256": receipt_digest, "evidence_bundle_sha256": bundle_sha,
                "oracle": {"method": "GET", "path": "/api/owners", "status": 200, "body_kind": kind, "body_sha256": sha,
                           "evidence": rev}})
            runtime = HERE / "compare-runtime-parity.py"
            p = subprocess.run([sys.executable, str(runtime), "--root", str(root), "--entry-point", read_ep, "--dest-url", url],
                               text=True, capture_output=True)
            v = load_json(root / _PARITY / (_slug(read_ep) + ".json"))
            kinds = {(x["path"], x["kind"]) for x in (v.get("body_diff") or {}).get("differences") or []}
            if p.returncode != 1 or v["verdict"] != "FAIL" or kinds != {("$[1].lastName", "value"), ("$[0].pets[0].name", "missing")}:
                return _fail("the read-oracle verdict locates the difference: rc=%s %s %s" % (p.returncode, v.get("reason"), kinds))
            if not Path((v["observed"].get("evidence") or {}).get("body_file", "")).is_file():
                return _fail("the read-oracle comparison retains the destination body: %s" % v["observed"])
            # an oracle captured before retention: the diff says why it cannot say where
            doc = load_json(root / _ORACLES / (_slug(read_ep) + ".json"))
            doc["oracle"].pop("evidence")
            write_canonical(root / _ORACLES / (_slug(read_ep) + ".json"), doc)
            for f in (root / _ORACLES / "bodies" / _slug(read_ep)).iterdir():
                f.unlink()
            subprocess.run([sys.executable, str(runtime), "--root", str(root), "--entry-point", read_ep, "--dest-url", url],
                           text=True, capture_output=True)
            v = load_json(root / _PARITY / (_slug(read_ep) + ".json"))
            if (v.get("body_diff") or {}).get("kind") != "unavailable" or "retains no body" not in v["body_diff"]["summary"]:
                return _fail("an oracle with no retained body yields a named unavailable diff: %s" % v.get("body_diff"))
    finally:
        srv.shutdown()
    return 0


def _orphaned_records_case() -> int:
    """A receipt judges the current corpus from the records that belong to it.

    The composer composes over the records on DISK, which is what lets a
    scoped run keep the verdicts the last full run left for every scenario the
    filter was not scoped to. Measured on destination v9,
    verification/parity/scenarios/ also held cors-preflight-<digest>.json and
    cors-actual-<digest>.json from an earlier naming scheme beside the current
    sc_cors-preflight-<...>.json records: the leftovers were read as this
    corpus's evidence, each became an INCONCLUSIVE row whose reason was "no
    scenario '<id>' in verification/scenarios/corpus.json", and the receipt
    came back 33 INCONCLUSIVE of 34 after a scoped run that compared one
    scenario and changed nothing else.

    The control here is that directory made concrete: one record that belongs,
    and one of each way a record can fail to -- a scenario nobody declares, a
    declared scenario under a file name that is not its slug, a record
    compared against another corpus digest, and one compared in another
    security mode. Each must be NAMED as an orphan and counted in no row; the
    scenario an orphan was the only record of must be INCONCLUSIVE for the
    orphan's own reason rather than reported as a plain absence; and with the
    records put right the same directory composes a PASS."""
    import tempfile as _tempfile

    good, stale, foreign_mode = "sc:list-owners", "sc:get-owner", "sc:head-owner"
    with _tempfile.TemporaryDirectory(prefix="orphan-receipt-") as td:
        root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        specimens.prepare_loop(root)
        rec = pipeline.admit(root)
        if rec["status"] != "ADMITTED":
            return _fail("orphan fixture not admitted: %s" % rec["reasons"][:3])
        receipt_digest = load_json(root / "evidence/planning/admission-receipt.json")["receipt_digest"]
        ep = sorted(str(e["id"]) for e in load_json(root / "evidence/planning/evidence-bundle.json")["entry_points"])[0]
        corpus = {"schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
                  "initial_state": {"reset": "restart the service", "dataset": "one owner"},
                  "scenarios": [{"id": sid, "entry_point": ep, "method": "GET", "path": path, "body_absent": True,
                                 "reset_before": False, "effects": [], "normalization": []}
                                for sid, path in ((good, "/api/owners"), (stale, "/api/owners/7"),
                                                  (foreign_mode, "/api/owners/8"))]}
        write_canonical(root / "verification" / "scenarios" / "corpus.json", corpus)
        corpus_sha = corpus_digest(load_json(root / "verification" / "scenarios" / "corpus.json"))
        sdir = root / SCENARIO_PARITY

        def _record(name: str, scenario: str, **over: object) -> None:
            doc = {"schema": "rhoai3.scenario-parity/v1", "scenario": scenario, "entry_point": ep,
                   "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "security_mode": "disabled",
                   "security_variant": "", "verdict": "PASS", "reason": ""}
            doc.update(over)
            write_canonical(sdir / name, doc)

        _record(scenario_slug(good) + ".json", good)
        # ... and the four that do not belong, one of each kind
        _record(scenario_slug(stale) + ".json", stale, corpus_sha256="0" * 64)
        _record(scenario_slug(foreign_mode) + ".json", foreign_mode, security_mode="enabled")
        _record("cors-preflight-7b1a3d9234cd.json", "cors-preflight-7b1a3d9234cd")
        _record("cors-actual-7b1a3d9234cd.json", good)

        def compose() -> tuple[int, dict]:
            p = subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
            return p.returncode, load_json(root / parity_receipt_path())

        rc, doc = compose()
        orphans = {o["path"].rsplit("/", 1)[-1]: o for o in (doc.get("orphaned_records") or [])}
        want = {scenario_slug(stale) + ".json": "stale-corpus",
                scenario_slug(foreign_mode) + ".json": "other-mode",
                "cors-preflight-7b1a3d9234cd.json": "undeclared-scenario",
                "cors-actual-7b1a3d9234cd.json": "name-mismatch"}
        if {n: o["kind"] for n, o in orphans.items()} != want:
            return _fail("every record that does not belong to this corpus is named, with its reason: %s"
                         % doc.get("orphaned_records"))
        if not all(o["path"].startswith(SCENARIO_PARITY.as_posix() + "/") and o["reason"] for o in orphans.values()):
            return _fail("an orphan is named by PATH and by reason: %s" % doc.get("orphaned_records"))
        if "0" * 12 not in orphans[scenario_slug(stale) + ".json"]["reason"] or corpus_sha[:12] not in orphans[scenario_slug(stale) + ".json"]["reason"]:
            return _fail("the stale record's reason names both corpora: %s" % orphans[scenario_slug(stale) + ".json"]["reason"])
        if "enabled" not in orphans[scenario_slug(foreign_mode) + ".json"]["reason"]:
            return _fail("the other mode's record names the mode it compared: %s" % orphans[scenario_slug(foreign_mode) + ".json"]["reason"])
        row = next(r for r in doc["entry_points"] if r["entry_point"] == ep)
        if rc != 1 or row["verdict"] != "INCONCLUSIVE":
            return _fail("a required scenario whose only record is an orphan has no verdict to read: rc=%s %s" % (rc, row))
        # the v9 receipt's two shapes, neither of which may appear: an orphan
        # read as a scenario of this corpus, and a second file counted as a
        # duplicate result for a scenario that has exactly one
        if "no scenario" in row["reason"] or "result files" in row["reason"]:
            return _fail("an orphan is judged in no row: %s" % row["reason"])
        if good in row["reason"]:
            return _fail("the scenario whose record belongs to this corpus is not a problem: %s" % row["reason"])
        for sid in (stale, foreign_mode):
            if ("%s has no result that belongs to this corpus" % sid) not in row["reason"]:
                return _fail("the scenario an orphan was the only record of is named with the orphan's reason: %s" % row["reason"])
        if "have no result" in row["reason"]:
            return _fail("a record that does not belong is not the same gap as no record at all: %s" % row["reason"])

        # the same directory, with the records put right: nothing is orphaned
        # and the receipt PASSes, so what the orphans cost was exactly the
        # orphans and not the corpus
        (sdir / "cors-preflight-7b1a3d9234cd.json").unlink()
        (sdir / "cors-actual-7b1a3d9234cd.json").unlink()
        _record(scenario_slug(stale) + ".json", stale)
        _record(scenario_slug(foreign_mode) + ".json", foreign_mode)
        rc, doc = compose()
        row = next(r for r in doc["entry_points"] if r["entry_point"] == ep)
        if row["verdict"] != "PASS" or doc.get("orphaned_records") != []:
            return _fail("the records that belong compose a PASS for their entry point: %s %s"
                         % (doc.get("orphaned_records"), row))
        if sorted(row["scenarios"]) != sorted([good, stale, foreign_mode]):
            return _fail("the row still states every scenario the corpus requires: %s" % row)
    return 0


def verify_gaps(root: Path) -> list[str]:
    from planner.admission import verify_receipt
    return verify_receipt(root, require_admitted=False)[1]


def _fixture_variant_case() -> int:
    """A variant capture and a baseline capture are never mixed.

    A fixture variant is a DIFFERENT database state of the same mode: the
    declared dataset with the Operator's statements applied after it. A
    capture taken against it answers what the source does in that state and
    nothing about the baseline, so comparing it against a destination reset to
    the baseline -- or the baseline's captures against a destination reset to
    the variant -- would grade one state's answers by another's. That is the
    cross-mode reuse ADR-014 forbids, arriving through the dataset instead of
    the switch, so the comparator refuses both directions and names both
    states. The control is the mix made concrete: the captures copied from one
    directory into the other, which is what a hurried hand would do.
    """
    import shutil
    variant = "identity-disabled"
    sc = {"id": "sc:auth-allowed-list-owners", "entry_point": "", "method": "GET", "path": "/api/owners",
          "body_absent": True, "reset_before": False, "effects": [], "normalization": [],
          "identity": {"kind": "none"}}
    with tempfile.TemporaryDirectory(prefix="variant-parity-") as td:
        t = Path(td)
        root = specimens.build_dest(t / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        specimens.prepare_loop(root)
        rec = pipeline.admit(root)
        if rec["status"] != "ADMITTED":
            return _fail("variant fixture not admitted: %s" % rec["reasons"][:3])
        receipt_digest = load_json(root / "evidence/planning/admission-receipt.json")["receipt_digest"]
        from planner.canonical import digest as _digest
        from _scenarios import corpus_path
        bundle_sha = _digest(load_json(root / "evidence" / "planning" / "evidence-bundle.json"))
        ep = sorted(str(e["id"]) for e in load_json(root / "evidence" / "planning" / "evidence-bundle.json")["entry_points"])[0]
        sc["entry_point"] = ep
        for mode_variant in ("", variant):
            doc = {"schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
                   "security_mode": "enabled",
                   "initial_state": {"reset": "restart the service", "dataset": "one owner"},
                   "scenarios": [dict(sc)]}
            if mode_variant:
                doc["security_variant"] = mode_variant
            write_canonical(root / corpus_path("enabled", mode_variant), doc)
        corpus_sha = corpus_digest(load_json(root / corpus_path("enabled")))
        req = request_of(root, sc)

        def _oracle(where: Path, captured_variant: str) -> None:
            write_canonical(where / (scenario_slug(sc["id"]) + ".json"), {
                "schema": "rhoai3.source-scenario/v1", "scenario": sc["id"], "entry_point": ep,
                "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "status": "CAPTURED", "reason": "",
                "evidence_bundle_sha256": bundle_sha, "source": {"base_url": "http://source.invalid"},
                "initial_state": {"reset": "restart the service", "dataset": "one owner"},
                "normalization": [], "reset_before": False,
                "security_mode": "enabled", "security_variant": captured_variant,
                "request": {"request_sha256": req["request_sha256"]},
                "response": {"status": 200, "body_kind": "json", "body_sha256": "0" * 64, "headers": {}},
                "before": [], "effects": []})

        # the mix, both ways: a baseline capture judged as the variant's, and
        # the variant's judged as the baseline's
        _oracle(root / scenario_oracles_dir("enabled", variant), "")
        _oracle(root / scenario_oracles_dir("enabled"), variant)
        p = subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", sc["id"],
                            "--dest-url", "http://dest.invalid", "--no-reset", "--security-mode", "enabled",
                            "--fixture-variant", variant], text=True, capture_output=True)
        if p.returncode != 1 or "REFUSE: SCENARIO_PARITY variant mismatch" not in p.stderr:
            return _fail("a baseline capture must not be compared as a variant's: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        v = load_json(root / scenario_parity_dir("enabled", variant) / (scenario_slug(sc["id"]) + ".json"))
        if (v["verdict"] != "INCONCLUSIVE" or v.get("security_variant") != variant
                or v.get("captured_security_variant") != "" or "baseline" not in v["reason"]):
            return _fail("the refused comparison names both states: %s" % {k: v.get(k) for k in ("verdict", "security_variant", "captured_security_variant", "reason")})
        p = subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", sc["id"],
                            "--dest-url", "http://dest.invalid", "--no-reset", "--security-mode", "enabled"],
                           text=True, capture_output=True)
        if p.returncode != 1 or "REFUSE: SCENARIO_PARITY variant mismatch" not in p.stderr:
            return _fail("a variant capture must not be compared as the baseline's: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        v = load_json(root / scenario_parity_dir("enabled") / (scenario_slug(sc["id"]) + ".json"))
        if v.get("captured_security_variant") != variant or v.get("security_variant") != "":
            return _fail("the other direction names both states too: %s" % v)

        # the paths themselves keep them apart, and the loader refuses a
        # corpus of one state read as the other's
        if scenario_oracles_dir("enabled", variant) == scenario_oracles_dir("enabled"):
            return _fail("a variant's captures must not share the baseline's directory")
        shutil.copyfile(str(root / corpus_path("enabled", variant)), str(root / corpus_path("enabled")))
        try:
            load_corpus(root, "enabled")
            return _fail("a variant corpus must not load as the mode's baseline corpus")
        except Exception as exc:
            if "security_variant" not in str(exc):
                return _fail("the refusal names the state: %s" % exc)
    return 0


class AccountStatusService(BaseHTTPRequestHandler):
    """A service whose account table has one identity DISABLED: that
    identity's requests are refused, another declared identity's are
    answered. ``writes_anyway`` is the defect a refusal can hide: the answer
    is the source's 401, and the write happens regardless."""

    refused = ""
    reader = ""
    owners: dict = {}
    writes_anyway = False

    def _answer(self, code: int, payload=None) -> None:
        body = json.dumps(payload, sort_keys=True).encode() if payload is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        if code == 401:
            self.send_header("WWW-Authenticate", 'Basic realm="Realm"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _who(self) -> str:
        auth = self.headers.get("Authorization") or ""
        return "reader" if auth == type(self).reader else ("refused" if auth == type(self).refused else "")

    def do_GET(self):  # noqa: N802
        if self._who() != "reader":
            return self._answer(401, {"error": "unauthorized"})
        key = self.path.rsplit("/", 1)[-1]
        if self.path.rstrip("/").endswith("/owners"):
            return self._answer(200, [type(self).owners[k] for k in sorted(type(self).owners)])
        if key not in type(self).owners:
            return self._answer(404, {"error": "not found"})
        return self._answer(200, type(self).owners[key])

    def _write(self, apply) -> None:
        who = self._who()
        if who != "reader":
            if who == "refused" and type(self).writes_anyway:
                apply()
            return self._answer(401, {"error": "unauthorized"})
        apply()
        return self._answer(204)

    def do_DELETE(self):  # noqa: N802
        key = self.path.rsplit("/", 1)[-1]
        self._write(lambda: type(self).owners.pop(key, None))

    def do_PUT(self):  # noqa: N802
        key = self.path.rsplit("/", 1)[-1]
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self._write(lambda: type(self).owners.__setitem__(key, dict(json.loads(raw or b"{}"), id=int(key))))

    def log_message(self, *a):  # noqa: D102
        return


def _variant_refused_write_case() -> int:
    """A refused write under a fixture variant is measured, not waived.

    ADR-018: what the source answers for a DISABLED account is only half of
    the account-status exit; the other half is that the write it refused did
    not happen. The variant's refused PUT and DELETE carry read-backs taken as
    a declared identity the variant does not refuse, with the role
    ``unchanged_under_refusal``, and their expected bodies are the SOURCE's
    captures under the variant. The controls: an identical destination
    PASSes and every read-back row says what it proves; a destination that
    answers the same 401 and performs the write anyway FAILs on the
    read-back, naming the refusal; a write whose derivation had no identity to
    read the state as stays INCONCLUSIVE and the verdict names the missing
    identity beside the rule; and the variant receipt says what each refused
    write proves."""
    import os
    from _oracle_common import http_observe
    from _scenarios import corpus_path
    from planner.canonical import digest as _digest

    variant = "identity-disabled"
    reader_ref, refused_ref = "TEST_VARIANT_READER_CREDENTIAL", "TEST_VARIANT_REFUSED_CREDENTIAL"
    creds = {reader_ref: ("a-reader", "r3ader-s3cret"), refused_ref: ("a-disabled-one", "d1sabled-s3cret")}
    tokens = {ref: "Basic %s" % base64.b64encode(("%s:%s" % pair).encode("utf-8")).decode("ascii") for ref, pair in creds.items()}
    kept = {ref: os.environ.get(ref) for ref in creds}
    for ref, pair in creds.items():
        os.environ[ref] = "%s:%s" % pair
    seed = {"7": {"id": 7, "name": "seven"}, "8": {"id": 8, "name": "eight"}}

    def handler(name: str) -> type:
        return type(name, (AccountStatusService,), {"refused": tokens[refused_ref], "reader": tokens[reader_ref],
                                                    "owners": json.loads(json.dumps(seed)), "writes_anyway": False})

    servers: list[HTTPServer] = []

    def start(h: type) -> str:
        srv = HTTPServer(("127.0.0.1", 0), h)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return "http://127.0.0.1:%d" % srv.server_address[1]

    role = "unchanged_under_refusal"
    try:
        with tempfile.TemporaryDirectory(prefix="variant-refused-write-") as td:
            root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
            specimens.prepare_loop(root)
            if pipeline.admit(root)["status"] != "ADMITTED":
                return _fail("the variant refused-write fixture must be admitted")
            receipt_digest = load_json(root / "evidence/planning/admission-receipt.json")["receipt_digest"]
            bundle_sha = _digest(load_json(root / "evidence" / "planning" / "evidence-bundle.json"))
            ep = sorted(str(e["id"]) for e in load_json(root / "evidence/planning/evidence-bundle.json")["entry_points"])[0]
            body_rel = "verification/scenarios-enabled-%s/bodies/update-7.json" % variant
            (root / body_rel).parent.mkdir(parents=True, exist_ok=True)
            (root / body_rel).write_text(json.dumps({"name": "renamed"}), encoding="utf-8")
            refused = {"kind": "basic", "credential_ref": refused_ref}
            reader = {"kind": "basic", "credential_ref": reader_ref}
            reads = [{"id": "eff:owners-7", "method": "GET", "path": "/api/owners/7", "role": role},
                     {"id": "eff:owners", "method": "GET", "path": "/api/owners", "role": role}]
            contract = {"intent": "negative", "expect_status_class": "4xx", "after_equals_before": True}
            scenarios = [
                {"id": "sc:fixture-%s-delete-owners-7" % variant, "entry_point": ep, "method": "DELETE",
                 "path": "/api/owners/7", "headers": {}, "identity": dict(refused), "body_absent": True,
                 "reset_before": False, "effects": [dict(e) for e in reads], "effects_identity": dict(reader),
                 "effects_reader": {"strategy": "second_identity", "name": "a-reader", "credential_ref": reader_ref},
                 "normalization": [], "security_mode": "enabled", "security_variant": variant, "qualify": dict(contract)},
                {"id": "sc:fixture-%s-update-owners-7" % variant, "entry_point": ep, "method": "PUT",
                 "path": "/api/owners/7", "headers": {"Content-Type": "application/json"}, "identity": dict(refused),
                 "body_file": body_rel, "reset_before": False, "effects": [dict(e) for e in reads],
                 "effects_identity": dict(reader),
                 "effects_reader": {"strategy": "second_identity", "name": "a-reader", "credential_ref": reader_ref},
                 "normalization": [], "security_mode": "enabled",
                 "security_variant": variant, "qualify": dict(contract)},
                {"id": "sc:fixture-%s-delete-owners-8" % variant, "entry_point": ep, "method": "DELETE",
                 "path": "/api/owners/8", "headers": {}, "identity": dict(refused), "body_absent": True,
                 "reset_before": False, "effects": [], "normalization": [], "security_mode": "enabled",
                 "security_variant": variant, "qualify": {"intent": "negative", "expect_status_class": "4xx"},
                 "effects_unobservable": "missing effects identity: decisions.security.identities declares no identity "
                                         "other than credential_ref %s (the one this variant refuses)" % refused_ref},
            ]
            corpus_doc = {"schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
                          "initial_state": {"reset": "restart the service", "dataset": "two owners, one account disabled"},
                          "security_mode": "enabled", "security_variant": variant, "scenarios": scenarios}
            write_canonical(root / corpus_path("enabled", variant), corpus_doc)
            corpus_sha = corpus_digest(load_json(root / corpus_path("enabled", variant)))
            write_canonical(root / capture_receipt_path("enabled", variant),
                            {"schema": "rhoai3.source-capture/v1", "status": "ok", "security_mode": "enabled",
                             "security_variant": variant, "corpus_sha256": corpus_sha})

            # what the SOURCE did under the variant: the read-backs as the
            # reader, the write as the disabled identity, the read-backs again
            src_url = start(handler("SrcAccounts"))
            odir = root / scenario_oracles_dir("enabled", variant)
            for sc in scenarios:
                req = request_of(root, sc)
                eff_auth = {"Authorization": tokens[reader_ref]}
                before = [http_observe(src_url, e["method"], e["path"], headers=eff_auth) for e in sc["effects"]]
                got = http_observe(src_url, sc["method"], sc["path"], body=req["body"],
                                   headers={**req["headers"], "Authorization": tokens[refused_ref]})
                after = [http_observe(src_url, e["method"], e["path"], headers=eff_auth) for e in sc["effects"]]
                if got["status"] != 401 or any(b["status"] != 200 for b in before + after):
                    return _fail("the fixture source refuses the disabled identity and answers the reader: %s %s"
                                 % (got["status"], [b["status"] for b in before + after]))
                rows = lambda obs: [{"id": e["id"], "method": e["method"], "path": e["path"], "role": e["role"],  # noqa: E731
                                     "status": o["status"], "body_kind": o["body_kind"], "body_sha256": o["body_sha256"]}
                                    for e, o in zip(sc["effects"], obs)]
                write_canonical(odir / (scenario_slug(sc["id"]) + ".json"), {
                    "schema": "rhoai3.source-scenario/v1", "scenario": sc["id"], "entry_point": ep,
                    "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "status": "CAPTURED", "reason": "",
                    "evidence_bundle_sha256": bundle_sha, "source": {"base_url": src_url},
                    "initial_state": corpus_doc["initial_state"], "normalization": [], "reset_before": False,
                    "security_mode": "enabled", "security_variant": variant,
                    **({"effects_identity": {"kind": "basic", "user_env": "", "password_env": "", "credential_ref": reader_ref},
                        # ADR-021: the source's scoped database state, before and after
                        "source_effects": {"observed": True, "strategy": "second_identity",
                                           "db": {"scope": {"tables": ["owners"]}, "before": {"sha256": "b" * 64},
                                                  "after": {"sha256": "c" * 64},
                                                  "comparison": {"equal": True, "differences": {}}}}}
                       if sc.get("effects_identity") else {}),
                    "request": {"request_sha256": req["request_sha256"]},
                    "response": {"status": got["status"], "body_kind": got["body_kind"], "body_sha256": got["body_sha256"],
                                 "headers": got["headers"]},
                    "before": rows(before), "effects": rows(after)})

            def compare(sid: str, dest_url: str) -> tuple[int, dict]:
                p = subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", sid,
                                    "--dest-url", dest_url, "--no-reset", "--security-mode", "enabled",
                                    "--fixture-variant", variant], text=True, capture_output=True)
                return p.returncode, load_json(root / scenario_parity_dir("enabled", variant) / (scenario_slug(sid) + ".json"))

            for sc in scenarios[:2]:
                # an identical destination: refused, and nothing changed
                rc, v = compare(sc["id"], start(handler("DestSame")))
                if rc != 0 or v["verdict"] != "PASS":
                    return _fail("an identical destination PASSes the refused %s: rc=%s %s" % (sc["method"], rc, v.get("reason")))
                if [r.get("role") for r in v["effects"]] != [role, role] or not all(r["match"] for r in v["effects"]):
                    return _fail("every read-back row says what it proves: %s" % v["effects"])
                if v.get("effects_identity", {}).get("credential_ref") != reader_ref:
                    return _fail("the destination's read-backs are taken as the reader: %s" % v.get("effects_identity"))
                if v["results"].get("source_effect", {}).get("verdict") != "OBSERVED" or v["results"]["source_effect"].get("db_unchanged") is not True:
                    return _fail("the source effect is the database comparison: %s" % v.get("results"))
                # a destination that answers the same refusal and writes anyway
                liar = handler("DestWritesAnyway")
                liar.writes_anyway = True
                rc, v = compare(sc["id"], start(liar))
                if rc != 1 or v["verdict"] != "FAIL" or "refused write changed the state" not in v["reason"]:
                    return _fail("a refused %s that happened anyway FAILs on its read-back: rc=%s %s %s"
                                 % (sc["method"], rc, v.get("verdict"), v.get("reason")))
                if v["observed"]["status"] != 401:
                    return _fail("the control is a destination whose ANSWER is right: %s" % v["observed"])
            # without the database comparison the source effect is not observed,
            # however well the HTTP read-backs match
            cap0 = root / scenario_oracles_dir("enabled", variant) / (scenario_slug(scenarios[0]["id"]) + ".json")
            doc0 = load_json(cap0)
            doc0["source_effects"] = {"observed": False, "reason": "SOURCE_STORE_UNKNOWN fixture"}
            write_canonical(cap0, doc0)
            rc, v = compare(scenarios[0]["id"], start(handler("DestNoDb")))
            if (rc != 1 or v["verdict"] != "INCONCLUSIVE" or v["results"]["source_effect"]["verdict"] != "INCONCLUSIVE"
                    or "SOURCE_STORE_UNKNOWN" not in v["reason"] or v["results"].get("destination_effect") != "PASS"):
                return _fail("HTTP read-backs alone never observe the source effect: rc=%s %s %s"
                             % (rc, v.get("reason"), v.get("results")))
            # no identity to read the state as: the rule stands, and says why
            rc, v = compare(scenarios[2]["id"], start(handler("DestNoReader")))
            if (rc != 1 or v["verdict"] != "INCONCLUSIVE" or "must declare at least one effect" not in v["reason"]
                    or "missing effects identity" not in v["reason"] or refused_ref not in v["reason"]):
                return _fail("a refused write with no read-back stays INCONCLUSIVE and names the missing identity: rc=%s %s"
                             % (rc, v.get("reason")))
            # the variant receipt says what each refused write proves
            subprocess.run([sys.executable, str(RECEIPT), "--root", str(root), "--security-mode", "enabled",
                            "--fixture-variant", variant], text=True, capture_output=True)
            rp = root / parity_receipt_path("enabled", variant)
            doc = load_json(rp) if rp.is_file() else {}
            rw = doc.get("refused_writes") or {}
            if (sorted(rw.get(scenarios[0]["id"], {}).get("reads") or []) != ["eff:owners", "eff:owners-7"]
                    or "unchanged" not in str(rw.get(scenarios[0]["id"], {}).get("proves"))
                    or "missing effects identity" not in str(rw.get(scenarios[2]["id"], {}).get("unobservable"))
                    or rw.get(scenarios[2]["id"], {}).get("verdict") != "INCONCLUSIVE"):
                return _fail("the variant receipt names what each refused write proves: %s" % rw)
            written = json.dumps(doc) + "".join(p.read_text(encoding="utf-8")
                                                for p in (root / "verification").rglob("*.json"))
            for ref, pair in creds.items():
                if pair[1] in written or tokens[ref] in written:
                    return _fail("only credential references travel into the evidence")
    finally:
        for srv in servers:
            srv.shutdown()
        for ref, value in kept.items():
            if value is None:
                os.environ.pop(ref, None)
            else:
                os.environ[ref] = value
    return 0


class RevertStateService(BaseHTTPRequestHandler):
    """A service with ONE declared identity, disabled by the variant and
    enabled again by its revert. ``/__state`` is the stub's reset script:
    baseline, variant, and a revert that refuses unless it finds the variant
    state. ``writes_anyway`` performs a refused write; ``reenables`` is a
    refused request that touches the variant's own column."""

    token = ""
    owners: dict = {}
    disabled = False
    writes_anyway = False
    reenables = False
    ops: list = []
    seed: dict = {}

    def _answer(self, code: int, payload=None) -> None:
        body = json.dumps(payload, sort_keys=True).encode() if payload is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        if code == 401:
            self.send_header("WWW-Authenticate", 'Basic realm="Realm"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _ok(self) -> bool:
        cls = type(self)
        return self.headers.get("Authorization") == cls.token and not cls.disabled

    def do_POST(self):  # noqa: N802
        cls = type(self)
        op = self.path.rsplit("=", 1)[-1]
        cls.ops.append(op)
        if op == "baseline":
            cls.owners, cls.disabled = json.loads(json.dumps(cls.seed)), False
        elif op == "variant":
            cls.disabled = True
        elif op == "revert":
            if not cls.disabled:
                return self._answer(409, {"error": "REVERT_UNEXPECTED_STATE the variant value is not there"})
            cls.disabled = False
        return self._answer(200, {"op": op})

    def do_GET(self):  # noqa: N802
        if not self._ok():
            return self._answer(401, {"error": "unauthorized"})
        cls = type(self)
        if self.path.rstrip("/").endswith("/owners"):
            return self._answer(200, [cls.owners[k] for k in sorted(cls.owners)])
        key = self.path.rsplit("/", 1)[-1]
        return self._answer(200, cls.owners[key]) if key in cls.owners else self._answer(404, {"error": "not found"})

    def do_DELETE(self):  # noqa: N802
        cls = type(self)
        key = self.path.rsplit("/", 1)[-1]
        if not self._ok():
            if cls.writes_anyway:
                cls.owners.pop(key, None)
            if cls.reenables:
                cls.disabled = False
            return self._answer(401, {"error": "unauthorized"})
        cls.owners.pop(key, None)
        return self._answer(204)

    def log_message(self, *a):  # noqa: D102
        return


_STATE_SCRIPT = """import sys, urllib.error, urllib.request
args = sys.argv[1:]
op = "variant" if "--variant" in args else ("revert" if "--revert-variant" in args else "baseline")
url = args[args.index("--url") + 1]
try:
    urllib.request.urlopen(urllib.request.Request(url + "/__state?op=" + op, data=b"", method="POST"), timeout=5)
except urllib.error.HTTPError as exc:
    print("FAIL: RESET %s: %s" % (op, exc.read().decode("utf-8", "replace"))); sys.exit(1)
print("OK: %s" % op)
"""


def _variant_revert_then_read_case() -> int:
    """REVERT-THEN-READ: a refused write measured with no second identity.

    The one declared identity is the one the variant disables, so the state
    is read as that identity on the verified BASELINE, the variant is applied
    and the request refused, the variant's own change is reverted by the reset
    script, and the reads are taken again -- against the baseline reads the
    SOURCE recorded. The controls: an identical destination PASSes with the
    three states visited in order (a --variant the caller's --reset-cmd
    carries is not what decides them); a destination that answers the same
    401 and writes anyway FAILs; one whose refused request touched the
    variant's own column makes the revert refuse, which is INCONCLUSIVE and
    says so; --no-reset cannot move through three states and is refused."""
    import os
    from _oracle_common import http_observe
    from _scenarios import corpus_path
    from planner.canonical import digest as _digest

    variant = "identity-disabled"
    ref = "TEST_VARIANT_ONLY_CREDENTIAL"
    pair = ("the-only-one", "0nly-s3cret")
    token = "Basic %s" % base64.b64encode(("%s:%s" % pair).encode("utf-8")).decode("ascii")
    kept = os.environ.get(ref)
    os.environ[ref] = "%s:%s" % pair
    seed = {"7": {"id": 7, "name": "seven"}, "8": {"id": 8, "name": "eight"}}
    servers: list[HTTPServer] = []

    def start(name: str, **flags) -> tuple[str, type]:
        h = type(name, (RevertStateService,), dict({"token": token, "owners": json.loads(json.dumps(seed)), "seed": seed,
                                                    "disabled": False, "writes_anyway": False, "reenables": False,
                                                    "ops": []}, **flags))
        srv = HTTPServer(("127.0.0.1", 0), h)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return "http://127.0.0.1:%d" % srv.server_address[1], h

    own = {"kind": "basic", "credential_ref": ref}
    try:
        with tempfile.TemporaryDirectory(prefix="variant-revert-read-") as td:
            root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
            specimens.prepare_loop(root)
            if pipeline.admit(root)["status"] != "ADMITTED":
                return _fail("the revert-then-read fixture must be admitted")
            receipt_digest = load_json(root / "evidence/planning/admission-receipt.json")["receipt_digest"]
            bundle_sha = _digest(load_json(root / "evidence" / "planning" / "evidence-bundle.json"))
            ep = sorted(str(e["id"]) for e in load_json(root / "evidence/planning/evidence-bundle.json")["entry_points"])[0]
            state_script = Path(td) / "state.py"
            state_script.write_text(_STATE_SCRIPT, encoding="utf-8")
            reads = [{"id": "eff:owners-7", "method": "GET", "path": "/api/owners/7", "role": "unchanged_under_refusal"},
                     {"id": "eff:owners", "method": "GET", "path": "/api/owners", "role": "unchanged_under_refusal"}]
            sc = {"id": "sc:fixture-%s-delete-owners-7" % variant, "entry_point": ep, "method": "DELETE",
                  "path": "/api/owners/7", "headers": {}, "identity": dict(own), "body_absent": True,
                  "reset_before": True, "effects": [dict(e) for e in reads], "effects_identity": dict(own),
                  "effects_reader": {"strategy": "revert_then_read", "name": "the-only-one", "credential_ref": ref},
                  "normalization": [], "security_mode": "enabled", "security_variant": variant,
                  "qualify": {"intent": "negative", "expect_status_class": "4xx", "before_reads_usable": True}}
            # a variant READ that declares no reset (hand-authored; the
            # derivation now always declares one): the v9 ordering that broke
            rd = {"id": "sc:fixture-%s-read-owners" % variant, "entry_point": ep, "method": "GET", "path": "/api/owners",
                  "headers": {}, "identity": dict(own), "body_absent": True, "reset_before": False, "effects": [],
                  "normalization": [], "security_mode": "enabled", "security_variant": variant,
                  "qualify": {"intent": "negative", "expect_status_class": "4xx"}}
            write_canonical(root / corpus_path("enabled", variant), {
                "schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
                "initial_state": {"reset": "the reset script", "dataset": "two owners, one account"},
                "security_mode": "enabled", "security_variant": variant, "scenarios": [sc, rd]})
            corpus_sha = corpus_digest(load_json(root / corpus_path("enabled", variant)))
            write_canonical(root / capture_receipt_path("enabled", variant),
                            {"schema": "rhoai3.source-capture/v1", "status": "ok", "security_mode": "enabled",
                             "security_variant": variant, "corpus_sha256": corpus_sha})
            req = request_of(root, sc)

            # the SOURCE: baseline reads as the only identity, then the variant
            # and the refused request; its in-process database is not reverted
            src_url, src = start("SrcRevert")
            auth = {"Authorization": token}
            before = [http_observe(src_url, e["method"], e["path"], headers=auth) for e in reads]
            src.disabled = True
            got = http_observe(src_url, "DELETE", sc["path"], headers=auth)
            if got["status"] != 401 or any(b["status"] != 200 for b in before):
                return _fail("the fixture source answers the baseline reads and refuses under the variant: %s %s"
                             % (got["status"], [b["status"] for b in before]))
            write_canonical(root / scenario_oracles_dir("enabled", variant) / (scenario_slug(sc["id"]) + ".json"), {
                "schema": "rhoai3.source-scenario/v1", "scenario": sc["id"], "entry_point": ep,
                "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "status": "CAPTURED", "reason": "",
                "evidence_bundle_sha256": bundle_sha, "source": {"base_url": src_url},
                "initial_state": {}, "normalization": [], "reset_before": True,
                "security_mode": "enabled", "security_variant": variant,
                "effects_identity": {"kind": "basic", "user_env": "", "password_env": "", "credential_ref": ref},
                "effects_reader": dict(sc["effects_reader"]),
                "revert": {"strategy": "revert_then_read", "applied_on_source": False, "reason": "in-process"},
                "request": {"request_sha256": req["request_sha256"]},
                "response": {"status": got["status"], "body_kind": got["body_kind"], "body_sha256": got["body_sha256"],
                             "headers": got["headers"]},
                "before": [{"id": e["id"], "method": e["method"], "path": e["path"], "role": e["role"], "status": o["status"],
                            "body_kind": o["body_kind"], "body_sha256": o["body_sha256"]} for e, o in zip(reads, before)],
                "effects": []})
            read = http_observe(src_url, "GET", rd["path"], headers=auth)
            if read["status"] != 401:
                return _fail("the fixture source refuses the read under the variant: %s" % read["status"])
            write_canonical(root / scenario_oracles_dir("enabled", variant) / (scenario_slug(rd["id"]) + ".json"), {
                "schema": "rhoai3.source-scenario/v1", "scenario": rd["id"], "entry_point": ep,
                "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "status": "CAPTURED", "reason": "",
                "evidence_bundle_sha256": bundle_sha, "source": {"base_url": src_url},
                "initial_state": {}, "normalization": [], "reset_before": False,
                "security_mode": "enabled", "security_variant": variant,
                "request": {"request_sha256": request_of(root, rd)["request_sha256"]},
                "response": {"status": read["status"], "body_kind": read["body_kind"], "body_sha256": read["body_sha256"],
                             "headers": read["headers"]},
                "before": [], "effects": []})

            def compare(dest_url: str, *extra: str, scenario: dict | None = None) -> tuple[int, dict]:
                target = scenario or sc
                reset = "%s %s --root %s --url %s --variant %s" % (sys.executable, state_script, root, dest_url, variant)
                p = subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", target["id"],
                                    "--dest-url", dest_url, "--security-mode", "enabled", "--fixture-variant", variant,
                                    "--reset-cmd", reset] + list(extra), text=True, capture_output=True)
                return p.returncode, load_json(root / scenario_parity_dir("enabled", variant) / (scenario_slug(target["id"]) + ".json"))

            url, dest = start("DestSame", disabled=True, owners={})   # a dirty state the baseline reset must repair
            rc, v = compare(url)
            # ADR-020: without a source observation the destination's no-effect
            # result stands on its own and the source effect is INCONCLUSIVE
            if (rc != 1 or v["verdict"] != "INCONCLUSIVE" or "not observed" not in v["reason"]
                    or v["results"].get("response") != "PASS" or v["results"].get("destination_no_effect") != "PASS"
                    or v["results"]["source_effect"]["verdict"] != "INCONCLUSIVE"):
                return _fail("an identical destination with no source observation is response PASS, destination no-effect "
                             "PASS and source effect INCONCLUSIVE: rc=%s %s %s" % (rc, v.get("reason"), v.get("results")))
            if dest.ops != ["baseline", "variant", "revert", "variant"]:
                return _fail("the three states are visited in order, whatever --variant the caller's command carried, and "
                             "the variant is applied again after the after-reads: %s" % dest.ops)
            if (v.get("restored_variant") or {}).get("rc") != 0 or not dest.disabled:
                return _fail("the comparison leaves the destination in the variant state and records it: %s" % v.get("restored_variant"))
            # the next scenario declares no reset: it is still judged on the
            # variant (401 as the source answered), not on the reverted baseline
            rc, rv = compare(url, "--no-reset", scenario=rd)
            if rc != 0 or rv["verdict"] != "PASS" or rv["observed"]["status"] != 401 or dest.ops[-1:] != ["variant"] or len(dest.ops) != 4:
                return _fail("a variant read after a revert-then-read write is judged on the variant state: rc=%s %s %s %s"
                             % (rc, rv.get("verdict"), rv.get("reason"), dest.ops))
            if (v.get("effects_strategy") != "revert_then_read" or [r.get("role") for r in v["effects"]] != ["unchanged_under_refusal"] * 2
                    or v["observed"]["status"] != 401 or not all(r["match"] for r in v["before"] + v["effects"])):
                return _fail("the verdict records the strategy, the refusal and reads matching the baseline: %s" % v)
            # the source effect is never discharged by the destination's reads
            subprocess.run([sys.executable, str(RECEIPT), "--root", str(root), "--security-mode", "enabled",
                            "--fixture-variant", variant], text=True, capture_output=True)
            rw = (load_json(root / parity_receipt_path("enabled", variant)).get("refused_writes") or {}).get(sc["id"]) or {}
            if rw.get("source_effect") != "INCONCLUSIVE" or rw.get("results", {}).get("destination_no_effect") != "PASS":
                return _fail("the receipt keeps the destination's no-effect result apart from the source effect: %s" % rw)
            url, dest = start("DestWritesAnyway", writes_anyway=True)
            rc, v = compare(url)
            if (rc != 1 or v["verdict"] != "FAIL" or "refused write changed the state" not in v["reason"]
                    or v["results"].get("destination_no_effect") != "FAIL" or v["results"].get("response") != "PASS"):
                return _fail("a refused write that happened anyway FAILs under revert-then-read: rc=%s %s %s %s"
                             % (rc, v.get("verdict"), v.get("reason"), v.get("results")))
            url, dest = start("DestReenables", reenables=True)
            rc, v = compare(url)
            if (rc != 1 or v["verdict"] != "INCONCLUSIVE" or "revert refused" not in v["reason"]
                    or "REVERT_UNEXPECTED_STATE" not in json.dumps(v.get("revert"))):
                return _fail("a revert that finds unexpected state refuses, and the comparison says so: rc=%s %s %s"
                             % (rc, v.get("reason"), v.get("revert")))
            url, dest = start("DestNoReset")
            rc, v = compare(url, "--no-reset")
            if rc != 1 or v["verdict"] != "INCONCLUSIVE" or "--no-reset" not in v["reason"] or dest.ops:
                return _fail("--no-reset cannot move through three states: rc=%s %s %s" % (rc, v.get("reason"), dest.ops))

            # the SOURCE's post-request state OBSERVED (the capture held its
            # database, reverted the fixture rows and read through the running
            # source): the destination is compared against those reads
            cap_p = root / scenario_oracles_dir("enabled", variant) / (scenario_slug(sc["id"]) + ".json")
            cap = load_json(cap_p)
            src.disabled = False   # the source's store, reverted on the fixture rows only
            after = [http_observe(src_url, e["method"], e["path"], headers=auth) for e in reads]
            cap["effects"] = [{"id": e["id"], "method": e["method"], "path": e["path"], "role": e["role"], "status": o["status"],
                               "body_kind": o["body_kind"], "body_sha256": o["body_sha256"]} for e, o in zip(reads, after)]
            cap["source_effects"] = {"observed": True, "mechanism": "fixture", "snapshot": {"sha256": "a" * 64},
                                     "db": {"scope": {"tables": ["owners"]}, "before": {"sha256": "b" * 64},
                                            "after": {"sha256": "c" * 64}, "comparison": {"equal": True, "differences": {}}}}
            write_canonical(cap_p, cap)
            url, dest = start("DestObserved")
            rc, v = compare(url)
            if (rc != 0 or v["verdict"] != "PASS" or v["results"].get("destination_effect") != "PASS"
                    or v["results"]["source_effect"] != {"verdict": "OBSERVED", "db_unchanged": True, "changed_tables": [],
                                                         "scope": ["owners"], "db_before_sha256": "b" * 64,
                                                         "db_after_sha256": "c" * 64, "snapshot_sha256": "a" * 64}):
                return _fail("with the source's effect observed an identical destination PASSes on it: rc=%s %s %s"
                             % (rc, v.get("reason"), v.get("results")))
            url, dest = start("DestObservedWrites", writes_anyway=True)
            rc, v = compare(url)
            if rc != 1 or v["verdict"] != "FAIL" or v["results"].get("destination_effect") != "FAIL":
                return _fail("a destination that writes despite the refusal FAILs against the observed source: rc=%s %s"
                             % (rc, v.get("results")))
    finally:
        for srv in servers:
            srv.shutdown()
        if kept is None:
            os.environ.pop(ref, None)
        else:
            os.environ[ref] = kept
    return 0


def _scenario_coverage_case() -> int:
    """ARCHITECT RULING 2026-09-22: scenario coverage COUNTS, and only when it
    is evidence.

    v9's receipt reported 20 of 34 entry points "not compared" because the
    older single-request read oracle was absent -- a non-idempotent method or
    a wildcard path that cannot be replayed by a method and a path. The ruling:
    a QUALIFIED scenario that explicitly binds the entry point, whose
    destination replay PASSED with the required assertions in this mode, is
    comparable evidence, and the absence of a read oracle is not itself
    disqualifying. What it does NOT do is weaken anything: a scenario that
    never ran, one that ran and failed, and one the qualification did not pass
    all cover nothing, and an entry point no scenario binds stays a gap
    however many other scenarios pass.

    Four entry points, one of each shape, and the receipt's three-way count."""
    with tempfile.TemporaryDirectory(prefix="coverage-") as td:
        root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        specimens.prepare_loop(root)
        if pipeline.admit(root)["status"] != "ADMITTED":
            return _fail("the coverage fixture must be admitted")
        digest = load_json(root / "evidence" / "planning" / "admission-receipt.json")["receipt_digest"]
        eps = sorted(str(e["id"]) for e in load_json(root / "evidence" / "planning" / "evidence-bundle.json")["entry_points"])
        if len(eps) < 4:
            return _fail("the coverage fixture needs four admitted entry points, got %d" % len(eps))
        by_oracle, by_scenario, replay_failed, never_ran = eps[:4]
        uncovered_eps = eps[4:]

        # the corpus binds three entry points, each by exactly one scenario;
        # `by_oracle` is bound by none, and is compared by its read oracle
        bound = {"sc:covered": by_scenario, "sc:replay-failed": replay_failed,
                 "sc:never-ran": never_ran}
        corpus = {"schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
                  "initial_state": {"reset": "restart the service", "dataset": "empty"},
                  "scenarios": [{"id": sid, "entry_point": ep, "method": "POST", "path": "/api/owners",
                                 "headers": {"Content-Type": "application/json"}, "body_absent": True,
                                 "reset_before": True, "effects": [], "normalization": []}
                                for sid, ep in sorted(bound.items())]}
        write_canonical(root / "verification" / "scenarios" / "corpus.json", corpus)
        corpus_sha = corpus_digest(load_json(root / "verification" / "scenarios" / "corpus.json"))

        # the qualification: the source demonstrated every one of them
        def _qualify(inconclusive: str = "") -> None:
            write_canonical(root / qualification_path("disabled"), {
                "schema": "rhoai3.scenario-qualification/v1", "security_mode": "disabled",
                "corpus_sha256": corpus_sha,
                "scenarios": {sid: {"capability": "INCONCLUSIVE" if sid == inconclusive else "PASS",
                                    "intent": "positive",
                                    "reason": "the capture does not say whether the source created anything" if sid == inconclusive else ""}
                              for sid in bound}})

        _qualify()

        # the destination replays: covered PASSes, replay-failed FAILs,
        # never-ran has no record at all
        for sid, verdict in (("sc:covered", "PASS"), ("sc:replay-failed", "FAIL")):
            write_canonical(root / scenario_parity_dir("disabled") / (scenario_slug(sid) + ".json"), {
                "schema": "rhoai3.scenario-parity/v1", "scenario": sid, "entry_point": bound[sid],
                "verdict": verdict, "reason": "" if verdict == "PASS" else "status 500 vs 201",
                "receipt_sha256": digest, "corpus_sha256": corpus_sha})

        # the read oracle: the single-request replay of an entry point the
        # corpus binds no scenario to
        from _oracle_common import PARITY, slug
        write_canonical(root / PARITY / (slug(by_oracle) + ".json"), {
            "schema": "rhoai3.parity/v1", "entry_point": by_oracle, "verdict": "PASS",
            "reason": "", "receipt_sha256": digest})

        subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        doc = load_json(root / parity_receipt_path("disabled"))
        rows = {str(r["entry_point"]): r for r in doc["entry_points"]}

        want = {by_oracle: ("oracle", []), by_scenario: ("scenario", ["sc:covered"]),
                replay_failed: ("none", []), never_ran: ("none", [])}
        for ep, (kind, scenarios) in sorted(want.items()):
            row = rows.get(ep) or {}
            if str(row.get("coverage_kind") or "") != kind:
                return _fail("%s must be covered %r, the receipt says %r (%s)" % (ep, kind, row.get("coverage_kind"), row.get("reason")))
            if [str(s) for s in ((row.get("covered_by") or {}).get("scenarios") or [])] != scenarios:
                return _fail("%s must name the scenarios that cover it (%s): %s" % (ep, scenarios, row.get("covered_by")))
        if rows[by_scenario]["verdict"] != "PASS":
            return _fail("an entry point a qualified passing scenario binds is compared: %s" % rows[by_scenario])
        if rows[never_ran]["verdict"] != "INCONCLUSIVE" or "no result" not in rows[never_ran]["reason"]:
            return _fail("a scenario that never ran leaves its entry point INCONCLUSIVE: %s" % rows[never_ran])
        if rows[replay_failed]["verdict"] != "FAIL":
            return _fail("a scenario whose replay failed is a FAIL, never coverage: %s" % rows[replay_failed])
        for ep in uncovered_eps:
            if (rows.get(ep) or {}).get("coverage_kind") != "none":
                return _fail("an entry point no scenario binds and no oracle replayed is uncovered: %s" % rows.get(ep))

        cs = doc["coverage_summary"]
        want_summary = {"entry_points": len(eps), "by_oracle": 1, "by_scenario": 1,
                        "uncovered": len(eps) - 2}
        if cs != want_summary:
            return _fail("the receipt must count the three kinds: %s (want %s)" % (cs, want_summary))
        if cs["by_oracle"] + cs["by_scenario"] + cs["uncovered"] != cs["entry_points"]:
            return _fail("the three counts must be disjoint and total: %s" % cs)

        # a scenario the QUALIFICATION did not pass covers nothing, however
        # well its destination replay went: the source never demonstrated the
        # capability, so there is nothing to have reproduced
        _qualify(inconclusive="sc:covered")
        subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        unq = load_json(root / parity_receipt_path("disabled"))
        urow = next(r for r in unq["entry_points"] if r["entry_point"] == by_scenario)
        if urow["coverage_kind"] != "none" or urow["verdict"] != "INCONCLUSIVE":
            return _fail("an unqualified scenario covers nothing whatever its replay says: %s" % urow)
        if unq["coverage_summary"]["by_scenario"] != 0:
            return _fail("the count must drop with it: %s" % unq["coverage_summary"])
        _qualify()

        # the control for "passing all existing scenarios cannot fill a gap":
        # every scenario on disk now PASSes, and the entry points none of them
        # binds are covered by exactly as much as before
        write_canonical(root / scenario_parity_dir("disabled") / (scenario_slug("sc:replay-failed") + ".json"), {
            "schema": "rhoai3.scenario-parity/v1", "scenario": "sc:replay-failed", "entry_point": replay_failed,
            "verdict": "PASS", "reason": "", "receipt_sha256": digest, "corpus_sha256": corpus_sha})
        subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        after = load_json(root / parity_receipt_path("disabled"))["coverage_summary"]
        if after != dict(want_summary, by_scenario=2, uncovered=len(eps) - 3):
            return _fail("a scenario that now passes covers its OWN entry point and no other: %s" % after)
        return 0


def main() -> int:
    if _scenario_coverage_case():
        return 1
    if _no_corpus_case() or _missing_exposed_model_case() or _stale_receipt_case() or _security_mode_case():
        return 1
    if (_fixture_variant_case() or _variant_refused_write_case() or _variant_revert_then_read_case() or _diagnostic_probe_case()
            or _body_diff_case()):
        return 1
    if _acceptance_binding_case():
        return 1
    if _effects_identity_parity_case():
        return 1
    if _effectless_reset_case():
        return 1
    if _capture_contract_case() or _header_contract_case():
        return 1
    if _navigation_receipt_case():
        return 1
    if _orphaned_records_case():
        return 1
    with tempfile.TemporaryDirectory(prefix="scen-") as td:
        t = Path(td)
        root = specimens.build_dest(t / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        specimens.prepare_loop(root)
        rec = pipeline.admit(root)
        if rec["status"] != "ADMITTED":
            return _fail("fixture not admitted: %s" % rec["reasons"][:3])
        digest = load_json(root / "evidence/planning/admission-receipt.json")["receipt_digest"]
        ep = sorted(str(e["id"]) for e in load_json(root / "evidence/planning/evidence-bundle.json")["entry_points"])[0]
        corpus = json.loads(json.dumps(CORPUS))
        for sc in corpus["scenarios"]:
            sc["entry_point"] = ep
        (root / "verification" / "scenarios" / "bodies").mkdir(parents=True, exist_ok=True)
        (root / "verification" / "scenarios" / "bodies" / "create-owner.json").write_text(json.dumps({"id": 7, "lastName": "Franklin"}), encoding="utf-8")
        write_canonical(root / "verification" / "scenarios" / "corpus.json", corpus)
        corpus_sha = corpus_digest(load_json(root / "verification" / "scenarios" / "corpus.json"))
        reqs = {sc["id"]: request_of(root, sc) for sc in corpus["scenarios"]}

        # the source: a service that requires the body and really deletes
        Service.owners = {}
        Service.lie_on_delete = False
        src, src_url = serve()
        from _oracle_common import http_observe as _obs
        before_create = _obs(src_url, "GET", "/api/owners/7")
        create = reqs["sc:create-owner"]
        from _oracle_common import http_observe
        created = http_observe(src_url, "POST", "/api/owners", body=create["body"], headers={"Content-Type": "application/json"})
        if created["status"] != 201:
            return _fail("test setup: the source must create with a body")
        eff_created = http_observe(src_url, "GET", "/api/owners/7")
        _capture(root, src_url, "sc:create-owner", create["request_sha256"],
                 {"status": 201, "body_kind": "json", "body_sha256": eff_created["body_sha256"], "headers": created["headers"]},
                 [{"id": "eff:owner-7", "method": "GET", "path": "/api/owners/7", "status": eff_created["status"], "body_sha256": eff_created["body_sha256"]}],
                 digest, corpus_sha,
                 before=[{"id": "eff:owner-7", "method": "GET", "path": "/api/owners/7", "status": 404, "body_sha256": before_create["body_sha256"]}])
        # the source starts the delete with the row PRESENT: that is the state
        # a destination has to be in before the delete means anything
        before_delete = http_observe(src_url, "GET", "/api/owners/7")
        delete_obs = http_observe(src_url, "DELETE", "/api/owners/7")
        eff_gone = http_observe(src_url, "GET", "/api/owners/7")
        _capture(root, src_url, "sc:delete-owner", reqs["sc:delete-owner"]["request_sha256"],
                 {"status": delete_obs["status"], "body_kind": delete_obs["body_kind"], "body_sha256": delete_obs["body_sha256"]},
                 [{"id": "eff:owner-7-gone", "method": "GET", "path": "/api/owners/7", "status": eff_gone["status"], "body_sha256": eff_gone["body_sha256"]}],
                 digest, corpus_sha,
                 before=[{"id": "eff:owner-7-gone", "method": "GET", "path": "/api/owners/7", "status": before_delete["status"], "body_sha256": before_delete["body_sha256"]}])
        src.shutdown()

        # the destination: the same implementation. The replay must PASS.
        Service.owners = {}
        Service.lie_on_delete = False
        dest, dest_url = serve()
        p = subprocess.run([sys.executable, str(COMPARE), "--no-reset", "--root", str(root), "--scenario", "sc:create-owner", "--dest-url", dest_url], text=True, capture_output=True)
        if p.returncode != 0:
            return _fail("an identical destination must PASS the recorded write: %s%s" % (p.stdout, p.stderr))
        v = load_json(root / SCENARIO_PARITY / (scenario_slug("sc:create-owner") + ".json"))
        if v["observed"]["status"] != 201 or not v["effects"] or not v["effects"][0]["match"]:
            return _fail("the replay must send the body and check the effect: %s" % v)
        # the capture is bound to the frozen source and the corpus, never to
        # the receipt: one taken under a non-authoritative receipt (recorded
        # receipt_sha256 "") compares just the same, one from another bundle
        # or with no bundle digest is INCONCLUSIVE, and the VERDICT stays
        # bound to the current receipt
        cap_p = root / SCENARIO_ORACLES / (scenario_slug("sc:create-owner") + ".json")
        cap = load_json(cap_p)
        bundle_sha = load_json(root / "evidence/planning/evidence-bundle.json")
        from planner.canonical import digest as _digest
        bundle_sha = _digest(bundle_sha)
        for patch_cap, want_rc, needle in ((dict(cap, receipt_sha256="", evidence_bundle_sha256=bundle_sha), 0, ""),
                                           (dict(cap, receipt_sha256="", evidence_bundle_sha256="0" * 64), 1, "describes bundle"),
                                           ({k: v for k, v in cap.items() if k != "evidence_bundle_sha256"}, 1, "not bound to the frozen source")):
            write_canonical(cap_p, patch_cap)
            Service.owners = {}
            p = subprocess.run([sys.executable, str(COMPARE), "--no-reset", "--root", str(root), "--scenario", "sc:create-owner", "--dest-url", dest_url], text=True, capture_output=True)
            if p.returncode != want_rc or needle not in p.stderr:
                return _fail("capture binding (%s): rc=%s %s" % (needle or "stale receipt, same bundle", p.returncode, p.stderr[-300:]))
            v = load_json(root / SCENARIO_PARITY / (scenario_slug("sc:create-owner") + ".json"))
            if v["receipt_sha256"] != digest:
                return _fail("the verdict stays bound to the current receipt: %s" % v["receipt_sha256"])
        write_canonical(cap_p, cap)
        # a POSITIVE scenario whose capture FAILED qualification is a
        # source-side fixture failure: parity is not asked, the verdict is
        # INCONCLUSIVE (never a FAIL that becomes a repair card), and only a
        # qualification bound to THIS capture counts
        import hashlib as _hashlib
        from _scenarios import QUALIFICATION
        cap_sha = _hashlib.sha256(cap_p.read_bytes()).hexdigest()
        write_canonical(root / QUALIFICATION, {"schema": "rhoai3.scenario-qualification/v1", "corpus_sha256": corpus_sha,
                                               "scenarios": {"sc:create-owner": {"capability": "FAIL", "intent": "positive", "reason": "expect_status: status 500",
                                                                                 "capture_sha256": cap_sha}}, "verdict": "FAIL"})
        Service.owners = {}
        p = subprocess.run([sys.executable, str(COMPARE), "--no-reset", "--root", str(root), "--scenario", "sc:create-owner", "--dest-url", dest_url], text=True, capture_output=True)
        v = load_json(root / SCENARIO_PARITY / (scenario_slug("sc:create-owner") + ".json"))
        if p.returncode != 1 or v["verdict"] != "INCONCLUSIVE" or "source fixture failed qualification" not in v["reason"] or Service.owners:
            return _fail("a fixture-failed positive scenario is INCONCLUSIVE and nothing is replayed: rc=%s %s %s" % (p.returncode, v.get("reason"), p.stderr[-200:]))
        # ... a stale qualification (another capture) does not short-circuit
        write_canonical(root / QUALIFICATION, {"schema": "rhoai3.scenario-qualification/v1", "corpus_sha256": corpus_sha,
                                               "scenarios": {"sc:create-owner": {"capability": "FAIL", "intent": "positive", "reason": "old", "capture_sha256": "0" * 64}}, "verdict": "FAIL"})
        p = subprocess.run([sys.executable, str(COMPARE), "--no-reset", "--root", str(root), "--scenario", "sc:create-owner", "--dest-url", dest_url], text=True, capture_output=True)
        if p.returncode != 0 or load_json(root / SCENARIO_PARITY / (scenario_slug("sc:create-owner") + ".json"))["verdict"] != "PASS":
            return _fail("a stale qualification judged another capture and does not stop the comparison: %s" % p.stderr[-200:])
        (root / QUALIFICATION).unlink()
        # leave the destination as the original create left it: owner 7
        # present, which is the state the delete below starts from
        Service.owners = {"7": {"id": 7, "lastName": "Franklin"}}
        p = subprocess.run([sys.executable, str(COMPARE), "--no-reset", "--root", str(root), "--scenario", "sc:delete-owner", "--dest-url", dest_url], text=True, capture_output=True)
        if p.returncode != 0:
            return _fail("an identical destination must PASS the recorded delete: %s%s" % (p.stdout, p.stderr))
        dest.shutdown()

        # a destination that answers the delete but keeps the row: response
        # equality passes, the resulting state does not
        Service.owners = {}
        Service.lie_on_delete = True
        liar, liar_url = serve()
        # a destination whose row is already gone is not in the source's
        # initial state: the delete cannot be compared there at all
        p = subprocess.run([sys.executable, str(COMPARE), "--no-reset", "--root", str(root), "--scenario", "sc:delete-owner", "--dest-url", liar_url], text=True, capture_output=True)
        if p.returncode != 1 or "not in the state the source started from" not in p.stderr:
            return _fail("a destination that never had the row must refuse the delete comparison: rc=%s %s" % (p.returncode, p.stderr[:300]))
        subprocess.run([sys.executable, str(COMPARE), "--no-reset", "--root", str(root), "--scenario", "sc:create-owner", "--dest-url", liar_url], text=True, capture_output=True)
        p = subprocess.run([sys.executable, str(COMPARE), "--no-reset", "--root", str(root), "--scenario", "sc:delete-owner", "--dest-url", liar_url], text=True, capture_output=True)
        if p.returncode != 1 or "effect eff:owner-7-gone" not in p.stderr:
            return _fail("a 204 that deleted nothing must FAIL its resulting-state check: rc=%s %s" % (p.returncode, p.stderr[:300]))
        v = load_json(root / SCENARIO_PARITY / (scenario_slug("sc:delete-owner") + ".json"))
        if v["verdict"] != "FAIL" or v["observed"]["status"] != 204:
            return _fail("the record must show an identical response and a divergent effect: %s" % v)
        liar.shutdown()

        # a corpus edited after the source was captured is not comparable
        Service.owners = {}
        Service.lie_on_delete = False
        dest2, dest2_url = serve()
        edited = load_json(root / "verification" / "scenarios" / "corpus.json")
        edited["scenarios"][0]["path"] = "/api/owners?tampered=1"
        write_canonical(root / "verification" / "scenarios" / "corpus.json", edited)
        p = subprocess.run([sys.executable, str(COMPARE), "--no-reset", "--root", str(root), "--scenario", "sc:create-owner", "--dest-url", dest2_url], text=True, capture_output=True)
        if p.returncode != 1 or "corpus" not in p.stderr:
            return _fail("a corpus that changed after capture must refuse: rc=%s %s" % (p.returncode, p.stderr[:300]))
        write_canonical(root / "verification" / "scenarios" / "corpus.json", corpus)
        dest2.shutdown()

        # the receipt groups scenarios by entry point: all must pass
        Service.owners = {}
        dest3, dest3_url = serve()
        for sid in ("sc:create-owner", "sc:delete-owner"):
            subprocess.run([sys.executable, str(COMPARE), "--no-reset", "--root", str(root), "--scenario", sid, "--dest-url", dest3_url], text=True, capture_output=True)
        p = subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        doc = load_json(root / "verification" / "parity" / "receipt.json")
        row = next(r for r in doc["entry_points"] if r["entry_point"] == ep)
        if row["verdict"] != "PASS" or sorted(row["scenarios"]) != ["sc:create-owner", "sc:delete-owner"]:
            return _fail("an entry point's verdict is the conjunction of its scenarios: %s" % row)

        # a scenario the corpus REQUIRES and nothing compared: the receipt
        # enumerated result files, so a required scenario could disappear and
        # the entry point still read PASS
        with_extra = load_json(root / "verification" / "scenarios" / "corpus.json")
        with_extra["scenarios"].append({"id": "sc:required-second", "entry_point": ep, "method": "GET", "path": "/api/owners",
                                        "body_absent": True, "reset_before": False, "effects": [], "normalization": []})
        write_canonical(root / "verification" / "scenarios" / "corpus.json", with_extra)
        subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        doc = load_json(root / "verification" / "parity" / "receipt.json")
        row = next(r for r in doc["entry_points"] if r["entry_point"] == ep)
        if row["verdict"] != "INCONCLUSIVE" or "sc:required-second" not in row["reason"]:
            return _fail("a required scenario with no result must be INCONCLUSIVE, never PASS: %s" % row)
        # and a result compared against a different corpus satisfies nothing
        write_canonical(root / "verification" / "scenarios" / "corpus.json", corpus)
        stale = load_json(root / SCENARIO_PARITY / (scenario_slug("sc:create-owner") + ".json"))
        stale["corpus_sha256"] = "0" * 64
        write_canonical(root / SCENARIO_PARITY / (scenario_slug("sc:create-owner") + ".json"), stale)
        subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        doc = load_json(root / "verification" / "parity" / "receipt.json")
        row = next(r for r in doc["entry_points"] if r["entry_point"] == ep)
        if row["verdict"] != "INCONCLUSIVE" or "corpus" not in row["reason"]:
            return _fail("a result compared against another corpus must not satisfy coverage: %s" % row)
        dest3.shutdown()

        # a scenario that declares reset_before and cannot restore that state
        # is INCONCLUSIVE: the comparison never happens
        Service.owners = {}
        dest4, dest4_url = serve()
        p = subprocess.run([sys.executable, str(COMPARE), "--root", str(root), "--scenario", "sc:create-owner",
                            "--dest-url", dest4_url, "--reset-cmd", "%s -c 'import sys; sys.exit(3)'" % sys.executable],
                           text=True, capture_output=True)
        if p.returncode != 1 or "could not be restored" not in p.stderr:
            return _fail("a reset that fails must stop the comparison: rc=%s %s" % (p.returncode, p.stderr[:300]))
        v = load_json(root / SCENARIO_PARITY / (scenario_slug("sc:create-owner") + ".json"))
        if v["verdict"] != "INCONCLUSIVE" or v["reset"]["rc"] != 3:
            return _fail("the failed reset must be recorded beside the verdict: %s" % v.get("reset"))
        dest4.shutdown()
    print("OK: scenario-parity selftest (the recorded body and headers are replayed; a recorded Location header that the destination omits FAILs, and a 201 against a capture with no header map is INCONCLUSIVE; the capture is the first response (redirects not followed) and only the declared origins are mapped in Location; a preflight is not a write, carries Origin + Access-Control-Request-Method and no credentials; CORS coverage is per policy and the source's policies come from M1's model; the headers the source exposes are asserted too, and full bodies are retained as digest-bound evidence; a write with no declared effect refuses; a 204 that deleted nothing FAILs on its resulting state; an effect-less scenario that declares reset_before still runs the reset, notes that no before state was declared and "
          "compares on the first response (PASS when equal, FAIL typed by its diffs when not), while one WITH effects and no before "
          "state stays INCONCLUSIVE; a corpus edited after capture refuses; the capture is bound to the frozen source and the corpus, never to the admission receipt (a stale receipt is a note on the producer receipt, not a refusal; a capture from another bundle or with no bundle digest is INCONCLUSIVE; the verdict stays receipt-bound); an entry point passes only when every REQUIRED scenario passes, and a missing or foreign-corpus result is INCONCLUSIVE; a declared reset that fails stops the comparison; no corpus is idle with a receipt that says so; "
          "the security mode binds the evidence: the qualification, the scenario verdict and the parity receipt each record the mode "
          "they are of, and the disabled captures copied into the enabled directory are refused by the comparator, the qualification "
          "gate and the receipt composer alike -- no cross-mode reuse; a scenario naming an effects_identity has its destination "
          "read-backs taken as that identity too, so a refused write's state is compared as the source saw it while the write "
          "itself stays anonymous, and a capture that took the read-backs as somebody else is refused by reference rather than "
          "compared; a verdict produced during an acceptance verify binds to the CANDIDATE and the ISSUED card (--issued): the "
          "work list the acceptance path rebuilt on the candidate is not a refusal there, the verdict and the receipt record "
          "the candidate, the receipt the card was minted under and the card, a verdict measured for another card or on "
          "another candidate satisfies no coverage, and another receipt, another candidate, a tree edited after verification "
          "or no issued card at all refuse by name -- while without the flag the M4 road still refuses a stale seal; "
          "a comparison that PASSed is not the whole of the redirect ruling: the composer reads the BOUNDED NAVIGATION "
          "records written beside it, an entry point whose redirect target is dead, loops or never settles becomes FAIL "
          "typed navigation naming the address and the status it ended on -- as its own obligation row beside the redirect's PASS (ADR-020) -- "
          "a navigation that reached the UI is recorded navigation: ok and changes no verdict, and a comparison that "
          "FAILED keeps its own diff and its own typing; "
          "and a receipt judges the CURRENT corpus from the records that belong to it: a scenario this corpus does not "
          "declare, a declared scenario under a file name that is not its slug, a record compared against another "
          "corpus digest and one compared in another security mode are each named under orphaned_records with the "
          "reason and counted in no row -- the v9 receipt's 'no scenario <id> in the corpus' and 'N result files' "
          "cannot be produced by a leftover -- while the scenario an orphan was the only record of is INCONCLUSIVE "
          "for the orphan's own reason, and the same directory with its records put right composes a PASS; a fixture variant's refused PUT and DELETE are measured, not waived: their unchanged_under_refusal read-backs are taken as the declared reader against the source's own captures under the variant, an identical destination PASSes with each row saying what it proves, a destination that answers the same 401 and writes anyway FAILs naming the refused write, a refused write with no identity to read its state as stays INCONCLUSIVE naming the missing identity beside the rule, and the variant receipt records what each refused write proves; with no second identity a refused write is compared REVERT-THEN-READ -- the "
 "baseline, the variant and its revert visited in that order through the reset script, the post-revert reads judged against the "
 "source's baseline reads -- an identical destination PASSes, one that writes despite the 401 FAILs, a revert that finds "
 "unexpected state is INCONCLUSIVE naming it, and --no-reset is refused; the variant is re-applied after the after-reads, so a "
 "following variant read that declares no reset is still judged on the variant state; an entry point is covered by its READ ORACLE or by a QUALIFIED scenario that explicitly binds it and whose destination replay passed -- the two recorded as distinct kinds with the scenario ids, counted three ways on the receipt (oracle / scenario / not at all) -- while a scenario that never ran, one that failed and one the qualification did not pass cover nothing, and passing every scenario on disk fills no gap at an entry point none of them binds; a body mismatch carries body_diff -- "
 "order-only lists once per path with [*] in the summary, values, missing fields, types and non-JSON lines named, the destination "
 "body retained beside the verdict and pointed at from the receipt row -- for scenario and read-oracle verdicts alike)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
