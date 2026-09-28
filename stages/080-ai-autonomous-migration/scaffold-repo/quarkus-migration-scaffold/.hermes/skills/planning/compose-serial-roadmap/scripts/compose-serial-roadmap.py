#!/usr/bin/env python3
"""Compose evidence/planning/serial-roadmap.json after M2.

Derived view of the work list and admission receipt. Does not mint.
Does not seal. Planned M4/M5 rows never claim a candidate or receipt.
Exit 0 on write; 2 on missing inputs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _ensure_hermes_lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()
from planner.paths import SERIAL_ROADMAP  # noqa: E402
from planner.roadmap import compose_serial_roadmap  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--print", dest="dump", action="store_true",
                    help="write the document to stdout as well as disk")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        doc = compose_serial_roadmap(root)
    except FileNotFoundError as exc:
        print("FAIL: ROADMAP_INPUT %s" % exc, file=sys.stderr)
        return 2
    except ValueError as exc:
        print("FAIL: ROADMAP %s" % exc, file=sys.stderr)
        return 2
    exe = doc.get("executable") or []
    exe_s = exe[0]["title"] if exe else "(none)"
    planned = [p["title"] for p in doc.get("planned") or []]
    print("OK: serial-roadmap admission=%s executable=%s planned=%d parallel=%s → %s" % (
        doc.get("admission_status"), exe_s, len(planned), doc.get("parallel_execution"), SERIAL_ROADMAP))
    if args.dump:
        json.dump(doc, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
