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
from _scenarios import SCENARIO_ORACLES, SCENARIO_PARITY, corpus_digest, request_of, scenario_slug  # noqa: E402
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

    def log_message(self, *a):  # noqa: D102 - quiet
        return

    def _send(self, code: int, payload=None):
        body = json.dumps(payload).encode() if payload is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
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
        return self._send(201, payload)

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


def main() -> int:
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
        import urllib.request as _u
        r = _u.urlopen(_u.Request(src_url + "/api/owners", data=create["body"], method="POST", headers={"Content-Type": "application/json"}))
        if r.status != 201:
            return _fail("test setup: the source must create with a body")
        from _oracle_common import http_observe
        eff_created = http_observe(src_url, "GET", "/api/owners/7")
        _capture(root, src_url, "sc:create-owner", create["request_sha256"],
                 {"status": 201, "body_kind": "json", "body_sha256": eff_created["body_sha256"]},
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
    print("OK: scenario-parity selftest (the recorded body and headers are replayed; a write with no declared effect refuses; a 204 that deleted nothing FAILs on its resulting state; a corpus edited after capture refuses; an entry point passes only when every REQUIRED scenario passes, and a missing or foreign-corpus result is INCONCLUSIVE; a declared reset that fails stops the comparison)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
