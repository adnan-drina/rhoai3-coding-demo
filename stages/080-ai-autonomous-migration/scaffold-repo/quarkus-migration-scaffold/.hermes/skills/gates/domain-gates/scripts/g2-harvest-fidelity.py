#!/usr/bin/env python3
"""G-2 admission evaluator — field/obligation conservation (W2 §10)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from verdict import expect, write_verdict  # noqa: E402

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
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    base = root / "migration/fixtures/admission/g2-harvest-fidelity"
    expected = {
        "known-good": "ACCEPT",
        "known-bad": "REFUSE",
        "known-vacuous": "INCONCLUSIVE",
    }
    rc = 0
    out_dir = root / "migration/fixtures/admission/out/g2-harvest-fidelity"
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
