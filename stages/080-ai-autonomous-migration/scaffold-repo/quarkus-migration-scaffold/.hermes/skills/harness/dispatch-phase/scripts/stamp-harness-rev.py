#!/usr/bin/env python3
"""Stamp .hermes/HARNESS_REV with the resolved golden scaffold SHA (V34-2).

fetch:plain of quarkus-migration-scaffold/tree/main strips .git, so dests
cannot self-report which golden they carry. Write the resolved main SHA
at create. --sha is for fixtures; dest create uses git ls-remote.

Usage:
  python3 stamp-harness-rev.py --root /projects/modernized
  python3 stamp-harness-rev.py --root . --sha <40-hex>
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_URL = (
    "https://github.com/adnan-drina/quarkus-migration-scaffold.git"
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def resolve_sha(url: str, explicit: str) -> str:
    pin = (explicit or os.environ.get("RHOAI3_HARNESS_REV") or "").strip()
    if pin:
        if not SHA_RE.match(pin):
            raise SystemExit(f"FAIL: --sha must be 40-hex, got {pin!r}")
        return pin
    proc = subprocess.run(
        ["git", "ls-remote", url, "refs/heads/main"],
        capture_output=True,
        text=True,
        check=False,
    )
    line = (proc.stdout or "").splitlines()[0] if proc.stdout else ""
    sha = line.split()[0] if line else ""
    if proc.returncode != 0 or not SHA_RE.match(sha):
        err = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(f"FAIL: git ls-remote {url} main: {err or 'no sha'}")
    return sha


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    ap.add_argument("--sha", default="")
    ap.add_argument("--url", default=DEFAULT_URL)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    out = root / ".hermes" / "HARNESS_REV"
    if out.is_file():
        existing = out.read_text(encoding="utf-8").strip()
        if SHA_RE.match(existing):
            print(f"OK: existing {out} {existing}")
            return 0
    sha = resolve_sha(args.url, args.sha)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(sha + "\n", encoding="utf-8")
    print(f"OK: wrote {out} {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
