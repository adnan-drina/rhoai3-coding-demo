#!/usr/bin/env python3
"""Negative-space — golden scaffold must not ship a root scripts/ tree.

AD-H §7: procedures live under .hermes/skills/*/scripts/ or
.hermes/skills/harness/*/scripts/. A root scripts/ (even with only a README
explaining emptiness) is the last negative-space artefact
(Deputy E-20260813T184709Z / Operator E-20260813T173644Z).

Usage:
  python3 check-scripts-absent.py --root .
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exit: 0=absent/empty, 1=scripts present with content, 2=usage",
    )
    ap.add_argument("--root", default=".", help="scaffold root")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"FAIL: bad root {root}", file=sys.stderr)
        return 2
    scripts = root / "scripts"
    if not scripts.exists():
        print("OK: root scripts/ absent from golden")
        return 0
    if not scripts.is_dir():
        print(
            f"FAIL: {scripts} exists and is not a directory — remove it "
            "(negative-space ruling; procedures live under .hermes/)",
            file=sys.stderr,
        )
        return 1
    # Any entry (incl. README / .gitkeep) fails — empty dir is still unwanted
    # once the assert lands; git cannot track empty dirs, so presence means
    # content or a leftover.
    kids = sorted(p.name for p in scripts.iterdir() if p.name != ".DS_Store")
    if kids:
        print(
            f"FAIL: root scripts/ is not empty ({', '.join(kids)}) — "
            "delete scripts/ (AD-H §7; Deputy E-20260813T184709Z)",
            file=sys.stderr,
        )
        return 1
    print(
        f"FAIL: empty root scripts/ directory present at {scripts} — "
        "remove the directory (git cannot track it; do not re-add README)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
