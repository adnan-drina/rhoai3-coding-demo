#!/usr/bin/env python3
"""Resolve which worker logs M4 must scan for fence evasion.

Operator E-20260825T105656ZO / Architect E-20260825T110118ZA: under an M4
card, HERMES_KANBAN_TASK is the verdict log. Scanning it is a silent pass.
Scan M1, M2, and every M3 story — parent-chain walk, or FENCE_EVASION_LOGS.

Stdout: one log path per line (the set that will be scanned).
Stderr: the set being scanned.
Exit 2: refuse (empty set, only self, missing ancestor log, show failed).
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from collections import deque
from pathlib import Path


def _log_home() -> Path:
    home = os.environ.get("HERMES_HOME") or "/projects/modernized/.hermes/home"
    return Path(home) / "kanban" / "logs"


def _self_id() -> str:
    return (os.environ.get("HERMES_KANBAN_TASK") or "").strip()


def _self_log() -> Path | None:
    sid = _self_id()
    if not sid:
        return None
    return _log_home() / ("%s.log" % sid)


def _split_list(raw: str) -> list[str]:
    out: list[str] = []
    for part in raw.replace("\n", ":").split(":"):
        part = part.strip()
        if part:
            out.append(part)
    return out


def _parent_ids(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return []
    task = payload
    if "parents" not in payload and "parent_ids" not in payload:
        for key in ("task", "item", "data"):
            inner = payload.get(key)
            if isinstance(inner, dict) and (
                "parents" in inner or "id" in inner or "parent_ids" in inner
            ):
                task = inner
                break
    parents = task.get("parents") or task.get("parent_ids") or []
    out: list[str] = []
    if not isinstance(parents, list):
        return out
    for item in parents:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            ident = item.get("id") or item.get("task_id")
            if ident:
                out.append(str(ident).strip())
    return out


def _show(task_id: str) -> dict:
    override = (os.environ.get("HERMES_KANBAN_SHOW") or "").strip()
    if override:
        cmd = shlex.split(override) + [task_id, "--json"]
    else:
        cmd = ["hermes", "kanban", "show", task_id, "--json"]
    try:
        proc = subprocess.run(
            cmd, check=False, capture_output=True, text=True
        )
    except OSError as exc:
        print(
            "resolve-m4-work-logs: REFUSE cannot exec kanban show %s: %s"
            % (cmd, exc),
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:400]
        print(
            "resolve-m4-work-logs: REFUSE kanban show %s rc=%s %s"
            % (task_id, proc.returncode, err),
            file=sys.stderr,
        )
        raise SystemExit(2)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        print(
            "resolve-m4-work-logs: REFUSE kanban show %s not JSON: %s"
            % (task_id, exc),
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    if not isinstance(data, dict):
        print(
            "resolve-m4-work-logs: REFUSE kanban show %s JSON is not an object"
            % task_id,
            file=sys.stderr,
        )
        raise SystemExit(2)
    return data


def _walk_ancestors(start_id: str) -> list[str]:
    seen = {start_id}
    queue: deque[str] = deque([start_id])
    ancestors: list[str] = []
    while queue:
        current = queue.popleft()
        for parent in _parent_ids(_show(current)):
            if parent in seen:
                continue
            seen.add(parent)
            ancestors.append(parent)
            queue.append(parent)
    return ancestors


def _finalize(paths: list[str]) -> list[str]:
    self_log = _self_log()
    self_resolved = self_log.resolve() if self_log is not None else None
    ordered: list[str] = []
    seen: set[str] = set()
    missing: list[str] = []
    dropped_self = False
    for raw in paths:
        path = Path(os.path.expandvars(os.path.expanduser(raw)))
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        key = str(resolved)
        if self_resolved is not None and resolved == self_resolved:
            dropped_self = True
            continue
        if key in seen:
            continue
        seen.add(key)
        if not path.is_file():
            missing.append(str(path))
            continue
        ordered.append(str(path))
    if missing:
        print(
            "resolve-m4-work-logs: REFUSE missing work log(s): %s"
            % ", ".join(missing),
            file=sys.stderr,
        )
        raise SystemExit(2)
    if not ordered:
        why = "empty after dropping this card's verdict log" if dropped_self else "empty"
        print(
            "resolve-m4-work-logs: REFUSE %s — scan M1/M2/M3 work logs, not M4"
            % why,
            file=sys.stderr,
        )
        raise SystemExit(2)
    print(
        "resolve-m4-work-logs: scanning %d work log(s):" % len(ordered),
        file=sys.stderr,
    )
    for item in ordered:
        print("  %s" % item, file=sys.stderr)
    return ordered


def resolve() -> list[str]:
    logs_env = (os.environ.get("FENCE_EVASION_LOGS") or "").strip()
    single = (os.environ.get("FENCE_EVASION_LOG") or "").strip()
    self_id = _self_id()

    if logs_env:
        return _finalize(_split_list(logs_env))

    if self_id:
        ancestors = _walk_ancestors(self_id)
        paths = [str(_log_home() / ("%s.log" % tid)) for tid in ancestors]
        if single:
            paths.append(single)
        if not ancestors and not single:
            print(
                "resolve-m4-work-logs: REFUSE %s has no parent work cards to scan"
                % self_id,
                file=sys.stderr,
            )
            raise SystemExit(2)
        return _finalize(paths)

    if single:
        return _finalize([single])

    print(
        "resolve-m4-work-logs: REFUSE silent skip — set FENCE_EVASION_LOGS "
        "or HERMES_KANBAN_TASK (walk parents) or FENCE_EVASION_LOG",
        file=sys.stderr,
    )
    raise SystemExit(2)


def main() -> int:
    for path in resolve():
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
