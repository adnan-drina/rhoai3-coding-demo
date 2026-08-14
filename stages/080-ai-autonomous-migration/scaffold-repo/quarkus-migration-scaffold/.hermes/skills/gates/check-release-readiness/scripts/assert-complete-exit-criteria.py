#!/usr/bin/env python3
"""Architect E-20260811T175509Z Class A — refuse complete when cmd exits fail.

BANK-COMPLETE-CMD-1 elevated: Hermes `kanban_complete` does not evaluate
cmd-shaped exit_criteria. Workers MUST run this script (rc=0) before calling
`kanban_complete`. Lead/watchdog MAY reclaim `done` cards that lack a green
receipt via enforce-complete-exit-criteria.py.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "rhoai3.complete-exit-ok/v1"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--body", required=True)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    body = Path(args.body)
    if not body.is_file():
        body = root / args.body
    if not body.is_file():
        print(f"FAIL: body not found: {args.body}", file=sys.stderr)
        return 1

    eval_py = (
        Path(__file__).resolve().parent / "evaluate-exit-criteria.py"
    )
    cp = subprocess.run(
        [
            sys.executable,
            str(eval_py),
            str(root),
            "--body",
            str(body),
            "--task-id",
            args.task_id,
            "--trigger",
            "complete",
        ],
        text=True,
        capture_output=True,
    )
    sys.stdout.write(cp.stdout or "")
    sys.stderr.write(cp.stderr or "")

    eval_path = root / "evidence" / "runs" / args.task_id / "exit-eval.json"
    overall_ok = False
    cmd_failed: list = []
    if eval_path.is_file():
        try:
            payload = json.loads(eval_path.read_text(encoding="utf-8"))
            overall_ok = bool(payload.get("overall_ok"))
            cmd_failed = list(payload.get("cmd_failed") or [])
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    out_dir = root / "evidence" / "runs" / args.task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema": SCHEMA,
        "task_id": args.task_id,
        "ok": overall_ok and cp.returncode == 0,
        "eval_rc": cp.returncode,
        "cmd_failed": cmd_failed,
        "exit_eval": str(eval_path.relative_to(root)) if eval_path.is_file() else None,
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": [
            "Architect E-20260811T175509Z Class A — BANK-COMPLETE-CMD-1 elevated",
            "kanban_complete MUST NOT be called unless ok=true",
            "compile/test_compile use scope-filtered gate (compile-scope-filtered.md)",
        ],
    }
    out = out_dir / "complete-exit-ok.json"
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    if not receipt["ok"]:
        print(
            f"FAIL: refuse kanban_complete — cmd exits failed {cmd_failed} "
            f"(receipt {out.relative_to(root)})",
            file=sys.stderr,
        )
        return 1

    # Architect E-20260813T152211Z / Lead wire-or-retire: AD-H §17/§19 must not
    # depend on skill_view. Invoke enforcement scripts on the complete path.
    # Wave B tip layout: enforcement scripts live under .hermes/enforcement/
    # (skills/harness retained as legacy fallback).
    skills = root / ".hermes" / "skills" / "harness"
    enforcement = root / ".hermes" / "enforcement"
    gates = root / ".hermes" / "skills" / "gates" / "check-release-readiness" / "scripts"

    def find_script(rel: str) -> Path:
        for base in (enforcement, skills):
            cand = base / rel
            if cand.is_file():
                return cand
        return skills / rel  # for missing-script error path

    citation = find_script("ground-in-harvest/scripts/check-citation.py")
    body_digest = find_script(
        "record-run-evidence/scripts/check-body-digest-match.py"
    )
    provenance = find_script("record-run-evidence/scripts/check-provenance.py")
    runnable_db = gates / "check-runnable-db-config.py"
    empty_security = gates / "check-empty-security.py"
    for label, cmd in (
        (
            "body-digest",
            [sys.executable, str(body_digest), str(root), "--body", str(body)],
        ),
        (
            "citation",
            [
                sys.executable,
                str(citation),
                str(root),
                "--packet",
                str(body),
            ],
        ),
        (
            "provenance",
            [sys.executable, str(provenance), str(root)],
        ),
        # A2 / runnable-db-security — refuse complete on HSQLDB / empty security
        (
            "runnable-db-config",
            [sys.executable, str(runnable_db), str(root)],
        ),
        (
            "empty-security",
            [sys.executable, str(empty_security), str(root)],
        ),
    ):
        if not Path(cmd[1]).is_file():
            print(f"FAIL: missing enforcement script for {label}: {cmd[1]}", file=sys.stderr)
            return 2
        sub = subprocess.run(cmd, text=True, capture_output=True)
        sys.stdout.write(sub.stdout or "")
        sys.stderr.write(sub.stderr or "")
        if sub.returncode != 0:
            print(
                f"FAIL: refuse kanban_complete — {label} enforcement rc={sub.returncode} "
                f"(Architect E-20260813T152211Z mechanical path)",
                file=sys.stderr,
            )
            return 1 if sub.returncode == 1 else sub.returncode

    print(f"OK: complete-exit green → {out.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
