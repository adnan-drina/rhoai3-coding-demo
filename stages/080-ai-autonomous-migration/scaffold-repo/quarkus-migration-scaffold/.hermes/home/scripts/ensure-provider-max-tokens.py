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
# Official named provider (configuring-models). Older seats used providers.custom.
PRIMARY_PROVIDER_KEYS = ("qwen27b", "custom")


def _load_yaml(path: Path):
    try:
        import yaml  # type: ignore
    except ImportError:
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _dump_yaml(path: Path, doc) -> None:
    import yaml  # type: ignore

    path.write_text(
        yaml.safe_dump(doc, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def _regex_values(text: str) -> tuple[int | None, int | None, int | None, int | None]:
    """Best-effort read without PyYAML (model + first qwen provider block)."""
    import re

    model_mt = re.search(r"(?m)^model:\s*\n(?:[ \t]+.+\n)*?[ \t]+max_tokens:\s*(\d+)\s*$", text)
    ctx = re.search(r"(?m)^[ \t]+context_length:\s*(\d+)\s*$", text)
    # provider model max_tokens under qwen3-6-27b
    qwen_block = re.search(
        rf"(?ms)^[ \t]+{re.escape(MODEL_ID)}:\s*\n((?:[ \t]+.+\n)*)",
        text,
    )
    qwen_mt = None
    qwen_stale = None
    if qwen_block:
        qwen_mt_m = re.search(r"(?m)^[ \t]+max_tokens:\s*(\d+)\s*$", qwen_block.group(1))
        stale_m = re.search(
            r"(?m)^[ \t]+stale_timeout_seconds:\s*(\d+)\s*$", qwen_block.group(1)
        )
        qwen_mt = int(qwen_mt_m.group(1)) if qwen_mt_m else None
        qwen_stale = int(stale_m.group(1)) if stale_m else None
    return (
        int(model_mt.group(1)) if model_mt else None,
        qwen_mt,
        int(ctx.group(1)) if ctx else None,
        qwen_stale,
    )


def _regex_apply(path: Path) -> None:
    """Pin knobs with line rewrites when PyYAML is unavailable."""
    import re

    text = path.read_text(encoding="utf-8")
    text2, n1 = re.subn(
        r"(?m)^([ \t]+context_length:\s*)\d+\s*$",
        rf"\g<1>{REQUIRED_CONTEXT}",
        text,
        count=1,
    )
    text2, n2 = re.subn(
        r"(?m)^(model:\s*\n(?:[ \t]+.+\n)*?[ \t]+max_tokens:\s*)\d+\s*$",
        rf"\g<1>{REQUIRED_MAX_TOKENS}",
        text2,
        count=1,
    )
    # provider qwen max_tokens + stale
    def _qwen_sub(m: re.Match[str]) -> str:
        block = m.group(0)
        block, _ = re.subn(
            r"(?m)^([ \t]+max_tokens:\s*)\d+\s*$",
            rf"\g<1>{REQUIRED_MAX_TOKENS}",
            block,
            count=1,
        )
        block, _ = re.subn(
            r"(?m)^([ \t]+stale_timeout_seconds:\s*)\d+\s*$",
            r"\g<1>900",
            block,
            count=1,
        )
        if "max_tokens:" not in block:
            indent = re.match(r"^([ \t]+)", m.group(0).splitlines()[-1] or "        ")
            ind = indent.group(1) if indent else "        "
            block = block.rstrip() + f"\n{ind}max_tokens: {REQUIRED_MAX_TOKENS}\n"
        return block

    text2, n3 = re.subn(
        rf"(?ms)^([ \t]+{re.escape(MODEL_ID)}:\s*\n(?:[ \t]+.+\n)*)",
        _qwen_sub,
        text2,
        count=1,
    )
    if n1 + n2 + n3 == 0 and f"max_tokens: {REQUIRED_MAX_TOKENS}" not in text2:
        raise SystemExit(f"FAIL: regex apply could not pin max_tokens in {path}")
    path.write_text(text2, encoding="utf-8")


def ensure(path: Path, apply: bool) -> bool:
    if not path.is_file():
        print(f"SKIP: missing {path}")
        return False
    doc = _load_yaml(path)
    if doc is None:
        before = _regex_values(path.read_text(encoding="utf-8"))
        need = (
            before[0] != REQUIRED_MAX_TOKENS
            or before[1] != REQUIRED_MAX_TOKENS
            or before[2] != REQUIRED_CONTEXT
            or before[3] != 900
        )
        if not need:
            print(f"OK: {path} already max_tokens={REQUIRED_MAX_TOKENS} (regex)")
            return False
        print(
            f"{'APPLY' if apply else 'WOULD'}: {path} (no PyYAML) "
            f"model.max_tokens {before[0]!r}→{REQUIRED_MAX_TOKENS} "
            f"provider.max_tokens {before[1]!r}→{REQUIRED_MAX_TOKENS}"
        )
        if not apply:
            return True
        _regex_apply(path)
        print(f"OK: patched {path} via regex")
        return True

    model = doc.setdefault("model", {})
    providers = doc.setdefault("providers", {})
    prov_key = next((k for k in PRIMARY_PROVIDER_KEYS if k in providers), "qwen27b")
    custom = providers.setdefault(prov_key, {})
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
        managed_raw = (os.environ.get("HERMES_MANAGED_DIR") or "").strip()
        managed = Path(managed_raw or "/projects/.platform/hermes")
        home_raw = (os.environ.get("HERMES_HOME") or "").strip()
        home = Path(home_raw or "/projects/modernized/.hermes/home")
        paths = [managed / "config.yaml", home / "config.yaml"]
    changed = False
    for p in paths:
        changed = ensure(p, args.apply) or changed
    if changed and not args.apply:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
