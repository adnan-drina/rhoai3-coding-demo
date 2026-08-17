#!/usr/bin/env python3
"""EX-3 B-S2 / B-2 — in-repo write-set fence as a Hermes pre_tool_call hook.

Native / SAFE_ROOT sandbox only blocks *outside* HERMES_WRITE_SAFE_ROOT
(HKN-12: a deny-prefix path inside the project is still allowed natively).
This hook is the one registered pre_tool_call.

Allow-model (B-2, Architect E-20260817T091919Z): when a write-set is
published for the active kanban task, only `files_writable` paths pass
(deny-prefixes still refuse). A published empty list (`[]`) denies every
dest-relative write — not only `src/`/`pom.xml`. Enforcement is
**path-bearing**: if `extract_path` yields a dest path, the tool name
does not matter. `WRITE_TOOLS` is a no-path fail-closed fast-path only.

If HERMES_KANBAN_TASK is set but the write-set cannot be loaded, treat
that as published `[]` (fail closed on dest paths).

If no kanban task is published, deny-prefix only — validate/dev seats
keep working without a write-set.

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


def in_write_set(rel: str, writable: list[str]) -> bool:
    n = norm_rel(rel)
    for raw in writable:
        ww = norm_rel(str(raw))
        if not ww:
            continue
        if n == ww:
            return True
        if ww.endswith("/"):
            if n.startswith(ww):
                return True
        elif n.startswith(ww + "/"):
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


def _writable_from_obj(obj: object) -> list[str] | None:
    """Return a list when a write-set key is present, including `[]`.

    `files_writable: []` is a published empty set (deny all dest writes).
    It must not collapse to None via `or` — that is how attempt-7 M1
    treated honesty-`[]` as unpublished.
    """
    if not isinstance(obj, dict):
        return None
    body = obj.get("body") if isinstance(obj.get("body"), dict) else obj
    if not isinstance(body, dict):
        return None
    if "files_writable" in body:
        fw = body.get("files_writable")
    elif "write_set" in body:
        fw = body.get("write_set")
    else:
        return None
    if not isinstance(fw, list):
        return None
    return [str(x) for x in fw if str(x).strip()]


def load_write_set(safe_p: Path) -> tuple[list[str] | None, str]:
    """Return (writable, source).

    writable is None when no kanban task is in play (deny-prefix only).
    writable is [] when a task is set but the write-set cannot be loaded
    (fail-closed on product writes).
    """
    env_fw = os.environ.get("HERMES_KANBAN_FILES_WRITABLE", "").strip()
    if env_fw:
        try:
            data = json.loads(env_fw)
        except json.JSONDecodeError:
            data = [x.strip() for x in env_fw.split(",") if x.strip()]
        if isinstance(data, list):
            return (
                [str(x) for x in data if str(x).strip()],
                "env:HERMES_KANBAN_FILES_WRITABLE",
            )
        if isinstance(data, str) and data.strip():
            return [data.strip()], "env:HERMES_KANBAN_FILES_WRITABLE"

    env_body = os.environ.get("HERMES_KANBAN_BODY", "").strip()
    if env_body:
        parsed: object | None = None
        if env_body[:1] in "{[":
            try:
                parsed = json.loads(env_body)
            except json.JSONDecodeError:
                parsed = None
        fw = _writable_from_obj(parsed) if parsed is not None else None
        if fw is not None:
            return fw, "env:HERMES_KANBAN_BODY"
        bp = Path(env_body)
        if not bp.is_absolute():
            bp = safe_p / env_body
        if bp.is_file():
            try:
                fw = _writable_from_obj(json.loads(bp.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, TypeError):
                fw = None
            if fw is not None:
                return fw, str(bp)

    task = os.environ.get("HERMES_KANBAN_TASK", "").strip()
    if not task:
        return None, "unpublished"

    runtime = safe_p / "evidence" / "runtime" / "active-write-set.json"
    if runtime.is_file():
        try:
            data = json.loads(runtime.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            data = None
        if isinstance(data, dict) and str(data.get("task_id") or "").strip() == task:
            fw = _writable_from_obj(data)
            if fw is not None:
                return fw, "evidence/runtime/active-write-set.json"

    ws_dir = safe_p / "evidence" / "runtime" / "write-sets"
    per_task = ws_dir / f"{task}.json"
    if per_task.is_file():
        try:
            fw = _writable_from_obj(json.loads(per_task.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError):
            fw = None
        # Same indent as env_body above. Inside-except this return never ran
        # (Operator E-20260817T110743Z).
        if fw is not None:
            return fw, str(per_task.relative_to(safe_p))

    bodies = safe_p / "evidence" / "bodies"
    if bodies.is_dir():
        for path in sorted(bodies.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError):
                continue
            body = data.get("body") if isinstance(data, dict) and isinstance(
                data.get("body"), dict
            ) else data
            if not isinstance(body, dict):
                continue
            if str(body.get("task_id") or "").strip() != task:
                continue
            fw = _writable_from_obj(body)
            if fw is not None:
                return fw, str(path.relative_to(safe_p))

    return [], f"task-set-unresolved:{task}"


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in {"-h", "--help"}:
        print(
            "write-set-hook.py — Hermes pre_tool_call write fence. "
            "Reads stdin JSON; exit 2 blocks deny-prefix / out-of-SAFE_ROOT "
            "/ out-of-write-set (B-2) writes."
        )
        return 0
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        if os.environ.get("HERMES_KANBAN_TASK", "").strip():
            return _block(
                "write-set-hook: malformed JSON with HERMES_KANBAN_TASK set"
            )
        return _allow()
    if not isinstance(payload, dict):
        if os.environ.get("HERMES_KANBAN_TASK", "").strip():
            return _block(
                "write-set-hook: non-object payload with HERMES_KANBAN_TASK set"
            )
        return _allow()
    tool = payload.get("tool_name") or ""
    raw = extract_path(payload)
    safe = os.environ.get(
        "HERMES_WRITE_SAFE_ROOT",
        os.environ.get("PROJECT_DIR", os.getcwd()),
    )
    safe_p = Path(safe).resolve()
    writable, source = load_write_set(safe_p)
    if not raw:
        # Known write tool, no path, write-set in play → fail closed.
        # Unknown tools with no path stay allow (reads, terminal, etc.).
        if writable is not None and tool in WRITE_TOOLS:
            return _block(
                f"write-set-hook: {tool} missing path with write-set "
                f"published ({source})"
            )
        return _allow()
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
    if writable is None:
        return _allow()
    if not in_write_set(rel_s, writable):
        return _block(
            f"write-set-hook: {rel_s} outside files_writable "
            f"({source}; B-2 path-bearing allow-model)"
        )
    return _allow()


if __name__ == "__main__":
    raise SystemExit(main())
