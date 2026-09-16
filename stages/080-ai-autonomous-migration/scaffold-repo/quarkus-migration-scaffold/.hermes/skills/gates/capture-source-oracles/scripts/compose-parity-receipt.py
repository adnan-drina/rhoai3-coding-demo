#!/usr/bin/env python3
"""Compose verification/parity/receipt.json — receipt-bound parity summary.

Independent producer: reads every parity verdict for the current
admission receipt and every entry point in the evidence bundle. PASS only
when every entry point has a PASS verdict bound to this receipt. Exit 0 on
PASS; 1 otherwise (never completes around a FAIL or an INCONCLUSIVE).

The receipt records what it is OF, as ``binding``: the accepted tree under the
live seal (``mode: sealed``, the M4 road) or, with --issued, the candidate that
issued card was verified on (``mode: candidate``, the fix-until-green
acceptance path, where the work list has been rebuilt on the candidate and the
live seal cannot match it). In candidate mode a scenario verdict measured for
another card, another candidate or another receipt satisfies nothing, while a
sealed-bound verdict still counts: those are the ones the last full M4 run left
for every scenario a scoped run was not scoped to.

A comparison that PASSed is not the whole of ADR-016. The comparator compares
the FIRST response and never follows a redirect, so a 302 whose status and
literal Location are exactly the source's passes even when that address answers
404 -- the dead compatibility URL the ruling refuses. The bounded navigation
check run-parity.py performs beside the comparison records what the address
actually does (verification/parity/navigation/<slug>.json); this reads those
records, and an entry point whose comparison PASSed while its redirect target
is dead, loops or never settles becomes FAIL with kind ``navigation``. A PASS
navigation is recorded on the row as ``navigation: ok``.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from typing import Any
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import PARITY, slug  # noqa: E402
from _scenarios import (BINDING_CANDIDATE, CorpusError, DEFAULT_SECURITY_MODE, QUALIFICATION, QUALIFICATION_SCHEMA,  # noqa: E402,F401
                        SCENARIO_ORACLES, SCENARIO_PARITY, SECURITY_MODES, binding_mismatch, candidate_binding,
                        capture_security_mode, corpus_digest, cors_coverage, is_derived, load_corpus,
                        normalize_security_mode, parity_receipt_path, qualification_path, scenario_oracles_dir,
                        scenario_parity_dir, scenario_slug, sealed_binding, source_cors_policies)
from planner.admission import verify_receipt  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE  # noqa: E402

# Where run-parity.py leaves its bounded navigation records, and which terminal
# states are a redirect target that does not do its job.
NAVIGATION = PARITY / "navigation"
NAVIGATION_FAILED = ("dead", "loop", "too-many-hops")


def load_navigation(root: Path) -> dict[str, dict[str, Any]]:
    """Every bounded navigation record on disk, by scenario id.

    The records are a measurement of the destination, not of a receipt: they
    carry no binding of their own and none is asked of them. What binds them to
    this receipt is the scenario verdict they sit beside, which IS bound."""
    out: dict[str, dict[str, Any]] = {}
    ndir = Path(root) / NAVIGATION
    for p in sorted(ndir.glob("*.json")) if ndir.is_dir() else []:
        try:
            doc = load_json(p)
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict) and str(doc.get("scenario") or ""):
            out[str(doc["scenario"])] = doc
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--security-mode", choices=list(SECURITY_MODES), default=DEFAULT_SECURITY_MODE,
                    help="the security mode this receipt is of (ADR-014). It selects the captures, the qualification and the "
                         "scenario verdicts, and the receipt refuses to compose over evidence from another mode")
    ap.add_argument("--issued", default="", metavar="PATH",
                    help="verification/loop/issued.json: compose over the CANDIDATE that issued card was verified on. The live "
                         "seal is then not required to match the rebuilt work list, the receipt records the binding, and a "
                         "scenario verdict measured for another card, another candidate or another receipt satisfies nothing. "
                         "Without it the receipt is sealed-bound, exactly as on the M4 road.")
    ap.add_argument("--candidate", default="", metavar="SHA", help="the candidate digest the caller believes this tree has; checked, never trusted. Implies --issued.")
    ap.add_argument("--issued-receipt", default="", metavar="SHA", help="the receipt the issued card was minted under; checked against the issued card. Implies --issued.")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    binding, binding_gaps = ({}, [])
    if args.issued or args.candidate or args.issued_receipt:
        binding, binding_gaps = candidate_binding(root, issued_path=args.issued, candidate_sha256=args.candidate,
                                                  issued_receipt_sha256=args.issued_receipt)
    else:
        binding = sealed_binding()
    if binding_gaps:
        for g in binding_gaps:
            print("  - " + g, file=sys.stderr)
        print("REFUSE: PARITY_RECEIPT the issued binding could not be made", file=sys.stderr)
        return 1
    candidate_mode = str(binding.get("mode") or "") == BINDING_CANDIDATE
    try:
        security_mode = normalize_security_mode(args.security_mode)
    except CorpusError as exc:
        print("REFUSE: PARITY_RECEIPT %s" % exc, file=sys.stderr)
        return 1
    oracles_dir = scenario_oracles_dir(security_mode)
    # The mode the capture RECORDS decides; an M4 verdict then names the mode
    # it judged instead of leaving a reader to guess which switch the source
    # was standing behind.
    recorded_mode, mode_why = capture_security_mode(root, security_mode)
    if recorded_mode and recorded_mode != security_mode:
        print("REFUSE: PARITY_RECEIPT mode mismatch: %s holds captures taken in the %s mode, this receipt is of %s"
              % (oracles_dir.as_posix(), recorded_mode, security_mode), file=sys.stderr)
        return 1
    receipt, gaps = verify_receipt(root, require_admitted=True)
    # On the acceptance path the work list was rebuilt on the candidate before
    # this runs, so the live seal cannot match it. The binding says what this
    # receipt is of instead; the receipt it names is still the one the card was
    # minted under, which candidate_binding proved is the one on disk.
    if not candidate_mode and (gaps or receipt is None):
        for g in gaps:
            print("  - " + g, file=sys.stderr)
        print("REFUSE: PARITY_RECEIPT receipt not authoritative", file=sys.stderr)
        return 1
    receipt_sha = str(binding.get("issued_receipt_sha256") or "") if candidate_mode else str((receipt or {}).get("receipt_digest") or "")
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
        # the corpus of THIS mode: the enabled receipt is composed over the
        # enabled corpus, never over the anonymous one beside it
        corpus = load_corpus(root, security_mode)
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
    qp = root / qualification_path(security_mode)
    mode_mixes: list[str] = []
    if qp.is_file():
        qdoc = load_json(qp)
        qmode = str(qdoc.get("security_mode") or "") if isinstance(qdoc, dict) else ""
        if qmode and qmode != security_mode:
            mode_mixes.append("%s qualified the %s mode" % (qualification_path(security_mode).as_posix(), qmode))
        if qdoc.get("schema") != QUALIFICATION_SCHEMA:
            qualification_gap = "%s is not a %s document" % (qualification_path(security_mode), QUALIFICATION_SCHEMA)
        elif corpus_sha and str(qdoc.get("corpus_sha256") or "") != corpus_sha:
            qualification_gap = "captures were qualified against corpus %s, this is %s" % (str(qdoc.get("corpus_sha256"))[:12], corpus_sha[:12])
        else:
            qualification_loaded = True
            for sid, r in (qdoc.get("scenarios") or {}).items():
                if not isinstance(r, dict):
                    continue
                # a qualification is bound to the exact capture it judged;
                # a capture re-taken since is unjudged, not judged PASS
                cp = root / oracles_dir / (scenario_slug(str(sid)) + ".json")
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
    navigation = load_navigation(root)
    navigation_failures: list[dict[str, Any]] = []
    results: dict[str, list[dict[str, Any]]] = {}
    sdir = root / scenario_parity_dir(security_mode)
    for sp in sorted(sdir.glob("*.json")) if sdir.is_dir() else []:
        doc = load_json(sp)
        dmode = str(doc.get("security_mode") or "")
        if dmode and dmode != security_mode:
            mode_mixes.append("%s compared the %s mode" % (sp.name, dmode))
        results.setdefault(str(doc.get("scenario") or ""), []).append(doc)
    # A receipt that mixes modes is the cross-mode reuse ADR-014 forbids,
    # arriving one file at a time. Refuse before judging anything.
    if mode_mixes:
        for m in mode_mixes:
            print("  - " + m, file=sys.stderr)
        print("REFUSE: PARITY_RECEIPT mode mismatch: this receipt is of the %s mode and %d artifact(s) are of another"
              % (security_mode, len(mode_mixes)), file=sys.stderr)
        return 1
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
                # WHOSE measurement this verdict is. In candidate mode a
                # verdict bound to the SEAL still counts -- those are the ones
                # the last full M4 run left for every scenario a scoped run
                # was not scoped to -- but one measured for another card, another
                # candidate or another receipt satisfies nothing.
                bad_binding = binding_mismatch(doc, binding) if candidate_mode else ""
                if doc.get("receipt_sha256") != receipt_sha:
                    problems.append("%s is bound to receipt %s" % (sid, str(doc.get("receipt_sha256"))[:12]))
                elif bad_binding:
                    problems.append("%s is not this verification's measurement: %s" % (sid, bad_binding))
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
            # The comparison compared the FIRST response and never followed the
            # redirect: that is the design, and it leaves ADR-016's second exit
            # condition unmeasured. The bounded navigation measured it, beside
            # the comparison, and a legacy address that answers nothing is the
            # dead compatibility URL the ruling refuses -- so a PASS whose
            # redirect target is dead, loops or never settles is a FAIL, typed
            # ``navigation`` so the work list can locate it at the controller
            # that answers the redirect rather than at a response diff.
            nav_bad = [(sid, navigation[sid]) for sid in names
                       if str((navigation.get(sid) or {}).get("terminal") or "") in NAVIGATION_FAILED]
            nav_ok = [sid for sid in names if str((navigation.get(sid) or {}).get("terminal") or "") == "ok"]
            row = {"entry_point": ep, "verdict": verdict, "reason": reason, "scenarios": names,
                   "coverage": {"positive": positive, "negative": negative}}
            if verdict == "PASS" and nav_bad:
                row["verdict"] = "FAIL"
                row["kind"] = "navigation"
                row["reason"] = "; ".join(
                    "redirect target %s is %s on the destination (%s)"
                    % (str(n.get("start") or ""), str(n.get("terminal") or ""), n.get("final_status"))
                    for _, n in nav_bad)[:400]
                row["navigation_failures"] = [{"scenario": sid, "target": str(n.get("start") or ""),
                                               "terminal": str(n.get("terminal") or ""),
                                               "final_status": n.get("final_status")} for sid, n in nav_bad]
                navigation_failures.extend(row["navigation_failures"])
            elif nav_ok and not nav_bad:
                row["navigation"] = "ok"
            rows.append(row)
            failed += 0 if row["verdict"] == "PASS" else 1
            continue
        p = root / PARITY / (slug(ep) + ".json")
        if p.is_file():
            v = load_json(p)
            bound = v.get("receipt_sha256") == receipt_sha and not (binding_mismatch(v, binding) if candidate_mode else "")
            ok = v.get("verdict") == "PASS" and bound
            rows.append({"entry_point": ep, "verdict": v.get("verdict") if bound else "INCONCLUSIVE", "reason": v.get("reason", "") if bound else "verdict bound to another receipt", "scenarios": []})
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
    doc = {"schema": "rhoai3.parity-receipt/v1", "receipt_sha256": receipt_sha, "binding": dict(binding), "producer": "compose-parity-receipt.py",
           "corpus_sha256": corpus_sha, "corpus_error": corpus_error, "entry_points": rows, "total": len(rows), "not_passed": failed,
           "security_mode": security_mode, "security_mode_recorded": recorded_mode, "security_mode_note": "" if recorded_mode else mode_why,
           "cors": {"source_policies": source_policies, "gaps": cors_gaps},
           "qualification": {"present": qp.is_file(), "derived_corpus": bool(corpus) and is_derived(corpus), "gap": qualification_gap,
                             "not_passed": sorted(sid for sid, v in qualified.items() if v["capability"] != "PASS" or v["stale"]),
                             "stale": sorted(sid for sid, v in qualified.items() if v["stale"])},
           "coverage_gaps": coverage_gaps,
           "navigation": {"checked": len(navigation), "failures": navigation_failures},
           "verdict": verdict}
    out = root / parity_receipt_path(security_mode)
    write_canonical(out, doc)
    for g in coverage_gaps:
        print("  - coverage gap %s (%s): %s" % (g["scenario"], g["entry_point"], g["reason"]))
    for n in navigation_failures:
        print("  - navigation %s (%s): %s is %s (%s)" % (n["scenario"], n["terminal"], n["target"], n["terminal"],
                                                         n["final_status"]))
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
