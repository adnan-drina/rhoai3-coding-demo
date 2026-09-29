"""The one independent M3 repair pair of a pilot run, and the serial chain around it.

PARALLEL-M3-PILOT.md, policy ``m3-pair-pilot/v1``. Pure functions of the plan revision and the
FROZEN structural model (the admitted evidence bundle): identical inputs select the same pair.

A pair qualifies only when every one of these is PROVEN from the inputs; anything unknown is a
reason, and a reason means serial:

  * both are compile (``source``) repair outcomes, neither a shared prerequisite, with a known
    writable scope made only of Java sources under src/main/java (no build, generator,
    configuration or resource file: those stay serial);
  * neither is an ancestor of the other in the genuine dependency graph;
  * their writable scopes (plan paths) and their clusters are disjoint;
  * neither declares a type the other's files reference, per the frozen model -- every type of
    both scopes must be fully resolved there (a partial model is unknown);
  * their family budget keys are distinct;
  * no check each will be issued needs the whole application (runtime checks are deferred to M4).

Different file names alone are not independence; shared read-only references and a whole-project
compile are not dependence. The first qualifying pair in topological order is chosen; the
selection records every candidate it rejected and why, and the chosen pair's evidence.
"""
from __future__ import annotations

import hashlib
from typing import Any

from planner.execution_policy import PILOT, WORKTREES_DIR
from planner.outcome_graph import plan_digest, topo_order

SCHEMA = "rhoai3.pair-selection/v1"
CROSS_CUTTING = ("pom.xml", ".mvn/", "src/main/resources/", "src/test/", "src/main/openapi", "src/gen/", "target/")
RUNTIME_CHECK_PREFIXES = ("parity:", "behavior:", "gate:package", "gate:augmentation", "gate:startup", "gate:runtime")
REJECTED_LIMIT = 60


def slug(outcome_id: str) -> str:
    return "m3-" + hashlib.sha256(outcome_id.encode("utf-8")).hexdigest()[:12]


def worktree_of(dest: str, outcome_id: str) -> tuple[str, str]:
    """(absolute worktree path, branch) of a pair outcome under the destination root."""
    s = slug(outcome_id)
    return "%s/%s/%s" % (dest.rstrip("/"), WORKTREES_DIR, s), "wt/%s" % s


def _ancestors(nodes: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    memo: dict[str, set[str]] = {}

    def up(n: str) -> set[str]:
        if n in memo:
            return memo[n]
        memo[n] = set()
        acc: set[str] = set()
        for p in nodes.get(n, {}).get("parents") or []:
            if p in nodes:
                acc |= {p} | up(p)
        memo[n] = acc
        return acc
    for n in nodes:
        up(n)
    return memo


def _type_index(structure: dict[str, Any] | None) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, bool], str]:
    """(path -> declared fqns, path -> referenced project fqns, path -> fully resolved, why unavailable)."""
    st = structure or {}
    if not st.get("available") or not isinstance(st.get("types"), list) or not st["types"]:
        return {}, {}, {}, "the frozen structural model is unavailable"
    declared: dict[str, set[str]] = {}
    refs: dict[str, set[str]] = {}
    full: dict[str, bool] = {}
    for t in st["types"]:
        if not isinstance(t, dict):
            continue
        path = str(t.get("path") or "")
        fqn = str(t.get("fqn") or "")
        if not path or not fqn:
            continue
        declared.setdefault(path, set()).add(fqn)
        r = refs.setdefault(path, set())
        r |= set(map(str, t.get("type_refs") or [])) | set(map(str, t.get("supertypes") or []))
        for m in list(t.get("methods") or []) + list(t.get("constructors") or []):
            if isinstance(m, dict):
                r |= set(map(str, m.get("type_refs") or []))
        for f in t.get("fields") or []:
            if isinstance(f, dict) and f.get("type"):
                r.add(str(f["type"]))
        full[path] = full.get(path, True) and str(t.get("resolution") or "partial") == "full"
    return declared, refs, full, ""


def _issued_checks(node: dict[str, Any]) -> list[str]:
    acc = node.get("acceptance") or {}
    checks = list(acc.get("checks") or []) + list(acc.get("requirement_checks") or [])
    return [str(c) for c in checks]


