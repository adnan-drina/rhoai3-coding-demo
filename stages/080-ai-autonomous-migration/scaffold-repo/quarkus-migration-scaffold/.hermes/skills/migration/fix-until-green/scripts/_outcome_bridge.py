"""advance.py under the outcome-board protocol (OUTCOME-BOARD-CONTRACT.md T6).

The serial loop's acceptance transaction is unchanged: the same measure, veto,
revert and commit. Only what surrounds the verdict differs:

  * no K4 re-mint per attempt: a rejected or pending attempt stays on the SAME
    outcome card, and the authority re-issues the cluster for the next attempt
    in this run (reissue);
  * the verdict is recorded on the outcome's ledger (cumulative budget);
  * an acceptance is begun on the ledger BEFORE the commit and recorded after
    it, so a crash between the two is recovered, not re-spent;
  * after an accepted cluster, either the OUTCOME is accepted (the worker
    completes the card) or the authority issues the outcome's next cluster on
    the same card.

Every function is a no-op (returns None) unless the root runs the outcome
protocol and has an authority store.

outcome-board/v2 (native cooperative control, planner/native_control.py):
the same calls record on the native board instead (issue / reject / pending /
accept-begin / accept-commit records on this task), and an accepted outcome
is handed to REVIEW -- ``kanban_request_review reviewer=reviewer`` -- where
the reviewer completes it after the audit or requests changes (another native
run of the same task). An owner defect holds the candidate as an attachment,
publishes one owner repair as a native prerequisite and ends the run with
``kanban_block kind=dependency``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

_HERMES = Path(__file__).resolve().parents[4]
for _p in (_HERMES / "lib", _HERMES / "kernel"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _native(root: Path):
    """The native board when this root runs outcome-board/v2 AND the current
    task is one of its nodes; None otherwise (serial loop, v1, M1/M2)."""
    try:
        from planner.outcome_protocol import select_protocol
        if not select_protocol(Path(root)).native:
            return None
        from planner import native_control as NC
        task, _run = _ids()
        board = NC.board_for(Path(root))
        return board if task and board.node_of(task) is not None else None
    except Exception:
        return None


def active(root: Path) -> bool:
    if _native(root) is not None:
        return True
    try:
        from planner.outcome_hook import active as maybe
        from planner.outcome_protocol import select_protocol, store_present
    except ImportError:
        return False
    # the store may live in the protected authority service, not in the tree
    return maybe(str(root)) and select_protocol(Path(root)).outcome and store_present(Path(root))


def _ids() -> tuple[str, int]:
    task = (os.environ.get("HERMES_KANBAN_TASK") or "").strip()
    try:
        run = int((os.environ.get("HERMES_KANBAN_RUN_ID") or "0").strip() or 0)
    except ValueError:
        run = 0
    return task, run


def _ctx(root: Path):
    from outcome_gate import _ctx as gate_ctx
    return gate_ctx(Path(root))


def _refuse(exc: Exception) -> int:
    print("REFUSE: %s" % exc, file=sys.stderr)
    return 1


def record(root: Path, verdict: str, candidate: str, reason: str = "") -> int | None:
    """REVERTED / VERIFICATION_PENDING / ACCEPTED (accept-begin) for this run's issue."""
    board = _native(root)
    if board is not None:
        return _native_record(root, board, verdict, candidate, reason)
    if not active(root):
        return None
    from planner import outcome_lifecycle as L
    task, run = _ids()
    try:
        out = L.record_verdict(_ctx(root), task_id=task, run_id=run, verdict=verdict, candidate=candidate,
                               attempt=candidate[:16], reason=reason)
    except (L.Refusal, Exception) as exc:  # the ledger must accept the verdict before anything else moves
        return _refuse(exc)
    if out.get("verdict") == "OWNER_RECOVERY":
        # automatic owner recovery: the authority HELD this candidate (no attempt spent) and
        # scheduled one repair of the accepted owner as this card's prerequisite
        print("OWNER_RECOVERY %s: the runtime failure belongs to %s (proven on the baseline). The candidate is held by "
              "the authority; the tree is reverted as usual. End this run with kanban_block kind=dependency; after the "
              "repair this card resumes and outcome_gate.py restore-held puts the candidate back for re-verification."
              % (out["outcome_id"], out["owner"]), file=sys.stderr)
        return 0
    if out.get("exhausted"):
        print("OUTCOME_BUDGET_EXHAUSTED %s: %d of %d rejected attempts spent (cumulative across runs). "
              "kanban_block kind=needs_input naming the outcome." % (out["outcome_id"], out["spent"], out["limit"]),
              file=sys.stderr)
    return 0


