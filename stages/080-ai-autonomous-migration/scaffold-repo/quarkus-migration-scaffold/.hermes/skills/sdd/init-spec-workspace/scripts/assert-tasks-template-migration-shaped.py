#!/usr/bin/env python3
"""Fail if the tasks template is stock Spec Kit or emits directory tasks.

Architect 102851ZA: T001 Create project structure / T002 directory
structure induce K4_PLANNING_DEFECT (directories are not files_writable).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ASSET = (
    Path(__file__).resolve().parents[1] / "assets" / "tasks-template.md"
)

STOCK = (
    "Create project structure",
    "Initialize [language] project",
    "Setup database schema",
    "Implement authentication/authorization",
    "Setup API routing and middleware",
    "Create source directory structure",
)

# Checklist line whose only dest paths are directories (trailing / or
# "com/demo/" with no filename).
DIR_TASK = re.compile(
    r"(?im)^- \[[ x]\] T\d+.*(?:directory structure|"
    r"src/main/java/[\w./]+/\s+and\s+src/test/java/)"
)


def main() -> int:
    if not ASSET.is_file():
        print("FAIL: missing %s" % ASSET, file=sys.stderr)
        return 1
    text = ASSET.read_text(encoding="utf-8")
    bad = 0
    for needle in STOCK:
        if needle in text:
            print("FAIL: stock Spec Kit placeholder: %s" % needle, file=sys.stderr)
            bad = 1
    if DIR_TASK.search(text):
        print(
            "FAIL: directory-only task (K4_PLANNING_DEFECT): %s"
            % DIR_TASK.search(text).group(0)[:120],
            file=sys.stderr,
        )
        bad = 1
    if "K4_PLANNING_DEFECT" not in text:
        print(
            "FAIL: template must name K4_PLANNING_DEFECT next to directory rule",
            file=sys.stderr,
        )
        bad = 1
    if bad:
        return 1
    print("OK: tasks-template.md is migration-shaped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
