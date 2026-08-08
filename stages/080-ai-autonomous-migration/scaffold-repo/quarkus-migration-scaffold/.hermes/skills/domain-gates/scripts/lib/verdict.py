"""Shared gate verdict helpers (ACCEPT / REFUSE / INCONCLUSIVE)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_verdict(path: Path, gate: str, fixture: str, verdict: str, reason: str, evidence: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "gate": gate,
        "fixture": fixture,
        "verdict": verdict,
        "reason": reason,
        "evidence": evidence,
    }
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def expect(actual: str, expected: str, gate: str, fixture: str) -> int:
    if actual == expected:
        print(f"PASS {gate}/{fixture}: {actual}")
        return 0
    print(f"FAIL {gate}/{fixture}: got {actual}, want {expected}")
    return 1
