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
  * no ATTRIBUTION compile diagnostic (a symbol javac cannot resolve, a
    package that does not exist -- every code outside FLOW_CODES) is
    reported that the accepted tree did not report, in any file. javac
    reports all of those in one compilation, so one the accepted tree lacked
    was introduced by the candidate; only the flow-analysis codes are
    reported one at a time, and only they can be "exposed". Dest v9
    t_3903f495 (c:fb2e558f39a5, UriComponentsBuilder, 7 items, 6 files)
    replaced the builder with `@Context UriInfo` in six controllers -- the
    right repair -- but imported jakarta.ws.rs.Context instead of
    jakarta.ws.rs.core.Context: the 13 accepted diagnostics (6 doesnt.exist
    on org.springframework.web.util, 7 cant.resolve.location on
    UriComponentsBuilder) went and 13 new ones of the same shape came (6 bad
    imports, 7 @Context usages). Equal counts reached progress()'s identity
    branch, which found them outside the sealed family and parked the card
    for a human as exposed-outside-scope. It is REVERTED with the symbols
    named, so the next attempt fixes one import;

  * on a UNIT card that introduced set is PARTITIONED before the veto decides.
    A diagnostic inside the unit's FILE seal whose token resolves -- through
    the declaring file's imports -- to a symbol the unit SEALED, or to a
    replacement the catalogue DOCUMENTS with a row, is the unit's own work in
    progress: it is tolerated and recorded on the step as
    explained_regressions, and the build or config cluster that resolves it is
    the next card. Everything else is introduced and is rejected with the same
    message as before. jakarta.ws.rs.core.Context has a compat-mapping row and
    jakarta.ws.rs.Context does not, so t_3903f495 is explained by nothing and
    still REVERTS -- which is what the relaxation must never eat;

  * a UNIT card is then judged at its CHECKPOINT (worklist._unit_progress):
    its own sealed identities gone, every sealed member assessed clean from the
    tree, no regressed test or incident slot, no gate going backwards -- and,
    only then, a compile slot that may stand still or briefly rise for exactly
    what the partition above explained;

  * a card issued for the PARITY gate is judged by the comparison the
    acceptance path re-ran for its scenarios and for the READ ORACLES of its
    own entry points (run-verify.sh → run-parity.py --scenario … --read-oracle
    …; H3, dest v9 t_4d75569c: a read-oracle obligation names no scenario and
    is re-measured by nothing else): the composed receipt must record every
    issued obligation's scenario as PASS -- or, per obligation, its own
    differences gone from its own re-run record (worklist.parity_obligation_discharged)
    -- and no entry point it recorded PASS before may be anything else now.
    A receipt that was not composed, or a comparison that did not run, is an
    unmeasured slot: VERIFICATION_PENDING, no attempt spent. That receipt is
    composed against the CANDIDATE (the acceptance path rebuilt the work list
    on it, so the live seal cannot match), and it says so: a receipt bound to
    another card or to a tree this verification did not measure is not this
    card's evidence and leaves the slot unmeasured -- and so is one that says
    nothing at all when the comparison ran bound to the issued card, because
    that is the receipt a refusing composer left behind;

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
import _outcome_bridge  # noqa: E402  outcome-board protocol; a no-op on serial-loop runs
from _loop_common import PARITY_SNAPSHOT, _pending_dir, attempt_budget, attempts_spent, budget, candidate_sha256, classify_inconclusive, clear_pending, source_write_members, state_change_violations, catalog_property_mappings, ensure_hermes_lib, git, load_deferred, load_issued, load_state, load_steps, pending_for, product_paths_changed, profile_keys_lost_in_tree, publish_loop_state, restore_reports, revert_paths, save_deferred, save_pending_candidate, save_steps, snapshot_reports, tree_changes  # noqa: E402

ensure_hermes_lib()
from planner import pipeline  # noqa: E402
from planner.canonical import digest, load_json, write_canonical  # noqa: E402
from planner.dest_model import DestModelUnavailable, checked_exception_delta, dest_model, diagnostic_identity  # noqa: E402
from planner.decisions import load_decisions, max_attempts  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE, LOOP_ACCEPTED, LOOP_ISSUED, MTA_RESCAN_FINDINGS, VERIFY_DIAGNOSTICS, VERIFY_DIR, VERIFY_PACKAGE, VERIFY_RUN, WORKLIST  # noqa: E402
from planner.worklist import cdi_wiring_changes, carry_unmeasured, issued_parity_plan, navigation_handlers_added, parity_before_file, parity_discharge_scope, parity_obligation_discharged, parity_receipt_file, parity_remeasured, parity_run_file, parity_state, security_mode_of_run, CHECKED_FAMILY_RULE, EXPOSED, PARITY_RECEIPT, RETAIN, SECURITY_MODES, UNIT_KIND, UNPROVEN, assess_unit, batch_scope_digest, build_worklist, compile_items, gate_items, incidents_from_findings, item_ids, obligation_keys, progress, unit_continue_scope, unit_explained_regressions  # noqa: E402

# The codes javac's flow analysis reports ONE site at a time per compilation
# (control in dest_model.py: three files with the same defect are one reported
# error). The same list as DestModel.FLOW_CODES (jdk-dest-model/DestModel.java);
# keep them together. Every other compiler.* error is an ATTRIBUTION diagnostic
# and javac reports all of them at once, so "the count did not fall and the
# compiler now names something else" means something else for the two kinds:
# a flow code may have been hidden behind the one just repaired (exposed); an
# attribution code the accepted tree did not report was introduced.
FLOW_CODES = frozenset((
    "compiler.err.unreported.exception.need.to.catch.or.throw",
    "compiler.err.unreported.exception.default.constructor",
    "compiler.err.unreported.exception.implicit.close",
    "compiler.err.var.might.not.have.been.initialized",
    "compiler.err.var.might.already.be.assigned",
    "compiler.err.missing.ret.stmt",
    "compiler.err.unreachable.stmt",
))


def _url_path_of(url: str) -> str:
    import urllib.parse
    return urllib.parse.urlsplit(str(url or "")).path or "/"


def _attribution_items(items: list) -> dict:
    """Line-free identity → item, for every javac ATTRIBUTION diagnostic.

    Only compiler.* codes: a BUILD_UNRESOLVABLE or GENERATED_SOURCE_ERROR item
    is javac's absence or its generator's configuration, not a report of the
    tree. The identity is diagnostic_identity's diag: form (file, code, message
    digest; no line), the same one the work list stamps on its items, so an
    edit that moves a diagnostic down a line does not make it a new one."""
    out: dict = {}
    for i in items or []:
        if str(i.get("source") or "") != "javac":
            continue
        code = str(i.get("rule_id") or i.get("code") or "")
        if not code.startswith("compiler.") or code in FLOW_CODES:
            continue
        out[str(i.get("identity") or "") or diagnostic_identity(None, i)] = i
    return out


PARITY_BEFORE = VERIFY_DIR / "parity-before.json"


def _card_names(issued: dict, card: str) -> set[str]:
    """Every name this step's card answers to. K4 writes ``task_id`` only once
    the card has been minted, so a candidate-bound receipt may name the cluster
    or the idempotency key instead; all of them are this card."""
    values = (card, (issued or {}).get("task_id"), (issued or {}).get("cluster"), (issued or {}).get("idempotency_key"))
    return {str(v) for v in values if v}


PARITY_RUN_RECORD = PARITY_RECEIPT.parent / "_run.json"


def _issued_bound_comparison(root: Path, run: dict, security_mode: str | None = None) -> bool:
    """Did the comparison in THIS verification run bound to an issued card?

    run-verify.sh hands run-parity.py the issued card whenever there is one, so
    on the acceptance path every comparison is candidate-bound; the runner
    records what it ran under in verification/parity/_run.json (``issued``,
    ``binding``), and run.json's runtime.parity says the comparison ran in this
    verification. When the run was issued-bound, a receipt that is NOT
    candidate-bound cannot be its output: the composer would have written the
    binding it was given, so a sealed or unbound receipt on disk is one an
    earlier run left -- exactly what a refusing composer leaves behind.

    The runner record is the one of this verification's security mode. An
    enabled replay writes ``_run-enabled.json``; reading the default
    ``_run.json`` would treat a sealed disabled run as this measurement."""
    if not bool(((run.get("runtime") or {}).get("parity") or {}).get("ran")):
        return False
    parity = (run.get("runtime") or {}).get("parity") or {}
    recorded = str(parity.get("security_mode") or "").strip().lower()
    mode = security_mode if security_mode is not None else (recorded or None)
    # what the verification itself recorded, when it records it
    if str(parity.get("issued") or ""):
        return True
    b = parity.get("binding") if isinstance(parity.get("binding"), dict) else {}
    if b:
        return str(b.get("mode") or "sealed") == "candidate"
    # otherwise the runner's own record of the run that just happened
    p = root / parity_run_file(mode)
    if not p.is_file():
        return False
    try:
        rec = load_json(p)
    except (OSError, ValueError):
        return False
    if not isinstance(rec, dict):
        return False
    rb = rec.get("binding") if isinstance(rec.get("binding"), dict) else {}
    rec_mode = str(rec.get("security_mode") or "disabled").strip().lower() or "disabled"
    want_mode = str(mode or "disabled").strip().lower() or "disabled"
    if rec_mode != want_mode:
        return False
    return bool(str(rec.get("issued") or "")) or str(rb.get("mode") or "sealed") == "candidate"