def _eligible(node: dict[str, Any]) -> str:
    """'' when the outcome may be one of the pair, else why not."""
    if node.get("role") != "repair":
        return "not a repair outcome"
    if node.get("class") != "source":
        return "class %s is not a compile (source) outcome" % node.get("class")
    if node.get("shared_prerequisite"):
        return "a shared prerequisite of other outcomes"
    paths = [str(p) for p in node.get("plan_paths") or []]
    if not paths:
        return "no known writable scope"
    bad = [p for p in paths if p.startswith(CROSS_CUTTING) or not (p.startswith("src/main/java/") and p.endswith(".java"))]
    if bad:
        return "cross-cutting or non-Java scope %s" % bad[0]
    runtime = [c for c in _issued_checks(node) if c.startswith(RUNTIME_CHECK_PREFIXES)]
    if runtime:
        return "needs the whole application (%s)" % runtime[0]
    if not ((node.get("budget") or {}).get("key")):
        return "no family budget key"
    return ""


def select_pair(plan: dict[str, Any], structure: dict[str, Any] | None) -> dict[str, Any]:
    """The selection document: ``pair`` is [a, b] (outcome ids, topological order) or [] with ``why``."""
    nodes = {n["outcome_id"]: n for n in plan.get("nodes") or []}
    order = [n["outcome_id"] for n in topo_order(list(nodes.values())) if n.get("role") == "repair"]
    excluded = []
    candidates = []
    for oid in order:
        why = _eligible(nodes[oid])
        (excluded.append({"outcome": oid, "reason": why}) if why else candidates.append(oid))
    doc: dict[str, Any] = {"schema": SCHEMA, "policy": PILOT, "plan_digest": plan.get("digest"), "order": order,
                           "candidates": candidates, "excluded": excluded, "rejected": [], "pair": [], "evidence": {}}
    declared, refs, full, unavailable = _type_index(structure)
    if unavailable:
        doc["why"] = "no pair: %s, so independence is unknown" % unavailable
        return doc
    anc = _ancestors(nodes)
    rejected: list[dict[str, Any]] = []
    for i, a in enumerate(candidates):
        for b in candidates[i + 1:]:
            na, nb = nodes[a], nodes[b]
            pa, pb = set(map(str, na["plan_paths"])), set(map(str, nb["plan_paths"]))
            reasons = []
            if a in anc.get(b, set()) or b in anc.get(a, set()):
                reasons.append("one depends on the other")
            if pa & pb:
                reasons.append("overlapping writable scope %s" % sorted(pa & pb)[0])
            ca = {c if isinstance(c, str) else str(c.get("id")) for c in na.get("clusters") or []}
            cb = {c if isinstance(c, str) else str(c.get("id")) for c in nb.get("clusters") or []}
            if ca & cb:
                reasons.append("shared cluster %s" % sorted(ca & cb)[0])
            if na["budget"]["key"] == nb["budget"]["key"]:
                reasons.append("shared family budget %s" % na["budget"]["key"])
            unknown = sorted(p for p in pa | pb if p not in full or not full[p])
            if unknown:
                reasons.append("independence unknown: %s is not fully resolved in the frozen model" % unknown[0])
            else:
                decl_a = set().union(*(declared[p] for p in pa))
                decl_b = set().union(*(declared[p] for p in pb))
                refs_a = set().union(*(refs.get(p, set()) for p in pa))
                refs_b = set().union(*(refs.get(p, set()) for p in pb))
                if decl_a & refs_b:
                    reasons.append("%s relies on %s, which %s changes" % (b, sorted(decl_a & refs_b)[0], a))
                if decl_b & refs_a:
                    reasons.append("%s relies on %s, which %s changes" % (a, sorted(decl_b & refs_a)[0], b))
            if reasons:
                if len(rejected) < REJECTED_LIMIT:
                    rejected.append({"pair": [a, b], "reasons": reasons})
                continue
            doc["rejected"] = rejected
            doc["pair"] = [a, b]
            doc["evidence"] = {
                "genuine_parents": {a: sorted(na.get("parents") or []), b: sorted(nb.get("parents") or [])},
                "writable_scopes": {a: sorted(pa), b: sorted(pb)},
                "declared_types": {a: sorted(set().union(*(declared[p] for p in pa))),
                                   b: sorted(set().union(*(declared[p] for p in pb)))},
                "budget_keys": {a: na["budget"]["key"], b: nb["budget"]["key"]},
                "issued_checks": {a: _issued_checks(na), b: _issued_checks(nb)},
                "why": "independent: neither is the other's ancestor, disjoint Java scopes and clusters, no type one "
                       "changes is referenced by the other (frozen model, fully resolved), distinct budgets, compile-"
                       "level checks only",
            }
            doc["why"] = "the first qualifying pair in topological order"
            return doc
    doc["rejected"] = rejected
    doc["why"] = ("no pair: %d eligible outcome(s), no qualifying pair among them" % len(candidates)
                  if len(candidates) > 1 else "no pair: fewer than two eligible outcomes")
    return doc


