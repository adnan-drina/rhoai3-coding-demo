#!/usr/bin/env python3
"""V35-SERIAL — resolve identity.parents story ids to already-created task ids.

Create order is setup → foundational → US*. identity.parents names story_id
tokens. Look them up in evidence/derived/created-story-cards.json.

Usage:
  python3 resolve-story-parent-ids.py --root . --body evidence/bodies/m3-US1.json
  python3 resolve-story-parent-ids.py --root . --body … --print ids
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _inner(doc: dict) -> dict:
    body = doc.get("body") if isinstance(doc.get("body"), dict) else doc
    return body if isinstance(body, dict) else {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    ap.add_argument("--body", required=True)
    ap.add_argument(
        "--cards",
        default="evidence/derived/created-story-cards.json",
    )
    ap.add_argument(
        "--print",
        dest="print_field",
        choices=("ids", "story-ids"),
        default="ids",
    )
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    body_path = Path(args.body)
    if not body_path.is_file():
        body_path = root / args.body
    if not body_path.is_file():
        print(f"FAIL: missing body {args.body}", file=sys.stderr)
        return 1
    try:
        doc = json.loads(body_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: body {body_path}: {exc}", file=sys.stderr)
        return 1
    body = _inner(doc) if isinstance(doc, dict) else {}
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    wanted = ident.get("parents") or body.get("parents") or []
    if not isinstance(wanted, list):
        wanted = []
    names = [str(x).strip() for x in wanted if str(x).strip()]
    if not names:
        if args.print_field == "ids":
            print("")
        else:
            print("")
        return 0
    cards_path = Path(args.cards)
    if not cards_path.is_file():
        cards_path = root / args.cards
    if not cards_path.is_file():
        print(
            f"REFUSE: identity.parents={names} but missing {args.cards} "
            "(create identity.parents after those stories exist)",
            file=sys.stderr,
        )
        return 1
    try:
        payload = json.loads(cards_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: cards {cards_path}: {exc}", file=sys.stderr)
        return 1
    by_story: dict[str, str] = {}
    for rec in payload.get("cards") or []:
        if not isinstance(rec, dict):
            continue
        sid = str(rec.get("story_id") or "").strip()
        tid = str(rec.get("id") or rec.get("task_id") or "").strip()
        if sid and tid:
            by_story[sid] = tid
    missing = [n for n in names if n not in by_story]
    if missing:
        print(
            f"REFUSE: identity.parents not yet created: {missing} "
            f"(have {sorted(by_story)})",
            file=sys.stderr,
        )
        return 1
    ids = [by_story[n] for n in names]
    if args.print_field == "story-ids":
        print(" ".join(names))
    else:
        print(" ".join(ids))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
