#!/usr/bin/env python3
"""The M1/M2 handoff facts, computed from sealed artifacts, and the check of a
card's handoff prose against them.

v23 (2026-09-28) handed off three wrong claims that no artifact made:

- M1 and M2 said 20 of 34 entry points needed operator observations as
  scheduled/messaging/lifecycle work. The inventory says HTTP 34, non-HTTP 0:
  the 20 inconclusive READ oracles are 19 non-idempotent writes routed to the
  scenario corpus and one wildcard path that is not a request.
- M2 said "29 repair outcomes/objectives"; the published plan has 30 repair
  outcomes plus 4 milestones (M4 and three M5) = 34 cards.
- M2 recorded ``unresolved: []``; the admitted plan keeps 7 ship-blocking
  verification responsibilities spanning 12 HTTP entry points.

Counts and classifications are therefore code, written to
``evidence/handoff/<phase>-facts.json``; the worker's prose may explain them
but must not contradict them. Read-oracle coverage, scenario coverage and
unresolved behavior coverage are kept as three separate numbers.

    handoff_facts.py --root . --phase m1 --write
    handoff_facts.py --root . --phase m2 --task "$HERMES_KANBAN_TASK" --write
    handoff_facts.py --root . --phase m2 --check-task t_…   # reviewer
"""
from __future__ import annotations

import glob
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

SCHEMA = "rhoai3.handoff-facts/v1"
INVENTORY = "evidence/entry-point-inventory.json"
READ_ORACLES = "verification/source-oracles"
MODES = {"disabled": "scenarios", "enabled": "scenarios-enabled"}
ADMISSION = "evidence/planning/admission-receipt.json"
PLAN_SEMANTICS = "evidence/planning/plan-semantics.json"  # frozen by the first ADMITTED receipt
READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
PLAN_NAME = re.compile(r"^plan\.r(\d+)\.json$")


def out_path(phase: str) -> str:
    return "evidence/handoff/%s-facts.json" % phase


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- M1

def read_inconclusive_class(ep: dict[str, Any] | None) -> str:
    """Why a read oracle is not captured, from the inventory, never from prose."""
    if ep is None:
        return "not-in-inventory"
    if str(ep.get("kind") or "") != "http":
        return "non-http-observation"  # the only class that needs an operator observation
    if str(ep.get("http_method") or "").upper() not in READ_METHODS:
        return "write-in-scenario-corpus"
    path = str(ep.get("http_path") or "")
    if "*" in path or not path.startswith("/"):
        return "unrequestable-path"
    return "http-read-not-captured"


def m1_facts(root: Path) -> dict[str, Any]:
    inv = _load(root / INVENTORY)
    eps = [e for e in inv.get("entry_points") or [] if isinstance(e, dict)]
    by_id = {str(e.get("entry_point_id") or ""): e for e in eps}
    kinds = Counter(str(e.get("kind") or "?") for e in eps)
    captured, inconclusive = 0, Counter()
    methods: Counter = Counter()
    records = sorted(glob.glob(str(root / READ_ORACLES / "ep_*.json")))
    for p in records:
        rec = _load(Path(p))
        if str(rec.get("status") or "") == "CAPTURED":
            captured += 1
            continue
        ep = by_id.get(str(rec.get("entry_point") or ""))
        cls = read_inconclusive_class(ep)
        inconclusive[cls] += 1
        if cls == "write-in-scenario-corpus":
            methods[str(ep.get("http_method")).upper()] += 1
    scenarios: dict[str, Any] = {}
    for mode, sub in MODES.items():
        cap_p = root / READ_ORACLES / sub / "_capture.json"
        qual_p = root / READ_ORACLES / sub / "_qualification.json"
        cap = _load(cap_p) if cap_p.is_file() else {}
        qual = _load(qual_p) if qual_p.is_file() else {}
        sc = qual.get("scenarios") or {}
        rows = sc.values() if isinstance(sc, dict) else sc
        verdicts = Counter(str((r or {}).get("capability") or "?") for r in rows if isinstance(r, dict))
        scenarios[mode] = {"status": cap.get("status") or "absent", "requested": int(cap.get("requested") or 0),
                           "captured": int(cap.get("captured") or 0),
                           "qualification": {k: verdicts.get(k, 0) for k in ("PASS", "FAIL", "INCONCLUSIVE")},
                           "reason": str(cap.get("reason") or "")}
    non_http = sum(v for k, v in kinds.items() if k != "http")
    return {
        "schema": SCHEMA, "phase": "m1",
        "entry_points": {"total": len(eps), "http": kinds.get("http", 0), "non_http": non_http, "by_kind": dict(sorted(kinds.items()))},
        "read_oracles": {"records": len(records), "captured": captured, "inconclusive": sum(inconclusive.values()),
                         "inconclusive_by_class": dict(sorted(inconclusive.items())),
                         "writes_by_method": dict(sorted(methods.items()))},
        "scenarios": scenarios,
        "operator_observations_needed": inconclusive.get("non-http-observation", 0),
        "note": "read-oracle coverage (idempotent reads), scenario coverage (the replayed corpus) and unresolved behavior "
                "coverage (M2's verification responsibilities) are different counts; a write is covered by the scenario "
                "corpus, never by a read oracle",
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
                     % (task or "no --task", PLAN_SEMANTICS))


