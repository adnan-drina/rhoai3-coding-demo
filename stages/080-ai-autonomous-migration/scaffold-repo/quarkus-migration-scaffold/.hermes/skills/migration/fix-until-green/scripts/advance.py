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
  * the measure strictly decreased with no new mandatory obligation, or a
    typed gate/coverage outcome retained the candidate unaccepted;

  * verification ran in acceptance mode (diagnostic cannot promote or reject).

Accept → commit exactly the changed paths, snapshot the tool reports,
rebuild the work list, re-seal admission, and (unless --no-mint) mint the
next card. Reject → restore HEAD in index and working tree, restore the
accepted reports, count the attempt, re-seal; at the ADR threshold the
cluster is deferred and the loop STOPS (pilot rule): no next card.
Unknown / inconclusive measure → VERIFICATION_PENDING: retain the
candidate files, restore the accepted tree, do not count an attempt, do
not mint; terminator is kanban_block kind=needs_input.

--baseline records step 0 (the bootstrapped tree) without a comparison.
Exit 0 accepted; 1 reverted / deferred / pending / refused; 2 usage or no state.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loop_common import attempt_budget, attempts_spent, budget, candidate_sha256, classify_inconclusive, clear_pending, source_write_members, state_change_violations, catalog_property_mappings, ensure_hermes_lib, git, load_deferred, load_issued, load_state, load_steps, pending_for, product_paths_changed, profile_keys_lost_in_tree, publish_loop_state, restore_reports, revert_paths, save_deferred, save_pending_candidate, save_steps, snapshot_reports  # noqa: E402

ensure_hermes_lib()
from planner import pipeline  # noqa: E402
from planner.canonical import digest, load_json, write_canonical  # noqa: E402
from planner.dest_model import checked_exception_delta  # noqa: E402
from planner.decisions import load_decisions, max_attempts  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE, LOOP_ACCEPTED, LOOP_ISSUED, MTA_RESCAN_FINDINGS, VERIFY_RUN, WORKLIST  # noqa: E402
from planner.worklist import CHECKED_FAMILY_RULE, EXPOSED, RETAIN, UNPROVEN, assess_batch_scope, batch_scope_digest, build_worklist, gate_items, incidents_from_findings, item_ids, obligation_keys, progress  # noqa: E402


