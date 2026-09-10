#!/usr/bin/env python3
"""The acceptance transaction: promote the verified candidate or discard it.

A candidate is the product tree exactly as verify.py measured it. advance.py
refuses unless ALL of these hold, and never touches the accepted baseline
otherwise:

  * an issued card exists (verification/loop/issued.json, written by K4) and
    --cluster / --card name it (an unknown cluster or card is refused);
  * the product tree on disk still has the identity verify.py recorded
    (an edit after verification is refused and reverted);
  * every changed product path is inside the issued cluster's write set
    (tests are never in a write set);
  * the measure strictly decreased with no new mandatory obligation.

Accept → commit exactly the changed paths, snapshot the tool reports,
rebuild the work list, re-seal admission, and (unless --no-mint) mint the
next card. Reject → restore HEAD in index and working tree, restore the
accepted reports, count the attempt, re-seal; at the ADR threshold the
cluster is deferred and the loop STOPS (pilot rule): no next card.

--baseline records step 0 (the bootstrapped tree) without a comparison.
Exit 0 accepted; 1 reverted / deferred / refused; 2 usage or no state.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loop_common import candidate_sha256, ensure_hermes_lib, git, load_cards, load_deferred, load_issued, load_state, load_steps, product_paths_changed, restore_reports, revert_paths, save_deferred, save_steps, snapshot_reports  # noqa: E402

ensure_hermes_lib()
from planner import pipeline  # noqa: E402
from planner.canonical import digest, load_json  # noqa: E402
from planner.decisions import load_decisions, max_attempts  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE, LOOP_ACCEPTED, LOOP_ISSUED, MTA_RESCAN_FINDINGS, WORKLIST  # noqa: E402
from planner.worklist import build_worklist, incidents_from_findings, item_ids, obligation_keys, progress  # noqa: E402


def _commit(root: Path, paths: list[str], message: str) -> str:
    git(root, "reset", "-q")  # nothing staged but what we add now
    if paths:
        git(root, "add", "--", *paths)
    proc = git(root, "-c", "user.email=fix-until-green@local", "-c", "user.name=fix-until-green", "commit", "-q", "--allow-empty", "-m", message)
    if proc.returncode != 0:
        raise SystemExit("FAIL: LOOP_COMMIT %s" % proc.stderr.strip()[:200])
    return git(root, "rev-parse", "HEAD").stdout.strip()


def _reject(root: Path, steps: dict, cluster: str, card: str, cur: dict, reason: str, changed: list[str], *, mint: bool = False, hermes: str = "hermes") -> int:
    """Discard the candidate, count the attempt, re-seal and re-issue the
    cluster (K4 mints the next attempt); defer + stop at the threshold."""
    revert_paths(root, changed)
    restore_reports(root)
    attempts = dict(steps.get("attempts") or {})
    attempts[cluster] = int(attempts.get(cluster, 0)) + 1
    steps["attempts"] = attempts
    steps.setdefault("rejected", []).append({"cluster": cluster, "card": card, "measure": cur.get("measure"), "reason": reason, "changed": changed})
    save_steps(root, steps)
    if (root / LOOP_ISSUED).is_file():
        (root / LOOP_ISSUED).unlink()
    limit = max_attempts(load_decisions(root))
    build_worklist(root)
    if attempts[cluster] >= limit:
        deferred = load_deferred(root)
        if cluster not in deferred["clusters"]:
            deferred["clusters"].append(cluster)
            deferred["reasons"][cluster] = "%d rejected attempt(s); last: %s" % (attempts[cluster], reason)
            save_deferred(root, deferred)
        build_worklist(root)
        pipeline.admit(root)
        print("DEFERRED %s after %d attempt(s): %s → the loop STOPS here (kanban_block kind=needs_input naming the cluster). Operator: fix the cause, then scripts/rewind.py --to-step N --operator WHO --reason WHY restores an accepted step with a fresh budget" % (cluster, attempts[cluster], reason), file=sys.stderr)
        return 1
    rec = pipeline.admit(root)
    print("REVERTED %s attempt %d/%d: %s" % (cluster, attempts[cluster], limit, reason), file=sys.stderr)
    if mint and rec.get("status") == "ADMITTED":
        # the same cluster, next attempt key: the retry is its own card (pilot v6
        # measured the gap — the skill promised the re-issue, nothing minted it)
        _mint(root, hermes)
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--cluster", default="", help="cluster id this step worked on (must be the issued card)")
    ap.add_argument("--card", default="", help="Hermes t_* id of this card (must be the issued card once minted)")
    ap.add_argument("--baseline", action="store_true", help="record step 0 (the bootstrapped tree): commit + measure, no comparison")
    ap.add_argument("--no-mint", action="store_true")
    ap.add_argument("--hermes", default=os.environ.get("HERMES_BIN", "hermes"))
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    state = load_state(root)
    if state is None:
        print("FAIL: LOOP_NOT_VERIFIED run run-verify.sh first", file=sys.stderr)
        return 2
    cur = load_json(root / WORKLIST)
    if digest(cur) != state.get("worklist_sha256"):
        print("FAIL: LOOP_STALE_STATE work list changed after verify", file=sys.stderr)
        return 2
    on_disk = candidate_sha256(root)
    if on_disk != state.get("candidate_sha256"):
        # the tree changed after verification: the measure no longer describes it
        if args.baseline:
            print("FAIL: LOOP_CANDIDATE_CHANGED tree edited after run-verify.sh; run it again", file=sys.stderr)
            return 2
        changed = product_paths_changed(root)
        steps = load_steps(root)
        print("REFUSE: LOOP_CANDIDATE_CHANGED product tree edited after verification (verified %s, on disk %s); nothing promoted" % (str(state.get("candidate_sha256"))[:12], on_disk[:12]), file=sys.stderr)
        if steps["steps"] and args.cluster:
            _reject(root, steps, args.cluster, args.card, cur, "tree edited after verification", changed)
        else:
            revert_paths(root, changed)
        return 1
    steps = load_steps(root)
    if args.baseline:
        if steps["steps"]:
            print("OK: baseline already recorded (%s)" % steps["steps"][0].get("commit", "")[:12])
            return 0
        if not cur["measure"].get("known"):
            print("FAIL: LOOP_BASELINE_UNKNOWN measure not fully known: %s" % "; ".join(cur["measure"].get("blocked") or []), file=sys.stderr)
            return 1
        changed = product_paths_changed(root)
        sha = _commit(root, changed, "fix-until-green: baseline %s" % cur["measure"]["tuple"])
        snapshot_reports(root)
        steps["steps"].append({"cluster": "bootstrap", "card": args.card, "commit": sha, "candidate_sha256": on_disk, "measure": cur["measure"], "item_ids": sorted(item_ids(cur)), "obligation_keys": sorted(obligation_keys(cur)), "worklist_sha256": digest(cur), "changed": changed, "verdict": "baseline", "reason": "bootstrap-destination baseline"})
        save_steps(root, steps)
        rec = pipeline.admit(root)
        print("OK: BASELINE recorded commit %s measure=%s admission=%s" % (sha[:12], cur["measure"]["tuple"], rec["status"]))
        return 0
    if not args.cluster:
        print("FAIL: pass --cluster <id> (or --baseline)", file=sys.stderr)
        return 2
    if not steps["steps"]:
        print("FAIL: LOOP_NO_BASELINE bootstrap step missing (bootstrap-destination + run-verify + advance --baseline)", file=sys.stderr)
        return 2
    issued = load_issued(root)
    changed = product_paths_changed(root)
    if issued is None or str(issued.get("cluster")) != args.cluster:
        print("REFUSE: LOOP_NOT_ISSUED %r is not the issued card (%s); nothing promoted, candidate discarded" % (args.cluster, (issued or {}).get("cluster", "none")), file=sys.stderr)
        revert_paths(root, changed)
        restore_reports(root)
        build_worklist(root)
        pipeline.admit(root)
        return 1
    if issued.get("task_id") and args.card != issued["task_id"]:
        print("REFUSE: LOOP_WRONG_CARD --card %r is not the minted card %s; nothing promoted, candidate discarded" % (args.card, issued["task_id"]), file=sys.stderr)
        revert_paths(root, changed)
        restore_reports(root)
        build_worklist(root)
        pipeline.admit(root)
        return 1
    allowed = set(issued.get("write_set") or [])
    outside = [p for p in changed if p not in allowed]
    if outside:
        return _reject(root, steps, args.cluster, args.card, cur, "changed path(s) outside the write set: %s" % ",".join(outside[:5]), changed, mint=not args.no_mint, hermes=args.hermes)
    prev = steps["steps"][-1]
    prev_keys = set(prev.get("obligation_keys") or [])
    cur_keys = obligation_keys(cur)
    if not prev_keys:
        # a step recorded before obligation_keys existed: rebuild the accepted
        # state's keys from its snapshotted rescan findings (the same tool
        # output the work list was built from); only if even that is absent
        # fall back to comparing the old content-hash ids on both sides.
        # (pilot v6 attempt 2 was vetoed on 23 "new" obligations because the
        # baseline's hash ids were compared against rule|file keys)
        snap = root / LOOP_ACCEPTED / MTA_RESCAN_FINDINGS.name
        if snap.is_file():
            bundle = load_json(root / EVIDENCE_BUNDLE)
            canary = str((bundle.get("migration") or {}).get("canary_rule_id") or "")
            prev_keys = obligation_keys({"items": incidents_from_findings(load_json(snap), [str(root), "/projects/modernized"], canary)})
        else:
            prev_keys = set(prev.get("item_ids") or [])
            cur_keys = item_ids(cur)
    ok, reason = progress(prev["measure"], cur["measure"], prev_keys, cur_keys)
    if not ok:
        return _reject(root, steps, args.cluster, args.card, cur, reason, changed, mint=not args.no_mint, hermes=args.hermes)
    sha = _commit(root, changed, "fix-until-green: %s attempt %s %s" % (args.cluster, issued.get("attempt"), cur["measure"]["tuple"]))
    snapshot_reports(root)
    steps["steps"].append({"cluster": args.cluster, "card": args.card, "attempt": issued.get("attempt"), "idempotency_key": issued.get("idempotency_key"), "commit": sha, "candidate_sha256": on_disk, "measure": cur["measure"], "item_ids": sorted(item_ids(cur)), "obligation_keys": sorted(obligation_keys(cur)), "worklist_sha256": digest(cur), "changed": changed, "verdict": "accepted", "reason": reason})
    save_steps(root, steps)
    (root / LOOP_ISSUED).unlink()
    print("OK: ACCEPTED %s (%s) commit %s" % (args.cluster, reason, sha[:12]))
    build_worklist(root)
    rec = pipeline.admit(root)
    if rec["status"] != "ADMITTED":
        print("REFUSE: LOOP_ADMISSION %s: %s" % (rec["status"], "; ".join(rec["reasons"][:3])), file=sys.stderr)
        return 1
    if args.no_mint:
        return 0
    return _mint(root, args.hermes)


def _mint(root: Path, hermes: str) -> int:
    """Trusted continuation: K4 mints the next card. The current card is a
    parent through steps.json, never the M2 control card."""
    kernel = root / ".hermes" / "kernel" / "k4_mint.py"
    env = dict(os.environ)
    env.pop("HERMES_KANBAN_TASK", None)  # control cards come from verification/loop/cards.json
    proc = subprocess.run([sys.executable, str(kernel), "--root", str(root), "--exec", "--verify-board", "--hermes", hermes], text=True, capture_output=True, env=env)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
