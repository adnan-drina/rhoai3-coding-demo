#!/usr/bin/env python3
"""M3 wave-holder / M2 procedure checkpoint (not dest write-set).

Architect E-20260819T131337Z adopted checkpoint.json for M2 next dest.
Operator E-20260819T132404Z: the holder is the multi-step Procedure and
needs it at least as much. Recollection skipped attach on v32 resume.
V34-3: same script, --kind m2 (rhoai3.m2-checkpoint/v1). Do not grow mint.

Usage:
  python3 holder-checkpoint.py init --task-id t_xxx [--root .] [--kind holder|m2]
  python3 holder-checkpoint.py stamp --task-id t_xxx --next create:US1 \\
      [--ack-gate t_ack] [--story-id setup --child-id t_yyy --skills a,b]
  python3 holder-checkpoint.py check --task-id t_xxx [--root .] [--kind holder|m2]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMAS = {
    "holder": "rhoai3.m3-holder-checkpoint/v1",
    "m2": "rhoai3.m2-checkpoint/v1",
}
M2_NEXT = frozenset(
    {"preseed", "findings", "inventory", "speckit", "assemble", "done"}
)


def cp_path(root: Path, task_id: str) -> Path:
    return root / "evidence" / "runs" / task_id / "checkpoint.json"


def schema_for(kind: str) -> str:
    if kind not in SCHEMAS:
        raise ValueError(f"unknown kind {kind!r}")
    return SCHEMAS[kind]


def load(path: Path, kind: str = "holder") -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    want = schema_for(kind)
    if not isinstance(data, dict) or data.get("schema") != want:
        raise ValueError(f"not {want}: {path}")
    return data


def valid_next(value: str, kind: str = "holder") -> bool:
    if kind == "m2":
        return value in M2_NEXT
    if value in {"lint", "ack_gate", "mint-m4", "mint-m5", "pre-complete", "done"}:
        return True
    return value.startswith("create:") and len(value) > len("create:")


def cmd_init(root: Path, task_id: str, kind: str) -> int:
    out = cp_path(root, task_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    label = "M2" if kind == "m2" else "holder"
    first = "preseed" if kind == "m2" else "lint"
    if out.is_file():
        existing = load(out, kind)
        print(
            f"OK: existing {label} checkpoint {out.relative_to(root)} "
            f"next={existing.get('next')}"
        )
        return 0
    payload = {
        "schema": schema_for(kind),
        "kind": kind,
        "task_id": task_id,
        "next": first,
        "ack_gate_id": None,
        "stories": {},
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"OK: init {out.relative_to(root)} next={first}")
    return 0


def cmd_stamp(
    root: Path,
    task_id: str,
    nxt: str,
    ack_gate: str,
    story_id: str,
    child_id: str,
    skills: str,
    kind: str,
) -> int:
    if not valid_next(nxt, kind):
        allowed = (
            "|".join(sorted(M2_NEXT))
            if kind == "m2"
            else "lint|ack_gate|mint-m4|mint-m5|pre-complete|done|create:<id>"
        )
        print(
            f"FAIL: invalid --next {nxt!r}; allowed={allowed}",
            file=sys.stderr,
        )
        return 1
    path = cp_path(root, task_id)
    if not path.is_file():
        print(f"FAIL: missing checkpoint {path} — run init first", file=sys.stderr)
        return 1
    data = load(path, kind)
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


def cmd_check(root: Path, task_id: str, kind: str) -> int:
    path = cp_path(root, task_id)
    label = "M2" if kind == "m2" else "holder"
    if not path.is_file():
        print(
            f"FAIL: missing {label} checkpoint {path} "
            "(init before first Procedure step)",
            file=sys.stderr,
        )
        return 1
    data = load(path, kind)
    nxt = str(data.get("next") or "")
    if not valid_next(nxt, kind):
        print(f"FAIL: checkpoint next invalid: {nxt!r}", file=sys.stderr)
        return 1
    print(f"OK: {label} checkpoint next={nxt} stories={len(data.get('stories') or {})}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("init", "stamp", "check"))
    ap.add_argument("--task-id", default="")
    ap.add_argument("--root", default=".")
    ap.add_argument("--kind", choices=("holder", "m2"), default="holder")
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
        if args.nxt:
            allowed = "|".join(sorted(M2_NEXT)) if args.kind == "m2" else "stamp --next <step>"
            print(
                "FAIL: init does not take --next; use stamp --next "
                f"({allowed})",
                file=sys.stderr,
            )
            return 1
        return cmd_init(root, task_id, args.kind)
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
            args.kind,
        )
    return cmd_check(root, task_id, args.kind)


if __name__ == "__main__":
    raise SystemExit(main())
