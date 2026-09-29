---
name: paved-road-m3
description: >
  Pin only this on every M3 loop card (K4 stamps it). Index for one step
  of the fix-until-green loop: view the loop procedure, read the brief,
  patch the write set one item at a time, run the real tools, run the
  acceptance transaction, complete on its verdict. No reviewer seat on a
  serial-loop run: the transaction is the audit (K2 lets the implementer
  complete once the loop record names the card). On an outcome-board/v2 run
  the accepted outcome goes to review (section below). Never for M1, M2,
  M4, or story implementation.
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
2. `python3 .hermes/skills/migration/fix-until-green/scripts/brief.py --root . --cluster <id>`
   — **this card's** brief (the cluster id is stamped on the card). If
   `--cluster` is omitted, the script binds to `verification/loop/issued.json`
   when `$HERMES_KANBAN_TASK` matches. The work-list **head** after a workspace
   bounce is not this card (v9 `t_cc3b6aac`: `LOOP_NO_OPEN_CLUSTER` then
   rummaging). `REFUSE: LOOP_WRONG_CARD` / `LOOP_CLUSTER_NOT_OPEN` /
   `LOOP_NO_OPEN_CLUSTER` → `kanban_block` kind=needs_input naming the cluster;
   do not rummage `verification/loop/`. **Your own issued cluster is never
   "not open" to you:** when a mid-card verification no longer lists it, the
   brief says `issued_not_open` and its procedure is run-verify (if the
   candidate changed) then `advance.py` for this card — do that and follow the
   verdict; do not block. A parity card's advice is under `parity`:
   `body_diffs` (the differing paths and the producing file), `server_errors`
   (the exception behind a 5xx and the first product frame), and `handlers`
   -- one entry per handler for every `request_rejections` item at it (a 4xx
   with an empty body where the source accepted the same body-carrying
   request): each parameter classified against the compat catalog with the
   rows' notes and sources, and `first_action`. Do it; do not re-derive it.
   A handler entry with `generated_body.missing_required` is a **pom.xml
   build card** (the body type is generated; its first action is the
   generator option under `<configOptions>`); never edit the generated file.
   All three are handled by the scope rule in step 3. K2 treats `brief.py` `[exit 1]` as a
   bound gate: re-run brief or `kanban_block` (run-verify and advance need not
   have run). **The brief is the plan.** Each item carries
   the rule's advice; pom items carry the element at the line, which
   advised artifacts are already present, and which advised artifact the
   BOM does not manage together with the managed equivalent
   (`advice_unmanaged` / `advice_managed_equivalent`: use the equivalent,
   never the old name, never a version). Compile items carry the compiler
   diagnostic, the inventory hit for a missing type, the Jakarta rename for
   a `javax.*` package, and the reference file that covers a Spring symbol.
   An item with `already_imported: true` is a classpath/API replacement —
   follow `do_not`; do not add the same import again. Config items carry the
   property line and the catalog mapping.
