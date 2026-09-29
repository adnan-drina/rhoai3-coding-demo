#!/usr/bin/env python3
"""K2 post_tool_call observer: positive execution evidence for terminal calls.

V17-6b. The official kanban log renders a terminal call as one line and
stamps ``[exit N]`` only when the tool result parses as JSON with a non-zero
``exit_code`` (pinned runtime agent/display.py ``_detect_tool_failure``); an
unmarked line therefore says nothing about success. v17 M4 t_4c09775b: the
reviewer's audit exited 1 twice and both lines are unmarked.

This observer runs after every terminal call (the Stage 050 producer copies
THIS FILE ALONE into Managed Scope and registers it as a ``post_tool_call``
shell hook, matcher ``terminal``; it therefore imports nothing from the
destination tree) and appends
one row to ``<kanban root>/kanban/logs/<task>.exec.jsonl``:

    {"phase": "end", "run", "profile", "task", "tool_call_id", "command",
     "command_sha256", "exit_code", "status", "output_tail", "output_sha256",
     "output_chars"}

paired by ``tool_call_id`` with the ``"phase": "start"`` row the K2 pre hook
writes for the same call before it runs.

``exit_code`` is read from the tool result the runtime hands the hook; a
result without one is recorded as ``null`` (unknown, never success). The
paved-road audit grades mandated commands from these rows, not from the
absence of a marker.

``output_tail`` is the last OUTPUT_TAIL characters of the result's output
(with its sha256 and full length), so a native retry can be told what a
repeated call already answered (V26-6 item 2) without re-running it.
Bounded on purpose: this is a pointer to what the worker saw, not a copy of
the session.

Observer only: it never blocks, never writes stdout, and a failure to record
leaves the row missing, which the audit reads as "no positive evidence".
Same integrity as the official log it sits beside (both live under the
worker's HERMES_HOME): this is process evidence for the audit, not
acceptance authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys


def kanban_root_home() -> str:
    """Official logs live under the base HERMES_HOME, not a profile home."""
    home = (os.environ.get("HERMES_HOME") or "").strip()
    if not home:
        return ""
    parent, name = os.path.split(home.rstrip("/"))
    root, profiles = os.path.split(parent)
    if profiles == "profiles" and name and root:
        return root
    return home


OUTPUT_TAIL = 800


def _result_doc(result):
    if isinstance(result, dict):
        return result
    try:
        doc = json.loads(result) if isinstance(result, str) else None
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def output_of(result) -> str | None:
    """The terminal output the call returned; None when the result carries none."""
    doc = _result_doc(result)
    if doc is not None:
        out = doc.get("output")
        return out if isinstance(out, str) else None
    return result if isinstance(result, str) else None


def exit_code_of(result) -> int | None:
    doc = _result_doc(result)
    if not isinstance(doc, dict):
        return None
    code = doc.get("exit_code")
    if isinstance(code, bool) or not isinstance(code, int):
        return None
    return code


def record(payload: dict) -> str:
    """Append this call's row; returns the ledger path ('' when not recorded)."""
    if str(payload.get("tool_name") or "") != "terminal":
        return ""
    task = (os.environ.get("HERMES_KANBAN_TASK") or "").strip()
    home = kanban_root_home()
    if not task or not home:
        return ""
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
    tin = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    command = str(tin.get("command") or "")
    row = {
        "schema": "rhoai3.exec-ledger/v1",
        "phase": "end",  # the K2 pre hook wrote this call's "start" row
        "run": (os.environ.get("HERMES_KANBAN_RUN_ID") or "").strip(),
        "profile": (os.environ.get("HERMES_PROFILE") or "").strip().lower(),
        "task": task,
        "tool_call_id": str(extra.get("tool_call_id") or ""),
        "command": command,
        "command_sha256": hashlib.sha256(command.encode("utf-8", errors="replace")).hexdigest(),
        "exit_code": exit_code_of(extra.get("result")),
        "status": str(extra.get("status") or ""),
    }
    out = output_of(extra.get("result"))
    if out is not None:
        row["output_tail"] = out[-OUTPUT_TAIL:]
        row["output_sha256"] = hashlib.sha256(out.encode("utf-8", errors="replace")).hexdigest()
        row["output_chars"] = len(out)
    path = os.path.join(home, "kanban", "logs", "%s.exec.jsonl" % task)
    line = (json.dumps(row, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line)  # one write per row: O_APPEND keeps concurrent rows whole
    finally:
        os.close(fd)
    return path


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if isinstance(payload, dict):
            record(payload)
    except Exception as exc:  # an observer never fails the tool call
        print("post_tool_call: not recorded (%s)" % type(exc).__name__, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
