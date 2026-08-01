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

    # Harness bookkeeping often dirties the tree (ensure_discovered, run-log).
    # Ignore like .hermes/staging — Wave2 T-001: discovered.md alone caused
    # unexpected-paths on an otherwise valid .gitkeep scaffold (O-SCAFFOLDDIR).
    _ignore_prefixes = (
        ".hermes/",
        "migration/staging/",
    )
    _ignore_exact = {
        "migration/discovered.md",
        "migration/run-log.md",
        "migration/mta-findings-current.json",
        "migration/mta-findings-after.json",
        "migration/findings-delta.txt",
        "migration/mta-findings.json",
    }
    _ignore_prefixes = _ignore_prefixes + (
        "migration/mta-findings-",
    )

    staged = []
    for ln in sys.stdin.read().splitlines():
        p = ln.strip()
        if not p:
            continue
        if any(p.startswith(pref) for pref in _ignore_prefixes):
            continue
        if p in _ignore_exact:
            continue
        staged.append(p)

    blob = f"{title}\n{body}"
    paths = re.findall(r"src/(?:main|test)/[A-Za-z0-9_./-]+\.java", blob)
    # O-ACCREATE: Create/Add/… titles never use removal-already-absent (Wave2
    # T-009: body said "EntityUtils removal" while the work is Create *Test).
    create_task = bool(
        re.search(
            r"(?i)^\s*(Create|Add|Implement|Write|Author|Introduce|Build)\b",
            title,
        )
    )
    # O-T6DREMOVAL (R-104/Wave2 T-005): removal/refactor tasks whose Target
    # path is already absent are satisfied with an empty stage — O-T6d's
    # "path overlap" assumption is for create/modify harvests, not absences.
    removal_task = (not create_task) and bool(
        re.search(r"(?i)\bremoved?\b|\bremoval\b|\bdelet(?:e|ion)\b|\brefactored\b", blob)
    )
    if removal_task and paths and all(not Path(w).exists() for w in paths):
        # Ignore harness bookkeeping dirt — absence of the target is the work.
        print("removal-already-absent")
        return 0

    if not staged:
        print("empty-stage")
        return 1

    wants_tests = bool(
        re.search(
            r"(?i)\bcharacterization\b|src/test/|DomainModelTest|"
            r"\bunit tests?\b|\bintegration tests?\b",
            blob,
        )
    )
    if wants_tests:
        if any(p.startswith("src/test/") for p in staged):
            return 0
        print("need-src-test")
        return 1

    if paths:
        for want in paths:
            for got in staged:
                if got == want or got.endswith("/" + Path(want).name):
                    return 0
        # Deletion staged as the target path also counts (git rm / deleted).
        if removal_task and any(
            got == want or got.endswith("/" + Path(want).name)
            for want in paths
            for got in staged
        ):
            return 0
        print("no-path-overlap")
        return 1

    # O-SCAFFOLDDIR / O-STRUCTINFO: directory-scaffold tasks accept .gitkeep
    # and package-info.java under src/{main,test}/java/ (T-001 allows either
    # for commitability). Do NOT classify package-info *content* tasks as
    # structure-only — "com.demo package structure" in T-003 Target design
    # previously tripped structure-non-gitkeep on real package-info.java
    # (Wave2 wake17) and forced MiniMax after a successful Qwen write.
    package_info_task = bool(re.search(r"(?i)package-info", title))
    structure_task = (not package_info_task) and bool(
        re.search(
            r"(?i)directory structure|(?<![\w-])package structure|\.gitkeep|empty package|package director",
            blob,
        )
    )
    if structure_task:
        def _scaffold_ok(p: str) -> bool:
            return (
                p.endswith("/.gitkeep")
                or p.endswith(".gitkeep")
                or p.endswith("/package-info.java")
                or p.endswith("package-info.java")
                or p == "pom.xml"
                or p.startswith("k8s/")
            )

        bad = [p for p in staged if not _scaffold_ok(p)]
        if not bad and all(
            p.startswith("src/main/java/")
            or p.startswith("src/test/java/")
            or p == "pom.xml"
            or p.startswith("k8s/")
            for p in staged
        ):
            return 0
        if bad:
            print("structure-non-gitkeep")
            return 1

    # Soft tasks (package dirs, pom, package-info): allow src/ or pom.xml only.
    if all(p.startswith("src/") or p == "pom.xml" or p.startswith("k8s/") for p in staged):
        return 0
    print("unexpected-paths")
    return 1


if __name__ == "__main__":
    sys.exit(main())
