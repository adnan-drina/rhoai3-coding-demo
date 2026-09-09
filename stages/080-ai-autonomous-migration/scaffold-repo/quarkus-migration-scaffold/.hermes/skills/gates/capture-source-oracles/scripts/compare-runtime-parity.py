#!/usr/bin/env python3
"""Compare the DESTINATION against a captured source oracle for one entry point.

Writes verification/parity/<slug>.json with PASS / FAIL / INCONCLUSIVE.
Exit 0 only on PASS. A missing or UNCAPTURED oracle is INCONCLUSIVE.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import ORACLES, PARITY, http_observe, normalize_observation, slug  # noqa: E402
from planner.admission import verify_receipt  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402


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
        elif oracle.get("receipt_sha256") != receipt["receipt_digest"]:
            verdict["reason"] = "source oracle belongs to receipt %s, not %s" % (str(oracle.get("receipt_sha256"))[:12], receipt["receipt_digest"][:12])
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
