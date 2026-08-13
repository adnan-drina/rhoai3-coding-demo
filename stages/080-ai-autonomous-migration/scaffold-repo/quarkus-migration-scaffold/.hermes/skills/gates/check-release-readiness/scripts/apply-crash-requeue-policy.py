#!/usr/bin/env python3
"""Architect E-20260810T142650Z — crash requeue ceiling (K_crash).

Wall soft-K bounds timed_out only. Crash/reclaim loops must not be unbounded
while wall policy reports green. Default K_crash=1 (proving-min, peer of wall).

After the ceiling: typed terminal primary harness_fault / environmental_provider /
context_budget per --cause — never budget/timed_out as primary, never wall-fit
evidence. Does not spend wall soft-K. Does not MiniMax.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_K_CRASH = 1
ALLOWED_CAUSES = (
    "harness_fault",
    "environmental_provider",
    "context_budget",
)


def count_crashed(task_id: str) -> int:
    cp = subprocess.run(
        ["hermes", "kanban", "show", task_id, "--json"],
        text=True,
        capture_output=True,
    )
    if cp.returncode != 0 or not (cp.stdout or "").strip():
        cp2 = subprocess.run(
            ["hermes", "kanban", "show", task_id],
            text=True,
            capture_output=True,
        )
        text = (cp2.stdout or "").lower()
        return text.count("crashed")
    try:
        data = json.loads(cp.stdout)
    except Exception:
        return (cp.stdout or "").lower().count("crashed")
    runs = data.get("runs") or data.get("task_runs") or []
    if isinstance(runs, list):
        n = 0
        for r in runs:
            if isinstance(r, dict):
                st = str(r.get("status") or r.get("outcome") or "").lower()
                if st in {"crashed", "crash", "gave_up", "kill"}:
                    # gave_up/kill after provider death count as crash-class for ceiling
                    if st == "crashed" or st == "crash":
                        n += 1
                    elif st in {"gave_up", "kill"} and "timeout" not in str(r).lower():
                        n += 1
            elif "crashed" in str(r).lower():
                n += 1
        return n
    return str(data).lower().count("crashed")


def write_stamp(
    root: Path,
    *,
    task_id: str,
    cause: str,
    crash_count: int,
    k_crash: int,
    note: str,
) -> Path:
    out_dir = root / "evidence" / "verdicts"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = {
        "schema": "rhoai3.crash-requeue-block/v1",
        "ad": "AD-010",
        "block_class": cause,
        "task_id": task_id,
        "crash_count": crash_count,
        "k_crash": k_crash,
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "minimax_escalate": False,
        "spends_wall_soft_k": False,
        "note": note
        or (
            "Crash-requeue ceiling — typed terminal; not budget/timed_out; "
            "not wall-fit evidence (Architect E-20260810T142650Z)"
        ),
    }
    path = out_dir / f"crash-requeue-{cause}-{task_id}.json"
    path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task-id", required=True)
    ap.add_argument(
        "--k-crash",
        type=int,
        default=DEFAULT_K_CRASH,
        help="soft crash requeues allowed before hard ceiling (default 1)",
    )
    ap.add_argument(
        "--cause",
        choices=ALLOWED_CAUSES,
        default="harness_fault",
        help="typed primary class when ceiling trips",
    )
    ap.add_argument(
        "--note",
        default="",
        help="optional stamp note (e.g. max_tokens overflow)",
    )
    ap.add_argument(
        "--stamp",
        action="store_true",
        help="write verdict stamp when hard ceiling trips (default: print only)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print plan only; skip --stamp write",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()

    # A2 / workspace-recovery — F4 restore-or-refuse before soft reclaim / requeue
    restore_py = Path(__file__).resolve().parent / "restore-or-refuse-requeue.py"
    if not restore_py.is_file():
        print(f"FAIL: missing {restore_py.name}", file=sys.stderr)
        return 2
    f4 = subprocess.run(
        [
            sys.executable,
            str(restore_py),
            str(root),
            "--terminal",
            "crashed",
            "--action",
            "check",
        ],
        text=True,
        capture_output=True,
    )
    sys.stdout.write(f4.stdout or "")
    sys.stderr.write(f4.stderr or "")
    if f4.returncode != 0:
        print(
            f"FAIL: refuse crash reclaim — F4 restore-or-refuse rc={f4.returncode} "
            f"(governance/contracts/workspace-recovery.md)",
            file=sys.stderr,
        )
        return 1 if f4.returncode == 1 else f4.returncode

    n = count_crashed(args.task_id)
    print(f"crash-policy: crashed_count={n} k_crash={args.k_crash} cause={args.cause}")

    if n > args.k_crash:
        msg = (
            f"FAIL: HARD CRASH CEILING — crashed_count={n} > k_crash={args.k_crash}. "
            f"Block task (do not soft-requeue). Typed primary={args.cause} "
            f"(never budget/timed_out). Architect E-20260810T142650Z."
        )
        print(msg, file=sys.stderr)
        if args.stamp:
            stamp_path = (
                root / "evidence" / "verdicts" / f"crash-requeue-{args.cause}-{args.task_id}.json"
            )
            if args.dry_run:
                print(f"DRY-RUN: would stamp {stamp_path} (skipped write)")
            else:
                path = write_stamp(
                    root,
                    task_id=args.task_id,
                    cause=args.cause,
                    crash_count=n,
                    k_crash=args.k_crash,
                    note=args.note,
                )
                print(f"stamped {path}")
        return 2
    if n == args.k_crash:
        print(
            f"OK: soft crash reclaim budget exhausted (n={n}=k). "
            f"NEXT crashed must hard-block + typed {args.cause} stamp "
            f"(no further silent reclaim)."
        )
        return 0
    print(f"OK: soft crash reclaim still available (n={n} < k={args.k_crash})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
