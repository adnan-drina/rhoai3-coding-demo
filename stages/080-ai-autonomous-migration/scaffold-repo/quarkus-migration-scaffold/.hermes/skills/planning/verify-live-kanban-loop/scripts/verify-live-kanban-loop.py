#!/usr/bin/env python3
"""Skill wrapper over .hermes/kernel/k3_live.py (K3 live comparator)."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    for parent in Path(__file__).resolve().parents:
        kernel = parent / "kernel"
        if (kernel / "k3_live.py").is_file():
            sys.argv = [str(kernel / "k3_live.py")] + sys.argv[1:]
            try:
                runpy.run_path(str(kernel / "k3_live.py"), run_name="__main__")
            except SystemExit as exc:
                return int(exc.code or 0)
            return 0
    print("FAIL: .hermes/kernel/k3_live.py not found", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
