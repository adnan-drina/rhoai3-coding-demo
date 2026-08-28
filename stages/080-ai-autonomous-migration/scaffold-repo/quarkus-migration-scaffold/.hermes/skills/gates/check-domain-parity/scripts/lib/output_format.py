"""Shared CLI output helper — data on stdout, diagnostics on stderr (UPLIFT-2).

Usage in a check script:

    from output_format import add_format_arg, emit_result

    ap = argparse.ArgumentParser(...)
    add_format_arg(ap)
    args = ap.parse_args()
    ...
    emit_result(args.format, {"check": "name", "ok": True}, human="OK: …", ok=True)
"""
from __future__ import annotations

import json
import sys
from typing import Any


def add_format_arg(parser) -> None:
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help=(
            "text: human line on stdout when ok, stderr when not (default); "
            "json: one JSON object on stdout, human on stderr"
        ),
    )


def emit_result(
    fmt: str,
    record: dict[str, Any],
    human: str,
    *,
    ok: bool = True,
) -> None:
    """Emit a check result.

    text  — human on stdout if ok else stderr (legacy greppable / FAIL-on-stderr).
    json  — JSON on stdout; human line on stderr.
    """
    if fmt == "json":
        print(json.dumps(record, separators=(",", ":")), flush=True)
        if human:
            print(human, file=sys.stderr)
        return
    if human:
        print(human, file=sys.stdout if ok else sys.stderr)
