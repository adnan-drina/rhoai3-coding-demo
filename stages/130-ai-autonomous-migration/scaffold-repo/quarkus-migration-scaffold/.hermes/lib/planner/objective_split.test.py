#!/usr/bin/env python3
"""split-large-objectives/v1 selftest (SYNTHETIC evidence, no specimen name).

An eight-file request-boundary objective (three units sharing a response type,
one requirement spanning two of its files, one requirement on one file, a
repository contract that waits on it) measured at 92 KiB on the tree:

1. Over the pinned byte bound (40 KiB) it is issued as three ordered
   parts. The parts partition the objective's write set and its obligations
   exactly; each obligation lies in its part's files; a requirement's files
   stay in one part and the requirement is owned and checked there; every
   (requirement, check) row is planned exactly once; the parts share the
   objective descriptor, class checks and budget family.
2. Dependencies: each part follows the one before it, the last part keeps the
   objective's id and waits on all of them, every node that waited on the
   objective waits on every part, M4 waits on every part; acyclic; the check
   schedule finds nothing the unsplit plan did not; the plan counts the
   objective once.
3. Renamed twin: renaming every package, type and file and reordering the
   clusters gives the same partition under the rename mapping.
4. The bound is BYTES only. The same eight files at 42.8 KB split into two
   parts; at a few bytes each they do not split (no file-count bound); a
   15-file 18.5 KB single-unit objective is one card. Below the bound (a
   three-file objective) the revision is byte-identical to the revision
   without the split; without a measured tree nothing splits; a single file
   past the byte bound is not split further.
5. Native execution (FakeNative board, real git, real native control): a part
   is issued its own files only, a write to another part's file refuses, the
   envelope carries the part and assesses only its files' members, the last
   part is issued every identity of the objective and assesses every member,
   and the progress account counts the objective once.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/objective_split.test.py
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "kernel"))
from planner import compatibility_objectives as CO  # noqa: E402
from planner import native_control as NC  # noqa: E402
from planner import outcome_graph as OG  # noqa: E402
from planner import worklist as W  # noqa: E402
from planner.canonical import write_canonical  # noqa: E402
from planner.outcome_checks import Refusal  # noqa: E402
from planner.worklist import batch_scope_digest, batch_scope_path, build_objective_scope  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CO_T = _load("co_split", HERE / "compatibility_objectives.test.py")
NB = _load("nb_split", HERE / "native_board.test.py")
import native_gate as NG  # noqa: E402

P = CO_T.P
KB = 1024
VAL, URI, CORS = ("org.springframework.validation.BindingResult", "org.springframework.web.util.UriComponentsBuilder",
                  "org.springframework.web.bind.annotation.CrossOrigin")
# file -> bytes on the tree at planning time (92 KiB in all)
SIZES = {"web/Problem.java": 2 * KB, "web/ItemApi.java": 12 * KB, "web/OrderApi.java": 18 * KB, "web/CartApi.java": 15 * KB,
         "web/UserApi.java": 9 * KB, "web/AdminApi.java": 6 * KB, "web/AuditApi.java": 5 * KB, "web/StockApi.java": 25 * KB,
         "repo/StockStore.java": 3 * KB}


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def fqn(f: str) -> str:
    return "com.acme.shop." + f[:-5].replace("/", ".")


def world() -> "CO_T.World":
    w = CO_T.World()
    val = ["web/Problem.java", "web/ItemApi.java", "web/OrderApi.java", "web/CartApi.java"]
    uri = ["web/OrderApi.java", "web/CartApi.java", "web/UserApi.java"]
    cors = ["web/UserApi.java", "web/AdminApi.java", "web/AuditApi.java", "web/StockApi.java"]
    w.unit("u:val", VAL, "type", val, 0, types=[fqn(f) for f in val])
    w.unit("u:uri", URI, "type", uri, 1, types=[fqn(f) for f in uri])
    w.unit("u:cors", CORS, "annotation", cors, 2, types=[fqn(f) for f in cors])
    # the frozen model: every endpoint type uses the shared response type
    w.types = [{"fqn": fqn(f), "path": P + f, "annotations": [], "methods": [], "fields": [],
                "type_refs": [] if f == "web/Problem.java" else [fqn("web/Problem.java")]}
               for f in sorted(set(val + uri + cors))]
    w.reqs = [
        {"id": "req:request-validation:item-create", "rule": "request-validation/v1", "status": "applicable", "class": "source",
         "subject": fqn("web/ItemApi.java") + "#create(" + fqn("model/Item.java") + ")",
         "paths": [P + "web/ItemApi.java", P + "web/Problem.java"],
         "acceptance": ["gate:compile", "parity:sc:item-create-invalid"],
         "facts": {"sites": 2}, "consumers": [], "dependencies": []},
        {"id": "req:annotation-retirement:order-api", "rule": "annotation-retirement/v1", "status": "applicable",
         "class": "source", "subject": fqn("web/OrderApi.java") + "@" + CORS, "paths": [P + "web/OrderApi.java"],
         "acceptance": ["gate:compile"],
         "facts": {"sites": 1}, "consumers": [], "dependencies": []},
        {"id": "req:repository-architecture:stock", "rule": "repository-architecture/v1", "status": "applicable",
         "class": "source", "subject": "req:repository-architecture:stock",
         "paths": [P + "repo/StockStore.java", P + "web/StockApi.java"],
         "acceptance": ["unit:fragment-implementation", "gate:startup"],
         "facts": {"repository": "com.acme.shop.repo.StockStore", "members": ["save(Stock)"]}, "consumers": [],
         "dependencies": []},
    ]
    return w


def sizes_of(w, table: dict[str, int]) -> dict[str, int]:
    return {P + f: n for f, n in table.items()}


def derive(w, sizes: dict[str, int] | None, run_id: str = "r") -> dict:
    obj = {"catalog": CO_T.CATALOG, "seals": copy.deepcopy(w.seals), "item_symbols": {},
           "structure_types": copy.deepcopy(w.types)}
    if sizes is not None:
        obj["file_sizes"] = dict(sizes)
    return OG.derive_initial_graph(run_id=run_id, worklist=w.worklist(), entry_points=[], oracles=None, references=None,
                                   provenance=CO_T.PROV, requirements=copy.deepcopy(w.reqs), objectives=obj)


def reps(g: dict) -> dict[str, dict]:
    return {n["outcome_id"]: n for n in g["nodes"] if n.get("role") == "repair"}


def objective_of(g: dict, cluster: str) -> dict:
    return next(n for n in reps(g).values() if cluster in (n.get("clusters") or []))


def parts_of(g: dict, oid: str) -> list[dict]:
    return sorted((n for n in reps(g).values() if (n.get("split") or {}).get("objective") == oid),
                  key=lambda n: n["split"]["part"])


def check_split(whole: dict, split: dict, sizes: dict[str, int]) -> str:
    """'' when ``split`` is a correct split of ``whole``'s request-boundary objective; else why not."""
    obj = objective_of(whole, "u:val")
    oid = obj["outcome_id"]
    parts = parts_of(split, oid)
    if len(parts) < 2:
        return "the objective was not split: %d part(s)" % len(parts)
    ids = [p["outcome_id"] for p in parts]
    if ids[-1] != oid or ids[:-1] != [CO.part_id(oid, i) for i in range(1, len(parts))]:
        return "the last part keeps the objective's id, earlier parts are numbered in order: %s" % ids
    if any(p["split"]["of"] != len(parts) or p["split"]["parts"] != ids for p in parts):
        return "every part names its position and its siblings"
    # 1. the write set and the obligations are partitioned exactly
    want_paths = set(obj["execution_unit"]["paths"])
    got = [set(p["plan_paths"]) for p in parts]
    if set().union(*got) != want_paths or sum(len(x) for x in got) != len(want_paths):
        return "the parts must partition the objective's write set: %s vs %s" % ([sorted(x) for x in got], sorted(want_paths))
    for p in parts:
        if set(p["execution_unit"]["paths"]) != set(p["plan_paths"]) or p["execution_unit"]["bounds"]["files"] != len(p["plan_paths"]):
            return "a part's executable scope is exactly its own files: %s" % p["outcome_id"]
        b = sum(sizes.get(x, 0) for x in p["plan_paths"])
        if b > CO.SPLIT_MAX_BYTES and len(p["plan_paths"]) > 1:
            return "%s holds %d bytes over %d files, past the bound" % (p["outcome_id"], b, len(p["plan_paths"]))
    obs = [set(p["obligations"]) for p in parts]
    if set().union(*obs) != set(obj["obligations"]) or sum(len(x) for x in obs) != len(obj["obligations"]):
        return "the parts must partition the objective's obligations"
    items = {i["id"]: i for i in split_items(split)}
    for p in parts:
        stray = [o for o in p["obligations"] if items[o]["path"] not in p["plan_paths"]]
        if stray:
            return "%s owns obligations outside its files: %s" % (p["outcome_id"], stray)
        if any(split["ownership"][o] != p["outcome_id"] for o in p["obligations"]):
            return "the plan's ownership names the part for each obligation it owns"
    if set(split["ownership"]) != set(whole["ownership"]):
        return "every obligation keeps exactly one account"
    # requirements: owned once, by the part holding all of their files; every check row planned once
    reqs = {r["id"]: r for r in split["requirements"]}
    if sorted(q for p in parts for q in p["requirements"]) != sorted(obj["requirements"]):
        return "the objective's requirements are distributed over its parts exactly once"
    for p in parts:
        for q in p["requirements"]:
            if split["requirement_ownership"][q] != p["outcome_id"] or not set(reqs[q]["paths"]) <= set(p["plan_paths"]):
                return "%s is owned and judged by the part holding its files" % q
    rows = lambda ns: sorted((r["requirement"], r["check"], r["stage"]) for n in ns for r in n.get("check_plan") or [])
    if rows(parts) != rows([obj]):
        return "every (requirement, check) row is planned exactly once: %s vs %s" % (rows(parts), rows([obj]))
    if set(split["requirement_ownership"]) != set(whole["requirement_ownership"]):
        return "every requirement keeps exactly one account"
    # the same objective, class checks and budget family on every part
    for p in parts:
        if p["objective"]["family"] != obj["objective"]["family"] or \
                [c["cluster"] for c in p["objective"]["constituents"]] != [c["cluster"] for c in obj["objective"]["constituents"]]:
            return "%s carries the objective's descriptor" % p["outcome_id"]
        if p["acceptance"]["checks"] != obj["acceptance"]["checks"] or p["budget"] != obj["budget"]:
            return "%s carries the objective's class checks and budget family" % p["outcome_id"]
    # the last part judges the whole objective
    last = parts[-1]
    if last["execution_unit"]["part"]["verifies"] != "objective" or \
            set(last["execution_unit"]["identities"]) != set(obj["obligations"]) or \
            sorted(last["execution_unit"]["constituents"]) != sorted(obj["clusters"]) or \
            sorted(last["clusters"]) != sorted(obj["clusters"]):
        return "the last part holds the clusters and verifies every identity and constituent of the objective"
    for p in parts[:-1]:
        if p["execution_unit"]["part"]["verifies"] != "part" or set(p["execution_unit"]["identities"]) != set(p["obligations"]) \
                or p["clusters"]:
            return "an earlier part verifies its own obligations and holds no cluster: %s" % p["outcome_id"]
    # 2. dependencies
    for k, p in enumerate(parts):
        if not set(obj["parents"]) <= set(p["parents"]) or not set(ids[:k]) <= set(p["parents"]):
            return "%s keeps the objective's parents and follows every earlier part: %s" % (p["outcome_id"], p["parents"])
    for n in split["nodes"]:
        if n["outcome_id"] in ids:
            continue
        was = next((m for m in whole["nodes"] if m["outcome_id"] == n["outcome_id"]), None)
        if was is not None and oid in was["parents"] and not set(ids) <= set(n["parents"]):
            return "%s waited on the objective and must wait on every part: %s" % (n["outcome_id"], n["parents"])
    m4 = next(n for n in split["nodes"] if n.get("role") == "assess")
    if not set(ids) <= set(m4["parents"]):
        return "M4 waits on every part"
    try:
        OG._acyclic(split["nodes"])
    except OG.PlanError as exc:
        return "the split graph has a cycle: %s" % exc
    order = [n["outcome_id"] for n in OG.topo_order(split["nodes"]) if n["outcome_id"] in ids]
    if order != ids:
        return "the parts run in order: %s" % order
    codes = lambda g: sorted({(f["code"], f["outcome"].split("/part:")[0]) for f in g["check_schedule"]["findings"]})
    if codes(split) != codes(whole):
        return "the split adds no schedule finding: %s vs %s" % (codes(split), codes(whole))
    # the plan counts the objective once
    if split["counts"]["baseline_outcomes"] != whole["counts"]["baseline_outcomes"] or \
            split["composition"]["objectives"] != whole["composition"]["objectives"]:
        return "the plan counts the objective once: %s vs %s" % (split["counts"], whole["counts"])
    row = next((r for r in split["composition"].get("split") or [] if r["objective"] == oid), None)
    if not row or row["parts"] != ids or row["files"] != len(want_paths):
        return "the composition records the split: %s" % split["composition"].get("split")
    if split["composition"]["budget"] != whole["composition"]["budget"]:
        return "budgets are conserved"
    return ""


