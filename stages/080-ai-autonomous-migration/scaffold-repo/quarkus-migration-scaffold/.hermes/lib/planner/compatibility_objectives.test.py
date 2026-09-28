#!/usr/bin/env python3
"""compatibility-objectives/v1 selftest (SYNTHETIC evidence, no PetClinic name).

The baseline is the real derive_initial_graph revision (one outcome per
admitted unit); the objective revision is composed from it.

1. Three sorting units on the same files compose into ONE objective with one
   execution unit; the budget is their three accounts pooled once.
2. Main and test occurrences of one retired configuration rule compose; a
   different rule is not swept in.
3. Repository requirements are owned by their selected contract
   (facts.repository), two per contract composed, never by the Profile or DAO
   unit the baseline attached them to by first path; the contract waits on
   the units that own compile obligations in its files (verification).
4. Two disconnected controller sets stay two objectives; a connected set
   composes; an unqualified symbol qualifies only through the frozen model.
5. Renaming types and reordering clusters changes no membership (under the
   rename mapping); an unknown symbol or no family stays its own objective
   with a named reason; a missing catalog refuses.
6. One scope validator over the FINAL envelope: 20 files compose and 21
   refuse COMPOSITION_OVERSIZE -- for a plain union, for paths a requirement
   attaches and for a sealed child's writable paths; duplicates count once.
   Symbols are distinct source symbols, never transformation names: 8 pass,
   9 refuse, several under one transformation count separately, a shared one
   counts once; the 16-symbol fragment limit applies only when every
   constituent's seal qualified. Nothing is split to fit, and the refusal
   names what it accounts for.
7. Conservation: every obligation and requirement has one account; every
   later check is due at M4; a hard prerequisite cycle is PREREQUISITE_CYCLE.
8. Without objectives the revision is byte-identical to the baseline.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/compatibility_objectives.test.py
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import compatibility_objectives as CO  # noqa: E402
from planner import native_control as NC  # noqa: E402
from planner import outcome_graph as OG  # noqa: E402

HERMES = Path(__file__).resolve().parents[2]
CATALOG = json.loads((HERMES / "planning/catalogs/compat-mapping.json").read_text())
P = "src/main/java/com/acme/shop/"
PROV = {"snapshot_kind": "synthetic", "scope_note": "objectives selftest", "construction": "compatibility_objectives.test",
        "observed_migration_event": False}


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


class World:
    def __init__(self):
        self.items: list[dict] = []
        self.clusters: list[dict] = []
        self.seals: dict[str, dict] = {}
        self.reqs: list[dict] = []
        self.types: list[dict] = []
        self.n = 0

    def item(self, path: str, kind: str = "compile", rule: str = "compiler.err.doesnt.exist") -> str:
        self.n += 1
        iid = "err:%04d" % self.n if kind == "compile" else "inc:%04d" % self.n
        self.items.append({"id": iid, "kind": kind, "category": "mandatory", "path": P + path if "/" not in path or not path.startswith("src/") else path,
                           "source": "javac" if kind == "compile" else "mta", "rule_id": rule,
                           "identity": "diag:%s|%s|%04d" % (path, rule, self.n) if kind == "compile" else ""})
        return iid

    def unit(self, cid: str, symbol: str, kind: str, files: list[str], order: int, types: list[str] | None = None) -> None:
        ids = [self.item(f) for f in files]
        paths = [P + f for f in files]
        self.clusters.append({"id": cid, "kind": "compile", "status": "open", "items": ids, "write_set": paths,
                              "order_key": [2, order, paths[0]], "label": symbol,
                              "batch_scope": {"path": "evidence/planning/batch-scope/%s/x.json" % cid, "digest": "d" + cid,
                                              "rule": "unit/diagnostic-family/v1", "kind": "unit", "unit_id": cid}})
        self.seals[cid] = {"rule": "unit/diagnostic-family/v1", "symbols": [{"fqn": symbol, "kind": kind}],
                           "members": [{"path": P + f, "type": (types or ["com.acme.shop." + f.rsplit("/", 1)[-1][:-5]])[i % len(types or [1])]
                                        if types else "com.acme.shop." + f.rsplit("/", 1)[-1][:-5].replace("/", "."),
                                        "member_id": "", "occurrence": 0, "identity": self.items[-len(files) + i]["identity"]}
                                       for i, f in enumerate(files)]}

    def config(self, cid: str, path: str, rule: str, order: int) -> None:
        iid = self.item(path, kind="config", rule=rule)
        self.clusters.append({"id": cid, "kind": "config", "status": "open", "items": [iid], "write_set": [path],
                              "order_key": [1, order, path]})

    def worklist(self) -> dict:
        return {"items": copy.deepcopy(self.items), "clusters": copy.deepcopy(self.clusters), "unlocatable": [],
                "not_counted": [], "measure": {"known": True, "tuple": [0, len(self.items), 0]}}


def shop() -> World:
    w = World()
    w.config("c:cfg-main", "src/main/resources/application.properties", "springboot-properties-to-quarkus-00003", 0)
    w.config("c:cfg-test", "src/test/resources/application.properties", "springboot-properties-to-quarkus-00003", 1)
    w.config("c:cfg-other", "src/main/resources/application.properties", "props-rule-b", 2)
    m = ["model/Order.java", "model/Item.java", "model/Cart.java"]
    w.unit("u:sort-pkg", "org.springframework.beans.support", "package", m, 0)
    w.unit("u:sort-cmp", "org.springframework.beans.support.PropertyComparator", "type", m, 1)
    w.unit("u:sort-def", "org.springframework.beans.support.MutableSortDefinition", "type", m, 2)
    d = ["repo/data/DataOrderStore.java", "repo/data/DataOrderStoreImpl.java", "repo/data/OrderStoreCustom.java"]
    w.unit("u:profile", "org.springframework.context.annotation.Profile", "annotation", d, 3)
    w.unit("u:dao", "org.springframework.dao.DataAccessException", "type", ["repo/OrderStore.java", "repo/data/DataOrderStoreImpl.java"], 4)
    # two controller sets that share no file, each connected inside
    w.unit("u:val-a", "org.springframework.validation.BindingResult", "type", ["web/OrderApi.java", "web/Problem.java"], 5,
           types=["com.acme.shop.web.OrderApi", "com.acme.shop.web.Problem"])
    w.unit("u:uri-a", "org.springframework.web.util.UriComponentsBuilder", "type", ["web/OrderApi.java"], 6,
           types=["com.acme.shop.web.OrderApi"])
    w.unit("u:val-b", "org.springframework.validation.BindingResult", "type", ["admin/AuditApi.java"], 7,
           types=["com.acme.shop.admin.AuditApi"])
    # a wildcard-imported annotation the destination could not qualify
    w.unit("u:cors", "CrossOrigin", "annotation", ["web/OrderApi.java"], 8, types=["com.acme.shop.web.OrderApi"])
    w.types = [{"fqn": "com.acme.shop.web.OrderApi", "annotations": [{"fqn": "org.springframework.web.bind.annotation.CrossOrigin"}],
                "type_refs": [], "methods": [], "fields": []}]
    # an unrelated unit no family names
    w.unit("u:fmt", "org.springframework.format.annotation", "package", ["model/Order.java"], 9)
    rep = lambda rid, repo, paths, members: {"id": rid, "rule": "repository-architecture/v1", "status": "applicable", "class": "source",
                                            "subject": rid, "paths": [P + p for p in paths],
                                            "acceptance": ["unit:fragment-implementation", "structure:single-injectable-implementation",
                                                           "gate:startup", "behavior:repository-effects:" + repo],
                                            "facts": {"repository": repo, "members": members}, "consumers": [], "dependencies": []}
    w.reqs = [
        rep("req:repository-architecture:order-owed", "com.acme.shop.repo.data.DataOrderStore",
            ["repo/OrderStore.java", "repo/OrderStoreImpl.java", "repo/data/DataOrderStore.java"], ["save(Order)"]),
        rep("req:repository-architecture:order-selected", "com.acme.shop.repo.data.DataOrderStore",
            ["repo/data/OrderStoreCustom.java", "repo/data/DataOrderStore.java", "repo/data/DataOrderStoreImpl.java"], ["delete(Order)"]),
        rep("req:repository-architecture:item-owed", "com.acme.shop.repo.data.DataItemStore",
            ["repo/ItemStore.java", "repo/ItemStoreImpl.java", "repo/data/DataItemStore.java"], ["save(Item)"]),
        {"id": "req:annotation-retirement:order-api", "rule": "annotation-retirement/v1", "status": "applicable", "class": "source",
         "subject": "com.acme.shop.web.OrderApi@org.springframework.web.bind.annotation.CrossOrigin", "paths": [P + "web/OrderApi.java"],
         "acceptance": ["structure:annotation-absent:org.springframework.web.bind.annotation.CrossOrigin", "gate:compile"],
         "facts": {"sites": 1}, "consumers": [], "dependencies": []},
    ]
    return w


def derive(w: World, *, objectives: bool = True, catalog: dict | None = None, run_id: str = "r") -> dict:
    extra = {"objectives": {"catalog": CATALOG if catalog is None else catalog, "seals": copy.deepcopy(w.seals),
                            "item_symbols": {}, "structure_types": copy.deepcopy(w.types)}} if objectives else {}
    return OG.derive_initial_graph(run_id=run_id, worklist=w.worklist(), entry_points=[], oracles=None, references=None,
                                   provenance=PROV, requirements=copy.deepcopy(w.reqs), **extra)


def reps(g: dict) -> dict[str, dict]:
    return {n["outcome_id"]: n for n in g["nodes"] if n.get("role") == "repair"}


def by_clusters(g: dict) -> dict[frozenset, dict]:
    return {frozenset(n.get("clusters") or []): n for n in reps(g).values()}


def main() -> int:
    if set(CO.LATER_CHECK_PREFIXES) != set(NC.RUNTIME_CHECK_PREFIXES):
        return _fail("the objective policy defers exactly what native control defers")
    w = shop()
    base, g = derive(w, objectives=False), derive(w)
    nb, ng = reps(base), reps(g)
    bc = by_clusters(g)

    # 1. sorting
    sort = bc.get(frozenset({"u:sort-pkg", "u:sort-cmp", "u:sort-def"}))
    if not sort or not sort.get("execution_unit") or sort["objective"]["family"] != "collection-sorting":
        return _fail("three sorting units must compose into one objective: %s" % sorted(map(sorted, bc)))
    if sort["budget"]["limit"] != 9 or len(sort["budget"]["accounts"]) != 3:
        return _fail("the pooled sorting budget is its three accounts once: %s" % sort["budget"])
    # 2. configuration
    cfg = bc.get(frozenset({"c:cfg-main", "c:cfg-test"}))
    if not cfg or frozenset({"c:cfg-other"}) not in bc:
        return _fail("main+test of one rule compose, another rule stays out: %s" % sorted(map(sorted, bc)))
    # 3. repositories
    acct = g["requirement_ownership"]
    order_owner = acct["req:repository-architecture:order-owed"]
    if order_owner != acct["req:repository-architecture:order-selected"] or order_owner == acct["req:repository-architecture:item-owed"]:
        return _fail("repository requirements are owned per selected contract: %s" % acct)
    if any(acct[r] in (ng.get("source:u:profile", {}).get("outcome_id"), ng.get("source:u:dao", {}).get("outcome_id"))
           for r in acct if r.startswith("req:repository")):
        return _fail("no repository requirement may be owned by the Profile or DAO unit")
    base_acct = base["requirement_ownership"]
    if base_acct["req:repository-architecture:order-selected"] not in ("source:u:profile", "source:u:dao"):
        return _fail("the baseline shape (first-path attachment to Profile/DAO) is not reproduced: %s" % base_acct)
    rep = ng[order_owner]
    if not {"source:u:profile", "source:u:dao"} <= set(rep["parents"]) or \
            not any("verification" in b for b in rep["prerequisites"].get("source:u:dao", [])):
        return _fail("the repository contract waits on the units owning compile obligations in its files: %s" % rep["prerequisites"])
    if rep["budget"]["key"] != ng["source:u:dao"]["budget"]["key"]:
        return _fail("a separated repository responsibility keeps its originating allowance (one family with DAO)")
    # 4. controllers
    val_a = bc.get(frozenset({"u:val-a", "u:uri-a", "u:cors"}))
    if not val_a or frozenset({"u:val-b"}) not in bc:
        return _fail("the connected controller set composes and the disconnected one stays separate: %s" % sorted(map(sorted, bc)))
    if acct["req:annotation-retirement:order-api"] != val_a["outcome_id"]:
        return _fail("the CrossOrigin retirement belongs to the request-boundary objective of its type")
    # 5. rename + reorder, unknown symbol, missing catalog
    ren = json.loads(json.dumps([w.items, w.clusters, w.seals, w.reqs, w.types]).replace("com.acme.shop", "net.other.zz")
                     .replace("Order", "Zlorp").replace("Item", "Aaxe"))
    w2 = World()
    w2.items, w2.clusters, w2.seals, w2.reqs, w2.types = ren
    w2.clusters.reverse()
    g2 = derive(w2)
    same = sorted(sorted(k) for k in by_clusters(g2)) == sorted(sorted(k) for k in bc)
    if not same:
        return _fail("renaming types and reordering clusters must not change membership")
    fmt = next(n for n in ng.values() if n.get("clusters") == ["u:fmt"])
    if fmt["objective"]["family"] or not fmt["objective"]["fallback_reason"]:
        return _fail("a unit no family names stays its own objective with a named reason")
    w3 = shop()
    w3.types = []
    g3 = derive(w3)
    cors3 = next(n for n in reps(g3).values() if "u:cors" in (n.get("clusters") or []))
    if len(cors3["clusters"]) != 1 or "unqualified" not in cors3["objective"]["fallback_reason"]:
        return _fail("an unqualified symbol without frozen evidence is not guessed into a family: %s" % cors3["objective"])
    try:
        derive(w, catalog={k: v for k, v in CATALOG.items() if k != "objective_families"})
    except OG.PlanError as exc:
        if exc.code != "OBJECTIVES_CATALOG":
            return _fail("a missing catalog refuses OBJECTIVES_CATALOG, got %s" % exc.code)
    else:
        return _fail("a requested policy without its catalog must refuse")
    # 6. one validator over the final envelope
    def refused(fn) -> str:
        try:
            fn()
        except OG.PlanError as exc:
            return exc.code if exc.code == "COMPOSITION_OVERSIZE" and "Accounted:" in str(exc) else "BAD:%s %s" % (exc.code, exc)
        return ""

    def tx_world(n_files: int) -> World:
        wb = World()
        a = ["b/F%02d.java" % i for i in range(n_files)]
        wb.unit("u:tx-a", "org.springframework.transaction.annotation", "package", a[:11], 0)
        wb.unit("u:tx-b", "org.springframework.transaction.annotation.Transactional", "annotation", a[10:], 1)
        return wb
    gb = derive(tx_world(20))
    if frozenset({"u:tx-a", "u:tx-b"}) not in by_clusters(gb) or \
            len(by_clusters(gb)[frozenset({"u:tx-a", "u:tx-b"})]["execution_unit"]["paths"]) != 20:
        return _fail("a 20-file connected component composes into one 20-path scope")
    if refused(lambda: derive(tx_world(21))) != "COMPOSITION_OVERSIZE":
        return _fail("a 21-file connected component is a typed refusal, never an unproved split: %s"
                     % refused(lambda: derive(tx_world(21))))
    # requirement-attached paths count, duplicates once
    ctl = next(n for n in reps(g).values() if "u:val-a" in (n.get("clusters") or []))
    have = len(ctl["execution_unit"]["paths"])
    for extra, ok in ((20 - have, True), (21 - have, False)):
        wr = shop()
        wr.reqs[3]["paths"] += [P + "zz/Extra%02d.java" % i for i in range(extra)] + [ctl["execution_unit"]["paths"][0]]
        got = refused(lambda: derive(wr))
        if ok and got:
            return _fail("20 final paths (requirement-attached, one duplicate) compose: %s" % got)
        if not ok and got != "COMPOSITION_OVERSIZE":
            return _fail("21 final paths after requirement attachment refuse before any grant: %s" % (got or "composed"))
        if ok:
            node = next(n for n in reps(derive(wr)).values() if "u:val-a" in (n.get("clusters") or []))
            eu = node["execution_unit"]
            if len(eu["paths"]) != 20 or eu["bounds"]["files"] != 20 or not eu["bounds"]["within"]:
                return _fail("the recorded bound is the final envelope's: %s over %d paths" % (eu["bounds"], len(eu["paths"])))
    # a sealed child's writable paths count
    for extra, ok in ((9, True), (10, False)):
        wc_ = tx_world(11)
        wc_.seals["u:tx-a"]["writable_paths"] = [P + "b/F%02d.java" % i for i in range(11)] + [P + "c/W%02d.java" % i for i in range(extra)]
        got = refused(lambda: derive(wc_))
        if bool(got) == ok or (got and got != "COMPOSITION_OVERSIZE"):
            return _fail("%d sealed child path(s) beyond an 11-file union: %s" % (extra, got or "composed"))
    # symbols: distinct source symbols, never transformation names
    def sym_world(parts: list[list[str]], fragment: tuple[bool, ...] = ()) -> tuple[World, dict]:
        cat = copy.deepcopy(CATALOG)
        allsyms = sorted({x for part in parts for x in part})
        cat["objective_families"]["families"]["collection-sorting"]["transformations"].append(
            {"id": "selftest-multi-symbol", "symbols": allsyms})
        ws = World()
        for j, part in enumerate(parts):
            cid = "u:many%d" % j
            ws.unit(cid, part[0], "type", ["model/Shared.java"], j)
            ws.seals[cid]["symbols"] = [{"fqn": x, "kind": "type"} for x in part]
            if fragment and fragment[j]:
                ws.seals[cid]["bounds"] = {"max_symbols": CO.MAX_FRAGMENT_SYMBOLS}
        return ws, cat
    syms = ["example.compat.Type%d" % i for i in range(12)]
    for parts, fragment, ok, why in (
            ([syms[0:4], syms[4:8]], (), True, "8 distinct symbols under ONE transformation"),
            ([syms[0:5], syms[5:9]], (), False, "9 distinct symbols"),
            ([syms[0:5], syms[3:8]], (), True, "5 + 5 sharing 2 identities count 8"),
            ([syms[0:5], syms[5:10]], (True, True), True, "10 symbols where every seal qualified as a fragment set"),
            ([syms[0:5], syms[5:10]], (True, False), False, "10 symbols where only one seal qualified")):
        ws, cat = sym_world(parts, fragment)
        got = refused(lambda: derive(ws, catalog=cat))
        if ok and got:
            return _fail("%s must compose: %s" % (why, got))
        if not ok and got != "COMPOSITION_OVERSIZE":
            return _fail("%s must refuse COMPOSITION_OVERSIZE: %s" % (why, got or "composed"))
        if ok:
            eu = next(n["execution_unit"] for n in reps(derive(ws, catalog=cat)).values() if n.get("execution_unit"))
            want = len({x for part in parts for x in part})
            if eu["bounds"]["symbols"] != want:
                return _fail("%s: the bound counts %s symbols, want %d" % (why, eu["bounds"]["symbols"], want))
    # 7. conservation, later checks, cycle
    if set(g["ownership"]) != set(base["ownership"]) or set(acct) != set(base_acct):
        return _fail("every obligation and requirement keeps exactly one account")
    if g["composition"]["budget"]["baseline_total"] != g["composition"]["budget"]["objective_total"]:
        return _fail("budget not conserved: %s" % g["composition"]["budget"])
    m4 = next(n for n in g["nodes"] if n.get("role") == "assess")
    later = {(d["outcome"], d["check"]) for d in (m4.get("acceptance") or {}).get("deferred_requirement_checks") or []}
    if (order_owner, "gate:startup") not in later or "gate:startup" in rep["acceptance"]["requirement_checks"]:
        return _fail("a later check is due at M4 and never judged at the card: %s" % sorted(later)[:4])
    wc = shop()
    wc.reqs.append({"id": "req:annotation-retirement:cycle", "rule": "annotation-retirement/v1", "status": "applicable",
                    "class": "source", "subject": "com.acme.shop.admin.AuditApi@org.springframework.web.bind.annotation.CrossOrigin",
                    "paths": [P + "admin/AuditApi.java", P + "web/OrderApi.java"], "acceptance": ["gate:compile"],
                    "facts": {}, "consumers": [], "dependencies": []})
    wc.reqs[3]["paths"] = [P + "web/OrderApi.java", P + "admin/AuditApi.java"]
    try:
        derive(wc)
    except OG.PlanError as exc:
        if exc.code != "PREREQUISITE_CYCLE":
            return _fail("mutual check prerequisites must refuse PREREQUISITE_CYCLE, got %s" % exc.code)
    else:
        return _fail("mutual check prerequisites were planned instead of refused")
    # 8. without objectives: exactly the baseline
    if derive(w, objectives=False)["digest"] != base["digest"] or any(n.get("objective") for n in nb.values()):
        return _fail("without the policy the revision is unchanged")
    if derive(w)["digest"] != g["digest"]:
        return _fail("two derivations from identical inputs differ")
    print("OK: compatibility objectives (sorting and main/test configuration compose; repository requirements owned per "
          "selected contract behind their verification prerequisites; disconnected controllers stay apart; rename/reorder "
          "invariant; unknown symbols and missing catalogs are explicit; bounds refuse at +1; conservation, later checks at "
          "M4, prerequisite cycles refused; budget families conserved; unchanged without the policy)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
