#!/usr/bin/env python3
"""Refuse an installed Hermes agent that does not match `.hermes/pins.json`.

Reads `__version__` and `__release_date__` from `hermes_cli/__init__.py`
via `ast` (Operator `112353Z` / Architect `112612Z`). Does not parse the
`hermes --version` banner. Does not `import hermes_cli`. Dashboard stamp
MATCH is `assert-web-dist-pin.py`. Lives in `.hermes/checks/`.

Not a skill. Not a `.hermes/lib/` module.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path

_PIN_KEYS = ("__version__", "__release_date__")


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"assert-agent-pin: cannot read {path}: {exc}") from exc


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
            f"assert-agent-pin: {key} is not a literal constant"
        ) from exc
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"assert-agent-pin: {key} is not a non-empty string literal")
    return value


def read_agent_constants(agent_src: Path) -> tuple[str, str]:
    init_py = agent_src / "hermes_cli" / "__init__.py"
    try:
        source = init_py.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"assert-agent-pin: cannot read {init_py}: {exc}") from exc
    try:
        tree = ast.parse(source, filename=str(init_py))
    except SyntaxError as exc:
        raise SystemExit(f"assert-agent-pin: cannot parse {init_py}: {exc}") from exc

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
            "assert-agent-pin: missing or non-literal "
            + ", ".join(missing)
            + f" in {init_py}"
        )
    return got["__version__"], got["__release_date__"]


def resolve_agent_src(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    candidates = []
    hermes_home = Path(os.environ.get("HERMES_HOME") or "")
    if str(hermes_home):
        candidates.append(hermes_home / "hermes-agent")
    candidates.append(Path.home() / ".hermes" / "hermes-agent")
    for path in candidates:
        if (path / "hermes_cli" / "__init__.py").is_file():
            return path
    raise SystemExit(
        "assert-agent-pin: hermes_cli/__init__.py not found under "
        "HERMES_HOME/hermes-agent or ~/.hermes/hermes-agent"
    )


def _want_pin(pins_path: Path) -> tuple[str, str]:
    pins = _load_json(pins_path)
    agent = (pins.get("pins") or {}).get("hermes_agent") or {}
    want_ver = str(agent.get("version") or "")
    want_build = str(agent.get("build") or "")
    if not want_ver or not want_build:
        raise SystemExit(
            "assert-agent-pin: pins.json missing hermes_agent.version/build"
        )
    return want_ver, want_build


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pins", required=True, type=Path, help="path to .hermes/pins.json")
    p.add_argument(
        "--agent-src",
        type=Path,
        help="Hermes agent checkout containing hermes_cli/__init__.py",
    )
    args = p.parse_args(argv)

    want_ver, want_build = _want_pin(args.pins)
    try:
        agent_src = resolve_agent_src(args.agent_src)
        got_ver, got_build = read_agent_constants(agent_src)
    except SystemExit as exc:
        msg = exc.code if isinstance(exc.code, str) else (exc.args[0] if exc.args else "")
        if isinstance(msg, str) and msg.startswith("assert-agent-pin:"):
            print(msg, file=sys.stderr)
        return 1

    if _norm_ver(got_ver) != _norm_ver(want_ver) or got_build != want_build:
        print(
            "assert-agent-pin: refusing off-pin agent "
            f"(installed {got_ver}/{got_build} != pin {want_ver}/{want_build})",
            file=sys.stderr,
        )
        return 1
    print(f"assert-agent-pin: MATCH {want_ver} / {want_build}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
