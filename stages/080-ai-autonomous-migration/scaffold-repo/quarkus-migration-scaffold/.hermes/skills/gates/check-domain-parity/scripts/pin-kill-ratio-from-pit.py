#!/usr/bin/env python3
"""Pin G-1 kill-ratio under dual-denominator rule (plan #8 / AD-H §18.0¶5).

Sole attempted ratio (killed/attempted) is forbidden as the PASS predicate —
deleting survivor-covering tests raises it (NO_COVERAGE leaves denominator).

M5 kill-ratio PASS requires all of:
  1. generated > 0 (W2 §5 volume)
  2. coverage floor: attempted/generated >= coverage_min
  3. kill strength: killed/attempted >= kill_attempted_min
  4. optional stringency: killed/generated >= kill_generated_min (when set)
Always report killed/generated. Bar source (AD-H §18.0¶5 / Architect
E-20260808T125536Z):
  - ratchet_from_measured — floors as margin under this tree's score (record
    measured_* + margin_*); prevents regression; not an engineering target
  - declared_engineering_target — bars sourced outside this subject's score
  - measured_from_this_run at equality — forbidden (script refuses)

Usage:
  pin-kill-ratio-from-pit.py <mutations.xml> -o evidence/derived/g1-kill-ratio-pin.json \\
    --coverage-min 0.41 --kill-attempted-min 0.60 --kill-generated-min 0.38 \\
    --source ratchet_from_measured \\
    --rationale "Architect E-… ratchet margins under live pack"
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
    generated = len(mutants)
    attempted = killed + survived + timed_out
    kill_attempted = (killed / attempted) if attempted > 0 else None
    coverage = (attempted / generated) if generated > 0 else None
    kill_generated = (killed / generated) if generated > 0 else None
    return {
        "mutations_total": generated,
        "generated": generated,
        "by_status": by_status,
        "killed": killed,
        "survived": survived,
        "timed_out": timed_out,
        "no_coverage": no_cov,
        "not_started": not_started,
        "attempted": attempted,
        "coverage_ratio": coverage,
        "kill_attempted_ratio": kill_attempted,
        "kill_generated_ratio": kill_generated,
        "kill_ratio": kill_attempted,
        "source": str(path),
    }


def evaluate(
    stats: dict,
    coverage_min: float,
    kill_attempted_min: float,
    kill_generated_min: float | None,
) -> dict:
    generated = int(stats["generated"])
    attempted = int(stats["attempted"])
    killed = int(stats["killed"])
    coverage = stats["coverage_ratio"]
    kill_att = stats["kill_attempted_ratio"]
    kill_gen = stats["kill_generated_ratio"]
    reasons: list[str] = []
    if generated <= 0:
        reasons.append("generated==0 (W2 §5 vacuity)")
    if attempted <= 0:
        reasons.append("attempted==0 (no killing population)")
    if coverage is None or coverage < coverage_min:
        reasons.append(
            f"coverage_floor FAIL: attempted/generated={coverage} < coverage_min={coverage_min}"
        )
    if kill_att is None or kill_att < kill_attempted_min:
        reasons.append(
            f"kill_strength FAIL: killed/attempted={kill_att} < kill_attempted_min={kill_attempted_min}"
        )
    if kill_generated_min is not None:
        if kill_gen is None or kill_gen < kill_generated_min:
            reasons.append(
                f"kill_generated FAIL: killed/generated={kill_gen} < kill_generated_min={kill_generated_min}"
            )
    return {
        "pass": not reasons,
        "coverage_ratio": coverage,
        "kill_attempted_ratio": kill_att,
        "kill_generated_ratio": kill_gen,
        "killed": killed,
        "attempted": attempted,
        "generated": generated,
        "fail_reasons": reasons,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mutations_xml", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--story-id", default="B-OWNER-PET-1")
    ap.add_argument(
        "--scope",
        default="measured live PIT slice",
    )
    ap.add_argument("--coverage-min", type=float, required=True)
    ap.add_argument("--kill-attempted-min", type=float, required=True)
    ap.add_argument(
        "--kill-generated-min",
        type=float,
        default=None,
        help="optional stringency floor killed/generated (Architect before first M5 ACCEPT)",
    )
    ap.add_argument("--rationale", required=True)
    ap.add_argument(
        "--source",
        choices=("ratchet_from_measured", "declared_engineering_target"),
        required=True,
        help="AD-H §18.0¶5 bar source (Architect E-20260808T125536Z)",
    )
    ap.add_argument(
        "--invalidate-prior",
        default="prior dual pin coverage_min=0.25 without kill_generated_min (stringency raise)",
    )
    args = ap.parse_args()
    if not args.mutations_xml.is_file():
        print(f"FAIL: missing {args.mutations_xml}", file=sys.stderr)
        return 1
    if args.coverage_min <= 0 or args.coverage_min > 1:
        print("FAIL: coverage-min must be in (0,1]", file=sys.stderr)
        return 1
    if args.kill_attempted_min <= 0 or args.kill_attempted_min > 1:
        print("FAIL: kill-attempted-min must be in (0,1]", file=sys.stderr)
        return 1
    if args.kill_generated_min is not None and (
        args.kill_generated_min <= 0 or args.kill_generated_min > 1
    ):
        print("FAIL: kill-generated-min must be in (0,1]", file=sys.stderr)
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

    cov = stats["coverage_ratio"]
    katt = stats["kill_attempted_ratio"]
    kgen = stats["kill_generated_ratio"]
    if cov is not None and abs(cov - args.coverage_min) < 1e-9:
        print(
            "FAIL: coverage_min equals measured coverage (circular measured_from_this_run)",
            file=sys.stderr,
        )
        return 1
    if katt is not None and abs(katt - args.kill_attempted_min) < 1e-9:
        print(
            "FAIL: kill_attempted_min equals measured kill strength (circular)",
            file=sys.stderr,
        )
        return 1
    if (
        args.kill_generated_min is not None
        and kgen is not None
        and abs(kgen - args.kill_generated_min) < 1e-9
    ):
        print(
            "FAIL: kill_generated_min equals measured kill_generated (circular)",
            file=sys.stderr,
        )
        return 1

    ev = evaluate(
        stats, args.coverage_min, args.kill_attempted_min, args.kill_generated_min
    )
    threshold = {
        "coverage_min": args.coverage_min,
        "kill_attempted_min": args.kill_attempted_min,
        "rule": (
            "PASS iff generated>0 AND attempted>0 AND "
            "attempted/generated >= coverage_min AND "
            "killed/attempted >= kill_attempted_min"
            + (
                " AND killed/generated >= kill_generated_min"
                if args.kill_generated_min is not None
                else ""
            )
            + "; always report killed/generated; "
            "sole killed/attempted PASS predicate FORBIDDEN"
        ),
        "source": args.source,
        "rationale": args.rationale,
        "folklore": False,
    }
    if args.kill_generated_min is not None:
        threshold["kill_generated_min"] = args.kill_generated_min
    if args.source == "ratchet_from_measured":
        threshold["measured_coverage"] = cov
        threshold["measured_kill_attempted"] = katt
        threshold["measured_kill_generated"] = kgen
        if cov is not None:
            threshold["margin_coverage"] = cov - args.coverage_min
        if katt is not None:
            threshold["margin_kill_attempted"] = katt - args.kill_attempted_min
        if args.kill_generated_min is not None and kgen is not None:
            threshold["margin_kill_generated"] = kgen - args.kill_generated_min
    pin_authority_extra = (
        "; pin-source E-20260808T125536Z"
        if args.source == "ratchet_from_measured"
        else ""
    )

    pin = {
        "schema": "migration/g1-kill-ratio-pin/v2-dual-denominator",
        "authority": "EXECUTION-LIVE-VALIDATION-PLAN #8; W2 §5/§9; AD-H §18.0¶5; "
        "Architect decide E-20260808T115649Z; stringency E-20260808T120152Z/"
        "E-20260808T121549Z/E-20260808T123742Z"
        + pin_authority_extra,
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "story_id": args.story_id,
        "scope": args.scope,
        "tool": "pitest-maven",
        "pinned_version": "1.25.5",
        "mode": "live_mutationCoverage",
        "prior_pin": {
            "status": "SUPERSEDED",
            "reason": args.invalidate_prior,
            "defect": "coverage_min=0.25 admitted ~75% NO_COVERAGE; stringency "
            "required before first M5 ACCEPT",
        },
        "measurement": stats,
        "threshold": threshold,
        "evaluation_against_measurement": ev,
        "waiver_path": {
            "token": None,
            "authority": "none",
            "effect": "deleted — M5 ACCEPT requires kill-ratio PASS+pin; "
            "a waiver cannot author ACCEPT (B-4/C-3(a))",
            "location": None,
        },
        "m5_note": "Pinning does NOT grant M5 ACCEPT — plan #1e still required "
        "(G-4 both-modes + dual-denominator kill-ratio PASS).",
        "status": "PINNED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
    print(
        f"OK: pin coverage_min={args.coverage_min} "
        f"kill_attempted_min={args.kill_attempted_min} "
        f"kill_generated_min={args.kill_generated_min} "
        f"(measured coverage={cov} kill_attempted={katt} "
        f"kill_generated={kgen}) eval_pass={ev['pass']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
