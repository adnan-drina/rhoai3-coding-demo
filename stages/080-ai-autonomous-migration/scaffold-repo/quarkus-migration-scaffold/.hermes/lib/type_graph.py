#!/usr/bin/env python3
"""In-prefix Java type graph (no Kanban body).

The same walk stamp-body-dependencies.py uses: transitive extends, in-prefix
imports, same-package simple names, JDK/framework stop. Callable from M1
with a file list (inventory row ``file``s) — there is no ``--body``.

Simple names also resolve through ``import pkg.*;`` into that package
directory, then a unique in-prefix basename match. That is still this
parser, not a second one, and not a Dto/mapper allow-list.
"""
from __future__ import annotations

import re
from pathlib import Path

IMP_RE = re.compile(r"\bimport\s+([a-zA-Z0-9_.]+)\s*;")
STAR_IMP_RE = re.compile(r"\bimport\s+([a-zA-Z0-9_.]+)\.\*\s*;")
EXTENDS_RE = re.compile(
    r"\b(?:class|interface)\s+\w+(?:<[^>\n]*>)?\s+extends\s+([\w.]+)",
    re.M,
)
COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.S)
COMMENT_LINE_RE = re.compile(r"//.*?$", re.M)
_JDK_SUPERS = frozenset(
    {"Object", "Enum", "Record", "java.lang.Object", "java.lang.Enum"}
)


def strip_java_comments(text: str) -> str:
    text = COMMENT_BLOCK_RE.sub(" ", text)
    return COMMENT_LINE_RE.sub(" ", text)


def java_src_root(current: Path) -> Path | None:
    s = str(current).replace("\\", "/")
    for marker in ("/src/main/java/", "/src/test/java/"):
        idx = s.find(marker)
        if idx >= 0:
            return Path(s[: idx + len(marker) - 1])
    return None


def generated_java_root(current: Path) -> Path | None:
    src = java_src_root(current)
    if src is None:
        return None
    gen = src.parent.parent.parent / "target" / "generated-sources"
    return gen if gen.is_dir() else None


def src_rel_from_path(path: Path) -> str | None:
    s = str(path).replace("\\", "/")
    for marker in ("src/main/java/", "src/test/java/"):
        idx = s.find(marker)
        if idx >= 0:
            return s[idx:]
    return None


def layer_of(rel: str) -> str:
    """Last package segment of a src/.../Name.java path — not an allow-list."""
    p = rel.replace("\\", "/")
    for marker in ("src/main/java/", "src/test/java/"):
        idx = p.find(marker)
        if idx >= 0:
            p = p[idx + len(marker) :]
            break
    parent = Path(p).parent.as_posix()
    if not parent or parent == ".":
        return ""
    return parent.rsplit("/", 1)[-1]


def _in_prefix_fqcn(name: str, pkg_prefixes: list[str]) -> bool:
    if not pkg_prefixes:
        return not (
            name.startswith("java.")
            or name.startswith("javax.")
            or name.startswith("jakarta.")
        )
    return any(name == p.rstrip(".") or name.startswith(p) for p in pkg_prefixes)


def resolve_type_file(
    current: Path,
    name: str,
    pkg_prefixes: list[str],
    star_packages: list[str] | None = None,
) -> Path | None:
    if name in _JDK_SUPERS:
        return None
    root = java_src_root(current)
    if "." in name:
        if name.startswith("java.") or name.startswith("javax.") or name.startswith(
            "jakarta."
        ):
            return None
        if not _in_prefix_fqcn(name, pkg_prefixes):
            return None
        if root is None:
            return None
        cand = root / (name.replace(".", "/") + ".java")
        if cand.is_file():
            return cand
        return _resolve_in_generated(current, name)
    sibling = current.parent / f"{name}.java"
    if sibling.is_file():
        return sibling
    if root is None:
        return None
    for pkg in star_packages or []:
        if not _in_prefix_fqcn(pkg + ".", pkg_prefixes) and pkg_prefixes:
            continue
        cand = root / pkg.replace(".", "/") / f"{name}.java"
        if cand.is_file():
            return cand
        ghit = _resolve_in_generated_package(current, pkg, name)
        if ghit is not None:
            return ghit
    hits = [
        p
        for p in root.rglob(f"{name}.java")
        if p.is_file() and p != current
    ]
    if pkg_prefixes:
        kept: list[Path] = []
        for hit in hits:
            rel = src_rel_from_path(hit) or ""
            body = rel.split("src/main/java/", 1)[-1] if "src/main/java/" in rel else rel
            fqcn = body[: -len(".java")].replace("/", ".") if body.endswith(".java") else ""
            if _in_prefix_fqcn(fqcn, pkg_prefixes):
                kept.append(hit)
        hits = kept
    if len(hits) == 1:
        return hits[0]
    return _resolve_in_generated(current, name)