def split_items(g: dict) -> list[dict]:
    return SPLIT_ITEMS[id(g)]


SPLIT_ITEMS: dict[int, list[dict]] = {}


def planning_cases() -> int:
    w = world()
    sizes = sizes_of(w, SIZES)
    whole = derive(w, None)
    split = derive(w, sizes)
    SPLIT_ITEMS[id(split)] = w.items
    why = check_split(whole, split, sizes)
    if why:
        return _fail("original: " + why)
    oid = objective_of(whole, "u:val")["outcome_id"]
    parts = parts_of(split, oid)
    names = [[x.rsplit("/", 1)[-1] for x in p["plan_paths"]] for p in parts]
    # leaf first: the shared response type (and the requirement that spans it) goes first
    if "Problem.java" not in names[0] or "ItemApi.java" not in names[0]:
        return _fail("the shared type and the requirement spanning it form the first part: %s" % names)
    titles = [p["title"] for p in parts]
    if len(set(titles)) != len(titles) or not all("part %d of %d" % (i + 1, len(parts)) in t for i, t in enumerate(titles)):
        return _fail("each part is titled with its position: %s" % titles)
    # the repository contract that read a file of the objective waits on every part
    repo = next(n for n in reps(split).values() if "req:repository-architecture:stock" in (n.get("requirements") or []))
    if not {p["outcome_id"] for p in parts} <= set(repo["parents"]):
        return _fail("the repository contract waits on every part: %s" % repo["parents"])
    if derive(w, sizes)["digest"] != split["digest"] or derive(w, sizes, run_id="other")["digest"] == split["digest"]:
        return _fail("the split is deterministic (same inputs, same digest; another run binding differs)")

    # 3. renamed twin: packages, types and files renamed, clusters reordered
    def rename(text: str) -> str:
        for a, b in (("com/acme/shop", "net/other/zz"), ("com.acme.shop", "net.other.zz"), ("Problem", "Fault"),
                     ("ItemApi", "WidgetEndpoint"), ("OrderApi", "LedgerEndpoint"), ("CartApi", "BasketEndpoint"),
                     ("UserApi", "MemberEndpoint"), ("AdminApi", "RootEndpoint"), ("AuditApi", "TrailEndpoint"),
                     ("StockApi", "SupplyEndpoint"), ("StockStore", "SupplyVault"), ("Item", "Widget"),
                     ("item-create", "widget-make"), ("order-api", "ledger-endpoint")):
            text = text.replace(a, b)
        return text
    w2 = CO_T.World()
    w2.items, w2.clusters, w2.seals, w2.reqs, w2.types = json.loads(rename(json.dumps([w.items, w.clusters, w.seals, w.reqs, w.types])))
    w2.clusters.reverse()
    sizes2 = json.loads(rename(json.dumps(sizes)))
    whole2, split2 = derive(w2, None), derive(w2, sizes2)
    SPLIT_ITEMS[id(split2)] = w2.items
    why = check_split(whole2, split2, sizes2)
    if why:
        return _fail("renamed twin: " + why)
    parts2 = parts_of(split2, objective_of(whole2, "u:val")["outcome_id"])
    if [sorted(rename(x) for x in p["plan_paths"]) for p in parts] != [sorted(p["plan_paths"]) for p in parts2]:
        return _fail("the renamed twin splits the same way under the rename mapping: %s vs %s"
                     % ([p["plan_paths"] for p in parts], [p["plan_paths"] for p in parts2]))
    if [sorted(p["requirements"]) for p in parts2] != [sorted(rename(q) for q in p["requirements"]) for p in parts]:
        return _fail("the renamed twin places its requirements in the same parts")

    # 4. below the bound: byte-identical; no measurement: nothing splits; one oversized file: not split further
    small = CO_T.World()
    three = ["web/Problem.java", "web/ItemApi.java", "web/OrderApi.java"]
    small.unit("u:val", VAL, "type", three, 0, types=[fqn(f) for f in three])
    small.unit("u:uri", URI, "type", ["web/OrderApi.java", "web/ItemApi.java"], 1,
               types=[fqn("web/OrderApi.java"), fqn("web/ItemApi.java")])
    small.reqs = [r for r in copy.deepcopy(w.reqs) if r["id"] != "req:repository-architecture:stock"]
    ssizes = sizes_of(small, {f: 9 * KB for f in three})
    a, b = derive(small, ssizes), derive(small, None)
    if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
        return _fail("a three-file objective under the bound must be byte-identical to the revision without the split")
    saved = CO.SPLIT_MAX_BYTES
    try:
        CO.SPLIT_MAX_BYTES = 10 ** 12
        c = derive(small, ssizes)
    finally:
        CO.SPLIT_MAX_BYTES = saved
    if json.dumps(a, sort_keys=True) != json.dumps(c, sort_keys=True) or "split" in a["composition"] or \
            any(n.get("split") for n in a["nodes"]):
        return _fail("below the bound the split changes nothing")
    if any(n.get("split") for n in whole["nodes"]) or "split" in whole["composition"]:
        return _fail("without a measured tree nothing is split (an unmeasured size is unknown, never zero)")
    big = CO_T.World()
    big.unit("u:val", VAL, "type", ["web/Problem.java"], 0, types=[fqn("web/Problem.java")])
    g = derive(big, sizes_of(big, {"web/Problem.java": 60 * KB}))
    if any(n.get("split") for n in g["nodes"]):
        return _fail("one file past the byte bound is the smallest card there is; it is not split")
    # bytes only: the same eight files at 42.8 KB split into two parts ...
    s428 = sizes_of(w, {"web/Problem.java": 1536, "web/ItemApi.java": 6144, "web/OrderApi.java": 7168,
                        "web/CartApi.java": 6144, "web/UserApi.java": 5632, "web/AdminApi.java": 5120,
                        "web/AuditApi.java": 4915, "web/StockApi.java": 7168})
    g = derive(w, s428)
    SPLIT_ITEMS[id(g)] = w.items
    why = check_split(whole, g, s428)
    if why or len(parts_of(g, oid)) != 2:
        return _fail("eight files at 42.8 KB split into exactly two parts: %s (%d parts)" % (why, len(parts_of(g, oid))))
    # ... and at a few bytes each they do not split: there is no file-count bound
    g = derive(w, sizes_of(w, {f: 1 for f in SIZES}))
    if any(n.get("split") for n in g["nodes"]) or "split" in g["composition"]:
        return _fail("eight small files under the byte bound are one card: a file count never splits")
    # a 15-file, 18.5 KB single-unit objective (one annotation across many small files) is one card
    many = CO_T.World()
    files = ["cfg/Profile%02d.java" % i for i in range(15)]
    many.unit("u:many", "org.springframework.context.annotation.Profile", "annotation", files, 0,
              types=[fqn(f) for f in files])
    msizes = sizes_of(many, {f: 1263 for f in files})          # 18945 bytes = 18.5 KiB
    a, b = derive(many, msizes), derive(many, None)
    if any(n.get("split") for n in a["nodes"]) or json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
        return _fail("a 15-file 18.5 KB objective is one card, byte-identical to the unsplit revision")
    return 0