def _verify_meta(run: dict) -> dict:
    return {"mode": str(run.get("mode") or "acceptance"), "stages_ms": run.get("stages_ms") or {}, "total_ms": run.get("total_ms")}


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
    verify = _verify_meta(load_json(root / VERIFY_RUN) if (root / VERIFY_RUN).is_file() else {})
    issued = load_issued(root) or {}
    loci_before = [{"id": str(i.get("id") or i), "path": str(i.get("path") or ""), "line": i.get("line")}
                   for i in (cur.get("items") or []) if str(i.get("id") or i) in set(issued.get("items") or [])]
    if not loci_before:
        loci_before = [{"id": str(x)} for x in (issued.get("items") or [])]
    loci_after = [{"id": str(i.get("id")), "path": str(i.get("path") or ""), "line": i.get("line"),
                   "detail": str(i.get("detail") or i.get("message") or "")[:200]}
                  for i in (cur.get("items") or []) if str(i.get("id") or "").startswith("err:")]
    clear_pending(steps, cluster, why="rejected")
    revert_paths(root, changed)
    restore_reports(root)
    # the budget belongs to the problem, not to the card: gate + cause + file,
    # or the sealed repair-family identity. Read it from the issued record first:
    # after a sibling is exposed the candidate work list may no longer contain
    # this cluster id (v8 Owner → Pet, 2026-09-11).
    cur_list = load_json(root / WORKLIST) if (root / WORKLIST).is_file() else {}
    row = next((c for c in (cur_list.get("clusters") or []) if str(c.get("id")) == cluster), {})
    if str(issued.get("cluster") or "") == cluster and issued.get("retry_key"):
        key = str(issued["retry_key"])
    else:
        key = str(row.get("retry_key") or cluster)
    attempts = dict(steps.get("attempts") or {})
    attempts[key] = attempts_spent(steps, cluster, key) + 1
    steps["attempts"] = attempts
    steps.setdefault("retry_keys", {})[cluster] = key
    family = str((issued.get("batch_scope") or {}).get("rule") or "") == CHECKED_FAMILY_RULE
    legal_next = (("do not remint a single-file retry of this cluster: the family's remaining members stay in the "
                   "sealed write set. " if family else "") +
                  "Do not repeat this patch; the next brief names the previous diagnostic movement and this reason.")
    steps.setdefault("rejected", []).append({
        "cluster": cluster, "card": card, "measure": cur.get("measure"), "reason": reason,
        "changed": changed, "verify": verify, "loci_before": loci_before, "loci_after": loci_after,
        "write_set": list(issued.get("write_set") or []), "legal_next": legal_next,
        "patch_summary": sorted(changed), "retry_key": key,
        "budget": budget(steps, cluster, key, max_attempts(load_decisions(root))),
    })
    save_steps(root, steps)
    if (root / LOOP_ISSUED).is_file():
        (root / LOOP_ISSUED).unlink()
    limit = attempt_budget(steps, cluster, max_attempts(load_decisions(root)), key)
    rebuilt = build_worklist(root)
    if attempts[key] >= limit:
        deferred = load_deferred(root)
        if cluster not in deferred["clusters"]:
            deferred["clusters"].append(cluster)
            deferred["reasons"][cluster] = "%d of %d attempt(s) spent against %s; last: %s" % (attempts[key], limit, key, reason)
            save_deferred(root, deferred)
        rebuilt = build_worklist(root)
        pipeline.admit(root)
        publish_loop_state(root, rebuilt)
        print("DEFERRED %s after %d of %d attempt(s) against %s: %s → the loop STOPS here (kanban_block kind=needs_input naming the cluster). "
              "Operator: remove the cause, then record the clearance -- operator-step.py --clear-deferred %s with the product change, or "
              "--clear-deferred %s --disposition-only when the cause was a harness defect. The budget rises by what was spent; no attempt "
              "or card is deleted." % (cluster, attempts[key], limit, key, reason, cluster, cluster), file=sys.stderr)
        return 1
    rec = pipeline.admit(root)
    publish_loop_state(root, rebuilt)
    print("REVERTED %s attempt %d/%d (budget %s): %s" % (cluster, attempts[key], limit, key, reason), file=sys.stderr)
    if mint and rec.get("status") == "ADMITTED":
        # the same cluster, next attempt key: the retry is its own card (pilot v6
        # measured the gap — the skill promised the re-issue, nothing minted it)
        _mint(root, hermes)
    return 1


def _pending(root: Path, steps: dict, cluster: str, card: str, cur: dict, reason: str, changed: list[str], on_disk: str, cause: str = "") -> int:
    """Retain an unaccepted candidate when verification cannot conclude.

    Does not count an implementation attempt. Restores the accepted tree so
    Operator steps can land. Keeps issued.json so the same card can restore
    the candidate and re-verify; K4 must not mint a new attempt (pending
    blocks next_card). Terminator: kanban_block kind=needs_input naming the cluster."""
    run = load_json(root / VERIFY_RUN) if (root / VERIFY_RUN).is_file() else {}
    cause = cause or classify_inconclusive(cur.get("measure") or {}, run if isinstance(run, dict) else {})
    clear_pending(steps, cluster, why="replaced")
    issued = load_issued(root)
    row = save_pending_candidate(
        root,
        cluster=cluster,
        card=card,
        changed=changed,
        candidate_sha256_value=on_disk,
        measure=cur.get("measure") or {},
        reason=reason,
        cause=cause,
        run=run if isinstance(run, dict) else {},
        issued=issued if isinstance(issued, dict) else {},
    )
    revert_paths(root, changed)
    restore_reports(root)
    steps.setdefault("pending", []).append(row)
    save_steps(root, steps)
    rebuilt = build_worklist(root)
    pipeline.admit(root)
    publish_loop_state(root, rebuilt)
    print(
        "VERIFICATION_PENDING %s cause=%s card=%s: %s → retain the candidate; do not re-implement. "
        "When the prerequisite changes: python3 .hermes/skills/migration/fix-until-green/scripts/restore-pending.py --root . --cluster %s "
        "then bash run-verify.sh --mode acceptance and advance.py. Terminator: kanban_block kind=needs_input naming the cluster."
        % (cluster, cause, card, reason, cluster),
        file=sys.stderr,
    )
    return 1


