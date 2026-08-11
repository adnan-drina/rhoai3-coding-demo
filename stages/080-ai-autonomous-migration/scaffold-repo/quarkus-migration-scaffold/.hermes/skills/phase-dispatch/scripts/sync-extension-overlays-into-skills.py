#!/usr/bin/env python3
"""R-M3.32 — sync extensions/<skill>/references/* into .hermes/skills/<skill>/references/.

Hermes skill_view resolves in-skill references/ only. AD-011 overlays under
extensions/ are the authoring source; create/init must materialize them into
the Hermes skill tree before the next security (or overlay) card runs.

Usage:
  python3 .hermes/skills/phase-dispatch/scripts/sync-extension-overlays-into-skills.py [ROOT]
  python3 ... --check   # exit 1 if any overlay missing from skill tree
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument(
        "--check",
        action="store_true",
        help="verify overlays are present in skill tree; do not write",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    ext_root = root / "extensions"
    skills_root = root / ".hermes" / "skills"
    if not ext_root.is_dir():
        print(f"OK: no extensions/ at {ext_root} (nothing to sync)")
        return 0
    if not skills_root.is_dir():
        print(f"FAIL: missing skills root {skills_root}", file=sys.stderr)
        return 1

    synced = 0
    missing = 0
    for skill_dir in sorted(ext_root.iterdir()):
        refs = skill_dir / "references"
        if not refs.is_dir():
            continue
        dest_refs = skills_root / skill_dir.name / "references"
        if not dest_refs.is_dir():
            print(
                f"FAIL: skill references dir missing for overlay {skill_dir.name}: {dest_refs}",
                file=sys.stderr,
            )
            missing += 1
            continue
        for src in sorted(refs.glob("*.md")):
            dest = dest_refs / src.name
            if args.check:
                if not dest.is_file():
                    print(f"FAIL: missing skill-tree overlay {dest}", file=sys.stderr)
                    missing += 1
                else:
                    print(f"OK: {dest.relative_to(root)}")
                continue
            dest_refs.mkdir(parents=True, exist_ok=True)
            try:
                dest_refs.chmod(0o755)
            except OSError:
                pass
            shutil.copyfile(src, dest)
            try:
                dest.chmod(0o644)
            except OSError:
                pass
            print(f"SYNC: {src.relative_to(root)} -> {dest.relative_to(root)}")
            synced += 1

    if args.check:
        if missing:
            print(f"FAIL: {missing} overlay(s) not in Hermes skill tree", file=sys.stderr)
            return 1
        print("OK: all extension overlays present in Hermes skill tree")
        return 0

    print(f"OK: synced {synced} overlay file(s) into Hermes skill tree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
