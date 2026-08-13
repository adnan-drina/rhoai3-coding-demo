#!/usr/bin/env python3
"""AD-002 §1 / AD-009 §3.5 — pre-flight refuse when prompt+max_out > max-model-len.

Exit codes:
  0  OK to emit (or dry meta)
  2  REFUSE emit — would overflow served ceiling
  1  usage / I/O error

Optional --stamp writes block_class=context_budget via stamp-context-budget-block.py.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Refuse emit when prompt_tokens + max_tokens > max-model-len"
    )
    ap.add_argument("--prompt-tokens", type=int, required=True)
    ap.add_argument("--max-tokens", type=int, required=True, help="Requested output tokens")
    ap.add_argument("--max-model-len", type=int, default=131072)
    ap.add_argument("--task-id", default="")
    ap.add_argument("--model-id", default="qwen3-6-27b")
    ap.add_argument(
        "--stamp",
        action="store_true",
        help="On refuse, write evidence/verdicts/context-budget-<task>.json",
    )
    ap.add_argument("--root", default=".")
    ap.add_argument("--json-out", default="", help="Optional path for machine result JSON")
    args = ap.parse_args()

    total = args.prompt_tokens + args.max_tokens
    overflow = total - args.max_model_len
    ok = total <= args.max_model_len
    result = {
        "schema": "rhoai3.preflight-ceiling-check/v1",
        "ad": "AD-002§1/AD-009§3.5",
        "prompt_tokens": args.prompt_tokens,
        "max_tokens": args.max_tokens,
        "max_model_len": args.max_model_len,
        "total": total,
        "overflow_by": 0 if ok else overflow,
        "verdict": "OK" if ok else "REFUSE",
        "block_class": None if ok else "context_budget",
        "harness_ceiling_guard": True,
        "note": (
            "OK to emit"
            if ok
            else "Harness must refuse emit — do not discover via VLLMValidationError"
        ),
    }
    line = (
        f"preflight-ceiling: {result['verdict']} "
        f"prompt={args.prompt_tokens} max_out={args.max_tokens} "
        f"total={total} ceiling={args.max_model_len}"
        + (f" overflow_by={overflow}" if not ok else "")
    )
    print(line)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    if ok:
        return 0

    if args.stamp:
        if not args.task_id:
            print("ERROR: --stamp requires --task-id", file=sys.stderr)
            return 1
        stamp = Path(__file__).resolve().parent / "stamp-context-budget-block.py"
        rc = subprocess.call(
            [
                sys.executable,
                str(stamp),
                "--root",
                args.root,
                "--task-id",
                args.task_id,
                "--model-id",
                args.model_id,
                "--prompt-tokens",
                str(args.prompt_tokens),
                "--max-tokens",
                str(args.max_tokens),
                "--max-model-len",
                str(args.max_model_len),
                "--trigger",
                "preflight_ceiling_guard",
            ]
        )
        if rc != 0:
            return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