3. Patch the write set **one item at a time**. Never satisfy an item by
   deleting the code or configuration it is about: an obligation on a
   Spring profile file is met by moving its keys into
   `application.properties` as `%<profile>.<key>` (advance.py vetoes a
   deletion whose `quarkus.*` or catalog-mapped keys did not land).
   **Scope rule** (for every parity item, and for any runtime obligation
   whose producing file is outside the write set): find the producing file
   -- the item's `locus_hints` name it: a `body_diff`'s producer, a
   `server_error`'s first product frame, a `request_rejection`'s handler or
   body type -- record it BEFORE editing it with
   `amend-scope.py --root . --cluster <id> --card $HERMES_KANBAN_TASK --path
   <file> --reason <why> --evidence parity:<item id>` (bounded by the card's
   own bounds: two amendments, a unit's four and never past its file bound),
   then edit it — with the file tools (`patch`, `write_file`) on that path;
   they honour the amended set (K2 reads `issued.json`). The config file
   `application.properties` is amended the same way when the advice names a
   property there (navigation: `quarkus.swagger-ui.always-include=true`);
   never serve a substitute page from a handler instead — advance reverts it.
   `kanban_block` kind=needs_input ONLY when amend-scope.py
   REFUSES (quote its `REFUSE: SCOPE_AMENDMENT` line) or when the fix is in a
   path the loop never grants: tests, `evidence/`, `decisions.yaml`, a plugin
   or dependency the brief did not ask for. A path outside the amended write
   set is reverted by advance.py. Never a whole-file rewrite
   (the model server buffers a tool call's arguments; a 12 KB rewrite is
   minutes of silence). Never tests, never `evidence/`, never
   `decisions.yaml`, never a plugin or dependency the brief did not ask
   for.
   No inline python (`python3 -c`, `python3 -`) on a loop card: K2 refuses
   it. Everything it would compute is already in the brief.
4. `bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root .`
   — the real tools. Default is `--mode acceptance` (tests, MTA, packaging/startup
   when green). `--mode diagnostic` is classpath + compiler only and **cannot**
   feed advance.py. exit 1 here is a tool failure: re-run it; if it stays
   red, `kanban_block` kind=needs_input naming the tool. Do not run extra
   `mvn compile`/`test`/`verify` beside this script.
5. `python3 .hermes/skills/migration/fix-until-green/scripts/advance.py --root . --cluster <id> --card $HERMES_KANBAN_TASK`
   — the transaction decides. Run it ONCE per verify, through the terminal
   tool with its `timeout` parameter set to `600` (its foreground maximum;
   the default 180 s killed a 30 s acceptance on v9 `t_2da2458b`). It prints
   `advance: <phase>` lines; the verdict is on the record when printed.
   After any non-zero, killed (`[exit 124]`) or truncated advance: run it
   again — it is idempotent and answers `OK: ACCEPTED already (step N,
   commit X)` / `REVERTED already` — or read `verification/loop/steps.json`.
   Never `kanban_block` a card whose step is recorded accepted (K2 refuses
   it): `kanban_complete` is its terminator. `OK: ACCEPTED` committed and minted the next
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
   this log). After VERIFICATION_PENDING: nothing -- `advance.py` raised the
   run's stop request, and the runtime blocks the card (needs_input) and
   ends the run; only when `advance.py` printed `Terminator: kanban_block`
   (no stop-request variable) is `kanban_block` the terminator.
   `kanban_block` kind=needs_input naming the cluster after DEFERRED or a
   `REFUSE: LOOP_*` (K2 allows that block even when run-verify and advance
   did not run). `CONTINUE` is not a
   verdict: neither complete nor block. Never `kanban_request_review` on a loop
   card; never retry inside this card after REVERTED (the retry is the next K4 card).
   After VERIFICATION_PENDING, restore with `restore-pending.py` when the
   prerequisite changes (the Operator's unblock starts a new run; K2 allows
   the restore whenever this card has a pending record), then run acceptance
   verify and advance on **this** card — do not mint a new attempt.

## Evidence, stop, reads (every loop card)

- Evidence: the measured artifact is the packaged application run-verify.sh
  builds under the declared build profiles (`decisions.yaml build_profiles`)
  and starts as the parity phase starts it. `mvn quarkus:dev`, a dev-profile
  build, `java -jar`, or any server you start is NOT evidence (K2 refuses
  it): a dev build activates other beans and config than the packaged build.
- The ONLY way to observe the destination is run-verify.sh: it packages,
  starts, replays this card's scenarios, re-runs its read oracles, and leaves
  the verdicts, the destination log and (for a 5xx) the exception under
  `verification/parity`. The brief is their digest.
- Stop: run-verify.sh prints `verify runs on card …: N` with the obligations
  still reported; the brief carries it as `verify_runs`. After two acceptance
  runs with the same obligations still reported: stop exploring. Write a
  typed diagnosis (what you changed; what each verify measured; the one
  hypothesis you could not test and the evidence that would test it) and
  `kanban_block` kind=needs_input carrying it. No third verify without a new
  edit. Never start a server to explore.
- Reads: the brief carries every diff, the advice, the loci and the catalog
  rows. Read a product file at most once per edit cycle. Do not read
  `receipt.json`, `_run.json` or verdict files.

## Reference skills (view only when the brief's advice is not enough)

