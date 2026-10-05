#!/usr/bin/env python3
"""Consumer-side seal check: is the receipt on disk still authoritative?

Re-digests the four artifacts, decisions.yaml, every contract file, and
the tool pins and compares them with the receipt seals. Exit 0 when the
receipt is ADMITTED and intact; 1 otherwise (gaps listed). `--any-status`
accepts a non-ADMITTED receipt whose seals are intact (for reporting).
"""
from __future__ import annotations

import argparse
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
from planner.admission import verify_receipt  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--any-status", action="store_true")
    args = ap.parse_args(argv)
    receipt, gaps = verify_receipt(Path(args.root).resolve(), require_admitted=not args.any_status)
    if gaps:
        for g in gaps:
            print("  - " + g, file=sys.stderr)
        print("REFUSE: RECEIPT_NOT_AUTHORITATIVE (%d gap(s))" % len(gaps), file=sys.stderr)
        return 1
    print("OK: receipt %s status=%s" % (receipt["receipt_digest"][:16], receipt["status"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
