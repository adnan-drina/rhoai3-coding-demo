#!/usr/bin/env python3
"""Path maps — path_rewrites, intra_package_maps, dest-as-written.

Split from specimen_agnostic.py (TR-3). Not a skill.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from inventory_io import load_json, load_migration_yaml

def _pkg_to_java_prefix(pkg: str) -> str:
    p = str(pkg).strip().strip(".").replace(".", "/")
    return f"src/main/java/{p}/" if p else ""


def path_rewrites(root: Path) -> list[tuple[str, str]]:
    """Return (dest_prefix, legacy_prefix) pairs for norm_file remaps.

    Sources (first non-empty wins):
      1) migration.yaml migration.path_rewrites: [{from, to}, ...]
         where *from* is dest-tree prefix and *to* is legacy-tree prefix
      2) migration.yaml legacyPackage + targetPackage synthesis (A-6)
      3) Discover from inventory HTTP files vs bodies dual-path (best-effort)
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
        # Synthesize from package stamps when explicit rewrites absent.
        legacy_pkg = (
            mig.get("legacyBasePackage")
            or mig.get("legacy_base_package")
            or mig.get("legacyPackage")
            or ""
        )
        target_pkg = mig.get("targetPackage") or mig.get("target_package") or ""
        dest_p = _pkg_to_java_prefix(str(target_pkg))
        leg_p = _pkg_to_java_prefix(str(legacy_pkg))
        if dest_p and leg_p and dest_p != leg_p:
            return [
                (dest_p, leg_p),
                (
                    dest_p.replace("src/main/java/", "src/test/java/", 1),
                    leg_p.replace("src/main/java/", "src/test/java/", 1),
                ),
            ]

    # Discover: inventory legacy java dirs vs modernized dest dirs in bodies
    inv = None
    for cand in (
        root / "evidence/entry-point-inventory.json",
        root / ".hermes/skills/sdd/check-spec-readiness/fixtures/inventory/entry-point-inventory-petclinic-f11.json",
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
        for path in bodies.glob("*.json"):
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

    rewrites: list[tuple[str, str]] = []

    def lcp(paths: list[str]) -> str:
        if not paths:
            return ""
        s1 = min(paths)
        s2 = max(paths)
        i = 0
        while i < len(s1) and i < len(s2) and s1[i] == s2[i]:
            i += 1
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


def _slash_dir(s: str) -> str:
    p = str(s or "").replace("\\", "/").strip().strip("/")
    return f"{p}/" if p else ""


def intra_package_maps(root: Path) -> list[tuple[str, str]]:
    """Return (dest_leaf, legacy_leaf) pairs under the rewritten package root.

    Source: migration.yaml migration.intra_package_maps (alias leaf_maps):
    [{from, to}, ...] with the same from=dest / to=legacy convention as
    path_rewrites. Leaves are relative to the package prefix, not full paths.
    Empty when dest leaves already mirror legacy. Do not hardcode specimen
    leaf names in Python — stamps live in the per-run yaml.
    """
    mig = load_migration_yaml(root).get("migration") or {}
    if not isinstance(mig, dict):
        return []
    raw = mig.get("intra_package_maps") or mig.get("leaf_maps") or []
    out: list[tuple[str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            frm = _slash_dir(item.get("from") or item.get("dest") or "")
            to = _slash_dir(item.get("to") or item.get("legacy") or "")
            if frm and to and frm != to:
                out.append((frm, to))
    return out


def dest_hole_leaves(root: Path) -> tuple[str, ...]:
    """Dest directory names that count as domain-leaf DEPENDENCY_HOLE.

    Unmapped seats keep the prior unmapped convention. Mapped seats use every
    leaf named in the stamp (dest and legacy sides) so leftover either-side
    paths still hole.
    """
    pairs = intra_package_maps(root)
    if not pairs:
        return ("model",)
    names: list[str] = []
    for dest_leaf, leg_leaf in pairs:
        for raw in (dest_leaf, leg_leaf):
            n = str(raw).strip("/")
            if n and n not in names:
                names.append(n)
    return tuple(names) if names else ("model",)


def _apply_leaf_remainder(
    remainder: str, leaf_pairs: list[tuple[str, str]], *, to_dest: bool
) -> str:
    if not leaf_pairs:
        return remainder
    idx = 1 if to_dest else 0
    ordered = sorted(leaf_pairs, key=lambda pair: len(pair[idx]), reverse=True)
    for dest_leaf, leg_leaf in ordered:
        src = _slash_dir(leg_leaf if to_dest else dest_leaf)
        dst = _slash_dir(dest_leaf if to_dest else leg_leaf)
        if src and remainder.startswith(src):
            return dst + remainder[len(src) :]
    return remainder


def rewrite_across(
    rel: str,
    pairs: list[tuple[str, str]],
    *,
    to_dest: bool,
    leaf_pairs: list[tuple[str, str]] | None = None,
) -> str:
    """Map a src/... path between dest and legacy prefixes (path_rewrites).

    `pairs` is `(dest_prefix, legacy_prefix)` as returned by `path_rewrites`.
    `leaf_pairs` is `(dest_leaf, legacy_leaf)` from `intra_package_maps`,
    applied to the remainder only after a prefix pair matches.
    Do not invent a second mapper — every stamp that crosses the trees uses this.
    """
    p = (rel or "").replace("\\", "/").lstrip("./")
    leaves = leaf_pairs or []
    for dest_p, leg_p in pairs:
        if to_dest:
            if p.startswith(leg_p):
                rem = _apply_leaf_remainder(p[len(leg_p) :], leaves, to_dest=True)
                return dest_p + rem
        elif p.startswith(dest_p):
            rem = _apply_leaf_remainder(p[len(dest_p) :], leaves, to_dest=False)
            return leg_p + rem
    return p


def resolve_java_source(root: Path, dest_rel: str) -> Path | None:
    """Dest Java if present, else the legacy twin (mint has no dest sources).

    One resolver for relocate + topological order. Do not skip the gate when
    dest files are still unwritten.
    """
    rel = dest_path_as_written(dest_rel)
    if not rel.endswith(".java"):
        return None
    dest = root / rel
    if dest.is_file():
        return dest
    pairs = path_rewrites(root)
    leaves = intra_package_maps(root)
    legacy_rel = rewrite_across(rel, pairs, to_dest=False, leaf_pairs=leaves)
    bases = (
        root / "evidence" / "derived" / "legacy-at-3",
        root / ".." / ".derived" / "legacy-at-3",
        Path("/projects/.derived/legacy-at-3"),
        root.parent / ".derived" / "legacy-at-3",
    )
    for base in bases:
        for candidate in (legacy_rel, rel):
            if not candidate:
                continue
            path = base / candidate
            if path.is_file():
                return path
    return None


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
            return [_product_package_prefix(common)]
    return []


# HTTP/lifecycle scanners usually live one package below the product root
# (`…petclinic.rest`). v17 inventory fallback used raw LCP and collapsed to
# `…petclinic.rest.` — too specific for import-prefix scans, so A-6 starved
# even when inventory existed (Lead V18-2 / Deputy E-20260814T141027Z).
_LEAF_PACKAGE_SEGMENTS = frozenset(
    {
        "rest",
        "web",
        "api",
        "controller",
        "controllers",
        "config",
        "configuration",
        "service",
        "services",
        "repository",
        "repositories",
        "endpoint",
        "endpoints",
        "resource",
        "resources",
    }
)


def _product_package_prefix(segments: list[str]) -> str:
    segs = list(segments)
    while len(segs) > 1 and segs[-1].lower() in _LEAF_PACKAGE_SEGMENTS:
        segs.pop()
    return ".".join(segs) + "."



def _rel_posix(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


_DEST_AS_WRITTEN_PREFIXES = (
    "/projects/.derived/legacy-at-3/",
    "/projects/modernized/",
    "/projects/legacy/",
    "projects/.derived/legacy-at-3/",
    "projects/modernized/",
    "projects/legacy/",
)


def dest_path_as_written(path: str) -> str:
    """Dest-relative path without intra_package_maps rewrite.

    Write-set subset compares the body path as declared against the
    partition story's declared frame. Rewriting dest leaves into the
    other side of intra_package_maps would hide extras (entity vs model).
    """
    p = _rel_posix(path)
    for prefix in _DEST_AS_WRITTEN_PREFIXES:
        if p.startswith(prefix):
            p = p[len(prefix) :]
    return p.lstrip("./")

