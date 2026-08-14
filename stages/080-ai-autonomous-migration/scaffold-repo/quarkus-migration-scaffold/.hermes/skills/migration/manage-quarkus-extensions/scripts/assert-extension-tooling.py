#!/usr/bin/env python3
"""W3 — typed preflight for Quarkus extension tooling (CLI or Maven fallback).

Fail-closed when CLI is present but RH registry is not first (silent community
pull risk). When CLI is absent, print a typed MAVEN_FALLBACK line and exit 0 —
pipeline / air-gap seats never run postStart.

Usage:
  python3 assert-extension-tooling.py
  python3 assert-extension-tooling.py /path/to/.quarkus/config.yaml
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        print(
            "Exit 0: CLI+RH-first OK, or CLI absent (Maven fallback).\n"
            "Exit 1: CLI present but RH registry not first / config missing."
        )
        return 0

    cfg = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else Path.home() / ".quarkus" / "config.yaml"
    )

    quarkus = shutil.which("quarkus")
    if not quarkus:
        print(
            "MAVEN_FALLBACK: quarkus CLI absent — use "
            "mvn -q quarkus:list / quarkus:add-extension "
            "(W3 typed; postStart may still provision CLI on Dev Spaces seats)"
        )
        return 0

    if not cfg.is_file():
        print(
            f"FAIL: quarkus CLI at {quarkus} but missing {cfg} "
            "(need registry.quarkus.redhat.com first)",
            file=sys.stderr,
        )
        return 1

    text = cfg.read_text(encoding="utf-8")
    rh = text.find("registry.quarkus.redhat.com")
    com = text.find("registry.quarkus.io")
    if rh < 0 or (com >= 0 and com < rh):
        print(
            f"FAIL: CLI present but RH registry not first in {cfg} "
            "(community-first risk)",
            file=sys.stderr,
        )
        return 1

    print(f"OK: quarkus CLI at {quarkus}; RH registry first in {cfg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
