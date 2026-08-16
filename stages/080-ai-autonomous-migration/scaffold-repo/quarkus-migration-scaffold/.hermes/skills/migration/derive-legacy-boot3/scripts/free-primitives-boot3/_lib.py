"""Shared helpers for free-primitives Boot 2→3 composite rules."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Iterable

COMPOSITE_VERSION = "1.2.1"
SKIP_DIRS = {".git", "target", ".idea", ".derived", "node_modules"}
DERIVED_MARKER = ".rhoai3-derived-tree"


def _is_derived_tree(root: Path) -> bool:
    """Write-beside only for a positively derived tree (FP-1).

    APPLY_LOG_PATH (caller) still wins. Otherwise: marker file, or a
    `.derived` path segment. Not-golden is not enough (Deputy
    E-20260816T160604Z).
    """
    if (root / DERIVED_MARKER).is_file():
        return True
    return any(part == ".derived" for part in root.parts)


def repo_root() -> Path:
    return Path(os.environ.get("COMPOSITE_ROOT", ".")).resolve()


def apply_log_path() -> Path:
    p = os.environ.get("APPLY_LOG_PATH", "").strip()
    if p:
        return Path(p).expanduser().resolve()
    root = repo_root()
    if _is_derived_tree(root):
        return root / ".rhoai3-free-primitives-apply-log.json"
    return Path(tempfile.gettempdir()) / "rhoai3-free-primitives-apply-log.json"


def has_candidate_sources(root: Path | None = None) -> bool:
    root = root or repo_root()
    if (root / "pom.xml").is_file():
        return True
    return bool(iter_files(root, (".java",)))


def iter_files(root: Path, suffixes: Iterable[str]) -> list[Path]:
    out: list[Path] = []
    suffixes = tuple(suffixes)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(suffixes):
                out.append(Path(dirpath) / name)
    return sorted(out)


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def tree_digest(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        if p.is_file():
            h.update(str(p).encode())
            h.update(file_digest(p).encode())
    return h.hexdigest()


def record_rule(
    *,
    rule_id: str,
    cite: str,
    files: list[str],
    pre_digest: str,
    post_digest: str,
    skipped: bool = False,
    notes: str = "",
) -> None:
    path = apply_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema": "free-primitives-apply-log/v1",
        "composite_version": COMPOSITE_VERSION,
        "rules": [],
    }
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8"))
    doc.setdefault("rules", []).append(
        {
            "rule_id": rule_id,
            "cite": cite,
            "files": files,
            "pre_digest": pre_digest,
            "post_digest": post_digest,
            "skipped": skipped,
            "notes": notes,
        }
    )
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def rewrite_text_file(path: Path, old: str, new: str) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    if old not in text:
        return False
    path.write_text(text.replace(old, new), encoding="utf-8")
    return True
