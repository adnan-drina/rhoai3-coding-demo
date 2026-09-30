#!/usr/bin/env python3
"""Worker-side entry points of native cooperative control (outcome-board/v2).

    native_gate.py --root . publish [--plan-file F]   (M2: publish the plan as native tasks)
    native_gate.py --root . preview                   (read-only: the plan M2 would publish)
    native_gate.py --root . readback                  (read-only: board vs latest revision)
    native_gate.py --root . issue                     (M3/M4/M5: this run's scope + issued.json)
    native_gate.py --root . verdict --verdict REVERTED|VERIFICATION_PENDING|ACCEPTED --attempt N [--reason ..]
    native_gate.py --root . accept-commit --attempt N --commit SHA --classes compile,tests [--scenarios a,b]
    native_gate.py --root . restore-pending
    native_gate.py --root . restore-held
    native_gate.py --root . assessment-record [--verdict-file evidence/verdicts/m4-verdict.json]
    native_gate.py --root . m4-repair                 (after a REFUSE: repairs become M4's prerequisites)
    native_gate.py --root . push [--remote origin] [--ref refs/heads/main]
    native_gate.py --root . account                   (read-only progress projection)
    native_gate.py --root . handoff                   (read-only: the review summary + metadata for this card)
    native_gate.py --root . park                      (hold this card's uncommitted candidate; restore HEAD)
    native_gate.py --root . integrate                 (pilot pair: apply the accepted worktree candidate to the main tree, verified there)
    native_gate.py --root . rebase                    (pilot pair: move the worktree onto the main tree's HEAD for rework)
    native_gate.py --root . restore-parked            (put this card's parked candidate back, re-verified)

A refusal repeated three times in one run answers REPEATED_REFUSAL: the
candidate is parked and the only legal next step is kanban_block
kind=needs_input (the K2 hook refuses every other tool for that run).

The task, native run and claim come from the dispatcher's environment of THIS
worker (HERMES_KANBAN_TASK / HERMES_KANBAN_RUN_ID / HERMES_KANBAN_CLAIM_LOCK)
and are re-checked against the board. Hermes Kanban owns the lifecycle; this
CLI records domain facts on the board (comments, attachments) and publishes
the plan's nodes. Output is JSON; exit 0 for an allowed step, 1 for a typed
refusal. Not claimed control: native Kanban is cooperative (planner/native_control.py).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

_KERNEL = Path(__file__).resolve().parent
_LIB = _KERNEL.parent / "lib"
for _p in (_KERNEL, _LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from planner import native_control as NC  # noqa: E402
from planner.outcome_checks import VERDICT, Refusal  # noqa: E402


def write_issued_projection(root: Path, issued: dict) -> str:
    """Publish the projection under the native publication lock, which
    retire_issuance also takes: a retirement never interleaves with a new
    issuance's publication (architect review of 0dd677ba)."""
    if not issued.get("cluster"):
        return ""
    with NC.publication_lock(Path(root)):
        return _write_issued_projection(root, issued)


