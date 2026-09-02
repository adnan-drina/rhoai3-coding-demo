#!/usr/bin/env python3
"""Refuse a partition whose write-set names dest Java the type-inventory did not.

Twin of ``assert-partition-invented-routes.py`` (Operator ``3e3409d0``).
Coverage already requires every type-inventory ``dest_file`` in a write-set
(``types_uncovered``). This is the other direction: product
``src/main/java`` paths in ``files_writable`` must be a dest twin.
Do not join inventory ``file`` to dest write-set (A-8; no
RestController→Resource mapper). F7: write-set overlap is this gate, not
``derive-story-oracles``.

Exit 0: no type-inventory (skip), or every product Java path is a dest_file.
Exit 1: invented dest Java (dest-9 Application.java / GreetingResource.java).
Exit 2: usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KERNEL = Path(__file__).resolve().parents[4] / "lib"
if str(KERNEL) not in sys.path:
    sys.path.insert(0, str(KERNEL))

from path_maps import dest_path_as_written  # noqa: E402
from supersede import collect_supersedes, type_inventory_invented_writes  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def story_files(story: dict) -> list[str]:
    for key in ("files_writable", "files", "files_in_scope"):
        val = story.get(key)
        if isinstance(val, list):
            return [str(x) for x in val if str(x).strip()]
    return []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        return 2
    part = next(
        (
            root / c
            for c in ("evidence/partition.json", "evidence/briefs/partition.json")
            if (root / c).is_file()
        ),
        root / "evidence/partition.json",
    )
    if not part.is_file():
        return _fail("INVENTED_FILES missing partition at %s" % part)
    try:
        partition = json.loads(part.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _fail("INVENTED_FILES unreadable partition: %s" % exc)
    if not isinstance(partition, dict):
        return _fail("INVENTED_FILES partition is not an object")
    stories = [s for s in (partition.get("stories") or []) if isinstance(s, dict)]
    owned: set[str] = set()
    for story in stories:
        for f in story_files(story):
            owned.add(dest_path_as_written(f))
    supersedes = collect_supersedes(partition, stories)
    invented = type_inventory_invented_writes(root, owned, supersedes)
    if invented is None:
        print("OK: assert-partition-invented-files (no type-inventory; skip)")
        return 0
    if invented:
        print(
            "REFUSE: INVENTED_FILES write-set names dest Java "
            "type-inventory did not:",
            file=sys.stderr,
        )
        for path in invented:
            print("  - " + path, file=sys.stderr)
        print(
            "  Remedy: drop the path, or ground it as types[].dest_file. "
            "Do not invent Application.java / *Resource.java from a mapper.",
            file=sys.stderr,
        )
        return 1
    print(
        "OK: assert-partition-invented-files (%s product write-set path(s))"
        % len(owned)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
