#!/usr/bin/env python3
"""R-M3.7 — compile-deps preflight before first model/entity write.

Fails closed when persistence BOM is absent so workers dependency_wait
before sinking N file writes. Architect E-20260810T172800Z.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    script = Path(__file__).resolve().parent / "check-persistence-bom.py"
    cp = subprocess.run(
        [sys.executable, str(script), str(root)],
        text=True,
        capture_output=True,
    )
    sys.stdout.write(cp.stdout or "")
    sys.stderr.write(cp.stderr or "")
    if cp.returncode != 0:
        print(
            "FAIL: R-M3.7 compile-deps preflight — typed dependency_wait "
            "(do not write entities; escalate Lead:fix-upstream-pom). "
            "Architect E-20260810T172800Z.",
            file=sys.stderr,
        )
        return 2
    print("OK: R-M3.7 compile-deps preflight (persistence BOM)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
