#!/usr/bin/env python3
"""Architect E-121300Z — wall requeue policy: exit-eval + soft K ceiling.

Soft interval (requeue) OR hard ceiling after K timed_out outcomes.
Unbounded silent requeue REJECT. Call on every timed_out / before resume.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_K = 1  # soft requeues allowed; next wall → hard terminal expectation


def count_timed_out(task_id: str) -> int:
    cp = subprocess.run(
        ["hermes", "kanban", "show", task_id, "--json"],
        text=True,
        capture_output=True,
    )
    if cp.returncode != 0 or not (cp.stdout or "").strip():
        # Fallback: parse text show
        cp2 = subprocess.run(
            ["hermes", "kanban", "show", task_id],
            text=True,
            capture_output=True,
        )
        text = cp2.stdout or ""
        return text.count("timed_out")
    try:
        data = json.loads(cp.stdout)
    except Exception:
        return (cp.stdout or "").count("timed_out")
    runs = data.get("runs") or data.get("task_runs") or []
    if isinstance(runs, list):
        n = 0
        for r in runs:
            if isinstance(r, dict):
                st = str(r.get("status") or r.get("outcome") or "").lower()
                if st == "timed_out":
                    n += 1
            elif "timed_out" in str(r).lower():
                n += 1
        return n
    return str(data).count("timed_out")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--k-soft", type=int, default=DEFAULT_K)
    ap.add_argument(
        "--skip-eval",
        action="store_true",
        help="Only check K / artifact presence (eval already ran)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print plan only; skip eval/sync subprocess side effects",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    scripts = root / ".hermes/skills/gates/check-release-readiness/scripts"
    n = count_timed_out(args.task_id)
    print(f"wall-policy: timed_out_count={n} k_soft={args.k_soft}")

    if args.dry_run:
        print(
            f"DRY-RUN: skip eval/sync side effects for task={args.task_id} "
            f"skip_eval={args.skip_eval}"
        )
        if n > args.k_soft:
            print(
                f"DRY-RUN: would FAIL HARD CEILING (timed_out_count={n} > k_soft={args.k_soft})"
            )
            return 2
        if n == args.k_soft:
            print(
                f"DRY-RUN: soft requeue budget exhausted (n={n}=k); "
                f"next timed_out would hard-block"
            )
            return 0
        print(f"DRY-RUN: soft requeue still available (n={n} < k={args.k_soft})")
        return 0

    if not args.skip_eval:
        eval_py = scripts / "evaluate-exit-criteria.py"
        cp = subprocess.run(
            [
                sys.executable,
                str(eval_py),
                str(root),
                "--body",
                args.body,
                "--task-id",
                args.task_id,
                "--trigger",
                "timed_out",
            ],
            text=True,
        )
        # eval may return 1 when cmd checks fail — still produced artifact
        check_py = scripts / "check-wall-exit-eval.py"
        cp2 = subprocess.run(
            [
                sys.executable,
                str(check_py),
                str(root),
                "--task-id",
                args.task_id,
                "--trigger",
                "timed_out",
                "--require-test-compile",
            ],
            text=True,
        )
        if cp2.returncode != 0:
            print("FAIL: wall-exit-eval missing/invalid after timed_out", file=sys.stderr)
            return 1
    else:
        check_py = scripts / "check-wall-exit-eval.py"
        cp2 = subprocess.run(
            [
                sys.executable,
                str(check_py),
                str(root),
                "--task-id",
                args.task_id,
                "--trigger",
                "timed_out",
                "--require-test-compile",
            ],
            text=True,
        )
        if cp2.returncode != 0:
            print("FAIL: wall-exit-eval required before soft resume", file=sys.stderr)
            return 1

    # Lag sync obligation (harness-driven stamp catch-up)
    ck = root / "evidence" / "runs" / args.task_id / "checkpoint.json"
    if ck.is_file():
        sync = (
            root
            / ".hermes/skills/harness/record-run-evidence/scripts/sync-checkpoint-from-test-writes.py"
        )
        subprocess.run(
            [sys.executable, str(sync), str(ck), "--root", str(root)],
            text=True,
        )

    if n > args.k_soft:
        print(
            f"FAIL: HARD CEILING — timed_out_count={n} > k_soft={args.k_soft}. "
            f"Block task (do not soft-requeue). Architect E-121300Z.",
            file=sys.stderr,
        )
        return 2
    if n == args.k_soft:
        print(
            f"OK: soft requeue budget exhausted (n={n}=k). "
            f"NEXT timed_out must hard-block + exit-eval (no further soft resume)."
        )
        return 0
    print(f"OK: soft requeue still available (n={n} < k={args.k_soft})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
