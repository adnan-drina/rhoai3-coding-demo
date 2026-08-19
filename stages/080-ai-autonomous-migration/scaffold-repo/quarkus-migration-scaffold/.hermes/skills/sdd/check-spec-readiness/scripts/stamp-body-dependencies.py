#!/usr/bin/env python3
"""Stamp body `dependencies:` from partition/body ownership (Operator E-20260811T144200Z).

For each Java import reachable from this body's files_writable, emit:
  { "file": "<dest-rel path>", "provider": "<story_id>" | "pre-exists" | "generated" }

`provider` is the story whose files_writable owns the file. Paths are dest-tree
(via migration.yaml `path_rewrites` and `intra_package_maps`). Never emit a
legacy Spring path as dest-relative `pre-exists`
(Architect E-20260817T162352Z / E-20260817T161821Z).

Unowned dest twins of project `extends`, in-prefix `import`s, and
same-package types the source names are added to *this* story's write-set
— transitive closure, stop at JDK/framework. Generated types
(target/generated-sources, @Generated, or a declared generator plugin)
stamp `provider: "generated"` and are not assigned onto the partition.
When partition.json names this story, source dest twins are assigned onto
the story's declared frame first (V34-5). Do not stamp unowned collaborators as
`pre-exists` (generated types are the third kind, not this fallthrough). The
walk lives in `type_graph.py` so M1 can invoke it without a `--body`.

Orphans that remain unowned dest domain-leaf/repo paths → DEPENDENCY_HOLE
listing the full dest-path set. Body paths outside the expanded frame
still WRITESET_NOT_SUBSET (entity/ extra beside a model/ declaration).

Usage:
  python3 stamp-body-dependencies.py /projects/modernized --body evidence/bodies/m3-s-002a.json --write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from generated_sources import is_generated  # noqa: E402
from specimen_agnostic import (  # noqa: E402
    dest_hole_leaves,
    dest_path_as_written,
    intra_package_maps,
    legacy_java_prefixes,
    partition_story_writeset,
    path_rewrites,
    rewrite_across,
)
from type_graph import (  # noqa: E402
    IMP_RE,
    project_type_closure,
    src_rel_from_path,
)

_ABS_PREFIXES = (
    "/projects/.derived/legacy-at-3/",
    "/projects/modernized/",
    "/projects/legacy/",
    "projects/.derived/legacy-at-3/",
    "projects/modernized/",
    "projects/legacy/",
)


def strip_abs_prefix(path: str) -> str:
    p = path.replace("\\", "/").lstrip("./")
    for prefix in _ABS_PREFIXES:
        if p.startswith(prefix):
            return p[len(prefix) :]
    return p


def make_rewrites(root: Path):
    pairs = path_rewrites(root)
    leaves = intra_package_maps(root)

    def to_dest(path: str) -> str:
        return rewrite_across(
            strip_abs_prefix(path), pairs, to_dest=True, leaf_pairs=leaves
        )

    def to_legacy(path: str) -> str:
        return rewrite_across(
            strip_abs_prefix(path), pairs, to_dest=False, leaf_pairs=leaves
        )

    return pairs, to_dest, to_legacy


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


def provider_map(bodies_dir: Path, to_dest) -> dict[str, str]:
    own: dict[str, str] = {}
    if not bodies_dir.is_dir():
        return own
    for path in sorted(bodies_dir.glob("*.json")):
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
            nf = to_dest(f)
            if not nf or nf.endswith("pom.xml"):
                continue
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
    return None


def resolve_scope_legacy(body: dict, rel_or_basename: str) -> str | None:
    """Pick a legacy relative path from files_in_scope by dest rel or basename.

    Accepts string scope entries and {legacy, dest} dicts (M2 partition shape).
    """
    rel_n = rel_or_basename.replace("\\", "/")
    basename = Path(rel_n).name
    for item in body.get("files_in_scope") or []:
        if isinstance(item, dict):
            dest = str(item.get("dest") or item.get("dst") or "").replace("\\", "/")
            legacy = str(item.get("legacy") or item.get("src") or "").replace(
                "\\", "/"
            )
            if not legacy:
                continue
            if dest and dest != rel_n and not dest.endswith("/" + basename):
                continue
            if dest or legacy.endswith("/" + basename) or legacy.endswith(basename):
                p = strip_abs_prefix(legacy)
                if p.startswith("src/"):
                    return p
            continue
        if not isinstance(item, str):
            continue
        p = item.replace("\\", "/")
        if p.endswith("/" + basename) or p.endswith(basename):
            if "org/springframework" in p or "/.derived/" in p or p.startswith(
                "src/main/java/"
            ):
                p = strip_abs_prefix(p)
                if p.startswith("src/"):
                    return p
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
            if (
                not imp
                or imp.startswith("java.")
                or imp.startswith("javax.")
                or imp.startswith("jakarta.")
            ):
                continue
        out.append("src/main/java/" + imp.replace(".", "/") + ".java")
    return out


def _endpoint_tokens(ep: str) -> set[str]:
    s = " ".join(str(ep).split())
    out = {s} if s else set()
    parts = s.split(" ", 1)
    if len(parts) == 2 and parts[1].strip():
        out.add(parts[1].strip())
    return out


def _row_tokens(row: dict) -> set[str]:
    method = str(row.get("http_method") or "").strip().upper()
    path = str(row.get("http_path") or "").strip()
    symbol = str(row.get("symbol") or "").strip()
    out: set[str] = set()
    if path:
        out.add(path)
        if method:
            out.add(f"{method} {path}")
    if symbol:
        out.add(symbol)
    return {x for x in out if x}


def load_partition_story(root: Path, sid: str) -> dict | None:
    path = root / "evidence/briefs/partition.json"
    data = load_json(path)
    if not isinstance(data, dict):
        return None
    for story in data.get("stories") or data.get("units") or []:
        if not isinstance(story, dict):
            continue
        if str(story.get("story_id") or "").strip() == sid:
            return story
    return None


def is_http_story(root: Path, body: dict, sid: str) -> bool:
    story = load_partition_story(root, sid) or {}
    if story.get("endpoints"):
        return True
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    raw = ident.get("operand_class") or body.get("operand_class")
    classes = raw if isinstance(raw, list) else [raw]
    return any(str(c).strip().lower() in {"rest", "api"} for c in classes if c)


def inventory_files_collect_all(root: Path, story: dict) -> list[str]:
    """A-8 join, collect-all unique inventory `file`s (Architect E-20260817T164700Z)."""
    wanted: set[str] = set()
    for ep in story.get("endpoints") or []:
        wanted |= _endpoint_tokens(str(ep))
    inv_path = root / "evidence/entry-point-inventory.json"
    data = load_json(inv_path)
    if not isinstance(data, dict) or not wanted:
        return []
    files: list[str] = []
    seen: set[str] = set()
    for row in data.get("entry_points") or []:
        if not isinstance(row, dict):
            continue
        if not (wanted & _row_tokens(row)):
            continue
        rel = strip_abs_prefix(str(row.get("file") or ""))
        if not rel.endswith(".java") or rel in seen:
            continue
        seen.add(rel)
        files.append(rel)
    return files


_DEST_ONLY_KINDS = frozenset({"setup", "foundational", "polish"})


def story_kind(root: Path, body: dict, sid: str) -> str:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    raw = str(ident.get("kind") or body.get("kind") or "").strip().lower()
    if raw:
        return raw
    story = load_partition_story(root, sid) or {}
    k = str(story.get("kind") or "").strip().lower()
    if k:
        return k
    return sid.strip().lower()


def locus_is_non_java(body: dict) -> bool:
    for ref in body.get("refs") or []:
        if not isinstance(ref, dict):
            continue
        if str(ref.get("key") or "") != "legacy_locus":
            continue
        raw = str(ref.get("path") or "").strip()
        return bool(raw) and not raw.lower().endswith(".java")
    return False


def dest_only_empty_deps_ok(
    root: Path, body: dict, sid: str, resolved_sources: int
) -> bool:
    """Architect E-20260817T170100Z: dest-only create is not VACUOUS.

    kind in {setup, foundational, polish} + non-Java locus + dest Java that
    does not resolve after package rewrite. HTTP stories still refuse.
    """
    if is_http_story(root, body, sid):
        return False
    if story_kind(root, body, sid) not in _DEST_ONLY_KINDS:
        return False
    if not locus_is_non_java(body):
        return False
    return resolved_sources == 0


def java_legacy_locus_file(root: Path, body: dict) -> Path | None:
    """Parse refs.legacy_locus only when the path is Java, not harvest JSON."""
    for ref in body.get("refs") or []:
        if not isinstance(ref, dict):
            continue
        if str(ref.get("key") or "") != "legacy_locus":
            continue
        raw = str(ref.get("path") or "").strip()
        if not raw.lower().endswith(".java"):
            return None
        p = Path(raw)
        if p.is_file():
            return p
        rel = strip_abs_prefix(raw)
        return resolve_legacy(root, rel)
    return None


def harvest_parse_roots(
    root: Path,
    body: dict,
    *,
    sid: str,
    to_legacy,
) -> list[Path]:
    """Legacy Java to parse. HTTP: inventory files + Java locus. Never dest Resource."""
    seen: set[str] = set()
    out: list[Path] = []

    def add(path: Path | None) -> None:
        if path is None or not path.is_file():
            return
        try:
            key = str(path.resolve())
        except OSError:
            return
        if key in seen:
            return
        seen.add(key)
        out.append(path)

    if is_http_story(root, body, sid):
        story = load_partition_story(root, sid) or {
            "story_id": sid,
            "endpoints": body.get("endpoints") or [],
        }
        for rel in inventory_files_collect_all(root, story):
            add(resolve_legacy(root, rel))
        add(java_legacy_locus_file(root, body))
        return out
    for wf in writable_paths(body):
        rel = strip_abs_prefix(str(wf))
        if not rel.endswith(".java"):
            continue
        nrel = rel.replace("\\", "/")
        if nrel.startswith("src/test/") or "/src/test/" in nrel:
            continue
        add(resolve_writable_legacy(root, body, rel, to_legacy))
    return out


def resolve_writable_legacy(
    root: Path, body: dict, rel: str, to_legacy
) -> Path | None:
    lp = resolve_legacy(root, to_legacy(rel))
    if lp is not None:
        return lp
    scope_rel = resolve_scope_legacy(body, rel)
    if scope_rel:
        lp = resolve_legacy(root, scope_rel)
        if lp is not None:
            return lp
        for item in body.get("files_in_scope") or []:
            if isinstance(item, str) and item.endswith(Path(rel).name):
                cand = Path(item)
                if cand.is_file():
                    return cand
    return None


def append_unique(seq: list, item: str) -> None:
    if item not in seq:
        seq.append(item)


def inherited_unowned_dests(
    root: Path,
    body: dict,
    *,
    to_dest,
    to_legacy,
    pkg_prefixes: list[str],
    own: dict[str, str],
    self_sid: str,
    harvest_roots: list[Path] | None = None,
) -> list[str]:
    """Dest twins reachable by inheritance or in-prefix import from owned Java.

    Specimen-agnostic: walk project_type_closure from harvest roots. Skip
    dests another story already owns. JDK/framework stop is inside the
    closure walker.
    """
    found: list[str] = []
    writable = {to_dest(x) for x in writable_paths(body)}
    starts = list(harvest_roots or [])
    if not starts:
        for wf in writable_paths(body):
            rel = to_dest(wf)
            if not rel.endswith(".java"):
                continue
            nrel = rel.replace("\\", "/")
            if nrel.startswith("src/test/") or "/src/test/" in nrel:
                continue
            lp = resolve_writable_legacy(root, body, rel, to_legacy)
            if lp is not None:
                starts.append(lp)
    for lp in starts:
        for extra in project_type_closure(lp, pkg_prefixes):
            src_rel = src_rel_from_path(extra)
            if not src_rel:
                continue
            dest = to_dest(src_rel)
            if dest in writable or dest in found:
                continue
            if is_generated(
                root, dest, source=extra, legacy_rel=to_legacy(dest)
            ):
                continue
            owner = own.get(dest)
            if owner and owner != self_sid:
                continue
            found.append(dest)
    return found


def _field_dests(raw: object) -> set[str]:
    out: set[str] = set()
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.add(dest_path_as_written(item))
        elif isinstance(item, dict):
            for k in ("dest", "dst", "path", "file"):
                if item.get(k):
                    out.add(dest_path_as_written(str(item[k])))
                    break
    return out


def assign_inherited_to_partition(
    data: dict, sid: str, dests: list[str]
) -> list[str]:
    """Append unowned dest twins onto this story's declared write-set keys.

    Only mutates keys that already hold paths so a new files_writable list
    cannot hide files_in_scope as the declared frame.
    """
    assigned: list[str] = []
    stories = data.get("stories")
    if not isinstance(stories, list):
        return assigned
    for story in stories:
        if not isinstance(story, dict):
            continue
        if str(story.get("story_id") or "").strip() != sid:
            continue
        keys = [
            k
            for k in (
                "files_writable",
                "files",
                "files_in_scope",
                "legacy_files",
                "scope_files",
            )
            if _field_dests(story.get(k))
        ]
        for dest in dests:
            written = dest_path_as_written(dest)
            touched = False
            for key in keys:
                raw = story.get(key)
                if not isinstance(raw, list):
                    continue
                if written in _field_dests(raw):
                    continue
                raw.append(dest)
                touched = True
            if touched:
                assigned.append(dest)
        return assigned
    return assigned


def close_write_set(
    root: Path,
    body: dict,
    *,
    to_dest,
    to_legacy,
    pkg_prefixes: list[str],
    own: dict[str, str],
    self_sid: str,
    harvest_roots: list[Path] | None = None,
    allowed: set[str] | None = None,
) -> list[str]:
    """Add unowned dest twins of project types onto this story's write-set.

    When ``allowed`` is set, dest twins outside that declared frame are
    skipped. Callers expand ``allowed`` with dependency-reachable unowned
    dest twins first (V34-5 AMEND: import+extends). Mint-path extras that
    are not in that closure (entity/ beside partition model/) still skip
    and WRITESET_NOT_SUBSET.
    """
    added: list[str] = []
    writable = [to_dest(x) for x in writable_paths(body)]
    scope = body.get("files_in_scope")
    if not isinstance(scope, list):
        scope = list(writable)
        body["files_in_scope"] = scope
    fw = body.get("files_writable")
    if not isinstance(fw, list):
        fw = list(writable)
        body["files_writable"] = fw
    starts = list(harvest_roots or [])
    if not starts:
        for wf in list(writable):
            rel = to_dest(wf)
            if not rel.endswith(".java"):
                continue
            nrel = rel.replace("\\", "/")
            if nrel.startswith("src/test/") or "/src/test/" in nrel:
                continue
            lp = resolve_writable_legacy(root, body, rel, to_legacy)
            if lp is not None:
                starts.append(lp)
    for lp in starts:
        for extra in project_type_closure(lp, pkg_prefixes):
            src_rel = src_rel_from_path(extra)
            if not src_rel:
                continue
            dest = to_dest(src_rel)
            if dest in writable or dest in added:
                continue
            if is_generated(
                root, dest, source=extra, legacy_rel=to_legacy(dest)
            ):
                continue
            if allowed is not None and dest_path_as_written(dest) not in allowed:
                continue
            owner = own.get(dest)
            if owner and owner != self_sid:
                continue
            append_unique(fw, dest)
            append_unique(scope, dest)
            own.setdefault(dest, self_sid)
            added.append(dest)
            writable.append(dest)
    if added:
        ident = body.get("identity") if isinstance(body.get("identity"), dict) else None
        if ident is not None:
            ident["operand_count"] = len(
                [p for p in writable_paths(body) if isinstance(p, str) and p.strip()]
            )
    return added


def is_model_or_repo_hole(
    dest_rel: str, leaves: tuple[str, ...] | None = None
) -> bool:
    f = dest_rel.replace("\\", "/")
    for name in leaves if leaves else ("model",):
        token = "/" + str(name).strip("/") + "/"
        if token != "//" and token in f:
            return True
    return (
        "/repository/" in f
        and f.endswith("Repository.java")
        and "/jdbc/" not in f
        and "/jpa/" not in f
        and "/springdatajpa/" not in f
    )


def looks_like_legacy_tree(path: str) -> bool:
    p = path.replace("\\", "/")
    return "/org/springframework/samples/" in p or "/org/springframework/" in p


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit: 0=stamp ok (deps may be empty only with proof), "
            "1=DEPENDENCY_HOLE or DEPENDENCY_STAMP_VACUOUS, 2=usage"
        ),
    )
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
    part_status, part_files = partition_story_writeset(root, self_sid)
    allowed: set[str] | None = None
    if part_status == "missing_story":
        print(
            "WRITESET_NOT_SUBSET: identity.story_id "
            f"{self_sid!r} is not in evidence/briefs/partition.json "
            "(assert-body-writeset-subset-of-partition / E-20260819T104254Z)",
            file=sys.stderr,
        )
        return 1
    if part_status == "ok" and part_files:
        allowed = set(part_files)
    _pairs, to_dest, to_legacy = make_rewrites(root)
    pkg_prefixes = legacy_java_prefixes(root)
    own = provider_map(root / args.bodies, to_dest)
    roots = harvest_parse_roots(root, body, sid=self_sid, to_legacy=to_legacy)
    inherited = inherited_unowned_dests(
        root,
        body,
        to_dest=to_dest,
        to_legacy=to_legacy,
        pkg_prefixes=pkg_prefixes,
        own=own,
        self_sid=self_sid,
        harvest_roots=roots,
    )
    part_path = root / "evidence/briefs/partition.json"
    part_data = load_json(part_path) if part_path.is_file() else None
    assigned: list[str] = []
    if (
        allowed is not None
        and inherited
        and isinstance(part_data, dict)
        and isinstance(part_data.get("stories"), list)
    ):
        assigned = assign_inherited_to_partition(part_data, self_sid, inherited)
        for dest in assigned:
            allowed.add(dest_path_as_written(dest))
        if assigned:
            print(
                "OK: assigned inheritance-reachable dest twins onto partition n="
                + str(len(assigned))
                + " "
                + " ".join(assigned[:12])
            )
    added = close_write_set(
        root,
        body,
        to_dest=to_dest,
        to_legacy=to_legacy,
        pkg_prefixes=pkg_prefixes,
        own=own,
        self_sid=self_sid,
        harvest_roots=roots,
        allowed=allowed,
    )
    if allowed is not None:
        extras = sorted(
            {
                dest_path_as_written(p)
                for p in writable_paths(body)
                if dest_path_as_written(p) not in allowed
            }
        )
        if extras:
            print(
                "WRITESET_NOT_SUBSET: body.files_writable is not a subset of "
                f"partition.stories[{self_sid}].files_writable extras="
                + " ".join(extras[:12])
                + " (repair body; do not stamp digest; E-20260819T104254Z)",
                file=sys.stderr,
            )
            return 1
    if added:
        print(
            "OK: supertype closure added dest twins n="
            + str(len(added))
            + " "
            + " ".join(added[:12])
        )
    if roots:
        print(
            "OK: harvest parse roots n="
            + str(len(roots))
            + " "
            + " ".join((src_rel_from_path(p) or p.name) for p in roots[:8])
        )
    deps: dict[str, str] = {}
    unowned_imports: list[str] = []
    java_writables = 0
    in_pkg_imports_seen = 0
    self_owned_imports = 0
    for wf in writable_paths(body):
        rel = to_dest(wf)
        if not rel.endswith(".java"):
            continue
        nrel = rel.replace("\\", "/")
        if nrel.startswith("src/test/") or "/src/test/" in nrel:
            continue
        java_writables += 1
    resolved_sources = len(roots)
    for lp in roots:
        for dep_rel in imports_for(lp, pkg_prefixes):
            in_pkg_imports_seen += 1
            dest = to_dest(dep_rel)
            if looks_like_legacy_tree(dest) and dest == dep_rel:
                continue
            provider = own.get(dest)
            if provider == self_sid:
                self_owned_imports += 1
                continue
            if provider:
                deps[dest] = provider
            elif is_generated(root, dest, legacy_rel=to_legacy(dest)):
                # Classify before pre-exists / hole fallthrough (dc66c244).
                deps[dest] = "generated"
            else:
                # AMEND V34-5: unowned in-prefix dest twins are a hole, not
                # pre-exists (pre-exists DEST_MISS at JAVA 0 is the wrong class).
                append_unique(unowned_imports, dest)
    ordered = [{"file": f, "provider": deps[f]} for f in sorted(deps.keys())]
    body["dependencies"] = ordered

    dest_only_ok = dest_only_empty_deps_ok(
        root, body, self_sid, resolved_sources
    )
    vacuous_ok = bool(body.get("dependencies_vacuous_ok")) or dest_only_ok
    if dest_only_ok and java_writables and not ordered:
        print(
            "OK: stamped dependencies=0 "
            "(dest-only create; non-Java locus; unresolved dest Java)"
        )
    # Unowned dest twins that remain after the walk are DEPENDENCY_HOLE
    # below, not A-6 vacuous.
    if java_writables and not ordered and not vacuous_ok and not unowned_imports:
        if not pkg_prefixes:
            print(
                "DEPENDENCY_STAMP_VACUOUS: body has Java writables but "
                "legacyBasePackage/legacyPackage is unset and inventory "
                "prefix discovery failed — fix migration.yaml stamp "
                "(A-6 E-20260814T103448Z)",
                file=sys.stderr,
            )
            return 1
        if not resolved_sources:
            print(
                "DEPENDENCY_STAMP_VACUOUS: could not resolve any legacy "
                "Java sources for files_writable (path_rewrites / "
                "legacyPackage+targetPackage missing or wrong) — "
                "refusing empty dependencies stamp (A-6)",
                file=sys.stderr,
            )
            return 1
        if in_pkg_imports_seen:
            if self_owned_imports and not ordered:
                print(
                    f"OK: stamped dependencies=0 "
                    f"(self-owned imports={self_owned_imports}; "
                    f"same-story closure is not a hole)"
                )
            else:
                print(
                    "DEPENDENCY_STAMP_VACUOUS: resolved sources have in-package "
                    "imports but stamped dependencies=[] — provider map / "
                    "norm mismatch (A-6)",
                    file=sys.stderr,
                )
                return 1
        print(
            f"OK: stamped dependencies=0 "
            f"(resolved={resolved_sources} java_writables={java_writables} "
            f"no in-package imports)"
        )

    if args.write:
        if assigned and isinstance(part_data, dict):
            part_path.parent.mkdir(parents=True, exist_ok=True)
            part_path.write_text(
                json.dumps(part_data, indent=2) + "\n", encoding="utf-8"
            )
            print(f"OK: partition frame gained inheritance-reachable types → {part_path}")
        body_path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        try:
            from injection_receipt import write_injection_receipt
        except ImportError:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from injection_receipt import write_injection_receipt
        receipt = write_injection_receipt(
            root,
            script="stamp-body-dependencies.py",
            target=body_path,
            fields=["dependencies", "files_writable", "files_in_scope"],
            source=(
                "legacy source import+extends scan + provider map from "
                "evidence/bodies (migration.yaml path_rewrites + "
                "intra_package_maps; dest paths)"
            ),
            summary=f"stamped dependencies n={len(ordered)} closure={len(added)} inherited={len(assigned)}",
            extra={"n": len(ordered), "closure": len(added), "inherited": len(assigned)},
        )
        print(f"OK: stamped dependencies={len(ordered)} → {body_path}")
        print(f"OK: injection receipt → {receipt}")
    else:
        print(json.dumps({"dependencies": ordered, "closure": added}, indent=2))
    hole_leaves = dest_hole_leaves(root)
    holes = list(unowned_imports)
    holes.extend(
        d["file"]
        for d in ordered
        if d["provider"] == "pre-exists"
        and is_model_or_repo_hole(d["file"], hole_leaves)
    )
    # unique, stable
    seen_h: set[str] = set()
    uniq: list[str] = []
    for h in holes:
        if h not in seen_h:
            seen_h.add(h)
            uniq.append(h)
    holes = uniq
    if holes:
        print(
            "DEPENDENCY_HOLE: domain-leaf/interface deps lack story owner — "
            "assign in partition/bodies before dispatch:",
            file=sys.stderr,
        )
        for h in holes:
            print(f"  - {h}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
