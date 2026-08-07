#!/usr/bin/env python3
"""O-SEATBUDGET / ARCH A5 — story seat budget from kind × size.

Calibration (Wave4 A5): rename ≈ 1 seat/unit, reimplement ≈ 5, mixed ≈ 5.
At M2, size is owned-finding incident count from the findings inventory.
Units = ceil(incidents / SEAT_BUDGET_INCIDENTS_PER_UNIT) (default 10) so the
product is an operator-useful seat count rather than rate×raw-incidents.

O-SEATSIZE: also floor on non-generated scope path count — recipe-stripped
stories can own near-zero findings while carrying dozens of harvest/reimplement
files; incident-only arithmetic inverted S02 (budget 3 / 32 tasks) and left
S05 (findings: -) at the bare rate minimum.

  inc_budget   = rate * max(1, ceil(incidents / INC_UNIT))   if incidents else 0
  scope_budget = max(rate, ceil(scope_paths * rate / SCOPE_UNIT))  if scope else 0
  expected     = max(inc_budget, scope_budget, rate)

SCOPE_UNIT default 2 (SEAT_BUDGET_SCOPE_PER_UNIT).

Publish as roadmap `- seat-budget: N` + brief; O-LOGBRIEF banner; supervisor
escalates (debt-freeze) when actual story seats exceed N × OVER_FACTOR
(default 2).

O-SEATBRAKE: when the live plan has more than SEAT_BUDGET_BRAKE_TASKS tasks
(default 14 — the pre-char/convert calibration band), the overrun ceiling is
also floored at tasks × SEAT_BUDGET_TASK_HEADROOM (default 6). That lifts
42-task repository stories (freeze was 210 under incident×2 alone) without
loosening 6–14-task stories.

Usage:
  seat-budget.py expected --kind reimplement --incidents 51 [--scope-paths N]
  seat-budget.py from-story <roadmap.md> <findings-inventory.md> <S0N>
  seat-budget.py check-overrun --sid S03 [--budget N] [--factor F] [--tasks N]
"""
from __future__ import annotations

import argparse
import glob
import math
import os
import re
import sys
from pathlib import Path

RATES = {
    "rename": 1,
    "reimplement": 5,
    "mixed": 5,
}

# O-SCOPENOGEN / O-SEATSIZE — ignore Maven/Gradle build outs in scope counts
_GENERATED_SCOPE_RE = re.compile(
    r"(?:^|/)(?:target|build)(?:/|$)|(?:^|/)generated-sources/"
)


def unit_size() -> int:
    try:
        n = int(os.environ.get("SEAT_BUDGET_INCIDENTS_PER_UNIT", "10"))
    except ValueError:
        n = 10
    return max(1, n)


def scope_unit_size() -> int:
    """Paths per scope-budget unit (O-SEATSIZE). Default 2."""
    try:
        n = int(os.environ.get("SEAT_BUDGET_SCOPE_PER_UNIT", "2"))
    except ValueError:
        n = 2
    return max(1, n)


def over_factor() -> float:
    try:
        return float(os.environ.get("SEAT_BUDGET_OVER_FACTOR", "2"))
    except ValueError:
        return 2.0


def brake_task_threshold() -> int:
    """Task counts above this get the O-SEATBRAKE headroom floor (default 14)."""
    try:
        return int(os.environ.get("SEAT_BUDGET_BRAKE_TASKS", "14"))
    except ValueError:
        return 14


def task_headroom() -> float:
    """Min seats/task before overrun freeze on large plans (O-SEATBRAKE)."""
    try:
        return float(os.environ.get("SEAT_BUDGET_TASK_HEADROOM", "6"))
    except ValueError:
        return 6.0


def count_plan_tasks(sid: str, root: str = ".") -> int:
    """Count #### T-* headings in specs/<sid>-*/tasks.md (O-SEATBRAKE)."""
    patterns = [
        os.path.join(root, "specs", f"{sid}-*", "tasks.md"),
        os.path.join(root, "specs", sid, "tasks.md"),
    ]
    paths: list[str] = []
    for pat in patterns:
        paths.extend(glob.glob(pat))
    if not paths:
        return 0
    try:
        text = open(paths[0], encoding="utf-8", errors="replace").read()
    except OSError:
        return 0
    # O-M4COMPOSITE / O-T6dTCHEADING: count TC-* + T-NNN + legacy headings.
    try:
        from task_contract import HEADING_TASK_ID_ATOM  # type: ignore
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from task_contract import HEADING_TASK_ID_ATOM  # type: ignore
    return len(
        re.findall(
            rf"(?m)^#{{2,6}}\s+(?:{HEADING_TASK_ID_ATOM})",
            text,
        )
    )


