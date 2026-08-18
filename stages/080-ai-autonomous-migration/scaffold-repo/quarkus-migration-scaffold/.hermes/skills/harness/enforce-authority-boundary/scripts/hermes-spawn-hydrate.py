#!/usr/bin/env python3
"""Spawn-time cache → HERMES_KANBAN_FILES_WRITABLE, then exec real hermes.

The fence reads spawn env only. This wrapper snapshots
evidence/runtime/write-sets/<task>.json into env **once at exec**.
It is resolution speed, not a trust boundary (relocatable managed dir
and $HOME hermes bits remain worker-reachable; hole 2 stays open).

Env:
  HERMES_REAL_BIN  real CLI (default: ~/.local/bin/hermes)
  HERMES_WRITE_SAFE_ROOT / PROJECT_DIR  dest root for the cache path
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def hydrate() -> None:
    if os.environ.get("HERMES_KANBAN_FILES_WRITABLE", "").strip():
        return
    task = os.environ.get("HERMES_KANBAN_TASK", "").strip()
    if not task:
        return
    root = (
        os.environ.get("HERMES_WRITE_SAFE_ROOT")
        or os.environ.get("PROJECT_DIR")
        or ""
    ).strip()
    if not root:
        return
    path = Path(root) / "evidence" / "runtime" / "write-sets" / f"{task}.json"
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return
    if not isinstance(data, dict):
        return
    fw = data.get("files_writable")
    if not isinstance(fw, list):
        return
    os.environ["HERMES_KANBAN_FILES_WRITABLE"] = json.dumps(
        [str(x) for x in fw if str(x).strip()]
    )


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in {"-h", "--help"}:
        print(
            "hermes-spawn-hydrate.py — copy dest write-set cache into "
            "HERMES_KANBAN_FILES_WRITABLE once, then exec HERMES_REAL_BIN. "
            "Not a trust boundary."
        )
        return 0
    hydrate()
    real = os.environ.get("HERMES_REAL_BIN") or str(
        Path.home() / ".local" / "bin" / "hermes"
    )
    if not os.path.isfile(real) or not os.access(real, os.X_OK):
        print(f"hermes-spawn-hydrate: missing HERMES_REAL_BIN={real}", file=sys.stderr)
        return 127
    os.execv(real, [real, *sys.argv[1:]])
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
