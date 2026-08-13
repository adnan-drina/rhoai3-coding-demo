#!/usr/bin/env python3
"""RW-1 CONV-LIVE stream-layer classifier (Architect E-20260812T074514Z).

After BANK-CONV-LIVE-WD-1 fires, classify whether the stall looks like:
  - client_unconsumed: provider likely still ACTIVE / tokens flowing elsewhere
  - provider_idle: no provider progress during silence (send/close path)
  - unknown: cannot probe

Does NOT mutate the board. Emits a JSON receipt under
evidence/receipts/conv-live-classify/ for Lead reclaim + bounded-retry policy
(`governance/contracts/conv-live-bounded-retry.md`).

Usage:
  classify-conv-live-stall.py <root> --task-id t_xxx [--stamp]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _probe_vllm_busy() -> str | None:
    """Best-effort: return 'active'|'idle'|None if a local probe exists."""
    # Prefer seat helper if present; never invent provider calls that need secrets.
    for cmd in (
        ["curl", "-sf", "--max-time", "2", "http://127.0.0.1:8000/metrics"],
        ["true"],
    ):
        if cmd[0] == "true":
            return None
        try:
            cp = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if cp.returncode != 0:
                continue
            text = cp.stdout or ""
            # Heuristic: any non-empty metrics scrape ⇒ probe reachable; idle/active
            # left unknown without model-specific counters.
            if text.strip():
                return "unknown_metrics_reachable"
        except Exception:
            continue
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--stamp", action="store_true")
    ap.add_argument("--flat-sec", type=int, default=240)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    home = root / ".hermes" / "home"
    detector = home / "scripts" / "check-conversation-liveness.py"
    if not detector.is_file():
        print(f"FAIL: CONV_LIVE_CLASSIFY missing {detector}", file=sys.stderr)
        return 1
    cp = subprocess.run(
        [
            sys.executable,
            str(detector),
            str(root),
            "--task-id",
            args.task_id,
            "--flat-sec",
            str(args.flat_sec),
        ],
        capture_output=True,
        text=True,
    )
    msg = (cp.stderr or cp.stdout or "").strip()
    probe = _probe_vllm_busy()
    if cp.returncode == 0:
        klass = "not_stalled"
        action = "none"
    elif probe is None:
        klass = "unknown"
        action = "bounded_retry_once_then_reclaim"
    elif "idle" in probe:
        klass = "provider_idle"
        action = "fix_send_close_path"
    elif "active" in probe:
        klass = "client_unconsumed"
        action = "bounded_stream_read_timeout_plus_one_resume"
    else:
        klass = "unknown"
        action = "bounded_retry_once_then_reclaim"

    receipt = {
        "schema": "rhoai3.conv-live-classify/v1",
        "task_id": args.task_id,
        "detector_rc": cp.returncode,
        "detector_msg": msg.splitlines()[0] if msg else "",
        "class": klass,
        "provider_probe": probe,
        "recommended_action": action,
        "bounded_retry_budget": 1,
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Alert/classify only — Lead reclaim owns board mutate",
    }
    print(f"CONV_LIVE_CLASSIFY class={klass} action={action} probe={probe}")
    if args.stamp:
        outdir = root / "evidence" / "receipts" / "conv-live-classify"
        outdir.mkdir(parents=True, exist_ok=True)
        path = outdir / f"{args.task_id}-{int(time.time())}.json"
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(f"WROTE {path}")
    return 0 if cp.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
