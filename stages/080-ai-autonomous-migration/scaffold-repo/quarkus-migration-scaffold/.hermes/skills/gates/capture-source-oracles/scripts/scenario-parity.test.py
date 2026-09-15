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


def verify_gaps(root: Path) -> list[str]:
    from planner.admission import verify_receipt
    return verify_receipt(root, require_admitted=False)[1]


def main() -> int:
    if _no_corpus_case() or _missing_exposed_model_case() or _stale_receipt_case() or _security_mode_case():
        return 1
    if _effects_identity_parity_case():
        return 1
    if _effectless_reset_case():
        return 1
    if _capture_contract_case() or _header_contract_case():
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
          "compared)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