def after_accept(root: Path, commit: str, candidate: str, worklist: dict[str, Any], run: dict[str, Any]) -> int | None:
    board = _native(root)
    if board is not None:
        return _native_after_accept(root, board, commit, candidate, worklist, run)
    if not active(root):
        return None
    from planner import outcome_lifecycle as L
    task, run_id = _ids()
    parity = (((run or {}).get("runtime") or {}).get("parity") or {}) if isinstance(run, dict) else {}
    scenarios = [str(s) for s in parity.get("scenarios") or []]
    classes = ["build", "compile", "tests"] + (["runtime"] if (worklist.get("runtime") or {}).get("ready") else []) + \
              (["parity"] if scenarios else [])
    try:
        ctx = _ctx(root)
        out = L.accept_commit(ctx, task_id=task, run_id=run_id, attempt=candidate[:16], commit=commit,
                              measurement={"classes": classes, "scenarios": scenarios})
    except Exception as exc:
        return _refuse(exc)
    if out["outcome_accepted"]:
        print("OUTCOME ACCEPTED %s on commit %s: kanban_complete this card." % (out["outcome_id"], commit[:12]))
        return 0
    return reissue(root, note="outcome %s still owns %s" % (out["outcome_id"], ", ".join(out["open_owned"][:4]) or "unmeasured checks"))


def amend(root: Path, cluster: str, rel: str, row: dict[str, Any]) -> int | None:
    """Scope amendment under the outcome protocol: the authority transition first
    (it widens the governing permission); the caller writes the projection only
    after it succeeds."""
    board = _native(root)
    if board is not None:
        from planner import native_control as NC
        task, run = _ids()
        try:
            out = NC.amend(Path(root), board, task_id=task, run_id=run, cluster=cluster, rel=rel, row=row)
        except Exception as exc:
            return _refuse(exc)
        print("OUTCOME AMENDMENT recorded: %s + %s (issue %s)" % (cluster, rel, out.get("issue_id", "unchanged")))
        return 0
    if not active(root):
        return None
    from planner import outcome_lifecycle as L
    task, run = _ids()
    try:
        out = L.amend_issue(_ctx(root), task_id=task, run_id=run, cluster=cluster, rel=rel, row=row)
    except Exception as exc:
        return _refuse(exc)
    print("OUTCOME AMENDMENT recorded: %s + %s (issue %s)" % (cluster, rel, out.get("issue_id", "unchanged")))
    return 0


def resume_recovered(root: Path, worklist: dict[str, Any], run: dict[str, Any]) -> int | None:
    """After a worker died between its commit and the acceptance record, the next
    run's issue recovered that commit (review R5). The re-measured tree then
    finishes THAT acceptance; nothing is committed or spent again. None when
    there is nothing recovered to finish."""
    board = _native(root)
    if board is not None:
        from planner import native_control as NC
        task, run_id = _ids()
        try:
            out = NC.evaluate_recovered(Path(root), board, task_id=task, run_id=run_id,
                                        measurement=_measurement(worklist, run))
        except Exception as exc:
            return _refuse(exc)
        if out is None:
            return None
        if out["outcome_accepted"]:
            print(_REVIEW % (out["outcome_id"], "commit " + str(out["commit"])[:12] + ", judged again on the unchanged tree"))
            return 0
        reasons = out.get("not_accepted_because") or ["open obligation %s" % o for o in out["open_owned"][:4]]
        print("OUTCOME NOT YET ACCEPTED %s (commit %s, judged again on the unchanged tree): %s"
              % (out["outcome_id"], str(out["commit"])[:12], "; ".join(reasons[:4])), file=sys.stderr)
        return reissue(root, note="outcome %s is not accepted yet: %s" % (out["outcome_id"], "; ".join(reasons[:3])))
    if not active(root):
        return None
    from planner import outcome_lifecycle as L
    task, run_id = _ids()
    parity = (((run or {}).get("runtime") or {}).get("parity") or {}) if isinstance(run, dict) else {}
    scenarios = [str(s) for s in parity.get("scenarios") or []]
    classes = ["build", "compile", "tests"] + (["runtime"] if (worklist.get("runtime") or {}).get("ready") else []) + \
              (["parity"] if scenarios else [])
    try:
        out = L.evaluate_recovered(_ctx(root), task_id=task, run_id=run_id,
                                   measurement={"classes": classes, "scenarios": scenarios})
    except Exception as exc:
        return _refuse(exc)
    if out is None:
        return None
    if out["outcome_accepted"]:
        print("OUTCOME ACCEPTED %s on recovered commit %s: kanban_complete this card." % (out["outcome_id"], out["commit"][:12]))
        return 0
    return reissue(root, note="recovered commit %s; outcome still owns %s" % (out["commit"][:12], ", ".join(out["open_owned"][:4])))


