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
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} result={args.result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
