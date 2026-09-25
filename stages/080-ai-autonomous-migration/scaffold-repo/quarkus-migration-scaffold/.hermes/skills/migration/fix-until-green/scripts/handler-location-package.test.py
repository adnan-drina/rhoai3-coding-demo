#!/usr/bin/env python3
"""V16-5 package-level fixture: a handler parameter's catalog action, packaged
and run on the pinned Spring compatibility stack.

fixtures/handler-location-package holds a Spring Web controller (quarkus-spring-web
+ quarkus-rest-jackson, the pinned platform BOM) under a non-root application
path (quarkus.http.root-path=/ledger). Its handlers take `@Context UriInfo`
-- the handler_parameters.undocumented action for UriComponentsBuilder -- one
of them without using it, and a helper in the SAME file keeps an ordinary
jakarta.ws.rs.core.UriBuilder (the symbol_renames mapping). Asked of the real
platform, offline, from the local Maven repository:

  * the BARE RENAME (the handler takes an unannotated UriBuilder, as v16
    t_7074fcda wrote it) fails augmentation at the resource method, and the
    structural check (worklist._assess_handler_parameters) refuses it;
  * the documented repair packages, the structural check accepts it, and the
    packaged application answers: POST creates with 201 and the absolute
    Location http://<host>:<port>/ledger/api/entries/7 (the application path
    once), the handler that never uses its UriInfo answers 200, and the helper's
    builder still builds /archive/7.

When the local environment cannot package or start it (no mvn, java or javac;
the pinned artifacts not in the local Maven repository; no loopback port), the
case prints SKIP with the precise reason and exits 0.
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
FIXTURE = HERE.parent / "fixtures" / "handler-location-package"
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
from planner.dest_model import dest_model  # noqa: E402
from planner.worklist import (_assess_handler_parameters, _unit_path, handler_parameter_sites, handler_parameters,  # noqa: E402
                              symbol_renames, unit_target_symbols)

RETIRED = "org.springframework.web.util.UriComponentsBuilder"
CONTROLLER = "src/main/java/org/acme/ledger/rest/EntryRestController.java"
_OFFLINE = ("Cannot access", "offline mode", "Could not resolve", "could not be resolved",
            "Non-resolvable import POM", "has not been downloaded")


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _skip(msg: str) -> int:
    print("SKIP: handler-location-package: %s" % msg)
    return 0


def _pin() -> dict:
    return json.loads((GOLDEN / ".hermes" / "pins.json").read_text(encoding="utf-8"))["pins"]["quarkus_platform"]


def _mvn(root: Path, *goals: str) -> subprocess.CompletedProcess[str]:
    pin = _pin()
    return subprocess.run(["mvn", "-B", "-q", "-o", "-s", str(GOLDEN / ".mvn" / "settings.xml"),
                           "-Dquarkus.platform.group-id=%s" % pin["group_id"],
                           "-Dquarkus.platform.version=%s" % pin["version"], *goals],
                          cwd=str(root), text=True, capture_output=True, timeout=900)


def _offline_gap(p: subprocess.CompletedProcess[str]) -> str:
    out = p.stdout + p.stderr
    hit = next((n for n in _OFFLINE if n in out), "")
    if not hit:
        return ""
    return "the pinned platform's artifacts are not all in the local Maven repository (%s)" % next(
        (ln.strip() for ln in out.splitlines() if hit in ln), hit)[:240]


def _bare(root: Path) -> None:
    """The v16 t_7074fcda shape: the symbol_renames target at the handler."""
    p = root / CONTROLLER
    p.write_text(p.read_text(encoding="utf-8").replace(
        "addEntry(@RequestBody Entry entry, @Context UriInfo uriInfo) {\n        entry.id = 7;\n"
        "        URI location = uriInfo.getBaseUriBuilder()",
        "addEntry(@RequestBody Entry entry, UriBuilder ucBuilder) {\n        entry.id = 7;\n"
        "        URI location = ucBuilder"), encoding="utf-8")


def _structural(root: Path, sites: list[dict]) -> dict[str, str]:
    """The planner's sealed rows for a UriComponentsBuilder unit whose handlers
    are `sites`, assessed against the compiler model of the tree."""
    targets = unit_target_symbols([{"kind": "type", "fqn": RETIRED, "path": CONTROLLER}], symbol_renames(GOLDEN), {}, None,
                                  {RETIRED: sites}, handler_parameters(GOLDEN)["undocumented"])
    by_path: dict[str, list[dict]] = defaultdict(list)
    for t in dest_model(root).get("types") or []:
        by_path[_unit_path(t)].append(t)
    return {r["member"].split("#", 1)[1]: r["verdict"]
            for r in _assess_handler_parameters({"target_symbols": targets}, by_path, "unit/diagnostic-family/v1")}


def _http(method: str, url: str, body: bytes | None = None) -> tuple[int, dict, str]:
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Content-Type": "application/json"} if body is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 - the fixture's own loopback app
            return int(resp.status), {k.lower(): v for k, v in resp.headers.items()}, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return int(exc.code), {k.lower(): v for k, v in exc.headers.items()}, exc.read().decode("utf-8", "replace")


def _serve(root: Path) -> int:
    try:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
    except OSError as exc:
        return _skip("no loopback port to start the packaged application on (%s)" % exc)
    log = (root / "run.log").open("w")
    proc = subprocess.Popen(["java", "-Dquarkus.http.host=127.0.0.1", "-Dquarkus.http.port=%d" % port,
                             "-jar", str(root / "target" / "quarkus-app" / "quarkus-run.jar")],
                            cwd=str(root), stdout=log, stderr=subprocess.STDOUT)
    base = "http://127.0.0.1:%d/ledger" % port
    try:
        deadline = time.time() + 60
        while True:
            try:
                status, _h, _b = _http("GET", base + "/api/entries/1/archive")
                break
            except (urllib.error.URLError, ConnectionError, OSError):
                if proc.poll() is not None or time.time() > deadline:
                    return _fail("the packaged application did not start: %s" % (root / "run.log").read_text()[-600:])
                time.sleep(0.5)
        status, headers, body = _http("POST", base + "/api/entries", b'{"name":"first"}')
        if status != 201 or headers.get("location") != base + "/api/entries/7" or json.loads(body).get("id") != 7:
            return _fail("POST creates with 201 and the absolute Location under the application path once: %s %s %s"
                         % (status, headers.get("location"), body))
        status, _h, body = _http("POST", base + "/api/entries/touch", b'{"name":"second"}')
        if status != 200 or json.loads(body).get("name") != "second":
            return _fail("the handler that never uses its @Context UriInfo still answers: %s %s" % (status, body))
        status, _h, body = _http("GET", base + "/api/entries/7/archive")
        if status != 200 or body.strip() != "/archive/7":
            return _fail("the helper's ordinary UriBuilder still builds its path: %s %r" % (status, body))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
    return 0


def main() -> int:
    for tool in ("mvn", "java", "javac"):
        if not shutil.which(tool):
            return _skip("%s is not on PATH, so the platform cannot package and run the fixture here" % tool)
    with tempfile.TemporaryDirectory(prefix="handler-location-pkg-") as td:
        root = Path(td) / "fixture"
        shutil.copytree(FIXTURE, root)
        (root / ".hermes").mkdir()
        (root / ".hermes" / "pins.json").write_text(json.dumps({"pins": {"quarkus_platform": {"java_release": 21}}}),
                                                    encoding="utf-8")
        cp = root / "verification" / "build" / ".work" / "classpath.txt"
        cp.parent.mkdir(parents=True)
        p = _mvn(root, "dependency:build-classpath", "-Dmdep.outputFile=%s" % cp)
        if p.returncode != 0:
            return _skip(_offline_gap(p) or "the classpath could not be resolved offline: %s" % (p.stdout + p.stderr)[-300:])
        # the planner finds exactly the handlers, never the helper
        fqn = "org.acme.ledger.rest.EntryRestController"
        sites = handler_parameter_sites(dest_model(root), [CONTROLLER], "jakarta.ws.rs.core.UriInfo")
        if sorted((s["member"], s["parameter"]) for s in sites) != [("addEntry", "uriInfo"), ("touch", "uriInfo")]:
            return _fail("the handler parameters are the two handlers' and never the helper's: %s" % sites)
        sealed = [{"path": CONTROLLER, "type": fqn, "member": m, "parameter": "ucBuilder"} for m in ("addEntry", "touch")]

        # --- the bare rename at the handler ---
        pristine = (root / CONTROLLER).read_text(encoding="utf-8")
        _bare(root)
        verdicts = _structural(root, sealed)
        if verdicts.get("addEntry(ucBuilder)") != "violates" or verdicts.get("touch(ucBuilder)") != "ok":
            return _fail("the structural check refuses the unannotated UriBuilder at the handler: %s" % verdicts)
        p = _mvn(root, "package", "-DskipTests")
        out = p.stdout + p.stderr
        if p.returncode == 0:
            return _fail("the bare rename at a handler must NOT package")
        if "addEntry(org.acme.ledger.rest.Entry entry, jakarta.ws.rs.core.UriBuilder ucBuilder)" not in out:
            gap = _offline_gap(p)
            return _skip(gap) if gap else _fail("the bare rename fails for another reason: %s" % out[-600:])

        # --- the documented repair ---
        (root / CONTROLLER).write_text(pristine, encoding="utf-8")
        shutil.rmtree(root / "target", ignore_errors=True)
        verdicts = _structural(root, sealed)
        if set(verdicts.values()) != {"ok"}:
            return _fail("the structural check accepts @Context UriInfo at the handlers: %s" % verdicts)
        p = _mvn(root, "package", "-DskipTests")
        if p.returncode != 0:
            return _fail("the documented repair packages: %s" % (p.stdout + p.stderr)[-900:])
        if _serve(root):
            return 1
    print("OK: handler-location-package (pinned platform %s, offline, quarkus-spring-web + quarkus-rest-jackson: an "
          "unannotated UriBuilder handler parameter fails augmentation at the resource method and the structural check "
          "refuses it; @Context UriInfo at the handlers packages and the structural check accepts it; the packaged "
          "application answers POST 201 with Location http://127.0.0.1:<port>/ledger/api/entries/7, the unused-parameter "
          "handler 200, and the helper's UriBuilder /archive/7)" % _pin()["version"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
