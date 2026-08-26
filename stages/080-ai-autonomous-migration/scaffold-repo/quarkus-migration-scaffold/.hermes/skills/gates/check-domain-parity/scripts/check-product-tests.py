#!/usr/bin/env python3
"""AR-2.8 — require product acceptance tests for inventory-grounded families.

When evidence/entry-point-inventory.json is present, require only families
the harvest actually found (Architect 130758ZA). Greeting-only inventory
does not demand /q/health — that route is not a grounding exception
(assert-partition-invented-routes). N/A is declared with inventory
evidence; it is not idle-in-ACCEPT.

When inventory is absent, keep the four-family floor (fail dest-8-as-stood
without this file). Exit 1 when a *required* family is missing, probe-only,
or there are no product tests. Exit 2 on unreadable inventory.

Families (content or name heuristics; optional AR28:<family> markers):
  boot     — start/smoke of harvested HTTP (@QuarkusTest, /q/health, *Boot*IT, AR28:boot)
  security — authz (401/403, Security*IT, AR28:security)
  crud     — product API read/write (/api/ + HTTP verb, *Crud*IT, AR28:crud)
  db       — seeded/Flyway data (seed names, flyway, AR28:db)

Harness package com.example.tooling.smoke.* never counts toward acceptance.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _ensure_hermes_lib() -> None:
    p = Path(__file__).resolve()
    for parent in p.parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            s = str(lib)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()
from http_join import inventory_http_paths, normalize_http_path  # noqa: E402

HARNESS_PREFIX = "com/example/tooling/smoke/"
FAMILIES = ("boot", "security", "crud", "db")

BOOT_RE = re.compile(
    r"AR28:boot|/q/health|ApplicationBoot|BootIT|@?QuarkusTest",
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


def load_inventory(root: Path) -> dict | None:
    path = root / "evidence" / "entry-point-inventory.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("unreadable entry-point-inventory.json: " + str(exc)) from exc
    if not isinstance(data, dict):
        raise ValueError("entry-point-inventory.json is not an object")
    schema = str(data.get("schema") or "")
    if schema != "rhoai3.entry-point-inventory/v1":
        raise ValueError(
            "entry-point-inventory.json schema is %r, want rhoai3.entry-point-inventory/v1"
            % schema
        )
    return data


def db_intent(root: Path) -> bool:
    path = root / "evidence" / "required-extensions.json"
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    return any(
        token in text
        for token in (
            "jdbc",
            "jpa",
            "agroal",
            "hibernate",
            "datasource",
            "quarkus-jdbc",
        )
    )


def required_families(root: Path, inventory: dict) -> set[str]:
    """Boot is start/smoke of harvested HTTP (Architect 130828ZA), not /q/health."""
    required: set[str] = set()
    paths = inventory_http_paths(inventory)
    methods: set[str] = set()
    for row in inventory.get("entry_points") or []:
        if not isinstance(row, dict) or row.get("kind") != "http":
            continue
        methods.add(str(row.get("http_method") or "").upper())
    if paths:
        required.add("boot")
    for hp in paths:
        n = normalize_http_path(hp)
        if any(tok in n for tok in ("/login", "/oauth", "/auth", "/security")):
            required.add("security")
        if n.startswith("/api/") or "/api/" in n:
            required.add("crud")
    if methods & {"POST", "PUT", "PATCH", "DELETE"}:
        required.add("crud")
    if db_intent(root):
        required.add("db")
    return required


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    try:
        inventory = load_inventory(root)
    except ValueError as exc:
        print("FAIL: AR-2.8 " + str(exc), file=sys.stderr)
        return 2
    required: tuple[str, ...] | None
    if inventory is None:
        required = FAMILIES
        grounded = False
    else:
        grounded = True
        required = tuple(f for f in FAMILIES if f in required_families(root, inventory))

    tests = test_paths(root)
    product = [p for p in tests if not is_harness(p, root)]
    harness = [p for p in tests if is_harness(p, root)]
    na = [f for f in FAMILIES if f not in required]

    if grounded and not required:
        paths = sorted(inventory_http_paths(inventory or {}))
        print(
            "N/A: AR-2.8 no inventory-grounded families "
            "(not idle; harvest HTTP %s)" % (paths or ["<none>"])
        )
        return 0

    if not tests:
        print("FAIL: AR-2.8 no *Test.java/*IT.java — product acceptance empty", file=sys.stderr)
        return 1

    if not product:
        print(
            "FAIL: AR-2.8 probe-only tests (com.example.tooling.smoke.*) — "
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

    missing = [f for f in required if not covered[f]]
    if missing:
        print(
            f"FAIL: AR-2.8 missing product-test families: {', '.join(missing)}",
            file=sys.stderr,
        )
        for fam in required:
            srcs = covered[fam]
            if srcs:
                print(f"  {fam}: OK ({len(srcs)}) e.g. {srcs[0]}", file=sys.stderr)
            else:
                print(f"  {fam}: MISSING", file=sys.stderr)
        if grounded:
            print(
                "  required families are inventory-grounded; do not invent /q/health",
                file=sys.stderr,
            )
        else:
            print(
                "  need boot (/q/health), security (401/auth), crud (/api), "
                "db (seed/Flyway) — markers AR28:<family> allowed "
                "(no entry-point-inventory.json; four-family floor stands)",
                file=sys.stderr,
            )
        return 1

    print(
        f"OK: AR-2.8 product acceptance covers {', '.join(required)} "
        f"({len(product)} product file(s); harness smoke={len(harness)}"
        f"{'; inventory-grounded' if grounded else ''})"
    )
    for fam in required:
        print(f"  {fam}: {covered[fam][0]}")
    if grounded and na:
        print("N/A: AR-2.8 %s (no inventory surface; not idle)" % ", ".join(na))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
