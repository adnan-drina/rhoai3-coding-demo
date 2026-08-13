#!/usr/bin/env python3
"""G-4 admission evaluator — response parity / identical 5xx vacuity (W2 §10).

ER#2 F8 / AD-H §G.4: current depth is SAMPLE, not behavioral-equivalence.
Every gate output stamps g4_mode=SAMPLE until partitions + permitted
equivalence + zero unverified entry points land for release_qualified.

Runs the three admission fixtures under
`governance/fixtures/admission/g4-runtime-parity/` (known-good / known-bad /
known-vacuous) and writes each verdict under
`evidence/fixtures/admission/out/g4-runtime-parity/`.

Usage:
  python3 g4-runtime-parity.py .
  python3 g4-runtime-parity.py /projects/modernized
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from verdict import expect, write_verdict  # noqa: E402

EXIT_CODES = """Exit codes:
  0  pass — every admission fixture produced its expected verdict and every
     written verdict carries the g4_mode=SAMPLE stamp
  1  BLOCK — a fixture verdict differs from expectation, or a written verdict
     is missing the g4_mode=SAMPLE stamp (ER#2 F8)
  2  usage / harness defect (bad or unknown argument)
"""

# AD-H §G.4 / ER#2 F8 — honest label until equivalence bar is met
G4_MODE = "SAMPLE"


def evaluate(fixture_dir: Path) -> str:
    path = fixture_dir / "parity.json"
    if not path.is_file():
        return "INCONCLUSIVE"
    data = json.loads(path.read_text(encoding="utf-8"))
    evidence = data.get("execution_evidence") or {}
    scenarios = data.get("scenarios") or []
    if not evidence.get("scenarios_ran") or not scenarios:
        return "INCONCLUSIVE"
    conclusive = 0
    for sc in scenarios:
        ref = sc.get("referent") or {}
        dst = sc.get("destination") or {}
        rs, ds = int(ref.get("status") or 0), int(dst.get("status") or 0)
        if rs >= 500 and ds >= 500 and rs == ds:
            # identical failure — vacuous for this scenario
            continue
        conclusive += 1
        if rs != ds or (ref.get("body") != dst.get("body")):
            return "REFUSE"
    if conclusive == 0:
        return "INCONCLUSIVE"
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
    args = ap.parse_args()
    root = Path(args.root)
    base = root / "governance/fixtures/admission/g4-runtime-parity"
    expected = {
        "known-good": "ACCEPT",
        "known-bad": "REFUSE",
        "known-vacuous": "INCONCLUSIVE",
    }
    rc = 0
    out_base = __import__("os").environ.get("RHOAI3_ADMISSION_OUT")
    if out_base:
        out_dir = Path(out_base) / "g4-runtime-parity"
    else:
        # UPLIFT-7: never write run-state into the golden tree by default
        out_dir = Path(__import__("tempfile").mkdtemp(prefix="rhoai3-g4-runtime-parity-"))
    for name, want in expected.items():
        got = evaluate(base / name)
        write_verdict(
            out_dir / f"{name}.json",
            "G-4",
            name,
            got,
            "parity.json",
            {"path": str(base / name)},
            g4_mode=G4_MODE,
        )
        # F8: refuse silent equivalence — SAMPLE stamp required on every write
        written = json.loads((out_dir / f"{name}.json").read_text(encoding="utf-8"))
        if written.get("g4_mode") != G4_MODE:
            print(f"FAIL G-4/{name}: missing g4_mode={G4_MODE} stamp (ER#2 F8)", file=sys.stderr)
            rc = 1
        rc |= expect(got, want, "G-4", name)
    if rc == 0:
        print(f"OK: G-4 admission stamped g4_mode={G4_MODE} (not equivalence oracle)")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
