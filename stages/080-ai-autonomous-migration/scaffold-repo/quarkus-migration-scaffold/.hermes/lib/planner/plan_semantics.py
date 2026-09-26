"""Semantic identity of the initial M3 plan (plan semantics v1).

The same frozen application, migration decisions and pinned toolchain must
produce the same initial logical M3 plan. The exact evidence digests the
admission receipt seals (evidence bundle, work list, bootstrap, contracts,
pins) answer a different question -- "is this the very state that was
admitted?" -- and they rightly move with an elapsed time, a candidate digest
or a producer receipt path. This module answers the planning question beside
them, never instead of them:

  input fingerprint   one digest per planning input, in producer order, each
                      with its completeness and named unknowns; an input that
                      is missing or partial is UNKNOWN, never zero
  plan projection     an explicit projection of the planning fields of the
                      work list, the source-derived requirements and the
                      initial outcome graph: obligation identities and
                      memberships, write scopes, recipes, dependencies,
                      acceptance and unresolved responsibilities. Audit
                      facts (run id, budget keys, timestamps, tool durations,
                      candidate bindings, receipt and file digests, producer
                      paths) are carried separately and never enter the plan
                      fingerprint
  comparison          classified differences with the FIRST divergent producer,
                      not merely two unequal hashes

Mathematical sets are sorted; orders that mean something (a cluster's order
key, a node's parents after sorting, a recipe's steps) are kept. Nothing here
normalizes away a real difference: two obligations stay two.

The document is a description, not a plan: it grants nothing, issues nothing
and is never a queue (the work list and the outcome store remain the only
executable records). No LLM, no clock, no environment in any digested field.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from planner.canonical import digest, load_json, sha256_file
from planner.paths import (
    BOOTSTRAP_RECEIPT,
    DECIDED_REPAIRS_RECEIPT,
    EVIDENCE_BUNDLE,
    VERIFY_DIAGNOSTICS,
    VERIFY_RUN,
    WORKLIST,
    contract_files,
)

SCHEMA = "rhoai3.plan-semantics/v1"
MODE_V1 = "v1"

# Producer order: the first component that differs is the first divergent
# producer. Tool/contract versions come first because a version change
# explains every later difference.
INPUT_ORDER = ("planner", "contracts", "pins", "tools", "decisions", "source", "build", "structure",
               "entry_points", "mta", "oracles", "bootstrap", "decided_repairs", "diagnostics", "verification")
PLAN_ORDER = ("worklist", "requirements", "graph")
VERSION_INPUTS = frozenset({"planner", "contracts", "pins", "tools"})

# Planner code whose content decides the plan (tests and fixture builders are
# not part of it). Paths relative to the destination root.
PLANNER_CODE = (
    ".hermes/lib/planner",
    ".hermes/lib/response_adapters.py",
    ".hermes/skills/migration/fix-until-green/scripts/jdk-diagnostics/JdkDiagnostics.java",
    ".hermes/skills/migration/fix-until-green/scripts/jdk-dest-model/DestModel.java",
    ".hermes/skills/migration/bootstrap-destination/scripts/_decided_repairs.py",
    ".hermes/skills/migration/bootstrap-destination/scripts/java-structure/JavaStructure.java",
)
_NOT_PLANNER = ("specimens.py",)

# Work-list fields that are exact audit evidence, not planning content.
WORKLIST_AUDIT = ("sources", "evidence_bundle_sha256", "candidate_sha256", "runtime")
ITEM_AUDIT = ("detail", "message", "message_sha256", "generated_path", "observed")
CLUSTER_AUDIT = ("batch_scope",)
NODE_AUDIT = ("description",)


class SemanticsError(ValueError):
    pass


def _read(path: Path) -> Any:
    try:
        return load_json(path)
    except (OSError, ValueError):
        return None


def _component(value: Any, *, complete: bool = True, unknowns: list[str] | None = None) -> dict[str, Any]:
    return {"digest": digest(value), "complete": bool(complete), "unknowns": sorted(set(unknowns or []))}


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------

def planner_code_digest(root: Path) -> dict[str, Any]:
    root = Path(root)
    rows: dict[str, str] = {}
    missing: list[str] = []
    for rel in PLANNER_CODE:
        p = root / rel
        if p.is_dir():
            for f in sorted(p.glob("*.py")):
                if f.name.endswith(".test.py") or f.name in _NOT_PLANNER:
                    continue
                rows[f.relative_to(root).as_posix()] = sha256_file(f)
        elif p.is_file():
            rows[rel] = sha256_file(p)
        else:
            missing.append("%s is absent" % rel)
    return _component(rows, complete=not missing, unknowns=missing)


def _mta_semantic(bundle: dict[str, Any]) -> dict[str, Any]:
    mta = dict(bundle.get("mta") or {})
    # the output file's digest and the process exit status are audit: the
    # normalized obligations below are what the plan is made of
    for k in ("output_digest", "exit_status"):
        mta.pop(k, None)
    return {"mta": mta, "obligations": bundle.get("obligations") or []}


def _decided_rows(doc: Any) -> list[dict[str, Any]]:
    rows = []
    for r in (doc or {}).get("rows") or (doc or {}).get("transformations") or []:
        if not isinstance(r, dict):
            continue
        rows.append({"id": r.get("id"), "adr": r.get("adr"), "kind": r.get("kind"), "status": r.get("status"),
                     "files": sorted(r.get("files") or []), "symbols": sorted(r.get("symbols") or []),
                     "outputs": r.get("outputs") or {}, "refusal": ((r.get("refusal") or {}).get("class") if isinstance(r.get("refusal"), dict) else None)})
    return sorted(rows, key=lambda r: str(r.get("id")))


def input_components(root: Path, *, bundle: dict[str, Any] | None = None, decisions: dict[str, Any] | None = None,
                     oracles: dict[str, list[str]] | None = None, oracles_known: bool = True) -> dict[str, dict[str, Any]]:
    """One semantic component per planning input (INPUT_ORDER)."""
    root = Path(root)
    if bundle is None:
        bundle = _read(root / EVIDENCE_BUNDLE)
    if not isinstance(bundle, dict):
        raise SemanticsError("%s is missing or malformed; the planning inputs are unknown" % EVIDENCE_BUNDLE)
    if decisions is None:
        try:
            from planner.decisions import load_decisions
            decisions = load_decisions(root)
        except (OSError, ValueError):
            decisions = None
    out: dict[str, dict[str, Any]] = {}
    out["planner"] = planner_code_digest(root)
    out["contracts"] = _component({p.relative_to(root).as_posix(): sha256_file(p) for p in contract_files(root)})
    try:
        from planner.pins import digestable_pins, load_pins
        pins = digestable_pins(load_pins(root))
        # activation is admission authority, not a planning input
        pins.pop("planner", None)
        out["pins"] = _component(pins)
    except (OSError, ValueError) as exc:
        out["pins"] = _component(None, complete=False, unknowns=["pins unreadable: %s" % exc])
    producers = bundle.get("producers") or {}
    tools = {n: (r.get("tool") if isinstance(r, dict) else None) for n, r in sorted(producers.items())}
    missing_tools = sorted(n for n, r in producers.items() if not isinstance(r, dict) or str(r.get("status")) in ("missing", ""))
    out["tools"] = _component(tools, complete=not missing_tools, unknowns=["producer %s did not run" % n for n in missing_tools])
    out["decisions"] = _component(decisions, complete=decisions is not None,
                                  unknowns=[] if decisions is not None else ["decisions.yaml missing or invalid"])
    out["source"] = _component(bundle.get("source") or {}, complete=bool((bundle.get("source") or {}).get("digest")))
    build = bundle.get("build") or {}
    out["build"] = _component(build, complete=str(build.get("outcome")) == "success",
                              unknowns=[] if str(build.get("outcome")) == "success" else ["source build outcome %r" % build.get("outcome")])
    st = bundle.get("structure") or {}
    st_unknown = []
    if not st.get("available"):
        st_unknown.append("no admitted structural model")
    elif str(st.get("mode")) != "full":
        st_unknown.append("structural model mode %r (partial facts: absence is not evidence)" % st.get("mode"))
    partial_types = sorted(str(t.get("fqn")) for t in st.get("types") or [] if isinstance(t, dict) and str(t.get("resolution") or "full") != "full")
    if partial_types:
        st_unknown.append("%d type(s) only partially resolved: %s" % (len(partial_types), ", ".join(partial_types[:5])))
    out["structure"] = _component({"available": st.get("available"), "mode": st.get("mode"), "types": st.get("types") or []},
                                  complete=not st_unknown, unknowns=st_unknown)
    out["entry_points"] = _component(bundle.get("entry_points") or [], complete=bool(st.get("available")))
    mta = bundle.get("mta") or {}
    out["mta"] = _component(_mta_semantic(bundle), complete=str(mta.get("status")) == "ok",
                            unknowns=[] if str(mta.get("status")) == "ok" else ["MTA producer status %r" % mta.get("status")])
    norm_oracles = {str(k): sorted({str(s) for s in v or []}) for k, v in (oracles or {}).items()}
    out["oracles"] = _component(norm_oracles, complete=oracles_known,
                                unknowns=[] if oracles_known else ["no captured scenario corpus: behavior coverage is unresolved"])
    bs = _read(root / BOOTSTRAP_RECEIPT)
    if isinstance(bs, dict):
        b = {k: v for k, v in bs.items() if k not in ("inputs", "path", "observations")}
        out["bootstrap"] = _component(b, complete=str(bs.get("status")) == "ok",
                                      unknowns=[] if str(bs.get("status")) == "ok" else ["bootstrap status %r" % bs.get("status")])
    else:
        out["bootstrap"] = _component(None, complete=False, unknowns=["bootstrap receipt missing"])
    dr = _read(root / DECIDED_REPAIRS_RECEIPT)
    out["decided_repairs"] = _component(_decided_rows(dr) if isinstance(dr, dict) else None)
    diags = _read(root / VERIFY_DIAGNOSTICS)
    d_unknown: list[str] = []
    if not isinstance(diags, dict):
        d_unknown.append("no compiler diagnostics")
        dprov: Any = None
    else:
        dprov = {k: diags.get(k) for k in ("rendering_locale", "args_available", "output_classes_on_classpath",
                                           "generated_roots", "build_unresolvable", "success", "errors")}
        if str(diags.get("rendering_locale") or "") != "root":
            d_unknown.append("diagnostic text rendered in an unpinned locale (older producer)")
        if diags.get("output_classes_on_classpath"):
            d_unknown.append("target/classes was on the analysis classpath (orphan classes can hide errors)")
        if diags.get("build_unresolvable"):
            d_unknown.append("build unresolvable: %s" % str(diags.get("reason") or "")[:120])
    out["diagnostics"] = _component(dprov, complete=not d_unknown, unknowns=d_unknown)
    run = _read(root / VERIFY_RUN)
    if isinstance(run, dict):
        v = {k: ({kk: vv for kk, vv in (run.get(k) or {}).items() if kk in ("ran", "rc", "build_unresolvable", "skipped")}
                 if isinstance(run.get(k), dict) else run.get(k))
             for k in ("mode", "diagnostics", "tests", "rescan", "initial_preparation")}
        out["verification"] = _component(v)
    else:
        out["verification"] = _component(None, complete=False, unknowns=["verification run record missing"])
    return {k: out[k] for k in INPUT_ORDER}


# ---------------------------------------------------------------------------
# projections
# ---------------------------------------------------------------------------

def _strip(d: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k not in keys}


def worklist_projection(worklist: dict[str, Any]) -> dict[str, Any]:
    """The planning content of a work list: obligations, clusters (membership,
    write scope, order, status), the measure's knowledge and dispositions.
    Evidence file digests, candidate bindings and runtime receipts are audit."""
    if not isinstance(worklist, dict):
        raise SemanticsError("work list missing or malformed")
    items = sorted((_strip(i, ITEM_AUDIT) for i in worklist.get("items") or [] if isinstance(i, dict)), key=lambda i: str(i.get("id")))
    clusters = []
    for c in worklist.get("clusters") or []:
        if not isinstance(c, dict):
            continue
        row = _strip(c, CLUSTER_AUDIT)
        bs = c.get("batch_scope") if isinstance(c.get("batch_scope"), dict) else None
        if bs:
            # the seal's own digest binds the candidate; its rule and shape are planning
            row["batch_scope"] = {k: bs.get(k) for k in ("rule", "kind", "family_id", "unit_id", "members")}
        row["items"] = sorted(row.get("items") or [])
        row["write_set"] = sorted(row.get("write_set") or [])
        clusters.append(row)
    measure = dict(worklist.get("measure") or {})
    measure["blocked"] = sorted(str(b) for b in measure.get("blocked") or [])
    out = {k: v for k, v in worklist.items() if k not in WORKLIST_AUDIT and k not in ("items", "clusters", "measure")}
    out["items"] = items
    out["clusters"] = clusters  # the former's order is the serial order: kept
    out["measure"] = measure
    for k in ("deferred", "blocked_clusters"):
        out[k] = sorted(out.get(k) or [])
    out["not_counted"] = sorted(out.get("not_counted") or [], key=lambda r: str((r or {}).get("id")))
    out["unlocatable"] = sorted(out.get("unlocatable") or [], key=lambda r: str((r or {}).get("id")))
    ho = out.get("harness_owned")
    if isinstance(ho, dict):
        out["harness_owned"] = dict(ho, findings=sorted(ho.get("findings") or [], key=lambda r: str((r or {}).get("id"))))
    return out


def graph_projection(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    """The logical initial outcome graph without its run binding: the run id,
    the provenance receipt digests, the budget KEY (run-scoped) and the
    revision digest are audit; the budget limit is planning."""
    if plan is None:
        return None
    nodes = []
    for n in plan.get("nodes") or []:
        row = _strip(copy.deepcopy(n), NODE_AUDIT)
        if isinstance(row.get("budget"), dict):
            row["budget"] = {k: v for k, v in row["budget"].items() if k != "key"}
        for k in ("obligations", "clusters", "plan_paths", "entry_points", "scenarios", "parents", "requirements"):
            if isinstance(row.get(k), list):
                row[k] = sorted(row[k])
        nodes.append(row)
    nodes.sort(key=lambda n: str(n.get("outcome_id")))
    return {"schema": plan.get("schema"), "kind": plan.get("kind"), "nodes": nodes,
            "ownership": dict(sorted((plan.get("ownership") or {}).items())),
            "dispositions": plan.get("dispositions") or [], "unresolved": plan.get("unresolved") or [],
            "counts": plan.get("counts") or {}, "requirements": plan.get("requirements") or []}


def graph_audit(plan: dict[str, Any] | None) -> dict[str, Any]:
    if plan is None:
        return {}
    return {"run_id": plan.get("run_id"), "digest": plan.get("digest"), "provenance": plan.get("provenance"),
            "budget_keys": {n["outcome_id"]: (n.get("budget") or {}).get("key") for n in plan.get("nodes") or [] if n.get("budget")}}


# ---------------------------------------------------------------------------
# the document
# ---------------------------------------------------------------------------

def compose(*, inputs: dict[str, dict[str, Any]], worklist: dict[str, Any], requirements: list[dict[str, Any]] | None,
            graph: dict[str, Any] | None, audit: dict[str, Any] | None = None) -> dict[str, Any]:
    """The semantic plan document. Pure over its arguments."""
    plan = {"worklist": worklist_projection(worklist),
            "requirements": sorted(requirements or [], key=lambda r: str(r.get("id"))),
            "graph": graph_projection(graph)}
    doc = {
        "schema": SCHEMA,
        "inputs": {k: inputs[k] for k in INPUT_ORDER if k in inputs},
        "plan": plan,
        "input_fingerprint": digest({k: inputs[k]["digest"] for k in INPUT_ORDER if k in inputs}),
        "plan_fingerprint": digest(plan),
        "complete": all(inputs[k].get("complete") for k in inputs),
        "unknowns": sorted({"%s: %s" % (k, u) for k in inputs for u in inputs[k].get("unknowns") or []}),
        # exact evidence and run binding: reported, compared as audit only,
        # never part of either fingerprint
        "audit": dict(audit or {}, graph=graph_audit(graph), worklist_digest=digest(worklist)),
        "note": "descriptive: grants nothing, issues nothing; the work list and the outcome store stay the executable records",
    }
    return doc


def initial_graph(root: Path, worklist: dict[str, Any], *, requirements: list[dict[str, Any]] | None,
                  oracles: dict[str, list[str]] | None, run_id: str = "semantic") -> tuple[dict[str, Any] | None, str]:
    """Revision 1 exactly as the outcome board derives it (the ONE initial
    graph builder, outcome_graph.derive_initial_graph), from this root's
    admission-time evidence; (None, why) when the evidence does not allow a
    plan. The run id only names budget keys, which the projection drops."""
    from planner.decisions import load_decisions, max_attempts
    from planner.outcome_graph import PlanError, derive_initial_graph
    from planner.outcome_lifecycle import EP_INVENTORY, _references

    inv = _read(Path(root) / EP_INVENTORY)
    if not isinstance(inv, dict) or not isinstance(inv.get("entry_points"), list):
        return None, "ADMISSION_EVIDENCE_INCOMPLETE: %s is missing or malformed" % EP_INVENTORY
    try:
        dec = load_decisions(root)
    except (OSError, ValueError):
        dec = {}
    try:
        g = derive_initial_graph(run_id=run_id, worklist=worklist, entry_points=inv["entry_points"], oracles=oracles,
                                 references=_references(root), max_attempts=max_attempts(dec),
                                 provenance={"snapshot_kind": "admission", "scope_note": "semantic projection of this root's admission-time evidence"},
                                 requirements=requirements)
    except PlanError as exc:
        return None, "%s: %s" % (exc.code, exc.detail)
    return g, ""


def from_root(root: Path, *, run_id: str = "semantic", worklist: dict[str, Any] | None = None) -> dict[str, Any]:
    """The semantic document of a destination root's initial plan.

    Every input is read from the root's own M1/M2 records; the requirements
    come from planner.source_requirements and the graph from
    derive_initial_graph -- production consumers, never a hand-authored plan.
    A graph the evidence does not allow is recorded as an unknown, never as an
    empty plan."""
    from planner.outcome_lifecycle import _oracles

    root = Path(root)
    if worklist is None:
        worklist = _read(root / WORKLIST)
    if not isinstance(worklist, dict):
        raise SemanticsError("%s is missing or malformed" % WORKLIST)
    from planner import source_requirements

    oracles = _oracles(root)
    inputs = input_components(root, oracles=oracles or {}, oracles_known=oracles is not None)
    reqs = source_requirements.for_root(root, oracles=oracles)
    graph, why = initial_graph(root, worklist, requirements=reqs["requirements"], oracles=oracles, run_id=run_id)
    doc = compose(inputs=inputs, worklist=worklist, requirements=reqs["requirements"], graph=graph,
                  audit={"root": str(root), "bundle_sha256": sha256_file(root / EVIDENCE_BUNDLE) if (root / EVIDENCE_BUNDLE).is_file() else ""})
    if reqs.get("unknowns"):
        doc["unknowns"] = sorted(set(doc["unknowns"]) | {"requirements: %s" % u for u in reqs["unknowns"]})
        doc["complete"] = False
    if graph is None:
        doc["unknowns"] = sorted(set(doc["unknowns"]) | {"graph: %s" % why})
        doc["complete"] = False
    return doc


def contract(root: Path) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """Admission's plan-semantics v1 check: the semantic document and every
    reason it may not be admitted (typed blocks). The exact evidence checks of
    planner.admission still run; this adds, never replaces.

      PLAN_SEMANTICS_UNDERIVABLE  the planning inputs cannot be read
      PLAN_CONTRACT               the one graph builder refused the plan
                                  (conservation, scope bound, cycle, lost
                                  requirement, ...): its own code is kept
      PLAN_ACCEPTANCE_MISSING     an applicable requirement names no check
      PLAN_RECIPE_MISSING         an applicable REPAIR requirement
                                  (source_requirements.RECIPE_RULES) has no
                                  qualified recipe; verification and decided
                                  configuration are judged by their checks
    Unresolved requirements are not blocks here: like a missing oracle they
    are named responsibilities that block delivery, never an empty plan."""
    from planner.source_requirements import RECIPE_RULES
    blocks: list[dict[str, str]] = []
    try:
        doc = from_root(root)
    except (SemanticsError, OSError, ValueError) as exc:
        return None, [{"class": "PLAN_SEMANTICS_UNDERIVABLE", "subject": "plan-semantics", "detail": str(exc)[:300]}]
    for u in doc.get("unknowns") or []:
        if u.startswith("graph: "):
            code = u[len("graph: "):].split(":", 1)[0]
            blocks.append({"class": "PLAN_CONTRACT", "subject": code, "detail": u[len("graph: "):][:300]})
    for r in doc["plan"]["requirements"]:
        if r.get("status") != "applicable":
            continue
        if not r.get("acceptance"):
            blocks.append({"class": "PLAN_ACCEPTANCE_MISSING", "subject": r["id"], "detail": "an applicable requirement names no completion check"})
        if not r.get("recipe") and str(r.get("rule") or "").split("/", 1)[0] in RECIPE_RULES:
            blocks.append({"class": "PLAN_RECIPE_MISSING", "subject": r["id"], "detail": "an applicable repair requirement has no qualified recipe"})
    return doc, blocks


def frozen(root: Path) -> dict[str, Any] | None:
    """The initial plan's semantic document once an ADMITTED receipt froze it
    (pipeline.admit), or None before that."""
    from planner.paths import PLAN_SEMANTICS

    doc = _read(Path(root) / PLAN_SEMANTICS)
    return doc if isinstance(doc, dict) and doc.get("frozen") is True and doc.get("schema") == SCHEMA else None


def seal_of(doc: dict[str, Any]) -> dict[str, str]:
    return {"schema": SCHEMA, "input_fingerprint": doc["input_fingerprint"], "plan_fingerprint": doc["plan_fingerprint"],
            "semantic_digest": semantic_digest(doc)}


def seal_gaps(root: Path, seal: dict[str, Any]) -> list[str]:
    """The file admission wrote still carries the sealed semantics and its
    fingerprints still cover its own content (a tampered or replaced file
    fails)."""
    from planner.paths import PLAN_SEMANTICS

    doc = _read(Path(root) / PLAN_SEMANTICS)
    if not isinstance(doc, dict):
        return ["%s is missing after admission" % PLAN_SEMANTICS]
    gaps = []
    if digest(doc.get("plan")) != doc.get("plan_fingerprint"):
        gaps.append("plan semantics: the plan fingerprint does not cover the file's plan")
    if digest({k: (doc.get("inputs") or {}).get(k, {}).get("digest") for k in INPUT_ORDER if k in (doc.get("inputs") or {})}) != doc.get("input_fingerprint"):
        gaps.append("plan semantics: the input fingerprint does not cover the file's inputs")
    for k in ("input_fingerprint", "plan_fingerprint"):
        if doc.get(k) != seal.get(k):
            gaps.append("plan semantics %s %s != sealed %s" % (k, str(doc.get(k))[:12], str(seal.get(k))[:12]))
    return gaps


def plan_view(doc: dict[str, Any], *, protocol: str, revisions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The one derived human-readable view of the plan: each planned M3
    outcome, why it exists, its prerequisites, recipes, bounded units,
    completion checks and unresolved conditions; the M4/M5 milestones by their
    existing titles. It grants nothing and is never a queue. On a serial-loop
    run it is observational: that run executes the serial loop, not pre-minted
    outcomes.

    Without `revisions` it is STRICTLY the frozen initial plan (scope
    "frozen-initial-plan"): it says nothing about additions or what is
    unfinished, because the frozen document cannot know. With the outcome
    store's recorded plan revisions (oldest first, each {"rev", "doc"}), the
    additions are the repair outcomes a later revision carries that the
    initial one did not, with the revision that added them and their lineage
    (round 3: no hard-coded empty field)."""
    g = (doc.get("plan") or {}).get("graph") or {}
    reqs = {r["id"]: r for r in (doc.get("plan") or {}).get("requirements") or []}
    nodes = g.get("nodes") or []
    titles = {n["outcome_id"]: n.get("title") for n in nodes}
    outcomes, milestones = [], []
    for n in nodes:
        if n.get("role") != "repair":
            milestones.append({"outcome_id": n["outcome_id"], "title": n.get("title"),
                               "after": [titles.get(p, p) for p in n.get("parents") or [] if p in titles]})
            continue
        why = ["%d measured obligation(s)" % len(n.get("obligations") or [])] if n.get("obligations") else []
        why += ["%s: %s" % (reqs[r]["rule"].split("/", 1)[0], reqs[r]["subject"]) for r in n.get("requirements") or [] if r in reqs]
        outcomes.append({
            "outcome_id": n["outcome_id"], "title": n.get("title"), "class": n.get("class"), "why": why,
            "after": [titles.get(p, p) for p in n.get("parents") or [] if p in titles],
            "recipes": list(n.get("recipes") or []),
            "units": ([{"cluster": c} for c in n.get("clusters") or []] + list(n.get("planned_units") or [])),
            "completion_checks": list((n.get("acceptance") or {}).get("checks") or []) + list((n.get("acceptance") or {}).get("requirement_checks") or []),
            "budget_limit": (n.get("budget") or {}).get("limit"),
        })
    counts = g.get("counts") or {}
    return {
        "schema": "rhoai3.plan-view/v1",
        "protocol": protocol,
        "observational": protocol != "outcome-board/v1",
        "note": ("derived from evidence/planning/plan-semantics.json; grants nothing and is not a queue"
                 + ("; this run executes the serial loop, so the outcomes below are the planned responsibilities, not pre-minted cards"
                    if protocol != "outcome-board/v1" else "; the outcome store and K4 publication remain the executable records")),
        "plan_fingerprint": doc.get("plan_fingerprint"),
        "input_fingerprint": doc.get("input_fingerprint"),
        "scope": "frozen-initial-plan" if revisions is None else "initial-plan-and-recorded-revisions",
        "baseline": outcomes,
        **({} if revisions is None else {"additions": _additions(revisions)}),
        "milestones": milestones,
        "unresolved": [{"id": u["id"], "blocks": u.get("blocks"), "reason": u.get("reason")} for u in g.get("unresolved") or []],
        "counts": {"baseline_outcomes": counts.get("baseline_outcomes"), "requirements": counts.get("requirements") or {},
                   "unresolved": counts.get("unresolved")},
        "unknowns": list(doc.get("unknowns") or []),
    }


