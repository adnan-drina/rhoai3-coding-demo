#!/usr/bin/env python3
"""AD-H §16.9 / AR-4.3 — run journal body + pre/post digests.

Sources:
  - evidence/runs/*.json          (run journals, schema rhoai3.run-journal/v1)
  - evidence/bodies/*.sha256.json (body digest sidecars)

Refuses schema drift, missing journal fields, body digest drift, and retries
that reused more than one body digest for the same task_id.

Usage:
  python3 check-run-digests.py                 # scan the current directory
  python3 check-run-digests.py /path/to/repo   # scan an explicit workspace root
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SCHEMA = "rhoai3.run-journal/v1"

EXIT_CODES = """\
Exit codes:
  0  pass — digests consistent, or lint idle (no run journals and no body
     digest sidecars)
  1  BLOCK — at least one FAIL: line on stderr (unparseable journal/sidecar,
     bad schema, missing required field, body digest drift, or multi-digest
     retries for one task_id)
  2  usage error (bad/unknown arguments; emitted by argparse)
"""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="workspace root to scan (default: current directory)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    runs = root / "evidence" / "runs"
    sidecars = list((root / "evidence" / "bodies").glob("*.sha256.json")) if (
        root / "evidence" / "bodies"
    ).is_dir() else []
    journals = list(runs.glob("*.json")) if runs.is_dir() else []

    if not journals and not sidecars:
        print("OK: AR-4.3 idle (no run journals / body digest sidecars)")
        return 0

    bad = 0
    # Sidecars must match current body bytes
    for sc in sidecars:
        try:
            stamp = json.loads(sc.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"FAIL: AR-4.3 {sc.name}: {e}", file=sys.stderr)
            bad = 1
            continue
        bpath = Path(stamp.get("body_path") or "")
        if not bpath.is_file():
            cand = root / "evidence" / "bodies" / sc.name.replace(".sha256.json", "")
            # *.json.sha256.json → *.json
            name = sc.name[: -len(".sha256.json")]
            cand = root / "evidence" / "bodies" / name
            bpath = cand if cand.is_file() else bpath
        if not bpath.is_file():
            print(f"FAIL: AR-4.3 {sc.name}: body_path missing", file=sys.stderr)
            bad = 1
            continue
        actual = sha256_file(bpath)
        if actual != stamp.get("body_sha256"):
            print(
                f"FAIL: AR-4.3 {sc.name}: body digest drift "
                f"(stamp={stamp.get('body_sha256')} actual={actual})",
                file=sys.stderr,
            )
            bad = 1

    by_task: dict[str, set[str]] = {}
    for path in journals:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"FAIL: AR-4.3 {path.name}: {e}", file=sys.stderr)
            bad = 1
            continue
        if doc.get("schema") != SCHEMA:
            print(f"FAIL: AR-4.3 {path.name}: bad schema", file=sys.stderr)
            bad = 1
            continue
        for req in ("task_id", "run_id", "body_path", "body_sha256", "pre_tree_sha256", "post_tree_sha256"):
            if not doc.get(req):
                print(f"FAIL: AR-4.3 {path.name}: missing {req}", file=sys.stderr)
                bad = 1
        tid = str(doc.get("task_id") or "")
        bsha = str(doc.get("body_sha256") or "")
        by_task.setdefault(tid, set()).add(bsha)
        # verify body bytes if present
        bp = Path(str(doc.get("body_path")))
        if not bp.is_file():
            bp = root / str(doc.get("body_path"))
        if bp.is_file() and sha256_file(bp) != bsha:
            print(f"FAIL: AR-4.3 {path.name}: body_sha256 mismatch vs file", file=sys.stderr)
            bad = 1

    for tid, digests in by_task.items():
        if len(digests) > 1:
            print(
                f"FAIL: AR-4.3 task {tid}: retries used multiple body digests {digests}",
                file=sys.stderr,
            )
            bad = 1

    if bad:
        print("AR-4.3 run digests FAILED", file=sys.stderr)
        return 1
    print(
        f"OK: AR-4.3 run digests (journals={len(journals)} sidecars={len(sidecars)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
