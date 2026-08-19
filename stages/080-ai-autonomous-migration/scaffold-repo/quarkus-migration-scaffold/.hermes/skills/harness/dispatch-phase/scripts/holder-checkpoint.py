#!/usr/bin/env python3
"""M3 wave-holder procedure checkpoint (not dest write-set).

Architect E-20260819T131337Z adopted checkpoint.json for M2 next dest.
Operator E-20260819T132404Z: the holder is the multi-step Procedure and
needs it at least as much. Recollection skipped attach on v32 resume.

Usage:
  python3 holder-checkpoint.py init --task-id t_xxx [--root .]
  python3 holder-checkpoint.py stamp --task-id t_xxx --next create:US1 \\
      [--ack-gate t_ack] [--story-id setup --child-id t_yyy --skills a,b]
  python3 holder-checkpoint.py check --task-id t_xxx [--root .]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "rhoai3.m3-holder-checkpoint/v1"


def cp_path(root: Path, task_id: str) -> Path:
    return root / "evidence" / "runs" / task_id / "checkpoint.json"


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError(f"not {SCHEMA}: {path}")
    return data


def valid_next(value: str) -> bool:
    if value in {"lint", "ack_gate", "mint-m4", "mint-m5", "pre-complete", "done"}:
        return True
    return value.startswith("create:") and len(value) > len("create:")


def cmd_init(root: Path, task_id: str) -> int:
    out = cp_path(root, task_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file():
        existing = load(out)
        print(
            f"OK: existing holder checkpoint {out.relative_to(root)} "
            f"next={existing.get('next')}"
        )
        return 0
    payload = {
        "schema": SCHEMA,
        "task_id": task_id,
        "next": "lint",
        "ack_gate_id": None,
        "stories": {},
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"OK: init {out.relative_to(root)} next=lint")
    return 0


def cmd_stamp(
    root: Path,
    task_id: str,
    nxt: str,
    ack_gate: str,
    story_id: str,
    child_id: str,
    skills: str,
) -> int:
    if not valid_next(nxt):
        print(f"FAIL: invalid --next {nxt!r}", file=sys.stderr)
        return 1
    path = cp_path(root, task_id)
    if not path.is_file():
        print(f"FAIL: missing checkpoint {path} — run init first", file=sys.stderr)
        return 1
    data = load(path)
    data["next"] = nxt
    if ack_gate:
        data["ack_gate_id"] = ack_gate
    if story_id:
        stories = data.setdefault("stories", {})
        if not isinstance(stories, dict):
            stories = {}
            data["stories"] = stories
        entry = stories.get(story_id) if isinstance(stories.get(story_id), dict) else {}
        if child_id:
            entry["task_id"] = child_id
        if skills:
            entry["skills"] = [s.strip() for s in skills.split(",") if s.strip()]
        stories[story_id] = entry
    data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"OK: stamp {path.relative_to(root)} next={nxt}")
    return 0


def cmd_check(root: Path, task_id: str) -> int:
    path = cp_path(root, task_id)
    if not path.is_file():
        print(
            f"FAIL: missing holder checkpoint {path} "
            "(init before first Procedure step)",
            file=sys.stderr,
        )
        return 1
    data = load(path)
    nxt = str(data.get("next") or "")
    if not valid_next(nxt):
        print(f"FAIL: checkpoint next invalid: {nxt!r}", file=sys.stderr)
        return 1
    print(f"OK: holder checkpoint next={nxt} stories={len(data.get('stories') or {})}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("init", "stamp", "check"))
    ap.add_argument("--task-id", default="")
    ap.add_argument("--root", default=".")
    ap.add_argument("--next", dest="nxt", default="")
    ap.add_argument("--ack-gate", default="")
    ap.add_argument("--story-id", default="")
    ap.add_argument("--child-id", default="")
    ap.add_argument("--skills", default="")
    args = ap.parse_args()
    task_id = (args.task_id or os.environ.get("HERMES_KANBAN_TASK") or "").strip()
    if not task_id:
        print("FAIL: --task-id or HERMES_KANBAN_TASK required", file=sys.stderr)
        return 1
    root = Path(args.root).resolve()
    if args.action == "init":
        return cmd_init(root, task_id)
    if args.action == "stamp":
        if not args.nxt:
            print("FAIL: stamp requires --next", file=sys.stderr)
            return 1
        return cmd_stamp(
            root,
            task_id,
            args.nxt,
            args.ack_gate,
            args.story_id,
            args.child_id,
            args.skills,
        )
    return cmd_check(root, task_id)


if __name__ == "__main__":
    raise SystemExit(main())
