"""Initial outcome graph from admission-time evidence (architect F5, C5).

Pure: reads only its arguments, performs no I/O, returns a JSON-compatible plan
revision. Nothing here publishes, grants an edit or decides acceptance; the
revision is an input to K4 graph publication (kernel/k4_graph.py) and to the
authority's checks (outcome_lifecycle.py).

Inputs are admission-time evidence, never a late remainder:

  worklist      the sealed admission work list (items, clusters, measure,
                not_counted, unlocatable, blocked_clusters). The measure must be
                KNOWN: missing evidence is not an empty work list.
  entry_points  the entry-point inventory rows (``entry_point_id``, ``kind``,
                ``subtype``, ``file``). Required, possibly empty.
  oracles       entry point id -> captured scenario ids, or None when no
                capture exists. An entry point with no oracle is a NAMED
                verification responsibility (unresolved), never a generic
                repair outcome.
  references    product path -> product paths it references (the type
                inventory / destination model's declared references). Used
                only to order support work before what it supports.

Outcome classes and their checkpoint (a class is where acceptance is decided):

  build / config   owned build or configuration obligations; build gate
  source           one cluster of compile / incident / test obligations
                   (the existing unit or cluster former already bounds it);
                   compile+test measurement
  runtime          package / startup gate obligations; the gate itself.
                   Compilation alone never discharges them
  behavior         one declaring type's entry points with captured oracles,
                   plus any parity obligation already measured for them;
                   the parity comparison of its scenarios

Grouping never unions files into a grant: each cluster keeps its own write set
and bound, and an outcome issues one cluster at a time. ``plan_paths`` is
descriptive scope only.

Dependencies are prerequisites: build/config before source; a source outcome
after every source outcome whose files it references (support before what it
supports, whatever the work list's order), with only a mutual reference ordered
by the work list's leaf-first order key so the graph stays acyclic; runtime
after every compile-bearing outcome, behavior after every non-behavior repair
outcome (parity cannot be measured on an application that does not start),
the assessment after every outcome, and delivery after the assessment. Every
executable node also names the open M2 control card, so nothing escapes the
publication hold.

Identity is frozen at publication (resolve_identities): a later derivation maps
each group onto the frozen outcome whose obligations it shares, whatever its
derived key now says; renames and regrouping never create a new budget.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

SCHEMA = "rhoai3.outcome-plan/v1"
CONTROL_M2 = "control:m2"
ASSESS_PREFIX = "assess:m4"
DELIVER_STAGES = ("prepare", "push", "accept")
DELIVER_TITLES = {"prepare": "M5 PREFLIGHT", "push": "M5 DEPLOY", "accept": "M5 VALIDATE"}
IMPL = "implementer"
REPAIR_SKILL = "paved-road-m3"
ASSESS_SKILL = "paved-road-m4"
DELIVER_SKILL = "paved-road-m5"
CLASSES = ("build", "config", "source", "runtime", "behavior")
RUNTIME_GATES = ("package", "startup", "boot")
CHECKS = {
    "build": ["worklist-absent", "measure:build"],
    "config": ["worklist-absent", "measure:build"],
    "source": ["worklist-absent", "measure:compile", "measure:tests"],
    "runtime": ["worklist-absent", "gate:runtime"],
    "behavior": ["worklist-absent", "parity:scenarios"],
}
# Scope bounds the existing unit former enforces (worklist.UNIT_MAX_FILES);
# a cluster above it at admission is refused here rather than silently issued.
MAX_WRITE_SET = 20


class PlanError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def _req(cond: bool, code: str, detail: str) -> None:
    if not cond:
        raise PlanError(code, detail)


def _s(v: Any) -> str:
    return v if isinstance(v, str) else ""


def declaring_type(entry_point: str) -> tuple[str, str]:
    """(declaring type, entry kind) from ``ep:<type>#<member>:<kind>`` or
    ``ep:<type>:<kind>``; ('', '') when it has neither shape."""
    ep = _s(entry_point)
    if not ep.startswith("ep:"):
        return "", ""
    body = ep[3:]
    kind = ""
    if body.rfind(":") > body.rfind("#") and ":" in body:
        body, kind = body.rsplit(":", 1)
    typ = body.split("#", 1)[0]
    if not typ or not kind or " " in typ:
        return "", ""
    return typ, kind


def _stable_key(cluster: dict[str, Any]) -> str:
    unit = cluster.get("unit") if isinstance(cluster.get("unit"), dict) else {}
    return _s(unit.get("unit_id")) or _s(cluster.get("retry_key")) or _s(cluster.get("id"))


def _class_of(cluster: dict[str, Any], items: list[dict[str, Any]]) -> str:
    gates = {_s(i.get("gate")) for i in items} | {_s(cluster.get("gate"))}
    kind = _s(cluster.get("kind"))
    if kind == "parity" or any(_s(i.get("kind")) == "parity" for i in items):
        return "behavior"
    if gates & set(RUNTIME_GATES) or any(_s(i.get("source")) == "runtime" for i in items):
        return "runtime"
    if kind == "build":
        return "build"
    if kind == "config":
        return "config"
    return "source"


def _title(cls: str, subject: str) -> str:
    return {
        "build": "Build: %s",
        "config": "Configuration: %s",
        "source": "Source compatibility: %s",
        "runtime": "Application %s",
        "behavior": "Behavior: %s",
    }[cls] % subject


def render_description(outcome: dict[str, Any]) -> str:
    """Two to four plain sentences: the result and how acceptance is recognized.
    No machine JSON, no write set, no commands, no history, no verdict."""
    cls = outcome.get("class")
    n = len(outcome.get("obligations") or [])
    subject = outcome.get("subject") or outcome.get("outcome_id")
    if outcome.get("role") == "assess":
        return ("Assess the combined migrated application on the final artifact. Complete when the measured "
                "assessment is recorded and its audit passes, whatever the application verdict is. "
                "The attached brief lists the prerequisite outcomes and the checks the assessment runs.")
    if outcome.get("role") == "deliver":
        return ("%s for the assessed candidate. It starts only after the delivery stage before it is accepted and "
                "the current assessment admits it. The attached brief states what this stage needs and produces."
                % DELIVER_TITLES.get(_s(outcome.get("stage")), "Delivery stage"))
    what = {
        "build": "Make the destination build configuration satisfy its {n} owned obligation(s) for {subject}.",
        "config": "Migrate the configuration owned here ({n} obligation(s)) for {subject}.",
        "source": "Make {subject} compile and pass its tests on the target platform ({n} owned obligation(s)).",
        "runtime": "Make the application {subject} on the target platform ({n} owned obligation(s)).",
        "behavior": "Restore source-equivalent behavior of {subject} ({n} owned obligation(s)).",
    }[cls]
    accept = {
        "build": "Complete when the owned obligations are gone from the measured work list and the build passes.",
        "config": "Complete when the owned obligations are gone from the measured work list and the build passes.",
        "source": "Complete when the owned obligations are gone from the measured work list for the current candidate.",
        "runtime": "Complete when that gate passes on the packaged candidate; compiling alone does not satisfy it.",
        "behavior": "Complete when the assigned parity checks pass for the current candidate and no owned obligation remains open.",
    }[cls]
    return "%s %s The attached brief lists the obligations and evidence; the pinned repair procedure applies." % (
        what.format(n=n, subject=subject), accept)


def _validate_worklist(worklist: Any) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    _req(isinstance(worklist, dict), "ADMISSION_INPUT", "worklist must be an object")
    items = worklist.get("items")
    clusters = worklist.get("clusters")
    _req(isinstance(items, list) and isinstance(clusters, list), "ADMISSION_INPUT", "worklist needs items and clusters arrays")
    measure = worklist.get("measure")
    _req(isinstance(measure, dict) and measure.get("known") is True, "ADMISSION_EVIDENCE_INCOMPLETE",
         "the admission measure is not known; missing evidence is not an empty work list")
    by_id: dict[str, dict[str, Any]] = {}
    for it in items:
        _req(isinstance(it, dict) and _s(it.get("id")), "ADMISSION_INPUT", "every item needs a non-empty id")
        _req(it["id"] not in by_id, "ADMISSION_INPUT", "duplicate item id %s" % it["id"])
        _req(_s(it.get("kind")) in ("build", "config", "compile", "incident", "test", "parity"),
             "ADMISSION_UNSUPPORTED", "item %s kind %r" % (it["id"], it.get("kind")))
        _req(_s(it.get("category")) in ("mandatory", "optional", "potential"), "ADMISSION_INPUT",
             "item %s category %r" % (it["id"], it.get("category")))
        by_id[it["id"]] = it
    seen: dict[str, str] = {}
    out: list[dict[str, Any]] = []
    cids: set[str] = set()
    for c in clusters:
        _req(isinstance(c, dict) and _s(c.get("id")), "ADMISSION_INPUT", "every cluster needs an id")
        _req(c["id"] not in cids, "ADMISSION_INPUT", "duplicate cluster id %s" % c["id"])
        cids.add(c["id"])
        _req(_s(c.get("status")) in ("open", "deferred", "blocked"), "ADMISSION_INPUT", "cluster %s status %r" % (c["id"], c.get("status")))
        members = c.get("items")
        _req(isinstance(members, list) and members, "ADMISSION_INPUT", "cluster %s has no items" % c["id"])
        ws = c.get("write_set")
        _req(isinstance(ws, list) and all(isinstance(p, str) and p for p in ws), "ADMISSION_INPUT", "cluster %s write_set" % c["id"])
        _req(len(ws) <= MAX_WRITE_SET, "SCOPE_BOUND", "cluster %s write set %d > %d" % (c["id"], len(ws), MAX_WRITE_SET))
        _req(not any(p.replace("\\", "/").startswith("src/test/java/") for p in ws), "SCOPE_BOUND",
             "cluster %s write set names a test source" % c["id"])
        for m in members:
            _req(m in by_id, "ADMISSION_INPUT", "cluster %s references unknown item %s" % (c["id"], m))
            _req(m not in seen, "ADMISSION_INPUT", "item %s in clusters %s and %s" % (m, seen.get(m), c["id"]))
            seen[m] = c["id"]
        out.append(c)
    unlocatable = {(_s(u.get("id")) if isinstance(u, dict) else _s(u)) for u in (worklist.get("unlocatable") or [])}
    for iid, it in by_id.items():
        if it["category"] == "mandatory" and iid not in seen and iid not in unlocatable:
            raise PlanError("OBLIGATION_ORPHAN", "mandatory item %s is in no cluster and not unlocatable" % iid)
    return by_id, out


def _validate_entry_points(entry_points: Any) -> list[dict[str, Any]]:
    _req(isinstance(entry_points, list), "ADMISSION_EVIDENCE_INCOMPLETE",
         "the entry-point inventory is required at admission (it may be empty, never missing)")
    out = []
    seen: set[str] = set()
    for row in entry_points:
        _req(isinstance(row, dict), "ADMISSION_INPUT", "entry point row must be an object")
        ep = _s(row.get("entry_point_id"))
        typ, kind = declaring_type(ep)
        _req(bool(typ), "ADMISSION_INPUT", "entry point %r is not ep:<type>#<member>:<kind>" % ep)
        _req(ep not in seen, "ADMISSION_INPUT", "duplicate entry point %s" % ep)
        seen.add(ep)
        out.append({"entry_point_id": ep, "type": typ, "kind": kind, "file": _s(row.get("file"))})
    return out


def _validate_provenance(p: Any) -> None:
    _req(isinstance(p, dict), "ADMISSION_INPUT", "provenance must be an object")
    _req(_s(p.get("snapshot_kind")) in ("admission", "synthetic"), "ADMISSION_INPUT",
         "provenance.snapshot_kind must be admission or synthetic")
    _req(bool(_s(p.get("scope_note"))), "ADMISSION_INPUT", "provenance.scope_note is required")
    if p["snapshot_kind"] == "synthetic":
        _req(bool(_s(p.get("construction"))) and p.get("observed_migration_event") is False, "ADMISSION_INPUT",
             "synthetic provenance needs construction and observed_migration_event: false")


def derive_initial_graph(*, run_id: str, worklist: dict[str, Any], entry_points: list[dict[str, Any]],
                         oracles: dict[str, list[str]] | None, references: dict[str, list[str]] | None,
                         provenance: dict[str, Any], max_attempts: int = 3,
                         satisfied: dict[str, str] | None = None,
                         requirements: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Plan revision 1 for a run, or PlanError. Never a partial plan.

    ``requirements`` (plan semantics v1, planner.source_requirements) are the
    known responsibilities derived from the frozen source. None (every caller
    before v1) leaves the revision exactly as before; a list makes each one
    owned by exactly one outcome, satisfied with its receipt, not applicable,
    or an explicit unresolved responsibility (attach_requirements)."""
    _req(bool(_s(run_id)) and ":" not in run_id, "ADMISSION_INPUT", "run_id must be a non-empty name without ':'")
    _req(isinstance(max_attempts, int) and max_attempts >= 1, "ADMISSION_INPUT", "max_attempts must be >= 1")
    _validate_provenance(provenance)
    worklist = copy.deepcopy(worklist)
    by_id, clusters = _validate_worklist(worklist)
    eps = _validate_entry_points(copy.deepcopy(entry_points))
    _req(oracles is None or isinstance(oracles, dict), "ADMISSION_INPUT", "oracles must be a map or null")
    refs = {str(k): sorted({str(x) for x in (v or [])}) for k, v in (references or {}).items()}
    satisfied = dict(satisfied or {})

    outcomes: dict[str, dict[str, Any]] = {}
    dispositions: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    order: dict[str, tuple] = {}

    def outcome(oid: str, cls: str, subject: str, natural: str) -> dict[str, Any]:
        if oid not in outcomes:
            outcomes[oid] = {"outcome_id": oid, "role": "repair", "class": cls, "subject": subject,
                             "natural_key": natural, "obligations": [], "clusters": [], "plan_paths": [],
                             "entry_points": [], "scenarios": []}
        _req(outcomes[oid]["class"] == cls, "IDENTITY_AMBIGUOUS", "%s derived as %s and %s" % (oid, outcomes[oid]["class"], cls))
        return outcomes[oid]

    # 1. clusters -> repair outcomes (one cluster each, or one declaring type for parity)
    for c in clusters:
        members = [by_id[m] for m in c["items"]]
        mandatory = [m for m in members if m["category"] == "mandatory"]
        cls = _class_of(c, members)
        if cls == "behavior":
            types = set()
            for m in members:
                typ, kind = declaring_type(_s(m.get("entry_point")))
                _req(bool(typ), "ADMISSION_UNSUPPORTED", "parity item %s has no ep:<type>#<member>:<kind> entry point" % m["id"])
                types.add((typ, kind))
            _req(len(types) == 1, "ADMISSION_UNSUPPORTED", "parity cluster %s spans %d declaring types" % (c["id"], len(types)))
            typ, kind = next(iter(types))
            o = outcome("behavior:%s:%s" % (kind, typ), cls, typ, "%s:%s" % (kind, typ))
        else:
            key = _stable_key(c)
            subject = _s(c.get("label")) or _s(c.get("path")).rsplit("/", 1)[-1] or key
            if cls == "runtime":
                gate = next((g for g in [_s(c.get("gate"))] + [_s(m.get("gate")) for m in members] if g), "package")
                o = outcome("runtime:%s:%s" % (gate, key), cls, "%s (%s gate)" % (subject, gate), key)
                o["subject"] = "package and start" if gate in RUNTIME_GATES else subject
            else:
                o = outcome("%s:%s" % (cls, key), cls, subject, key)
        if c["status"] == "blocked":
            unresolved.append({"id": "unresolved:blocked:%s" % c["id"], "kind": "blocked-cluster", "blocks": "delivery",
                               "reason": "cluster %s is a typed blocker at admission: %s" % (c["id"], _s(c.get("block")) or "no card can discharge it"),
                               "obligations": sorted(m["id"] for m in mandatory)})
        o["clusters"].append(c["id"])
        o["obligations"].extend(m["id"] for m in mandatory)
        o["plan_paths"].extend(c["write_set"])
        o["plan_paths"].extend(p for p in [_s(c.get("path"))] if p)
        ok = c.get("order_key")
        order[c["id"]] = tuple(json.dumps(x) for x in ok) if isinstance(ok, list) else (json.dumps(c["id"]),)
        for m in members:
            if m["category"] != "mandatory":
                dispositions.append({"obligation_id": m["id"], "disposition": "optional", "reason": "category %s" % m["category"]})
            if m.get("entry_point"):
                o["entry_points"].append(_s(m["entry_point"]))
            if m.get("scenario"):
                o["scenarios"].append(_s(m["scenario"]))

    # 2. entry points -> behavior outcomes (verification responsibilities)
    by_type: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for ep in eps:
        by_type.setdefault((ep["kind"], ep["type"]), []).append(ep)
    for (kind, typ), rows in sorted(by_type.items()):
        captured = [r for r in rows if oracles is not None and oracles.get(r["entry_point_id"])]
        missing = [r for r in rows if r not in captured]
        if captured:
            o = outcome("behavior:%s:%s" % (kind, typ), "behavior", typ, "%s:%s" % (kind, typ))
            for r in captured:
                oid = "verify:%s" % r["entry_point_id"]
                if oid in satisfied:
                    dispositions.append({"obligation_id": oid, "disposition": "satisfied", "reason": satisfied[oid]})
                    continue
                o["obligations"].append(oid)
                o["entry_points"].append(r["entry_point_id"])
                o["scenarios"].extend(str(s) for s in oracles.get(r["entry_point_id"]) or [])
                if r["file"]:
                    o["plan_paths"].append(r["file"])
        if missing:
            unresolved.append({"id": "unresolved:verification:%s:%s" % (kind, typ), "kind": "verification-responsibility", "blocks": "ship",
                               "reason": "no captured oracle for %d %s entry point(s) of %s; behavior is unverified, not accepted"
                                         % (len(missing), kind, typ),
                               "entry_points": sorted(r["entry_point_id"] for r in missing)})
    for o in outcomes.values():
        if o["class"] == "behavior" and not o["obligations"] and not o["clusters"]:
            # every captured entry point was already satisfied: no repair outcome is issued
            pass
    req_account: dict[str, str] = {}
    if requirements is not None:
        req_account = attach_requirements(outcomes, requirements, unresolved=unresolved, dispositions=dispositions,
                                          order=order, outcome=outcome)
    outcomes = {k: v for k, v in outcomes.items() if v["obligations"] or v.get("requirements")}

    # 3. conservation: each mandatory item exactly once, or explicitly disposed
    owned: dict[str, str] = {}
    for o in outcomes.values():
        for ob in o["obligations"]:
            _req(ob not in owned, "OBLIGATION_DUPLICATE", "%s owned by %s and %s" % (ob, owned.get(ob), o["outcome_id"]))
            owned[ob] = o["outcome_id"]
    for u in worklist.get("unlocatable") or []:
        uid = _s(u.get("id")) if isinstance(u, dict) else _s(u)
        if uid:
            unresolved.append({"id": "unresolved:unlocatable:%s" % uid, "kind": "unlocatable", "blocks": "delivery",
                               "reason": "measured obligation with no file of this tree", "obligations": [uid]})
    for nc in worklist.get("not_counted") or []:
        if isinstance(nc, dict) and _s(nc.get("id")):
            dispositions.append({"obligation_id": nc["id"], "disposition": "superseded",
                                 "reason": _s((nc.get("by") or {}).get("reason")) or _s(nc.get("category")) or "not counted"})
    for iid, it in by_id.items():
        if it["category"] == "mandatory" and iid not in owned and not any(iid in (u.get("obligations") or []) for u in unresolved):
            raise PlanError("OBLIGATION_LOST", "mandatory item %s has no owner and no disposition" % iid)

    # 4. dependencies
    ids = sorted(outcomes)
    cls_of = {k: outcomes[k]["class"] for k in ids}
    path_owner: dict[str, set[str]] = {}
    for k in ids:
        for p in outcomes[k]["plan_paths"]:
            path_owner.setdefault(p, set()).add(k)
    first_order = {k: min([order.get(c, ("~",)) for c in outcomes[k]["clusters"]]
                          + ([outcomes[k]["_order"]] if outcomes[k].get("_order") else []), default=("~",)) for k in ids}
    # support first: A references B => A depends on B. Only a mutual reference
    # (a strongly connected component) is ordered by the work list's own
    # leaf-first order key, which keeps the graph acyclic without ever putting
    # support work behind the outcome it unblocks.
    src = [k for k in ids if cls_of[k] == "source"]
    ref_edges: dict[str, set[str]] = {k: set() for k in src}
    for k in src:
        for p in outcomes[k]["plan_paths"]:
            for q in refs.get(p, []):
                for other in path_owner.get(q, set()):
                    if other != k and cls_of[other] == "source":
                        ref_edges[k].add(other)
    comp = _scc(ref_edges)
    referenced_by: dict[str, set[str]] = {k: set() for k in ids}
    for k in ids:
        o = outcomes[k]
        parents = {CONTROL_M2}
        if cls_of[k] in ("source", "runtime", "behavior"):
            parents |= {x for x in ids if cls_of[x] in ("build", "config")}
        if cls_of[k] == "source":
            for other in ref_edges[k]:
                if comp[other] != comp[k] or first_order[other] < first_order[k]:
                    parents.add(other)
                    referenced_by[other].add(k)
        if cls_of[k] == "runtime":
            parents |= {x for x in ids if cls_of[x] == "source"}
        if cls_of[k] == "behavior":
            parents |= {x for x in ids if cls_of[x] != "behavior"}
        # qualified source/recipe prerequisites (generated models before their
        # consumers, a retirement before the behaviour it hands over)
        parents |= {x for x in o.pop("_req_parents", set()) if x in outcomes and x != k}
        o["parents"] = sorted(parents)
    for k in ids:
        o = outcomes[k]
        o["obligations"] = sorted(set(o["obligations"]))
        o["clusters"] = sorted(set(o["clusters"]))
        o["plan_paths"] = sorted(set(o["plan_paths"]))
        o["entry_points"] = sorted(set(o["entry_points"]))
        o["scenarios"] = sorted(set(o["scenarios"]))
        o["shared_prerequisite"] = len(referenced_by[k]) >= 2
        o["title"] = _title(o["class"], o["subject"])
        o["acceptance"] = {"checks": list(CHECKS[o["class"]])}
        o.pop("_order", None)
        if o.get("requirements"):
            # the owner's applicable completion checks: an empty live work list
            # never discharges them (outcome_lifecycle._covers)
            o["requirements"] = sorted(set(o["requirements"]))
            o["acceptance"]["requirement_checks"] = sorted(set(o.pop("_req_checks", [])))
            o["recipes"] = sorted(set(o.pop("_recipes", [])))
        o["assignee"] = IMPL
        o["skills"] = [REPAIR_SKILL]
        o["budget"] = {"key": "rk:outcome:%s:%s" % (run_id, k), "limit": max_attempts * max(1, len(o["clusters"]))}
        o["description"] = render_description(o)
    assess_id = "%s:g1" % ASSESS_PREFIX
    nodes = [outcomes[k] for k in ids]
    assess = {"outcome_id": assess_id, "role": "assess", "class": "assess", "generation": 1, "subject": "M4 ASSESS",
              "title": "M4 ASSESS", "parents": sorted({CONTROL_M2} | set(ids)), "assignee": IMPL,
              "skills": [ASSESS_SKILL], "obligations": [], "clusters": [], "plan_paths": []}
    assess["description"] = render_description(assess)
    nodes.append(assess)
    prev = assess_id
    for stage in DELIVER_STAGES:
        did = "deliver:%s:c1" % stage
        d = {"outcome_id": did, "role": "deliver", "class": "deliver", "stage": stage, "cycle": 1,
             "title": DELIVER_TITLES[stage], "subject": DELIVER_TITLES[stage], "parents": [prev], "assignee": None,
             "skills": [DELIVER_SKILL], "obligations": [], "clusters": [], "plan_paths": [],
             "binding": {"assessment": assess_id}}
        d["description"] = render_description(d)
        nodes.append(d)
        prev = did
    _acyclic(nodes)
    counts = {"baseline_outcomes": len(ids), "additions": 0, "replaced_or_removed": 0,
              "accepted": 0, "unfinished": len(ids), "milestones": 1 + len(DELIVER_STAGES),
              "satisfied_obligations": sum(1 for d in dispositions if d["disposition"] == "satisfied"),
              "unresolved": len(unresolved)}
    doc = {
        "schema": SCHEMA,
        "run_id": run_id,
        "revision": 1,
        "parent_revision": None,
        "kind": "initial",
        "provenance": copy.deepcopy(provenance),
        "nodes": nodes,
        "ownership": {ob: oid for oid in ids for ob in outcomes[oid]["obligations"]},
        "dispositions": sorted(dispositions, key=lambda d: (d["obligation_id"], d["disposition"])),
        "unresolved": sorted(unresolved, key=lambda u: u["id"]),
        "counts": counts,
        "claimed_control": False,
    }
    if requirements is not None:
        # present only under plan semantics v1, so an existing revision's
        # content -- and its digest -- is exactly what it was
        doc["requirements"] = sorted((copy.deepcopy(r) for r in requirements), key=lambda r: str(r.get("id")))
        doc["requirement_ownership"] = dict(sorted(req_account.items()))
        by_status: dict[str, int] = {}
        for r in requirements:
            by_status[_s(r.get("status"))] = by_status.get(_s(r.get("status")), 0) + 1
        counts["requirements"] = dict(sorted(by_status.items()))
    doc["digest"] = plan_digest(doc)
    return doc


