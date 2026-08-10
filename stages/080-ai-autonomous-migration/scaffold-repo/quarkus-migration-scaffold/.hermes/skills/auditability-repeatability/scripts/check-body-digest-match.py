#!/usr/bin/env python3
"""Architect E-111424Z — refuse AR-4.3 body digest mismatch (immutability)."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SCHEMA = "rhoai3.body-digest/v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_pair(body: Path, expect: str, label: str) -> int:
    if not body.is_file():
        print(f"FAIL: {label}: body missing {body}", file=sys.stderr)
        return 1
    actual = sha256_file(body)
    if actual != expect:
        print(
            f"FAIL: {label}: body digest mismatch "
            f"(expect={expect} actual={actual}) — dispatched body immutable "
            f"(Architect E-111424Z / migration/contracts/body-immutability.md)",
            file=sys.stderr,
        )
        return 1
    print(f"OK: {label} body_sha256={actual}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--body", default=None, help="Typed body JSON path")
    ap.add_argument("--expect", default=None, help="Expected sha256 (card digest)")
    ap.add_argument(
        "--sidecar",
        default=None,
        help="rhoai3.body-digest/v1 sidecar (default: scan migration/bodies/*.sha256.json)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()

    if args.body and args.expect:
        body = Path(args.body)
        if not body.is_file():
            body = root / args.body
        return check_pair(body, args.expect.strip().lower(), str(body))

    sidecars: list[Path] = []
    if args.sidecar:
        p = Path(args.sidecar)
        if not p.is_file():
            p = root / args.sidecar
        sidecars = [p]
    else:
        d = root / "migration" / "bodies"
        if d.is_dir():
            sidecars = sorted(d.glob("*.sha256.json"))

    if not sidecars:
        print("OK: body-digest match idle (no sidecars / no --expect)")
        return 0

    bad = 0
    for sc in sidecars:
        try:
            stamp = json.loads(sc.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"FAIL: {sc}: {e}", file=sys.stderr)
            bad = 1
            continue
        if stamp.get("schema") != SCHEMA:
            print(f"FAIL: {sc.name}: bad schema {stamp.get('schema')!r}", file=sys.stderr)
            bad = 1
            continue
        expect = str(stamp.get("body_sha256") or "").strip().lower()
        bpath = Path(str(stamp.get("body_path") or ""))
        if not bpath.is_file():
            name = sc.name[: -len(".sha256.json")]
            cand = root / "migration" / "bodies" / name
            bpath = cand if cand.is_file() else bpath
        if not bpath.is_file() and args.body:
            bpath = Path(args.body)
            if not bpath.is_file():
                bpath = root / args.body
        bad |= check_pair(bpath, expect, sc.name)
    if bad:
        print("BODY_DIGEST mismatch checks FAILED", file=sys.stderr)
        return 1
    print(f"OK: body-digest match ({len(sidecars)} sidecar(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
