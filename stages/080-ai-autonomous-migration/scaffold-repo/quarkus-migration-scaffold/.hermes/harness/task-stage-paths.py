#!/usr/bin/env python3
"""O-OWNSTAGE — emit stageable Owns/Target paths for a task (one per line).

Used by supervisor stage_for_task_commit to allowlist-stage instead of
`git add -A`, so sibling entities stay untracked for their owning tip.

Exit 0 always when the task is found (even with zero paths — caller falls
back). Exit 1 if the task id is missing from tasks.md.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_JAVA = re.compile(r"src/(?:main|test)/[A-Za-z0-9_./-]+\.java")
_SHARED = re.compile(
    r"(?<![\w./])(?:pom\.xml|"
    r"src/(?:main|test)/resources/[A-Za-z0-9_./-]+\.(?:properties|ya?ml|xml)|"
    r"k8s/[A-Za-z0-9_./-]+)"
)
_CLAIM = re.compile(
    r"(?i)(?:^\s*\*?\*?(?:Owns|Target\s*design|Target|Design|Absorbs)\*?\*?\s*:)"
    r"|(?:→|->)\s*`?(?:src/|pom\.xml|k8s/)"
)
_OOS = re.compile(
    r"(?i)(?:^\s*\*?\*?Out of scope\*?\*?\s*:)"
    r"|(?:\bdo NOT touch\b)"
    r"|(?:\bowned by T[-A-Za-z0-9]*\d+)"
)
_STAGING = re.compile(r"(?:^|/)(?:migration/staging|legacy)(?:/|$)")


def _task_body(tasks_file: Path, tid: str) -> str:
    text = tasks_file.read_text(encoding="utf-8", errors="replace")
    heads = list(
        re.finditer(r"^#{2,6}\s+(T[-A-Za-z0-9]*\d+)\s*:\s*(.+)$", text, re.M)
    )
    for i, m in enumerate(heads):
        if m.group(1) != tid:
            continue
        start = m.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[start:end]
        body = re.split(r"^##\s+", body, maxsplit=1, flags=re.M)[0]
        return body
    return ""


def stage_paths(body: str) -> list[str]:
    """Declared Owns/Target/Absorbs paths that may land in a T-NNN tip."""
    out: list[str] = []
    seen: set[str] = set()

    def _add(p: str) -> None:
        p = p.strip().strip("`").rstrip(",")
        if not p or _STAGING.search(p):
            return
        if p in seen:
            return
        # Basenames alone are not stageable without a tree path.
        if "/" not in p and p != "pom.xml":
            return
        seen.add(p)
        out.append(p)

    for label in ("Owns", "Target design", "Target", "Design", "Absorbs"):
        for m in re.finditer(
            rf"^\*?\*?{re.escape(label)}\*?\*?\s*:?\s*(.+)$",
            body,
            re.M | re.I,
        ):
            line = m.group(1)
            if _OOS.search(line):
                continue
            for tok in re.split(r"[,;\s]+", line.strip()):
                tok = tok.strip().strip("`")
                if tok.startswith("src/") or tok == "pom.xml" or tok.startswith("k8s/"):
                    _add(tok)
            for p in _JAVA.findall(line):
                _add(p)
            for p in _SHARED.findall(line):
                _add(p)

    for line in body.splitlines():
        if _OOS.search(line):
            continue
        if not _CLAIM.search(line):
            continue
        for p in _JAVA.findall(line):
            _add(p)
        for p in _SHARED.findall(line):
            _add(p)
        # structure: …/.gitkeep (may not match _JAVA if written without backslash)
        for p in re.findall(r"src/(?:main|test)/[A-Za-z0-9_./-]+/\.gitkeep", line):
            _add(p)

    return out


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: task-stage-paths.py <tasks.md> <T-NNN>", file=sys.stderr)
        return 2
    tasks = Path(sys.argv[1])
    tid = sys.argv[2].strip()
    # Accept "T-004 sensor fix" / "T-004:" forms from callers.
    m = re.match(r"(T[-A-Za-z0-9]*\d+)", tid)
    if m:
        tid = m.group(1)
    if not tasks.is_file():
        print("no-tasks-file", file=sys.stderr)
        return 1
    body = _task_body(tasks, tid)
    if not body:
        print("no-task", file=sys.stderr)
        return 1
    for p in stage_paths(body):
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
