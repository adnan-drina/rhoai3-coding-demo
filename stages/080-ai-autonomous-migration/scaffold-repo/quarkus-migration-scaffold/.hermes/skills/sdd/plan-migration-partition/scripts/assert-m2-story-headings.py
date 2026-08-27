#!/usr/bin/env python3
"""Refuse when tasks.md User Story headings disagree with partition story_ids.

Architect 142518ZA: story-heading ↔ story_id coverage, still not write-set
scrape. PATH_TOKEN OBJECT.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

KERNEL = Path(__file__).resolve().parents[4] / "kernel"
if str(KERNEL) not in sys.path:
    sys.path.insert(0, str(KERNEL))

from speckit_feature import find_tasks  # noqa: E402

PARTITION_CANDIDATES = (
    Path("evidence") / "partition.json",
    Path("evidence") / "briefs" / "partition.json",
)

US_HEADING = re.compile(
    r"^#{1,3}\s+.*\bUser Story\s+(\d+)\b",
    re.I | re.M,
)
US_TAG = re.compile(r"\[US(\d+)\]", re.I)
US_ID = re.compile(r"^us(\d+)(?:_|$)", re.I)
SETUP_HEADING = re.compile(
    r"^#{1,3}\s+.*\b(?:Phase\s+\d+:\s*)?Setup\b",
    re.I | re.M,
)
POLISH_HEADING = re.compile(
    r"^#{1,3}\s+.*\bPolish\b",
    re.I | re.M,
)


def _fail(msg: str) -> int:
    print("FAIL: STORY_HEADING_MISMATCH: " + msg, file=sys.stderr)
    return 1


def find_partition(root: Path) -> Path | None:
    for rel in PARTITION_CANDIDATES:
        path = root / rel
        if path.is_file():
            return path
    return None


def story_us_nums(stories: list[dict]) -> set[int]:
    out: set[int] = set()
    for story in stories:
        sid = str(story.get("story_id") or story.get("id") or "").strip()
        m = US_ID.match(sid)
        if m:
            out.add(int(m.group(1)))
    return out


def heading_us_nums(text: str) -> set[int]:
    found = {int(n) for n in US_HEADING.findall(text)}
    found.update(int(n) for n in US_TAG.findall(text))
    return found


def has_setup(stories: list[dict]) -> bool:
    for story in stories:
        sid = str(story.get("story_id") or "").strip().lower()
        kind = str(story.get("kind") or "").strip().lower()
        if sid == "setup" or kind == "setup":
            return True
    return False


def has_polish(stories: list[dict]) -> bool:
    for story in stories:
        sid = str(story.get("story_id") or "").strip().lower()
        kind = str(story.get("kind") or "").strip().lower()
        if "polish" in sid or kind == "polish":
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0] if argv else (sys.argv[1] if len(sys.argv) > 1 else ".")).resolve()
    if not root.is_dir():
        print("FAIL: not a directory %s" % root, file=sys.stderr)
        return 2
    tasks, tasks_err = find_tasks(root)
    if tasks_err:
        return _fail(tasks_err)
    if not tasks:
        return _fail("missing non-empty specs/*/tasks.md")
    if len(tasks) != 1:
        return _fail("need exactly one tasks.md, found %s" % ",".join(str(p) for p in tasks))
    text = tasks[0].read_text(encoding="utf-8")
    part_path = find_partition(root)
    if part_path is None:
        return _fail("missing evidence/partition.json")
    try:
        partition = json.loads(part_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _fail("partition unreadable: %s" % exc)
    stories = [s for s in (partition.get("stories") or []) if isinstance(s, dict)]
    if not stories:
        return _fail("partition stories[] empty")

    from_ids = story_us_nums(stories)
    from_head = heading_us_nums(text)
    if from_ids != from_head:
        return _fail(
            "tasks.md User Story headings %s != partition usN story_id %s"
            % (sorted(from_head), sorted(from_ids))
        )
    if has_setup(stories) and not SETUP_HEADING.search(text):
        return _fail("partition has setup but tasks.md has no Setup heading")
    if has_polish(stories) and not POLISH_HEADING.search(text):
        return _fail("partition has polish but tasks.md has no Polish heading")
    print(
        "OK: story headings match partition story_ids (us=%s)"
        % sorted(from_ids)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
