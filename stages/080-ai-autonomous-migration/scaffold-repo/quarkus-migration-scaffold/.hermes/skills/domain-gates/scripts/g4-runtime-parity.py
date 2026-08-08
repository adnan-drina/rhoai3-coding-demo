#!/usr/bin/env python3
"""G-4 admission evaluator — response parity / identical 5xx vacuity (W2 §10)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from verdict import expect, write_verdict  # noqa: E402


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
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    base = root / "migration/fixtures/admission/g4-runtime-parity"
    expected = {
        "known-good": "ACCEPT",
        "known-bad": "REFUSE",
        "known-vacuous": "INCONCLUSIVE",
    }
    rc = 0
    out_dir = root / "migration/fixtures/admission/out/g4-runtime-parity"
    for name, want in expected.items():
        got = evaluate(base / name)
        write_verdict(
            out_dir / f"{name}.json",
            "G-4",
            name,
            got,
            "parity.json",
            {"path": str(base / name)},
        )
        rc |= expect(got, want, "G-4", name)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
