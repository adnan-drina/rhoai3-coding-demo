#!/usr/bin/env python3
"""Inventory I/O — load JSON/YAML stamps and resolve inventory paths.

Split from specimen_agnostic.py (TR-3). Not a skill.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

def _parse_migration_yaml_lite(text: str) -> dict:
    """Minimal migration.yaml reader (no PyYAML dep). Supports legacyBasePackage,
    path_rewrites, and intra_package_maps lists used by portability stamps."""
    out: dict = {"migration": {}}
    mig = out["migration"]
    lines = text.splitlines()
    i = 0
    in_migration = False
    in_list: str | None = None
    current: dict | None = None

    def _scalar(key: str, s: str) -> None:
        nonlocal in_list, current
        mig[key] = s.split(":", 1)[1].strip().strip('"').strip("'")
        in_list = None
        current = None

    def _start_list(canonical: str, also: str | None = None) -> None:
        nonlocal in_list, current
        mig[canonical] = []
        if also:
            mig[also] = mig[canonical]
        in_list = canonical
        current = None

    while i < len(lines):
        ln = lines[i]
        raw = ln.rstrip()
        # A-6: stamp corruption glues `migration:` onto the preceding comment
        # ("...wrong.migration:"). Treat that as section open even inside #.
        if raw.strip().startswith("#") and raw.rstrip().endswith("migration:"):
            in_migration = True
            in_list = None
            i += 1
            continue
        if not raw.strip() or raw.strip().startswith("#"):
            i += 1
            continue
        # Tolerate non-comment glued forms too.
        if raw == "migration:" or raw.rstrip().endswith("migration:"):
            in_migration = True
            in_list = None
            i += 1
            continue
        if in_migration and raw and not raw.startswith(" ") and not raw.startswith("\t"):
            # left migration section
            in_migration = False
            in_list = None
            continue
        if not in_migration:
            i += 1
            continue
        s = raw.strip()
        if s.startswith("legacyRepoUrl:"):
            _scalar("legacyRepoUrl", s)
        elif s.startswith("legacyBasePackage:"):
            _scalar("legacyBasePackage", s)
        elif s.startswith("legacy_base_package:"):
            _scalar("legacy_base_package", s)
        elif s.startswith("legacyPackage:"):
            # RHDH app-migration skeleton stamp key (alias of legacyBasePackage)
            _scalar("legacyPackage", s)
        elif s.startswith("targetPackage:") or s.startswith("target_package:"):
            _scalar("targetPackage", s)
        elif s.startswith("path_rewrites:"):
            _start_list("path_rewrites")
        elif s.startswith("packageRemap:"):
            _start_list("path_rewrites", also="packageRemap")
        elif s.startswith("intra_package_maps:") or s.startswith("leaf_maps:"):
            _start_list("intra_package_maps")
        elif in_list and s.startswith("- "):
            current = {}
            mig.setdefault(in_list, [])
            mig[in_list].append(current)
            rest = s[2:].strip()
            if rest and ":" in rest:
                k, v = rest.split(":", 1)
                current[k.strip()] = v.strip().strip('"').strip("'")
        elif in_list and current is not None and ":" in s and s[0] not in "-":
            k, v = s.split(":", 1)
            current[k.strip()] = v.strip().strip('"').strip("'")
        else:
            in_list = None
        i += 1
    return out


def load_json(path: Path) -> dict | list | None:
    if not path.is_file():
        return None
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_migration_yaml(root: Path) -> dict[str, Any]:
    path = root / "migration.yaml"
    if not path.is_file():
        return {}
    try:
        return _parse_migration_yaml_lite(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# Producer (dest M2) writes evidence/partition.json; fixtures and older
# harvests use evidence/briefs/partition.json. Prefer the producer.
PARTITION_REL_CANDIDATES = (
    "evidence/partition.json",
    "evidence/briefs/partition.json",
)


def resolve_partition_path(
    root: Path, explicit: str = ""
) -> tuple[Path | None, list[str]]:
    """Locate the typed partition. Refusal names every path looked at.

    dest-5 / dest-4 wrote evidence/partition.json while the coverage default
    was evidence/briefs/partition.json (Lead:partition-coverage-default-path-disagrees-with-producer).
    """
    looked: list[str] = []

    def _note(p: Path) -> str:
        try:
            return str(p.relative_to(root)).replace("\\", "/")
        except ValueError:
            return str(p)

    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = root / p
        looked.append(_note(p))
        return (p if p.is_file() else None), looked
    for rel in PARTITION_REL_CANDIDATES:
        p = root / rel
        looked.append(rel)
        if p.is_file():
            return p, looked
    return None, looked


def resolve_inventory_path(root: Path, explicit: str = "", *, allow_specimen_fixture: bool = False) -> Path | None:
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = root / p
        return p if p.is_file() else None
    primary = root / "evidence/entry-point-inventory.json"
    if primary.is_file():
        return primary
    return None


def inventory_http_expected(inventory: dict) -> int:
    """Denominator = runtime inventory HTTP count (never a specimen constant)."""
    eps = inventory.get("entry_points") or []
    if not isinstance(eps, list):
        return 0
    return sum(1 for e in eps if isinstance(e, dict) and e.get("kind") == "http")

