#!/usr/bin/env python3
"""M4 char→convert waves (build step C / O-M4WAVE).

Wave A = characterize tasks. Wave B = everything else (convert/harvest/…).
Scheduling: complete all wave-A tasks in a story before dispatching wave B.
Wave membership is derived from typed ``kind`` (not a second authored field).

Usage:
  m4_wave.py wave --task TID [--model path]
  m4_wave.py order --ids TID [TID ...] [--model path]
  m4_wave.py blockers --ids TID [TID ...] --committed TID [TID ...] [--model path]
  m4_wave.py check-dispatch --task TID --ids ... --committed ... [--model path]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("SENSOR_ROOT", ".")).resolve()


def _load_model(path: str | None) -> dict:
    p = Path(path) if path else ROOT / "migration" / "model.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _tasks_by_id(model: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for t in model.get("tasks") or []:
        tid = str(t.get("id") or "")
        if tid:
            out[tid] = t
    return out


def wave_for_task(t: dict | None, tid: str = "") -> str:
    """A = characterize; B = convert/other; INVALID = missing typed kind.

    W4-737 §5 — do not prose-key on ``-TC-`` in the id. Missing ``kind`` is
    INVALID_INPUT (M3-owned), logged by name every time (O-M4WAVE-KINDABSENT).
    """
    if t is None:
        print(f"O-M4WAVE-KINDABSENT tid={tid} reason=no-model-row", file=sys.stderr)
        return "INVALID"
    kind = str(t.get("kind") or "").strip().lower()
    if not kind:
        print(f"O-M4WAVE-KINDABSENT tid={tid} reason=empty-kind", file=sys.stderr)
        return "INVALID"
    if kind == "characterize":
        return "A"
    return "B"


def order_ids(ids: list[str], by_id: dict[str, dict]) -> list[str]:
    """Stable partition: wave A, then B; INVALID last (still visible)."""
    a, b, bad = [], [], []
    for i in ids:
        w = wave_for_task(by_id.get(i), i)
        if w == "A":
            a.append(i)
        elif w == "INVALID":
            bad.append(i)
        else:
            b.append(i)
    return a + b + bad


def open_wave_a(ids: list[str], committed: set[str], by_id: dict[str, dict]) -> list[str]:
    """Uncommitted characterize tasks still blocking wave B."""
    out = []
    for i in ids:
        if wave_for_task(by_id.get(i), i) != "A":
            continue
        if i in committed:
            continue
        out.append(i)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="O-M4WAVE char/convert wave helper")
    ap.add_argument("cmd", choices=("wave", "order", "blockers", "check-dispatch"))
    ap.add_argument("--task", default="")
    ap.add_argument("--ids", nargs="*", default=[])
    ap.add_argument("--committed", nargs="*", default=[])
    ap.add_argument("--model", default="")
    args = ap.parse_args()
    model = _load_model(args.model or None)
    by_id = _tasks_by_id(model)
    committed = set(args.committed or [])

    if args.cmd == "wave":
        tid = args.task or (args.ids[0] if args.ids else "")
        if not tid:
            print("missing --task", file=sys.stderr)
            return 2
        print(wave_for_task(by_id.get(tid), tid))
        return 0

    if args.cmd == "order":
        ids = list(args.ids or [])
        print(" ".join(order_ids(ids, by_id)))
        return 0

    if args.cmd == "blockers":
        ids = list(args.ids or [])
        open_a = open_wave_a(ids, committed, by_id)
        print(" ".join(open_a))
        return 0

    # check-dispatch
    tid = args.task
    if not tid:
        print("missing --task", file=sys.stderr)
        return 2
    ids = list(args.ids or [])
    w = wave_for_task(by_id.get(tid), tid)
    if w == "INVALID":
        print(f"BLOCK wave=INVALID missing kind on {tid} (O-M4WAVE-KINDABSENT → M3)", file=sys.stderr)
        print(f"BLOCK KINDABSENT {tid}")
        return 1
    if w == "A":
        print("OK wave=A")
        return 0
    open_a = open_wave_a(ids, committed, by_id)
    if open_a:
        print(f"BLOCK wave=B open_char={' '.join(open_a)}", file=sys.stderr)
        print(f"BLOCK {' '.join(open_a)}")
        return 1
    print("OK wave=B")
    return 0


if __name__ == "__main__":
    sys.exit(main())
