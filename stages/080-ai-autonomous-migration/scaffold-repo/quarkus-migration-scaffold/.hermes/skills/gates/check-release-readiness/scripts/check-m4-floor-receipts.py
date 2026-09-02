#!/usr/bin/env python3
"""Consumer for M4 floor receipts — refuse missing/contradictory set."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REQUIRED_CORE = ("boot_health", "g4_hook")
# B8: health/root-only smoke may use endpoint_smoke_health
SMOKE_ALIASES = ("endpoint_smoke", "endpoint_smoke_health")
OK = {"PASS", "INCONCLUSIVE"}  # INCONCLUSIVE honest for g4 SAMPLE floor


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "rhoai3.gate-receipt/v1":
        raise ValueError(f"{path}: bad schema")
    return data


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    # accept either a receipts dir or a product root with evidence/receipts/m4-floor
    candidates = [
        root,
        root / "evidence/receipts/m4-floor",
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
    for name in REQUIRED_CORE:
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

    smoke_name = next((n for n in SMOKE_ALIASES if n in by_check), None)
    if smoke_name is None:
        print(
            "FAIL: missing receipt for endpoint_smoke or endpoint_smoke_health "
            "(B8 / .hermes/skills/gates/check-release-readiness/references/check-semantics-manifest.md)",
            file=sys.stderr,
        )
        bad = 1
    else:
        result = by_check[smoke_name].get("result")
        if result != "PASS":
            print(f"FAIL: {smoke_name} result={result} (need PASS)", file=sys.stderr)
            bad = 1
        else:
            print(f"OK: {smoke_name}={result}")

    # B8 semantics lint on the same receipt set
    lint = Path(__file__).resolve().parent / "check-semantics-manifest.py"
    proc = subprocess.run(
        [sys.executable, str(lint), str(receipts_dir)],
        text=True,
        capture_output=True,
    )
    sys.stdout.write(proc.stdout or "")
    sys.stderr.write(proc.stderr or "")
    if proc.returncode != 0:
        bad = 1

    if bad:
        return 1
    print(f"OK: M4 floor receipts complete under {receipts_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
