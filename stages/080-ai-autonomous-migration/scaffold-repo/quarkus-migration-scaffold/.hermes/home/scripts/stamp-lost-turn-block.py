#!/usr/bin/env python3
"""Architect E-20260810T144150Z — stamp harness_fault/lost_turn under migration/verdicts/."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="/projects/modernized")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--run-id", default="")
    ap.add_argument("--transcript-bytes", type=int, default=0)
    ap.add_argument("--transcript-frozen-sec", type=int, default=0)
    ap.add_argument("--last-api-call", default="")
    ap.add_argument("--last-tool", default="")
    ap.add_argument("--provider-signal", default="")
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    root = Path(args.root)
    out_dir = root / "migration" / "verdicts"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = {
        "schema": "rhoai3.lost-turn-block/v1",
        "ad": "AD-010",
        "block_class": "harness_fault",
        "fault_subtype": "lost_turn",
        "task_id": args.task_id,
        "run_id": args.run_id or None,
        "transcript_bytes": args.transcript_bytes,
        "transcript_frozen_sec": args.transcript_frozen_sec,
        "last_api_call": args.last_api_call or None,
        "last_tool": args.last_tool or None,
        "provider_signal": args.provider_signal or None,
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "minimax_escalate": False,
        "spends_wall_soft_k": False,
        "note": args.note
        or (
            "Lost turn — provider idle/stale with no durable transcript/artifact; "
            "not budget/timed_out primary (Architect E-20260810T144150Z)"
        ),
    }
    path = out_dir / f"lost-turn-{args.task_id}.json"
    path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"OK: stamped {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
