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
from _oracle_common import ensure_hermes_lib, header_diffs, http_observe, is_preflight, origin_of, required_headers  # noqa: E402
from _scenarios import (BINDING_CANDIDATE, CorpusError, DEFAULT_SECURITY_MODE, QUALIFICATION, SCENARIO_ORACLES,  # noqa: E402,F401
                        SCENARIO_PARITY, SECURITY_MODES, auth_headers, candidate_binding, corpus_digest,
                        effects_identity_of, load_corpus, normalize_security_mode, normalized_identity,
                        qualification_path, request_of, scenario, scenario_oracles_dir, scenario_parity_dir,
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
    except CorpusError as exc:
        print("REFUSE: SCENARIO_PARITY %s" % exc, file=sys.stderr)
        return 1
    oracles_dir = scenario_oracles_dir(security_mode)
    receipt, gaps = verify_receipt(root, require_admitted=True)
    candidate_mode = str(binding.get("mode") or "") == BINDING_CANDIDATE
    # A candidate-bound verdict still names a receipt: the one the issued card
    # was minted under, which candidate_binding proved is the receipt on disk.
    receipt_sha = str(binding.get("issued_receipt_sha256") or "") if candidate_mode else (receipt["receipt_digest"] if receipt else "")
    verdict = {"schema": "rhoai3.scenario-parity/v1", "scenario": args.scenario, "entry_point": "",
               "receipt_sha256": receipt_sha, "verdict": "INCONCLUSIVE",
               "binding": dict(binding) if binding else {"mode": BINDING_CANDIDATE, "gaps": list(binding_gaps)},
               "corpus_sha256": "", "security_mode": security_mode, "reason": "", "request": {}, "reset": {},
               "before": [], "before_state": "", "expected": {}, "observed": {}, "effects": []}
    out = root / scenario_parity_dir(security_mode) / (scenario_slug(args.scenario) + ".json")
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
        corpus = load_corpus(root, security_mode)
        sc = scenario(corpus, args.scenario)
        req = request_of(root, sc)
    except CorpusError as exc:
        verdict["reason"] = str(exc)
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, exc), file=sys.stderr)
        return 1
    verdict["entry_point"] = str(sc["entry_point"])
    verdict["corpus_sha256"] = corpus_digest(corpus)
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
    checks: list[str] = []
    # A positive scenario whose capture FAILED qualification is a SOURCE-SIDE
    # fixture failure (a 500 deleting a referenced pettype): the source did
    # not perform the operation, so there is nothing to compare, no parity
    # credit, and no destination repair card. Parity is not asked
    # (architect review of 708cfef9). Only a qualification bound to THIS
    # capture counts; a stale one judged another capture.
    qp = root / qualification_path(security_mode)
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
    if sc.get("reset_before", True) and not args.no_reset:
        cmd = shlex.split(args.reset_cmd) if args.reset_cmd else ["bash", str(Path(__file__).resolve().parent / "reset-parity-db.sh"), "--root", str(root)]
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
                       assert_headers=extra)
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
    diffs.extend(header_diffs(exp.get("headers"), got.get("headers"), source_origin=source_origin, dest_origin=dest_origin))
    # the resulting state: what the write actually did
    for eff in oracle.get("effects") or []:
        probe = http_observe(args.dest_url, str(eff.get("method") or "GET"), str(eff.get("path") or "/"), headers=eff_headers)
        row = {"id": eff.get("id"), "method": eff.get("method"), "path": eff.get("path"),
               "expected": {"status": eff.get("status"), "body_sha256": eff.get("body_sha256")},
               "observed": {"status": probe.get("status"), "body_sha256": probe.get("body_sha256"), "body_sample": probe.get("body_sample", "")}}
        row["match"] = bool(probe.get("status") == eff.get("status") and probe.get("body_sha256") == eff.get("body_sha256"))
        verdict["effects"].append(row)
        if not row["match"]:
            diffs.append("effect %s: status %s vs %s, body %s vs %s" % (row["id"], probe.get("status"), eff.get("status"),
                                                                        str(probe.get("body_sha256"))[:12], str(eff.get("body_sha256"))[:12]))
    declared = [str(e.get("id") or e.get("path")) for e in (sc.get("effects") or [])]
    recorded_effects = [str(e.get("id")) for e in (oracle.get("effects") or [])]
    if sorted(declared) != sorted(recorded_effects):
        verdict["reason"] = "the corpus declares effects %s but the source capture recorded %s" % (declared, recorded_effects)
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    if str(req["method"]) not in ("GET", "HEAD") and not is_preflight(req["method"], req["headers"]) and not recorded_effects:
        verdict["reason"] = "a %s scenario must declare at least one effect: an identical response does not prove the write happened" % req["method"]
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    verdict["verdict"] = "PASS" if not diffs else "FAIL"
    verdict["reason"] = "; ".join(diffs)
    write_canonical(out, verdict)
    if verdict["verdict"] == "PASS":
        print("OK: SCENARIO_PARITY %s PASS (%s %s, %d effect(s)) → %s" % (args.scenario, req["method"], req["path"], len(verdict["effects"]), out))
        return 0
    print("REFUSE: SCENARIO_PARITY %s %s (%s) → %s" % (args.scenario, verdict["verdict"], verdict["reason"], out), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
