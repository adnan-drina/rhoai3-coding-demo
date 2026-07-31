#!/usr/bin/env python3
"""O-HARVESTSTALL — mechan pre-seed missing Target .java from migration/staging.

For rewrite tasks whose Target design names destination .java paths that are
still absent, run harvest-from-staging.sh so the worker is not stuck with a
clean tree inventing G-PLACE stubs (S05 T-001).

Exit 0 always (best-effort). Prints `seeded:<path>` lines for each harvest.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(os.environ.get("PRESEED_ROOT", ".")).resolve()
HARVEST = ROOT / ".hermes/skills/migration-harness/scripts/harvest-from-staging.sh"


def task_body(tasks_file: Path, tid: str) -> tuple[str, str, str]:
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
        cls_m = re.search(r"(?im)^\*?\*?Class\*?\*?\s*:\s*(\w+)", body)
        cls = (cls_m.group(1) if cls_m else "").lower()
        return title, body, cls
    return "", "", ""


def target_java_paths(body: str) -> list[str]:
    paths: list[str] = []
    for line in body.splitlines():
        if not re.search(r"(?:Target|→|->)", line, re.I):
            continue
        paths.extend(
            re.findall(r"src/(?:main|test)/java/[A-Za-z0-9_./]+\.java", line)
        )
    return [p for p in paths if "migration/staging" not in p and "/legacy/" not in p]


def package_rel(path: str, tgt_slash: str) -> Optional[str]:
    """src/{main|test}/java/<tgtPackage>/X.java → X.java relative to package."""
    m = re.match(
        rf"src/(?:main|test)/java/{re.escape(tgt_slash)}/(.+\.java)$", path
    )
    if m:
        return m.group(1)
    # Also allow legacy package path in Target (brief sometimes cites it).
    return None


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: preseed-targets.py <tasks.md> <T-xxx>", file=sys.stderr)
        return 2
    tasks = Path(sys.argv[1])
    tid = sys.argv[2]
    _title, body, cls = task_body(tasks, tid)
    if cls and cls != "rewrite":
        return 0
    if not HARVEST.is_file():
        print("no-harvest-script", file=sys.stderr)
        return 0

    myaml = ROOT / "migration.yaml"
    if not myaml.is_file():
        return 0
    text = myaml.read_text(encoding="utf-8", errors="replace")
    tgt_m = re.search(r"(?m)^\s*targetPackage:\s*(\S+)", text)
    leg_m = re.search(r"(?m)^\s*legacyPackage:\s*(\S+)", text)
    if not tgt_m or not leg_m:
        return 0
    tgt = tgt_m.group(1)
    leg = leg_m.group(1)
    tgt_slash = tgt.replace(".", "/")
    leg_slash = leg.replace(".", "/")

    seeded = 0
    for path in target_java_paths(body):
        if (ROOT / path).is_file():
            continue
        rel = package_rel(path, tgt_slash)
        if not rel:
            # Target cited under legacy package — map to package-relative.
            m = re.match(
                rf"src/(?:main|test)/java/{re.escape(leg_slash)}/(.+\.java)$",
                path,
            )
            if m:
                rel = m.group(1)
            else:
                # Basename-only fallback: leaf under staging package tree.
                leaf = Path(path).name
                for base in (
                    ROOT / "migration/staging/src/main/java" / leg_slash,
                    ROOT / "migration/staging/src/test/java" / leg_slash,
                ):
                    hits = list(base.rglob(leaf)) if base.is_dir() else []
                    if hits:
                        rel = str(hits[0].relative_to(base))
                        break
        if not rel:
            continue
        try:
            subprocess.run(
                ["bash", str(HARVEST), rel],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as e:
            err = getattr(e, "stderr", "") or str(e)
            print(f"seed-fail:{rel}:{err.splitlines()[:1]}", file=sys.stderr)
            continue
        print(f"seeded:{path}")
        seeded += 1
    if seeded:
        print(f"preseeded:{seeded}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
