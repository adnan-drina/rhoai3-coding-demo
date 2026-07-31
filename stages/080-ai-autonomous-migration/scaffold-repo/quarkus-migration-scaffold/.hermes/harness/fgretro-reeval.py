#!/usr/bin/env python3
"""O-FGRETRO — re-open false already-complete skips after probe harden.

Scans RUN_BASE..HEAD for T-NNN commits that used the supervisor skip paths
(ALREADY COMPLETE / Already satisfied). Re-runs already-complete.py (and for
ESCW, escw-eligible.py when present). Tasks the hardened probe now refuses
are printed one id per line (re-open list).

Usage: fgretro-reeval.py <tasks.md> [run_base_sha]
Env: FGRETO_ROOT (default .)
Exit 0 always; stdout = task ids to re-dispatch.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("FGRETO_ROOT", ".")).resolve()
SKIP_RE = re.compile(
    r"^(T[-A-Za-z0-9]*\d+):\s*(ALREADY COMPLETE|Already satisfied)\b",
    re.I,
)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: fgretro-reeval.py <tasks.md> [run_base]", file=sys.stderr)
        return 2
    tasks = Path(sys.argv[1])
    run_base = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("RUN_BASE", "HEAD~50")
    ac = ROOT / ".hermes/harness/already-complete.py"
    if not ac.is_file() or not tasks.is_file():
        return 0
    try:
        log = subprocess.check_output(
            ["git", "-C", str(ROOT), "log", "--format=%s", f"{run_base}..HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return 0

    seen: set[str] = set()
    reopen: list[str] = []
    for subject in log.splitlines():
        m = SKIP_RE.match(subject.strip())
        if not m:
            continue
        tid = m.group(1)
        if tid in seen:
            continue
        seen.add(tid)
        env = os.environ.copy()
        env["ALREADY_COMPLETE_ROOT"] = str(ROOT)
        # ALREADY COMPLETE path — probe must still allow skip
        if "ALREADY COMPLETE" in subject.upper():
            rc = subprocess.call(
                [sys.executable, str(ac), str(tasks), tid],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if rc != 0:
                reopen.append(tid)
                print(tid)
            continue
        # Already satisfied (O-ESCW) — re-check escw-eligible when available
        escw = ROOT / ".hermes/harness/escw-eligible.py"
        if escw.is_file():
            rc = subprocess.call(
                [sys.executable, str(escw), str(tasks), tid],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if rc != 0:
                reopen.append(tid)
                print(tid)
    if reopen:
        print(
            f"# O-FGRETRO: {len(reopen)} skip(s) refused by hardened probe — re-dispatch",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
