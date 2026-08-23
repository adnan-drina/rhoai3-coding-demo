#!/usr/bin/env bash
# K2 pre_tool_call — allow-root containment (Architect E-20260823T122407Z).
# Not claimed control until write-escape MATCH. Gate P-kernel stays OPEN.
# Hermes pipes hook JSON on stdin — do not steal it with a heredoc.
# Allow root: K2_ALLOW_ROOT, else HERMES_WRITE_SAFE_ROOT.
# Command with no path proven inside allow-root is deny (quoted perl/ruby).
# No interpreter substring denylist.
set -euo pipefail
exec python3 -c '
import json, os, sys

def block(reason: str) -> None:
    print(json.dumps({"action": "block", "message": reason}))
    raise SystemExit(0)

allow = os.environ.get("K2_ALLOW_ROOT") or os.environ.get("HERMES_WRITE_SAFE_ROOT") or ""
raw = sys.stdin.read()
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    block("unparseable hook payload")
tool = data.get("tool_name") or ""
inp = data.get("tool_input") or {}
if not isinstance(inp, dict):
    inp = {}

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
    for tok in cmd.split():
        if tok.startswith("/") or tok.startswith("./") or tok.startswith("../"):
            paths.append(tok)

if not allow:
    if cmd or paths:
        block("no allow root")
    print("{}")
    raise SystemExit(0)

allow_r = os.path.realpath(allow)
proven = False
for p in paths:
    try:
        rp = os.path.realpath(p)
    except OSError:
        block("path %s unresolved" % p)
    if rp == allow_r or rp.startswith(allow_r + os.sep):
        proven = True
    else:
        block("path %s resolves outside allow root" % p)

if cmd and not proven:
    block("unproven command path")

print("{}")
'
