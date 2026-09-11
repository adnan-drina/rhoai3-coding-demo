---
name: paved-road-m3
description: >
  Pin only this on every M3 loop card (K4 stamps it). Index for one step
  of the fix-until-green loop: view the loop procedure, read the brief,
  patch the write set one item at a time, run the real tools, run the
  acceptance transaction, complete on its verdict. No reviewer seat: the
  transaction is the audit (K2 lets the implementer complete once the loop
  record names the card). Never for M1, M2, M4, or story implementation.
license: Apache-2.0
compatibility: Linux seat; Hermes v0.20.5 Kanban; Python 3.11+
metadata:
  author: rhoai3-harness-team
  version: "1.1.0"
  hermes:
    tags:
    - paved-road
    - m3
    category: paved-road
    kind: guidance
---
# Paved road: M3 loop step (view → brief → patch per item → run-verify → advance → complete)

`steps.json` is the contract; `audit.json` is generated from it
(`python3 .hermes/lib/paved_road.py generate --steps steps.json --out audit.json`).
The audit (`scripts/assert-paved-road-audit.py`) grades the official
kanban log plus the loop record: advance.py is a **verdict step**, so its
exit code is not the grade. `verification/loop/steps.json` naming this
card as an accepted step or a rejected attempt is. K2 applies the same
rule to `kanban_complete`.

## Procedure (in order)

1. `skill_view fix-until-green` — the loop procedure. Do not view
   `author-destination-pom`, `manage-quarkus-extensions` or
   `reference-rh-quarkus-pom` on a loop card (pilot v5 measured the
   whole-pom rewrite they produce). The brief carries the pom data.
2. `python3 .hermes/skills/migration/fix-until-green/scripts/brief.py --root .`
   — the head cluster's brief. **The brief is the plan.** Each item carries
   the rule's advice; pom items carry the element at the line, which
   advised artifacts are already present, and which advised artifact the
   BOM does not manage together with the managed equivalent
   (`advice_unmanaged` / `advice_managed_equivalent`: use the equivalent,
   never the old name, never a version). Compile items carry the compiler
   diagnostic, the inventory hit for a missing type, the Jakarta rename for
   a `javax.*` package, and the reference file that covers a Spring symbol.
   Config items carry the property line and the catalog mapping.
3. Patch the write set **one item at a time**. Never satisfy an item by
   deleting the code or configuration it is about: an obligation on a
   Spring profile file is met by moving its keys into
   `application.properties` as `%<profile>.<key>` (advance.py vetoes a
   deletion whose `quarkus.*` or catalog-mapped keys did not land). If the
   documented fix needs a path outside the write set, `kanban_block`
   kind=needs_input naming that path. Never a whole-file rewrite
   (the model server buffers a tool call's arguments; a 12 KB rewrite is
   minutes of silence). Never tests, never `evidence/`, never
   `decisions.yaml`, never a plugin or dependency the brief did not ask
   for, never a path outside the write set (advance.py reverts it).
   No inline python (`python3 -c`, `python3 -`) on a loop card: K2 refuses
   it. Everything it would compute is already in the brief.
4. `bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root .`
   — the real tools. Default is `--mode acceptance` (tests, MTA, packaging/startup
   when green). `--mode diagnostic` is classpath + compiler only and **cannot**
   feed advance.py. exit 1 here is a tool failure: re-run it; if it stays
   red, `kanban_block` kind=needs_input naming the tool. Do not run extra
   `mvn compile`/`test`/`verify` beside this script.
5. `python3 .hermes/skills/migration/fix-until-green/scripts/advance.py --root . --cluster <id> --card $HERMES_KANBAN_TASK`
   — the transaction decides. `OK: ACCEPTED` committed and minted the next
   card. `REVERTED` (exit 1) discarded the candidate and re-minted this
   cluster as its own next card. `CONTINUE` (exit 3, repair-family cards)
   kept the candidate on the tree without counting an attempt: the compiler
   now names another member of this card's sealed family — repair it (the
   brief's `batch_scope` lists every member and its verdict), then steps 4
   and 5 again on this card. `VERIFICATION_PENDING` (exit 1) retained the
   candidate without counting an attempt. `DEFERRED` (exit 1) stopped the
   loop. A candidate that introduces an unhandled checked exception is
   `REVERTED` even when the measure fell.
6. Terminator: **`kanban_complete`** after ACCEPTED or REVERTED (K2 allows
   it because the loop record names this card and steps 1, 2, 4, 5 are in
   this log). `kanban_block` kind=needs_input naming the cluster after
   VERIFICATION_PENDING, DEFERRED or a `REFUSE: LOOP_*`. `CONTINUE` is not a
   verdict: neither complete nor block. Never `kanban_request_review` on a loop
   card; never retry inside this card after REVERTED (the retry is the next K4 card).
   After VERIFICATION_PENDING, restore with `restore-pending.py` when the
   prerequisite changes, then run acceptance verify and advance on **this**
   card — do not mint a new attempt.

## Reference skills (view only when the brief's advice is not enough)

The card body names one per cluster kind: `spring-to-quarkus-patterns`
for compile / incident / test items (its `references/*.md` are cited per
symbol in the brief), `configure-quarkus-profiles` for config items. They
are references, not checklists: the brief's items are the work.

## Operator

- DEFERRED is a mechanism stop, not a request for a human to edit code.
  The Operator fixes the cause (a harness defect, a catalog gap, an ADR in
  `decisions.yaml`) and, when an accepted step was a false green, runs
  `fix-until-green/scripts/rewind.py --to-step N --operator WHO --reason WHY`
  (restores the tree, re-measures, clears the budget, mints in a new epoch).
- A card that ended blocked although the record names its verdict:
  `hermes kanban complete <id> --summary "…"` from the CLI.

## Self-test

`python3 scripts/selftest.py` (golden only, never on a card): steps.json ↔
audit.json sync, the kind rules, fixture PASS/REFUSE set, coverage lint.
