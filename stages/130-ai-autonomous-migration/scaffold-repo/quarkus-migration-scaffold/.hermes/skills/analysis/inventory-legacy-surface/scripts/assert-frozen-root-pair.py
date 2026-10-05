#!/usr/bin/env python3
"""FAIL unless the inventory root equals the frozen analysis copy.

Both M1 scanners (JDK-model inventory and MTA) take the freeze receipt's
``analysis_copy``. A hardcoded /projects/legacy or a derived Boot 3 tree
is REFUSE. Exit 0 roots agree; 1 mismatch or missing; 2 usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _fail(msg: str) -> int:
    print("REFUSE: frozen-root pair: " + msg, file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        print("usage: assert-frozen-root-pair.py <dest-root>", file=sys.stderr)
        return 2
    rec = root / "evidence" / "producers" / "freeze.json"
    if not rec.is_file():
        return _fail("missing evidence/producers/freeze.json (freeze-migration-input did not run)")
    freeze = json.loads(rec.read_text(encoding="utf-8"))
    copy = str(freeze.get("analysis_copy") or "").strip()
    if not copy:
        return _fail("freeze receipt names no analysis_copy (do not guess /projects/legacy)")
    inv = root / "evidence" / "entry-point-inventory.json"
    if not inv.is_file():
        return _fail("missing evidence/entry-point-inventory.json")
    doc = json.loads(inv.read_text(encoding="utf-8"))
    raw = str(doc.get("root") or "").strip()
    if not raw:
        return _fail("inventory missing root")
    if Path(raw).resolve() != Path(copy).resolve():
        return _fail("inventory root %s != frozen analysis copy %s" % (raw, copy))
    digest = str(((doc.get("execution_evidence") or {}).get("inputs_digest_sha256")) or "")
    if digest and digest != str(freeze.get("source_digest") or ""):
        return _fail("inventory inputs digest %s != frozen source digest %s" % (digest[:12], str(freeze.get("source_digest"))[:12]))
    print("OK: frozen-root pair root=%s digest=%s" % (copy, str(freeze.get("source_digest"))[:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