def _continue(root: Path, steps: dict, cluster: str, card: str, cur: dict, reason: str, changed: list[str], on_disk: str,
              scope_doc: dict, reported: list[str], *, mint: bool, hermes: str) -> int:
    """RETAIN inside a sealed family: the SAME card continues, bounded.

    The compiler reports one unhandled checked exception at a time, so fixing
    one family member exposes the next. That is the family's own remaining
    work, inside the write set the card was sealed with; stopping the worker
    there (what VERIFICATION_PENDING did) turned a six-member repair into six
    Operator restores. So the candidate stays on the tree, nothing is
    reverted, no attempt is spent, and the continuation is recorded on the
    issued card. Bounded twice: at most one continuation per family member,
    and a continuation that did not move (the same member still reported) is
    a rejection, not another continuation."""
    issued = load_issued(root) or {}
    conts = list(issued.get("continuations") or [])
    bound = max(1, len(scope_doc.get("members") or []))
    if conts:
        stuck = sorted(set(conts[-1].get("reported") or []) & set(reported))
        if stuck:
            return _reject(root, steps, cluster, card, cur, "continuation %d did not move: %s is still reported" % (len(conts), ", ".join(stuck[:2])),
                           changed, mint=mint, hermes=hermes)
    if len(conts) >= bound:
        return _pending(root, steps, cluster, card, cur, "the sealed family allows %d continuation(s), one per member, and all are spent: %s" % (bound, reason),
                        changed, on_disk, cause="continuation-budget")
    conts.append({"n": len(conts) + 1, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "card": card,
                  "measure": (cur.get("measure") or {}).get("tuple"), "reported": sorted(reported),
                  "changed": sorted(changed), "candidate_sha256": on_disk})
    issued["continuations"] = conts
    write_canonical(root / LOOP_ISSUED, issued)
    print("CONTINUE %s continuation %d/%d card=%s: %s → the candidate stays on the tree and no attempt is spent. Repair the family "
          "members the brief lists (batch_scope) inside the sealed write set, then run-verify.sh --mode acceptance and advance.py "
          "again on THIS card. Not a verdict: do not kanban_complete or kanban_block." % (cluster, len(conts), bound, card, reason),
          file=sys.stderr)
    return 3


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
    steps = load_steps(root)
    on_disk = candidate_sha256(root)
    pending_row = pending_for(steps, args.cluster) if (not args.baseline and args.cluster) else None
    last_sha = str((steps["steps"][-1].get("candidate_sha256") if steps.get("steps") else "") or "")
    if pending_row and last_sha and on_disk == last_sha:
        print("REFUSE: LOOP_PENDING_NOT_RESTORED a VERIFICATION_PENDING candidate is retained for %s; restore-pending.py then run-verify.sh --mode acceptance (do not count an attempt)" % args.cluster, file=sys.stderr)
        return 1
    cur = load_json(root / WORKLIST)
    if digest(cur) != state.get("worklist_sha256"):
        print("FAIL: LOOP_STALE_STATE work list changed after verify", file=sys.stderr)
        return 2
    run = load_json(root / VERIFY_RUN) if (root / VERIFY_RUN).is_file() else {}
    if not args.baseline and isinstance(run, dict) and str(run.get("mode") or "acceptance") == "diagnostic":
        print("REFUSE: LOOP_DIAGNOSTIC_NOT_ACCEPTANCE diagnostic mode cannot promote or reject; run run-verify.sh --mode acceptance on this candidate", file=sys.stderr)
        return 1
    if on_disk != state.get("candidate_sha256"):
        # the tree changed after verification: the measure no longer describes it
        if args.baseline:
            print("FAIL: LOOP_CANDIDATE_CHANGED tree edited after run-verify.sh; run it again", file=sys.stderr)
            return 2
        changed = product_paths_changed(root)
        print("REFUSE: LOOP_CANDIDATE_CHANGED product tree edited after verification (verified %s, on disk %s); nothing promoted" % (str(state.get("candidate_sha256"))[:12], on_disk[:12]), file=sys.stderr)
        if pending_row:
            return 1
        if steps["steps"] and args.cluster:
            _reject(root, steps, args.cluster, args.card, cur, "tree edited after verification", changed)
        else:
            revert_paths(root, changed)
        return 1
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
    # An amendment is the only way the write set grows, and it is only an
    # authority if it was granted BEFORE the file moved. Acceptance re-checks
    # that: a recorded amendment whose file was already dirty when it was
    # granted authorized nothing.
    bad_amendments = [a for a in (issued.get("amendments") or [])
                      if not a.get("granted_before_sha256") or a.get("dirty_at_grant")]
    if bad_amendments:
        return _reject(root, steps, args.cluster, args.card, cur,
                       "amendment(s) without authority: %s were added to the write set after the file had already been "
                       "edited, so no card ever authorized the change" % ", ".join(str(a.get("path")) for a in bad_amendments[:3]),
                       changed, mint=not args.no_mint, hermes=args.hermes)
    outside = [p for p in changed if p not in allowed]
    if outside:
        return _reject(root, steps, args.cluster, args.card, cur, "changed path(s) outside the write set: %s" % ",".join(outside[:5]), changed, mint=not args.no_mint, hermes=args.hermes)
    lost = profile_keys_lost_in_tree(root, changed, catalog_property_mappings(root))
    if lost:
        detail = "; ".join("%s: %s" % (p, ",".join(k[:4])) for p, k in sorted(lost.items()))
        return _reject(root, steps, args.cluster, args.card, cur, "profile config lost (the obligation was satisfied by withdrawing behavior): %s did not land in application.properties as %%<profile>.<key>" % detail, changed, mint=not args.no_mint, hermes=args.hermes)
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
    # SI-1: a member the SOURCE implemented as a state change must still
    # perform one. The rule is the contract, not a naming convention: a
    # @Modifying UPDATE/DELETE/INSERT passes, a query this rule cannot read is
    # inconclusive and recorded, and a write answered with a read fails.
    si1_writes = source_write_members(root)
    si1_bad: list[dict] = []
    si1_unknown: list[dict] = []
    for rel in changed:
        if not rel.endswith(".java"):
            continue
        f = root / rel
        if not f.is_file():
            continue
        bad, unknown = state_change_violations(f.read_text(encoding="utf-8", errors="replace"), si1_writes)
        for row in bad + unknown:
            row["path"] = rel
        si1_bad.extend(bad)
        si1_unknown.extend(unknown)
    if si1_bad:
        return _reject(root, steps, args.cluster, args.card, cur,
                       "%s: %s" % (si1_bad[0]["rule"], "; ".join("%s %s" % (r["path"].rsplit("/", 1)[-1], r["detail"]) for r in si1_bad[:3])),
                       changed, mint=not args.no_mint, hermes=args.hermes)
    if si1_unknown:
        print("WARN: %s inconclusive on %s (not a pass and not a violation): %s"
              % (si1_unknown[0]["rule"], ", ".join(sorted({r["path"] for r in si1_unknown})),
                 "; ".join(r["detail"] for r in si1_unknown[:2])), file=sys.stderr)
    # A proven newly INTRODUCED unhandled checked exception vetoes acceptance
    # even when the tuple falls (architect decision 3, 2026-09-11). javac
    # reports one such site per compilation, so a count can fall while a
    # transformation introduces six: t_cef8a0f6 took the compile count from 29
    # to 16 by writing six unhandled URI constructors, and was accepted. The
    # obligation is compiler-derived: baseline (the last accepted commit) and
    # candidate are modelled under the same compiler configuration, catches
    # and declared throws accounted for; a site the baseline already had is
    # EXPOSED, not introduced; incomplete baseline coverage is INCONCLUSIVE.
    java_changed = [c for c in changed if c.startswith("src/main/java/") and c.endswith(".java")]
    checked: dict = {}
    if java_changed:
        checked = checked_exception_delta(root, str(prev.get("commit") or "HEAD"), java_changed)
        vetoes = (["%s.%s calls %s: %s unhandled (%s)" % (r["type"].rsplit(".", 1)[-1], r["member_id"], r["callee"], r["exception"], r.get("proof") or "")
                   for r in checked["introduced"]] +
                  ["%s.%s now declares %s" % (r["type"].rsplit(".", 1)[-1], r["member_id"], ",".join(r["exceptions"])) for r in checked["throws_added"]])
        if vetoes:
            return _reject(root, steps, args.cluster, args.card, cur,
                           "introduced %d unhandled checked exception(s), a compiler-derived obligation that vetoes acceptance whatever the measure does: %s"
                           % (len(vetoes), "; ".join(vetoes[:4])), changed, mint=not args.no_mint, hermes=args.hermes)
        if checked["state"] in ("unavailable", "inconclusive"):
            return _pending(root, steps, args.cluster, args.card, cur,
                            "whether this candidate introduces an unhandled checked exception could not be decided: %s"
                            % (checked["why"] or "; ".join("%s (%s)" % (r.get("key") or r.get("path"), r.get("why")) for r in checked["inconclusive"][:2])),
                            changed, on_disk, cause="unassessable-exceptions")
    # The SEALED SCOPE: a repository card carries an inventory of every member
    # the declared rule reaches, and the card is not finished while one of them
    # still breaks that rule. An already-correct member needs no edit and earns
    # no credit either way; only the assessment counts, and it is made here from
    # the tree rather than from anything the worker wrote.
    scope_ref = issued.get("batch_scope") or {}
    scope_rows: list[dict] = []
    scope_doc: dict = {}
    family = False
    bad: list[dict] = []
    family_detail = ""
    if scope_ref:
        scope_doc = load_json(root / str(scope_ref.get("path") or "")) if (root / str(scope_ref.get("path") or "")).is_file() else {}
        if not scope_doc:
            return _reject(root, steps, args.cluster, args.card, cur,
                           "the card's scope inventory %s is not on disk, so no member can be assessed" % scope_ref.get("path"),
                           changed, mint=not args.no_mint, hermes=args.hermes)
        if batch_scope_digest(scope_doc) != str(scope_ref.get("digest") or ""):
            return _reject(root, steps, args.cluster, args.card, cur,
                           "the scope inventory on disk is not the one sealed with the card",
                           changed, mint=not args.no_mint, hermes=args.hermes)
        scope_rows = assess_batch_scope(root, scope_doc)
        bad = [r for r in scope_rows if r.get("verdict") == "violates"]
        family = str(scope_doc.get("rule") or "") == CHECKED_FAMILY_RULE
        target = str(scope_doc.get("repository") or scope_doc.get("signature") or scope_doc.get("rule") or "scope")
        family_detail = "%s member(s) of %s still break %s: %s" % (
            len(bad), target, scope_doc.get("rule"), "; ".join("%s (%s)" % (r["member"], r["detail"]) for r in bad[:4]))
        # A family member still unhandled is the family's REMAINING work, which
        # the measure below decides about (continue, or reject when the issued
        # one is still reported). A repository member is judged here.
        if bad and not family:
            return _reject(root, steps, args.cluster, args.card, cur, family_detail,
                           changed, mint=not args.no_mint, hermes=args.hermes)
        # An assessment that could not be made is not an assessment that
        # passed. The card cannot complete on a member nobody could resolve;
        # that is a prerequisite to repair, not an attempt to spend.
        unknown = [r for r in scope_rows if r.get("verdict") == "inconclusive"]
        if unknown:
            return _pending(root, steps, args.cluster, args.card, cur,
                            "%s member(s) of %s could not be assessed against %s: %s" % (
                                len(unknown), scope_doc.get("repository"), scope_doc.get("rule"),
                                "; ".join("%s (%s)" % (r["member"], r["detail"]) for r in unknown[:3])),
                            changed, on_disk, cause="unassessable-scope")
    gate = str(issued.get("gate") or "")
    # identities without lines: whether the issued failure is "still reported"
    cur_identities = {str(i.get("identity")) for i in (cur.get("items") or []) if str(i.get("source") or "") == "javac" and i.get("identity")}
    issued_identities = {str(v) for v in (issued.get("item_identities") or {}).values() if v} or None
    family_keys = ({"chk:" + str(m.get("member") or "") for m in (scope_doc.get("members") or [])}
                   if scope_ref and family else None)
    ok, reason = progress(prev["measure"], cur["measure"], prev_keys, cur_keys,
                          gate=gate,
                          prev_runtime=prev.get("runtime") or {}, cur_runtime=cur.get("runtime") or {},
                          issued_items=list(issued.get("items") or []),
                          prev_gate_items=set(str(i) for i in (issued.get("gate_items") or [])),
                          cur_gate_items=gate_items(cur, gate),
                          cur_item_ids=item_ids(cur),
                          issued_identities=issued_identities,
                          cur_identities=cur_identities if issued_identities is not None else None,
                          family_scope=family_keys)
    if not ok:
        if ok is RETAIN:
            # the compiler moved to another member of THIS card's sealed family
            return _continue(root, steps, args.cluster, args.card, cur, reason, changed, on_disk, scope_doc,
                             sorted(cur_identities - set(issued_identities or ())), mint=not args.no_mint, hermes=args.hermes)
        if ok is EXPOSED:
            # outside every sealed scope: a typed diagnosis, the candidate kept
            return _pending(root, steps, args.cluster, args.card, cur, reason, changed, on_disk, cause="exposed-outside-scope")
        if ok is UNPROVEN:
            # the repair may well be right and the gate cannot say so yet
            return _pending(root, steps, args.cluster, args.card, cur, reason, changed, on_disk, cause="unproven-repair")
        if not (cur.get("measure") or {}).get("known"):
            return _pending(root, steps, args.cluster, args.card, cur, reason, changed, on_disk)
        clear_pending(steps, args.cluster, why="rejected")
        return _reject(root, steps, args.cluster, args.card, cur, reason, changed, mint=not args.no_mint, hermes=args.hermes)
    if scope_ref and family and bad:
        # the measure fell and a member still breaks the family's rule (caught,
        # declared, or its operation deleted): that is not a repair
        return _reject(root, steps, args.cluster, args.card, cur, family_detail, changed, mint=not args.no_mint, hermes=args.hermes)
    clear_pending(steps, args.cluster, why="accepted")
    sha = _commit(root, changed, "fix-until-green: %s attempt %s %s" % (args.cluster, issued.get("attempt"), cur["measure"]["tuple"]))
    snapshot_reports(root)
    steps["steps"].append({"cluster": args.cluster, "card": args.card, "attempt": issued.get("attempt"), "idempotency_key": issued.get("idempotency_key"), "commit": sha, "candidate_sha256": on_disk, "measure": cur["measure"], "item_ids": sorted(item_ids(cur)), "obligation_keys": sorted(obligation_keys(cur)), "worklist_sha256": digest(cur), "changed": changed, "verdict": "accepted", "reason": reason, "runtime": cur.get("runtime") or {}, "gate": str(issued.get("gate") or ""), "discharged": sorted(str(i) for i in (issued.get("items") or [])), "si1_inconclusive": si1_unknown, "batch_scope": ({"digest": str(scope_ref.get("digest") or ""), "assessed": len(scope_rows),
                                                          "inconclusive": [r for r in scope_rows if r.get("verdict") == "inconclusive"]} if scope_ref else {}), "amendments": list(issued.get("amendments") or []), "verify": _verify_meta(run if isinstance(run, dict) else {}),
                           "continuations": list(issued.get("continuations") or []),
                           "checked_exceptions": ({k: (checked.get(k) if k in ("state", "base", "coverage") else len(checked.get(k) or []))
                                                   for k in ("state", "base", "introduced", "exposed", "resolved", "throws_added", "inconclusive", "coverage")}
                                                  if checked else {})})
    save_steps(root, steps)
    (root / LOOP_ISSUED).unlink()
    print("OK: ACCEPTED %s (%s) commit %s" % (args.cluster, reason, sha[:12]))
    rebuild = build_worklist(root)
    rec = pipeline.admit(root)
    # published either way: the accepted step is on record whether or not the
    # next card can be admitted, and the state must describe it
    publish_loop_state(root, rebuild)
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
