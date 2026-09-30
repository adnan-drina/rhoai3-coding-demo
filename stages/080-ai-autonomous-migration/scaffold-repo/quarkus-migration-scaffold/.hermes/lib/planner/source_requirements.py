"""Known migration responsibilities derived from the FROZEN source (plan semantics v1).

Pure over its arguments (``derive``): M1's structural model and entry points
(as sealed in the evidence bundle), the accepted decisions, the pinned
compatibility catalog (its ``migration_recipes``, ``handler_parameters``,
``adapter_owned_annotations`` and ``build_plugins`` rows), the captured
oracles, and the receipts of repairs the bootstrap already applied. No LLM,
no file-name heuristic, no application-name branch: every rule is keyed by a
qualified catalogue identity or a framework contract.

Each requirement is planned BEFORE any destination failure reveals it:

  repository-architecture   a Spring Data repository extending a project
                            fragment interface: one intended injectable
                            implementation per contract (the fragment's
                            <Fragment>Impl naming contract), selected profile
                            respected
  request-validation        a handler asking a BindingResult/Errors: the
                            validation translation that keeps the source's
                            guard and error response
  handler-parameter-binding a handler parameter kind the compatibility layer
                            does not bind (e.g. a URI builder): the parameter
                            binding and the Location it builds
  annotation-retirement     an adapter-owned annotation (e.g. CrossOrigin):
                            the compile half only
  adapter-behavior          the behaviour that annotation declared, owned by
                            the registered response adapter; a retirement
                            never discharges it
  generator-configuration   a build-time source generator: its configuration
                            and the request-body semantics of every handler
                            consuming its models (generated models before
                            their consumers)
  configuration-decision    decided datasource / security / build profiles:
                            existing configuration work, satisfied when the
                            bootstrap receipt applied it
  behavior-verification     every discovered entry point, HTTP or not: named
                            oracles, or explicitly unresolved coverage

Statuses: ``applicable`` (planned work), ``not-applicable`` (the complete
model proves there is no site), ``unresolved`` (unknown, ambiguous, or a
missing input -- NEVER read as absent), ``satisfied`` (already applied, with
the receipt that says so). A partial model makes every "no site" answer
``unresolved``.

Identities (``req:<rule>:<subject>``) carry no elapsed time, run id, path of
a checkout or native task id; evidence selectors are exact.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from planner.canonical import load_json

SCHEMA = "rhoai3.source-requirements/v1"
BUNDLE = "evidence/planning/evidence-bundle.json"

REPOSITORY_SUPERTYPES = (
    "org.springframework.data.repository.Repository",
    "org.springframework.data.repository.CrudRepository",
    "org.springframework.data.repository.ListCrudRepository",
    "org.springframework.data.jpa.repository.JpaRepository",
    "org.springframework.data.repository.PagingAndSortingRepository",
    "org.springframework.data.repository.ListPagingAndSortingRepository",
)
PROFILE_ANNOTATION = "org.springframework.context.annotation.Profile"
REQUEST_BODY = "org.springframework.web.bind.annotation.RequestBody"
FRAGMENT_SUFFIX = "Impl"  # Spring Data's fragment naming contract (worklist.FRAGMENT_IMPL_CONTRACT)

RULES = ("repository-architecture", "request-validation", "handler-parameter-binding", "annotation-retirement",
         "adapter-behavior", "generator-configuration", "configuration-decision", "application-path", "behavior-verification")
# the outcome class a requirement's work belongs to (outcome_graph.CLASSES)
RULE_CLASS = {"repository-architecture": "source", "request-validation": "source", "handler-parameter-binding": "source",
              "annotation-retirement": "source", "adapter-behavior": "behavior", "generator-configuration": "build",
              "configuration-decision": "config", "application-path": "config", "behavior-verification": "behavior"}
APPLICABLE, NOT_APPLICABLE, UNRESOLVED, SATISFIED = "applicable", "not-applicable", "unresolved", "satisfied"
# The rules whose work is a source REPAIR and so needs a qualified recipe
# (compat-mapping migration_recipes) before admission. Verification
# (behaviour, adapter behaviour) is judged by its named checks, and decided
# configuration by the decision and the bootstrap that applies it: neither has
# a recipe, and requiring one would refuse every run that captured an oracle.
RECIPE_RULES = ("repository-architecture", "request-validation", "handler-parameter-binding", "annotation-retirement",
                "generator-configuration")


def _s(v: Any) -> str:
    return v if isinstance(v, str) else ""


def _ann(anns: Any) -> list[str]:
    return [_s(a.get("fqn")) for a in anns or [] if isinstance(a, dict)]


def _ann_values(anns: Any, fqn: str) -> list[str]:
    out: list[str] = []
    for a in anns or []:
        if isinstance(a, dict) and _s(a.get("fqn")) == fqn:
            for v in (a.get("values") or {}).values():
                out.extend(str(x) for x in (v if isinstance(v, list) else [v]))
    return out


def rid(rule: str, subject: str) -> str:
    return "req:%s:%s" % (rule, subject)


def short(subject: str) -> str:
    return hashlib.sha256(subject.encode("utf-8")).hexdigest()[:12]


def recipes_of(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    block = (catalog or {}).get("migration_recipes") or {}
    return {str(k): dict(v) for k, v in block.items() if k != "note" and isinstance(v, dict) and v.get("rule")}


def _template_file() -> str:
    from planner.static_triggers import TEMPLATE_FILE
    return TEMPLATE_FILE


def _recipe_for(recipes: dict[str, dict[str, Any]], rule: str, key: str = "") -> dict[str, Any] | None:
    hits = sorted((rid_, r) for rid_, r in recipes.items() if r.get("rule") == rule and (not key or key in (r.get("applies_to") or [key])))
    if not hits:
        return None
    rid_, r = hits[0]
    return {"id": rid_, "version": str(r.get("version") or ""), "phase": str(r.get("phase") or "m3"),
            "implementation": str((r.get("implementation") or {}).get("kind") or "")}


def recipe_call_gap(recipes: dict[str, dict[str, Any]], recipe: dict[str, Any] | None, method: dict[str, Any]) -> str:
    """'' when the recipe qualifies this handler's calls, else the named capability gap.

    A recipe with ``requires_calls`` is qualified only for a handler that calls the
    listed owners and whose every call on them is one of ``names`` (the structural
    model records each distinct owner#name a method body calls). v26 t_4fd2dcec:
    a Servlet response parameter used only for sendRedirect has a verified
    translation; any other use of it has none, and a guess is not a translation."""
    spec = (recipes.get(str((recipe or {}).get("id") or "")) or {}).get("requires_calls")
    if not isinstance(spec, dict):
        return ""
    owners = set(spec.get("owners") or [])
    used = sorted({_s(c.get("name")) for c in method.get("calls") or [] if isinstance(c, dict) and _s(c.get("owner")) in owners})
    other = [n for n in used if n not in set(spec.get("names") or [])]
    gap = _s(spec.get("gap")) or "unqualified-call"
    if other:
        return "capability gap %s: the handler calls %s, which no qualified recipe translates" % (gap, ", ".join(other))
    if not used:
        return "capability gap %s: the handler never calls the parameter, so the qualified shape (%s) is absent" % (
            gap, ", ".join(spec.get("names") or []))
    return ""


def _req(rule: str, subject: str, status: str, *, evidence: list[dict[str, str]], paths: list[str], acceptance: list[str],
         recipe: dict[str, Any] | None = None, consumers: list[str] | None = None, unknowns: list[str] | None = None,
         dependencies: list[str] | None = None, facts: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": rid(rule, subject),
        "rule": "%s/v1" % rule,
        "subject": subject,
        "status": status,
        "class": RULE_CLASS[rule],
        "phase": (recipe or {}).get("phase") or ("verification" if rule in ("behavior-verification", "adapter-behavior") else "m3"),
        "recipe": recipe,
        "evidence": sorted(evidence, key=lambda e: (e.get("artifact", ""), e.get("selector", ""))),
        "paths": sorted(set(paths)),
        "consumers": sorted(set(consumers or [])),
        "acceptance": list(dict.fromkeys(acceptance)),
        "unknowns": sorted(set(unknowns or [])),
        "dependencies": sorted(set(dependencies or [])),
        "facts": facts or {},
    }


def _sel(*parts: str) -> dict[str, str]:
    return {"artifact": BUNDLE, "selector": ".".join(parts)}


def generator_body_semantics(facts: dict[str, Any], status: str) -> tuple[str, list[str], list[str], dict[str, Any]]:
    """V17-4: the generator requirement from the static facts
    (worklist.static_generated_body_facts). (status, acceptance, unknowns,
    facts). The qualification decides the status -- a pom that already stops
    the creator, or a generator that binds by setters, is not-applicable; an
    unqualified pair or an unreadable source build is unresolved -- and every
    required property of every request-body model contributes its four cases
    (omitted, null, empty, invalid), each bound to the captures that send it.
    A case no capture sends is an unknown, never an invented expectation."""
    q = facts.get("qualification") or {}
    qs = _s(q.get("status"))
    cases = [c for c in facts.get("cases") or [] if isinstance(c, dict)]
    if qs == NOT_APPLICABLE:
        new_status = NOT_APPLICABLE
    elif qs == APPLICABLE:
        new_status = status
    else:
        new_status = UNRESOLVED
    acceptance = ["build:clean-generation"]
    unknowns: list[str] = []
    if new_status != NOT_APPLICABLE:
        acceptance.append("parity:request-body-positive-negative")
        for c in sorted(cases, key=lambda c: (_s(c.get("model")), _s(c.get("property")), _s(c.get("case")))):
            if c.get("status") == "covered":
                acceptance.extend("parity:%s" % sid for sid in c.get("scenarios") or [])
            else:
                unknowns.append(_s(c.get("reason")) or "%s.%s %s: no capture" % (_s(c.get("model")), _s(c.get("property")), _s(c.get("case"))))
    if qs == UNRESOLVED:
        unknowns.extend("generator pair: %s" % r for r in q.get("reasons") or [])
    extra = {"qualification": {k: q.get(k) for k in ("status", "reasons", "dest", "source", "option")},
             "body_cases": [{k: c.get(k) for k in ("model", "property", "case", "status", "scenarios", "omitted_by_accepted") if k in c}
                            for c in cases],
             "omitted_by_accepted": sorted({"%s.%s" % (_s(c.get("model")), _s(c.get("property")))
                                            for c in cases if c.get("omitted_by_accepted")})}
    return new_status, list(dict.fromkeys(acceptance)), sorted(set(unknowns)), extra


# ---------------------------------------------------------------------------
# the derivation
# ---------------------------------------------------------------------------

def derive(*, types: list[dict[str, Any]], entry_points: list[dict[str, Any]], catalog: dict[str, Any],
           decisions: dict[str, Any] | None, oracles: dict[str, list[str]] | None, structure_complete: bool,
           generator: dict[str, Any] | None = None, generator_known: bool = True,
           decided_rows: list[dict[str, Any]] | None = None, bootstrap: dict[str, Any] | None = None,
           scenario_facts: dict[str, dict[str, Any]] | None = None,
           generator_facts: dict[str, Any] | None = None,
           source_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """{"schema", "requirements": [...], "unknowns": [...]}. Pure.

    ``scenario_facts``: scenario id -> {method, effects} from the captured
    corpus (a write is covered only by a scenario that reads its committed
    effect back); None when the corpus is unreadable.
    ``source_config`` (round 3): the frozen source's configuration files
    ({"files": {name: {key: value}}, "unread": [names]}), from which the
    application paths are derived; None when it could not be read.
    ``generator_facts`` (V17-4, worklist.static_generated_body_facts): the
    qualification of the destination/source generator pair and the request
    body cases bound to the corpus captures; None keeps the generator
    requirement exactly as before (a destination generator qualified by name
    only)."""
    types = sorted((t for t in types or [] if isinstance(t, dict) and _s(t.get("fqn"))), key=lambda t: t["fqn"])
    by_fqn = {t["fqn"]: t for t in types}
    recipes = recipes_of(catalog)
    hp = (catalog or {}).get("handler_parameters") or {}
    undocumented = {str(k): v for k, v in (hp.get("undocumented") or {}).items() if k != "note" and isinstance(v, dict)}
    adapter_owned = {str(k): v for k, v in ((catalog or {}).get("adapter_owned_annotations") or {}).items()
                     if k != "note" and isinstance(v, dict) and "." in str(k)}
    decisions = decisions or {}
    out: list[dict[str, Any]] = []
    unknowns: list[str] = []
    partial = sorted(t["fqn"] for t in types if _s(t.get("resolution") or "full") != "full")
    if not structure_complete:
        unknowns.append("the structural model is not complete; absence of a site is not evidence")
    eps = sorted((e for e in entry_points or [] if isinstance(e, dict) and _s(e.get("id"))), key=lambda e: e["id"])
    ep_by_handler: dict[tuple[str, str], str] = {}
    for e in eps:
        ep_by_handler[(_s(e.get("type")), _s(e.get("member")))] = e["id"]
    applied = {str(r.get("id")): r for r in decided_rows or [] if isinstance(r, dict) and r.get("status") in ("applied", "already-applied")}

    def none_found(rule: str, what: str) -> None:
        if structure_complete and not partial:
            out.append(_req(rule, "*", NOT_APPLICABLE, evidence=[_sel("structure", "types")], paths=[], acceptance=[],
                            facts={"reason": "the complete structural model has no %s" % what}))
        else:
            out.append(_req(rule, "*", UNRESOLVED, evidence=[_sel("structure", "types")], paths=[], acceptance=[],
                            unknowns=["no %s found, but the model is partial (%s): absence is unproven"
                                      % (what, ", ".join(partial[:3]) or "structure incomplete")]))

    # -- handlers and their parameters (HTTP entry points only) -----------
    handlers: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for e in eps:
        if _s(e.get("kind")) != "http":
            continue
        t = by_fqn.get(_s(e.get("type")))
        if t is None:
            continue
        ms = [m for m in t.get("methods") or [] if isinstance(m, dict) and _s(m.get("signature")) == _s(e.get("member"))]
        if len(ms) == 1:
            handlers.append((t, ms[0], e["id"]))
    generated_pkg = _s(((generator or {}).get("configuration") or {}).get("modelPackage"))

    validation = 0
    binding = 0
    location_eps: set[str] = set()  # V17-5: handlers that build a Location from a catalogued builder
    for t, m, ep in handlers:
        sig = _s(m.get("signature"))
        subject = "%s#%s" % (t["fqn"], sig)
        params = [p for p in m.get("params") or [] if isinstance(p, dict)]
        if any(_s(p.get("type")) == "" for p in params) or _s(m.get("resolution") or "full") != "full":
            partial.append("%s (handler parameters unresolved)" % subject)
            out.append(_req("request-validation", subject + "|unresolved", UNRESOLVED, evidence=[_sel("structure", "types[%s]" % t["fqn"], "methods[%s]" % sig)],
                            paths=[_s(t.get("path"))], acceptance=[], consumers=[ep],
                            unknowns=["the handler's parameters are not fully resolved; its validation and binding needs are unknown"]))
            continue
        body = [p for p in params if REQUEST_BODY in _ann(p.get("annotations"))]
        for p in params:
            ptype = _s(p.get("type"))
            row = undocumented.get(ptype)
            if not row or row.get("kind") != "type":
                continue
            sel = [_sel("structure", "types[%s]" % t["fqn"], "methods[%s]" % sig, "params[%s]" % _s(p.get("name")))]
            scen = sorted(set((oracles or {}).get(ep) or []))
            unk = [] if scen else ["no captured valid/invalid request scenario for %s: behavioural acceptance is unresolved" % ep]
            if row.get("translation"):
                validation += 1
                valid_params = [q for q in params if set(_ann(q.get("annotations"))) & {k for k, v in undocumented.items() if v.get("kind") == "annotation"}]
                facts = {"parameter": _s(p.get("name")), "parameter_type": ptype,
                         "validated_body": [_s(q.get("name")) for q in (body or valid_params)],
                         "valid_annotation_on": [_s(q.get("name")) for q in valid_params],
                         "translation": dict(row["translation"])}
                rec = _recipe_for(recipes, "request-validation", ptype)
                out.append(_req("request-validation", subject, APPLICABLE if rec else UNRESOLVED, evidence=sel, paths=[_s(t.get("path"))],
                                recipe=rec, consumers=[ep],
                                acceptance=["unit:handler-validation-guards", "gate:package"] + ["parity:%s" % s for s in scen],
                                unknowns=unk + ([] if rec else ["no qualified recipe for %s" % ptype]), facts=facts))
            else:
                binding += 1
                rec = _recipe_for(recipes, "handler-parameter-binding", ptype)
                gap = recipe_call_gap(recipes, rec, m)
                if gap:
                    rec = None
                elif rec is None and _s(row.get("capability_gap")):
                    gap = "capability gap %s: no qualified recipe for %s on the selected stack" % (_s(row.get("capability_gap")), ptype)
                loc = row.get("location_translation") if isinstance(row.get("location_translation"), dict) else None
                if loc:
                    location_eps.add(ep)
                out.append(_req("handler-parameter-binding", "%s|%s" % (subject, _s(p.get("name"))), APPLICABLE if rec else UNRESOLVED,
                                evidence=sel, paths=[_s(t.get("path"))], recipe=rec, consumers=[ep],
                                acceptance=["unit:handler-parameter-sites", "gate:package", "gate:augmentation"]
                                + (["unit:location-null-arguments"] if loc else []) + ["parity:%s" % s for s in scen],
                                unknowns=unk + ([] if rec else [gap or "no qualified recipe for %s" % ptype]),
                                facts=dict({"parameter": _s(p.get("name")), "parameter_type": ptype,
                                            **({"capability_gap": gap} if gap else {}),
                                            "precedes": ["symbol_renames:%s" % ptype]},
                                           **({"location": {"null_argument": _s(loc.get("null_argument")),
                                                            "substitution": _s(loc.get("substitution")),
                                                            "checked_by": _s(loc.get("checked_by"))}} if loc else {}))))
    if not validation:
        none_found("request-validation", "handler asking a catalogued validation-result parameter")
    if not binding:
        none_found("handler-parameter-binding", "handler parameter of a catalogued unbound kind")

    # -- adapter-owned annotations and the behaviour they declared --------
    per_adapter: dict[str, dict[str, Any]] = {}
    retire = 0
    for t in types:
        holders = [("type", "", t.get("annotations"))] + [("method", _s(m.get("signature")), m.get("annotations")) for m in t.get("methods") or [] if isinstance(m, dict)]
        sites = [(kind, name) for kind, name, anns in holders for a in _ann(anns) if a in adapter_owned]
        if not sites:
            continue
        for ann in sorted({a for _k, _n, anns in holders for a in _ann(anns) if a in adapter_owned}):
            row = adapter_owned[ann]
            retire += 1
            n_sites = sum(1 for _k, _n, anns in holders for a in _ann(anns) if a == ann)
            rec = _recipe_for(recipes, "annotation-retirement", ann)
            decided = [r for r in applied.values() if r.get("kind") == "java_retire_annotation" and _s(t.get("path")) in (r.get("files") or [])
                       and any(ann in str(s) for s in (r.get("symbols") or []) + [str((r.get("details") or {}).get("annotation") or "")])]
            status = SATISFIED if decided else (APPLICABLE if rec else UNRESOLVED)
            out.append(_req("annotation-retirement", "%s@%s" % (t["fqn"], ann), status,
                            evidence=[_sel("structure", "types[%s]" % t["fqn"], "annotations")], paths=[_s(t.get("path"))],
                            recipe=rec, acceptance=["structure:annotation-absent:%s" % ann, "gate:compile"],
                            unknowns=[] if rec else ["no qualified recipe for %s" % ann],
                            facts={"annotation": ann, "sites": n_sites, "adapter": _s(row.get("adapter")),
                                   "discharges_adapter_obligation": False,
                                   "receipt": sorted(str(r.get("id")) for r in decided)}))
            ad = per_adapter.setdefault(_s(row.get("adapter")), {"annotation": ann, "contract": _s(row.get("contract")), "types": set(), "eps": set()})
            ad["types"].add(t["fqn"])
            ad["eps"].update(e["id"] for e in eps if _s(e.get("type")) == t["fqn"])
    if not retire:
        none_found("annotation-retirement", "adapter-owned annotation")
    sec = decisions.get("security") if isinstance(decisions.get("security"), dict) else None
    modes = ["disabled", "enabled"] if sec else ["disabled"]
    for adapter in sorted(per_adapter):
        ad = per_adapter[adapter]
        scen = sorted({s for ep in ad["eps"] for s in (oracles or {}).get(ep) or []})
        out.append(_req("adapter-behavior", adapter, APPLICABLE if scen else UNRESOLVED,
                        evidence=[_sel("structure", "types[%s]" % f, "annotations") for f in sorted(ad["types"])],
                        paths=[], consumers=sorted(ad["eps"]),
                        acceptance=["adapter:%s" % ad["contract"]] + ["parity:%s-mode:%s" % (adapter, m) for m in modes] + ["parity:%s" % s for s in scen],
                        unknowns=[] if scen else ["no captured %s scenario for the covered entry points: behaviour coverage is unresolved" % adapter],
                        dependencies=[rid("annotation-retirement", "%s@%s" % (f, ad["annotation"])) for f in sorted(ad["types"])],
                        facts={"contract": ad["contract"], "security_modes": modes, "policy_source": "M1 structural model (source policy)"}))

    # -- repository fragments and single injectable implementations -------
    # V17-3: every fragment member also carries its SELECTED source behaviour
    # (repository_behaviour) and the functional verification that proves it
    # (repository_verification); an inactive-profile implementation is named
    # only as what the behaviour must NOT be copied from
    repos = [t for t in types if _s(t.get("kind")) == "interface" and set(t.get("supertypes") or []) & set(REPOSITORY_SUPERTYPES)]
    impls_of: dict[str, list[dict[str, Any]]] = {}
    for t in types:
        if _s(t.get("kind")) in ("class", "record"):
            for st in t.get("supertypes") or []:
                impls_of.setdefault(str(st), []).append(t)
    bp = decisions.get("build_profiles") if isinstance(decisions.get("build_profiles"), dict) else {}
    active = [str(p) for p in (bp.get("active") or [])]
    decided = active if active else None
    frags = 0
    for r in repos:
        if _selected(r, decided) is False:
            continue  # a repository the decided profiles do not select owes nothing
        for f in sorted(str(s) for s in r.get("supertypes") or []):
            if f in REPOSITORY_SUPERTYPES or f not in by_fqn or _s(by_fqn[f].get("kind")) != "interface":
                continue
            frags += 1
            ft = by_fqn[f]
            impls = sorted(impls_of.get(f, []), key=lambda x: x["fqn"])
            named = [i for i in impls if i["fqn"] == f + FRAGMENT_SUFFIX]
            profiled = {i["fqn"]: _ann_values(i.get("annotations"), PROFILE_ANNOTATION) for i in impls}
            selected = [i for i in impls if _selected(i, decided) is True]
            undecided = [i for i in impls if _selected(i, decided) is None] + ([r] if _selected(r, decided) is None else [])
            members = sorted(_s(m.get("signature")) for m in ft.get("methods") or [] if isinstance(m, dict))
            unk: list[str] = []
            status = APPLICABLE
            owed_path = ""
            if undecided and not selected:
                status, unk = UNRESOLVED, ["fragment %s has %d profile-gated implementations and no decided build profile" % (f, len(impls))]
            elif len(selected) > 1:
                status, unk = UNRESOLVED, ["fragment %s has %d implementations in the selected profile: the intended injectable one is ambiguous" % (f, len(selected))]
            if status == APPLICABLE and selected:
                # the source's own selected implementation is carried: its
                # methods ARE the behaviour of each member
                impl = selected[0]
                ms = [x for x in impl.get("methods") or [] if isinstance(x, dict)]
                wc = ((catalog or {}).get("repository_behaviour") or {}).get("write_calls") or {}
                rows = []
                for sig in members:
                    m = _match(ms, sig)
                    if m is None:
                        rows.append({"signature": sig, "kind": "unresolved", "source": "", "path": _s(impl.get("path")),
                                     "why": "%s declares no method answering %s" % (impl["fqn"], sig)})
                        continue
                    rows.append({"signature": sig, "kind": "source-override", "source": "%s#%s" % (impl["fqn"], _s(m.get("signature"))),
                                 "path": _s(impl.get("path")), "translations": persistence_translations(m, catalog),
                                 "effect": "write" if any(_calls_match(wc, c) for c in m.get("calls") or [] if isinstance(c, dict)) else "read",
                                 "why": "the selected source implementation of the fragment"})
                behaviour = {"parent": f, "repository": r["fqn"], "members": rows, "not_behaviour_sources": [
                    {"type": i["fqn"], "path": _s(i.get("path")), "profiles": profiled[i["fqn"]],
                     "why": "gated by @Profile(%s), which the decided build profiles do not select" % ",".join(profiled[i["fqn"]])}
                    for i in impls if _selected(i, decided) is False], "unknowns": []}
                unk.extend("member %s: %s" % (x["signature"], x["why"]) for x in rows if x["kind"] == "unresolved")
            elif status == APPLICABLE:
                # no implementation in the decided profiles: Spring Data served the
                # members in the source; the destination's generator needs a
                # <Fragment>Impl (FRAGMENT_IMPL_CONTRACT), owed with that behaviour
                behaviour = repository_behaviour(types, parent=f, members=members, decisions=decisions, catalog=catalog)
                owed_path = "%s/%s%s.java" % (_s(ft.get("path")).rsplit("/", 1)[0], f.rsplit(".", 1)[-1], FRAGMENT_SUFFIX)
                unk.extend(behaviour["unknowns"])
            else:
                behaviour = {"parent": f, "repository": r["fqn"], "members": [], "not_behaviour_sources": [], "unknowns": list(unk)}
            verification = repository_verification(behaviour, entry_points=eps, types=types, oracles=oracles,
                                                   scenarios=scenario_facts) if status == APPLICABLE else []
            unk.extend(u for v in verification for u in v["unknowns"])
            rec = _recipe_for(recipes, "repository-architecture")
            out.append(_req("repository-architecture", "%s<-%s" % (r["fqn"], f), status if rec else UNRESOLVED,
                            evidence=[_sel("structure", "types[%s]" % r["fqn"], "supertypes"), _sel("structure", "types[%s]" % f, "methods")]
                            + [_sel("structure", "types[%s]" % i["fqn"], "supertypes") for i in impls],
                            paths=[_s(x.get("path")) for x in [r, ft] + (named or selected[:1])] + ([owed_path] if owed_path else []),
                            recipe=rec,
                            acceptance=["unit:fragment-implementation", "unit:fragment-behaviour-bodies",
                                        "structure:single-injectable-implementation", "gate:package", "gate:startup",
                                        "behavior:repository-effects:%s" % f]
                            + ["parity:%s" % x for v in verification for x in v["scenarios"]],
                            unknowns=unk + ([] if rec else ["no qualified repository recipe"]),
                            facts={"repository": r["fqn"], "fragment": f, "members": members,
                                   "implementations": [i["fqn"] for i in impls], "selected": [i["fqn"] for i in selected],
                                   "profiles": {k: sorted(v) for k, v in profiled.items() if v}, "decided_profiles": active,
                                   "owed_implementation": owed_path, "behaviour": behaviour, "verification": verification}))
    if not frags:
        none_found("repository-architecture", "Spring Data repository extending a project fragment")

    # -- generator configuration and its consumers -------------------------
    if not generator_known:
        out.append(_req("generator-configuration", "*", UNRESOLVED, evidence=[], paths=["pom.xml"], acceptance=[],
                        unknowns=["the destination build configuration could not be read; generators are unknown"]))
    elif generator:
        conf = generator.get("configuration") or {}
        gname = _s(conf.get("generatorName"))
        ga = "%s:%s" % (_s(generator.get("groupId")), _s(generator.get("artifactId")))
        row = (((catalog or {}).get("build_plugins") or {}).get(ga) or {})
        qualified = bool((row.get("generators") or {}).get(gname))
        consumers = []
        for t, m, ep in handlers:
            for p in m.get("params") or []:
                if isinstance(p, dict) and REQUEST_BODY in _ann(p.get("annotations")) and generated_pkg and _s(p.get("type")).startswith(generated_pkg + "."):
                    consumers.append(ep)
        rec = _recipe_for(recipes, "generator-configuration", ga)
        unk = []
        if not qualified:
            unk.append("generator %s of %s is not qualified by the catalog (build_plugins)" % (gname or "(unnamed)", ga))
        if not rec:
            unk.append("no qualified generator recipe for %s" % ga)
        status = APPLICABLE if (qualified and rec) else UNRESOLVED
        acceptance = ["build:clean-generation", "parity:request-body-positive-negative"]
        facts = {"plugin_version": _s(generator.get("version")), "generator": gname,
                 "model_package": generated_pkg, "options": dict(generator.get("configOptions") or {})}
        if generator_facts is not None:
            status, acceptance, extra_unk, extra = generator_body_semantics(generator_facts, status)
            unk.extend(extra_unk)
            facts.update(extra)
        out.append(_req("generator-configuration", "%s|%s" % (ga, gname), status,
                        evidence=[{"artifact": "pom.xml", "selector": "build.plugins[%s].configuration" % ga}]
                        + ([{"artifact": _s(((generator_facts or {}).get("qualification") or {}).get("source", {}).get("build_file")),
                             "selector": "build.plugins[%s].configuration" % ga}]
                           if _s(((generator_facts or {}).get("qualification") or {}).get("source", {}).get("build_file")) else []),
                        # the required-readOnly action restores @NotNull through a build-owned
                        # template (static_triggers.TEMPLATE_FILE); an outcome-board grant must name it
                        paths=["pom.xml"] + ([_template_file()] if ((row.get("generators") or {}).get(gname) or {}).get("required_read_only") else []),
                        recipe=rec, consumers=consumers,
                        acceptance=acceptance, unknowns=unk, facts=facts))
    else:
        out.append(_req("generator-configuration", "*", NOT_APPLICABLE, evidence=[{"artifact": "pom.xml", "selector": "build.plugins"}],
                        paths=[], acceptance=[], facts={"reason": "the destination build declares no catalogued source generator"}))

    # -- decided configuration -------------------------------------------------
    bs_ok = isinstance(bootstrap, dict) and str(bootstrap.get("status")) == "ok" and not bootstrap.get("blocks")
    for key, fact in (("datasource", decisions.get("datasource")), ("security", decisions.get("security")),
                      ("build_profiles", decisions.get("build_profiles"))):
        if not isinstance(fact, dict) or not fact:
            continue
        out.append(_req("configuration-decision", key, SATISFIED if (bs_ok and key != "security") else APPLICABLE,
                        evidence=[{"artifact": "decisions.yaml", "selector": key}] + ([{"artifact": "evidence/producers/bootstrap.json", "selector": "status"}] if bs_ok else []),
                        paths=["src/main/resources/application.properties"] if key != "build_profiles" else [".mvn/maven.config", "pom.xml", "src/main/resources/application.properties"],
                        acceptance=["config:decided-keys", "gate:startup"],
                        facts={"adr": _s(fact.get("adr")), "applied_by_bootstrap": bs_ok and key != "security"}))

    # -- application paths (round 3): what the SOURCE configures ------------
    out.extend(application_paths(source_config, catalog, decisions))

    # -- behaviour verification of every entry point -----------------------
    for e in eps:
        scen = sorted(set((oracles or {}).get(e["id"]) or []))
        loc = e["id"] in location_eps
        blind = _unobservable_write(e, scen, scenario_facts)
        out.append(_req("behavior-verification", e["id"], APPLICABLE if scen and not blind else UNRESOLVED,
                        evidence=[_sel("entry_points[%s]" % e["id"])], paths=[], consumers=[e["id"]],
                        acceptance=(["parity:%s" % s for s in scen] or ["coverage:unresolved"])
                        + (["location:%s" % e["id"]] if loc and scen else []),
                        unknowns=([] if scen else ["no captured oracle for %s (%s): behaviour is unverified, never PASS" % (e["id"], _s(e.get("kind")))])
                        + (["the captured scenarios of %s declare no read-back of what the write persisted (%s): the response is "
                            "captured, the write is unverified, never PASS" % (e["id"], blind)] if blind else [])
                        + (["no capture of the source's create/Location behaviour for %s: the Location it builds, a null "
                            "expansion argument included, is unverified, never PASS" % e["id"]] if loc and not scen else []),
                        facts=dict({"kind": _s(e.get("kind")), "type": _s(e.get("type"))},
                                   **({"location": {"builds_location": True, "coverage": scen or "unresolved"}} if loc else {}))))
    if not eps:
        unknowns.append("no entry point was discovered; behaviour verification has nothing to cover")

    # -- dependencies: generated models before their consumers ------------
    gen_ids = [r["id"] for r in out if r["rule"] == "generator-configuration/v1" and r["status"] == APPLICABLE]
    for r in out:
        if r["rule"] in ("request-validation/v1", "handler-parameter-binding/v1") and gen_ids:
            if set(r["consumers"]) & {c for g in out if g["id"] in gen_ids for c in g["consumers"]}:
                r["dependencies"] = sorted(set(r["dependencies"]) | set(gen_ids))
    ids = [r["id"] for r in out]
    if len(ids) != len(set(ids)):
        raise ValueError("SOURCE_REQUIREMENT_DUPLICATE: %s" % sorted({i for i in ids if ids.count(i) > 1}))
    return {"schema": SCHEMA, "requirements": sorted(out, key=lambda r: r["id"]), "unknowns": sorted(set(unknowns))}


# ---------------------------------------------------------------------------
# V17-3: the SELECTED source behaviour of an owed fragment member
# ---------------------------------------------------------------------------

def _profiles_of(t: dict[str, Any]) -> list[str]:
    return _ann_values(t.get("annotations"), PROFILE_ANNOTATION)


def _selected(t: dict[str, Any], active: list[str] | None) -> bool | None:
    """True/False by the decided build profiles; None when a profile gate
    exists and no profile was decided (unknown, never guessed)."""
    prof = _profiles_of(t)
    if not prof:
        return True
    if active is None:
        return None
    return bool(set(prof) & set(active))


def _arity(sig: str) -> int:
    inner = sig[sig.find("(") + 1:sig.rfind(")")] if "(" in sig else ""
    if not inner.strip():
        return 0
    depth, n = 0, 1
    for ch in inner:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif ch == "," and depth == 0:
            n += 1
    return n


def _match(methods: list[dict[str, Any]], sig: str) -> dict[str, Any] | None:
    """The source method answering `sig`: the exact signature, else the one
    method with the same name and arity; None when absent or ambiguous."""
    exact = [m for m in methods if _s(m.get("signature")) == sig]
    if len(exact) == 1:
        return exact[0]
    name = sig.split("(", 1)[0]
    same = [m for m in methods if _s(m.get("name")) == name and _arity(_s(m.get("signature"))) == _arity(sig)]
    return same[0] if len(same) == 1 else None


def _calls_match(spec: dict[str, Any], call: dict[str, Any]) -> bool:
    return (_s(call.get("owner")) in set(spec.get("owners") or []) and _s(call.get("name")) in set(spec.get("names") or []))


def persistence_translations(method: dict[str, Any], catalog: dict[str, Any]) -> list[dict[str, str]]:
    """compat-mapping persistence_behaviour_translations rows whose ordered
    call condition the source method meets (a pre-order call list from the
    frozen structural model)."""
    rows = ((catalog or {}).get("persistence_behaviour_translations") or {})
    calls = [c for c in method.get("calls") or [] if isinstance(c, dict)]
    out = []
    for rid_ in sorted(k for k in rows if k != "note" and isinstance(rows[k], dict)):
        row = rows[rid_]
        when = row.get("when") or {}
        first = next((i for i, c in enumerate(calls) if _calls_match(when.get("first") or {}, c)), None)
        if first is None:
            continue
        later = [c for c in calls[first + 1:] if _calls_match(when.get("then_any") or {}, c)]
        if later:
            out.append({"id": rid_, "obligation": _s(row.get("obligation")), "evidence": _s(row.get("evidence")),
                        "source": _s(row.get("source")),
                        "calls": ["%s.%s" % (_s(c.get("owner")).rsplit(".", 1)[-1], _s(c.get("name")))
                                  for c in [calls[first]] + later[:3]]})
    return out


def repository_behaviour(types: list[dict[str, Any]], *, parent: str, members: list[str], decisions: dict[str, Any] | None,
                         catalog: dict[str, Any]) -> dict[str, Any]:
    """Where each owed member of fragment parent `parent` gets its behaviour
    in the SOURCE, under the decided build profiles (V17-3). Pure.

    {"parent", "repository", "members": [{signature, kind, source, path, ...}],
     "not_behaviour_sources": [{type, path, profiles, why}], "unknowns"}

    kind: source-override (a custom fragment implementation the selected
    repository extends), query (@Query on the selected repository),
    crud-default (the base repository method the name and arity select),
    derived-query (a query derived from the method name), unresolved."""
    by_fqn = {_s(t.get("fqn")): t for t in types or [] if isinstance(t, dict) and _s(t.get("fqn"))}
    sem = (catalog or {}).get("repository_behaviour") or {}
    q_anns = set(sem.get("query_annotations") or [])
    mod_anns = set(sem.get("modifying_annotations") or [])
    crud = {k: v for k, v in (sem.get("crud_defaults") or {}).items() if isinstance(v, dict)}
    prefixes = [str(p) for p in sem.get("derived_query_prefixes") or []]
    bp = (decisions or {}).get("build_profiles")
    active = [str(p) for p in (bp.get("active") or [])] if isinstance(bp, dict) and bp.get("active") else None
    retired = {_s(r.get("path")): _s(r.get("adr")) for r in ((decisions or {}).get("retired_sources") or []) if isinstance(r, dict)}
    out: dict[str, Any] = {"parent": parent, "repository": "", "members": [], "not_behaviour_sources": [], "unknowns": []}
    # implementations of the parent the decided profiles do NOT select: never the behaviour source
    for t in sorted(by_fqn.values(), key=lambda x: _s(x.get("fqn"))):
        if _s(t.get("kind")) in ("class", "record") and parent in (t.get("supertypes") or []) and _selected(t, active) is False:
            why = "gated by @Profile(%s), which the decided build profiles (%s) do not select" % (
                ",".join(_profiles_of(t)), ",".join(active or []))
            if retired.get(_s(t.get("path"))):
                why += "; retired by %s" % retired[_s(t.get("path"))]
            out["not_behaviour_sources"].append({"type": _s(t.get("fqn")), "path": _s(t.get("path")),
                                                 "profiles": _profiles_of(t), "why": why})
    repos = [t for t in by_fqn.values() if _s(t.get("kind")) == "interface" and parent in (t.get("supertypes") or [])
             and set(t.get("supertypes") or []) & set(REPOSITORY_SUPERTYPES)]
    sel = [t for t in repos if _selected(t, active) is True]
    undecided = [t for t in repos if _selected(t, active) is None]
    if undecided and not sel:
        out["unknowns"].append("the Spring Data repositories extending %s are profile-gated and no build profile is decided" % parent)
    elif len(sel) != 1:
        out["unknowns"].append("%d Spring Data repositories extending %s in the decided profiles: the behaviour source is %s"
                               % (len(sel), parent, "absent" if not sel else "ambiguous"))
    repo = sel[0] if len(sel) == 1 else None
    overrides: list[tuple[dict[str, Any], dict[str, Any]]] = []  # (override impl, override interface)
    if repo is not None:
        out["repository"] = _s(repo.get("fqn"))
        for f in sorted(str(s) for s in repo.get("supertypes") or []):
            ft = by_fqn.get(f)
            if f == parent or f in REPOSITORY_SUPERTYPES or ft is None or _s(ft.get("kind")) != "interface":
                continue
            for impl in sorted(by_fqn.values(), key=lambda x: _s(x.get("fqn"))):
                if _s(impl.get("kind")) in ("class", "record") and f in (impl.get("supertypes") or []) and _selected(impl, active) is True:
                    overrides.append((impl, ft))
    for sig in sorted(set(members)):
        row: dict[str, Any] = {"signature": sig, "kind": "unresolved", "source": "", "path": ""}
        name = sig.split("(", 1)[0]
        if repo is None:
            row["why"] = out["unknowns"][0] if out["unknowns"] else "no selected repository"
            out["members"].append(row)
            continue
        hit = next(((impl, m) for impl, _ft in overrides
                    for m in [_match([x for x in impl.get("methods") or [] if isinstance(x, dict)], sig)] if m is not None), None)
        declared = _match([x for x in repo.get("methods") or [] if isinstance(x, dict)], sig)
        if hit is not None:
            impl, m = hit
            row.update(kind="source-override", source="%s#%s" % (_s(impl.get("fqn")), _s(m.get("signature"))),
                       path=_s(impl.get("path")), translations=persistence_translations(m, catalog),
                       why="a custom implementation fragment of the selected repository: Spring Data calls it ahead of the "
                           "base repository and query derivation; port its BEHAVIOUR")
        elif declared is not None and set(_ann(declared.get("annotations"))) & q_anns:
            qs = [v for a in sorted(q_anns) for v in _ann_values(declared.get("annotations"), a)]
            row.update(kind="query", source="%s#%s" % (_s(repo.get("fqn")), _s(declared.get("signature"))),
                       path=_s(repo.get("path")), query=qs, modifying=bool(set(_ann(declared.get("annotations"))) & mod_anns),
                       why="the selected repository declares this @Query; run exactly that query")
        elif "%s/%d" % (name, _arity(sig)) in crud:
            c = crud["%s/%d" % (name, _arity(sig))]
            row.update(kind="crud-default", source="%s (Spring Data base repository)" % "%s/%d" % (name, _arity(sig)),
                       path=_s(repo.get("path")), effect=_s(c.get("kind")), semantics=_s(c.get("semantics")),
                       why="no override and no @Query: the base repository method the name and arity select")
        elif any(name.startswith(p) and ("By" in name[len(p):] or name == p) for p in prefixes):
            row.update(kind="derived-query", source="%s#%s (derived from the method name)" % (_s(repo.get("fqn")), sig),
                       path=_s(repo.get("path")), why="a query Spring Data derives from the method name")
        else:
            row["why"] = "no override, @Query, CRUD method or derivable name answers %s in %s" % (sig, _s(repo.get("fqn")))
        if row["kind"] == "source-override":
            wc = sem.get("write_calls") or {}
            row["effect"] = "write" if any(_calls_match(wc, c) for c in (hit[1].get("calls") or []) if isinstance(c, dict)) else "read"
        elif row["kind"] == "query":
            row["effect"] = "write" if row.get("modifying") else "read"
        elif row["kind"] == "derived-query":
            row["effect"] = "write" if name.startswith(("delete", "remove")) else "read"
        out["members"].append(row)
    if any(r["kind"] == "unresolved" for r in out["members"]):
        out["unknowns"].append("members with no selected source behaviour: %s"
                               % ", ".join(r["signature"] for r in out["members"] if r["kind"] == "unresolved"))
    return out


def repository_verification(behaviour: dict[str, Any], *, entry_points: list[dict[str, Any]], types: list[dict[str, Any]],
                            oracles: dict[str, list[str]] | None,
                            scenarios: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The functional verification one owed fragment implementation needs
    (V17-3): per owed member, a READ is proven by a scenario that reads through
    it, a WRITE by a committed effect read back across a request boundary
    (create -> independent read, update -> read, delete -> read proving the
    removal and the related records). The entry points that reach the member
    are found through the frozen call graph (handler -> ... -> the repository
    member, by the calls the structural model records); their captured
    scenarios are the coverage. A member no captured scenario reaches is
    UNRESOLVED -- the responsibility stays open, the expected response is
    never invented. Pure."""
    by_fqn = {_s(t.get("fqn")): t for t in types or [] if isinstance(t, dict)}
    parent = _s(behaviour.get("parent"))
    names_of_parent = {parent, _s(behaviour.get("repository"))}
    # who calls a member of the parent, transitively: type#method -> callers
    callers: dict[str, set[str]] = {}
    field_types: dict[str, dict[str, str]] = {}
    for t in by_fqn.values():
        field_types[_s(t.get("fqn"))] = {_s(f.get("name")): _s(f.get("type")) for f in t.get("fields") or [] if isinstance(f, dict)}
    for t in by_fqn.values():
        for m in t.get("methods") or []:
            if not isinstance(m, dict):
                continue
            me = "%s#%s" % (_s(t.get("fqn")), _s(m.get("name")))
            for c in m.get("calls") or []:
                if isinstance(c, dict) and _s(c.get("owner")) and _s(c.get("name")):
                    callers.setdefault("%s#%s" % (_s(c.get("owner")), _s(c.get("name"))), set()).add(me)
    # an interface call resolves to its implementations too (service interfaces)
    ep_by_member = {"%s#%s" % (_s(e.get("type")), _s(e.get("member")).split("(", 1)[0]): _s(e.get("id"))
                    for e in entry_points or [] if isinstance(e, dict)}
    out = []
    for row in behaviour.get("members") or []:
        name = _s(row.get("signature")).split("(", 1)[0]
        frontier = ["%s#%s" % (p, name) for p in names_of_parent if p]
        seen: set[str] = set(frontier)
        reach: set[str] = set()
        while frontier:
            cur = frontier.pop()
            if cur in ep_by_member:
                reach.add(ep_by_member[cur])
            owner, meth = cur.split("#", 1)
            keys = {cur} | {"%s#%s" % (sup, meth) for t in [by_fqn.get(owner) or {}] for sup in t.get("supertypes") or []}
            for k in sorted(keys):
                for caller in sorted(callers.get(k, set())):
                    if caller not in seen:
                        seen.add(caller)
                        frontier.append(caller)
        effect = _s(row.get("effect")) or "read"
        scen_all = sorted({s for ep in reach for s in (oracles or {}).get(ep) or []})
        unknown_facts = [x for x in scen_all if scenarios is None or x not in scenarios]
        if effect == "write":
            # a write is proven only by a scenario that WRITES and then reads
            # the committed effect back in another request (corpus `effects`)
            scen = sorted(x for x in scen_all if scenarios is not None and x in scenarios
                          and _s((scenarios[x] or {}).get("method")).upper() not in ("", "GET", "HEAD", "OPTIONS")
                          and (scenarios[x] or {}).get("effects"))
        else:
            scen = scen_all
        need = ("a committed effect read back across a request boundary: the write, then an independent read that "
                "proves it (create -> read, update -> read, delete -> read proving the removal and the related records)"
                if effect == "write" else "a read through the generated repository returning the source's records")
        out.append({"member": "%s#%s" % (parent, _s(row.get("signature"))), "effect": effect, "behaviour": _s(row.get("kind")),
                    "entry_points": sorted(reach), "scenarios": scen, "needs": need,
                    "status": APPLICABLE if scen else UNRESOLVED,
                    "unknowns": ([] if scen else ["no captured scenario reaches %s through %s%s: %s coverage is unresolved "
                                                  "(never invented)" % (row.get("signature"), parent,
                                                                        " with a committed read-back" if effect == "write" else "",
                                                                        effect)])
                    + (["scenario facts unreadable for %s: whether it proves the effect is unknown" % ", ".join(unknown_facts[:3])]
                       if (effect == "write" and unknown_facts) else [])})
    return out


# ---------------------------------------------------------------------------
# application paths (round 3)
# ---------------------------------------------------------------------------

def _norm_path(v: str) -> str:
    """A context/root path as both platforms resolve it: leading slash, no
    trailing slash except the root itself."""
    t = "/" + str(v or "").strip().strip("/")
    return "/" if t == "/" else t


def effective_source_properties(files: dict[str, dict[str, str]]) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """(effective key -> value, key -> the file it came from, the active
    profiles) of a Spring Boot source: application.properties, then each
    application-<profile>.properties the source itself activates
    (spring.profiles.active), in order, the later overriding."""
    base = dict(files.get("application.properties") or {})
    active = [x.strip() for x in str(base.get("spring.profiles.active") or "").split(",") if x.strip()]
    eff, came = dict(base), {k: "application.properties" for k in base}
    for prof in active:
        name = "application-%s.properties" % prof
        for k, v in (files.get(name) or {}).items():
            eff[k], came[k] = v, name
    return eff, came, active


def application_paths(source_config: dict[str, Any] | None, catalog: dict[str, Any],
                      decisions: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The application path requirements: every key of compat-mapping
    `application_paths` the frozen source configures (its effective value,
    under the profiles it activates itself) is owed on the destination key the
    row names, with that value -- or the value decisions.yaml
    `application_paths.values` records under an ACCEPTED ADR. A source that
    configures none of them keeps the platform defaults on both sides:
    not-applicable. Unreadable configuration, or configuration the source also
    keeps in a format not read here (YAML), is unresolved."""
    rows = {str(k): v for k, v in ((catalog or {}).get("application_paths") or {}).items()
            if k != "note" and isinstance(v, dict) and v.get("dest")}
    if not rows:
        return []
    if source_config is None:
        return [_req("application-path", "*", UNRESOLVED, evidence=[], paths=["src/main/resources/application.properties"],
                     acceptance=[], unknowns=["the frozen source's configuration could not be read: its application paths are unknown"])]
    files = {str(k): dict(v) for k, v in (source_config.get("files") or {}).items() if isinstance(v, dict)}
    unread = sorted(str(x) for x in source_config.get("unread") or [])
    eff, came, active = effective_source_properties(files)
    dec = (decisions or {}).get("application_paths") if isinstance((decisions or {}).get("application_paths"), dict) else {}
    from planner.decisions import accepted_adrs
    decided = dict(dec.get("values") or {}) if dec and str(dec.get("adr") or "") in accepted_adrs(decisions or {}) else {}
    out = []
    for key in sorted(rows):
        if key not in eff:
            continue
        row = rows[key]
        dest = str(row["dest"])
        want = _norm_path(str(decided.get(dest) if dest in decided else eff[key]))
        out.append(_req("application-path", key, UNRESOLVED if unread else APPLICABLE,
                        evidence=[{"artifact": ".derived/frozen-input/src/main/resources/%s" % came[key], "selector": key}]
                        + ([{"artifact": "decisions.yaml", "selector": "application_paths.values.%s" % dest}] if dest in decided else []),
                        paths=["src/main/resources/application.properties"],
                        acceptance=["config:application-path"],
                        unknowns=(["the source also configures through %s, which is not read: its effective %s is unproven"
                                   % (", ".join(unread), key)] if unread else []),
                        facts={"source_key": key, "source_value": eff[key], "source_file": came[key],
                               "source_profiles": active, "dest_key": dest, "dest_value": want,
                               "decided": dest in decided, "source": str(row.get("source") or "")}))
    if not out:
        out.append(_req("application-path", "*", UNRESOLVED if unread else NOT_APPLICABLE, evidence=[], paths=[], acceptance=[],
                        unknowns=["the source also configures through %s, which is not read" % ", ".join(unread)] if unread else [],
                        facts={"reason": "the frozen source configures no application path; both platforms keep their default"}))
    return out


def source_configuration(root: Path, *, frozen_dir: Path | None = None) -> dict[str, Any] | None:
    """The frozen source's configuration files (.derived/frozen-input, or
    `frozen_dir`, src/main/resources/application*.properties), parsed as
    properties; None when the frozen input is absent."""
    from response_adapters import read_properties
    frozen = Path(frozen_dir) if frozen_dir is not None else Path(root) / ".derived" / "frozen-input"
    res = frozen / "src" / "main" / "resources"
    if not frozen.is_dir():
        return None
    files: dict[str, dict[str, str]] = {}
    unread: list[str] = []
    if res.is_dir():
        for f in sorted(res.iterdir()):
            if f.is_file() and f.name.startswith("application") and f.suffix == ".properties":
                files[f.name] = read_properties(f.read_text(encoding="utf-8", errors="replace"))
            elif f.is_file() and f.name.startswith("application") and f.suffix in (".yml", ".yaml"):
                unread.append(f.name)
    return {"files": files, "unread": unread}


# ---------------------------------------------------------------------------
# reading a destination root (I/O lives here, never in derive)
# ---------------------------------------------------------------------------

_READ_METHODS = ("GET", "HEAD", "OPTIONS")


def _unobservable_write(ep: dict[str, Any], scen: list[str], facts: dict[str, dict[str, Any]] | None) -> str:
    """Why a WRITE entry point's captured scenarios cannot verify the write;
    "" when they can, or when that is not decidable. Every write scenario of
    it declares no read-back (the derivation found no route that reads what
    it persists and said so in ``effects_unobservable``): the comparator
    refuses such a scenario at M4, so counting it as the entry point's oracle
    would make a capability that stays unknown disappear from the plan (M-1)."""
    if not scen or facts is None or _s(ep.get("http_method")).upper() in _READ_METHODS + ("",):
        return ""
    writes = [facts.get(s) for s in scen if _s((facts.get(s) or {}).get("method")).upper() not in _READ_METHODS]
    if not writes or any(w is None or w.get("effects") for w in writes):
        return ""
    reasons = sorted({_s(w.get("effects_unobservable")) for w in writes if _s(w.get("effects_unobservable"))})
    return "; ".join(reasons) or "no scenario declares an effect"


def _scenario_facts(root: Path) -> dict[str, dict[str, Any]] | None:
    from planner.worklist import corpus_scenario_facts
    return corpus_scenario_facts(root)[1]


def for_root(root: Path, *, oracles: dict[str, list[str]] | None = None) -> dict[str, Any]:
    from planner.decisions import load_decisions
    from planner.paths import BOOTSTRAP_RECEIPT, CATALOGS_DIR, DECIDED_REPAIRS_RECEIPT, EVIDENCE_BUNDLE

    root = Path(root)

    def read(p: Path) -> Any:
        try:
            return load_json(p)
        except (OSError, ValueError):
            return None

    bundle = read(root / EVIDENCE_BUNDLE)
    if not isinstance(bundle, dict):
        return {"schema": SCHEMA, "requirements": [], "unknowns": ["the evidence bundle is missing: source requirements are unknown"]}
    st = bundle.get("structure") or {}
    try:
        decisions = load_decisions(root)
    except (OSError, ValueError):
        decisions = None
    catalog = read(root / CATALOGS_DIR / "compat-mapping.json") or {}
    try:
        from planner.worklist import generator_plugin_config, static_generated_body_facts
        generator = generator_plugin_config(root) or None
        gen_known = True
        gen_facts = static_generated_body_facts(root, bundle) if generator else None
    except Exception:  # an unreadable build is unknown, not generator-free
        generator, gen_known, gen_facts = None, False, None
    dr = read(root / DECIDED_REPAIRS_RECEIPT)
    rows = list(dr.get("rows") or []) if isinstance(dr, dict) else []
    doc = derive(types=st.get("types") or [], entry_points=bundle.get("entry_points") or [], catalog=catalog,
                 decisions=decisions, oracles=oracles, structure_complete=bool(st.get("available")) and str(st.get("mode")) == "full",
                 generator=generator, generator_known=gen_known, decided_rows=rows, bootstrap=read(root / BOOTSTRAP_RECEIPT),
                 scenario_facts=_scenario_facts(root), generator_facts=gen_facts,
                 source_config=source_configuration(root))
    if decisions is None:
        doc["unknowns"] = sorted(set(doc["unknowns"]) | {"decisions.yaml missing or invalid: decided configuration is unknown"})
    return doc
