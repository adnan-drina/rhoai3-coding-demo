#!/usr/bin/env python3
"""Operator step: record a decided change to the product tree as a loop step.

Some changes are decisions, not card work: an ADR accepted after M2 retires
source files (bootstrap-destination.py --retire-only deletes them). The loop
record must carry that change like any accepted step, or the next card's
baseline is wrong (its measure and obligation keys describe a tree that no
longer exists) and a rewind would restore the retired files.

What it does (every check refuses before it changes anything):
  * refuses with a LIVE issued card (a worker's candidate may be on the tree:
    let it finish, or revert it with rewind.py --close-card) or with nothing
    changed in the product tree -- except --disposition-only, which refuses
    WITH a change (see below). An issued card whose candidate is RETAINED
    (VERIFICATION_PENDING: an uncleared pending row for its cluster, the
    candidate aside under verification/loop/pending-files/) is not live, and
    the step is recorded BESIDE it: the accepted tree is on disk, the card is
    kept untouched, and nothing is minted whatever --no-mint says, because the
    pending card still owns the head. That case is not a corner: the
    prerequisite a pending card waits for is sometimes Operator-owned
    (ADR-008: the port of a retained Spring test), and refusing there leaves
    the protocol with no way to resume;
  * refuses a change to test sources that names no ADR, or no independent
    reviewer, or a reviewer equal to the operator (ADR-008);
  * refuses --clear-deferred for a cluster that is not deferred, and lifts a
    deferral only after the re-measure of the committed tree succeeded (a
    deferral is lifted by a measured tree, never by the intent to fix it);
    the clearance is appended as a disposition and raises the attempt budget --
    neither the attempts nor the cards they minted are ever removed;
  * --disposition-only records a clearance whose cause was removed OUTSIDE the
    product tree (a harness correction): no commit, no step, the product tree
    must be clean and the current verification must describe it. The same
    lineage is recorded; the budget rises the same way;
  * commits exactly the changed product paths with the operator and reason;
  * RE-MEASURES the tree (run-verify.sh; --verify-cmd overrides for tests);
  * appends a step {verdict: operator, adr, operator, reason, commit,
    measure, obligation_keys, beside_pending} to verification/loop/steps.json,
    snapshots the reports as the accepted state (so the pending card's later
    advance measures against THIS step, not the one before it), rebuilds the
    work list, re-seals admission and (unless --no-mint, or unless the step
    was recorded beside a pending card) mints the next card.

Exit 0 recorded; 1 refused; 2 usage.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loop_common import attempts_spent, candidate_sha256, ensure_hermes_lib, git, load_deferred, load_issued, load_state, load_steps, pending_for, product_paths_changed, publish_loop_state, retry_key_for, save_deferred, parity_not_of_this_tree, save_steps, snapshot_reports  # noqa: E402

ensure_hermes_lib()
from planner import pipeline  # noqa: E402
from planner.canonical import load_json  # noqa: E402
from planner.paths import WORKLIST  # noqa: E402
from planner.worklist import build_worklist, obligation_keys  # noqa: E402

RUN_VERIFY = Path(__file__).resolve().parent / "run-verify.sh"
RESUME = ("python3 .hermes/skills/migration/fix-until-green/scripts/restore-pending.py --root . --cluster %s, "
          "then bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root . --mode acceptance, "
          "then advance.py --root . --cluster %s --card %s")


def _refuse(msg: str) -> int:
    print("REFUSE: LOOP_OPERATOR_STEP %s" % msg, file=sys.stderr)
    return 1


def _beside_pending(root: Path, steps: dict) -> tuple[dict | None, int | None]:
    """(the pending row this step would stand beside, refusal) for the issued card.

    An issued card is LIVE when no uncleared pending row names its cluster: a
    worker's candidate may be on the product tree, and a step recorded over it
    would commit the worker's unaccepted work as the Operator's. A card whose
    candidate is RETAINED is the opposite: the tree is the accepted tree, the
    candidate is aside under pending-files, and what the card waits for may be
    exactly this step (advance.py's own instruction: "when the prerequisite
    changes, restore-pending then run-verify then advance"). So the retained
    case records the step and keeps the card; only the live case refuses."""
    issued = load_issued(root)
    if issued is None:
        return None, None
    cluster = str(issued.get("cluster") or "")
    row = pending_for(steps, cluster) if cluster else None
    if row is None:
        return None, _refuse("an issued card is live (%s, cluster %s); let it finish or revert it (rewind.py --close-card)"
                             % (str(issued.get("task_id") or "no card"), cluster or "unknown"))
    return {"cluster": cluster,
            "card": str(row.get("card") or issued.get("task_id") or ""),
            "cause": str(row.get("cause") or "")}, None


def _append_clearances(steps: dict, cleared: list[str], args: argparse.Namespace, reasons: dict, *, kind: str, commit: str) -> None:
    """The history is append-only. The rejected rows are the record of which
    cards a cluster minted -- the live-board comparator expects every one of
    them as a closed card, and dropping a row made three real cards foreign
    on pilot v7 -- and the attempt count is what the record says the problem
    spent. So a clearance appends a disposition that names BOTH identities
    (cluster and retry key) and what was spent against the key, and the
    budget resolver raises the limit from there (planner.budget)."""
    for c in cleared:
        key = retry_key_for(steps, c)
        steps.setdefault("deferral_clearances", []).append({
            "cluster": c, "retry_key": key, "kind": kind, "commit": commit,
            "operator": args.operator, "reason": args.reason,
            "at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "attempts": attempts_spent(steps, c, key),
            "cards": [str(r.get("card") or "") for r in (steps.get("rejected") or [])
                      if (str(r.get("cluster") or "") == c or str(r.get("retry_key") or "") == key) and r.get("card")],
            "was_deferred_because": str(reasons.get(c) or ""),
        })
    for r in steps.get("rejected") or []:
        if str((r or {}).get("cluster") or "") in set(cleared):
            r["deferral_cleared_by"] = args.operator


def _disposition_only(root: Path, args: argparse.Namespace, steps: dict, deferred: dict, open_clusters: list[str], changed: list[str], beside: dict | None = None) -> int:
    """A clearance whose cause was removed outside the product tree.

    Nothing is committed and no step is appended: the product did not change,
    so the last step still describes it. What is required instead is that the
    CURRENT verification describes this tree (a deferral is lifted by a
    measured tree, never by the intent to fix it) and that the measure is
    known."""
    if not args.clear_deferred:
        return _refuse("--disposition-only records a --clear-deferred disposition; name the cluster")
    if changed:
        return _refuse("--disposition-only is for a cause removed outside the product tree, and the product tree has changes: %s" % ", ".join(changed[:3]))
    state = load_state(root)
    if not state or str(state.get("candidate_sha256") or "") != candidate_sha256(root):
        return _refuse("the current verification does not describe this tree; run run-verify.sh --mode acceptance first")
    if not (state.get("measure") or {}).get("known"):
        return _refuse("the measure is not known: %s" % (state.get("measure") or {}).get("blocked"))
    cleared = [c for c in open_clusters if c in set(args.clear_deferred)]
    reasons = dict(deferred.get("reasons") or {})
    deferred["clusters"] = [c for c in open_clusters if c not in set(cleared)]
    deferred["reasons"] = {k: v for k, v in reasons.items() if k not in set(cleared)}
    save_deferred(root, deferred)
    head = str((steps.get("steps") or [{}])[-1].get("commit") or "")
    _append_clearances(steps, cleared, args, reasons, kind="metadata-only", commit=head)
    save_steps(root, steps)
    rebuilt = build_worklist(root)
    rec = pipeline.admit(root)
    publish_loop_state(root, rebuilt)
    print("OK: DISPOSITION %s cleared by %s (metadata only: no commit, no step; the last step %s still describes the tree) admission %s"
          % (", ".join(cleared), args.operator, head[:12], rec.get("status")))
    if rec.get("status") != "ADMITTED":
        print("REFUSE: LOOP_ADMISSION %s: %s" % (rec["status"], "; ".join(rec.get("reasons") or [])[:300]), file=sys.stderr)
        return 1
    if beside:
        print("   beside VERIFICATION_PENDING %s (card %s): the card stays issued and nothing is minted. Resume it with %s"
              % (beside["cluster"], beside["card"] or "none", RESUME % (beside["cluster"], beside["cluster"], beside["card"] or "<card>")))
        return 0
    if args.no_mint:
        return 0
    from advance import _mint  # noqa: E402

    return _mint(root, args.hermes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--operator", required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--clear-deferred", action="append", default=[], help="a cluster deferred to a human (ADR-002 max_attempts) whose cause this change removes: drop it from verification/loop/deferred.json and append a disposition that raises its budget by what it had spent (attempts and cards are never deleted), so the loop can issue it again; repeatable, and refused for a cluster that is not deferred")
    ap.add_argument("--disposition-only", action="store_true", help="record the --clear-deferred disposition WITHOUT a product change (the cause was a harness defect, since corrected): no commit and no step; refused when the product tree has changes or the current verification does not describe it")
    ap.add_argument("--author", default="", help="the seat that wrote the change, when it is not the operator (recorded, never inferred)")
    ap.add_argument("--reviewer", default="", help="the seat that independently reviewed the change; required, and distinct from --operator, when the change touches test sources (ADR-008)")
    ap.add_argument("--adr", default="", help="the accepted ADR(s) this change applies, e.g. ADR-004,ADR-005")
    ap.add_argument("--verify-cmd", default="")
    ap.add_argument("--no-mint", action="store_true")
    ap.add_argument("--hermes", default="hermes")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    steps = load_steps(root)
    if not steps.get("steps"):
        return _refuse("no baseline step recorded")
    beside, refused = _beside_pending(root, steps)
    if refused is not None:
        return refused
    deferred = load_deferred(root)
    open_clusters = list(deferred.get("clusters") or [])
    unknown = [c for c in args.clear_deferred if c not in open_clusters]
    if unknown:
        return _refuse("--clear-deferred names %s, which %s deferred; open deferrals: %s" % (", ".join(unknown), "is not" if len(unknown) == 1 else "are not", ", ".join(open_clusters) or "none"))
    changed = product_paths_changed(root)
    if args.disposition_only:
        return _disposition_only(root, args, steps, deferred, open_clusters, changed, beside)
    if not changed:
        return _refuse("nothing changed in the product tree")
    if beside:
        # The step stands beside the pending card because the tree is the
        # ACCEPTED tree. If the retained candidate has been restored onto it,
        # it is not, and committing here would sign the worker's unaccepted
        # candidate as the Operator's change.
        row = pending_for(steps, beside["cluster"]) or {}
        own = set(row.get("changed") or []) | set(row.get("stored") or []) | set(row.get("deleted") or [])
        clash = sorted(set(changed) & own)
        if clash:
            return _refuse("the retained candidate for %s is back on the product tree (%s); an operator step beside a pending card records "
                           "the Operator's change on the accepted tree -- revert those paths (the candidate is kept under %s) and re-run"
                           % (beside["cluster"], ", ".join(clash[:3]), row.get("files_dir") or "verification/loop/pending-files/"))
    # A test source states what the destination must do. An operator may change
    # one only under an ADR and only with a second seat naming itself; without
    # that, the intervention is one seat editing both the claim and its proof.
    tests = [c for c in changed if c.startswith("src/test/") or "/src/test/" in c]
    if tests:
        if not args.adr:
            return _refuse("the change touches test sources and names no ADR: %s" % ", ".join(tests[:3]))
        if not args.reviewer:
            return _refuse("the change touches test sources and names no reviewer (--reviewer): %s" % ", ".join(tests[:3]))
        if args.reviewer.strip() == args.operator.strip():
            return _refuse("the reviewer of a test-source change must be a seat other than the operator (%s): %s" % (args.operator, ", ".join(tests[:3])))
    git(root, "reset", "-q")
    git(root, "add", "-A", "--", *changed)
    msg = "fix-until-green: operator step by %s%s: %s" % (args.operator, (" (%s)" % args.adr) if args.adr else "", args.reason)
    proc = git(root, "-c", "user.email=fix-until-green@local", "-c", "user.name=fix-until-green", "commit", "-q", "-m", msg)
    if proc.returncode != 0:
        return _refuse("commit failed: %s" % proc.stderr.strip()[:200])
    sha = git(root, "rev-parse", "HEAD").stdout.strip()
    cmd = shlex.split(args.verify_cmd) if args.verify_cmd else ["bash", str(RUN_VERIFY), "--root", str(root)]
    run = subprocess.run(cmd, text=True, capture_output=True)
    sys.stdout.write(run.stdout[-2000:])
    if run.returncode != 0:
        return _refuse("re-measure exited %d after the commit %s (the commit stands; fix the tool and re-run run-verify.sh): %s" % (run.returncode, sha[:12], run.stderr.strip()[-300:]))
    state = load_state(root)
    if not state or not (state.get("measure") or {}).get("known"):
        return _refuse("measure not known after the commit %s: %s" % (sha[:12], (state or {}).get("measure")))
    cur = load_json(root / WORKLIST)
    # F2: the step changed the product; a parity receipt of the tree before it
    # is not this tree's baseline
    stale = parity_not_of_this_tree(root)
    snapshot_reports(root, parity_unmeasured=("operator step %s changed the product and %s" % (sha[:12], stale)) if stale else "",
                     commit=sha, by=args.operator)
    cleared: list[str] = []
    if args.clear_deferred:
        cleared = [c for c in open_clusters if c in set(args.clear_deferred)]
        reasons = dict(deferred.get("reasons") or {})
        deferred["clusters"] = [c for c in open_clusters if c not in set(cleared)]
        deferred["reasons"] = {k: v for k, v in (deferred.get("reasons") or {}).items() if k not in set(cleared)}
        save_deferred(root, deferred)
        # The history is append-only. The rejected rows are the record of which
        # cards this cluster minted -- the live-board comparator expects every
        # one of them as a closed card, and dropping a row made three real
        # cards foreign on pilot v7 -- and the attempt count is what the record
        # says the cluster spent. So clearing a deferral appends a disposition
        # and RAISES the budget (attempt_budget) instead of deleting either.
        _append_clearances(steps, cleared, args, reasons, kind="operator-step", commit=sha)
    step = {
        "cluster": "operator", "card": "", "attempt": 0, "verdict": "operator",
        "operator": args.operator, "author": args.author or args.operator, "reviewer": args.reviewer, "adr": args.adr, "reason": args.reason,
        "at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": sha, "candidate_sha256": str(state.get("candidate_sha256") or ""),
        "measure": state["measure"], "obligation_keys": sorted(obligation_keys(cur)), "changed": changed,
        "cleared_deferred": cleared,
    }
    if beside:
        step["beside_pending"] = dict(beside)
        step["mint"] = ("withheld: the VERIFICATION_PENDING card %s still owns the head; it resumes on this step"
                        % (beside["card"] or beside["cluster"]))
    steps["steps"].append(step)
    save_steps(root, steps)
    rebuilt = build_worklist(root)
    rec = pipeline.admit(root)
    publish_loop_state(root, rebuilt)
    print("OK: OPERATOR STEP %s (%d path(s), measure %s%s) admission %s" % (sha[:12], len(changed), state["measure"]["tuple"], "; deferral cleared: " + ", ".join(cleared) if cleared else "", rec.get("status")))
    if beside:
        print("   beside VERIFICATION_PENDING %s (card %s, cause %s): the card stays issued and nothing is minted -- this step is its new "
              "baseline. Resume it with %s" % (beside["cluster"], beside["card"] or "none", beside["cause"] or "unknown",
                                               RESUME % (beside["cluster"], beside["cluster"], beside["card"] or "<card>")))
    if rec.get("status") != "ADMITTED":
        print("REFUSE: LOOP_ADMISSION %s: %s" % (rec["status"], "; ".join(rec.get("reasons") or [])[:300]), file=sys.stderr)
        return 1
    if beside:
        return 0
    if args.no_mint:
        return 0
    from advance import _mint  # noqa: E402

    return _mint(root, args.hermes)


if __name__ == "__main__":
    raise SystemExit(main())
