#!/usr/bin/env python3
"""Card ↔ live-sidecar digest cross-assert (Operator E-20260812T061639Z).

REFUSE when a kanban card's AR-4.3 body-digest line does not match the live
typed-body sidecar sha256. Closes the stale-digest family at the ack-regen /
create-ack choke point (third surface after v11 bodies + complete-cmd scan).

Usage:
  assert-card-body-digest-match.py <root> --task-id t_xxx --body evidence/bodies/m3-s-003.json
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import sys
from pathlib import Path

DIGEST_RE = re.compile(r"Body digest \(AR-4\.3\): `([0-9a-f]{64})`")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--body", required=True, help="typed body JSON path (relative to root or absolute)")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    body = Path(args.body)
    if not body.is_absolute():
        body = (root / body).resolve()
    if not body.is_file():
        print(f"FAIL: missing body {body}", file=sys.stderr)
        return 1
    live = sha256_file(body)
    db = root / ".hermes" / "home" / "kanban.db"
    if not db.is_file():
        print(f"FAIL: missing kanban.db {db}", file=sys.stderr)
        return 1
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = conn.execute("select body from tasks where id=?", (args.task_id,)).fetchone()
    finally:
        conn.close()
    if not row or row[0] is None:
        print(f"FAIL: unknown task {args.task_id}", file=sys.stderr)
        return 1
    m = DIGEST_RE.search(row[0])
    if not m:
        print(
            f"FAIL: card {args.task_id} missing Body digest (AR-4.3) line",
            file=sys.stderr,
        )
        return 1
    card = m.group(1)
    if card != live:
        print(
            f"REFUSE: card↔sidecar digest mismatch task={args.task_id} "
            f"card={card} live={live} body={body} "
            f"(Operator E-20260812T061639Z / Architect E-20260812T061718Z)",
            file=sys.stderr,
        )
        return 1
    # Also refuse any OTHER 64-hex digests in the card markdown (obligation
    # "Verify … matches `…`" / --expect lines). Partial restamps left those
    # stale and caused S-003 run#65 typed BLOCK (Review E-20260812T063915Z).
    extras = sorted({h for h in re.findall(r"[0-9a-f]{64}", row[0]) if h != live})
    if extras:
        print(
            f"REFUSE: card {args.task_id} has stale obligation digest(s) "
            f"{[e[:16] for e in extras]} != live {live[:16]} "
            f"(must replace ALL body-digest occurrences on restamp)",
            file=sys.stderr,
        )
        return 1
    print(f"OK: card↔sidecar digest match task={args.task_id} sha256={live}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
