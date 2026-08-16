#!/usr/bin/env python3
"""WC-5 — mta_rescan must prove the analyzer ran after M3, not that a handoff file exists.

v19 M5 named the rescan six times, ran check-findings-handoff.py only, and
wrote PASS. Presence of findings-handoff.json is not a rescan.

Requires:
  * evidence/mta-findings.json execution_evidence.analyzer_ran == true
  * input_digest and normalized_at present
  * input_digest newer than the M1 snapshot (a copy of M1 without a new
    run fails)
  * normalized_at newer than the last M3 complete-exit-ok.json stamped_at
    when any M3 completion exists

--snapshot-m1 writes evidence/derived/m1-findings-digest.json if absent
(called from mta-analyze-legacy.sh after the first normalize). M5 assert
never snapshots.

Usage:
  python3 assert-mta-rescan.py ROOT
  python3 assert-mta-rescan.py ROOT --findings evidence/mta-findings.json
  python3 assert-mta-rescan.py ROOT --snapshot-m1 --findings PATH
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "rhoai3.m1-findings-digest/v1"
SNAPSHOT_REL = "evidence/derived/m1-findings-digest.json"
FINDINGS_REL = "evidence/mta-findings.json"

EXIT_CODES = """Exit codes:
  0  pass — analyzer_ran and digest/timestamp prove a post-M3 rescan,
     or --snapshot-m1 wrote/kept the M1 snapshot
  1  BLOCK — missing findings, analyzer did not run, copy of M1, or
     stamp not newer than last M3 completion
  2  usage / harness defect
"""


def parse_ts(raw: object) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: not an object")
    return data


def snapshot_payload(findings: dict, findings_path: Path) -> dict:
    ev = findings.get("execution_evidence") if isinstance(
        findings.get("execution_evidence"), dict
    ) else {}
    return {
        "schema": SCHEMA,
        "findings_path": str(findings_path),
        "input_digest": str(ev.get("input_digest") or ""),
        "normalized_at": str(findings.get("normalized_at") or ""),
        "analyzer_ran": bool(ev.get("analyzer_ran")),
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def last_m3_complete_ts(root: Path) -> datetime | None:
    runs = root / "evidence" / "runs"
    if not runs.is_dir():
        return None
    best: datetime | None = None
    for path in runs.glob("*/complete-exit-ok.json"):
        try:
            data = load_json(path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        ts = parse_ts(data.get("stamped_at"))
        if ts is None:
            continue
        if best is None or ts > best:
            best = ts
    return best


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument(
        "--findings",
        default=FINDINGS_REL,
        help="dest-relative or absolute mta-findings.json",
    )
    ap.add_argument(
        "--snapshot-m1",
        action="store_true",
        help="write M1 digest snapshot if absent (M1 analyze path only)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    findings_path = Path(args.findings)
    if not findings_path.is_absolute():
        findings_path = root / findings_path
    if not findings_path.is_file():
        print(f"FAIL: mta findings missing: {findings_path}", file=sys.stderr)
        return 1
    try:
        findings = load_json(findings_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL: unreadable findings {findings_path}: {exc}", file=sys.stderr)
        return 1

    snap_path = root / SNAPSHOT_REL
    if args.snapshot_m1:
        snap_path.parent.mkdir(parents=True, exist_ok=True)
        if snap_path.is_file():
            print(f"OK: M1 findings digest snapshot already present ({SNAPSHOT_REL})")
            return 0
        snap_path.write_text(
            json.dumps(snapshot_payload(findings, findings_path), indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"OK: wrote {SNAPSHOT_REL}")
        return 0

    ev = findings.get("execution_evidence")
    if not isinstance(ev, dict):
        print(
            "FAIL: mta_rescan: execution_evidence missing "
            "(handoff presence is not a rescan; WC-5)",
            file=sys.stderr,
        )
        return 1
    if ev.get("analyzer_ran") not in (True, "true", "yes", 1):
        print(
            "FAIL: mta_rescan: execution_evidence.analyzer_ran is not true "
            "(WC-5: the analyzer must have run)",
            file=sys.stderr,
        )
        return 1
    digest = str(ev.get("input_digest") or "").strip()
    normalized_at = str(findings.get("normalized_at") or "").strip()
    if not digest:
        print("FAIL: mta_rescan: execution_evidence.input_digest missing", file=sys.stderr)
        return 1
    if not normalized_at:
        print("FAIL: mta_rescan: normalized_at missing", file=sys.stderr)
        return 1
    if "/fixtures/admission/" in str(findings_path).replace("\\", "/"):
        print(
            "FAIL: mta_rescan: findings path is an admission fixture "
            "(INCONCLUSIVE_FIXTURE; B-5/WC-5)",
            file=sys.stderr,
        )
        return 1

    if not snap_path.is_file():
        print(
            f"FAIL: mta_rescan: missing {SNAPSHOT_REL} — cannot prove this "
            "run is newer than M1 (first analyze must --snapshot-m1)",
            file=sys.stderr,
        )
        return 1
    try:
        snap = load_json(snap_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL: mta_rescan: unreadable M1 snapshot: {exc}", file=sys.stderr)
        return 1
    snap_digest = str(snap.get("input_digest") or "").strip()
    if snap_digest and digest == snap_digest:
        print(
            "FAIL: mta_rescan: input_digest equals M1 snapshot — a copy of "
            "M1 without a new analyzer run is not a rescan (WC-5)",
            file=sys.stderr,
        )
        return 1

    ts = parse_ts(normalized_at)
    if ts is None:
        print(
            f"FAIL: mta_rescan: normalized_at={normalized_at!r} unparseable",
            file=sys.stderr,
        )
        return 1
    last_m3 = last_m3_complete_ts(root)
    if last_m3 is not None and ts <= last_m3:
        print(
            f"FAIL: mta_rescan: normalized_at {normalized_at} is not newer "
            f"than last M3 complete-exit-ok {last_m3.strftime('%Y-%m-%dT%H:%M:%SZ')} "
            "(WC-5)",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: mta_rescan analyzer_ran digest={digest[:16]}… "
        f"normalized_at={normalized_at} (newer than M1"
        + (f" and last M3 {last_m3.strftime('%Y-%m-%dT%H:%M:%SZ')}" if last_m3 else "")
        + ")"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
