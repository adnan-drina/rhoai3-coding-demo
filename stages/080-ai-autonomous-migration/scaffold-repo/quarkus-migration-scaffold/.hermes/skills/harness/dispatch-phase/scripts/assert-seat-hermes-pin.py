#!/usr/bin/env python3
"""Refuse Hermes seat drift vs .hermes/pins.json (Architect E-20260818T111730Z).

The initial_status contract is binary-local (--help + VALID_INITIAL_STATUSES),
not the public CLI page. Omit --initial-status → ready (fail-open). Pin the
binary on the seat.

Version probe is likewise binary-local: `hermes --version` / `-V` (hermes-cli
Validation). Do not call `hermes version` — that subcommand is on the public
CLI page and this seat's argparse rejects it. A usage dump is not a version
string (v37 autostart false-refusal).

Exit: 0=match; 1=mismatch (typed BLOCK / seat drift); 2=unreadable/broken probe.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _is_argparse_noise(blob: str) -> bool:
    head = blob.lstrip()
    return head.startswith("usage:") or "invalid choice" in blob


def _probe_version() -> tuple[int, str]:
    proc = subprocess.run(
        ["hermes", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    blob = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, blob


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    pins_path = root / ".hermes" / "pins.json"
    if not pins_path.is_file():
        print("FAIL: missing .hermes/pins.json", file=sys.stderr)
        return 2
    try:
        pins = json.loads(pins_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exec_err:
        print(f"FAIL: pins.json unreadable: {exec_err}", file=sys.stderr)
        return 2
    want = str(
        ((pins.get("pins") or {}).get("hermes_agent") or {}).get("version") or ""
    ).strip()
    if not want:
        print("FAIL: pins.hermes_agent.version empty", file=sys.stderr)
        return 2
    rc, blob = _probe_version()
    if rc != 0 or not blob or _is_argparse_noise(blob):
        print(
            f"FAIL: hermes --version unreadable (rc={rc}; not a version string)",
            file=sys.stderr,
        )
        return 2
    needle = want.lstrip("v")
    if needle not in blob and want not in blob:
        print(
            f"FAIL: seat Hermes {blob!r} does not match pin {want} "
            "(binary-local contract; public CLI page is not authority)",
            file=sys.stderr,
        )
        return 1
    print(f"OK: seat Hermes matches pin {want}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
