#!/usr/bin/env python3
"""compat-mapping objective_families.transaction-annotations, at runtime on the
pinned platform and PostgreSQL 16.

transaction-mapping.test.py checks the attribute table against the two APIs;
this checks what the translated boundaries DO. Each case is written in the
SOURCE's terms (Spring @Transactional attributes) and translated to
@jakarta.transaction.Transactional through the catalog's own `propagation` and
`attributes` tables, then compiled into fixtures/repository-effects-runtime
(a write is a flushed INSERT of a Label row). Every case runs in its own HTTP
request; its committed state is read back by a LATER request in a fresh
transaction. Expected = the source semantics the catalog records (Spring:
rollback on RuntimeException and Error, not on a checked exception, unless the
rollback rules say otherwise):

  runtime-default     @Transactional, throws IllegalStateException     -> rolled back
  checked-default     @Transactional, throws a checked exception       -> committed
  rollback-for        rollbackFor = <checked>, throws it               -> rolled back
  no-rollback-for     noRollbackFor = IllegalStateException, throws it -> committed
  requires-new        REQUIRED outer writes, calls a REQUIRES_NEW inner that
                      writes, then throws                              -> outer rolled back, inner committed
  required            the same with a REQUIRED inner                   -> both rolled back
  control             rollback-for with the attribute dropped (not a translation the catalog allows)
                                                                       -> committed: differs from the source

and a packaging variant with the boundary on a PRIVATE method (the catalog's
unsupported shape) must fail the build (ArC refuses an intercepted private
method). SKIP with the reason when a prerequisite (mvn, java/javac, podman, the
local PostgreSQL image, the pinned artifacts offline, a loopback port) is
missing; a SKIP is never a PASS.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_runtime_fixture as rt  # noqa: E402

FIXTURE = rt.FIXTURES / "repository-effects-runtime"
TX = "src/main/java/org/acme/depot/tx/"
CHECKED = "TxProbe.Checked.class"
RUNTIME = "IllegalStateException.class"
# case -> (Spring attributes of the boundary, what the method throws, expected committed rows)
CASES = {
    "runtime-default": ({}, "runtime", 0),
    "checked-default": ({}, "checked", 1),
    "rollback-for": ({"rollbackFor": CHECKED}, "checked", 0),
    "no-rollback-for": ({"noRollbackFor": RUNTIME}, "runtime", 1),
}
INNER = {"requires-new": "REQUIRES_NEW", "required": "REQUIRED"}
EXPECT_INNER = {"requires-new": (0, 1), "required": (0, 0)}  # (outer, inner)
PRIVATE_REFUSAL = "@Transactional will have no effect on method"


def jakarta(family: dict, spring: dict) -> str:
    """The @jakarta.transaction.Transactional the catalog's tables translate `spring` to."""
    parts = []
    for attr, value in sorted(spring.items()):
        if attr == "propagation":
            parts.append("value = Transactional.TxType.%s" % family["propagation"][value])
        else:
            parts.append("%s = %s" % (family["attributes"][attr].split()[0], value))
    return "@Transactional" + ("(%s)" % ", ".join(parts) if parts else "")


def sources(family: dict, private: bool = False) -> dict[str, str]:
    throw = {"runtime": 'throw new IllegalStateException("boom");', "checked": 'throw new Checked();'}
    probe = []
    for case, (spring, kind, _e) in CASES.items():
        probe.append("    %s\n    public void %s(String n) throws Checked { write(n); %s }\n"
                     % (jakarta(family, spring), _java(case), throw[kind]))
    probe.append("    @Transactional\n    public void control(String n) throws Checked { write(n); %s }\n" % throw["checked"])
    for case in INNER:
        probe.append("    %s\n    public void %s(String n) { write(n + \"-outer\"); inner.%s(n + \"-inner\"); %s }\n"
                     % (jakarta(family, {}), _java(case), _java(case), throw["runtime"]))
    inner = ["    %s\n    public void %s(String n) { probe.write(n); }\n"
             % (jakarta(family, {"propagation": p}), _java(case)) for case, p in INNER.items()]
    if private:
        inner.append("    @Transactional\n    private void hidden(String n) { probe.write(n); }\n"
                     "    public void callHidden(String n) { hidden(n); }\n")
    head = ("package org.acme.depot.tx;\n\nimport jakarta.enterprise.context.ApplicationScoped;\nimport jakarta.inject.Inject;\n"
            "import jakarta.persistence.EntityManager;\nimport jakarta.transaction.Transactional;\nimport org.acme.depot.model.Label;\n\n")
    calls = "".join("            case \"%s\": probe.%s(n); break;\n" % (c, _java(c)) for c in list(CASES) + ["control"] + list(INNER))
    return {
        "TxProbe.java": head + "@ApplicationScoped\npublic class TxProbe {\n    public static class Checked extends Exception {}\n\n"
        "    @Inject\n    EntityManager em;\n\n    @Inject\n    TxInner inner;\n\n"
        "    public void write(String n) {\n        Label l = new Label();\n        l.name = n;\n        em.persist(l);\n        em.flush();\n    }\n\n"
        + "\n".join(probe) + "}\n",
        "TxInner.java": head + "@ApplicationScoped\npublic class TxInner {\n    @Inject\n    TxProbe probe;\n\n" + "\n".join(inner) + "}\n",
        "TxResource.java": head.replace("import jakarta.enterprise.context.ApplicationScoped;\n", "")
        + "import jakarta.ws.rs.GET;\nimport jakarta.ws.rs.POST;\nimport jakarta.ws.rs.Path;\nimport jakarta.ws.rs.PathParam;\n"
        "import jakarta.ws.rs.Produces;\nimport jakarta.ws.rs.core.Response;\n\n@Path(\"/api/tx\")\npublic class TxResource {\n"
        "    @Inject\n    TxProbe probe;\n\n    @Inject\n    EntityManager em;\n\n"
        "    @POST\n    @Path(\"/{case}/{n}\")\n    @Produces(\"text/plain\")\n"
        "    public Response run(@PathParam(\"case\") String c, @PathParam(\"n\") String n) {\n        try {\n"
        "            switch (c) {\n" + calls + "            default: return Response.status(404).build();\n            }\n"
        "        } catch (Exception e) {\n            return Response.status(500).entity(e.getClass().getName()).build();\n        }\n"
        "        return Response.noContent().build();\n    }\n\n"
        "    // a fresh transaction in a later request: the committed state only\n"
        "    @GET\n    @Path(\"/count/{n}\")\n    @Produces(\"text/plain\")\n    @Transactional\n"
        "    public long count(@PathParam(\"n\") String n) {\n"
        "        return em.createQuery(\"select count(l) from Label l where l.name = :n\", Long.class).setParameter(\"n\", n).getSingleResult();\n"
        "    }\n}\n",
    }


