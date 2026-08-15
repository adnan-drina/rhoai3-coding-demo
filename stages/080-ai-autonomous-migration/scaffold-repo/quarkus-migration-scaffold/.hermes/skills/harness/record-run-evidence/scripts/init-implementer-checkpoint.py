#!/usr/bin/env python3
"""Init rhoai3.implementer-checkpoint/v1 from an M3 body write-set."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA = "rhoai3.implementer-checkpoint/v1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _normalize(item: Any) -> Optional[str]:
    if isinstance(item, str):
        p = item
    elif isinstance(item, dict):
        p = (
            item.get("dest")
            or item.get("dst")
            or item.get("destination")
            or item.get("src")
            or ""
        )
    else:
        return None
    p = str(p).replace("\\", "/")
    if "/projects/modernized/" in p:
        p = p.split("/projects/modernized/", 1)[1]
    if "/.derived/" in p or p.startswith("projects/legacy"):
        return None
    if not p.startswith("src/"):
        return None
    return p


def dest_paths(body: dict) -> list[str]:
    out: list[str] = []
    # Prefer explicit writable set; fall back to in-scope dests.
    keys = ("files_writable", "filesWritable", "files_in_scope", "filesInScope")
    for key in keys:
        items = body.get(key) or []
        if not isinstance(items, list) or not items:
            continue
        for item in items:
            p = _normalize(item)
            if p and p not in out:
                out.append(p)
        if key in ("files_writable", "filesWritable") and out:
            return out
    return out


def _print_existing_summary(out: Path, root: Path, existing: dict) -> None:
    try:
        rel = out.relative_to(root)
    except ValueError:
        rel = out
    completed = existing.get("completed") or []
    n_completed = len(completed) if isinstance(completed, list) else 0
    print(
        f"OK: existing checkpoint {rel} "
        f"next={existing.get('next', '?')} completed={n_completed} (idempotent retry)"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("body_json")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument(
        "--force",
        action="store_true",
        help="wipe/re-init checkpoint even when body_sha256 matches",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print planned checkpoint write (or keep existing) and exit 0",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    body_path = Path(args.body_json)
    if not body_path.is_file():
        body_path = root / args.body_json
    if not body_path.is_file():
        print(f"FAIL: body not found: {args.body_json}", file=sys.stderr)
        return 1
    body = json.loads(body_path.read_text(encoding="utf-8"))
    work = dest_paths(body)
    if not work:
        print("FAIL: no dest src/ paths in body write-set/scope", file=sys.stderr)
        return 1
    digest = sha256_file(body_path)
    try:
        rel_body = str(body_path.resolve().relative_to(root))
    except ValueError:
        rel_body = str(body_path)
    out_dir = root / "evidence" / "runs" / args.task_id
    out = out_dir / "checkpoint.json"

    if out.is_file() and not args.force:
        try:
            existing = json.loads(out.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = None
        if isinstance(existing, dict) and existing.get("body_sha256") == digest:
            if args.dry_run:
                print(
                    f"DRY-RUN: would keep existing {out.relative_to(root)} "
                    f"(body_sha256 matches; no write)"
                )
                _print_existing_summary(out, root, existing)
                return 0
            _print_existing_summary(out, root, existing)
            return 0

    ck = {
        "schema": SCHEMA,
        "task_id": args.task_id,
        "body_path": rel_body,
        "body_sha256": digest,
        "work_list": work,
        "completed": [],
        "next": work[0],
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": "init",
    }
    if args.dry_run:
        try:
            rel_out = out.relative_to(root)
        except ValueError:
            rel_out = out
        print(
            f"DRY-RUN: would write {rel_out} "
            f"next={ck['next']} work={len(work)} body_sha256={digest[:12]}…"
        )
        if out.is_file() and args.force:
            print(f"DRY-RUN: --force would replace existing {rel_out}")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ck, indent=2) + "\n", encoding="utf-8")
    print(f"OK: wrote {out.relative_to(root)} next={ck['next']} work={len(work)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
