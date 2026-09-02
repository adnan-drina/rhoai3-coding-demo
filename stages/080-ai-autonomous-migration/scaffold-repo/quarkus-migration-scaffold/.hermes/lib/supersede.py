#!/usr/bin/env python3
"""1:N dest_file supersede — named successor sets and coverage gaps.

Split from specimen_agnostic.py (TR-3). Not a skill.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from path_maps import dest_path_as_written

def _inventory_row_is_generated(root: Path, rec: dict) -> bool:
    scripts = Path(__file__).resolve().parent
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from generated_sources import inventory_row_is_generated  # noqa: PLC0415

    return inventory_row_is_generated(root, rec)


def collect_supersedes(partition: dict, stories: list[dict] | None = None) -> dict[str, list[str]]:
    """dest_file → successor dest paths from the typed partition.

    A row is a legal 1:N supersede only when ``successors`` is a named
    non-empty list. A string-only ``supersedes`` entry is recorded with an
    empty successor set (incomplete — not coverage).
    """
    out: dict[str, list[str]] = {}

    def _ingest(obj: object) -> None:
        if not isinstance(obj, dict):
            return
        raw = obj.get("supersedes")
        if not isinstance(raw, list):
            return
        for item in raw:
            dest = ""
            succ: list[str] = []
            if isinstance(item, str) and item.strip():
                dest = dest_path_as_written(item)
            elif isinstance(item, dict):
                dest = dest_path_as_written(
                    str(
                        item.get("dest_file")
                        or item.get("legacy_file")
                        or item.get("file")
                        or ""
                    )
                )
                raw_s = item.get("successors")
                if raw_s is None:
                    raw_s = item.get("successor")
                if isinstance(raw_s, str):
                    raw_s = [raw_s]
                if isinstance(raw_s, list):
                    succ = [dest_path_as_written(str(s)) for s in raw_s if s]
            if dest:
                out[dest] = [s for s in succ if s]

    _ingest(partition)
    for st in stories or []:
        _ingest(st)
    return out


def type_inventory_supersede_gaps(
    owned: set[str], supersedes: dict[str, list[str]]
) -> list[str]:
    """All incomplete successor sets (report the full gap, not the first)."""
    owned_n = {dest_path_as_written(x) for x in owned if x}
    gaps: list[str] = []
    for dest in sorted(supersedes):
        succ = [s for s in supersedes[dest] if s]
        if not succ:
            gaps.append(f"supersede_incomplete:{dest}:empty_successors")
            continue
        missing = [s for s in succ if s not in owned_n]
        if missing:
            gaps.append(f"supersede_incomplete:{dest}:{len(missing)}")
            for m in missing:
                gaps.append(f"supersede_missing:{dest}:{m}")
    return gaps


def type_inventory_uncovered(
    root: Path,
    owned: set[str],
    supersedes: dict[str, list[str]] | None = None,
) -> list[str] | None:
    """Dest twins in evidence/type-inventory.json missing from ``owned``.

    ``None`` means the file is absent — skip (I-16 / dests whose M1 predated
    the walk). Empty list means present and covered. Rows that
    ``generated_sources.inventory_row_is_generated`` classifies as generator
    output are skipped — do not trust a stored ``generated`` boolean (v41).

    1:N supersede (rewrite plan §4): a non-generated dest_file may be declared
    superseded by a named non-empty successor set. That row is covered iff
    every successor is owned; the superseded path is not required in any
    write-set. Incomplete successor sets are reported by
    ``type_inventory_supersede_gaps``, not this function.
    """
    path = root / "evidence" / "type-inventory.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    owned_n = {dest_path_as_written(x) for x in owned if x}
    super_n = supersedes or {}
    missing: list[str] = []
    seen: set[str] = set()
    for rec in data.get("types") or []:
        if not isinstance(rec, dict):
            continue
        dest = dest_path_as_written(str(rec.get("dest_file") or ""))
        if not dest or dest in seen:
            continue
        seen.add(dest)
        if _inventory_row_is_generated(root, rec):
            continue
        succ = [s for s in super_n.get(dest, []) if s]
        if succ and all(s in owned_n for s in succ):
            continue
        if dest not in owned_n:
            missing.append(dest)
    return missing


def _write_is_setup_or_test(path: str) -> bool:
    p = dest_path_as_written(path)
    if p == "pom.xml" or p.startswith("src/main/resources/"):
        return True
    if p.startswith("src/test/"):
        return True
    return False


def type_inventory_invented_writes(
    root: Path,
    owned: set[str],
    supersedes: dict[str, list[str]] | None = None,
) -> list[str] | None:
    """Product ``src/main/java`` write-set paths with no type-inventory dest_file.

    Twin of ``type_inventory_uncovered`` (Operator ``3e3409d0``): coverage
    requires dest twins in the write-set; this refuses write-set Java that
    the inventory did not name. Do **not** join inventory ``file`` to dest
    paths (A-8 RestController→Resource mapper OBJECT). ``None`` means the
    type-inventory file is absent — skip. Empty list means no invented dest
    Java. pom.xml, ``src/main/resources/``, and ``src/test/`` are not dest
    twins. Successors of a named supersede set are grounded.
    """
    path = root / "evidence" / "type-inventory.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    grounded: set[str] = set()
    for rec in data.get("types") or []:
        if not isinstance(rec, dict):
            continue
        dest = dest_path_as_written(str(rec.get("dest_file") or ""))
        if dest:
            grounded.add(dest)
    super_n = supersedes or {}
    for dest, succ in super_n.items():
        if dest in grounded:
            grounded.update(s for s in succ if s)
    invented: list[str] = []
    seen: set[str] = set()
    for raw in owned:
        p = dest_path_as_written(raw)
        if not p or p in seen:
            continue
        seen.add(p)
        if _write_is_setup_or_test(p):
            continue
        if not p.startswith("src/main/java/") or not p.endswith(".java"):
            continue
        if p in grounded:
            continue
        invented.append(p)
    return invented
