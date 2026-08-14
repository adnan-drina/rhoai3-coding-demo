#!/usr/bin/env python3
"""Deterministic M3 body assembler (Architect E-20260814T181701Z).

Copies partition fields. Stamps the singleton class-legal exit. Does not invent
oracles. Unknown operand_class refuses (T-8 fail-closed).

Does not mint. Does not dispatch a worker.

Usage:
  python3 assemble-m3-bodies-from-partition.py <root> [--dry-run]
  python3 assemble-m3-bodies-from-partition.py <root> --write
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from specimen_agnostic import (  # noqa: E402
    OPERAND_CLASS_SEMANTIC_EXITS,
    PREFERRED_SEMANTIC_EXIT_CMD,
    preferred_semantic_exit_for,
)


def _paths(item) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for k in ("path", "file", "dest", "dst", "src"):
            if item.get(k):
                return str(item[k])
    return ""


def assemble_one(story: dict) -> dict:
    sid = str(story.get("story_id") or "").strip()
    oc = str(story.get("operand_class") or "").strip()
    if not sid:
        raise ValueError("partition story missing story_id")
    if oc not in OPERAND_CLASS_SEMANTIC_EXITS:
        raise ValueError(
            f"{sid}: unknown operand_class={oc!r} — no legal exit set "
            "(T-8 fail-closed, Architect E-20260814T181701Z)"
        )
    check = preferred_semantic_exit_for(oc)
    if not check:
        raise ValueError(f"{sid}: operand_class={oc!r} has no preferred stamp")
    fis = [_paths(x) for x in (story.get("files_in_scope") or [])]
    fis = [p for p in fis if p]
    if not fis:
        raise ValueError(f"{sid}: empty files_in_scope (PB-2 / S-012)")
    cmd = PREFERRED_SEMANTIC_EXIT_CMD.get(check, check)
    return {
        "phase": "M3",
        "task_type": "implementing",
        "identity": {"story_id": sid, "operand_class": oc},
        "files_in_scope": fis,
        "files_writable": fis,
        "exit_criteria": [{"check": check, "cmd": cmd}],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    if args.write and args.dry_run:
        print("assemble-m3-bodies: use --dry-run or --write, not both", file=sys.stderr)
        return 2
    if not args.write:
        args.dry_run = True

    root = Path(args.root).resolve()
    part = root / "evidence/briefs/partition.json"
    if not part.is_file():
        print(f"FAIL: missing {part}", file=sys.stderr)
        return 1
    data = json.loads(part.read_text(encoding="utf-8"))
    stories = data.get("stories") or data.get("units") or []
    out_dir = root / "evidence/bodies"
    assembled: list[tuple[str, dict]] = []
    for s in stories:
        if not isinstance(s, dict):
            continue
        body = assemble_one(s)
        sid = body["identity"]["story_id"]
        assembled.append((sid, body))

    if not assembled:
        print("FAIL: partition has zero stories", file=sys.stderr)
        return 1

    for sid, body in assembled:
        oc = body["identity"]["operand_class"]
        check = body["exit_criteria"][0]["check"]
        n = len(body["files_writable"])
        dest = out_dir / f"m3-{sid}.json"
        print(f"{sid} operand_class={oc} exit={check} files_writable={n} -> {dest}")
        if args.write:
            out_dir.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")

    mode = "WRITE" if args.write else "DRY-RUN"
    print(f"OK: assemble-m3-bodies {mode} n={len(assembled)} (no mint)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
