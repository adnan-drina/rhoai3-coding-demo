#!/usr/bin/env python3
"""AD-009 — apply campaign circuit-breaker for provider-stale failures.

If consecutive environmental failures for a task reach phase K, write the typed
`block_class=environmental_provider` stamp (via stamp-environmental-provider-block.py
logic) and exit 2 (= breaker tripped). Exit 0 if under threshold. Exit 1 on usage
errors.

K (AD-009):
  M1 / M2: 1
  M3: 2

Does **not** call MiniMax. Does **not** kanban_block by itself — Lead/Monitor
invoke `hermes kanban block` after stamp when operating the board.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

K_BY_PHASE = {"M1": 1, "M2": 1, "M3": 2}

STALE_PATTERNS = (
    re.compile(r"Broken pipe", re.I),
    re.compile(r"Stream stale", re.I),
    re.compile(r"APITimeoutError", re.I),
    re.compile(r"provider-stale", re.I),
    re.compile(r"ReadError", re.I),
)


def count_stale_from_errors(errors_log: Path) -> int:
    if not errors_log.is_file():
        return 0
    text = errors_log.read_text(encoding="utf-8", errors="replace")
    # Count exhausted-retry / kill events rather than every retry line
    n = 0
    for line in text.splitlines():
        if "API call failed after" in line and any(p.search(line) for p in STALE_PATTERNS):
            n += 1
        elif "Stream stale for" in line and "Killing connection" in line:
            n += 1
    return n


def write_stamp(
    root: Path,
    *,
    task_id: str,
    model_id: str,
    provider_stale_events: int,
    prior_run_ids: list[str],
    phase: str,
) -> Path:
    out_dir = root / "evidence" / "verdicts"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = {
        "schema": "rhoai3.environmental-provider-block/v1",
        "ad": "AD-009",
        "block_class": "environmental_provider",
        "phase": phase,
        "circuit_breaker_k": K_BY_PHASE.get(phase.upper(), 1),
        "task_id": task_id,
        "model_id": model_id,
        "provider_stale_events": provider_stale_events,
        "prior_run_ids": prior_run_ids,
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "minimax_escalate": False,
        "note": (
            "Environmental terminal — successful measurement if circuit-breaker "
            "applies; Review NO-GO on M1/M2 when K reached"
        ),
    }
    path = out_dir / f"environmental-provider-{task_id}.json"
    path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/projects/modernized")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--phase", required=True, choices=sorted(K_BY_PHASE))
    ap.add_argument("--model-id", default="qwen3-6-27b")
    ap.add_argument(
        "--provider-stale-events",
        type=int,
        default=None,
        help="If omitted, count from HERMES_HOME/logs/errors.log heuristics",
    )
    ap.add_argument("--prior-run-ids", default="")
    ap.add_argument(
        "--hermes-home",
        default="",
        help="Default: $HERMES_HOME or <root>/.hermes/home",
    )
    ap.add_argument(
        "--force-stamp",
        action="store_true",
        help="Write stamp even when under K (evidence only)",
    )
    args = ap.parse_args()
    root = Path(args.root)
    phase = args.phase.upper()
    k = K_BY_PHASE[phase]
    prior = [p.strip() for p in args.prior_run_ids.split(",") if p.strip()]

    hermes_home = Path(args.hermes_home) if args.hermes_home else None
    if hermes_home is None:
        import os

        env = os.environ.get("HERMES_HOME", "").strip()
        hermes_home = Path(env) if env else root / ".hermes" / "home"

    count = args.provider_stale_events
    if count is None:
        count = count_stale_from_errors(hermes_home / "logs" / "errors.log")

    print(f"AD-009: phase={phase} K={k} provider_stale_events={count} task={args.task_id}")
    if count >= k or args.force_stamp:
        path = write_stamp(
            root,
            task_id=args.task_id,
            model_id=args.model_id,
            provider_stale_events=count,
            prior_run_ids=prior,
            phase=phase,
        )
        print(f"AD-009: stamped {path}")
        if count >= k:
            print(
                f"AD-009: CIRCUIT BREAKER TRIPPED (count={count} >= K={k}) — "
                f"typed environmental_provider; do not MiniMax; Review NO-GO "
                f"is success for M1/M2",
                file=sys.stderr,
            )
            return 2
        return 0
    print("AD-009: under threshold — no stamp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
