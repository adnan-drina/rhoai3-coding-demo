#!/usr/bin/env python3
"""Fast-deny detector for non-retryable vLLM / context validation 400s.

Deputy E-20260810T163600Z: sleep-retrying the same over-limit prompt burns the
wall. Exit 2 ⇒ stamp context_budget (trigger vllm_validation_error).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PATTERNS = (
    re.compile(r"VLLMValidationError", re.I),
    re.compile(r"maximum context length is \d+", re.I),
    re.compile(r"requested \d+ output tokens and your prompt contains", re.I),
    re.compile(r"Range of max_tokens should be", re.I),
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--stamp", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--max-model-len", type=int, default=131072)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    agent = root / ".hermes/home/logs/agent.log"
    task_log = root / ".hermes/home/kanban/logs" / f"{args.task_id}.log"
    blobs: list[str] = []
    for p in (agent, task_log):
        if p.is_file():
            blobs.append(p.read_text(encoding="utf-8", errors="replace")[-12000:])
    text = "\n".join(blobs)
    if not text.strip():
        print(f"SKIP: no logs for {args.task_id}")
        return 0
    hit = next((p.pattern for p in PATTERNS if p.search(text)), None)
    if not hit:
        print(f"OK: no vLLM validation 400 signal for {args.task_id}")
        return 0
    # Best-effort prompt size from error text
    m = re.search(
        r"prompt contains at least (\d+) input tokens",
        text,
        re.I,
    )
    prompt_tokens = int(m.group(1)) if m else args.max_model_len - args.max_tokens + 1
    print(
        f"FAIL: fast-deny — non-retryable validation signal ({hit}) "
        f"task={args.task_id} prompt_tokens≈{prompt_tokens}",
        file=sys.stderr,
    )
    if args.stamp:
        stamp = Path(__file__).resolve().parent / "stamp-context-budget-block.py"
        subprocess.run(
            [
                sys.executable,
                str(stamp),
                "--root",
                str(root),
                "--task-id",
                args.task_id,
                "--prompt-tokens",
                str(prompt_tokens),
                "--max-tokens",
                str(args.max_tokens),
                "--max-model-len",
                str(args.max_model_len),
                "--trigger",
                "vllm_validation_error",
            ],
            check=False,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
