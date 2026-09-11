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

import json
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3] / "lib"))
from _scenarios import load_corpus, SCENARIO_ORACLES, SCENARIO_PARITY, corpus_digest, request_of, scenario_slug  # noqa: E402
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
    write_canonical(root / SCENARIO_ORACLES / (scenario_slug(sc_id) + ".json"), {
        "schema": "rhoai3.source-scenario/v1", "scenario": sc_id, "entry_point": next(s["entry_point"] for s in CORPUS["scenarios"] if s["id"] == sc_id),
        "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "status": "CAPTURED", "reason": "",
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
    return 0


def main() -> int:
    if _no_corpus_case():
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
    print("OK: scenario-parity selftest (the recorded body and headers are replayed; a recorded Location header that the destination omits FAILs, and a 201 against a capture with no header map is INCONCLUSIVE; the capture is the first response (redirects not followed) and only the declared origins are mapped in Location; a preflight is not a write, carries Origin + Access-Control-Request-Method and no credentials; CORS coverage is per policy and the source's policies come from M1's model; a write with no declared effect refuses; a 204 that deleted nothing FAILs on its resulting state; a corpus edited after capture refuses; an entry point passes only when every REQUIRED scenario passes, and a missing or foreign-corpus result is INCONCLUSIVE; a declared reset that fails stops the comparison; no corpus is idle with a receipt that says so)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