def _candidate_binding_gap(receipt: dict, run: dict, issued: dict, card: str) -> str:
    """Why a CANDIDATE-bound parity receipt is not this step's measurement.

    A receipt with no binding, or one bound to the seal, is the M4 road's own
    and is read exactly as before. One bound to a candidate names the tree it
    measured and the card it was measured for, and it counts here only when
    both are this step's: a receipt composed for another card, or on a tree
    this verification did not measure, is somebody else's evidence."""
    b = receipt.get("binding") if isinstance(receipt.get("binding"), dict) else {}
    if str(b.get("mode") or "sealed") != "candidate":
        return ""
    names = _card_names(issued, card)
    got_card = str(b.get("card") or "")
    if got_card not in names:
        return ("it was composed for card %s and this step advances %s"
                % (got_card or "nobody", ", ".join(sorted(names)) or "an unnamed card"))
    want = str(run.get("candidate_sha256") or "")
    got = str(b.get("candidate_sha256") or "")
    if not want or got != want:
        return ("it was composed on candidate %s and this verification measured %s"
                % (got[:12] or "nothing", want[:12] or "nothing"))
    return ""


def _parity_receipts(root: Path, run: dict, issued: dict | None = None, card: str = "",
                     security_mode: str | None = None) -> tuple[dict, dict]:
    """(what parity said BEFORE this candidate, what it says now).

    "Now" counts only when the comparison RAN in this verification
    (run.json runtime.parity): a receipt left over from an earlier card
    measures nothing about this one, and the measurement contract is the same
    here as for every other tool. A receipt the acceptance path composed
    against the CANDIDATE (compose-parity-receipt.py --issued) says so, and
    then it also has to be THIS card's and THIS candidate's.

    The converse matters just as much: when the comparison ran bound to the
    issued card, a receipt it composed WOULD carry that binding, so one that
    does not is the receipt the last run left when this run's composer refused
    to compose. It still says PASS and it measures another tree; it is not
    "now".

    "Before" is the accepted state's receipt: the snapshot taken at the last
    accepted step when there is one, and otherwise the copy run-verify.sh took
    of the receipt as it stood before this candidate's comparison. Either may
    be sealed (the M4 road's) or the binding the last accepted step recorded;
    both describe the accepted tree, which is what "before" means.

    Receipt, runner record and baseline snapshot are the ones of this
    verification's security mode. Scenario naming is not a substitute: a
    sealed disabled ``receipt.json`` is never "now" for an enabled replay."""
    mode = security_mode if security_mode is not None else security_mode_of_run(run, issued)
    if str(mode or "") == "mixed":
        return {}, {}
    receipt_rel = parity_receipt_file(mode)
    ran = bool(((run.get("runtime") or {}).get("parity") or {}).get("ran"))
    cur = load_json(root / receipt_rel) if (ran and (root / receipt_rel).is_file()) else {}
    if cur:
        got_mode = str(cur.get("security_mode") or "disabled").strip().lower() or "disabled"
        want_mode = str(mode or "disabled").strip().lower() or "disabled"
        gap = ""
        if want_mode in ("disabled", "enabled") and got_mode != want_mode:
            gap = ("this verification compared the %s security mode and %s records %s"
                   % (want_mode, receipt_rel.as_posix(), got_mode))
        if not gap:
            gap = _candidate_binding_gap(cur, run, issued or {}, card)
        if not gap and _issued_bound_comparison(root, run, want_mode):
            # The comparison ran bound to the issued card, so what it composed
            # is candidate-bound. A receipt that is not is the one the last run
            # left on disk when this run's composer REFUSED to compose -- the
            # false green this rule exists for: it still says PASS, and it is
            # not a measurement of this candidate.
            bind = str((cur.get("binding") or {}).get("mode") or "") if isinstance(cur.get("binding"), dict) else ""
            if bind != "candidate":
                gap = ("this verification's comparison was bound to the issued card and a receipt it composed would say "
                       "so; this one is %s and was left by an earlier run" % (bind + "-bound" if bind else "bound to nothing"))
        if gap:
            print("WARN: %s is not this card's measurement: %s; parity is UNMEASURED here"
                  % (receipt_rel.as_posix(), gap), file=sys.stderr)
            cur = {}
    snap = root / LOOP_ACCEPTED / PARITY_SNAPSHOT / receipt_rel.name
    if snap.is_file():
        return load_json(snap), cur
    before = root / parity_before_file(mode)
    return (load_json(before) if before.is_file() else {}), cur


def _verify_meta(run: dict) -> dict:
    return {"mode": str(run.get("mode") or "acceptance"), "stages_ms": run.get("stages_ms") or {}, "total_ms": run.get("total_ms")}


def _decided_repairs_for_baseline(root: Path) -> dict | None:
    """ADR-019: {} when nothing is decided for bootstrap, the receipt binding
    when the decided repairs are demonstrably applied, None (after printing
    the refusal) when they are not -- the baseline is then not recorded."""
    from planner import decided_repairs
    from planner.canonical import sha256_file
    from planner.decisions import DecisionsError
    from planner.paths import DECISIONS, DECIDED_REPAIRS_RECEIPT

    if not (root / DECISIONS).is_file():
        return {}
    try:
        doc = load_decisions(root)
    except DecisionsError:
        return {}  # admission reports an invalid decision file on its own
    if not decided_repairs.section(doc):
        return {}
    gaps = decided_repairs.receipt_gaps(root, doc, for_baseline=True)
    if gaps:
        for g in gaps:
            print("  - %s %s: %s" % (g["class"], g["subject"], g["detail"]), file=sys.stderr)
        print("FAIL: LOOP_BASELINE_REPAIRS_PENDING the decided repairs (decisions.yaml decided_repairs) are not applied; "
              "re-run bootstrap-destination and resolve its refusals before the baseline", file=sys.stderr)
        return None
    rec = load_json(root / DECIDED_REPAIRS_RECEIPT)
    return {"receipt": str(DECIDED_REPAIRS_RECEIPT), "receipt_sha256": sha256_file(root / DECIDED_REPAIRS_RECEIPT),
            "classification": rec.get("classification"), "counts": rec.get("counts")}


def _commit(root: Path, paths: list[str], message: str) -> str:
    git(root, "reset", "-q")  # nothing staged but what we add now
    if paths:
        git(root, "add", "--", *paths)
    proc = git(root, "-c", "user.email=fix-until-green@local", "-c", "user.name=fix-until-green", "commit", "-q", "--allow-empty", "-m", message)
    if proc.returncode != 0:
        raise SystemExit("FAIL: LOOP_COMMIT %s" % proc.stderr.strip()[:200])
    return git(root, "rev-parse", "HEAD").stdout.strip()


def _reject(root: Path, steps: dict, cluster: str, card: str, cur: dict, reason: str, changed: list[str], *, mint: bool = False, hermes: str = "hermes",
            legal_next: str = "") -> int:
    """Discard the candidate, count the attempt, re-seal and re-issue the
    cluster (K4 mints the next attempt); defer + stop at the threshold.
    `legal_next` is what the retry brief tells the next attempt it may do;
    a reason that knows better than the default says so here."""
    if _outcome_bridge.active(root) and _outcome_bridge.record(root, "REVERTED", candidate_sha256(root), reason):
        return 1  # the outcome ledger refused (stale run, no issue): nothing moves
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
                  (legal_next.rstrip(". ") + ". " if legal_next else "") +
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


