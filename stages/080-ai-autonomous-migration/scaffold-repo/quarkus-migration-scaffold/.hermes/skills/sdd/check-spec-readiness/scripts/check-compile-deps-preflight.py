#!/usr/bin/env python3
"""RETIRED — R-M3.7 compile-deps preflight (DD4 / Operator E-20260814T070901Z).

Story-owns-extensions (DD3): JPA stories add their own persistence extensions
before entity writes. Do not call this script.

Usage:
  python3 check-compile-deps-preflight.py --help
"""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exit: 0 --help only; 1 RETIRED for any other invocation",
    )
    ap.add_argument("root", nargs="?", default=".")
    if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        ap.print_help()
        return 0
    print(
        "RETIRED: R-M3.7 check-compile-deps-preflight.py — DD4 E-20260814T070901Z "
        "(story owns extensions; see governance/retired/pom-persistence-handoff.md)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
