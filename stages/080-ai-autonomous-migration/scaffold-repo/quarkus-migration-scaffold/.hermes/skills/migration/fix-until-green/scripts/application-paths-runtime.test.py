#!/usr/bin/env python3
"""compat-mapping application_paths, over HTTP on the pinned platform.

The source serves its controllers under server.servlet.context-path and
spring.mvc.servlet.path (Spring: <context-path><servlet-path><mapping>, and a
Location built from the request is absolute under both). The catalog owes each
configured source key's value on its destination key. fixtures/handler-location-package
(a Spring Web controller on quarkus-spring-web; POST answers 201 with a Location
from UriInfo's base, GET /{id}/archive answers 200) is packaged with the
destination properties DERIVED from the catalog row for a source that configures

    server.servlet.context-path=/ledger     spring.mvc.servlet.path=/svc

Variants:
  mapped     every key translated: the source's paths answer (GET 200, POST
             201 with Location <base>/ledger/svc/api/entries/7); the same
             routes outside the source's prefix answer 404
  root-only  negative control, spring.mvc.servlet.path not translated: the
             source's paths answer 404
  none       negative control, no key translated: the source's paths answer 404

SKIP with the reason when a prerequisite (mvn, java, the pinned artifacts
offline, a loopback port) is missing; a SKIP is never a PASS.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_runtime_fixture as rt  # noqa: E402

FIXTURE = rt.FIXTURES / "handler-location-package"
PROPS = "src/main/resources/application.properties"
SOURCE_CONFIG = {"server.servlet.context-path": "/ledger", "spring.mvc.servlet.path": "/svc"}
PREFIX = "/ledger/svc"
VARIANTS = {"mapped": tuple(SOURCE_CONFIG), "root-only": ("server.servlet.context-path",), "none": ()}


def dest_properties(catalog: dict, translated: tuple) -> dict[str, str]:
    """The catalog's destination key for every translated source key (KeyError: the catalog lost a row)."""
    return {catalog[k]["dest"]: SOURCE_CONFIG[k] for k in translated}


def exercise(base: str) -> dict:
    st, h, b = rt.http("POST", base + PREFIX + "/api/entries", {"name": "n"})
    return {
        "get": rt.http("GET", base + PREFIX + "/api/entries/3/archive")[0],
        "post": st,
        "location": h.get("location"),
        "get_outside": [rt.http("GET", base + p + "/api/entries/3/archive")[0] for p in ("", "/ledger", "/svc")],
    }


def main() -> int:
    catalog = json.loads((rt.GOLDEN / ".hermes" / "planning" / "catalogs" / "compat-mapping.json").read_text())["application_paths"]
    got: dict[str, dict] = {}
    try:
        rt.need_tools("mvn", "java")
        with tempfile.TemporaryDirectory(prefix="app-paths-rt-") as td:
            for label, translated in VARIANTS.items():
                root = Path(td) / label
                shutil.copytree(FIXTURE, root)
                props = dest_properties(catalog, translated)
                (root / PROPS).write_text("".join("%s=%s\n" % kv for kv in sorted(props.items())), encoding="utf-8")
                ok, out = rt.package(root)
                if not ok:
                    print("FAIL: %s packages: %s" % (label, out[-900:]), file=sys.stderr)
                    return 1
                with rt.boot(root, "/") as base:
                    got[label] = exercise(base)
                    got[label]["base"] = base
                    got[label]["props"] = props
    except rt.Skip as exc:
        print("SKIP: application-paths-runtime: %s" % exc)
        return 0
    for label, v in got.items():
        print("%-9s %s" % (label, {k: x for k, x in v.items() if k != "base"}))
    m = got["mapped"]
    if (m["get"], m["post"], m["location"]) != (200, 201, m["base"] + PREFIX + "/api/entries/7"):
        print("FAIL: with every key translated the source's paths must answer GET 200 and POST 201 with the Location "
              "under %s" % PREFIX, file=sys.stderr)
        return 1
    if m["get_outside"] != [404, 404, 404]:
        print("FAIL: the routes outside the source's prefix must answer 404, got %s" % m["get_outside"], file=sys.stderr)
        return 1
    for label in ("root-only", "none"):
        if got[label]["get"] != 404 or got[label]["post"] != 404:
            print("FAIL: the %s control must not serve the source's paths" % label, file=sys.stderr)
            return 1
    print("OK: application-paths-runtime (pinned platform %s, packaged jar over HTTP: the catalog's %s serve the source's "
          "%s paths, GET 200 and POST 201 with Location %s/api/entries/7; the routes outside it answer 404; without "
          "the servlet-path key, or without both, the source's paths answer 404)"
          % (rt.pin()["version"], " + ".join(sorted(m["props"])), PREFIX, PREFIX))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
