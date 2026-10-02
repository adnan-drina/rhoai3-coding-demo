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
VARIANTS = {"literal": [EFFECTS.REMOVE_FIRST], "reordered": []}
FK_TOKEN = "violates foreign key constraint"


def _j(body: str) -> dict:
    try:
        return json.loads(body or "null") or {}
    except ValueError:
        return {}


def exercise(base: str) -> dict:
    api = base + "/api"
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
                got[label]["fk_logged"] = FK_TOKEN in (root / "run.log").read_text(errors="replace")
    except rt.Skip as exc:
        print("SKIP: referenced-delete-runtime: %s" % exc)
        return 0
    for label, v in got.items():
        for k, x in v.items():
            print("%-9s %-13s %s" % (label, k, x))
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
    print("OK: referenced-delete-runtime (pinned platform %s, PostgreSQL 16 in podman, packaged jar over HTTP, effects read "
          "back by later requests: the literal remove-then-bulk-delete order completes an unreferenced delete (204, row "
          "gone) and refuses a referenced one (%s, FK violation in the log, label and join row kept); the dependents-first "
          "reordering makes the referenced delete succeed (204, row and join row gone) -- the change H-21 forbids where "
          "the source refused)" % (rt.pin()["version"], r["delete"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
