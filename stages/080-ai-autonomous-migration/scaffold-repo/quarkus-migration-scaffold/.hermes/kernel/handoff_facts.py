#!/usr/bin/env python3
"""The M1/M2 handoff facts, computed from sealed artifacts, and the reviewer's
structured comparison of the current handoff against them.

v23 (2026-09-28) handed off wrong claims no artifact made: M1/M2 said 20 of
34 entry points needed operator observations (the inventory is HTTP 34,
non-HTTP 0); M2 said "29 repair outcomes" (the plan has 30 plus 4
milestones) and recorded ``unresolved: []`` (the plan keeps 7 ship-blocking
groups over 12 HTTP entry points).

The facts are structured data bound to the task, the implementer run that
hands off, the phase and the evidence identity (M1: the evidence bundle; M2:
the published plan revision, its digest and the admission receipt it was
published under). The handoff carries them verbatim in ``metadata.facts``,
M2 also the exact unresolved ID set in ``metadata.unresolved``, and the
factual paragraph this tool generates in ``metadata.factual_summary``. Free
narrative stays in ``summary`` and is not parsed: a keyword is not a claim.

Coverage is not inferred from an HTTP method. A write needs a scenario
(``write-requires-scenario``) -- that is suitability, not coverage. An entry
point is covered only by a captured read oracle, or by a captured scenario of
that entry point whose qualification PASSED in a security mode whose capture
is bound to this evidence bundle and corpus. A source qualification FAIL or
INCONCLUSIVE is recorded source evidence, never a pass. Read-oracle, scenario,
qualification and unresolved behavior counts stay separate.

    handoff_facts.py --root . --phase m1 --write            # implementer
    handoff_facts.py --root . --phase m2 --write            # implementer ($HERMES_KANBAN_TASK/_RUN_ID)
    handoff_facts.py --root . --phase m2 --check-task t_…   # reviewer (the paved-road audit also runs it)
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_KERNEL = Path(__file__).resolve().parent
_LIB = _KERNEL.parent / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
from native_attachments import hermes_bin, latest_by_name, read_records  # noqa: E402

SCHEMA = "rhoai3.handoff-facts/v2"
INVENTORY = "evidence/entry-point-inventory.json"
BUNDLE = "evidence/planning/evidence-bundle.json"
READ_ORACLES = "verification/source-oracles"
MODES = {"disabled": "scenarios", "enabled": "scenarios-enabled"}
ADMISSION = "evidence/planning/admission-receipt.json"
PLAN_SEMANTICS = "evidence/planning/plan-semantics.json"  # frozen by the first ADMITTED receipt
READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
PLAN_NAME = re.compile(r"^plan\.r(\d+)\.json$")
# the fields a handoff must carry verbatim (metadata.facts); the rest is explanation
REQUIRED = {
    "m1": ("binding", "entry_points", "read_oracles", "scenarios", "coverage", "operator_observations_needed"),
    "m2": ("binding", "cards", "requirements", "unresolved", "admission"),
}


def out_path(phase: str) -> str:
    return "evidence/handoff/%s-facts.json" % phase


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _bundle_digest(root: Path) -> str:
    from planner.canonical import digest
    return digest(_load(root / BUNDLE)) if (root / BUNDLE).is_file() else ""


def _binding(phase: str, task: str, run: str, **evidence: Any) -> dict[str, Any]:
    return dict({"phase": phase, "task": str(task or ""), "run": str(run or "")}, **evidence)


# ---------------------------------------------------------------- M1

def read_suitability(ep: dict[str, Any] | None) -> str:
    """Why a READ oracle does not fit an entry point, from the inventory. This
    is suitability, never coverage: a write still needs its scenario."""
    if ep is None:
        return "not-in-inventory"
    if str(ep.get("kind") or "") != "http":
        return "non-http-observation"  # the only class that needs an operator observation
    if str(ep.get("http_method") or "").upper() not in READ_METHODS:
        return "write-requires-scenario"
    path = str(ep.get("http_path") or "")
    if "*" in path or not path.startswith("/"):
        return "needs-request-fixture"  # a route pattern, not a request; not evidence of unreachable behavior
    return "http-read-not-captured"


def _mode_coverage(root: Path, mode: str, sub: str, bundle_sha: str) -> dict[str, Any]:
    """The captured scenarios of one security mode per entry point, with their
    qualification -- only when the capture and the qualification are bound to
    this evidence bundle, this corpus and this mode -- and the mode's summary."""
    corpus_p = root / "verification" / sub / "corpus.json"
    cap_p = root / READ_ORACLES / sub / "_capture.json"
    qual_p = root / READ_ORACLES / sub / "_qualification.json"
    cap = _load(cap_p) if cap_p.is_file() else {}
    qual = _load(qual_p) if qual_p.is_file() else {}
    rows = qual.get("scenarios") or {}
    if isinstance(rows, list):
        rows = {str(r.get("id")): r for r in rows if isinstance(r, dict)}
    verdicts = Counter(str((r or {}).get("capability") or "?") for r in rows.values() if isinstance(r, dict))
    summary: dict[str, Any] = {"status": cap.get("status") or "absent", "requested": int(cap.get("requested") or 0),
                               "captured": int(cap.get("captured") or 0),
                               "qualification": {k: verdicts.get(k, 0) for k in ("PASS", "FAIL", "INCONCLUSIVE")}}
    why = ""
    if not corpus_p.is_file():
        why = "no corpus"
    elif not cap:
        why = "no capture receipt"
    else:
        corpus_sha = hashlib.sha256(corpus_p.read_bytes()).hexdigest()
        if str(cap.get("evidence_bundle_sha256") or "") != bundle_sha:
            why = "the capture is bound to another evidence bundle"
        elif str(cap.get("corpus_sha256") or "") != corpus_sha or str(qual.get("corpus_sha256") or "") != corpus_sha:
            why = "the capture or qualification is bound to another corpus"
        elif str(cap.get("security_mode") or "") != mode or str(qual.get("security_mode") or "") != mode:
            why = "the capture or qualification was not taken in the %s security mode" % mode
    summary["bound"] = not why
    if why:
        summary["unbound_reason"] = why
        return {"summary": summary, "by_ep": {}, "fail": []}
    captured = {str(s) for s in cap.get("scenarios") or []}
    by_ep: dict[str, list[str]] = {}
    fail: list[str] = []
    for sc in _load(corpus_p).get("scenarios") or []:
        sid, ep = str(sc.get("id") or ""), str(sc.get("entry_point") or "")
        if not sid or not ep or sid not in captured:
            continue
        cap_v = str((rows.get(sid) or {}).get("capability") or "INCONCLUSIVE")
        by_ep.setdefault(ep, []).append(cap_v)
        if cap_v == "FAIL":
            fail.append(sid)
    return {"summary": summary, "by_ep": by_ep, "fail": sorted(fail)}


