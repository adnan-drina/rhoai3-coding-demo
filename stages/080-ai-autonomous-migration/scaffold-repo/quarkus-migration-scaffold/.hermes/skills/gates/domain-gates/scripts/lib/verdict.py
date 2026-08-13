"""Shared gate verdict helpers (ACCEPT / REFUSE / INCONCLUSIVE).

UPLIFT-2: machine-consumable JSON on stdout; human PASS/FAIL lines on stderr
(byte-identical to the pre-uplift strings so greps/SKILL Verification stay valid).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


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
