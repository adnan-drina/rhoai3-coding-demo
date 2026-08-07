#!/usr/bin/env python3
"""ADR-46 §3 / step 2b — derive typed edges, log only (do not dispatch).

Edge types (derived from model.units depends_on + task unit_keys):
  requires-type   task A’s unit imports unit owned by task B  → B before A
  characterizes   characterize task T covers unit U           → T before convert(U)

Log: migration/m4-edges-log.json
Sizing metric: convert↔convert edges that contradict current task-list order.

Usage:
  m4_edges.py derive [--model path] [--order TID ...] [--json path]
  m4_edges.py summary [--json path]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("SENSOR_ROOT", ".")).resolve()
DEFAULT_LOG = ROOT / "migration" / "m4-edges-log.json"


def _load_model(path: str | None) -> dict:
    p = Path(path) if path else ROOT / "migration" / "model.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _units_by_key(model: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for u in model.get("units") or []:
        k = u.get("key")
        if k:
            out[str(k)] = u
    return out


def _task_unit_keys(t: dict) -> list[str]:
    keys = t.get("unit_keys") or []
    if isinstance(keys, str):
        return [keys] if keys.strip() else []
    return [str(k) for k in keys if str(k).strip()]


def _is_characterize(t: dict) -> bool:
    return str(t.get("kind") or "").strip().lower() == "characterize"


def derive_edges(model: dict) -> list[dict]:
    """Derive characterizes + requires-type edges (specimen-agnostic)."""
    units = _units_by_key(model)
    tasks = [t for t in (model.get("tasks") or []) if t.get("id")]
    # unit_key → list of convert/other task ids that own it
    owners: dict[str, list[str]] = {}
    char_by_unit: dict[str, list[str]] = {}
    for t in tasks:
        tid = str(t["id"])
        for uk in _task_unit_keys(t):
            if _is_characterize(t):
                char_by_unit.setdefault(uk, []).append(tid)
            else:
                owners.setdefault(uk, []).append(tid)

    edges: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    def add(etype: str, src: str, dst: str, **extra: object) -> None:
        """src before dst (schedule constraint direction)."""
        key = (etype, src, dst)
        if key in seen or src == dst:
            return
        seen.add(key)
        row = {"type": etype, "before": src, "after": dst, **extra}
        edges.append(row)

    # characterizes: char task before any convert of same unit
    for uk, chars in char_by_unit.items():
        for conv in owners.get(uk) or []:
            for ch in chars:
                add(
                    "characterizes",
                    ch,
                    conv,
                    unit_key=uk,
                )

    # requires-type: if convert A's unit depends_on unit owned by convert B → B before A
    for t in tasks:
        if _is_characterize(t):
            continue
        tid = str(t["id"])
        for uk in _task_unit_keys(t):
            u = units.get(uk) or {}
            for dep in u.get("depends_on") or []:
                dep = str(dep)
                for owner in owners.get(dep) or []:
                    if owner == tid:
                        continue
                    add(
                        "requires-type",
                        owner,
                        tid,
                        from_unit=uk,
                        depends_on=dep,
                    )
    return edges


def order_violations(edges: list[dict], order: list[str]) -> list[dict]:
    """Edges whose before/after contradict the authored task order."""
    pos = {tid: i for i, tid in enumerate(order)}
    bad: list[dict] = []
    for e in edges:
        a, b = e["before"], e["after"]
        if a not in pos or b not in pos:
            continue
        if pos[a] > pos[b]:
            bad.append({**e, "order_index_before": pos[a], "order_index_after": pos[b]})
    return bad


def derive_and_log(
    model: dict,
    order: list[str] | None,
    log_path: Path,
) -> dict:
    edges = derive_edges(model)
    req = [e for e in edges if e["type"] == "requires-type"]
    cha = [e for e in edges if e["type"] == "characterizes"]
    # Default order = model task list order
    if not order:
        order = [str(t["id"]) for t in (model.get("tasks") or []) if t.get("id")]
    # Convert↔convert sizing: requires-type only (both ends in wave B)
    viol = order_violations(req, order)
    # Also note characterizes violations (should be 0 after O-M4WAVE reorder)
    char_viol = order_violations(cha, order)
    summary = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "log-only",
        "edge_count": len(edges),
        "requires_type": len(req),
        "characterizes": len(cha),
        "requires_type_order_violations": len(viol),
        "characterizes_order_violations": len(char_viol),
        "dispatch_from_edges": False,
        "note": (
            "O-ADR46-S3 / step 2b — edges derived for sizing; "
            "supervisor MUST NOT reorder from this log yet"
        ),
        "violation_samples": viol[:12],
        "edges": edges,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="O-ADR46-S3 log-only edge derive")
    ap.add_argument("cmd", choices=("derive", "summary"))
    ap.add_argument("--model", default="")
    ap.add_argument("--order", nargs="*", default=[])
    ap.add_argument("--json", default=str(DEFAULT_LOG))
    args = ap.parse_args()
    log_path = Path(args.json)

    if args.cmd == "summary":
        if not log_path.is_file():
            print("no edge log", file=sys.stderr)
            return 1
        d = json.loads(log_path.read_text(encoding="utf-8"))
        print(
            f"O-ADR46-S3 edges={d.get('edge_count')} "
            f"requires-type={d.get('requires_type')} "
            f"characterizes={d.get('characterizes')} "
            f"requires_type_violations={d.get('requires_type_order_violations')} "
            f"characterizes_violations={d.get('characterizes_order_violations')} "
            f"dispatch={d.get('dispatch_from_edges')}"
        )
        for v in (d.get("violation_samples") or [])[:8]:
            print(
                f"  VIOL {v.get('type')}: {v.get('before')} should precede "
                f"{v.get('after')} (depends_on={v.get('depends_on')})"
            )
        return 0

    model = _load_model(args.model or None)
    summary = derive_and_log(model, list(args.order or []), log_path)
    print(
        f"O-ADR46-S3:LOG-ONLY edges={summary['edge_count']} "
        f"requires-type={summary['requires_type']} "
        f"characterizes={summary['characterizes']} "
        f"requires_type_violations={summary['requires_type_order_violations']} "
        f"characterizes_violations={summary['characterizes_order_violations']} "
        f"log={log_path}"
    )
    for v in summary["violation_samples"][:8]:
        print(
            f"  VIOL requires-type: {v['before']} before {v['after']} "
            f"(unit {v.get('from_unit')} depends_on {v.get('depends_on')})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
