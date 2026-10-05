#!/usr/bin/env python3
"""FAIL unless the canary rule fired in the recorded MTA run.

Reads evidence/producers/mta.json `canary` and migration.yaml
`analysis.canary_rule_id`. Exit 0 fired; 1 not fired / not configured;
2 usage. Admission blocks CANARY_MISSING independently of this exit —
this script names the gap at M1 time, where it can still be fixed.
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
from planner.canonical import load_json  # noqa: E402
from planner.evidence import load_migration  # noqa: E402
from planner.paths import producer_receipt  # noqa: E402


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    if not root.is_dir():
        print("usage: assert-mta-canary.py <dest-root>", file=sys.stderr)
        return 2
    canary_id = load_migration(root)["canary_rule_id"]
    if not canary_id:
        print("FAIL: CANARY_MISSING migration.yaml analysis.canary_rule_id is empty", file=sys.stderr)
        return 1
    rec = producer_receipt(root, "mta")
    if not rec.is_file():
        print("FAIL: CANARY_MISSING no evidence/producers/mta.json", file=sys.stderr)
        return 1
    canary = (load_json(rec).get("canary") or {})
    if canary.get("rule_id") != canary_id or canary.get("fired") is not True:
        print("FAIL: CANARY_MISSING rule %s did not fire (effective ruleset unproven; check --rules and target labels)" % canary_id, file=sys.stderr)
        return 1
    print("OK: canary %s fired" % canary_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
