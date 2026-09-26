#!/usr/bin/env python3
"""V17-5 runtime proof: a create whose Location is built from the REQUEST
body's (null) id, over HTTP, on a booted Quarkus app and a real PostgreSQL.

The source built it with Spring's `ucBuilder.path("/api/x/{id}").buildAndExpand(dto.getId())`.
Spring expands a null URI variable to an empty string (UriComponents
expansion: a null value becomes ""), so the source answered 201 with a
Location ending in an empty segment. When spring-web and spring-core are in
the local Maven repository, that is not taken on trust: the oracle compiles
and runs a three-line program against them and records what Spring returns.

fixtures/repository-effects-runtime's LabelRestController saves the label in
a transactional service call (committed when it returns) and THEN builds the
Location, exactly the v17 order:

  bare       `uriInfo.getBaseUriBuilder().path("/api/labels/{id}").build(dto.id)`:
             JAX-RS UriBuilder.build refuses a null template value
             (IllegalArgumentException), the request answers 500 -- and the
             row IS committed (read back by an independent GET): the v17 shape
  tolerant   `build(dto.id == null ? "" : dto.id)`: 201, Location ending in
             "/api/labels/" -- the source's null semantics -- and the row read
             back

A missing prerequisite prints SKIP with the reason and exits 0.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _runtime_fixture as rt  # noqa: E402

FIXTURE = rt.FIXTURES / "repository-effects-runtime"
CONTROLLER = "src/main/java/org/acme/depot/rest/LabelRestController.java"
BARE = "        URI location = uriInfo.getBaseUriBuilder().path(\"/api/labels/{id}\").build(dto.id);\n"
M2 = Path.home() / ".m2" / "repository" / "org" / "springframework"
SPRING = "5.3.31"


def spring_oracle(td: Path) -> str:
    """What Spring's buildAndExpand(null) produces, measured; '' when the jars
    are not in the local repository (then the documented semantics stand)."""
    jars = [M2 / "spring-web" / SPRING / ("spring-web-%s.jar" % SPRING), M2 / "spring-core" / SPRING / ("spring-core-%s.jar" % SPRING)]
    if not all(j.is_file() for j in jars):
        return ""
    src = td / "Oracle.java"
    src.write_text("public class Oracle { public static void main(String[] a) {\n"
                   "  System.out.println(org.springframework.web.util.UriComponentsBuilder.fromHttpUrl(\"http://h\")\n"
                   "    .path(\"/api/labels/{id}\").buildAndExpand((Object) null).toUri());\n} }\n", encoding="utf-8")
    cp = ":".join(str(j) for j in jars)
    c = subprocess.run(["javac", "-cp", cp, "-d", str(td), str(src)], capture_output=True, text=True)
    if c.returncode != 0:
        return ""
    r = subprocess.run(["java", "-cp", cp + ":" + str(td), "Oracle"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def exercise(base: str) -> dict:
    st, h, body = rt.http("POST", base + "/api/labels", {"name": "fragile"})
    gs, _h, gb = rt.http("GET", base + "/api/labels/1")
    try:
        row = json.loads(gb or "null") or {}
    except ValueError:
        row = {}
    return {"status": st, "location": h.get("location") or "", "read_back": gs, "name": row.get("name")}


def main() -> int:
    try:
        rt.need_tools("mvn", "java", "javac", "podman")
        got: dict[str, dict] = {}
        with tempfile.TemporaryDirectory(prefix="location-null-rt-") as td, rt.postgres() as pg:
            oracle = spring_oracle(Path(td))
            for label in ("bare", "tolerant"):
                root = Path(td) / label
                shutil.copytree(FIXTURE, root)
                if label == "bare":
                    rt.edit(root, CONTROLLER, "// LOCATION", "// END-LOCATION", BARE)
                ok, out = rt.package(root)
                if not ok:
                    print("FAIL: %s packages: %s" % (label, out[-900:]), file=sys.stderr)
                    return 1
                props = {"quarkus.datasource.jdbc.url": pg["url"], "quarkus.datasource.username": pg["user"],
                         "quarkus.datasource.password": pg["password"]}
                with rt.boot(root, "/api/crates", props) as base:
                    got[label] = exercise(base)
                    got[label]["base"] = base
                log = (root / "run.log").read_text(errors="replace")
                got[label]["iae_logged"] = "IllegalArgumentException" in log
    except rt.Skip as exc:
        print("SKIP: location-null-runtime: %s" % exc)
        return 0
    for k, v in got.items():
        print("%-9s %s" % (k, {x: v[x] for x in ("status", "location", "read_back", "name", "iae_logged")}))
    print("spring    buildAndExpand(null) -> %s" % (oracle or "NOT RUN (spring-web/core %s not in ~/.m2)" % SPRING))
    b, t = got["bare"], got["tolerant"]
    if b["status"] != 500 or b["read_back"] != 200 or b["name"] != "fragile" or not b["iae_logged"]:
        print("FAIL: the bare build(null) must answer 500 with IllegalArgumentException AFTER the row was committed", file=sys.stderr)
        return 1
    if t["status"] != 201 or t["location"] != t["base"] + "/api/labels/" or t["read_back"] != 200:
        print("FAIL: the null-tolerant build must answer 201 with Location %s/api/labels/" % t["base"], file=sys.stderr)
        return 1
    if oracle and oracle != "http://h/api/labels/":
        print("FAIL: Spring's own expansion of null is %r, not the empty segment the tolerant form reproduces" % oracle, file=sys.stderr)
        return 1
    print("OK: location-null-runtime (pinned platform %s, PostgreSQL 16 in podman, packaged jar over HTTP: the bare "
          "UriBuilder.build(dto.id) answers 500 (IllegalArgumentException) after the row was committed; the null-tolerant "
          "build answers 201 with Location .../api/labels/; Spring %s buildAndExpand(null) measured offline -> %s)"
          % (rt.pin()["version"], SPRING, oracle or "NOT RUN"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
