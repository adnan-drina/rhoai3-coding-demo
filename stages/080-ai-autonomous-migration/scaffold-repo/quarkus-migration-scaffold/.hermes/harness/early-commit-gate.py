#!/usr/bin/env python3
"""O-ESCALGPLACE — existing prefix commit may succeed only if task sensor GREEN.

run_stage early path: if committed(prefix) already, refuse_red_task_commit
must run before treating that as success. This helper is the pure decision
(sensor_rc == 0 → keep / else reset) so instruments can prove the contract
without sourcing supervisor.sh.

Usage:
  early-commit-gate.py <sensor_rc>
Exit 0 = keep commit; exit 1 = refuse (reset / retry).
"""
from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) < 2:
        return 2
    try:
        rc = int(sys.argv[1])
    except ValueError:
        return 2
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
