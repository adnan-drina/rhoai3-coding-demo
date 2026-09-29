#!/usr/bin/env python3
"""V26-6 item 1 package-level fixture: the servlet-redirect-response recipe, packaged
and run on the pinned Spring compatibility stack, compared with the source.

fixtures/servlet-redirect-package holds two Spring Web controllers (quarkus-spring-web
+ quarkus-rest-jackson, the pinned platform BOM) under the source's context path
(quarkus.http.root-path=/petclinic/): RootRestController, the v26 source handler
translated by the recipe, and PortalResource, a renamed equivalent. The source
took javax.servlet.http.HttpServletResponse and called
response.sendRedirect(servletContextPath + "/swagger-ui/index.html");
source-oracle.json is what the frozen source answered (302, an absolute Location
under /petclinic, an empty body). Asked of the real platform, offline, from the
local Maven repository:

  * the NAMESPACE RENAME alone (jakarta.servlet.http.HttpServletResponse, v26
    t_4fd2dcec's rejected candidate) does not compile: the stack has no Servlet
    API, and the structural check refuses the handler that still takes it;
  * a handler that drops the parameter and returns void (the worker exercise's sample 1) is refused
    by the structural check: it compiles and answers nothing;
  * the verified redirect with the @Value("#{servletContext.contextPath}") field kept (v28 t_25819d9c) is
    refused by the structural check, and the platform refuses to package it (SpEL is not supported);
  * URI.create of the context-relative target packages but answers a RELATIVE
    Location where the source answered an absolute one (the form the catalog
    forbids);
  * the recipe's form packages, the structural check accepts it, and the
    packaged application answers GET /petclinic/ with the recorded source
    response -- 302, Location http://<host>:<port>/petclinic/swagger-ui/index.html
    (origin normalized), an empty body -- and the renamed controller answers
    302 with http://<host>:<port>/petclinic/docs/index.html.

When the local environment cannot package or start it (no mvn, java or javac;
the pinned artifacts not in the local Maven repository; no loopback port), the
case prints SKIP with the precise reason and exits 0.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
FIXTURE = HERE.parent / "fixtures" / "servlet-redirect-package"
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
from planner.dest_model import dest_model  # noqa: E402
from planner.worklist import (_assess_handler_parameters, _unit_path, handler_parameters, symbol_renames,  # noqa: E402
                              unit_target_symbols)

RETIRED = "javax.servlet.http.HttpServletResponse"
CONTROLLER = "src/main/java/org/springframework/samples/petclinic/rest/RootRestController.java"
FQN = "org.springframework.samples.petclinic.rest.RootRestController"
_OFFLINE = ("Cannot access", "offline mode", "Could not resolve", "could not be resolved",
            "Non-resolvable import POM", "has not been downloaded")

RENAMED_ONLY = """package org.springframework.samples.petclinic.rest;

import java.io.IOException;

import jakarta.servlet.http.HttpServletResponse;

import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/")
public class RootRestController {

    @RequestMapping(value = "/")
    public void redirectToSwagger(HttpServletResponse response) throws IOException {
        response.sendRedirect("/petclinic/swagger-ui/index.html");
    }
}
"""

# the v26 worker exercise's corrected-brief sample 1: the parameter removed and the redirect dropped
EMPTIED = """package org.springframework.samples.petclinic.rest;

import java.io.IOException;

import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/")
public class RootRestController {

    @RequestMapping(value = "/")
    public void redirectToSwagger() throws IOException {
    }
}
"""

# v28 t_25819d9c (commit dfeda3d): the verified redirect, with the SpEL field that read the Servlet context kept
KEPT_FIELD = """package org.springframework.samples.petclinic.rest;

import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.UriInfo;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/")
public class RootRestController {

    @Value("#{servletContext.contextPath}")
    private String servletContextPath;

