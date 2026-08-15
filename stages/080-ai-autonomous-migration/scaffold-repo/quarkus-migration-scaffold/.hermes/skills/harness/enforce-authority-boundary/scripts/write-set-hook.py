#!/usr/bin/env python3
"""EX-3 B-S2 — in-repo write-set fence as a Hermes pre_tool_call hook.

Native / SAFE_ROOT sandbox only blocks *outside* HERMES_WRITE_SAFE_ROOT
(HKN-12: a deny-prefix path inside the project is still allowed natively).
This hook is the one registered pre_tool_call: it also refuses deny-prefix
paths inside the repo. Legitimate product writes (src/, pom.xml, …) pass.

Hermes shell hook contract (hermes-hooks):
  stdin  JSON {tool_name, tool_input}
  stdout {} to allow, or {"action":"block","message":...} to refuse
  exit 2 blocks pre_tool_call; fail_closed: true on the registration
  Headless seats need hooks_auto_accept / HERMES_ACCEPT_HOOKS / --accept-hooks

Usage:
  python3 write-set-hook.py          # read stdin payload
  python3 write-set-hook.py --help
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

WRITE_TOOLS = frozenset(
    {"write_file", "patch", "edit_file", "apply_patch", "create_file"}
)

DENY_PREFIXES = (
    "evidence/acks/",
    "evidence/acks",
    "evidence/verdicts/",
    "evidence/verdicts",
    ".hermes/",
    ".hermes",
    "AGENTS.md",
    "SOUL.md",
    ".hermes/SOUL.md",
    "devfile.yaml",
    ".hermes/home/kanban.db",
)


def _allow() -> int:
    print("{}")
    return 0


def _block(msg: str) -> int:
    print(json.dumps({"action": "block", "message": msg}))
    return 2


def norm_rel(path: str) -> str:
    s = path.replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s


def is_denied(rel: str) -> bool:
    n = norm_rel(rel)
    for ban in DENY_PREFIXES:
        b = ban.rstrip("/")
        if n == b or n.startswith(b + "/") or n == ban:
            return True
    return False


def extract_path(payload: dict) -> str | None:
    ti = payload.get("tool_input") or {}
    if not isinstance(ti, dict):
        ti = {}
    for k in ("path", "file", "filename", "target"):
        v = ti.get(k)
        if isinstance(v, str) and v:
            return v
    targets = ti.get("targets") if isinstance(ti.get("targets"), dict) else {}
    for k in ("path", "file"):
        v = targets.get(k)
        if isinstance(v, str) and v:
            return v
    return None


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in {"-h", "--help"}:
        print(
            "write-set-hook.py — Hermes pre_tool_call write fence. "
            "Reads stdin JSON; exit 2 blocks deny-prefix / out-of-SAFE_ROOT writes."
        )
        return 0
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return _allow()
    if not isinstance(payload, dict):
        return _allow()
    tool = payload.get("tool_name") or ""
    if tool not in WRITE_TOOLS:
        return _allow()
    raw = extract_path(payload)
    if not raw:
        return _allow()
    safe = os.environ.get(
        "HERMES_WRITE_SAFE_ROOT",
        os.environ.get("PROJECT_DIR", os.getcwd()),
    )
    safe_p = Path(safe).resolve()
    target = Path(raw)
    if not target.is_absolute():
        target = Path.cwd() / target
    target = Path(os.path.abspath(str(target)))
    try:
        rel = target.relative_to(safe_p)
    except ValueError:
        return _block(
            f"write-set-hook: path {target} outside HERMES_WRITE_SAFE_ROOT={safe_p}"
        )
    rel_s = str(rel).replace("\\", "/")
    if is_denied(rel_s):
        return _block(
            f"write-set-hook: in-repo OOS path {rel_s} (B-S2 deny-prefix)"
        )
    return _allow()


if __name__ == "__main__":
    raise SystemExit(main())
