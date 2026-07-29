#!/usr/bin/env python3
"""Build an OpenCode task packet from tasks.md (V7 model routing).

Prints a single packet string on stdout for:
  opencode run "<packet>" -m <worker> ...

Used by supervisor.sh so mechanical rewrite/infer coding runs on the
worker (Qwen) without MiniMax applying file edits directly.
"""
from __future__ import annotations

import re
import sys


def task_block(text: str, tid: str) -> tuple[str, str]:
    heads = list(
        re.finditer(r"^#{2,6}\s+(T[-A-Za-z0-9]*\d+)\s*:\s*(.+)$", text, re.M)
    )
    for i, m in enumerate(heads):
        if m.group(1) != tid:
            continue
        title = m.group(2).strip()
        start = m.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        return title, text[start:end].strip()
    return "", ""


def field(body: str, *names: str) -> str:
    for name in names:
        m = re.search(
            rf"^\*\*{re.escape(name)}\*\*\s*:?\s*(.+)$",
            body,
            re.M | re.I,
        )
        if m:
            return m.group(1).strip()
        m = re.search(
            rf"^{re.escape(name)}\s*:\s*(.+)$",
            body,
            re.M | re.I,
        )
        if m:
            return m.group(1).strip()
    return ""


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: task-packet.py <tasks.md> <T-xxx> [worker-model]", file=sys.stderr)
        return 2
    path, tid = sys.argv[1], sys.argv[2]
    worker = sys.argv[3] if len(sys.argv) > 3 else "qwen27b/qwen3-6-27b"
    text = open(path, encoding="utf-8", errors="replace").read()
    title, body = task_block(text, tid)
    if not body:
        print(f"FATAL: task {tid} not found in {path}", file=sys.stderr)
        return 1
    cls = field(body, "Class", "Type") or "infer"
    cls_m = re.search(r"\b(rewrite|infer)\b", cls, re.I)
    cls = cls_m.group(1).lower() if cls_m else "infer"
    goal = field(body, "Goal") or title
    findings = field(body, "Findings") or "(see tasks.md)"
    acceptance = field(body, "Acceptance") or "mvn -q clean test passes; commit ready"
    # Keep packet bounded — full body is attached via -f tasks.md
    design = ""
    for label in ("Target design", "Target Design", "Target", "Design"):
        chunk = field(body, label)
        if chunk:
            design = chunk
            break
    if not design:
        # First 1200 chars of body as design context
        design = re.sub(r"\s+", " ", body)[:1200]

    packet = f"""Task ID: {tid}
Class: {cls}
Goal: {goal}
Findings: {findings}
Target Design: {design}
Constraints:
- Follow AGENTS.md and the repo skills; no scope creep
- Package rename is full legacyPackage → targetPackage prefix replace (never invent targetPackage.coolstore)
- For Class rewrite: use .hermes/skills/migration-harness/scripts/harvest-from-staging.sh for harvests; do not re-run OpenRewrite
- Worker model for this run is {worker}
Inputs: tasks.md (attached), AGENTS.md (attached), migration/staging when harvesting
Acceptance: {acceptance}
Out of scope: do not push; do not start other tasks; finish with changes ready for a commit whose message STARTS with '{tid}:'
"""
    print(packet.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
