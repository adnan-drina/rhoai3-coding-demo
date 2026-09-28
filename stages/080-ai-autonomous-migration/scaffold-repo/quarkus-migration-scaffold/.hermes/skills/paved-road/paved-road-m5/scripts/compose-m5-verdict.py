#!/usr/bin/env python3
"""Compose the M5 verdict from recorded delivery evidence. Checkers do not author it."""
from __future__ import annotations

import sys
from pathlib import Path

from _cli import dump, ensure_hermes_lib, root_parser

ensure_hermes_lib()
from m5_delivery import compose_verdict, load_delivery_contract, walkthrough  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = root_parser(__doc__).parse_args(argv)
    doc = compose_verdict(args.root.resolve())
    dump(doc)
    contract = load_delivery_contract(args.root.resolve())
    print("deployment_status=%s verdict=%s ship=%s" % (doc.get("deployment_status"), doc.get("verdict"), doc.get("ship")))
    for line in walkthrough(doc, contract):
        print("WALKTHROUGH: " + line)
    if doc.get("failed_stage"):
        print("BLOCKED %s: %s" % (doc.get("failed_stage"), doc.get("reason")), file=sys.stderr)
        return 2
    print("OK: M5 %s (deployment %s; outstanding %d)"
          % (doc.get("verdict"), doc.get("deployment_status"), len(doc.get("outstanding") or [])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
