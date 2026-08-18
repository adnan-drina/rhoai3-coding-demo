#!/usr/bin/env python3
"""Mint-side write-set **cache** emission (Architect 35099226).

Writes evidence/runtime/write-sets/<task_id>.json from a typed body's
files_writable. The fence does **not** read this file for policy. Spawn
hydrate may copy it into HERMES_KANBAN_FILES_WRITABLE once. v24 does not
claim a new trust boundary.

Usage:
  python3 emit-write-set-cache.py --root . --task-id t_abcdef --body evidence/bodies/m3-setup.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def files_writable_of(obj: dict) -> list[str]:
    body = obj.get("body") if isinstance(obj.get("body"), dict) else obj
    if not isinstance(body, dict):
        raise SystemExit("FAIL: body is not an object")
    if "files_writable" in body:
        fw = body.get("files_writable")
    elif "write_set" in body:
        fw = body.get("write_set")
    else:
        raise SystemExit("FAIL: body missing files_writable")
    if not isinstance(fw, list):
        raise SystemExit("FAIL: files_writable is not a list")
    return [str(x) for x in fw if str(x).strip()]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Emit dest write-set cache (not fence policy).")
    p.add_argument("--root", default=".", help="scaffold/dest root")
    p.add_argument("--task-id", required=True, help="Hermes t_<hex> card id")
    p.add_argument("--body", required=True, help="typed body JSON path")
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    tid = args.task_id.strip()
    if not tid.startswith("t_"):
        print(f"FAIL: task-id {tid!r} is not Hermes t_<hex> hygiene", file=sys.stderr)
        return 2
    body_path = Path(args.body)
    if not body_path.is_absolute():
        body_path = root / body_path
    obj = json.loads(body_path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        print("FAIL: body JSON is not an object", file=sys.stderr)
        return 2
    fw = files_writable_of(obj)
    out_dir = root / "evidence" / "runtime" / "write-sets"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{tid}.json"
    doc = {
        "schema": "rhoai3.write-set-cache/v1",
        "authority": "cache-not-policy",
        "task_id": tid,
        "files_writable": fw,
    }
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    if not out.is_file() or out.stat().st_size < 2:
        print(f"FAIL: cache not written {out}", file=sys.stderr)
        return 2
    print(f"OK: write-set cache {out.relative_to(root)} task_id={tid} n={len(fw)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