The card body names one per cluster kind: `spring-to-quarkus-patterns`
for compile / incident / test items (its `references/*.md` are cited per
symbol in the brief), `configure-quarkus-profiles` for config items. They
are references, not checklists: the brief's items are the work.

## Outcome-board runs (new protocol, disabled by default)

Only when the run declares `outcome-board/v1` (see `.hermes/LAYOUT.md`). The
card is an OUTCOME, not one attempt: it stays open across rejected and pending
attempts, and it completes only when the outcome is accepted.

1. First call: `python3 .hermes/kernel/outcome_gate.py --root . issue`. It
   binds this native run and writes `verification/loop/issued.json` for the
   ONE cluster you may edit now. The printed `allowed_paths` is your write
   set. No issue means no product write (K2 refuses).
2. Then the same road: brief → patch → run-verify → advance. advance.py
   records the verdict on the outcome ledger. REVERTED or CONTINUE means
   read the brief again on this card, because the next attempt is re-issued
   here and no new card is minted. `OUTCOME ACCEPTED` means
   `kanban_complete`. `OUTCOME_BUDGET_EXHAUSTED` or VERIFICATION_PENDING
   means `kanban_block kind=needs_input`.
3. After a restart (a new native run), run `issue` again. A retained
   candidate is reported. `outcome_gate.py --root . restore-pending` adopts
   it and never renews the budget.
4. `OWNER_RECOVERY` (or `OWNER_REPAIR_PENDING`) from advance.py or `issue`:
   the runtime failure was proven on the baseline and belongs to an accepted
   outcome. The authority holds your candidate (no attempt spent) and
   publishes ONE repair of that outcome as this card's prerequisite. The only
   terminator is `kanban_block kind=dependency` (K2 refuses `kanban_complete`
   naming it). When the repair is accepted this card is dispatched again:
   run `issue`, then `outcome_gate.py --root . restore-held` to put the held
   candidate back, then run-verify and advance as usual (it is re-verified
   on the repaired baseline, never carried over).
5. A planned unit (`cluster` `planned:<outcome>:1`, no finding cluster) is
   issued like a cluster: its `allowed_paths` are the plan's bounded unit.

`kanban_request_review` is refused on an outcome card: its acceptance is
the recorded measurement.

## outcome-board/v2 runs (native control)

When the card body names "outcome-board/v2" the card is one
native task per outcome. Hermes Kanban owns its runs, dependencies and
review; the domain checks guard your native actions.

1. First call on every run: `python3 .hermes/kernel/native_gate.py --root . issue`.
   It checks this native run, writes `verification/loop/issued.json` for the
   ONE scope you may edit now and records the issue on the card. Its
   `allowed_paths` is your write set. No issue means no product write.
   Read its `next` field first:
   - `SATISFIED: …` — another outcome's accepted commit already discharged
     everything this card owns; the acceptance is recorded. Run `handoff`,
     then `kanban_request_review` reviewer=reviewer (item 3). Do not run
     brief.py or advance.py: there is nothing to edit.
   - `NOTHING ISSUED: …` — no scope and not satisfied: `kanban_block
     kind=needs_input` naming the reasons it lists. Do not search for work.
   - A **behavior or runtime card** measures the running application. When
     the work list reports an obligation no open card discharges (for
     example the package gate failing at another card's file), `issue`
     refuses before any scope: `OWNER_REPAIR_PENDING` names the follow-up it
     published for that file's owner (now this card's prerequisite): end the
     run with `kanban_block kind=dependency`; this card resumes after it.
     `ISSUE_ORPHANED_OBLIGATION` means no owner could be established: end
     the run with `kanban_block kind=needs_input` naming it. Never edit the
     other card's file, and never record a witness checkpoint to get past it.
