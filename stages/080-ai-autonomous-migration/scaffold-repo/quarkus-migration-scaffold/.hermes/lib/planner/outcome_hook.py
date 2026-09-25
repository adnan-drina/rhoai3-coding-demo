"""The K2 hook's outcome-board branch (called in-process by kernel/pre_tool_call.sh).

Serial-loop runs return None immediately and the hook behaves exactly as
before. The fast path reads two files and never runs git: no authority store,
and ``run-defaults.json`` does not name outcome-board/v1. For an outcome-board
run the phase, the write set and the completion rule come from the authority
records and the native board. They never come from the card body or from K2_*
environment overrides.

Decisions:
  kanban_block        always allowed (escalation is a legal result)
  kanban_complete     outcome_lifecycle.check_complete (records the intent first)
  request_review      M2: publication read-back must be green; assessment:
                      the implementer's terminator; repair outcome: refused
                      (an outcome completes on its acceptance, no review lane)
  product writes      outcome_lifecycle.check_write against the run-bound issue;
                      the authority store and harness state are never tool-written
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from planner.outcome_protocol import DEFAULTS, OUTCOME, STORE_FILE, describe, execution_gate, select_protocol


def active(root: str) -> bool:
    """Cheap: is this root possibly an outcome-board run?"""
    if not root:
        return False
    r = Path(root)
    if (r / STORE_FILE).exists():
        return True
    try:
        return OUTCOME.encode() in (r / DEFAULTS).read_bytes()
    except OSError:
        return False


def _ctx(root: str):
    from planner.outcome_lifecycle import Ctx
    from planner.outcome_native import KanbanNative
    from planner.outcome_store import Store
    store = Store(Path(root))
    native = KanbanNative(store.meta("native_db"))
    return Ctx(Path(root), store, native)


def _block(code: str, detail: str) -> dict[str, Any]:
    return {"action": "block", "code": code, "message": "%s: %s" % (code, detail)}


def terminator(root: str, *, kind: str, profile: str, env: dict[str, str],
               audit_green: Callable[[], bool]) -> dict[str, Any] | None:
    """kind in {complete, block, request_review}. None = not an outcome run."""
    if not active(root):
        return None
    sel = select_protocol(Path(root))
    if not sel.outcome:
        if (Path(root) / STORE_FILE).exists():
            return _block("PROTOCOL_MIXED", "serial-loop run carries an outcome-board store")
        return None
    if kind == "block":
        return {"action": "allow", "code": "BLOCK_ALLOWED"}
    gate = execution_gate(Path(root), sel)
    if gate:
        return _block(gate[0][0], describe(gate).splitlines()[0])
    task = (env.get("HERMES_KANBAN_TASK") or "").strip()
    try:
        run_id = int((env.get("HERMES_KANBAN_RUN_ID") or "0").strip() or 0)
    except ValueError:
        run_id = 0
    if not (Path(root) / STORE_FILE).exists():
        # before publication: the serial M1/M2 road governs (its audit requires publication)
        return None
    from planner.outcome_lifecycle import Refusal, _pub_by_task, check_complete
    try:
        ctx = _ctx(root)
        if kind == "complete":
            out = check_complete(ctx, task_id=task, run_id=run_id, profile=profile, audit_green=audit_green())
            return {"action": "allow", "code": "COMPLETE_ALLOWED", "intent": out.get("intent")}
        if kind == "request_review":
            if task == ctx.store.meta("m2_task"):
                from k4_graph import readback
                gaps = readback(ctx.store, ctx.native)
                if ctx.store.meta("publication_state") not in ("complete", "released") or gaps:
                    return _block("M2_PUBLICATION_INCOMPLETE", "; ".join(gaps[:3]) or ctx.store.meta("publication_state"))
                return {"action": "allow", "code": "M2_REVIEW_ALLOWED"}
            pub = _pub_by_task(ctx.store, task)
            if pub and pub["outcome_id"].startswith("assess:"):
                return {"action": "allow", "code": "ASSESS_REVIEW_ALLOWED"}
            return _block("OUTCOME_NO_REVIEW_LANE", "an outcome card completes on its recorded acceptance; "
                                                    "kanban_block if it cannot be accepted")
    except Refusal as exc:
        return _block(exc.code, exc.detail)
    except Exception as exc:  # fail closed on an outcome run
        return _block("OUTCOME_HOOK_ERROR", "%s: %s" % (type(exc).__name__, exc))
    return None


def writes(root: str, *, rel_paths: list[str], env: dict[str, str]) -> dict[str, Any] | None:
    """Product-write decision for an outcome run; None = not an outcome run."""
    if not active(root):
        return None
    sel = select_protocol(Path(root))
    if not sel.outcome:
        return None
    rels = [r for r in rel_paths if r]
    if not rels:
        return {"action": "allow", "code": "NO_WRITE"}
    from planner.outcome_lifecycle import PROTECTED_DIRS, Refusal, check_write, norm_rel
    for r in rels:
        rr = norm_rel(r)
        if any(rr == d.rstrip("/") or rr.startswith(d) for d in PROTECTED_DIRS):
            return _block("STORE_WRITE_REFUSED", "%s is authority or harness state" % rr)
    gate = execution_gate(Path(root), sel)
    if gate:
        return _block(gate[0][0], describe(gate).splitlines()[0])
    if not (Path(root) / STORE_FILE).exists():
        return None
    task = (env.get("HERMES_KANBAN_TASK") or "").strip()
    try:
        run_id = int((env.get("HERMES_KANBAN_RUN_ID") or "0").strip() or 0)
    except ValueError:
        run_id = 0
    try:
        ctx = _ctx(root)
        check_write(ctx, task_id=task, run_id=run_id, rel_paths=rels)
    except Refusal as exc:
        return _block(exc.code, exc.detail)
    except Exception as exc:
        return _block("OUTCOME_HOOK_ERROR", "%s: %s" % (type(exc).__name__, exc))
    return {"action": "allow", "code": "WRITE_IN_ISSUE"}
