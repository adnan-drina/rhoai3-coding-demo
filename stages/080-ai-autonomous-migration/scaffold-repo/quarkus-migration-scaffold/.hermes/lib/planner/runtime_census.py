"""The first-package census (R-3; M-2 "at the first viable package, run their real application checks promptly").

v31 met its behaviour-phase blockers one card at a time, hours apart, although the runtime-feedback sweep had compared
the whole scenario phase on the first package. This census reads that comparison ONCE, as soon as it exists:

  * every FAIL scenario record, with the files its evidence names -- the product frames of its server error (the
    structured frames, or the log excerpt) and the source file of the entry point it exercises;
  * the open cards that judge the scenario now (native_control.open_judges) and the open cards whose write set holds an
    evidenced file (``reachable_by``); a header-only difference is reachable through an open adapter requirement;
  * the shared producers (completion_map.causal_groups: recursion and same root exception) and shared signatures.

A FAIL that no open card can reach is a planning gap; ``unreachable`` names every one at once. The census is evidence
and a gate input, never acceptance: it binds to the candidate its records were measured on. Nothing here knows a
specimen.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

SCHEMA = "rhoai3.runtime-census/v1"
CENSUS = Path("verification") / "loop" / "runtime-census.json"
HEADER_ONLY_PREFIX = "header "


def _class_file(cls: str, known: set[str]) -> str:
    rel = "src/main/java/%s.java" % cls.split("$", 1)[0].replace(".", "/")
    if rel in known:
        return rel
    # a nested type recorded with '.' (Outer.Inner): its file is the outer type's
    parts = cls.split(".")
    for i in range(len(parts) - 1, 0, -1):
        cand = "src/main/java/%s.java" % "/".join(parts[:i])
        if cand in known:
            return cand
    return ""


def _reason_kinds(reason: str) -> set[str]:
    kinds = set()
    for part in str(reason or "").split("; "):
        p = part.strip()
        if p.startswith("status "):
            kinds.add("status")
        elif p.startswith("body "):
            kinds.add("body")
        elif p.startswith("effect "):
            kinds.add("effect")
        elif p.startswith(HEADER_ONLY_PREFIX):
            kinds.add("header")
    return kinds


def census(*, records: dict[str, dict[str, Any]], plan: dict[str, Any], native_status: Callable[[str], str],
           entry_points: list[dict[str, Any]], types: list[dict[str, Any]], tree: str,
           source_responses: dict[str, dict[str, Any]] | None = None,
           advice_shapes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The census document (pure). ``records``: scenario id -> its comparison record (rhoai3.scenario-parity/v1).

    Which files a failure's evidence names decides who can reach it:
      * a server error with product frames: those frame files -- the causal site, not the handler that called it;
      * a SOURCE response its exception advice produced (``source_responses`` in an ``advice_shapes`` shape): the
        advice's file is required as well -- only the advice reproduces that response (H-20, v31);
      * otherwise the source file of the entry point the scenario exercises."""
    from completion_map import _frames, causal_groups
    from planner.native_control import EXECUTABLE_STATUSES, open_judges
    known = {str(t.get("path") or "") for t in types or [] if isinstance(t, dict) and t.get("path")}
    type_path = {str(t.get("fqn")): str(t.get("path") or "") for t in types or [] if isinstance(t, dict)}
    ep_file = {str(e.get("id")): type_path.get(str(e.get("type") or ""), "") for e in entry_points or [] if isinstance(e, dict)}
    judges = open_judges(plan, native_status)
    open_nodes = [n for n in plan.get("nodes") or [] if n.get("role") == "repair" and native_status(n["outcome_id"]) in EXECUTABLE_STATUSES]
    adapter_open = [n["outcome_id"] for n in open_nodes
                    if any(str(q).startswith("req:adapter-behavior:") for q in n.get("requirements") or [])]
    failures, unreachable, unattributed = [], [], []
    for sid, r in sorted((records or {}).items()):
        if not isinstance(r, dict) or r.get("verdict") != "FAIL":
            continue
        sid = sid if sid.startswith("sc:") else "sc:" + sid
        se = r.get("server_error") if isinstance(r.get("server_error"), dict) else {}
        files = sorted({f for f in (_class_file(str(fr.get("class") or ""), known) for fr in _frames(se)) if f})
        epf = ep_file.get(str(r.get("entry_point") or ""), "")
        src = (source_responses or {}).get(sid) or (source_responses or {}).get(sid[3:]) or {}
        advice = None
        if src and advice_shapes:
            from planner.exception_advice import advice_response
            advice = advice_response(src.get("status"), src.get("body"), advice_shapes)
        required = [advice["path"]] if advice and advice.get("path") else []
        site = files or ([epf] if epf else [])
        evidenced = sorted(set(site) | set(required))
        kinds = _reason_kinds(str(r.get("reason") or ""))
        owns = lambda n, fs: bool(set(n.get("plan_paths") or []) & set(fs))   # noqa: E731
        reach = sorted({n["outcome_id"] for n in open_nodes
                        if (not required or owns(n, required)) and (owns(n, site) or owns(n, required))})
        how = ("the advice the source answered through is owned" if required and reach else
               "write set holds the causal site" if reach else "")
        if not reach and kinds == {"header"} and adapter_open:
            reach, how = sorted(adapter_open), "header-only difference: an open adapter requirement"
        row = {"scenario": sid, "entry_point": r.get("entry_point") or None, "kinds": sorted(kinds),
               "source_advice": advice.get("fqn") if advice else None,
               "exception": str((se or {}).get("exception") or "") or None, "evidenced_files": evidenced,
               "open_judges": sorted(judges.get(sid, [])), "reachable_by": reach, "how": how}
        failures.append(row)
        if not reach and evidenced:
            unreachable.append(row)        # its evidence names files no open card's write set holds
        elif not reach:
            unattributed.append(row)       # no file named: unproven either way, reported, never a gate
    groups = causal_groups({"parity": {"disabled": {"records": {sid: dict(r, verdict=r.get("verdict")) for sid, r in (records or {}).items()}}},
                            "accepted_parity": {}}, plan)
    return {"schema": SCHEMA, "tree": tree, "failures": failures, "unreachable": unreachable, "unattributed": unattributed,
            "groups": groups.get("groups") or [], "shared_signatures": groups.get("shared_signatures") or [],
            "summary": {"failing": len(failures), "unreachable": len(unreachable), "unattributed": len(unattributed),
                        "groups": len(groups.get("groups") or [])}}