def _write_issued_projection(root: Path, issued: dict) -> str:
    """The loop tools (brief, run-verify, advance, amend-scope) read
    verification/loop/issued.json. Under native control it is written for the
    ONE cluster (or unit) this run was issued, bound to the claimed task: a
    projection of the issue record, never read back as a decision. '' when
    nothing is issued for product edits."""
    if not issued.get("cluster"):
        return ""
    from k4_convert import write_issued
    from planner.canonical import load_json, write_canonical
    from planner.cards import cluster_card
    from planner.outcome_checks import load_worklist
    from planner.paths import ADMISSION_RECEIPT, LOOP_ISSUED, LOOP_STEPS
    wl, _why = load_worklist(root)
    row = next((c for c in (wl or {}).get("clusters") or [] if c["id"] == issued["cluster"]), None)
    if issued.get("objective"):
        row = _objective_row(root, issued, wl)
    if row is None and issued.get("planned_unit"):
        allowed = sorted(issued.get("allowed_paths") or [])
        row = {"id": issued["cluster"], "kind": issued["planned_unit"].get("kind") or "compile", "path": allowed[0] if allowed else "",
               "write_set": allowed, "items": [], "retry_key": (issued.get("budget") or {}).get("key") or issued["cluster"]}
    if row is None:
        raise Refusal("ISSUE_PROJECTION", "cluster %s is not in the measured work list" % issued["cluster"])
    steps = load_json(root / LOOP_STEPS) if (root / LOOP_STEPS).is_file() else {}
    receipt = load_json(root / ADMISSION_RECEIPT) if (root / ADMISSION_RECEIPT).is_file() else {}
    key = "outcome:v2:%s:%s:%s:issue%d:r%d" % (issued.get("run") or "", issued["outcome_id"], issued["cluster"],
                                               int(issued["issue_id"]), int(issued["run_id"]))
    card = cluster_card(row, steps)
    card["write_set"] = sorted(set(card["write_set"]) | set(issued.get("allowed_paths") or []))
    if issued.get("planned_unit") and str(issued["cluster"]).startswith("planned:"):
        from planner.worklist import PLANNED_UNIT_GATE
        card["gate"] = PLANNED_UNIT_GATE          # judged by its requirement checks, not the tuple
    write_issued(root, wl, card, str(receipt.get("receipt_digest") or ""), key, task_id=issued["task_id"])
    if issued.get("objective"):
        # the admitted descriptor rides with the card: advance.py rebuilds the
        # envelope from it and refuses one that differs
        doc = load_json(root / LOOP_ISSUED)
        doc["objective"] = dict(issued["objective"])
        write_canonical(root / LOOP_ISSUED, doc)
    nb = issued.get("budget") or {}
    if nb.get("key"):
        # v24: the M2-published family budget GOVERNS this card (one limit, one count: native
        # family_spent). The loop counts against the same key and projects that count; it never
        # applies decisions.max_attempts as a second family ceiling.
        doc = load_json(root / LOOP_ISSUED)
        doc["native_budget"] = {"key": str(nb["key"]), "spent": int(nb.get("spent") or 0), "limit": int(nb.get("limit") or 0),
                                "shared": str(nb["key"]).startswith("rk:family:")}
        doc["retry_key"] = str(nb["key"])
        doc["budget_authority"] = "native"
        write_canonical(root / LOOP_ISSUED, doc)
    amends = list(issued.get("amendments") or [])
    if amends:
        doc = load_json(root / LOOP_ISSUED)
        # the grant facts travel with the amendment: advance.py rejects one without them (v29 run 76)
        doc["amendments"] = [{"path": a["path"], "reason": a["reason"], "locus": a["locus"], "evidence": a.get("evidence") or {},
                              "granted_before_sha256": a.get("granted_before_sha256") or "",
                              "dirty_at_grant": bool(a.get("dirty_at_grant"))} for a in amends]
        write_canonical(root / LOOP_ISSUED, doc)
    return key


def _objective_row(root: Path, issued: dict, wl: dict | None) -> dict:
    """The card row of an objective issued whole: every still-reported
    obligation it admitted (by line-free identity, or id for an incident), the
    admitted file seal, and its composite scope written ONCE at its digest path."""
    from planner.canonical import write_canonical
    from planner.worklist import ObjectiveScopeError, batch_scope_path, build_objective_scope
    desc = issued["objective"]
    oid = str(issued["outcome_id"])
    try:
        env = build_objective_scope(root, oid, desc, wl)
    except ObjectiveScopeError as exc:
        raise Refusal("ISSUE_OBJECTIVE_SCOPE", str(exc))
    out = root / batch_scope_path(env)
    if not out.is_file():
        out.parent.mkdir(parents=True, exist_ok=True)
        write_canonical(out, env)
    want = set((desc.get("identities") or {}).values())
    items = sorted(str(i["id"]) for i in (wl or {}).get("items") or []
                   if isinstance(i, dict) and (str(i.get("identity") or "") in want or str(i.get("id") or "") in want))
    kinds = {str(c.get("kind") or "") for c in (wl or {}).get("clusters") or [] if c.get("id") in {u["cluster"] for u in desc.get("units") or []}}
    kind = kinds.pop() if len(kinds) == 1 else "compile"
    paths = sorted(desc.get("paths") or [])
    return {"id": issued["cluster"], "kind": kind, "path": paths[0] if paths else "", "write_set": paths, "items": items,
            "retry_key": (issued.get("budget") or {}).get("key") or issued["cluster"],
            "batch_scope": {"path": batch_scope_path(env).as_posix(), "digest": env["digest"], "rule": env["rule"],
                            "kind": env["kind"], "family_id": "", "unit_id": env["unit_id"], "members": len(env["members"])},
            "unit": {"unit_id": env["unit_id"], "rule": env["rule"], "symbols": env["symbols"],
                     "target_symbols": env["target_symbols"], "completion": env["completion"],
                     "constituents": [c["cluster"] for c in env["children"]]}}


def _ids() -> tuple[str, int]:
    task = (os.environ.get("HERMES_KANBAN_TASK") or "").strip()
    try:
        run_id = int((os.environ.get("HERMES_KANBAN_RUN_ID") or "0").strip() or 0)
    except ValueError:
        run_id = 0
    return task, run_id


