#!/usr/bin/env python3
"""O-K5MILESCOPE — in-loop milestone findings scope = completed tasks only.

Post-commit milestone (every 3rd task / pom touch) must not fail K5 on MTA
rules owned by later tasks (e.g. pom native/metrics after DTO harvest T-001).

Prints comma-separated rule ids (stdout) for sensors.sh FINDINGS_SCOPE.
Preflight / milestone_sensor full still use full PLAN_SCOPE.

Usage: findings-milestone-scope.py <tasks.md> [run_base_sha]
Env: FINDINGS_MILESTONE_SCOPE_ROOT (repo root), PLAN_SCOPE (optional intersect)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


def task_findings(text: str, tid: str) -> list[str]:
    heads = list(re.finditer(r"^#{2,6}\s+(T[-A-Za-z0-9]*\d+)\s*:\s*(.+)$", text, re.M))
    body = ""
    for i, m in enumerate(heads):
        if m.group(1) != tid:
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[m.end() : end]
        break
    if not body:
        return []
    ids: list[str] = []
    for m in re.finditer(r"(?im)^\s*-?\s*\*\*Findings\*\*:\s*(.+)$", body):
        ids.extend(re.findall(r"[a-z][a-z0-9_-]*-\d+", m.group(1), re.I))
    return list(dict.fromkeys(ids))


def completed_task_ids(root: Path, run_base: str) -> list[str]:
    if not run_base:
        run_base = "HEAD"
    try:
        subprocess.run(
            ["git", "rev-parse", "--verify", f"{run_base}^{{commit}}"],
            cwd=root,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        run_base = "HEAD"
    # O-RESUMEBASEEXCL: include tip at RUN_BASE (same as supervisor committed()).
    rev_range = f"{run_base}..HEAD"
    out_exclusive = subprocess.check_output(
        ["git", "log", "--format=%s", rev_range],
        cwd=root,
        text=True,
        errors="replace",
    )
    out_base = subprocess.check_output(
        ["git", "log", "--format=%s", "-1", run_base],
        cwd=root,
        text=True,
        errors="replace",
    )
    subjects = (out_exclusive + "\n" + out_base).splitlines()
    seen: list[str] = []
    for subj in subjects:
        m = re.match(r"^(T[-A-Za-z0-9]*\d+)\s*:", subj.strip())
        if m and m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "usage: findings-milestone-scope.py <tasks.md> [run_base_sha]",
            file=sys.stderr,
        )
        return 2
    tasks_path = Path(sys.argv[1])
    run_base = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
    root = Path(os.environ.get("FINDINGS_MILESTONE_SCOPE_ROOT", ".")).resolve()
    if not tasks_path.is_file():
        return 0
    text = tasks_path.read_text(encoding="utf-8", errors="replace")
    tids = completed_task_ids(root, run_base)
    scope: list[str] = []
    for tid in tids:
        scope.extend(task_findings(text, tid))
    scope = list(dict.fromkeys(scope))
    plan = os.environ.get("PLAN_SCOPE", "").strip()
    if plan:
        plan_set = {s.strip() for s in re.split(r"[\s,]+", plan) if s.strip()}
        scope = [s for s in scope if s in plan_set]
    if scope:
        print(",".join(scope))
    return 0


if __name__ == "__main__":
    sys.exit(main())
