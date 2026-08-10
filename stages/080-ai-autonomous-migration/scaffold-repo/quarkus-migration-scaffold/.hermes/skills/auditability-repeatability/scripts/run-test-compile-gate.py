#!/usr/bin/env python3
"""Run mvn test-compile and stamp gate evidence (S-010 Class A #1b invariant)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "rhoai3.test-compile-gate/v1"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task-id", required=True)
    ap.add_argument(
        "--paths",
        action="append",
        default=[],
        help="Dest paths this gate covers (repeatable)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not (root / "pom.xml").is_file():
        print(f"FAIL: no pom.xml under {root}", file=sys.stderr)
        return 1
    cp = subprocess.run(
        ["mvn", "-q", "test-compile"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    out_dir = root / "migration" / "runs" / args.task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEMA,
        "task_id": args.task_id,
        "cmd": "mvn -q test-compile",
        "rc": cp.returncode,
        "ok": cp.returncode == 0,
        "paths": args.paths,
        "evaluated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stderr_tail": (cp.stderr or "")[-400:],
    }
    out = out_dir / "test-compile-gate.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if cp.returncode != 0:
        print(
            f"FAIL: test-compile gate rc={cp.returncode} → {out.relative_to(root)}",
            file=sys.stderr,
        )
        return 1
    print(f"OK: test-compile gate → {out.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