def m2_facts(root: Path, plan_path: Path) -> dict[str, Any]:
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
    ep_kinds = Counter(e.rsplit(":", 1)[-1] if ":" in e else "?" for e in eps)
    adm = _load(root / ADMISSION) if (root / ADMISSION).is_file() else {}
    # the receipt is mutable (every accepted step re-admits): only the receipt
    # the plan was published under describes the plan's input
    published = str((plan.get("provenance") or {}).get("receipt_sha256") or "")
    same = (str(adm.get("receipt_digest") or "") == published) if published else True  # semantics: frozen by this receipt's first ADMITTED
    return {
        "schema": SCHEMA, "phase": "m2",
        "plan": {"path": str(plan_path), "revision": doc.get("revision", plan.get("revision")), "policy": plan.get("policy")},
        "admission": {"published_under_receipt": published,
                      "current_receipt_is_published": same,
                      "status": (adm.get("status") or adm.get("verdict") or "absent") if same else "admitted at publication; receipt has since moved",
                      "blocks": len(adm.get("blocks") or []) if same else None,
                      "measure": adm.get("measure") if same else None},
        "cards": {"total": len(nodes), "repair": len(repairs), "milestones": len(milestones),
                  "repair_by_class": dict(sorted(Counter(str(n.get("class")) for n in repairs).items())),
                  "milestones_by_role": dict(sorted(Counter(str(n.get("role")) for n in milestones).items()))},
        "requirements": dict(sorted(reqs.items())),
        "unresolved": {"groups": len(unresolved), "requirements": len({r for u in unresolved for r in u.get("requirements") or []}),
                       "entry_points": len(eps), "entry_point_kinds": dict(sorted(ep_kinds.items())),
                       "blocks": dict(sorted(Counter(str(u.get("blocks")) for u in unresolved).items())),
                       "ids": [str(u.get("id")) for u in unresolved]},
        # M2 carries M1's limitations forward: it carries M1's classification with them
        "carried_m1": m1_facts(root) if (root / INVENTORY).is_file() else None,
        "note": "admission blocks refuse the plan; unresolved rows are admitted release qualifications that stay open "
                "until evidence closes them (blocks: ship). Neither is cleared by prose or completion metadata.",
    }


# ---------------------------------------------------------------- the check

_NON_HTTP = re.compile(r"non[- ]?http|scheduled|messaging|lifecycle|operator[- ](?:captured )?observation", re.I)
_REPAIR_COUNT = re.compile(r"\b(\d+)\s+(?:repair\s+)?(?:outcomes?(?:/objectives)?|repairs?|repair cards?)\b", re.I)
# "no unresolved BLOCK classes" speaks of admission blocks, a different thing, and is not flagged
_NO_UNRESOLVED = re.compile(r"\bno unresolved\b(?!\s+block)|\bunresolved:\s*(?:\[\]|none|0)\b", re.I)


