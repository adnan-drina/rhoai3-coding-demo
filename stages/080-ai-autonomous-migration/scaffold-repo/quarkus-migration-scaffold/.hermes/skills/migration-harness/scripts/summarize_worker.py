#!/usr/bin/env python3
"""Summarize an OpenCode worker JSON event stream without printing it.

Usage: summarize_worker.py /tmp/oc-task.json
Prints tool-call count, error events, and the final text tail.
"""
import json, sys

texts, tools, errors = [], [], []
for line in open(sys.argv[1]):
    line = line.strip()
    if not line:
        continue
    try:
        ev = json.loads(line)
    except ValueError:
        continue
    t = ev.get("type")
    p = ev.get("part", ev)
    if t == "text":
        txt = ev.get("text") or p.get("text", "")
        if txt: texts.append(txt)
    elif t in ("tool", "tool_use"):
        tools.append(str(p.get("tool") or p.get("name") or "?"))
    elif t == "error":
        errors.append(json.dumps(ev.get("error", ev))[:200])

print("tool calls:", len(tools))
if errors:
    print("ERRORS:")
    for e in errors: print(" ", e)
print("final text:", " ".join(texts)[-600:])