def _pending(root: Path, steps: dict, cluster: str, card: str, cur: dict, reason: str, changed: list[str], on_disk: str, cause: str = "", scope_assessment: list[dict] | None = None,
             outside_scope: dict | None = None) -> int:
    """Retain an unaccepted candidate when verification cannot conclude.

    Does not count an implementation attempt. Restores the accepted tree so
    Operator steps can land. Keeps issued.json so the same card can restore
    the candidate and re-verify; K4 must not mint a new attempt (pending
    blocks next_card). Terminator: kanban_block kind=needs_input naming the cluster."""
    if _outcome_bridge.record(root, "VERIFICATION_PENDING", on_disk, reason):
        return 1  # the outcome ledger refused: the candidate stays exactly where it is
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
    if scope_assessment is not None:
        row["scope_assessment"] = scope_assessment
    if outside_scope:
        # V16-2: what the gate names outside this card, the card's scope, and
        # the prerequisite only the Operator can supply -- on the record, so a
        # resumed card and the Operator read the same facts the message gave
        row["outside_scope"] = outside_scope
    revert_paths(root, changed)
    restore_reports(root)
    steps.setdefault("pending", []).append(row)
    save_steps(root, steps)
    rebuilt = build_worklist(root)
    pipeline.admit(root)
    publish_loop_state(root, rebuilt)
    stop = _stop_request_path(card)
    print(
        "VERIFICATION_PENDING %s cause=%s card=%s: %s → retain the candidate; do not re-implement. "
        "When the prerequisite changes: python3 .hermes/skills/migration/fix-until-green/scripts/restore-pending.py --root . --cluster %s "
        "then bash run-verify.sh --mode acceptance and advance.py. %s"
        % (cluster, cause, card, reason, cluster,
           "The runtime blocks this card (needs_input) and ends the run: nothing else to call."
           if stop else "Terminator: kanban_block kind=needs_input naming the cluster."),
        file=sys.stderr,
    )
    if stop:
        _write_stop_request(stop, card, "VERIFICATION_PENDING %s cause=%s card=%s: %s; candidate retained (sha256 %s) under %s; "
                            "after the prerequisite: restore-pending.py, run-verify.sh --mode acceptance, advance.py"
                            % (cluster, cause, card, reason, on_disk[:16], _pending_dir(root, cluster).relative_to(root).as_posix()))
    return 1


def _stop_request_path(card: str) -> Path | None:
    """V16-3 (runtime 0011): the run's stop-request file, when this process is
    the dispatcher-spawned worker of THIS card. Anything else -- an older
    runtime, a manual or Operator run, another card's id -- is None and the
    worker's own kanban_block stays the terminator."""
    path = (os.environ.get("HERMES_KANBAN_STOP_REQUEST") or "").strip()
    task = (os.environ.get("HERMES_KANBAN_TASK") or "").strip()
    if not path or not card or card != task:
        return None
    return Path(path)


def _write_stop_request(path: Path, card: str, reason: str) -> None:
    """Ask the runtime to record the native needs_input block and end the run.
    Written after the pending row, the retained candidate and the loop state
    are persisted, so the block never precedes what it names. Atomic: a
    temporary file in the same directory, then os.replace -- the runtime never
    reads half a request."""
    import json
    import tempfile
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".%s." % path.name, dir=str(path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"kind": "needs_input", "reason": reason, "task": card}, fh)
        os.replace(tmp, path)
    except OSError as exc:
        # the pending verdict stands either way; without the request the
        # worker's kanban_block is the terminator, as on an older runtime
        print("WARN: the stop request %s could not be written (%s); end the card with kanban_block kind=needs_input "
              "naming the cluster" % (path, exc), file=sys.stderr)


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


_T0 = time.monotonic()


def _phase(label: str) -> None:
    """One progress line per slow phase (stderr, with the elapsed time), so a
    terminal call killed mid-transaction shows WHERE it was killed. Dest v9
    t_2da2458b: advance.py ran 30.3 s, the worker's terminal timeout cut it at
    ~30 s with no line after 'OK: ACCEPTED', and nothing said whether the
    rebuild, the re-seal or the mint had happened."""
    print("advance: %s (t+%.1fs)" % (label, time.monotonic() - _T0), file=sys.stderr)



CONTINUATION = Path("verification") / "loop" / "continuation.json"


def _continuation(root: Path, state: str, **fields) -> None:
    """B8: the accept -> admit -> mint transition, durable. Written at each
    stage so a kill, a restart or a refused admission leaves the exact stage
    and reason on disk; K2 refuses kanban_complete on the predecessor while it
    is not `minted`, so a stalled continuation is a BLOCKED
    card on the board, never an idle one. Re-running advance.py with the same
    arguments (the H9b idempotent path) finishes it."""
    doc = load_json(root / CONTINUATION) if (root / CONTINUATION).is_file() else {}
    doc = dict(doc if isinstance(doc, dict) else {}, schema="rhoai3.loop-continuation/v1", state=state,
               at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **fields)
    write_canonical(root / CONTINUATION, doc)

