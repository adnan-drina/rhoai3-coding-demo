#!/usr/bin/env python3
"""Refuse an M4 card body that already names the verdict token or ship flag.

Lead:m4-card-must-not-pre-specify-the-verdict — dest-5 M4 body carried
``Token: PROVISIONAL_ACCEPT, ship: false``; dest-4 ``t_9acd47cb`` did not
and derived the token. A verdict phase handed its verdict is not a verdict.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

TOKEN_ASSIGN = re.compile(
    r"(?is)\b(?:token|verdict)\s*:\s*"
    r"(PROVISIONAL_ACCEPT|SCOPED_ACCEPT|ACCEPT|REFUSE)\b"
)
SHIP_ASSIGN = re.compile(r"(?is)\bship\s*:\s*(true|false)\b")


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def body_from_show(data: object) -> str:
    if not isinstance(data, dict):
        return ""
    task = data.get("task") if isinstance(data.get("task"), dict) else data
    if not isinstance(task, dict):
        return ""
    for key in ("body", "description", "prompt"):
        val = task.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return ""


def load_show(task_id: str) -> dict:
    override = (os.environ.get("HERMES_KANBAN_SHOW") or "").strip()
    if override:
        cmd = shlex.split(override) + [task_id, "--json"]
    else:
        cmd = ["hermes", "kanban", "show", task_id, "--json"]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:400]
        raise RuntimeError("kanban show %s rc=%s %s" % (task_id, proc.returncode, err))
    data = json.loads(proc.stdout)
    if not isinstance(data, dict):
        raise RuntimeError("kanban show %s JSON is not an object" % task_id)
    return data


def resolve_body(
    *,
    body: str | None,
    body_file: Path | None,
    env_body: str,
    task_id: str,
) -> str:
    if body is not None:
        return body
    if body_file is not None:
        return body_file.read_text(encoding="utf-8")
    if env_body.strip():
        return env_body
    if task_id:
        return body_from_show(load_show(task_id))
    return ""


def check_body(text: str) -> list[str]:
    issues: list[str] = []
    if TOKEN_ASSIGN.search(text):
        issues.append("M4 body names a verdict token (Token:/verdict: ACCEPT*)")
    if SHIP_ASSIGN.search(text):
        issues.append("M4 body names ship: true/false")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--body",
        default=None,
        help="raw card body (tests)",
    )
    parser.add_argument("--body-file", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        text = resolve_body(
            body=args.body,
            body_file=args.body_file,
            env_body=os.environ.get("M4_CARD_BODY") or "",
            task_id=(os.environ.get("HERMES_KANBAN_TASK") or "").strip(),
        )
    except (OSError, json.JSONDecodeError, RuntimeError) as exc:
        return _fail("could not read M4 card body: " + str(exc))
    if not text.strip():
        return _fail(
            "missing M4 card body — pass --body-file, M4_CARD_BODY, or "
            "HERMES_KANBAN_TASK (fail closed, not idle)"
        )
    issues = check_body(text)
    if issues:
        for issue in issues:
            print("FAIL: " + issue, file=sys.stderr)
        print(
            "M4 body is acceptance/oracles only; dest-4 t_9acd47cb named none",
            file=sys.stderr,
        )
        return 1
    print("OK: M4 card body does not pre-specify a verdict token", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
