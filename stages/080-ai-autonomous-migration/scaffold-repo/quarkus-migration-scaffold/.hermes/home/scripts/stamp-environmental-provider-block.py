#!/usr/bin/env python3
"""AD-009: write typed environmental_provider BLOCK stamp under evidence/verdicts/."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/projects/modernized")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--provider-stale-events", type=int, required=True)
    ap.add_argument(
        "--prior-run-ids",
        default="",
        help="Comma-separated prior run ids",
    )
    args = ap.parse_args()
    root = Path(args.root)
    out_dir = root / "evidence" / "verdicts"
    out_dir.mkdir(parents=True, exist_ok=True)
    prior = [p.strip() for p in args.prior_run_ids.split(",") if p.strip()]
    stamp = {
        "schema": "rhoai3.environmental-provider-block/v1",
        "ad": "AD-009",
        "block_class": "environmental_provider",
        "task_id": args.task_id,
        "model_id": args.model_id,
        "provider_stale_events": args.provider_stale_events,
        "prior_run_ids": prior,
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "minimax_escalate": False,
        "note": "Environmental terminal — successful measurement if circuit-breaker applies",
    }
    path = out_dir / f"environmental-provider-{args.task_id}.json"
    path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"AD-009 stamp wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
