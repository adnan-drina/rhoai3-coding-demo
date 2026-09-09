#!/usr/bin/env python3
"""FAIL if the analysis copy no longer matches the frozen manifest.

Run before MTA analysis: nothing may transform the byte-identical copy
before the baseline analysis (SAD §5.1). Exit 0 intact; 1 diverged; 2 usage.
"""
from __future__ import annotations

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
from planner.canonical import load_json, sha256_file  # noqa: E402
from planner.paths import SOURCE_MANIFEST, producer_receipt  # noqa: E402


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    if not root.is_dir():
        print("usage: assert-frozen-input-intact.py <dest-root>", file=sys.stderr)
        return 2
    rec = producer_receipt(root, "freeze")
    man = root / SOURCE_MANIFEST
    if not rec.is_file() or not man.is_file():
        print("FAIL: FROZEN_INPUT missing freeze receipt or manifest", file=sys.stderr)
        return 1
    copy = Path(str(load_json(rec).get("analysis_copy") or ""))
    if not copy.is_dir():
        print("FAIL: FROZEN_INPUT analysis_copy %s missing" % copy, file=sys.stderr)
        return 1
    bad: list[str] = []
    for row in load_json(man).get("files") or []:
        p = copy / row["path"]
        if not p.is_file() or sha256_file(p) != row["sha256"]:
            bad.append(row["path"])
    if bad:
        print("FAIL: FROZEN_INPUT %d file(s) diverged from the frozen manifest: %s" % (len(bad), ", ".join(bad[:5])), file=sys.stderr)
        return 1
    print("OK: analysis copy intact (%s)" % copy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
