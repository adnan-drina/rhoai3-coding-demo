#!/usr/bin/env python3
"""Compose evidence/planning/admission-receipt.json.

Exit 0 ADMITTED; 1 INCONCLUSIVE (receipt written, BLOCKs on stderr);
2 COMPAT_FAIL or missing inputs.
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
from planner.admission import ADMITTED, COMPAT_FAIL, INCONCLUSIVE  # noqa: E402
from planner.paths import ADMISSION_RECEIPT  # noqa: E402
from planner.pipeline import admit  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        receipt = admit(root)
    except FileNotFoundError as exc:
        print("FAIL: ADMISSION_INPUT %s" % exc, file=sys.stderr)
        return 2
    status = receipt["status"]
    c = receipt["counts"]
    line = "admission %s receipt=%s head=%s open_clusters=%d deferred=%d measure=%s open_blocks=%d loop_complete=%s → %s" % (
        status, receipt["receipt_digest"][:16], receipt.get("head") or "-", c["open_clusters"], c["deferred"], (receipt.get("measure") or {}).get("tuple"), c["open_blocks"], receipt.get("loop_complete"), ADMISSION_RECEIPT)
    if status == ADMITTED:
        print("OK: " + line)
        return 0
    for r in receipt["reasons"]:
        print("  - " + r, file=sys.stderr)
    if status == INCONCLUSIVE:
        print("REFUSE: " + line, file=sys.stderr)
        return 1
    print("FAIL: %s %s" % (COMPAT_FAIL, line), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
