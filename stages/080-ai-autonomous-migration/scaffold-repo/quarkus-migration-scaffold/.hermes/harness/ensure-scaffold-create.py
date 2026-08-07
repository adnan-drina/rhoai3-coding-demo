#!/usr/bin/env python3
"""O-SCAFFOLDREADY — mechanical create for package-info / .gitkeep Targets.

Architecture
------------
O-HARVESTREADY makes *harvested* Java tip-ready (content + classpath).
Scaffold/create tasks are a different class: Targets are documentation or
directory anchors (``package-info.java``, ``.gitkeep``) with Oracle:absent
and often **no staging file**. Burning Qwen→MiniMax for a five-line
package-info (Wave5 S01-T-008) is a harness defect.

This ensurer runs for every task before O-T6:

1. Read Owns/Target paths via task-stage-paths (same allowlist as OWNSTAGE).
2. For each missing ``package-info.java``: harvest-from-staging if present,
   else synthesize a minimal Javadoc + ``package <from-path>;``.
3. For each missing ``.gitkeep``: create parent dirs + empty file.

Then supervisor ``try_mechan_commit`` can tip without a model seat.
Migration-general — no specimen package names beyond path→package derivation.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[3] if len(sys.argv) > 3 else ".")
TASKS = Path(sys.argv[1]) if len(sys.argv) > 1 else None
TID = sys.argv[2] if len(sys.argv) > 2 else ""
HARNESS = Path(__file__).resolve().parent


def _owned_paths(tasks: Path, tid: str) -> list[str]:
    helper = HARNESS / "task-stage-paths.py"
    if not helper.is_file() or not tasks.is_file():
        return []
    try:
        out = subprocess.check_output(
            [sys.executable, str(helper), str(tasks), tid],
            text=True,
            stderr=subprocess.DEVNULL,
            cwd=str(ROOT),
        )
    except (subprocess.CalledProcessError, OSError):
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def _pkg_from_path(rel: str) -> str:
    # src/main/java/com/demo/model/package-info.java → com.demo.model
    m = re.match(
        r"src/(?:main|test)/java/(.+)/package-info\.java$", rel.replace("\\", "/")
    )
    if not m:
        return "com.demo"
    return m.group(1).replace("/", ".")


def _synth_package_info(rel: str) -> str:
    pkg = _pkg_from_path(rel)
    return (
        "/**\n"
        f" * Package {pkg} — migrated types (harness scaffold create).\n"
        " */\n"
        f"package {pkg};\n"
    )


def _try_harvest(rel: str) -> bool:
    script = (
        ROOT
        / ".hermes"
        / "skills"
        / "migration-harness"
        / "scripts"
        / "harvest-from-staging.sh"
    )
    if not script.is_file():
        return False
    # package-relative under java tree, e.g. model/package-info.java
    m = re.match(
        r"src/(?:main|test)/java/(.+)$", rel.replace("\\", "/")
    )
    if not m:
        return False
    rel_java = m.group(1)
    try:
        proc = subprocess.run(
            ["bash", str(script), rel_java],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and (ROOT / rel).is_file()


def main() -> int:
    if not TASKS or not TID:
        print("usage: ensure-scaffold-create.py <tasks.md> <T-id> [root]", file=sys.stderr)
        return 2
    notes: list[str] = []
    for rel in _owned_paths(TASKS, TID):
        if rel == "pom.xml" or rel.startswith("k8s/"):
            continue
        dest = ROOT / rel
        if dest.is_file():
            continue
        if rel.endswith("package-info.java"):
            dest.parent.mkdir(parents=True, exist_ok=True)
            if _try_harvest(rel):
                notes.append(f"harvested:{rel}")
            else:
                dest.write_text(_synth_package_info(rel), encoding="utf-8")
                notes.append(f"synth:{rel}")
        elif rel.endswith("/.gitkeep") or rel.endswith(".gitkeep"):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("", encoding="utf-8")
            notes.append(f"gitkeep:{rel}")
    if not notes:
        print("skip:nothing")
        return 0
    print("ok:" + ",".join(notes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