def _recorded_verdict(root: Path, steps: dict, card: str, on_disk: str, *, mint: bool, hermes: str) -> int | None:
    """H9b: advance.py is IDEMPOTENT on a card whose verdict is already on the
    record. A worker whose terminal call was killed after the acceptance had
    committed (dest v9 t_2da2458b: exit 124 at 30 s, then LOOP_STALE_STATE
    from a second call, then kanban_block on an ACCEPTED card) gets the
    verdict back, not a refusal: `OK: ACCEPTED already (step N, commit X)`
    exit 0 -- and the acceptance's tail (rebuild, re-seal, publish, mint) is
    completed if the kill interrupted it -- or `REVERTED already` /
    `DEFERRED already` exit 1, each naming its terminator. None when the card
    has no recorded verdict (the normal path)."""
    for n, row in enumerate(steps.get("steps") or []):
        if not isinstance(row, dict) or str(row.get("card") or "") != card or str(row.get("verdict") or "") != "accepted":
            continue
        commit = str(row.get("commit") or "")
        same = str(row.get("candidate_sha256") or "") == on_disk
        print("OK: ACCEPTED already (step %d, commit %s) -- call kanban_complete; this invocation changes nothing about the verdict%s"
              % (n, commit[:12], "" if same else " (the tree on disk is no longer that candidate: %s vs %s)" % (on_disk[:12], str(row.get("candidate_sha256") or "")[:12])))
        if not same:
            return 0
        # the tail the kill may have interrupted, each step idempotent: the
        # rebuilt work list, the admission seal and the published state
        # describe the accepted tree either way, and the mint runs only when
        # nothing is issued (K4 wrote issued.json if it ran)
        _phase("completing the acceptance's tail: rebuilding the work list")
        rebuild = build_worklist(root)
        _phase("re-sealing admission")
        rec = pipeline.admit(root)
        publish_loop_state(root, rebuild)
        return _finish_continuation(root, rec, card, commit, mint=mint, hermes=hermes)
    # a rejection is "already answered" only while the tree carries no new
    # candidate: a rejected card is restored to the accepted tree, so a repeat
    # call on a clean tree is the killed-terminal case, while a fresh edit is
    # a new candidate and takes the normal path (and its own refusals)
    if product_paths_changed(root):
        return None
    for row in reversed(steps.get("rejected") or []):
        if isinstance(row, dict) and str(row.get("card") or "") == card and not row.get("rewound"):
            deferred = load_deferred(root)
            cluster = str(row.get("cluster") or "")
            if cluster in set(deferred.get("clusters") or []):
                print("DEFERRED already (%s: %s) -- the loop is stopped; kanban_block kind=needs_input naming the cluster"
                      % (cluster, str(deferred.get("reasons", {}).get(cluster) or "")[:160]), file=sys.stderr)
                return 1
            print("REVERTED already (%s attempt on card %s: %s) -- the retry is the next K4 card; call kanban_complete"
                  % (cluster, card, str(row.get("reason") or "")[:160]), file=sys.stderr)
            return 1
    return None


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
    from planner.run_control import run_gaps
    drift = run_gaps(root)
    if drift:
        # B10: never a verdict. The candidate, the attempts and the deadline
        # stay exactly as they are; a run on a harness it was not created
        # with stops with the reason instead of being judged by it.
        print("REFUSE: %s" % drift[0], file=sys.stderr)
        return 2
    state = load_state(root)
    if state is None:
        print("FAIL: LOOP_NOT_VERIFIED run run-verify.sh first", file=sys.stderr)
        return 2
    steps = load_steps(root)
    _phase("state loaded")
    on_disk = candidate_sha256(root)
    _phase("candidate digest computed")
    if not args.baseline and args.card:
        done = _recorded_verdict(root, steps, args.card, on_disk, mint=not args.no_mint, hermes=args.hermes)
        if done is not None:
            return done
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
    if isinstance(run, dict) and ((run.get("admission") or {}) if isinstance(run.get("admission"), dict) else {}).get("resealed_during_verify"):
        adm = run["admission"]
        print("NOTE: admission-receipt.json was re-sealed while run-verify.sh ran (file %s -> %s): a verification never does "
              "that; another process did. The parity comparison of this candidate is bound to the receipt the issued card was "
              "minted under (issued.json), so the verdict below is on this card's own evidence."
              % (str(adm.get("file_sha256_before") or "")[:12], str(adm.get("file_sha256_after") or "")[:12]), file=sys.stderr)
    if not args.baseline and isinstance(run, dict) and str(run.get("mode") or "acceptance") == "diagnostic":
        print("REFUSE: LOOP_DIAGNOSTIC_NOT_ACCEPTANCE diagnostic mode cannot promote or reject; run run-verify.sh --mode acceptance on this candidate", file=sys.stderr)
        return 1
    if on_disk != state.get("candidate_sha256"):
        # The tree changed after verification, so the measure no longer
        # describes it -- UNLESS what changed is not part of the candidate at
        # all. `is_product_path` is an exempt list, so a diagnosis that leaves
        # tool output in the tree (v9 t_46556d5e: javap extracted .class files
        # under io/quarkus/ at the root, after the verification) moved this
        # digest and cost a measured repair its attempt. Untracked files
        # outside the migration's product are nobody's repair and no evidence
        # against one: asked here, before any verdict, and answered by what
        # the digest WOULD be without them.
        scratch = tree_changes(root)[1]
        if scratch and candidate_sha256(root, exclude=scratch) == str(state.get("candidate_sha256") or ""):
            print("REFUSE: LOOP_SCRATCH_IN_TREE %d untracked file(s) outside this migration's product sit in the tree "
                  "and moved the candidate digest: %s. The verified candidate is otherwise intact, so nothing is "
                  "judged, no attempt is spent and the candidate stays where it is: remove the files (they are tool "
                  "output, not a repair) and run advance.py again."
                  % (len(scratch), ", ".join(scratch[:8]) + (", ..." if len(scratch) > 8 else "")), file=sys.stderr)
            return 1
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
        # ADR-019: the decided repairs are applied BEFORE the first baseline,
        # so the baseline commit carries them and nothing is measured without
        repairs_rec = _decided_repairs_for_baseline(root)
        if repairs_rec is None:
            return 1
        changed = product_paths_changed(root)
        sha = _commit(root, changed, "fix-until-green: baseline %s" % cur["measure"]["tuple"])
        snapshot_reports(root)
        steps["steps"].append({"cluster": "bootstrap", "card": args.card, "commit": sha, "candidate_sha256": on_disk, "measure": cur["measure"], "item_ids": sorted(item_ids(cur)), "obligation_keys": sorted(obligation_keys(cur)), "worklist_sha256": digest(cur), "changed": changed, "verdict": "baseline", "reason": "bootstrap-destination baseline", **({"decided_repairs": repairs_rec} if repairs_rec else {})})
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
    # The SEALED SCOPE: a repository card carries an inventory of every member
    # the declared rule reaches, and the card is not finished while one of them
    # still breaks that rule. An already-correct member needs no edit and earns
    # no credit either way; only the assessment counts, and it is made here from
    # the tree rather than from anything the worker wrote.
    scope_ref = issued.get("batch_scope") or {}
    scope_rows: list[dict] = []
    scope_doc: dict = {}
    family = False
    unit = False
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
        # assess_unit dispatches on the sealed rule: a repository inventory and
        # a checked-exception family are assessed by the same code as before,
        # and a unit by the rule that formed it.
        scope_rows = assess_unit(root, scope_doc)
        bad = [r for r in scope_rows if r.get("verdict") == "violates"]
        family = str(scope_doc.get("rule") or "") == CHECKED_FAMILY_RULE
        unit = str(scope_doc.get("kind") or "") == UNIT_KIND
        target = str(scope_doc.get("repository") or scope_doc.get("signature") or scope_doc.get("rule") or "scope")
        family_detail = "%s member(s) of %s still break %s: %s" % (
            len(bad), target, scope_doc.get("rule"), "; ".join("%s (%s)" % (r["member"], r["detail"]) for r in bad[:4]))
        # A family member still unhandled is the family's REMAINING work, which
        # the measure below decides about (continue, or reject when the issued
        # one is still reported). A UNIT's members are judged at its checkpoint,
        # in progress(), after its own sealed identities are asked about -- a
        # coordinated repair is one verdict, in one order, or the message a
        # worker gets names the wrong half of it. A repository member is judged
        # here, exactly as before.
        if bad and not family and not unit:
            return _reject(root, steps, args.cluster, args.card, cur, family_detail,
                           changed, mint=not args.no_mint, hermes=args.hermes)
    # An ATTRIBUTION diagnostic the accepted tree did not report was introduced
    # by this candidate, in whatever file it stands: javac reports every one of
    # them in one compilation (only FLOW_CODES come one at a time), and a
    # candidate that deletes a method breaks callers in files it never touched.
    # Dest v9 t_3903f495 (c:fb2e558f39a5, UriComponentsBuilder, 7 items in 6
    # files): the right repair with the wrong import (jakarta.ws.rs.Context for
    # jakarta.ws.rs.core.Context) swapped 13 diagnostics for 13 of the same
    # shape; equal counts reached progress()'s identity branch, which parked
    # the card as exposed-outside-scope for a human. Decided here, BEFORE
    # progress(), on purpose: a candidate that lowers the count and breaks a
    # caller is rejected too, not accepted on the fall. The identity is
    # line-free (file, code, message digest); the message names the line.
    # Compared against the accepted snapshot of javac's own report, never
    # against the previous step's err: ids alone, which hash the line and so
    # cannot tell a moved diagnostic from a new one.
    cur_attr = _attribution_items(cur.get("items") or [])
    snap = root / LOOP_ACCEPTED / VERIFY_DIAGNOSTICS.name
    if snap.is_file():
        prev_attr = set(_attribution_items(compile_items(load_json(snap))))
        introduced = sorted(set(cur_attr) - prev_attr)
    else:
        # only the previous step's ids: a current item carrying one of them is
        # the same diagnostic for certain, anything else is undecidable
        prev_err = set(str(x) for x in (prev.get("item_ids") or []))
        introduced = []
        undecided = sorted(k for k, i in cur_attr.items() if str(i.get("id") or "") not in prev_err)
        if undecided:
            # B7: without the snapshot nobody can say whether these were
            # introduced, and an undecided regression is not an absent one --
            # the candidate is kept and the step refuses, naming the snapshot
            return _pending(root, steps, args.cluster, args.card, cur,
                            "DIAGNOSTIC_BASELINE_MISSING: expected %s for accepted %s; %d current diagnostic(s) carry no "
                            "accepted err: id, so whether this candidate introduced them cannot be decided"
                            % (snap.relative_to(root), str(prev.get("commit") or "HEAD")[:12], len(undecided)),
                            changed, on_disk, cause="diagnostic-baseline-missing")
    # THE PARTITION, and only for a unit card. The veto itself does not move:
    # it stays global over every file and it stays here, BEFORE progress().
    # What a unit adds is that some of what it introduced is the unit's own
    # work in progress -- a diagnostic inside the file seal whose token
    # resolves to a symbol the unit sealed, or to a replacement the CATALOGUE
    # documents. Everything else is introduced and is rejected exactly as
    # before, with the same message. jakarta.ws.rs.core.Context has a
    # compat-mapping row and jakarta.ws.rs.Context does not, so the v9
    # t_3903f495 candidate -- the right repair with the wrong import -- is
    # explained by nothing and stays REVERTED, which is the counterexample the
    # relaxation must never eat.
    explained_rows: list[dict] = []
    if introduced and unit:
        try:
            _cand_model = dest_model(root)
        except DestModelUnavailable as exc:
            _cand_model = None
            print("WARN: the destination could not be modelled (%s), so no diagnostic can be explained by this unit's "
                  "sealed symbols; every introduced diagnostic is judged as before" % exc, file=sys.stderr)
        explained_rows, why = unit_explained_regressions(scope_doc, cur.get("items") or [], _cand_model,
                                                         identities=set(introduced))
        if why:
            print("WARN: nothing is tolerated at this checkpoint: %s" % why, file=sys.stderr)
            explained_rows = []
        tolerated = {r["identity"] for r in explained_rows}
        introduced = [k for k in introduced if k not in tolerated]
    if introduced:
        named = ["%s:%s %s — %s" % (cur_attr[k].get("path") or "", cur_attr[k].get("line") or 0,
                                     cur_attr[k].get("rule_id") or "", str(cur_attr[k].get("message") or cur_attr[k].get("detail") or "")[:120])
                 for k in introduced[:3]]
        return _reject(root, steps, args.cluster, args.card, cur,
                       "INTRODUCED_COMPILE_DIAGNOSTIC: introduced %d compile diagnostic(s) the accepted tree (%s) did not have: %s"
                       % (len(introduced), str(prev.get("commit") or "HEAD")[:12], "; ".join(named)),
                       changed, mint=not args.no_mint, hermes=args.hermes,
                       legal_next="fix the named symbols in the same write set; do not widen the write set to satisfy a missing import")
    if explained_rows:
        print("NOTE: %d diagnostic(s) remain that this unit's sealed symbols explain and its checkpoint tolerates: %s. "
              "They are recorded on the step as explained_regressions; the build or config cluster that resolves them "
              "is the NEXT card, never a wider write set"
              % (len(explained_rows), "; ".join("%s → %s" % (r["path"], r["symbol"]) for r in explained_rows[:3])),
              file=sys.stderr)
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
    # B7 (v12 t_b33f25fa): a KNOWN regression is decided before any UNKNOWN.
    # The introduced-diagnostic veto and the checked-exception veto above run
    # first; only a candidate neither of them rejects can be parked because
    # a member or a site could not be assessed. Before, an unassessable member
    # returned VERIFICATION_PENDING ahead of both, and seven new files importing
    # a class that does not exist parked the card for an Operator instead of
    # being REVERTED with the symbols named.
    if java_changed:
        if checked["state"] in ("unavailable", "inconclusive"):
            return _pending(root, steps, args.cluster, args.card, cur,
                            "whether this candidate introduces an unhandled checked exception could not be decided: %s"
                            % (checked["why"] or "; ".join("%s (%s)" % (r.get("key") or r.get("path"), r.get("why")) for r in checked["inconclusive"][:2])),
                            changed, on_disk, cause="unassessable-exceptions")
    # An assessment that could not be made is not an assessment that
    # passed. The card cannot complete on a member nobody could resolve;
    # that is a prerequisite to repair, not an attempt to spend.
    unknown = [r for r in scope_rows if r.get("verdict") == "inconclusive"]
    if unknown and unit:
        return _pending(root, steps, args.cluster, args.card, cur,
                        "%s sealed member(s) of %s could not be assessed against %s: %s" % (
                            len(unknown), scope_doc.get("unit_id") or args.cluster, scope_doc.get("rule"),
                            "; ".join("%s (%s)" % (r["member"], r["detail"]) for r in unknown[:3])),
                        changed, on_disk, cause="unassessable-scope", scope_assessment=scope_rows)
    if unknown:
        return _pending(root, steps, args.cluster, args.card, cur,
                        "%s member(s) of %s could not be assessed against %s: %s" % (
                            len(unknown), scope_doc.get("repository"), scope_doc.get("rule"),
                            "; ".join("%s (%s)" % (r["member"], r["detail"]) for r in unknown[:3])),
                        changed, on_disk, cause="unassessable-scope", scope_assessment=scope_rows)
    gate = str(issued.get("gate") or "")
    # identities without lines: whether the issued failure is "still reported"
    cur_identities = {str(i.get("identity")) for i in (cur.get("items") or []) if str(i.get("source") or "") == "javac" and i.get("identity")}
    issued_identities = {str(v) for v in (issued.get("item_identities") or {}).values() if v} or None
    # what a CONTINUE may move to: a checked-exception family's own members, or
    # -- for a unit -- a diagnostic reported now at a file the unit seals and at
    # a member row its inventory carries (the flow codes come one site at a
    # time and carry no symbol token, so they are never "explained" and the
    # card continues on them instead).
    family_keys = ({"chk:" + str(m.get("member") or "") for m in (scope_doc.get("members") or [])}
                   if scope_ref and family else
                   (unit_continue_scope(scope_doc, cur.get("items") or []) if scope_ref and unit else None))
    run_doc = run if isinstance(run, dict) else {}
    run_parity = (run_doc.get("runtime") or {}).get("parity") if isinstance((run_doc.get("runtime") or {}).get("parity"), dict) else {}
    pending_why = str(run_parity.get("pending") or "")
    if pending_why:
        return _pending(root, steps, args.cluster, args.card, cur, pending_why, changed, on_disk,
                        cause=str(run_parity.get("cause") or "issuance-scope-missing"))
    issued_mode = str(issued.get("security_mode") or "").strip().lower()
    if gate == "parity":
        plan = issued_parity_plan(issued)
        issued_mode = str(plan.get("mode") or "").strip().lower()
        if plan["kind"] == "skip" or issued_mode == "mixed":
            return _reject(root, steps, args.cluster, args.card, cur,
                           "LOOP_MIXED_SECURITY_MODE the issued card spans both security modes; "
                           "partition into one mode per repair card",
                           changed, mint=not args.no_mint, hermes=args.hermes,
                           legal_next="mint one repair card per security mode; do not compare both modes on one card")
        if plan["kind"] == "pending" or issued_mode not in SECURITY_MODES:
            return _pending(root, steps, args.cluster, args.card, cur,
                            str(plan.get("reason") or "the issued card does not record a security mode or scenario scope"),
                            changed, on_disk, cause="issuance-scope-missing")
        recorded = str(run_parity.get("security_mode") or "").strip().lower()
        ran = bool(run_parity.get("ran"))
        if ran and recorded and recorded != issued_mode:
            return _pending(root, steps, args.cluster, args.card, cur,
                            "this verification compared the %s security mode and the issued card requires %s; "
                            "a %s PASS cannot discharge it" % (recorded, issued_mode, recorded),
                            changed, on_disk, cause="wrong-security-mode")
        if ran and not recorded:
            return _pending(root, steps, args.cluster, args.card, cur,
                            "this verification did not record a security mode and the issued card requires %s; "
                            "a wrong-mode PASS cannot discharge it" % issued_mode,
                            changed, on_disk, cause="wrong-security-mode")
    parity_mode = issued_mode if (gate == "parity" and issued_mode in SECURITY_MODES) else security_mode_of_run(run_doc, issued)
    remeasured = parity_remeasured(run_doc)
    if parity_mode == "mixed":
        return _reject(root, steps, args.cluster, args.card, cur,
                       "LOOP_MIXED_SECURITY_MODE the issued card spans both security modes; "
                       "partition into one mode per repair card",
                       changed, mint=not args.no_mint, hermes=args.hermes,
                       legal_next="mint one repair card per security mode; do not compare both modes on one card")
    prev_parity, cur_parity = _parity_receipts(root, run_doc, issued, args.card, parity_mode)
    # F1: a SCOPED comparison re-ran only this card's scenarios; every other
    # entry point is carried from the accepted baseline, never read as a
    # regression (and never as a pass it did not earn)
    judged_parity, carried_rows = carry_unmeasured(prev_parity, cur_parity, remeasured, root)
    judged_obl = parity_state(judged_parity)["obligations"] if judged_parity else {}
    parity_discharged = {}
    discharge_scope = parity_discharge_scope(run if isinstance(run, dict) else {})
    for oid in (issued.get("items") or []):
        row = judged_obl.get(str(oid))
        if row is not None and str(row.get("what") or "") in ("cors", "response", "representation"):
            parity_discharged[str(oid)] = parity_obligation_discharged(root, row, discharge_scope, judged_parity)
    reran_oracles = sorted(str(e) for e in ((((run if isinstance(run, dict) else {}).get("runtime") or {}).get("parity") or {}).get("read_oracles_rerun") or []))
    if carried_rows:
        print("NOTE: the scoped comparison re-ran %s; %d entry point(s) carried from the accepted baseline %s: %s"
              % (", ".join(sorted(remeasured or [])), len(carried_rows), str((prev_parity or {}).get("receipt_sha256") or "")[:12],
                 ", ".join("%s %s" % (c["entry_point"], c["verdict"]) for c in carried_rows[:4])))
    if reran_oracles:
        print("NOTE: the scoped comparison re-ran the read oracle(s) of %s for this card" % ", ".join(reran_oracles))
    _phase("judging the candidate (measure, gates, parity, unit checkpoint)")
    ok, reason = progress(prev["measure"], cur["measure"], prev_keys, cur_keys,
                          gate=gate,
                          unit_scope=scope_doc if unit else None,
                          unit_assessment=scope_rows if unit else None,
                          explained={r["identity"] for r in explained_rows},
                          prev_runtime=prev.get("runtime") or {}, cur_runtime=cur.get("runtime") or {},
                          prev_parity=prev_parity, cur_parity=cur_parity,
                          parity_remeasured=remeasured, parity_discharged=parity_discharged,
                          issued_items=list(issued.get("items") or []),
                          prev_gate_items=set(str(i) for i in (issued.get("gate_items") or [])),
                          cur_gate_items=gate_items(cur, gate),
                          cur_item_ids=item_ids(cur),
                          issued_identities=issued_identities,
                          cur_identities=cur_identities if issued_identities is not None else None,
                          family_scope=family_keys)
    handoff = None
    if not ok:
        if ok is RETAIN:
            # the compiler moved to another member of THIS card's sealed family
            return _continue(root, steps, args.cluster, args.card, cur, reason, changed, on_disk, scope_doc,
                             sorted(cur_identities - set(issued_identities or ())), mint=not args.no_mint, hermes=args.hermes)
        if ok is EXPOSED:
            # outside every sealed scope: a typed diagnosis, the candidate kept.
            # Reachable only for a flow-class diagnostic (FLOW_CODES, reported
            # one at a time, so the accepted tree may well have had the site)
            # or for one the accepted snapshot could not be compared against:
            # an introduced attribution diagnostic was rejected above.
            return _pending(root, steps, args.cluster, args.card, cur, reason, changed, on_disk, cause="exposed-outside-scope")
        if ok is UNPROVEN:
            # the repair may well be right and the gate cannot say so yet. A
            # unit whose members could not be assessed is the other shape of
            # the same thing, and it keeps its own cause. The one exception is
            # a unit whose gate now stops on an obligation it does not reach
            # (_unit_gate_handoff): accepted at its checkpoint, proof owed later.
            handoff_why: list[str] = []
            handoff = (_unit_gate_handoff(root, scope_doc, scope_rows, issued, cur, gate, prev=prev, steps=steps,
                                          changed=changed, why=handoff_why) if unit else None)
            if handoff is None:
                cause = "unassessable-scope" if (unit and any(r.get("verdict") == "inconclusive" for r in scope_rows)) else "unproven-repair"
                # V16-2 (v16 t_d3f89ded): what the gate names NOW, against this
                # card's scope. A failure outside it is never this candidate's
                # to repair, and the message must not say so.
                guide = _gate_scope_guidance(issued, cur, gate, changed)
                if guide and guide["cause"]:
                    return _pending(root, steps, args.cluster, args.card, cur,
                                    guide["reason"] + ("; " + handoff_why[0] if handoff_why else ""), changed, on_disk,
                                    cause=guide["cause"], outside_scope=guide["record"])
                if guide:
                    reason = guide["reason"]
                return _pending(root, steps, args.cluster, args.card, cur,
                                reason + ("; " + handoff_why[0] if handoff_why else ""), changed, on_disk, cause=cause)
            reason = handoff["reason"]
        if handoff is None:
            if not (cur.get("measure") or {}).get("known"):
                return _pending(root, steps, args.cluster, args.card, cur, reason, changed, on_disk)
            clear_pending(steps, args.cluster, why="rejected")
            return _reject(root, steps, args.cluster, args.card, cur, reason, changed, mint=not args.no_mint, hermes=args.hermes)
    if scope_ref and family and bad:
        # the measure fell and a member still breaks the family's rule (caught,
        # declared, or its operation deleted): that is not a repair
        return _reject(root, steps, args.cluster, args.card, cur, family_detail, changed, mint=not args.no_mint, hermes=args.hermes)
    # H11 (v9 t_0527c69b): a NAVIGATION obligation is discharged by the
    # platform's UI answering at the redirect target, never by a handler this
    # candidate ADDED at that path to serve a substitute page. Structural: the
    # compiler models of the accepted tree and the candidate, compared at the
    # URL paths the bounded navigation walked.
    nav_items = [oid for oid in (issued.get("items") or []) if str((judged_obl.get(str(oid)) or {}).get("what") or "") == "navigation"]
    if gate == "parity" and nav_items and any(str(p).endswith(".java") for p in changed):
        nav_paths: list[str] = []
        ndir = root / "verification" / "parity" / "navigation"
        for np_ in sorted(ndir.glob("*.json")) if ndir.is_dir() else []:
            try:
                nrec = load_json(np_)
            except (OSError, ValueError):
                continue
            if not isinstance(nrec, dict):
                continue
            for u in [nrec.get("start")] + [h.get("url") for h in (nrec.get("hops") or []) if isinstance(h, dict)] + \
                     [h.get("location") for h in (nrec.get("hops") or []) if isinstance(h, dict)]:
                if u:
                    nav_paths.append(_url_path_of(str(u)))
        try:
            added = navigation_handlers_added(root, str(prev.get("commit") or "HEAD"), nav_paths) if nav_paths else []
        except DestModelUnavailable as exc:
            added = []
            print("WARN: the added-handler check for the navigation obligation could not be made: %s" % exc, file=sys.stderr)
        if added:
            h = added[0]
            return _reject(root, steps, args.cluster, args.card, cur,
                           "the navigation obligation %s is discharged by a handler this candidate ADDED at %s (%s.%s in %s): "
                           "the redirect target must be served by the platform's UI (quarkus.swagger-ui.always-include=true, "
                           "quarkus.swagger-ui.path, in application.properties) or by code that was already there, never by a "
                           "substitute page from product code (ADR-016)"
                           % (",".join(nav_items[:2]), h["navigation_path"], h["type"], h["member"], h["file"] or "?"),
                           changed, mint=not args.no_mint, hermes=args.hermes)
    wiring = _cdi_wiring_record(root, str(prev.get("commit") or ""), changed, on_disk)
    if wiring and not wiring.get("verified"):
        print("NOTE: CDI_WIRING_UNVERIFIED %s; the package gate did not pass on this candidate, so this acceptance "
              "is no claim that the bean wiring is complete: package and boot stay owed, and the first candidate "
              "the package gate reaches proves or refutes it" % wiring["summary"])
    clear_pending(steps, args.cluster, why="accepted")
    _phase("verdict: accepted; committing the candidate")
    if _outcome_bridge.record(root, "ACCEPTED", on_disk):
        return 1  # accept-begin must be on the outcome ledger before the commit (crash recovery)
    sha = _commit(root, changed, "fix-until-green: %s attempt %s %s" % (args.cluster, issued.get("attempt"), cur["measure"]["tuple"]))
    _phase("snapshotting the tool reports")
    snapshot_reports(root)
    if carried_rows:
        # the accepted baseline is what acceptance JUDGED: the scoped receipt
        # with its un-re-run rows carried, each marked carried_from -- of the
        # mode this card compared, never the other mode's sealed receipt
        snap_name = parity_receipt_file(parity_mode).name
        write_canonical(root / LOOP_ACCEPTED / PARITY_SNAPSHOT / snap_name, judged_parity)
    steps["steps"].append({"cluster": args.cluster, "card": args.card, "attempt": issued.get("attempt"), "idempotency_key": issued.get("idempotency_key"), "commit": sha, "candidate_sha256": on_disk, "measure": cur["measure"], "item_ids": sorted(item_ids(cur)), "obligation_keys": sorted(obligation_keys(cur)), "worklist_sha256": digest(cur), "changed": changed, "verdict": "accepted", "reason": reason, "runtime": cur.get("runtime") or {}, "gate": str(issued.get("gate") or ""), "parity": ({"verdict": str((cur_parity or {}).get("verdict") or ""), "binding": dict((cur_parity or {}).get("binding") or {}), "scenarios": list((((run if isinstance(run, dict) else {}).get("runtime") or {}).get("parity") or {}).get("scenarios") or []), "read_oracles_rerun": list(reran_oracles), "carried": list(carried_rows)} if cur_parity else {}), "discharged": sorted(str(i) for i in (issued.get("items") or [])), "si1_inconclusive": si1_unknown, "batch_scope": ({"digest": str(scope_ref.get("digest") or ""), "assessed": len(scope_rows),
                                                          "inconclusive": [r for r in scope_rows if r.get("verdict") == "inconclusive"]} if scope_ref else {}), "amendments": list(issued.get("amendments") or []), "verify": _verify_meta(run if isinstance(run, dict) else {}),
                           "unit": ({"unit_id": str(scope_doc.get("unit_id") or ""), "rule": str(scope_doc.get("rule") or ""),
                                     "family_key": str(scope_doc.get("family_key") or "")} if unit else {}),
                           # what this checkpoint TOLERATED and on whose
                           # authority: the audit must be able to read back
                           # which diagnostics were carried and which catalogue
                           # row documented each one
                           "explained_regressions": list(explained_rows),
                           # a unit accepted because its gate now stops on an
                           # obligation it does not reach: what was handed off,
                           # to what, and who still owes the gate's proof
                           "gate_handoff": ({k: v for k, v in handoff.items() if k != "reason"} if handoff else {}),
                           # V16-4: a candidate that changed CDI wiring, and
                           # whether packaging under the decided build profile
                           # proved it; unverified wiring is recorded debt
                           "cdi_wiring": wiring,
                           "revisions": list(issued.get("revisions") or []),
                           "continuations": list(issued.get("continuations") or []),
                           "checked_exceptions": ({k: (checked.get(k) if k in ("state", "base", "coverage") else len(checked.get(k) or []))
                                                   for k in ("state", "base", "introduced", "exposed", "resolved", "throws_added", "inconclusive", "coverage")}
                                                  if checked else {})})
    save_steps(root, steps)
    (root / LOOP_ISSUED).unlink()
    print("OK: ACCEPTED %s (%s) commit %s" % (args.cluster, reason, sha[:12]))
    _phase("the verdict is on the record (steps.json); rebuilding the work list on the accepted tree")
    rebuild = build_worklist(root)
    _phase("re-sealing admission")
    rec = pipeline.admit(root)
    # published either way: the accepted step is on record whether or not the
    # next card can be admitted, and the state must describe it
    publish_loop_state(root, rebuild)
    if rec["status"] == "ADMITTED":
        ob = _outcome_bridge.after_accept(root, sha, on_disk, rebuild if isinstance(rebuild, dict) else {}, run if isinstance(run, dict) else {})
        if ob is not None:
            return ob  # outcome board: the outcome is accepted, or its next cluster is issued on this same card
    return _finish_continuation(root, rec, args.card, sha, mint=not args.no_mint, hermes=args.hermes)


