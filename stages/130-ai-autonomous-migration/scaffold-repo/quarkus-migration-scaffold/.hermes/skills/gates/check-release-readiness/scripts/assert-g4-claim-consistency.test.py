#!/usr/bin/env python3
"""Negative control: dest-4 N/A vs INCONCLUSIVE must fail. Not dest."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "g4c", HERE / "assert-g4-claim-consistency.py"
)
assert _SPEC and _SPEC.loader
g4c = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(g4c)


def _write(root: Path, rel: str, obj: object) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def _fail(msg: str) -> int:
    print("FAIL: %s" % msg, file=sys.stderr)
    return 1


def main_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        empty = Path(tmp) / "empty"
        empty.mkdir()
        if g4c.check_root(empty) != []:
            return _fail("idle empty tree must have no issues")
        if g4c.main([str(empty)]) != 0:
            return _fail("idle empty tree must exit 0")

        split = Path(tmp) / "split"
        _write(
            split,
            "evidence/verdicts/refusals/check-domain-parity.json",
            {
                "ran": False,
                "reason": (
                    "runtime parity (G-4) is N/A for this scope; "
                    "M5 ACCEPT would require G-4"
                ),
            },
        )
        _write(
            split,
            "evidence/verdicts/check-release-readiness.json",
            {
                "verdict": "PROVISIONAL_ACCEPT",
                "ship": False,
                "reason": "g4_hook=INCONCLUSIVE (honest for SAMPLE floor)",
            },
        )
        if not g4c.check_root(split):
            return _fail("dest-4-shaped split must refuse")
        if g4c.main([str(split)]) != 1:
            return _fail("dest-4-shaped split must exit 1")

        greeting = Path(tmp) / "greeting"
        _write(
            greeting,
            "evidence/verdicts/refusals/check-domain-parity.json",
            {
                "ran": False,
                "reason": "Single stateless HTTP endpoint (GET /greeting); G-4 N/A",
            },
        )
        if not g4c.check_root(greeting):
            return _fail("GET /greeting G-4 N/A must refuse")

        ok = Path(tmp) / "ok"
        _write(
            ok,
            "evidence/verdicts/refusals/check-domain-parity.json",
            {"ran": False, "reason": "specimen-n/a: no DB"},
        )
        _write(
            ok,
            "evidence/verdicts/check-release-readiness.json",
            {
                "verdict": "PROVISIONAL_ACCEPT",
                "ship": False,
                "reason": "g4_hook=INCONCLUSIVE",
            },
        )
        leftover = g4c.check_root(ok)
        if leftover:
            return _fail("G-1/2/3 n/a plus honest g4_hook INCONCLUSIVE must pass: %s" % leftover)
        if g4c.main([str(ok)]) != 0:
            return _fail("consistent INCONCLUSIVE must exit 0")

    print("OK: G-4 claim consistency (split fails, greeting N/A fails, consistent passes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_test())
