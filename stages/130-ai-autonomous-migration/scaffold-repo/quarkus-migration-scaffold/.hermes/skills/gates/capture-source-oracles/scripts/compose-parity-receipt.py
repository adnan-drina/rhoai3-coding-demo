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

The receipt is composed over the records on DISK, which is what lets a scoped
run keep the verdicts the last full run left for every scenario the filter was
not scoped to -- and it is composed only over the records that BELONG to it: a
file whose name is the slug of a scenario the current corpus declares, holding
that scenario, compared against this corpus digest in this security mode and
this fixture variant. Every other file under the parity scenarios directory is
named in ``orphaned_records`` with the reason it does not belong, and counted
nowhere else. Measured on destination v9, that directory still held
cors-preflight-<digest>.json from an earlier naming scheme beside the current
sc_cors-preflight-<...>.json, and every such leftover became an INCONCLUSIVE
row ("no scenario '<id>' in the corpus") or a second result file for a
scenario that already had one: 33 of 34 rows INCONCLUSIVE after a scoped run
that compared one scenario and changed nothing else. A required scenario whose
only record on disk is an orphan is still INCONCLUSIVE -- with the orphan's
reason on the row, so the gap is named rather than reported as an absence.

A comparison that PASSed is not the whole of ADR-016. The comparator compares
the FIRST response and never follows a redirect, so a 302 whose status and
literal Location are exactly the source's passes even when that address answers
404 -- the dead compatibility URL the ruling refuses. The bounded navigation
check run-parity.py performs beside the comparison records what the address
actually does (verification/parity/navigation/<slug>.json); this reads those
records. First-response parity and target reachability are SEPARATE results
(ADR-020): an entry point whose comparison PASSed keeps its PASS, its row says
``navigation: failed`` with the failures, and the failure is its own row under
``navigation_obligations`` (``kind: navigation``, verdict FAIL) -- which fails
the receipt without re-typing the redirect as a response diff. A PASS
navigation is recorded on the row as ``navigation: ok``.

Every row also says HOW the entry point is covered (ARCHITECT RULING,
2026-09-22). ``coverage_kind`` is ``oracle`` when the older single-request
replay (method and path) is on disk, bound to this receipt and PASS;
``scenario`` when a QUALIFIED scenario explicitly binds this entry point and
its destination replay passed the required assertions in this mode -- the
absence of a read oracle is not itself disqualifying, and the scenario ids are
on the row under ``covered_by``; and ``none`` when neither. Absence of
comparable scenario evidence stays a gap: passing every scenario the corpus
declares cannot cover an entry point none of them binds, and a scenario that
did not run, or ran and failed, covers nothing. ``coverage_summary`` counts the
three, so a reader of the receipt cannot mistake a closed run with uncovered
entry points for a shipped one.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from typing import Any
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import PARITY, slug  # noqa: E402
from _scenarios import (BINDING_CANDIDATE, CorpusError, DEFAULT_SECURITY_MODE, EFFECT_ROLE_UNCHANGED, QUALIFICATION,  # noqa: E402
                        SCENARIO_BROWSER_PREFLIGHT, SCENARIO_CORS_ACTUAL, SCENARIO_DIAGNOSTIC_PROBE,
                        classification_conflict, is_diagnostic, QUALIFICATION_SCHEMA,  # noqa: E402,F401
                        SCENARIO_ORACLES, SCENARIO_PARITY, SECURITY_MODES, binding_mismatch, candidate_binding,
                        capture_security_mode, capture_security_variant, corpus_digest, cors_coverage,
                        declared_slugs, is_derived,
                        load_corpus,
                        normalize_security_mode, normalize_variant, parity_receipt_path, partition_parity_records,
                        qualification_path, scenario_oracles_dir,
                        scenario_parity_dir, scenario_slug, sealed_binding, source_cors_policies)
from planner.admission import verify_receipt  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE  # noqa: E402

# Where run-parity.py leaves its bounded navigation records, and which terminal
# states are a redirect target that does not do its job.
NAVIGATION = PARITY / "navigation"
NAVIGATION_FAILED = ("dead", "loop", "too-many-hops")