def _additions(revisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Repair outcomes of later recorded revisions that revision 1 did not
    have: the first revision that carries each, and its lineage."""
    revs = sorted((r for r in revisions or [] if isinstance(r, dict) and isinstance(r.get("doc"), dict)),
                  key=lambda r: int(r.get("rev") or 0))
    if not revs:
        return []
    seen = {n.get("outcome_id") for n in revs[0]["doc"].get("nodes") or [] if n.get("role") == "repair"}
    out = []
    for r in revs[1:]:
        for n in r["doc"].get("nodes") or []:
            oid = n.get("outcome_id")
            if n.get("role") != "repair" or oid in seen:
                continue
            seen.add(oid)
            out.append({"outcome_id": oid, "title": n.get("title"), "added_in_revision": int(r.get("rev") or 0),
                        "lineage": n.get("lineage") or {}, "revision_class": (n.get("lineage") or {}).get("class") or n.get("revision_class")})
    return out


def semantic_digest(doc: dict[str, Any]) -> str:
    """input fingerprint + plan fingerprint: what 'same initial plan for
    equivalent pinned inputs' is asked of."""
    return digest({"input_fingerprint": doc.get("input_fingerprint"), "plan_fingerprint": doc.get("plan_fingerprint")})


# ---------------------------------------------------------------------------
# comparison
# ---------------------------------------------------------------------------

def _by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(r.get(key)): r for r in rows or [] if isinstance(r, dict)}


