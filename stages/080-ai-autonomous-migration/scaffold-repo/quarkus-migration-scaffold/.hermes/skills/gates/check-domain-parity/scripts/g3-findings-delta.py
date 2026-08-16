#!/usr/bin/env python3
"""G-3 admission evaluator — MTA findings / asserted-resolved (W2 §10).

Runs the three admission fixtures under
`.hermes/skills/gates/check-release-readiness/fixtures/admission/g3-findings-delta/` (known-good / known-bad /
known-vacuous) and writes each verdict under
`evidence/fixtures/admission/out/g3-findings-delta/`.

Usage:
  python3 g3-findings-delta.py .
  python3 g3-findings-delta.py /projects/modernized
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from verdict import expect, product_gate_verdict, write_verdict, INCONCLUSIVE_FIXTURE  # noqa: E402

EXIT_CODES = """Exit codes:
  0  pass — every admission fixture produced its expected verdict
  1  BLOCK — at least one fixture verdict differs from expectation
     (printed as `FAIL G-3/<fixture>: got X, want Y`)
  2  usage / harness defect (bad or unknown argument)
"""


def evaluate(fixture_dir: Path) -> str:
    path = fixture_dir / "mta-findings.json"
    if not path.is_file():
        return "INCONCLUSIVE"
    data = json.loads(path.read_text(encoding="utf-8"))
    evidence = data.get("execution_evidence") or {}
    if not evidence.get("analyzer_ran"):
        return "INCONCLUSIVE"
    violations = data.get("violations") or {}
    if not violations:
        return "ACCEPT"
    for v in violations.values():
        if v.get("asserted_resolved"):
            # Finding still present but marked resolved — G-3's own failure mode
            return "REFUSE"
        if (v.get("category") or "").lower() == "mandatory":
            return "REFUSE"
    return "ACCEPT"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="product root containing governance/fixtures/admission (default: .)",
    )
    ap.add_argument(
        "--product",
        action="store_true",
        help="score dest evidence only; fixtures cannot ACCEPT (B-5)",
    )
    args = ap.parse_args()
    root = Path(args.root)
    if args.product:
        evidence = root / "evidence" / "mta-findings.json"
        computed = (
            evaluate(root / "evidence") if evidence.is_file() else INCONCLUSIVE_FIXTURE
        )
        got = product_gate_verdict(computed, evidence if evidence.is_file() else None)
        print(f"PRODUCT G-3: {got}")
        print(f"PRODUCT G-3: {got}", file=sys.stderr)
        return 0
    base = root / ".hermes/skills/gates/check-release-readiness/fixtures/admission/g3-findings-delta"
    expected = {
        "known-good": "ACCEPT",
        "known-bad": "REFUSE",
        "known-vacuous": "INCONCLUSIVE",
    }
    rc = 0
    out_base = __import__("os").environ.get("RHOAI3_ADMISSION_OUT")
    if out_base:
        out_dir = Path(out_base) / "g3-findings-delta"
    else:
        # UPLIFT-7: never write run-state into the golden tree by default
        out_dir = Path(__import__("tempfile").mkdtemp(prefix="rhoai3-g3-findings-delta-"))
    for name, want in expected.items():
        got = evaluate(base / name)
        write_verdict(
            out_dir / f"{name}.json",
            "G-3",
            name,
            got,
            "mta-findings.json",
            {"path": str(base / name)},
        )
        rc |= expect(got, want, "G-3", name)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
