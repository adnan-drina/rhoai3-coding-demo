#!/usr/bin/env python3
"""Golden assert: `.specify/` must be absent on the scaffold source tree.

Workspaces under `/projects/*` are allowed to have `.specify/` after AD-S
init. This script is the mechanical stand-in for the retired
DO_NOT_COMMIT_SPECIFY note (init-spec-workspace).
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    specify = root / ".specify"
    if specify.exists():
        print(
            f"FAIL: SPECIFY_PRESENT {specify} — scaffold/source tree must not carry .specify/",
            file=sys.stderr,
        )
        return 1
    print(f"OK: .specify absent under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
