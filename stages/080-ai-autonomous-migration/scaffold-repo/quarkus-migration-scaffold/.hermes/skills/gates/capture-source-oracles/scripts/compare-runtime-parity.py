#!/usr/bin/env python3
"""Compare the DESTINATION against a captured source oracle for one entry point.

Writes verification/parity/<slug>.json with PASS / FAIL / INCONCLUSIVE.
Exit 0 only on PASS. A missing or UNCAPTURED oracle is INCONCLUSIVE.

Binding rule. The ORACLE is bound to the frozen source (the evidence bundle
digest); the VERDICT is a destination judgement and stays bound to the
admission receipt. This script used to refuse an oracle whose receipt digest
was not the current one, which made every M1 read oracle INCONCLUSIVE the
moment the next accepted step re-sealed admission (measured on v9,
2026-09-14) -- yet the source's behaviour does not change when the
destination's admission is re-sealed. An oracle from another bundle, or one
with no bundle digest at all (an older capture), is INCONCLUSIVE.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import ORACLES, PARITY, http_observe, normalize_observation, slug  # noqa: E402
from planner.admission import verify_receipt  # noqa: E402
from planner.canonical import digest, load_json, write_canonical  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--entry-point", required=True)
    ap.add_argument("--dest-url", default="")
    ap.add_argument("--dest-observation", default="", help="captured destination observation file for non-HTTP kinds")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    receipt, gaps = verify_receipt(root, require_admitted=True)
    verdict = {"schema": "rhoai3.parity/v1", "entry_point": args.entry_point, "receipt_sha256": receipt["receipt_digest"] if receipt else "", "verdict": "INCONCLUSIVE", "reason": "", "expected": {}, "observed": {}}
    out = root / PARITY / (slug(args.entry_point) + ".json")
    if gaps or receipt is None:
        verdict["reason"] = "receipt not authoritative: " + "; ".join(gaps)
        write_canonical(out, verdict)
        print("REFUSE: PARITY %s INCONCLUSIVE (%s)" % (args.entry_point, verdict["reason"]), file=sys.stderr)
        return 1
    op = root / ORACLES / (slug(args.entry_point) + ".json")
    if not op.is_file():
        verdict["reason"] = "no source oracle captured"
    else:
        oracle = load_json(op)
        if oracle.get("status") != "CAPTURED":
            verdict["reason"] = "source oracle %s: %s" % (oracle.get("status"), oracle.get("reason"))
        elif not oracle.get("evidence_bundle_sha256"):
            verdict["reason"] = "capture not bound to the frozen source (no evidence_bundle_sha256; re-capture the reads)"
        elif str(oracle.get("evidence_bundle_sha256")) != digest(load_json(root / EVIDENCE_BUNDLE)):
            verdict["reason"] = ("source oracle describes another frozen source (bundle %s, this tree's is %s); the destination cannot be compared against a source that is not this one"
                                 % (str(oracle.get("evidence_bundle_sha256"))[:12], digest(load_json(root / EVIDENCE_BUNDLE))[:12]))
        elif oracle.get("kind") == "http" and str((oracle.get("oracle") or {}).get("method") or "GET").upper() not in ("GET", "HEAD"):
            # This script replays a method and a path. That is enough for a
            # read and provably not enough for a write: it sent no body, so a
            # recorded POST the source answered 201 for was replayed as an
            # empty POST and compared FAIL against an identical destination.
            # Writes go through the scenario corpus, which carries the complete
            # request and the effects that prove what it did.
            verdict["reason"] = ("a %s entry point is compared through the scenario corpus (compare-scenario-parity.py), "
                                 "not here: a replay without the recorded body and headers is not a replay"
                                 % str(oracle["oracle"].get("method")))
        elif oracle.get("kind") == "http":
            exp = oracle["oracle"]
            verdict["expected"] = {"status": exp.get("status"), "body_sha256": exp.get("body_sha256"), "body_kind": exp.get("body_kind")}
            if not args.dest_url:
                verdict["reason"] = "no --dest-url"
            else:
                got = http_observe(args.dest_url, exp.get("method", "GET"), exp.get("path", "/"))
                verdict["observed"] = {"status": got.get("status"), "body_sha256": got.get("body_sha256"), "body_kind": got.get("body_kind"), "body_sample": got.get("body_sample", "")}
                if got.get("status") == 0:
                    verdict["reason"] = "destination unreachable: %s" % got.get("error")
                elif got.get("status") == exp.get("status") and got.get("body_sha256") == exp.get("body_sha256"):
                    verdict["verdict"] = "PASS"
                else:
                    verdict["verdict"] = "FAIL"
                    verdict["reason"] = "status %s vs %s; body %s vs %s" % (got.get("status"), exp.get("status"), str(got.get("body_sha256"))[:12], str(exp.get("body_sha256"))[:12])
        else:
            exp = oracle["oracle"]
            verdict["expected"] = {"observation_sha256": exp.get("observation_sha256"), "lines": exp.get("lines")}
            f = Path(args.dest_observation) if args.dest_observation else None
            if not f or not f.is_file():
                verdict["reason"] = "%s parity needs --dest-observation <file> captured from the destination" % oracle.get("kind")
            else:
                sha, n = normalize_observation(f)
                verdict["observed"] = {"observation_sha256": sha, "lines": n}
                if sha == exp.get("observation_sha256"):
                    verdict["verdict"] = "PASS"
                else:
                    verdict["verdict"] = "FAIL"
                    verdict["reason"] = "normalized observation differs (%d vs %d lines)" % (n, exp.get("lines") or 0)
    write_canonical(out, verdict)
    if verdict["verdict"] == "PASS":
        print("OK: PARITY %s PASS → %s" % (args.entry_point, out))
        return 0
    print("REFUSE: PARITY %s %s (%s) → %s" % (args.entry_point, verdict["verdict"], verdict["reason"], out), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
