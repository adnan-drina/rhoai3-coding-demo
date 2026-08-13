#!/usr/bin/env python3
"""S-008 / W4 — parent→child→grandchild (scar triad) resurrection order.

Contract: governance/contracts/s008-quarantine-resurrection-order.md
Distinct from quarantine-survives-dispatch (tombstones). This lint refuses
partition / story bodies that list grandchild before child, or child before
parent, when the triad appears together.

Usage:
  python3 check-s008-resurrection-order.py .
  python3 check-s008-resurrection-order.py /projects/modernized
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

EXIT_CODES = """Exit codes:
  0  pass — no triad disorder, or idle (no triad present)
  1  BLOCK — grandchild before child or child before parent in partition/bodies
  2  usage
"""

CONTRACT = "governance/contracts/s008-quarantine-resurrection-order.md"
# Scar role tokens (W4) — matched in partition/bodies; guidance prose must not
# use specimen slash-forms (R-SK.5).
ROLE_RX = {
    "owner": re.compile(r"\bowners?\b|\bowner\b", re.I),
    "pet": re.compile(r"\bpets?\b|\bpet\b", re.I),
    "visit": re.compile(r"\bvisits?\b|\bvisit\b", re.I),
}
# Exclude false positives from compound product names by relying on
# word-boundary regexes above (ROLE_RX).


def role_hits(text: str) -> set[str]:
    hits: set[str] = set()
    for role, rx in ROLE_RX.items():
        if rx.search(text):
            hits.add(role)
    return hits


def first_index(text: str, role: str) -> int:
    m = ROLE_RX[role].search(text)
    return m.start() if m else -1


def check_order(label: str, text: str) -> int:
    hits = role_hits(text)
    # Only enforce when at least two of the triad appear together
    if len(hits & {"owner", "pet", "visit"}) < 2:
        return 0
    bad = 0
    idxs = {r: first_index(text, r) for r in ("owner", "pet", "visit")}
    # Parent must precede child when both present
    if idxs["owner"] >= 0 and idxs["pet"] >= 0 and idxs["pet"] < idxs["owner"]:
        print(
            f"FAIL: {label}: child (pet) appears before parent (owner) "
            f"(S-008 / {CONTRACT})",
            file=sys.stderr,
        )
        bad = 1
    # Child must precede grandchild when both present
    if idxs["pet"] >= 0 and idxs["visit"] >= 0 and idxs["visit"] < idxs["pet"]:
        print(
            f"FAIL: {label}: grandchild (visit) appears before child (pet) "
            f"(S-008 / {CONTRACT})",
            file=sys.stderr,
        )
        bad = 1
    # Parent must precede grandchild when both present (even if child absent)
    if idxs["owner"] >= 0 and idxs["visit"] >= 0 and idxs["visit"] < idxs["owner"]:
        print(
            f"FAIL: {label}: grandchild (visit) appears before parent (owner) "
            f"(S-008 / {CONTRACT})",
            file=sys.stderr,
        )
        bad = 1
    return bad


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    contract = root / CONTRACT
    if not contract.is_file():
        print(f"FAIL: missing {CONTRACT}", file=sys.stderr)
        return 1
    _ = contract.read_text(encoding="utf-8")[:40]
    print(f"OK: citing {CONTRACT}")

    bad = 0
    checked = 0
    part = root / "evidence" / "briefs" / "partition.json"
    if part.is_file():
        checked += 1
        bad |= check_order(
            "evidence/briefs/partition.json",
            part.read_text(encoding="utf-8"),
        )

    bodies = root / "evidence" / "bodies"
    if bodies.is_dir():
        for path in sorted(bodies.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            blob = json.dumps(data, ensure_ascii=False)
            checked += 1
            bad |= check_order(str(path.relative_to(root)), blob)

    if bad:
        return 1
    if checked == 0:
        print("OK: S-008 resurrection-order idle (no partition/bodies)")
        return 0
    print(f"OK: S-008 resurrection-order passed ({checked} artifact(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
