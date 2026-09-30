"""Compatibility objectives: the initial M3 graph composed by repair objective
(policy compatibility-objectives/v1, decisions.loop.compatibility_objectives).

Pure: no I/O, no clock, no model. Input is the revision the current policy
derives from the SAME admission evidence (outcome_graph.derive_initial_graph
without objectives -- one outcome per admitted unit, first-path requirement
attachment); output is the revision the native graph publishes instead. The
baseline is the budget and conservation control, never a second task graph.

A compatibility objective is one named change to an application contract with
the coordinated edits and checks it needs (catalogs/compat-mapping.json
objective_families). Units of one family that share a site compose into ONE
bounded executable scope (``execution_unit``), issued whole; independent
components stay separate; a unit no family names stays its own objective. A
requirement is owned by the objective of its rule's family and semantic
subject, never by a card that merely holds its files. Checks are planned per
(requirement, check): IMMEDIATE ones carry their prerequisite owners as hard
parents; LATER ones (package/boot/parity) are linked to where they are due and
never count as passed at a structural checkpoint. Budgets are conserved: each
connected set of baseline accounts and new objectives is one family whose limit
is the sum of its baseline accounts, counted once.

Check schedule (``check-schedule/v1``, schedule_checks; migration roadmap M-2)
is a derived view over the composed graph, never a second graph: it adds no
parent, moves no owner, splits nothing and changes no budget. Each check-plan
row states its kind (``stage``: immediate = judged at this card; later =
functional debt this outcome owns), its owner, its verification prerequisites
(``requires``: the files it reads compile, a packaged/started application, a
working database, a mode receipt, and the named causal repairs), the earliest
useful measurement point (``earliest``: a roadmap milestone and the outcomes,
first package or M4 where it can first be measured), for a repository contract
the focused M-3 qualification that covers it before any package exists, and,
for a comparison that depends on a known server-error producer, the producer's
check it comes ``after``. Implementation dependencies (``dependency_kinds``)
are reported apart from verification prerequisites. A repository objective
records both states (``acceptance_states``): structurally accepted at its card,
behaviour owed at its measurement points. A shared producer lists every path it
affects (``causal_scope``): each is remeasured; one path's pass is not evidence
for another. What cannot be scheduled -- an immediate check with no producer or
with a prerequisite no parent provides, a later check due before its owner or
its causal repair (a cycle deferred to M4), a behaviour whose only route is an
edit outside every planned scope -- is a typed finding, never a silent deferral.

A runtime (package/startup gate) finding whose locus and cause a planned
requirement's recipe declares it owns (migration_recipes <id>.runtime_findings)
is that requirement owner's obligation inside its existing scope, with the
runtime account joining the owner's budget family
(absorb_recipe_runtime_findings); as a separate runtime outcome it would both
wait on and block that owner.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

POLICY = "compatibility-objectives/v1"
# the same prefixes native_control.RUNTIME_CHECK_PREFIXES defers (asserted equal in the test)
LATER_CHECK_PREFIXES = ("parity:", "behavior:", "gate:package", "gate:augmentation", "gate:startup")
MAX_FILES, MAX_SITES, MAX_SYMBOLS, MAX_FRAGMENT_SYMBOLS = 20, 160, 8, 16
PARITY_GENERATED_BODY = "PARITY_GENERATED_BODY"
# check -> what its prerequisite set is read from (the first explicit table;
# design §7.2). "files": owners of obligations still open in the
# requirement's files; "none": the check reads parsed sites only.
CHECK_READS = {
    "gate:compile": "files",
    "unit:fragment-implementation": "files", "unit:fragment-behaviour-bodies": "files",
    "structure:single-injectable-implementation": "files",
    "unit:handler-validation-guards": "files", "unit:handler-parameter-sites": "files",
    "unit:location-null-arguments": "files",
    "structure:annotation-absent": "none",
}
# check-schedule/v1: the roadmap M-2 milestones, in order (a derived view of the
# graph's own owners and checks, never five mega-cards)
CHECK_SCHEDULE = "check-schedule/v1"
MILESTONES = ("source-understood", "target-structurally-viable", "persistence-and-one-http-path",
              "application-behavior-preserved", "delivered-and-usable")
MILESTONE_TITLES = {
    "source-understood": "Source understood (builds on its toolchain; profiles, generated types and captures qualified)",
    "target-structurally-viable": "Target structurally viable (transitions applied; compilation and augmentation succeed)",
    "persistence-and-one-http-path": "Persistence and one HTTP path work (repository reads/writes through the real database)",
    "application-behavior-preserved": "Application behavior preserved (remaining paths, validation, Location, CORS, security modes)",
    "delivered-and-usable": "Delivered and usable (M4 results, M5 pipeline, deployment and live tests)",
}
# verification prerequisites (``requires``); "compiled:<o>" and "repair:<o>" name an outcome
APP_PACKAGED, APP_STARTED, DB_WORKING = "application:packaged", "application:started", "database:working"
RUNTIME_REQUIRES = (APP_PACKAGED, APP_STARTED, DB_WORKING)
# measurement points (``earliest.at``) besides outcome ids
FIRST_PACKAGE = "first-package"
POINTS = {
    FIRST_PACKAGE: "the first candidate measured after every build, configuration and source outcome is accepted: "
                   "the whole application must build first, so this is the first behavior issue",
    "<outcome id>": "that outcome's issue and acceptance measurement",
    "<assess id>": "the M4 assessment (the backstop every later check is also deferred to)",
}
# the focused M-3 component qualification of a repository contract (read/write
# effects through a fresh transaction, recursion and no-op negatives): usable
# while unrelated sources still prevent a whole-application build
QUALIFY_REPOSITORY = "qualify:repository-contract:%s"
# derive-source-scenarios names its cross-origin and security scenarios with
# these prefixes (sc:cors-actual-*, sc:cors-preflight-*, sc:auth-<kind>-*): the
# harness's own scenario contract, not a specimen spelling
MODE_SCENARIO_PREFIXES = ("sc:cors-", "sc:auth-")
REQUEST_BODY_CHECK = "parity:request-body-positive-negative"
REMEASURE_RULE = ("every affected path is remeasured after the shared repair; a passing path is evidence for "
                  "itself only, never for another endpoint the same producer serves")


class ObjectiveError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def _s(v: Any) -> str:
    return v if isinstance(v, str) else ""


def _h(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:12]


def families(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The versioned objective families; a requested policy with missing or
    malformed metadata refuses (no silent fallback)."""
    block = (catalog or {}).get("objective_families")
    if not isinstance(block, dict) or str(block.get("version") or "") != "1" or not isinstance(block.get("families"), dict):
        raise ObjectiveError("OBJECTIVES_CATALOG", "compat-mapping.json objective_families v1 is missing or malformed")
    out: dict[str, dict[str, Any]] = {}
    for fid, row in block["families"].items():
        if not isinstance(row, dict) or not _s(row.get("title")):
            raise ObjectiveError("OBJECTIVES_CATALOG", "family %r has no title" % fid)
        out[str(fid)] = row
    return out


def _symbol_index(fams: dict[str, dict[str, Any]]) -> dict[str, tuple[str, str]]:
    """qualified symbol -> (family, transformation id)."""
    idx: dict[str, tuple[str, str]] = {}
    for fid, row in fams.items():
        for t in row.get("transformations") or []:
            for sym in t.get("symbols") or []:
                if sym in idx and idx[sym][0] != fid:
                    raise ObjectiveError("OBJECTIVES_CATALOG", "%s is in families %s and %s" % (sym, idx[sym][0], fid))
                idx[str(sym)] = (fid, str(t.get("id")))
    return idx


