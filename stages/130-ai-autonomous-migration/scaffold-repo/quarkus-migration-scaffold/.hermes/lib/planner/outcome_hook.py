"""The K2 hook's outcome-board branch (called in-process by kernel/pre_tool_call.sh).

Serial-loop runs return None immediately and the hook behaves exactly as
before. The fast path reads a few small files and never runs git: no authority
store in the tree, and neither ``run-defaults.json``, the initial declaration
``run-budget.json`` nor the platform contract names outcome-board/v1. For an
outcome-board run the phase, the write set and the completion rule come from the
authority (in-process for a qualification fixture, the protected service under
enabled execution) and the native board. They never come from the card body or
from K2_* environment overrides.

outcome-board/v2 (native cooperative control) decides from the board itself
(planner/native_control.py): the M2 card completes only on a green read-back
of the published graph; a node's terminators follow its role (repair: an
accepted outcome on the current tree, handed to review, completed by the
reviewer after the audit; assess: an ACCEPTED verdict bound to the current
candidate; deliver: the stage's derived evidence); product writes follow
this native run's issue record. Tasks that are neither (M1) keep the serial
rules.

Decisions (outcome-board/v1):
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
            if b"outcome-board/v" in data or b'"outcome_board"' in data:
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
        if sel.native:
            # native control decides one thing about a block: a card whose issued run
            # leaves product edits in the shared tree parks them first (v20 cascade).
            # Escalation stays possible whatever else fails: only that named refusal blocks.
            from planner import native_control as NC
            task, run_id = _ids(env)
            try:
                NC.check_terminator(Path(root), NC.board_for(Path(root)), task_id=task, run_id=run_id, kind=kind,
                                    profile=profile, audit_green=audit_green)
            except NC.Refusal as exc:
                if exc.code == "BLOCK_LEAVES_CANDIDATE":
                    return _block(exc.code, exc.detail)
            except Exception:  # noqa: BLE001 - a block is never trapped by a hook error
                pass
        return {"action": "allow", "code": "BLOCK_ALLOWED"}
    gate = execution_gate(Path(root), sel)
    if gate:
        return _block(gate[0][0], describe(gate).splitlines()[0])
    task, run_id = _ids(env)
    if sel.native:
        from planner import native_control as NC
        try:
            return NC.check_terminator(Path(root), NC.board_for(Path(root)), task_id=task, run_id=run_id, kind=kind,
                                       profile=profile, audit_green=audit_green)
        except NC.Refusal as exc:
            return _block(exc.code, exc.detail)
        except Exception as exc:  # fail closed on a native-control run
            return _block("OUTCOME_HOOK_ERROR", "%s: %s" % (type(exc).__name__, exc))
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


def run_ended(root: str, env: dict[str, str]) -> str:
    """outcome-board/v2: this worker's native run is no longer the task's
    current run (it requested review, completed, blocked, or was reclaimed).
    Hermes may still nudge the ended session to "finish" (v21 t_051c4490: the
    nudged session tried park, block, git checkout and a file write against
    the NEXT card's edit, each refused). One answer, whatever the tool: end
    the turn. '' when the run is live, the task is unknown, or not v2."""
    task, run_id = _ids(env)
    if not task or not run_id or not active(root):
        return ""
    try:
        sel = select_protocol(Path(root))
        if not sel.native:
            return ""
        from planner import native_control as NC
        t = NC.board_for(Path(root)).task(task)
    except Exception:  # noqa: BLE001 - undecidable here: the other checks decide
        return ""
    if not t or int(t.get("current_run_id") or 0) == run_id:
        return ""
    return ("RUN_ENDED: your run %d of %s has ended (the card is %s%s). Nothing is left for this session to do and "
            "no tool will act for it: do not park, block, complete or edit. End your turn now with a one-line final "
            "message." % (run_id, task, t.get("status"), ", now run %s" % t.get("current_run_id") if t.get("current_run_id") else ""))


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
    if sel.native:
        return _native_writes(root, sel, rels, env)
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


def _native_writes(root: str, sel, rels: list[str], env: dict[str, str]) -> dict[str, Any] | None:
    """Product writes on a native-control run: harness state is never
    tool-written; a v2 node writes only inside this native run's issue; the
    M1/M2 cards keep the serial rules (None)."""
    from planner import native_control as NC
    for r in rels:
        rr = NC.norm_rel(r)
        if any(rr == d.rstrip("/") or rr.startswith(d) for d in NC.PROTECTED_DIRS):
            return _block("STORE_WRITE_REFUSED", "%s is harness state" % rr)
    gate = execution_gate(Path(root), sel)
    if gate:
        return _block(gate[0][0], describe(gate).splitlines()[0])
    task, run_id = _ids(env)
    try:
        board = NC.board_for(Path(root))
        if not task or board.node_of(task) is None:
            return None
        NC.check_write(board, task_id=task, run_id=run_id, rel_paths=rels)
    except NC.Refusal as exc:
        return _block(exc.code, exc.detail)
    except Exception as exc:
        return _block("OUTCOME_HOOK_ERROR", "%s: %s" % (type(exc).__name__, exc))
    return {"action": "allow", "code": "WRITE_IN_ISSUE"}
