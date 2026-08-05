#!/usr/bin/env python3
"""O-EXECSCOPE — refuse M4 tips whose non-test paths fall outside story scope.

Reads staged paths from stdin (git diff --cached --name-only).
Exit 0 = ok; exit 1 = refuse (print violators).

Env:
  STORY_SCOPE — space-separated project-relative paths from the roadmap
Typed exceptions:
  - Ownstage / Target paths for this task (task-stage-paths.py)
  - pom.xml when the task body/Findings mention pom / datasource / O-DSKIND
  - scaffold .gitkeep / package-info.java under Shape=structure
  - src/test/** always free (characterization / unit pins)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


def _task_body(tasks: Path, tid: str) -> tuple[str, str]:
    text = tasks.read_text(encoding="utf-8", errors="replace")
    heads = list(
        re.finditer(r"^#{2,6}\s+(T[-A-Za-z0-9]*\d+[A-Za-z]*)\s*:\s*(.+)$", text, re.M)
    )
    for i, m in enumerate(heads):
        if m.group(1) != tid:
            continue
        title = m.group(2).strip()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        return title, text[m.end() : end]
    return "", ""


def _ownstage(tasks: Path, tid: str) -> set[str]:
    helper = Path(__file__).resolve().parent / "task-stage-paths.py"
    if not helper.is_file():
        return set()
    try:
        out = subprocess.check_output(
            [sys.executable, str(helper), str(tasks), tid],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, OSError):
        return set()
    return {ln.strip() for ln in out.splitlines() if ln.strip()}


def _in_scope(path: str, scope: set[str]) -> bool:
    if path in scope:
        return True
    # Directory-form scope entries (rare) cover children.
    for s in scope:
        if s.endswith("/") and path.startswith(s):
            return True
        if path.startswith(s.rstrip("/") + "/"):
            return True
    return False


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: exec-scope.py <tasks.md> <T-xxx> < staged-paths", file=sys.stderr)
        return 2
    tasks = Path(sys.argv[1])
    tid = sys.argv[2]
    scope_raw = os.environ.get("STORY_SCOPE", "").strip()
    scope = {e for e in scope_raw.split() if e.startswith("src/") or e in {"pom.xml"}}
    if not scope:
        # No path-form scope — informational only (matches scope_enforce skip).
        print("exec-scope:skip-no-path-scope")
        return 0

    title, body = _task_body(tasks, tid)
    blob = f"{title}\n{body}"
    own = _ownstage(tasks, tid)
    shape_m = re.search(r"(?im)^\*?\*?Shape\*?\*?\s*:?\s*(\w+)", body)
    shape = (shape_m.group(1).lower() if shape_m else "")
    pom_ok = bool(
        re.search(
            r"(?i)\bpom\.xml\b|quarkus-jdbc|datasource|hibernate-orm|O-DSKIND|"
            r"Findings:.*pom|javaee-pom|springboot-.*pom",
            blob,
        )
    )
    struct = shape == "structure" or bool(
        re.search(r"(?i)\.gitkeep|package structure|directory structure", blob)
    )

    staged = [ln.strip() for ln in sys.stdin if ln.strip()]
    viol: list[str] = []
    for p in staged:
        if p.startswith("src/test/"):
            continue
        if p.startswith(("migration/", ".hermes/", "specs/", "k8s/")):
            continue
        if p in {
            "migration/discovered.md",
            "migration/run-log.md",
            "migration/findings-delta.txt",
            "devfile.yaml",
        }:
            continue
        # Enforce non-test production surface only.
        if not (
            p.startswith("src/main/")
            or p == "pom.xml"
            or p.startswith("src/main/resources/")
        ):
            continue
        if _in_scope(p, scope) or p in own:
            continue
        if p == "pom.xml" and pom_ok:
            continue
        if struct and (
            p.endswith(".gitkeep")
            or p.endswith("package-info.java")
            or p.endswith(".properties")
        ):
            # Structure/config scaffold may create empty packages / profile props
            # named in Target even when roadmap scope lists class files only.
            if p in own or re.search(re.escape(p), blob) or p.endswith(".gitkeep"):
                continue
        viol.append(p)

    if viol:
        print("O-EXECSCOPE:" + ",".join(viol[:12]))
        return 1
    print("exec-scope:ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
