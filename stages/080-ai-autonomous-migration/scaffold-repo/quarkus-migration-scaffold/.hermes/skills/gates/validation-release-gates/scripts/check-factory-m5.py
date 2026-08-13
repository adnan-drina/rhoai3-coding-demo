#!/usr/bin/env python3
"""AD-H §18 — required oracle: factory must not contradict M5 ACCEPT.

Triggers when a factory advance/ship claim exists. Then requires a coherent
M5 ACCEPT verdict (or ack). Refuses factory ship if M5 is missing, REFUSE,
or INCONCLUSIVE.

Idle (exit 0) when no factory claim is present.

Usage:
  python3 check-factory-m5.py .
  python3 check-factory-m5.py /projects/modernized
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_CODES = """Exit codes:
  0  pass — factory claim is coherent with a full M5 ACCEPT, or gate idle
     (no factory claim present)
  1  BLOCK — factory claim without M5 ACCEPT, factory contradicting an M5
     REFUSE/INCONCLUSIVE, or an M5 ACCEPT that is not composition-complete
     (provisional / scoped / standing descopes / unpinned kill-ratio)
  2  usage / harness defect (bad or unknown argument)
"""


def load_items(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def factory_claims(root: Path) -> list[str]:
    claims: list[str] = []
    for d in (root / "migration/preflight", root / "migration/verdicts"):
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.json")):
            try:
                for obj in load_items(path):
                    if not isinstance(obj, dict):
                        continue
                    phase = str(obj.get("phase") or "").upper()
                    status = str(obj.get("status") or obj.get("state") or "").lower()
                    ship = obj.get("ship") in (True, "true", "yes", 1)
                    if phase == "FACTORY" or status in {"factory", "factory_ready", "push_main"}:
                        claims.append(str(path.relative_to(root)))
                    elif ship and phase in {"FACTORY", ""}:
                        claims.append(str(path.relative_to(root)))
            except Exception:
                continue
    for d in (root / "migration/tasks", root / "migration/kanban"):
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.json")):
            try:
                for obj in load_items(path):
                    if not isinstance(obj, dict):
                        continue
                    phase = str(obj.get("phase") or "").upper()
                    status = str(obj.get("status") or "").lower()
                    if phase == "FACTORY" and status in {
                        "done",
                        "complete",
                        "completed",
                        "shipped",
                        "closed",
                    }:
                        claims.append(str(path.relative_to(root)))
            except Exception:
                continue
    return claims


def m5_accept_state(root: Path) -> tuple[str, str, dict]:
    """Return (state, label, obj) where state is ACCEPT|REFUSE|INCONCLUSIVE|MISSING.

    ACCEPT here means **full** M5 ACCEPT (AD-H §18.0). Provisional is rejected.
    """
    best: tuple[str, str, dict] = ("MISSING", "", {})
    vdir = root / "migration/verdicts"
    if vdir.is_dir():
        for path in sorted(vdir.glob("*.json")):
            try:
                for obj in load_items(path):
                    if not isinstance(obj, dict):
                        continue
                    if str(obj.get("phase") or "").upper() != "M5":
                        continue
                    v = str(obj.get("verdict") or obj.get("gate_verdict") or "").upper()
                    if v in {"ACCEPT", "REFUSE", "INCONCLUSIVE"}:
                        best = (v, str(path.relative_to(root)), obj)
            except Exception:
                continue
    ack = root / "migration/acks/m5-accept.ack"
    if ack.is_file() and best[0] == "MISSING":
        return ("ACCEPT", str(ack.relative_to(root)), {"accept_kind": "full", "g1_kill_ratio_waiver": True})
    for d in (root / "migration/bodies", root / "migration/tasks"):
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                items = data if isinstance(data, list) else [data]
                for obj in items:
                    if not isinstance(obj, dict):
                        continue
                    body = obj.get("body") if isinstance(obj.get("body"), dict) else obj
                    if str(body.get("phase") or "").upper() != "FACTORY":
                        continue
                    refs = body.get("refs") or []
                    if isinstance(refs, list) and any(
                        isinstance(r, dict) and r.get("key") == "m5_accept" for r in refs
                    ):
                        if best[0] == "MISSING":
                            best = (
                                "ACCEPT",
                                str(path.relative_to(root)) + " (m5_accept ref)",
                                {"accept_kind": "full", "g1_kill_ratio_waiver": True},
                            )
            except Exception:
                continue
    return best


def full_accept_ok(obj: dict) -> str | None:
    """Return error string if M5 ACCEPT is not composition-complete, else None."""
    verdict = str(obj.get("verdict") or obj.get("gate_verdict") or "").upper().replace(
        "-", "_"
    )
    if verdict == "PROVISIONAL_ACCEPT":
        return "factory needs M5 ACCEPT, not PROVISIONAL_ACCEPT (AD-H §18.0)"
    if verdict == "SCOPED_ACCEPT":
        return (
            "factory needs full ACCEPT — SCOPED_ACCEPT is not factory-eligible "
            "(standing descopes; Architect E-20260809T113120Z)"
        )
    kind = str(obj.get("accept_kind") or obj.get("acceptKind") or "").lower()
    if kind == "provisional":
        return "M5 ACCEPT is provisional — factory needs full ACCEPT (AD-H §18.0)"
    if kind in {"scoped", "scoped_accept"}:
        return "factory needs full ACCEPT — accept_kind=scoped not eligible"
    if kind and kind not in {"full", ""}:
        return f"M5 ACCEPT accept_kind={kind!r} — need full"
    # Standing descopes block full ACCEPT even if accept_kind claims full
    try:
        descope = int(obj.get("entry_point_descope_count") or 0)
    except (TypeError, ValueError):
        descope = 0
    if descope > 0:
        return (
            f"entry_point_descope_count={descope} — full ACCEPT forbidden; "
            f"use SCOPED_ACCEPT (AD-H §18 / finding 3)"
        )
    kill = str(obj.get("g1_kill_ratio") or obj.get("g1KillRatio") or "").lower()
    pinned = obj.get("g1_kill_ratio_threshold_pinned") in (True, "true", "yes", 1)
    waiver = obj.get("g1_kill_ratio_waiver") in (True, "true", "yes", 1) or (
        isinstance(obj.get("operator_waiver"), dict)
        and obj["operator_waiver"].get("g1_kill_ratio") in (True, "true", "yes", 1)
    )
    if kill == "pass" and not pinned:
        return "g1_kill_ratio=PASS without threshold pin"
    if kill in {"", "pending_threshold"} and not waiver:
        return "M5 full ACCEPT needs kill-ratio PASS (pinned) or typed waiver"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="product root containing migration/preflight, verdicts, tasks (default: .)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    claims = factory_claims(root)
    if not claims:
        print("OK: no factory advance claim — M5-contradict oracle idle")
        return 0
    state, where, obj = m5_accept_state(root)
    if state == "MISSING":
        print(
            "FAIL: factory claim without M5 ACCEPT "
            f"(claims={claims}; AD-H §18 must_not_contradict_m5_accept)",
            file=sys.stderr,
        )
        return 1
    if state in {"REFUSE", "INCONCLUSIVE"}:
        print(
            f"FAIL: factory contradicts M5 {state} at {where} (AD-H §18)",
            file=sys.stderr,
        )
        return 1
    err = full_accept_ok(obj)
    if err:
        print(f"FAIL: factory vs {where}: {err}", file=sys.stderr)
        return 1
    print(f"OK: factory coherent with M5 full ACCEPT ({where}; claims={len(claims)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
