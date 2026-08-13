#!/usr/bin/env python3
"""Create-path interface-closure gate (Architect E-20260811T181749Z Class A).

BANK-CREATE-PATH-IFACE-1 elevated: every interface an in-scope / writable class
*implements* must be (a) in files_in_scope / files_writable, (b) already present
on destination, or (c) declared in dependencies[].

Fail-closed before create-m3 / dispatch so workers are not cornered into
typed-BLOCK vs OOS-create (proven: S-002a t_f3e44947 ApplicationService).

Usage:
  python3 check-interface-closure.py /projects/modernized --body evidence/bodies/m3-s-002a.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CLASS_IMPL_RE = re.compile(
    r"(?m)^\s*(?:public\s+|protected\s+|private\s+)?(?:abstract\s+|final\s+)*"
    r"class\s+[A-Za-z_][A-Za-z0-9_]*"
    r"(?:\s*<[^;{]+>)?"
    r"(?:\s+extends\s+[^{]+?)?"
    r"\s+implements\s+([^{]+?)\{"
)
IMPORT_RE = re.compile(r"(?m)^\s*import\s+([a-zA-Z0-9_.]+)\s*;")
PKG_RE = re.compile(r"(?m)^\s*package\s+([a-zA-Z0-9_.]+)\s*;")
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
        Path("/projects/legacy") / rel,
        Path("/projects/.derived/legacy-at-3") / rel,
        root.parent / "legacy" / rel,
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def fqcn_to_rel(fqcn: str) -> str:
    return "src/main/java/" + fqcn.replace(".", "/") + ".java"


PLATFORM_PREFIXES = (
    "java.",
    "javax.",
    "jakarta.",
    "io.quarkus.",
    "org.eclipse.",
    "org.junit.",
    "org.mockito.",
    "com.fasterxml.",
    "org.hibernate.",
    "org.jboss.",
)


def is_platform_fqcn(fqcn: str) -> bool:
    return any(fqcn.startswith(p) for p in PLATFORM_PREFIXES)


def resolve_simple_type(root: Path, simple: str, text: str, class_rel: str) -> str | None:
    """Map simple interface name → workspace-relative .java path (specimen only)."""
    imports = {m.group(1).split(".")[-1]: m.group(1) for m in IMPORT_RE.finditer(text)}
    if simple in imports:
        fqcn = imports[simple]
        if is_platform_fqcn(fqcn):
            return None
        return fqcn_to_rel(fqcn)
    pkg_m = PKG_RE.search(text)
    if pkg_m:
        same = fqcn_to_rel(f"{pkg_m.group(1)}.{simple}")
        for base in (root, Path("/projects/legacy"), Path("/projects/.derived/legacy-at-3")):
            if (base / same).is_file():
                return same
        if class_rel.endswith(".java"):
            sibling = str(Path(class_rel).with_name(simple + ".java")).replace("\\", "/")
            return sibling
    parent = str(Path(class_rel).parent.parent / f"{simple}.java").replace("\\", "/")
    for base in (root, Path("/projects/legacy"), Path("/projects/.derived/legacy-at-3")):
        if (base / parent).is_file():
            return parent
    return None


def interfaces_for(root: Path, rel: str) -> set[str]:
    needed: set[str] = set()
    src = resolve_source(root, rel)
    if src is None:
        return needed
    text = read_text(src)
    m = CLASS_IMPL_RE.search(text)
    if not m:
        return needed
    clause = m.group(1)
    for raw in clause.split(","):
        raw = raw.strip()
        if not raw:
            continue
        head = raw.split("<", 1)[0].strip()
        if is_platform_fqcn(head):
            continue
        simple = head.split(".")[-1]
        if not TYPE_RE.fullmatch(simple):
            continue
        if simple in ("Serializable", "Cloneable", "AutoCloseable"):
            continue
        resolved = resolve_simple_type(root, simple, text, rel)
        if not resolved:
            continue
        # Framework jars resolve under src/main/java/io/... — drop those
        if "/io/quarkus/" in resolved or resolved.startswith("src/main/java/io/"):
            continue
        if not resolved.startswith("src/main/java/"):
            continue
        # Only care if the interface exists in legacy (migration specimen) or dest
        # or is clearly same-app package as the implementing class.
        legacy_hit = any(
            (base / resolved).is_file()
            for base in (
                Path("/projects/legacy"),
                Path("/projects/.derived/legacy-at-3"),
            )
        )
        dest_hit = (root / resolved).is_file()
        same_app = Path(rel).parts[:5] == Path(resolved).parts[:5]
        if not (legacy_hit or dest_hit or same_app):
            continue
        needed.add(resolved)
    return needed


def covered(iface: str, scope: set[str], deps: set[str], root: Path) -> bool:
    if iface in scope or iface in deps:
        return True
    if (root / iface).is_file():
        return True  # pre-exists on destination
    return False


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
        ifaces = interfaces_for(root, rel)
        if not ifaces:
            continue
        checked += 1
        for iface in sorted(ifaces):
            if covered(iface, scope, deps, root):
                continue
            holes.append(f"{rel} → missing interface {iface}")

    if holes:
        print(
            "FAIL: INTERFACE_CLOSURE (Architect E-20260811T181749Z Class A) — "
            "in-scope class(es) implement interface(s) not in scope/deps/dest:",
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
        f"(classes_with_implements={checked} scope={len(scope)} deps={len(deps)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
