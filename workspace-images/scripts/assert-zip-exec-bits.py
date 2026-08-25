#!/usr/bin/env python3
"""Assert an extracted zip kept the executable bits the archive declared.

Zip archives carry Unix modes in ``external_attr``. Some extractors preserve
them (``unzip``) and some discard them (``python -m zipfile``, which is how
``/opt/kantra`` came to hold a 644 ``java-external-provider`` that no runtime
chmod could repair, because the tree is chown'd to a different uid than the
workspace runs as).

This checks the invariant rather than a list of filenames: every entry the
archive marks owner-executable must be owner-executable on disk. A new
archive layout, a renamed binary, or a new provider is covered without
editing this script.

Usage:
    assert-zip-exec-bits.py --zip ARCHIVE --dest DIR
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
import zipfile


def declared_exec_entries(archive: str) -> list[str]:
    """Names in ``archive`` whose stored Unix mode has the owner-exec bit.

    Entries created on non-Unix systems store no mode at all (``external_attr``
    high bits zero); those are reported as not-declared rather than guessed at.
    """
    names: list[str] = []
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            mode = info.external_attr >> 16
            if mode and (mode & stat.S_IXUSR):
                names.append(info.filename)
    return names


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, help="the archive that was extracted")
    ap.add_argument("--dest", required=True, help="directory it was extracted into")
    args = ap.parse_args()

    declared = declared_exec_entries(args.zip)
    if not declared:
        print(
            f"REFUSE: {args.zip} declares no owner-executable entries; "
            "either the archive stores no Unix modes or it shipped no binaries. "
            "Extracted permissions cannot be verified.",
            file=sys.stderr,
        )
        return 1

    lost = []
    missing = []
    for name in declared:
        path = os.path.join(args.dest, name)
        if not os.path.exists(path):
            missing.append(name)
        elif not os.access(path, os.X_OK):
            lost.append(name)

    if missing:
        print(
            "REFUSE: declared-executable entries absent from "
            f"{args.dest}: {', '.join(sorted(missing))}",
            file=sys.stderr,
        )
        return 1
    if lost:
        print(
            f"REFUSE: {len(lost)} of {len(declared)} executable entries lost "
            f"their exec bit during extraction into {args.dest}: "
            f"{', '.join(sorted(lost))}. The extractor is discarding Unix "
            "modes - use unzip, not `python -m zipfile`.",
            file=sys.stderr,
        )
        return 1

    print(f"exec bits intact: {len(declared)} executable entries under {args.dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
