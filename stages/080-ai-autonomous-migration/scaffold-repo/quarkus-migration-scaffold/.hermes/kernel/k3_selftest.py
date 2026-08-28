#!/usr/bin/env python3
"""K3 land-time selftest. Not pytest. Not dest."""
from __future__ import annotations

import sys
from pathlib import Path

KERNEL = Path(__file__).resolve().parent
sys.path.insert(0, str(KERNEL))
from k3_verify import validate_file  # noqa: E402


def main() -> int:
    hold = KERNEL / "fixtures" / "k3-valid-hold.json"
    refuse = KERNEL / "fixtures" / "k3-valid-refuse-hold.json"
    retired = KERNEL / "fixtures" / "k3-valid-no-factory.json"
    bad = KERNEL / "fixtures" / "k3-bad-gap.json"
    for path in (hold, refuse, retired):
        issues = validate_file(path)
        if issues:
            print("FAIL: %s %s" % (path.name, issues), file=sys.stderr)
            return 1
    bad_codes = {c for c, _, _ in validate_file(bad)}
    need = {
        "K3_CREATED_CARDS",
        "K3_VERIFIER_PARENT",
        "K3_TERMINATOR",
        "K3_ACK_GATE",
        "K3_DAEMON",
        "K3_ASSIGNEE",
        "K3_REFUSE_CLAIM",
    }
    missing = need - bad_codes
    if missing:
        print("FAIL: bad fixture missed %s got %s" % (missing, bad_codes), file=sys.stderr)
        return 1
    if len(bad_codes) < 6:
        print("FAIL: expected full gap set, got %s" % bad_codes, file=sys.stderr)
        return 1
    print("OK: K3 selftest (%d codes on bad fixture)" % len(bad_codes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