def reissue(root: Path, note: str = "") -> int | None:
    """The next attempt (or the outcome's next cluster) on the SAME card: a
    fresh issue for this run and a fresh issued.json. Never a new card."""
    board = _native(root)
    if board is not None:
        return _native_reissue(root, board, note)
    if not active(root):
        return None
    from planner import outcome_lifecycle as L
    from outcome_gate import write_issued_record
    task, run = _ids()
    try:
        ctx = _ctx(root)
        t = ctx.native.task(task) or {}
        out = L.issue(ctx, task_id=task, run_id=run, claim_lock=str(t.get("claim_lock") or ""),
                      pid=int(t.get("worker_pid") or 0), pgid=0)
        key = write_issued_record(Path(root), ctx, out)
    except Exception as exc:
        if getattr(exc, "code", "") == "OWNER_REPAIR_PENDING":
            # automatic owner recovery: this card waits on its owner's repair; the one
            # legal terminator (paved-road-m3), not a refusal to work around
            print("OWNER_REPAIR_PENDING: %s. Terminator: kanban_block kind=dependency." % getattr(exc, "detail", exc),
                  file=sys.stderr)
            return 0
        return _refuse(exc)
    print("CONTINUE THIS CARD: outcome %s, cluster %s issued (%s)%s. Read the brief again; do not complete."
          % (out["outcome_id"], out["cluster"] or "(verification only)", key or "no product edits",
             "; " + note if note else ""))
    return 0


# ---------------------------------------------------------------------------
# outcome-board/v2: native cooperative control
# ---------------------------------------------------------------------------

_REVIEW = ("OUTCOME ACCEPTED %s on %s: end this run with kanban_request_review reviewer=reviewer (metadata: the "
           "commit and the tree). The reviewer runs the paved-road audit and completes the card, or requests changes "
           "(another run of this same card). Do not kanban_complete.")


def _measurement(worklist: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    parity = (((run or {}).get("runtime") or {}).get("parity") or {}) if isinstance(run, dict) else {}
    scenarios = [str(s) for s in parity.get("scenarios") or []]
    classes = ["build", "compile", "tests"] + (["runtime"] if ((worklist or {}).get("runtime") or {}).get("ready") else []) + \
              (["parity"] if scenarios else [])
    return {"classes": classes, "scenarios": scenarios}


def _native_record(root: Path, board, verdict: str, candidate: str, reason: str) -> int:
    from planner import native_control as NC
    task, run = _ids()
    try:
        out = NC.record_verdict(Path(root), board, task_id=task, run_id=run, verdict=verdict, candidate=candidate,
                                attempt=candidate[:16], reason=reason)
    except Exception as exc:  # the board must hold the verdict before anything else moves
        return _refuse(exc)
    if out.get("verdict") == "OWNER_RECOVERY":
        print("OWNER_RECOVERY %s: the runtime failure belongs to %s (proven on the baseline). The candidate is held on "
              "this card (attachment); the tree is reverted as usual. One repair of the owner (%s) is published as this "
              "card's prerequisite. End this run with kanban_block kind=dependency; the dispatcher resumes this card after "
              "the repair, and native_gate.py restore-held puts the candidate back for re-verification."
              % (out["outcome_id"], out["owner"], out.get("repair")), file=sys.stderr)
        return 0
    if out.get("exhausted"):
        print("OUTCOME_BUDGET_EXHAUSTED %s: %d of %d rejected attempts and change requests spent (cumulative across runs). "
              "kanban_block kind=needs_input naming the outcome." % (out["outcome_id"], out["spent"], out["limit"]),
              file=sys.stderr)
    return 0


def _native_after_accept(root: Path, board, commit: str, candidate: str, worklist: dict[str, Any], run: dict[str, Any]) -> int:
    from planner import native_control as NC
    task, run_id = _ids()
    try:
        out = NC.accept_commit(Path(root), board, task_id=task, run_id=run_id, attempt=candidate[:16], commit=commit,
                               measurement=_measurement(worklist, run))
    except Exception as exc:
        return _refuse(exc)
    if out["outcome_accepted"]:
        print(_REVIEW % (out["outcome_id"], "commit " + commit[:12]))
        return 0
    reasons = out.get("not_accepted_because") or ["an unmeasured check class"]
    print("OUTCOME NOT YET ACCEPTED %s (commit %s is recorded): %s" % (out["outcome_id"], commit[:12], "; ".join(reasons[:4])),
          file=sys.stderr)
    return reissue(root, note="outcome %s is not accepted yet: %s" % (out["outcome_id"], "; ".join(reasons[:3])))


def _native_reissue(root: Path, board, note: str = "") -> int:
    from planner import native_control as NC
    from native_gate import write_issued_projection
    task, run = _ids()
    try:
        out = NC.issue(Path(root), board, task_id=task, run_id=run)
        key = write_issued_projection(Path(root), out)
    except Exception as exc:
        code = getattr(exc, "code", "")
        if code == "OWNER_REPAIR_PENDING":
            print("OWNER_REPAIR_PENDING: %s. Terminator: kanban_block kind=dependency." % getattr(exc, "detail", exc),
                  file=sys.stderr)
            return 0
        if code == "ISSUE_BUDGET_EXHAUSTED":
            print("OUTCOME_BUDGET_EXHAUSTED: %s. Terminator: kanban_block kind=needs_input." % getattr(exc, "detail", exc),
                  file=sys.stderr)
            return 0
        return _refuse(exc)
    print("CONTINUE THIS CARD: outcome %s, scope %s issued (%s)%s. Read the brief again; do not complete."
          % (out["outcome_id"], out["cluster"] or "(verification only)", key or "no product edits",
             "; " + note if note else ""))
    return 0
