#!/usr/bin/env python3
"""AD-009 §3.1 — auto-stamp (+ optional kanban_block) for untyped silent exits.

Exit codes:
  0 — stamped (and blocked if --block)
  1 — usage / hermes failure
  3 — skipped (no protocol_violation signal and --force not set)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROTOCOL_RE = re.compile(
    r"protocol violation|without calling kanban_complete|without calling kanban_block",
    re.I,
)


def write_stamp(
    root: Path,
    *,
    task_id: str,
    run_id: str,
    detail: str,
    secondary_to: str,
) -> Path:
    out_dir = root / "evidence" / "verdicts"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = {
        "schema": "rhoai3.protocol-untyped-block/v1",
        "ad": "AD-009",
        "block_class": "protocol_untyped",
        "task_id": task_id,
        "run_id": run_id or None,
        "detail": detail,
        "secondary_to": secondary_to or None,
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "minimax_escalate": False,
        "note": (
            "Typed terminal for silent worker exit — not automatic proof of "
            "context overflow; dual-annotate when campaign class differs"
        ),
    }
    path = out_dir / f"protocol-untyped-{task_id}.json"
    path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    return path


def hermes_show(task_id: str) -> str:
    env = os.environ.copy()
    try:
        out = subprocess.check_output(
            ["hermes", "kanban", "show", task_id],
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return str(exc)
    return out


def kanban_block(task_id: str, reason: str) -> int:
    try:
        subprocess.check_call(
            [
                "hermes",
                "kanban",
                "block",
                task_id,
                reason,
            ]
        )
        return 0
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"AD-009: hermes kanban block failed: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/projects/modernized")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--run-id", default="")
    ap.add_argument("--detail", default="")
    ap.add_argument(
        "--secondary-to",
        default="",
        help="Campaign class if this is residual (e.g. environmental_provider)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Stamp even when hermes show lacks protocol_violation text",
    )
    ap.add_argument(
        "--block",
        action="store_true",
        help="Also invoke hermes kanban block after stamp",
    )
    ap.add_argument(
        "--show-text",
        default="",
        help="Optional pre-captured hermes kanban show text (tests / offline)",
    )
    args = ap.parse_args()
    root = Path(args.root)
    show = args.show_text or hermes_show(args.task_id)
    matched = bool(PROTOCOL_RE.search(show))
    if not matched and not args.force:
        print(
            "AD-009: no protocol_violation signal — skip "
            "(pass --force to stamp anyway)",
            file=sys.stderr,
        )
        return 3
    detail = args.detail or (
        "worker exited rc=0 without kanban_complete or kanban_block"
        if matched
        else "forced protocol_untyped stamp"
    )
    path = write_stamp(
        root,
        task_id=args.task_id,
        run_id=args.run_id,
        detail=detail,
        secondary_to=args.secondary_to,
    )
    print(f"AD-009: stamped {path}")
    if args.block:
        reason = (
            f"AD-009 block_class=protocol_untyped stamp={path.name}"
            + (f" secondary_to={args.secondary_to}" if args.secondary_to else "")
        )
        return kanban_block(args.task_id, reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
