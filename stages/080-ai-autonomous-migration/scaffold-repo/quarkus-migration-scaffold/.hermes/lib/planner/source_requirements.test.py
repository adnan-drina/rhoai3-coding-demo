#!/usr/bin/env python3
"""source_requirements selftest: known migration work is planned from the frozen source.

1. The migration specimen (PetClinic spelling) derives every V16
   responsibility BEFORE any destination failure: request validation for both
   BindingResult handlers, the URI-builder parameter binding, the CrossOrigin
   retirement AND the separate CORS adapter behaviour, the generator
   configuration with its consumers, the repository fragment architecture,
   the decided configuration, and a verification responsibility per entry
   point -- with no compiler error in the evidence.
2. A renamed structural twin (another package, other class, method and
   profile-free names) derives the SAME rule applications: no rule branches on
   a name.
3. Incomplete evidence never erases work: a partial model turns every "no
   site" into unresolved, an unresolved handler is unresolved, never absent.
4. Ambiguity is unresolved, not guessed: profile-gated fragment
   implementations without a decided profile, two implementations in the
   selected profile, an unqualified generator.
5. A decided repair already applied is satisfied with its receipt and never
   discharges the adapter behaviour.
6. Every recipe names checks that exist (functions and package-level tests).
7. The initial graph owns every requirement exactly once (conservation), puts
   the requirement checks on the owner, keeps the legacy revision unchanged
   when no requirements are given, bounds an oversize requirement as a typed
   blocker, and a finding revealed later -- in any order, through any
   endpoint -- resolves to the planned owner without a new budget; an
   unowned finding is a TYPED revision class.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import outcome_graph as OG  # noqa: E402
from planner import outcome_lifecycle as L  # noqa: E402
from planner import source_requirements as SR  # noqa: E402
from planner import specimens as S  # noqa: E402
from planner import worklist as W  # noqa: E402
from planner.canonical import load_json  # noqa: E402
from planner.evidence import derive_entry_points, load_catalogs  # noqa: E402

HERMES = Path(__file__).resolve().parents[2]
CATALOG = load_json(HERMES / "planning/catalogs/compat-mapping.json")
CATALOGS = load_catalogs(HERMES.parent)
GENERATOR = {"groupId": "org.openapitools", "artifactId": "openapi-generator-maven-plugin", "version": "7.25.0",
             "configuration": {"generatorName": "jaxrs-spec", "library": "quarkus", "modelPackage": "@DTO@"}, "configOptions": {}}
DECISIONS = {"datasource": {"adr": "ADR-001", "db_kind": "postgresql"}, "build_profiles": {"adr": "ADR-001", "active": ["spring-data-jpa"]}}


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def derive(base: str, names: dict, *, types=None, decisions=None, structure_complete=True, generator="default",
           oracles=None, decided_rows=None) -> dict:
    types = types if types is not None else S.migration_types(base, names)
    eps = derive_entry_points({"types": types}, CATALOGS)
    gen = None
    if generator == "default":
        gen = copy.deepcopy(GENERATOR)
        gen["configuration"]["modelPackage"] = "%s.%s.%s" % (base, names["rest"], names["dtopkg"])
    elif generator is not None:
        gen = generator
    return SR.derive(types=types, entry_points=eps, catalog=CATALOG, decisions=DECISIONS if decisions is None else decisions,
                     oracles=oracles, structure_complete=structure_complete, generator=gen,
                     decided_rows=decided_rows, bootstrap={"status": "ok", "blocks": []})


def shape(doc: dict) -> list[tuple]:
    """The rule applications without the names: rule, status, recipe,
    acceptance kinds, number of paths/consumers, dependency count."""
    return sorted((r["rule"], r["status"], (r.get("recipe") or {}).get("id"), tuple(a.split(":", 1)[0] + ":" + a.split(":", 2)[1] if a.count(":") >= 1 else a for a in r["acceptance"]),
                   len(r["paths"]), len(r["consumers"]), len(r["dependencies"])) for r in doc["requirements"])


def by_rule(doc: dict, rule: str) -> list[dict]:
    return [r for r in doc["requirements"] if r["rule"] == rule + "/v1"]


def planned_case() -> int:
    doc = derive("org.acme.clinic", S.PETCLINIC_NAMES)
    need = {"request-validation": 2, "handler-parameter-binding": 1, "annotation-retirement": 1, "adapter-behavior": 1,
            "generator-configuration": 1, "repository-architecture": 1, "configuration-decision": 2, "behavior-verification": 3}
    for rule, n in need.items():
        rows = [r for r in by_rule(doc, rule) if r["subject"] != "*"]
        if len(rows) != n:
            return _fail("%s: %d requirement(s), expected %d: %s" % (rule, len(rows), n, [r["id"] for r in rows]))
    val = by_rule(doc, "request-validation")
    if any(r["status"] != "applicable" or (r["recipe"] or {}).get("id") != "handler-validation-translation" for r in val):
        return _fail("the BindingResult handlers must be planned with the qualified translation recipe")
    if not all("unit:handler-validation-guards" in r["acceptance"] and r["facts"]["validated_body"] == ["dto"] for r in val):
        return _fail("the validation requirement must name its guard check and the validated body")
    ucb = by_rule(doc, "handler-parameter-binding")[0]
    if (ucb["recipe"] or {}).get("id") != "handler-uri-parameter" or "symbol_renames:org.springframework.web.util.UriComponentsBuilder" not in ucb["facts"]["precedes"]:
        return _fail("the URI builder parameter must be planned with the handler-parameter recipe ahead of the bare rename")
    ret = by_rule(doc, "annotation-retirement")[0]
    cors = by_rule(doc, "adapter-behavior")[0]
    if ret["facts"]["discharges_adapter_obligation"] is not False or ret["id"] not in cors["dependencies"]:
        return _fail("the retirement must never discharge the adapter behaviour, which follows it as a separate requirement")
    if cors["status"] != "unresolved" or not any(a.startswith("parity:cors-mode:") for a in cors["acceptance"]):
        return _fail("without a captured CORS scenario the adapter behaviour stays unresolved with both-mode checks named")
    gen = by_rule(doc, "generator-configuration")[0]
    if gen["status"] != "applicable" or len(gen["consumers"]) != 2:
        return _fail("the generator must be planned with its two consuming handlers: %s" % gen["consumers"])
    if not all(gen["id"] in r["dependencies"] for r in val):
        return _fail("generated models come before their consumers")
    repo = by_rule(doc, "repository-architecture")[0]
    if repo["status"] != "applicable" or repo["facts"]["selected"] != ["org.acme.clinic.repository.PetRepositoryOverrideImpl"]:
        return _fail("the fragment's selected implementation is the decided profile's <Fragment>Impl: %s" % repo["facts"])
    vb = by_rule(doc, "behavior-verification")
    if any(r["status"] != "unresolved" or r["acceptance"] != ["coverage:unresolved"] for r in vb):
        return _fail("an entry point with no oracle is an unresolved verification responsibility, never a PASS")
    return 0


def twin_case() -> int:
    a = derive("org.acme.clinic", S.PETCLINIC_NAMES)
    b = derive("com.example.ledger", S.LEDGER_NAMES)
    if shape(a) != shape(b):
        return _fail("the renamed twin derives different rule applications:\n%s\n%s" % (shape(a), shape(b)))
    # application-level subjects (the generator plugin, a decided setting, an
    # adapter) are the same in both; every source subject is the twin's own
    shared = ("generator-configuration/v1", "configuration-decision/v1", "adapter-behavior/v1")
    if {r["id"] for r in a["requirements"]} & {r["id"] for r in b["requirements"] if r["subject"] != "*" and r["rule"] not in shared}:
        return _fail("the twin's identities must be its own subjects")
    return 0


def incomplete_case() -> int:
    part = derive("org.acme.clinic", S.PETCLINIC_NAMES, structure_complete=False, types=[t for t in S.migration_types("org.acme.clinic", S.PETCLINIC_NAMES) if "Repository" not in t["fqn"]])
    na = [r for r in part["requirements"] if r["status"] == "not-applicable"]
    if na:
        return _fail("a partial model proved an absence: %s" % [r["id"] for r in na])
    if not any(r["id"] == "req:repository-architecture:*" and r["status"] == "unresolved" for r in part["requirements"]):
        return _fail("a partial model without the repository must leave the repository requirement unresolved")
    types = S.migration_types("org.acme.clinic", S.PETCLINIC_NAMES)
    for t in types:
        for m in t["methods"]:
            if m["name"] == "updateOwner":
                m["resolution"] = "partial"
    doc = derive("org.acme.clinic", S.PETCLINIC_NAMES, types=types)
    if not any(r["status"] == "unresolved" and "updateOwner" in r["subject"] for r in doc["requirements"]):
        return _fail("an unresolved handler must be an unresolved requirement")
    if any(r["status"] == "not-applicable" and r["rule"] == "request-validation/v1" for r in doc["requirements"]):
        return _fail("an unresolved handler must not let the rule be read as not applicable")
    # the complete http specimen has none of these features: proven absent
    http = S.specimen("http")
    full = SR.derive(types=http["types"], entry_points=derive_entry_points({"types": http["types"]}, CATALOGS), catalog=CATALOG,
                     decisions={}, oracles=None, structure_complete=True, generator=None)
    na = {r["rule"] for r in full["requirements"] if r["status"] == "not-applicable"}
    if not {"request-validation/v1", "annotation-retirement/v1", "generator-configuration/v1"} <= na:
        return _fail("a complete model without the features must say not-applicable: %s" % sorted(na))
    return 0


def ambiguity_case() -> int:
    doc = derive("org.acme.clinic", S.PETCLINIC_NAMES, decisions={})
    repo = by_rule(doc, "repository-architecture")[0]
    if repo["status"] != "unresolved" or "no decided build profile" not in " ".join(repo["unknowns"]):
        return _fail("profile-gated implementations without a decided profile are unresolved, never guessed")
    types = S.migration_types("org.acme.clinic", S.PETCLINIC_NAMES)
    for t in types:
        if t["fqn"].endswith("JdbcPetRepositoryImpl"):
            t["annotations"] = [{"fqn": S.A_PROFILE, "values": {"value": ["spring-data-jpa"]}}]
    doc = derive("org.acme.clinic", S.PETCLINIC_NAMES, types=types)
    if by_rule(doc, "repository-architecture")[0]["status"] != "unresolved":
        return _fail("two implementations in the selected profile are ambiguous")
    doc = derive("org.acme.clinic", S.PETCLINIC_NAMES, generator=dict(GENERATOR, configuration={"generatorName": "typescript-axios"}))
    if by_rule(doc, "generator-configuration")[0]["status"] != "unresolved":
        return _fail("a generator the catalog does not qualify is unresolved")
    return 0


def satisfied_case() -> int:
    ctrl = "src/main/java/org/acme/clinic/rest/OwnerRestController.java"
    rows = [{"id": "retire-cors", "kind": "java_retire_annotation", "status": "applied", "files": [ctrl],
             "symbols": ["org.acme.clinic.rest.OwnerRestController @org.springframework.web.bind.annotation.CrossOrigin"],
             "details": {"annotation": "org.springframework.web.bind.annotation.CrossOrigin"}}]
    doc = derive("org.acme.clinic", S.PETCLINIC_NAMES, decided_rows=rows)
    ret = by_rule(doc, "annotation-retirement")[0]
    if ret["status"] != "satisfied" or ret["facts"]["receipt"] != ["retire-cors"]:
        return _fail("an applied retirement is satisfied with its receipt: %s" % ret)
    if by_rule(doc, "adapter-behavior")[0]["status"] == "satisfied":
        return _fail("the retirement discharged the adapter behaviour")
    return 0


def recipes_case() -> int:
    recipes = SR.recipes_of(CATALOG)
    if len(recipes) != 5:
        return _fail("five qualified recipes expected, found %s" % sorted(recipes))
    for rid, r in recipes.items():
        if r["rule"] not in SR.RULES:
            return _fail("%s names an unknown rule %s" % (rid, r["rule"]))
        for chk in r.get("acceptance") or []:
            name = str(chk.get("checker") or "").split(" ", 1)[0]
            if name.startswith("planner.worklist."):
                if not callable(getattr(W, name.rsplit(".", 1)[-1], None)):
                    return _fail("%s cites %s, which does not exist" % (rid, name))
            elif name.startswith("skills/"):
                if not (HERMES / name).is_file():
                    return _fail("%s cites %s, which does not exist" % (rid, name))
            else:
                return _fail("%s cites an unresolvable checker %r" % (rid, name))
    return 0


def _graph(reqs: list[dict] | None, worklist: dict) -> dict:
    return OG.derive_initial_graph(run_id="r", worklist=worklist, entry_points=[], oracles=None, references=None,
                                   provenance={"snapshot_kind": "synthetic", "scope_note": "source requirements",
                                               "construction": "source_requirements.test", "observed_migration_event": False},
                                   requirements=reqs)


def graph_case() -> int:
    doc = derive("org.acme.clinic", S.PETCLINIC_NAMES)
    ctrl = "src/main/java/org/acme/clinic/rest/OwnerRestController.java"
    items = [{"id": "inc:web:1", "source": "mta", "kind": "incident", "category": "mandatory", "path": ctrl, "line": 20, "rule_id": "web"}]
    wl = {"items": items, "clusters": W.cluster_items(items, {}, set()), "unlocatable": [], "not_counted": [],
          "measure": {"known": True, "tuple": [1, 0, 0]}}
    legacy = _graph(None, wl)
    legacy2 = OG.derive_initial_graph(run_id="r", worklist=wl, entry_points=[], oracles=None, references=None,
                                      provenance=legacy["provenance"])
    if legacy["digest"] != legacy2["digest"] or "requirements" in legacy:
        return _fail("without requirements the revision must be exactly the legacy one")
    g = _graph(doc["requirements"], wl)
    acct = g["requirement_ownership"]
    if set(acct) != {r["id"] for r in doc["requirements"]}:
        return _fail("a requirement has no account")
    owners = {n["outcome_id"]: n for n in g["nodes"]}
    ctrl_owner = acct[by_rule(doc, "request-validation")[0]["id"]]
    if not ctrl_owner.startswith("source:c:") or acct[by_rule(doc, "annotation-retirement")[0]["id"]] != ctrl_owner:
        return _fail("the controller's requirements must join the finding cluster that already owns that file: %s" % ctrl_owner)
    node = owners[ctrl_owner]
    if "unit:handler-validation-guards" not in node["acceptance"]["requirement_checks"] or node["budget"]["limit"] != 3:
        return _fail("the owner carries the requirement checks and keeps its own budget: %s" % node["acceptance"])
    gen_owner = acct[by_rule(doc, "generator-configuration")[0]["id"]]
    if gen_owner not in node["parents"]:
        return _fail("the generator's owner must precede its consumers' owner")
    if not acct[by_rule(doc, "adapter-behavior")[0]["id"]].startswith("unresolved:"):
        return _fail("the unresolved CORS behaviour must be an explicit unresolved responsibility")
    for r in doc["requirements"]:
        if r["status"] == "applicable" and acct[r["id"]] not in owners:
            return _fail("applicable %s has no outcome" % r["id"])
    # the owner's acceptance is not met by an empty work list
    m = {"classes": ["compile", "tests"], "scenarios": [], "open": []}
    if L._covers(node, m):
        return _fail("a measurement without the requirement checks covered a requirement owner")
    if not L._covers(node, dict(m, checks=node["acceptance"]["requirement_checks"])):
        return _fail("a measurement recording every requirement check must cover it")
    # reveal order: the same defect seen through either handler, or first via a compile error, keeps its owner
    for item in ({"id": "err:x", "source": "javac", "kind": "compile", "path": ctrl},
                 {"id": "par:y", "source": "parity", "kind": "parity", "path": "", "entry_point": by_rule(doc, "request-validation")[1]["consumers"][0]}):
        got = OG.owner_of_finding(g, item)
        if got.get("owner") != ctrl_owner:
            return _fail("a later finding %s did not resolve to its planned owner: %s" % (item["id"], got))
    other = OG.owner_of_finding(g, {"id": "err:z", "source": "javac", "kind": "compile", "path": "src/main/java/x/Unplanned.java"})
    if other.get("owner") is not None or other.get("class") != "missing-planning-rule":
        return _fail("a finding outside every planned scope must be a typed revision: %s" % other)
    # oversize: one requirement wider than a coherent unit is a typed blocker
    big = copy.deepcopy(by_rule(doc, "repository-architecture")[0])
    big["paths"] = ["src/main/java/p/F%02d.java" % i for i in range(25)]
    g2 = _graph([big], wl)
    u = [x for x in g2["unresolved"] if big["id"] in (x.get("requirements") or [])]
    if not u or "UNIT_OVERSIZE" not in u[0]["reason"]:
        return _fail("an oversize requirement must be a typed UNIT_OVERSIZE blocker")
    # shuffled requirement order gives the same graph
    rev = _graph(list(reversed(doc["requirements"])), wl)
    if rev["digest"] != g["digest"]:
        return _fail("requirement order changed the graph")
    return 0


def main() -> int:
    for case in (planned_case, twin_case, incomplete_case, ambiguity_case, satisfied_case, recipes_case, graph_case):
        if case():
            return 1
    print("OK: source requirements (every V16 responsibility planned before a failure; a renamed twin derives the same "
          "rule applications; partial evidence is unresolved, never absent; ambiguity is unresolved; an applied repair is "
          "satisfied and discharges no adapter behaviour; recipes cite real checks; the graph owns each requirement once, "
          "carries its checks, bounds oversize work and resolves later findings to the planned owner)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
