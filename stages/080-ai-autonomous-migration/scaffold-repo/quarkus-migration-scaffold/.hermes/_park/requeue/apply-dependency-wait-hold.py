#!/usr/bin/env python3
"""R-M3.6 — hold dependency_wait; do not soft-promote without upstream fix.

Architect E-20260810T172800Z. R-M3.5/7 persistence BOM handoff retired (DD4);
dependency_wait remains for other producers (dest-inventory, JDBC preflight).
See governance/retired/pom-persistence-handoff.md for history.

On typed dependency_wait: stamp verdict + optional hard block. Names actor Need
`steward:fix-upstream-pom` (peer of AD-010 §3d). Never MiniMax.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def write_stamp(root: Path, *, task_id: str, note: str) -> Path:
    out_dir = root / "evidence" / "verdicts"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = {
        "schema": "rhoai3.dependency-wait-hold/v1",
        "ad": "AD-010",
        "block_class": "dependency_wait",
        "task_id": task_id,
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "auto_promote": False,
        "minimax_escalate": False,
        "needs": f"steward:fix-upstream-pom({task_id})",
        "note": note
        or (
            "dependency_wait hold — no auto-promote until steward/Operator fixes "
            "upstream pom or body gains typed pom write (R-M3.6 / "
            "Architect E-20260810T172800Z)"
        ),
    }
    path = out_dir / f"dependency-wait-hold-{task_id}.json"
    path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    return path


def kanban_block(task_id: str, reason: str) -> None:
    subprocess.check_call(
        [
            "hermes",
            "kanban",
            "block",
            task_id,
            reason,
        ]
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--note", default="")
    ap.add_argument(
        "--stamp",
        action="store_true",
        help="write evidence/verdicts/dependency-wait-hold-<task>.json",
    )
    ap.add_argument(
        "--block",
        action="store_true",
        help="hermes kanban block (hard hold; no soft promote)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print plan only; skip stamp write and kanban block",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    reason = (
        "R-M3.6 dependency_wait hold — Needs: steward:fix-upstream-pom; "
        "do not auto-promote (Architect E-20260810T172800Z)"
    )
    print(
        f"dependency-wait-hold: task={args.task_id} "
        f"Needs: steward:fix-upstream-pom({args.task_id})"
    )
    if args.stamp:
        stamp_path = root / "evidence" / "verdicts" / f"dependency-wait-hold-{args.task_id}.json"
        if args.dry_run:
            print(f"DRY-RUN: would stamp {stamp_path} (skipped write)")
        else:
            path = write_stamp(root, task_id=args.task_id, note=args.note)
            print(f"stamped {path}")
    if args.block:
        if args.dry_run:
            print(f"DRY-RUN: would kanban block {args.task_id} reason={reason!r}")
        else:
            kanban_block(args.task_id, reason)
            print(f"blocked {args.task_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
