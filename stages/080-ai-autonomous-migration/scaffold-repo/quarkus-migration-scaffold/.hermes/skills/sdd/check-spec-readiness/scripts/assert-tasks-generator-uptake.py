#!/usr/bin/env python3
"""V35-M2-UPTAKE — tasks.md must name the dest generator when types are generated.

Golden tasks-template T013 already requires configure-in-pom. Spec Kit may
omit it. Refuse M2 complete / scratch-assemble when type-inventory has
generated types and tasks.md has no generator plugin token.

Do not dest-rewrite tasks.md. Do not add a second template line.

Usage:
  python3 assert-tasks-generator-uptake.py <root> [--tasks tasks.md]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from generated_sources import GENERATOR_AID_RE

PLUGIN_TOKEN = "openapi-generator-maven-plugin"


def _generated_rows(root: Path) -> list[dict]:
    inv = root / "evidence" / "type-inventory.json"
    if not inv.is_file():
        return []
    try:
        data = json.loads(inv.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = data if isinstance(data, list) else (data or {}).get("types") or []
    if not isinstance(rows, list):
        return []
    out: list[dict] = []
    for rec in rows:
        if not isinstance(rec, dict):
            continue
        if rec.get("generated") is True or str(rec.get("provider") or "") == "generated":
            out.append(rec)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--tasks", default="tasks.md")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    generated = _generated_rows(root)
    if not generated:
        print("OK: M2-UPTAKE skip (no generated types in type-inventory)")
        return 0
    tasks = Path(args.tasks)
    if not tasks.is_file():
        tasks = root / args.tasks
    if not tasks.is_file():
        print(f"FAIL: missing tasks.md {args.tasks}", file=sys.stderr)
        return 1
    text = tasks.read_text(encoding="utf-8", errors="ignore")
    if PLUGIN_TOKEN in text or GENERATOR_AID_RE.search(text):
        print(f"OK: M2-UPTAKE tasks.md names generator plugin n={len(generated)}")
        return 0
    print(
        "REFUSE: M2_UPTAKE type-inventory has generated types but tasks.md "
        f"has no generator plugin token ({PLUGIN_TOKEN})",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
