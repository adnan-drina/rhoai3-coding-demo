#!/usr/bin/env python3
"""AR-4.3 — stamp body_sha256 next to a typed body (sidecar or stdout)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: stamp-body-digest.py <body.json> [out-sidecar.json]", file=sys.stderr)
        return 2
    body = Path(sys.argv[1]).resolve()
    if not body.is_file():
        print(f"FAIL: missing body {body}", file=sys.stderr)
        return 1
    digest = sha256_file(body)
    try:
        doc = json.loads(body.read_text(encoding="utf-8"))
        task_id = str(doc.get("task_id") or doc.get("id") or body.stem)
    except Exception:
        task_id = body.stem
    stamp = {
        "schema": "rhoai3.body-digest/v1",
        "task_id": task_id,
        "body_path": str(body),
        "body_sha256": digest,
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else body.with_suffix(body.suffix + ".sha256.json")
    out.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"OK: body_sha256={digest} → {out}")
    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