def m1_facts(root: Path, *, task: str = "", run: str = "") -> dict[str, Any]:
    inv = _load(root / INVENTORY)
    eps = [e for e in inv.get("entry_points") or [] if isinstance(e, dict)]
    by_id = {str(e.get("entry_point_id") or ""): e for e in eps}
    kinds = Counter(str(e.get("kind") or "?") for e in eps)
    bundle_sha = _bundle_digest(root)
    read_captured: set[str] = set()
    suitability: Counter = Counter()
    records = sorted(glob.glob(str(root / READ_ORACLES / "ep_*.json")))
    for p in records:
        rec = _load(Path(p))
        ep_id = str(rec.get("entry_point") or "")
        if str(rec.get("status") or "") == "CAPTURED":
            read_captured.add(ep_id)
        else:
            suitability[read_suitability(by_id.get(ep_id))] += 1
    modes = {m: _mode_coverage(root, m, sub, bundle_sha) for m, sub in MODES.items()}
    scenario_pass = {m: sorted(ep for ep, vs in v["by_ep"].items() if "PASS" in vs) for m, v in modes.items()}
    covered = (read_captured | {ep for eps_ in scenario_pass.values() for ep in eps_}) & set(by_id)
    unverified = sorted(e for e in by_id if e not in covered)
    return {
        "schema": SCHEMA, "phase": "m1",
        "binding": _binding("m1", task, run, evidence_bundle_sha256=bundle_sha),
        "entry_points": {"total": len(eps), "http": kinds.get("http", 0), "non_http": sum(v for k, v in kinds.items() if k != "http"),
                         "by_kind": dict(sorted(kinds.items()))},
        "read_oracles": {"records": len(records), "captured": len(read_captured), "inconclusive": sum(suitability.values()),
                         "not_captured_by_suitability": dict(sorted(suitability.items()))},
        "scenarios": {m: v["summary"] for m, v in modes.items()},
        "coverage": {"read_oracle": len(read_captured),
                     "scenario_passed": {m: len(v) for m, v in scenario_pass.items()},
                     "source_qualification_fail": {m: v["fail"] for m, v in modes.items()},
                     "covered": len(covered), "unverified": len(unverified), "unverified_entry_points": unverified},
        "operator_observations_needed": suitability.get("non-http-observation", 0),
        "note": "suitability is not coverage: a write needs a captured, qualified scenario of that entry point in a bound "
                "mode; a source qualification FAIL is source evidence, not a pass; unresolved behavior coverage is M2's count",
    }


