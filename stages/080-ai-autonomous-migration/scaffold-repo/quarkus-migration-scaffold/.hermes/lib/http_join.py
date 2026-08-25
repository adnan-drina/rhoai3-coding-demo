#!/usr/bin/env python3
"""HTTP join — inventory HTTP denominator + story.endpoints ∩ inventory rows.

Split from specimen_agnostic.py / check-partition-coverage.py (TR-3). Not a skill.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from inventory_io import inventory_http_expected


def endpoint_tokens(ep: str) -> set[str]:
    """Transcribed story.endpoints tokens (path-only or METHOD path). Not mint."""
    s = " ".join(str(ep).split())
    out = {s} if s else set()
    parts = s.split(" ", 1)
    if len(parts) == 2 and parts[1].strip():
        out.add(parts[1].strip())
    return out


def row_tokens(row: dict) -> set[str]:
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


def story_claims_http(story: dict, row: dict) -> bool:
    wanted: set[str] = set()
    for ep in story.get("endpoints") or []:
        wanted |= endpoint_tokens(str(ep))
    return bool(wanted & row_tokens(row))


# Architect E-20260825T202337ZA — every named HTTP path must be an inventory row.
# `/q/health` is not a grounding exception. Empty endpoints are legal scaffolding
# iff the story names no HTTP path. dest REST prefix `/api` + an inventory path
# is dest layering (constitution III), not invention.
_METHOD_PATH_RE = re.compile(
    r"\b(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(/[A-Za-z0-9_{}.\-/]*)",
    re.I,
)
_JAVA_CALL_RE = re.compile(
    r"\.(?:get|post|put|delete|patch|head)\(\s*\"(/[^\"]+)\"",
    re.I,
)
_PATH_ANN_RE = re.compile(r"@Path\(\s*\"(/[^\"]+)\"")
_FS_PREFIXES = (
    "/projects",
    "/home",
    "/usr",
    "/opt",
    "/tmp",
    "/var",
    "/etc",
    "/bin",
    "/src/",
)
_DEST_REST_PREFIX = "/api/"


def normalize_http_path(path: str) -> str:
    p = str(path or "").strip()
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p


def inventory_http_paths(inventory: dict) -> set[str]:
    out: set[str] = set()
    for row in inventory.get("entry_points") or []:
        if not isinstance(row, dict) or row.get("kind") != "http":
            continue
        hp = normalize_http_path(str(row.get("http_path") or ""))
        if hp and hp != "/":
            out.add(hp)
    return out


def _skip_named_path(path: str) -> bool:
    p = normalize_http_path(path)
    if not p.startswith("/") or p == "/":
        return True
    if any(p.startswith(pref) for pref in _FS_PREFIXES):
        return True
    if "." in p.rsplit("/", 1)[-1] and p.rsplit(".", 1)[-1].lower() in {
        "java",
        "xml",
        "json",
        "md",
        "properties",
        "yaml",
        "yml",
    }:
        return True
    return False


def extract_http_paths(text: str) -> set[str]:
    """HTTP path tokens from endpoints/AC/test sources. Not filesystem paths."""
    out: set[str] = set()
    blob = text or ""
    for m in _METHOD_PATH_RE.finditer(blob):
        out.add(normalize_http_path(m.group(2)))
    for m in _JAVA_CALL_RE.finditer(blob):
        out.add(normalize_http_path(m.group(1)))
    for m in _PATH_ANN_RE.finditer(blob):
        out.add(normalize_http_path(m.group(1)))
    return {p for p in out if not _skip_named_path(p)}


def path_is_inventory_grounded(path: str, inventory_paths: set[str]) -> bool:
    p = normalize_http_path(path)
    if p in inventory_paths:
        return True
    if p.startswith(_DEST_REST_PREFIX):
        rest = "/" + p[len(_DEST_REST_PREFIX) :]
        rest = normalize_http_path(rest)
        if rest in inventory_paths:
            return True
    return False


def _story_prose(story: dict) -> str:
    chunks: list[str] = []
    for ep in story.get("endpoints") or []:
        chunks.append(str(ep))
    ac = story.get("acceptance_criteria")
    if ac is not None:
        chunks.append(json.dumps(ac) if not isinstance(ac, str) else ac)
    ex = story.get("exit_criteria")
    if ex is not None:
        chunks.append(json.dumps(ex) if not isinstance(ex, str) else ex)
    return "\n".join(chunks)


def _writable_test_paths(story: dict) -> list[str]:
    out: list[str] = []
    for key in ("files_writable", "files", "files_in_scope"):
        val = story.get(key)
        if not isinstance(val, list):
            continue
        for item in val:
            if not isinstance(item, str):
                continue
            rel = item.replace("\\", "/").lstrip("./")
            name = rel.rsplit("/", 1)[-1]
            if "/src/test/" in f"/{rel}/" or name.endswith("Test.java"):
                out.append(rel)
    return out


def invented_route_gaps(
    root: Path, stories: list[dict], inventory: dict
) -> list[str]:
    """Refuse HTTP paths named by a story that are not inventory rows.

    Architect ``E-20260825T202337ZA``. Empty ``endpoints`` is legal iff the
    story names no HTTP path. ``/q/health`` is not a grounding exception.
    """
    inv_paths = inventory_http_paths(inventory)
    gaps: list[str] = []
    invented: list[str] = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        sid = str(story.get("story_id") or "").strip() or "?"
        named: set[str] = set()
        named |= extract_http_paths(_story_prose(story))
        for rel in _writable_test_paths(story):
            p = root / rel
            if p.is_file():
                try:
                    named |= extract_http_paths(
                        p.read_text(encoding="utf-8", errors="replace")
                    )
                except OSError:
                    continue
        for path in sorted(named):
            if not path_is_inventory_grounded(path, inv_paths):
                invented.append(f"{sid}:{path}")
    if invented:
        gaps.append(f"invented_routes={len(invented)}")
        for item in invented:
            gaps.append(f"invented_route:{item}")
    return gaps
