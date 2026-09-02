#!/usr/bin/env python3
"""Thin CLI: official-log + KEEP audit for this paved-road kind.

Logic lives in ``.hermes/lib/paved_road.py``. Default ``--steps`` is this
skill's ``steps.json``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_hermes_lib() -> None:
    p = Path(__file__).resolve()
    for parent in p.parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            s = str(lib)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()
from paved_road import audit_paths, resolve_log  # noqa: E402

SKILL = Path(__file__).resolve().parents[1]
STEPS = SKILL / "steps.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("task_id", nargs="?", help="t_… (reads $HERMES_HOME/kanban/logs)")
    ap.add_argument(
        "--log",
        type=Path,
        help="official log path (workshop fixture; dest-14 harvested lines)",
    )
    ap.add_argument(
        "--root",
        type=Path,
        required=True,
        help="workspace root for KEEP paths",
    )
    ap.add_argument(
        "--steps",
        type=Path,
        default=STEPS,
        help="steps.json (default: this skill)",
    )
    args = ap.parse_args(argv)
    log = resolve_log(args.task_id, args.log)
    if log is None:
        return 2
    return audit_paths(log, args.root, args.steps)


if __name__ == "__main__":
    raise SystemExit(main())