# ---------------------------------------------------------------- M2

def published_plan_path(root: Path, task: str = "", plan: str = "") -> Path:
    """The published plan: an explicit path; else the newest plan.r<N>.json
    native attachment of the M2 card (outcome-board/v2); else, when the card
    holds none (serial-loop/v1 publishes no revision), the frozen admitted
    plan semantics, which carry the same graph."""
    if plan:
        return Path(plan)
    revs: list = []
    if task:
        named = latest_by_name(read_records(task))
        revs = sorted(((int(m.group(1)), r) for n, r in named.items() for m in [PLAN_NAME.match(n)] if m), key=lambda x: x[0])
    if revs:
        return Path(str(revs[-1][1].get("stored_path") or ""))
    sem = root / PLAN_SEMANTICS
    if sem.is_file() and _load(sem).get("frozen") is True:
        return sem
    raise ValueError("no published plan: %s holds no plan.r<N>.json native attachment and %s is not frozen"
                     % (task or "no task", PLAN_SEMANTICS))


def m2_facts(root: Path, plan_path: Path, *, task: str = "", run: str = "") -> dict[str, Any]:
    doc = _load(plan_path)
    plan = doc.get("plan") if isinstance(doc.get("plan"), dict) else doc
    if isinstance(plan.get("graph"), dict):  # the frozen plan semantics
        plan = dict(plan["graph"], requirements=plan["graph"].get("requirements") or plan.get("requirements") or [])
    nodes = [n for n in plan.get("nodes") or [] if isinstance(n, dict)]
    repairs = [n for n in nodes if n.get("role") == "repair"]
    milestones = [n for n in nodes if n.get("role") != "repair"]
    reqs = Counter(str(r.get("status") or "?") for r in plan.get("requirements") or [] if isinstance(r, dict))
    unresolved = [u for u in plan.get("unresolved") or [] if isinstance(u, dict)]
    eps = sorted({str(e) for u in unresolved for e in u.get("entry_points") or []})
    adm = _load(root / ADMISSION) if (root / ADMISSION).is_file() else {}
    # the receipt is mutable (every accepted step re-admits): only the receipt
    # the plan was published under describes the plan's input
    published = str((plan.get("provenance") or {}).get("receipt_sha256") or "")
    same = (str(adm.get("receipt_digest") or "") == published) if published else True
    return {
        "schema": SCHEMA, "phase": "m2",
        "binding": _binding("m2", task, run, plan_revision=doc.get("revision", plan.get("revision")),
                            plan_digest=str(plan.get("digest") or doc.get("plan_fingerprint") or ""),
                            policy=plan.get("policy"), published_under_receipt=published),
        "admission": {"status": (adm.get("status") or adm.get("verdict") or "absent") if same else "admitted at publication",
                      "blocks": len(adm.get("blocks") or []) if same else None},
        "cards": {"total": len(nodes), "repair": len(repairs), "milestones": len(milestones),
                  "repair_by_class": dict(sorted(Counter(str(n.get("class")) for n in repairs).items())),
                  "milestones_by_role": dict(sorted(Counter(str(n.get("role")) for n in milestones).items()))},
        "requirements": dict(sorted(reqs.items())),
        "unresolved": {"groups": len(unresolved), "requirements": len({r for u in unresolved for r in u.get("requirements") or []}),
                       "entry_points": len(eps),
                       "entry_point_kinds": dict(sorted(Counter(e.rsplit(":", 1)[-1] if ":" in e else "?" for e in eps).items())),
                       "blocks": dict(sorted(Counter(str(u.get("blocks")) for u in unresolved).items())),
                       "ids": sorted(str(u.get("id")) for u in unresolved)},
        "note": "admission blocks refuse the plan; unresolved rows are admitted release qualifications that stay open "
                "until evidence closes them (blocks: ship). Neither is cleared by prose or completion metadata.",
    }


