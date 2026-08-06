#!/usr/bin/env python3
"""OpenCode / session JSONL forensics (tool counts, tokens, text snippets).

Usage:
  python3 qwenscan.py /tmp/outer-m1-profile-prose.log
  python3 qwenscan.py /tmp/profile-classify-Unit.jsonl
"""
from __future__ import annotations

import collections
import json
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <jsonl-or-log>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    evs = []
    for line in open(path, errors="replace", encoding="utf-8"):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            evs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    print(collections.Counter(e.get("type") for e in evs))
    tools: collections.Counter = collections.Counter()
    toks = []
    for e in evs:
        p = e.get("part") or {}
        st = p.get("state") if isinstance(p.get("state"), dict) else {}
        if p.get("tool"):
            tools[p["tool"]] += 1
            inp = st.get("input") or {}
            print(
                "tool %-6s %s"
                % (
                    p["tool"],
                    str(inp.get("filePath") or inp.get("command") or "")[:90],
                )
            )
        if p.get("type") == "step-finish" and p.get("tokens"):
            toks.append(p["tokens"])
        if p.get("type") == "text" and (p.get("text") or "").strip():
            print("text %s" % p["text"][:200].replace("\n", " | "))
    print(tools)
    for i, t in enumerate(toks, 1):
        print(
            "step=%d input=%d output=%d"
            % (i, t.get("input", 0), t.get("output", 0))
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
