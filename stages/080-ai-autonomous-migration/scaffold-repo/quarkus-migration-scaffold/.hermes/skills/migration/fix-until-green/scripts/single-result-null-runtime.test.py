#!/usr/bin/env python3
"""compat-mapping repository_behaviour.query_result_semantics.single_entity,
over HTTP on the pinned platform and PostgreSQL 16.

Spring Data returns null when a single-entity query method finds no row; the
controller answers its own null path (404). fixtures/repository-effects-runtime's
LabelRepositoryImpl.findById is ported three ways:

  bare        em.createQuery(...).getSingleResult(): NoResultException -> 500
              for a missing id (the M-3 2026-09-30 v28 shape: owner-get-missing)
  translated  getResultStream().findFirst().orElse(null): 404 for a missing id
  (both)      200 with the row for an existing id

The existing-row read and the missing-row 404 are the source's behaviour; the
bare port must fail exactly the missing-row case. SKIP with the reason when a
prerequisite (mvn, java, podman, the local PostgreSQL image, the pinned
artifacts offline) is missing.
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
IMPL = "src/main/java/org/acme/depot/repository/LabelRepositoryImpl.java"
FIND = "        return em.find(Label.class, id);\n"
QUERY = 'em.createQuery("select l from Label l where l.id = :id", Label.class).setParameter("id", id)'
VARIANTS = {"bare": "        return %s.getSingleResult();\n" % QUERY,
            "translated": "        return %s.getResultStream().findFirst().orElse(null);\n" % QUERY}


def main() -> int:
    got: dict[str, dict] = {}
    try:
        rt.need_tools("mvn", "java", "javac", "podman")
        with tempfile.TemporaryDirectory(prefix="single-result-rt-") as td, rt.postgres() as pg:
            for label, body in VARIANTS.items():
                root = Path(td) / label
                shutil.copytree(FIXTURE, root)
                p = root / IMPL
                text = p.read_text(encoding="utf-8")
                if FIND not in text:
                    print("FAIL: the fixture's findById changed shape", file=sys.stderr)
                    return 1
                p.write_text(text.replace(FIND, body), encoding="utf-8")
                ok, out = rt.package(root)
                if not ok:
                    print("FAIL: %s packages: %s" % (label, out[-900:]), file=sys.stderr)
                    return 1
                props = {"quarkus.datasource.jdbc.url": pg["url"], "quarkus.datasource.username": pg["user"],
                         "quarkus.datasource.password": pg["password"]}
                with rt.boot(root, "/api/crates", props) as base:
                    st, _h, b = rt.http("POST", base + "/api/labels", {"name": "fragile"})
                    lid = json.loads(b or "{}").get("id")
                    hit = rt.http("GET", base + "/api/labels/%s" % lid)[0] if lid else 0
                    miss = rt.http("GET", base + "/api/labels/987654")[0]
                log = (root / "run.log").read_text(errors="replace")
                got[label] = {"created": st, "existing": hit, "missing": miss, "no_result_logged": "NoResultException" in log}
    except rt.Skip as exc:
        print("SKIP: single-result-null-runtime: %s" % exc)
        return 0
    for k, v in got.items():
        print("%-10s %s" % (k, v))
    b, t = got["bare"], got["translated"]
    if b["existing"] != 200 or b["missing"] != 500 or not b["no_result_logged"]:
        print("FAIL: the bare getSingleResult port must read an existing row and answer 500 (NoResultException) for a missing one",
              file=sys.stderr)
        return 1
    if t["existing"] != 200 or t["missing"] != 404:
        print("FAIL: the translated port must read an existing row and answer the source's 404 for a missing one", file=sys.stderr)
        return 1
    print("OK: single-result-null-runtime (pinned platform %s, PostgreSQL 16 in podman, packaged jar over HTTP: a bare "
          "getSingleResult answers 500 with NoResultException for a missing row; getResultStream().findFirst().orElse(null) "
          "answers the source's 404; both read an existing row 200)" % rt.pin()["version"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
