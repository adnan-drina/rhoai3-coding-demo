#!/usr/bin/env python3
"""O-RETROAPPEND — archive migration/retro-proposals.md before overwrite.

Each story Retro used to replace retro-proposals.md, erasing prior
misdiagnoses (V10 Poll 67). Call this before writing a new proposals file.
History lands under migration/retro-history/<stamp>-<label>.md.

Usage:
  archive-retro.py [--label S06] [--root .]
Exit 0 always (missing current file is a no-op). Prints archived path or
'noop' on stdout.
"""
from __future__ import annotations

import argparse
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--label", default="run")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    src = root / "migration" / "retro-proposals.md"
    if not src.is_file() or src.stat().st_size == 0:
        print("noop")
        return 0
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", args.label.strip()) or "run"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    hist = root / "migration" / "retro-history"
    hist.mkdir(parents=True, exist_ok=True)
    dest = hist / f"{stamp}-{label}.md"
    shutil.copy2(src, dest)
    idx = hist / "INDEX.md"
    line = f"- `{dest.name}` — archived before next Retro ({label})\n"
    if idx.is_file():
        idx.write_text(idx.read_text(encoding="utf-8") + line, encoding="utf-8")
    else:
        idx.write_text(
            "# Retro proposal history (O-RETROAPPEND)\n\n"
            "Prior `retro-proposals.md` snapshots. Newest current file is\n"
            "`migration/retro-proposals.md` (brief-refresh reads that).\n\n" + line,
            encoding="utf-8",
        )
    print(str(dest.relative_to(root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
