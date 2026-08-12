#!/usr/bin/env python3
"""Consumer for M4 floor receipts — refuse missing/contradictory set."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED = ("boot_health", "endpoint_smoke", "g4_hook")
OK = {"PASS", "INCONCLUSIVE"}  # INCONCLUSIVE honest for g4 SAMPLE floor


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "rhoai3.gate-receipt/v1":
        raise ValueError(f"{path}: bad schema")
    return data


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    # accept either a receipts dir or a product root with migration/receipts/m4-floor
    candidates = [
        root,
        root / "migration/receipts/m4-floor",
        root / "receipts",
    ]
    receipts_dir = next((c for c in candidates if c.is_dir() and any(c.glob("*.json"))), None)
    if receipts_dir is None:
        print(f"FAIL: no receipts under {root}", file=sys.stderr)
        return 1

    by_check: dict[str, dict] = {}
    for path in sorted(receipts_dir.glob("*.json")):
        try:
            data = load(path)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        by_check[data["check"]] = data

    bad = 0
    for name in REQUIRED:
        if name not in by_check:
            print(f"FAIL: missing receipt for {name}", file=sys.stderr)
            bad = 1
            continue
        result = by_check[name].get("result")
        if name == "g4_hook":
            if result not in OK | {"REFUSE"}:
                print(f"FAIL: g4_hook bad result {result}", file=sys.stderr)
                bad = 1
            # REFUSE is conclusive fail for floor consumer of Phase-3 gate
            if result == "REFUSE":
                print(f"FAIL: g4_hook REFUSE", file=sys.stderr)
                bad = 1
        elif result != "PASS":
            print(f"FAIL: {name} result={result} (need PASS)", file=sys.stderr)
            bad = 1
        else:
            print(f"OK: {name}={result}")

    if bad:
        return 1
    print(f"OK: M4 floor receipts complete under {receipts_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