def qualify_symbol(sym: str, kind: str, member_types: list[str], structure: dict[str, dict[str, Any]]) -> str:
    """A sealed symbol that is not qualified (a wildcard import the destination
    cannot resolve) is qualified ONLY through the frozen model: the sealed
    members' own types must declare exactly one qualified identity of that
    simple name (annotation or reference). Otherwise ''."""
    if "." in sym:
        return sym
    hits: set[str] = set()
    for fqn in member_types:
        t = structure.get(fqn) or {}
        names = [_s(a.get("fqn")) for a in t.get("annotations") or [] if isinstance(a, dict)] + [_s(r) for r in t.get("type_refs") or []]
        for m in (t.get("methods") or []) + (t.get("fields") or []):
            names += [_s(a.get("fqn")) for a in m.get("annotations") or [] if isinstance(a, dict)]
        hits |= {n for n in names if n.rsplit(".", 1)[-1] == sym and "." in n}
    return next(iter(hits)) if len(hits) == 1 else ""


def _atoms(worklist: dict[str, Any], baseline: dict[str, Any], seals: dict[str, dict[str, Any]],
           item_symbols: dict[str, str], structure: dict[str, dict[str, Any]], idx: dict[str, tuple[str, str]],
           fams: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """cluster id -> its family decision, sites and baseline owner."""
    items = {_s(i.get("id")): i for i in worklist.get("items") or [] if isinstance(i, dict)}
    rule_fam = {r: fid for fid, row in fams.items() for r in row.get("rules") or []}
    owner = {c: n["outcome_id"] for n in baseline["nodes"] if n.get("role") == "repair" for c in n.get("clusters") or []}
    out: dict[str, dict[str, Any]] = {}
    for c in worklist.get("clusters") or []:
        cid = _s(c.get("id"))
        node = next((n for n in baseline["nodes"] if n["outcome_id"] == owner.get(cid)), None)
        if node is None or node["class"] not in ("build", "config", "source"):
            continue
        members = [items[m] for m in c.get("items") or [] if m in items]
        seal = seals.get(cid) or {}
        syms: list[tuple[str, str]] = []
        unknown: list[str] = []
        if seal:
            types = sorted({_s(m.get("type")) for m in seal.get("members") or [] if _s(m.get("type"))})
            for s in seal.get("symbols") or []:
                q = qualify_symbol(_s(s.get("fqn")), _s(s.get("kind")), types, structure)
                (syms.append((q, _s(s.get("kind")))) if q else unknown.append(_s(s.get("fqn"))))
            sites = set(seal_site_keys(seal))
            member_types = types
        else:
            for m in members:
                q = item_symbols.get(_s(m.get("id")), "")
                if q:
                    syms.append((q, "resolved"))
                elif _s(m.get("kind")) == "compile":
                    unknown.append(_s(m.get("id")))
            sites = {"i|%s" % _s(m.get("id")) for m in members}
            member_types = []
        rules = sorted({_s(m.get("rule_id")) for m in members if _s(m.get("kind")) in ("config", "incident", "build")})
        fam_hits = {idx[q][0] for q, _k in syms if q in idx} | {rule_fam[r] for r in rules if r in rule_fam}
        family, why = "", ""
        if len(fam_hits) == 1 and not unknown and all(q in idx for q, _k in syms) and all(r in rule_fam for r in rules):
            family = next(iter(fam_hits))
        elif len(fam_hits) > 1:
            why = "the unit names symbols of %d families (%s)" % (len(fam_hits), ", ".join(sorted(fam_hits)))
        elif unknown:
            why = "unqualified or unresolved symbol(s) %s: absence of attribution is not a family" % ", ".join(unknown[:3])
        else:
            why = "no objective family names its symbols or rules"
        out[cid] = {"cluster": cid, "baseline_owner": node["outcome_id"], "class": node["class"], "family": family,
                    "fallback_reason": why, "files": sorted(set(c.get("write_set") or [])), "sites": sites,
                    "writable": sorted(set(c.get("write_set") or []) | {_s(p) for p in seal.get("writable_paths") or []}),
                    "fragment": fragment_seal(seal),
                    "transformations": sorted({idx[q][1] for q, _k in syms if q in idx} | {"rule:%s" % r for r in rules}),
                    "symbols": sorted({q for q, _k in syms}), "rules": rules, "member_types": member_types,
                    "items": list(c.get("items") or []), "order": c.get("order_key"),
                    "seal": ({"path": _s((c.get("batch_scope") or {}).get("path")), "digest": _s((c.get("batch_scope") or {}).get("digest")),
                              "rule": _s(seal.get("rule"))} if seal else {})}
    return out


def _components(atoms: list[dict[str, Any]], by_rule: bool) -> list[list[dict[str, Any]]]:
    left = sorted(atoms, key=lambda a: a["cluster"])
    out = []
    while left:
        comp = [left.pop(0)]
        grew = True
        while grew:
            grew = False
            for a in list(left):
                link = (set(a["rules"]) & {r for x in comp for r in x["rules"]}) if by_rule else \
                    (set(a["files"]) & {f for x in comp for f in x["files"]})
                if link:
                    comp.append(a)
                    left.remove(a)
                    grew = True
        out.append(sorted(comp, key=lambda a: a["cluster"]))
    return out


def seal_site_keys(seal: dict[str, Any]) -> list[str]:
    """A sealed unit's sites, one identity per member (the unit former's own
    site count: worklist._unit_size counts members)."""
    return sorted({"m|%s|%s|%s|%d|%s" % (_s(m.get("path")), _s(m.get("type")), _s(m.get("member_id")),
                                         int(m.get("occurrence") or 0), _s(m.get("identity")))
                   for m in seal.get("members") or [] if isinstance(m, dict)})


def fragment_seal(seal: dict[str, Any]) -> bool:
    """The unit former qualified this sealed unit for the fragment-set symbol
    limit (worklist._bound_unit records max_symbols); nothing else does."""
    return int(((seal or {}).get("bounds") or {}).get("max_symbols") or 0) == MAX_FRAGMENT_SYMBOLS


def scope_bounds(*, files, sites, symbols, fragment: bool) -> dict[str, Any]:
    """THE bound of an objective scope, over its FINAL canonical envelope and
    in the unit former's own units (worklist._unit_size): files = every
    writable path, sites = distinct sealed member (or unsealed item)
    identities, symbols = distinct source symbol identities -- never
    transformation names. The fragment limit applies only when every
    constituent's own seal qualified for it. Derivation (compose) and
    consumption (worklist.build_objective_scope, before any path is granted)
    both call this; a stored `within` is never trusted."""
    def n(x) -> int:
        return x if isinstance(x, int) else len(set(x))
    lim = {"files": MAX_FILES, "sites": MAX_SITES, "symbols": MAX_FRAGMENT_SYMBOLS if fragment else MAX_SYMBOLS}
    b = {"files": n(files), "sites": n(sites), "symbols": n(symbols), "limits": lim}
    b["within"] = b["files"] <= lim["files"] and b["sites"] <= lim["sites"] and b["symbols"] <= lim["symbols"]
    return b


def _bounds(comp: list[dict[str, Any]], extra_files=()) -> dict[str, Any]:
    return scope_bounds(files={f for a in comp for f in a["writable"]} | set(extra_files),
                        sites={x for a in comp for x in a["sites"]},
                        symbols={q for a in comp for q in a["symbols"]},
                        fragment=bool(comp) and all(a["fragment"] for a in comp))


def _oversize(what: str, comp: list[dict[str, Any]], bounds: dict[str, Any], baseline_nodes: dict[str, dict[str, Any]],
              requirements=()) -> str:
    owners = sorted({a["baseline_owner"] for a in comp})
    obligations = sum(len(baseline_nodes[o].get("obligations") or []) for o in owners)
    accounts = sorted({_s((baseline_nodes[o].get("budget") or {}).get("key")) or o for o in owners})
    return ("%s: %s exceeds the scope bound (%s) and no independent subcontract is proven; nothing is split or "
            "issued. Accounted: clusters %s, %d obligation(s), requirements %s, budget accounts %s"
            % (what, ", ".join(a["cluster"] for a in comp),
               ", ".join("%s %d/%d" % (k, bounds[k], bounds["limits"][k]) for k in ("files", "sites", "symbols")),
               ", ".join(a["cluster"] for a in comp), obligations, sorted(requirements) or "none", accounts))


def _subject_type(r: dict[str, Any]) -> str:
    rule = _s(r.get("rule")).split("/", 1)[0]
    subj = _s(r.get("subject"))
    if rule == "annotation-retirement":
        return subj.split("@", 1)[0]
    if rule in ("request-validation", "handler-parameter-binding"):
        return subj.split("#", 1)[0]
    return ""


def compose(*, baseline: dict[str, Any], worklist: dict[str, Any], requirements: list[dict[str, Any]] | None,
            catalog: dict[str, Any], seals: dict[str, dict[str, Any]] | None, item_symbols: dict[str, str] | None,
            structure_types: list[dict[str, Any]] | None, run_id: str) -> dict[str, Any]:
    """The objective revision for this run, or ObjectiveError / a PlanError
    from the caller's validation. ``baseline`` is the current policy's revision
    1 on the same inputs (its digest excluded)."""
    from planner.outcome_graph import CHECKS, CONTROL_M2, IMPL, REPAIR_SKILL, REPAIR_SKILLS, PlanError, _acyclic, _title, render_description

    fams = families(catalog)
    idx = _symbol_index(fams)
    structure = {_s(t.get("fqn")): t for t in structure_types or [] if isinstance(t, dict)}
    base = copy.deepcopy(baseline)
    bnodes = {n["outcome_id"]: n for n in base["nodes"]}
    reqrows = {_s(r.get("id")): r for r in requirements or [] if isinstance(r, dict)}
    items = {_s(i.get("id")): i for i in worklist.get("items") or [] if isinstance(i, dict)}
    atoms = _atoms(worklist, base, seals or {}, item_symbols or {}, structure, idx, fams)

    # 1. objectives from atoms: family components within bounds, else one per atom
    objectives: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    by_fam: dict[str, list[dict[str, Any]]] = {}
    for a in atoms.values():
        by_fam.setdefault(a["family"], []).append(a)
    for fam in sorted(by_fam):
        group = by_fam[fam]
        comps = [[a] for a in sorted(group, key=lambda a: a["cluster"])] if not fam else \
            _components(group, by_rule=bool(fams[fam].get("rules")))
        for comp in comps:
            b = _bounds(comp)
            if len(comp) > 1 and not b["within"]:
                # a connected component is ONE repair; splitting it by size alone would issue halves whose
                # independent acceptance nobody proved. A typed planning refusal, never a fallback.
                raise PlanError("COMPOSITION_OVERSIZE", _oversize("the %s component" % fam, comp, b, bnodes))
            objectives.append({"family": fam, "atoms": comp, "bounds": b, "requirements": [],
                               "fallback_reason": comp[0]["fallback_reason"] if not fam else ""})

    # 2. identities: a singleton keeps its baseline id; a composition hashes
    #    policy, family and constituent identities (never a display name)
    def oid_of(o: dict[str, Any]) -> str:
        if len(o["atoms"]) == 1:
            return o["atoms"][0]["baseline_owner"]
        return "objective:%s:%s" % (o["family"], _h(POLICY, o["family"], sorted(a["cluster"] for a in o["atoms"])))
    for o in objectives:
        o["id"] = oid_of(o)

    # 3. requirements: semantic subject, never the first file
    account: dict[str, str] = dict(base.get("requirement_ownership") or {})
    fam_of_rule = {r: fid for fid, row in fams.items() for r in row.get("requirement_rules") or []}
    req_objectives: dict[str, dict[str, Any]] = {}
    ownership_unresolved: list[dict[str, Any]] = []
    moved: dict[str, str] = {}
    for rq, r in sorted(reqrows.items()):
        owner0 = account.get(rq, "")
        if owner0 not in bnodes or bnodes[owner0].get("role") != "repair" or bnodes[owner0]["class"] == "behavior":
            continue  # satisfied / not-applicable / unresolved / behaviour / adapter: unchanged
        if owner0.startswith("requirement:") and _s(r.get("rule")).split("/", 1)[0] not in fam_of_rule:
            continue  # its own requirement outcome already (adapter, decided configuration): unchanged
        rule = _s(r.get("rule")).split("/", 1)[0]
        fam = fam_of_rule.get(rule, "")
        target = ""
        if fam == "selected-repository-implementation":
            subject = _s((r.get("facts") or {}).get("repository"))
            if not subject:
                ownership_unresolved.append({"requirement": rq, "reason": "no selected repository contract (facts.repository)"})
                continue
            key = "objective:%s:%s" % (fam, _h(POLICY, fam, subject))
            ro = req_objectives.setdefault(key, {"id": key, "family": fam, "subject": subject, "requirements": []})
            ro["requirements"].append(rq)
            target = key
        elif fam:
            subj_type = _subject_type(r)
            hits = sorted({o["id"] for o in objectives if o["family"] == fam
                           and subj_type and any(subj_type in a["member_types"] for a in o["atoms"])})
            if len(hits) == 1:
                target = hits[0]
                next(o for o in objectives if o["id"] == target)["requirements"].append(rq)
            elif len(hits) > 1:
                ownership_unresolved.append({"requirement": rq, "reason": "AMBIGUOUS_OWNER: %s" % ", ".join(hits)})
                continue
            else:
                # no composed objective transforms this subject: the family's
                # requirements of ONE semantic subject (the handler's declaring
                # type) are one objective -- never one card per requirement,
                # never the card that merely holds the file
                anchor = subj_type or _s(r.get("subject"))
                key = "objective:%s:%s" % (fam, _h(POLICY, fam, anchor))
                ro = req_objectives.setdefault(key, {"id": key, "family": fam, "subject": anchor, "requirements": []})
                ro["requirements"].append(rq)
                target = key
        elif rule == "generator-configuration":
            hits = sorted({o["id"] for o in objectives
                           if any(_s(items.get(i, {}).get("rule_id")) == PARITY_GENERATED_BODY for a in o["atoms"] for i in a["items"])})
            if len(hits) == 1:
                target = hits[0]
                next(o for o in objectives if o["id"] == target)["requirements"].append(rq)
        if not target:
            # no family and no semantic owner: its own requirement objective,
            # exactly as the current policy creates one when nothing owns it
            key = "requirement:%s:%s" % (rule, hashlib.sha256(_s(r.get("subject")).encode("utf-8")).hexdigest()[:12])
            ro = req_objectives.setdefault(key, {"id": key, "family": "", "subject": _s(r.get("subject")), "requirements": []})
            ro["requirements"].append(rq)
            target = key
        moved[rq] = target

    # 4. nodes
    nodes: dict[str, dict[str, Any]] = {}
    lineage: dict[str, set[str]] = {}

    def repair_node(oid: str, cls: str, subject: str, natural: str) -> dict[str, Any]:
        return {"outcome_id": oid, "role": "repair", "class": cls, "subject": subject, "natural_key": natural,
                "obligations": [], "clusters": [], "plan_paths": [], "entry_points": [], "scenarios": []}

    for o in objectives:
        atoms_ = o["atoms"]
        b0 = bnodes[atoms_[0]["baseline_owner"]]
        if len(atoms_) == 1:
            n = copy.deepcopy(b0)
            for k in ("requirements", "recipes", "planned_units", "parents", "budget", "description", "title", "acceptance"):
                n.pop(k, None)
            n["acceptance"] = {"checks": list(CHECKS[n["class"]])}
        else:
            classes = {bnodes[a["baseline_owner"]]["class"] for a in atoms_}
            if len(classes) != 1:
                raise ObjectiveError("OBJECTIVE_CLASS", "%s composes units of classes %s" % (o["id"], sorted(classes)))
            anchors = sorted({t.rsplit(".", 1)[-1] for a in atoms_ for t in a["member_types"]} or
                             {f.rsplit("/", 1)[-1] for a in atoms_ for f in a["files"]})
            n = repair_node(o["id"], classes.pop(), "%s (%s)" % (fams[o["family"]]["title"], ", ".join(anchors[:4]) + (", ..." if len(anchors) > 4 else "")),
                            "objective:%s:%s" % (o["family"], ",".join(sorted(a["cluster"] for a in atoms_))))
            for a in atoms_:
                bn = bnodes[a["baseline_owner"]]
                n["obligations"] += bn["obligations"]
                n["clusters"] += bn["clusters"]
                n["plan_paths"] += bn["plan_paths"]
                n["entry_points"] += bn.get("entry_points") or []
                n["scenarios"] += bn.get("scenarios") or []
            n["acceptance"] = {"checks": list(CHECKS[n["class"]])}
        n["requirements"] = sorted(o["requirements"])
        n["objective"] = {"policy": POLICY, "family": o["family"], "fallback_reason": o["fallback_reason"],
                          "constituents": [{"cluster": a["cluster"], "baseline_outcome": a["baseline_owner"], "seal": a["seal"],
                                            "transformations": a["transformations"], "write_set": a["files"],
                                            "items": sorted(a["items"])} for a in atoms_],
                          "bounds": o["bounds"]}
        n["_order"] = min((tuple(json.dumps(x) for x in (a["order"] or [a["cluster"]])) for a in atoms_))
        nodes[n["outcome_id"]] = n
        lineage[n["outcome_id"]] = {a["baseline_owner"] for a in atoms_}
    for key, ro in sorted(req_objectives.items()):
        rows = [reqrows[q] for q in ro["requirements"]]
        cls = {_s(r.get("class")) or "source" for r in rows}
        if len(cls) != 1:
            raise ObjectiveError("OBJECTIVE_CLASS", "%s owns requirements of classes %s" % (key, sorted(cls)))
        paths = sorted({p for r in rows for p in r.get("paths") or []})
        symbols = sum(len((r.get("facts") or {}).get("members") or []) or len(r.get("paths") or []) for r in rows)
        sites = sum(int((r.get("facts") or {}).get("sites") or 0) for r in rows if isinstance((r.get("facts") or {}).get("sites"), int))
        # a requirement objective's scope is its requirements' own paths; its symbols are the members it
        # owes (the planned-unit grant's measure), and a selected repository contract is a fragment set
        bounds = scope_bounds(files=paths, sites=sites, symbols=symbols,
                              fragment=ro["family"] == "selected-repository-implementation")
        if not bounds["within"]:
            raise ObjectiveError("OBJECTIVE_OVERSIZE", "%s spans %s; one requirement objective is one coherent repair" % (key, bounds))
        title = fams[ro["family"]]["title"] if ro["family"] else "requirement"
        subject = ro["subject"].rsplit(".", 1)[-1] if ro["family"] == "selected-repository-implementation" else \
            " ".join(part.rsplit(".", 1)[-1] for part in ro["subject"].replace("@", " @").split(" ")).split("|", 1)[0]
        n = repair_node(key, cls.pop(), "%s %s" % (title, subject), "objective:%s:%s" % (ro["family"], ro["subject"]))
        n["plan_paths"] = paths
        n["entry_points"] = sorted({_s(e) for r in rows for e in r.get("consumers") or [] if _s(e).startswith("ep:")})
        n["requirements"] = sorted(ro["requirements"])
        n["planned_units"] = [{"unit": 1, "paths": paths, "symbols": symbols, "grant": "none until issued"}]
        n["acceptance"] = {"checks": list(CHECKS[n["class"]])}
        n["objective"] = {"policy": POLICY, "family": ro["family"], "fallback_reason": "" if ro["family"] else
                          "no objective family names this requirement rule", "constituents": [], "bounds": bounds,
                          "subject": ro["subject"]}
        n["_order"] = (json.dumps("~req"), json.dumps(ro["family"]), json.dumps(ro["subject"]))
        if key in nodes:
            raise ObjectiveError("IDENTITY_AMBIGUOUS", "%s derived twice" % key)
        nodes[key] = n
        lineage[key] = {account[q] for q in ro["requirements"] if account.get(q) in bnodes}
    # behaviour / runtime / untouched requirement outcomes: exactly the baseline's
    for oid, bn in bnodes.items():
        if bn.get("role") != "repair" or oid in nodes:
            continue
        if bn["class"] in ("behavior", "runtime") or (bn.get("requirements") and not bn.get("clusters")
                                                       and not any(moved.get(q) for q in bn["requirements"])):
            n = copy.deepcopy(bn)
            for k in ("parents", "budget", "description", "title"):
                n.pop(k, None)
            n["requirements"] = sorted(q for q in bn.get("requirements") or [] if q not in moved)
            n["_order"] = (json.dumps("~keep"), json.dumps(oid))
            nodes[oid] = n
            lineage[oid] = {oid}
    for rq, target in moved.items():
        account[rq] = target
    absorb_recipe_runtime_findings(nodes, lineage, account, reqrows, items,
                                   {_s(c.get("id")): c for c in worklist.get("clusters") or [] if isinstance(c, dict)},
                                   (catalog or {}).get("migration_recipes") or {})
    for u in ownership_unresolved:
        uid = "unresolved:ownership:%s" % _h(u["requirement"])
        base.setdefault("unresolved", []).append({"id": uid, "kind": "ownership", "blocks": "delivery", "reason": u["reason"],
                                                  "requirements": [u["requirement"]]})
        account[u["requirement"]] = uid

    # 5. conservation (the same obligations and requirements, each owned once)
    owned: dict[str, str] = {}
    for oid, n in nodes.items():
        for ob in n["obligations"]:
            if ob in owned:
                raise PlanError("OBLIGATION_DUPLICATE", "%s owned by %s and %s" % (ob, owned[ob], oid))
            owned[ob] = oid
    if set(owned) != set(base.get("ownership") or {}):
        raise PlanError("OBLIGATION_LOST", "objectives own %d obligations, the baseline %d" % (len(owned), len(base.get("ownership") or {})))
    if set(account) != set(base.get("requirement_ownership") or {}):
        raise PlanError("REQUIREMENT_LOST", "requirement accounts differ from the baseline")
    for rq, owner in account.items():
        if owner in nodes and rq not in nodes[owner].get("requirements", []):
            raise PlanError("REQUIREMENT_LOST", "%s accounted to %s, which does not own it" % (rq, owner))

    # 6. per-(requirement, check) plan and hard prerequisites
    ids = sorted(nodes)
    cls_of = {k: nodes[k]["class"] for k in ids}
    # the obligations a check's read set can wait on: COMPILE diagnostics only.
    # gate:compile counts open javac items in its files, and the model-based
    # checks need those files to resolve; an MTA incident in the same file
    # changes neither, so its owner is no prerequisite.
    open_owner: dict[str, set[str]] = {}
    for ob, oid in owned.items():
        it = items.get(ob) or {}
        if _s(it.get("path")) and (_s(it.get("source")) == "javac" or _s(it.get("kind")) == "compile"):
            open_owner.setdefault(_s(it.get("path")), set()).add(oid)
    beh_by_ep = {ep: oid for oid, n in nodes.items() if n["class"] == "behavior" for ep in n.get("entry_points") or []}
    parents: dict[str, set[str]] = {k: {CONTROL_M2} for k in ids}
    basis: dict[str, dict[str, set[str]]] = {k: {} for k in ids}

    def add(k: str, p: str, why: str) -> None:
        parents[k].add(p)
        basis[k].setdefault(p, set()).add(why)

    for k in ids:
        n = nodes[k]
        if cls_of[k] in ("source", "runtime", "behavior"):
            for x in ids:
                if cls_of[x] in ("build", "config"):
                    add(k, x, "barrier: build and configuration first")
        if cls_of[k] == "runtime":
            for x in ids:
                if cls_of[x] == "source":
                    add(k, x, "barrier: a runtime gate needs every source outcome")
        if cls_of[k] == "behavior":
            for x in ids:
                if cls_of[x] != "behavior":
                    add(k, x, "barrier: parity needs the whole application to build and start")
        plan_rows = []
        for rq in n.get("requirements") or []:
            r = reqrows.get(rq) or {}
            for dep in r.get("dependencies") or []:
                d = account.get(_s(dep), "")
                if d in nodes and d != k:
                    add(k, d, "implementation: requirement %s depends on %s" % (rq, dep))
            for chk in r.get("acceptance") or []:
                later = cls_of[k] != "behavior" and str(chk).startswith(LATER_CHECK_PREFIXES) and not (
                    cls_of[k] == "runtime" and str(chk).startswith(("gate:package", "gate:augmentation", "gate:startup")))
                row = {"requirement": rq, "check": str(chk), "stage": "later" if later else "immediate", "prerequisites": []}
                if later:
                    dues = sorted({beh_by_ep[e] for e in r.get("consumers") or [] if e in beh_by_ep})
                    row["due"] = dues or ["M4"]
                else:
                    reads = "none" if str(chk).startswith("structure:annotation-absent:") else CHECK_READS.get(str(chk), "none")
                    if reads == "files":
                        need = sorted({o for p in r.get("paths") or [] for o in open_owner.get(p, set()) if o != k})
                        row["prerequisites"] = need
                        for o in need:
                            add(k, o, "verification: %s of %s reads files where %s owns obligations" % (chk, rq, o))
                plan_rows.append(row)
        n["check_plan"] = sorted(plan_rows, key=lambda x: (x["requirement"], x["check"]))
        immediate = sorted({x["check"] for x in plan_rows if x["stage"] == "immediate"})
        if immediate or n.get("requirements"):
            n["acceptance"]["requirement_checks"] = immediate
            n["acceptance"]["later_checks"] = sorted({x["check"] for x in plan_rows if x["stage"] == "later"})
        if n.get("requirements"):
            recipes = sorted({"%s@%s" % (_s((reqrows[q].get("recipe") or {}).get("id")), _s((reqrows[q].get("recipe") or {}).get("version")))
                              for q in n["requirements"] if reqrows.get(q, {}).get("recipe")})
            if recipes:
                n["recipes"] = recipes
    # hard cycles: combine only within one family and bounds, otherwise refuse
    for k in ids:
        for p in list(parents[k]):
            if p in parents and k in _ancestors(parents, p):
                raise PlanError("PREREQUISITE_CYCLE", "%s and %s each need the other's change before their checks (%s | %s)"
                                % (k, p, sorted(basis[k].get(p, set()))[:1], sorted(basis[p].get(k, set()))[:1]))

    # 7. budgets: connected baseline accounts <-> objectives, one family each
    budget_of = {oid: (n.get("budget") or {}) for oid, n in bnodes.items() if n.get("role") == "repair"}
    comp_of: dict[str, int] = {}
    groups: list[tuple[set[str], set[str]]] = []
    for oid in ids:
        acc = set(lineage.get(oid) or set()) & set(budget_of)
        hit = [i for i, (_objs, accs) in enumerate(groups) if accs & acc]
        merged_objs, merged_accs = {oid}, set(acc)
        for i in sorted(hit, reverse=True):
            o2, a2 = groups.pop(i)
            merged_objs |= o2
            merged_accs |= a2
        groups.append((merged_objs, merged_accs))
    for objs, accs in groups:
        limit = sum(int(budget_of[a].get("limit") or 0) for a in accs)
        fam_key = "rk:family:%s:%s" % (run_id, _h(sorted(accs)))
        for oid in objs:
            nodes[oid]["budget"] = {"key": fam_key, "limit": limit, "accounts": sorted(accs)}
    for oid in ids:
        if not nodes[oid].get("budget") or not nodes[oid]["budget"]["limit"]:
            raise PlanError("BUDGET_LINEAGE", "%s has no baseline budget account" % oid)
    regrouped = budget_regrouping({oid: nodes[oid]["budget"] for oid in ids}, budget_of,
                                  {oid: set(lineage.get(oid) or set()) & set(budget_of) for oid in ids})
    if regrouped:
        raise PlanError("BUDGET_REGROUPED", "; ".join(regrouped[:3]))

    # 8. finish nodes and the milestones exactly as the baseline builds them
    out_nodes = []
    for k in ids:
        n = nodes[k]
        n["parents"] = sorted(parents[k])
        n["prerequisites"] = {p: sorted(basis[k][p]) for p in sorted(basis[k])}
        n["order_hint"] = list(n.pop("_order"))
        for key in ("obligations", "clusters", "plan_paths", "entry_points", "scenarios"):
            n[key] = sorted(set(n.get(key) or []))
        n["shared_prerequisite"] = False
        n["title"] = _title(n["class"], n["subject"])
        n["assignee"] = IMPL
        n["skills"] = list(REPAIR_SKILLS)
        if len(n.get("objective", {}).get("constituents") or []) > 1:
            comp = [atoms[c["cluster"]] for c in n["objective"]["constituents"]]
            req_paths = {p for q in n.get("requirements") or [] for p in reqrows[q].get("paths") or []}
            final_paths = sorted(set(n["plan_paths"]) | req_paths | {f for a in comp for f in a["writable"]})
            final = _bounds(comp, extra_files=final_paths)
            if not final["within"]:
                raise PlanError("COMPOSITION_OVERSIZE", _oversize("objective %s after its requirements attached" % k, comp,
                                                                  final, bnodes, n.get("requirements") or []))
            n["objective"]["bounds"] = final
            n["execution_unit"] = {
                "policy": POLICY, "constituents": sorted(c["cluster"] for c in n["objective"]["constituents"]),
                "units": [{"cluster": c["cluster"], "seal": c["seal"], "write_set": c["write_set"], "items": c["items"],
                           "symbols": sorted(atoms[c["cluster"]]["symbols"]), "fragment": atoms[c["cluster"]]["fragment"]}
                          for c in sorted(n["objective"]["constituents"], key=lambda c: c["cluster"])],
                "obligations": list(n["obligations"]), "requirements": list(n.get("requirements") or []),
                # line-free identities of the admitted obligations: what "still
                # open" means for this scope, whatever lines the edits move
                "identities": {ob: _s(items.get(ob, {}).get("identity")) or ob for ob in n["obligations"]},
                "paths": final_paths,
                "bounds": final,
                "family": n["objective"]["family"],
                "check_plan": [dict(r) for r in n.get("check_plan") or []]}
        n["description"] = render_description(n)
        out_nodes.append(n)
    assess = next(x for x in base["nodes"] if x.get("role") == "assess")
    assess["parents"] = sorted({CONTROL_M2} | set(ids))
    # every LATER check is due at M4, exactly as the current policy defers a
    # runtime check an early outcome cannot measure (native_control.
    # defer_runtime_checks): planned here, never dropped, never a pass
    later: dict[tuple[str, str], set[str]] = {}
    for n in out_nodes:
        for row in n.get("check_plan") or []:
            if row["stage"] == "later":
                later.setdefault((n["outcome_id"], row["check"]), set()).add(row["requirement"])
    if later:
        acc = dict(assess.get("acceptance") or {})
        acc["deferred_requirement_checks"] = [{"outcome": o, "requirements": sorted(r), "check": c}
                                              for (o, c), r in sorted(later.items())]
        assess["acceptance"] = acc
    milestones = [assess] + [x for x in base["nodes"] if x.get("role") == "deliver"]
    doc = {k: v for k, v in base.items() if k not in ("digest",)}
    doc["nodes"] = out_nodes + milestones
    _acyclic(doc["nodes"])
    doc["ownership"] = dict(sorted(owned.items()))
    doc["requirement_ownership"] = dict(sorted(account.items()))
    doc["unresolved"] = sorted(base.get("unresolved") or [], key=lambda u: u["id"])
    doc["counts"] = dict(base.get("counts") or {}, baseline_outcomes=len(ids), unfinished=len(ids),
                         unresolved=len(doc["unresolved"]))
    doc["policy"] = POLICY
    doc["composition"] = {
        "baseline_outcomes": sum(1 for n in base["nodes"] if n.get("role") == "repair"),
        "objectives": len(ids), "refused": refused,
        "budget": {"baseline_total": sum(int(b.get("limit") or 0) for b in budget_of.values()),
                   "objective_total": sum(int(limit) for limit in {n["budget"]["key"]: n["budget"]["limit"] for n in out_nodes}.values())},
    }
    if doc["composition"]["budget"]["baseline_total"] != doc["composition"]["budget"]["objective_total"]:
        raise PlanError("BUDGET_NOT_CONSERVED", "%s" % doc["composition"]["budget"])
    schedule_checks(doc)
    return doc


def recipe_runtime_owners(item: dict[str, Any], write_set: list[str], nodes: dict[str, dict[str, Any]],
                          account: dict[str, str], reqrows: dict[str, dict[str, Any]],
                          recipes: dict[str, dict[str, Any]]) -> list[tuple[str, str, str]]:
    """The (outcome, requirement, recipe) rows whose planned recipe owns this
    runtime (package/startup gate) finding: the recipe declares the finding's
    gate and closed-vocabulary cause (compat-mapping migration_recipes
    <id>.runtime_findings), the requirement's own paths hold the finding's
    locus, and the owning outcome's planned scope already holds the finding's
    whole write set (no scope is widened). Pure."""
    gate, cause, path = _s(item.get("gate")), _s(item.get("cause")), _s(item.get("path"))
    if _s(item.get("source")) != "runtime" or not gate or not cause or not path or item.get("unlocated"):
        return []
    out = []
    for rq, owner in sorted(account.items()):
        n = nodes.get(owner)
        r = reqrows.get(rq) or {}
        if n is None or n.get("class") not in ("build", "config", "source") or rq not in (n.get("requirements") or []):
            continue
        rid_ = _s((r.get("recipe") or {}).get("id"))
        spec = (recipes.get(rid_) or {}).get("runtime_findings")
        if not isinstance(spec, dict) or gate not in (spec.get("gates") or []) or cause not in (spec.get("causes") or []):
            continue
        if path not in (r.get("paths") or []) or not set(write_set) <= set(n.get("plan_paths") or []):
            continue
        out.append((owner, rq, rid_))
    return out


def absorb_recipe_runtime_findings(nodes: dict[str, dict[str, Any]], lineage: dict[str, set[str]], account: dict[str, str],
                                   reqrows: dict[str, dict[str, Any]], items: dict[str, dict[str, Any]],
                                   clusters: dict[str, dict[str, Any]], recipes: dict[str, dict[str, Any]]) -> None:
    """Roadmap M-2 (never silently defer a dependency cycle): a runtime
    finding whose locus and cause a planned requirement's recipe owns is that
    requirement owner's obligation, never a separate runtime outcome. As a
    separate outcome it waits on every source outcome (a runtime gate needs
    the whole application) AND is waited on by the recipe's owner (its
    compile/model checks read the file where it holds an obligation): a cycle
    by construction, although one bounded edit discharges both (v28: the
    Servlet-redirect recipe removes the SpEL field the package gate refuses).

    Moved per whole cluster, only to exactly ONE owner, only inside that
    owner's planned scope; the runtime outcome's budget account joins the
    owner's family (lineage), so budgets stay conserved; an emptied runtime
    outcome is dropped. Anything else stays where the baseline put it, and a
    remaining mutual prerequisite is still refused as PREREQUISITE_CYCLE. In
    place; each move is recorded on the owner's objective (runtime_findings)."""
    for rt in sorted(k for k, n in nodes.items() if n.get("class") == "runtime"):
        n = nodes[rt]
        for cid in sorted(n.get("clusters") or []):
            c = clusters.get(cid) or {}
            members = sorted(_s(m) for m in c.get("items") or [])
            if not members or not set(members) <= set(n.get("obligations") or []):
                continue
            owners = {m: recipe_runtime_owners(items.get(m) or {}, list(c.get("write_set") or []), nodes, account, reqrows, recipes)
                      for m in members}
            targets = {o for rows in owners.values() for o, _q, _r in rows}
            if len(targets) != 1 or not all(owners.values()):
                continue
            target = targets.pop()
            t = nodes[target]
            t["obligations"] = list(t.get("obligations") or []) + members
            t["clusters"] = list(t.get("clusters") or []) + [cid]
            n["obligations"] = [o for o in n["obligations"] if o not in set(members)]
            n["clusters"] = [x for x in n["clusters"] if x != cid]
            lineage.setdefault(target, set()).update(lineage.get(rt) or {rt})
            t.setdefault("objective", {}).setdefault("runtime_findings", []).append({
                "cluster": cid, "obligations": members, "from": rt,
                "gates": sorted({_s((items.get(m) or {}).get("gate")) for m in members}),
                "causes": sorted({_s((items.get(m) or {}).get("cause")) for m in members}),
                "requirements": sorted({q for rows in owners.values() for _o, q, _r in rows}),
                "recipes": sorted({r for rows in owners.values() for _o, _q, r in rows})})
        if not n.get("obligations") and not n.get("requirements"):
            del nodes[rt]
            lineage.pop(rt, None)


def _ancestors(parents: dict[str, set[str]], k: str) -> set[str]:
    seen: set[str] = set()
    stack = list(parents.get(k, ()))
    while stack:
        x = stack.pop()
        if x not in seen:
            seen.add(x)
            stack.extend(parents.get(x, ()))
    return seen


def budget_regrouping(budgets: dict[str, dict[str, Any]], baseline: dict[str, dict[str, Any]],
                      lineage: dict[str, set[str]]) -> list[str]:
    """Roadmap M-2: regrouping never increases a family budget. ``budgets``
    outcome -> its composed {"key", "limit", "accounts"}; ``baseline`` baseline
    account -> its budget; ``lineage`` outcome -> the baseline accounts it came
    from. Empty when every baseline account is counted in exactly one family,
    each family's limit is exactly the sum of its own accounts' baseline limits,
    one family is recorded one way, and every outcome's lineage lies inside its
    family; otherwise each violation, named."""
    out: list[str] = []
    fam: dict[str, tuple[tuple[str, ...], int]] = {}
    for oid in sorted(budgets):
        b = budgets[oid] or {}
        key = _s(b.get("key"))
        accs = tuple(sorted(str(a) for a in b.get("accounts") or []))
        limit = int(b.get("limit") or 0)
        if key in fam and fam[key] != (accs, limit):
            out.append("family %s is recorded with two account sets or limits (at %s)" % (key, oid))
        fam.setdefault(key, (accs, limit))
        extra = sorted(set(lineage.get(oid) or ()) - set(accs))
        if extra:
            out.append("%s draws on baseline account(s) %s outside its family %s" % (oid, extra, key))
    seen: dict[str, str] = {}
    for key, (accs, limit) in sorted(fam.items()):
        for a in accs:
            if a in seen and seen[a] != key:
                out.append("baseline account %s is counted in families %s and %s" % (a, seen[a], key))
            seen.setdefault(a, key)
        want = sum(int((baseline.get(a) or {}).get("limit") or 0) for a in accs)
        if limit != want:
            out.append("family %s limit %d != %d, the sum of its baseline accounts %s" % (key, limit, want, list(accs)))
    for a in sorted(set(baseline) - set(seen)):
        out.append("baseline account %s is counted in no family" % a)
    return out


def _milestone(chk: str, scenarios: list[str], reaches_db: bool, validating: bool = False) -> str:
    """The earliest roadmap milestone at which a check says something useful:
    a repository read/write path is persistence; validation (a scenario a
    request-validation requirement names), CORS and security-mode scenarios,
    Location and adapters' modes are the remaining application behavior."""
    if chk == "coverage:unresolved":
        return "source-understood"
    if chk.startswith(("gate:", "unit:", "structure:", "config:", "build:", "adapter:")):
        return "target-structurally-viable"
    if chk.startswith("behavior:repository-effects:"):
        return "persistence-and-one-http-path"
    if chk.startswith("parity:") and "-mode:" not in chk and chk != REQUEST_BODY_CHECK and reaches_db and not validating \
            and not any(s.startswith(MODE_SCENARIO_PREFIXES) for s in scenarios):
        return "persistence-and-one-http-path"
    return "application-behavior-preserved"


def _row_scenarios(chk: str, req: dict[str, Any]) -> list[str]:
    """The captured scenarios a check's verdict is made of."""
    if chk.startswith("behavior:repository-effects:"):
        return sorted({str(s) for v in (req.get("facts") or {}).get("verification") or [] if isinstance(v, dict)
                       for s in v.get("scenarios") or []})
    if chk.startswith("location:") or chk == REQUEST_BODY_CHECK:
        return sorted({str(a)[len("parity:"):] for a in req.get("acceptance") or []
                       if str(a).startswith("parity:") and "-mode:" not in str(a) and str(a) != REQUEST_BODY_CHECK})
    if chk.startswith("parity:") and "-mode:" not in chk:
        return [chk[len("parity:"):]]
    return []


def schedule_checks(doc: dict[str, Any]) -> dict[str, Any]:
    """check-schedule/v1 over a composed revision, in place; returns the
    plan-level summary it records as ``doc["check_schedule"]``. Pure over the
    document: it reads nodes, parents, prerequisites, check plans and
    requirements, and writes only schedule metadata (no parent, owner, scope,
    obligation or budget changes). Deterministic: node and requirement order do
    not matter."""
    from planner.requirement_checks import has_producer

    nodes = {n["outcome_id"]: n for n in doc.get("nodes") or []}
    repair = {k: n for k, n in nodes.items() if n.get("role") == "repair"}
    reqs = {_s(r.get("id")): r for r in doc.get("requirements") or [] if isinstance(r, dict)}
    acct = doc.get("requirement_ownership") or {}
    parents = {k: {p for p in n.get("parents") or [] if p in nodes} for k, n in nodes.items()}
    anc: dict[str, set[str]] = {}

    def ancestors(k: str) -> set[str]:
        if k not in anc:
            anc[k] = _ancestors(parents, k)
        return anc[k]

    structural = {k for k, n in repair.items() if n.get("class") != "behavior"}
    # a packaged / started application: every build, configuration and source outcome accepted
    whole_app = {k for k, n in repair.items() if n.get("class") in ("build", "config", "source")}
    assess = sorted(k for k, n in nodes.items() if n.get("role") == "assess")
    m4 = assess[0] if assess else "M4"
    beh_by_scen: dict[str, set[str]] = {}
    beh_by_ep: dict[str, set[str]] = {}
    for k, n in repair.items():
        if n.get("class") == "behavior":
            for s in n.get("scenarios") or []:
                beh_by_scen.setdefault(str(s), set()).add(k)
            for e in n.get("entry_points") or []:
                beh_by_ep.setdefault(str(e), set()).add(k)
    # scenario -> the outcomes accountable for its verdict (their requirements name it)
    scen_owner: dict[str, set[str]] = {}
    # scenario -> the repository contracts it reaches: (owner or None, producer check)
    reach: dict[str, set[tuple[str, str]]] = {}
    validation: set[str] = set()
    for rid, r in reqs.items():
        own = _s(acct.get(rid))
        for a in r.get("acceptance") or []:
            if str(a).startswith("parity:") and own in repair:
                scen_owner.setdefault(str(a)[len("parity:"):], set()).add(own)
            if str(a).startswith("parity:") and _s(r.get("rule")).split("/", 1)[0] == "request-validation":
                validation.add(str(a)[len("parity:"):])
        if _s(r.get("rule")).split("/", 1)[0] == "repository-architecture" and _s(r.get("status")) == "applicable":
            producer = sorted(str(a) for a in r.get("acceptance") or [] if str(a).startswith("behavior:repository-effects:"))
            for v in (r.get("facts") or {}).get("verification") or []:
                for s in (v.get("scenarios") or []) if isinstance(v, dict) else []:
                    for p in producer or ["behavior:repository-effects:%s" % _s((r.get("facts") or {}).get("fragment"))]:
                        reach.setdefault(str(s), set()).add((own if own in repair else "", p))
    # implementation coupling: requirements linked by `dependencies` that serve a common consumer
    coupled: dict[str, set[str]] = {}
    for rid, r in reqs.items():
        for dep in r.get("dependencies") or []:
            d = reqs.get(str(dep))
            if d is None or not (set(r.get("consumers") or []) & set(d.get("consumers") or [])):
                continue
            a, b = _s(acct.get(rid)), _s(acct.get(str(dep)))
            if a in repair and b in repair and a != b:
                coupled.setdefault(rid, set()).add(b)
                coupled.setdefault(str(dep), set()).add(a)

    findings: list[dict[str, str]] = []
    affects: dict[str, dict[str, set[str]]] = {}
    counts = {m: {"immediate": 0, "later": 0} for m in MILESTONES}
    qualifications: set[str] = set()

    def finding(code: str, k: str, row: dict[str, Any], detail: str) -> None:
        findings.append({"code": code, "outcome": k, "check": _s(row.get("check")), "requirement": _s(row.get("requirement")),
                         "detail": detail})

    for k in sorted(repair):
        n = repair[k]
        if n.get("check_plan") is None:
            continue
        states: dict[str, dict[str, Any]] = {}
        for row in n["check_plan"]:
            chk, rid = _s(row.get("check")), _s(row.get("requirement"))
            r = reqs.get(rid) or {}
            scen = _row_scenarios(chk, r)
            requires: set[str] = {"compiled:%s" % o for o in row.get("prerequisites") or []}
            behavioural = chk.startswith(("parity:", "behavior:", "location:"))
            if chk in ("gate:package", "gate:augmentation"):
                requires.add(APP_PACKAGED)
            elif chk == "gate:startup" or behavioural:
                requires |= {APP_PACKAGED, APP_STARTED}
            if chk.startswith("parity:") and "-mode:" in chk:
                requires.add("mode-receipt:%s" % chk.rsplit(":", 1)[1])
            producers = {x for s in scen for x in reach.get(s, set())}
            reaches_db = bool(producers) or chk.startswith("behavior:repository-effects:")
            if reaches_db:
                requires.add(DB_WORKING)
            repairs: set[str] = set()
            if behavioural:
                repairs = {o for s in scen for o in scen_owner.get(s, set())} | set(coupled.get(rid, set()))
                repairs |= {o for o, _p in producers if o}
                repairs = (repairs & structural) - {k}
            requires |= {"repair:%s" % o for o in repairs}
            after = sorted({"%s#%s" % (o, p) for o, p in producers if o and o != k})
            unowned = sorted({p for o, p in producers if not o})
            ms = _milestone(chk, scen, reaches_db, validating=bool(set(scen) & validation))
            if row.get("stage") == "later":
                pts: set[str] = set()
                if chk.startswith("gate:"):
                    pts = {FIRST_PACKAGE}
                else:
                    for s in scen:
                        pts |= beh_by_scen.get(s, set())
                    for e in list(r.get("consumers") or []) + ([chk[len("location:"):]] if chk.startswith("location:") else []):
                        pts |= beh_by_ep.get(str(e), set())
                at = sorted(pts) or [m4]
            else:
                at = [k]
            row["owner"] = k
            row["requires"] = sorted(requires)
            row["earliest"] = {"milestone": ms, "at": at}
            if after:
                row["after"] = after
            else:
                row.pop("after", None)
            if chk.startswith("behavior:repository-effects:"):
                row["qualification"] = QUALIFY_REPOSITORY % chk[len("behavior:repository-effects:"):]
                qualifications.add(row["qualification"])
            else:
                row.pop("qualification", None)
            stage = "later" if row.get("stage") == "later" else "immediate"
            counts[ms][stage] += 1
            st = states.setdefault(stage, {"checks": 0, "milestones": set(), "at": set(), "qualification": set()})
            st["checks"] += 1
            st["milestones"].add(ms)
            st["at"] |= set(at)
            if row.get("qualification"):
                st["qualification"].add(row["qualification"])
            for o, _p in producers:
                if o and o != k:
                    affects.setdefault(o, {}).setdefault(k, set()).add(chk)
            # -- what cannot be scheduled is named, never deferred ---------------------
            if not has_producer(chk):
                finding("CHECK_NO_PRODUCER", k, row, "no measurement producer implements %s: it could never pass" % chk)
            for p in unowned:
                finding("SCOPE_ONLY_ROUTE", k, row, "%s depends on %s, whose repository contract no planned outcome owns: "
                        "the only route to acceptance would be an edit outside every planned scope" % (chk, p))
            if stage == "immediate":
                need = {x.split(":", 1)[1] for x in requires if x.startswith(("compiled:", "repair:"))}
                if requires & set(RUNTIME_REQUIRES) or any(x.startswith("mode-receipt:") for x in requires):
                    need |= whole_app - {k}
                missing = sorted(need - ancestors(k))
                if missing:
                    finding("IMMEDIATE_NOT_EXECUTABLE", k, row, "judged at issue, but %d prerequisite outcome(s) are not its "
                            "ancestors: %s" % (len(missing), ", ".join(missing[:4])))
            else:
                for pt in at:
                    if pt not in nodes or pt == m4:
                        continue
                    if pt in ancestors(k) or pt == k:
                        finding("LATER_DEFERRED_CYCLE", k, row, "measured at %s, which precedes its owner %s: the check "
                                "could only pass at M4" % (pt, k))
                    elif k not in ancestors(pt):
                        finding("LATER_BEFORE_OWNER", k, row, "measured at %s, which does not follow its owner" % pt)
                    late = sorted(o for o in repairs if o not in ancestors(pt))
                    if late:
                        finding("LATER_BEFORE_PREREQUISITE", k, row, "measured at %s before its causal repair(s) %s"
                                % (pt, ", ".join(late[:4])))
        if not states:
            n.pop("acceptance_states", None)
        else:
            n["acceptance_states"] = {
                stage: {"checks": st["checks"], "milestones": [m for m in MILESTONES if m in st["milestones"]],
                        "at": sorted(st["at"]), **({"qualification": sorted(st["qualification"])} if st["qualification"] else {}),
                        "meaning": ("judged at this outcome's acceptance" if stage == "immediate" else
                                    "owned by this outcome and measured at the points named; structural acceptance never "
                                    "discharges it")}
                for stage, st in sorted(states.items())}
        kinds: dict[str, set[str]] = {}
        for p, why in (n.get("prerequisites") or {}).items():
            for w in why or []:
                kinds.setdefault(str(w).split(":", 1)[0].strip(), set()).add(p)
        n["dependency_kinds"] = {kk: sorted(v) for kk, v in sorted(kinds.items())}
        if isinstance(n.get("execution_unit"), dict):
            n["execution_unit"]["check_plan"] = [dict(r) for r in n["check_plan"]]
    for o in sorted(repair):
        if o in affects:
            repair[o]["causal_scope"] = {
                "affects": [{"outcome": b, "checks": sorted(c)} for b, c in sorted(affects[o].items())],
                "remeasure": REMEASURE_RULE}
        else:
            repair[o].pop("causal_scope", None)
    summary = {
        "version": CHECK_SCHEDULE,
        "milestones": [{"id": m, "title": MILESTONE_TITLES[m]} for m in MILESTONES],
        "points": dict(POINTS),
        "counts": counts,
        "qualifications": sorted(qualifications),
        "findings": sorted(findings, key=lambda f: (f["code"], f["outcome"], f["requirement"], f["check"])),
    }
    doc["check_schedule"] = summary
    return summary
