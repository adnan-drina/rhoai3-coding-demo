#!/usr/bin/env python3
"""Create-path interface-closure gate (Architect E-20260811T181749Z Class A).

BANK-CREATE-PATH-IFACE-1 elevated: every interface an in-scope / writable impl
implements must be (a) in files_in_scope / files_writable, (b) already present
on destination, or (c) declared in dependencies[].

Fail-closed before create-m3 / dispatch so workers are not cornered into
typed-BLOCK vs OOS-create (proven: S-002a t_f3e44947 ClinicService).

Usage:
  python3 check-interface-closure.py /projects/modernized --body migration/bodies/m3-s-002a.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

IMPL_RE = re.compile(r"implements\s+([^{]+)")
TYPE_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def norm_rel(path: str) -> str:
    p = path.replace("\\", "/").lstrip("./")
    for prefix in (
        "/projects/modernized/",
        "projects/modernized/",
        "/projects/.derived/legacy-at-3/",
        "projects/.derived/legacy-at-3/",
        "/projects/legacy/",
        "projects/legacy/",
    ):
        if p.startswith(prefix):
            p = p[len(prefix) :]
    return p


def path_list(body: dict, *keys: str) -> list[str]:
    out: list[str] = []
    for key in keys:
        for item in body.get(key) or []:
            if isinstance(item, str):
                out.append(norm_rel(item))
            elif isinstance(item, dict):
                for k in ("dest", "dst", "destination", "path", "file", "src"):
                    if item.get(k):
                        out.append(norm_rel(str(item[k])))
                        break
    return out


def dep_files(body: dict) -> set[str]:
    out: set[str] = set()
    for item in body.get("dependencies") or []:
        if isinstance(item, str):
            out.add(norm_rel(item))
        elif isinstance(item, dict) and item.get("file"):
            out.add(norm_rel(str(item["file"])))
    return out


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def resolve_source(root: Path, rel: str) -> Path | None:
    candidates = [
        root / rel,
        root / "projects" / "legacy" / rel,
        Path("/projects/legacy") / rel,
        Path("/projects/.derived/legacy-at-3") / rel,
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def interfaces_for(root: Path, rel: str) -> set[str]:
    """Return workspace-relative interface .java paths required by rel."""
    needed: set[str] = set()
    p = Path(rel)
    if not rel.endswith(".java"):
        return needed
    # Heuristic: FooImpl.java → same-dir Foo.java
    if p.name.endswith("Impl.java"):
        iface = p.with_name(p.name[: -len("Impl.java")] + ".java")
        needed.add(str(iface).replace("\\", "/"))
    src = resolve_source(root, rel)
    if src is None:
        return needed
    text = read_text(src)
    # class FooImpl implements A, B {
    for m in IMPL_RE.finditer(text):
        clause = m.group(1)
        # drop extends leftovers / generics crud roughly
        clause = clause.split("{", 1)[0]
        for tok in TYPE_RE.findall(clause):
            if tok in ("implements", "extends"):
                continue
            # same-package simple name → sibling .java
            sibling = str(p.with_name(tok + ".java")).replace("\\", "/")
            needed.add(sibling)
    return needed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--body", required=True)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    body_path = Path(args.body)
    if not body_path.is_file():
        body_path = root / args.body
    if not body_path.is_file():
        print(f"FAIL: body not found: {args.body}", file=sys.stderr)
        return 2
    raw = json.loads(body_path.read_text(encoding="utf-8"))
    body = raw["body"] if isinstance(raw.get("body"), dict) else raw

    scope = set(path_list(body, "files_writable", "files_in_scope", "write_set"))
    deps = dep_files(body)
    holes: list[str] = []
    checked = 0
    for rel in sorted(scope):
        if not rel.endswith(".java"):
            continue
        if not (
            rel.endswith("Impl.java")
            or "/service/" in rel
            or "/repository/" in rel
        ):
            # Still parse implements for any scoped java that looks like a class
            pass
        ifaces = interfaces_for(root, rel)
        if not ifaces:
            continue
        checked += 1
        for iface in sorted(ifaces):
            if iface in scope:
                continue
            if iface in deps:
                continue
            if (root / iface).is_file():
                continue  # pre-exists on destination
            # legacy-only pre-exist does NOT count — dest must have it or scope it
            holes.append(f"{rel} → missing interface {iface}")

    if holes:
        print(
            "FAIL: INTERFACE_CLOSURE (Architect E-20260811T181749Z Class A) — "
            "in-scope impl(s) require interface(s) not in scope/deps/dest:",
            file=sys.stderr,
        )
        for h in holes:
            print(f"  {h}", file=sys.stderr)
        print(
            "Fix: add interface to files_in_scope+files_writable, or declare "
            "dependencies[] provider, or ensure pre-exists on destination. "
            "Do not dispatch — workers will be cornered into OOS-create.",
            file=sys.stderr,
        )
        return 1
    print(
        f"OK: interface-closure "
        f"(scoped_java_checked≈{checked} scope={len(scope)} deps={len(deps)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
