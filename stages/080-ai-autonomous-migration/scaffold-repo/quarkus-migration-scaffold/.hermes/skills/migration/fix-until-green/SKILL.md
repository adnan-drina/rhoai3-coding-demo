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
| measure strictly decreased, no new mandatory obligation | `REVERTED` | candidate discarded (index and working tree); accepted reports restored; attempt counted |

| Outcome | What happened | Your terminator |
|---|---|---|
| `ACCEPTED` | exactly the changed paths committed, tool reports snapshotted, work list rebuilt, admission re-sealed, next card minted (K4) with this card as parent and K3-verified | `kanban_complete` (the loop record is the audit; K2 allows it once brief, run-verify and advance ran in this log) |
| `REVERTED` (exit 1) | same cluster re-issued with the next attempt key | `kanban_complete` — the retry is its own card; never loop inside this card |
| `VERIFICATION_PENDING` (exit 1) | candidate retained under `verification/loop/pending-files/`; issued card kept; K4 will not mint | `kanban_block` kind=needs_input naming the cluster. When the prerequisite changes: `restore-pending.py` then `run-verify.sh --mode acceptance` then `advance.py` |
| `DEFERRED` (exit 1) | attempt threshold reached → cluster in `verification/loop/deferred.json`; **the loop stops**, nothing mints | `kanban_block` kind=needs_input naming the cluster (Operator: `scripts/rewind.py` after the cause is fixed) |
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
  (tree, budget, deferral, new epoch) → re-land → green → M4.
- Every accepted step is a commit; `verification/loop/steps.json` is the
  append-only record; the sealed work list is rebuilt, never edited.

## Scripts

- `scripts/brief.py` — the head cluster's brief
- `scripts/run-verify.sh` — `--mode diagnostic` (classpath + JDK diagnostics) or `--mode acceptance` (default: online warm-up, then offline JDK diagnostics, surefire, MTA rescan, packaging/startup when green) → `verify.py`; every tool's exit status and stage duration lands in `verification/build/run.json`
- `scripts/verify.py` — tool outputs + recorded outcomes → work list + state + candidate identity
- `scripts/advance.py` — the acceptance transaction (`--baseline` records step 0; unknown measure → `VERIFICATION_PENDING`)
- `scripts/restore-pending.py` — put a retained candidate back on the product tree (then acceptance verify + advance)
- `scripts/operator-step.py` — Operator step: a decided change to the product tree (an ADR retirement applied by `bootstrap-destination.py --retire-only`) committed, re-measured and recorded as a loop step (`verdict: operator`) so the next card's baseline is true
- `scripts/rewind.py` — Operator rewind to an accepted step (`--to-step N --operator WHO --reason WHY`; re-measures with run-verify.sh, refuses on a measure mismatch, starts a new card-key epoch)
- `scripts/jdk-diagnostics/JdkDiagnostics.java` — compiler diagnostics as JSON (JDK compiler API)
- `scripts/_loop_common.py` — shared helpers
- `scripts/fix-until-green.test.py` — selftest

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
