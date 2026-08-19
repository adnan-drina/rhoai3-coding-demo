#!/usr/bin/env python3
"""M1 type-graph inventory (no Kanban body).

Walks types reachable from each entry-point inventory row ``file`` using
the same parser as stamp-body-dependencies.py (type_graph.py). Writes
evidence/type-inventory.json. Specimen-agnostic: layer is the last
package segment, not a Dto/mapper allow-list.

Usage:
  python3 inventory-type-graph.py --dest-root /projects/modernized \\
    --inventory evidence/entry-point-inventory.json \\
    --legacy /projects/.derived/legacy-at-3 \\
    -o evidence/type-inventory.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_type_graph() -> Path:
    cur = Path(__file__).resolve().parent
    for _ in range(10):
        cand = (
            cur
            / "sdd"
            / "check-spec-readiness"
            / "scripts"
            / "type_graph.py"
        )
        if cand.is_file():
            return cand.parent
        if cur.name == "skills" and (cur / "sdd/check-spec-readiness/scripts/type_graph.py").is_file():
            return cur / "sdd/check-spec-readiness/scripts"
        cur = cur.parent
    return Path("/nonexistent")


_TG = _find_type_graph()
if str(_TG) not in sys.path:
    sys.path.insert(0, str(_TG))

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


def _legacy_root(dest_root: Path, explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.is_dir() else None
    for cand in (
        dest_root.parent / ".derived" / "legacy-at-3",
        Path("/projects/.derived/legacy-at-3"),
        dest_root / ".derived" / "legacy-at-3",
        dest_root / "legacy-at-3",
    ):
        if cand.is_dir():
            return cand
    return None


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
    ap.add_argument("--legacy", default="", help="legacy@3.x tree (default: derived)")
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
    legacy = _legacy_root(dest_root, args.legacy or None)
    if legacy is None:
        print("FAIL: no legacy-at-3 tree to walk", file=sys.stderr)
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
