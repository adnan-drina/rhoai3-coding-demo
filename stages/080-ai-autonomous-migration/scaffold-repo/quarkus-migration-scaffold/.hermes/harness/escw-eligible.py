#!/usr/bin/env python3
"""O-ESCW3 — may the supervisor allow-empty "Already satisfied" for this task?

Exit 0 = eligible (noop commit OK when tree has no app dirt + task sensor GREEN).
Exit 1 = not eligible — worker/escalation must still produce deliverables.

V9 S03 T-008: O-ESCW allow-empty'd characterization after worker wrote nothing;
task sensor stays GREEN without tests. Characterization / missing Target .java
must never ESCW.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("ALREADY_COMPLETE_ROOT", ".")).resolve()


def task_body(tasks_file: Path, tid: str) -> tuple[str, str]:
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
        print("usage: escw-eligible.py <tasks.md> <T-xxx>", file=sys.stderr)
        return 2
    tasks = Path(sys.argv[1])
    tid = sys.argv[2]
    title, body = task_body(tasks, tid)
    if not title and not body:
        print("no-task")
        return 1

    blob = f"{title}\n{body}"
    wants_tests = bool(
        re.search(
            r"(?i)\bcharacterization\b|src/test/|DomainModelTest|\bunit tests?\b",
            blob,
        )
    )
    if wants_tests:
        tests = (
            list((ROOT / "src/test").rglob("*.java"))
            if (ROOT / "src/test").is_dir()
            else []
        )
        named = re.findall(r"src/test/[A-Za-z0-9_./-]+\.java", blob)
        if named:
            if all((ROOT / p).is_file() for p in named):
                print("tests-present")
                return 0
            print("need-src-test")
            return 1
        # Service-layer characterization must not ESCW on model-only tests (S02).
        if re.search(r"(?i)service layer|/service/|com\.demo\.service", blob):
            svc = [t for t in tests if "/service/" in str(t).replace("\\", "/")]
            if not svc:
                print("need-service-tests")
                return 1
            print("tests-present")
            return 0
        if not tests:
            print("need-src-test")
            return 1
        print("tests-present")
        return 0

    # Target destination .java files must exist for ESCW (conversion tasks).
    for want in re.findall(
        r"(?:Target|→|->)[^\n]*?(src/main/java/[A-Za-z0-9_./-]+\.java)", blob
    ):
        if not (ROOT / want).is_file():
            print(f"missing-target:{want}")
            return 1

    # Package-structure: need .gitkeep or any file in the named directory.
    if re.search(r"(?i)package structure|empty package", blob):
        dirs = re.findall(r"src/(?:main|test)/java/[A-Za-z0-9_./-]+/", blob)
        for d in dirs:
            p = ROOT / d.rstrip("/")
            if not p.is_dir():
                print(f"missing-pkgdir:{d}")
                return 1
            if not any(p.iterdir()):
                print(f"empty-pkgdir:{d}")
                return 1

    print("eligible")
    return 0


if __name__ == "__main__":
    sys.exit(main())