REQ_UNIT_MAX_FILES = MAX_WRITE_SET   # worklist.UNIT_MAX_FILES
REQ_UNIT_MAX_SYMBOLS = 16            # worklist.UNIT_MAX_FRAGMENT_SYMBOLS (the widest coherent unit the former allows)
_REQ_WORDS = {"repository-architecture": "repository fragment", "request-validation": "request validation",
              "handler-parameter-binding": "handler parameter", "annotation-retirement": "retire annotation",
              "adapter-behavior": "adapter behaviour", "generator-configuration": "generator configuration",
              "configuration-decision": "decided configuration", "behavior-verification": "verify"}


def _simple(subject: str) -> str:
    """org.a.B#m(org.a.C,org.x.D) -> B#m(C,D): readable, still distinct."""
    out, tok = [], ""
    for ch in subject + " ":
        if ch.isalnum() or ch in "._$":
            tok += ch
            continue
        if tok:
            out.append(tok.rsplit(".", 1)[-1] if "." in tok and not tok.startswith(".") else tok)
            tok = ""
        out.append(ch)
    return "".join(out).strip()


def attach_requirements(outcomes: dict[str, dict[str, Any]], requirements: list[dict[str, Any]], *,
                        unresolved: list[dict[str, Any]], dispositions: list[dict[str, Any]],
                        order: dict[str, tuple], outcome: Any) -> dict[str, str]:
    """Give every source requirement exactly one account (conservation).

    applicable      owned by the outcome that already owns the SAME work (a
                    finding cluster of the same class whose write scope holds
                    the requirement's primary path; several: the work list's
                    leaf-first order key, then the id -- never file order), a
                    captured behaviour outcome for an entry point, or a new
                    requirement outcome with its planned scope bounded by the
                    unit limits (UNIT_OVERSIZE otherwise). Its acceptance
                    becomes the owner's requirement_checks; the owner's budget
                    is NOT reset or widened.
    satisfied       a disposition carrying the receipt that applied it
    not-applicable  recorded, owns nothing
    unresolved      an explicit unresolved responsibility, never an empty plan

    Returns requirement id -> owner (outcome id, unresolved id, 'satisfied'
    or 'not-applicable')."""
    account: dict[str, str] = {}
    by_id = {_s(r.get("id")): r for r in requirements if isinstance(r, dict) and _s(r.get("id"))}
    _req(len(by_id) == len([r for r in requirements if isinstance(r, dict)]), "ADMISSION_INPUT", "duplicate or unnamed source requirement")
    unresolved_ids = {u["id"] for u in unresolved}

    def unresolved_for(r: dict[str, Any], kind: str, reason: str) -> str:
        rule = _s(r.get("rule")).split("/", 1)[0]
        if rule == "behavior-verification":
            typ, k = declaring_type(_s(r.get("subject")))
            uid = "unresolved:verification:%s:%s" % (k, typ)
            if uid in unresolved_ids:
                row = next(u for u in unresolved if u["id"] == uid)
                row.setdefault("requirements", []).append(r["id"])
                row["requirements"] = sorted(set(row["requirements"]))
                return uid
        uid = "unresolved:requirement:%s:%s" % (rule, hashlib.sha256(_s(r.get("subject")).encode("utf-8")).hexdigest()[:12])
        unresolved.append({"id": uid, "kind": kind, "blocks": "ship" if rule in ("behavior-verification", "adapter-behavior") else "delivery",
                           "reason": reason, "requirements": [r["id"]], "subject": _s(r.get("subject"))})
        unresolved_ids.add(uid)
        return uid

    for rq in sorted(by_id):
        r = by_id[rq]
        status = _s(r.get("status"))
        rule = _s(r.get("rule")).split("/", 1)[0]
        if status == "not-applicable":
            account[rq] = "not-applicable"
            continue
        if status == "satisfied":
            account[rq] = "satisfied"
            dispositions.append({"obligation_id": rq, "disposition": "satisfied",
                                 "reason": "applied before the baseline: %s" % (", ".join((r.get("facts") or {}).get("receipt") or []) or "the bootstrap receipt")})
            continue
        if status == "unresolved":
            account[rq] = unresolved_for(r, "requirement", "; ".join(r.get("unknowns") or []) or "unresolved")
            continue
        _req(status == "applicable", "ADMISSION_INPUT", "requirement %s status %r" % (rq, status))
        cls = _s(r.get("class")) or "source"
        _req(cls in CLASSES, "ADMISSION_UNSUPPORTED", "requirement %s class %r" % (rq, cls))
        owner = ""
        if rule == "behavior-verification":
            typ, k = declaring_type(_s(r.get("subject")))
            cand = "behavior:%s:%s" % (k, typ)
            if cand in outcomes:
                owner = cand
        elif r.get("paths"):
            primary = sorted(r.get("paths") or [])[0]
            cands = [oid for oid, o in outcomes.items() if o["class"] == cls and primary in o["plan_paths"]]
            if cands:
                owner = min(cands, key=lambda oid: (min((order.get(c, ("~",)) for c in outcomes[oid]["clusters"]), default=("~",)), oid))
        if not owner:
            paths = sorted(set(r.get("paths") or []))
            symbols = len((r.get("facts") or {}).get("members") or []) or len(paths)
            if len(paths) > REQ_UNIT_MAX_FILES or symbols > REQ_UNIT_MAX_SYMBOLS:
                account[rq] = unresolved_for(r, "blocked-cluster", "UNIT_OVERSIZE: requirement %s spans %d file(s) and %d symbol(s); "
                                             "the unit limits are %d and %d and one requirement is one coherent repair"
                                             % (rq, len(paths), symbols, REQ_UNIT_MAX_FILES, REQ_UNIT_MAX_SYMBOLS))
                continue
            short = hashlib.sha256(_s(r.get("subject")).encode("utf-8")).hexdigest()[:12]
            owner = "requirement:%s:%s" % (rule, short)
            subject = "%s %s" % (_REQ_WORDS.get(rule, rule), _simple(_s(r.get("subject"))))
            o = outcome(owner, cls, subject, "%s:%s" % (rule, _s(r.get("subject"))))
            o["plan_paths"].extend(paths)
            o["entry_points"].extend(_s(e) for e in r.get("consumers") or [] if _s(e).startswith("ep:"))
            o["_order"] = (json.dumps("~req"), json.dumps(rule), json.dumps(_s(r.get("subject"))))
            # the planned responsibility, not a write grant: the authority grants
            # one bounded unit at a time (outcome_lifecycle._allowed_paths)
            o["planned_units"] = [{"unit": 1, "paths": paths, "symbols": symbols, "grant": "none until issued"}]
        o = outcomes[owner]
        o.setdefault("requirements", []).append(rq)
        o.setdefault("_req_checks", []).extend(_s(c) for c in r.get("acceptance") or [])
        if r.get("recipe"):
            o.setdefault("_recipes", []).append("%s@%s" % (_s((r.get("recipe") or {}).get("id")), _s((r.get("recipe") or {}).get("version"))))
        account[rq] = owner
    # prerequisites between the owners of dependent requirements
    for rq, owner in account.items():
        if owner not in outcomes:
            continue
        for dep in by_id[rq].get("dependencies") or []:
            dep_owner = account.get(_s(dep), "")
            if dep_owner in outcomes and dep_owner != owner:
                outcomes[owner].setdefault("_req_parents", set()).add(dep_owner)
    lost = sorted(set(by_id) - set(account))
    _req(not lost, "REQUIREMENT_LOST", "source requirement(s) with no account: %s" % ", ".join(lost[:5]))
    return account


