#!/usr/bin/env python3
"""Compose verification/parity/receipt.json — receipt-bound parity summary.

Independent producer: reads every parity verdict for the current
admission receipt and every entry point in the evidence bundle. PASS only
when every entry point has a PASS verdict bound to this receipt. Exit 0 on
PASS; 1 otherwise (never completes around a FAIL or an INCONCLUSIVE).
"""
from __future__ import annotations

import argparse
import sys
from typing import Any
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import PARITY, slug  # noqa: E402
from _scenarios import SCENARIO_PARITY  # noqa: E402
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
    # Scenario verdicts, grouped by the entry point they exercise. An entry
    # point covered by scenarios is PASS only when EVERY one of them passed:
    # one successful response is not behavioural coverage of an endpoint.
    by_ep: dict[str, list[dict[str, Any]]] = {}
    sdir = root / SCENARIO_PARITY
    for sp in sorted(sdir.glob("*.json")) if sdir.is_dir() else []:
        doc = load_json(sp)
        by_ep.setdefault(str(doc.get("entry_point") or ""), []).append(doc)
    rows = []
    failed = 0
    for ep in wanted:
        scenarios = by_ep.get(ep) or []
        if scenarios:
            bound = [d for d in scenarios if d.get("receipt_sha256") == receipt["receipt_digest"]]
            names = sorted(str(d.get("scenario")) for d in scenarios)
            if len(bound) != len(scenarios):
                verdict, reason = "INCONCLUSIVE", "one or more scenario verdicts are bound to another receipt"
            else:
                bad = [d for d in bound if d.get("verdict") != "PASS"]
                if not bad:
                    verdict, reason = "PASS", "%d scenario(s): %s" % (len(bound), ", ".join(names))
                elif all(d.get("verdict") == "INCONCLUSIVE" for d in bad):
                    verdict, reason = "INCONCLUSIVE", "; ".join("%s: %s" % (d.get("scenario"), d.get("reason")) for d in bad)[:400]
                else:
                    verdict, reason = "FAIL", "; ".join("%s: %s" % (d.get("scenario"), d.get("reason")) for d in bad if d.get("verdict") == "FAIL")[:400]
            rows.append({"entry_point": ep, "verdict": verdict, "reason": reason, "scenarios": names})
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
    doc = {"schema": "rhoai3.parity-receipt/v1", "receipt_sha256": receipt["receipt_digest"], "producer": "compose-parity-receipt.py", "entry_points": rows, "total": len(rows), "not_passed": failed, "verdict": "PASS" if rows and failed == 0 else ("INCONCLUSIVE" if not rows or all(r["verdict"] == "INCONCLUSIVE" for r in rows if r["verdict"] != "PASS") else "FAIL")}
    out = root / PARITY / "receipt.json"
    write_canonical(out, doc)
    if doc["verdict"] == "PASS":
        print("OK: parity receipt PASS (%d entry points) → %s" % (len(rows), out))
        return 0
    for r in rows:
        if r["verdict"] != "PASS":
            print("  - %s %s: %s" % (r["entry_point"], r["verdict"], r["reason"]), file=sys.stderr)
    print("REFUSE: parity receipt %s (%d of %d not passed) → %s" % (doc["verdict"], failed, len(rows), out), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
