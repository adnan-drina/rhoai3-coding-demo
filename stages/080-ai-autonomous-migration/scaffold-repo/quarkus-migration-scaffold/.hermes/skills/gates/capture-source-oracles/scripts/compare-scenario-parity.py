#!/usr/bin/env python3
"""Replay one recorded scenario against the destination and compare.

What "replay" has to mean, after the defect this script exists to fix: the
comparator resolves the scenario from the corpus, rebuilds the complete request
(method, concrete URL, headers, identity, body bytes or their explicit
absence), VERIFIES that request against the digest the source capture recorded,
and only then sends it. A comparator that sends the recorded path with no body
turns identical behaviour into FAIL.

For a write, response equality is not sufficient. Every effect the scenario
declares is read back and compared too, so a DELETE that answers 204 without
deleting anything fails its resulting-state check.

WHICH destination the verdict is about is recorded on it as ``binding``. By
default it is the accepted tree under the live seal (``mode: sealed``, the M4
road). With --issued it is the CANDIDATE that issued card was verified on
(``mode: candidate``): the acceptance path rebuilds the work list on the
candidate before this stage runs, so the live seal is stale by construction,
and what binds the verdict instead is the candidate digest this verification
recorded, the receipt the card was minted under, and the card.

Writes verification/parity/scenarios/<slug>.json. Exit 0 only on PASS; FAIL and
INCONCLUSIVE exit 1 and say which comparison failed.
"""
from __future__ import annotations

import argparse
import hashlib
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import (DESTINATION_BODIES, body_diff, ensure_hermes_lib, header_diffs, http_observe,  # noqa: E402
                            is_preflight, origin_of, required_headers, retain_body, retained_bytes)
from _scenarios import (BINDING_CANDIDATE, CorpusError, DEFAULT_SECURITY_MODE, EFFECT_ROLE_UNCHANGED, EFFECTS_REVERT_THEN_READ,  # noqa: E402
                        EFFECTS_SECOND_IDENTITY, SCENARIO_DIAGNOSTIC_PROBE,
                        QUALIFICATION, classification_conflict, effects_strategy_of, record_classification, SCENARIO_ORACLES,  # noqa: E402,F401
                        SCENARIO_PARITY, SECURITY_MODES, auth_headers, candidate_binding, corpus_digest,
                        effects_identity_of, load_corpus, normalize_security_mode, normalized_identity,
                        normalize_variant, qualification_path, request_of, scenario, scenario_oracles_dir, scenario_parity_dir,
                        scenario_slug, sealed_binding, source_exposed_headers)

ensure_hermes_lib()
from planner.admission import verify_receipt  # noqa: E402
from planner.canonical import digest, load_json, write_canonical  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE  # noqa: E402


def _identity_label(identity: dict) -> str:
    """How an identity is SAID in a refusal: by the variable holding its
    credential, never by what the variable holds."""
    ref = str((identity or {}).get("credential_ref") or "")
    if ref:
        return "credential_ref %s" % ref
    pair = [str((identity or {}).get(k) or "") for k in ("user_env", "password_env")]
    if all(pair):
        return "%s/%s" % tuple(pair)
    return "the request's own identity"


def _reset_argvs(reset_cmd: str, root: Path, variant: str) -> tuple[list[str], list[str], list[str]]:
    """(baseline, variant, revert) invocations of the reset script for a
    revert-then-read scenario. A caller's --reset-cmd names the script (and
    its root); a --variant/--revert-variant it carries is the caller's idea of
    which state, and the three states are this comparison's to choose."""
    argv = shlex.split(reset_cmd) if reset_cmd else ["bash", str(Path(__file__).resolve().parent / "reset-parity-db.sh"),
                                                     "--root", str(root)]
    base: list[str] = []
    skip = False
    for i, a in enumerate(argv):
        if skip:
            skip = False
            continue
        if a in ("--variant", "--revert-variant"):
            skip = True
            continue
        base.append(a)
    return base, base + ["--variant", variant], base + ["--revert-variant", variant]