def _scc(edges: dict[str, set[str]]) -> dict[str, int]:
    """Tarjan: node -> component index (deterministic over sorted nodes)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on: set[str] = set()
    comp: dict[str, int] = {}
    counter = [0, 0]

    def strong(v: str) -> None:
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in sorted(edges.get(v, ())):
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            while True:
                w = stack.pop()
                on.discard(w)
                comp[w] = counter[1]
                if w == v:
                    break
            counter[1] += 1

    for v in sorted(edges):
        if v not in index:
            strong(v)
    return comp


def plan_digest(doc: dict[str, Any]) -> str:
    body = {k: v for k, v in doc.items() if k != "digest"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _acyclic(nodes: list[dict[str, Any]]) -> None:
    ids = {n["outcome_id"] for n in nodes}
    state: dict[str, int] = {}
    graph = {n["outcome_id"]: [p for p in n["parents"] if p in ids] for n in nodes}

    def visit(n: str, trail: list[str]) -> None:
        if state.get(n) == 2:
            return
        _req(state.get(n) != 1, "GRAPH_CYCLE", " -> ".join(trail + [n]))
        state[n] = 1
        for p in graph[n]:
            visit(p, trail + [n])
        state[n] = 2

    for n in sorted(graph):
        visit(n, [])
    for n in nodes:
        for p in n["parents"]:
            _req(p in ids or p == CONTROL_M2, "GRAPH_DANGLING", "%s parent %s" % (n["outcome_id"], p))


def topo_order(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Nodes in dependency order (parents first), ties by outcome id."""
    ids = {n["outcome_id"]: n for n in nodes}
    done: list[str] = []
    seen: set[str] = set()

    def visit(n: str) -> None:
        if n in seen:
            return
        seen.add(n)
        for p in sorted(ids[n]["parents"]):
            if p in ids:
                visit(p)
        done.append(n)

    for n in sorted(ids):
        visit(n)
    return [ids[n] for n in done]


