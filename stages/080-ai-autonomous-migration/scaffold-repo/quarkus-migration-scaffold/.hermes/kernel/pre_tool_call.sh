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
# Batch 4: toolchain reads (/dev/null, /usr/lib/jvm) are not K2_ALLOW_ROOT
# widening (AD-020). Write-set deny. Orchestrator disabled-toolset named
# refusal. kanban_complete refused when a bound gate last exited non-zero.
# Batch 6: M4/VERDICT writes default to evidence/; add-extension is implement.
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
cmd = inp.get("command") if isinstance(inp.get("command"), str) else ""
profile = (os.environ.get("HERMES_PROFILE") or "").strip().lower()
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

def resolve_rp(p):
    s = (p or "").strip()
    if s.startswith("~"):
        s = os.path.expanduser(s)
    if hook_cwd and not os.path.isabs(s):
        s = os.path.join(hook_cwd, s)
    try:
        return os.path.realpath(s)
    except OSError:
        return s

ORCH_DISABLED = {
    "file", "terminal", "code_execution", "delegation", "web", "browser", "skills",
}
TOOL_TO_SET = {
    "terminal": "terminal", "bash": "terminal", "shell": "terminal",
    "read_file": "file", "write_file": "file", "search_files": "file",
    "patch": "file", "edit_file": "file", "str_replace": "file",
    "execute_code": "code_execution", "delegate_task": "delegation",
}
if profile == "orchestrator":
    ts = TOOL_TO_SET.get(tool)
    if ts in ORCH_DISABLED:
        block("%s disabled for profile orchestrator" % ts)

if tool in {"execute_code", "delegate_task", "mcp", "skill_manage"}:
    block("%s is pathless-or-mutation; deny" % tool)

def is_complete():
    if tool in {"kanban_complete", "complete_task"}:
        return True
    blob = " ".join([tool, cmd, str(inp.get("action") or "")])
    if "kanban_complete" in blob:
        return True
    if re.search(r"\bkanban\s+complete\b", blob):
        return True
    return False

