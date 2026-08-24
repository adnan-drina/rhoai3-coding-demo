#!/usr/bin/env python3
"""Build-time pin oracle for a Hermes source tree.

Reads ``__version__`` and ``__release_date__`` from ``hermes_cli/__init__.py``
via ``ast`` — the same contract as dest ``.hermes/checks/assert-agent-pin.py``.
Does not parse ``hermes --version``. Does not ``import hermes_cli``.

This script lives in ``workspace-images/`` so the Docker build does not copy
or modify the fenced ``.hermes/`` tree. Keep the two oracles in lockstep when
the pin keys change.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

_PIN_KEYS = ("__version__", "__release_date__")


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"assert-hermes-source-pin: cannot read {path}: {exc}") from exc


def _norm_ver(value: str) -> str:
    text = (value or "").strip()
    if len(text) >= 2 and text[0] in "vV" and text[1].isdigit():
        return text[1:]
    return text


def _literal_str(node: ast.AST, key: str) -> str:
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError) as exc:
        raise SystemExit(
            f"assert-hermes-source-pin: {key} is not a literal constant"
        ) from exc
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(
            f"assert-hermes-source-pin: {key} is not a non-empty string literal"
        )
    return value


def read_agent_constants(agent_src: Path) -> tuple[str, str]:
    init_py = agent_src / "hermes_cli" / "__init__.py"
    try:
        source = init_py.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"assert-hermes-source-pin: cannot read {init_py}: {exc}") from exc
    try:
        tree = ast.parse(source, filename=str(init_py))
    except SyntaxError as exc:
        raise SystemExit(f"assert-hermes-source-pin: cannot parse {init_py}: {exc}") from exc

    got: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in _PIN_KEYS:
                got[target.id] = _literal_str(node.value, target.id)

    missing = [key for key in _PIN_KEYS if key not in got]
    if missing:
        raise SystemExit(
            "assert-hermes-source-pin: missing or non-literal "
            + ", ".join(missing)
            + f" in {init_py}"
        )
    return got["__version__"], got["__release_date__"]


def _want_from_pins(pins_path: Path) -> tuple[str, str]:
    pins = _load_json(pins_path)
    agent = (pins.get("pins") or {}).get("hermes_agent") or {}
    want_ver = str(agent.get("version") or "")
    want_build = str(agent.get("build") or "")
    if not want_ver or not want_build:
        raise SystemExit(
            "assert-hermes-source-pin: pins.json missing hermes_agent.version/build"
        )
    return want_ver, want_build


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--pins", type=Path, help="path to .hermes/pins.json")
    src.add_argument("--version", help="expected __version__ (optional v prefix)")
    p.add_argument("--date", help="expected __release_date__ (required with --version)")
    p.add_argument(
        "--agent-src",
        required=True,
        type=Path,
        help="Hermes checkout containing hermes_cli/__init__.py",
    )
    args = p.parse_args(argv)

    if args.pins is not None:
        want_ver, want_build = _want_from_pins(args.pins)
    else:
        if not args.date:
            raise SystemExit("assert-hermes-source-pin: --date is required with --version")
        want_ver, want_build = args.version, args.date

    got_ver, got_build = read_agent_constants(args.agent_src)
    if _norm_ver(got_ver) != _norm_ver(want_ver) or got_build != want_build:
        print(
            "assert-hermes-source-pin: refusing off-pin source "
            f"(tree {got_ver}/{got_build} != pin {want_ver}/{want_build})",
            file=sys.stderr,
        )
        return 1
    print(f"assert-hermes-source-pin: MATCH {want_ver} / {want_build}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
