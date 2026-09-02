#!/usr/bin/env python3
"""Refuse an @Id on a type whose mapped superclass already declares one.

W6 (Operator ``190602ZO`` / ``194657ZO``): 'Every entity declares @Id' never
said an inherited ``@Id`` / ``@EmbeddedId`` counts. PetClinic ``BaseEntity``
is that shape. This is the check.

Exit 0: no dest Java (idle), or each hierarchy has one effective id.
Exit 1: a type declares ``@Id``/``@EmbeddedId`` while an ancestor already does.
Exit 2: usage.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.S)
COMMENT_LINE = re.compile(r"//.*?$", re.M)
CLASS = re.compile(
    r"\bclass\s+(\w+)(?:\s+extends\s+(\w+))?"
)
ID = re.compile(r"@(?:Id|EmbeddedId)\b")
MAPPED = re.compile(r"@MappedSuperclass\b")
ENTITY = re.compile(r"@Entity\b")


def _fail(msg: str) -> int:
    print("REFUSE: INHERITED_ID_REDECLARED " + msg, file=sys.stderr)
    return 1


def strip_comments(text: str) -> str:
    return COMMENT_LINE.sub("", COMMENT_BLOCK.sub("", text))


@dataclass
class TypeInfo:
    name: str
    rel: str
    extends: str | None
    has_id: bool
    mapped: bool
    entity: bool


def load_types(root: Path) -> dict[str, TypeInfo]:
    java = root / "src" / "main" / "java"
    out: dict[str, TypeInfo] = {}
    if not java.is_dir():
        return out
    for path in java.rglob("*.java"):
        if not path.is_file():
            continue
        text = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        match = CLASS.search(text)
        if not match:
            continue
        name = match.group(1)
        out[name] = TypeInfo(
            name=name,
            rel=str(path.relative_to(root)),
            extends=match.group(2),
            has_id=bool(ID.search(text)),
            mapped=bool(MAPPED.search(text)),
            entity=bool(ENTITY.search(text)),
        )
    return out


def ancestor_id(types: dict[str, TypeInfo], start: str) -> TypeInfo | None:
    seen: set[str] = set()
    cur = types.get(start)
    parent = cur.extends if cur else None
    while parent and parent not in seen:
        seen.add(parent)
        info = types.get(parent)
        if info is None:
            return None
        if info.has_id and (info.mapped or info.entity):
            return info
        parent = info.extends
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".", help="destination product root")
    args = ap.parse_args(argv)
    dest = Path(args.root).resolve()
    if not dest.is_dir():
        return 2
    types = load_types(dest)
    if not types:
        print("OK: assert-inherited-id-not-redeclared (no dest Java; idle)")
        return 0
    hits: list[str] = []
    for info in types.values():
        if not info.has_id:
            continue
        anc = ancestor_id(types, info.name)
        if anc is None:
            continue
        hits.append("%s (%s) redeclares @Id; %s already has identity" % (info.name, info.rel, anc.name))
    if hits:
        return _fail("; ".join(hits))
    print("OK: assert-inherited-id-not-redeclared (%d type(s))" % len(types))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
