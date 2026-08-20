#!/usr/bin/env python3
"""Move dest types that import descendant-owned types onto polish.

Architect #34: a whole-domain facade cannot live on a slice that runs
before the entity stories. Specimen-agnostic: any dest Java whose import
closure needs types owned by a descendant story is reassigned to polish.

Does not grow handover-mint.py. Does not hardcode a specimen facade type.

Usage:
  python3 relocate-descendant-import-writesets.py <root> --write
  python3 relocate-descendant-import-writesets.py <root> --dry-run
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
from type_graph import IMP_RE, strip_java_comments  # noqa: E402


def _inner(doc: dict) -> dict:
    body = doc.get("body") if isinstance(doc.get("body"), dict) else doc
    return body if isinstance(body, dict) else {}


def _sid_of(body: dict) -> str:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    return str(ident.get("story_id") or body.get("story_id") or "").strip()


def _kind(body: dict, story: dict) -> str:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    raw = str(ident.get("kind") or body.get("kind") or story.get("kind") or "").strip()
    if raw:
        return raw.lower()
    return _sid_of(body).lower()


def _writables(obj: dict) -> list[str]:
    ident = obj.get("identity") if isinstance(obj.get("identity"), dict) else {}
    raw = obj.get("files_writable") or ident.get("files_writable") or []
    if not isinstance(raw, list):
        return []
    return [dest_path_as_written(x) for x in raw if isinstance(x, str) and x.strip()]


def _set_writables(obj: dict, paths: list[str]) -> None:
    obj["files_writable"] = list(paths)
    ident = obj.get("identity")
    if isinstance(ident, dict) and "files_writable" in ident:
        ident["files_writable"] = list(paths)


def _apply_writables(
    sid: str,
    keep: list[str],
    stories: dict,
    bodies: dict,
) -> None:
    if sid in stories:
        stories[sid]["files_writable"] = list(keep)
    if sid in bodies:
        _path, doc = bodies[sid]
        target = doc["body"] if isinstance(doc.get("body"), dict) else doc
        _set_writables(target, keep)


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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    part_path = root / "evidence" / "briefs" / "partition.json"
    if not part_path.is_file():
        print(f"FAIL: missing {part_path}", file=sys.stderr)
        return 1
    part = load_json(part_path)
    if not isinstance(part, dict):
        print("FAIL: partition.json is not an object", file=sys.stderr)
        return 1
    bodies_dir = root / "evidence" / "bodies"
    bodies: dict[str, tuple[Path, dict]] = {}
    if bodies_dir.is_dir():
        for path in sorted(bodies_dir.glob("m3-*.json")):
            if path.name.endswith(".sha256.json"):
                continue
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            body = _inner(doc)
            sid = _sid_of(body)
            if sid:
                bodies[sid] = (path, doc if "body" in doc else body)
    stories = {}
    for story in part.get("stories") or []:
        if isinstance(story, dict) and str(story.get("story_id") or "").strip():
            stories[str(story.get("story_id")).strip()] = story
    polish_sid = ""
    for sid, story in stories.items():
        body = {}
        if sid in bodies:
            _p, doc = bodies[sid]
            body = _inner(doc)
        if _kind(body, story) == "polish" or sid.lower() == "polish":
            polish_sid = sid
            break
    if not polish_sid:
        print("REFUSE: FACADE_RELOCATE no polish story to receive facades", file=sys.stderr)
        return 1
    parents: dict[str, list[str]] = {}
    for sid, story in stories.items():
        body = _inner(bodies[sid][1]) if sid in bodies else {}
        ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
        raw = ident.get("parents") or story.get("parents") or []
        parents[sid] = [str(x).strip() for x in raw if isinstance(raw, list) and str(x).strip()] if isinstance(raw, list) else []
    owners: dict[str, list[str]] = {}
    for sid, story in stories.items():
        body = _inner(bodies[sid][1]) if sid in bodies else {}
        for rel in _writables(body) or [
            dest_path_as_written(x)
            for x in (story.get("files_writable") or [])
            if isinstance(x, str)
        ]:
            if rel.endswith(".java"):
                for key in (Path(rel).name, Path(rel).stem, rel):
                    lst = owners.setdefault(key, [])
                    if sid not in lst:
                        lst.append(sid)
    moved: list[str] = []
    relocated: list[str] = []
    for sid, story in list(stories.items()):
        if sid == polish_sid:
            continue
        body = _inner(bodies[sid][1]) if sid in bodies else {}
        allowed = {sid} | ancestors(sid, parents)
        current = _writables(body) or [
            dest_path_as_written(x)
            for x in (story.get("files_writable") or [])
            if isinstance(x, str)
        ]
        keep: list[str] = []
        to_polish: list[str] = []
        for rel in current:
            if not rel.endswith(".java"):
                keep.append(rel)
                continue
            path = resolve_java_source(root, rel)
            if path is None:
                keep.append(rel)
                continue
            try:
                text = strip_java_comments(
                    path.read_text(encoding="utf-8", errors="ignore")
                )
            except OSError:
                keep.append(rel)
                continue
            bad = False
            for m in IMP_RE.finditer(text):
                name = m.group(1).rsplit(".", 1)[-1]
                claimants = owners.get(name) or []
                owner = claimants[0] if len(claimants) == 1 else ""
                if owner and owner not in allowed:
                    bad = True
                    break
            if bad:
                to_polish.append(rel)
                if rel not in relocated:
                    relocated.append(rel)
                moved.append(f"{rel}:{sid}->{polish_sid}")
            else:
                keep.append(rel)
        if not to_polish:
            continue
        story["files_writable"] = keep
        if sid in bodies:
            path, doc = bodies[sid]
            target = doc["body"] if isinstance(doc.get("body"), dict) else doc
            _set_writables(target, keep)
            deps = target.get("dependencies") if isinstance(target.get("dependencies"), list) else []
            kept_deps = []
            for dep in deps:
                if not isinstance(dep, dict):
                    continue
                provider = str(dep.get("provider") or "").strip()
                if provider and provider not in allowed and provider in stories:
                    continue
                kept_deps.append(dep)
            target["dependencies"] = kept_deps
        pstory = stories[polish_sid]
        pbody = _inner(bodies[polish_sid][1]) if polish_sid in bodies else {}
        pfiles = _writables(pbody) or [
            dest_path_as_written(x)
            for x in (pstory.get("files_writable") or [])
            if isinstance(x, str)
        ]
        for rel in to_polish:
            if rel not in pfiles:
                pfiles.append(rel)
        pstory["files_writable"] = pfiles
        if polish_sid in bodies:
            _pp, pdoc = bodies[polish_sid]
            ptarget = pdoc["body"] if isinstance(pdoc.get("body"), dict) else pdoc
            _set_writables(ptarget, pfiles)
    # Serial coverage does not refuse non-pom overlap (152824Z). A facade
    # moved onto polish must not remain on sibling write-sets (dest US1–US6).
    dropped_overlap = 0
    if relocated:
        drop = set(relocated)
        for sid, story in stories.items():
            if sid == polish_sid:
                continue
            body = _inner(bodies[sid][1]) if sid in bodies else {}
            current = _writables(body) or [
                dest_path_as_written(x)
                for x in (story.get("files_writable") or [])
                if isinstance(x, str)
            ]
            keep = [p for p in current if p not in drop]
            if keep != current:
                dropped_overlap += len(current) - len(keep)
                _apply_writables(sid, keep, stories, bodies)
        if dropped_overlap:
            moved.append(f"unique-owner:{dropped_overlap}")
    owners = {}
    for sid, story in stories.items():
        body = _inner(bodies[sid][1]) if sid in bodies else {}
        current = _writables(body) or [
            dest_path_as_written(x)
            for x in (story.get("files_writable") or [])
            if isinstance(x, str)
        ]
        for rel in current:
            owners.setdefault(rel, []).append(sid)
    for rel, claimants in owners.items():
        if len(owners[rel]) > 1:
            print(
                f"REFUSE: MULTI_OWNER {rel}:{'+'.join(claimants)}",
                file=sys.stderr,
            )
            return 1
    if not moved:
        print("OK: FACADE_RELOCATE none")
        return 0
    print("OK: FACADE_RELOCATE " + " ".join(moved))
    if args.write:
        part_path.write_text(json.dumps(part, indent=2) + "\n", encoding="utf-8")
        for sid, (path, doc) in bodies.items():
            path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
