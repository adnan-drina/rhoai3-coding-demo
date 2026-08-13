#!/usr/bin/env python3
"""R-M3.7 — compile-deps preflight before first model/entity write.

Fails closed when persistence BOM is absent so workers dependency_wait
before sinking N file writes. Architect E-20260810T172800Z.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

EXIT_CODES = """\
Exit codes (house contract UPLIFT-3):
  0  pass — persistence BOM preflight passed
  1  BLOCK — missing pom or persistence deps (typed dependency_wait; same as
     check-persistence-bom.py — passed through, not remapped)
  2  usage / harness defect (bad arguments, or sibling script missing)
"""


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="product root containing pom.xml (default: .)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    script = Path(__file__).resolve().parent / "check-persistence-bom.py"
    if not script.is_file():
        print(f"FAIL: missing sibling {script}", file=sys.stderr)
        return 2
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
        # Pass through sibling code (1=BLOCK); only invent 2 for harness defects.
        return 1 if cp.returncode == 1 else cp.returncode
    print("OK: R-M3.7 compile-deps preflight (persistence BOM)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