def _java(case: str) -> str:
    head, *rest = case.split("-")
    return head + "".join(w.capitalize() for w in rest)


def write_sources(root: Path, family: dict, private: bool = False) -> None:
    (root / TX).mkdir(parents=True, exist_ok=True)
    for name, text in sources(family, private).items():
        (root / TX / name).write_text(text, encoding="utf-8")


def main() -> int:
    family = json.loads((rt.GOLDEN / ".hermes" / "planning" / "catalogs" / "compat-mapping.json").read_text()
                        )["objective_families"]["families"]["transaction-annotations"]
    got: dict[str, tuple] = {}
    try:
        rt.need_tools("mvn", "java", "javac", "podman")
        with tempfile.TemporaryDirectory(prefix="tx-rt-") as td:
            priv = Path(td) / "private"
            shutil.copytree(FIXTURE, priv)
            write_sources(priv, family, private=True)
            ok, priv_out = rt.package(priv)
            if ok or PRIVATE_REFUSAL not in priv_out:
                print("FAIL: a @Transactional private method must fail the build with ArC's refusal (%r): %s"
                      % (PRIVATE_REFUSAL, priv_out[-600:]), file=sys.stderr)
                return 1
            root = Path(td) / "app"
            shutil.copytree(FIXTURE, root)
            write_sources(root, family)
            ok, out = rt.package(root)
            if not ok:
                print("FAIL: the translated boundaries package: %s" % out[-900:], file=sys.stderr)
                return 1
            with rt.postgres() as pg:
                props = {"quarkus.datasource.jdbc.url": pg["url"], "quarkus.datasource.username": pg["user"],
                         "quarkus.datasource.password": pg["password"]}
                with rt.boot(root, "/api/crates", props) as base:
                    def count(n: str) -> int:
                        st, _h, body = rt.http("GET", base + "/api/tx/count/" + n)
                        return int(body) if st == 200 else -1
                    for case in list(CASES) + ["control"]:
                        st, _h, body = rt.http("POST", base + "/api/tx/%s/tx-%s" % (case, case))
                        got[case] = (st, body, count("tx-" + case))
                    for case in INNER:
                        st, _h, body = rt.http("POST", base + "/api/tx/%s/tx-%s" % (case, case))
                        got[case] = (st, body, (count("tx-%s-outer" % case), count("tx-%s-inner" % case)))
    except rt.Skip as exc:
        print("SKIP: transaction-runtime: %s" % exc)
        return 0
    for case, v in got.items():
        print("%-16s status %s %-40s committed %s" % (case, v[0], v[1][:40], v[2]))
    private_reason = next(ln.strip() for ln in priv_out.splitlines() if PRIVATE_REFUSAL in ln)
    print("%-16s package refused: %s" % ("private", private_reason[private_reason.index(PRIVATE_REFUSAL):][:160]))
    for case, (_s, _k, expected) in CASES.items():
        if got[case][0] != 500 or got[case][2] != expected:
            print("FAIL: %s must answer the thrown exception and leave %s committed row(s), got %s"
                  % (case, expected, got[case]), file=sys.stderr)
            return 1
    for case, expected in EXPECT_INNER.items():
        if got[case][2] != expected:
            print("FAIL: %s must leave (outer, inner) = %s committed, got %s" % (case, expected, got[case][2]), file=sys.stderr)
            return 1
    if got["control"][2] == CASES["rollback-for"][2]:
        print("FAIL: the control (rollbackFor dropped) must differ from the source's rollback", file=sys.stderr)
        return 1
    print("OK: transaction-runtime (pinned platform %s, PostgreSQL 16 in podman, packaged jar over HTTP, committed state read "
          "back by a later request: the catalog's translation rolls back a RuntimeException and commits a checked one; "
          "rollbackFor->rollbackOn rolls back the checked exception, noRollbackFor->dontRollbackOn commits the runtime one; "
          "a REQUIRES_NEW inner write survives its REQUIRED caller's rollback and a REQUIRED inner write does not; dropping "
          "rollbackFor commits (control); a @Transactional private method fails the build)" % rt.pin()["version"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