    @RequestMapping(value = "/")
    public ResponseEntity<Void> redirectToSwagger(@Context UriInfo uriInfo) {
        return ResponseEntity.status(HttpStatus.FOUND)
            .location(uriInfo.getBaseUriBuilder().path("swagger-ui/index.html").build())
            .build();
    }
}
"""

RELATIVE = """package org.springframework.samples.petclinic.rest;

import java.net.URI;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/")
public class RootRestController {

    @RequestMapping(value = "/")
    public ResponseEntity<Void> redirectToSwagger() {
        return ResponseEntity.status(HttpStatus.FOUND).location(URI.create("/petclinic/swagger-ui/index.html")).build();
    }
}
"""


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _skip(msg: str) -> int:
    print("SKIP: servlet-redirect-package: %s" % msg)
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


def _structural(root: Path) -> dict[str, str]:
    """The planner's sealed row for the source handler's Servlet response parameter, assessed against the
    compiler model of the tree."""
    sites = [{"path": CONTROLLER, "type": FQN, "member": "redirectToSwagger", "parameter": "response"}]
    targets = unit_target_symbols([{"kind": "type", "fqn": RETIRED, "path": CONTROLLER}], symbol_renames(GOLDEN), {}, None,
                                  {RETIRED: sites}, handler_parameters(GOLDEN)["undocumented"])
    by_path: dict[str, list[dict]] = defaultdict(list)
    for t in dest_model(root).get("types") or []:
        by_path[_unit_path(t)].append(t)
    return {r["member"].split("#", 1)[1]: r["verdict"]
            for r in _assess_handler_parameters({"target_symbols": targets}, by_path, "unit/diagnostic-family/v1")}


def _get(port: int, path: str) -> tuple[int, dict, bytes]:
    """One GET that does not follow redirects (the oracle was captured with redirects_followed false)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        return int(resp.status), {k.lower(): v for k, v in resp.getheaders()}, resp.read()
    finally:
        conn.close()


def _normalize(url: str) -> str:
    """The origin is the one difference between two deployments: compare the path (and query) of an absolute
    URL; a relative URL is left as it is, so it never equals an absolute one."""
    parts = urlsplit(url)
    if not parts.scheme:
        return "RELATIVE " + url
    return parts.path + (("?" + parts.query) if parts.query else "")


def _serve(root: Path, check) -> int:
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
    try:
        deadline = time.time() + 60
        while True:
            try:
                _get(port, "/petclinic/")
                break
            except OSError:
                if proc.poll() is not None or time.time() > deadline:
                    return _fail("the packaged application did not start: %s" % (root / "run.log").read_text()[-600:])
                time.sleep(0.5)
        return check(port)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


def _package(root: Path) -> subprocess.CompletedProcess[str]:
    shutil.rmtree(root / "target", ignore_errors=True)
    return _mvn(root, "package", "-DskipTests")