# ---------------------------------------------------------------------------
# 5. native execution
# ---------------------------------------------------------------------------

def setup(w, sizes) -> "NB.Run":
    r = NB.Run(publish=False)
    NB.mirror_layout(r.root)
    wl = w.worklist()
    for c in wl["clusters"]:
        seal = w.seals.get(c["id"])
        doc = dict(copy.deepcopy(seal), cluster=c["id"], kind="unit", unit_id=c["id"],
                   writable_paths=sorted(set(c["write_set"]) | set(seal.get("writable_paths") or [])))
        doc["digest"] = batch_scope_digest(doc)
        rel = batch_scope_path(doc)
        write_canonical(r.root / rel, doc)
        c["batch_scope"] = {"path": rel.as_posix(), "digest": doc["digest"], "rule": doc["rule"], "kind": "unit", "unit_id": c["id"]}
        w.seals[c["id"]] = doc
    for c in wl["clusters"]:
        for p in c["write_set"]:
            f = r.root / p
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("// %s v0\n" % p)
    r.worklist = wl
    r.save_worklist()
    NB.git(r.root, "add", "-A")
    NB.git(r.root, "commit", "-qm", "split world")
    plan = OG.derive_initial_graph(run_id=r.run_id, worklist=wl, entry_points=[], oracles=None, references=None,
                                   provenance=CO_T.PROV, requirements=copy.deepcopy(w.reqs),
                                   objectives={"catalog": CO_T.CATALOG, "seals": copy.deepcopy(w.seals), "item_symbols": {},
                                               "structure_types": copy.deepcopy(w.types), "file_sizes": sizes})
    r.plan_file.write_text(json.dumps(plan))
    r.out = r.publish()
    r.release()
    return r


