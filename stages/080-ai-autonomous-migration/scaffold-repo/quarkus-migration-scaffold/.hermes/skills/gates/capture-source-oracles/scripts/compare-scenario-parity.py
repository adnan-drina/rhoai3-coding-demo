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

Writes verification/parity/scenarios/<slug>.json. Exit 0 only on PASS; FAIL and
INCONCLUSIVE exit 1 and say which comparison failed.
"""
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import ensure_hermes_lib, header_diffs, http_observe, is_preflight, origin_of, required_headers  # noqa: E402
from _scenarios import (CorpusError, SCENARIO_ORACLES, SCENARIO_PARITY, auth_headers, corpus_digest,  # noqa: E402
                        load_corpus, request_of, scenario, scenario_slug)

ensure_hermes_lib()
from planner.admission import verify_receipt  # noqa: E402
from planner.canonical import digest, load_json, write_canonical  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--dest-url", required=True, help="the destination's base URL, including its root path")
    ap.add_argument("--reset-cmd", default="", help="the command that restores the declared initial state; defaults to the reset script beside this one. A scenario that declares reset_before is INCONCLUSIVE without it.")
    ap.add_argument("--no-reset", action="store_true", help="the caller restored the initial state itself; it must still match what the source started from, which is checked either way")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    receipt, gaps = verify_receipt(root, require_admitted=True)
    verdict = {"schema": "rhoai3.scenario-parity/v1", "scenario": args.scenario, "entry_point": "",
               "receipt_sha256": receipt["receipt_digest"] if receipt else "", "verdict": "INCONCLUSIVE",
               "corpus_sha256": "", "reason": "", "request": {}, "reset": {}, "before": [], "expected": {}, "observed": {}, "effects": []}
    out = root / SCENARIO_PARITY / (scenario_slug(args.scenario) + ".json")
    if gaps or receipt is None:
        verdict["reason"] = "receipt not authoritative: " + "; ".join(gaps)
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    try:
        corpus = load_corpus(root)
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
    oracle_p = root / SCENARIO_ORACLES / (scenario_slug(args.scenario) + ".json")
    if not oracle_p.is_file():
        verdict["reason"] = "no source capture for this scenario; the expected values come only from the source"
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    oracle = load_json(oracle_p)
    checks: list[str] = []
    if oracle.get("status") != "CAPTURED":
        checks.append("the source capture is %s: %s" % (oracle.get("status"), oracle.get("reason")))
    # The capture is bound to the frozen source (the evidence bundle) and to
    # the corpus, not to the admission receipt: it is taken at M1, and a
    # destination repair must not oblige anyone to re-capture the source.
    bundle_sha = digest(load_json(root / EVIDENCE_BUNDLE))
    if str(oracle.get("evidence_bundle_sha256") or "") not in ("", bundle_sha):
        checks.append("the source capture describes bundle %s, this run's is %s" % (str(oracle.get("evidence_bundle_sha256"))[:12], bundle_sha[:12]))
    if oracle.get("corpus_sha256") != corpus_digest(corpus):
        checks.append("the source capture was taken against corpus %s, this is corpus %s; re-capture the source rather than comparing across corpora"
                      % (str(oracle.get("corpus_sha256"))[:12], corpus_digest(corpus)[:12]))
    recorded = oracle.get("request") or {}
    if recorded.get("request_sha256") != req["request_sha256"]:
        checks.append("the request this corpus describes (%s) is not the one the source answered (%s); the replay would not be a replay"
                      % (req["request_sha256"][:12], str(recorded.get("request_sha256"))[:12]))
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
    if sc.get("reset_before", True) and not before_expected:
        verdict["reason"] = ("the source capture recorded no initial state for a scenario that declares reset_before; "
                             "re-capture the source so the state it started from is on record")
        write_canonical(out, verdict)
        print("REFUSE: SCENARIO_PARITY %s INCONCLUSIVE (%s)" % (args.scenario, verdict["reason"]), file=sys.stderr)
        return 1
    for exp_before in before_expected:
        probe = http_observe(args.dest_url, str(exp_before.get("method") or "GET"), str(exp_before.get("path") or "/"), headers=headers)
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
    got = http_observe(args.dest_url, req["method"], req["path"], body=req["body"], headers={**req["headers"], **headers})
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
        probe = http_observe(args.dest_url, str(eff.get("method") or "GET"), str(eff.get("path") or "/"), headers=headers)
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
