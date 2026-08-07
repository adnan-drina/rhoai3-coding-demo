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
# After strip_noise, iface methods are `ReturnType name(...);` — require a
# type token before the name so license text / stray tokens cannot match.
IFACE_METHOD = re.compile(
    # O-INSTREGRESS: also match single-line `{ Type name(...); }` bodies.
    r"(?:^|\n|\{)\s*(?:(?:default|static)\s+)?(?:[\w.<>,\[\]?]+\s+)+(\w+)\s*\([^;{}]*\)\s*;",
    re.M,
)
INTERFACE = re.compile(r"\b(?:public\s+)?interface\s+(\w+)")
CONVERTED = re.compile(
    r"@(ApplicationScoped|RequestScoped|Singleton|Inject|Path|RegisterRestClient)\b"
)


def strip_noise(text: str) -> str:
    """O-REDESIGNSIGANNOT — drop comments and annotations before method scrape.

    Naive ``name(...);`` matching treats ``@Query("...")`` + the following
    method as one capture named ``Query``, and license ``Version 2.0 (...)``
    as a method named ``0``. Strip those so only real API names remain.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*?$", "", text, flags=re.M)
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "@":
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            if j < n and text[j] == "(":
                depth = 0
                while j < n:
                    if text[j] == "(":
                        depth += 1
                    elif text[j] == ")":
                        depth -= 1
                        if depth == 0:
                            j += 1
                            break
                    j += 1
            i = j
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


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
    text = strip_noise(text)
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
    # O-FIDELITYPORT: --mode=reimpl checks public signatures on *all* paired
    # files (Port=reimplement acceptance regime). Default mode stays
    # iface/converted-only (O-REDESIGNSIG / O-IFACERENAME).
    args = list(sys.argv[1:])
    mode = "default"
    if args and args[0] in ("--mode=reimpl", "--reimpl"):
        mode = "reimpl"
        args = args[1:]
    staging = args[0] if len(args) > 0 else "migration/staging/src/main/java"
    dest = args[1] if len(args) > 1 else "src/main/java"
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
        if mode != "reimpl" and not (is_iface or is_conv):
            continue
        a, b = public_methods(raw_s), public_methods(raw_d)
        # Ignore ctor-looking names matching file stem.
        stem = fn[:-5]
        a.discard(stem)
        b.discard(stem)
        missing = sorted(a - b)
        extra = sorted(b - a)
        if missing:
            helperish = [
                m
                for m in missing
                if m == "mapRow"
                or m == "extractData"
                or m.startswith("create")
                and m.endswith("ParameterSource")
            ]
            # O-AGROALHELPERSIG: catch rename/privatize smells (mapRow→mapVetRow
            # / mapVisitRow) even when the exact public name is absent.
            rename_smell = [
                e
                for e in extra
                if helperish
                and (
                    e.startswith("map")
                    and e.endswith("Row")
                    and e != "mapRow"
                    or "ParameterSource" in e
                    and e not in a
                )
            ]
            tag = (
                " (O-AGROALHELPERSIG — keep *exact public* helper names on Impl; "
                "do not rename/privatize/move-only to RowMapper)"
                if helperish
                else ""
            )
            print(
                f"SIG:{fn}: public methods absent vs staging (keep legacy names): "
                + ", ".join(missing[:8])
                + tag
            )
            if rename_smell:
                print(
                    f"SIG:{fn}: O-AGROALHELPERSIG rename/privatize smell — "
                    f"dest has {', '.join(rename_smell[:4])} but staging "
                    f"public helpers missing: {', '.join(helperish[:4])}"
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
        tag = (
            "O-FIDELITYPORT/O-REDESIGNSIG"
            if mode == "reimpl"
            else "O-REDESIGNSIG/O-IFACERENAME/O-AGROALHELPERSIG"
        )
        print(
            f"REDESIGN SIG RED: {problems} file(s) — {tag} "
            "(preserve legacy public method names through "
            "redesign / Port=reimplement / JDBC→Agroal rewrite)"
        )
        return 1
    label = "reimpl-sig" if mode == "reimpl" else "redesign-sig"
    print(f"{label} GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