def bound_gate_red():
    env_exit = (os.environ.get("K2_BOUND_GATE_EXIT") or "").strip().lower()
    if env_exit in {"1", "fail", "true", "nonzero"}:
        return os.environ.get("K2_BOUND_GATE_NAME") or "bound-gate"
    if env_exit in {"0", "pass", "ok"}:
        return None
    task = (os.environ.get("HERMES_KANBAN_TASK") or "").strip()
    home = (os.environ.get("HERMES_HOME") or "").strip()
    if not task or not home:
        return None
    log = os.path.join(home, "kanban", "logs", "%s.log" % task)
    try:
        text = open(log, encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    names = (
        "assert-m2-speckit-conformance", "assert-m2-story-headings", "assert-m4-verdict-schema", "check-product-tests", "run-m4-pre-verdict", "assert-pinned-gates-ran",
        "assert-retrievable-tree", "check-spec-readiness", "check-domain-parity",
        "check-release-readiness", "check-test-toolchain", "check-external-dirs",
        "check-readiness", "check-partition-coverage", "check-kanban-body",
        "assert-surefire-results", "assert-m4-card-body",
    )
    last = {}
    for line in text.splitlines():
        hits = [n for n in names if n in line]
        if not hits:
            continue
        name = max(hits, key=len)
        if re.search(r"\[exit 1\]|FAIL:|REFUSE", line, re.I):
            last[name] = name
        elif re.search(r"\[exit 0\]|\bOK:", line, re.I):
            last.pop(name, None)
    for name in names:
        if name in last:
            return last[name]
    return None

if is_complete():
    gate = bound_gate_red()
    if gate:
        block("kanban_complete refused: bound gate %s last exited non-zero; "
              "kanban_block is the terminator" % gate)

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

def toolchain_read(rp):
    n = (rp or "").replace("\\", "/")
    for prefix in (
        "/dev/null", "/dev/stdout", "/dev/stderr", "/dev/fd",
        "/usr/lib/jvm",
    ):
        if n == prefix or n.startswith(prefix + "/"):
            return True
    jh = (os.environ.get("JAVA_HOME") or "").strip()
    if jh:
        try:
            jr = os.path.realpath(jh).replace("\\", "/")
        except OSError:
            jr = jh.replace("\\", "/")
        if n == jr or n.startswith(jr + "/"):
            return True
    return False

_HTTP_FS_PREFIXES = (
    "/projects", "/home", "/usr", "/opt", "/tmp", "/var", "/etc",
    "/bin", "/src/", "/dev/", "/lib", "/proc", "/sys",
)
_HTTP_FILE_EXT = {
    "java", "xml", "json", "md", "properties", "yaml", "yml", "sh", "py",
}

def looks_like_http_route(p):
    n = str(p or "").replace("\\", "/")
    if not n.startswith("/") or n.startswith("//"):
        return False
    for pref in _HTTP_FS_PREFIXES:
        if n == pref.rstrip("/") or n.startswith(pref if pref.endswith("/") else pref + "/"):
            return False
    last = n.rsplit("/", 1)[-1]
    if "." in last and last.rsplit(".", 1)[-1].lower() in _HTTP_FILE_EXT:
        return False
    return True

paths = []
collect(inp, paths)
cmd_for_paths = strip_env_assignments(cmd) if cmd else ""
if cmd_for_paths:
    for tok in cmd_for_paths.split():
        if tok.startswith("/") or tok.startswith("./") or tok.startswith("../"):
            if not looks_like_http_route(tok):
                paths.append(tok)
    cmd_scan = re.sub(r"https?://\S+", " ", cmd_for_paths)
    for m in re.finditer(r"(?:~/|\.\./|\./|(?<![\w:])/)(?!\d)[^\s\"{}()]+", cmd_scan):
        span = m.group(0)
        span = span.split(",")[0]
        while span and span[-1] in ".,;:" + chr(39) + chr(34):
            span = span[:-1]
        if span.startswith("~"):
            span = os.path.expanduser(span)
        if looks_like_http_route(span):
            continue
        if span not in paths:
            paths.append(span)
    if re.search(r"\bmkdir\b", cmd_for_paths):
        parts = cmd_for_paths.split()
        i = 0
        while i < len(parts):
            base = parts[i].rsplit("/", 1)[-1]
            if base == "mkdir":
                i += 1
                while i < len(parts) and parts[i].startswith("-"):
                    i += 1
                while i < len(parts):
                    arg = parts[i]
                    if arg in ("&&", "||", ";", "|"):
                        break
                    if arg.startswith("-"):
                        i += 1
                        continue
                    if arg not in paths:
                        paths.append(arg)
                    i += 1
                continue
            i += 1

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
only_toolchain = True
for p in paths:
    rp = resolve_rp(p)
    if toolchain_read(rp) or toolchain_read(str(p).replace("\\", "/")):
        continue
    only_toolchain = False
    if inside(rp):
        proven = True
    else:
        block("path %s resolves outside allow root" % p)
if paths and only_toolchain:
    print("{}")
    raise SystemExit(0)

def dest_root():
    wr = (os.environ.get("HERMES_WRITE_SAFE_ROOT") or "").strip()
    if wr:
        try:
            return os.path.realpath(wr)
        except OSError:
            return wr
    return roots[0] if roots else ""

def dest_rel(rp):
    root = dest_root()
    if not root:
        return None
    if rp == root:
        return ""
    if rp.startswith(root + os.sep):
        return rp[len(root) + 1:].replace("\\", "/")
    return None

def list_from_fw(fw):
    if not isinstance(fw, list):
        return None
    out = []
    for item in fw:
        if isinstance(item, str) and item.strip():
            out.append(item.strip().replace("\\", "/"))
    return out

def parse_writeset_blob(blob):
    if not blob or not isinstance(blob, str):
        return None
    blobs = [blob]
    for m in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", blob, re.S):
        blobs.append(m.group(1))
    idx = blob.find("files_writable")
    if idx >= 0:
        brace = blob.rfind("{", 0, idx)
        if brace >= 0:
            blobs.append(blob[brace:])
    for cand in blobs:
        data = None
        try:
            data = json.loads(cand)
        except json.JSONDecodeError:
            start = cand.find("{")
            end = cand.rfind("}")
            if start >= 0 and end > start:
                try:
                    data = json.loads(cand[start:end + 1])
                except json.JSONDecodeError:
                    data = None
        if not isinstance(data, dict):
            continue
        if isinstance(data.get("body"), dict):
            data = data["body"]
        elif isinstance(data.get("task"), dict):
            inner = data["task"]
            if isinstance(inner.get("body"), dict):
                data = inner["body"]
            elif isinstance(inner.get("description"), str):
                nested = parse_writeset_blob(inner["description"])
                if nested is not None:
                    return nested
                data = inner
        if "files_writable" in data or "write_set" in data:
            parsed = list_from_fw(data.get("files_writable") or data.get("write_set"))
            if parsed is not None:
                return parsed
    m = re.search(chr(34) + r"files_writable" + r"\s*:\s*(\[[^\]]*\])", blob)
    if m:
        try:
            arr = json.loads(m.group(1))
            parsed = list_from_fw(arr)
            if parsed is not None:
                return parsed
        except json.JSONDecodeError:
            pass
    return None

def load_body_from_sqlite():
    task = (os.environ.get("HERMES_KANBAN_TASK") or "").strip()
    if not task:
        return ""
    cands = []
    for key in ("HERMES_KANBAN_DB", "HERMES_KANBAN_DB_PATH"):
        v = (os.environ.get(key) or "").strip()
        if v:
            cands.append(v)
    home = (os.environ.get("HERMES_HOME") or "").strip()
    if home:
        cands.extend([
            os.path.join(home, "kanban.db"),
            os.path.join(home, "kanban", "kanban.db"),
        ])
    for db in cands:
        if not db or not os.path.isfile(db):
            continue
        try:
            import sqlite3
            con = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
        except Exception:
            continue
        try:
            tables = [r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type=?",
                ("table",),
            )]
            for table in tables:
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", table or ""):
                    continue
                if table not in {"tasks", "kanban_tasks"} and "task" not in table.lower():
                    continue
                cols = [r[1] for r in con.execute("PRAGMA table_info(%s)" % table)]
                idcol = "id" if "id" in cols else ("task_id" if "task_id" in cols else None)
                bodycol = next(
                    (c for c in ("description", "body", "prompt", "content") if c in cols),
                    None,
                )
                if not idcol or not bodycol:
                    continue
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", idcol):
                    continue
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", bodycol):
                    continue
                row = con.execute(
                    "SELECT %s FROM %s WHERE %s = ?" % (bodycol, table, idcol),
                    (task,),
                ).fetchone()
                if row and row[0]:
                    return str(row[0])
        except Exception:
            pass
        finally:
            try:
                con.close()
            except Exception:
                pass
    return ""

