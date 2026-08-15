#!/usr/bin/env python3
"""EX-4: print the seat Kanban assignee profile for a phase.

Walks up to migration.yaml (SR-2). Refuses assignee default. Catalog:
.hermes/skills/harness/dispatch-phase/references/assignee-profiles.json
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
        raise SystemExit(f"EX-4: missing assignee catalog {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("EX-4: catalog is not an object")
    return data


def resolve(phase: str, data: dict) -> str:
    phases = data.get("phases") or {}
    profiles = data.get("profiles") or {}
    name = phases.get(phase)
    if not name:
        raise SystemExit(f"EX-4: no seat assignee mapped for phase {phase!r}")
    if name == "default":
        raise SystemExit("EX-4: assignee default is the identity hole — refused")
    spec = profiles.get(name)
    if not isinstance(spec, dict):
        raise SystemExit(f"EX-4: profile {name!r} missing from catalog")
    desc = (spec.get("description") or "").strip()
    if not desc:
        raise SystemExit(f"EX-4: profile {name!r} has empty description")
    return name


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Print the EX-4 seat assignee profile for a Kanban phase."
    )
    p.add_argument("phase", help="M1|M2|M3|M4|M5|factory (M2a/M2b map to planner)")
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
