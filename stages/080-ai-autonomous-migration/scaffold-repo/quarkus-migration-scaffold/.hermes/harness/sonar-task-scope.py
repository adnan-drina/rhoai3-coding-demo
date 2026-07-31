#!/usr/bin/env python3
"""O-SONARBLEED — filter sonar violations to the current task's owned paths.

Exit 0 and print `in-scope:N` when any violation touches task paths.
Exit 1 and print `bleed-only:N` when all violations are outside task scope
(prior-task Sonar debt — do not burn MiniMax sfix on them).

Usage: sonar-task-scope.py <tasks.md> <T-xxx> [/tmp/sonar-violations.txt]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def task_body(tasks_file: Path, tid: str) -> str:
    text = tasks_file.read_text(encoding="utf-8", errors="replace")
    heads = list(
        re.finditer(r"^#{2,6}\s+(T[-A-Za-z0-9]*\d+)\s*:\s*(.+)$", text, re.M)
    )
    for i, m in enumerate(heads):
        if m.group(1) != tid:
            continue
        start = m.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        return text[start:end]
    return ""


def owned_paths(body: str) -> set[str]:
    paths = set(
        re.findall(
            r"(?:src/(?:main|test)/[A-Za-z0-9_./-]+\.java|pom\.xml|"
            r"src/main/resources/[A-Za-z0-9_./-]+\.(?:properties|ya?ml))",
            body,
        )
    )
    for m in re.finditer(r"(?im)^\*?\*?(?:Owns|Absorbs|Target)\*?\*?\s*:?\s*(.+)$", body):
        for tok in re.split(r"[,;\s]+", m.group(1)):
            tok = tok.strip().strip("`")
            if tok.endswith(".java") or tok in ("pom.xml",) or "/" in tok:
                paths.add(tok)
    return paths


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: sonar-task-scope.py <tasks.md> <T-xxx> [violations.txt]", file=sys.stderr)
        return 2
    tasks = Path(sys.argv[1])
    tid = sys.argv[2]
    vfile = Path(sys.argv[3] if len(sys.argv) > 3 else "/tmp/sonar-violations.txt")
    body = task_body(tasks, tid)
    if not body:
        print("no-task")
        return 0  # fail-open: treat as in-scope unknown
    owned = owned_paths(body)
    if not owned:
        print("no-owns")
        return 0
    if not vfile.is_file():
        print("no-violations-file")
        return 0
    text = vfile.read_text(encoding="utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        print("in-scope:0")
        return 0
    in_scope = []
    bleed = []
    for ln in lines:
        hit = any(p in ln or Path(p).name in ln for p in owned)
        if hit:
            in_scope.append(ln)
        else:
            bleed.append(ln)
    if in_scope:
        print(f"in-scope:{len(in_scope)}")
        return 0
    print(f"bleed-only:{len(bleed)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
