---
name: paved-road-m4
description: >
  Pin only this on the M4 VERIFY card (K4 mints it when the work list
  reaches empty). Index for the closing phase: record what the legacy
  system does, measure the destination against it, generate the product
  acceptance tests from the source captures, run the fail-closed
  pre-verdict runner, compose the verdict from measured exit codes, lint
  it. The verdict is composed, never chosen: a non-empty failed_floors is
  a REFUSE. Never for M1, M2, M3, or story implementation.
license: Apache-2.0
compatibility: Linux seat; Hermes v0.20.5 Kanban; Python 3.11+
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - paved-road
    - m4
    category: paved-road
    kind: guidance
---
# Paved road: M4 VERIFY (oracles → parity → generate → pre-verdict → verdict → lint)

`steps.json` is the contract; `audit.json` is generated from it
(`python3 .hermes/lib/paved_road.py generate --steps steps.json --out audit.json`).
The reviewer runs `scripts/assert-paved-road-audit.py` over the official
Kanban log; silence, a missing KEEP artifact, or an unmatched `[exit 1]`
refuses.

M4 answers one question with evidence: does the destination do what the
source did. Everything here is measurement. Nothing here decides.

## Procedure (in order)

1. `skill_view capture-source-oracles` → read what the comparison means. The
   source was recorded at M1; M4 asks the destination the same questions.
   Reads are compared against `verification/source-oracles/<slug>.json`;
   writes through the scenario corpus, which restores the declared initial
   state, proves the destination is in it, replays the complete recorded
   request (body and headers included) and reads back every declared effect.
   An expected value comes only from the M1 capture. Never from the card
   body, never from what the destination happens to return, never from what
   you believe the legacy did, and never by re-capturing the source now —
   that would record its answer to a question the destination has already
   been asked. Do **not** drive the comparators by hand from here; step 2
   runs them.
