#!/usr/bin/env python3
"""Refuse wall terminals that lack rhoai3.exit-eval/v1 (Architect E-110403Z)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA = "rhoai3.exit-eval/v1"
WALLISH = frozenset({"timed_out", "timeout_kill", "gave_up"})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--trigger", required=True)
    ap.add_argument(
        "--require-test-compile",
        action="store_true",
        help="When body has test_compile exit, require it evaluated as cmd",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    trigger = args.trigger.strip().lower()
    path = root / "evidence" / "runs" / args.task_id / "exit-eval.json"
    if trigger not in WALLISH:
        print(f"OK: trigger={trigger} not wallish — exit-eval not required")
        return 0
    if not path.is_file():
        print(
            f"FAIL: wall trigger={trigger} missing {path.relative_to(root)} "
            f"(Architect wall-as-terminal — run evaluate-exit-criteria.py)",
            file=sys.stderr,
        )
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        print(f"FAIL: bad schema {data.get('schema')!r}", file=sys.stderr)
        return 1
    if data.get("task_id") != args.task_id:
        print(
            f"FAIL: exit-eval task_id={data.get('task_id')!r} != {args.task_id!r}",
            file=sys.stderr,
        )
        return 1
    if str(data.get("trigger") or "").lower() not in WALLISH:
        print(
            f"FAIL: exit-eval trigger={data.get('trigger')!r} not wallish",
            file=sys.stderr,
        )
        return 1
    results = data.get("results") or []
    cmd_results = [r for r in results if isinstance(r, dict) and r.get("kind") == "cmd"]
    if not cmd_results:
        print(
            "FAIL: wall exit-eval has no cmd results — vacuous artifact",
            file=sys.stderr,
        )
        return 1
    uneval_cmds = [
        r for r in cmd_results if r.get("ok") is None and r.get("status") == "skipped"
    ]
    if uneval_cmds:
        print(
            "FAIL: wall exit-eval left cmd checks skipped — not an evaluation",
            file=sys.stderr,
        )
        return 1
    if args.require_test_compile:
        tc = [r for r in cmd_results if r.get("check") == "test_compile"]
        if not tc:
            print(
                "FAIL: --require-test-compile but no test_compile cmd result",
                file=sys.stderr,
            )
            return 1
    print(
        f"OK: wall exit-eval present task={args.task_id} "
        f"overall_ok={data.get('overall_ok')} cmd_failed={data.get('cmd_failed')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
