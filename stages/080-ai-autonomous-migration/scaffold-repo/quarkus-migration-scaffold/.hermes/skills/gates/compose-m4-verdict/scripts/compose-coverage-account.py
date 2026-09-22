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
from planner.paths import DECIDED_REPAIRS_RECEIPT, DECISIONS, PARITY_DIR  # noqa: E402

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


def parity_coverage(root: Path) -> tuple[dict[str, dict], dict[str, int]]:
    """How each entry point is covered, and the receipt's own three-way count.

    ARCHITECT RULING 2026-09-22: a qualified scenario that explicitly binds an
    entry point, and whose destination replay passed, is coverage -- recorded
    by compose-parity-receipt.py as ``coverage_kind: scenario`` with the
    scenario ids, distinct from ``oracle``. It is carried through to the
    account so a replacement claim says HOW it was measured, never only that
    it passed. It grants no credit on its own: the row still has to be PASS."""
    p = root / PARITY_DIR / "receipt.json"
    if not p.is_file():
        return {}, {}
    doc = load_json(p)
    per = {}
    for r in (doc.get("entry_points") or []):
        if not isinstance(r, dict):
            continue
        by = r.get("covered_by") if isinstance(r.get("covered_by"), dict) else {}
        per[str(r.get("entry_point"))] = {"kind": str(r.get("coverage_kind") or ""),
                                          "scenarios": [str(s) for s in (by.get("scenarios") or [])]}
    summary = doc.get("coverage_summary") if isinstance(doc.get("coverage_summary"), dict) else {}
    return per, {str(k): int(v) for k, v in summary.items()}


def uncovered_capabilities(root: Path) -> list[dict]:
    """The parity receipt's ``coverage_gaps``: scenarios whose capture did
    not demonstrate the operation the scenario intends (``fixture-failed``:
    the SOURCE did not perform it, e.g. a create the source answered 400 for),
    whose capture could not be judged at all (``inconclusive-qualification``:
    unusable evidence, or a predicate the document leaves unanswerable -- a
    capability nobody judged is a capability nobody demonstrated), or whose
    qualification judged another capture (``stale-qualification``).
    The parity receipt used to be read for its per-entry-point verdict only,
    so such a gap was invisible here (architect review of 708cfef9): an
    entry point could earn replacement credit for a capability nobody
    demonstrated. Each is recorded as UNCOVERED and denies credit."""
    p = root / PARITY_DIR / "receipt.json"
    if not p.is_file():
        return []
    out = []
    for g in (load_json(p).get("coverage_gaps") or []):
        if isinstance(g, dict) and g.get("entry_point"):
            out.append({"scenario": str(g.get("scenario") or ""), "entry_point": str(g.get("entry_point")),
                        "kind": str(g.get("kind") or "not-qualified"), "intent": str(g.get("intent") or "positive"),
                        "reason": str(g.get("reason") or "")})
    return sorted(out, key=lambda g: (g["entry_point"], g["scenario"]))


def retired_thresholds(root: Path) -> list[dict]:
    """Coverage thresholds a decided retirement removed from the build
    (ADR-013 via the bootstrap's decided repairs, ADR-019 §3). Recorded as
    retired-not-achieved: a retirement never counts as reaching them."""
    p = root / DECIDED_REPAIRS_RECEIPT
    if not p.is_file():
        return []
    rows = ((load_json(p).get("coverage_account") or {}).get("retired_thresholds")) or []
    return sorted((dict(r) for r in rows if isinstance(r, dict)), key=lambda r: str(r.get("id")))


def rows_of(doc: dict, root: Path) -> list[dict]:
    ok = accepted_adrs(doc)
    parity_verdict, per_ep = parity_verdicts(root)
    per_cov, _ = parity_coverage(root)
    uncovered = uncovered_capabilities(root)
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
            for g in uncovered:
                if g["entry_point"] == ep and g["intent"] == "positive":
                    # no replacement credit for a capability the source never
                    # demonstrated, whatever the entry point's parity verdict
                    gaps.append("%s: %s did not demonstrate its capability (%s: %s); no replacement credit" % (ep, g["scenario"], g["kind"], g["reason"][:160]))
        if named and kind == "test" and not tests_executed:
            gaps.append("a retired test is replaced only beside fresh executed test evidence (%s)" % ("assert-surefire-results receipt rc %s" % surefire.get("rc") if surefire else "no assert-surefire-results receipt"))
        out.append({
            "path": path, "adr": adr, "kind": kind,
            "retired_because": str(raw.get("reason") or ""),
            "replaced_by": named,
            "replacement_measured": [{"entry_point": ep, "verdict": per_ep.get(ep, ""),
                                      "coverage": str((per_cov.get(ep) or {}).get("kind") or ""),
                                      "covered_by_scenarios": list((per_cov.get(ep) or {}).get("scenarios") or [])}
                                     for ep in named],
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
    uncovered = uncovered_capabilities(root)
    _, cov_summary = parity_coverage(root)
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
            "uncovered_capabilities": len(uncovered),
        },
        "remaining_gaps": sorted(gaps),
        # the receipt's own three-way count: entry points covered by their
        # read oracle, by a qualified passing scenario (the 2026-09-22
        # ruling), and not at all. Kept out of `summary`, which the M4 verdict
        # carries verbatim, and reported beside it: a run with uncovered entry
        # points can be CLOSED, and is still not shipped.
        "entry_point_coverage": dict(cov_summary),
        # capabilities the source never demonstrated (the parity receipt's
        # coverage_gaps): uncovered, never silently covered by a passing
        # entry point
        "uncovered_capabilities": uncovered,
        # thresholds the build no longer enforces, kept as an open follow-up
        # (never as coverage achieved)
        "retired_thresholds": retired_thresholds(root),
    }
    out = Path(args.out).resolve() if args.out else root / ACCOUNT
    write_canonical(out, account)
    s = account["summary"]
    print("OK: coverage account (%d retired: %d test, %d implementation; %d replaced, %d gap(s); parity %s) → %s"
          % (s["retired"], s["tests"], s["implementations"], s["replaced"], s["remaining_gaps"], parity_verdict or "not measured", out if args.out else ACCOUNT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
