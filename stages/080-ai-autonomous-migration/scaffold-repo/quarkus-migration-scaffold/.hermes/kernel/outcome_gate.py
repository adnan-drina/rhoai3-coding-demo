#!/usr/bin/env python3
"""Worker-side entry points of the outcome-board authority (named, K2-allowed).

    outcome_gate.py --root . issue
    outcome_gate.py --root . verdict --verdict REVERTED|VERIFICATION_PENDING|ACCEPTED --attempt N [--reason ..]
    outcome_gate.py --root . accept-commit --attempt N --commit SHA --classes compile,tests [--scenarios a,b]
    outcome_gate.py --root . restore-pending
    outcome_gate.py --root . restore-held
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

Under enabled execution every command is a REQUEST to the protected authority
service (planner/outcome_authority.py): this process holds no authority record
and the service re-derives each decision (the candidate, the scope, the
baseline, the budget) itself. The only local effects are the projection
(issued.json), the observer view (account.json) and, for ``push``, the git push
the service admitted -- whose result is this caller's report.
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


def _ctx(root: Path):
    """The authority context for this root: the protected service when the
    run's selection names one, else the in-process (cooperative) store."""
    from planner.outcome_protocol import authority_endpoint, select_protocol
    endpoint = authority_endpoint(select_protocol(root))
    if endpoint:
        from planner.outcome_native import default_db_path
        return L.RemoteCtx(root, endpoint, KanbanNative(default_db_path()))
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
    key = "outcome:v1:%s:%s:%s:issue%d" % (issued.get("run") or "", issued["outcome_id"], issued["cluster"], issued["issue_id"])
    card = cluster_card(row, steps)
    card["write_set"] = sorted(set(card["write_set"]) | set(issued.get("allowed_paths") or []))
    write_issued(root, wl, card, str(receipt.get("receipt_digest") or ""), key, task_id=issued["task_id"])
    amends = list(issued.get("amendments") or [])
    if amends:
        from planner.canonical import load_json as _lj, write_canonical as _wc
        from planner.paths import LOOP_ISSUED
        doc = _lj(root / LOOP_ISSUED)
        doc["amendments"] = [{"path": a["path"], "reason": a["reason"], "locus": a["locus"], "evidence": a.get("evidence") or {}}
                             for a in amends]
        _wc(root / LOOP_ISSUED, doc)
    return key


def _write_view(root: Path, acc: dict) -> None:
    """The observer view the service returned, written by the caller (the
    service never writes the other principal's tree). Derived; never read back
    as authority."""
    path = root / L.ACCOUNT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(acc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _remote_push(root: Path, ctx, task: str, run_id: int, remote: str, ref: str) -> dict:
    """The admitted push under the service: admission (and the refusal of any
    second admission) is the authority's; the push and its observed result are
    this caller's, recorded as its report. An already recorded push is never
    repeated: it is reported or probed by identity."""
    import subprocess
    adm = L.push_admit(ctx, task_id=task, run_id=run_id, remote=remote, ref=ref)
    eid, op = adm["effect_id"], adm["operation_id"]
    if adm.get("already"):
        if adm["state"] in ("landed", "failed"):
            return {"effect_id": eid, "state": adm["state"], "already": True}
        state = L.push_probe(root)(dict(kind="push", operation_id=op)) or "uncertain"
        L.record_delivery_effect(ctx, task_id=task, run_id=run_id, effect_id=eid, state=state, detail={"recovered": True})
        return {"effect_id": eid, "state": state, "already": True}
    p = subprocess.run(["git", "-C", str(root), "push", remote, "%s:%s" % (adm["head"], ref)], capture_output=True,
                       text=True, timeout=600)
    L.record_delivery_effect(ctx, task_id=task, run_id=run_id, effect_id=eid, state="sent",
                             detail={"rc": p.returncode, "stderr": (p.stderr or "")[-400:]})
    state = L.push_probe(root)(dict(kind="push", operation_id=op)) or "uncertain"
    L.record_delivery_effect(ctx, task_id=task, run_id=run_id, effect_id=eid, state=state, detail={"rc": p.returncode})
    return {"effect_id": eid, "state": state, "already": False}


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
    sub.add_parser("restore-held")
    r = sub.add_parser("assessment-record")
    r.add_argument("--verdict-file", default=str(L.VERDICT))
    sub.add_parser("stage-result")
    pu = sub.add_parser("push")
    pu.add_argument("--remote", default="origin")
    pu.add_argument("--ref", default="refs/heads/main")
    e = sub.add_parser("effect-admit")
    e.add_argument("--kind", required=True, choices=("push", "deploy"))
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
    ctx = None
    try:
        ctx = _ctx(root)
        remote = getattr(ctx, "remote", None) is not None
        if ns.cmd == "issue":
            t = (ctx.native.task(task) if not remote else None) or {}
            pid = int(t.get("worker_pid") or 0)   # the service reads the worker pid itself
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
        elif ns.cmd == "restore-held":
            # the held candidate of this outcome, back on the repaired baseline; the
            # authority names only paths the current issue allows; it is re-verified
            import base64
            out = L.restore_held(ctx, task_id=task, run_id=run_id)
            for rel, b64 in sorted((out.get("files") or {}).items()):
                p = root / rel
                if b64:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(base64.b64decode(b64))
                elif p.exists():
                    p.unlink()
            out = dict(out, files=sorted(out.get("files") or {}))
        elif ns.cmd == "assessment-record":
            doc = json.loads((root / ns.verdict_file).read_text(encoding="utf-8"))
            out = L.record_assessment(ctx, task_id=task, run_id=run_id, verdict_doc=doc)
        elif ns.cmd == "stage-result":
            out = L.record_stage_result(ctx, task_id=task, run_id=run_id)
        elif ns.cmd == "push":
            if remote:
                out = _remote_push(root, ctx, task, run_id, ns.remote, ns.ref)
            else:
                out = L.push_candidate(ctx, task_id=task, run_id=run_id, remote=ns.remote, ref=ns.ref)
        elif ns.cmd == "effect-admit":
            out = {"effect_id": L.admit_effect_checked(ctx, task_id=task, run_id=run_id, kind=ns.kind,
                                                        operation_id=ns.operation_id, revision=ns.revision)}
        elif ns.cmd == "effect-record":
            out = L.record_delivery_effect(ctx, task_id=task, run_id=run_id, effect_id=ns.effect_id, state=ns.state)
        else:
            out = L.write_account(ctx)
            if remote:
                _write_view(root, out)
    except (L.Refusal, StoreError) as exc:
        print(json.dumps({"refused": exc.code, "detail": exc.detail}))
        return 1
    finally:
        if ctx is not None and getattr(ctx, "store", None) is not None:
            ctx.store.close()
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
