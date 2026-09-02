#!/usr/bin/env python3
"""Import helper: gate scripts emit evidence/receipts/gates/<gate>.json."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_WR = _HERE / "write-gate-receipt.py"
_spec = importlib.util.spec_from_file_location("write_gate_receipt", _WR)
if _spec is None or _spec.loader is None:
    raise SystemExit("FAIL: write-gate-receipt.py missing")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
emit_script_receipt = _mod.emit_script_receipt  # noqa: F401
is_runner_receipt = _mod.is_runner_receipt  # noqa: F401
RECEIPT_DIR = _mod.RECEIPT_DIR


def load_from(script_file: str):
    """Load this helper from a gate script via a known relative path."""
    path = Path(script_file).resolve()
    for rel in (
        Path("assert-pinned-gates-ran") / "scripts" / "script_gate_receipt.py",
        Path("gates") / "assert-pinned-gates-ran" / "scripts" / "script_gate_receipt.py",
    ):
        for parent in path.parents:
            hit = parent / rel
            if hit.is_file():
                spec = importlib.util.spec_from_file_location("script_gate_receipt", hit)
                if spec is None or spec.loader is None:
                    continue
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
    print("FAIL: script_gate_receipt.py not found from %s" % script_file, file=sys.stderr)
    raise SystemExit(2)