2. `python3 .hermes/skills/paved-road/paved-road-m4/scripts/run-parity.py --root .`
   — **the** way to run parity. One command for the whole phase, in this
   order: every scenario the corpus declares in corpus order with the reset
   command, then every admitted entry point that has a captured http read
   oracle, then `compose-parity-receipt.py` last. It starts the packaged
   destination (`target/quarkus-app/quarkus-run.jar`) against the decided
   datasource and stops what it started; pass `--dest-url` when someone else
   is running one. KEEP `verification/parity/receipt.json` and
   `verification/parity/_run.json` (what ran, each child's exit code, the
   entry points nobody could compare and why).

   **Which `java` starts it.** The boot gate's own: `$JAVA_HOME_21/bin/java`,
   else `$JAVA_HOME/bin/java`, else `java` on PATH (the one function
   `fix-until-green/scripts/_java_runtime.py` that `verify-runtime.py` uses
   too); `--java <path>` overrides it. The binary, where it came from and its
   `java -version` line are recorded under `destination.java` in `_run.json`.
   Before anything is started, the class-file version of the application's
   own jar (`target/quarkus-app/app/*.jar`) is compared with that runtime, and
   an older runtime refuses with `REFUSE: PARITY_RUN the resolved java <path>
   (<version>) cannot run classes compiled for Java <n>` (dest v9: the first
   `java` on PATH was older than the build's, the artifact died with
   `UnsupportedClassVersionError`, and both phases read "the destination did
   not become ready"). Fix the environment or pass `--java`; do not repackage.

   There is no per-entry-point loop for you to run. v9's first M4 card is
   why: driven by hand, the composer ran first, `compare-runtime-parity.py`
   ran for none of the 34 admitted entry points, and 24 of them ended "no
   parity record" in a receipt that was composed anyway.

   **The security mode (ADR-014).** By default the runner measures the
   `disabled` mode: the corpus, captures, parity records and receipt that have
   always been at those paths. When the source was also captured with its
   security switch ON (`verification/source-oracles/scenarios-enabled/`), run
   it a second time against the **same packaged artifact**, restarted with the
   switch changed:

```bash
python3 .hermes/skills/paved-road/paved-road-m4/scripts/run-parity.py --root . \
  --security-mode enabled --from-decisions
```

   `--security-mode` scopes everything to that mode — its corpus, its
   captures, `verification/parity/scenarios-enabled/`,
   `verification/parity/receipt-enabled.json` and its own
   `verification/parity/_run-enabled.json` — and is passed to every comparator
   and to the composer, so nothing can be compared across modes.
   `--from-decisions` starts the destination with the switch `decisions.yaml`
   declares (`security.switch.key` = that mode's value) as a `-D` system
   property, recorded verbatim in the run record; `--dest-config KEY=VALUE`
   says it explicitly instead. Both run records carry the packaged artifact's
   digest, which is how "one artifact, restarted with the switch changed" is
   shown rather than asserted. KEEP both receipts and both run records.

   Two things the enabled run does **not** do, and says so: it does not
   re-compare the read oracles (those captures are not mode-scoped and were
   taken with the switch off — every entry point is named with that reason),
   and it does not invent an identity. The enabled-mode requests are made as
   the credential environment variables the corpus names and the capture used;
   the runner checks they are set before it starts anything and refuses naming
   the VARIABLE when one is absent. A `--dest-config` value that equals one of
   those credentials is refused by KEY: the run record is evidence.

   The runner exits 0 whenever every child ran and the receipt was composed.
   A receipt verdict of `FAIL` or `INCONCLUSIVE` is the measurement, not a
   runner failure: it is carried into the verdict at step 6. The runner exits
   1 only when a child could not run — no corpus, a destination that never
   became ready, a child that recorded no verdict, a composer that refused to
   compose, a declared credential the workspace does not hold, a switch
   `decisions.yaml` does not declare — and that is a `kanban_block`
   kind=needs_input, not a verdict.
3. `skill_view generate-product-tests` then
   `python3 .hermes/skills/gates/generate-product-tests/scripts/generate-product-tests.py --root .`
   — the HARNESS writes the product acceptance tests (ADR-015): one
   `@QuarkusTest` case per qualified scenario, asserting the status, canonical
   body, required headers and declared effects the SOURCE was recorded
   producing. You never author one of these tests and never weaken what one
   asserts; a scenario the source did not demonstrate is a named gap in the
   manifest, not a silent omission. KEEP
   `evidence/tests/generated-manifest.json`.

   The generated sources go to `src/parity-test/java` (+
   `src/parity-test/resources`), and nothing compiles them except the
   `m4-parity` profile in `pom.xml`, between its own comment markers. That is
   the phase rule made mechanical: under `src/test/java` every M3 verify would
   run these cases, a parity finding would enter the loop's own measure, and it
   would revert the step being verified for a reason that has nothing to do
   with it. Parity is measured once, here. That block is written by
   `bootstrap-destination.py` (ADR-015), so it is already in the committed pom
   when this runs and this producer finds it byte-identical and changes
   nothing.

   It runs **after** step 2 and **before** step 6: the rebuild step 6 drives
   (`-Pm4-parity`) is what executes the generated cases and leaves their
   surefire XML where the floors read it.
4. `python3 .hermes/skills/gates/generate-product-tests/scripts/commit-generated-tests.py --root .`
   — commit the generated suite. The files of step 3 land in a tree
   `assert-retrievable-tree` still requires to be committed against `HEAD`,
   and an untracked generated file is dirt to that gate. The gate is right and
   is not weakened: a verdict composed over a tree nobody can retrieve says
   nothing about what was measured. This step is what makes the tree
   retrievable again.

   It commits **only** what `evidence/tests/generated-manifest.json` lists,
   the manifest, and the generated roots — as
   `generate-product-tests <generate-product-tests@local>`, message
   `m4: generated product tests (corpus <sha12>, generator <version>)`. It
   refuses first when `generate-product-tests.py --check` does (committing an
   edited expectation would make the edit the harness's own), and it refuses
   any other change to `src/` or `pom.xml` — a worker's edit is committed by
   whoever made it, never swept into a harness commit. With nothing to commit
   it says so and exits 0.
5. `skill_view check-domain-parity` → run its evaluators. G-1 to G-4
   measured against the referent, each writing its own verdict. A REFUSE
   is a real outcome; the next step is to report it, not to soften it.
6. `bash .hermes/skills/gates/check-release-readiness/scripts/run-m4-pre-verdict.sh /projects/modernized`
   — the fail-closed runner: it first runs the generated parity suite
   (`mvn -Pm4-parity test`, no `clean`: that profile is the only thing that
   compiles `src/parity-test/java`), snapshots the test reports so a later
   rebuild cannot hide them, parses surefire, refuses a card body that pre-specifies a
   verdict, asserts the tree is retrievable, runs the pinned feeding
   gates so their receipts exist — `generate-product-tests --check` among
   them, so the verdict cites tests the harness still owns byte for byte,
   profile block included — then asserts that every pinned gate
   ran, that the G-4 claims are consistent, and that the fence was not
   evaded. KEEP `evidence/receipts/gates`. The feeding gates must run
   before the receipts are asserted, or the floor refuses on an empty
   directory.
7. `skill_view compose-m4-verdict` → author
   `evidence/verdicts/m4-verdict.json` from the measured exit codes and
   nothing else, with an explicit `failed_floors`. A non-empty
   `failed_floors` makes the verdict `REFUSE`. `idle: true` is a legal
   floor result; a floor you did not run is not. Then compose
   `evidence/verdicts/coverage-account.json` (`compose-coverage-account.py`)
   and carry its counts in the verdict's `coverage_account`: every source an
   accepted ADR retired gets a row naming its replacement scenario and its
   remaining gap.

   Then bind the verdict — with the tool, never from memory:

```bash
python3 .hermes/skills/gates/compose-m4-verdict/scripts/bind-m4-verdict.py --root .
```

   It writes `card_id` (this card, from `verification/loop/issued.json`),
   `receipt_sha256` (the admission receipt it was minted under) and
   `parity_receipt_sha256` (the digest of the parity receipt of step 2), and
   changes nothing a floor measured. The lint of step 8 refuses
   `M4_VERDICT_BINDING` without them, and `resume-after-m4.py` binds on the
   same three. v9's second M4 card is why: it composed an honest `REFUSE` and
   wrote no `card_id`, the card completed, and the resume had a measurement it
   could not attribute to any run.
8. `skill_view check-release-readiness` → lint what you just wrote: the
   verdict against its schema, the floor receipts, the claim tokens, and the
   coverage account against `decisions.yaml` and the parity receipt. This
   step can agree or refuse. It cannot change the verdict or the account.
9. Terminator: `kanban_request_review reviewer=reviewer`, then end the turn.
   That is the terminator for **every** outcome the phase can reach,
   `REFUSE` included: a REFUSE verdict is what M4 measured, so the card is
   complete work and goes to the reviewer. Never `kanban_complete` — K2
   refuses it here, and a worker that waits for it to be allowed waits
   forever (v9's card hung 30 minutes between the refusal and a body that
   never named the terminator). Never dest-dispatch M5. `kanban_block`
   kind=needs_input is only for a phase that could not measure: no
   destination to call, no database, no corpus, MaaS down — never for a
   verdict you dislike.

   The M4 worker's turn ends there. **The reviewer** (or the Operator), once
   the review audit above passes, runs the one command that decides what the
   verdict means for the run:

```bash
python3 .hermes/skills/migration/fix-until-green/scripts/resume-after-m4.py --root . --exec --operator WHO
```

   It refuses unless the verdict is this run's — its three bindings
   (`card_id` = the issued close card, `receipt_sha256` = the admission receipt
   that card was minted under, `parity_receipt_sha256` = the digest of the
   parity receipt on disk) all hold, the parity receipt is itself bound to the
   admission receipt that seals the tree, no candidate is retained for the
   close card, and the product tree is clean. Three outcomes:

   - `RESUMED` (exit 0): the parity floor's FAIL verdicts are mandatory
     obligations whose loci are files of this tree. The close card goes on the
     loop record, the work list is rebuilt, admission is re-sealed and K4
     mints the next M3 card. The loop is running again; the reviewer has
     nothing further to do on this card.
   - `BLOCKED` (exit 2): every failed floor is a decision, not a card
     (`check-product-tests` / `assert-surefire-results` → ADR-015, a harness
     capability; an entry point whose read-back answered 401/403 → ADR-014,
     one bounded Operator step). Nothing is minted, the close card stays
     issued, and `verification/loop/release-blockers.json` names each floor
     with the ADR and the seat that owns it. That file is the Operator's queue.
   - `REFUSE: LOOP_RESUME` (exit 1): the verdict is not this run's, a worker
     still holds the tree, or this verdict was already resumed. Nothing changed.

   Both classes at once is the normal case (v9's first M4 verdict): the parity
   card is minted **and** the blockers file is written, one printed line per
   class. Do not re-run M4 to change a verdict — the resume is what consumes it.

## What refuses, and why that is the point

- A verdict that names a floor you did not run.
- A verdict that names no card, another card, another admission receipt, or a
  parity receipt digest this tree does not hold: a measurement nobody can
  attribute to a run is not a result.
- A retirement with no row in the coverage account, a claimed replacement
  whose scenario did not pass, or a verdict reporting fewer gaps than the
  account holds. A disclosed gap does not refuse; a hidden one does.
- A verdict written before the pre-verdict runner (the runner is what
  makes the receipts the verdict cites exist).
- An expected runtime value that is not in an oracle.
- A generated product test whose bytes moved, an unlisted file in a generated
  package, or a `pom.xml` whose `m4-parity` block is edited or gone: the
  harness owns those files, and a suite that nothing compiles is a suite that
  never ran.
- A parity phase with no `verification/parity/_run.json`: the receipt alone
  cannot say which comparisons ran, so a receipt composed before them reads
  exactly like one composed after them.
- A card body that already contains a verdict token: the runner refuses
  it, because a pre-specified verdict is not a measurement.
- `PROVISIONAL_ACCEPT` without a retrievable tree: uncommitted `src/` or
  `pom.xml` means there is nothing to ship.

## Operator

A REFUSE verdict is the run's honest result, not a failure of the loop.
`resume-after-m4.py` (step 8) is what consumes it: the floors a card can
repair become the next M3 card, and the floors a decision owns land in
`verification/loop/release-blockers.json` with their ADR and seat. The
Operator reads that file, removes the cause (a harness capability under
ADR-015, a bounded security step under ADR-014, an ADR in `decisions.yaml`),
and then either resumes again or re-opens earlier work with
`fix-until-green/scripts/rewind.py`. Do not re-run M4 hoping for a different
answer: the same measurement on the same tree returns the same verdict.

## Self-test

`python3 scripts/selftest.py` (golden only, never on a card): steps.json ↔
audit.json sync, the kind rules (oracles first, the parity runner then the
pre-verdict runner as the only native steps, the generator between them, the pre-verdict runner before
the producer, `compose-m4-verdict` the only producer, lint after it), the
fixture PASS/REFUSE set, and the coverage lint.
`python3 scripts/run-parity.test.py` exercises the batch runner end to end
against a stub destination: every scenario in corpus order, every captured
read oracle compared, the uncomparable entry points named with their reason,
the receipt composed last, a FAIL receipt exiting 0, a missing corpus
exiting 1; and the security mode (ADR-014) — an enabled-mode run reads and
writes only that mode's evidence, tells every child the mode, skips the read
oracles with the reason, asks the destination as the identity the corpus
names, leaves the disabled mode's own run record untouched and records the
same artifact digest as it, while a missing credential refuses by NAME and a
`--dest-config` carrying one refuses by KEY.
