#!/usr/bin/env python3
"""O-ADR47-1c — minimal phase rewind primitive (ADR-47 / W4-723).

Not a lifecycle state machine. On INVALID_INPUT (e.g. M4 consumer-assert
refuse), record ``next_stage = owning_phase`` and let outer-loop continue
there. Cap re-entries to stop ADR-46 §7.3 livelock (same defect → refuse →
rewind → same defect).

Ledger: migration/phase-rewind.json

Usage:
  phase_rewind.py request --from M4 --to M3 --reason CODE [--story S0N] [--detail PATH]
  phase_rewind.py status
  phase_rewind.py apply     # mark story UNSPECIFIED (clear filled) + bump attempt
  phase_rewind.py clear
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("SENSOR_ROOT", ".")).resolve()
LEDGER = ROOT / "migration" / "phase-rewind.json"
def _max_attempts(prev: dict | None = None) -> int:
    if prev and prev.get("max_attempts"):
        try:
            return int(prev["max_attempts"])
        except (TypeError, ValueError):
            pass
    return int(os.environ.get("PHASE_REWIND_MAX", "3"))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _load() -> dict:
    if not LEDGER.is_file():
        return {}
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save(data: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def request(from_phase: str, to_phase: str, reason: str, story: str, detail: str) -> int:
    prev = _load()
    attempt = int(prev.get("attempt") or 0)
    # Same story+reason continuing → bump; otherwise reset counter.
    if (
        prev.get("story") == story
        and prev.get("reason") == reason
        and prev.get("to_phase") == to_phase
    ):
        attempt += 1
    else:
        attempt = 1
    max_a = _max_attempts(prev if attempt > 1 else None)
    if attempt == 1:
        max_a = int(os.environ.get("PHASE_REWIND_MAX", "3"))
    data = {
        "oid": "O-ADR47-1c",
        "from_phase": from_phase,
        "to_phase": to_phase,
        "reason": reason,
        "story": story,
        "detail": detail,
        "attempt": attempt,
        "max_attempts": max_a,
        "requested_at": _now(),
        "status": "pending",
    }
    if attempt > max_a:
        data["status"] = "exhausted"
        _save(data)
        print(
            f"PHASE_REWIND:EXHAUSTED story={story} {from_phase}→{to_phase} "
            f"attempt={attempt}/{max_a} reason={reason} (ADR-46 §7.3 livelock)"
        )
        return 2
    _save(data)
    print(
        f"PHASE_REWIND:REQUESTED story={story} {from_phase}→{to_phase} "
        f"attempt={attempt}/{max_a} reason={reason}"
    )
    return 0


def _persist_rewind_fires(detail: str) -> int:
    """O-M3REWINDRSN — copy refuse fires into migration/ so M3 re-emit can consume them.

    /tmp/m4-consumer-assert.json is archived away; durable path is
    migration/m4-rewind-fires.json (task → surface members).
    """
    src = Path(detail) if detail else Path()
    if not src.is_file():
        # fall back to last known assert dump in migration/
        alt = ROOT / "migration" / "m4-consumer-assert-last.json"
        src = alt if alt.is_file() else src
    if not src.is_file():
        return 0
    try:
        payload = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    by_task: dict[str, list[str]] = {}
    for fire in payload.get("fires") or []:
        if str(fire.get("assert") or "") != "char_surface":
            continue
        tid = str(fire.get("task") or "")
        detail_s = str(fire.get("detail") or "")
        if not tid:
            continue
        # e.g. surface=['save'] or surface=['findById', 'findAll', 'save', 'delete']
        m = re.search(r"surface=\[([^\]]*)\]", detail_s)
        members: list[str] = []
        if m:
            members = [
                x.strip().strip("'\"")
                for x in m.group(1).split(",")
                if x.strip().strip("'\"")
            ]
        if not members:
            members = ["save"]  # characterize default verb; still forces clause change
        by_task[tid] = members
    out = ROOT / "migration" / "m4-rewind-fires.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "oid": "O-M3REWINDRSN",
                "source": str(src),
                "persisted_at": _now(),
                "by_task": by_task,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return len(by_task)


def _stamp_char_acceptance_from_fires(model: dict, story: str) -> int:
    """Rewrite characterize acceptance clauses from durable rewind fires."""
    fires_path = ROOT / "migration" / "m4-rewind-fires.json"
    if not fires_path.is_file():
        return 0
    try:
        fires = json.loads(fires_path.read_text(encoding="utf-8")).get("by_task") or {}
    except (OSError, json.JSONDecodeError):
        return 0
    if not fires:
        return 0
    n = 0
    for t in model.get("tasks") or []:
        tid = str(t.get("id") or "")
        sid = str(t.get("sid") or "")
        if story and not (sid == story or tid.startswith(story + "-")):
            continue
        members = fires.get(tid)
        if not members or str(t.get("kind") or "") != "characterize":
            continue
        simple = tid.rsplit("-", 1)[-1].replace("Char", "") if "Char" in tid else tid
        # Prefer Owns basename from task
        owns = [p for p in (t.get("owns") or []) if str(p).endswith("Test.java")]
        test_name = Path(str(owns[0])).name if owns else f"{simple}Test.java"
        clause = (
            f"Owns {test_name} invokes ≥1 of unit_keys public surface "
            f"({', '.join(members)}) — O-M3REWINDRSN / W4-708"
        )
        t["acceptance"] = [clause]
        t["filled"] = False
        t["goal_source"] = ""
        n += 1
    return n


def apply() -> int:
    data = _load()
    if not data or data.get("status") == "exhausted":
        print("PHASE_REWIND: nothing to apply")
        return 1
    story = str(data.get("story") or "")
    to_phase = str(data.get("to_phase") or "")
    if to_phase != "M3":
        print(f"PHASE_REWIND: apply only implements M3 today (got {to_phase})")
        return 1
    model_path = ROOT / "migration" / "model.json"
    if not model_path.is_file():
        print("PHASE_REWIND: missing model.json")
        return 1
    # O-M3REWINDRSN (W4-773): persist refuse fires before M3 re-emit
    n_fires = _persist_rewind_fires(str(data.get("detail") or ""))
    model = json.loads(model_path.read_text(encoding="utf-8"))
    n = 0
    for t in model.get("tasks") or []:
        tid = str(t.get("id") or "")
        sid = str(t.get("sid") or "")
        if story and not (sid == story or tid.startswith(story + "-")):
            continue
        if t.get("filled"):
            t["filled"] = False
            t["goal_source"] = ""
            n += 1
    n_stamp = _stamp_char_acceptance_from_fires(model, story)
    model_path.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")
    data["status"] = "applied"
    data["applied_at"] = _now()
    data["cleared_filled"] = n
    data["rewind_fires"] = n_fires
    data["acceptance_stamped"] = n_stamp
    _save(data)
    print(
        f"PHASE_REWIND:APPLIED story={story} → M3 cleared_filled={n} "
        f"fires={n_fires} acceptance_stamped={n_stamp} "
        f"attempt={data.get('attempt')}/{data.get('max_attempts')}"
    )
    return 0


def status() -> int:
    data = _load()
    if not data:
        print("PHASE_REWIND: idle")
        return 0
    print(json.dumps(data, indent=2))
    return 0 if data.get("status") != "exhausted" else 2


def clear() -> int:
    if LEDGER.is_file():
        LEDGER.unlink()
    print("PHASE_REWIND: cleared")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("request")
    r.add_argument("--from", dest="from_phase", required=True)
    r.add_argument("--to", dest="to_phase", required=True)
    r.add_argument("--reason", required=True)
    r.add_argument("--story", default="")
    r.add_argument("--detail", default="")
    sub.add_parser("apply")
    sub.add_parser("status")
    sub.add_parser("clear")
    args = ap.parse_args()
    if args.cmd == "request":
        return request(args.from_phase, args.to_phase, args.reason, args.story, args.detail)
    if args.cmd == "apply":
        return apply()
    if args.cmd == "status":
        return status()
    if args.cmd == "clear":
        return clear()
    return 1


if __name__ == "__main__":
    sys.exit(main())
