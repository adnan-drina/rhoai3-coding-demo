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


def active(root: Path) -> bool:
    try:
        from planner.outcome_hook import active as maybe
        from planner.outcome_protocol import STORE_FILE, select_protocol
    except ImportError:
        return False
    return maybe(str(root)) and (Path(root) / STORE_FILE).exists() and select_protocol(Path(root)).outcome


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
    if not active(root):
        return None
    from planner import outcome_lifecycle as L
    task, run = _ids()
    try:
        out = L.record_verdict(_ctx(root), task_id=task, run_id=run, verdict=verdict, candidate=candidate,
                               attempt=candidate[:16], reason=reason)
    except (L.Refusal, Exception) as exc:  # the ledger must accept the verdict before anything else moves
        return _refuse(exc)
    if out.get("exhausted"):
        print("OUTCOME_BUDGET_EXHAUSTED %s: %d of %d rejected attempts spent (cumulative across runs). "
              "kanban_block kind=needs_input naming the outcome." % (out["outcome_id"], out["spent"], out["limit"]),
              file=sys.stderr)
    return 0


def after_accept(root: Path, commit: str, candidate: str, worklist: dict[str, Any], run: dict[str, Any]) -> int | None:
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


def reissue(root: Path, note: str = "") -> int | None:
    """The next attempt (or the outcome's next cluster) on the SAME card: a
    fresh issue for this run and a fresh issued.json. Never a new card."""
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
        return _refuse(exc)
    print("CONTINUE THIS CARD: outcome %s, cluster %s issued (%s)%s. Read the brief again; do not complete."
          % (out["outcome_id"], out["cluster"] or "(verification only)", key or "no product edits",
             "; " + note if note else ""))
    return 0
