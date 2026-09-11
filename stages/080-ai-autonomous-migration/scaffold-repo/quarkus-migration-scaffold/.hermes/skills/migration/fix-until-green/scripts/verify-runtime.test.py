#!/usr/bin/env python3
"""verify-runtime selftest: the architect's negative controls for the boot gate.

Each case is one way the gate used to accept evidence about something other
than the application it was asked to verify.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "verify-runtime.py"
sys.path.insert(0, str(HERE.parents[4] / "lib"))

spec = importlib.util.spec_from_file_location("verify_runtime", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore[union-attr]

DS = {"db_kind": "postgresql", "db_version": "16", "jdbc_extension": "io.quarkus:quarkus-jdbc-postgresql",
      "profile": "prod", "instance": "fixture", "jdbc_url_env": "FX_URL", "username_env": "FX_USER",
      "password_env": "FX_PASSWORD"}


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


class Stranger(BaseHTTPRequestHandler):
    def log_message(self, *a):
        return

    def do_GET(self):
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()


def _app(root: Path, files: dict[str, str]) -> None:
    base = root / "target" / "quarkus-app"
    for rel, body in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")


def main() -> int:
    os.environ.update({"FX_URL": "jdbc:postgresql://db:5432/x", "FX_USER": "u", "FX_PASSWORD": "p"})
    with tempfile.TemporaryDirectory(prefix="rt-") as td:
        root = Path(td)
        _app(root, {"quarkus-run.jar": "launcher", "lib/main/pg.jar": "driver", "app/app.jar": "code"})
        files, manifest = mod.artifact_manifest(root)
        if len(files) != 3 or not manifest:
            return _fail("the manifest is the whole quarkus-app directory: %s" % sorted(files))
        # changing a file that is NOT the launcher must change the artifact
        _app(root, {"lib/main/pg.jar": "driver-tampered"})
        _, manifest2 = mod.artifact_manifest(root)
        if manifest2 == manifest:
            return _fail("a change anywhere in the application must change its digest")

        pkg = {"artifact": "target/quarkus-app", "artifact_sha256": manifest, "candidate_sha256": "cand"}
        b = mod.boot(root, DS, ["prod"], pkg, 18099, "/", 5, "java", "cand")
        if b["ready"] or "not the one packaging verified" not in b["detail"]:
            return _fail("starting an application that changed after packaging must refuse: %s" % b)

        pkg = {"artifact": "target/quarkus-app", "artifact_sha256": manifest2, "candidate_sha256": "cand"}
        b = mod.boot(root, DS, ["prod"], pkg, 18099, "/", 5, "java", "other-candidate")
        if b["ready"] or "another tree" not in b["detail"]:
            return _fail("startup evidence must be about the tree packaging verified: %s" % b)

        # an unrelated server holding the port
        srv = HTTPServer(("127.0.0.1", 0), Stranger)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        b = mod.boot(root, DS, ["prod"], pkg, port, "/", 5, "java", "cand")
        srv.shutdown()
        if b["ready"] or "already answering" not in b["detail"]:
            return _fail("a port that answers before anything is started must refuse: %s" % b)

        # the error lines, not the closing summary: a failure named halfway
        # through a Maven log must reach the receipt
        log = ("[INFO] building\n"
               "[ERROR] \t[error]: Build step SpringDataJPAProcessor#build threw an exception: UnableToParseMethodException: Method 'findPetTypes' of repository 'a.PetRepository'\n"
               + "[INFO] surefire summary line\n" * 200)
        errs = mod._errors(log)
        if "findPetTypes" not in errs or "surefire summary" in errs:
            return _fail("the receipt must carry the error lines, not the tail: %r" % errs[:200])
        if mod._tail(log).find("findPetTypes") != -1:
            return _fail("test setup: the tail must NOT contain the error, or this proves nothing")

        # the datasource has to appear in the application's own startup report
        ok, why = mod.database_ready("INFO  [io.quarkus] Installed features: [agroal, cdi, hibernate-orm, jdbc-postgresql, rest]", DS)
        if not ok:
            return _fail("the decided extension in the installed features is datasource evidence: %s" % why)
        ok, why = mod.database_ready("INFO  [io.quarkus] Installed features: [cdi, rest]", DS)
        if ok or "do not include" not in why:
            return _fail("an application that started without the datasource is not ready: %s" % why)
        ok, why = mod.database_ready("nothing useful here", DS)
        if ok or "never reported" not in why:
            return _fail("no report at all is not evidence of a datasource: %s" % why)

        # a process that answers nothing, with a stranger on the port, must not
        # be attributed: this is the exact case the review reproduced
        srv = HTTPServer(("127.0.0.1", 0), Stranger)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        quiet = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
        try:
            owned, why = mod.port_owner(port, quiet.pid)
            if owned:
                return _fail("a port held by another process must not be attributed to ours")
            if "another process" not in why and "/proc" not in why:
                return _fail("the refusal must say why: %s" % why)
        finally:
            quiet.kill()
            srv.shutdown()
    print("OK: verify-runtime selftest (the artifact is the whole quarkus-app directory; a changed or foreign artifact, a changed candidate, an occupied port, an unattributed listener and a datasource that never started all refuse)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