def _run(argv: list[str]) -> dict:
    proc = subprocess.run(argv, text=True, capture_output=True)
    return {"ran": True, "rc": proc.returncode, "argv": argv, "output": (proc.stdout + proc.stderr).strip()[-400:]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--dest-url", required=True, help="the destination's base URL, including its root path")
    ap.add_argument("--reset-cmd", default="", help="the command that restores the declared initial state; defaults to the reset script beside this one. A scenario that declares reset_before is INCONCLUSIVE without it.")
    ap.add_argument("--no-reset", action="store_true", help="the caller restored the initial state itself; it must still match what the source started from, which is checked either way")
    ap.add_argument("--security-mode", choices=list(SECURITY_MODES), default=DEFAULT_SECURITY_MODE,
                    help="the security mode the DESTINATION is running in (ADR-014). It selects the captures to compare against, "
                         "and a capture taken in another mode is refused: a destination started with security enabled proves "
                         "nothing against anonymous expectations")
    ap.add_argument("--fixture-variant", default="", metavar="NAME",
                    help="compare against the captures of a declared fixture VARIANT of that mode's baseline (ADR-014). The "
                         "variant scopes the corpus, the captures, the qualification and this verdict; a capture taken "
                         "against another dataset state -- the baseline, or another variant -- is refused by name")
    ap.add_argument("--issued", default="", metavar="PATH",
                    help="verification/loop/issued.json: this verdict is of the CANDIDATE that issued card was verified on, "
                         "not of the accepted tree. The live seal is then not required to match the rebuilt work list (the "
                         "acceptance path rebuilds it on the candidate before the comparison runs); the verdict records the "
                         "candidate, the receipt the card was minted under and the card itself. Without it the verdict is "
                         "sealed-bound, exactly as on the M4 road.")
    ap.add_argument("--candidate", default="", metavar="SHA",
                    help="the candidate digest the caller believes this tree has; checked against verification/build/run.json "
                         "and against the tree itself, never trusted. Implies --issued.")
    ap.add_argument("--issued-receipt", default="", metavar="SHA",
                    help="the admission receipt the issued card was minted under; checked against the issued card. Implies --issued.")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    # the binding FIRST: what this verdict is about is not a detail of how it
    # is written down, it decides which seal it is measured against
    binding, binding_gaps = ({}, [])
    if args.issued or args.candidate or args.issued_receipt:
        binding, binding_gaps = candidate_binding(root, issued_path=args.issued, candidate_sha256=args.candidate,
                                                  issued_receipt_sha256=args.issued_receipt)
    else:
        binding = sealed_binding()
    try:
        security_mode = normalize_security_mode(args.security_mode)
        variant = normalize_variant(args.fixture_variant, security_mode)
    except CorpusError as exc:
        print("REFUSE: SCENARIO_PARITY %s" % exc, file=sys.stderr)
        return 1
    oracles_dir = scenario_oracles_dir(security_mode, variant)
    receipt, gaps = verify_receipt(root, require_admitted=True)
    candidate_mode = str(binding.get("mode") or "") == BINDING_CANDIDATE
    # A candidate-bound verdict still names a receipt: the one the issued card
    # was minted under (issued.json) -- never whatever admission-receipt.json says now (H10).
    receipt_sha = str(binding.get("issued_receipt_sha256") or "") if candidate_mode else (receipt["receipt_digest"] if receipt else "")
    verdict = {"schema": "rhoai3.scenario-parity/v1", "scenario": args.scenario, "entry_point": "",
               "receipt_sha256": receipt_sha, "verdict": "INCONCLUSIVE",
               "binding": dict(binding) if binding else {"mode": BINDING_CANDIDATE, "gaps": list(binding_gaps)},
               "corpus_sha256": "", "security_mode": security_mode, "security_variant": variant,
               "reason": "", "request": {}, "reset": {},
               "before": [], "before_state": "", "expected": {}, "observed": {}, "effects": [], "results": {}}
    out = root / scenario_parity_dir(security_mode, variant) / (scenario_slug(args.scenario) + ".json")
    if binding_gaps:
        verdict["reason"] = "the issued binding could not be made: " + "; ".join(binding_gaps)
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    # On the acceptance path the live seal is stale BY CONSTRUCTION: run-verify.sh
    # rebuilds the work list on the candidate before this stage runs, so its
    # digest can never be the accepted tree's sealed one. The binding above is
    # what this verdict is bound to instead; the seal is not asked.
    if not candidate_mode and (gaps or receipt is None):
        verdict["reason"] = "receipt not authoritative: " + "; ".join(gaps)
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    try:
        # the corpus of THIS mode (ADR-014): a replay of the enabled mode
        # resolves its scenario from the enabled corpus, never from the
        # anonymous one that happens to sit beside it
        corpus = load_corpus(root, security_mode, variant)
        sc = scenario(corpus, args.scenario)
        req = request_of(root, sc)
    except CorpusError as exc:
        verdict["reason"] = str(exc)
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, exc), file=sys.stderr)
        return 1
    verdict["entry_point"] = str(sc["entry_point"])
    verdict["corpus_sha256"] = corpus_digest(corpus)
    # the gating classification is part of what is compared (ADR-021): bound
    # before the replay, and fixed once any result for the scenario exists
    verdict["scenario_type"] = str(sc.get("scenario_type") or "")
    conflict = classification_conflict(root, sc, security_mode, variant)
    if conflict:
        verdict["reason"] = conflict
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, conflict), file=sys.stderr)
        return 1
    verdict["request"] = {k: req[k] for k in ("method", "path", "headers", "identity", "body_sha256", "body_absent", "request_sha256")}
    oracle_p = root / oracles_dir / (scenario_slug(args.scenario) + ".json")
    if not oracle_p.is_file():
        verdict["reason"] = "no source capture for this scenario; the expected values come only from the source"
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    oracle = load_json(oracle_p)
    # The mode BINDS the comparison (ADR-014). A capture that recorded no mode
    # is one taken before modes were bound, which is the default mode and only
    # that: comparing it against a destination running with security enabled
    # would grade an authenticated service on anonymous expectations.
    captured_mode = str(oracle.get("security_mode") or "") or DEFAULT_SECURITY_MODE
    if captured_mode != security_mode:
        verdict["captured_security_mode"] = captured_mode
        verdict["reason"] = ("the source capture was taken in the %s security mode and this comparison is of the %s mode; "
                             "capture the source in the %s mode rather than comparing across modes"
                             % (captured_mode, security_mode, security_mode))
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY mode mismatch: %s (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    verdict["captured_security_mode"] = captured_mode
    # ... and the same for the fixture VARIANT. A capture taken against the
    # declared dataset with a fixture's statements applied is evidence about
    # that database state and no other: comparing it against a destination
    # reset to the baseline (or to another variant) would judge one state's
    # answers by another state's, which is the cross-mode reuse ADR-014
    # forbids arriving through the dataset instead of the switch.
    captured_variant = str(oracle.get("security_variant") or "")
    if captured_variant != variant:
        verdict["captured_security_variant"] = captured_variant
        verdict["reason"] = ("the source capture was taken against the %s and this comparison is of the %s; capture the "
                             "source against the same state rather than mixing a variant with a baseline"
                             % ("%s fixture variant" % captured_variant if captured_variant else "mode's baseline",
                                "%s fixture variant" % variant if variant else "mode's baseline"))
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY variant mismatch: %s (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    verdict["captured_security_variant"] = captured_variant
    checks: list[str] = []
    captured_type = str(oracle.get("scenario_type") or "")
    if captured_type != verdict["scenario_type"] and (
            SCENARIO_DIAGNOSTIC_PROBE in (captured_type, verdict["scenario_type"]) or "scenario_type" in oracle):
        checks.append("the source capture was taken as %s and the corpus types the scenario %s; a classification is bound "
                      "at capture and never changed after it" % (captured_type or "a contract scenario",
                                                                 verdict["scenario_type"] or "a contract scenario"))
    # A positive scenario whose capture FAILED qualification is a SOURCE-SIDE
    # fixture failure (a 500 deleting a referenced pettype): the source did
    # not perform the operation, so there is nothing to compare, no parity
    # credit, and no destination repair card. Parity is not asked
    # (architect review of 708cfef9). Only a qualification bound to THIS
    # capture counts; a stale one judged another capture.
    qp = root / qualification_path(security_mode, variant)
    if qp.is_file():
        try:
            qdoc = load_json(qp)
        except (OSError, ValueError):
            qdoc = {}
        q = (qdoc.get("scenarios") or {}).get(args.scenario) if isinstance(qdoc, dict) else None
        if isinstance(q, dict) and str(qdoc.get("corpus_sha256") or "") == verdict["corpus_sha256"]:
            bound = str(q.get("capture_sha256") or "")
            on_disk = hashlib.sha256(oracle_p.read_bytes()).hexdigest()
            verdict["qualification"] = {"capability": q.get("capability"), "intent": q.get("intent"), "stale": bool(bound) and bound != on_disk}
            if (not bound or bound == on_disk) and str(q.get("capability")) == "FAIL" and str(q.get("intent") or "positive") == "positive":
                verdict["reason"] = "source fixture failed qualification: %s" % (q.get("reason") or "")
                write_canonical(out, verdict)
                print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
                return 1
    if oracle.get("status") != "CAPTURED":
        checks.append("the source capture is %s: %s" % (oracle.get("status"), oracle.get("reason")))
    # The capture is bound to the frozen source (the evidence bundle) and to
    # the corpus, not to the admission receipt: it is taken at M1, and a
    # destination repair must not oblige anyone to re-capture the source.
    bundle_sha = digest(load_json(root / EVIDENCE_BUNDLE))
    if not oracle.get("evidence_bundle_sha256"):
        checks.append("capture not bound to the frozen source (no evidence_bundle_sha256); re-capture it")
    elif str(oracle.get("evidence_bundle_sha256")) != bundle_sha:
        checks.append("the source capture describes bundle %s, this run's is %s" % (str(oracle.get("evidence_bundle_sha256"))[:12], bundle_sha[:12]))
    if oracle.get("corpus_sha256") != corpus_digest(corpus):
        checks.append("the source capture was taken against corpus %s, this is corpus %s; re-capture the source rather than comparing across corpora"
                      % (str(oracle.get("corpus_sha256"))[:12], corpus_digest(corpus)[:12]))
    recorded = oracle.get("request") or {}
    if recorded.get("request_sha256") != req["request_sha256"]:
        checks.append("the request this corpus describes (%s) is not the one the source answered (%s); the replay would not be a replay"
                      % (req["request_sha256"][:12], str(recorded.get("request_sha256"))[:12]))
    # WHOSE view the recorded read-backs are. A refused write's effects are
    # read back as an identity the policy accepts (the scenario's
    # ``effects_identity``), because the refused caller is answered 401 by the
    # read-backs too; comparing those rows against probes taken as anyone else
    # would compare two different observations.
    effects_identity = effects_identity_of(sc)
    want_effects_identity = normalized_identity(effects_identity) if effects_identity is not None else {}
    got_effects_identity = oracle.get("effects_identity") if isinstance(oracle.get("effects_identity"), dict) else {}
    if want_effects_identity != got_effects_identity:
        checks.append("this corpus takes the read-backs as %s and the source capture took them as %s; re-capture the source rather "
                      "than comparing read-backs of two identities"
                      % (_identity_label(want_effects_identity), _identity_label(got_effects_identity)))
    if not checks:
        record_classification(root, sc, verdict["corpus_sha256"], security_mode, variant)
    if checks:
        verdict["reason"] = "; ".join(checks)
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    headers, gap = auth_headers(req["identity"])
    if gap:
        verdict["reason"] = gap
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, gap), file=sys.stderr)
        return 1
    # the read-backs are taken as the identity the source's were taken as: the
    # same reference, resolved from THIS environment
    eff_headers, eff_gap = ((headers, "") if effects_identity is None else auth_headers(effects_identity))
    if eff_gap:
        verdict["reason"] = "the read-backs of this scenario are taken as another identity, and %s" % eff_gap
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    if effects_identity is not None:
        verdict["effects_identity"] = dict(want_effects_identity)

    # Restore the declared initial state, and then PROVE the destination is in
    # it. Without this a delete that deletes nothing passed against a
    # destination whose row was already gone: the response matched and so did
    # the effect, because both were "absent".
    # REVERT-THEN-READ: three states in one comparison -- the verified
    # baseline (where the before reads are taken), the variant (where the
    # request is refused) and the variant reverted (where the after reads are
    # taken) -- so the caller cannot have restored "the" state for it
    rtr = effects_strategy_of(sc) == EFFECTS_REVERT_THEN_READ
    rtr_argvs = _reset_argvs(args.reset_cmd, root, variant) if rtr else ([], [], [])
    if rtr:
        verdict["effects_strategy"] = EFFECTS_REVERT_THEN_READ
        if not variant or args.no_reset:
            verdict["reason"] = ("%s moves the destination through the baseline, the %s variant and its revert, and %s"
                                 % (EFFECTS_REVERT_THEN_READ, variant or "(no)",
                                    "--no-reset leaves it no reset to do that with" if args.no_reset else "this comparison is of no variant"))
            write_canonical(out, verdict)
            print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
            return 1
        verdict["reset"] = _run(rtr_argvs[0])
        verdict["reset"]["state"] = "baseline"
        if verdict["reset"]["rc"] != 0:
            verdict["reason"] = "the verified baseline could not be restored (%s exited %d): %s" % (
                rtr_argvs[0][0], verdict["reset"]["rc"], verdict["reset"]["output"][-200:])
            write_canonical(out, verdict)
            print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
            return 1
    elif sc.get("reset_before", True) and not args.no_reset:
        # the destination is restored to the state this comparison is OF: the
        # declared baseline, or -- for a fixture variant -- that baseline with
        # the variant's own statements applied after it
        cmd = (shlex.split(args.reset_cmd) if args.reset_cmd else
               ["bash", str(Path(__file__).resolve().parent / "reset-parity-db.sh"), "--root", str(root)]
               + (["--variant", variant] if variant else []))
        proc = subprocess.run(cmd, text=True, capture_output=True)
        verdict["reset"] = {"ran": True, "rc": proc.returncode, "argv": cmd, "output": (proc.stdout + proc.stderr).strip()[-400:]}
        if proc.returncode != 0:
            verdict["reason"] = "the declared initial state could not be restored (%s exited %d): %s" % (cmd[0], proc.returncode, verdict["reset"]["output"][-200:])
            write_canonical(out, verdict)
            print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
            return 1
    else:
        verdict["reset"] = {"ran": False, "rc": None, "declared": bool(sc.get("reset_before", True)), "reason": "--no-reset: the caller restored it" if args.no_reset else "the scenario does not declare reset_before"}

    before_expected = oracle.get("before") or []
    # The capture records the state the source started from by probing the
    # scenario's OWN effects, so a scenario that declares no effect can never
    # have one. Demanding it made every effect-less read INCONCLUSIVE for the
    # absence of a state nobody could have recorded (v9's first M4 receipt,
    # sc:cors-actual-*). The fix is here and not in the derivation: a data
    # read that declares reset_before is still RESET -- the reset above ran,
    # and a collection GET's recorded body is only deterministic against a
    # restored state -- and the comparison then proceeds on the first
    # response, with the absence stated rather than silent. A scenario WITH effects and
    # no before state is still INCONCLUSIVE: there the capture skipped probes
    # it was asked to take, and a delete that removes nothing would pass
    # against a destination whose row was already gone.
    if sc.get("reset_before", True) and not before_expected:
        if sc.get("effects"):
            verdict["reason"] = ("the source capture recorded no initial state for a scenario that declares reset_before "
                                 "and %d effect(s); re-capture the source so the state it started from is on record"
                                 % len(sc.get("effects") or []))
            write_canonical(out, verdict)
            print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
            return 1
        verdict["before_state"] = ("none declared: the scenario declares no effect, so the source recorded no initial state; "
                                   "the comparison is the response itself")
    for exp_before in before_expected:
        probe = http_observe(args.dest_url, str(exp_before.get("method") or "GET"), str(exp_before.get("path") or "/"), headers=eff_headers)
        row = {"id": exp_before.get("id"), "path": exp_before.get("path"),
               "expected": {"status": exp_before.get("status"), "body_sha256": exp_before.get("body_sha256")},
               "observed": {"status": probe.get("status"), "body_sha256": probe.get("body_sha256"), "body_sample": probe.get("body_sample", "")}}
        row["match"] = bool(probe.get("status") == exp_before.get("status") and probe.get("body_sha256") == exp_before.get("body_sha256"))
        verdict["before"].append(row)
    unmatched = [r for r in verdict["before"] if not r["match"]]
    if unmatched:
        verdict["reason"] = ("the destination is not in the state the source started from: %s"
                             % "; ".join("%s status %s vs %s" % (r["id"], r["observed"]["status"], r["expected"]["status"]) for r in unmatched)[:300])
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1

    if rtr:
        # the variant, set by the same script, on the baseline just verified
        step = _run(rtr_argvs[1])
        verdict["variant_reset"] = step
        if step["rc"] != 0:
            verdict["reason"] = "the %s variant could not be applied (%s exited %d): %s" % (
                variant, rtr_argvs[1][0], step["rc"], step["output"][-200:])
            write_canonical(out, verdict)
            print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
            return 1
    exp = oracle.get("response") or {}
    verdict["expected"] = {"status": exp.get("status"), "body_kind": exp.get("body_kind"), "body_sha256": exp.get("body_sha256"),
                           "headers": exp.get("headers")}
    # assert exactly what the capture asserted: the headers the source exposes
    # are recorded on the oracle, and fall back to the model for older ones.
    # The scenario's own asserted_headers are unioned in so the destination's
    # value is OBSERVED even when the capture predates them; whether they are
    # COMPARED is still the capture's word (header_diffs walks the expected
    # map), because a header nobody recorded on the source has no expectation.
    extra = list(oracle.get("asserted_headers_extra") or source_exposed_headers(root)[0])
    extra += [str(h) for h in (sc.get("asserted_headers") or []) if str(h) and str(h) not in extra]
    got = http_observe(args.dest_url, req["method"], req["path"], body=req["body"], headers={**req["headers"], **headers},
                       assert_headers=extra, keep_body=True)
    got_raw = got.pop("raw", b"")
    verdict["observed"] = {"status": got.get("status"), "body_kind": got.get("body_kind"), "body_sha256": got.get("body_sha256"),
                           "body_sample": got.get("body_sample", ""), "headers": got.get("headers")}
    if not got.get("status"):
        verdict["reason"] = "destination unreachable: %s" % got.get("error")
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    # A header this exchange REQUIRES (a Location on a 201 or a redirect, the
    # CORS permission headers on a cross-origin exchange) cannot be compared
    # against a capture that recorded no header map: that is INCONCLUSIVE,
    # never a quiet skip. Re-capture the source.
    needed = required_headers(req["method"], exp.get("status"), req["headers"])
    if needed and not isinstance(exp.get("headers"), dict):
        verdict["reason"] = ("the source capture recorded no header map and this exchange requires %s; re-capture the source "
                             "(redirects not followed) before comparing" % ", ".join(needed))
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    source_origin = origin_of(str((oracle.get("source") or {}).get("base_url") or ""))
    dest_origin = origin_of(args.dest_url)
    verdict["origins"] = {"source": source_origin, "destination": dest_origin}
    diffs: list[str] = []
    if got.get("status") != exp.get("status"):
        diffs.append("status %s vs %s" % (got.get("status"), exp.get("status")))
    if got.get("body_sha256") != exp.get("body_sha256"):
        diffs.append("body %s vs %s" % (str(got.get("body_sha256"))[:12], str(exp.get("body_sha256"))[:12]))
        # H1a: WHERE the bodies differ, from the retained source body and the
        # destination's own, retained beside the verdict the same way (capped,
        # digested, never inside this record)
        dest_dir = root / scenario_parity_dir(security_mode, variant) / DESTINATION_BODIES / scenario_slug(args.scenario)
        verdict["observed"]["evidence"] = retain_body(dest_dir, "response", got_raw, str(got.get("body_sha256") or ""))
        src_raw, src_why = retained_bytes(root, exp.get("evidence"),
                                          root / oracles_dir / "bodies" / scenario_slug(args.scenario) / "response.body")
        verdict["body_diff"] = (body_diff(None, None, unavailable="the source body: %s" % src_why) if src_raw is None else
                                body_diff(src_raw, got_raw, truncated_input=(
                                    src_why == "truncated" or bool(verdict["observed"]["evidence"].get("truncated")))))
        diffs[-1] += " (%s)" % verdict["body_diff"]["summary"]
    diffs.extend(header_diffs(exp.get("headers"), got.get("headers"), source_origin=source_origin, dest_origin=dest_origin))
    # the resulting state: what the write actually did -- or, for a refused
    # write (role unchanged_under_refusal), that it did nothing: the source's
    # before and after read-backs were equal, and the destination's after
    # read-backs must be those same bodies
    roles = {str(e.get("id") or e.get("path")): str(e.get("role") or "") for e in (sc.get("effects") or []) if isinstance(e, dict)}
    expected_after = oracle.get("effects") or []
    if rtr:
        # the variant's own changes are reverted -- by the same script, which
        # refuses when it does not find exactly the variant state it expects
        # -- and the reads are then judged against the BASELINE reads the
        # source recorded: a refused write left nothing behind, so after the
        # revert the state is the baseline's
        step = _run(rtr_argvs[2])
        verdict["revert"] = step
        if step["rc"] != 0:
            verdict["reason"] = ("the %s variant's revert refused (%s exited %d), so the state the refused request left is not "
                                 "readable: %s" % (variant, rtr_argvs[2][0], step["rc"], step["output"][-240:]))
            write_canonical(out, verdict)
            print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
            return 1
    if rtr or effects_strategy_of(sc) == EFFECTS_SECOND_IDENTITY:
        # ADR-020/021: what the SOURCE's post-request state was is known only
        # when the capture observed it (a same-engine store, its scoped state
        # read before and after the request). Otherwise -- for
        # revert-then-read -- the destination's reads can show only that the
        # DESTINATION changed nothing, judged against the source's baseline
        # reads as a separate result, and the source effect stays
        # INCONCLUSIVE.
        source_effects = oracle.get("source_effects") if isinstance(oracle.get("source_effects"), dict) else {}
        db = source_effects.get("db") if isinstance(source_effects.get("db"), dict) else {}
        comparison = db.get("comparison") if isinstance(db.get("comparison"), dict) else None
        if source_effects.get("observed") is True and oracle.get("effects") and comparison is not None:
            # ADR-021: the source effect is the DATABASE comparison over the
            # declared scope; the HTTP read-backs are what the destination is
            # compared against
            verdict["results"]["source_effect"] = {
                "verdict": "OBSERVED", "db_unchanged": bool(comparison.get("equal")),
                "changed_tables": sorted((comparison.get("differences") or {})),
                "scope": list((db.get("scope") or {}).get("tables") or []),
                "db_before_sha256": str((db.get("before") or {}).get("sha256") or ""),
                "db_after_sha256": str((db.get("after") or {}).get("sha256") or ""),
                "snapshot_sha256": str((source_effects.get("snapshot") or {}).get("sha256") or "")}
        else:
            if rtr:
                expected_after = before_expected
            verdict["results"]["source_effect"] = {
                "verdict": "INCONCLUSIVE",
                "reason": "the source's post-request database state was not observed and compared (%s); a declared "
                          "refusal, a captured 4xx or HTTP read-backs alone prove neither that the handler never ran nor "
                          "that it left the state unchanged"
                          % (source_effects.get("reason") or ("the capture records no database comparison"
                                                              if source_effects.get("observed") else
                                                              "the capture records no source observation"))}
    for eff in expected_after:
        probe = http_observe(args.dest_url, str(eff.get("method") or "GET"), str(eff.get("path") or "/"), headers=eff_headers)
        row = {"id": eff.get("id"), "method": eff.get("method"), "path": eff.get("path"),
               "expected": {"status": eff.get("status"), "body_sha256": eff.get("body_sha256")},
               "observed": {"status": probe.get("status"), "body_sha256": probe.get("body_sha256"), "body_sample": probe.get("body_sample", "")}}
        row["match"] = bool(probe.get("status") == eff.get("status") and probe.get("body_sha256") == eff.get("body_sha256"))
        role = roles.get(str(eff.get("id")), "")
        if role:
            row["role"] = role
        verdict["effects"].append(row)
        if not row["match"]:
            diffs.append("effect %s%s: status %s vs %s, body %s vs %s"
                         % (row["id"], " (the refused write changed the state it reads)" if role == EFFECT_ROLE_UNCHANGED else "",
                            probe.get("status"), eff.get("status"),
                            str(probe.get("body_sha256"))[:12], str(eff.get("body_sha256"))[:12]))
    if rtr:
        # the revert left the BASELINE; a variant comparison leaves the
        # variant, so no later scenario -- even one that declares no reset --
        # is judged on a state it is not about (v9: 14 reads answered 200)
        step = _run(rtr_argvs[1])
        verdict["restored_variant"] = step
        if step["rc"] != 0:
            verdict["reason"] = ("the %s variant could not be re-applied after the revert (%s exited %d), so the destination is "
                                 "left on the baseline: %s" % (variant, rtr_argvs[1][0], step["rc"], step["output"][-200:]))
            write_canonical(out, verdict)
            print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
            return 1
    declared = [str(e.get("id") or e.get("path")) for e in (sc.get("effects") or [])]
    recorded_effects = [str(e.get("id")) for e in expected_after]
    if sorted(declared) != sorted(recorded_effects):
        verdict["reason"] = "the corpus declares effects %s but the source capture recorded %s" % (declared, recorded_effects)
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    if str(req["method"]) not in ("GET", "HEAD") and not is_preflight(req["method"], req["headers"]) and not recorded_effects:
        verdict["reason"] = "a %s scenario must declare at least one effect: an identical response does not prove the write happened" % req["method"]
        # the derivation may have said WHY it could not declare one (a refused
        # write with no identity to read its state back as): the rule stands,
        # and the reason names what is missing
        if str(sc.get("effects_unobservable") or ""):
            verdict["reason"] += "; %s" % sc["effects_unobservable"]
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    # the results, SEPARATELY: the first response, what the destination's
    # reads show, and (for a refused variant write) what is known of the
    # source's own effect
    effect_diffs = [d for d in diffs if d.startswith("effect ")]
    verdict["results"]["response"] = "FAIL" if len(effect_diffs) != len(diffs) else "PASS"
    if verdict["effects"]:
        name = "destination_effect" if not rtr or verdict["results"].get("source_effect", {}).get("verdict") == "OBSERVED" \
            else "destination_no_effect"
        verdict["results"][name] = "FAIL" if effect_diffs else "PASS"
    source_open = verdict["results"].get("source_effect", {}).get("verdict") == "INCONCLUSIVE"
    if diffs:
        verdict["verdict"] = "FAIL"
        verdict["reason"] = "; ".join(diffs)
    elif source_open:
        verdict["verdict"] = "INCONCLUSIVE"
        verdict["reason"] = verdict["results"]["source_effect"]["reason"]
    else:
        verdict["verdict"] = "PASS"
        verdict["reason"] = ""
    write_canonical(out, verdict)
    if verdict["verdict"] == "INCONCLUSIVE":
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    write_canonical(out, verdict)
    if verdict["verdict"] == "PASS":
        print("OK: SCENARIO_PARITY %s PASS (%s %s, %d effect(s)) → %s" % (args.scenario, req["method"], req["path"], len(verdict["effects"]), out))
        return 0
    print("REFUSE: SCENARIO_PARITY %s %s (%s) → %s" % (args.scenario, verdict["verdict"], verdict["reason"], out), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
