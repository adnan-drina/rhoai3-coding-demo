#!/usr/bin/env python3
"""Specimen-agnostic helpers for migration gates (Operator E-20260811T150800Z).

Falsifier: coolstore must work unchanged. Specimen literals belong in
fixtures / per-run migration.yaml stamps — never in gate logic constants.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

def _parse_migration_yaml_lite(text: str) -> dict:
    """Minimal migration.yaml reader (no PyYAML dep). Supports legacyBasePackage
    and path_rewrites list used by portability stamps."""
    out: dict = {"migration": {}}
    mig = out["migration"]
    lines = text.splitlines()
    i = 0
    in_migration = False
    in_rewrites = False
    current: dict | None = None
    while i < len(lines):
        ln = lines[i]
        raw = ln.rstrip()
        if not raw.strip() or raw.strip().startswith("#"):
            i += 1
            continue
        if raw == "migration:":
            in_migration = True
            in_rewrites = False
            i += 1
            continue
        if in_migration and raw and not raw.startswith(" ") and not raw.startswith("	"):
            # left migration section
            in_migration = False
            in_rewrites = False
            continue
        if not in_migration:
            i += 1
            continue
        s = raw.strip()
        if s.startswith("legacyBasePackage:"):
            mig["legacyBasePackage"] = s.split(":", 1)[1].strip().strip('"').strip("'")
            in_rewrites = False
        elif s.startswith("legacy_base_package:"):
            mig["legacy_base_package"] = s.split(":", 1)[1].strip().strip('"').strip("'")
            in_rewrites = False
        elif s.startswith("legacyPackage:"):
            # RHDH app-migration skeleton stamp key (alias of legacyBasePackage)
            mig["legacyPackage"] = s.split(":", 1)[1].strip().strip('"').strip("'")
            in_rewrites = False
        elif s.startswith("path_rewrites:") or s.startswith("packageRemap:"):
            key = "path_rewrites" if s.startswith("path_rewrites") else "packageRemap"
            mig[key] = []
            in_rewrites = True
            current = None
        elif in_rewrites and s.startswith("- "):
            current = {}
            mig.setdefault("path_rewrites", mig.get("packageRemap") or [])
            # normalize to path_rewrites
            if "path_rewrites" not in mig:
                mig["path_rewrites"] = []
            if "packageRemap" in mig and mig["packageRemap"] is not mig.get("path_rewrites"):
                mig["path_rewrites"] = mig["packageRemap"]
            mig["path_rewrites"].append(current)
            rest = s[2:].strip()
            if rest and ":" in rest:
                k, v = rest.split(":", 1)
                current[k.strip()] = v.strip().strip('"').strip("'")
        elif in_rewrites and current is not None and ":" in s and s[0] not in "-":
            k, v = s.split(":", 1)
            current[k.strip()] = v.strip().strip('"').strip("'")
        else:
            in_rewrites = False
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


def path_rewrites(root: Path) -> list[tuple[str, str]]:
    """Return (dest_prefix, legacy_prefix) pairs for norm_file remaps.

    Sources (first non-empty wins):
      1) migration.yaml migration.path_rewrites: [{from, to}, ...]
         where *from* is dest-tree prefix and *to* is legacy-tree prefix
      2) Discover from inventory HTTP files vs bodies dual-path (best-effort)
    """
    mig = load_migration_yaml(root).get("migration") or {}
    if isinstance(mig, dict):
        raw = mig.get("path_rewrites") or mig.get("packageRemap") or []
        out: list[tuple[str, str]] = []
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                frm = str(item.get("from") or item.get("dest") or "").replace("\\", "/")
                to = str(item.get("to") or item.get("legacy") or "").replace("\\", "/")
                if frm and to:
                    out.append((frm.rstrip("/") + "/", to.rstrip("/") + "/"))
        if out:
            return out

    # Discover: inventory legacy java dirs vs modernized dest dirs in bodies
    inv = None
    for cand in (
        root / "evidence/entry-point-inventory.json",
        root / "governance/fixtures/inventory/entry-point-inventory-petclinic-f11.json",
    ):
        inv = load_json(cand)
        if isinstance(inv, dict):
            break
    legacy_pkgs: set[str] = set()
    if isinstance(inv, dict):
        for ep in inv.get("entry_points") or []:
            if not isinstance(ep, dict):
                continue
            f = str(ep.get("file") or "").replace("\\", "/")
            m = re.match(r"(src/(?:main|test)/java/.+)/[^/]+\.java$", f)
            if m:
                # package directory (drop class file); keep up to parent of class
                legacy_pkgs.add(m.group(1).rsplit("/", 1)[0] + "/")

    dest_pkgs: set[str] = set()
    bodies = root / "evidence/bodies"
    if bodies.is_dir():
        for path in bodies.glob("m3-*.json"):
            if path.name.endswith(".sha256.json"):
                continue
            data = load_json(path)
            if not isinstance(data, dict):
                continue
            for item in data.get("files_writable") or []:
                if not isinstance(item, str):
                    continue
                p = item.replace("\\", "/")
                if "/modernized/" in p:
                    p = p.split("/modernized/", 1)[1]
                m = re.match(r"(src/(?:main|test)/java/.+)/[^/]+\.java$", p)
                if m:
                    dest_pkgs.add(m.group(1).rsplit("/", 1)[0] + "/")

    # Pair by java/(main|test) + depth-1 package root swap when unique
    rewrites: list[tuple[str, str]] = []
    # Prefer remapping dest base → legacy base when both have single java root
    def java_roots(pkgs: set[str]) -> set[str]:
        roots: set[str] = set()
        for p in pkgs:
            m = re.match(r"(src/(?:main|test)/java/[^/]+(?:/[^/]+){0,3})/", p)
            if m:
                # take up to 3 segments after java/ as base package guess
                parts = m.group(1).split("/")
                # src/main/java/a/b/c → keep a/b/c if present
                if len(parts) >= 4:
                    roots.add("/".join(parts[: min(7, len(parts))]) + "/")
        return roots

    # Simpler: if exactly one dest root under com/ and one legacy under org/, pair them
    dest_bases = sorted(
        {re.sub(r"(src/(?:main|test)/java/)(.+?)/$", r"\1\2/", p) for p in dest_pkgs}
    )
    leg_bases = sorted(legacy_pkgs)
    # Collapse to package-root (strip trailing entity folder noise) — use
    # longest common prefix within each set
    def lcp(paths: list[str]) -> str:
        if not paths:
            return ""
        s1 = min(paths)
        s2 = max(paths)
        i = 0
        while i < len(s1) and i < len(s2) and s1[i] == s2[i]:
            i += 1
        # trim to last /
        pref = s1[:i]
        if "/" in pref:
            pref = pref[: pref.rfind("/") + 1]
        return pref

    droot = lcp(sorted(dest_pkgs))
    lroot = lcp(sorted(legacy_pkgs))
    if (
        droot.startswith("src/main/java/")
        and lroot.startswith("src/main/java/")
        and droot != lroot
    ):
        rewrites.append((droot, lroot))
        rewrites.append(
            (
                droot.replace("src/main/java/", "src/test/java/", 1),
                lroot.replace("src/main/java/", "src/test/java/", 1),
            )
        )
    return rewrites


def legacy_java_prefixes(
    root: Path, *, allow_specimen_fixture: bool = False
) -> list[str]:
    """Import prefixes like 'com.example.app.' for deps stamp.

    Order: migration.yaml stamp → live evidence inventory → (opt-in) fixture.
    Never silently fall back to a demo fixture on the golden tip
    (Deputy E-20260813T184217Z).
    """
    mig = load_migration_yaml(root).get("migration") or {}
    if isinstance(mig, dict):
        base = (
            mig.get("legacyBasePackage")
            or mig.get("legacy_base_package")
            or mig.get("legacyPackage")
        )
        if base:
            b = str(base).strip().rstrip(".") + "."
            return [b]
    # Derive from inventory file paths (live evidence only by default)
    cands = [root / "evidence/entry-point-inventory.json"]
    if allow_specimen_fixture:
        cands.append(
            root
            / "governance/fixtures/inventory/entry-point-inventory-petclinic-f11.json"
        )
    for cand in cands:
        inv = load_json(cand)
        if not isinstance(inv, dict):
            continue
        pkgs: list[str] = []
        for ep in inv.get("entry_points") or []:
            if not isinstance(ep, dict):
                continue
            f = str(ep.get("file") or "").replace("\\", "/")
            m = re.match(r"src/(?:main|test)/java/(.+)/[^/]+\.java$", f)
            if m:
                pkgs.append(m.group(1).replace("/", "."))
        if not pkgs:
            continue
        # longest common package prefix
        parts = [p.split(".") for p in pkgs]
        common: list[str] = []
        for segs in zip(*parts):
            if len(set(segs)) == 1:
                common.append(segs[0])
            else:
                break
        if common:
            return [".".join(common) + "."]
    return []


def resolve_inventory_path(root: Path, explicit: str = "", *, allow_specimen_fixture: bool = False) -> Path | None:
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = root / p
        return p if p.is_file() else None
    primary = root / "evidence/entry-point-inventory.json"
    if primary.is_file():
        return primary
    if allow_specimen_fixture:
        fixture = root / "governance/fixtures/inventory/entry-point-inventory-petclinic-f11.json"
        if fixture.is_file():
            return fixture
    return None


def inventory_http_expected(inventory: dict) -> int:
    """Denominator = runtime inventory HTTP count (never a specimen constant)."""
    eps = inventory.get("entry_points") or []
    if not isinstance(eps, list):
        return 0
    return sum(1 for e in eps if isinstance(e, dict) and e.get("kind") == "http")
