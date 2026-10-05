#!/usr/bin/env python3
"""M5 PREFLIGHT: bind the closed M4 result, record qualifications, write the candidate."""
from __future__ import annotations

import sys
from pathlib import Path

from _cli import dump, ensure_hermes_lib, root_parser

ensure_hermes_lib()
from m5_delivery import prepare_candidate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = root_parser(__doc__).parse_args(argv)
    doc = prepare_candidate(args.root.resolve())
    dump(doc)
    if not doc.get("ok"):
        print("BLOCKED M5 PREFLIGHT: %s" % doc.get("reason"), file=sys.stderr)
        return 2
    print("OK: candidate %s pipeline_eligible=%s release_eligible=%s outstanding=%d"
          % (doc.get("candidate_sha"), doc.get("pipeline_eligible"), doc.get("release_eligible"),
             len(doc.get("outstanding") or [])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
