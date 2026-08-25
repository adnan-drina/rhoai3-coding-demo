#!/usr/bin/env bash
# K2 pre_tool_call — allow-root containment (Architect E-20260823T122407Z).
# Not claimed control. Gate P-kernel CLOSED (Architect 142526Z); this
# file remains K2 instrumentation (MEASURED), not a claimed write fence.
# Hermes pipes hook JSON on stdin — do not steal it with a heredoc.
# Allow roots: K2_ALLOW_ROOT, else HERMES_WRITE_SAFE_ROOT. os.pathsep
# split (Architect 214325ZA): dest terminal roots are dest tree +
# /projects/legacy. Do not put / in the list. Write sandbox stays
# HERMES_WRITE_SAFE_ROOT as the dest tree only (legacy is read-only).
# Architect 124330Z: extract POSIX-looking path spans (/ -anchored, ~/,
# ./, ../) including quotes/q{}. Not every / (https://, 2026/08/23).
# Opaque construction denies even inside a grant (Architect 085408ZA AMEND
# of 214743ZA). Discriminator is opacity, not empty path set. Transparent
# pathless + cwd realpath inside K2_ALLOW_ROOT allow. Missing cwd deny.
# Not an interpreter denylist. Dual-root allow-root still stands (214325ZA).
# Do not add /opt/kantra. Do not allow /. Do not add /projects/.derived
# (Architect 082958ZA). export NAME=value / NAME=value prefixes are env
# values, not access targets (Operator 083840ZO GAP 2) — JAVA_HOME and
# PATH=/bin:$PATH must not block. RHS $PATH in PATH=/bin:$PATH is
# concatenation, not a later access.
set -euo pipefail
exec python3 -c '
import json, os, re, sys

def block(reason):
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

def strip_env_assignments(s):
    s = re.sub(r"\bexport\s+[A-Za-z_][A-Za-z0-9_]*=[^\s;|&]+", " ", s)
    s = re.sub(r"(?:^|[\s;|&])[A-Za-z_][A-Za-z0-9_]*=[^\s;|&]+", " ", s)
    return s

paths = []
collect(inp, paths)
cmd = inp.get("command") if isinstance(inp.get("command"), str) else ""
cmd_for_paths = strip_env_assignments(cmd) if cmd else ""
if cmd_for_paths:
    for tok in cmd_for_paths.split():
        if tok.startswith("/") or tok.startswith("./") or tok.startswith("../"):
            paths.append(tok)
    cmd_scan = re.sub(r"https?://\S+", " ", cmd_for_paths)
    for m in re.finditer(r"(?:~/|\.\./|\./|(?<![\w:])/)(?!\d)[^\s\"{}()]+", cmd_scan):
        span = m.group(0)
        span = span.split(",")[0]
        while span and span[-1] in ".,;:" + chr(39) + chr(34):
            span = span[:-1]
        if span.startswith("~"):
            span = os.path.expanduser(span)
        if span not in paths:
            paths.append(span)

roots = []
for part in allow.split(os.pathsep):
    part = part.strip()
    if part:
        try:
            roots.append(os.path.realpath(part))
        except OSError:
            block("allow root %s unresolved" % part)

if not roots:
    if cmd or paths:
        block("no allow root")
    print("{}")
    raise SystemExit(0)

def inside(rp):
    for allow_r in roots:
        if rp == allow_r or rp.startswith(allow_r + os.sep):
            return True
    return False

proven = False
for p in paths:
    try:
        rp = os.path.realpath(p)
    except OSError:
        block("path %s unresolved" % p)
    if inside(rp):
        proven = True
    else:
        block("path %s resolves outside allow root" % p)

# Architect 085408ZA AMEND 214743ZA: opacity on EVERY command, not only
# when `not proven` (Operator 090438ZO). Prefixing an in-root path must
# not disable the dest-3 vector. Still a guardrail (AD-020). OBJECT argv[0]
# allowlist. OBJECT any-pathless cwd ALLOW.
_OPAQUE = (
    r"base64\s+(?:-d\b|--decode\b|-D\b)",
    r"\bxxd\s+-r\b",
    r"printf\s+[" + chr(34) + chr(39) + r"]\\x",
    r"\$" + chr(39) + r"\\x",
    r"\beval\b",
)

if cmd.strip():
    for _rx in _OPAQUE:
        if re.search(_rx, cmd, re.IGNORECASE):
            block("opaque command construction: the path this touches is not "
                  "visible. If the access is legitimate, name the path plainly "
                  "or ask for it in K2_ALLOW_ROOT. Do not encode it.")

if cmd_for_paths.strip() and not proven:
    extra = data.get("extra") if isinstance(data.get("extra"), dict) else {}
    args = data.get("args") if isinstance(data.get("args"), dict) else {}
    hook_cwd = ""
    for src in (data, extra, inp, args):
        if not isinstance(src, dict):
            continue
        for key in ("cwd", "working_dir", "workdir"):
            v = src.get(key)
            if isinstance(v, str) and v.strip():
                hook_cwd = v.strip()
                break
        if hook_cwd:
            break
    if hook_cwd:
        try:
            cr = os.path.realpath(hook_cwd)
        except OSError:
            block("cwd unresolved")
        if inside(cr):
            print("{}")
            raise SystemExit(0)
    block("unproven command path")

print("{}")
'