def _refused(root: Path, task: str, run_id: int, code: str, detail: str) -> int:
    """Print a typed refusal. The third identical refusal in one run parks
    this card's candidate and answers REPEATED_REFUSAL: kanban_block is the
    only legal next step (v20 t_686c715b repeated one refused command 181x)."""
    try:
        count = NC.note_refusal(root, task, run_id, code) if task and run_id else 0
    except OSError:
        count = 0
    if count >= NC.REPEAT_LIMIT:
        parked = ""
        try:
            board = NC.board_for(root)
            # only a candidate THIS run was issued is parked here: edits left by another
            # card are never attached to this one (the block then names the drift)
            if any(int(r.get("run") or 0) == int(run_id) for r in board.records(task, "issue")):
                got = NC.park(root, board, task_id=task, run_id=run_id)
                parked = "; candidate parked: %s" % (", ".join(got.get("parked") or []) or "none")
            else:
                parked = "; nothing parked (this run was never issued)"
        except Exception as exc:  # noqa: BLE001 - the stop stands whatever the park does
            parked = "; park not possible (%s)" % getattr(exc, "code", type(exc).__name__)
        print(json.dumps({"refused": "REPEATED_REFUSAL", "detail": "%s refused %d times in this run (%s)%s. The only legal "
                          "next step is kanban_block kind=needs_input naming %s; every other tool is refused for this run."
                          % (code, count, detail[:300], parked, code)}))
        return 1
    print(json.dumps({"refused": code, "detail": detail}))
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="native_gate.py")
    ap.add_argument("--root", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("publish")
    pb.add_argument("--plan-file", default="", help="qualification mode only: publish this derived plan revision")
    sub.add_parser("preview")
    sub.add_parser("readback")
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
    r.add_argument("--verdict-file", default=str(VERDICT))
    sub.add_parser("m4-repair")
    pu = sub.add_parser("push")
    pu.add_argument("--remote", default="origin")
    pu.add_argument("--ref", default="refs/heads/main")
    sub.add_parser("account")
    sub.add_parser("handoff")
    vr = sub.add_parser("void-rejects", help="Operator: take rejections a harness defect caused out of the budget")
    vr.add_argument("--task", default="")
    vr.add_argument("--key", action="append", default=[], required=True)
    vr.add_argument("--reason", required=True)
    rd = sub.add_parser("reconcile-deferrals", help="Operator: lift a deferral this card's budget caused once it is no longer exhausted (idempotent; never mints)")
    rd.add_argument("--task", default="")
    rd.add_argument("--reason", required=True)
    ri = sub.add_parser("retire-issuance", help="Operator: move an EXPIRED verification/loop/issued.json into issued-history (refuses a live or retained one)")
    ri.add_argument("--reason", required=True)
    sub.add_parser("park")
    sub.add_parser("restore-parked")
    sub.add_parser("integrate")
    sub.add_parser("rebase")
    ns = ap.parse_args(argv)
    root = Path(ns.root).resolve()
    task, run_id = _ids()
    try:
        board = NC.board_for(root)
        if ns.cmd == "preview":
            from planner.outcome_checks import initial_plan_from_root
            from planner.outcome_protocol import execution_gate, select_protocol
            from planner.native_publish import pilot_plan
            plan = pilot_plan(root, NC.native_plan(initial_plan_from_root(root)), select_protocol(root).execution)
            out = {"preview": True, "gate": [list(g) for g in execution_gate(root)],
                   "execution": plan.get("execution") or {"policy": "serial"},
                   "nodes": [{k: n.get(k) for k in ("outcome_id", "title", "parents", "assignee")} for n in plan["nodes"]],
                   "counts": plan["counts"], "unresolved": [u["id"] for u in plan["unresolved"]]}
        elif ns.cmd == "publish":
            from planner.native_publish import publish_initial
            out = publish_initial(root, board, m2=task, plan_file=ns.plan_file)
            if out["gaps"]:
                print(json.dumps(out, indent=2, sort_keys=True))
                print("native graph read-back mismatch (resume with the same command; nothing is duplicated)", file=sys.stderr)
                return 1
            out["created_cards"] = [c["task_id"] for c in out["created"]]
        elif ns.cmd == "readback":
            from planner.native_publish import readback
            gaps = readback(board, board.plan(NC.run_id_of(root, board)))
            print(json.dumps({"gaps": gaps}, indent=2))
            return 0 if not gaps else 1
        elif ns.cmd == "issue":
            from planner import pilot as PL
            if PL.is_pilot_worktree(root):
                # a pilot pair worktree holds only tracked files: its run state is seeded from the main tree first
                try:
                    PL.seed(root, task=task, run=run_id)
                except ValueError as exc:
                    code, _, detail = str(exc).partition(" ")
                    return _refused(root, task, run_id, code, detail)
            out = NC.issue(root, board, task_id=task, run_id=run_id,
                           claim_lock=(os.environ.get("HERMES_KANBAN_CLAIM_LOCK") or "").strip(), replay_unchanged=True)
            out["issued_record"] = write_issued_projection(root, out)
        elif ns.cmd == "verdict":
            from planner.canonical import product_tree_sha256
            out = NC.record_verdict(root, board, task_id=task, run_id=run_id, verdict=ns.verdict,
                                    candidate=product_tree_sha256(root), attempt=ns.attempt, reason=ns.reason)
        elif ns.cmd == "accept-commit":
            out = NC.accept_commit(root, board, task_id=task, run_id=run_id, attempt=ns.attempt, commit=ns.commit,
                                   measurement={"classes": [c for c in ns.classes.split(",") if c],
                                                "scenarios": [s for s in ns.scenarios.split(",") if s]})
        elif ns.cmd == "restore-pending":
            from planner.canonical import product_tree_sha256
            out = NC.restore_pending(root, board, task_id=task, run_id=run_id, candidate_now=product_tree_sha256(root))
        elif ns.cmd == "restore-held":
            out = NC.restore_held(root, board, task_id=task, run_id=run_id)
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
            out = NC.record_assessment(root, board, task_id=task, run_id=run_id, verdict_doc=doc)
            out["next"] = ("kanban_request_review reviewer=reviewer" if out["accepted"] else
                           "python3 .hermes/kernel/native_gate.py --root . m4-repair, then kanban_block kind=dependency")
        elif ns.cmd == "m4-repair":
            out = NC.m4_repair(root, board, task_id=task, run_id=run_id)
        elif ns.cmd == "handoff":
            out = NC.handoff(root, board, task_id=task)
        elif ns.cmd == "void-rejects":
            by = (os.environ.get("HERMES_PROFILE") or "").strip().lower()
            out = {"voided": NC.void_rejects(board, task_id=ns.task or task, keys=ns.key, reason=ns.reason, by=by)}
            # a deferral the voided rejections caused goes with them, and only if the budget recovered
            out["deferrals"] = NC.reconcile_deferrals(root, board, task_id=ns.task or task, by=by, reason=ns.reason)
        elif ns.cmd == "reconcile-deferrals":
            out = NC.reconcile_deferrals(root, board, task_id=ns.task or task, reason=ns.reason,
                                         by=(os.environ.get("HERMES_PROFILE") or "").strip().lower())
        elif ns.cmd == "retire-issuance":
            out = NC.retire_issuance(root, board, reason=ns.reason,
                                     by=(os.environ.get("HERMES_PROFILE") or "").strip().lower())
        elif ns.cmd == "park":
            out = NC.park(root, board, task_id=task, run_id=run_id)
        elif ns.cmd == "restore-parked":
            out = NC.restore_parked(root, board, task_id=task, run_id=run_id)
        elif ns.cmd in ("integrate", "rebase"):
            from planner import pilot as PL
            fn = PL.integrate if ns.cmd == "integrate" else PL.rebase
            out = fn(root, board, task_id=task, run_id=run_id)
            if ns.cmd == "integrate":
                out["next"] = {
                    "INTEGRATED": "the candidate is the application's now: python3 .hermes/kernel/native_gate.py --root . handoff, "
                                  "then kanban_request_review reviewer=reviewer",
                    "CONFLICT": "the main tree changed under this candidate: python3 .hermes/kernel/native_gate.py --root . rebase, "
                                "then run-verify.sh and advance.py again here, then integrate",
                    "REJECTED": "the combined tree was not accepted (advance.py verdict above, recorded on this card): "
                                "python3 .hermes/kernel/native_gate.py --root . rebase, repair here, then integrate again",
                    "VERIFY_FAILED": "verification of the combined tree could not run; integrate again after the named tool failure",
                    "NOTHING_ISSUED": "the main tree issues this card nothing: follow the issue's next step",
                }.get(str(out.get("status")), "")
        elif ns.cmd == "push":
            out = NC.push(root, board, task_id=task, run_id=run_id, remote=ns.remote, ref=ns.ref)
        else:
            out = NC.progress_account(root, board, NC.run_id_of(root, board))
    except Refusal as exc:
        return _refused(root, task, run_id, exc.code, exc.detail)
    except Exception as exc:  # NativeError, OSError, ValueError: a typed stop, never a silent pass
        return _refused(root, task, run_id, getattr(exc, "code", "NATIVE_GATE_ERROR"), "%s: %s" % (type(exc).__name__, exc))
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
