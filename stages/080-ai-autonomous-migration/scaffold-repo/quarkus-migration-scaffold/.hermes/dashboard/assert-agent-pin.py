#!/usr/bin/env python3
"""Refuse an installed Hermes agent that does not match `.hermes/pins.json`.

Same fail-closed shape as `assert-web-dist-pin.py`, but compares
`hermes --version` (or `--version-text`) to `hermes_agent.version` +
`hermes_agent.build`. Dashboard stamp MATCH is not this check.

Not a skill. Not a `.hermes/lib/` module.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_VER_RE = re.compile(
    r"(v\d+\.\d+\.\d+)\s*\(([^)]+)\)",
    re.IGNORECASE,
)


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"assert-agent-pin: cannot read {path}: {exc}") from exc


def _parse_version_text(text: str) -> tuple[str, str]:
    match = _VER_RE.search(text or "")
    if not match:
        print(
            f"assert-agent-pin: cannot parse hermes version from {text!r}",
            file=sys.stderr,
        )
        return "", ""
    return match.group(1), match.group(2).strip()


def _want_pin(pins_path: Path) -> tuple[str, str]:
    pins = _load_json(pins_path)
    agent = (pins.get("pins") or {}).get("hermes_agent") or {}
    want_ver = str(agent.get("version") or "")
    want_build = str(agent.get("build") or "")
    if not want_ver or not want_build:
        print(
            "assert-agent-pin: pins.json missing hermes_agent.version/build",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return want_ver, want_build


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pins", required=True, type=Path, help="path to .hermes/pins.json")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--hermes", type=Path, help="path to hermes CLI")
    src.add_argument(
        "--version-text",
        help="already-captured hermes --version output (tests / dest-exec)",
    )
    args = p.parse_args(argv)

    want_ver, want_build = _want_pin(args.pins)
    if args.version_text is not None:
        text = args.version_text
    else:
        if not args.hermes.is_file():
            print(f"assert-agent-pin: missing hermes CLI {args.hermes}", file=sys.stderr)
            return 1
        try:
            proc = subprocess.run(
                [str(args.hermes), "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"assert-agent-pin: hermes --version failed: {exc}", file=sys.stderr)
            return 1
        text = (proc.stdout or "") + "\n" + (proc.stderr or "")
        if proc.returncode != 0 and not _VER_RE.search(text):
            print(
                f"assert-agent-pin: hermes --version rc={proc.returncode}",
                file=sys.stderr,
            )
            return 1

    got_ver, got_build = _parse_version_text(text)
    if not got_ver or not got_build:
        return 1
    if got_ver != want_ver or got_build != want_build:
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
