#!/usr/bin/env python3
"""capture-source-oracles selftest with a local stub HTTP server.

- HTTP capture from the "source"; parity PASS against an identical "destination"; FAIL against a diverging one
- non-HTTP capture from an observation file; parity PASS / FAIL on normalized observations
- missing oracle → INCONCLUSIVE; parity receipt refuses until every entry point passes
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
GOLDEN = HERE.parents[4]
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
from planner import pipeline, specimens  # noqa: E402
from planner.canonical import load_json  # noqa: E402

CAPTURE = HERE / "capture-source-oracles.py"
COMPARE = HERE / "compare-runtime-parity.py"
RECEIPT = HERE / "compose-parity-receipt.py"


class Stub(BaseHTTPRequestHandler):
    payloads: dict[str, object] = {}

    def do_GET(self):  # noqa: N802
        body = json.dumps(self.payloads.get(self.path, {"path": self.path})).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # noqa: D102
        return


def serve(payloads: dict[str, object]) -> tuple[HTTPServer, str]:
    handler = type("H", (Stub,), {"payloads": payloads})
    srv = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="oracle-") as tmp:
        t = Path(tmp).resolve()
        root = specimens.build_dest(t / "dest", specimens.specimen("scheduled"), decisions=specimens.admitted_decisions("scheduled"))
        specimens.prepare_loop(root)
        if pipeline.admit(root)["status"] != "ADMITTED":
            return _fail("fixture not admitted: %s" % pipeline.admit(root)["reasons"][:3])
        # add an http specimen too for HTTP parity
        hroot = specimens.build_dest(t / "http", specimens.specimen("http"), decisions=specimens.admitted_decisions("http"))
        specimens.prepare_loop(hroot)
        pipeline.admit(hroot)
        src, src_url = serve({"/api/owners": [{"id": 1, "name": "a"}], "/api/pets": [{"id": 2}], "/api/vets": []})
        same, same_url = serve({"/api/owners": [{"name": "a", "id": 1}], "/api/pets": [{"id": 2}], "/api/vets": []})
        diff, diff_url = serve({"/api/owners": [{"id": 1, "name": "b"}], "/api/pets": [{"id": 2}], "/api/vets": []})
        try:
            p = _run([sys.executable, str(CAPTURE), "--root", str(hroot), "--base-url", src_url])
            if p.returncode != 0:
                return _fail("capture: %s%s" % (p.stdout, p.stderr))
            oracles = list((hroot / "verification" / "source-oracles").glob("*.json"))
            statuses = {load_json(o)["entry_point"]: load_json(o)["status"] for o in oracles}
            get_owner = next(k for k in statuses if "OwnerController#list" in k)
            post_owner = next(k for k in statuses if "OwnerController#create" in k)
            if statuses[get_owner] != "CAPTURED" or statuses[post_owner] != "INCONCLUSIVE":
                return _fail("capture statuses %s" % statuses)
            # parity PASS (key order differs but canonical JSON matches)
            if _run([sys.executable, str(COMPARE), "--root", str(hroot), "--entry-point", get_owner, "--dest-url", same_url]).returncode != 0:
                return _fail("identical destination must PASS")
            p = _run([sys.executable, str(COMPARE), "--root", str(hroot), "--entry-point", get_owner, "--dest-url", diff_url])
            if p.returncode != 1 or "FAIL" not in p.stderr:
                return _fail("diverging destination must FAIL: %s" % p.stderr)
            rec = load_json(hroot / "verification" / "parity" / [f for f in (hroot / "verification" / "parity").glob("*.json") if "list" in f.name][0].name)
            if rec["verdict"] != "FAIL":
                return _fail("parity record must retain FAIL")
            # parity receipt refuses (POST inconclusive + FAIL)
            p = _run([sys.executable, str(RECEIPT), "--root", str(hroot)])
            if p.returncode != 1:
                return _fail("parity receipt must refuse while any entry point is not PASS")
            # non-HTTP: scheduled + messaging observations
            eps = load_json(root / "evidence" / "planning" / "evidence-bundle.json")["entry_points"]
            sched = next(e["id"] for e in eps if e["kind"] == "scheduled")
            msg = next(e["id"] for e in eps if e["kind"] == "messaging")
            obs = t / "sync.log"
            obs.write_text("2026-09-08T10:00:00Z sync started\n2026-09-08T10:00:01Z synced 12 items\n", encoding="utf-8")
            obs2 = t / "orders.log"
            obs2.write_text("12:00:00 order 1 handled\n", encoding="utf-8")
            p = _run([sys.executable, str(CAPTURE), "--root", str(root), "--observation", "%s=%s" % (sched, obs), "--observation", "%s=%s" % (msg, obs2)])
            if p.returncode != 0:
                return _fail("non-http capture: %s" % p.stderr)
            dest_obs = t / "sync-dest.log"
            dest_obs.write_text("2026-09-09T11:22:33Z synced 12 items\n2026-09-09T11:22:32Z sync started\n", encoding="utf-8")
            if _run([sys.executable, str(COMPARE), "--root", str(root), "--entry-point", sched, "--dest-observation", str(dest_obs)]).returncode != 0:
                return _fail("timestamp-stripped identical observation must PASS")
            dest_obs.write_text("2026-09-09T11:22:33Z synced 11 items\n", encoding="utf-8")
            if _run([sys.executable, str(COMPARE), "--root", str(root), "--entry-point", sched, "--dest-observation", str(dest_obs)]).returncode != 1:
                return _fail("diverging observation must FAIL")
            p = _run([sys.executable, str(COMPARE), "--root", str(root), "--entry-point", msg])
            if p.returncode != 1 or "INCONCLUSIVE" not in p.stderr:
                return _fail("missing destination observation must be INCONCLUSIVE")
            # hand-written expected value is not accepted: oracle bound to another receipt
            op = next((root / "verification" / "source-oracles").glob("*.json"))
            doc = load_json(op)
            doc["receipt_sha256"] = "0" * 64
            op.write_text(json.dumps(doc), encoding="utf-8")
            p = _run([sys.executable, str(COMPARE), "--root", str(root), "--entry-point", doc["entry_point"], "--dest-observation", str(dest_obs)])
            if p.returncode != 1 or "another receipt" not in p.stderr and "belongs to receipt" not in p.stderr:
                return _fail("oracle from another receipt must be INCONCLUSIVE: %s" % p.stderr)
        finally:
            for s in (src, same, diff):
                s.shutdown()
    print("OK: capture-source-oracles (HTTP capture/parity PASS+FAIL; non-idempotent INCONCLUSIVE; non-HTTP observations; receipt binding; parity receipt refuses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
