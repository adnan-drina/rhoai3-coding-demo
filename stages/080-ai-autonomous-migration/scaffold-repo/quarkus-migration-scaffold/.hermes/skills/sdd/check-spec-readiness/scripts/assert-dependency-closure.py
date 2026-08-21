#!/usr/bin/env python3
"""Dependency / pre-exists / generated / import-closure gate (Class A).

Architect E-20260811T203657Z — elevate BANK-DEP-CLOSURE-1:
create-m3 / partition path fail-closed when:
  1) dependencies[] declare provider=pre-exists but the dest file is DEST_MISS
  2) (optional --imports) Java imports under files_writable reference types
     with no owner in this body's writable/scope/deps and no dest file
  3) provider=generated skips DEST_MISS (build output need not exist yet)
     but the plan must own generator inputs (spec + build config)

Sibling to interface-closure (implements-only).

Usage:
  python3 assert-dependency-closure.py . --body evidence/bodies/m3-s-003.json
  python3 assert-dependency-closure.py . --body evidence/bodies/m3-s-003.json --imports
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

from generated_sources import (  # noqa: E402
    generator_input_paths,
    generator_plugins,
    inventory_row_is_generated,
    is_generated,
)
from specimen_agnostic import dest_path_as_written, legacy_java_prefixes  # noqa: E402

IMPORT_RE = re.compile(r"^\s*import\s+([\w.]+)\s*;", re.M)
PKG_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.M)


def load_body(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw.get("body"), dict):
        return raw["body"]
    return raw


def norm_rel(path: str, root: Path) -> Path:
    p = path.replace("\\", "/")
    for prefix in (
        str(root) + "/",
        "/projects/modernized/",
        "projects/modernized/",
    ):
        if p.startswith(prefix):
            p = p[len(prefix) :]
            break
    return Path(p)


def resolve_dest(root: Path, rel: str) -> Path:
    n = norm_rel(rel, root)
    cand = root / n
    if cand.is_file():
        return cand
    # dependencies often omit leading src/
    if not str(n).startswith("src/"):
        alt = root / "src/main/java" / n
        if alt.is_file():
            return alt
    return cand


def check_pre_exists(root: Path, body: dict) -> list[str]:
    bad: list[str] = []
    for dep in body.get("dependencies") or []:
        if not isinstance(dep, dict):
            continue
        provider = str(dep.get("provider") or "").strip().lower()
        if provider in {"generated"}:
            continue
        if provider not in {"pre-exists", "preexists", "pre_exists"}:
            continue
        f = dep.get("file") or dep.get("path")
        if not f:
            bad.append("dependency missing file/path with provider=pre-exists")
            continue
        dest = resolve_dest(root, str(f))
        if not dest.is_file():
            bad.append(f"pre-exists DEST_MISS: {f} (resolved {dest})")
    return bad


def _field_paths(raw: object) -> list[str]:
    out: list[str] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            for k in ("dest", "dst", "path", "file", "src"):
                if item.get(k):
                    out.append(str(item[k]).strip())
                    break
    return out


def plan_owned_files(root: Path) -> set[str]:
    """Union of partition + body write-sets (generator inputs may sit on setup)."""
    owned: set[str] = set()
    part = root / "evidence" / "briefs" / "partition.json"
    if part.is_file():
        try:
            data = json.loads(part.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        for story in data.get("stories") or []:
            if not isinstance(story, dict):
                continue
            for key in ("files_writable", "files", "files_in_scope"):
                for p in _field_paths(story.get(key)):
                    owned.add(dest_path_as_written(p))
    bodies = root / "evidence" / "bodies"
    if bodies.is_dir():
        for path in bodies.glob("*.json"):
            if path.name.endswith(".sha256.json"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data.get("body"), dict):
                data = data["body"]
            if not isinstance(data, dict):
                continue
            for key in ("files_writable", "files_in_scope"):
                for p in _field_paths(data.get(key)):
                    owned.add(dest_path_as_written(p))
    return owned


def type_inventory_generated_count(root: Path) -> int | None:
    path = root / "evidence" / "type-inventory.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    types = data.get("types") if isinstance(data, dict) else None
    if not isinstance(types, list):
        return None
    n = 0
    for row in types:
        if isinstance(row, dict) and inventory_row_is_generated(root, row):
            n += 1
    return n


def _generator_surface(root: Path, dest_only: bool) -> str:
    recs = generator_plugins(root, dest_only=dest_only)
    gen_n = type_inventory_generated_count(root)
    gen_s = "absent" if gen_n is None else str(gen_n)
    if not recs:
        return (
            f"surface=dest build files (no generator plugin); "
            f"type-inventory generated:true count={gen_s}"
        )
    bits = []
    for rec in recs:
        bits.append(
            f"build_file={rec.get('build_file')} "
            f"artifactId={rec.get('artifactId')} "
            f"inputSpec={','.join(rec.get('input_specs') or []) or '(none)'}"
        )
    return (
        "; ".join(bits)
        + f"; type-inventory generated:true count={gen_s}"
    )


def check_generated_inputs(root: Path, body: dict) -> list[str]:
    """If this body depends on generated types, the plan must own spec + build."""
    has_generated = False
    for dep in body.get("dependencies") or []:
        if not isinstance(dep, dict):
            continue
        if str(dep.get("provider") or "").strip().lower() == "generated":
            has_generated = True
            break
        f = dep.get("file") or dep.get("path")
        if f and is_generated(root, str(f)):
            has_generated = True
            break
    gen_n = type_inventory_generated_count(root)
    dest_plugins = generator_plugins(root, dest_only=True)
    # H-1: handwritten type-inventory + no dest plugin → do not inherit
    # legacy-at-3 openapi inputSpec (v40 api-docs.yml false demand).
    if gen_n == 0 and not dest_plugins:
        return []
    if not has_generated:
        return []
    dest_only = True
    if gen_n and gen_n > 0 and not dest_plugins:
        dest_only = False
    wanted = generator_input_paths(root, dest_only=dest_only)
    surface = _generator_surface(root, dest_only)
    owned = plan_owned_files(root)
    # This body also counts.
    for key in ("files_writable", "files_in_scope"):
        for p in _field_paths(body.get(key)):
            owned.add(dest_path_as_written(p))
    bad: list[str] = []
    for spec in wanted.get("specs") or []:
        s = dest_path_as_written(spec)
        if s not in owned and Path(s).name not in {Path(x).name for x in owned}:
            bad.append(
                f"GENERATOR_INPUTS: spec not owned: {s} ({surface})"
            )
    build_ok = False
    for b in wanted.get("builds") or ["pom.xml"]:
        bn = dest_path_as_written(b)
        pom_owned = any(
            dest_path_as_written(x).endswith("pom.xml") for x in owned
        )
        if bn in owned or (bn.endswith("pom.xml") and pom_owned):
            build_ok = True
            break
    if not build_ok:
        bad.append(
            "GENERATOR_INPUTS: dest build file not owned ("
            + ",".join(wanted.get("builds") or ["pom.xml"])
            + f") ({surface})"
        )
    if dest_plugins and not (wanted.get("specs") or []):
        bad.append(
            "GENERATOR_INPUTS: generator plugin declared but no spec path "
            f"parsed from the dest build file (inputSpec / equivalent) ({surface})"
        )
    return bad


def java_type_to_path(fqcn: str, prefixes: list[str]) -> Path | None:
    """Map a legacy FQCN to its source path, for any specimen.

    R-SK.5: the legacy base package is derived from migration.yaml / the
    entry-point inventory via legacy_java_prefixes(). Hardcoding one
    specimen's package made this gate a silent no-op on every other
    codebase — it recognised no types, so it found no violations.
    """
    if not any(fqcn.startswith(p) for p in prefixes):
        return None
    return Path("src/main/java") / Path(*fqcn.split(".")).with_suffix(".java")


def owned_basenames(body: dict, root: Path) -> set[str]:
    names: set[str] = set()
    for key in ("files_writable", "files_in_scope"):
        for item in body.get(key) or []:
            s = item if isinstance(item, str) else str((item or {}).get("path") or "")
            if s:
                names.add(Path(s).name)
    for dep in body.get("dependencies") or []:
        if isinstance(dep, dict) and dep.get("file"):
            names.add(Path(str(dep["file"])).name)
    return names


def check_imports(root: Path, body: dict) -> list[str]:
    """Fail when writable Java imports legacy types not owned and DEST_MISS."""
    prefixes = legacy_java_prefixes(root)
    bad: list[str] = []
    owned = owned_basenames(body, root)
    for item in body.get("files_writable") or []:
        s = item if isinstance(item, str) else str((item or {}).get("path") or "")
        if not s.endswith(".java"):
            continue
        path = resolve_dest(root, s)
        if not path.is_file():
            # not yet created — skip import scan for missing writable (create story)
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in IMPORT_RE.finditer(text):
            fqcn = m.group(1)
            rel = java_type_to_path(fqcn, prefixes)
            if rel is None:
                continue
            base = rel.name
            dest = root / rel
            if dest.is_file():
                continue
            if base in owned:
                continue
            bad.append(
                f"import-closure: {path.name} imports {fqcn} but DEST_MISS and "
                f"no owner in writable/scope/deps"
            )
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--body", required=True)
    ap.add_argument(
        "--imports",
        action="store_true",
        help="Also fail on unowned DEST_MISS imports from existing writable Java",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    body_path = Path(args.body)
    if not body_path.is_file():
        body_path = root / args.body
    if not body_path.is_file():
        print(f"FAIL: body missing {args.body}", file=sys.stderr)
        return 1
    body = load_body(body_path)
    bad = check_pre_exists(root, body)
    bad.extend(check_generated_inputs(root, body))
    if args.imports:
        bad.extend(check_imports(root, body))
    if bad:
        print("FAIL: DEPENDENCY_CLOSURE", file=sys.stderr)
        for line in bad:
            print(f"  - {line}", file=sys.stderr)
        print(
            "Architect E-20260811T203657Z / .hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
            file=sys.stderr,
        )
        return 1
    print(f"OK: dependency-closure ({body_path.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