2. The same road: brief, patch, run-verify, advance. A REVERTED attempt stays
   on this card: advance re-issues the scope (`CONTINUE THIS CARD`), read the
   brief again.
   **A compatibility objective** (`cluster` is `objective:<outcome>`): the scope is
   the whole objective, issued once. The brief's `objective` block lists every
   constituent's action in order, the checks judged now (`checks_now`) and those
   left to M4 (`checks_later`). Make ONE candidate that repairs every constituent:
   the same replacement at each of its sites, or the whole request boundary
   (validation guard, URI parameter, error payload). Do not split it across runs.
   advance judges each constituent against its own sealed inventory. A partial
   repair fails with the unrepaired constituent named, and a later check is
   never yours on this card.
3. `OUTCOME ACCEPTED`: run `python3 .hermes/kernel/native_gate.py --root . handoff`
   and end the run with `kanban_request_review` reviewer=reviewer, passing its
   `summary` and `metadata` (commit, tree, measurement, attempts, budget,
   limitations). Add one sentence on what changed if it helps the reviewer.
   Never `kanban_complete` (K2 refuses it for the implementer). The reviewer
   runs this road's audit and completes the card, or requests changes: then
   this card is dispatched to you again, and `issue` grants the paths your
   accepted commits changed (`rework:<outcome>:<run>`).
3a. **Parallel pilot pair** (the card body says "Parallel pilot"): you run
   beside one sibling card, each in its own git worktree -- the directory you
   start in -- not /projects/modernized. Run every tool with `--root .` from
   there; K2 refuses writes to the main tree or the sibling's worktree
   (`PILOT_CONFINED`). The first `issue` seeds the worktree's run state from
   the main tree. `CANDIDATE ACCEPTED IN THIS WORKTREE` is not yet the
   application's: run `python3 .hermes/kernel/native_gate.py --root . integrate`.
   It applies the candidate to the main tree (one card at a time) and runs the
   acceptance on the combined tree. `INTEGRATED`: then item 3. `CONFLICT` or
   `REJECTED`: run `native_gate.py --root . rebase`, repair here again, and
   integrate again -- the same card; a conflict spends no attempt, a rejected
   combined tree is a rejected attempt. Review is refused until the card is
   integrated (`PILOT_NOT_INTEGRATED`).
4. `OUTCOME_BUDGET_EXHAUSTED` (rejected attempts plus change requests of this
   outcome's family): `kanban_block kind=needs_input` naming the outcome.
   One limit, one count: the M2-published family budget (the brief's
   `budget`, key and limit from this card's contract) is shared by every card
   of the family and counts rejected candidates plus reviewer change
   requests. Changing cards, a restart or an accepted checkpoint never
   replenishes it; `decisions.max_attempts` is not a second ceiling here.
   VERIFICATION_PENDING: `kanban_block kind=needs_input`; after a restart,
   `native_gate.py --root . restore-pending` adopts the retained candidate.
5. `CHECKPOINT RECORDED; OUTCOME PENDING`: the commit is kept on this card
   and the outcome is **not** accepted. The line names each remaining reason
   (an open obligation, a check with its measured detail, a missing
   measurement). A checkpoint is not completion: do not complete or request
   review. Work on the reissued scope of this card. A runtime check
   (`parity:*`, package/startup) and the full test suite (`measure:tests`,
   which cannot run while the application does not compile) are never yours
   on a build, config or source card: the published plan gives them to M4,
   naming this outcome. A test the verification DID run and your candidate
   broke is still vetoed here.
6. Never leave uncommitted product edits behind: before `kanban_block`, run
   `python3 .hermes/kernel/native_gate.py --root . park` (it holds your candidate
   on this card and restores HEAD; K2 refuses the block otherwise). When the card
   resumes, `issue` reports `parked_candidate` and
   `native_gate.py --root . restore-parked` puts it back for re-verification.
7. `REPEATED_REFUSAL`: the same refusal three times in this run. Your candidate
   is parked for you; the only legal next step is `kanban_block kind=needs_input`
   naming the refusal (K2 refuses every other tool). Do not retry it.
8. `OWNER_RECOVERY` / `OWNER_REPAIR_PENDING`: the runtime failure belongs to an
   accepted outcome. Your candidate is held on this card and one repair is now
   this card's prerequisite. End the run with `kanban_block kind=dependency`.
   When the repair is done the dispatcher runs this card again: `issue`, then
   `native_gate.py --root . restore-held`, then run-verify and advance.

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
