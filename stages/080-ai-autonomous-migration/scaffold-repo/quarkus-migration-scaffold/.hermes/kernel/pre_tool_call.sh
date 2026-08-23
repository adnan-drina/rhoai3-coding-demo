#!/usr/bin/env bash
# K2 instrumentation — one shell pre_tool_call module (Architect E-20260823T120100Z).
# Not claimed control. Gate P-kernel stays OPEN until write-escape MATCH.
# Hermes pipes hook JSON on stdin — do not steal it with a heredoc.
# Probe allow root: K2_ALLOW_ROOT. Empty allow skips path checks (pathless still deny).
set -euo pipefail
exec python3 -c '
import json, os, sys
allow = os.environ.get("K2_ALLOW_ROOT") or ""
raw = sys.stdin.read()
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    sys.exit(0)
tool = data.get("tool_name") or ""
inp = data.get("tool_input") or {}
if not isinstance(inp, dict):
    inp = {}

def block(reason: str) -> None:
    print(json.dumps({"action": "block", "message": reason}))
    raise SystemExit(0)

if tool in {"execute_code", "delegate_task", "mcp", "skill_manage"}:
    block("%s is pathless-or-mutation; deny" % tool)

def collect(obj, acc):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in {
                "path", "file", "filename", "target", "dest",
                "destination", "old_path", "new_path",
            } and isinstance(v, str):
                acc.append(v)
            collect(v, acc)
    elif isinstance(obj, list):
        for x in obj:
            collect(x, acc)

paths = []
collect(inp, paths)
cmd = inp.get("command") if isinstance(inp.get("command"), str) else ""
if cmd:
    low = cmd.lower()
    for needle in (
        "python", "python3", "javac", "mvn ", "ln -s", " >", ">>",
        " mv ", "mv ", "cp ", "dd ", "chmod ",
    ):
        if needle in low:
            block("terminal class %r denied" % needle)
    for tok in cmd.split():
        if tok.startswith("/") or tok.startswith("./") or tok.startswith("../"):
            paths.append(tok)

if allow:
    allow_r = os.path.realpath(allow)
    for p in paths:
        try:
            rp = os.path.realpath(p)
        except OSError:
            continue
        if rp != allow_r and not rp.startswith(allow_r + os.sep):
            block("path %s resolves outside allow root" % p)

print("{}")
'
