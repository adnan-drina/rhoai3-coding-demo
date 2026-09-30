#!/usr/bin/env python3
"""The completion map (M-1): what completion means for this run, which known
gaps can prevent it, who resolves each one and what evidence closes it.

A derived VIEW over artifacts the run already keeps. It plans nothing, admits
nothing, issues nothing and accepts nothing: the admitted plan, the loop's
measurements, the parity receipts, the M4 verdict and the M5 delivery records
remain the only authorities. It never writes a file.

  contract            the supported source/target pair, composed from the
                      existing inputs (frozen source identity, decided build
                      profiles, build and generator toolchains, destination
                      platform and its pin, decided datasource, owed security
                      modes, HTTP behavior in scope) with its explicit analysis
                      limits: an HTTP inventory is not evidence that
                      reflective, scheduled or message-driven entry paths are
                      absent
  release blockers    every unresolved verification responsibility of the
                      admitted plan, one row PER ENTRY POINT, and every source
                      qualification FAIL, each with a resolution owner,
                      prerequisites and a measurable exit. A row closes only
                      by the release rule m5_delivery already applies (the
                      parity receipts the bound M4 verdict judged measure the
                      entry point PASS in every owed security mode); a
                      finished card or an empty work list never closes it
  milestones          the M-2 progression (source understood, target
                      structurally viable, persistence and one HTTP path,
                      application behavior preserved, delivered and usable),
                      each demonstrated / not-demonstrated / unknown from
                      check and measurement evidence -- never from card
                      completion -- plus the functional, delivery, full
                      release and repeatability distinctions
  measurement         whether the current measurement can support a claim at
                      all: a stale or blocked admission seal, verdicts the
                      comparator refused to measure, and INCONCLUSIVE written
                      over a recorded FAIL make it invalid, whatever the
                      measure tuple or the work list says
  causal groups       repeated runtime failures grouped only where the records
                      prove a shared producer (same exception, a recursion the
                      recorded frames show, throwing files owned by plan
                      outcomes of one family and recipe); every affected check
                      is kept

``build`` is pure over the inputs ``load_inputs`` reads; the same inputs give
the same map and the same digest. Specimen-agnostic: no application name,
package or path is in this module. It lives beside, not in, ``planner/``: a
view must not enter the planner code fingerprint (plan_semantics.PLANNER_CODE).

    python3 .hermes/lib/completion_map.py --root /projects/modernized [--plan plan.r1.json ...] [--json]
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA = "rhoai3.completion-map/v1"
DEMONSTRATED, NOT_DEMONSTRATED, UNKNOWN = "demonstrated", "not-demonstrated", "unknown"
MILESTONES = (
    ("source-understood", "source understood"),
    ("target-structurally-viable", "target structurally viable"),
    ("persistence-and-one-http-path", "persistence and one HTTP path"),
    ("application-behavior-preserved", "application behavior preserved"),
    ("delivered-and-usable", "delivered and usable"),
)
OWNERS = {
    "source-capture": "source capture/fixture work",
    "destination-behavior-check": "destination behavior check",
    "external-dependency": "named external dependency",
    "scope-decision": "explicit scope decision with evidence",
}
# entry paths an HTTP entry-point inventory does not establish, present or absent
UNANALYSED_ENTRY_PATHS = ("reflective", "scheduled", "message-driven", "other dynamic dispatch")
NOT_AUTHORITATIVE = "receipt not authoritative"
PLAN_SCHEMAS = ("rhoai3.native-plan/v1", "rhoai3.plan-semantics/v1", "rhoai3.outcome-plan/v1")


def _d(x: Any) -> dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _l(x: Any) -> list[Any]:
    return x if isinstance(x, list) else []


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _ep_kind(ep: str) -> str:
    return ep.rsplit(":", 1)[-1] if ":" in ep else "?"


def _ep_short(ep: str) -> str:
    head = ep.split("(", 1)[0]
    return head.split(":", 1)[-1].rsplit(".", 1)[-1]


# --------------------------------------------------------------------------- the plan

def normalize_plan(doc: Any) -> dict[str, Any] | None:
    """One shape for a native plan revision (``plan.r<N>.json``), a frozen plan
    semantics document (its ``graph``) or a bare outcome plan; None when the
    document is none of these."""
    d = _d(doc)
    plan = d.get("plan") if isinstance(d.get("plan"), dict) else d
    if isinstance(plan.get("graph"), dict):          # frozen plan semantics
        g = plan["graph"]
        plan = dict(g, requirements=g.get("requirements") or plan.get("requirements") or [])
    if not isinstance(plan.get("nodes"), list) or not isinstance(plan.get("unresolved"), list):
        return None
    return {"revision": int(d.get("revision") or plan.get("revision") or 1), "digest": str(plan.get("digest") or ""),
            "run_id": str(plan.get("run_id") or ""), "policy": str(plan.get("policy") or ""),
            "nodes": [n for n in plan["nodes"] if isinstance(n, dict)],
            "requirements": [r for r in _l(plan.get("requirements")) if isinstance(r, dict)],
            "unresolved": [u for u in plan["unresolved"] if isinstance(u, dict)],
            "provenance": _d(plan.get("provenance"))}


def inventory(plan: dict[str, Any]) -> dict[str, Any]:
    """Counts recomputed from the plan itself (never a copied counts block)."""
    reqs = plan["requirements"]
    by_status: dict[str, int] = {}
    for r in reqs:
        by_status[str(r.get("status") or "?")] = by_status.get(str(r.get("status") or "?"), 0) + 1
    repairs = [n for n in plan["nodes"] if n.get("role") == "repair"]
    by_class: dict[str, int] = {}
    for n in repairs:
        by_class[str(n.get("class"))] = by_class.get(str(n.get("class")), 0) + 1
    groups = [u for u in plan["unresolved"] if u.get("kind") == "verification-responsibility"]
    eps = sorted({str(e) for u in plan["unresolved"] for e in _l(u.get("entry_points"))})
    later = {str(n.get("outcome_id")): sum(1 for c in _l(n.get("check_plan")) if _d(c).get("stage") == "later")
             for n in repairs if any(_d(c).get("stage") == "later" for c in _l(n.get("check_plan")))}
    blocks: dict[str, int] = {}
    for u in plan["unresolved"]:
        blocks[str(u.get("blocks"))] = blocks.get(str(u.get("blocks")), 0) + 1
    return {"requirements": len(reqs), "requirements_by_status": dict(sorted(by_status.items())),
            "repair_outcomes": len(repairs), "repair_outcomes_by_class": dict(sorted(by_class.items())),
            "milestone_nodes": len(plan["nodes"]) - len(repairs),
            "unresolved_rows": len(plan["unresolved"]), "unresolved_by_blocks": dict(sorted(blocks.items())),
            "verification_groups": len(groups),
            "ship_blocking_verification_groups": sum(1 for u in groups if u.get("blocks") == "ship"),
            "unresolved_entry_points": len(eps),
            "unresolved_entry_point_kinds": dict(sorted({k: sum(1 for e in eps if _ep_kind(e) == k) for k in {_ep_kind(e) for e in eps}}.items())),
            "later_checks_by_outcome": dict(sorted(later.items()))}


# --------------------------------------------------------------------------- the contract

def owed_modes(decisions: Any) -> list[str]:
    """The security modes the release owes: both when the source has a
    decided security switch (ADR-014 shape), else the default mode."""
    try:
        from planner.decisions import security
        return ["disabled", "enabled"] if security(_d(decisions)) else ["disabled"]
    except Exception:  # noqa: BLE001 - an unreadable declaration owes at least the default mode
        return ["disabled"]


def contract(inputs: dict[str, Any], plan: dict[str, Any] | None) -> dict[str, Any]:
    from planner.decisions import build_profiles, datasource
    dec = _d(inputs.get("decisions"))
    missing = _d(inputs.get("missing"))
    freeze, manifest, build = _d(inputs.get("freeze")), _d(inputs.get("source_manifest")), _d(inputs.get("build_receipt"))
    pins = _d(_d(inputs.get("pins")).get("pins"))
    ds = datasource(dec) if dec else {}
    bp = build_profiles(dec) if dec else {}
    reqs = plan["requirements"] if plan else []
    gens = sorted({str(r.get("subject")) for r in reqs if str(r.get("rule") or "").startswith("generator-configuration")})
    eps = sorted({str(r.get("subject")) for r in reqs if str(r.get("rule") or "").startswith("behavior-verification")})
    kinds: dict[str, int] = {}
    for e in eps:
        kinds[_ep_kind(e)] = kinds.get(_ep_kind(e), 0) + 1
    platform = _d(dec.get("destination_platform"))
    qp = _d(pins.get("quarkus_platform"))
    m1 = _d(inputs.get("m1_facts"))
    return {
        "source": {
            "content_digest": str(manifest.get("digest") or freeze.get("source_digest") or "") or None,
            "repository": str(_d(_d(inputs.get("migration")).get("migration")).get("legacyRepoUrl") or "") or None,
            "revision": None,
            "revision_reason": "no artifact records the cloned legacy commit; the frozen content digest is the source identity",
            "build": {"status": build.get("status") or None, "outcome": build.get("outcome") or None,
                      "toolchain": _d(build.get("toolchain")) or None,
                      "generated_source_roots": sorted(str(x) for x in _l(build.get("generated_source_roots")))},
        },
        "active_profiles": sorted(str(x) for x in _l(bp.get("active"))) if bp else None,
        "generator_toolchains": gens,
        "target": {"platform": str(platform.get("id") or "") or None,
                   "pin": ("%s:%s:%s" % (qp.get("group_id"), qp.get("bom_artifact_id"), qp.get("version"))) if qp.get("version") else None},
        "database": ({k: ds.get(k) for k in ("db_kind", "db_version", "profile", "schema_owner", "source_baseline_db_kind") if k in ds}
                     if ds else None),
        "security_modes": owed_modes(dec),
        "security_modes_basis": ("decisions.yaml security section" if dec else
                                 "decisions unknown (%s): the default mode is the least owed" % missing.get("decisions", "absent")),
        "http_behavior": {"entry_points": len(eps), "by_kind": dict(sorted(kinds.items())),
                          "source": "admitted plan behavior-verification requirements" if plan else None,
                          "m1_inventory": _d(m1.get("entry_points")) or None},
        "limitations": ["the entry-point inventory is structural: it does not establish coverage of %s entry paths; they "
                        "are unanalysed, not absent" % ", ".join(UNANALYSED_ENTRY_PATHS)]
                       + (["no admitted plan was read (%s): requirements and missing oracles are unknown" % missing.get("plan", "absent")]
                          if plan is None else []),
        "unknown_inputs": dict(sorted((k, v) for k, v in missing.items() if k in (
            "decisions", "pins", "freeze", "source_manifest", "build_receipt", "m1_facts", "migration"))),
    }


# --------------------------------------------------------------------------- release blockers

def release_blockers(plan: dict[str, Any] | None, *, modes: list[str], m1: dict[str, Any] | None,
                     parity: dict[str, dict[str, str]] | None, parity_reason: str,
                     toolchain: dict[str, Any] | None) -> list[dict[str, Any]]:
    """One row per unresolved entry point (or other unresolved plan row) and
    per source qualification FAIL. Closed only by the M4-bound parity evidence
    m5_delivery reads (PASS in every owed mode); otherwise open."""
    rows: list[dict[str, Any]] = []
    unverified = set(_l(_d(_d(m1).get("coverage")).get("unverified_entry_points"))) if m1 else None
    tool = ", ".join("%s %s" % kv for kv in sorted(_d(toolchain).items())) or "its recorded toolchain"
    mode_txt = ", ".join(modes)
    for u in sorted(plan["unresolved"] if plan else [], key=lambda x: str(x.get("id"))):
        eps = sorted(str(e) for e in _l(u.get("entry_points")))
        reqs = sorted(str(r) for r in _l(u.get("requirements")))
        for ep in eps or [""]:
            kind = _ep_kind(ep) if ep else ""
            req = next((r for r in reqs if ep and r.endswith(ep)), reqs[0] if reqs else "")
            if u.get("kind") != "verification-responsibility":
                owner = "scope-decision"
                prereq = ["the plan row's reason is answered by a recorded decision (ADR) or an explained plan revision"]
                exit_ = "a later admitted plan revision owns or retires %s with evidence" % u.get("id")
            elif kind != "http":
                owner = "scope-decision"
                prereq = ["an operator observation or a recorded scope decision for this %s entry point" % kind]
                exit_ = "a recorded decision with evidence, or a qualified observation of the source behavior"
            elif unverified is not None and ep not in unverified:
                owner = "destination-behavior-check"
                prereq = ["a qualified source capture exists (M1)", "the destination packages and starts with the decided datasource"]
                exit_ = "the parity receipts the bound M4 verdict judged measure this entry point PASS in %s" % mode_txt
            else:
                owner = "source-capture"
                prereq = ["the frozen source builds and runs on %s with the decided datasource" % tool,
                          "a corpus scenario reaches this entry point (a write declares its initial state and read-backs)",
                          "that scenario is captured, bound to the evidence bundle and corpus, in each owed mode: %s" % mode_txt,
                          "its source qualification is PASS in each owed mode"]
                exit_ = ("the capture qualifies PASS in %s, then the parity receipts the bound M4 verdict judged measure this "
                         "entry point PASS in %s" % (mode_txt, mode_txt))
            status, missing_modes = "open", []
            if parity is not None and ep:
                missing_modes = ["%s: %s" % (m, parity.get(m, {}).get(ep) or "not measured") for m in modes
                                 if parity.get(m, {}).get(ep) != "PASS"]
                status = "closed" if not missing_modes else "open"
            rows.append({"id": str(u.get("id")), "entry_point": ep or None, "kind": kind or str(u.get("kind")),
                         "requirement": req or None, "blocks": str(u.get("blocks")), "cause": str(u.get("reason") or "")[:300],
                         "capability": "known" if status == "closed" else "unknown",
                         "owner": owner, "owner_label": OWNERS[owner], "prerequisites": prereq, "exit": exit_, "status": status,
                         "not_yet": missing_modes or ([] if status == "closed" else ["no usable M4-bound parity assessment (%s)" % parity_reason])})
    for mode, sids in sorted(_d(_d(_d(m1).get("coverage")).get("source_qualification_fail")).items()):
        for sid in sorted(str(s) for s in _l(sids)):
            rows.append({"id": "qualification:%s:%s" % (mode, sid), "entry_point": None, "kind": "source-qualification",
                         "requirement": None, "blocks": "ship", "cause": "the source capture of %s did not qualify in the %s mode" % (sid, mode),
                         "capability": "unknown", "owner": "source-capture", "owner_label": OWNERS["source-capture"],
                         "prerequisites": ["the source reproduces its own capture of %s in the %s mode" % (sid, mode)],
                         "exit": "qualification PASS of %s in the %s mode, bound to the current corpus" % (sid, mode),
                         "status": "open", "not_yet": ["source qualification FAIL"]})
    return rows


# --------------------------------------------------------------------------- measurement validity

def _records(inputs: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for mode, block in sorted(_d(inputs.get(key)).items()):
        for sid, rec in sorted(_d(_d(block).get("records")).items()):
            out["%s|%s" % (mode, sid)] = dict(_d(rec), _mode=mode)
    return out


def measurement_validity(inputs: dict[str, Any]) -> dict[str, Any]:
    findings: list[str] = []
    adm = inputs.get("admission")
    deferred = set(_l(_d(inputs.get("deferred")).get("clusters")))
    if not isinstance(adm, dict):
        findings.append("no admission receipt: nothing measured is admitted")
    elif str(adm.get("status")) != "ADMITTED":
        blocks = [b for b in _l(adm.get("blocks")) if isinstance(b, dict)]
        stale = sorted(str(b.get("subject")) for b in blocks if b.get("class") == "MANUAL_CLUSTER" and b.get("subject") not in deferred)
        findings.append("admission seal %s (%s)" % (adm.get("status"), ", ".join(sorted("%s %s" % (b.get("class"), b.get("subject")) for b in blocks)) or "no block named"))
        if stale:
            findings.append("stale seal: MANUAL_CLUSTER on %s, which is no longer deferred" % ", ".join(stale))
    live = _records(inputs, "parity")
    refused = sorted(k for k, r in live.items() if r.get("verdict") == "INCONCLUSIVE" and str(r.get("reason") or "").startswith(NOT_AUTHORITATIVE))
    if refused:
        findings.append("%d verdict(s) were not measured: %s" % (len(refused), NOT_AUTHORITATIVE))
    recorded_fail = set()
    for k, r in _records(inputs, "accepted_parity").items():
        if r.get("verdict") == "FAIL":
            recorded_fail.add(k)
    for mode, block in _d(inputs.get("parity")).items():
        for sid, v in _d(_d(block).get("receipt_scenarios")).items():
            if v == "FAIL":
                recorded_fail.add("%s|%s" % (mode, sid))
    over = sorted(k for k, r in live.items() if r.get("verdict") == "INCONCLUSIVE" and k in recorded_fail)
    if over:
        findings.append("%d scenario verdict(s) are INCONCLUSIVE over a recorded FAIL" % len(over))
    meas = _d(_d(inputs.get("state")).get("measure"))
    if inputs.get("state") is not None and meas.get("known") is False:
        findings.append("the loop measure is unknown")
    wl = _d(inputs.get("worklist"))
    empty = inputs.get("worklist") is not None and not _l(wl.get("items"))
    if findings and empty:
        findings.append("an empty work list under an invalid measurement is not a completion")
    return {"valid": not findings, "findings": findings, "refused_verdicts": len(refused), "inconclusive_over_fail": over[:20],
            "worklist_empty": empty, "measure": _l(meas.get("tuple")) or None}


# --------------------------------------------------------------------------- milestones

def _m(key: str, state: str, evidence: list[str], gaps: list[str]) -> dict[str, Any]:
    return {"id": key, "title": dict(MILESTONES)[key], "state": state, "evidence": evidence, "gaps": gaps}


def _gate_pass(doc: Any, boot: bool = False) -> str | None:
    d = _d(doc)
    if not d:
        return None
    return "pass" if d.get("ran") and d.get("rc") == 0 and (not boot or d.get("ready")) else ("fail" if d.get("ran") else "not-run")


def milestones(inputs: dict[str, Any], blockers: list[dict[str, Any]], validity: dict[str, Any], modes: list[str]) -> list[dict[str, Any]]:
    out = []
    # source understood
    b, m1, dec = _d(inputs.get("build_receipt")), _d(inputs.get("m1_facts")), _d(inputs.get("decisions"))
    ev, gaps, failed = [], [], False
    if not b:
        gaps.append("no source build receipt")
    elif b.get("status") == "ok":
        ev.append("the frozen source builds (%s)" % ", ".join("%s %s" % kv for kv in sorted(_d(b.get("toolchain")).items())))
    else:
        gaps.append("the frozen source build is %s" % b.get("status"))
        failed = True
    from planner.decisions import build_profiles
    if dec and build_profiles(dec):
        ev.append("build profiles decided: %s" % ", ".join(sorted(str(x) for x in _l(build_profiles(dec).get("active")))))
    else:
        gaps.append("no decided build profiles")
    if not m1:
        gaps.append("no M1 handoff facts (evidence/handoff/m1-facts.json): source captures unknown")
    else:
        for mode in modes:
            s = _d(_d(m1.get("scenarios")).get(mode))
            q = _d(s.get("qualification"))
            if not s or not s.get("bound"):
                gaps.append("%s-mode captures are not bound (%s)" % (mode, s.get("unbound_reason") or "absent"))
            elif int(q.get("FAIL") or 0):
                gaps.append("%s-mode source qualification: %d FAIL" % (mode, int(q.get("FAIL") or 0)))
                failed = True
            else:
                ev.append("%s-mode captures qualified: %s PASS, %s INCONCLUSIVE" % (mode, q.get("PASS"), q.get("INCONCLUSIVE")))
        cov = _d(m1.get("coverage"))
        if cov.get("unverified"):
            ev.append("%s entry point(s) have no captured oracle: release blockers, not source failures" % cov.get("unverified"))
    state = DEMONSTRATED if not gaps else (NOT_DEMONSTRATED if failed else UNKNOWN)
    out.append(_m("source-understood", state, ev, gaps))

    # target structurally viable: compile, package, start
    ev, gaps = [], []
    meas = _d(_d(inputs.get("state")).get("measure"))
    tup = _l(meas.get("tuple"))
    stages = _d(_d(inputs.get("execution")).get("stages"))
    compile_state = _d(stages.get("compile")).get("state") if _d(inputs.get("execution")).get("bound") else None
    if compile_state == "passed" or (compile_state is None and len(tup) >= 2 and tup[1] == 0 and meas.get("known")):
        ev.append("0 compile errors on the measured tree")
    elif compile_state in ("failed",) or (len(tup) >= 2 and isinstance(tup[1], int) and tup[1] > 0):
        gaps.append("compile errors remain (%s)" % (tup[1] if len(tup) >= 2 else "measured"))
    else:
        gaps.append("compilation not measured on the current tree")
    for name, doc, boot in (("package", inputs.get("package"), False), ("start", inputs.get("boot"), True)):
        g = _gate_pass(doc, boot)
        (ev if g == "pass" else gaps).append("%s gate %s" % (name, g or "not recorded"))
    state = DEMONSTRATED if not gaps else (NOT_DEMONSTRATED if any("remain" in g or g.endswith("fail") for g in gaps) else UNKNOWN)
    out.append(_m("target-structurally-viable", state, ev, gaps))
    structural = state

    # persistence and one HTTP path: a write whose read-backs match the source, on the current tree
    tree = str(_d(inputs.get("worklist")).get("candidate_sha256") or "")
    live = _records(inputs, "parity")

    def valid(r: dict[str, Any]) -> bool:
        # a record bound to this tree, or (seal-bound, no candidate of its own) composed into a receipt of this tree
        own = str(_d(r.get("binding")).get("candidate_sha256") or "")
        rec = _d(_d(_d(inputs.get("parity")).get(r.get("_mode"))).get("receipt"))
        via = str(_d(rec.get("binding")).get("candidate_sha256") or "")
        return (bool(tree) and (own == tree or (not own and via == tree))
                and not str(r.get("reason") or "").startswith(NOT_AUTHORITATIVE))
    usable = {k: r for k, r in live.items() if valid(r)}
    db_pass = sorted(k for k, r in usable.items() if r.get("verdict") == "PASS" and _l(r.get("effects")))
    fails = sorted(k for k, r in usable.items() if r.get("verdict") == "FAIL")
    ev, gaps = [], []
    if not validity["valid"]:
        gaps.append("measurement invalid: %s" % validity["findings"][0])
    if db_pass:
        ev.append("%d write scenario(s) PASS with source-matching read-backs (e.g. %s)" % (len(db_pass), db_pass[0].split("|", 1)[1]))
    elif usable and fails:
        gaps.append("no write scenario passes with its read-backs; %d scenario(s) FAIL on this tree" % len(fails))
    else:
        gaps.append("no scenario verdict bound to the current tree")
    if structural != DEMONSTRATED:
        gaps.append("the target is not structurally viable")
    state = DEMONSTRATED if db_pass and structural == DEMONSTRATED and validity["valid"] else (
        NOT_DEMONSTRATED if (usable and fails and validity["valid"] and not db_pass) else UNKNOWN)
    out.append(_m("persistence-and-one-http-path", state, ev, gaps))

    # application behavior preserved: every owed mode PASS on this tree, no open blocker, valid measurement
    ev, gaps, failed = [], [], False
    for mode in modes:
        blk = _d(_d(inputs.get("parity")).get(mode))
        rec = _d(blk.get("receipt"))
        bound = str(_d(rec.get("binding")).get("candidate_sha256") or "")
        if not rec:
            gaps.append("no %s-mode parity receipt" % mode)
        elif bound != tree or not tree:
            gaps.append("the %s-mode receipt is bound to %s, not to the current tree" % (mode, bound[:12] or "nothing"))
        elif rec.get("verdict") == "PASS":
            ev.append("%s-mode parity PASS on the current tree" % mode)
        else:
            n = sum(1 for v in _d(blk.get("receipt_entry_points")).values() if v == "FAIL")
            gaps.append("%s-mode parity %s (%d entry point(s) FAIL)" % (mode, rec.get("verdict"), n))
            failed = failed or n > 0
    open_ = [x for x in blockers if x["status"] == "open"]
    if open_:
        gaps.append("%d release blocker(s) open; their behavior is unknown" % len(open_))
    if not validity["valid"]:
        gaps.append("measurement invalid")
    state = DEMONSTRATED if not gaps else (NOT_DEMONSTRATED if failed and validity["valid"] else UNKNOWN)
    out.append(_m("application-behavior-preserved", state, ev, gaps))

    # delivered and usable (M5 records through m5_delivery's own contracts)
    d = delivery(inputs)
    ev, gaps = [], []
    if d["verdict"] is None:
        gaps.append("no M5 delivery verdict")
        state = NOT_DEMONSTRATED
    elif d["deployed"] and d["live_ok"] and not d["stale_evidence"]:
        ev.append("deployed at %s, live checks passed (M5 %s, ship=%s)" % (d["route_url"] or "an unrecorded URL", d["verdict"], d["ship"]))
        state = DEMONSTRATED
    else:
        gaps.append("M5 %s: %s" % (d["verdict"], d["reason"] or d["failed_stage"] or "not deployed"))
        state = NOT_DEMONSTRATED
    out.append(_m("delivered-and-usable", state, ev, gaps))
    return out


def delivery(inputs: dict[str, Any]) -> dict[str, Any]:
    """candidate -> PipelineRun -> image digest -> deployment -> live checks -> verdict, as the
    M5 records written by lib/m5_delivery.py state them (no new judgement)."""
    m5 = _d(inputs.get("m5"))
    v, c, p, dep, live = (_d(m5.get(k)) for k in ("verdict", "candidate", "pipeline", "deployment", "live"))
    return {"candidate": str(v.get("candidate_sha") or c.get("candidate_sha") or "") or None,
            "pipeline_run": str(v.get("pipeline_run") or p.get("pipeline_run") or "") or None,
            "image_digest": str(v.get("image_digest") or p.get("image_digest") or "") or None,
            "deployed_image": str(v.get("deployed_image") or dep.get("deployed_image") or "") or None,
            "route_url": str(v.get("route_url") or dep.get("route_url") or "") or None,
            "deployed": (v.get("deployment_status") == "deployed") if v else bool(dep.get("ok")),
            "live_ok": bool(v.get("live_ok")) if v else bool(live.get("ok")),
            "live_issues": sorted(str(x) for x in _l(live.get("issues"))),
            "verdict": str(v.get("verdict")) if v.get("verdict") else None, "ship": bool(v.get("ship")),
            "reason": str(v.get("reason") or ""), "failed_stage": str(v.get("failed_stage") or ""),
            "stale_evidence": sorted(str(x) for x in _l(v.get("stale_evidence"))),
            "outstanding": [{"kind": _d(o).get("kind"), "id": _d(o).get("id"), "count": _d(o).get("count")} for o in _l(v.get("outstanding"))]}


def distinctions(ms: list[dict[str, Any]], d: dict[str, Any], classification: Any) -> dict[str, Any]:
    st = {m["id"]: m["state"] for m in ms}
    functional = DEMONSTRATED if st["target-structurally-viable"] == DEMONSTRATED and st["persistence-and-one-http-path"] == DEMONSTRATED else (
        UNKNOWN if UNKNOWN in (st["target-structurally-viable"], st["persistence-and-one-http-path"]) else NOT_DEMONSTRATED)
    full = DEMONSTRATED if d["verdict"] == "ACCEPT" and d["ship"] else NOT_DEMONSTRATED
    cls = str(classification or "")
    if not cls:
        rep = (UNKNOWN, "the run's classification was not given")
    elif cls.startswith("assisted"):
        rep = (NOT_DEMONSTRATED, "this run is %s: a clean run and a confirming run without overlays or rescue are needed" % cls)
    else:
        rep = (UNKNOWN, "a single %s run; repeatability needs a confirming run on the same frozen inputs" % cls)
    return {"functional": functional, "delivery": st["delivered-and-usable"], "full_release": full,
            "repeatability": rep[0], "repeatability_reason": rep[1]}


# --------------------------------------------------------------------------- causal groups

def _class_path(cls: str) -> str:
    return cls.split("$", 1)[0].replace(".", "/") + ".java"


def causal_groups(inputs: dict[str, Any], plan: dict[str, Any] | None) -> dict[str, Any]:
    """Failures grouped only where the records prove a shared producer: the same
    exception, a recursion the recorded frames show (a frame repeats), and
    throwing files owned by plan outcomes of one family and recipe. Each
    affected check is kept; nothing else is grouped."""
    owners: dict[str, dict[str, Any]] = {}
    for n in (plan["nodes"] if plan else []):
        for p in _l(n.get("plan_paths")):
            owners.setdefault(str(p), n)
    recs = dict(_records(inputs, "accepted_parity"))
    recs.update({k: r for k, r in _records(inputs, "parity").items() if r.get("verdict") == "FAIL"})
    groups: dict[tuple, dict[str, Any]] = {}
    ungrouped = 0
    for key, r in sorted(recs.items()):
        se = _d(r.get("server_error"))
        if r.get("verdict") != "FAIL" or not se.get("exception"):
            continue
        frames = [f for f in _l(se.get("frames")) if isinstance(f, dict) and f.get("class")]
        sig = [(str(f.get("class")), str(f.get("method"))) for f in frames]
        recursive = len(set(sig)) < len(sig)
        node = None
        for f in frames:
            path = str(f.get("file") or "") if "/" in str(f.get("file") or "") else _class_path(str(f.get("class")))
            node = next((owners[p] for p in sorted(owners) if p.endswith(path)), None)
            if node is not None:
                break
        if node is None or not recursive:
            ungrouped += 1
            continue
        fam = str(_d(node.get("objective")).get("family") or node.get("class") or "")
        recipes = tuple(sorted(str(x) for x in _l(node.get("recipes"))))
        gk = (str(se.get("exception")), "recursion", fam, recipes)
        g = groups.setdefault(gk, {"exception": gk[0], "mechanism": "recursion shown by repeated recorded frames",
                                   "producer": {"family": fam, "recipes": list(recipes)}, "owners": set(), "checks": []})
        g["owners"].add(str(node.get("outcome_id")))
        mode, sid = key.split("|", 1)
        g["checks"].append({"mode": mode, "scenario": sid, "entry_point": r.get("entry_point") or None,
                            "owner": str(node.get("outcome_id")), "first_frame": "%s.%s" % sig[0] if sig else None})
    out = []
    for gk in sorted(groups):
        g = groups[gk]
        if len(g["owners"]) < 2:
            ungrouped += len(g["checks"])
            continue
        out.append(dict(g, owners=sorted(g["owners"]), checks=sorted(g["checks"], key=lambda c: (c["mode"], c["scenario"]))))
    return {"groups": out, "ungrouped_failures": ungrouped}


# --------------------------------------------------------------------------- oldest cause, headline

def oldest_cause(inputs: dict[str, Any], blockers: list[dict[str, Any]], groups: dict[str, Any]) -> dict[str, Any] | None:
    steps = _d(inputs.get("steps"))
    accepted = {str(s.get("cluster")) for s in _l(steps.get("steps")) if _d(s).get("verdict") == "accepted"}
    for r in _l(steps.get("rejected")):
        r = _d(r)
        if r.get("kind") == "close" or not r.get("cluster") or str(r.get("cluster")) in accepted:
            continue
        return {"source": "verification/loop/steps.json#rejected", "cluster": str(r.get("cluster")), "card": r.get("card"),
                "at": r.get("at"), "cause": str(r.get("reason") or "")[:240]}
    for c, why in sorted(_d(_d(inputs.get("deferred")).get("reasons")).items()):
        return {"source": "verification/loop/deferred.json", "cluster": c, "card": None, "at": None, "cause": str(why)[:240]}
    if groups["groups"]:
        g = groups["groups"][0]
        return {"source": "parity scenario records", "cluster": None, "card": None, "at": None,
                "cause": "%s (%s) across %d owner(s)" % (g["exception"], g["mechanism"], len(g["owners"]))}
    open_ = [b for b in blockers if b["status"] == "open"]
    if open_:
        return {"source": "admitted plan (M2)", "cluster": None, "card": None, "at": None, "cause": open_[0]["cause"]}
    return None


def headline(ms: list[dict[str, Any]], validity: dict[str, Any], d: dict[str, Any]) -> str:
    st = {m["id"]: m["state"] for m in ms}
    if d["verdict"] == "ACCEPT" and d["ship"]:
        text = "full release (M5 ACCEPT, ship=true)"
    elif st["delivered-and-usable"] == DEMONSTRATED:
        text = "deployed at %s; not released (M5 %s, ship=false)" % (d["route_url"] or "an unrecorded URL", d["verdict"])
    elif st["application-behavior-preserved"] == DEMONSTRATED:
        text = "application behavior preserved; not delivered"
    elif st["target-structurally-viable"] == DEMONSTRATED:
        text = "runtime behavior failing" if st["application-behavior-preserved"] == NOT_DEMONSTRATED else "runtime behavior unresolved"
    elif st["target-structurally-viable"] == NOT_DEMONSTRATED:
        text = "target not structurally viable"
    else:
        text = "target structure unmeasured"
    return text + ("" if validity["valid"] else "; measurement invalid")


def build(inputs: dict[str, Any], *, classification: Any = None) -> dict[str, Any]:
    plans = [p for p in _l(inputs.get("plans")) if isinstance(p, dict)]
    plans = sorted(plans, key=lambda p: p["revision"])
    plan = plans[0] if plans else None
    latest = plans[-1] if plans else None
    modes = owed_modes(inputs.get("decisions"))
    par = inputs.get("parity_evidence")
    parity = par[0] if isinstance(par, (list, tuple)) and par and isinstance(par[0], dict) else None
    parity_reason = str(par[1]) if isinstance(par, (list, tuple)) and len(par) > 1 else "not read"
    ctr = contract(inputs, plan)
    blockers = release_blockers(latest, modes=modes, m1=inputs.get("m1_facts"), parity=parity, parity_reason=parity_reason,
                                toolchain=ctr["source"]["build"]["toolchain"])
    validity = measurement_validity(inputs)
    ms = milestones(inputs, blockers, validity, modes)
    d = delivery(inputs)
    groups = causal_groups(inputs, latest)
    order = [m["id"] for m in ms]
    last = None
    for m in ms:
        if m["state"] == DEMONSTRATED:
            last = m["id"]
    nxt = None
    if not validity["valid"]:
        nxt = {"milestone": None, "prerequisite": "a valid measurement: %s" % validity["findings"][0]}
    else:
        for m in ms:
            if m["state"] != DEMONSTRATED:
                nxt = {"milestone": m["id"], "prerequisite": (m["gaps"] or ["unknown"])[0]}
                break
    added = []
    if plan and latest and latest is not plan:
        base = {n.get("outcome_id") for n in plan["nodes"] if n.get("role") == "repair"}
        for p in plans[1:]:
            for n in p["nodes"]:
                if n.get("role") == "repair" and n.get("outcome_id") not in base:
                    base.add(n.get("outcome_id"))
                    added.append({"outcome_id": n.get("outcome_id"), "revision": p["revision"]})
    open_ = [b for b in blockers if b["status"] == "open"]
    out = {
        "schema": SCHEMA,
        "note": "a derived view: it grants, admits, issues and accepts nothing; completed-card percentages are not migration percentages",
        "plan": ({"revision": plan["revision"], "latest_revision": latest["revision"], "digest": plan["digest"],
                  "run_id": plan["run_id"], "policy": plan["policy"]} if plan else None),
        "inventory": inventory(plan) if plan else None,
        "planned_vs_added": {"planned_repair_outcomes": (inventory(plan)["repair_outcomes"] if plan else None),
                             "added": added if len(plans) > 1 else None,
                             "note": "additions are known only from the plan revisions given" if len(plans) < 2 else ""},
        "contract": ctr,
        "security_modes": modes,
        "release_blockers": blockers,
        "release_blocker_summary": {"known": latest is not None,
                                    "reason": "" if latest is not None else "no admitted plan was read: the release blockers are unknown, not none",
                                    "rows": len(blockers), "open": len(open_),
                                    "entry_points_open": len({b["entry_point"] for b in open_ if b["entry_point"]}),
                                    "by_owner": dict(sorted({o: sum(1 for b in open_ if b["owner"] == o) for o in {b["owner"] for b in open_}}.items()))},
        "measurement": validity,
        "milestones": ms,
        "distinctions": distinctions(ms, d, classification),
        "delivery": d,
        "causal_groups": groups,
        "headline": {
            "state": headline(ms, validity, d),
            "last_demonstrated_milestone": last,
            "milestone_order": order,
            "current_candidate": {"delivery": d["candidate"], "tree": str(_d(inputs.get("worklist")).get("candidate_sha256") or "") or None,
                                  "loop_head": _d(inputs.get("state")).get("head") or None},
            "next_missing_prerequisite": nxt,
            "oldest_unresolved_cause": oldest_cause(inputs, blockers, groups),
            "release_verdict": ({"phase": "M5", "verdict": d["verdict"], "ship": d["ship"], "url": d["route_url"]} if d["verdict"] else
                                {"phase": "M4", "verdict": str(_d(inputs.get("m4_verdict")).get("verdict") or "") or None, "ship": False,
                                 "url": None, "note": "M4 close is not ship"}),
        },
        "unknown_inputs": dict(sorted(_d(inputs.get("missing")).items())),
    }
    out["digest"] = _digest(out)
    return out


# --------------------------------------------------------------------------- reading (the only I/O)

def _json(p: Path) -> tuple[Any, str]:
    if not p.is_file():
        return None, "%s is absent" % p.name
    try:
        return json.loads(p.read_text(encoding="utf-8")), ""
    except (OSError, ValueError) as exc:
        return None, "%s is unreadable: %s" % (p.name, exc)


def load_plan_file(p: Path) -> tuple[dict[str, Any] | None, str]:
    if p.suffix == ".gz":
        import gzip
        try:
            doc = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
        except (OSError, ValueError) as exc:
            return None, "%s is unreadable: %s" % (p.name, exc)
    else:
        doc, why = _json(p)
        if doc is None:
            return None, why
    plan = normalize_plan(doc)
    return (plan, "") if plan else (None, "%s is not a plan revision or frozen plan semantics" % p.name)


def load_inputs(root: Path, plan_paths: list[Path] | None = None) -> dict[str, Any]:
    """Read (never write) what the map is derived from. Every absent input is
    named in ``missing`` with a reason."""
    from planner.paths import (ADMISSION_RECEIPT, DELIVERY_CANDIDATE, DELIVERY_DEPLOYMENT, DELIVERY_LIVE, DELIVERY_PIPELINE,
                               LOOP_ACCEPTED, LOOP_DEFERRED, LOOP_STATE, LOOP_STEPS, M5_VERDICT, PARITY_DIR, PINS,
                               PLAN_SEMANTICS, SOURCE_MANIFEST, VERIFY_BOOT, VERIFY_PACKAGE, VERIFY_RUN, WORKLIST,
                               producer_receipt)
    root = Path(root)
    missing: dict[str, str] = {}
    out: dict[str, Any] = {"missing": missing}

    def get(name: str, rel: Any) -> Any:
        doc, why = _json(root / rel)
        if doc is None:
            missing[name] = why
        return doc
    plans = []
    for p in plan_paths or []:
        plan, why = load_plan_file(Path(p))
        if plan is None:
            missing["plan:%s" % Path(p).name] = why
        else:
            plans.append(plan)
    if not plan_paths:
        sem, why = _json(root / PLAN_SEMANTICS)
        plan = normalize_plan(sem) if isinstance(sem, dict) and sem.get("frozen") is True else None
        if plan is None:
            missing["plan"] = why or "%s is not frozen or carries no graph; pass --plan plan.r<N>.json" % PLAN_SEMANTICS
        else:
            plans.append(plan)
    out["plans"] = plans
    try:
        from planner.decisions import load_decisions
        out["decisions"] = load_decisions(root)
    except Exception as exc:  # noqa: BLE001
        out["decisions"] = None
        missing["decisions"] = "decisions.yaml cannot be read: %s" % exc
    try:
        from planner.yamlite import load_yaml
        out["migration"] = load_yaml(root / "migration.yaml") if (root / "migration.yaml").is_file() else None
    except Exception:  # noqa: BLE001
        out["migration"] = None
    if out["migration"] is None:
        missing["migration"] = "migration.yaml is absent or unreadable"
    out["pins"] = get("pins", PINS)
    out["freeze"] = get("freeze", producer_receipt(root, "freeze").relative_to(root))
    out["source_manifest"] = get("source_manifest", SOURCE_MANIFEST)
    out["build_receipt"] = get("build_receipt", producer_receipt(root, "build").relative_to(root))
    out["m1_facts"] = get("m1_facts", Path("evidence") / "handoff" / "m1-facts.json")
    for name, rel in (("admission", ADMISSION_RECEIPT), ("worklist", WORKLIST), ("run", VERIFY_RUN), ("state", LOOP_STATE),
                      ("deferred", LOOP_DEFERRED), ("steps", LOOP_STEPS), ("package", VERIFY_PACKAGE), ("boot", VERIFY_BOOT)):
        out[name] = get(name, rel)
    out["m4_verdict"] = get("m4_verdict", Path("evidence") / "verdicts" / "m4-verdict.json")
    out["m5"] = {k: _json(root / rel)[0] for k, rel in (("verdict", M5_VERDICT), ("candidate", DELIVERY_CANDIDATE),
                                                         ("pipeline", DELIVERY_PIPELINE), ("deployment", DELIVERY_DEPLOYMENT),
                                                         ("live", DELIVERY_LIVE))}
    from planner.worklist import parity_receipt_file, parity_state
    modes = owed_modes(out["decisions"])

    def scen(base: Path, mode: str) -> dict[str, Any]:
        d = base / ("scenarios" if mode == "disabled" else "scenarios-%s" % mode)
        recs = {}
        for p in sorted(d.glob("*.json")) if d.is_dir() else []:
            doc, _ = _json(p)
            if isinstance(doc, dict) and doc.get("scenario"):
                recs[str(doc["scenario"])] = doc
        return recs
    parity, accepted = {}, {}
    for mode in modes:
        rec, _ = _json(root / parity_receipt_file(mode))
        st = parity_state(rec) if isinstance(rec, dict) else {}
        parity[mode] = {"receipt": rec if isinstance(rec, dict) else None, "records": scen(root / PARITY_DIR, mode),
                        "receipt_scenarios": dict(st.get("scenarios") or {}), "receipt_entry_points": dict(st.get("entry_points") or {})}
        accepted[mode] = {"records": scen(root / LOOP_ACCEPTED / "parity", mode)}
    out["parity"], out["accepted_parity"] = parity, accepted
    try:
        from planner.measurement import execution
        out["execution"] = execution(out["worklist"], out["run"], "", root)
    except Exception as exc:  # noqa: BLE001
        out["execution"] = None
        missing["execution"] = "the measurement execution record cannot be derived: %s" % exc
    try:
        import m5_delivery
        out["parity_evidence"] = m5_delivery.parity_evidence(root)
    except Exception as exc:  # noqa: BLE001 - unknown, never a pass
        out["parity_evidence"] = (None, "the M4-bound parity evidence cannot be read: %s" % exc)
    return out


# --------------------------------------------------------------------------- rendering

def render_lines(cm: dict[str, Any]) -> list[str]:
    h = cm["headline"]
    L = ["**%s**" % h["state"]]
    L.append("- last demonstrated milestone: %s" % (dict(MILESTONES).get(h["last_demonstrated_milestone"]) or "none"))
    cc = h["current_candidate"]
    L.append("- current candidate: delivery %s; measured tree %s; loop head %s" % (
        (cc["delivery"] or "none")[:12], (cc["tree"] or "none")[:12], cc["loop_head"] or "none"))
    nx = h["next_missing_prerequisite"]
    L.append("- next missing prerequisite: %s" % ("none" if not nx else "%s%s" % (
        ("[%s] " % dict(MILESTONES)[nx["milestone"]]) if nx.get("milestone") else "", nx["prerequisite"])))
    oc = h["oldest_unresolved_cause"]
    L.append("- oldest unresolved cause: %s" % ("none recorded" if not oc else "%s%s (%s)" % (
        "".join(x for x in (oc.get("cluster") and "%s " % oc["cluster"], oc.get("at") and "at %s " % oc["at"]) if x)
        + ("— " if oc.get("cluster") or oc.get("at") else ""), oc["cause"], oc["source"])))
    rv = h["release_verdict"]
    L.append("- release verdict: %s %s, ship=%s%s" % (rv["phase"], rv["verdict"] or "none", str(rv["ship"]).lower(),
                                                    (", URL %s" % rv["url"]) if rv.get("url") else ""))
    L.append("- milestones: " + "; ".join("%s %s" % (m["title"], m["state"]) for m in cm["milestones"]))
    ds = cm["distinctions"]
    L.append("- functional %s; delivery %s; full release %s; repeatability %s" % (
        ds["functional"], ds["delivery"], ds["full_release"], ds["repeatability"]))
    if not cm["measurement"]["valid"]:
        for f in cm["measurement"]["findings"]:
            L.append("  - measurement: %s" % f)
    inv = cm["inventory"]
    if inv:
        L.append("- plan r%s: %d requirements %s; %d repair outcomes; %d ship-blocking verification group(s) over %d entry point(s)" % (
            cm["plan"]["revision"], inv["requirements"], inv["requirements_by_status"], inv["repair_outcomes"],
            inv["ship_blocking_verification_groups"], inv["unresolved_entry_points"]))
    else:
        L.append("- plan: unknown (%s)" % cm["unknown_inputs"].get("plan", "not read"))
    s = cm["release_blocker_summary"]
    if not s["known"]:
        L.append("- release blockers: unknown (%s)" % s["reason"])
    else:
        L.append("- release blockers: %d open of %d, %d entry point(s); owners %s" % (s["open"], s["rows"], s["entry_points_open"], s["by_owner"] or "{}"))
    for b in [b for b in cm["release_blockers"] if b["status"] == "open"][:40]:
        L.append("  - %s [%s] exit: %s" % (_ep_short(b["entry_point"]) if b["entry_point"] else b["id"], b["owner_label"], b["exit"]))
    for g in cm["causal_groups"]["groups"]:
        L.append("- causal group: %s (%s), producer %s %s, %d owner(s), %d check(s) kept" % (
            g["exception"], g["mechanism"], g["producer"]["family"], ",".join(g["producer"]["recipes"]), len(g["owners"]), len(g["checks"])))
    for lim in cm["contract"]["limitations"]:
        L.append("- scope limit: %s" % lim)
    return L


def main(argv: list[str] | None = None) -> int:
    import argparse
    lib = Path(__file__).resolve().parent
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    ap = argparse.ArgumentParser(description="Print the completion map (read-only).")
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--plan", type=Path, action="append", default=[], help="plan.r<N>.json (repeatable); default the frozen plan semantics")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    cm = build(load_inputs(args.root.resolve(), args.plan))
    if args.json:
        print(json.dumps(cm, indent=2, sort_keys=True))
    else:
        print("\n".join(render_lines(cm)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
