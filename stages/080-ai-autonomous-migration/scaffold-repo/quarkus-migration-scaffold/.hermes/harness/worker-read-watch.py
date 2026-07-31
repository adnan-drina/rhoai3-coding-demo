#!/usr/bin/env python3
"""O-WORKERREAD — exit 0 when worker is read/glob thrashing with no mutate.

Poll 55 / S04 T-007: Qwen did 30 reads + 3 globs + 1 edit + 0 bash before
wedge. Kill early when reads+globs exceed the threshold and there is no
bash/edit/write progress.

Usage: worker-read-watch.py <oc-T-NNN.json>
Exit 0 = kill worker; exit 1 = continue.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

READ_GLOBS_MAX = int(__import__("os").environ.get("WORKER_READ_GLOB_MAX", "20"))


def _events(raw: str) -> list:
    # OpenCode JSONL or a single JSON array / concatenated objects.
    evs = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
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
    for k in ("tool", "name", "type"):
        v = ev.get(k)
        if isinstance(v, str) and v:
            return v.lower()
    part = ev.get("part") or ev.get("message") or {}
    if isinstance(part, dict):
        for k in ("tool", "name", "type"):
            v = part.get(k)
            if isinstance(v, str) and v:
                return v.lower()
    return ""


def main() -> int:
    if len(sys.argv) < 2:
        return 1
    p = Path(sys.argv[1])
    if not p.is_file() or p.stat().st_size < 200:
        return 1
    raw = p.read_text(encoding="utf-8", errors="replace")
    # Fast path: count tool-ish tokens even if JSONL is messy.
    reads = len(re.findall(r'"tool"\s*:\s*"(read|Read|read_file)"', raw))
    reads += len(re.findall(r'"name"\s*:\s*"(read|Read|read_file)"', raw))
    globs = len(re.findall(r'"tool"\s*:\s*"(glob|Glob|grep|Grep)"', raw, re.I))
    globs += len(re.findall(r'"name"\s*:\s*"(glob|Glob|grep|Grep)"', raw, re.I))
    mutates = len(
        re.findall(
            r'"tool"\s*:\s*"(edit|Edit|write|Write|bash|Bash|shell|Shell)"',
            raw,
            re.I,
        )
    )
    mutates += len(
        re.findall(
            r'"name"\s*:\s*"(edit|Edit|write|Write|bash|Bash|shell|Shell)"',
            raw,
            re.I,
        )
    )
    # Prefer structured counts when available.
    for ev in _events(raw):
        if not isinstance(ev, dict):
            continue
        name = _tool_name(ev)
        if not name:
            continue
        if name in ("read", "read_file"):
            reads += 1
        elif name in ("glob", "grep"):
            globs += 1
        elif name in ("edit", "write", "bash", "shell"):
            mutates += 1

    if reads + globs > READ_GLOBS_MAX and mutates == 0:
        print(f"read-thrash:reads={reads}:globs={globs}:mutates={mutates}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
