#!/usr/bin/env python3
"""O-SEATBUDGET / ARCH A5 — story seat budget from kind × incident count.

Calibration (Wave4 A5): rename ≈ 1 seat/unit, reimplement ≈ 5, mixed ≈ 5.
At M2, size is owned-finding incident count from the findings inventory.
Units = ceil(incidents / SEAT_BUDGET_INCIDENTS_PER_UNIT) (default 10) so the
product is an operator-useful seat count rather than rate×raw-incidents.

  expected = rate(kind) * max(1, ceil(incidents / UNIT))

Publish as roadmap `- seat-budget: N` + brief; O-LOGBRIEF banner; supervisor
escalates (debt-freeze) when actual story seats exceed N × OVER_FACTOR
(default 2).

Usage:
  seat-budget.py expected --kind reimplement --incidents 51
  seat-budget.py from-story <roadmap.md> <findings-inventory.md> <S0N>
  seat-budget.py check-overrun --sid S03 [--budget N] [--factor F]
"""
from __future__ import annotations

import argparse
import glob
import math
import os
import re
import sys

RATES = {
    "rename": 1,
    "reimplement": 5,
    "mixed": 5,
}


def unit_size() -> int:
    try:
        n = int(os.environ.get("SEAT_BUDGET_INCIDENTS_PER_UNIT", "10"))
    except ValueError:
        n = 10
    return max(1, n)


def over_factor() -> float:
    try:
        return float(os.environ.get("SEAT_BUDGET_OVER_FACTOR", "2"))
    except ValueError:
        return 2.0


def expected_budget(kind: str, incidents: int) -> int:
    """kind × incident-count → expected seats (unit-normalized)."""
    rate = RATES.get((kind or "").lower().strip())
    if rate is None:
        raise ValueError(f"unknown kind '{kind}' (want rename|reimplement|mixed)")
    inc = max(0, int(incidents))
    units = max(1, math.ceil(inc / unit_size())) if inc else 1
    return rate * units


def incident_counts_from_inventory(inv: str) -> dict[str, int]:
    """Per-rule incident counts from findings-inventory.md site lines."""
    counts: dict[str, int] = {}
    current = None
    for line in inv.splitlines():
        m = re.match(
            r"^##\s+([a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d+)\b",
            line,
        )
        if m:
            current = m.group(1)
            counts.setdefault(current, 0)
            continue
        if current is None:
            continue
        # Site line: `- /path/File.java: line 1, 2, 3`
        sm = re.match(r"^-\s+\S+:\s*line\s+(.+)$", line)
        if not sm:
            continue
        nums = [x.strip() for x in sm.group(1).split(",") if x.strip()]
        counts[current] = counts.get(current, 0) + len(nums)
    return counts


def story_incident_total(inv: str, finding_ids: set[str]) -> int:
    """Sum incident sites for story findings; fallback 1 per id if no sites."""
    if not finding_ids:
        return 0
    counts = incident_counts_from_inventory(inv)
    total = sum(counts.get(f, 0) for f in finding_ids)
    if total == 0:
        # Summary-only inventory (fixtures) — one unit per owned finding id.
        return len(finding_ids)
    return total


def parse_kind(raw: str | None) -> str | None:
    if not raw:
        return None
    m = re.match(r"(?i)^(rename|reimplement|mixed)\b", raw.strip())
    return m.group(1).lower() if m else None


def parse_seat_budget_field(raw: str | None) -> int | None:
    if not raw:
        return None
    m = re.match(r"^\s*(\d+)\b", raw.strip())
    return int(m.group(1)) if m else None


def roadmap_story_fields(roadmap: str, sid: str) -> dict[str, str]:
    """Parse `- key: value` fields under ## S0N heading."""
    m = re.search(
        rf"(?m)^##\s+{re.escape(sid)}\b[^\n]*\n(.*?)(?=^##\s+S\d+|\Z)",
        roadmap,
        re.S,
    )
    if not m:
        return {}
    body = m.group(1)
    out = {}
    for fm in re.finditer(r"(?m)^-\s*([a-z0-9_-]+)\s*:\s*(.*)$", body):
        out[fm.group(1).lower()] = fm.group(2).strip()
    return out


def story_finding_ids(fields: dict[str, str]) -> set[str]:
    raw = (fields.get("findings") or "").strip()
    return {
        f
        for f in re.split(r"[,\s]+", raw)
        if f and f != "-" and re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d+", f)
    }


def brief_has_seat_budget(btext: str, n: int) -> bool:
    return bool(
        re.search(
            rf"(?i)(?:seat-budget|\*\*seat budget\*\*|seat budget)\s*[:=]\s*{n}\b",
            btext,
        )
    )


def count_actual_seats(sid: str) -> int:
    """Story-keyed OpenCode JSON seat files (same metric as O-LOGEPILOG COST)."""
    return len(glob.glob(f"/tmp/oc-{sid}-*.json"))


def cmd_expected(args: argparse.Namespace) -> int:
    print(expected_budget(args.kind, args.incidents))
    return 0


def cmd_from_story(args: argparse.Namespace) -> int:
    roadmap = open(args.roadmap, encoding="utf-8").read()
    inv = open(args.inventory, encoding="utf-8").read() if args.inventory else ""
    fields = roadmap_story_fields(roadmap, args.sid)
    kind = parse_kind(fields.get("kind"))
    if not kind:
        print(f"O-SEATBUDGET: {args.sid} has no kind — cannot derive", file=sys.stderr)
        return 2
    fids = story_finding_ids(fields)
    inc = story_incident_total(inv, fids)
    n = expected_budget(kind, inc)
    declared = parse_seat_budget_field(fields.get("seat-budget"))
    print(
        f"{n}\tkind={kind}\tincidents={inc}\tdeclared={declared if declared is not None else '-'}"
    )
    return 0


def cmd_check_overrun(args: argparse.Namespace) -> int:
    sid = args.sid
    budget = args.budget
    if budget is None:
        marker = f"/tmp/story-seat-budget-{sid}"
        if os.path.isfile(marker):
            try:
                budget = int(open(marker, encoding="utf-8").read().strip().split()[0])
            except (OSError, ValueError):
                budget = None
    if budget is None or budget <= 0:
        print(f"O-SEATBUDGET: no budget for {sid} — skip overrun check")
        return 0
    factor = args.factor if args.factor is not None else over_factor()
    actual = count_actual_seats(sid)
    limit = budget * factor
    print(
        f"O-SEATBUDGET: {sid} actual={actual} budget={budget} "
        f"factor={factor} limit={limit:g}"
    )
    if actual > limit:
        print(
            f"O-SEATBUDGET: OVERRUN {sid} actual={actual} > "
            f"{budget}×{factor:g}={limit:g} — escalate",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="O-SEATBUDGET / ARCH A5")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("expected", help="print expected seats for kind×incidents")
    p1.add_argument("--kind", required=True)
    p1.add_argument("--incidents", type=int, required=True)
    p1.set_defaults(func=cmd_expected)

    p2 = sub.add_parser("from-story", help="derive budget from roadmap+inventory")
    p2.add_argument("roadmap")
    p2.add_argument("inventory")
    p2.add_argument("sid")
    p2.set_defaults(func=cmd_from_story)

    p3 = sub.add_parser("check-overrun", help="rc=1 when actual seats exceed budget×factor")
    p3.add_argument("--sid", required=True)
    p3.add_argument("--budget", type=int, default=None)
    p3.add_argument("--factor", type=float, default=None)
    p3.set_defaults(func=cmd_check_overrun)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