# ---------------------------------------------------------------- the handoff

def factual_summary(facts: dict[str, Any]) -> str:
    """The factual paragraph of the handoff, generated from the facts (the
    worker copies it; the narrative around it is the worker's)."""
    if facts["phase"] == "m1":
        ep, ro, cov, sc = facts["entry_points"], facts["read_oracles"], facts["coverage"], facts["scenarios"]
        parts = ["%d entry points (%d HTTP, %d non-HTTP)." % (ep["total"], ep["http"], ep["non_http"]),
                 "Read oracles: %d captured, %d not captured (%s)." % (
                     ro["captured"], ro["inconclusive"],
                     ", ".join("%s %d" % kv for kv in ro["not_captured_by_suitability"].items()) or "none")]
        for m in MODES:
            s = sc[m]
            parts.append("Scenarios %s: %d/%d captured, qualification %d PASS / %d FAIL / %d INCONCLUSIVE%s." % (
                m, s["captured"], s["requested"], s["qualification"]["PASS"], s["qualification"]["FAIL"],
                s["qualification"]["INCONCLUSIVE"], "" if s.get("bound") else " (not bound: %s)" % s.get("unbound_reason")))
        parts.append("Entry points covered: %d (read oracle %d; passing scenario %s); unverified %d; operator "
                     "observations needed %d." % (cov["covered"], cov["read_oracle"],
                                                  ", ".join("%s %d" % kv for kv in cov["scenario_passed"].items()),
                                                  cov["unverified"], facts["operator_observations_needed"]))
        return " ".join(parts)
    c, u, r = facts["cards"], facts["unresolved"], facts["requirements"]
    return ("Plan revision %s (%s): %d cards = %d repair outcomes + %d milestones. Requirements: %s. "
            "Admission: %s. Unresolved: %d group(s), %d requirement(s), %d entry point(s) (%s), blocking %s." % (
                facts["binding"].get("plan_revision"), facts["binding"].get("policy"), c["total"], c["repair"],
                c["milestones"], ", ".join("%s %d" % kv for kv in r.items()), facts["admission"]["status"],
                u["groups"], u["requirements"], u["entry_points"],
                ", ".join("%s %d" % kv for kv in u["entry_point_kinds"].items()) or "none",
                ", ".join("%s %d" % kv for kv in u["blocks"].items()) or "nothing"))


def handoff_block(facts: dict[str, Any]) -> dict[str, Any]:
    """What the implementer puts in the review request's metadata."""
    out = {"facts": {k: facts[k] for k in REQUIRED[facts["phase"]]}, "factual_summary": factual_summary(facts)}
    if facts["phase"] == "m2":
        out["unresolved"] = list(facts["unresolved"]["ids"])
    return out


def handoff_gaps(facts: dict[str, Any], metadata: dict[str, Any] | None) -> list[str]:
    """Structured comparison of a handoff's metadata with the computed facts.
    Missing required fields, any difference, and (M2) a missing, extra,
    duplicate or foreign unresolved ID refuse. The narrative is not read."""
    meta = metadata if isinstance(metadata, dict) else {}
    phase = facts["phase"]
    want = handoff_block(facts)
    got = meta.get("facts")
    if not isinstance(got, dict):
        return ["metadata.facts is missing: run handoff_facts.py --phase %s --write and hand off its metadata block" % phase]
    gaps: list[str] = []
    for k in REQUIRED[phase]:
        if k not in got:
            gaps.append("metadata.facts.%s is missing" % k)
        elif got[k] != want["facts"][k]:
            gaps.append("metadata.facts.%s differs from the sealed artifacts: handed off %s, computed %s"
                        % (k, json.dumps(got[k], sort_keys=True)[:300], json.dumps(want["facts"][k], sort_keys=True)[:300]))
    if meta.get("factual_summary") != want["factual_summary"]:
        gaps.append("metadata.factual_summary is not the generated factual paragraph")
    if phase == "m2":
        ids = meta.get("unresolved")
        if not isinstance(ids, list):
            gaps.append("metadata.unresolved is missing (the plan keeps %d unresolved id(s))" % len(want["unresolved"]))
        else:
            ids = [str(x) for x in ids]
            dup = sorted(i for i, n in Counter(ids).items() if n > 1)
            plan_ids = set(want["unresolved"])
            missing, foreign = sorted(plan_ids - set(ids)), sorted(set(ids) - plan_ids)
            if dup:
                gaps.append("metadata.unresolved repeats %s" % ", ".join(dup))
            if missing:
                gaps.append("metadata.unresolved omits %d plan id(s): %s" % (len(missing), ", ".join(missing[:4])))
            if foreign:
                gaps.append("metadata.unresolved names %d id(s) the plan does not: %s" % (len(foreign), ", ".join(foreign[:4])))
    return gaps


