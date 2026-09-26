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
         "adapter-behavior", "generator-configuration", "configuration-decision", "behavior-verification")
# the outcome class a requirement's work belongs to (outcome_graph.CLASSES)
RULE_CLASS = {"repository-architecture": "source", "request-validation": "source", "handler-parameter-binding": "source",
              "annotation-retirement": "source", "adapter-behavior": "behavior", "generator-configuration": "build",
              "configuration-decision": "config", "behavior-verification": "behavior"}
APPLICABLE, NOT_APPLICABLE, UNRESOLVED, SATISFIED = "applicable", "not-applicable", "unresolved", "satisfied"


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


def _recipe_for(recipes: dict[str, dict[str, Any]], rule: str, key: str = "") -> dict[str, Any] | None:
    hits = sorted((rid_, r) for rid_, r in recipes.items() if r.get("rule") == rule and (not key or key in (r.get("applies_to") or [key])))
    if not hits:
        return None
    rid_, r = hits[0]
    return {"id": rid_, "version": str(r.get("version") or ""), "phase": str(r.get("phase") or "m3"),
            "implementation": str((r.get("implementation") or {}).get("kind") or "")}


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


# ---------------------------------------------------------------------------
# the derivation
# ---------------------------------------------------------------------------

def derive(*, types: list[dict[str, Any]], entry_points: list[dict[str, Any]], catalog: dict[str, Any],
           decisions: dict[str, Any] | None, oracles: dict[str, list[str]] | None, structure_complete: bool,
           generator: dict[str, Any] | None = None, generator_known: bool = True,
           decided_rows: list[dict[str, Any]] | None = None, bootstrap: dict[str, Any] | None = None) -> dict[str, Any]:
    """{"schema", "requirements": [...], "unknowns": [...]}. Pure."""
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
                out.append(_req("handler-parameter-binding", "%s|%s" % (subject, _s(p.get("name"))), APPLICABLE if rec else UNRESOLVED,
                                evidence=sel, paths=[_s(t.get("path"))], recipe=rec, consumers=[ep],
                                acceptance=["unit:handler-parameter-sites", "gate:package", "gate:augmentation"] + ["parity:%s" % s for s in scen],
                                unknowns=unk + ([] if rec else ["no qualified recipe for %s" % ptype]),
                                facts={"parameter": _s(p.get("name")), "parameter_type": ptype,
                                       "precedes": ["symbol_renames:%s" % ptype]}))
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
    repos = [t for t in types if _s(t.get("kind")) == "interface" and set(t.get("supertypes") or []) & set(REPOSITORY_SUPERTYPES)]
    impls_of: dict[str, list[dict[str, Any]]] = {}
    for t in types:
        if _s(t.get("kind")) in ("class", "record"):
            for st in t.get("supertypes") or []:
                impls_of.setdefault(str(st), []).append(t)
    active = [str(p) for p in ((decisions.get("build_profiles") or {}).get("active") or [])] if isinstance(decisions.get("build_profiles"), dict) else []
    frags = 0
    for r in repos:
        for f in sorted(str(s) for s in r.get("supertypes") or []):
            if f in REPOSITORY_SUPERTYPES or f not in by_fqn or _s(by_fqn[f].get("kind")) != "interface":
                continue
            frags += 1
            ft = by_fqn[f]
            impls = sorted(impls_of.get(f, []), key=lambda x: x["fqn"])
            named = [i for i in impls if i["fqn"] == f + FRAGMENT_SUFFIX]
            profiled = {i["fqn"]: _ann_values(i.get("annotations"), PROFILE_ANNOTATION) for i in impls}
            selected = [i for i in impls if not profiled[i["fqn"]] or set(profiled[i["fqn"]]) & set(active)]
            unk: list[str] = []
            status = APPLICABLE
            if not named:
                status, unk = UNRESOLVED, ["no %s%s implements fragment %s in the source (the naming contract Spring Data resolves by)" % (f.rsplit(".", 1)[-1], FRAGMENT_SUFFIX, f)]
            elif len(selected) != 1 and any(profiled.values()) and not active:
                status, unk = UNRESOLVED, ["fragment %s has %d profile-gated implementations and no decided build profile" % (f, len(impls))]
            elif len(selected) > 1:
                status, unk = UNRESOLVED, ["fragment %s has %d implementations in the selected profile: the intended injectable one is ambiguous" % (f, len(selected))]
            members = sorted(_s(m.get("signature")) for m in ft.get("methods") or [] if isinstance(m, dict))
            rec = _recipe_for(recipes, "repository-architecture")
            out.append(_req("repository-architecture", "%s<-%s" % (r["fqn"], f), status if rec else UNRESOLVED,
                            evidence=[_sel("structure", "types[%s]" % r["fqn"], "supertypes"), _sel("structure", "types[%s]" % f, "methods")]
                            + [_sel("structure", "types[%s]" % i["fqn"], "supertypes") for i in impls],
                            paths=[_s(x.get("path")) for x in [r, ft] + (named or [])], recipe=rec,
                            acceptance=["unit:fragment-implementation", "structure:single-injectable-implementation", "gate:package", "gate:startup"],
                            unknowns=unk + ([] if rec else ["no qualified repository recipe"]),
                            facts={"repository": r["fqn"], "fragment": f, "members": members,
                                   "implementations": [i["fqn"] for i in impls], "selected": [i["fqn"] for i in selected],
                                   "profiles": {k: sorted(v) for k, v in profiled.items() if v}, "decided_profiles": active}))
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
        out.append(_req("generator-configuration", "%s|%s" % (ga, gname), APPLICABLE if (qualified and rec) else UNRESOLVED,
                        evidence=[{"artifact": "pom.xml", "selector": "build.plugins[%s].configuration" % ga}],
                        paths=["pom.xml"], recipe=rec, consumers=consumers,
                        acceptance=["build:clean-generation", "parity:request-body-positive-negative"],
                        unknowns=unk, facts={"plugin_version": _s(generator.get("version")), "generator": gname,
                                             "model_package": generated_pkg, "options": dict(generator.get("configOptions") or {})}))
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
                        paths=["src/main/resources/application.properties"] if key != "build_profiles" else ["pom.xml", "src/main/resources/application.properties"],
                        acceptance=["config:decided-keys", "gate:startup"],
                        facts={"adr": _s(fact.get("adr")), "applied_by_bootstrap": bs_ok and key != "security"}))

    # -- behaviour verification of every entry point -----------------------
    for e in eps:
        scen = sorted(set((oracles or {}).get(e["id"]) or []))
        out.append(_req("behavior-verification", e["id"], APPLICABLE if scen else UNRESOLVED,
                        evidence=[_sel("entry_points[%s]" % e["id"])], paths=[], consumers=[e["id"]],
                        acceptance=["parity:%s" % s for s in scen] or ["coverage:unresolved"],
                        unknowns=[] if scen else ["no captured oracle for %s (%s): behaviour is unverified, never PASS" % (e["id"], _s(e.get("kind")))],
                        facts={"kind": _s(e.get("kind")), "type": _s(e.get("type"))}))
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
# reading a destination root (I/O lives here, never in derive)
# ---------------------------------------------------------------------------

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
        from planner.worklist import generator_plugin_config
        generator = generator_plugin_config(root) or None
        gen_known = True
    except Exception:  # an unreadable build is unknown, not generator-free
        generator, gen_known = None, False
    dr = read(root / DECIDED_REPAIRS_RECEIPT)
    rows = list(dr.get("rows") or []) if isinstance(dr, dict) else []
    doc = derive(types=st.get("types") or [], entry_points=bundle.get("entry_points") or [], catalog=catalog,
                 decisions=decisions, oracles=oracles, structure_complete=bool(st.get("available")) and str(st.get("mode")) == "full",
                 generator=generator, generator_known=gen_known, decided_rows=rows, bootstrap=read(root / BOOTSTRAP_RECEIPT))
    if decisions is None:
        doc["unknowns"] = sorted(set(doc["unknowns"]) | {"decisions.yaml missing or invalid: decided configuration is unknown"})
    return doc
