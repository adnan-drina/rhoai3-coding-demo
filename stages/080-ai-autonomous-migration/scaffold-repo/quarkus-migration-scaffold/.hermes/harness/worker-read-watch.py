#!/usr/bin/env python3
"""O-WORKERREAD / O-FIRSTMUT / O-FIRSTMUTBASH / O-SFIXMUTATE / O-TASKMUTATE — exit 0 when thrashing.

Poll 55 / S04 T-007: Qwen did 30 reads + 3 globs with no progress before wedge.
R-222 / S03 T-007: 23 reads + 2 bash + 0 edit/write — bash was wrongly counted as
a mutate, so the watch never fired and the session burned to JSON_STALE/TRUNCATION.
FIRST-mutate (N13 / O-FIRSTMUT): plain bash/shell do NOT count as mutates.

O-FIRSTMUTBASH (S03 T-002): bash that runs harvest-from-staging.sh and lands a
Target (stdout `harvested: … -> …`) IS a first mutate. Counting those as 0
caused false READ_THRASH → MiniMax after a correct harvest-first seat.

O-SFIXMUTATE / O-TASKMUTATE (ARCH-C1): seats that freeze with 0 edit/write
(sfix diagnose-freeze, or M4 task seats that never first-write). Set
WORKER_MUTATE_DEADLINE_SECS (e.g. 120 — aligned with M3 stall abort) so a
seat with tool activity and zero mutates past the deadline is killed early
for rescue/escalate. Supervisor wires this for both *sfix* and M4 task seats.

Usage: worker-read-watch.py <oc-T-NNN.json> [elapsed_secs]
Exit 0 = kill worker; exit 1 = continue.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

READ_GLOBS_MAX = int(os.environ.get("WORKER_READ_GLOB_MAX", "20"))
# 0 = disabled. Supervisor sets e.g. 120 for sfix and M4 task seats.
MUTATE_DEADLINE_SECS = int(os.environ.get("WORKER_MUTATE_DEADLINE_SECS", "0"))
# Minimum tool events before deadline kill (avoid killing during prompt load).
MUTATE_DEADLINE_MIN_EVENTS = int(os.environ.get("WORKER_MUTATE_DEADLINE_MIN_EVENTS", "3"))

READ_TOOLS = frozenset({"read", "read_file"})
GLOB_TOOLS = frozenset({"glob", "grep"})
# O-FIRSTMUT: edit/write only — plain bash/shell are not progress.
MUTATE_TOOLS = frozenset({"edit", "write"})
BASH_TOOLS = frozenset({"bash", "shell"})
# O-FIRSTMUTBASH: harvest script invocation (command) + success marker (stdout).
HARVEST_CMD_RE = re.compile(r"harvest-from-staging\.sh\b")
HARVEST_OK_RE = re.compile(r"harvested:\s+\S+\s+->\s+\S+")


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


def _part(ev: dict) -> dict:
    part = ev.get("part") or ev.get("message") or {}
    return part if isinstance(part, dict) else {}


def _bash_command(ev: dict) -> str:
    part = _part(ev)
    state = part.get("state") if isinstance(part.get("state"), dict) else {}
    inp = state.get("input") or part.get("input") or ev.get("input") or {}
    if isinstance(inp, dict):
        cmd = inp.get("command") or inp.get("cmd") or inp.get("script") or ""
        return cmd if isinstance(cmd, str) else str(cmd)
    if isinstance(inp, str):
        return inp
    return ""


def _bash_output(ev: dict) -> str:
    part = _part(ev)
    state = part.get("state") if isinstance(part.get("state"), dict) else {}
    out = state.get("output") or part.get("output") or ev.get("output") or ""
    if isinstance(out, dict):
        out = out.get("output") or out.get("stdout") or ""
    return out if isinstance(out, str) else str(out)


def _is_harvest_mutate(ev: dict) -> bool:
    """O-FIRSTMUTBASH: bash harvest that landed a Target counts as mutate."""
    cmd = _bash_command(ev)
    out = _bash_output(ev)
    if not HARVEST_CMD_RE.search(cmd):
        return False
    # Prefer success marker; also accept command-only when output absent yet
    # (in-flight tool_use) so the watch does not thrash-kill mid-harvest.
    if out.strip():
        return bool(HARVEST_OK_RE.search(out))
    return True


def _count_regex(raw: str) -> tuple[int, int, int]:
    reads = len(re.findall(r'"tool"\s*:\s*"(read|Read|read_file)"', raw))
    reads += len(re.findall(r'"name"\s*:\s*"(read|Read|read_file)"', raw))
    globs = len(re.findall(r'"tool"\s*:\s*"(glob|Glob|grep|Grep)"', raw, re.I))
    globs += len(re.findall(r'"name"\s*:\s*"(glob|Glob|grep|Grep)"', raw, re.I))
    mutates = len(re.findall(r'"tool"\s*:\s*"(edit|Edit|write|Write)"', raw))
    mutates += len(re.findall(r'"name"\s*:\s*"(edit|Edit|write|Write)"', raw))
    # O-FIRSTMUTBASH regex fallback: successful harvest stdout marker.
    mutates += len(HARVEST_OK_RE.findall(raw))
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
        elif name in BASH_TOOLS and _is_harvest_mutate(ev):
            mutates += 1
    return reads, globs, mutates


def _event_count(evs: list, raw: str) -> int:
    if evs:
        return len(evs)
    # Regex fallback: rough tool_use / tool markers
    return len(re.findall(r'"tool"\s*:\s*"', raw)) + len(
        re.findall(r'"type"\s*:\s*"tool_use"', raw)
    )


def main() -> int:
    if len(sys.argv) < 2:
        return 1
    p = Path(sys.argv[1])
    if not p.is_file() or p.stat().st_size < 200:
        return 1
    elapsed = 0
    if len(sys.argv) >= 3:
        try:
            elapsed = int(sys.argv[2])
        except ValueError:
            elapsed = 0
    raw = p.read_text(encoding="utf-8", errors="replace")
    evs = _events(raw)
    if evs:
        reads, globs, mutates = _count_events(evs)
    else:
        reads, globs, mutates = _count_regex(raw)

    if reads + globs > READ_GLOBS_MAX and mutates == 0:
        print(f"read-thrash:reads={reads}:globs={globs}:mutates={mutates}")
        return 0

    # O-SFIXMUTATE / O-TASKMUTATE: activity without any edit/write past the
    # deadline → early abort so rescue/escalate can own the seat.
    if (
        MUTATE_DEADLINE_SECS > 0
        and elapsed >= MUTATE_DEADLINE_SECS
        and mutates == 0
        and _event_count(evs, raw) >= MUTATE_DEADLINE_MIN_EVENTS
    ):
        n_ev = _event_count(evs, raw)
        # Keep sfix-mutate-deadline token for O-SFIXMUTATE instruments; also
        # emit mutate-deadline for ARCH-C1 / O-TASKMUTATE greps.
        print(
            f"mutate-deadline:sfix-mutate-deadline:elapsed={elapsed}:events={n_ev}"
            f":reads={reads}:globs={globs}:mutates={mutates}"
        )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
