#!/usr/bin/env python3
"""AD-H §19.2 — resolve the SOUL.md Hermes actually loads (loaded-path rule).

Order (first existing readable file wins):
  1. $HERMES_HOME/SOUL.md
  2. ~/.hermes/SOUL.md
  3. <repo>/.hermes/home/SOUL.md  (relocated home common in Dev Spaces)
  4. <repo>/.hermes/SOUL.md       ONLY if none of the above exist

Hashing an unread project copy while the worker loaded ~/.hermes/SOUL.md is a
P0 integrity failure (external review finding 5 / Architect E-20260809T113120Z).
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path


def candidate_paths(repo: Path | None = None) -> list[Path]:
    out: list[Path] = []
    hermes_home = os.environ.get("HERMES_HOME", "").strip()
    if hermes_home:
        out.append(Path(hermes_home) / "SOUL.md")
    out.append(Path.home() / ".hermes" / "SOUL.md")
    if repo is not None:
        out.append(repo / ".hermes" / "home" / "SOUL.md")
        out.append(repo / ".hermes" / "SOUL.md")
    # de-dupe preserving order
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def resolve_loaded_soul(repo: Path | None = None) -> dict:
    """Return {ok, soul_path, soul_sha, candidates, gaps}."""
    gaps: list[str] = []
    cands = candidate_paths(repo)
    for path in cands:
        if path.is_file() and os.access(path, os.R_OK):
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            return {
                "ok": True,
                "soul_path": str(path.resolve()),
                "soul_sha": digest,
                "candidates": [str(c) for c in cands],
                "gaps": [],
            }
    gaps.append("loaded_soul_not_found")
    return {
        "ok": False,
        "soul_path": None,
        "soul_sha": None,
        "candidates": [str(c) for c in cands],
        "gaps": gaps,
    }


def main() -> int:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    import json

    result = resolve_loaded_soul(repo)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
