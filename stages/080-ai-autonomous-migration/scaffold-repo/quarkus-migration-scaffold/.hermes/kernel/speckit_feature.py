#!/usr/bin/env python3
"""Resolve Spec Kit 0.16.1 tasks.md from feature.json, not a dual glob.

Architect ``183115ZA`` / ``193642ZA``: ``.specify/feature.json``
``feature_directory`` is ``specs/…`` while M2 gates globbed
``.specify/specs/*/tasks.md``. dest-13 wrote both trees (same bytes).
Architect ``202952ZA``: any file under that copy tree is refuse even
when feature.json is present (dest-20/dest-21 split).
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


def list_specify_specs_artifacts(root: Path) -> list[Path]:
    """Files under the dest-13/dest-20/dest-21 copy tree.

    Architect ``202952ZA``: ``find_tasks`` took the ``feature.json``
    branch and never inspected this tree. dest-20/dest-21 left
    ``spec.md`` here while ``setup-plan.sh`` wrote ``plan.md`` under
    ``specs/``. Any file here is refuse, feature.json present or not.
    """
    tree = Path(root) / ".specify" / "specs"
    if not tree.is_dir():
        return []
    out: list[Path] = []
    try:
        for path in sorted(tree.rglob("*")):
            if path.is_file():
                out.append(path)
    except OSError:
        return []
    return out


def copy_tree_refuse(root: Path) -> str:
    copied = list_specify_specs_artifacts(root)
    if not copied:
        return ""
    rels = []
    for path in copied[:8]:
        try:
            rels.append(str(path.relative_to(root)))
        except ValueError:
            rels.append(str(path))
    more = "" if len(copied) <= 8 else " (+%d)" % (len(copied) - 8)
    return (
        "M2_SPECKIT_BYPASS: SPECIFY_SPECS_COPY_TREE: %s%s; "
        "Spec Kit 0.16.1 writes feature_directory from feature.json "
        "(specs/<feature>/); move those files there"
        % (", ".join(rels), more)
    )


def find_tasks(root: Path) -> tuple[list[Path], str]:
    """Return (tasks.md paths, refuse reason).

    Prefer ``.specify/feature.json`` ``feature_directory``. Else the
    Spec Kit 0.16.1 tree ``specs/*/tasks.md``. Any file under the
    copy tree is SPECIFY_SPECS_COPY_TREE (feature.json present or
    not). Two trees without feature.json is also TWO_SPECKIT_TREES.
    """
    root = Path(root)
    copied_err = copy_tree_refuse(root)
    if copied_err:
        return [], copied_err
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
