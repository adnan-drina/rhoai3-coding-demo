#!/usr/bin/env python3
"""Parse Red Hat Quarkus platform GAV from .hermes/pins.json.

Root is found by walking up to migration.yaml (SR-2) — never a parent-count.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def resolve_migration_root(start: Path) -> Path:
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent
    while True:
        if (cur / "migration.yaml").is_file():
            return cur
        if cur == cur.parent:
            raise FileNotFoundError(
                f"no migration.yaml walking up from {start} (SR-2)"
            )
        cur = cur.parent


def quarkus_platform_gav(root: Path) -> str:
    path = root / ".hermes" / "pins.json"
    if not path.is_file():
        raise FileNotFoundError(str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    pins = data.get("pins") if isinstance(data, dict) else None
    if not isinstance(pins, dict):
        raise ValueError("pins.json missing pins object")
    qp = pins.get("quarkus_platform") or {}
    g = str(qp.get("group_id") or "").strip()
    a = str(qp.get("bom_artifact_id") or "").strip()
    v = str(qp.get("version") or "").strip()
    if not (g and a and v):
        raise ValueError("quarkus_platform incomplete in .hermes/pins.json")
    return f"{g}:{a}:{v}"


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        print("Parse Red Hat Quarkus platform GAV from .hermes/pins.json.")
        print("usage: parse-platform-gav.py [<scaffold-root>]")
        return 0
    start = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve()
    try:
        root = resolve_migration_root(start)
        print(quarkus_platform_gav(root))
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
