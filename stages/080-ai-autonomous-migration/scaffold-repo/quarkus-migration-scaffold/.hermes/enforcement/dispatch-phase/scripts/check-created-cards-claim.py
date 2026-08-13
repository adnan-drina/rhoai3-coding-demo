#!/usr/bin/env python3
"""Operator E-20260811T133000Z banked #5 — created_cards attribution seam.

M2b mandates CLI ``create-m3-implementer.sh`` (which now stamps parent linkage +
``created_by=<parent>``). Completing with ``created_cards=[]`` to skip the
Hermes card-claim check is a **consumer REJECT** when a derived claim list
exists for that parent.

Usage:
  python3 check-created-cards-claim.py --parent t_xxx [--claimed id id…]
  python3 check-created-cards-claim.py --parent t_xxx --claimed-empty

Exit 0 = OK; 1 = REJECT (empty claim while derived children exist, or
claimed id not in derived list).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def derived_path(root: Path, parent: str) -> Path:
    return root / "evidence" / "derived" / f"created-cards-{parent}.json"


def load_derived(path: Path) -> list[str]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        cards = data.get("cards") or data.get("task_ids") or []
    elif isinstance(data, list):
        cards = data
    else:
        cards = []
    out: list[str] = []
    for c in cards:
        if isinstance(c, str) and c.strip():
            out.append(c.strip())
        elif isinstance(c, dict) and c.get("id"):
            out.append(str(c["id"]).strip())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--parent", required=True, help="M2b / creating parent task id")
    ap.add_argument(
        "--claimed",
        nargs="*",
        default=None,
        help="created_cards ids passed to kanban_complete",
    )
    ap.add_argument(
        "--claimed-empty",
        action="store_true",
        help="Assert completing with created_cards=[] (will REJECT if derived nonempty)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    parent = str(args.parent).strip()
    path = derived_path(root, parent)
    derived = load_derived(path)

    if args.claimed_empty:
        claimed: list[str] = []
    elif args.claimed is None:
        print(
            "FAIL: pass --claimed id… or --claimed-empty",
            file=sys.stderr,
        )
        return 1
    else:
        claimed = [str(x).strip() for x in args.claimed if str(x).strip()]

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
        f"for parent={parent}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
