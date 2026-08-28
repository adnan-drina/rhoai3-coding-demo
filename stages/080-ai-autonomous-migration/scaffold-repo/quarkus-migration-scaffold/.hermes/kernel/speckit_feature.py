#!/usr/bin/env python3
"""Resolve Spec Kit 0.16.1 tasks.md from feature.json, not a dual glob.

Architect ``183115ZA`` / ``193642ZA``: ``.specify/feature.json``
``feature_directory`` is ``specs/…`` while M2 gates globbed
``.specify/specs/*/tasks.md``. dest-13 wrote both trees (same bytes).
Do not copy ``tasks.md`` onto ``.specify/specs``. Do not glob both.
"""
from __future__ import annotations

import json
from pathlib import Path


def read_feature_directory(root: Path) -> str | None:
    fj = root / ".specify" / "feature.json"
    if not fj.is_file():
        return None
    try:
        data = json.loads(fj.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    rel = data.get("feature_directory")
    if isinstance(rel, str) and rel.strip():
        return rel.strip().replace("\\", "/")
    return None


def _nonempty_tasks(feature_dir: Path) -> Path | None:
    path = feature_dir / "tasks.md"
    try:
        if path.is_file() and path.read_text(encoding="utf-8").strip():
            return path
    except OSError:
        return None
    return None


def glob_nonempty_tasks(specs_root: Path) -> list[Path]:
    if not specs_root.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(specs_root.glob("*/tasks.md")):
        try:
            if path.is_file() and path.read_text(encoding="utf-8").strip():
                out.append(path)
        except OSError:
            continue
    return out


def find_tasks(root: Path) -> tuple[list[Path], str]:
    """Return (tasks.md paths, refuse reason).

    Prefer ``.specify/feature.json`` ``feature_directory``. Else the
    Spec Kit 0.16.1 tree ``specs/*/tasks.md``. Never glob
    ``.specify/specs`` as the M2 authority — that is the dest-13 copy.
    Two trees without feature.json is TWO_SPECKIT_TREES.
    """
    root = Path(root)
    rel = read_feature_directory(root)
    if rel:
        feat = root / rel
        try:
            feat.resolve().relative_to(root.resolve())
        except ValueError:
            return [], (
                "M2_SPECKIT_BYPASS: .specify/feature.json feature_directory "
                "escapes the project (%s)" % rel
            )
        found = _nonempty_tasks(feat)
        if found:
            return [found], ""
        return [], (
            "M2_SPECKIT_BYPASS: missing non-empty %s/tasks.md "
            "(feature.json feature_directory; Spec Kit 0.16.1; "
            "do not copy onto .specify/specs)"
            % rel
        )

    root_specs = glob_nonempty_tasks(root / "specs")
    specify_specs = glob_nonempty_tasks(root / ".specify" / "specs")
    if root_specs and specify_specs:
        return [], (
            "M2_SPECKIT_BYPASS: TWO_SPECKIT_TREES: specs/*/tasks.md and "
            ".specify/specs/*/tasks.md both exist; pick Spec Kit 0.16.1 via "
            ".specify/feature.json feature_directory; do not copy tasks.md "
            "onto .specify/specs"
        )
    if root_specs:
        return root_specs, ""
    return [], (
        "M2_SPECKIT_BYPASS: missing non-empty specs/*/tasks.md "
        "(Spec Kit 0.16.1 writes specs/<feature>/; persist "
        ".specify/feature.json; do not author .specify/specs as the plan tree)"
    )
