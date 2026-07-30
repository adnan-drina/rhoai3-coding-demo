#!/usr/bin/env python3
"""O-T6d — may the supervisor attach this task's T-NNN: message to the staged tree?

Exit 0 = staged paths match the task targets (safe mechan-commit).
Exit 1 = refuse mechan-commit (worker/escalation must do real work).

Reads staged paths from stdin (git diff --cached --name-only), one per line.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def _task_body_local(tasks_file: Path, tid: str) -> tuple[str, str]:
    """Task title/body with story-waiver appendices stripped (O-AC2)."""
    text = tasks_file.read_text(encoding="utf-8", errors="replace")
    heads = list(
        re.finditer(r"^#{2,6}\s+(T[-A-Za-z0-9]*\d+)\s*:\s*(.+)$", text, re.M)
    )
    for i, m in enumerate(heads):
        if m.group(1) != tid:
            continue
        title = m.group(2).strip()
        start = m.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[start:end]
        body = re.split(
            r"^##\s+(Story Scope Waivers|Waivers|Notes|Appendix)\b",
            body,
            maxsplit=1,
            flags=re.M | re.I,
        )[0]
        return title, body
    return "", ""


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: mechan-match.py <tasks.md> <T-xxx> < staged-paths", file=sys.stderr)
        return 2
    tasks = Path(sys.argv[1])
    tid = sys.argv[2]
    title, body = _task_body_local(tasks, tid)
    if not body and not title:
        print("no-task", file=sys.stderr)
        return 1

    staged = [
        ln.strip()
        for ln in sys.stdin.read().splitlines()
        if ln.strip()
        and not ln.strip().startswith(".hermes/")
        and not ln.strip().startswith("migration/staging/")
    ]
    if not staged:
        print("empty-stage")
        return 1

    blob = f"{title}\n{body}"
    wants_tests = bool(
        re.search(r"(?i)\bcharacterization\b|src/test/|DomainModelTest|\bunit tests?\b", blob)
    )
    if wants_tests:
        if any(p.startswith("src/test/") for p in staged):
            return 0
        print("need-src-test")
        return 1

    paths = re.findall(r"src/(?:main|test)/[A-Za-z0-9_./-]+\.java", body)
    if paths:
        for want in paths:
            for got in staged:
                if got == want or got.endswith("/" + Path(want).name):
                    return 0
        print("no-path-overlap")
        return 1

    # Soft tasks (package dirs, pom): allow src/ or pom.xml only.
    if all(p.startswith("src/") or p == "pom.xml" or p.startswith("k8s/") for p in staged):
        return 0
    print("unexpected-paths")
    return 1


if __name__ == "__main__":
    sys.exit(main())