def _diff_rows(where: str, a: list[dict[str, Any]], b: list[dict[str, Any]], key: str,
               fields: dict[str, str], added: str, removed: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    ma, mb = _by(a, key), _by(b, key)
    for k in sorted(set(mb) - set(ma)):
        out.append({"class": added, "where": where, "id": k})
    for k in sorted(set(ma) - set(mb)):
        out.append({"class": removed, "where": where, "id": k})
    for k in sorted(set(ma) & set(mb)):
        ra, rb = ma[k], mb[k]
        seen = set()
        for f, cls in fields.items():
            if ra.get(f) != rb.get(f):
                out.append({"class": cls, "where": where, "id": k, "field": f})
                seen.add(f)
        rest = sorted(f for f in set(ra) | set(rb) if f not in seen and f not in fields and ra.get(f) != rb.get(f))
        if rest:
            out.append({"class": "changed", "where": where, "id": k, "fields": rest})
    return out


ITEM_FIELDS = {"kind": "membership", "category": "disposition", "path": "scope", "rule_id": "recipe",
               "identity_confidence": "evidence-quality", "gate": "acceptance"}
CLUSTER_FIELDS = {"items": "membership", "write_set": "scope", "order_key": "dependencies", "status": "disposition",
                  "kind": "membership", "gate": "acceptance", "batch_scope": "scope"}
REQ_FIELDS = {"status": "disposition", "recipe": "recipe", "dependencies": "dependencies", "acceptance": "acceptance",
              "paths": "scope", "evidence": "evidence-quality", "unknowns": "evidence-quality", "phase": "recipe"}
NODE_FIELDS = {"obligations": "membership", "clusters": "membership", "plan_paths": "scope", "parents": "dependencies",
               "acceptance": "acceptance", "requirements": "recipe", "recipes": "recipe", "budget": "budget",
               "entry_points": "membership", "scenarios": "acceptance"}


def compare(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Classified differences between two semantic documents.

    classes: input-version (planner/contract/pin/tool versions), input (a
    planning input's content), evidence-quality (completeness, unknowns,
    identity confidence, measure knowledge), outcome-added / outcome-removed,
    obligation-added / obligation-removed, requirement-added /
    requirement-removed, membership, scope, recipe, dependencies, acceptance,
    disposition, budget, changed; and audit-only (never makes plans unequal)."""
    diffs: list[dict[str, Any]] = []
    first = ""
    if a.get("schema") != b.get("schema"):
        diffs.append({"class": "input-version", "where": "schema", "a": a.get("schema"), "b": b.get("schema")})
        first = "schema"
    ia, ib = a.get("inputs") or {}, b.get("inputs") or {}
    for k in INPUT_ORDER:
        ca, cb = ia.get(k) or {}, ib.get(k) or {}
        if ca.get("digest") != cb.get("digest"):
            diffs.append({"class": "input-version" if k in VERSION_INPUTS else "input", "where": "inputs.%s" % k})
            first = first or k
        if ca.get("complete") != cb.get("complete") or ca.get("unknowns") != cb.get("unknowns"):
            diffs.append({"class": "evidence-quality", "where": "inputs.%s" % k,
                          "a": {"complete": ca.get("complete"), "unknowns": ca.get("unknowns")},
                          "b": {"complete": cb.get("complete"), "unknowns": cb.get("unknowns")}})
            first = first or k
    pa, pb = a.get("plan") or {}, b.get("plan") or {}
    wa, wb = pa.get("worklist") or {}, pb.get("worklist") or {}
    wl = _diff_rows("worklist.items", wa.get("items") or [], wb.get("items") or [], "id", ITEM_FIELDS, "obligation-added", "obligation-removed")
    wl += _diff_rows("worklist.clusters", wa.get("clusters") or [], wb.get("clusters") or [], "id", CLUSTER_FIELDS, "outcome-added", "outcome-removed")
    if [c.get("id") for c in wa.get("clusters") or []] != [c.get("id") for c in wb.get("clusters") or []] and not any(d["where"] == "worklist.clusters" and d["class"].startswith("outcome") for d in wl):
        wl.append({"class": "dependencies", "where": "worklist.clusters", "detail": "serial order differs"})
    if (wa.get("measure") or {}) != (wb.get("measure") or {}):
        wl.append({"class": "evidence-quality", "where": "worklist.measure", "a": wa.get("measure"), "b": wb.get("measure")})
    for k in sorted((set(wa) | set(wb)) - {"items", "clusters", "measure"}):
        if wa.get(k) != wb.get(k):
            wl.append({"class": "disposition" if k in ("deferred", "blocked_clusters", "not_counted", "unlocatable", "harness_owned") else "changed",
                       "where": "worklist.%s" % k})
    if wl:
        first = first or "worklist"
    diffs += wl
    rq = _diff_rows("requirements", pa.get("requirements") or [], pb.get("requirements") or [], "id", REQ_FIELDS,
                    "requirement-added", "requirement-removed")
    if rq:
        first = first or "requirements"
    diffs += rq
    ga, gb = pa.get("graph") or {}, pb.get("graph") or {}
    gr = _diff_rows("graph.nodes", ga.get("nodes") or [], gb.get("nodes") or [], "outcome_id", NODE_FIELDS, "outcome-added", "outcome-removed")
    for k in ("ownership", "dispositions", "unresolved"):
        if ga.get(k) != gb.get(k):
            gr.append({"class": "membership" if k == "ownership" else "disposition", "where": "graph.%s" % k})
    if gr:
        first = first or "graph"
    diffs += gr
    audit = []
    aa, ab = a.get("audit") or {}, b.get("audit") or {}
    for k in sorted(set(aa) | set(ab)):
        if aa.get(k) != ab.get(k):
            audit.append({"class": "audit-only", "where": "audit.%s" % k})
    plan_equal = a.get("plan_fingerprint") == b.get("plan_fingerprint")
    inputs_equal = a.get("input_fingerprint") == b.get("input_fingerprint")
    return {
        "equal": plan_equal and inputs_equal and not diffs,
        "plan_equal": plan_equal,
        "inputs_equal": inputs_equal,
        "first_divergent_producer": first,
        "differences": diffs,
        "audit_differences": audit,
        "a": {"input_fingerprint": a.get("input_fingerprint"), "plan_fingerprint": a.get("plan_fingerprint")},
        "b": {"input_fingerprint": b.get("input_fingerprint"), "plan_fingerprint": b.get("plan_fingerprint")},
    }
