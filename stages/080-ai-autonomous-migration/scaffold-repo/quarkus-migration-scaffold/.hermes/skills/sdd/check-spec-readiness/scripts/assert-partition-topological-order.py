#!/usr/bin/env python3
"""Mint-time topological import order (Architect BIND 97d3d2f9).

Coverage asks whether every type is declared by someone. This asks whether
card C can compile when it runs: every imported project type must be
provided by C or an ancestor of C — never a descendant or sibling.

Primary operand is stamped dependencies[].provider (available at mint).
Java parse is defense-in-depth when dest or legacy twins exist.

Usage:
  python3 assert-partition-topological-order.py <root>
  python3 assert-partition-topological-order.py <root> --report-only
  python3 assert-partition-topological-order.py <root> --body evidence/bodies/m3-foundational.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from specimen_agnostic import (  # noqa: E402
    dest_path_as_written,
    load_json,
    resolve_java_source,
)
from type_graph import IMP_RE, src_rel_from_path, strip_java_comments  # noqa: E402


def _inner(doc: dict) -> dict:
    body = doc.get("body") if isinstance(doc.get("body"), dict) else doc
    return body if isinstance(body, dict) else {}


def _sid(body: dict, story: dict | None = None) -> str:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    raw = str(ident.get("story_id") or body.get("story_id") or "").strip()
    if raw:
        return raw
    if story:
        return str(story.get("story_id") or "").strip()
    return ""


def _parents_of(body: dict, story: dict | None) -> list[str]:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    raw = ident.get("parents") or (story or {}).get("parents") or []
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def _writable(body: dict) -> list[str]:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    raw = body.get("files_writable") or ident.get("files_writable") or []
    if not isinstance(raw, list):
        return []
    return [dest_path_as_written(x) for x in raw if isinstance(x, str) and x.strip()]


def load_bodies(root: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    d = root / "evidence" / "bodies"
    if not d.is_dir():
        return out
    for path in sorted(d.glob("m3-*.json")):
        if path.name.endswith(".sha256.json"):
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        body = _inner(doc)
        sid = _sid(body)
        if sid:
            out[sid] = body
    return out


def story_map(root: Path) -> dict[str, dict]:
    part = root / "evidence" / "briefs" / "partition.json"
    data = load_json(part) if part.is_file() else {}
    out: dict[str, dict] = {}
    for story in (data or {}).get("stories") or []:
        if not isinstance(story, dict):
            continue
        sid = str(story.get("story_id") or "").strip()
        if sid:
            out[sid] = story
    return out


def parents_map(bodies: dict[str, dict], stories: dict[str, dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for sid, story in stories.items():
        body = bodies.get(sid) or {}
        out[sid] = _parents_of(body, story)
    for sid, body in bodies.items():
        if sid not in out:
            out[sid] = _parents_of(body, None)
    return out


def ancestors(sid: str, parents: dict[str, list[str]]) -> set[str]:
    found: set[str] = set()
    stack = list(parents.get(sid) or [])
    while stack:
        cur = stack.pop()
        if not cur or cur in found:
            continue
        found.add(cur)
        stack.extend(parents.get(cur) or [])
    return found


def owner_map(bodies: dict[str, dict], stories: dict[str, dict]) -> dict[str, str]:
    own: dict[str, str] = {}
    for sid, story in stories.items():
        body = bodies.get(sid) or {}
        paths = _writable(body)
        if not paths:
            raw = story.get("files_writable") or story.get("files") or []
            if isinstance(raw, list):
                paths = [dest_path_as_written(x) for x in raw if isinstance(x, str)]
        for rel in paths:
            if rel.endswith(".java"):
                own[rel] = sid
                own[Path(rel).name] = sid
                own[Path(rel).stem] = sid
    return own


def simple_name(rel: str) -> str:
    return Path(rel).stem


def flags_for_body(
    root: Path,
    sid: str,
    body: dict,
    *,
    parents: dict[str, list[str]],
    owners: dict[str, str],
) -> list[str]:
    allowed = {sid} | ancestors(sid, parents)
    flags: list[str] = []
    for dep in body.get("dependencies") or []:
        if not isinstance(dep, dict):
            continue
        provider = str(dep.get("provider") or "").strip()
        if not provider or provider.lower() in {
            "generated",
            "pre-exists",
            "preexists",
            "pre_exists",
            sid.lower(),
        }:
            continue
        if provider in allowed:
            continue
        if provider in parents or provider in owners.values():
            flags.append(f"{sid}:dep {dep.get('type') or dep.get('file')} provider={provider}")
    for rel in _writable(body):
        if not rel.endswith(".java"):
            continue
        path = resolve_java_source(root, rel)
        if path is None:
            continue
        try:
            text = strip_java_comments(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        for m in IMP_RE.finditer(text):
            fqcn = m.group(1)
            name = fqcn.rsplit(".", 1)[-1]
            owner = owners.get(name)
            if not owner or owner in allowed:
                continue
            flags.append(f"{sid}:import {fqcn} owner={owner}")
    return flags


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--body", default="")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    bodies = load_bodies(root)
    stories = story_map(root)
    parents = parents_map(bodies, stories)
    owners = owner_map(bodies, stories)
    sids = [args.body] if args.body else sorted(set(bodies) | set(stories))
    if args.body:
        bp = Path(args.body)
        if not bp.is_file():
            bp = root / args.body
        if bp.is_file():
            try:
                doc = json.loads(bp.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"FAIL: body {bp}: {exc}", file=sys.stderr)
                return 1
            body = _inner(doc)
            sid = _sid(body)
            sids = [sid] if sid else []
            if sid:
                bodies[sid] = body
                parents = parents_map(bodies, stories)
                owners = owner_map(bodies, stories)
    all_flags: list[str] = []
    for sid in sids:
        if not sid:
            continue
        body = bodies.get(sid) or {}
        all_flags.extend(
            flags_for_body(root, sid, body, parents=parents, owners=owners)
        )
    if args.report_only:
        for line in all_flags:
            print(f"REPORT: {line}")
        print(f"OK: topological report n={len(all_flags)}")
        return 0
    if all_flags:
        print(
            "REFUSE: TOPOLOGICAL_ORDER descendant/sibling import "
            + "; ".join(all_flags[:12]),
            file=sys.stderr,
        )
        return 1
    print("OK: partition topological order")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