def _finish_continuation(root: Path, rec: dict, card: str, commit: str, *, mint: bool, hermes: str) -> int:
    """admitted -> minted, recorded at each stage; anything short of a minted successor is a refusal."""
    if rec["status"] != "ADMITTED":
        _continuation(root, "admission-refused", predecessor=card, accepted_commit=commit[:12],
                      reasons=list(rec.get("reasons") or [])[:5])
        print("REFUSE: LOOP_ADMISSION %s: %s -- the accepted step is on record; this card cannot complete while no "
              "successor exists: kanban_block kind=needs_input naming this reason. Re-running advance.py with the same "
              "arguments finishes the continuation once the named prerequisite is restored"
              % (rec["status"], "; ".join(rec["reasons"][:3])), file=sys.stderr)
        return 1
    _continuation(root, "admitted", predecessor=card, accepted_commit=commit[:12], reasons=[])
    if not mint:
        _phase("done (no mint)")
        return 0
    if (root / LOOP_ISSUED).is_file():
        _continuation(root, "minted", predecessor=card, accepted_commit=commit[:12])
        _phase("done; the next card is already issued")
        return 0
    _phase("minting the next card (K4)")
    rc = _mint(root, hermes)
    if rc != 0:
        _continuation(root, "mint-failed", predecessor=card, accepted_commit=commit[:12],
                      reasons=["K4 mint exited %d; see the lines above" % rc])
        return rc
    if not (root / LOOP_ISSUED).is_file():
        # K4 minted nothing after an ACCEPTED step: every accepted step has a
        # successor (the next head cluster, or M4 VERIFY), so this is a stop,
        # and it must be seen as one (v12: the board went idle in silence)
        _continuation(root, "no-successor", predecessor=card, accepted_commit=commit[:12],
                      reasons=["K4 minted no card after the accepted step; see the lines above"])
        print("REFUSE: LOOP_NO_SUCCESSOR K4 minted no card after the accepted step -- kanban_block kind=needs_input "
              "naming this reason; re-running advance.py with the same arguments retries the mint", file=sys.stderr)
        return 1
    _continuation(root, "minted", predecessor=card, accepted_commit=commit[:12], reasons=[])
    _phase("done")
    return 0