def _resolve_in_generated(current: Path, name: str) -> Path | None:
    gen = generated_java_root(current)
    if gen is None:
        return None
    if "." in name:
        suffix = "/" + name.replace(".", "/") + ".java"
        hits = [
            p
            for p in gen.rglob("*.java")
            if p.is_file() and str(p).replace("\\", "/").endswith(suffix)
        ]
    else:
        hits = [p for p in gen.rglob(f"{name}.java") if p.is_file()]
    if len(hits) == 1:
        return hits[0]
    return None


def _resolve_in_generated_package(
    current: Path, pkg: str, name: str
) -> Path | None:
    gen = generated_java_root(current)
    if gen is None:
        return None
    pkg_rel = pkg.replace(".", "/")
    for d in gen.rglob("*"):
        if not d.is_dir():
            continue
        if d.as_posix().replace("\\", "/").endswith("/" + pkg_rel):
            cand = d / f"{name}.java"
            if cand.is_file():
                return cand
    return None


def project_type_closure(start: Path, pkg_prefixes: list[str]) -> list[Path]:
    """Transitive extends + in-prefix imports + same-package types. JDK stop."""
    seen: set[str] = set()
    found: list[Path] = []
    stack = [start]
    while stack:
        cur = stack.pop()
        try:
            key = str(cur.resolve())
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        try:
            raw = cur.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        text = strip_java_comments(raw)
        names: list[str] = []
        stars = [m.group(1) for m in STAR_IMP_RE.finditer(text)]
        for m in IMP_RE.finditer(text):
            names.append(m.group(1))
        for m in EXTENDS_RE.finditer(text):
            names.append(m.group(1))
        for sib in sorted(cur.parent.glob("*.java")):
            if sib.stem == cur.stem:
                continue
            if re.search(r"\b" + re.escape(sib.stem) + r"\b", text):
                names.append(sib.stem)
        # Star-import packages: same scan as same-package siblings, in that
        # directory. Simple names used in the file (OwnerDto from import dto.*)
        # are otherwise never added to ``names``.
        src_root = java_src_root(cur)
        if src_root is not None:
            for pkg in stars:
                pkg_dir = src_root / pkg.replace(".", "/")
                if pkg_dir.is_dir():
                    for sib in sorted(pkg_dir.glob("*.java")):
                        if sib.stem == cur.stem:
                            continue
                        if re.search(r"\b" + re.escape(sib.stem) + r"\b", text):
                            names.append(sib.stem)
                gen = generated_java_root(cur)
                if gen is not None:
                    pkg_rel = pkg.replace(".", "/")
                    for d in gen.rglob("*"):
                        if not d.is_dir():
                            continue
                        if not d.as_posix().replace("\\", "/").endswith(
                            "/" + pkg_rel
                        ):
                            continue
                        for sib in sorted(d.glob("*.java")):
                            if sib.stem == cur.stem:
                                continue
                            if re.search(
                                r"\b" + re.escape(sib.stem) + r"\b", text
                            ):
                                names.append(sib.stem)
        for name in names:
            nxt = resolve_type_file(
                cur, name, pkg_prefixes, star_packages=stars
            )
            if nxt is None:
                continue
            try:
                nkey = str(nxt.resolve())
            except OSError:
                continue
            if nkey == key or nkey in seen:
                continue
            stack.append(nxt)
            found.append(nxt)
    return found
