#!/usr/bin/env python3
"""Spawn-time cache → HERMES_KANBAN_FILES_WRITABLE, then exec real hermes.

Snapshots evidence/runtime/write-sets/<task>.json into env **once at exec**,
else the published phase-dispatch.yaml files_writable key (M3 omit stays
unset → hook deny-all). Speed, not a trust boundary. The hook must not
read dest JSON for policy.

Env:
  HERMES_REAL_BIN  real CLI (default: ~/.local/bin/hermes)
  HERMES_WRITE_SAFE_ROOT / PROJECT_DIR  dest root for the cache path
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _apply_fw(fw: list) -> None:
    os.environ["HERMES_KANBAN_FILES_WRITABLE"] = json.dumps(
        [str(x) for x in fw if str(x).strip()]
    )


def _hydrate_phase_yaml(root: Path, task: str) -> bool:
    phase = os.environ.get("HERMES_KANBAN_PHASE", "").strip()
    if not phase:
        derived = root / "evidence" / "derived"
        for name in ("M1", "M2", "M4", "M5"):
            ptr = derived / f"phase-{name}-task-id.txt"
            try:
                if ptr.is_file() and ptr.read_text(encoding="utf-8").strip() == task:
                    phase = name
                    break
            except OSError:
                continue
    if not phase:
        return False
    reader = (
        root
        / ".hermes"
        / "skills"
        / "harness"
        / "dispatch-phase"
        / "scripts"
        / "read-phase-dispatch.py"
    )
    yaml_path = root / ".hermes" / "phase-dispatch.yaml"
    if not reader.is_file() or not yaml_path.is_file():
        return False
    import subprocess
    import sys

    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(reader),
                "--yaml",
                str(yaml_path),
                "--phase",
                phase,
                "--print",
                "files_writable_json",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if proc.returncode != 0:
        return False
    raw = proc.stdout.strip()
    if raw in ("", "null"):
        return False
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, list):
        return False
    _apply_fw(data)
    return True


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
    root_p = Path(root)
    path = root_p / "evidence" / "runtime" / "write-sets" / f"{task}.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            data = None
        if isinstance(data, dict):
            fw = data.get("files_writable")
            if isinstance(fw, list):
                _apply_fw(fw)
                return
    _hydrate_phase_yaml(root_p, task)


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
