#!/usr/bin/env python3
"""Ensure Hermes provider output cap is present (Architect E-20260810T141120Z).

Unset Hermes max_tokens defaults to half of context_length (65536). With
context_length=131072, any prompt ≥65537 tokens is arithmetically unservable
(vLLM 131072 ceiling). Workspace-only caps are §G.1 hand_placed — this script
makes the tip enforce the pin on managed + HERMES_HOME configs at dispatch.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REQUIRED_MAX_TOKENS = 8192
REQUIRED_CONTEXT = 131072
MODEL_ID = "qwen3-6-27b"


def _load_yaml(path: Path):
    try:
        import yaml  # type: ignore
    except ImportError:
        # Minimal fallback: refuse rather than half-parse.
        print(f"FAIL: PyYAML required to patch {path}", file=sys.stderr)
        sys.exit(2)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _dump_yaml(path: Path, doc) -> None:
    import yaml  # type: ignore

    path.write_text(
        yaml.safe_dump(doc, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def ensure(path: Path, apply: bool) -> bool:
    if not path.is_file():
        print(f"SKIP: missing {path}")
        return False
    doc = _load_yaml(path)
    model = doc.setdefault("model", {})
    providers = doc.setdefault("providers", {})
    custom = providers.setdefault("custom", {})
    models = custom.setdefault("models", {})
    qwen = models.setdefault(MODEL_ID, {})

    before = (
        model.get("max_tokens"),
        qwen.get("max_tokens"),
        model.get("context_length"),
        qwen.get("stale_timeout_seconds"),
    )
    need = (
        before[0] != REQUIRED_MAX_TOKENS
        or before[1] != REQUIRED_MAX_TOKENS
        or before[2] != REQUIRED_CONTEXT
        or before[3] != 900
    )
    if not need:
        print(f"OK: {path} already max_tokens={REQUIRED_MAX_TOKENS}")
        return False
    print(
        f"{'APPLY' if apply else 'WOULD'}: {path} "
        f"model.max_tokens {before[0]!r}→{REQUIRED_MAX_TOKENS} "
        f"provider.max_tokens {before[1]!r}→{REQUIRED_MAX_TOKENS}"
    )
    if not apply:
        return True
    model["context_length"] = REQUIRED_CONTEXT
    model["max_tokens"] = REQUIRED_MAX_TOKENS
    qwen["max_tokens"] = REQUIRED_MAX_TOKENS
    qwen["stale_timeout_seconds"] = 900
    _dump_yaml(path, doc)
    print(f"OK: patched {path}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--apply",
        action="store_true",
        help="write patches (default: report only)",
    )
    ap.add_argument(
        "paths",
        nargs="*",
        help="config.yaml paths (default: managed + HERMES_HOME)",
    )
    args = ap.parse_args()
    paths = [Path(p) for p in args.paths]
    if not paths:
        managed = Path(os.environ.get("HERMES_MANAGED_DIR", "/projects/.platform/hermes"))
        home = Path(os.environ.get("HERMES_HOME", ""))
        if not home:
            home = Path("/projects/modernized/.hermes/home")
        paths = [managed / "config.yaml", home / "config.yaml"]
    changed = False
    for p in paths:
        changed = ensure(p, args.apply) or changed
    if changed and not args.apply:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
