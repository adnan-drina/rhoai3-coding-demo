#!/usr/bin/env python3
"""AD-009 §3.3/§3.5 — stamp typed context_budget BLOCK under evidence/verdicts/."""
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
    ap.add_argument("--prompt-tokens", type=int, required=True)
    ap.add_argument("--max-tokens", type=int, required=True)
    ap.add_argument("--max-model-len", type=int, default=131072)
    ap.add_argument(
        "--trigger",
        default="preflight_ceiling_guard",
        help="preflight_ceiling_guard | vllm_validation_error | compound_secondary",
    )
    ap.add_argument(
        "--secondary-to",
        default="",
        help="Optional primary campaign class (e.g. environmental_provider)",
    )
    args = ap.parse_args()
    root = Path(args.root)
    out_dir = root / "evidence" / "verdicts"
    out_dir.mkdir(parents=True, exist_ok=True)
    total = args.prompt_tokens + args.max_tokens
    stamp = {
        "schema": "rhoai3.context-budget-block/v1",
        "ad": "AD-009§3.5",
        "block_class": "context_budget",
        "harness_ceiling_guard": True,
        "task_id": args.task_id,
        "model_id": args.model_id,
        "prompt_tokens": args.prompt_tokens,
        "max_tokens": args.max_tokens,
        "max_model_len": args.max_model_len,
        "total": total,
        "overflow_by": max(0, total - args.max_model_len),
        "trigger": args.trigger,
        "secondary_to": args.secondary_to or None,
        "minimax_escalate": False,
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": (
            "Harness context ceiling — refuse emit client-side; "
            "not budget-wall sizing evidence; not MiniMax"
        ),
    }
    path = out_dir / f"context-budget-{args.task_id}.json"
    path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"AD-009 context_budget stamp wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
