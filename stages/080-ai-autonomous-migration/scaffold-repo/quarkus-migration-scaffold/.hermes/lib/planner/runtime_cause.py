"""Who caused a runtime failure a candidate meets: a classifier, never a verdict.

A 5xx whose first product frame sits in a file the candidate did not change
does NOT show that the failure pre-dates the candidate: a changed caller can
pass an unchanged callee invalid input (the counterexample to the v17
attribution rule). Only a measurement of the BASELINE -- the accepted tree
before this candidate -- that shows the same failure can. So:

  pre-existing-owner-defect  the same scenario failed on the baseline with the
                             same exception and the same first product frame
                             (and, when both records carry one, the same stack
                             digest), the baseline record is bound to the
                             baseline tree, and the frame's file was committed
                             by an accepted step of ANOTHER cluster
  candidate-regression       the baseline measured that scenario and it PASSED,
                             or failed differently
  ambiguous                  anything else: no baseline measurement of the
                             scenario, a record not bound to the baseline tree,
                             no stack, a changed file on the failing path with a
                             different stack, the throwing file changed by the
                             candidate, or no recorded owner

``classify`` is PURE over its arguments: it reads no file, so an authority can
call it on inputs it measured itself and trust nothing a worker wrote. ``root``
is accepted for the interface only and is never read. The serial loop's
loader (``inputs_from_root``) reads the loop's own records; that is a
convenience for diagnosis, not an authority.

Inputs
  issued    the issued card: {cluster, task_id, items, gate_items, scenarios,
            entry_points, write_set, amendments}
  cur       the candidate's measurement: {"failures": [failure]} where a
            failure is {obligation, scenario, entry_point, exception,
            frames: [{class, method, file, line}], stack_sha256}, plus
            "changed": [paths the candidate changed]
  steps     the loop's accepted steps: [{cluster, card, commit, verdict,
            changed, outcome_id?}]
  baseline  {"tree": the baseline product-tree digest, "records":
            {scenario id: {verdict, reason, binding: {candidate_sha256},
            server_error: {exception, frames, stack_sha256}}}}
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

PRE_EXISTING, REGRESSION, AMBIGUOUS = "pre-existing-owner-defect", "candidate-regression", "ambiguous"


def _first(frames: Any) -> dict[str, Any]:
    for f in frames or []:
        if isinstance(f, dict) and f.get("class"):
            return f
    return {}


def _sig(exception: str, frame: dict[str, Any]) -> tuple[str, str, str]:
    return (str(exception or ""), str(frame.get("class") or ""), str(frame.get("method") or ""))


def _owner_of(path: str, steps: list[dict[str, Any]], cluster: str) -> dict[str, Any] | None:
    """The latest accepted step of another cluster that committed `path`."""
    hit = None
    for st in steps or []:
        if not isinstance(st, dict) or st.get("verdict") != "accepted":
            continue
        if path in [str(p) for p in st.get("changed") or []]:
            hit = st
    if hit is None or str(hit.get("cluster") or "") == cluster:
        return None
    return {"cluster": str(hit.get("cluster") or ""), "card": str(hit.get("card") or ""),
            "commit": str(hit.get("commit") or "")[:40], "outcome_id": str(hit.get("outcome_id") or ""), "paths": [path]}


def _one(failure: dict[str, Any], issued: dict[str, Any], changed: set[str], steps: list[dict[str, Any]],
         baseline: dict[str, Any]) -> dict[str, Any]:
    sid = str(failure.get("scenario") or "")
    ev: list[dict[str, Any]] = [{"kind": "candidate-failure", "scenario": sid, "exception": failure.get("exception") or "",
                                  "first_frame": _first(failure.get("frames")), "stack_sha256": failure.get("stack_sha256") or ""}]

    def out(cls: str, reason: str, owner: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"class": cls, "owner": owner, "evidence": ev, "reason": reason}

    frame = _first(failure.get("frames"))
    if not sid:
        return out(AMBIGUOUS, "the failure names no scenario, so no baseline measurement can be matched to it")
    if not frame or not failure.get("exception"):
        return out(AMBIGUOUS, "scenario %s failed with no product stack on record; its cause cannot be located" % sid)
    rec = (baseline.get("records") or {}).get(sid) if isinstance(baseline.get("records"), dict) else None
    if not isinstance(rec, dict):
        return out(AMBIGUOUS, "the baseline tree has no recorded measurement of scenario %s: whether the failure pre-dates "
                              "the candidate is unknown" % sid)
    tree = str(baseline.get("tree") or "")
    bound = str(((rec.get("binding") or {}) if isinstance(rec.get("binding"), dict) else {}).get("candidate_sha256") or "")
    ev.append({"kind": "baseline-record", "scenario": sid, "verdict": rec.get("verdict") or "", "bound_to": bound,
               "baseline_tree": tree})
    if not tree or bound != tree:
        return out(AMBIGUOUS, "the baseline record of %s is bound to %s, not to the baseline tree %s: it is not a measurement "
                              "of that tree" % (sid, bound[:12] or "nothing", tree[:12] or "(unknown)"))
    verdict = str(rec.get("verdict") or "")
    if verdict == "PASS":
        return out(REGRESSION, "scenario %s PASSED on the baseline tree and fails on the candidate: the candidate caused it"
                               % sid)
    if verdict != "FAIL":
        return out(AMBIGUOUS, "the baseline verdict of %s is %r, which proves neither" % (sid, verdict))
    se = rec.get("server_error") if isinstance(rec.get("server_error"), dict) else {}
    bframe = _first(se.get("frames"))
    ev.append({"kind": "baseline-failure", "exception": se.get("exception") or "", "first_frame": bframe,
               "stack_sha256": se.get("stack_sha256") or ""})
    if not bframe or not se.get("exception"):
        return out(AMBIGUOUS, "scenario %s failed on the baseline too, but with no product stack on record to compare" % sid)
    if _sig(se.get("exception"), bframe) != _sig(failure.get("exception"), frame):
        return out(REGRESSION, "scenario %s failed differently on the baseline (%s at %s.%s) than on the candidate (%s at "
                               "%s.%s)" % (sid, se.get("exception"), bframe.get("class"), bframe.get("method"),
                                           failure.get("exception"), frame.get("class"), frame.get("method")))
    same_stack = bool(se.get("stack_sha256")) and se.get("stack_sha256") == failure.get("stack_sha256")
    on_path = sorted({str(f.get("file") or "") for f in failure.get("frames") or [] if isinstance(f, dict)} & changed)
    top = str(frame.get("file") or "")
    if top in changed:
        return out(AMBIGUOUS, "the failure is thrown in %s, which the candidate changed: the baseline failed there too, "
                              "but the candidate now owns that code" % top)
    if on_path and not same_stack:
        return out(AMBIGUOUS, "the candidate changed %s on the failing path and the stack differs from the baseline's: "
                              "the same exception may now arrive by another route" % ", ".join(on_path))
    owner = _owner_of(top, steps, str(issued.get("cluster") or ""))
    if owner is None:
        return out(AMBIGUOUS, "the same failure is proven on the baseline, but no accepted step of another cluster "
                              "committed %s: there is no owner to name" % (top or "the throwing file"))
    ev.append({"kind": "owner", **owner})
    return out(PRE_EXISTING, "scenario %s failed identically on the baseline tree %s (%s at %s.%s%s); %s was committed by "
                             "the accepted step of %s" % (sid, tree[:12], failure.get("exception"), frame.get("class"),
                                                         frame.get("method"), ", same stack" if same_stack else "", top,
                                                         owner["cluster"]), owner)


def classify(root: Path | None, issued: dict[str, Any], cur: dict[str, Any], steps: list[dict[str, Any]],
             baseline: dict[str, Any]) -> dict[str, Any]:
    """{"class", "owner", "evidence", "reason"} for the candidate's failures
    taken together. pre-existing-owner-defect only when EVERY failure is,
    with one owner; candidate-regression when any failure is; ambiguous
    otherwise. Pure: `root` is never read."""
    del root  # the interface carries it; the classifier reads nothing
    failures = [f for f in (cur or {}).get("failures") or [] if isinstance(f, dict)]
    changed = {str(p) for p in (cur or {}).get("changed") or []}
    if not failures:
        return {"class": AMBIGUOUS, "owner": None, "evidence": [], "reason": "no runtime failure to classify"}
    parts = [_one(f, issued or {}, changed, list(steps or []), baseline or {}) for f in failures]
    ev = [e for p in parts for e in p["evidence"]]
    reg = [p for p in parts if p["class"] == REGRESSION]
    if reg:
        return {"class": REGRESSION, "owner": None, "evidence": ev, "reason": "; ".join(p["reason"] for p in reg)}
    if all(p["class"] == PRE_EXISTING for p in parts):
        owners = {(p["owner"]["cluster"], p["owner"]["commit"]) for p in parts}
        if len(owners) == 1:
            o = dict(parts[0]["owner"])
            o["paths"] = sorted({q for p in parts for q in p["owner"]["paths"]})
            return {"class": PRE_EXISTING, "owner": o, "evidence": ev, "reason": "; ".join(p["reason"] for p in parts)}
        return {"class": AMBIGUOUS, "owner": None, "evidence": ev,
                "reason": "pre-existing failures of %d different owners: no single owner" % len(owners)}
    return {"class": AMBIGUOUS, "owner": None, "evidence": ev,
            "reason": "; ".join(p["reason"] for p in parts if p["class"] == AMBIGUOUS)}


# ---------------------------------------------------------------------------
# the serial loop's inputs (diagnosis only; an authority measures its own)
# ---------------------------------------------------------------------------

def failures_of(worklist: dict[str, Any], issued: dict[str, Any], records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """The candidate's runtime failures on this card's scenarios: its issued
    obligations and what its sealed scenarios / entry points report now, each
    with the server error its scenario record carries."""
    from planner.worklist import issued_parity_plan
    ids = {str(i) for i in (issued.get("items") or [])} | {str(i) for i in (issued.get("gate_items") or [])}
    plan = issued_parity_plan(issued)
    sids, eps = set(plan.get("scenarios") or []), set(plan.get("entry_points") or [])
    out = []
    for i in worklist.get("items") or []:
        if not isinstance(i, dict) or str(i.get("source") or "") not in ("parity", "runtime"):
            continue
        sid = str(i.get("scenario") or "")
        if not (str(i.get("id")) in ids or (sid and sid in sids) or (not sid and str(i.get("entry_point") or "") in eps)):
            continue
        se = ((records.get(sid) or {}).get("server_error") or {}) if sid else {}
        out.append({"obligation": str(i.get("id")), "scenario": sid, "entry_point": str(i.get("entry_point") or ""),
                    "exception": str(se.get("exception") or ""), "frames": list(se.get("frames") or []),
                    "stack_sha256": str(se.get("stack_sha256") or "")})
    return out


def scenario_records(base: Path) -> dict[str, dict[str, Any]]:
    """scenario id -> its verdict record, under one parity directory (both modes)."""
    from planner.canonical import load_json
    out: dict[str, dict[str, Any]] = {}
    for sub in ("scenarios", "scenarios-enabled"):
        d = Path(base) / sub
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.json")):
            try:
                doc = load_json(p)
            except (OSError, ValueError):
                continue
            if isinstance(doc, dict) and doc.get("scenario"):
                out[str(doc["scenario"])] = doc
    return out


def inputs_from_root(root: Path, issued: dict[str, Any], worklist: dict[str, Any], changed: list[str],
                     steps: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """(cur, steps, baseline) from the serial loop's own records: the live
    scenario records for the candidate, the accepted parity snapshot for the
    baseline, and the last accepted step's candidate digest as the baseline
    tree. Diagnosis only."""
    from planner.paths import LOOP_ACCEPTED, PARITY_DIR
    live = scenario_records(Path(root) / PARITY_DIR)
    base = scenario_records(Path(root) / LOOP_ACCEPTED / "parity")
    acc = [s for s in (steps.get("steps") or []) if isinstance(s, dict) and s.get("verdict") in ("accepted", "baseline")]
    tree = str((acc[-1] if acc else {}).get("candidate_sha256") or "")
    cur = {"failures": failures_of(worklist, issued, live), "changed": list(changed)}
    return cur, list(steps.get("steps") or []), {"tree": tree, "records": base}