def native_case() -> int:
    w = world()
    r = setup(w, sizes_of(w, SIZES))
    try:
        plan = r.plan()
        oid = objective_of(plan, "u:val")["outcome_id"]
        parts = parts_of(plan, oid)
        if len(parts) != 3:
            return _fail("the published plan carries the three parts: %s" % [p["outcome_id"] for p in parts])
        for p in parts:
            if r.tid(p["outcome_id"]) is None:
                return _fail("%s is a published native task" % p["outcome_id"])
        acc0 = NC.progress_account(r.root, r.board, r.run_id)
        objectives = len([n for n in plan["nodes"] if n.get("role") == "repair"]) - (len(parts) - 1)
        if acc0["active"] != objectives or acc0["baseline"] != objectives:
            return _fail("the account counts the split objective once: %s (want %d)" % (acc0, objectives))
        orig = W.assess_unit

        def fake_assess(root, scope):
            # the children's own rule-specific assessors need the JDK model; here every member is "ok" with its path
            if str(scope.get("rule") or "") == W.OBJECTIVE_RULE:
                return orig(root, scope)
            return [{"member": "%s#" % m["path"], "path": m["path"], "verdict": "ok"} for m in scope.get("members") or []]
        for k, p in enumerate(parts):
            pid = p["outcome_id"]
            tid, run, iss = r.issue(pid)
            if iss["cluster"] != "objective:%s" % pid or sorted(iss["allowed_paths"]) != sorted(p["plan_paths"]):
                return _fail("%s is issued its own files only: %s %s" % (pid, iss["cluster"], iss["allowed_paths"]))
            other = next(x for q in parts if q is not p for x in q["plan_paths"])
            try:
                NC.check_write(r.board, task_id=tid, run_id=run, rel_paths=[other])
            except Refusal:
                pass
            else:
                return _fail("%s may not write %s, another part's file" % (pid, other))
            NG.write_issued_projection(r.root, iss)
            issued = json.loads((r.root / "verification/loop/issued.json").read_text())
            env = json.loads((r.root / issued["batch_scope"]["path"]).read_text())
            if env.get("part", {}).get("index") != k + 1 or sorted(env["writable_paths"]) != sorted(p["plan_paths"]):
                return _fail("the envelope carries the part and its files: %s" % env.get("part"))
            if build_objective_scope(r.root, pid, issued["objective"], r.worklist)["digest"] != env["digest"]:
                return _fail("the part's envelope rebuilds identically from its descriptor")
            last = k == len(parts) - 1
            mpaths = {m["path"] for m in env["members"]}
            if (not last and not mpaths <= set(p["plan_paths"])) or (last and mpaths != set(obj_paths(plan, oid))):
                return _fail("the members judged at %s: %s" % (pid, sorted(mpaths)))
            W.assess_unit = fake_assess
            try:
                rows = W.assess_unit(r.root, env)
            finally:
                W.assess_unit = orig
            rpaths = {x["path"] for x in rows}
            if (not last and not rpaths <= set(p["plan_paths"])) or (last and rpaths != set(obj_paths(plan, oid))):
                return _fail("%s assesses %s" % (pid, sorted(rpaths)))
            want = set(p["obligations"]) if not last else set(objective_of(derive_whole(w), "u:val")["obligations"])
            if set(issued["objective"]["identities"]) != want:
                return _fail("%s is judged on %s" % (pid, "its own obligations" if not last else "every obligation of the objective"))
            out = r.accept_on_run(tid, run, iss)
            if not out["outcome_accepted"]:
                return _fail("%s is accepted once its obligations are gone: %s" % (pid, out))
            r.review_and_complete(tid, run)
            acc = NC.progress_account(r.root, r.board, r.run_id)
            if acc["accepted_historically"] != (1 if last else 0) or acc["active"] != objectives:
                return _fail("after part %d the objective is %s: %s" % (k + 1, "accepted once" if last else "not yet accepted", acc))
    finally:
        r.close()
    return 0


def obj_paths(plan: dict, oid: str) -> list[str]:
    return sorted(x for p in parts_of(plan, oid) for x in p["plan_paths"])


def derive_whole(w) -> dict:
    return derive(w, None)


def main() -> int:
    rc = planning_cases() or native_case()
    if rc:
        return rc
    print("OK: objective split (an 8-file, 92 KiB objective is issued as 3 ordered parts that partition its files, "
          "obligations and requirements, carry its descriptor, checks and budget family, follow each other with the "
          "last keeping its id and verifying the whole; everything that waited on it waits on every part; acyclic, no "
          "new schedule finding, counted once; the renamed twin splits identically; bytes only: 8 files at 42.8 KB give 2 parts, 8 tiny files and a 15-file 18.5 KB unit stay one card; a 3-file objective under the bound "
          "is byte-identical, an unmeasured tree and a single oversized file are not split; natively each part is "
          "issued and judged on its own files, the last on the whole objective, and the account counts it once)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
