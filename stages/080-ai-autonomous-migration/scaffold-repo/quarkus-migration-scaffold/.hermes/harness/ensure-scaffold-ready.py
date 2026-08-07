#!/usr/bin/env python3
"""O-SCAFFOLDREADY — orchestrate mechanical scaffold/create before O-T6.

Architecture (peer of O-HARVESTREADY)
-------------------------------------
**Harvest / rewrite** → ``ensure-harvest-ready.py`` + ENSURERS (content +
classpath for staged Java).

**Scaffold / create** → this orchestrator + CREATE_ENSURERS for Targets that
are documentation or directory anchors with Oracle:absent and often **no
staging file** (``package-info.java``, ``.gitkeep``). Burning Qwen→MiniMax
for those tips is a harness defect (Wave5 S01-T-008).

Register new create capabilities in CREATE_ENSURERS below. Do **not** add a
parallel supervisor ``if`` for a one-off ensure script.

Also depends on ``harvest_ready.needs_pom_stage`` scaffold-only / focused-
scan guards so OWNSTAGE never attaches pom.xml to package-info-only tasks.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[3] if len(sys.argv) > 3 else ".")
TASKS = Path(sys.argv[1]) if len(sys.argv) > 1 else None
TID = sys.argv[2] if len(sys.argv) > 2 else ""
HARNESS = Path(__file__).resolve().parent

# (name, script) — each returns 0; stdout ``ok:…`` or ``skip:…``
CREATE_ENSURERS: list[tuple[str, str]] = [
    ("scaffold-create", "ensure-scaffold-create.py"),
    # O-CHARSEEDFIRST: missing Shape=create *Test.java shells before Qwen
    ("char-seed", "ensure-char-seed.py"),
]


def main() -> int:
    if not TASKS or not TID:
        print(
            "usage: ensure-scaffold-ready.py <tasks.md> <T-id> [root]",
            file=sys.stderr,
        )
        return 2
    notes: list[str] = []
    for name, script in CREATE_ENSURERS:
        path = HARNESS / script
        if not path.is_file():
            notes.append(f"{name}:missing")
            continue
        try:
            proc = subprocess.run(
                [sys.executable, str(path), str(TASKS), TID, str(ROOT)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            notes.append(f"{name}:err:{exc}")
            continue
        line = (proc.stdout or "").strip().splitlines()
        summary = line[0] if line else f"rc={proc.returncode}"
        if summary.startswith("ok:"):
            notes.append(f"{name}:{summary}")
        elif summary.startswith("skip:"):
            notes.append(f"{name}:skip")
        else:
            notes.append(f"{name}:{summary}")
    print("scaffold-ready:" + ",".join(notes) if notes else "scaffold-ready:noop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
