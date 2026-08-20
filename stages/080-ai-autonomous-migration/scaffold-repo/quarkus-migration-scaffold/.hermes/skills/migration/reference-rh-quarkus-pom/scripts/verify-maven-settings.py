#!/usr/bin/env python3
"""Refuse unless in-repo Maven settings are wired and name the RH GA profile.

Maven 3 does not auto-read .mvn/settings.xml. Official .mvn/ files are
maven.config, jvm.config, extensions.xml. This verifier requires:

  .mvn/maven.config  contains -s then .mvn/settings.xml (one arg per line)
  .mvn/settings.xml  contains red-hat-enterprise-maven-repository

When `mvn` is on PATH, also require `mvn help:effective-settings` to cite
that profile. Missing mvn on a lint host is not a pass of resolve — the
file-shape check still runs.

Usage:
  python3 verify-maven-settings.py <root>
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROFILE = "red-hat-enterprise-maven-repository"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument(
        "--files-only",
        action="store_true",
        help="Skip mvn help:effective-settings (lint hosts; file shape only)",
    )
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    cfg = root / ".mvn" / "maven.config"
    settings = root / ".mvn" / "settings.xml"
    if not cfg.is_file():
        print("REFUSE: MAVEN_REPOS missing .mvn/maven.config (-s required)", file=sys.stderr)
        return 1
    if not settings.is_file():
        print("REFUSE: MAVEN_REPOS missing .mvn/settings.xml", file=sys.stderr)
        return 1
    lines = [
        ln.strip()
        for ln in cfg.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    joined = " ".join(lines)
    if "-s" not in lines and not any(x.startswith("-s") or x.startswith("--settings") for x in lines):
        print("REFUSE: MAVEN_REPOS maven.config missing -s", file=sys.stderr)
        return 1
    if ".mvn/settings.xml" not in joined and "settings.xml" not in joined:
        print(
            "REFUSE: MAVEN_REPOS maven.config -s does not point at .mvn/settings.xml",
            file=sys.stderr,
        )
        return 1
    blob = settings.read_text(encoding="utf-8", errors="ignore")
    if PROFILE not in blob:
        print(f"REFUSE: MAVEN_REPOS settings.xml missing {PROFILE}", file=sys.stderr)
        return 1
    if args.files_only:
        print("OK: MAVEN_REPOS .mvn/maven.config -s + settings.xml (files-only)")
        return 0
    mvn = shutil.which("mvn")
    if mvn:
        sub = subprocess.run(
            [mvn, "-q", "help:effective-settings"],
            cwd=str(root),
            text=True,
            capture_output=True,
            timeout=120,
        )
        text = (sub.stdout or "") + (sub.stderr or "")
        if sub.returncode != 0 or PROFILE not in text:
            print(
                "REFUSE: MAVEN_REPOS mvn help:effective-settings "
                f"does not show {PROFILE} rc={sub.returncode}",
                file=sys.stderr,
            )
            return 1
        print("OK: MAVEN_REPOS effective-settings shows RH GA profile")
        return 0
    print("OK: MAVEN_REPOS .mvn/maven.config -s + settings.xml (mvn not on PATH)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
