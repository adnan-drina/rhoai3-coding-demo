#!/usr/bin/env python3
"""G-2 admission evaluator — field/obligation conservation (W2 §10).

Runs the three admission fixtures under
`.hermes/skills/gates/check-release-readiness/fixtures/admission/g2-harvest-fidelity/` (known-good / known-bad /
known-vacuous) and writes each verdict under
`evidence/fixtures/admission/out/g2-harvest-fidelity/`.

Usage:
  python3 g2-harvest-fidelity.py .
  python3 g2-harvest-fidelity.py /projects/modernized
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from verdict import expect, product_gate_verdict, write_verdict, INCONCLUSIVE_FIXTURE  # noqa: E402

EXIT_CODES = """Exit codes:
  0  pass — every admission fixture produced its expected verdict
  1  BLOCK — at least one fixture verdict differs from expectation
     (printed as `FAIL G-2/<fixture>: got X, want Y`)
  2  usage / harness defect (bad or unknown argument)
"""

FIELD_RE = re.compile(r"\bprivate\s+[\w.<>,\s\[\]]+\s+(\w+)\s*;")


def fields_in(tree: Path) -> set[str]:
    names: set[str] = set()
    for p in tree.rglob("*.java"):
        for m in FIELD_RE.finditer(p.read_text(encoding="utf-8", errors="replace")):
            names.add(m.group(1))
    return names


def evaluate(fixture_dir: Path) -> str:
    ref = fixture_dir / "referent"
    dst = fixture_dir / "destination"
    if not ref.is_dir() or not dst.is_dir():
        return "INCONCLUSIVE"
    ref_files = list(ref.rglob("*.java"))
    if not ref_files:
        return "INCONCLUSIVE"
    ref_f = fields_in(ref)
    dst_f = fields_in(dst)
    if not ref_f and not dst_f:
        return "INCONCLUSIVE"
    missing = ref_f - dst_f
    if missing:
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
        dest = root / "evidence" / "g2" / "destination"
        ref = root / "evidence" / "g2" / "referent"
        evidence = dest if dest.is_dir() and ref.is_dir() else None
        computed = evaluate(root / "evidence" / "g2") if evidence else INCONCLUSIVE_FIXTURE
        got = product_gate_verdict(computed, evidence)
        print(f"PRODUCT G-2: {got}")
        print(f"PRODUCT G-2: {got}", file=sys.stderr)
        return 0
    base = root / ".hermes/skills/gates/check-release-readiness/fixtures/admission/g2-harvest-fidelity"
    expected = {
        "known-good": "ACCEPT",
        "known-bad": "REFUSE",
        "known-vacuous": "INCONCLUSIVE",
    }
    rc = 0
    out_base = __import__("os").environ.get("RHOAI3_ADMISSION_OUT")
    if out_base:
        out_dir = Path(out_base) / "g2-harvest-fidelity"
    else:
        # UPLIFT-7: never write run-state into the golden tree by default
        out_dir = Path(__import__("tempfile").mkdtemp(prefix="rhoai3-g2-harvest-fidelity-"))
    for name, want in expected.items():
        got = evaluate(base / name)
        write_verdict(
            out_dir / f"{name}.json",
            "G-2",
            name,
            got,
            "field-set comparison",
            {"path": str(base / name)},
        )
        rc |= expect(got, want, "G-2", name)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