def overrun_limit(
    budget: int, tasks: int = 0, factor: float | None = None
) -> float:
    """Effective seat ceiling: budget×factor, floored for large task counts."""
    f = over_factor() if factor is None else float(factor)
    limit = float(max(0, int(budget))) * f
    t = max(0, int(tasks))
    if t > brake_task_threshold():
        limit = max(limit, float(t) * task_headroom())
    return limit


def is_generated_scope_path(path: str) -> bool:
    """True for build-output paths that must not inflate seat budgets."""
    p = (path or "").replace("\\", "/").lstrip("./")
    return bool(_GENERATED_SCOPE_RE.search(p))


def scope_path_count(scope: str) -> int:
    """Count comma-separated scope paths excluding generated build outs."""
    n = 0
    for part in (scope or "").split(","):
        p = part.strip()
        if not p or p.startswith("<!--"):
            continue
        if is_generated_scope_path(p):
            continue
        n += 1
    return n


def expected_budget(kind: str, incidents: int, scope_paths: int = 0) -> int:
    """kind × max(incident units, scope floor) → expected seats (O-SEATSIZE)."""
    rate = RATES.get((kind or "").lower().strip())
    if rate is None:
        raise ValueError(f"unknown kind '{kind}' (want rename|reimplement|mixed)")
    inc = max(0, int(incidents))
    scope = max(0, int(scope_paths))
    if inc:
        inc_budget = rate * max(1, math.ceil(inc / unit_size()))
    else:
        inc_budget = 0
    if scope:
        # ceil(scope * rate / SCOPE_UNIT), but never below bare rate
        scope_budget = max(rate, math.ceil(scope * rate / scope_unit_size()))
    else:
        scope_budget = 0
    return max(inc_budget, scope_budget, rate)


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
    """True when brief publishes seat-budget N (bare, bold, or `N` code span).

    O-M2COMPOSEBOOK: compose emits `- **seat-budget**: \`N\``; the matcher must
    accept that form so lint does not false-RED a correctly published budget.
    """
    return bool(
        re.search(
            rf"(?i)(?:\*\*)?(?:seat-budget|seat budget)(?:\*\*)?\s*[:=]\s*`?{n}`?\b",
            btext,
        )
    )


def count_actual_seats(sid: str) -> int:
    """Story-keyed OpenCode JSON seat files (same metric as O-LOGEPILOG COST)."""
    return len(glob.glob(f"/tmp/oc-{sid}-*.json"))


def cmd_expected(args: argparse.Namespace) -> int:
    print(
        expected_budget(
            args.kind,
            args.incidents,
            scope_paths=getattr(args, "scope_paths", 0) or 0,
        )
    )
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
    scope_n = scope_path_count(fields.get("scope") or "")
    n = expected_budget(kind, inc, scope_paths=scope_n)
    declared = parse_seat_budget_field(fields.get("seat-budget"))
    print(
        f"{n}\tkind={kind}\tincidents={inc}\tscope_paths={scope_n}\t"
        f"declared={declared if declared is not None else '-'}"
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
    tasks = (
        args.tasks
        if getattr(args, "tasks", None) is not None
        else count_plan_tasks(sid)
    )
    actual = count_actual_seats(sid)
    limit = overrun_limit(budget, tasks=tasks, factor=factor)
    print(
        f"O-SEATBUDGET: {sid} actual={actual} budget={budget} "
        f"factor={factor} tasks={tasks} limit={limit:g}"
        + (
            " (O-SEATBRAKE task-headroom)"
            if tasks > brake_task_threshold()
            and limit > float(budget) * float(factor)
            else ""
        )
    )
    if actual > limit:
        print(
            f"O-SEATBUDGET: OVERRUN {sid} actual={actual} > limit={limit:g} "
            f"(budget={budget}×{factor:g}, tasks={tasks}) — escalate",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="O-SEATBUDGET / ARCH A5")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser(
        "expected", help="print expected seats for kind×incidents×scope (O-SEATSIZE)"
    )
    p1.add_argument("--kind", required=True)
    p1.add_argument("--incidents", type=int, required=True)
    p1.add_argument(
        "--scope-paths",
        type=int,
        default=0,
        help="non-generated scope path count (O-SEATSIZE floor)",
    )
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
    p3.add_argument(
        "--tasks",
        type=int,
        default=None,
        help="plan task count (default: count #### T-* in specs/<sid>-*/tasks.md)",
    )
    p3.set_defaults(func=cmd_check_overrun)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
