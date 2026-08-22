#!/usr/bin/env python3
"""Register destination wipe tombstones (Architect E-20260811T170706Z Class A).

Usage:
  python3 register-quarantine-tombstone.py /projects/modernized \
    --path src/main/java/.../PetRepositoryOverride.java \
    --reason "abort-run OOS Override residue" \
    [--task-id t_xxx] [--quarantine-dir migration/quarantine/...]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "rhoai3.quarantine-tombstones/v1"


def norm_rel(path: str) -> str:
    p = path.replace("\\", "/").lstrip("./")
    for prefix in (
        "/projects/modernized/",
        "projects/modernized/",
    ):
        if p.startswith(prefix):
            p = p[len(prefix) :]
    return p


def load(path: Path) -> dict:
    if not path.is_file():
        return {"schema": SCHEMA, "tombstones": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"schema": SCHEMA, "tombstones": []}
    data.setdefault("schema", SCHEMA)
    data.setdefault("tombstones", [])
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--path", action="append", required=True, dest="paths")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--task-id", default="")
    ap.add_argument("--quarantine-dir", default="")
    args = ap.parse_args()

    root = args.root.resolve()
    out = root / "evidence" / "quarantine" / "tombstones.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = load(out)
    by_path = {
        str(t.get("path")): t
        for t in data["tombstones"]
        if isinstance(t, dict) and t.get("path")
    }
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for raw in args.paths:
        rel = norm_rel(raw)
        by_path[rel] = {
            "path": rel,
            "reason": args.reason,
            "task_id": args.task_id,
            "quarantine_dir": args.quarantine_dir,
            "registered_at": now,
        }
        print(f"TOMBSTONE {rel}")
    data["tombstones"] = sorted(by_path.values(), key=lambda t: t["path"])
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"OK: wrote {out} count={len(data['tombstones'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
