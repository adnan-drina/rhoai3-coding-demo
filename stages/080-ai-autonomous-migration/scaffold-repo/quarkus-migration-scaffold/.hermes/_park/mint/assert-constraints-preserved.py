#!/usr/bin/env python3
"""Fail-closed: body amend must not silently drop constraints (Class A).

Architect E-20260811T182820Z / Operator E-20260811T182650Z — regression #2
(same class as t_29ccead3 forbid-drop): ApplicationService scope fix dropped the
entire constraints block (IfBuildProfile forbid / di-config path / sequence).

Usage:
  # Snapshot before amend
  python3 assert-constraints-preserved.py /projects/modernized \
    --body evidence/bodies/m3-s-002a.json --snapshot-before

  # After amend (compares to snapshot, or to --baseline)
  python3 assert-constraints-preserved.py /projects/modernized \
    --body evidence/bodies/m3-s-002a.json --check

  # Explicit baseline file
  python3 assert-constraints-preserved.py /projects/modernized \
    --body evidence/bodies/m3-s-002a.json --baseline /tmp/old.json --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SCHEMA = "rhoai3.constraints-snapshot/v1"


def load_body(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw.get("body"), dict):
        return raw["body"]
    return raw


def constraints_of(body: dict) -> list[str]:
    raw = body.get("constraints")
    if raw is None:
        return []
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            if isinstance(item, str):
                out.append(item.strip())
            elif isinstance(item, dict):
                out.append(json.dumps(item, sort_keys=True))
        return out
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    return [json.dumps(raw, sort_keys=True)]


def norm_set(items: list[str]) -> set[str]:
    return {i for i in items if i}


def snapshot_path(root: Path, body: Path) -> Path:
    digest = hashlib.sha256(str(body.resolve()).encode()).hexdigest()[:12]
    return root / "evidence" / "receipts" / "constraints-snapshots" / f"{digest}.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--body", required=True)
    ap.add_argument("--snapshot-before", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--baseline", default="")
    args = ap.parse_args()
    if not args.snapshot_before and not args.check:
        print("FAIL: pass --snapshot-before or --check", file=sys.stderr)
        return 2
    root = Path(args.root).resolve()
    body_path = Path(args.body)
    if not body_path.is_file():
        body_path = root / args.body
    if not body_path.is_file():
        print(f"FAIL: body not found: {args.body}", file=sys.stderr)
        return 2
    body = load_body(body_path)
    cur = constraints_of(body)

    if args.snapshot_before:
        snap = {
            "schema": SCHEMA,
            "body": str(body_path),
            "constraints": cur,
            "count": len(cur),
        }
        out = snapshot_path(root, body_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(snap, indent=2) + "\n", encoding="utf-8")
        print(f"OK: snapshot constraints={len(cur)} → {out.relative_to(root)}")
        return 0

    # --check
    if args.baseline:
        base_path = Path(args.baseline)
        if not base_path.is_file():
            base_path = root / args.baseline
        base_body = load_body(base_path)
        before = norm_set(constraints_of(base_body))
    else:
        snap_p = snapshot_path(root, body_path)
        if not snap_p.is_file():
            print(
                f"FAIL: no constraints snapshot at {snap_p} — run --snapshot-before "
                "before amend (Architect E-20260811T182820Z)",
                file=sys.stderr,
            )
            return 2
        snap = json.loads(snap_p.read_text(encoding="utf-8"))
        before = norm_set(list(snap.get("constraints") or []))
    after = norm_set(cur)
    missing = sorted(before - after)
    if missing:
        print(
            "FAIL: CONSTRAINTS_PRESERVATION (Architect E-20260811T182820Z Class A) — "
            f"amend dropped {len(missing)} prior constraint(s):",
            file=sys.stderr,
        )
        for m in missing:
            print(f"  - {m[:200]}", file=sys.stderr)
        print(
            "Restore constraints (forbid / di-config path / sequence) before minting "
            "ack-request. Silent constraint loss is refuse.",
            file=sys.stderr,
        )
        return 1
    if before and not after:
        print("FAIL: constraints became empty", file=sys.stderr)
        return 1
    print(
        f"OK: constraints preserved "
        f"(before={len(before)} after={len(after)} added={len(after - before)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
