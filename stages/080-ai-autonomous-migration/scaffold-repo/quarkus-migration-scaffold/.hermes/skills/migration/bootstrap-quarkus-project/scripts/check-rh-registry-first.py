#!/usr/bin/env python3
"""Exit 0 when registry.quarkus.redhat.com appears before registry.quarkus.io."""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        print('Exit 0 when RH Quarkus registry is listed first.')
        return 0
    if len(sys.argv) != 2:
        print("usage: check-rh-registry-first.py <config.yaml>", file=sys.stderr)
        return 2
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    rh = text.find("registry.quarkus.redhat.com")
    com = text.find("registry.quarkus.io")
    if rh < 0:
        return 1
    if com >= 0 and com < rh:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
