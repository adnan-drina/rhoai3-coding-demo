#!/usr/bin/env python3
"""AD-H §16.5 / AR-1.2 — Kanban comments are not executable authority.

Fails when a comment feed contains impersonating override prose from
`default` / worker authors (e.g. 'P1-B OVERRIDE (Lead)').

Inputs (any present):
  - evidence/authority/comment-feed.jsonl  (role, text per line)
  - governance/fixtures/authority/*.jsonl     (admission fixtures)
  - --feed PATH

Typed revisions live under evidence/authority/typed-revisions/*.json and
are the only comment-adjacent control-flow source (schema-validated separately).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

IMPERSONATE = re.compile(
    r"(?i)\b(OVERRIDE|HOLD\s+lift|UNPARK|DISPATCH)\b.*\bLead\b|"
    r"\bLead\b.*\b(OVERRIDE|HOLD\s+lift)\b|"
    r"\(Lead\)\s*$|"
    r"P1-[A-Z]\s+OVERRIDE\s*\(Lead\)"
)
WORKER_ROLES = frozenset({"default", "worker", "planner", "implementer", "spec-author", "agent"})


def iter_feed(path: Path) -> list[dict]:
    rows: list[dict] = []
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            rows = [x for x in data if isinstance(x, dict)]
        elif isinstance(data, dict) and isinstance(data.get("comments"), list):
            rows = [x for x in data["comments"] if isinstance(x, dict)]
        return rows
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError:
            rows.append({"role": "default", "text": ln})
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--feed", action="append", default=[], help="Extra feed path(s)")
    args = ap.parse_args()
    root = Path(args.root).resolve()

    feeds: list[Path] = []
    for rel in (
        "evidence/authority/comment-feed.jsonl",
        "evidence/authority/comment-feed.json",
    ):
        p = root / rel
        if p.is_file():
            feeds.append(p)
    fix = root / "governance/fixtures/authority"
    if fix.is_dir():
        feeds.extend(sorted(fix.glob("*.jsonl")))
        feeds.extend(sorted(fix.glob("*.json")))
    for f in args.feed:
        feeds.append(Path(f))

    if not feeds:
        print("OK: AR-1.2 idle (no comment feed)")
        return 0

    bad = 0
    seen = 0
    for feed in feeds:
        try:
            rows = iter_feed(feed)
        except Exception as e:
            print(f"FAIL: {feed}: {e}", file=sys.stderr)
            bad = 1
            continue
        for i, row in enumerate(rows):
            seen += 1
            role = str(row.get("role") or row.get("author") or row.get("assignee") or "").lower()
            text = str(row.get("text") or row.get("body") or row.get("comment") or "")
            if not text:
                continue
            if IMPERSONATE.search(text) and (not role or role in WORKER_ROLES):
                try:
                    label = str(feed.resolve().relative_to(root))
                except ValueError:
                    label = str(feed)
                print(
                    f"FAIL: AR-1.2 {label}[{i}]: role={role!r} comment claims Lead/override "
                    f"authority — comments≠executable",
                    file=sys.stderr,
                )
                bad = 1

    if bad:
        print("AR-1.2 comment authority FAILED", file=sys.stderr)
        return 1
    print(f"OK: AR-1.2 comment authority ({seen} comment(s) scanned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
