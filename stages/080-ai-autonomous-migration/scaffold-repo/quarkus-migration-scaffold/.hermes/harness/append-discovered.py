#!/usr/bin/env python3
"""K9 — append one structured discovered-work row to migration/discovered.md.

Usage: append-discovered.py <task-id> <file-or-area> <one-line-need>
Exit 0. Creates the file with a header if missing.
Not a debt ledger — forward-looking scope only (see debt.md for sensor RED).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("ORACLE_ROOT", ".")).resolve()
HEADER = """# Discovered work (K9)

Forward-looking scope intelligence — **not** sensor debt (`migration/debt.md`).
Workers append out-of-scope needs here instead of acting on them.

| when (UTC) | task | file/area | need |
|---|---|---|---|
"""


def main() -> int:
    if len(sys.argv) < 4:
        print(
            "usage: append-discovered.py <task-id> <file-or-area> <one-line-need>",
            file=sys.stderr,
        )
        return 2
    tid, area, need = sys.argv[1], sys.argv[2], " ".join(sys.argv[3:]).strip()
    area = area.replace("|", "/")
    need = need.replace("|", "/").replace("\n", " ")
    path = ROOT / "migration/discovered.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_text(HEADER, encoding="utf-8")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"| {ts} | {tid} | `{area}` | {need} |\n")
    print(f"discovered:{tid}:{area}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
