#!/usr/bin/env python3
"""Card ↔ sidecar ↔ file digest triple (Operator E-20260812T061639Z / V35-DIGEST).

REFUSE when the kanban card's AR-4.3 digest line, the sidecar body_sha256,
or the live typed-body file disagree. Holder complete must not pass on
card==sidecar!=file.

Usage:
  assert-card-body-digest-match.py <root> --task-id t_xxx --body evidence/bodies/m3-s-003.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

DIGEST_RES = (
    re.compile(r"Body digest \(AR-4\.3\): `([0-9a-f]{64})`"),
    re.compile(r"AR-4\.3 digest: ([0-9a-f]{64})"),
    re.compile(r"--expect ([0-9a-f]{64})"),
)


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
    sidecar = body.with_suffix(body.suffix + ".sha256.json")
    if not sidecar.is_file():
        print(f"FAIL: missing sidecar {sidecar}", file=sys.stderr)
        return 1
    try:
        side_doc = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: sidecar {sidecar}: {exc}", file=sys.stderr)
        return 1
    side = str(side_doc.get("body_sha256") or "").strip().lower()
    if side != live:
        print(
            f"REFUSE: sidecar↔file digest mismatch task={args.task_id} "
            f"sidecar={side} live={live} body={body}",
            file=sys.stderr,
        )
        return 1
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
    found: list[str] = []
    for rx in DIGEST_RES:
        found.extend(rx.findall(row[0]))
    if not found:
        print(
            f"FAIL: card {args.task_id} missing AR-4.3 digest line "
            "(Body digest / AR-4.3 digest / --expect)",
            file=sys.stderr,
        )
        return 1
    mismatched = sorted({h for h in found if h != live})
    if mismatched:
        print(
            f"REFUSE: card↔sidecar↔file digest mismatch task={args.task_id} "
            f"card={mismatched[0]} sidecar={side} live={live} body={body} "
            f"(Operator E-20260812T061639Z / Architect E-20260812T061718Z / V35-DIGEST)",
            file=sys.stderr,
        )
        return 1
    extras = sorted({h for h in re.findall(r"[0-9a-f]{64}", row[0]) if h != live})
    if extras:
        print(
            f"REFUSE: card {args.task_id} has stale obligation digest(s) "
            f"{[e[:16] for e in extras]} != live {live[:16]} "
            f"(must replace ALL body-digest occurrences on restamp)",
            file=sys.stderr,
        )
        return 1
    print(f"OK: card↔sidecar↔file digest match task={args.task_id} sha256={live}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