def claim_gaps(facts: dict[str, Any], summary: str, metadata: dict[str, Any] | None) -> list[str]:
    """Contradictions between a handoff's prose/metadata and the computed facts."""
    meta = metadata or {}
    text = summary + "\n" + json.dumps(meta, sort_keys=True)
    gaps: list[str] = []
    m1 = facts if facts.get("phase") == "m1" else facts.get("carried_m1")
    if m1:
        ep = m1.get("entry_points") or {}
        if int(ep.get("non_http", 0)) == 0 and m1.get("operator_observations_needed", 0) == 0:
            hit = _NON_HTTP.search(text)
            if hit:
                gaps.append("claims non-HTTP/operator-observation work (%r) but the inventory has %d HTTP and 0 non-HTTP "
                            "entry points; the %d inconclusive reads are %s" % (
                                hit.group(0), int(ep.get("http", 0)), int((m1.get("read_oracles") or {}).get("inconclusive", 0)),
                                json.dumps((m1.get("read_oracles") or {}).get("inconclusive_by_class"))))
    if facts.get("phase") == "m2":
        cards = facts["cards"]
        for m in _REPAIR_COUNT.finditer(text):
            n = int(m.group(1))
            if n != cards["repair"]:
                gaps.append("claims %r but the published plan has %d repair outcomes plus %d milestones (%d cards)"
                            % (m.group(0), cards["repair"], cards["milestones"], cards["total"]))
        un = facts["unresolved"]
        if un["groups"]:
            if "unresolved" in meta and not meta.get("unresolved"):
                gaps.append("metadata.unresolved is empty but the plan keeps %d unresolved group(s) spanning %d entry point(s)"
                            % (un["groups"], un["entry_points"]))
            hit = _NO_UNRESOLVED.search(summary)
            if hit:
                gaps.append("summary says %r but the plan keeps %d unresolved group(s) (blocks: %s)"
                            % (hit.group(0), un["groups"], json.dumps(un["blocks"])))
    return gaps


def latest_handoff(task: str) -> tuple[str, dict[str, Any]]:
    """The newest implementer handoff (review_requested run) of a native card."""
    proc = subprocess.run([hermes_bin(), "kanban", "show", task, "--json"], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise ValueError("cannot read native task %s: %s" % (task, (proc.stderr or "").strip()[:200]))
    runs = [r for r in json.loads(proc.stdout).get("runs") or [] if isinstance(r, dict)]
    handoffs = [r for r in runs if str(r.get("outcome") or "") == "review_requested"]
    if not handoffs:
        raise ValueError("native task %s has no review_requested handoff" % task)
    last = handoffs[-1]
    return str(last.get("summary") or ""), dict(last.get("metadata") or {})


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--phase", choices=("m1", "m2"), required=True)
    ap.add_argument("--task", default=os.environ.get("HERMES_KANBAN_TASK", ""), help="M2: the card holding plan.r<N>.json")
    ap.add_argument("--plan", default="", help="M2: an explicit published plan path")
    ap.add_argument("--write", action="store_true", help="write evidence/handoff/<phase>-facts.json")
    ap.add_argument("--check-task", default="", help="check that card's latest handoff against the facts")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.phase == "m1":
            facts = m1_facts(root)
        else:
            facts = m2_facts(root, published_plan_path(root, args.check_task or args.task, args.plan))
    except (OSError, ValueError, KeyError) as exc:
        print("FAIL: HANDOFF_FACTS %s" % exc, file=sys.stderr)
        return 1
    if args.write:
        dst = root / out_path(args.phase)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(facts, indent=2, sort_keys=True))
    if args.check_task:
        try:
            summary, meta = latest_handoff(args.check_task)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            print("FAIL: HANDOFF_FACTS %s" % exc, file=sys.stderr)
            return 1
        gaps = claim_gaps(facts, summary, meta)
        if gaps:
            print("FAIL: HANDOFF_CLAIMS %s handoff contradicts the sealed artifacts: %s" % (args.check_task, "; ".join(gaps)),
                  file=sys.stderr)
            return 1
        print("OK: HANDOFF_CLAIMS %s agrees with the %s facts" % (args.check_task, args.phase), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