def brief_document(plan: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    """The attachment a worker reads: membership, checks, lineage. Data only;
    it grants nothing (the authority recomputes every check)."""
    extra: dict[str, Any] = {}
    for key in ("requirements", "recipes", "planned_units"):
        if node.get(key):
            # plan semantics v1 only: the source requirements this outcome owns,
            # their qualified recipes and the planned (never granted) units
            extra[key] = copy.deepcopy(node[key])
    if node.get("requirements"):
        rows = {_s(r.get("id")): r for r in plan.get("requirements") or [] if isinstance(r, dict)}
        extra["requirement_rows"] = [copy.deepcopy(rows[r]) for r in node["requirements"] if r in rows]
    return dict(extra, **{
        "schema": "rhoai3.outcome-brief/v1",
        "run_id": plan["run_id"],
        "revision": plan["revision"],
        "plan_digest": plan["digest"],
        "outcome_id": node["outcome_id"],
        "role": node["role"],
        "class": node.get("class"),
        "title": node["title"],
        "obligations": list(node.get("obligations") or []),
        "clusters": list(node.get("clusters") or []),
        "entry_points": list(node.get("entry_points") or []),
        "scenarios": list(node.get("scenarios") or []),
        "plan_paths_descriptive_only": list(node.get("plan_paths") or []),
        "acceptance": dict(node.get("acceptance") or {}),
        "prerequisites": [p for p in node.get("parents") or []],
        "binding": dict(node.get("binding") or {}),
        "lineage": list(node.get("lineage") or []),
        "note": "Descriptive. Edits are granted per issued cluster by the authority, never by this file.",
    })


HANDLER_RULES = ("request-validation", "handler-parameter-binding", "behavior-verification")


def owner_of_finding(plan: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    """The frozen owner of a finding measured AFTER the initial plan (plan
    semantics v1), whatever order the destination revealed it in.

      obligation   the plan already owns this obligation id
      requirement  a planned requirement's scope holds the finding's locus
                   (its file, or for a behaviour finding its entry point):
                   one owner, so a defect seen through several endpoints or
                   checkpoints keeps that owner and its budget
      none         no planned owner: a TYPED revision class instead of an
                   arbitrary attachment -- previously-unknown-behavior (a
                   behaviour finding), evidence-gap (an environment or
                   unlocatable finding), missing-planning-rule (anything
                   else), or ambiguous-ownership (two owners claim the locus)
    Pure; grants nothing."""
    iid = _s(item.get("id"))
    own = plan.get("ownership") or {}
    if iid and iid in own:
        return {"owner": own[iid], "resolution": "obligation"}
    path = _s(item.get("path"))
    ep = _s(item.get("entry_point"))
    repair = {n["outcome_id"]: n for n in plan.get("nodes") or [] if n.get("role") == "repair" and n.get("requirements")}
    hits: set[str] = set()
    if path:
        hits = {oid for oid, n in repair.items() if path in (n.get("plan_paths") or [])}
    elif ep:
        # a behaviour finding at an entry point: the handler-level requirement
        # that serves it owns it; a generator or adapter requirement that only
        # lists the endpoint as a consumer owns it only when nothing closer does
        acct = plan.get("requirement_ownership") or {}
        near: set[str] = set()
        far: set[str] = set()
        for r in plan.get("requirements") or []:
            if ep in (r.get("consumers") or []) and acct.get(_s(r.get("id"))) in repair:
                (near if _s(r.get("rule")).split("/", 1)[0] in HANDLER_RULES else far).add(acct[_s(r.get("id"))])
        hits = near or far
    if len(hits) == 1:
        return {"owner": next(iter(hits)), "resolution": "requirement"}
    if len(hits) > 1:
        return {"owner": None, "class": "ambiguous-ownership", "candidates": sorted(hits)}
    if _s(item.get("kind")) == "parity" or ep:
        cls = "previously-unknown-behavior"
    elif _s(item.get("kind")) in ("environment", "unlocatable") or _s(item.get("cause")) == "environment":
        cls = "evidence-gap"
    else:
        cls = "missing-planning-rule"
    return {"owner": None, "class": cls}


def resolve_identities(frozen: dict[str, dict[str, Any]], derived: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map each derived repair group onto a frozen outcome.

    frozen:  outcome_id -> {"obligations": [...], "natural_key": str, "aliases": [...]}
    derived: groups with outcome_id, natural_key, obligations.
    Returns derived outcome_id -> {"outcome_id": frozen or new id, "resolution": ...}.
    A group sharing obligations with exactly one frozen outcome IS that outcome.
    Sharing with two refuses IDENTITY_AMBIGUOUS. No overlap: the natural key or an
    alias of a frozen outcome; otherwise a new outcome (an explicit addition)."""
    by_ob: dict[str, str] = {}
    for fid, f in frozen.items():
        for ob in f.get("obligations") or []:
            by_ob[str(ob)] = fid
    by_nat: dict[str, str] = {}
    for fid, f in frozen.items():
        for nat in [f.get("natural_key")] + list(f.get("aliases") or []):
            if nat:
                by_nat[str(nat)] = fid
    out: dict[str, dict[str, Any]] = {}
    claimed: dict[str, str] = {}
    for g in derived:
        hits = sorted({by_ob[ob] for ob in g.get("obligations") or [] if ob in by_ob})
        _req(len(hits) <= 1, "IDENTITY_AMBIGUOUS", "%s spans frozen outcomes %s" % (g["outcome_id"], ", ".join(hits)))
        if hits:
            target, how = hits[0], "obligations"
        elif g.get("natural_key") in by_nat:
            target, how = by_nat[g["natural_key"]], "natural-key"
        elif g["outcome_id"] in frozen:
            target, how = g["outcome_id"], "id"
        else:
            target, how = g["outcome_id"], "new"
        _req(target not in claimed or how == "new", "IDENTITY_AMBIGUOUS",
             "%s and %s both resolve to %s" % (claimed.get(target), g["outcome_id"], target))
        claimed[target] = g["outcome_id"]
        out[g["outcome_id"]] = {"outcome_id": target, "resolution": how}
    return out
