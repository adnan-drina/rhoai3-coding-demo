#!/usr/bin/env python3
"""Setup / dest-props honesty: datasource config needs a matching JDBC driver.

check-runnable-db-config.py is the runnable-profile gate (one working schema
mechanism, not named Flyway). This predicate only claims: if dest properties
set quarkus.datasource.*, the dest pom declares quarkus-jdbc-<kind> matching
the dest URL/db-kind through spring-dep-to-extension.md (never a Python H2
constant).

Usage:
  python3 assert-setup-datasource-driver.py <root>
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_MAP = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "migration"
    / "manage-quarkus-extensions"
    / "scripts"
)
if str(_MAP) not in sys.path:
    sys.path.insert(0, str(_MAP))

from spring_dep_map import load_map  # noqa: E402


def driver_for_jdbc_key(table: dict[str, tuple[str, ...]], key: str) -> str | None:
    for tgt in table.get(key.lower(), ()):
        if tgt.startswith("quarkus-jdbc-") and tgt != "quarkus-jdbc-*":
            return tgt
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    pom = root / "pom.xml"
    pom_text = pom.read_text(encoding="utf-8", errors="ignore") if pom.is_file() else ""
    props = ""
    res = root / "src" / "main" / "resources"
    if res.is_dir():
        for p in sorted(res.glob("application*.properties")):
            props += p.read_text(encoding="utf-8", errors="ignore") + "\n"
    table = load_map()
    kinds = re.findall(r"(?m)^quarkus\.datasource\.db-kind\s*=\s*(\S+)", props)
    urls = re.findall(r"(?m)^quarkus\.datasource\.jdbc\.url\s*=\s*(\S+)", props)
    if not kinds and not urls and "quarkus.datasource." not in props:
        print("OK: SETUP_JDBC idle (no dest datasource properties)")
        return 0
    if not pom.is_file():
        print("REFUSE: SETUP_JDBC dest pom.xml missing", file=sys.stderr)
        return 1

    for kind in kinds:
        k = kind.strip().lower()
        aid = driver_for_jdbc_key(table, f"jdbc:{k}")
        if aid is None:
            print(
                f"REFUSE: SETUP_JDBC dest db-kind={kind} has no jdbc:* row "
                "(table, not a Python fallback)",
                file=sys.stderr,
            )
            return 1
        if aid not in pom_text:
            print(
                f"REFUSE: SETUP_JDBC dest pom missing {aid} for db-kind={kind}",
                file=sys.stderr,
            )
            return 1
    for url in urls:
        m = re.search(r"jdbc:([a-zA-Z0-9]+):", url)
        if not m:
            continue
        k = m.group(1).lower()
        aid = driver_for_jdbc_key(table, f"jdbc:{k}")
        if aid is None:
            print(
                f"REFUSE: SETUP_JDBC dest URL {url} has no jdbc:{k} row",
                file=sys.stderr,
            )
            return 1
        if aid not in pom_text:
            print(
                f"REFUSE: SETUP_JDBC dest pom missing {aid} for URL {url}",
                file=sys.stderr,
            )
            return 1
    print("OK: SETUP_JDBC dest datasource has a matching JDBC driver")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
