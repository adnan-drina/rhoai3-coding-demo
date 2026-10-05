#!/usr/bin/env python3
"""compat-mapping persistence_behaviour_translations.hibernate66-merge-detached-without-row
and repository_behaviour.crud_defaults["save/1"] (H-22), over HTTP on the
pinned platform and PostgreSQL 16.

On the source's provider (Hibernate 5) Spring Data's save of an entity whose
generated id has no row merged it into a NEW row with a newly generated id; on
the destination's (Hibernate 6.6+) the merge throws OptimisticLockException
(StaleObjectStateException). fixtures/repository-effects-runtime's label create
is changed to carry the request's id onto the entity (as the v31 creates did),
and LabelRepositoryImpl.save is ported two ways:

  literal  `id == null ? persist : merge` (the v31 shape): a create carrying an
           id without a row answers 500 with the optimistic-lock failure in the
           log, and nothing is stored at that id (negative control)
  port     the catalog's port: an id without a row is persisted as new (the id
           generated, never the requested one); a row that exists is merged

Both: a create without an id answers 201 and is read back; a create carrying
the id of an EXISTING row updates that row (merge), read back by a later request.
SKIP with the reason when a prerequisite (mvn, java/javac, podman, the local
PostgreSQL image, the pinned artifacts offline, a loopback port) is missing; a
SKIP is never a PASS.
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
CTRL = "src/main/java/org/acme/depot/rest/LabelRestController.java"
SAVE = "        em.persist(label);\n"
CARRY = "        label.name = dto.name;\n"
VARIANTS = {
    "literal": "        if (label.id == null) {\n            em.persist(label);\n        } else {\n            em.merge(label);\n        }\n",
    "port": "        if (label.id != null && em.find(Label.class, label.id) == null) {\n"
            "            label.id = null;   // no row: persist as new, the identifier generated\n        }\n"
            "        if (label.id == null) {\n            em.persist(label);\n        } else {\n            em.merge(label);\n        }\n",
}
GHOST = 987654
LOG_TOKENS = ("OptimisticLockException", "StaleObjectStateException")


def _j(body: str) -> dict:
    try:
        return json.loads(body or "null") or {}
    except ValueError:
        return {}


def exercise(base: str) -> dict:
    api = base + "/api/labels"
    out: dict = {}
    st, _h, b = rt.http("POST", api, {"name": "plain"})
    pid = _j(b).get("id")
    out["create-no-id"] = (st, rt.http("GET", "%s/%s" % (api, pid))[0] if pid else 0)
    st, _h, b = rt.http("POST", api, {"id": GHOST, "name": "ghost"})
    gid = _j(b).get("id")
    rs, _h, rb = rt.http("GET", "%s/%s" % (api, gid)) if gid else (0, {}, "")
    out["create-id-without-row"] = {"status": st, "id": gid, "read_back": (rs, _j(rb).get("name")),
                                    "at_requested_id": rt.http("GET", "%s/%s" % (api, GHOST))[0]}
    st, _h, _b = rt.http("POST", api, {"id": pid, "name": "renamed"}) if pid else (0, {}, "")
    rs, _h, rb = rt.http("GET", "%s/%s" % (api, pid)) if pid else (0, {}, "")
    out["create-id-with-row"] = (st, rs, _j(rb).get("name"))
    return out


def main() -> int:
    got: dict[str, dict] = {}
    try:
        rt.need_tools("mvn", "java", "javac", "podman")
        with tempfile.TemporaryDirectory(prefix="merge-rt-") as td, rt.postgres() as pg:
            for label, body in VARIANTS.items():
                root = Path(td) / label
                shutil.copytree(FIXTURE, root)
                for rel, old, new in ((IMPL, SAVE, body), (CTRL, CARRY, "        label.id = dto.id;\n" + CARRY)):
                    p = root / rel
                    text = p.read_text(encoding="utf-8")
                    if text.count(old) != 1:
                        print("FAIL: the fixture's %s changed shape" % rel, file=sys.stderr)
                        return 1
                    p.write_text(text.replace(old, new), encoding="utf-8")
                ok, out = rt.package(root)
                if not ok:
                    print("FAIL: %s packages: %s" % (label, out[-900:]), file=sys.stderr)
                    return 1
                props = {"quarkus.datasource.jdbc.url": pg["url"], "quarkus.datasource.username": pg["user"],
                         "quarkus.datasource.password": pg["password"]}
                with rt.boot(root, "/api/crates", props) as base:
                    got[label] = exercise(base)
                log = (root / "run.log").read_text(errors="replace")
                got[label]["log"] = [t for t in LOG_TOKENS if t in log]
    except rt.Skip as exc:
        print("SKIP: merge-without-row-runtime: %s" % exc)
        return 0
    for label, v in got.items():
        for k, x in v.items():
            print("%-8s %-22s %s" % (label, k, x))
    for label, v in got.items():
        if v["create-no-id"] != (201, 200) or v["create-id-with-row"] != (201, 200, "renamed"):
            print("FAIL: %s must create without an id and merge a row that exists" % label, file=sys.stderr)
            return 1
    lit, port = got["literal"]["create-id-without-row"], got["port"]["create-id-without-row"]
    if lit["status"] != 500 or lit["at_requested_id"] != 404 or not got["literal"]["log"]:
        print("FAIL: the literal merge of an id without a row must answer 500 with the optimistic-lock failure "
              "(%s) in the log and store nothing" % " / ".join(LOG_TOKENS), file=sys.stderr)
        return 1
    if (port["status"] != 201 or not port["id"] or port["id"] == GHOST or port["read_back"] != (200, "ghost")
            or port["at_requested_id"] != 404 or got["port"]["log"]):
        print("FAIL: the port must insert an id without a row as new (201, a generated id, read back)", file=sys.stderr)
        return 1
    print("OK: merge-without-row-runtime (pinned platform %s, PostgreSQL 16 in podman, packaged jar over HTTP: the literal "
          "`id == null ? persist : merge` answers 500 for a create carrying an id without a row (%s in the log) and stores "
          "nothing; the catalog's port inserts it with generated id %s, read back by a later request; both create "
          "without an id and merge a row that exists)" % (rt.pin()["version"], ", ".join(got["literal"]["log"]), port["id"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