# Causes whose failure is decided by the expression written at the locus and
# nothing else, so an unchanged expression proves the failure pre-existed the
# candidate (B6). Deliberately ONE: a query, an injection or a missing
# implementation depends on types in other files, and a candidate can break
# them without touching the file the gate names.
FILE_LOCAL_CAUSES = {"unsupported-spel": r"#\{[^}]*\}"}


def _gate_cause_independent(root: Path, item: dict, prev_commit: str, steps: dict, changed: list[str]) -> dict | None:
    """Positive evidence that the gate failure a unit now meets was NOT made by
    the candidate: an accepted step already recorded this exact obligation id,
    or its cause is file-local and the exact expression is unchanged between the
    accepted tree and the candidate. None when neither can be shown."""
    import re
    iid = str(item.get("id") or "")
    for i, st in enumerate(steps.get("steps") or []):
        if iid and iid in (st.get("item_ids") or []):
            return {"kind": "baseline-named", "step": i, "commit": str(st.get("commit") or "")[:12]}
    rel, cause = str(item.get("path") or ""), str(item.get("cause") or "")
    rx = FILE_LOCAL_CAUSES.get(cause)
    if not rx or not rel or rel in changed:
        return None
    cand = root / rel
    if not cand.is_file():
        return None
    proc = subprocess.run(["git", "-C", str(root), "show", "%s:%s" % (prev_commit or "HEAD", rel)],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    before = sorted(set(re.findall(rx, proc.stdout)))
    after = sorted(set(re.findall(rx, cand.read_text(encoding="utf-8", errors="replace"))))
    if not before or before != after:
        return None
    return {"kind": "unchanged-expression", "cause": cause, "expressions": before[:4],
            "commit": (prev_commit or "HEAD")[:12]}


def _unit_gate_handoff(root: Path, scope_doc: dict, scope_rows: list[dict], issued: dict, cur: dict,
                       gate: str, reach=None, *, prev: dict | None = None, steps: dict | None = None,
                       changed: list[str] | None = None, why: list[str] | None = None) -> dict | None:
    """Whether a UNIT's gate obligation is discharged at its checkpoint because
    the failure the gate NOW reports belongs to a different obligation.

    The package gate reports one failure at a time, so its issued obligation
    disappearing is not proof by itself (UNPROVEN). The unit is accepted at its
    checkpoint only on POSITIVE evidence for every failure the gate now reports
    (B6): the typed reach test (amend-scope.unit_reach, the same test that
    refuses to widen the card) answers OUTSIDE_SCOPE -- never UNKNOWN -- and
    the failure is shown independent of the candidate (_gate_cause_independent).
    v12 t_b33f25fa: the fragment implementations were right and the build then
    stopped on an unrelated, unchanged SpEL @Value. The package+boot proof stays
    owed by the closing card. Anything short of that is None, the reason is
    appended to ``why`` (GATE_HANDOFF_UNPROVEN naming the cause), and the card
    stays pending exactly as before.
    """
    def refuse(text: str) -> None:
        if why is not None:
            why.append(text)
        return None

    if gate != "package" or not scope_rows or any(r.get("verdict") != "ok" for r in scope_rows):
        return None
    issued_gate = {str(i) for i in (issued.get("gate_items") or [])}
    now = [i for i in (cur.get("items") or []) if str(i.get("gate") or "") == gate]
    if not issued_gate or not now or issued_gate & {str(i.get("id")) for i in now}:
        return None
    if not (cur.get("measure") or {}).get("known"):
        return refuse("GATE_HANDOFF_UNPROVEN: the candidate's measure is not known, so no gate record is candidate-bound")
    if reach is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("amend_scope", Path(__file__).resolve().parent / "amend-scope.py")
        amend = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(amend)
        reach = amend.unit_reach
    prev_commit = str((prev or {}).get("commit") or "")
    rows = []
    for item in now:
        rel = str(item.get("path") or "")
        if item.get("unlocated") or item.get("set_wide") or not rel:
            return refuse("GATE_HANDOFF_UNPROVEN: package obligation %s is %s; independence UNKNOWN"
                          % (item.get("id"), "unlocated" if (item.get("unlocated") or not rel) else "set-wide"))
        status, detail = reach(root, scope_doc, rel)
        if status != "OUTSIDE_SCOPE":
            return refuse("GATE_HANDOFF_UNPROVEN: package obligation %s at %s; reach %s (%s)"
                          % (item.get("id"), rel, status, str(detail)[:200]))
        independent = _gate_cause_independent(root, item, prev_commit, steps or {}, list(changed or []))
        if independent is None:
            return refuse("GATE_HANDOFF_UNPROVEN: package obligation %s at %s (%s); independence UNKNOWN: no accepted "
                          "step recorded it and its cause is not a file-local expression unchanged since %s"
                          % (item.get("id"), rel, item.get("cause") or "unclassified", (prev_commit or "HEAD")[:12]))
        rows.append({"id": str(item.get("id")), "path": rel, "cause": str(item.get("cause") or ""),
                     "outside_unit": str(detail)[:300], "reach": status, "independence": independent})
    # V16-4: a unit whose obligations are CDI beans (a fragment delegate owed
    # its concrete-only exposure) is checked STRUCTURALLY here; whether the
    # container resolves them is decided at augmentation, which the build has
    # not reached. The handoff keeps those obligations on the record and says
    # the wiring is unverified -- never that it is correct.
    beans = [{"type": str(r.get("type") or ""), "path": str(r.get("path") or ""), "parent": str(r.get("parent") or ""),
              "contract": str(r.get("contract") or ""), "cdi": dict(r["cdi"])}
             for r in (scope_doc.get("implementation_obligations") or [])
             if isinstance(r, dict) and isinstance(r.get("cdi"), dict)]
    out = {"gate": gate, "issued": sorted(issued_gate), "now_reported": rows,
           "accepted_commit": prev_commit[:12],
           "debt": {"package": "owed", "boot": "owed"},
           "owed_by": "the closing card: an empty work list and the package and boot gates passing on the same artifact",
           "reason": ("the unit's %s obligation %s is no longer reported and every sealed member assesses clean; the "
                      "gate now stops on %s, located in %s, which this unit does not reach (OUTSIDE_SCOPE) and which "
                      "the candidate did not cause (%s) -- a different obligation, minted next; the %s proof stays "
                      "owed by the closing card"
                      % (gate, ", ".join(sorted(issued_gate)), ", ".join(r["cause"] or r["id"] for r in rows),
                         ", ".join(r["path"] for r in rows), ", ".join(r["independence"]["kind"] for r in rows), gate))}
    if beans:
        out["bean_obligations"] = beans
        out["bean_wiring"] = ("unverified: the package gate stopped before augmentation validated these %d bean(s); "
                              "the first candidate that clears %s must package under the decided build profile before "
                              "the wiring is claimed complete" % (len(beans), ", ".join(r["path"] for r in rows)))
        out["reason"] += ("; the bean wiring of %s is NOT verified by this checkpoint (structural only)"
                          % ", ".join(b["type"].rsplit(".", 1)[-1] for b in beans[:4]))
    return out


def _cdi_wiring_record(root: Path, prev_commit: str, changed: list[str], on_disk: str) -> dict:
    """V16-4 acceptance rule: compilation cannot establish bean correctness.
    When the candidate changed CDI wiring (cdi_wiring_changes, from the compiler
    models of the accepted commit and the candidate) and the package gate did
    not pass on THIS candidate, the step records the change as unverified with
    package and boot owed. {} when nothing changed or packaging proved it."""
    pkg = load_json(root / VERIFY_PACKAGE) if (root / VERIFY_PACKAGE).is_file() else {}
    bound = isinstance(pkg, dict) and bool(on_disk) and str(pkg.get("candidate_sha256") or "") == on_disk
    if bound and pkg.get("ran") and pkg.get("rc") == 0:
        return {}
    if not any(str(p).endswith(".java") for p in changed) or not prev_commit:
        return {}
    try:
        rows = cdi_wiring_changes(root, prev_commit, changed)
    except DestModelUnavailable as exc:
        return {"changed": [], "assessed": False, "verified": False, "packaged": False,
                "debt": {"package": "owed", "boot": "owed"},
                "summary": "whether the candidate changed CDI wiring could not be assessed (%s)" % str(exc)[:160]}
    if not rows:
        return {}
    ran = "packaging failed on this candidate (%s)" % (pkg.get("failed_goal") or pkg.get("detail") or "rc %s" % pkg.get("rc")) \
        if bound and pkg.get("ran") else "packaging did not run on this candidate"
    return {"changed": rows[:20], "assessed": True, "verified": False, "packaged": False,
            "profile": str(pkg.get("profile") or "") if bound else "", "packaging": ran,
            "debt": {"package": "owed", "boot": "owed"},
            "summary": "the candidate changed the CDI wiring of %s; %s" % (
                ", ".join("%s (%s)" % (r["type"].rsplit(".", 1)[-1], r["change"]) for r in rows[:4]), ran)}


# A bean the container names as a candidate for an injection point: the
# `target=` of each "available beans" row ArC prints for an ambiguous or
# unsatisfied dependency (quarkus-arc BeanDeployment.processErrors).
_BEAN_TARGET = r"target=([A-Za-z_$][\w$.]*)"


def _bean_source(target: str) -> str:
    """The source file a bean `target=` names: a nested type is its outer
    file, and a generated class (SpringDataXRepository_<hash>Impl) is the
    interface it was generated from."""
    pkg, _, simple = target.rpartition(".")
    simple = simple.split("$")[0].split("_")[0]
    return "src/main/java/%s%s.java" % ((pkg.replace(".", "/") + "/") if pkg else "", simple)


def _gate_scope_guidance(issued: dict, cur: dict, gate: str, changed: list[str]) -> dict | None:
    """V16-2 (v16 t_d3f89ded): what the gate reports NOW, against the card's
    scope -- the write set it was issued (and every amendment recorded on it).

    A failure the gate locates outside that scope is never this candidate's to
    repair: its location may be an unchanged consumer while the cause is a
    bean this candidate added, or a prerequisite another card or the Operator
    owns. So the answer is VERIFICATION_PENDING naming the paths, the scope
    and the Operator prerequisite -- never an instruction to edit them here,
    and never an acceptance by filename (a location is not independence).
    A failure with no location, or set-wide, has an UNKNOWN cause and stays
    pending until it is classified. None when the gate reports nothing new;
    {cause: ""} when everything it names is inside the scope."""
    import re
    if gate not in ("package", "boot"):
        return None
    issued_ids = {str(i) for i in (issued.get("items") or [])} | {str(i) for i in (issued.get("gate_items") or [])}
    now = [i for i in (cur.get("items") or []) if str(i.get("gate") or "") == gate and str(i.get("id")) not in issued_ids]
    if not now:
        return None
    scope = sorted({str(p) for p in (issued.get("write_set") or [])})
    inside, outside, unknown = [], [], []
    for i in now:
        rel = str(i.get("path") or "")
        if i.get("unlocated") or i.get("set_wide") or not rel:
            unknown.append(i)
        elif rel in scope:
            inside.append(i)
        else:
            outside.append(i)
    if not outside and not unknown:
        return {"cause": "", "record": {},
                "reason": ("the %s gate still fails and the issued obligation is no longer reported, which is not proof it "
                           "was repaired; the gate now names %s, inside this card's write set: repair it in this "
                           "candidate, and the gate passing discharges them together"
                           % (gate, ", ".join("%s (%s)" % (i["path"], i.get("cause") or "unclassified") for i in inside[:3])))}
    # the beans the container names for the failing injection point, and
    # which of them this candidate changed: a location is not a cause
    changed_set = {str(p) for p in changed}
    rows = []
    for i in outside + unknown:
        text = str(i.get("message") or "") + "\n" + str(i.get("detail") or "")
        beans = sorted({_bean_source(m) for m in re.findall(_BEAN_TARGET, text)})
        rows.append({"id": str(i.get("id") or ""), "path": str(i.get("path") or ""),
                     "cause": str(i.get("cause") or "unclassified"),
                     "location": "unknown" if i in unknown else "outside-scope",
                     "beans_named": beans, "beans_changed_by_candidate": sorted(set(beans) & changed_set)})
    caused = sorted({b for r in rows for b in r["beans_changed_by_candidate"]})
    located = [r for r in rows if r["location"] == "outside-scope"]
    unk = [r for r in rows if r["location"] == "unknown"]
    parts = []
    if located:
        parts.append("the %s gate now stops on %s at %s, outside this card's scope (write set: %s)"
                     % (gate, ", ".join(sorted({r["cause"] for r in located})), ", ".join(sorted({r["path"] for r in located})),
                        ", ".join(scope) or "none"))
    if unk:
        parts.append("%s %d failure(s) whose location or cause is UNKNOWN (%s), which stay pending until classified"
                     % ("and" if located else "the %s gate now reports" % gate, len(unk),
                        ", ".join("%s %s" % (r["id"], r["cause"]) for r in unk[:3])))
    if caused:
        prereq = ("the failure names bean(s) this candidate changed (%s), so the candidate may have caused it and no "
                  "handoff is possible: the Operator decides whether to reject the candidate or to record a scope "
                  "decision for the causal files" % ", ".join(caused))
    else:
        prereq = ("the Operator classifies the cause and, if it is not this candidate, records the repair of %s with "
                  "operator-step.py beside this pending card; then restore-pending.py, run-verify.sh --mode acceptance "
                  "and advance.py on this card" % (", ".join(sorted({r["path"] for r in located})) or "the named files"))
    reason = ("GATE_FAILURE_OUTSIDE_SCOPE: the %s obligation %s is no longer reported, which is not proof it was "
              "repaired, and %s. This candidate must not edit %s and must not widen its write set to reach %s. "
              "Required Operator prerequisite: %s"
              % (gate, ", ".join(sorted(str(i) for i in (issued.get("gate_items") or issued.get("items") or []))[:2]) or "issued",
                 "; ".join(parts), "those files" if located else "anything outside its write set",
                 "them" if located else "a cause no one has located", prereq))
    return {"cause": "outside-scope-prerequisite" if located else "unclassified-gate-failure", "reason": reason,
            "record": {"gate": gate, "scope": scope, "failures": rows, "caused_by_candidate": caused,
                       "prerequisite": prereq}}


def _mint(root: Path, hermes: str) -> int:
    """Trusted continuation: K4 mints the next card. The current card is a
    parent through steps.json, never the M2 control card."""
    ob = _outcome_bridge.reissue(root)
    if ob is not None:
        return ob  # outcome board: the next attempt stays on the same card; the graph is already published
    kernel = root / ".hermes" / "kernel" / "k4_mint.py"
    env = dict(os.environ)
    env.pop("HERMES_KANBAN_TASK", None)  # control cards come from verification/loop/cards.json
    proc = subprocess.run([sys.executable, str(kernel), "--root", str(root), "--exec", "--verify-board", "--hermes", hermes], text=True, capture_output=True, env=env)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
