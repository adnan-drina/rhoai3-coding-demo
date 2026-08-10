#!/usr/bin/env python3
"""AD-009 §3.2a — TTFC / lost-stream detector (Architect E-20260810T145240Z).

Hermes uses one stale_timeout for TTFC + inter-chunk. This script enforces the
proving-min TTFC band (default 90s) from transcript + agent.log signals while
inter-chunk remains 900s at the provider.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

DEFAULT_TTFC = 90
STALE_RE = re.compile(
    r"Stream stale for (\d+)s \(threshold (\d+)s\) — no chunks received",
    re.I,
)
NO_CHUNKS_RE = re.compile(r"no chunks yet|no chunks received|waiting for stream", re.I)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--ttfc-sec", type=int, default=DEFAULT_TTFC)
    ap.add_argument(
        "--stamp",
        action="store_true",
        help="on breach, run stamp-lost-turn-block.py",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    log = root / ".hermes/home/kanban/logs" / f"{args.task_id}.log"
    agent = root / ".hermes/home/logs/agent.log"
    now = time.time()
    if not log.is_file():
        print(f"SKIP: missing transcript {log}")
        return 0
    age = now - log.stat().st_mtime
    print(f"liveness: transcript_age_sec={age:.0f} ttfc={args.ttfc_sec}")

    agent_tail = ""
    if agent.is_file():
        agent_tail = agent.read_text(encoding="utf-8", errors="replace")[-8000:]

    zero_chunk_signal = bool(NO_CHUNKS_RE.search(agent_tail) or STALE_RE.search(agent_tail))
    # TTFC breach: transcript frozen beyond band AND (agent waiting with no chunks
    # OR age alone when chat is alive but silent after last tool)
    if age >= args.ttfc_sec and zero_chunk_signal:
        print(
            f"FAIL: TTFC/lost-stream — transcript frozen {age:.0f}s ≥ {args.ttfc_sec}s "
            f"with zero-chunk/stale signal in agent.log (AD-009 §3.2a)",
            file=sys.stderr,
        )
        if args.stamp:
            stamp = root / ".hermes/home/scripts/stamp-lost-turn-block.py"
            import subprocess

            subprocess.run(
                [
                    sys.executable,
                    str(stamp),
                    "--root",
                    str(root),
                    "--task-id",
                    args.task_id,
                    "--transcript-bytes",
                    str(log.stat().st_size),
                    "--transcript-frozen-sec",
                    str(int(age)),
                    "--primary-class",
                    "environmental_provider",
                    "--secondary-class",
                    "lost_turn",
                    "--provider-signal",
                    "ttfc_breach_or_stream_stale_zero_chunks",
                    "--note",
                    f"TTFC band {args.ttfc_sec}s breached; Hermes single stale knob "
                    f"cannot split TTFC from inter-chunk 900s",
                ],
                check=False,
            )
        return 2
    if age >= args.ttfc_sec:
        print(
            f"WARN: transcript frozen {age:.0f}s ≥ {args.ttfc_sec}s but no "
            f"zero-chunk agent signal yet — continue watch"
        )
        return 0
    print("OK: within TTFC band")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
