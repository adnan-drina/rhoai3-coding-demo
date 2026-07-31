#!/usr/bin/env python3
"""O-REDESIGNSIG / O-IFACERENAME — public method set must match legacy staging.

Harvest-fidelity skips CDI/JAX-RS converted classes. Redesign REST clients and
services can still rename public methods (products→getProducts) and stay GREEN
while callers break. This check compares public method *names* between staged
legacy and destination for interfaces and for classes that look converted.

Usage: redesign-sig.py [staging-root] [dest-src-root]
Exit 0 GREEN, 1 RED with SIG: lines.
"""
from __future__ import annotations

import os
import re
import sys

# Class methods with visibility; interface methods are often implicit-public
# without a modifier (`List items();`).
CLASS_METHOD = re.compile(
    r"(?:^|\n)\s*(?:public|protected)\s+(?:static\s+)?(?:[\w.<>,\[\]\s]+)\s+(\w+)\s*\(",
    re.M,
)
IFACE_METHOD = re.compile(r"\b(\w+)\s*\([^;{}]*\)\s*;")
INTERFACE = re.compile(r"\b(?:public\s+)?interface\s+(\w+)")
CONVERTED = re.compile(
    r"@(ApplicationScoped|RequestScoped|Singleton|Inject|Path|RegisterRestClient)\b"
)


def public_methods(text: str) -> set[str]:
    # Drop constructors roughly matching class name later; keep all names.
    skip = {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "return",
        "new",
        "class",
        "interface",
        "enum",
        "record",
    }
    names: set[str] = set()
    for m in CLASS_METHOD.finditer(text):
        if m.group(1) not in skip:
            names.add(m.group(1))
    if INTERFACE.search(text):
        for m in IFACE_METHOD.finditer(text):
            if m.group(1) not in skip:
                names.add(m.group(1))
    return names


def walk_java(root: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not os.path.isdir(root):
        return out
    for dp, _, fs in os.walk(root):
        for fn in fs:
            if fn.endswith(".java"):
                path = os.path.join(dp, fn)
                try:
                    out[fn] = open(path, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
    return out


def main() -> int:
    staging = sys.argv[1] if len(sys.argv) > 1 else "migration/staging/src/main/java"
    dest = sys.argv[2] if len(sys.argv) > 2 else "src/main/java"
    if not os.path.isdir(staging) or not os.path.isdir(dest):
        print("redesign-sig skipped — missing staging or dest tree")
        return 0
    staged = walk_java(staging)
    dests = walk_java(dest)
    problems = 0
    for fn, raw_s in staged.items():
        if fn not in dests:
            continue
        raw_d = dests[fn]
        is_iface = bool(INTERFACE.search(raw_s) or INTERFACE.search(raw_d))
        is_conv = bool(CONVERTED.search(raw_d))
        if not (is_iface or is_conv):
            continue
        a, b = public_methods(raw_s), public_methods(raw_d)
        # Ignore ctor-looking names matching file stem.
        stem = fn[:-5]
        a.discard(stem)
        b.discard(stem)
        missing = sorted(a - b)
        extra = sorted(b - a)
        if missing:
            print(
                f"SIG:{fn}: public methods absent vs staging (keep legacy names): "
                + ", ".join(missing[:8])
            )
            problems += 1
        if is_iface and extra and not missing:
            # Renames often show as missing+extra; flag pure renames too.
            pass
        if missing and extra:
            print(
                f"SIG:{fn}: possible rename vs staging — staging had "
                f"{', '.join(missing[:4])}; dest has {', '.join(extra[:4])}"
            )
    if problems:
        print(
            f"REDESIGN SIG RED: {problems} file(s) — O-REDESIGNSIG/O-IFACERENAME "
            "(preserve legacy public method names on redesign/interfaces)"
        )
        return 1
    print("redesign-sig GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