def _show(task: str) -> dict[str, Any]:
    proc = subprocess.run([hermes_bin(), "kanban", "show", task, "--json"], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise ValueError("cannot read native task %s: %s" % (task, (proc.stderr or "").strip()[:200]))
    return json.loads(proc.stdout)


def current_handoff(task: str) -> dict[str, Any]:
    """The implementer run under review: the LAST implementer run of the task,
    which must have requested review (a passing earlier run never stands for
    a later one)."""
    runs = [r for r in _show(task).get("runs") or [] if isinstance(r, dict)]
    impl = [r for r in runs if str(r.get("profile") or "") == "implementer"]
    if not impl:
        raise ValueError("native task %s has no implementer run" % task)
    last = impl[-1]
    if str(last.get("outcome") or "") != "review_requested":
        raise ValueError("the latest implementer run %s of %s did not request review (outcome %s)"
                         % (last.get("id"), task, last.get("outcome")))
    meta = last.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except ValueError:
            meta = {}
    return dict(last, metadata=meta if isinstance(meta, dict) else {})


def compute(root: Path, phase: str, *, task: str = "", run: str = "", plan: str = "") -> dict[str, Any]:
    if phase == "m1":
        return m1_facts(root, task=task, run=run)
    return m2_facts(root, published_plan_path(root, task, plan), task=task, run=run)


def review_gaps(root: Path, phase: str, task: str) -> list[str]:
    """The reviewer audit's check: the current handoff of ``task`` against the
    facts recomputed now from the phase's sealed artifacts, bound to that run."""
    try:
        run = current_handoff(task)
        facts = compute(Path(root), phase, task=task, run=str(run.get("id") or ""))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        return ["HANDOFF_FACTS: %s" % exc]
    return ["HANDOFF_FACTS: %s run %s: %s" % (task, run.get("id"), g) for g in handoff_gaps(facts, run.get("metadata"))]


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--phase", choices=("m1", "m2"), required=True)
    ap.add_argument("--task", default=os.environ.get("HERMES_KANBAN_TASK", ""))
    ap.add_argument("--run", default=os.environ.get("HERMES_KANBAN_RUN_ID", ""), help="the implementer run handing off")
    ap.add_argument("--plan", default="", help="M2: an explicit published plan path")
    ap.add_argument("--write", action="store_true", help="write evidence/handoff/<phase>-facts.json")
    ap.add_argument("--check-task", default="", help="reviewer: compare that card's current handoff with the facts")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    if args.check_task:
        gaps = review_gaps(root, args.phase, args.check_task)
        if gaps:
            print("FAIL: " + "; ".join(gaps), file=sys.stderr)
            return 1
        print("OK: HANDOFF_FACTS %s agrees with the %s facts" % (args.check_task, args.phase), file=sys.stderr)
        return 0
    try:
        facts = compute(root, args.phase, task=args.task, run=args.run, plan=args.plan)
    except (OSError, ValueError, KeyError) as exc:
        print("FAIL: HANDOFF_FACTS %s" % exc, file=sys.stderr)
        return 1
    block = handoff_block(facts)
    if args.write:
        dst = root / out_path(args.phase)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(dict(facts, handoff=block), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(block, indent=2, sort_keys=True))
    print("Hand these keys off verbatim in the review request's metadata (facts, factual_summary%s); explain in "
          "summary, never contradict." % (", unresolved" if args.phase == "m2" else ""), file=sys.stderr)
    if args.phase == "m2":
        print("Completion map (read-only view; owner and exit per unresolved entry point): python3 "
              ".hermes/lib/completion_map.py --root %s --plan <the plan.r<N>.json counted above>" % root, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
