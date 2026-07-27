#!/usr/bin/env python3
"""Outer-loop roadmap parser (improvement B2): emits one shell-safe line
per story for the supervisor to iterate.

Usage: parse-roadmap.py <roadmap.md>
Output per story:  <sid>|<deploy>|<findings-or-none>|<scope-files>
(fields pipe-separated; findings comma-separated; scope space-separated)
"""
import re
import sys


def main():
    text = open(sys.argv[1], encoding="utf-8").read()
    heads = re.findall(r"^##\s+(S\d{2,})\s*:", text, re.M)
    parts = re.split(r"^##\s+(S\d{2,})\s*:.*$", text, flags=re.M)
    bodies = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}

    def field(sid, name):
        m = re.search(rf"^-\s*{name}:\s*(.+)$", bodies.get(sid, ""), re.M)
        return m.group(1).strip() if m else ""

    for sid in heads:
        deploy = "true" if field(sid, "deploy").lower() == "true" else "false"
        findings = ",".join(
            f for f in re.split(r"[,\s]+", field(sid, "findings"))
            if f and f != "-" and re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d+", f))
        scope = " ".join(
            s.strip().rstrip(",") for s in field(sid, "scope").split(",") if s.strip())
        print(f"{sid}|{deploy}|{findings or 'none'}|{scope}")


if __name__ == "__main__":
    sys.exit(main())
