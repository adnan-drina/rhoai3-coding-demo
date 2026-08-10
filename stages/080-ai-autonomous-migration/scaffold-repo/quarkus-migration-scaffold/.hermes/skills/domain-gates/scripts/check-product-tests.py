#!/usr/bin/env python3
"""AR-2.8 — require product acceptance tests (boot/CRUD/security/DB).

Exit 0 when non-harness *Test.java / *IT.java cover all four families.
Exit 1 (REFUSE) when missing product tests, probe-only, or a family absent.

Families (content or name heuristics; optional AR28:<family> markers):
  boot     — package/start smoke (/q/health, *Boot*IT, AR28:boot)
  security — authz (401/403, Security*IT, AR28:security)
  crud     — product API read/write (/api/ + HTTP verb, *Crud*IT, AR28:crud)
  db       — seeded/Flyway data (seed names, flyway, AR28:db)

Harness package com.demo.harness.* never counts toward acceptance.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HARNESS_PREFIX = "com/demo/harness/"
FAMILIES = ("boot", "security", "crud", "db")

BOOT_RE = re.compile(
    r"AR28:boot|/q/health|ApplicationBoot|BootIT|QuarkusTest.*start",
    re.I | re.S,
)
SECURITY_RE = re.compile(
    r"AR28:security|statusCode\s*\(\s*401\s*\)|statusCode\s*\(\s*403\s*\)|"
    r"SecurityAuthz|Security.*IT|preemptive\(\)\s*\.\s*basic",
    re.I,
)
CRUD_RE = re.compile(
    r"AR28:crud|/api/\w+|OwnerCrud|CrudIT|"
    r"\.(get|post|put|delete)\s*\(\s*[\"']/api/",
    re.I,
)
DB_RE = re.compile(
    r"AR28:db|flyway|Franklin|seeded|migrate-at-start|flyway_schema",
    re.I,
)
FAMILY_SCANNERS = {
    "boot": BOOT_RE,
    "security": SECURITY_RE,
    "crud": CRUD_RE,
    "db": DB_RE,
}


def test_paths(root: Path) -> list[Path]:
    test_root = root / "src" / "test" / "java"
    if not test_root.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(test_root.rglob("*.java")):
        name = p.name
        if name.endswith("Test.java") or name.endswith("IT.java"):
            out.append(p)
    return out


def is_harness(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root / "src" / "test" / "java").as_posix()
    except ValueError:
        return False
    return rel.startswith(HARNESS_PREFIX)


def classify(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    blob = f"{path.name}\n{text}"
    hit: set[str] = set()
    for fam, rx in FAMILY_SCANNERS.items():
        if rx.search(blob):
            hit.add(fam)
    return hit


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()

    tests = test_paths(root)
    if not tests:
        print("FAIL: AR-2.8 no *Test.java/*IT.java — product acceptance empty", file=sys.stderr)
        return 1

    product = [p for p in tests if not is_harness(p, root)]
    harness = [p for p in tests if is_harness(p, root)]

    if not product:
        print(
            "FAIL: AR-2.8 probe-only tests (com.demo.harness.*) — "
            "REFUSE as product acceptance (pair AR-3.6)",
            file=sys.stderr,
        )
        for p in harness[:20]:
            print(f"  probe_test: {p.relative_to(root)}", file=sys.stderr)
        return 1

    covered: dict[str, list[str]] = {f: [] for f in FAMILIES}
    for p in product:
        for fam in classify(p):
            covered[fam].append(str(p.relative_to(root)))

    missing = [f for f in FAMILIES if not covered[f]]
    if missing:
        print(
            f"FAIL: AR-2.8 missing product-test families: {', '.join(missing)}",
            file=sys.stderr,
        )
        for fam in FAMILIES:
            srcs = covered[fam]
            if srcs:
                print(f"  {fam}: OK ({len(srcs)}) e.g. {srcs[0]}", file=sys.stderr)
            else:
                print(f"  {fam}: MISSING", file=sys.stderr)
        print(
            "  need boot (/q/health), security (401/auth), crud (/api), "
            "db (seed/Flyway) — markers AR28:<family> allowed",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: AR-2.8 product acceptance covers {', '.join(FAMILIES)} "
        f"({len(product)} product file(s); harness smoke={len(harness)})"
    )
    for fam in FAMILIES:
        print(f"  {fam}: {covered[fam][0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
