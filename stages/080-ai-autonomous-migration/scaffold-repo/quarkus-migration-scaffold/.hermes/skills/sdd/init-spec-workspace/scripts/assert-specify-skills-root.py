#!/usr/bin/env python3
"""FAIL unless speckit-specify is a sibling of the project skills root.

spec-kit 0.16.1 ``--integration hermes`` looks at
``Path.home()/.hermes/skills/speckit-specify`` (spec-kit#3334 unmerged).
``init-spec-workspace`` points that lookup at the project by running
specify with ``HOME=<project>`` at **init**, seeding the flat leaf, and
installing a PATH shim so a worker shell ``specify workflow run speckit``
still resolves ``speckit-specify`` when HOME is the profile (Operator
``091320ZO``). Nested ``sdd/speckit-specify`` is **not** seeded: dest-13
Hermes ``Ambiguous skill name 'speckit-specify': 2 skills``. The CLI
does not walk ``sdd/``.

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
            "$HOME/.hermes/skills/ (PATH shim / specify-from-project.sh at run). "
            "sdd/ copy is not sufficient"
            + (f" (nested copy exists at {nested})" if nested.is_file() else "")
            + ".",
            file=sys.stderr,
        )
        return 1
    dual = []
    sdd = root / ".hermes" / "skills" / "sdd"
    for name in ("speckit-specify", "speckit-plan", "speckit-tasks", "speckit-analyze"):
        leaf = sdd / name / "SKILL.md"
        if leaf.is_file():
            dual.append(str(leaf))
    if dual:
        print(
            "FAIL: dual-seeded sdd/ speckit skills make Hermes bare names "
            "Ambiguous (dest-13): " + "; ".join(dual),
            file=sys.stderr,
        )
        return 1
    print(f"OK: specify skills-root has speckit-specify ({want})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
