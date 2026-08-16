#!/usr/bin/env python3
"""G-1 admission evaluator — mutation / char_surface (W2 §10; §G.1 F9 table)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from verdict import (  # noqa: E402
    INCONCLUSIVE_FIXTURE,
    expect,
    product_gate_verdict,
    write_verdict,
)


def evaluate(fixture_dir: Path) -> str:
    """Apply §G.1 F9 transition table (v1) + prior char_surface / score rules.

    FAIL rows (F9): dest ``mutants_generated==0``; kill ratio ``0/0``.
    INCONCLUSIVE rows (F9): referent dry-run could not run; floor ambiguous.
    """
    evidence_path = fixture_dir / "mutation-evidence.json"
    if not evidence_path.is_file():
        return "INCONCLUSIVE"

    data = json.loads(evidence_path.read_text(encoding="utf-8"))

    # F9 — floor ambiguous / ratchet-only proposed for first qual → INCONCLUSIVE
    floor = str(data.get("floor_status") or "").lower()
    if data.get("floor_ambiguous") or floor in {"ambiguous", "ratchet_only"}:
        return "INCONCLUSIVE"

    ran = bool(data.get("ran"))
    tool_error = bool(data.get("tool_error") or data.get("skip"))
    # F9 — referent (or any) PIT dry-run could not run → INCONCLUSIVE
    if not ran or tool_error:
        return "INCONCLUSIVE"

    mutants = int(
        data.get("mutants_generated")
        if data.get("mutants_generated") is not None
        else (data.get("mutations_total") or 0)
    )
    killed = int(data.get("mutations_killed") or 0)

    # F9 — dest hollow / emptied OR vacuous 0/0 → FAIL (not INCONCLUSIVE)
    if mutants == 0:
        return "FAIL"

    if data.get("char_surface_stub"):
        return "REFUSE"

    # AR-3.6 — harness probe is not an acceptance operand
    operand = str(data.get("operand") or data.get("g1_operand") or "").lower()
    if data.get("probe_only") or operand in {"harness_probe", "probe", "tooling_smoke"}:
        return "REFUSE"

    if mutants > 0 and killed == mutants:
        return "ACCEPT"
    return "REFUSE"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument(
        "--product",
        action="store_true",
        help="score dest evidence only; fixtures cannot ACCEPT (B-5)",
    )
    args = ap.parse_args()
    root = Path(args.root)
    if args.product:
        evidence = root / "evidence" / "mutation-evidence.json"
        got = product_gate_verdict(
            evaluate(evidence.parent) if evidence.is_file() else INCONCLUSIVE_FIXTURE,
            evidence if evidence.is_file() else None,
        )
        out_base = __import__("os").environ.get("RHOAI3_ADMISSION_OUT")
        if out_base:
            out_dir = Path(out_base) / "g1-characterization-product"
        else:
            out_dir = Path(__import__("tempfile").mkdtemp(prefix="rhoai3-g1-product-"))
        write_verdict(
            out_dir / "product.json",
            "G-1",
            "product",
            got,
            "dest evidence/mutation-evidence.json",
            {"path": str(evidence) if evidence.is_file() else ""},
        )
        print(
            f"PRODUCT G-1: {got}",
            file=sys.stderr,
        )
        print(f"PRODUCT G-1: {got}")
        return 0
    base = root / ".hermes/skills/gates/check-release-readiness/fixtures/admission/g1-characterization"
    # known-vacuous SUPERSEDED by F9: zero mutants with ran=true → FAIL
    expected = {
        "known-good": "ACCEPT",
        "known-bad": "REFUSE",
        "known-vacuous": "FAIL",
        # ER#2 F9 golden rows (Architect E-20260810T083600Z)
        "f9-dest-zero-mutants": "FAIL",
        "f9-kill-ratio-0-0": "FAIL",
        "f9-referent-dry-run-fail": "INCONCLUSIVE",
        "f9-floor-ambiguous": "INCONCLUSIVE",
        # AR-3.6 — probe-only evidence → REFUSE (not ACCEPT)
        "ar36-probe-only": "REFUSE",
    }
    rc = 0
    out_base = __import__("os").environ.get("RHOAI3_ADMISSION_OUT")
    if out_base:
        out_dir = Path(out_base) / "g1-characterization"
    else:
        # UPLIFT-7: never write run-state into the golden tree by default
        out_dir = Path(__import__("tempfile").mkdtemp(prefix="rhoai3-g1-characterization-"))
    for name, want in expected.items():
        fixture = base / name
        if not fixture.is_dir():
            print(f"FAIL G-1/{name}: missing fixture dir {fixture}", file=sys.stderr)
            rc = 1
            continue
        got = evaluate(fixture)
        write_verdict(
            out_dir / f"{name}.json",
            "G-1",
            name,
            got,
            "mutation-evidence.json",
            {"path": str(fixture), "f9_table": "v1"},
        )
        rc |= expect(got, want, "G-1", name)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
