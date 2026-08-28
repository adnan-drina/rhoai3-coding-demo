#!/usr/bin/env python3
"""Static destfile checks for schemaVersion 2.2.2 (Dev Spaces 3.28 User Guide)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    ROOT
    / "gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/skeleton/devfile.yaml",
    ROOT
    / "gitops/stages/050-advanced-app-platform/base/rhdh/templates/agentic-quarkus-scaffold/skeleton/devfile.yaml",
    ROOT
    / "stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/devfile.yaml",
    ROOT
    / "stages/070-ai-agentic-development/scaffold-repo/agentic-quarkus-scaffold/devfile.yaml",
]


def fail(path: Path, msg: str) -> None:
    print(f"FAIL {path.relative_to(ROOT)}: {msg}", file=sys.stderr)


def main() -> int:
    rc = 0
    for path in FILES:
        if not path.is_file():
            fail(path, "missing")
            rc = 1
            continue
        text = path.read_text(encoding="utf-8")
        file_ok = True
        if "schemaVersion: 2.3.0" in text:
            fail(path, "schemaVersion 2.3.0 is destfile.io, not the 3.28 product pin")
            file_ok = False
        if "schemaVersion: 2.2.2" not in text:
            fail(path, "expected schemaVersion: 2.2.2")
            file_ok = False
        if "mountSources: true" not in text:
            fail(path, "missing mountSources: true")
            file_ok = False
        if "memoryRequest:" not in text:
            fail(path, "missing memoryRequest")
            file_ok = False
        if "cpuRequest:" not in text:
            fail(path, "missing cpuRequest")
            file_ok = False
        if "workingDir: /projects/modernized" in text:
            fail(
                path,
                "hardcoded /projects/modernized workingDir; use ${PROJECT_SOURCE} or ${PROJECTS_ROOT}",
            )
            file_ok = False
        if "quay.io/che-incubator/cli-ai-tools" in text:
            fail(path, "must not consume che-incubator/cli-ai-tools")
            file_ok = False
        if file_ok:
            print(f"OK {path.relative_to(ROOT)}")
        else:
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