def of_root(root: Path, plan: dict[str, Any], native_status: Callable[[str], str], tree: str) -> dict[str, Any]:
    """The census over the comparison records on disk (verification/parity/scenarios) bound to ``tree``."""
    from planner.paths import EVIDENCE_BUNDLE, PARITY_DIR
    root = Path(root)
    from planner.worklist import PARITY_SCENARIO_SUBDIRS
    records: dict[str, dict[str, Any]] = {}
    # every security mode the comparator wrote (the enabled-mode scenario ids are their own: sc:auth-...)
    files = [f for sub in PARITY_SCENARIO_SUBDIRS for f in sorted((root / PARITY_DIR / sub).glob("*.json"))]
    for f in files:
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict) or not doc.get("scenario"):
            continue
        if str((doc.get("binding") or {}).get("candidate_sha256") or "") not in ("", tree):
            continue                         # measured on another tree: not this candidate's evidence
        records[str(doc["scenario"])] = doc
    try:
        bundle = json.loads((root / EVIDENCE_BUNDLE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        bundle = {}
    from planner.exception_advice import shapes_of_root, source_responses
    return census(records=records, plan=plan, native_status=native_status, entry_points=bundle.get("entry_points") or [],
                  types=((bundle.get("structure") or {}).get("types")) or [], tree=tree,
                  source_responses=source_responses(root), advice_shapes=shapes_of_root(root))
