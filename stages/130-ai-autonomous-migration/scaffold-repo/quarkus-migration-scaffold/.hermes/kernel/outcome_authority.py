#!/usr/bin/env python3
"""Entry point of the protected outcome-board authority (architect F1).

    outcome_authority.py serve --root /projects/modernized \\
        --store-dir /var/lib/outcome-authority --socket /run/outcome-authority/authority.sock \\
        --native-db /projects/modernized/.hermes/home/kanban.db
    outcome_authority.py hello --socket /run/outcome-authority/authority.sock
    outcome_authority.py code-identity [--base DIR]

In production this file and the planner package it imports run from the
image's root-owned copy (/opt/rhoai3/outcome-authority/{kernel,lib}), never from
the worker-writable destination tree; the image stamp records their
code-identity digest as ``outcome_authority.code_sha256``. The service itself is
planner/outcome_authority.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

_KERNEL = Path(__file__).resolve().parent
_LIB = _KERNEL.parent / "lib"
for _p in (_KERNEL, _LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from planner.outcome_authority import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
