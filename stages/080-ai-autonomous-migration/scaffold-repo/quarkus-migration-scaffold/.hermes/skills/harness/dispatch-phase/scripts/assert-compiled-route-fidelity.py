#!/usr/bin/env python3
"""Architect 5724ea24 — compiled-tree route fidelity (KEEP).

R-OF.1: Hermes/spec-kit have no native JAX-RS @Path vs inventory diff
(Research typed-negative: speckit.analyze never loads the inventory).
The M2 sibling gates the mint receipt. This gates dest Java after M3.
Moved out of Operator `tools/verify-route-fidelity.sh` (that wrapper
`oc exec`'d this logic). Run in the dest cwd. Does not grow mint (1088).

Usage:
  python3 assert-compiled-route-fidelity.py [dest-root] [path-prefix]
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path


def load_inventory_routes(root: Path) -> set[tuple[str, str]]:
    inv_p = root / "evidence" / "entry-point-inventory.json"
    if not inv_p.is_file():
        raise SystemExit(f"FAIL: no inventory at {inv_p}")
    data = json.loads(inv_p.read_text(encoding="utf-8"))
    rows = (
        data
        if isinstance(data, list)
        else (data.get("entry_points") or data.get("entries") or [])
    )
    inv: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        method = str(row.get("http_method") or row.get("method") or "").upper()
        path = str(row.get("http_path") or row.get("path") or "")
        if method and path:
            inv.add((method, path))
    return inv


def implemented_routes(root: Path) -> tuple[set[tuple[str, str]], list[str]]:
    impl: set[tuple[str, str]] = set()
    warns: list[str] = []
    files = sorted(
        glob.glob(str(root / "src/main/java/**/*Resource.java"), recursive=True)
    )
    for f in files:
        src = Path(f).read_text(encoding="utf-8")
        cls = re.search(
            r'@Path\("([^"]+)"\)\s*(?:@\w+[^\n]*\n\s*)*public\s+class', src
        )
        if not cls:
            warns.append(f"WARN {f}: no class-level @Path")
            continue
        base = cls.group(1)
        for m in re.finditer(
            r"@(GET|POST|PUT|DELETE|PATCH|HEAD)([\s\S]{0,300}?)public\s", src
        ):
            verb = m.group(1)
            seg = re.search(r'@Path\("([^"]+)"\)', m.group(2))
            path = base + ("/" + seg.group(1) if seg else "")
            impl.add((verb, re.sub(r"//+", "/", path)))
    return impl, warns


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("prefix", nargs="?", default="")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    try:
        inv = load_inventory_routes(root)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2
    impl, warns = implemented_routes(root)
    for w in warns:
        print(f"  {w}")
    prefix = args.prefix
    if prefix:
        impl = {x for x in impl if x[1].startswith(prefix)}
        inv = {x for x in inv if x[1].startswith(prefix)}
    invented = sorted(impl - inv)
    missing = sorted(inv - impl)
    print(
        f"  resources scanned: implemented={len(impl)} inventory={len(inv)}"
    )
    for verb, path in sorted(impl):
        tag = "MATCH" if (verb, path) in inv else "<<< INVENTED"
        print(f"    {verb:<6} {path:<44} {tag}")
    if missing:
        print("  MISSING from code (in legacy contract):")
        for verb, path in missing:
            print(f"    {verb:<6} {path}")
    if invented or missing:
        print(
            f"FAIL: {len(invented)} invented, {len(missing)} missing",
            file=sys.stderr,
        )
        return 1
    print(f"OK: route fidelity {len(impl)}/{len(impl)}, none invented, none missing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
