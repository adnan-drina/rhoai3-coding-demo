"""Shared gate verdict helpers (ACCEPT / REFUSE / INCONCLUSIVE).

UPLIFT-2: machine-consumable JSON on stdout; human PASS/FAIL lines on stderr
(byte-identical to the pre-uplift strings so greps/SKILL Verification stay valid).

B-5: product mode never scores ACCEPT from admission fixtures. Missing dest
evidence or a path under `/fixtures/admission/` emits INCONCLUSIVE_FIXTURE.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

INCONCLUSIVE_FIXTURE = "INCONCLUSIVE_FIXTURE"
ADMISSION_FIXTURE_NEEDLE = "/fixtures/admission/"


def is_admission_fixture_path(path: Path | str | None) -> bool:
    if path is None:
        return True
    return ADMISSION_FIXTURE_NEEDLE in str(path).replace("\\", "/")


def product_gate_verdict(computed: str, evidence_path: Path | str | None) -> str:
    """Map a computed gate verdict onto the product path (B-5).

    Admission evaluators may still emit ACCEPT against fixtures. Product
    M4/M5 must not copy those ACCEPTs: missing dest evidence or a fixture
    path becomes INCONCLUSIVE_FIXTURE, never ACCEPT.
    """
    if evidence_path is None or not Path(evidence_path).exists():
        return INCONCLUSIVE_FIXTURE
    if is_admission_fixture_path(evidence_path):
        return INCONCLUSIVE_FIXTURE
    return computed


def write_verdict(
    path: Path,
    gate: str,
    fixture: str,
    verdict: str,
    reason: str,
    evidence: dict[str, Any],
    **extra: Any,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "gate": gate,
        "fixture": fixture,
        "verdict": verdict,
        "reason": reason,
        "evidence": evidence,
    }
    doc.update(extra)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def expect(actual: str, expected: str, gate: str, fixture: str) -> int:
    ok = actual == expected
    # Structured record — one JSON object per fixture (stdout).
    print(
        json.dumps(
            {
                "gate": gate,
                "fixture": fixture,
                "got": actual,
                "want": expected,
                "ok": ok,
            },
            separators=(",", ":"),
        ),
        flush=True,
    )
    # Human line — stderr, byte-identical to pre-UPLIFT-2 stdout text.
    if ok:
        print(f"PASS {gate}/{fixture}: {actual}", file=sys.stderr)
        return 0
    print(f"FAIL {gate}/{fixture}: got {actual}, want {expected}", file=sys.stderr)
    return 1
