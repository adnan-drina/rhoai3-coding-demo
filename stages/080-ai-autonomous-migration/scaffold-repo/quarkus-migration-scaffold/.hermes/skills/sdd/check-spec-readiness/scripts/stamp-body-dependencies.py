#!/usr/bin/env python3
"""Stamp body `dependencies:` from partition/body ownership (Operator E-20260811T144200Z).

For each Java import reachable from this body's files_writable, emit:
  { "file": "<rel path>", "provider": "<story_id>" | "pre-exists" }

`provider` is the story whose files_writable owns the file. When the file exists
under legacy/modernized but is owned by no story → `pre-exists` (scaffold or
already-landed substrate). Orphans that must be migration targets should be
assigned in partition/bodies before create — this stamp does not invent owners.

Usage:
  python3 stamp-body-dependencies.py /projects/modernized --body evidence/bodies/m3-s-002a.json --write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

IMP_RE = re.compile(r"^\s*import\s+([a-zA-Z0-9_.]+)\s*;", re.M)

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from specimen_agnostic import legacy_java_prefixes, path_rewrites  # noqa: E402


def make_norm_file(root: Path):
    rewrites = path_rewrites(root)

    def norm_file(path: str) -> str:
        p = path.replace("\\", "/")
        for prefix in (
            "/projects/.derived/legacy-at-3/",
            "/projects/modernized/",
            "/projects/legacy/",
            "projects/.derived/legacy-at-3/",
            "projects/modernized/",
            "projects/legacy/",
        ):
            if p.startswith(prefix):
                p = p[len(prefix) :]
        for dest_p, leg_p in rewrites:
            if p.startswith(dest_p):
                p = leg_p + p[len(dest_p) :]
                break
        return p.lstrip("./")

    return norm_file


def load_json(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def writable_paths(body: dict) -> list[str]:
    out: list[str] = []
    for item in body.get("files_writable") or body.get("write_set") or []:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            for k in ("dest", "dst", "destination", "path", "file", "src"):
                if item.get(k):
                    out.append(str(item[k]))
                    break
    return out


def provider_map(bodies_dir: Path, norm_file) -> dict[str, str]:
    own: dict[str, str] = {}
    if not bodies_dir.is_dir():
        return own
    for path in sorted(bodies_dir.glob("m3-*.json")):
        if path.name.endswith(".sha256.json"):
            continue
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        ident = data.get("identity") if isinstance(data.get("identity"), dict) else {}
        sid = str(ident.get("story_id") or data.get("story_id") or "").strip()
        if not sid:
            continue
        for f in writable_paths(data):
            nf = norm_file(f)
            if not nf or nf.endswith("pom.xml"):
                continue
            # First owner wins; overlaps are partition-coverage INVALID elsewhere
            own.setdefault(nf, sid)
    return own


def resolve_legacy(root: Path, rel: str) -> Path | None:
    for base in (
        root / ".." / ".derived" / "legacy-at-3",
        Path("/projects/.derived/legacy-at-3"),
        root.parent / ".derived" / "legacy-at-3",
    ):
        cand = (base / rel).resolve()
        if cand.is_file():
            return cand
    # also try under root (modernized may still hold referent)
    cand = root / rel
    if cand.is_file():
        return cand
    return None


def imports_for(java_path: Path, pkg_prefixes: list[str]) -> list[str]:
    text = java_path.read_text(encoding="utf-8", errors="ignore")
    out: list[str] = []
    for m in IMP_RE.finditer(text):
        imp = m.group(1)
        if imp.endswith(".*"):
            continue
        if pkg_prefixes and not any(imp.startswith(p) for p in pkg_prefixes):
            continue
        if not pkg_prefixes:
            # no prefix discovered — only accept imports under src/main/java tree shape
            if not imp or imp.startswith("java.") or imp.startswith("javax.") or imp.startswith("jakarta."):
                continue
        out.append("src/main/java/" + imp.replace(".", "/") + ".java")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--body", required=True)
    ap.add_argument("--bodies", default="evidence/bodies")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    body_path = Path(args.body)
    if not body_path.is_absolute():
        body_path = root / body_path
    body = load_json(body_path)
    if not isinstance(body, dict):
        print(f"FAIL: bad body {body_path}", file=sys.stderr)
        return 1
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    self_sid = str(ident.get("story_id") or body.get("story_id") or "").strip()
    norm_file = make_norm_file(root)
    pkg_prefixes = legacy_java_prefixes(root)
    own = provider_map(root / args.bodies, norm_file)
    deps: dict[str, str] = {}
    for wf in writable_paths(body):
        rel = norm_file(wf)
        if not rel.endswith(".java"):
            continue
        lp = resolve_legacy(root, rel)
        if lp is None:
            continue
        for dep_rel in imports_for(lp, pkg_prefixes):
            if dep_rel == rel:
                continue
            provider = own.get(dep_rel)
            if provider == self_sid:
                continue
            if provider:
                deps[dep_rel] = provider
            else:
                # exists on disk → pre-exists; missing → still record pre-exists
                # only when readable from legacy (import resolved from source)
                deps.setdefault(dep_rel, "pre-exists")
    ordered = [
        {"file": f, "provider": deps[f]}
        for f in sorted(deps.keys())
    ]
    body["dependencies"] = ordered
    if args.write:
        body_path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        print(f"OK: stamped dependencies={len(ordered)} → {body_path}")
    else:
        print(json.dumps({"dependencies": ordered}, indent=2))
    # Fail closed when any dep is pre-exists but looks like a migration target
    # under model/ or repository/ interface tree with no owner.
    holes = [
        d["file"]
        for d in ordered
        if d["provider"] == "pre-exists"
        and (
            "/model/" in d["file"]
            or (
                "/repository/" in d["file"]
                and d["file"].endswith("Repository.java")
                and "/jdbc/" not in d["file"]
                and "/jpa/" not in d["file"]
                and "/springdatajpa/" not in d["file"]
            )
        )
    ]
    if holes:
        print(
            "DEPENDENCY_HOLE: model/interface deps lack story owner — "
            "assign in partition/bodies before dispatch:",
            file=sys.stderr,
        )
        for h in holes[:20]:
            print(f"  - {h}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