def load_writeset():
    if "K2_FILES_WRITABLE" in os.environ:
        raw = os.environ.get("K2_FILES_WRITABLE") or ""
        return [p.strip().replace("\\", "/") for p in raw.split(os.pathsep) if p.strip()]
    blob = ""
    body_path = (os.environ.get("K2_CARD_BODY") or "").strip()
    if body_path and os.path.isfile(body_path):
        try:
            blob = open(body_path, encoding="utf-8", errors="replace").read()
        except OSError:
            blob = ""
    if not blob:
        blob = load_body_from_sqlite()
    return parse_writeset_blob(blob)

def load_phase():
    envp = (os.environ.get("K2_CARD_PHASE") or "").strip().upper()
    if envp:
        return envp
    blob = ""
    body_path = (os.environ.get("K2_CARD_BODY") or "").strip()
    if body_path and os.path.isfile(body_path):
        try:
            blob = open(body_path, encoding="utf-8", errors="replace").read()
        except OSError:
            blob = ""
    if not blob:
        blob = load_body_from_sqlite()
    if not blob:
        return ""
    m = re.search(chr(34) + r"phase" + r"\s*:\s*" + chr(34) + r"([A-Za-z0-9_]+)", blob)
    return m.group(1).upper() if m else ""

def writeset_ok(rel, writeset):
    if not rel:
        return True
    rel = rel.replace("\\", "/").lstrip("./")
    for w in writeset:
        ww = w.replace("\\", "/").lstrip("./").strip("/")
        if not ww:
            continue
        if rel == ww or rel.startswith(ww + "/"):
            return True
    return False

