#!/usr/bin/env python3
"""O-MSGCLAIM — subject claims class work that the commit diff does not touch.

S04 T-002: escalation message claimed a *Service Feign→REST convert while
the file was unchanged. Exit 1 when CamelCase *Service/*Endpoint/*Impl names
in the subject are absent from changed paths.

Usage: msgclaim-check.py [sha]
"""
from __future__ import annotations

import re
import subprocess
import sys


def main() -> int:
    sha = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    subj = subprocess.check_output(
        ["git", "log", "-1", "--format=%s", sha], text=True
    ).strip()
    names = re.findall(
        r"\b([A-Z][A-Za-z0-9]+(?:Service|Endpoint|Impl|Config|Application))\b",
        subj,
    )
    if not names:
        return 0
    changed = subprocess.check_output(
        ["git", "show", "--name-only", "--format=", sha], text=True
    )
    missing = [n for n in names if n not in changed]
    if missing:
        print("msgclaim:" + ",".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
