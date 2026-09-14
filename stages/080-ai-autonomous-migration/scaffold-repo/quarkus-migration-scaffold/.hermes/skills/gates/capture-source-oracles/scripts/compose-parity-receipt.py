#!/usr/bin/env python3
"""Compose verification/parity/receipt.json — receipt-bound parity summary.

Independent producer: reads every parity verdict for the current
admission receipt and every entry point in the evidence bundle. PASS only
when every entry point has a PASS verdict bound to this receipt. Exit 0 on
PASS; 1 otherwise (never completes around a FAIL or an INCONCLUSIVE).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from typing import Any
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import PARITY, slug  # noqa: E402
from _scenarios import CorpusError, QUALIFICATION, QUALIFICATION_SCHEMA, SCENARIO_ORACLES, SCENARIO_PARITY, corpus_digest, cors_coverage, is_derived, load_corpus, scenario_slug, source_cors_policies  # noqa: E402
from planner.admission import verify_receipt  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    receipt, gaps = verify_receipt(root, require_admitted=True)
    if gaps or receipt is None:
        for g in gaps:
            print("  - " + g, file=sys.stderr)
        print("REFUSE: PARITY_RECEIPT receipt not authoritative", file=sys.stderr)
        return 1
    bundle = load_json(root / EVIDENCE_BUNDLE)
    wanted = sorted(str(e["id"]) for e in (bundle.get("entry_points") or []))
    # Which scenarios an entry point REQUIRES comes from the approved corpus,
    # never from which result files happen to exist: with two required
    # scenarios and one result on disk, enumerating results marked the entry
    # point PASS. Results are matched to the required set by id and bound to
    # the corpus digest; a missing one is INCONCLUSIVE, and a stale, duplicate
    # or foreign one satisfies nothing.
    corpus: dict[str, Any] = {}
    corpus_sha = ""
    corpus_error = ""
    try:
        corpus = load_corpus(root)
        corpus_sha = corpus_digest(corpus)
    except CorpusError as exc:
        corpus_error = str(exc)
    required: dict[str, list[str]] = {}
    for sc in (corpus.get("scenarios") or []):
        required.setdefault(str(sc.get("entry_point") or ""), []).append(str(sc.get("id")))
    # A capture is coverage only once it is QUALIFIED: CAPTURED records an
    # observation, and a create the source answered 500 for replays faithfully
    # while proving nothing about creating. A derived corpus (no person signed
    # it) needs the qualification gate's verdict per scenario; a hand-authored
    # one keeps the Operator's own review when no gate ran, and is held to the
    # gate's verdict when one did.
    qualified: dict[str, dict[str, Any]] = {}
    qualification_loaded = False  # an empty verdict map is still a loaded qualification (nothing in it PASSes)
    qualification_gap = ""
    qp = root / QUALIFICATION
    if qp.is_file():
        qdoc = load_json(qp)
        if qdoc.get("schema") != QUALIFICATION_SCHEMA:
            qualification_gap = "%s is not a %s document" % (QUALIFICATION, QUALIFICATION_SCHEMA)
        elif corpus_sha and str(qdoc.get("corpus_sha256") or "") != corpus_sha:
            qualification_gap = "captures were qualified against corpus %s, this is %s" % (str(qdoc.get("corpus_sha256"))[:12], corpus_sha[:12])
        else:
            qualification_loaded = True
            for sid, r in (qdoc.get("scenarios") or {}).items():
                if not isinstance(r, dict):
                    continue
                # a qualification is bound to the exact capture it judged;
                # a capture re-taken since is unjudged, not judged PASS
                cp = root / SCENARIO_ORACLES / (scenario_slug(str(sid)) + ".json")
                on_disk = hashlib.sha256(cp.read_bytes()).hexdigest() if cp.is_file() else ""
                bound = str(r.get("capture_sha256") or "")
                qualified[str(sid)] = {
                    "capability": str(r.get("capability") or r.get("verdict") or "INCONCLUSIVE"),
                    "intent": str(r.get("intent") or "positive"),
                    "reason": str(r.get("reason") or ""),
                    "stale": bool(bound) and bound != on_disk,
                }
    elif corpus and is_derived(corpus):
        qualification_gap = "captures not qualified (run qualify-source-captures.py)"
    coverage_gaps: list[dict[str, str]] = []
    results: dict[str, list[dict[str, Any]]] = {}
    sdir = root / SCENARIO_PARITY
    for sp in sorted(sdir.glob("*.json")) if sdir.is_dir() else []:
        doc = load_json(sp)
        results.setdefault(str(doc.get("scenario") or ""), []).append(doc)
    rows = []
    failed = 0
    for ep in wanted:
        names = sorted(required.get(ep) or [])
        if names:
            missing: list[str] = []
            problems: list[str] = [qualification_gap] if qualification_gap else []
            failures: list[str] = []
            positive: list[str] = []
            negative: list[str] = []
            for sid in names:
                if qualification_loaded:
                    q = qualified.get(sid)
                    if q is None:
                        problems.append("capture not qualified: %s has no qualification record" % sid)
                    elif q["stale"]:
                        problems.append("capture not qualified: %s requalify after recapture (the qualification judged another capture)" % sid)
                        coverage_gaps.append({"scenario": sid, "entry_point": ep, "kind": "stale-qualification", "intent": q["intent"],
                                              "reason": "requalify after recapture"})
                    elif q["capability"] == "FAIL":
                        # the source did not demonstrate the operation (or,
                        # for a negative scenario, the rejection): a
                        # SOURCE-SIDE fixture failure. It earns no parity
                        # credit and must not become a destination repair
                        # card, so the entry point is INCONCLUSIVE and the
                        # scenario is a coverage gap of kind fixture-failed
                        coverage_gaps.append({"scenario": sid, "entry_point": ep, "kind": "fixture-failed", "intent": q["intent"],
                                              "reason": "source fixture failed qualification: %s" % q["reason"]})
                        problems.append("source fixture failed qualification: %s %s" % (sid, q["reason"]))
                    elif q["capability"] != "PASS":
                        # a capability nobody could judge is a capability
                        # nobody demonstrated: the M4 coverage account reads
                        # coverage_gaps, so an INCONCLUSIVE that only became a
                        # problem line left the capability looking covered
                        coverage_gaps.append({"scenario": sid, "entry_point": ep, "kind": "inconclusive-qualification", "intent": q["intent"],
                                              "reason": "capture not qualified: %s" % q["reason"]})
                        problems.append("capture not qualified: %s INCONCLUSIVE: %s" % (sid, q["reason"]))
                    elif q["intent"] == "negative":
                        negative.append(sid)  # the source rejects as intended: negative coverage only
                    else:
                        positive.append(sid)
                found = results.get(sid) or []
                if not found:
                    missing.append(sid)
                    continue
                if len(found) > 1:
                    problems.append("%s has %d result files" % (sid, len(found)))
                    continue
                doc = found[0]
                if doc.get("receipt_sha256") != receipt["receipt_digest"]:
                    problems.append("%s is bound to receipt %s" % (sid, str(doc.get("receipt_sha256"))[:12]))
                elif corpus_sha and str(doc.get("corpus_sha256") or "") != corpus_sha:
                    problems.append("%s was compared against corpus %s, this is %s" % (sid, str(doc.get("corpus_sha256"))[:12], corpus_sha[:12]))
                elif doc.get("verdict") == "FAIL":
                    failures.append("%s: %s" % (sid, doc.get("reason")))
                elif doc.get("verdict") != "PASS":
                    problems.append("%s: %s" % (sid, doc.get("reason") or doc.get("verdict")))
            foreign = sorted(sid for sid in results if sid not in set(names) and any(str(d.get("entry_point") or "") == ep for d in results[sid]))
            if foreign:
                problems.append("result(s) for %s, which the corpus does not require of this entry point" % ", ".join(foreign[:3]))
            if failures:
                verdict, reason = "FAIL", "; ".join(failures)[:400]
            elif missing or problems:
                verdict = "INCONCLUSIVE"
                reason = "; ".join(([("%d required scenario(s) have no result: %s" % (len(missing), ", ".join(missing)))] if missing else []) + problems)[:400]
            else:
                verdict, reason = "PASS", "%d required scenario(s): %s" % (len(names), ", ".join(names))
            rows.append({"entry_point": ep, "verdict": verdict, "reason": reason, "scenarios": names,
                         "coverage": {"positive": positive, "negative": negative}})
            failed += 0 if verdict == "PASS" else 1
            continue
        p = root / PARITY / (slug(ep) + ".json")
        if p.is_file():
            v = load_json(p)
            ok = v.get("verdict") == "PASS" and v.get("receipt_sha256") == receipt["receipt_digest"]
            rows.append({"entry_point": ep, "verdict": v.get("verdict") if v.get("receipt_sha256") == receipt["receipt_digest"] else "INCONCLUSIVE", "reason": v.get("reason", "") if v.get("receipt_sha256") == receipt["receipt_digest"] else "verdict bound to another receipt", "scenarios": []})
        else:
            ok = False
            rows.append({"entry_point": ep, "verdict": "INCONCLUSIVE", "reason": "no parity record", "scenarios": []})
        failed += 0 if ok else 1
    # CORS is judged per policy, not per entry point: every policy the corpus
    # declares, and every one the frozen source declares, needs an actual
    # cross-origin exchange and a preflight. Missing coverage is INCONCLUSIVE.
    source_policies, policy_gap = source_cors_policies(root)
    cors_gaps = cors_coverage(corpus, source_policies) if corpus else []
    if policy_gap:
        cors_gaps.append(policy_gap)
    verdict = "PASS" if rows and failed == 0 else ("INCONCLUSIVE" if not rows or all(r["verdict"] == "INCONCLUSIVE" for r in rows if r["verdict"] != "PASS") else "FAIL")
    if verdict == "PASS" and cors_gaps:
        verdict = "INCONCLUSIVE"
    doc = {"schema": "rhoai3.parity-receipt/v1", "receipt_sha256": receipt["receipt_digest"], "producer": "compose-parity-receipt.py",
           "corpus_sha256": corpus_sha, "corpus_error": corpus_error, "entry_points": rows, "total": len(rows), "not_passed": failed,
           "cors": {"source_policies": source_policies, "gaps": cors_gaps},
           "qualification": {"present": qp.is_file(), "derived_corpus": bool(corpus) and is_derived(corpus), "gap": qualification_gap,
                             "not_passed": sorted(sid for sid, v in qualified.items() if v["capability"] != "PASS" or v["stale"]),
                             "stale": sorted(sid for sid, v in qualified.items() if v["stale"])},
           "coverage_gaps": coverage_gaps,
           "verdict": verdict}
    out = root / PARITY / "receipt.json"
    write_canonical(out, doc)
    for g in coverage_gaps:
        print("  - coverage gap %s (%s): %s" % (g["scenario"], g["entry_point"], g["reason"]))
    if doc["verdict"] == "PASS":
        print("OK: parity receipt PASS (%d entry points) → %s" % (len(rows), out))
        return 0
    for r in rows:
        if r["verdict"] != "PASS":
            print("  - %s %s: %s" % (r["entry_point"], r["verdict"], r["reason"]), file=sys.stderr)
    for g in cors_gaps:
        print("  - CORS INCONCLUSIVE: %s" % g, file=sys.stderr)
    print("REFUSE: parity receipt %s (%d of %d not passed) → %s" % (doc["verdict"], failed, len(rows), out), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