def writeset_ok_mkdir(rel, writeset):
    if writeset_ok(rel, writeset):
        return True
    if not rel:
        return True
    rel = rel.replace("\\", "/").lstrip("./")
    for w in writeset:
        ww = w.replace("\\", "/").lstrip("./").strip("/")
        if ww.startswith(rel + "/"):
            return True
    return False

WRITE_TOOLS = {
    "write_file", "write", "patch", "edit_file", "str_replace",
    "apply_patch", "create_file",
}

def looks_like_write_cmd(c):
    if not c:
        return False
    if re.search(r"(?:^|[^=])>(?!>)", c) and ">/dev/null" not in c.replace(" ", ""):
        if re.search(r">\s*/dev/null\b", c):
            pass
        elif re.search(r"[^0-9]>\s*\S+", c) or re.search(r"^\s*>\s*\S+", c):
            if not re.search(r">\s*/dev/(null|stdout|stderr)\b", c):
                return True
    if re.search(r"\btee\b", c) and "/dev/null" not in c:
        return True
    if re.search(r"\b(?:mv|cp|rm|mkdir|install|install_name_tool)\b", c):
        return True
    if "quarkus:add-extension" in c or "add-extension" in c:
        return True
    return False

def in_dest_write_sandbox(rp):
    root = dest_root()
    if not root:
        return False
    return rp == root or rp.startswith(root + os.sep)

if tool in WRITE_TOOLS or looks_like_write_cmd(cmd):
    for p in paths:
        rp = resolve_rp(p)
        if toolchain_read(rp) or toolchain_read(str(p).replace("\\", "/")):
            continue
        if not in_dest_write_sandbox(rp):
            block("write %s is outside the dest write sandbox (legacy is read-only)" % p)
    if looks_like_write_cmd(cmd) and (
        "quarkus:add-extension" in cmd or re.search(r"\badd-extension\b", cmd)
    ):
        pom = os.path.join(dest_root() or "", "pom.xml")
        try:
            pr = os.path.realpath(pom) if dest_root() else "pom.xml"
        except OSError:
            pr = pom
        if dest_root() and not in_dest_write_sandbox(pr):
            block("write pom.xml is outside the dest write sandbox (legacy is read-only)")

writeset = load_writeset()
phase = load_phase()
if phase in {"M4", "VERDICT"}:
    if looks_like_write_cmd(cmd) and (
        "quarkus:add-extension" in cmd or re.search(r"\badd-extension\b", cmd)
    ):
        block("M4 VERDICT must not implement; quarkus:add-extension writes pom.xml")
    if writeset is None:
        writeset = ["evidence/"]
    else:
        kept = []
        for w in writeset:
            ww = w.replace("\\", "/").lstrip("./")
            if ww == "evidence" or ww.startswith("evidence/"):
                kept.append(w)
        writeset = kept or ["evidence/"]
story = (os.environ.get("K2_STORY_ID") or "").strip() or "this card"
if writeset is not None:
    rels = []
    if tool in WRITE_TOOLS:
        for p in paths:
            rel = dest_rel(resolve_rp(p))
            if rel:
                rels.append(rel)
    elif looks_like_write_cmd(cmd):
        for p in paths:
            rp = resolve_rp(p)
            if toolchain_read(rp) or toolchain_read(str(p).replace("\\", "/")):
                continue
            rel = dest_rel(rp)
            if rel:
                rels.append(rel)
        if "quarkus:add-extension" in cmd or re.search(r"\badd-extension\b", cmd):
            rels.append("pom.xml")
    mkdir_cmd = bool(cmd and re.search(r"\bmkdir\b", cmd))
    for rel in rels:
        ok = writeset_ok_mkdir(rel, writeset) if mkdir_cmd else writeset_ok(rel, writeset)
        if not ok:
            block("write %s outside files_writable (story %s); "
                  "do not override the write-set" % (rel or "pom.xml", story))

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
