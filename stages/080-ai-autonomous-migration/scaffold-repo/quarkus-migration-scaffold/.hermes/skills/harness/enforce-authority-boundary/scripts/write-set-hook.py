#!/usr/bin/env python3
"""EX-3 B-S2 / B-2 — in-repo write-set fence as a Hermes pre_tool_call hook.

Native / SAFE_ROOT sandbox only blocks *outside* HERMES_WRITE_SAFE_ROOT
(HKN-12: a deny-prefix path inside the project is still allowed natively).
This hook is the one registered pre_tool_call.

Allow-model (B-2, Architect E-20260817T091919Z / BIND 25a7c1e9): resolve
the write-set in this order:

  1. spawn env `HERMES_KANBAN_FILES_WRITABLE` (card set published at spawn)
  2. card `files_writable` when published (`HERMES_KANBAN_CARD_JSON` /
     `HERMES_KANBAN_CARD_BODY` — not dest cache)
  3. phase-dispatch.yaml `files_writable` when that key is published
  4. else deny-all `[]` (`task-set-unresolved`)

A published empty list (`[]`) denies every dest-relative write. Enforcement
is **path-bearing**: if `extract_path` yields a dest path, the tool name
does not matter. `WRITE_TOOLS` is a no-path fail-closed fast-path only.

`evidence/runtime/write-sets/*.json` is a mint **cache** (forensics /
spawn hydrate). This hook must not read dest JSON or typed bodies for
allow/deny (Architect 35099226 / Operator 7e93fb41). M3 omits the yaml
key — story write-sets are per-card. v24 does not claim a new trust
boundary (hole 2 / `$HOME` stays open).

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
import re
import subprocess
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
    "evidence/runtime/write-sets/",
    "evidence/runtime/write-sets",
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


def parse_files_writable_env(raw: str) -> list[str] | None:
    """Parse spawn-env FILES_WRITABLE. None = unset/unparseable (not `[]`)."""
    text = raw.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [x.strip() for x in text.split(",") if x.strip()]
    if isinstance(data, list):
        return [str(x) for x in data if str(x).strip()]
    if isinstance(data, str) and data.strip():
        return [data.strip()]
    return None


def _parse_files_writable_markdown(text: str) -> list[str] | None:
    """Parse a `## Files Writable` list. None if the section is absent."""
    in_sec = False
    seen = False
    items: list[str] = []
    for ln in text.splitlines():
        if re.match(r"^## Files Writable\s*$", ln, re.IGNORECASE):
            in_sec = True
            seen = True
            continue
        if in_sec:
            if ln.startswith("## "):
                break
            m = re.match(r"^-\s+(.+)$", ln.strip())
            if m:
                items.append(m.group(1).strip())
    if not seen:
        return None
    return items


def _writable_from_card_env() -> tuple[list[str] | None, str]:
    raw_json = os.environ.get("HERMES_KANBAN_CARD_JSON", "").strip()
    if raw_json:
        try:
            obj = json.loads(raw_json)
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict):
            fw = _writable_from_obj(obj)
            if fw is not None:
                return fw, "card:HERMES_KANBAN_CARD_JSON"
            body = obj.get("body")
            if isinstance(body, str):
                parsed = _parse_files_writable_markdown(body)
                if parsed is not None:
                    return parsed, "card:HERMES_KANBAN_CARD_JSON.body"
    raw_md = os.environ.get("HERMES_KANBAN_CARD_BODY", "").strip()
    if raw_md:
        parsed = _parse_files_writable_markdown(raw_md)
        if parsed is not None:
            return parsed, "card:HERMES_KANBAN_CARD_BODY"
    return None, ""


def _phase_id(safe_p: Path, task: str) -> str:
    phase = os.environ.get("HERMES_KANBAN_PHASE", "").strip()
    if phase:
        return phase
    derived = safe_p / "evidence" / "derived"
    if not task or not derived.is_dir():
        return ""
    for name in ("M1", "M2", "M4", "M5", "M3"):
        ptr = derived / f"phase-{name}-task-id.txt"
        try:
            if ptr.is_file() and ptr.read_text(encoding="utf-8").strip() == task:
                return name
        except OSError:
            continue
    return ""


def _writable_from_phase_yaml(
    safe_p: Path, phase: str
) -> tuple[list[str] | None, bool]:
    """Return (list, key_present). Omit → (None, False). `[]` → ([], True)."""
    if not phase:
        return None, False
    yaml_path = safe_p / ".hermes" / "phase-dispatch.yaml"
    reader = (
        safe_p
        / ".hermes"
        / "skills"
        / "harness"
        / "dispatch-phase"
        / "scripts"
        / "read-phase-dispatch.py"
    )
    if not yaml_path.is_file() or not reader.is_file():
        return None, False
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(reader),
                "--yaml",
                str(yaml_path),
                "--phase",
                phase,
                "--print",
                "files_writable_json",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, False
    if proc.returncode != 0:
        return None, False
    raw = proc.stdout.strip()
    if raw in ("", "null"):
        return None, False
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, False
    if not isinstance(data, list):
        return None, False
    return [str(x) for x in data if str(x).strip()], True


def load_write_set(safe_p: Path) -> tuple[list[str] | None, str]:
    """Return (writable, source).

    writable is None when no kanban task is in play (deny-prefix only).
    writable is [] when a task is set but no card/yaml set is published
    (fail-closed on product writes). Dest JSON is never consulted.
    """
    env_fw = os.environ.get("HERMES_KANBAN_FILES_WRITABLE", "")
    parsed = parse_files_writable_env(env_fw)
    if parsed is not None:
        return parsed, "env:HERMES_KANBAN_FILES_WRITABLE"

    task = os.environ.get("HERMES_KANBAN_TASK", "").strip()
    if not task:
        return None, "unpublished"

    card, card_src = _writable_from_card_env()
    if card is not None:
        return card, card_src

    phase = _phase_id(safe_p, task)
    yaml_fw, present = _writable_from_phase_yaml(safe_p, phase)
    if present:
        return yaml_fw if yaml_fw is not None else [], f"phase-yaml:{phase}"
    return [], f"task-set-unresolved:{task}"


def extract_terminal_cmd(payload: dict) -> str:
    ti = payload.get("tool_input") or {}
    if not isinstance(ti, dict):
        return ""
    for k in ("command", "cmd"):
        v = ti.get(k)
        if isinstance(v, str) and v.strip():
            return v
    argv = ti.get("argv") or ti.get("args")
    if isinstance(argv, list):
        return " ".join(str(x) for x in argv)
    return ""


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
    # Item 4: matcher may invoke this hook on `terminal`. In-workspace
    # cache overwrite via argv is refused. Extra-workspace ($HOME) is not
    # claimed (hole 2).
    if writable is not None and str(tool).lower() in {"terminal", "bash", "shell"}:
        cmd = extract_terminal_cmd(payload).replace("\\", "/")
        if "evidence/runtime/write-sets" in cmd:
            return _block(
                "write-set-hook: terminal argv targets write-set cache "
                "(defense-in-depth, not a trust boundary)"
            )
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
