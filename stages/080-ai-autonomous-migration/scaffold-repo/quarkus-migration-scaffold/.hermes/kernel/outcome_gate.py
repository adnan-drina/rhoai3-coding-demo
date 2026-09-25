#!/usr/bin/env python3
"""Worker-side entry points of the outcome-board authority (named, K2-allowed).

    outcome_gate.py --root . issue
    outcome_gate.py --root . verdict --verdict REVERTED|VERIFICATION_PENDING|ACCEPTED --attempt N [--reason ..]
    outcome_gate.py --root . accept-commit --attempt N --commit SHA --classes compile,tests [--scenarios a,b]
    outcome_gate.py --root . restore-pending
    outcome_gate.py --root . assessment-record [--verdict-file evidence/verdicts/m4-verdict.json]
    outcome_gate.py --root . stage-result --result-file PATH
    outcome_gate.py --root . effect-admit --kind push --operation-id ID --revision N
    outcome_gate.py --root . effect-record --effect-id ID --state sent|landed|failed
    outcome_gate.py --root . account

The task, native run and claim come from the dispatcher's environment of THIS
worker (HERMES_KANBAN_TASK / HERMES_KANBAN_RUN_ID / HERMES_KANBAN_CLAIM_LOCK),
and every one is re-checked against the board recorded at publication. Nothing
here trusts an argument for scope, acceptance or budget. Output is JSON. The
exit code is 0 for an allowed transition and 1 for a typed refusal.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_KERNEL = Path(__file__).resolve().parent
_LIB = _KERNEL.parent / "lib"
for _p in (_KERNEL, _LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from planner import outcome_lifecycle as L  # noqa: E402
from planner.outcome_native import KanbanNative  # noqa: E402
from planner.outcome_store import Store, StoreError  # noqa: E402


def _ctx(root: Path) -> L.Ctx:
    store = Store(root)
    return L.Ctx(root, store, KanbanNative(store.meta("native_db"),
                                           hermes=(os.environ.get("HERMES_BIN") or "hermes").split(),
                                           env=dict(os.environ, HERMES_KANBAN_DB=store.meta("native_db"))))


def write_issued_record(root: Path, ctx: L.Ctx, issued: dict) -> str:
    """The existing loop tools (brief, run-verify, advance, amend-scope) read
    verification/loop/issued.json. Under the outcome protocol it is written
    for the ONE cluster the authority issued, keyed outcome:..., and bound to
    the claimed task. It is a projection of the issue. The hook still decides
    from the authority record. '' when no cluster is issued (verification-only)."""
    if not issued.get("cluster"):
        return ""
    from k4_convert import write_issued
    from planner.cards import cluster_card
    from planner.canonical import load_json
    from planner.paths import ADMISSION_RECEIPT, LOOP_STEPS
    wl, _why = L.load_worklist(root)
    row = next(c for c in wl["clusters"] if c["id"] == issued["cluster"])
    steps = load_json(root / LOOP_STEPS) if (root / LOOP_STEPS).is_file() else {}
    receipt = load_json(root / ADMISSION_RECEIPT) if (root / ADMISSION_RECEIPT).is_file() else {}
    key = "outcome:v1:%s:%s:%s:issue%d" % (ctx.store.meta("run_id"), issued["outcome_id"], issued["cluster"], issued["issue_id"])
    write_issued(root, wl, cluster_card(row, steps), str(receipt.get("receipt_digest") or ""), key, task_id=issued["task_id"])
    return key


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="outcome_gate.py")
    ap.add_argument("--root", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("issue")
    v = sub.add_parser("verdict")
    v.add_argument("--verdict", required=True, choices=("REVERTED", "VERIFICATION_PENDING", "ACCEPTED"))
    v.add_argument("--attempt", required=True)
    v.add_argument("--reason", default="")
    a = sub.add_parser("accept-commit")
    a.add_argument("--attempt", required=True)
    a.add_argument("--commit", required=True)
    a.add_argument("--classes", default="compile,tests")
    a.add_argument("--scenarios", default="")
    sub.add_parser("restore-pending")
    r = sub.add_parser("assessment-record")
    r.add_argument("--verdict-file", default=str(L.VERDICT))
    s = sub.add_parser("stage-result")
    s.add_argument("--result-file", required=True)
    e = sub.add_parser("effect-admit")
    e.add_argument("--kind", required=True, choices=("commit", "push", "deploy"))
    e.add_argument("--operation-id", required=True)
    e.add_argument("--revision", type=int, required=True)
    er = sub.add_parser("effect-record")
    er.add_argument("--effect-id", required=True)
    er.add_argument("--state", required=True, choices=("sent", "landed", "failed", "uncertain"))
    sub.add_parser("account")
    ns = ap.parse_args(argv)
    root = Path(ns.root).resolve()
    task = (os.environ.get("HERMES_KANBAN_TASK") or "").strip()
    try:
        run_id = int((os.environ.get("HERMES_KANBAN_RUN_ID") or "0").strip() or 0)
    except ValueError:
        run_id = 0
    try:
        ctx = _ctx(root)
        if ns.cmd == "issue":
            t = ctx.native.task(task) or {}
            pid = int(t.get("worker_pid") or 0)
            try:
                pgid = os.getpgid(pid) if pid else 0
            except OSError:
                pgid = 0
            out = L.issue(ctx, task_id=task, run_id=run_id, claim_lock=os.environ.get("HERMES_KANBAN_CLAIM_LOCK") or "",
                          pid=pid, pgid=pgid)
            out["issued_record"] = write_issued_record(root, ctx, out)
        elif ns.cmd == "verdict":
            out = L.record_verdict(ctx, task_id=task, run_id=run_id, verdict=ns.verdict, candidate=ctx.product_tree(),
                                   attempt=ns.attempt, reason=ns.reason)
        elif ns.cmd == "accept-commit":
            out = L.accept_commit(ctx, task_id=task, run_id=run_id, attempt=ns.attempt, commit=ns.commit,
                                  measurement={"classes": [c for c in ns.classes.split(",") if c],
                                               "scenarios": [s for s in ns.scenarios.split(",") if s]})
        elif ns.cmd == "restore-pending":
            out = L.restore_pending(ctx, task_id=task, run_id=run_id, candidate_now=ctx.product_tree())
        elif ns.cmd == "assessment-record":
            doc = json.loads((root / ns.verdict_file).read_text(encoding="utf-8"))
            out = L.record_assessment(ctx, task_id=task, run_id=run_id, verdict_doc=doc)
        elif ns.cmd == "stage-result":
            out = L.record_stage_result(ctx, task_id=task, run_id=run_id,
                                        result=json.loads(Path(ns.result_file).read_text(encoding="utf-8")))
        elif ns.cmd == "effect-admit":
            L.active_issue(ctx, task, run_id)
            out = {"effect_id": L.admit_effect(ctx.store, kind=ns.kind, candidate=ctx.product_tree(),
                                                operation_id=ns.operation_id, expected_rev=ns.revision)}
        elif ns.cmd == "effect-record":
            L.active_issue(ctx, task, run_id)
            L.record_effect(ctx.store, ns.effect_id, ns.state)
            out = {"effect_id": ns.effect_id, "state": ns.state}
        else:
            out = L.write_account(ctx)
    except (L.Refusal, StoreError) as exc:
        print(json.dumps({"refused": exc.code, "detail": exc.detail}))
        return 1
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
