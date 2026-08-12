#!/usr/bin/env python3
"""G-3 admission evaluator — MTA findings / asserted-resolved (W2 §10)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from verdict import expect, write_verdict  # noqa: E402


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
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    base = root / "migration/fixtures/admission/g3-findings-delta"
    expected = {
        "known-good": "ACCEPT",
        "known-bad": "REFUSE",
        "known-vacuous": "INCONCLUSIVE",
    }
    rc = 0
    out_dir = root / "migration/fixtures/admission/out/g3-findings-delta"
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
