"""The K2 hook's outcome-board branch (called in-process by kernel/pre_tool_call.sh).

Serial-loop runs return None immediately and the hook behaves exactly as
before. The fast path reads a few small files and never runs git: no authority
store in the tree, and neither ``run-defaults.json``, the initial declaration
``run-budget.json`` nor the platform contract names outcome-board/v1. For an
outcome-board run the phase, the write set and the completion rule come from the
authority (in-process for a qualification fixture, the protected service under
enabled execution) and the native board. They never come from the card body or
from K2_* environment overrides.

Decisions:
  kanban_block        allowed on a consistent selection (escalation is a legal
                      result); an inconsistent selection refuses everything
  kanban_complete     outcome_lifecycle.check_complete (records the intent first)
  request_review      outcome_lifecycle.check_review
  product writes      outcome_lifecycle.check_write against the run-bound issue;
                      the authority store and harness state are never tool-written
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from planner.outcome_protocol import (DECLARATION, DEFAULTS, OUTCOME, SELECTION_REFUSALS, STORE_FILE, authority_endpoint,
                                      describe, execution_gate, select_protocol, store_present)

CONTRACT_HINT = Path("/etc/rhoai3/run-control/contract.json")


def active(root: str) -> bool:
    """Cheap: is this root possibly an outcome-board run? Any record that could
    select the protocol counts, so a governed run whose request and contract
    disagree still reaches the refusal instead of the serial road."""
    if not root:
        return False
    r = Path(root)
    if (r / STORE_FILE).exists():
        return True
    hints = [r / DEFAULTS, r / DECLARATION, CONTRACT_HINT]
    try:
        import json
        rc = (json.loads((r / DECLARATION).read_text(encoding="utf-8")) or {}).get("run_control") or {}
        if isinstance(rc, dict) and str(rc.get("root") or "").startswith("/"):
            hints.append(Path(str(rc["root"])) / "contract.json")
    except (OSError, ValueError, AttributeError):
        pass
    for p in hints:
        try:
            data = p.read_bytes()
            # the protocol named anywhere, or an outcome_board block in a contract
            if OUTCOME.encode() in data or b'"outcome_board"' in data:
                return True
        except OSError:
            continue
    return False


def _ctx(root: str, sel=None):
    from planner.outcome_lifecycle import Ctx, RemoteCtx
    from planner.outcome_native import KanbanNative, default_db_path
    endpoint = authority_endpoint(sel or select_protocol(Path(root)))
    if endpoint:
        return RemoteCtx(Path(root), endpoint, KanbanNative(default_db_path()))
    from planner.outcome_store import Store
    store = Store(Path(root))
    native = KanbanNative(store.meta("native_db"))
    return Ctx(Path(root), store, native)


def _block(code: str, detail: str) -> dict[str, Any]:
    return {"action": "block", "code": code, "message": "%s: %s" % (code, detail)}


def _ids(env: dict[str, str]) -> tuple[str, int]:
    task = (env.get("HERMES_KANBAN_TASK") or "").strip()
    try:
        run_id = int((env.get("HERMES_KANBAN_RUN_ID") or "0").strip() or 0)
    except ValueError:
        run_id = 0
    return task, run_id


def terminator(root: str, *, kind: str, profile: str, env: dict[str, str],
               audit_green: Callable[[], bool]) -> dict[str, Any] | None:
    """kind in {complete, block, request_review}. None = not an outcome run."""
    if not active(root):
        return None
    sel = select_protocol(Path(root))
    if any(code in SELECTION_REFUSALS for code, _ in sel.errors):
        # the run's request and its platform record disagree: nothing proceeds
        return _block(sel.errors[0][0], describe(sel.errors).splitlines()[0])
    if not sel.outcome:
        if (Path(root) / STORE_FILE).exists():
            return _block("PROTOCOL_MIXED", "serial-loop run carries an outcome-board store")
        return None
    if kind == "block":
        return {"action": "allow", "code": "BLOCK_ALLOWED"}
    gate = execution_gate(Path(root), sel)
    if gate:
        return _block(gate[0][0], describe(gate).splitlines()[0])
    task, run_id = _ids(env)
    if not store_present(Path(root), sel):
        # before publication: the serial M1/M2 road governs (its audit requires publication)
        return None
    from planner.outcome_lifecycle import Refusal, check_complete, check_review
    ctx = None
    try:
        ctx = _ctx(root, sel)
        if kind == "complete":
            out = check_complete(ctx, task_id=task, run_id=run_id, profile=profile, audit_green=audit_green())
            return {"action": "allow", "code": "COMPLETE_ALLOWED", "intent": out.get("intent")}
        if kind == "request_review":
            out = check_review(ctx, task_id=task, run_id=run_id)
            return {"action": "allow", "code": out.get("code") or "REVIEW_ALLOWED"}
    except Refusal as exc:
        return _block(exc.code, exc.detail)
    except Exception as exc:  # fail closed on an outcome run
        return _block("OUTCOME_HOOK_ERROR", "%s: %s" % (type(exc).__name__, exc))
    finally:
        if ctx is not None and getattr(ctx, "store", None) is not None:
            ctx.store.close()
    return None


def writes(root: str, *, rel_paths: list[str], env: dict[str, str]) -> dict[str, Any] | None:
    """Product-write decision for an outcome run; None = not an outcome run."""
    if not active(root):
        return None
    sel = select_protocol(Path(root))
    if any(code in SELECTION_REFUSALS for code, _ in sel.errors):
        return _block(sel.errors[0][0], describe(sel.errors).splitlines()[0])
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
    if not store_present(Path(root), sel):
        return None
    task, run_id = _ids(env)
    ctx = None
    try:
        ctx = _ctx(root, sel)
        check_write(ctx, task_id=task, run_id=run_id, rel_paths=rels)
    except Refusal as exc:
        return _block(exc.code, exc.detail)
    except Exception as exc:
        return _block("OUTCOME_HOOK_ERROR", "%s: %s" % (type(exc).__name__, exc))
    finally:
        if ctx is not None and getattr(ctx, "store", None) is not None:
            ctx.store.close()
    return {"action": "allow", "code": "WRITE_IN_ISSUE"}