def main() -> int:
    for tool in ("mvn", "java", "javac"):
        if not shutil.which(tool):
            return _skip("%s is not on PATH, so the platform cannot package and run the fixture here" % tool)
    oracle = json.loads((FIXTURE / "source-oracle.json").read_text(encoding="utf-8"))["oracle"]
    want = (oracle["status"], _normalize(oracle["location"]), oracle["body_sha256"])
    with tempfile.TemporaryDirectory(prefix="servlet-redirect-pkg-") as td:
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
        pristine = (root / CONTROLLER).read_text(encoding="utf-8")

        # --- the namespace rename alone ---
        (root / CONTROLLER).write_text(RENAMED_ONLY, encoding="utf-8")
        verdicts = _structural(root)
        if verdicts.get("redirectToSwagger(response)") != "violates":
            return _fail("the structural check refuses the handler that still takes the (renamed) Servlet response: %s" % verdicts)
        p = _package(root)
        out = p.stdout + p.stderr
        if p.returncode == 0:
            return _fail("the jakarta.servlet rename must NOT compile on the pinned stack")
        if "package jakarta.servlet.http does not exist" not in out:
            gap = _offline_gap(p)
            return _skip(gap) if gap else _fail("the rename fails for another reason: %s" % out[-600:])

        # --- the redirect dropped: compiles, and the structural check refuses it ---
        (root / CONTROLLER).write_text(EMPTIED, encoding="utf-8")
        verdicts = _structural(root)
        if verdicts.get("redirectToSwagger(response)") != "violates":
            return _fail("the structural check refuses a handler that returns void after dropping the response: %s" % verdicts)

        # --- the redirect translated but the SpEL servlet-context field kept (v28 t_25819d9c) ---
        (root / CONTROLLER).write_text(KEPT_FIELD, encoding="utf-8")
        verdicts = _structural(root)
        if verdicts.get("redirectToSwagger(response)") != "violates":
            return _fail("the structural check refuses a SpEL servlet-context field left on the handler's type: %s" % verdicts)
        p = _package(root)
        if p.returncode == 0 or "SpEL" not in (p.stdout + p.stderr):
            gap = _offline_gap(p)
            return _skip(gap) if gap else _fail("the kept SpEL field must fail packaging as SpEL: rc=%s %s"
                                                % (p.returncode, (p.stdout + p.stderr)[-500:]))

        # --- URI.create of the context-relative target (the form the catalog forbids) ---
        (root / CONTROLLER).write_text(RELATIVE, encoding="utf-8")
        p = _package(root)
        if p.returncode != 0:
            return _fail("the relative form packages (it is refused by behaviour, not by the compiler): %s" % (p.stdout + p.stderr)[-600:])

        def relative_differs(port: int) -> int:
            status, headers, body = _get(port, "/petclinic/")
            got = (status, _normalize(headers.get("location", "")), hashlib.sha256(body).hexdigest())
            if got == want:
                return _fail("a relative Location must not match the source's absolute one: %s" % (got,))
            if got[1] != "RELATIVE /petclinic/swagger-ui/index.html":
                return _fail("the relative form answers %s" % (got,))
            return 0
        if _serve(root, relative_differs):
            return 1

        # --- the recipe's form ---
        (root / CONTROLLER).write_text(pristine, encoding="utf-8")
        verdicts = _structural(root)
        if set(verdicts.values()) != {"ok"}:
            return _fail("the structural check accepts the translated handler: %s" % verdicts)
        p = _package(root)
        if p.returncode != 0:
            return _fail("the recipe's form packages: %s" % (p.stdout + p.stderr)[-900:])

        def matches_source(port: int) -> int:
            status, headers, body = _get(port, "/petclinic/")
            got = (status, _normalize(headers.get("location", "")), hashlib.sha256(body).hexdigest())
            if got != want:
                return _fail("GET /petclinic/ answers what the source answered: want %s got %s" % (want, got))
            if not headers.get("location", "").startswith("http://127.0.0.1:%d/" % port):
                return _fail("the Location is absolute on this deployment's origin: %s" % headers.get("location"))
            status, headers, body = _get(port, "/petclinic/portal/")
            if (status, _normalize(headers.get("location", "")), body) != (302, "/petclinic/docs/index.html", b""):
                return _fail("the renamed equivalent answers 302 to its own target under the context path once: %s %s"
                             % (status, headers.get("location")))
            return 0
        if _serve(root, matches_source):
            return 1
    print("OK: servlet-redirect-package (pinned platform %s, offline, quarkus-spring-web + quarkus-rest-jackson, root path "
          "/petclinic/: the jakarta.servlet rename does not compile and the structural check refuses it; a void handler "
          "that dropped the redirect is refused; a kept SpEL servlet-context field is refused and does not package; URI.create of the "
          "context-relative target answers a relative Location, unlike the source; the recipe's @Context UriInfo form packages, "
          "the structural check accepts it, GET /petclinic/ matches the recorded source response (302, "
          "/petclinic/swagger-ui/index.html absolute, empty body) and the renamed equivalent answers 302 "
          "/petclinic/docs/index.html)" % _pin()["version"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
