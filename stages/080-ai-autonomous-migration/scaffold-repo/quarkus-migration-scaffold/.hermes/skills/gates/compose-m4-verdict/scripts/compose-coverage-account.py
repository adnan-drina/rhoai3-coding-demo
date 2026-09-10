#!/usr/bin/env python3
"""Compose evidence/verdicts/coverage-account.json: what an ADR retired, and
what now covers it.

Retiring a source removes behaviour, or removes the only thing that checked
some behaviour. M4 must therefore say, per retired file, what covers it in the
destination and what does not. This is computed, never narrated:

  * the rows come from decisions.yaml retired_sources (path, adr, reason);
  * a row is REPLACED only when the decision names replacement scenarios
    (``replaced_by``: admitted entry-point ids) AND the parity receipt records
    every named entry point as PASS;
  * a row with no ``replaced_by`` is a recorded GAP. Not a failure: an accepted
    ADR may knowingly drop coverage. But it is never silent.

A retired test source additionally requires fresh executed test evidence to
count as replaced: assert-surefire-results owns that measurement, and its
receipt (if present) is cited here.

Exit 0 when the account was written, 1 when an input needed to compute it is
missing (never a partial account), 2 usage."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_hermes_lib() -> None:
    p = Path(__file__).resolve()
    for parent in p.parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            s = str(lib)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise SystemExit("FAIL: COVERAGE_ACCOUNT .hermes/lib marker missing")


_ensure_hermes_lib()
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.decisions import DecisionsError, accepted_adrs, load_decisions  # noqa: E402
from planner.paths import DECISIONS, PARITY_DIR  # noqa: E402

ACCOUNT = Path("evidence") / "verdicts" / "coverage-account.json"
SUREFIRE_RECEIPT = Path("evidence") / "receipts" / "gates" / "assert-surefire-results.json"


def _fail(msg: str) -> int:
    print("FAIL: COVERAGE_ACCOUNT %s" % msg, file=sys.stderr)
    return 1


def parity_verdicts(root: Path) -> tuple[str, dict[str, str]]:
    """(receipt verdict, entry point id → verdict) from the parity receipt."""
    p = root / PARITY_DIR / "receipt.json"
    if not p.is_file():
        return "", {}
    doc = load_json(p)
    rows = {str(r.get("entry_point")): str(r.get("verdict")) for r in (doc.get("entry_points") or []) if isinstance(r, dict)}
    return str(doc.get("verdict") or ""), rows


def rows_of(doc: dict, root: Path) -> list[dict]:
    ok = accepted_adrs(doc)
    parity_verdict, per_ep = parity_verdicts(root)
    surefire = load_json(root / SUREFIRE_RECEIPT) if (root / SUREFIRE_RECEIPT).is_file() else None
    tests_executed = bool(surefire) and int(surefire.get("rc", 1)) == 0
    out: list[dict] = []
    for raw in doc.get("retired_sources") or []:
        path = str(raw.get("path") or "")
        adr = str(raw.get("adr") or "")
        named = [str(x) for x in (raw.get("replaced_by") or []) if str(x)]
        kind = "test" if path.startswith("src/test/") or "/src/test/" in path else "implementation"
        gaps: list[str] = []
        if adr not in ok:
            gaps.append("the ADR that retires it is not accepted")
        if not named:
            gaps.append("the decision names no replacement scenario (replaced_by)")
        for ep in named:
            verdict = per_ep.get(ep, "")
            if not verdict:
                gaps.append("%s is not an entry point the parity receipt measured" % ep)
            elif verdict != "PASS":
                gaps.append("%s measured %s, not PASS" % (ep, verdict))
        if named and kind == "test" and not tests_executed:
            gaps.append("a retired test is replaced only beside fresh executed test evidence (%s)" % ("assert-surefire-results receipt rc %s" % surefire.get("rc") if surefire else "no assert-surefire-results receipt"))
        out.append({
            "path": path, "adr": adr, "kind": kind,
            "retired_because": str(raw.get("reason") or ""),
            "replaced_by": named,
            "replacement_measured": [{"entry_point": ep, "verdict": per_ep.get(ep, "")} for ep in named],
            "remaining_gap": bool(gaps),
            "gap_reasons": gaps,
        })
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out", default="", help="write the account here instead of evidence/verdicts/coverage-account.json (a checker recomputing the account must not author the product's copy)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not (root / DECISIONS).is_file():
        return _fail("%s is absent; the retirements cannot be enumerated" % DECISIONS)
    try:
        doc = load_decisions(root)
    except DecisionsError as exc:
        return _fail("%s: %s" % (DECISIONS, exc))
    parity_verdict, per_ep = parity_verdicts(root)
    rows = rows_of(doc, root)
    gaps = [r["path"] for r in rows if r["remaining_gap"]]
    account = {
        "schema": "rhoai3.coverage-account/v1",
        "producer": "compose-coverage-account.py",
        "parity_receipt_verdict": parity_verdict,
        "entry_points_measured": sorted(per_ep),
        "rows": rows,
        "summary": {
            "retired": len(rows),
            "tests": sum(1 for r in rows if r["kind"] == "test"),
            "implementations": sum(1 for r in rows if r["kind"] == "implementation"),
            "replaced": len(rows) - len(gaps),
            "remaining_gaps": len(gaps),
        },
        "remaining_gaps": sorted(gaps),
    }
    out = Path(args.out).resolve() if args.out else root / ACCOUNT
    write_canonical(out, account)
    s = account["summary"]
    print("OK: coverage account (%d retired: %d test, %d implementation; %d replaced, %d gap(s); parity %s) → %s"
          % (s["retired"], s["tests"], s["implementations"], s["replaced"], s["remaining_gaps"], parity_verdict or "not measured", out if args.out else ACCOUNT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
