#!/usr/bin/env python3
"""Eligibility-checked, idempotent mint of the three M5 delivery cards.

Assisted continuation after M4 close. The M4 worker must not dest-dispatch
this. Repeated invocation reuses existing idempotency keys and does not
create a second pipeline.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from _cli import dump, ensure_hermes_lib

ensure_hermes_lib()
from m5_delivery import start_delivery  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--exec", dest="execute", action="store_true")
    ap.add_argument("--hermes", default=os.environ.get("HERMES_BIN", "hermes"))
    ap.add_argument("--workspace", default=os.environ.get("K4_WORKSPACE", "dir:/projects/modernized"))
    args = ap.parse_args(argv)
    result = start_delivery(args.root.resolve(), runner=_runner, hermes=args.hermes,
                            execute=args.execute, workspace=args.workspace if args.workspace.startswith("dir:") else "dir:" + args.workspace)
    dump({k: v for k, v in result.items() if k != "commands"})
    if not result.get("ok"):
        print("BLOCKED %s: %s" % (result.get("failed_stage") or "M5 PREFLIGHT", result.get("reason")), file=sys.stderr)
        for row in (result.get("eligibility") or {}).get("reasons") or []:
            print("  condition=%s evidence=%s owner=%s resolution=%s"
                  % (row.get("condition"), row.get("evidence"), row.get("owner"), row.get("resolution")),
                  file=sys.stderr)
        return 2
    if result.get("reused") and not result.get("created"):
        print("OK: M5 delivery already started; reused %d card(s)" % len(result["reused"]))
    elif not args.execute:
        print("OK: M5 delivery plan ready (%d create argv); pass --exec to mint" % len(result.get("created") or []))
    else:
        print("OK: M5 delivery minted %d card(s)" % len(result["created"]))
    return 0


def _runner(argv: list[str]):
    import subprocess
    proc = subprocess.run(argv, text=True, capture_output=True)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


if __name__ == "__main__":
    raise SystemExit(main())