def _refused_writes(corpus: Any, results: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """What each refused write's verdict PROVES: the scenarios whose
    read-backs play the role ``unchanged_under_refusal`` (their verdict says
    whether the destination left the state the source left), and the ones
    whose derivation could not take read-backs at all, with the reason. Only
    a statement of what the rows are about -- the verdicts are counted above."""
    out: dict[str, dict[str, Any]] = {}
    for sc in ((corpus or {}).get("scenarios") or []) if isinstance(corpus, dict) else []:
        if not isinstance(sc, dict):
            continue
        sid = str(sc.get("id") or "")
        reads = [str(e.get("id") or "") for e in (sc.get("effects") or [])
                 if isinstance(e, dict) and str(e.get("role") or "") == EFFECT_ROLE_UNCHANGED]
        found = results.get(sid) or []
        seen = str(found[0].get("verdict") or "") if len(found) == 1 else ""
        separate = dict(found[0].get("results") or {}) if len(found) == 1 else {}
        if reads:
            # ADR-020: response parity, the destination's effect and the
            # source's effect are separate results; a destination-only
            # no-effect result is never promoted to source parity
            out[sid] = {"proves": "the refused write left the state unchanged", "reads": reads,
                        "strategy": str((sc.get("effects_reader") or {}).get("strategy") or ""),
                        "verdict": seen or "no single result", "results": separate,
                        "source_effect": str((separate.get("source_effect") or {}).get("verdict") or "not measured")}
        elif str(sc.get("effects_unobservable") or ""):
            out[sid] = {"proves": "nothing about the state", "unobservable": str(sc["effects_unobservable"]),
                        "verdict": seen or "no single result"}
    return out


def _diagnostics(corpus: Any, ids: set[str], results: dict[str, list[dict[str, Any]]],
                 qualified: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for sc in ((corpus or {}).get("scenarios") or []) if isinstance(corpus, dict) else []:
        sid = str((sc or {}).get("id") or "")
        if sid not in ids:
            continue
        found = results.get(sid) or []
        out[sid] = {"entry_point": str(sc.get("entry_point") or ""), "scenario_type": str(sc.get("scenario_type") or ""),
                    "cors_policy": str(sc.get("cors_policy") or ""),
                    "verdict": str(found[0].get("verdict") or "") if len(found) == 1 else
                    ("no result" if not found else "%d results" % len(found)),
                    "reason": str(found[0].get("reason") or "") if len(found) == 1 else "",
                    "qualification": str((qualified.get(sid) or {}).get("capability") or ""),
                    "gating": False, "obligations": 0, "browser_coverage": False}
    return out


def _cors_outcomes(corpus: Any, qualified: dict[str, dict[str, Any]],
                   results: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """Per CORS-bearing scenario: what it is, whether the SOURCE's answer lets
    a browser complete the exchange (``permits``) or prevents it
    (``prevents``; matching that is parity, not a demonstrated permission),
    its verdict, and whether it can discharge browser coverage at all (a
    diagnostic probe never does)."""
    out: dict[str, dict[str, Any]] = {}
    for sc in ((corpus or {}).get("scenarios") or []) if isinstance(corpus, dict) else []:
        if not isinstance(sc, dict) or not str(sc.get("cors_policy") or ""):
            continue
        sid = str(sc.get("id") or "")
        stype = str(sc.get("scenario_type") or "") or (
            SCENARIO_BROWSER_PREFLIGHT if str(sc.get("method") or "").upper() == "OPTIONS" else SCENARIO_CORS_ACTUAL)
        found = results.get(sid) or []
        out[sid] = {"policy": str(sc["cors_policy"]), "type": stype,
                    "browser_access": str((qualified.get(sid) or {}).get("browser_access") or ""),
                    "verdict": str(found[0].get("verdict") or "") if len(found) == 1 else "no single result",
                    "discharges_browser_coverage": stype != SCENARIO_DIAGNOSTIC_PROBE}
    return out


def oracle_covered(root: Path, ep: str, receipt_sha: str, binding: dict[str, Any], candidate_mode: bool) -> bool:
    """Is this entry point covered by its READ ORACLE -- the older
    single-request replay (method and path) compare-runtime-parity.py writes?

    Coverage, not merely a file: the record must be on disk, bound to THIS
    receipt (and, in candidate mode, to this verification), and PASS. A record
    bound to another receipt measured another tree, and a FAIL or INCONCLUSIVE
    one compared something without demonstrating equivalence."""
    p = Path(root) / PARITY / (slug(ep) + ".json")
    if not p.is_file():
        return False
    try:
        v = load_json(p)
    except (OSError, ValueError):
        return False
    if not isinstance(v, dict) or str(v.get("verdict") or "") != "PASS":
        return False
    if str(v.get("receipt_sha256") or "") != receipt_sha:
        return False
    return not (binding_mismatch(v, binding) if candidate_mode else "")


def coverage_of(oracle: bool, scenarios: list[str]) -> str:
    """ARCHITECT RULING 2026-09-22: scenario coverage COUNTS.

    An entry point whose comparable evidence is a qualified scenario that
    explicitly binds it, and whose destination replay passed the required
    assertions in this mode, is covered -- the absence of the older
    single-request oracle is not itself disqualifying. It is recorded as a
    DISTINCT kind, ``scenario``, with the scenario ids on the row, so nothing
    reads a scenario-covered entry point as if a read oracle had replayed it.
    An entry point with neither is ``none``: a gap, and passing every scenario
    the corpus happens to declare cannot fill it, because none of them binds
    this entry point."""
    if oracle:
        return "oracle"
    return "scenario" if scenarios else "none"


def coverage_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    """How many entry points are covered by oracle, by scenario, and not at
    all. The three are disjoint and sum to the entry points measured."""
    kinds = [str(r.get("coverage_kind") or "none") for r in rows]
    return {"entry_points": len(rows),
            "by_oracle": sum(1 for k in kinds if k == "oracle"),
            "by_scenario": sum(1 for k in kinds if k == "scenario"),
            "uncovered": sum(1 for k in kinds if k == "none")}


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
    ap.add_argument("--fixture-variant", default="", metavar="NAME",
                    help="compose the receipt of a declared fixture VARIANT of that mode's baseline (ADR-014): its own "
                         "corpus, captures, qualification, verdicts and receipt path, so a variant's receipt is never "
                         "read as the baseline's")
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
        variant = normalize_variant(args.fixture_variant, security_mode)
    except CorpusError as exc:
        print("REFUSE: PARITY_RECEIPT %s" % exc, file=sys.stderr)
        return 1
    oracles_dir = scenario_oracles_dir(security_mode, variant)
    # The mode the capture RECORDS decides; an M4 verdict then names the mode
    # it judged instead of leaving a reader to guess which switch the source
    # was standing behind.
    recorded_mode, mode_why = capture_security_mode(root, security_mode, variant)
    if recorded_mode and recorded_mode != security_mode:
        print("REFUSE: PARITY_RECEIPT mode mismatch: %s holds captures taken in the %s mode, this receipt is of %s"
              % (oracles_dir.as_posix(), recorded_mode, security_mode), file=sys.stderr)
        return 1
    # ... and the fixture VARIANT the captures were taken against, for the
    # same reason: a receipt must say which database state its verdicts are
    # about, and must not compose one state's evidence into another's
    recorded_variant, variant_why = capture_security_variant(root, security_mode, variant)
    if variant_why:
        print("REFUSE: PARITY_RECEIPT variant mismatch: %s" % variant_why, file=sys.stderr)
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
        corpus = load_corpus(root, security_mode, variant)
        corpus_sha = corpus_digest(corpus)
    except CorpusError as exc:
        corpus_error = str(exc)
    required: dict[str, list[str]] = {}
    # ADR-021: a diagnostic probe gates nothing -- it is not required of its
    # entry point, counts in no verdict and earns no coverage; its result is
    # kept apart under ``diagnostics``. Unless it was relabelled after a
    # result existed: then it is required, with the refusal as a problem.
    diagnostic_ids: set[str] = set()
    relabelled: dict[str, str] = {}
    for sc in (corpus.get("scenarios") or []):
        conflict = classification_conflict(root, sc, security_mode, variant) if isinstance(sc, dict) else ""
        if conflict:
            relabelled[str(sc.get("id"))] = conflict
        if is_diagnostic(sc) and not conflict:
            diagnostic_ids.add(str(sc.get("id")))
            continue
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
    qp = root / qualification_path(security_mode, variant)
    mode_mixes: list[str] = []
    if qp.is_file():
        qdoc = load_json(qp)
        qmode = str(qdoc.get("security_mode") or "") if isinstance(qdoc, dict) else ""
        if qmode and qmode != security_mode:
            mode_mixes.append("%s qualified the %s mode" % (qualification_path(security_mode, variant).as_posix(), qmode))
        if qdoc.get("schema") != QUALIFICATION_SCHEMA:
            qualification_gap = "%s is not a %s document" % (qualification_path(security_mode, variant), QUALIFICATION_SCHEMA)
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
                    "browser_access": str(r.get("browser_access") or ""),
                }
    elif corpus and is_derived(corpus):
        qualification_gap = "captures not qualified (run qualify-source-captures.py)"
    coverage_gaps: list[dict[str, str]] = []
    navigation = load_navigation(root)
    navigation_failures: list[dict[str, Any]] = []
    navigation_obligations: list[dict[str, Any]] = []
    # Only the records that BELONG to this receipt are composed over; every
    # other file in that directory is named as an orphan and counted nowhere
    # else. Without a corpus nothing can be judged to belong or not belong --
    # and nothing is read from there anyway, because the required set comes
    # from the corpus -- so nothing is called an orphan either.
    results: dict[str, list[dict[str, Any]]] = {}
    orphaned: list[dict[str, str]] = []
    if corpus:
        kept, orphaned = partition_parity_records(root, security_mode, variant,
                                                  declared=(corpus.get("scenarios") or []), corpus_sha=corpus_sha)
        for _sp, doc in kept:
            results.setdefault(str(doc.get("scenario") or ""), []).append(doc)
    # Which required scenario each orphan would have spoken for, so a scenario
    # whose only record on disk does not belong to this corpus is refused by
    # the orphan's own reason rather than reported as a plain absence.
    slugs = declared_slugs(corpus.get("scenarios") or [])
    orphan_why: dict[str, list[str]] = {}
    for o in orphaned:
        for sid in {str(o.get("scenario") or ""), slugs.get(Path(o["path"]).stem, "")}:
            if sid in slugs.values():
                orphan_why.setdefault(sid, []).append(o["reason"])
    # A QUALIFICATION of another mode is the cross-mode reuse ADR-014 forbids
    # arriving through the document that says which captures are coverage:
    # nothing here can be judged by it, so nothing is. (A parity RECORD of
    # another mode is a leftover of another run rather than a claim about this
    # one -- it is set aside as an orphan above, and the scenario it was the
    # only record of is INCONCLUSIVE with that reason.)
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
            body_diffs: list[dict[str, Any]] = []
            problems: list[str] = [qualification_gap] if qualification_gap else []
            failures: list[str] = []
            positive: list[str] = []
            negative: list[str] = []
            # the scenarios whose DESTINATION replay passed, bound to this
            # receipt, this corpus and this verification: the evidence the
            # coverage ruling counts (with the qualification below it)
            replayed: list[str] = []
            for sid in names:
                if sid in relabelled:
                    problems.append(relabelled[sid])
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
                    # An absence and a record that does not belong to this
                    # corpus are both "no verdict this receipt may read", and
                    # they are not the same gap: the second one is named by
                    # the reason the record was set aside.
                    why = orphan_why.get(sid)
                    if why:
                        problems.append("%s has no result that belongs to this corpus: %s" % (sid, "; ".join(why)[:200]))
                    else:
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
                    bd = doc.get("body_diff")
                    if isinstance(bd, dict):
                        # a pointer, not a copy: the verdict file holds the diff
                        body_diffs.append({"scenario": sid, "summary": str(bd.get("summary") or ""),
                                           "order_only": bool(bd.get("order_only")), "kind": str(bd.get("kind") or ""),
                                           "verdict_file": (scenario_parity_dir(security_mode, variant)
                                                            / (scenario_slug(sid) + ".json")).as_posix()})
                elif doc.get("verdict") != "PASS":
                    problems.append("%s: %s" % (sid, doc.get("reason") or doc.get("verdict")))
                else:
                    replayed.append(sid)
            foreign = sorted(sid for sid in results if sid not in set(names) and sid not in diagnostic_ids
                             and any(str(d.get("entry_point") or "") == ep for d in results[sid]))
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
            # H11 (v9 t_0527c69b): a walk that ends 2xx on a page that is not
            # the kind the SOURCE's final page is (the source capture recorded
            # its own redirect chain's final hop) is a failed navigation too --
            # "final hop 2xx" alone let a meta-refresh stub pass for the UI
            nav_bad = [(sid, navigation[sid]) for sid in names
                       if str((navigation.get(sid) or {}).get("terminal") or "") in NAVIGATION_FAILED
                       or (navigation.get(sid) or {}).get("final_differs")]
            nav_ok = [sid for sid in names if str((navigation.get(sid) or {}).get("terminal") or "") == "ok"
                      and not (navigation.get(sid) or {}).get("final_differs")]
            # A scenario counts as coverage only when it is QUALIFIED and its
            # destination replay PASSED. `positive`/`negative` are the ids the
            # qualification judged PASS (and not stale) in this mode; where no
            # qualification document is required at all -- a hand-authored
            # corpus with no gate run and no gap -- the Operator's own review
            # stands, and the scenarios are qualified by it. A scenario that
            # did not run, or ran and failed, is in neither list and covers
            # nothing.
            judged = (set(positive) | set(negative)) if qualification_loaded else (set(names) if not qualification_gap else set())
            covered_by_scenarios = sorted(set(replayed) & judged)
            oracle = oracle_covered(root, ep, receipt_sha, binding, candidate_mode)
            row = {"entry_point": ep, "verdict": verdict, "reason": reason, "scenarios": names,
                   "coverage": {"positive": positive, "negative": negative},
                   "coverage_kind": coverage_of(oracle, covered_by_scenarios),
                   "covered_by": {"oracle": oracle, "scenarios": covered_by_scenarios}}
            if body_diffs:
                row["body_diffs"] = body_diffs
            refusals = [relabelled[sid] for sid in names if sid in relabelled]
            if refusals:
                row["classification_refusals"] = refusals
            if verdict == "PASS" and nav_bad:
                # the redirect IS the source's (PASS stays); reachability of its
                # target is a separate obligation with its own row
                fails = [dict({"scenario": sid, "target": str(n.get("start") or ""),
                               "terminal": str(n.get("terminal") or ""),
                               "final_status": n.get("final_status")},
                              **({"final_differs": str(n.get("final_differs") or ""), "final": dict(n.get("final") or {}),
                                  "source_final": dict(n.get("source_final") or {})} if n.get("final_differs") else {}))
                         for sid, n in nav_bad]
                row["navigation"] = "failed"
                row["navigation_failures"] = fails
                navigation_obligations.append({
                    "entry_point": ep, "kind": "navigation", "verdict": "FAIL", "scenarios": list(names),
                    "reason": "; ".join(("redirect target %s reaches a final page that differs from the source's: %s"
                                         % (str(n.get("start") or ""), str(n.get("final_differs") or "")))
                                        if n.get("final_differs") and str(n.get("terminal") or "") not in NAVIGATION_FAILED else
                                        ("redirect target %s is %s on the destination (%s)"
                                         % (str(n.get("start") or ""), str(n.get("terminal") or ""), n.get("final_status")))
                                        for _, n in nav_bad)[:400],
                    "navigation_failures": list(fails)})
                navigation_failures.extend(fails)
            elif nav_ok and not nav_bad:
                row["navigation"] = "ok"
            rows.append(row)
            failed += 0 if row["verdict"] == "PASS" else 1
            continue
        # No corpus scenario binds this entry point, so the only evidence that
        # could cover it is its read oracle. Nothing here is scenario coverage
        # (the ruling counts a scenario that EXPLICITLY binds the entry point,
        # and none does), so the kind is oracle or none.
        p = root / PARITY / (slug(ep) + ".json")
        if p.is_file():
            v = load_json(p)
            bound = v.get("receipt_sha256") == receipt_sha and not (binding_mismatch(v, binding) if candidate_mode else "")
            ok = v.get("verdict") == "PASS" and bound
            row = {"entry_point": ep, "verdict": v.get("verdict") if bound else "INCONCLUSIVE", "reason": v.get("reason", "") if bound else "verdict bound to another receipt", "scenarios": [],
                   "coverage_kind": coverage_of(bool(ok), []), "covered_by": {"oracle": bool(ok), "scenarios": []}}
            if bound and isinstance(v.get("body_diff"), dict):
                row["body_diffs"] = [{"scenario": "", "summary": str(v["body_diff"].get("summary") or ""),
                                      "order_only": bool(v["body_diff"].get("order_only")),
                                      "kind": str(v["body_diff"].get("kind") or ""),
                                      "verdict_file": (PARITY / (slug(ep) + ".json")).as_posix()}]
            rows.append(row)
        else:
            ok = False
            rows.append({"entry_point": ep, "verdict": "INCONCLUSIVE", "scenarios": [],
                         "reason": "no parity record: no read-oracle replay on disk, and no scenario in this corpus binds this entry point",
                         "coverage_kind": "none", "covered_by": {"oracle": False, "scenarios": []}})
        failed += 0 if ok else 1
    # CORS is judged per policy, not per entry point: every policy the corpus
    # declares, and every one the frozen source declares, needs an actual
    # cross-origin exchange and a preflight. Missing coverage is INCONCLUSIVE.
    source_policies, policy_gap = source_cors_policies(root)
    cors_gaps = cors_coverage(corpus, source_policies) if corpus else []
    if policy_gap:
        cors_gaps.append(policy_gap)
    cors_outcomes = _cors_outcomes(corpus, qualified, results)
    if security_mode != DEFAULT_SECURITY_MODE and corpus:
        # with security enabled, a policy is covered only once the SOURCE's
        # answer to its browser preflight has been captured and read: until
        # then the enabled-mode CORS claim is not made (a diagnostic probe
        # never stands in for it)
        for pid in sorted({str(p.get("id")) for p in (corpus.get("cors_policies") or []) if isinstance(p, dict)}):
            seen = [o for o in cors_outcomes.values() if o["policy"] == pid and o["type"] == SCENARIO_BROWSER_PREFLIGHT
                    and o["browser_access"]]
            if not seen:
                cors_gaps.append("cors policy %s: no captured, qualified browser preflight with security enabled" % pid)
    verdict = "PASS" if rows and failed == 0 else ("INCONCLUSIVE" if not rows or all(r["verdict"] == "INCONCLUSIVE" for r in rows if r["verdict"] != "PASS") else "FAIL")
    if verdict == "PASS" and cors_gaps:
        verdict = "INCONCLUSIVE"
    if navigation_obligations and verdict != "FAIL":
        # a dead, looping or unsettled redirect target is a failed obligation
        # of the receipt, even where every first response is the source's
        verdict = "FAIL"
    doc = {"schema": "rhoai3.parity-receipt/v1", "receipt_sha256": receipt_sha, "binding": dict(binding), "producer": "compose-parity-receipt.py",
           "corpus_sha256": corpus_sha, "corpus_error": corpus_error, "entry_points": rows, "total": len(rows), "not_passed": failed,
           # how each entry point IS covered, counted three ways: by its read
           # oracle, by a qualified scenario whose destination replay passed,
           # or not at all. A closed run with an uncovered entry point is not
           # a shipped run, so the count is on the receipt and not inferred.
           "coverage_summary": coverage_summary(rows),
           "security_mode": security_mode, "security_mode_recorded": recorded_mode, "security_mode_note": "" if recorded_mode else mode_why,
           "security_variant": variant, "security_variant_recorded": recorded_variant, "security_variant_note": variant_why,
           "cors": {"source_policies": source_policies, "gaps": cors_gaps, "outcomes": cors_outcomes},
           "qualification": {"present": qp.is_file(), "derived_corpus": bool(corpus) and is_derived(corpus), "gap": qualification_gap,
                             "not_passed": sorted(sid for sid, v in qualified.items() if v["capability"] != "PASS" or v["stale"]),
                             "stale": sorted(sid for sid, v in qualified.items() if v["stale"])},
           "coverage_gaps": coverage_gaps,
           # the files in this mode's parity scenarios directory that are NOT
           # this receipt's evidence, each with the reason -- named here, and
           # counted in no row, no total and no verdict
           "orphaned_records": orphaned,
           "navigation": {"checked": len(navigation), "failures": navigation_failures},
           "navigation_obligations": navigation_obligations,
           "refused_writes": _refused_writes(corpus, results),
           # results that gate nothing: visible, never required, never coverage
           "diagnostics": _diagnostics(corpus, diagnostic_ids, results, qualified),
           "verdict": verdict}
    out = root / parity_receipt_path(security_mode, variant)
    write_canonical(out, doc)
    cs = doc["coverage_summary"]
    print("  - coverage: %d entry point(s): %d by read oracle, %d by qualified scenario, %d not compared at all"
          % (cs["entry_points"], cs["by_oracle"], cs["by_scenario"], cs["uncovered"]))
    for g in coverage_gaps:
        print("  - coverage gap %s (%s): %s" % (g["scenario"], g["entry_point"], g["reason"]))
    for o in orphaned:
        print("  - orphaned record %s (%s): %s" % (o["path"], o["kind"], o["reason"]))
    for n in navigation_failures:
        print("  - navigation %s (%s): %s is %s (%s)" % (n["scenario"], n["terminal"], n["target"], n["terminal"],
                                                         n["final_status"]))
    if doc["verdict"] == "PASS":
        print("OK: parity receipt PASS (%d entry points) → %s" % (len(rows), out))
        return 0
    for r in rows + navigation_obligations:
        if r["verdict"] != "PASS":
            print("  - %s %s: %s" % (r["entry_point"], r["verdict"], r["reason"]), file=sys.stderr)
    for g in cors_gaps:
        print("  - CORS INCONCLUSIVE: %s" % g, file=sys.stderr)
    print("REFUSE: parity receipt %s (%d of %d not passed) → %s" % (doc["verdict"], failed, len(rows), out), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
