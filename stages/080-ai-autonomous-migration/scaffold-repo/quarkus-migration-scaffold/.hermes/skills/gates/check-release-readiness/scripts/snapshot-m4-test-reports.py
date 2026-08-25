#!/usr/bin/env python3
"""Copy Maven test reports into evidence/ before any rebuild that can clean them.

Lead:m4-must-not-destroy-evidence-before-reading-it — dest-5 M4 ran
``mvn clean test`` and deleted unread surefire XML. First snapshot with
XML wins; never overwrite a populated snapshot with an empty target/.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCES = (
    ("surefire", Path("target") / "surefire-reports"),
    ("failsafe", Path("target") / "failsafe-reports"),
)
SNAP_ROOT = Path("evidence") / "m4-pre-rebuild" / "test-reports"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def xml_count(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.rglob("*.xml") if path.is_file())


def snapshot_root(root: Path) -> dict:
    dest = root / SNAP_ROOT
    dest.mkdir(parents=True, exist_ok=True)
    existing = xml_count(dest)
    copied: list[str] = []
    missing: list[str] = []
    kept = False
    if existing > 0:
        kept = True
    else:
        for label, rel in SOURCES:
            src = root / rel
            n = xml_count(src)
            if n == 0:
                missing.append(str(rel))
                continue
            target = dest / label
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
            copied.append("%s:%d" % (label, n))
    manifest = {
        "schema": "rhoai3.m4-test-report-snapshot/v1",
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kept_existing_snapshot": kept,
        "copied": copied,
        "live_missing": missing,
        "snapshot_xml": xml_count(dest),
    }
    (dest.parent / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "OK: snapshot-m4-test-reports (xml=%d kept=%s copied=%s)"
        % (manifest["snapshot_xml"], kept, ",".join(copied) or "-"),
        file=sys.stderr,
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="product / dest root")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        return _fail("root is not a directory: " + str(root))
    snapshot_root(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
