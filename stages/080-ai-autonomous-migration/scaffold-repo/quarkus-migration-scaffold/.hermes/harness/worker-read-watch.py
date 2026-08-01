#!/usr/bin/env python3
"""O-WORKERREAD / O-FIRSTMUT — exit 0 when worker is read/glob thrashing with no file mutate.

Poll 55 / S04 T-007: Qwen did 30 reads + 3 globs with no progress before wedge.
R-222 / S03 T-007: 23 reads + 2 bash + 0 edit/write — bash was wrongly counted as
a mutate, so the watch never fired and the session burned to JSON_STALE/TRUNCATION.
FIRST-mutate (N13): only edit/write count as mutates; bash/shell do not.

Usage: worker-read-watch.py <oc-T-NNN.json>
Exit 0 = kill worker; exit 1 = continue.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

READ_GLOBS_MAX = int(os.environ.get("WORKER_READ_GLOB_MAX", "20"))

READ_TOOLS = frozenset({"read", "read_file"})
GLOB_TOOLS = frozenset({"glob", "grep"})
# O-FIRSTMUT: file mutations only — bash/shell are not progress toward a commit.
MUTATE_TOOLS = frozenset({"edit", "write"})


def _events(raw: str) -> list:
    # OpenCode JSONL or a single JSON array / concatenated objects.
    evs = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, list):
            evs.extend(obj)
        else:
            evs.append(obj)
    if not evs:
        try:
            blob = json.loads(raw)
            if isinstance(blob, list):
                evs = blob
            elif isinstance(blob, dict):
                evs = [blob]
        except json.JSONDecodeError:
            pass
    return evs


def _tool_name(ev: dict) -> str:
    # OpenCode: {"type":"tool_use","part":{"type":"tool","tool":"read",...}}
    # Do NOT treat top-level/part "type" as the tool name (tool_use / tool).
    part = ev.get("part") or ev.get("message") or {}
    if isinstance(part, dict):
        t = part.get("tool") or part.get("name")
        if isinstance(t, str) and t.lower() not in ("tool", "tool_use", ""):
            return t.lower()
    for k in ("tool", "name"):
        v = ev.get(k)
        if isinstance(v, str) and v.lower() not in ("tool", "tool_use", ""):
            return v.lower()
    return ""


def _count_regex(raw: str) -> tuple[int, int, int]:
    reads = len(re.findall(r'"tool"\s*:\s*"(read|Read|read_file)"', raw))
    reads += len(re.findall(r'"name"\s*:\s*"(read|Read|read_file)"', raw))
    globs = len(re.findall(r'"tool"\s*:\s*"(glob|Glob|grep|Grep)"', raw, re.I))
    globs += len(re.findall(r'"name"\s*:\s*"(glob|Glob|grep|Grep)"', raw, re.I))
    mutates = len(re.findall(r'"tool"\s*:\s*"(edit|Edit|write|Write)"', raw))
    mutates += len(re.findall(r'"name"\s*:\s*"(edit|Edit|write|Write)"', raw))
    return reads, globs, mutates


def _count_events(evs: list) -> tuple[int, int, int]:
    reads = globs = mutates = 0
    for ev in evs:
        if not isinstance(ev, dict):
            continue
        name = _tool_name(ev)
        if not name:
            continue
        if name in READ_TOOLS:
            reads += 1
        elif name in GLOB_TOOLS:
            globs += 1
        elif name in MUTATE_TOOLS:
            mutates += 1
    return reads, globs, mutates


def main() -> int:
    if len(sys.argv) < 2:
        return 1
    p = Path(sys.argv[1])
    if not p.is_file() or p.stat().st_size < 200:
        return 1
    raw = p.read_text(encoding="utf-8", errors="replace")
    evs = _events(raw)
    if evs:
        reads, globs, mutates = _count_events(evs)
    else:
        reads, globs, mutates = _count_regex(raw)

    if reads + globs > READ_GLOBS_MAX and mutates == 0:
        print(f"read-thrash:reads={reads}:globs={globs}:mutates={mutates}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
