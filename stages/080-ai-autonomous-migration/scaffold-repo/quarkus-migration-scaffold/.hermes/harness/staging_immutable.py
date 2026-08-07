#!/usr/bin/env python3
"""O-ADR46-S1 — immutable staging baseline (ADR-46 §5 step 1 / W4-709).

Capture a tree hash of migration/staging at recipe-transform (or explicit
record) time. Sensors refuse any later git dirt or hash drift so
harvest-fidelity / assert-5 / V3-drift checks do not green against a
moving baseline.

Usage:
  staging_immutable.py record [--source=recipe-transform|manual|…]
  staging_immutable.py check          # exit 0 GREEN, 1 RED
  staging_immutable.py hash           # print sha256 only

Capture file: migration/staging-capture.json (outside the staging tree).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("SENSOR_ROOT", ".")).resolve()
STAGING = ROOT / "migration" / "staging"
CAPTURE = ROOT / "migration" / "staging-capture.json"


def tree_hash(staging: Path = STAGING) -> tuple[str, int]:
    """Stable sha256 over sorted relpath + per-file sha256 digests."""
    if not staging.is_dir():
        return ("", 0)
    h = hashlib.sha256()
    n = 0
    files = sorted(
        p for p in staging.rglob("*") if p.is_file() and ".git" not in p.parts
    )
    for p in files:
        rel = p.relative_to(staging).as_posix()
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        h.update(rel.encode())
        h.update(b"\0")
        h.update(digest.encode())
        h.update(b"\n")
        n += 1
    return (h.hexdigest(), n)


def record(source: str = "manual") -> dict:
    STAGING.parent.mkdir(parents=True, exist_ok=True)
    sha, n = tree_hash()
    if n == 0:
        print("STAGING_CAPTURE: empty or missing migration/staging — nothing recorded", file=sys.stderr)
        sys.exit(1)
    payload = {
        "sha256": sha,
        "file_count": n,
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "source": source,
        "oid": "O-ADR46-S1",
    }
    CAPTURE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"STAGING_CAPTURE: recorded {n} files sha256={sha[:12]}… source={source}")
    return payload


def git_staging_dirty() -> bool:
    """True when migration/staging has uncommitted changes vs HEAD."""
    try:
        r = subprocess.run(
            ["git", "diff", "--quiet", "--", "migration/staging"],
            cwd=ROOT,
            check=False,
        )
        if r.returncode != 0:
            return True
        r2 = subprocess.run(
            ["git", "diff", "--quiet", "--cached", "--", "migration/staging"],
            cwd=ROOT,
            check=False,
        )
        return r2.returncode != 0
    except FileNotFoundError:
        return False


def check() -> int:
    if not STAGING.is_dir():
        print("STAGING_IMMUTABLE: no migration/staging — skip")
        return 0
    if not CAPTURE.is_file():
        print(
            "STAGING_IMMUTABLE:RED missing migration/staging-capture.json — "
            "run staging_immutable.py record after recipe-transform (O-ADR46-S1)"
        )
        return 1
    try:
        cap = json.loads(CAPTURE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"STAGING_IMMUTABLE:RED capture unreadable: {e}")
        return 1
    want = cap.get("sha256") or ""
    if not want:
        print("STAGING_IMMUTABLE:RED capture missing sha256")
        return 1
    if git_staging_dirty():
        print(
            "STAGING_IMMUTABLE:RED git dirty under migration/staging — "
            "fidelity baseline moved (O-ADR46-S1 / W4-709). "
            "Revert staging or re-record only after intentional re-capture."
        )
        return 1
    got, n = tree_hash()
    if got != want:
        print(
            f"STAGING_IMMUTABLE:RED tree hash drift "
            f"captured={want[:12]}… now={got[:12]}… files={n} "
            f"(O-ADR46-S1) — baseline rewritten without re-record"
        )
        return 1
    print(f"STAGING_IMMUTABLE:GREEN sha256={got[:12]}… files={n}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("record", "check", "hash"))
    ap.add_argument("--source", default="manual")
    args = ap.parse_args()
    if args.cmd == "hash":
        sha, n = tree_hash()
        print(sha if n else "")
        return 0 if n else 1
    if args.cmd == "record":
        record(args.source)
        return 0
    return check()


if __name__ == "__main__":
    sys.exit(main())
