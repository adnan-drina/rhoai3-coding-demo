#!/usr/bin/env python3
"""compat-mapping persistence_behaviour_translations.hibernate6-flush-before-query
(H-21), over HTTP on the pinned platform and PostgreSQL 16.

The row binds a port to the committed effects the SOURCE recorded: a delete the
source completed must complete, and a delete the source REFUSED (the row still
referenced: the flushed removal's constraint violation) must stay refused with
the row kept -- never made to succeed by deleting the dependents first.
fixtures/repository-effects-runtime's label delete is ported two ways:

  literal     the source order: em.remove(label), THEN the bulk delete of its
              join rows. Hibernate 6 flushes the removal before the native
              statement, so
                unreferenced label  -> 204, the row gone
                referenced label    -> refused (non-2xx), FK violation in the log,
                                       the label and its join row kept
  reordered   dependents first (the reordering H-21 bounds), negative control:
                referenced label    -> 204, the row and its join row gone --
                                       a refused delete made to succeed

A delete whose dependents are LOADED first (the v31 lab finding): the
fixture's kind is referenced by pallets (Pallet.kind), each pallet owned by a
crate through the eager cascade-ALL collection, each pallet carrying a stamp
(a grandchild). Deleting a referenced kind:

  load-then-bulk-literal          SELECT the kind's pallets, em.remove(kind),
                                  then per pallet a bulk JPQL delete of its
                                  stamps and of the pallet
  load-then-bulk-dependents-first the same SELECT and bulk deletes, em.remove(kind)
                                  last
      both -> refused (non-2xx), TransientPropertyValueException in the log, the
      kind, the pallet and the stamp kept: the SELECT leaves the pallets (and
      their eager crates) managed, the bulk deletes bypass the persistence
      context, and at flush the crate's cascade re-persists the deleted pallet,
      which references the removed kind. Reordering does not help here.
  bulk-only (the fixture as shipped; also the kind delete in literal/reordered)
      bulk statements only, no entity loading: the stamps (IN a subquery of the
      kind's pallets), the pallets, the kind -> 204, the kind, its pallet and
      the stamp gone, the crate kept

Each effect is read back by a later, independent request. SKIP with the reason
when a prerequisite (mvn, java/javac, podman, the local PostgreSQL image, the
pinned artifacts offline, a loopback port) is missing; a SKIP is never a PASS.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_runtime_fixture as rt  # noqa: E402

_spec = importlib.util.spec_from_file_location("repository_effects_runtime", HERE / "repository-effects-runtime.test.py")
EFFECTS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(EFFECTS)  # type: ignore[union-attr]

FIXTURE = rt.FIXTURES / "repository-effects-runtime"
_LOAD = ("        java.util.List<org.acme.depot.model.Pallet> ps = em.createQuery(\"SELECT p FROM Pallet p WHERE p.kind.id = :id\",\n"
         "                org.acme.depot.model.Pallet.class).setParameter(\"id\", kind.id).getResultList();\n")
_REMOVE = "        em.remove(em.contains(kind) ? kind : em.merge(kind));\n"
_BULK = ("        for (org.acme.depot.model.Pallet p : ps) {\n"
         "            em.createQuery(\"DELETE FROM Stamp s WHERE s.pallet.id = :id\").setParameter(\"id\", p.id).executeUpdate();\n"
         "            em.createQuery(\"DELETE FROM Pallet p WHERE p.id = :id\").setParameter(\"id\", p.id).executeUpdate();\n"
         "        }\n")
LOAD_LITERAL = ("KindRepository.java", "// KIND-DELETE", "// END-KIND-DELETE", _LOAD + _REMOVE + _BULK)
LOAD_DEPS_FIRST = ("KindRepository.java", "// KIND-DELETE", "// END-KIND-DELETE", _LOAD + _BULK + _REMOVE)
VARIANTS = {"literal": [EFFECTS.REMOVE_FIRST], "reordered": [], "load-then-bulk-literal": [LOAD_LITERAL],
            "load-then-bulk-dependents-first": [LOAD_DEPS_FIRST], "bulk-only": []}
LOADED = ("load-then-bulk-literal", "load-then-bulk-dependents-first")
BULK_ONLY = ("literal", "reordered", "bulk-only")
FK_TOKEN = "violates foreign key constraint"
TPV_TOKEN = "TransientPropertyValueException"


def _j(body: str) -> dict:
    try:
        return json.loads(body or "null") or {}
    except ValueError:
        return {}


def _labels(api: str) -> dict:
    _s, _h, b = rt.http("POST", api + "/crates", {"name": "c", "pallets": [{"name": "p"}]})
    cid = _j(b).get("id")
    pallets = _j(rt.http("GET", api + "/crates/%s" % cid)[2]).get("pallets") or [] if cid else []
    pid = pallets[0].get("id") if pallets else None
    ref = _j(rt.http("POST", api + "/labels", {"name": "referenced"})[2]).get("id")
    unref = _j(rt.http("POST", api + "/labels", {"name": "unreferenced"})[2]).get("id")
    if not (pid and ref and unref) or rt.http("POST", api + "/pallets/%s/labels/%s" % (pid, ref))[0] != 204:
        raise RuntimeError("the fixture could not set up a referenced label (pallet %s, labels %s/%s)" % (pid, ref, unref))
    out = {}
    ds = rt.http("DELETE", api + "/labels/%s" % unref)[0]
    out["unreferenced"] = {"delete": ds, "label": rt.http("GET", api + "/labels/%s" % unref)[0]}
    ds = rt.http("DELETE", api + "/labels/%s" % ref)[0]
    gs, _h, gb = rt.http("GET", api + "/labels/%s" % ref)
    ps, _h, pb = rt.http("GET", api + "/pallets/%s" % pid)
    out["referenced"] = {"delete": ds, "label": gs, "pallet_labels": [x.get("id") for x in _j(pb).get("labels") or []],
                         "ref": ref}
    return out


def _kind(api: str) -> dict:
    kid = _j(rt.http("POST", api + "/kinds", {"name": "k"})[2]).get("id")
    _s, _h, b = rt.http("POST", api + "/crates", {"name": "owner", "pallets": [{"name": "kp"}]})
    cid = _j(b).get("id")
    pallets = _j(rt.http("GET", api + "/crates/%s" % cid)[2]).get("pallets") or [] if cid else []
    pid = pallets[0].get("id") if pallets else None
    if not (kid and pid) or rt.http("POST", api + "/pallets/%s/kind/%s" % (pid, kid))[0] != 204:
        raise RuntimeError("the fixture could not set up a referenced kind (kind %s, pallet %s)" % (kid, pid))
    sid = _j(rt.http("POST", api + "/pallets/%s/stamps" % pid, {"name": "s"})[2]).get("id")
    if not sid or (_j(rt.http("GET", api + "/pallets/%s" % pid)[2]).get("kind") or {}).get("id") != kid:
        raise RuntimeError("the fixture could not set up the kind's pallet and stamp (pallet %s, stamp %s)" % (pid, sid))
    ds = rt.http("DELETE", api + "/kinds/%s" % kid)[0]
    return {"delete": ds, "kind": rt.http("GET", api + "/kinds/%s" % kid)[0],
            "pallet": rt.http("GET", api + "/pallets/%s" % pid)[0], "stamp": rt.http("GET", api + "/stamps/%s" % sid)[0],
            "crate": rt.http("GET", api + "/crates/%s" % cid)[0]}


def exercise(base: str) -> dict:
    api = base + "/api"
    out = _labels(api)
    out["kind"] = _kind(api)
    return out


def main() -> int:
    got: dict[str, dict] = {}
    try:
        rt.need_tools("mvn", "java", "javac", "podman")
        with tempfile.TemporaryDirectory(prefix="ref-delete-rt-") as td, rt.postgres() as pg:
            for label, edits in VARIANTS.items():
                root = Path(td) / label
                shutil.copytree(FIXTURE, root)
                for fname, start, end, repl in edits:
                    rt.edit(root, EFFECTS.PKG + fname, start, end, repl)
                ok, out = rt.package(root)
                if not ok:
                    print("FAIL: %s packages: %s" % (label, out[-900:]), file=sys.stderr)
                    return 1
                props = {"quarkus.datasource.jdbc.url": pg["url"], "quarkus.datasource.username": pg["user"],
                         "quarkus.datasource.password": pg["password"]}
                with rt.boot(root, "/api/crates", props) as base:
                    got[label] = exercise(base)
                log = (root / "run.log").read_text(errors="replace")
                got[label]["fk_logged"] = FK_TOKEN in log
                got[label]["tpv_logged"] = TPV_TOKEN in log
    except rt.Skip as exc:
        print("SKIP: referenced-delete-runtime: %s" % exc)
        return 0
    for label, v in got.items():
        for k, x in v.items():
            print("%-31s %-13s %s" % (label, k, x))
    lit, reo = got["literal"], got["reordered"]
    if lit["unreferenced"] != {"delete": 204, "label": 404}:
        print("FAIL: the literal order must complete an unreferenced delete (204, the row gone)", file=sys.stderr)
        return 1
    r = lit["referenced"]
    if 200 <= r["delete"] < 300 or r["label"] != 200 or r["pallet_labels"] != [r["ref"]] or not lit["fk_logged"]:
        print("FAIL: the literal order must refuse a referenced delete (non-2xx, %r in the log) and keep the row and "
              "its join row" % FK_TOKEN, file=sys.stderr)
        return 1
    r2 = reo["referenced"]
    if (r2["delete"], r2["label"], r2["pallet_labels"]) != (204, 404, []):
        print("FAIL: the reordered control must make the referenced delete succeed (the effect H-21 forbids where the "
              "source refused)", file=sys.stderr)
        return 1
    for label in LOADED:
        k = got[label]["kind"]
        if 200 <= k["delete"] < 300 or (k["kind"], k["pallet"], k["stamp"]) != (200, 200, 200) or not got[label]["tpv_logged"]:
            print("FAIL: %s must refuse the referenced kind delete (non-2xx, %s in the log) and keep the kind, its "
                  "pallet and the stamp: %s" % (label, TPV_TOKEN, k), file=sys.stderr)
            return 1
    for label in BULK_ONLY:
        k = got[label]["kind"]
        if (k["delete"], k["kind"], k["pallet"], k["stamp"], k["crate"]) != (204, 404, 404, 404, 200):
            print("FAIL: %s's bulk-only kind delete must answer 204 with the kind, its pallet and the stamp gone and the "
                  "crate kept: %s" % (label, k), file=sys.stderr)
            return 1
    print("OK: referenced-delete-runtime (pinned platform %s, PostgreSQL 16 in podman, packaged jar over HTTP, effects read "
          "back by later requests: the literal remove-then-bulk-delete order completes an unreferenced delete (204, row "
          "gone) and refuses a referenced one (%s, FK violation in the log, label and join row kept); the dependents-first "
          "reordering makes the referenced delete succeed (204, row and join row gone) -- the change H-21 forbids where "
          "the source refused; a referenced kind delete that SELECT-loads its pallets before the bulk deletes is refused "
          "in both orders (%s / %s, %s: the eager owner's cascade re-persists the bulk-deleted pallet) with the kind, "
          "pallet and stamp kept, while the bulk-only form answers 204 with them gone)"
          % (rt.pin()["version"], r["delete"], got[LOADED[0]]["kind"]["delete"], got[LOADED[1]]["kind"]["delete"],
             TPV_TOKEN))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
