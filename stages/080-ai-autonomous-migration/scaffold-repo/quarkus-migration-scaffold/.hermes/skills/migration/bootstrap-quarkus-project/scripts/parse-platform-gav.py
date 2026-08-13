#!/usr/bin/env python3
"""Parse Red Hat Quarkus platform GAV from tooling-pins.md."""
from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        print('Parse Red Hat Quarkus platform GAV from tooling-pins.md.')
        return 0
    if len(sys.argv) != 2:
        print("usage: parse-platform-gav.py <tooling-pins.md>", file=sys.stderr)
        return 2
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    m = re.search(
        r"\*\*Red Hat Quarkus platform\*\*\s*\|\s*`([^`]+)`",
        text,
    )
    if not m:
        print(
            "FAIL: no Red Hat Quarkus platform GAV in tooling-pins.md",
            file=sys.stderr,
        )
        return 1
    print(m.group(1).strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
