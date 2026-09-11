---
name: fix-until-green
description: >
  Use on every M3 loop card (title "M3 c:<cluster>"). The common
  procedure of the fix-until-green loop: read the brief (the cluster's
  items from the sealed work list), edit only the cluster's write set,
  then let the tools decide — run-verify.sh recomputes compiler
  diagnostics, tests and the MTA rescan into the work list, and
  advance.py is a transaction: it promotes the candidate only when the
  card is the issued one, the tree is exactly the one verify.py measured,
  every changed path is inside the write set, and the measure strictly
  decreased with no new mandatory obligation; otherwise it discards the
  candidate (index and working tree) and re-mints the same cluster; at
  the ADR threshold the cluster is deferred to a human and the loop
  STOPS. Never edit tests, evidence/, verification/, decisions.yaml, or
  the work list. Not a producer skill (pair with the kind's producer).
license: Apache-2.0
compatibility: Linux seat; JDK 21 (javac); Maven offline; git; Python 3.11+
metadata:
  author: rhoai3-harness-team
  version: "1.1.0"
  hermes:
    tags:
    - migration
    - m3
    category: migration
    kind: guidance
    paths:
      reads: ["/projects/modernized/evidence/planning", "/projects/modernized/verification"]
      writes: ["/projects/modernized/src/main", "/projects/modernized/pom.xml", "/projects/modernized/verification"]
---
# Fix until green (the loop, one card = one cluster)

One state (the destination branch), one predicate (build green, zero
mandatory incidents, tests green, parity), one work list (tools only),
one loop. The model proposes; the tools decide.

## Procedure

```bash
python3 "${HERMES_SKILL_DIR}/scripts/brief.py" --root /projects/modernized          # 1. what this card is
#   … patch the write set one item at a time (the brief lists each item with its advice and,
#     for pom.xml, the element at the reported line); never a whole-file rewrite; never tests … # 2. propose
bash "${HERMES_SKILL_DIR}/scripts/run-verify.sh" --root /projects/modernized --mode acceptance  # 3. tools recompute the work list
python3 "${HERMES_SKILL_DIR}/scripts/advance.py" --root /projects/modernized \
  --cluster <cluster id from the brief> --card "$HERMES_KANBAN_TASK"               # 4. accept / revert / pending / defer, then mint or block
```

Optional cheap pass before acceptance (classpath + JDK diagnostics only; cannot feed `advance.py`):

```bash
bash "${HERMES_SKILL_DIR}/scripts/run-verify.sh" --root /projects/modernized --mode diagnostic
```

`advance.py` is a transaction over the candidate verify.py measured:

| Check | Refusal | Effect |
|---|---|---|
| `--cluster` is the issued card (`verification/loop/issued.json`, written by K4) and `--card` is its minted `t_*` | `LOOP_NOT_ISSUED` / `LOOP_WRONG_CARD` | nothing promoted; candidate discarded |
| the product tree is exactly the tree verify.py measured (`candidate_sha256`) | `LOOP_CANDIDATE_CHANGED` | nothing promoted; candidate discarded; attempt counted |
| every changed path is inside the write set (tests are never in one) | rejected: `outside the write set` | candidate discarded; attempt counted |
| the measure is not fully known (harness / environment / unresolved) | `VERIFICATION_PENDING` | candidate files retained; accepted tree restored; attempt **not** counted |
| a changed Java file introduces an unhandled checked exception, or adds one to a member's `throws` — compiler-derived: the last accepted commit and the candidate are modelled under the same compiler configuration, catches and declared throws accounted for | `REVERTED` (`introduced … unhandled checked exception`) | candidate discarded; attempt counted — **even when the measure fell** (javac reports one such site per compilation, so a count can fall while six are introduced) |
| whether a changed file introduces one cannot be decided (a site the compiler could not decide, or incomplete baseline coverage the parse tree cannot settle) | `VERIFICATION_PENDING` (`unassessable-exceptions`) | candidate retained; attempt **not** counted |
| the issued compile diagnostic's identity — file, member, call site, exception, never the line — is gone, the count did not fall, and the compiler now names another member of this card's sealed family | `CONTINUE` (exit 3) | the candidate **stays on the tree**; no attempt; recorded on the issued card; at most one continuation per family member; a continuation that did not move is `REVERTED` |
| … and what the compiler names now is outside every sealed scope of the card | `VERIFICATION_PENDING` (`exposed-outside-scope`) | candidate retained; accepted tree restored; attempt **not** counted |
| a failing package/boot gate no longer names the issued obligation | `VERIFICATION_PENDING` (`unproven-repair`) | candidate retained; attempt **not** counted |
| the issued compile diagnostic is still reported, or the measure did not otherwise decrease | `REVERTED` | candidate discarded (index and working tree); accepted reports restored; attempt counted |

| Outcome | What happened | Your terminator |
|---|---|---|
| `ACCEPTED` | exactly the changed paths committed, tool reports snapshotted, work list rebuilt, admission re-sealed, next card minted (K4) with this card as parent and K3-verified | `kanban_complete` (the loop record is the audit; K2 allows it once brief, run-verify and advance ran in this log) |
| `REVERTED` (exit 1) | same cluster re-issued with the next attempt key | `kanban_complete` — the retry is its own card; never loop inside this card |
| `CONTINUE` (exit 3) | repair-family card only: the candidate stays on the tree, the continuation is recorded in `issued.json`, no attempt is spent | none — it is not a verdict. Repair the members the brief lists, `run-verify.sh --mode acceptance`, then `advance.py` again on this card |
| `VERIFICATION_PENDING` (exit 1) | candidate retained under `verification/loop/pending-files/`; issued card kept; K4 will not mint | `kanban_block` kind=needs_input naming the cluster. When the prerequisite changes: `restore-pending.py` then `run-verify.sh --mode acceptance` then `advance.py` |
| `DEFERRED` (exit 1) | attempt threshold reached → cluster in `verification/loop/deferred.json`; **the loop stops**, nothing mints | `kanban_block` kind=needs_input naming the cluster (Operator: remove the cause, then `operator-step.py --clear-deferred <cluster>` with the product change, or `--clear-deferred <cluster> --disposition-only` when the cause was a harness defect; `rewind.py` only to abandon later steps) |
| (Operator) `scripts/rewind.py` | the Operator puts the loop back at an accepted step: product tree restored and re-measured, later steps and the spent budget moved to the record as `rewound`, deferral cleared, next card minted in a new epoch | not a card action; `--operator` and `--reason` are recorded in `steps.json.rewinds` |
| `REFUSE: LOOP_*` | stale state / no baseline / receipt not authoritative | `kanban_block` kind=needs_input |

Measurement contract: a component is known only when its tool ran in this
verification (`verification/build/run.json`). Tests that did not run, an
empty surefire directory, a `mvn test` failure with no recorded failing
test, a skipped MTA rescan, or a pom Maven cannot resolve (the compiler
never saw the sources) make the measure unknown. Unknown is not a
product regression: `advance.py` records `VERIFICATION_PENDING`, keeps
the candidate, and does not count an attempt. Known product regressions
still reject. Diagnostic mode (`run-verify.sh --mode diagnostic`) cannot
feed the acceptance transaction. Unknown ranks above every known measure: a candidate the
tools could measure beats a baseline they could not, provided it adds no
mandatory obligation. Obligation identity is line-free: moving code is
not a new obligation.

The measure is `(mandatory incidents, compile errors, failing tests,
parity mismatches)`. Removing a Spring annotation may add compile errors
while removing an incident — that is progress (lexicographic). Making a
test pass by editing the test is not possible (tests are never in a
write set).

No reviewer seat runs for a loop step: `kanban_request_review` on a loop
card is refused by K2. The card pins `paved-road-m3` (the index that views
this skill); the audit it declares grades the official log plus the loop
record naming the card.

## Verification

- `scripts/fix-until-green.test.py` — bootstrap → baseline → accept →
  revert (attempt 2) → unresolvable candidate retained as VERIFICATION_PENDING
  (attempts stay 0) → known no-progress defer (loop stops) → Operator rewind
  (tree, budget, deferral, new epoch) → re-land → green → M4. URI Location
  family: a transformation that makes the count fall while introducing an
  unhandled checked exception is REVERTED; the family is the sites ONE step
  introduced (a legacy site stays out); Owner→Pet CONTINUEs in the same card
  without an attempt; a stalled continuation rejects; an exposure outside the
  family is a typed VERIFICATION_PENDING.
- Every accepted step is a commit; `verification/loop/steps.json` is the
  append-only record; the sealed work list is rebuilt, never edited.

## Scripts

- `scripts/brief.py` — the head cluster's brief
- `scripts/run-verify.sh` — `--mode diagnostic` (classpath + JDK diagnostics) or `--mode acceptance` (default: online warm-up, then offline JDK diagnostics, surefire, MTA rescan, packaging/startup when green) → `verify.py`; every tool's exit status and stage duration lands in `verification/build/run.json`
- `scripts/verify.py` — tool outputs + recorded outcomes → work list + state + candidate identity
- `scripts/advance.py` — the acceptance transaction (`--baseline` records step 0; unknown measure → `VERIFICATION_PENDING`)
- `scripts/restore-pending.py` — put a retained candidate back on the product tree (then acceptance verify + advance)
- `scripts/operator-step.py` — Operator step: a decided change to the product tree (an ADR retirement applied by `bootstrap-destination.py --retire-only`) committed, re-measured and recorded as a loop step (`verdict: operator`) so the next card's baseline is true. `--clear-deferred` appends a disposition naming the cluster, its retry key and what it spent, and the budget rises by that (`planner/budget.py` is the one budget answer); `--disposition-only` records that disposition with no product change, for a cause that was a harness defect
- `scripts/rewind.py` — Operator rewind to an accepted step (`--to-step N --operator WHO --reason WHY`; re-measures with run-verify.sh, refuses on a measure mismatch, starts a new card-key epoch)
- `scripts/amend-scope.py` — widen a sealed batch card's write set by ONE file, on the record (`--path` + `--reason`), BEFORE touching it; the inventory itself is never rewritten and two amendments per card is the limit
- `scripts/diagnose.py` — (Operator) investigate a failure no card can carry: `--list` names them, `--open` starts one of two ten-minute attempts, `--close --conclusion LOCATED|ENVIRONMENT|DECISION_REQUIRED|INCONCLUSIVE` records the finding under `evidence/diagnosis/`. It grants no write authority — a product change during an investigation refuses the close — and closing discharges nothing
- `scripts/jdk-diagnostics/JdkDiagnostics.java` — compiler diagnostics as JSON (JDK compiler API)
- `scripts/jdk-dest-model/DestModel.java` — the DESTINATION's own structure from the JDK compiler API: resolved member signatures, what a type actually inherits and what its supertypes declare, and every annotation with its exact character range and its imports. Read through `planner.dest_model`, which caches it against the content of the sources AND the classpath it was compiled with, and raises rather than guessing. A regular expression answered these questions wrongly in both directions (a fully qualified annotation read as absent; a redeclared `findAll()` as underivable; a deleted member as inherited), so nothing here is read from text
- `scripts/_loop_common.py` — shared helpers
- `scripts/fix-until-green.test.py`, `scripts/amend-scope.test.py`, `scripts/diagnose.test.py` — selftests

## Pitfalls

- Rewriting a whole file through one tool call. The model server buffers a
  tool call's arguments until they are complete, so a 12 KB `pom.xml`
  rewrite is several thousand tokens of silence on the wire and trips the
  stream-read timeout (measured live 2026-09-09: two `APITimeoutError`
  retries on the first pom card). Edit with targeted patches, one incident
  or one dependency block at a time; the verifier measures the result, not
  the size of the edit.

- Touching a file outside the write set: the diff is reverted with the
  step, and K2 refuses the write in the first place.
- "Fixing" by deleting the offending code: incidents drop, but tests or
  parity will count it back at the end.
- Editing `verification/` or the work list by hand: `advance.py` refuses
  on a stale state.
