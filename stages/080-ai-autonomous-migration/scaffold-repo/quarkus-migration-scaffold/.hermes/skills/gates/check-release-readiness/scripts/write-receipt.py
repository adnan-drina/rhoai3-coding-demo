#!/usr/bin/env python3
"""Write a typed M4-floor gate receipt (rhoai3.gate-receipt/v1)."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="receipt JSON path")
    ap.add_argument("--check", required=True, help="check id e.g. boot_health")
    ap.add_argument("--result", required=True, choices=("PASS", "FAIL", "REFUSE", "INCONCLUSIVE"))
    ap.add_argument("--cmd", default="", help="command string executed")
    ap.add_argument("--rc", type=int, default=0)
    ap.add_argument("--operand", default="", help="path or URL operand")
    ap.add_argument("--note", default="")
    # B8 / check-semantics-manifest — typed fields for adequacy lints
    ap.add_argument("--package-rc", default=None, help="boot_health: mvn package rc (forbid skipped)")
    ap.add_argument("--health-status", default=None, help="boot_health: health probe status")
    ap.add_argument(
        "--smoke-paths",
        default=None,
        help="endpoint_smoke*: space-separated smoke URL paths",
    )
    ap.add_argument("--claim", default=None, help="coverage claim text (narrowed smoke)")
    ap.add_argument("--g4-mode", default=None, help="g4_hook: SAMPLE|PRODUCT")
    ap.add_argument("--adequacy", default=None, help="SEMANTIC|ADMISSION|TOOLING")
    ap.add_argument("--tests-required", default=None, help="unit_it_contract: true when AR-2.8 on")
    ap.add_argument("--test-count", type=int, default=None)
    ap.add_argument("--plugin-absent", default=None, help="sonar SKIP: true when plugin missing")
    args = ap.parse_args()

    operand = args.operand
    digest = hashlib.sha256(operand.encode("utf-8")).hexdigest() if operand else ""
    receipt = {
        "schema": "rhoai3.gate-receipt/v1",
        "check": args.check,
        "result": args.result,
        "cmd": args.cmd,
        "rc": args.rc,
        "operand": operand,
        "operand_digest": digest,
        "note": args.note,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "floor": "m4-minimum",
        "ad010_demo": False,
        # Contract citation — inbound ref for B8 check-semantics-manifest
        "contract": ".hermes/skills/gates/check-release-readiness/references/check-semantics-manifest.md",
    }
    if args.package_rc is not None:
        receipt["package_rc"] = args.package_rc
    if args.health_status is not None:
        receipt["health_status"] = args.health_status
    if args.smoke_paths is not None:
        receipt["smoke_paths"] = [p for p in args.smoke_paths.split() if p]
    if args.claim is not None:
        receipt["claim"] = args.claim
    if args.g4_mode is not None:
        receipt["g4_mode"] = args.g4_mode
    if args.adequacy is not None:
        receipt["adequacy"] = args.adequacy
    if args.tests_required is not None:
        receipt["tests_required"] = args.tests_required
    if args.test_count is not None:
        receipt["test_count"] = args.test_count
    if args.plugin_absent is not None:
        receipt["plugin_absent"] = args.plugin_absent in ("1", "true", "yes", "True")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} result={args.result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
