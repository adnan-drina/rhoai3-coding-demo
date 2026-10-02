#!/usr/bin/env python3
"""resolved_context selftest (V26-3): the issued objective's questions are answered from one attachment.

On the migration specimen (planner.specimens.migration_types: a CrossOrigin
controller over a GENERATED request body, a Spring Data repository whose
fragment has a profile-gated implementation beside an alternative one), with
the requirements planned by source_requirements.derive:

1. Inactive profile: the repository objective's context names the decided
   active profile (decisions.yaml), the selected implementation and the
   not-selected one with its profile and why -- every row with provenance.
2. Generated DTO: the validation objective's context places the handler's
   request-body type under the generated root with its generator, input and
   edit owner (never this file); handwritten types are placed under
   src/main/java; a type whose sources were not generated is an INFERENCE from
   the declared model package; a type nobody declares is a named unknown.
3. Wrong tree: a work list measured on another candidate never enters as a
   destination fact; a context bound to tree A is stale on tree B and
   fresh() withdraws its destination facts into unknowns naming both trees.
4. Missing information stays explicit: an owned requirement the plan lacks,
   an undecided build profile, a missing evidence bundle, a node with no
   staged check.
5. Renamed twin: the same assertions hold on another package and other type,
   method and profile names, and the twin's context names none of the first.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import resolved_context as RC  # noqa: E402
from planner import source_requirements as SR  # noqa: E402
from planner import specimens as S  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.evidence import derive_entry_points, load_catalogs  # noqa: E402
from planner.paths import CATALOGS_DIR, EVIDENCE_BUNDLE  # noqa: E402

HERMES = Path(__file__).resolve().parents[2]
CATALOG = load_json(HERMES / "planning/catalogs/compat-mapping.json")
CATALOGS = load_catalogs(HERMES.parent)
TREE_A, TREE_B = "a" * 64, "b" * 64


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def world(td: str, base: str, n: dict, *, decided: bool = True) -> tuple[Path, dict, list]:
    """A destination root carrying the planner inputs the context reads, and the plan derived from them."""
    root = Path(td)
    types = S.migration_types(base, n)
    spec = S.specimen("migration", base, n)
    (root / "pom.xml").write_text(spec["legacy_pom"], encoding="utf-8")
    for t in types:
        p = root / t["path"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("// handwritten\n", encoding="utf-8")
    dto = "%s.%s.%s.%s" % (base, n["rest"], n["dtopkg"], n["dto"])
    gen = root / "target/generated-sources/openapi/src/gen/java" / (dto.replace(".", "/") + ".java")
    gen.parent.mkdir(parents=True, exist_ok=True)
    gen.write_text("// generated\n", encoding="utf-8")
    write_canonical(root / EVIDENCE_BUNDLE, {"structure": {"available": True, "mode": "full", "source_digest": "d", "types": types},
                                             "build": {"source_roots": ["src/main/java"],
                                                       "generated_source_roots": spec["generated_source_roots"]}})
    (root / CATALOGS_DIR).mkdir(parents=True, exist_ok=True)
    (root / CATALOGS_DIR / "compat-mapping.json").write_text(json.dumps(CATALOG), encoding="utf-8")
    dec = dict(S.full_decisions(), build_profiles={"adr": "ADR-001", "active": [n["profile"]]}) if decided else S.full_decisions()
    (root / "decisions.yaml").write_text(S.decisions_yaml(dec), encoding="utf-8")
    generator = {"groupId": "org.openapitools", "artifactId": "openapi-generator-maven-plugin", "version": "7.25.0",
                 "configuration": {"generatorName": "jaxrs-spec", "library": "quarkus",
                                   "modelPackage": "%s.%s.%s" % (base, n["rest"], n["dtopkg"])}, "configOptions": {}}
    doc = SR.derive(types=types, entry_points=derive_entry_points({"types": types}, CATALOGS), catalog=CATALOG,
                    decisions={k: dec[k] for k in ("build_profiles",) if k in dec}, oracles=None, structure_complete=True,
                    generator=generator, bootstrap={"status": "ok", "blocks": []})
    return root, {"requirements": doc["requirements"]}, types


def req(plan: dict, rule: str, needle: str = "") -> dict:
    return next(r for r in plan["requirements"] if r["rule"] == rule + "/v1" and r["subject"] != "*" and needle in r["subject"])


def provenanced(doc: dict) -> str:
    """'' when every fact in every section carries a value, a provenance and a kind; else the first offender."""
    def walk(x, at):
        if isinstance(x, dict):
            if "value" in x or "provenance" in x:
                if not (x.get("provenance") and x.get("kind") in ("fact", "inference") and "value" in x):
                    return at
                return ""
            for k, v in x.items():
                hit = walk(v, "%s.%s" % (at, k))
                if hit:
                    return hit
        elif isinstance(x, list):
            for i, v in enumerate(x):
                hit = walk(v, "%s[%d]" % (at, i))
                if hit:
                    return hit
        return ""
    for sec in ("card", "source", "destination", "recipe", "checks"):
        hit = walk(doc.get(sec), sec)
        if hit:
            return hit
    return "" if all({"subject", "why", "provenance"} <= set(u) for u in doc.get("unknowns") or []) else "unknowns"


def values(rows: list, **match) -> list:
    return [r["value"] for r in rows if all((r["value"] or {}).get(k) == v for k, v in match.items())]


def specimen_case(base: str, n: dict) -> tuple[int, str]:
    tag = "[%s]" % base
    with tempfile.TemporaryDirectory(prefix="rc-") as td:
        root, plan, _types = world(td, base, n)
        data = "%s.%s" % (base, n["data"])
        rest = "%s.%s" % (base, n["rest"])
        dto = "%s.%s.%s" % (rest, n["dtopkg"], n["dto"])
        ctrl = "%s.%s" % (rest, n["controller"])
        ctrl_path = "src/main/java/%s/%s/%s.java" % (base.replace(".", "/"), n["rest"], n["controller"])

        # 1. inactive profile: answered from the attachment
        repo = req(plan, "repository-architecture")
        node = {"outcome_id": "o:repo", "requirements": [repo["id"]],
                "check_plan": [{"requirement": repo["id"], "check": "unit:fragment-implementation", "stage": "immediate", "prerequisites": []},
                               {"requirement": repo["id"], "check": "behavior:repository-effects:%s.%s" % (data, n["fragment"]),
                                "stage": "later", "due": ["behavior:ep:x"]}]}
        doc = RC.build(root, plan, node, None, TREE_A, issued={"cluster": "planned:o:repo", "allowed_paths": repo["paths"]})
        bad = provenanced(doc)
        if bad:
            return _fail("%s every assertion carries value, provenance and kind: %s" % (tag, bad)), ""
        ap = doc["source"].get("active_profiles") or {}
        if ap.get("value") != [n["profile"]] or not ap.get("provenance", "").startswith("decisions.yaml#build_profiles"):
            return _fail("%s the active profile is decisions.yaml's decision: %s" % (tag, ap)), ""
        impls = doc["source"]["implementations"]
        sel = values(impls, role="selected")
        off = values(impls, role="not-selected")
        if [v["type"] for v in sel] != ["%s.%sImpl" % (data, n["fragment"])] or sel[0]["profiles"] != [n["profile"]]:
            return _fail("%s the selected implementation is the decided profile's: %s" % (tag, sel)), ""
        if [v["type"] for v in off] != ["%s.%s" % (data, n["alt_impl"])] or off[0]["profiles"] != [n["alt_profile"]] \
                or n["alt_profile"] not in off[0]["why"]:
            return _fail("%s the inactive-profile implementation is named with its profile and why: %s" % (tag, off)), ""
        owed = [r for r in impls if r["value"].get("role") == "owed"]
        if any(r["kind"] != "inference" or not r.get("basis") for r in owed):
            return _fail("%s a contract-derived owed path is labelled an inference with its basis: %s" % (tag, owed)), ""
        if [c["value"]["check"] for c in doc["checks"]["immediate"]] != ["unit:fragment-implementation"] \
                or [c["value"]["due"] for c in doc["checks"]["deferred"]] != [["behavior:ep:x"]]:
            return _fail("%s immediate and deferred checks come from the node's check_plan: %s" % (tag, doc["checks"])), ""
        if not any(r["value"]["id"] == (repo["recipe"] or {}).get("id") and r["provenance"].endswith("migration_recipes.%s" % r["value"]["id"])
                   for r in doc["recipe"]):
            return _fail("%s the owned requirement's qualified recipe is carried from the catalog: %s" % (tag, doc["recipe"])), ""

        # 2. generated DTO: answered from the attachment
        val = req(plan, "request-validation", "#" + n["add"] + "(")
        vnode = {"outcome_id": "o:val", "requirements": [val["id"]]}
        wl = {"candidate_sha256": TREE_A, "items": [{"id": "inc:1", "path": ctrl_path, "line": 3, "rule_id": "r", "category": "mandatory"}]}
        doc2 = RC.build(root, plan, vnode, wl, TREE_A, issued={"cluster": "c:1", "write_set": [ctrl_path]})
        bad = provenanced(doc2)
        if bad:
            return _fail("%s every assertion carries value, provenance and kind: %s" % (tag, bad)), ""
        placed = {r["value"]["fqn"]: r for r in doc2["destination"]["types"]}
        g = placed.get(dto)
        if g is None or g["value"]["ownership"] != "generated" or g["kind"] != "fact" \
                or not g["value"]["path"].startswith("target/generated-sources/openapi/") \
                or g["value"]["generator"] != "openapi-generator-maven-plugin" or not g["value"]["inputs"] \
                or "never this file" not in g["value"]["edit_owner"] or g["tree"] != TREE_A:
            return _fail("%s the request body type is placed under its generated root with its generator and input: %s" % (tag, g)), ""
        h = placed.get(ctrl)
        if h is None or h["value"] != {"fqn": ctrl, "ownership": "handwritten", "path": ctrl_path}:
            return _fail("%s the handler's own type is handwritten, placed by its file: %s" % (tag, h)), ""
        if not any(v["type"] == dto and v["handler"].startswith(ctrl + "#") for v in values(doc2["source"]["parameters"])):
            return _fail("%s the body type comes from the frozen structural model's parameters: %s" % (tag, doc2["source"]["parameters"])), ""
        if [o["value"]["id"] for o in doc2["destination"]["open_obligations"]] != ["inc:1"]:
            return _fail("%s a work list of THIS tree is a destination fact: %s" % (tag, doc2["destination"]["open_obligations"])), ""
        if not any(c["kind"] == "inference" for c in doc2["checks"]["immediate"] + doc2["checks"]["deferred"]):
            return _fail("%s without a check_plan the staging is an inference, labelled: %s" % (tag, doc2["checks"])), ""
        if "active_profiles" not in doc2["source"]:
            return _fail("%s the decided profile is part of every objective's context" % tag), ""
        if not values(doc2["destination"]["generators"]) or not any(r["kind"] == "inference" for r in doc2["destination"]["generators"]):
            return _fail("%s the build's generators and the (inferred) generation command: %s" % (tag, doc2["destination"]["generators"])), ""

        # 3. wrong tree: rejected at build, stale after, withdrawn by fresh()
        old = RC.build(root, plan, vnode, dict(wl, candidate_sha256=TREE_B), TREE_A, issued={"write_set": [ctrl_path]})
        if old["destination"]["open_obligations"] or not any(TREE_B[:12] in u["why"] and u["provenance"].endswith("items[inc:1]")
                                                             for u in old["unknowns"]):
            return _fail("%s a work list measured on another tree never enters as a fact: %s" % (tag, old["unknowns"])), ""
        st = RC.staleness(doc2, TREE_B)
        if st["state"] != "stale" or not st["rejected"] or RC.staleness(doc2, TREE_A)["state"] != "current":
            return _fail("%s a context bound to tree A is stale on tree B, current on A: %s" % (tag, st)), ""
        moved = RC.fresh(doc2, TREE_B)
        if any(True for _ in RC._dest_facts(moved)) or moved["destination"]["withdrawn_from_tree"] != TREE_A \
                or not any(TREE_A[:12] in u["why"] and TREE_B[:12] in u["why"] for u in moved["unknowns"]):
            return _fail("%s fresh() withdraws every fact of the other tree into named unknowns: %s" % (tag, moved["destination"])), ""
        if doc2["source"] != moved["source"]:
            return _fail("%s frozen source facts are not bound to the destination tree" % tag), ""

        # sources not generated yet: an inference from the declared model package; nobody declares it: unknown
        (root / g["value"]["path"]).unlink()
        inf = {r["value"]["fqn"]: r for r in RC.build(root, plan, vnode, wl, TREE_A, issued={})["destination"]["types"]}.get(dto)
        if inf is None or inf["kind"] != "inference" or inf["value"]["path"] is not None or not inf.get("basis"):
            return _fail("%s an ungenerated type in the model package is an inference, not a fact: %s" % (tag, inf)), ""
        nobody = copy.deepcopy(plan)
        for r in nobody["requirements"]:
            if r["rule"] == "generator-configuration/v1":
                r["facts"]["model_package"] = ""
        (root / "pom.xml").unlink()
        gone = RC.build(root, nobody, vnode, wl, TREE_A, issued={})
        if dto in {r["value"]["fqn"] for r in gone["destination"]["types"]} or not any(u["subject"] == dto for u in gone["unknowns"]):
            return _fail("%s a type no root declares is a named unknown: %s" % (tag, gone["unknowns"])), ""

        # 4. missing information stays explicit
        miss = RC.build(root, plan, {"outcome_id": "o:x", "requirements": ["req:absent:x"]}, None, TREE_A, issued={})
        subjects = {u["subject"] for u in miss["unknowns"]}
        if not {"req:absent:x", "measured obligations", "checks"} <= subjects:
            return _fail("%s an absent requirement row, work list and check stage are named unknowns: %s" % (tag, subjects)), ""
        (root / EVIDENCE_BUNDLE).unlink()
        if "structural model" not in {u["subject"] for u in RC.build(root, plan, vnode, wl, TREE_A, issued={})["unknowns"]}:
            return _fail("%s a missing evidence bundle is a named unknown" % tag), ""
    with tempfile.TemporaryDirectory(prefix="rc-") as td:
        root, plan, _types = world(td, base, n, decided=False)
        repo = req(plan, "repository-architecture")
        und = RC.build(root, plan, {"outcome_id": "o:repo", "requirements": [repo["id"]]}, None, TREE_A, issued={})
        if "active_profiles" in und["source"] or values(und["source"]["implementations"], role="selected") \
                or "active build profile" not in {u["subject"] for u in und["unknowns"]}:
            return _fail("%s an undecided profile is an unknown, never a guessed selection: %s" % (tag, und["source"])), ""
    return 0, json.dumps([doc, doc2], sort_keys=True)


def main() -> int:
    rc, clinic = specimen_case("org.acme.clinic", S.PETCLINIC_NAMES)
    if rc:
        return 1
    rc, ledger = specimen_case("com.example.ledger", S.LEDGER_NAMES)
    if rc:
        return 1
    # the specimen's own type and method names (role words such as "owners" also occur in catalog prose)
    leaked = sorted(S.PETCLINIC_NAMES[k] for k in ("app", "controller", "dto", "add", "repo", "fragment", "entity", "alt_impl")
                    if S.PETCLINIC_NAMES[k] in ledger)
    if leaked or "org.acme.clinic" in ledger:
        return _fail("the twin's context names only the twin's own types: %s" % leaked)
    print("OK: resolved context (the inactive-profile and generated-DTO questions are answered from the attachment with "
          "provenance on every fact; contract-derived paths and ungenerated types are labelled inferences; a destination "
          "fact of another tree is rejected and withdrawn; missing inputs stay named unknowns; a renamed twin answers the same)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
