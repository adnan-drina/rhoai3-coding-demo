#!/usr/bin/env python3
"""C-2(a): print the seat Kanban assignee. Single-persona — always default.

Walks up to migration.yaml (SR-2). Catalog may still list retired names;
this resolver ignores them. Product `default` is the worker identity.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CATALOG_REL = (
    Path(".hermes")
    / "skills"
    / "harness"
    / "dispatch-phase"
    / "references"
    / "assignee-profiles.json"
)

SINGLE_PERSONA = "default"


def migration_root(start: Path) -> Path:
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent
    while True:
        if (cur / "migration.yaml").is_file():
            return cur
        if cur == cur.parent:
            raise SystemExit("cannot find project root (migration.yaml) (SR-2)")
        cur = cur.parent


def load_catalog(root: Path) -> dict:
    path = root / CATALOG_REL
    if not path.is_file():
        raise SystemExit(f"C-2(a): missing assignee catalog {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("C-2(a): catalog is not an object")
    return data


def resolve(phase: str, data: dict) -> str:
    """C-2(a): every phase resolves to default. Catalog is documentation only."""
    _ = phase, data
    return SINGLE_PERSONA


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Print the C-2(a) single-persona seat assignee (always default)."
    )
    p.add_argument("phase", help="M1|M2|M3|M4|M5|factory (all map to default)")
    p.add_argument(
        "--root",
        default="",
        help="scaffold root (default: walk up to migration.yaml from this script)",
    )
    args = p.parse_args(argv)
    root = Path(args.root).resolve() if args.root else migration_root(Path(__file__))
    name = resolve(args.phase, load_catalog(root))
    print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
