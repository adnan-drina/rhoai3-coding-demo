#!/usr/bin/env python3
"""Pin G-1 kill-ratio threshold from a live PIT mutations.xml (plan #8).

No folklore percentages. Reads measured KILLED / SURVIVED / TIMED_OUT /
NO_COVERAGE counts, computes kill_ratio over the killing population, and
writes a pin file. Zero mutants → REFUSE (vacuity closed, W2 §5).

Usage:
  pin-kill-ratio-from-pit.py <mutations.xml> -o migration/contracts/g1-kill-ratio-pin.json
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def count_mutations(path: Path) -> dict:
    tree = ET.parse(path)
    root = tree.getroot()
    mutants = [el for el in root.iter() if el.tag.endswith("mutation") or el.tag == "mutation"]
    by_status: dict[str, int] = {}
    for m in mutants:
        st = (m.attrib.get("status") or m.findtext("status") or "UNKNOWN").upper()
        by_status[st] = by_status.get(st, 0) + 1
    killed = by_status.get("KILLED", 0)
    survived = by_status.get("SURVIVED", 0)
    timed_out = by_status.get("TIMED_OUT", 0)
    no_cov = by_status.get("NO_COVERAGE", 0)
    not_started = by_status.get("NOT_STARTED", 0)
    # Killing population = mutants that tests were able to attempt
    # (exclude NOT_STARTED / dry-run). Survived + timed_out count against.
    attempted = killed + survived + timed_out
    kill_ratio = (killed / attempted) if attempted > 0 else None
    return {
        "mutations_total": len(mutants),
        "by_status": by_status,
        "killed": killed,
        "survived": survived,
        "timed_out": timed_out,
        "no_coverage": no_cov,
        "not_started": not_started,
        "attempted": attempted,
        "kill_ratio": kill_ratio,
        "source": str(path),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mutations_xml", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument(
        "--story-id",
        default="B-OWNER-PET-1",
        help="story id this pin applies to",
    )
    ap.add_argument(
        "--scope",
        default="Owner/Pet slice (measured live PIT)",
        help="human-readable scope note",
    )
    args = ap.parse_args()
    if not args.mutations_xml.is_file():
        print(f"FAIL: missing {args.mutations_xml}", file=sys.stderr)
        return 1
    stats = count_mutations(args.mutations_xml)
    if stats["mutations_total"] <= 0:
        print("FAIL: zero mutants — refuse vacuous pin (W2 §5)", file=sys.stderr)
        return 1
    if stats["not_started"] == stats["mutations_total"]:
        print(
            "FAIL: all mutants NOT_STARTED (dry-run only) — not a kill-ratio pin",
            file=sys.stderr,
        )
        return 1
    if stats["attempted"] <= 0:
        print(
            "FAIL: no attempted mutants (killed+survived+timed_out=0) — refuse pin",
            file=sys.stderr,
        )
        return 1

    # Pass line = measured kill_ratio floored to 4 decimal places.
    # M5 still requires kill_ratio >= this pin (and G-4 both-modes).
    measured = float(stats["kill_ratio"])
    pin_floor = round(measured, 4)
    pin = {
        "schema": "migration/g1-kill-ratio-pin/v1",
        "authority": "EXECUTION-LIVE-VALIDATION-PLAN #8; W2 §5; AD-H §18.0¶5",
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "story_id": args.story_id,
        "scope": args.scope,
        "tool": "pitest-maven",
        "pinned_version": "1.25.5",
        "mode": "live_mutationCoverage",
        "measurement": stats,
        "threshold": {
            "kill_ratio_min": pin_floor,
            "rule": "PASS iff attempted>0 AND killed/attempted >= kill_ratio_min; "
            "mutants_generated==0 for in-scope unit is FAIL (never 0/0 PASS)",
            "source": "measured_from_this_run",
            "folklore": False,
        },
        "waiver_path": {
            "token": "g1_kill_ratio_waiver",
            "authority": "Operator or deputy typed waiver only",
            "effect": "sole alternate M5 path when pin cannot be met; "
            "must name story_id + rationale + expiry/re_open_trigger",
            "location": "migration/acks/g1-kill-ratio-waiver-<story_id>.ack.yaml",
        },
        "m5_note": "Pinning does NOT grant M5 ACCEPT — plan #1e still required "
        "(G-4 both-modes + kill-ratio PASS vs this pin).",
        "status": "PINNED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
    print(
        f"OK: pinned kill_ratio_min={pin_floor} "
        f"(killed={stats['killed']} attempted={stats['attempted']} "
        f"total={stats['mutations_total']})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
