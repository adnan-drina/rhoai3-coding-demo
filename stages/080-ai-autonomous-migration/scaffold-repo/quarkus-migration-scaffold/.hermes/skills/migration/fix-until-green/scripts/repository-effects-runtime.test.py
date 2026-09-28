#!/usr/bin/env python3
"""V17-3 runtime proof: repository WRITE effects through a booted Quarkus app
on a real PostgreSQL, across request and transaction boundaries.

fixtures/repository-effects-runtime is the v17 shape on a specimen-agnostic
model (Crate 1..n Pallet n..m Label): Spring Data repositories whose fragment
parents are implemented by `@ApplicationScoped @Typed(XImpl.class)` delegates,
injected by the parent type (so every call goes through the GENERATED
repository to the delegate), a transactional service, Spring Web controllers.
The controller reads in one transaction and saves the detached change in
another, as the source's service does; every effect is read back by a later,
independent HTTP request.

Checks (each its own request):
  reads         GET a row the application never wrote (import.sql) and the list
  create        POST a crate with two pallets -> 201; GET it back with both
  update        PUT a new name -> 204; GET shows it
  link          POST a label, link it to a pallet; GET the pallet shows it
  label-delete  DELETE the label -> 204; GET the label -> 404; the pallet
                survives and no longer lists it (the join row is gone)
  crate-delete  DELETE the crate -> 204; GET -> 404; its pallets -> 404
                (cascade / orphan removal)

Variants (text edits of the delegate):
  faithful       every check passes
  noop-writes    "reads pass, writes do nothing" (save/delete bodies empty):
                 reads pass, every write check fails
  remove-first   the literal port of a source override that removes the entity
                 and THEN bulk-deletes its dependents: Hibernate 6 flushes the
                 pending removal before the native statement, so the delete
                 fails (FK violation) and the label and its join row survive;
                 the dependents-first port (faithful) passes

A missing prerequisite (mvn/java/podman, a local artifact, the local
PostgreSQL image, a loopback port) prints SKIP with the reason and exits 0.
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
PKG = "src/main/java/org/acme/depot/repository/"
NOOP_SAVE = ("CrateRepositoryImpl.java", "// WRITE-SAVE", "// END-WRITE-SAVE", "        // (a no-op: the stub shape)\n")
NOOP_DELETE = ("CrateRepositoryImpl.java", "// WRITE-DELETE", "// END-WRITE-DELETE", "        // (a no-op: the stub shape)\n")
REMOVE_FIRST = ("LabelRepositoryImpl.java", "// DELETE-ORDER", "// END-DELETE-ORDER",
                "        // the literal port: remove the entity first, then its dependents\n"
                "        em.remove(em.contains(label) ? label : em.merge(label));\n"
                "        em.createNativeQuery(\"delete from pallet_labels where label_id = ?1\").setParameter(1, label.id).executeUpdate();\n")
VARIANTS = {"faithful": [], "noop-writes": [NOOP_SAVE, NOOP_DELETE], "remove-first": [REMOVE_FIRST]}
WRITES = ("create", "update", "crate-delete")


def _j(body: str):
    try:
        return json.loads(body or "null")
    except ValueError:
        return None


def exercise(base: str) -> dict[str, tuple[bool, str]]:
    api = base + "/api"
    out: dict[str, tuple[bool, str]] = {}
    st, _h, b = rt.http("GET", api + "/crates/1000")
    st2, _h2, b2 = rt.http("GET", api + "/crates")
    out["reads"] = (st == 200 and (_j(b) or {}).get("name") == "seeded" and st2 == 200
                    and any(c.get("id") == 1000 for c in (_j(b2) or [])), "GET /crates/1000 %s, list %s" % (st, st2))
    st, _h, b = rt.http("POST", api + "/crates", {"name": "alpha", "pallets": [{"name": "p1"}, {"name": "p2"}]})
    cid = (_j(b) or {}).get("id")
    rs, _h, rb = rt.http("GET", api + "/crates/%s" % cid) if cid else (0, {}, "")
    crate = _j(rb) or {}
    pallets = sorted(crate.get("pallets") or [], key=lambda p: p.get("name") or "")
    out["create"] = (st == 201 and rs == 200 and crate.get("name") == "alpha" and [p.get("name") for p in pallets] == ["p1", "p2"],
                     "POST %s id=%s; read-back %s %s" % (st, cid, rs, [p.get("name") for p in pallets]))
    if cid:
        st, _h, _b = rt.http("PUT", api + "/crates/%s" % cid, {"name": "beta"})
        rs, _h, rb = rt.http("GET", api + "/crates/%s" % cid)
        out["update"] = (st == 204 and rs == 200 and (_j(rb) or {}).get("name") == "beta",
                         "PUT %s; read-back %s name=%s" % (st, rs, (_j(rb) or {}).get("name")))
    else:
        out["update"] = (False, "no created crate to update")
    st, _h, b = rt.http("POST", api + "/labels", {"name": "fragile"})
    lid = (_j(b) or {}).get("id")
    pid = pallets[0].get("id") if pallets else None
    if lid and pid:
        ls, _h, _b = rt.http("POST", api + "/pallets/%s/labels/%s" % (pid, lid))
        rs, _h, rb = rt.http("GET", api + "/pallets/%s" % pid)
        out["link"] = (ls == 204 and rs == 200 and [x.get("id") for x in (_j(rb) or {}).get("labels") or []] == [lid],
                       "link %s; pallet %s labels %s" % (ls, rs, (_j(rb) or {}).get("labels")))
        ds, _h, db = rt.http("DELETE", api + "/labels/%s" % lid)
        gs, _h, _b = rt.http("GET", api + "/labels/%s" % lid)
        ps, _h, pb = rt.http("GET", api + "/pallets/%s" % pid)
        out["label-delete"] = (ds == 204 and gs == 404 and ps == 200 and not ((_j(pb) or {}).get("labels") or []),
                               "DELETE %s; label %s; pallet %s labels %s" % (ds, gs, ps, (_j(pb) or {}).get("labels")))
    else:
        out["link"] = (False, "no label (%s) or pallet (%s)" % (lid, pid))
        out["label-delete"] = (False, "no linked label to delete")
    if cid:
        ds, _h, _b = rt.http("DELETE", api + "/crates/%s" % cid)
        gs, _h, _b = rt.http("GET", api + "/crates/%s" % cid)
        gone = [rt.http("GET", api + "/pallets/%s" % p.get("id"))[0] for p in pallets]
        out["crate-delete"] = (ds == 204 and gs == 404 and gone == [404] * len(pallets) and bool(pallets),
                               "DELETE %s; crate %s; pallets %s" % (ds, gs, gone))
    else:
        out["crate-delete"] = (False, "no created crate to delete")
    return out


def main() -> int:
    try:
        rt.need_tools("mvn", "java", "javac", "podman")
        table: dict[str, dict[str, tuple[bool, str]]] = {}
        with tempfile.TemporaryDirectory(prefix="repo-effects-rt-") as td, rt.postgres() as pg:
            for label, edits in VARIANTS.items():
                root = Path(td) / label
                shutil.copytree(FIXTURE, root)
                for fname, start, end, repl in edits:
                    rt.edit(root, PKG + fname, start, end, repl)
                ok, out = rt.package(root)
                if not ok:
                    print("FAIL: %s packages: %s" % (label, out[-900:]), file=sys.stderr)
                    return 1
                props = {"quarkus.datasource.jdbc.url": pg["url"], "quarkus.datasource.username": pg["user"],
                         "quarkus.datasource.password": pg["password"]}
                with rt.boot(root, "/api/crates", props) as base:
                    table[label] = exercise(base)
                (Path(td) / ("%s.log" % label)).write_text((root / "run.log").read_text(errors="replace"))
                if label == "remove-first":
                    log = (root / "run.log").read_text(errors="replace")
                    hits = [t for t in ("violates foreign key constraint", "TransientPropertyValueException",
                                        "ConstraintViolationException") if t in log]
                    table[label]["_log"] = (bool(hits), "the destination log names the flush-order failure: %s" % ", ".join(hits))
    except rt.Skip as exc:
        print("SKIP: repository-effects-runtime: %s" % exc)
        return 0
    for label, rows in table.items():
        for k, (ok, detail) in sorted(rows.items()):
            print("%-13s %-13s %-4s %s" % (label, k, "pass" if ok else "FAIL", detail))
    f, n, r = table["faithful"], table["noop-writes"], table["remove-first"]
    if not all(ok for ok, _d in f.values()):
        print("FAIL: the faithful delegates must pass every read and committed-write check", file=sys.stderr)
        return 1
    if not n["reads"][0] or any(n[w][0] for w in WRITES):
        print("FAIL: 'reads pass, writes do nothing' must pass the reads and fail every write check", file=sys.stderr)
        return 1
    if r["label-delete"][0] or not all(r[k][0] for k in ("reads", "create", "update", "link", "crate-delete")) or not r["_log"][0]:
        print("FAIL: the remove-first delete order must fail (and only it), with the flush-order failure in the log", file=sys.stderr)
        return 1
    print("OK: repository-effects-runtime (pinned platform %s, PostgreSQL 16 in podman, packaged jar over HTTP, every effect "
          "read back by an independent request after its transaction: faithful @Typed delegates pass reads, create with "
          "cascaded children, update of a detached row, a label link, the label delete removing its join row, and the "
          "crate delete cascading to its pallets; the no-op-write delegates pass the reads and fail create/update/delete; "
          "the remove-first label delete fails on Hibernate 6's flush (%s) while the dependents-first port passes)"
          % (rt.pin()["version"], r["label-delete"][1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