def schedule(plan: dict[str, Any], pair: list[str]) -> dict[str, list[str]]:
    """outcome id -> its SCHEDULE parents: every repair outcome after its predecessor in one serial
    chain, the pair sharing one predecessor and the next outcome after both. The pair is merged into
    one virtual node for ordering, so both run only after all of their genuine prerequisites."""
    nodes = [dict(n) for n in plan.get("nodes") or [] if n.get("role") == "repair"]
    ids = {n["outcome_id"] for n in nodes}
    a, b = (pair + [None, None])[:2] if pair else (None, None)
    if a and b:
        merged = []
        for n in nodes:
            if n["outcome_id"] == b:
                continue
            ps = [a if p == b else p for p in n.get("parents") or []]
            if n["outcome_id"] == a:
                ps = sorted(set(ps) | set(p for p in nodes_by(plan)[b].get("parents") or []) - {a})
            merged.append(dict(n, parents=sorted(set(ps))))
        nodes = merged
    chain = [n["outcome_id"] for n in topo_order(nodes)]
    out: dict[str, list[str]] = {}
    prev: list[str] = []
    for oid in chain:
        members = [a, b] if (a and oid == a) else [oid]
        for m in members:
            want = [p for p in prev if p in ids]
            genuine = set(nodes_by(plan)[m].get("parents") or [])
            extra = sorted(p for p in want if p not in genuine)
            if extra:
                out[m] = extra
        prev = members
    return out


def nodes_by(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {n["outcome_id"]: n for n in plan.get("nodes") or []}


def apply_pilot(plan: dict[str, Any], structure: dict[str, Any] | None) -> dict[str, Any]:
    """The revision as a pilot run publishes it: the selection recorded (``execution``), schedule
    edges on every repair outcome, the pair marked. Deterministic; the digest is recomputed."""
    sel = select_pair(plan, structure)
    sched = schedule(plan, sel["pair"])
    pair = set(sel["pair"])
    nodes = []
    for n in plan["nodes"]:
        m = dict(n)
        m.pop("schedule_parents", None)
        m.pop("pilot_pair", None)
        if n["outcome_id"] in sched:
            m["schedule_parents"] = sched[n["outcome_id"]]
        if n["outcome_id"] in pair:
            m["pilot_pair"] = sorted(pair - {n["outcome_id"]})
        nodes.append(m)
    out = dict(plan, nodes=nodes, execution={"policy": PILOT, "selection": sel})
    out.pop("digest", None)
    out["digest"] = plan_digest(out)
    return out


def chain_revision(plan: dict[str, Any], added: list[str], live_pair: list[str]) -> dict[str, dict[str, Any]]:
    """Schedule parents for the repair outcomes a later revision adds (owner repair, M4 repairs):
    chained among themselves in topological order, the first after any pair member still live, so a
    new outcome never runs beside the pair or beside another new outcome."""
    nodes = nodes_by(plan)
    new = [n["outcome_id"] for n in topo_order([nodes[o] for o in added if o in nodes]) if n.get("role") == "repair"]
    out: dict[str, list[str]] = {}
    prev = sorted(live_pair)
    for oid in new:
        extra = sorted(p for p in prev if p not in set(nodes[oid].get("parents") or []))
        if extra:
            out[oid] = extra
        prev = [oid]
    return {oid: {"schedule_parents": ps} for oid, ps in out.items()}
