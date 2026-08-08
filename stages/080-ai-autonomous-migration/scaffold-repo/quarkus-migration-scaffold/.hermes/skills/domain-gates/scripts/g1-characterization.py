#!/usr/bin/env python3
"""G-1 admission evaluator — mutation / char_surface (W2 §10)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from verdict import expect, write_verdict  # noqa: E402


def evaluate(fixture_dir: Path) -> str:
    evidence_path = fixture_dir / "mutation-evidence.json"
    if not evidence_path.is_file():
        return "INCONCLUSIVE"
    data = json.loads(evidence_path.read_text(encoding="utf-8"))
    if not data.get("ran"):
        return "INCONCLUSIVE"
    if int(data.get("mutations_total") or 0) == 0:
        return "INCONCLUSIVE"
    if data.get("char_surface_stub"):
        return "REFUSE"
    killed = int(data.get("mutations_killed") or 0)
    total = int(data.get("mutations_total") or 0)
    if total > 0 and killed == total:
        return "ACCEPT"
    return "REFUSE"


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    base = root / "migration/fixtures/admission/g1-characterization"
    expected = {
        "known-good": "ACCEPT",
        "known-bad": "REFUSE",
        "known-vacuous": "INCONCLUSIVE",
    }
    rc = 0
    out_dir = root / "migration/fixtures/admission/out/g1-characterization"
    for name, want in expected.items():
        got = evaluate(base / name)
        write_verdict(
            out_dir / f"{name}.json",
            "G-1",
            name,
            got,
            "mutation-evidence.json",
            {"path": str(base / name)},
        )
        rc |= expect(got, want, "G-1", name)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
