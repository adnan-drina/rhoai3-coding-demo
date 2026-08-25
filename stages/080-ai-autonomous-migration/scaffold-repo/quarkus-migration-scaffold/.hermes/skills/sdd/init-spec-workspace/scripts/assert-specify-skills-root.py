#!/usr/bin/env python3
"""FAIL unless speckit-specify is a sibling of the project skills root.

spec-kit 0.16.1 ``--integration hermes`` looks at
``Path.home()/.hermes/skills/speckit-specify`` (spec-kit#3334 unmerged).
``init-spec-workspace`` points that lookup at the project by running
specify with ``HOME=<project>`` and seeding the same leaf here — not
only under ``sdd/``. Nested ``sdd/speckit-specify`` is the implementer
taxonomy copy; the CLI does not walk ``sdd/``.

Usage:
  python3 assert-specify-skills-root.py /projects/modernized
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    want = root / ".hermes" / "skills" / "speckit-specify" / "SKILL.md"
    nested = root / ".hermes" / "skills" / "sdd" / "speckit-specify" / "SKILL.md"
    if not want.is_file():
        print(
            f"FAIL: specify CLI skills-root missing {want}. "
            "spec-kit 0.16.1 resolves speckit-specify from "
            "$HOME/.hermes/skills/ (HOME=project via specify-from-project.sh). "
            "sdd/ copy is not sufficient"
            + (f" (nested copy exists at {nested})" if nested.is_file() else "")
            + ".",
            file=sys.stderr,
        )
        return 1
    print(f"OK: specify skills-root has speckit-specify ({want})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
