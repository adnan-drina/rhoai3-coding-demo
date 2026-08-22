#!/usr/bin/env python3
"""Refuse a Hermes dashboard bundle stamped for a different agent pin.

PIN next to this file must match `.hermes/pins.json` `hermes_agent.version`
+ `hermes_agent.build`. A mismatch is fail-closed for *serving* the UI,
not for the workspace (caller is fail-soft). Invoked from
`install-web-dist.sh` before copy.

Not a skill. Not a `.hermes/lib/` module (no `__main__` CLIs there).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"assert-web-dist-pin: cannot read {path}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pins", required=True, type=Path, help="path to .hermes/pins.json")
    p.add_argument("--stamp", required=True, type=Path, help="path to shipped PIN JSON")
    p.add_argument(
        "--bundle",
        required=True,
        type=Path,
        help="path to shipped web_dist/index.html",
    )
    args = p.parse_args(argv)

    if not args.bundle.is_file():
        print(f"assert-web-dist-pin: missing bundle {args.bundle}", file=sys.stderr)
        return 1

    pins = _load_json(args.pins)
    agent = (pins.get("pins") or {}).get("hermes_agent") or {}
    want_ver = str(agent.get("version") or "")
    want_build = str(agent.get("build") or "")
    if not want_ver or not want_build:
        print("assert-web-dist-pin: pins.json missing hermes_agent.version/build", file=sys.stderr)
        return 1

    stamp = _load_json(args.stamp)
    got_ver = str(stamp.get("hermes_agent_version") or "")
    got_build = str(stamp.get("hermes_agent_build") or "")
    if got_ver != want_ver or got_build != want_build:
        print(
            "assert-web-dist-pin: refusing stale UI "
            f"(bundle {got_ver}/{got_build} != pin {want_ver}/{want_build})",
            file=sys.stderr,
        )
        return 1
    print(f"assert-web-dist-pin: MATCH {want_ver} / {want_build}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
