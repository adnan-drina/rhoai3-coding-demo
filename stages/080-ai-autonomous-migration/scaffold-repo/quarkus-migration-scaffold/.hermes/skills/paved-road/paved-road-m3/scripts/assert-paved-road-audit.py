#!/usr/bin/env python3
"""Thin CLI: official-log + KEEP audit for this paved-road kind.

Logic lives in ``.hermes/lib/paved_road.py``. Default ``--steps`` is this
skill's ``steps.json``.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _ensure_hermes_lib() -> None:
    p = Path(__file__).resolve()
    for parent in p.parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            s = str(lib)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()
from paved_road import audit_paths, invalidate_audit_receipt, resolve_log, write_audit_receipt  # noqa: E402


def _satisfied_audit(task_id: str, root: Path, log: Path, steps: Path) -> int | None:
    """outcome-board/v2: an outcome whose obligations another outcome's commit
    discharged has no loop step to grade (``issue`` recorded it SATISFIED and
    told the worker not to run the loop). Its evidence is that harness record,
    re-judged here on the current tree. None when this is not such a card."""
    try:
        from planner import native_control as NC
        board = NC.board_for(root)
        recs = NC._accept_records(board, task_id)
        if not recs or not recs[-1].get("satisfied_by"):
            return None
        role, _run, oid, plan, node = NC.node_context(board, task_id)
    except Exception:  # noqa: BLE001 - not a native card: the log audit decides
        return None
    write_audit_receipt(log, None, steps_path=steps, root=root)
    ok, why = NC.outcome_acceptance(root, board, task_id, plan, node)
    changed = NC.changed_product_paths(root, NC._head(root))
    if role != "repair" or not ok or changed:
        print("FAIL: PAVED_ROAD kind=m3-loop satisfied card %s: %s" % (
            task_id, why if not ok else ("product edits in the tree: %s" % ", ".join(changed[:4]) if changed else role)),
            file=sys.stderr)
        write_audit_receipt(log, 1, steps_path=steps, root=root)
        return 1
    by = recs[-1]["satisfied_by"]
    print("OK: PAVED_ROAD kind=m3-loop artifact=satisfied card=%s outcome=%s discharged_by=%s (%s, commit %s); %s"
          % (task_id, oid, by.get("outcome"), by.get("task"), str(by.get("commit") or "")[:12], why))
    write_audit_receipt(log, 0, steps_path=steps, root=root)
    return 0

SKILL = Path(__file__).resolve().parents[1]
STEPS = SKILL / "steps.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("task_id", nargs="?", help="t_… (reads $HERMES_HOME/kanban/logs)")
    ap.add_argument(
        "--log",
        type=Path,
        help="official log path (workshop fixture; dest-14 harvested lines)",
    )
    ap.add_argument(
        "--root",
        type=Path,
        required=True,
        help="workspace root for KEEP paths",
    )
    ap.add_argument(
        "--steps",
        type=Path,
        default=STEPS,
        help="steps.json (default: this skill)",
    )
    args = ap.parse_args(argv)
    log = resolve_log(args.task_id, args.log)
    if log is None:
        # V17-6: no log to audit is not "still green from last time"
        invalidate_audit_receipt(args.task_id or os.environ.get("HERMES_KANBAN_TASK"))
        print("FAIL: pass a t_* id, $HERMES_KANBAN_TASK, or --log to an existing official kanban log", file=sys.stderr)
        return 2
    task = args.task_id or os.environ.get("HERMES_KANBAN_TASK") or ""
    if task and args.log is None:
        rc = _satisfied_audit(task, args.root.resolve(), log, args.steps)
        if rc is not None:
            return rc
    return audit_paths(log, args.root, args.steps)


if __name__ == "__main__":
    raise SystemExit(main())
