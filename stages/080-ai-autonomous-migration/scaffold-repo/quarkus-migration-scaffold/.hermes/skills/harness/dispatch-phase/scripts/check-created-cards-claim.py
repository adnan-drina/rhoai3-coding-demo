#!/usr/bin/env python3
"""Created-cards claim vs partition (Deputy E-20260813T221456Z F8a).

F8 question: did we mint the stories the partition asked for?
Answer = set equality of partition story_ids ↔ created card story_ids
(both directions). Stamp↔board self-consistency alone is circular and
insufficient.

Modes:
  --mode partition   (default) partition story_ids == derived story_ids
  --mode subset      derived story_ids ⊆ partition (incremental create-m3)
  --mode stamp       legacy: claimed task ids ⊆ derived stamp (secondary)

Usage:
  python3 check-created-cards-claim.py --parent t_xxx --mode partition
  python3 check-created-cards-claim.py --parent t_xxx --mode subset
  python3 check-created-cards-claim.py --parent t_xxx --claimed id… --mode stamp

Exit 0 = OK; 1 = REJECT.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def derived_path(root: Path, parent: str) -> Path:
    return root / "evidence" / "derived" / f"created-cards-{parent}.json"


def partition_path(root: Path) -> Path:
    return root / "evidence" / "briefs" / "partition.json"


def load_derived(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        cards = data.get("cards") or data.get("task_ids") or []
    elif isinstance(data, list):
        cards = data
    else:
        cards = []
    out: list[dict] = []
    for c in cards:
        if isinstance(c, str) and c.strip():
            out.append({"id": c.strip()})
        elif isinstance(c, dict) and c.get("id"):
            out.append(c)
    return out


def derived_ids(cards: list[dict]) -> list[str]:
    return [str(c.get("id") or "").strip() for c in cards if str(c.get("id") or "").strip()]


def derived_story_ids(cards: list[dict]) -> set[str]:
    out: set[str] = set()
    for c in cards:
        sid = str(c.get("story_id") or "").strip()
        if sid:
            out.add(sid)
    return out


def partition_story_ids(root: Path) -> set[str]:
    """Identity is partition.json stories[].story_id (SR-9). Not titles, not filenames."""
    path = partition_path(root)
    if not path.is_file():
        raise FileNotFoundError(f"missing partition at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    stories = data.get("stories") if isinstance(data, dict) else None
    if not isinstance(stories, list):
        raise ValueError(f"partition missing stories[]: {path}")
    out: set[str] = set()
    for i, s in enumerate(stories):
        if not isinstance(s, dict):
            raise ValueError(f"partition stories[{i}] is not an object: {path}")
        sid = str(s.get("story_id") or "").strip()
        if not sid:
            raise ValueError(
                f"partition stories[{i}] missing story_id (SR-9 — do not "
                f"derive from title or id): {path}"
            )
        out.add(sid)
    return out


def minted_story_ids(root: Path, parent: str) -> set[str]:
    """Prefer created-story-cards.json (Deputy baseline); else derived stamp."""
    csc = root / "evidence" / "derived" / "created-story-cards.json"
    if csc.is_file():
        try:
            data = json.loads(csc.read_text(encoding="utf-8"))
            cards = data.get("cards") if isinstance(data, dict) else data
            out: set[str] = set()
            if isinstance(cards, list):
                for c in cards:
                    if isinstance(c, dict) and c.get("story_id"):
                        out.add(str(c["story_id"]).strip())
            if out:
                return out
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return derived_story_ids(load_derived(derived_path(root, parent)))


def check_partition(root: Path, parent: str, *, mode: str) -> int:
    created = minted_story_ids(root, parent)
    try:
        wanted = partition_story_ids(root)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"CREATED_CARDS_REJECT: partition load failed: {e}", file=sys.stderr)
        return 1

    if not wanted:
        print("CREATED_CARDS_REJECT: partition stories[] empty", file=sys.stderr)
        return 1

    extra = sorted(created - wanted)
    missing = sorted(wanted - created)

    if mode == "subset":
        if extra:
            print(
                f"CREATED_CARDS_REJECT: derived story_ids not in partition: {extra}",
                file=sys.stderr,
            )
            return 1
        if not created:
            print(
                f"WARN: derived claim empty at {path} (create-m3 not stamped yet)",
                file=sys.stderr,
            )
        print(
            f"OK: minted ⊆ partition "
            f"({len(created)}/{len(wanted)} stories; parent={parent})"
        )
        return 0

    # full partition equality
    if extra or missing:
        print(
            "CREATED_CARDS_REJECT: partition story_ids ≠ created card story_ids "
            f"(missing={missing} extra={extra}) — F8a E-20260813T221456Z "
            "(compare partition, not stamp self-consistency)",
            file=sys.stderr,
        )
        return 1
    print(
        f"OK: partition == minted story_ids (partition.json story_id ↔ created-story-cards) "
        f"({len(wanted)} stories; parent={parent}) — F8a/SR-9c"
    )
    return 0


def check_stamp(root: Path, parent: str, claimed: list[str], claimed_empty: bool) -> int:
    path = derived_path(root, parent)
    cards = load_derived(path)
    derived = derived_ids(cards)

    if claimed_empty:
        claimed = []

    if derived and not claimed:
        print(
            "CREATED_CARDS_REJECT: created_cards=[] while "
            f"{path} lists {len(derived)} script-created card(s) — "
            "pass id+digest list (Operator E-20260811T133000Z #5); "
            "empty-list-to-skip is forbidden",
            file=sys.stderr,
        )
        return 1

    if claimed and not derived:
        print(
            f"WARN: claimed {claimed} but no derived list at {path} "
            "(create-m3 may predate stamp) — OK if parent-linked + created_by=parent",
            file=sys.stderr,
        )
        return 0

    missing = [c for c in claimed if c not in set(derived)]
    if missing:
        print(
            f"CREATED_CARDS_REJECT: claimed ids not in derived list: {missing}",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: created_cards claim ({len(claimed)} id(s)) matches derived "
        f"for parent={parent} (stamp mode; prefer --mode partition)"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--parent", required=True, help="M2 / creating parent task id")
    ap.add_argument(
        "--mode",
        choices=("partition", "subset", "stamp"),
        default="partition",
        help="partition=set equality (F8a); subset=incremental; stamp=legacy",
    )
    ap.add_argument(
        "--claimed",
        nargs="*",
        default=None,
        help="created_cards ids (stamp mode)",
    )
    ap.add_argument(
        "--claimed-empty",
        action="store_true",
        help="Assert completing with created_cards=[] (stamp mode)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    parent = str(args.parent).strip()

    if args.mode in {"partition", "subset"}:
        return check_partition(root, parent, mode=args.mode)

    if args.claimed is None and not args.claimed_empty:
        print(
            "FAIL: stamp mode requires --claimed id… or --claimed-empty",
            file=sys.stderr,
        )
        return 1
    claimed = [str(x).strip() for x in (args.claimed or []) if str(x).strip()]
    return check_stamp(root, parent, claimed, args.claimed_empty)


if __name__ == "__main__":
    raise SystemExit(main())
