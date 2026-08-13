#!/usr/bin/env python3
"""AD-009 §3.1 — stamp block_class=protocol_untyped under evidence/verdicts/.

Use when a worker exits rc=0 without kanban_complete/kanban_block so the board
does not leave silence as an untyped protocol_violation narrative.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/projects/modernized")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--run-id", default="")
    ap.add_argument(
        "--detail",
        default="worker exited rc=0 without kanban_complete or kanban_block",
    )
    ap.add_argument(
        "--secondary-to",
        default="",
        help="Optional campaign class this is secondary to (e.g. environmental_provider)",
    )
    args = ap.parse_args()
    root = Path(args.root)
    out_dir = root / "evidence" / "verdicts"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = {
        "schema": "rhoai3.protocol-untyped-block/v1",
        "ad": "AD-009",
        "block_class": "protocol_untyped",
        "task_id": args.task_id,
        "run_id": args.run_id or None,
        "detail": args.detail,
        "secondary_to": args.secondary_to or None,
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "minimax_escalate": False,
        "note": (
            "Typed terminal for silent worker exit — not automatic proof of "
            "context overflow; dual-annotate when campaign class differs"
        ),
    }
    path = out_dir / f"protocol-untyped-{args.task_id}.json"
    path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"AD-009 protocol_untyped stamp wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
