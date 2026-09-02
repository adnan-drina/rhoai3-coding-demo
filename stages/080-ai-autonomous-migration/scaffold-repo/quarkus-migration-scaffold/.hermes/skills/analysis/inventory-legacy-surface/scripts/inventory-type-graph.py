#!/usr/bin/env python3
"""M1 type-graph inventory (no Kanban body).

Walks types reachable from each entry-point inventory row ``file`` using
the same parser as stamp-body-dependencies.py (type_graph.py). Writes
evidence/type-inventory.json. Specimen-agnostic: layer is the last
package segment, not a Dto/mapper allow-list.

Usage:
  python3 inventory-type-graph.py --dest-root /projects/modernized \\
    --inventory evidence/entry-point-inventory.json \\
    --from-manifest evidence/derived/legacy-at-3.json \\
    -o evidence/type-inventory.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


# BIND N6: import type_graph as a module. OBJECT: runtime tree walk.
# Parser lives beside this file (Architect 140351Z relocate, not thinning).

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _ensure_hermes_lib() -> None:
    p = Path(__file__).resolve()
    for parent in p.parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            s = str(lib)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")
_ensure_hermes_lib()

from generated_sources import is_generated  # noqa: E402
from specimen_agnostic import (  # noqa: E402
    intra_package_maps,
    legacy_java_prefixes,
    path_rewrites,
    rewrite_across,
)
from type_graph import (  # noqa: E402
    layer_of,
    project_type_closure,
    src_rel_from_path,
)


def _strip_abs(path: str) -> str:
    p = path.replace("\\", "/").lstrip("./")
    for prefix in (
        "/projects/.derived/legacy-at-3/",
        "/projects/modernized/",
        "/projects/legacy/",
        "projects/.derived/legacy-at-3/",
        "projects/modernized/",
        "projects/legacy/",
    ):
        if p.startswith(prefix):
            return p[len(prefix) :]
    return p


def _harvest_from_manifest(path: Path, dest_root: Path) -> Path | None:
    if not path.is_absolute():
        path = dest_root / path
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict):
        return None
    raw = str(doc.get("harvest_referent") or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = (dest_root / p).resolve()
    else:
        p = p.resolve()
    return p if p.is_dir() else None


def _legacy_root(
    dest_root: Path, explicit: str | None, from_manifest: str | None
) -> tuple[Path | None, str]:
    harvest: Path | None = None
    if from_manifest:
        harvest = _harvest_from_manifest(Path(from_manifest), dest_root)
        if harvest is None:
            return None, (
                "FAIL: --from-manifest missing harvest_referent "
                "(do not guess /projects/legacy)"
            )
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = (dest_root / p).resolve()
        else:
            p = p.resolve()
        if not p.is_dir():
            return None, "FAIL: --legacy is not a directory: %s" % p
        if harvest is not None and p != harvest:
            return None, (
                "FAIL: --legacy %s != harvest_referent %s" % (p, harvest)
            )
        return p, ""
    if harvest is not None:
        return harvest, ""
    return None, (
        "FAIL: pass --from-manifest or --legacy "
        "(do not guess /projects/legacy)"
    )


def _resolve_legacy_file(legacy_root: Path, rel: str) -> Path | None:
    rel_n = _strip_abs(rel)
    cand = legacy_root / rel_n
    if cand.is_file():
        return cand
    if rel_n.startswith("src/"):
        return None
    alt = legacy_root / "src/main/java" / rel_n
    return alt if alt.is_file() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dest-root", default=".", help="migration dest (migration.yaml)")
    ap.add_argument(
        "--inventory",
        default="evidence/entry-point-inventory.json",
    )
    ap.add_argument(
        "--legacy",
        default="",
        help="legacy@3.x tree (must match harvest_referent when --from-manifest)",
    )
    ap.add_argument(
        "--from-manifest",
        default="",
        help="evidence/derived/legacy-at-3.json — walk harvest_referent (W4)",
    )
    ap.add_argument(
        "--from-files",
        nargs="*",
        default=None,
        help="override inventory: repository-relative Java files to walk",
    )
    ap.add_argument("-o", "--output", default="evidence/type-inventory.json")
    args = ap.parse_args()
    dest_root = Path(args.dest_root).resolve()
    inv_path = Path(args.inventory)
    if not inv_path.is_absolute():
        inv_path = dest_root / inv_path
    legacy, err = _legacy_root(
        dest_root, args.legacy or None, args.from_manifest or None
    )
    if legacy is None:
        print(err, file=sys.stderr)
        return 2

    starts: list[tuple[str, Path]] = []
    if args.from_files:
        rels = [str(x) for x in args.from_files]
    else:
        if not inv_path.is_file():
            print(f"FAIL: missing inventory {inv_path}", file=sys.stderr)
            return 1
        inv = json.loads(inv_path.read_text(encoding="utf-8"))
        rels = []
        seen: set[str] = set()
        for ep in inv.get("entry_points") or []:
            if not isinstance(ep, dict):
                continue
            f = _strip_abs(str(ep.get("file") or ""))
            if not f.endswith(".java") or f in seen:
                continue
            seen.add(f)
            rels.append(f)
    for rel in rels:
        lp = _resolve_legacy_file(legacy, rel)
        if lp is None:
            continue
        starts.append((rel, lp))

    pairs = path_rewrites(dest_root)
    leaves = intra_package_maps(dest_root)
    prefixes = legacy_java_prefixes(dest_root)

    def to_dest(path: str) -> str:
        return rewrite_across(
            _strip_abs(path), pairs, to_dest=True, leaf_pairs=leaves
        )

    reached: dict[str, dict] = {}
    for src_rel, start in starts:
        for extra in project_type_closure(start, prefixes):
            leg = src_rel_from_path(extra)
            if not leg:
                continue
            dest = to_dest(leg)
            rec = reached.setdefault(
                dest,
                {
                    "legacy_file": leg,
                    "dest_file": dest,
                    "layer": layer_of(dest) or layer_of(leg),
                    "generated": is_generated(dest_root, dest, source=extra),
                    "reached_from": [],
                },
            )
            if is_generated(dest_root, dest, source=extra):
                rec["generated"] = True
            if src_rel not in rec["reached_from"]:
                rec["reached_from"].append(src_rel)

    types = [reached[k] for k in sorted(reached)]
    by_layer: dict[str, int] = {}
    for t in types:
        layer = str(t.get("layer") or "") or "_"
        by_layer[layer] = by_layer.get(layer, 0) + 1

    out = {
        "schema": "rhoai3.type-inventory/v1",
        "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "root": str(legacy),
        "execution_evidence": {
            "scanner": "inventory-type-graph.py",
            "entry_files_seen": len(starts),
            "types_seen": len(types),
            "ran": True,
            "vacuous": False if starts else "no_entry_files",
        },
        "counts": {"total": len(types), "by_layer": by_layer},
        "types": types,
    }
    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = dest_root / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(
        f"OK: {len(types)} types from {len(starts)} entry files "
        f"→ {out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
