# V26 improvement list: reusable migration repairs

Status: v26 scope decided 2026-09-29 (architect). Recorded 2026-09-28; scope and
evidence status updated 2026-09-29. Implementation status below is source-level:
unit, fixture and model-free reproduction evidence. It is not live-run proof.

**v26 is the reliability validation release.** Its objective is M1→M5 without
harness overlays or Operator rescues, with every acceptance gate preserved. It
carries the workflow-reliability corrections (V26-6, the targeted part of V26-3,
and V26-4 reporting from existing records). Deterministic recipe execution
(V26-1 with V26-2) remains agreed work for the subsequent feature package, so a
reliability improvement is not confused with one introduced by a new
transformation executor.

**v25 disposition.** The validation run `spring-petclinic-rest-legacy-v25` (the
v24 package) is preserved as an **assisted diagnostic run**. It stopped at 21 of
36 cards after two recorded harness rebases and four unblocks. Its measured tasks
are a partial baseline for the stages it reached (M1, M2 and part of M3). It is
not an end-to-end baseline, and no saving can be claimed for M3 behaviour cards,
M4 or M5, which it never reached. Nothing here changes that run, its pinned
harness, task history, retry allowance or deadline.

## v26 scope and evidence status

| ID | v26 scope | Status (2026-09-29) |
|---|---|---|
| V26-6 | **Included**: the known investigation-loop, retry, rework and guard defects | Implemented for the defects listed under V26-6 below; item 1 (Servlet redirect guidance) and parts of items 2–3 are open, as marked there |
| V26-3 | **Included, targeted only**: complete instructions, bounded selectors, owned obligations, saved diagnostics, actionable retry context | Implemented as listed under V26-6 items 2–4; the broader resolved-context attachment and classpath/API lookup are deferred |
| V26-4 | **Included, from existing records only**: actual verification, retries, assistance, requests, tokens, elapsed time | Reported at the close of the v26 run from the native run records, execution ledger and request ledger; no new receipt. Recipe-specific reporting ships with the executor |
| V26-1, V26-2 | **Subsequent feature package** (paired) | Not started; design and mandatory qualification below are unchanged |
| V26-5 | **Deferred** pending measurements | Not started |

No deferred item is promised for a particular numbered run.

## Objective and current baseline

Make established migration knowledge executable so the model does not have to
rediscover the same repair on every run. Preserve deterministic M1/M2 planning,
bounded compatibility objectives, native Hermes lifecycle and independent
acceptance checks.

Compatibility-objective composition already borrows declarative composition,
applicability checks, idempotence and table-style reporting from
OpenRewrite/Moderne. Several catalog repairs still use `implementation.kind:
agent-bounded`: the rule describes the edit, but the worker must implement it.
The existing decided-repairs producer also applies some mechanical repairs at
bootstrap. Extend these contracts rather than add another planner or scheduler.

The objective-sized cards have demonstrated useful progress. That is not yet
proof that a new recipe executor improves the complete migration. The feature
package must measure that improvement against a completed reliability baseline
(v26, if it completes), not against v25's partial one.

## Reuse and licensing decision

The project's licensing boundary remains unchanged:

- Open-source components are eligible for direct adoption under their applicable
  licenses and the project's licensing/distribution requirements. Reuse a suitable
  maintained component rather than recreate it merely because it is third-party.
  Record the exact artifact/version, license and required notices with its pin.
- Do not introduce proprietary components or treat source-available software as
  open source. Check individual artifacts; one vendor's catalog can mix licenses.
- For useful proprietary or restricted functionality, avoid the dependency or
  independently implement similar behaviour from public documentation, observable
  contracts and our requirements. Here, "clone similar logic" means our own
  implementation; it does not mean copying restricted source, tests or assets,
  removing notices, or assuming a rewrite changes the original license.
- Keep provenance clear: identify directly reused components separately from
  independently implemented patterns and project-specific migration rules.

Candidate components are OpenRewrite's open-source Java/XML transformation
infrastructure, Maven integration and recipe-testing support. Verify the licenses
of the exact selected versions and transitive dependencies before including them.
The core and original Java/XML libraries are documented as Apache licensed;
licensing is not uniform across all recipe bundles. [R1]

Do not import a broad Spring-to-Quarkus composite as the default migration. For
example, the documented Data JPA recipe selects Hibernate ORM Panache, whereas
our selected architecture uses Spring compatibility where appropriate. [R6]
Reuse eligible building blocks and author the transformations our contract needs.

When implementation begins, align the SAD's existing blanket prohibition on
third-party analysis libraries with the narrowly selected execution component.
Keep M1/M2 evidence authority, the licensing boundary and the prohibition on
OpenRewrite acting as the planner intact. This document changes no runtime policy.

## Prioritized improvements

| ID | Scope | Improvement | Implementation choice |
|---|---|---|---|
| V26-1 | Subsequent feature package | Execute qualified known repairs | Small deterministic adapter inside the existing M3 flow; reuse eligible OpenRewrite components |
| V26-2 | Subsequent feature package, with V26-1 | Qualify each repair as a reusable capability | Before/after, no-change, repeatability, idempotence and behavioural tests |
| V26-3 | v26 (targeted part); remainder deferred | Give workers resolved, task-specific context | v26: complete instructions, bounded selectors, owned obligations, saved diagnostics, retry context. Later: the compact attachment (Prethink pattern) and classpath/API lookup |
| V26-4 | v26 (existing records); recipe reporting with the executor | Report actual transformation and verification results | Extend existing records and reports, using data-table concepts |
| V26-5 | Deferred pending measurements | Reuse valid analysis/build metadata | Explicit cache identity and invalidation |
| V26-6 | v26 | Prevent repeated investigation and make native retries actionable | Bounded recovery context and saved verification diagnostics; retain the existing loop guard |

### V26-1 — Executable, typed repairs

Use the existing recipe catalog as the selection contract. Pin the executor,
recipe version and options per new run. M2 determines applicability from evidence;
issuance rechecks it against the current candidate. No model chooses architecture
or expands the repair's permitted files.

The flow remains: issued M3 objective → qualified transformation → existing
verification and advance → native review. A deterministic edit does not complete
a card or prove an outcome. It receives the same checks as an agent-authored edit.

Start with two transformations:

1. **Selected repository CDI exposure.** Apply the existing resolved bean-scope
   and exposure rules together. Preserve the selected source profile, interfaces
   and method behaviour. Do not synthesize repository bodies or assume one
   annotation shape fits every repository.
2. **Handler URI parameter translation.** Apply the catalog's resolved handler
   parameter action and associated builder-use changes together. Preserve source
   path templates, argument order and null handling; do not substitute a guessed
   entity identifier.

Use typed references, not simple-name matching or regular-expression rewriting.
Collect cross-file facts before generating or editing, following the documented
scan → generate → edit pattern. Any dependency on a preceding transformation must
be explicit; do not assume a scan sees another recipe's later edits. [R2, R3]

Execution contract:

- Stage edits against the identified candidate and inspect the complete diff
  before applying it. Unexpected paths or exceeded bounds reject the patch.
- Missing required type/classpath facts or unsupported shapes yield an explicit
  unresolved result without partial edits. A broken application build is not, by
  itself, proof that all type attribution is unavailable; qualify required symbols.
- Distinguish applied, already in the required form, not applicable, unresolved
  and failed. A no-op alone never establishes that the requirement is satisfied.
- Unresolved work returns to the existing bounded agent path or prerequisite
  handling. Do not silently drop it, grant extra attempts or create a new task loop.
- Executor tooling belongs to the harness, not the migrated application's runtime
  dependencies. Preserve the pinned Red Hat Quarkus platform and source protection.

Exit: both transformations produce repeatable, scoped patches; unsupported inputs
remain accounted for; the real verification/advance path accepts correct candidates
and refuses the known bad-CDI and handler-parameter forms.

### V26-2 — Recipe qualification and repeatability

Use OpenRewrite's before/after and unchanged-source testing infrastructure where
adopted. Borrow the same testing contract for our own transformations. [R4]

Each recipe must demonstrate:

- Same source, classpath, profile, options and tool pins → identical patch.
- A second application makes no further change; an already-correct input is kept.
- Unrelated same-named types, reordered files and renamed application/package
  fixtures do not cause unintended changes.
- Missing types, unsupported source shapes and out-of-scope changes refuse clearly.
- Generated files are changed through their owning generator/configuration when
  required by the existing contract, not patched as disposable output.
- A negative control reproduces each targeted defect and is rejected; the repair
  passes the same independent checks. Include partial-edit/interruption recovery.

For the initial pair, demonstrate package augmentation and repository access for
CDI, plus real HTTP handler/Location behaviour for the URI translation. Source
captures remain the behavioural oracle. Do not replace runtime evidence with
before/after text equality or relabel a source qualification as PASS.

### V26-3 — Resolved context for each objective

Borrow Prethink's pattern of exported facts with progressive discovery, using our
own producers and existing native attachments. Its documented approach makes
structured context discoverable by agents; adopting its proprietary discovery
components is not required. [R5]

Build a concise context attachment containing:

- Active profile, selected implementation and evidence for that selection.
- Generated versus handwritten types, generation command and actual source roots.
- Relevant interfaces, callers, method signatures and qualified symbols.
- The chosen recipe, its prerequisites and unsupported/unknown facts.
- Immediate acceptance checks, named deferred obligations and available fixtures.

Bind frozen source facts and current destination facts separately. Refresh
destination-derived facts when their inputs change. Preserve provenance for every
assertion and label inferences/unknowns; do not turn name-based guesses into facts.
Keep a short index in the brief and detailed evidence in attachments, avoiding
repeated injection of the whole repository into model context.

Exit: the generated DTO and inactive-profile failure cases are answered from the
attachment; wrong-tree facts are rejected/refreshed; missing information remains
explicit; measured searches/context use are compared with a completed baseline.

Scope: v26 ships only the targeted part (the V26-6 items 2–4 context:
complete instructions, bounded selectors, owned obligations, saved diagnostics,
retry context). The attachment above and a classpath/API lookup are deferred
with the feature package.

### V26-4 — Transformation results and honest cost accounting

Extend the v24 package's handoff/measurement work, validated in v25, instead of creating another receipt or
acceptance authority. OpenRewrite data tables provide a useful reporting pattern
for matches, changes, errors and execution statistics. [R7]

Record task/objective and recipe identity, candidate before/after, matched symbols,
changed/created/deleted files, applicability result, unresolved reasons, actual
verification execution and outcome, and elapsed time. Include executor/classpath
pins needed to reproduce the edit.

Keep causal edits separate from an already-satisfied witness. Record model requests
and reported token usage when available; report unknown otherwise. Include parsing,
startup, verification and review overhead in total cost. Do not substitute a
recipe's estimated manual effort for measured savings.

Exit: each accepted repair is traceable to its actual edit and checks; a no-op,
missing result, skipped test or unrelated accepted commit cannot supply false credit.

### V26-5 — Analysis reuse, deferred

Consider reusing parsed/build metadata only after measuring where v26 spends time.
Cache keys must include source content, generated inputs, dependency/classpath
identities, JDK, active profiles, analysis options and producer version. Build-file
equality alone is insufficient. Missing or mismatched identity triggers recomputation.

Do not cache a past test/parity result as a fresh measurement, or remove the clean
M1/M2 repeatability qualification. This item is not a v26 launch prerequisite.

### V26-6 — Repair guidance and recovery from tool loops

Observed in v25: `t_e5f21725` (RootRestController compile), native run 17,
halted with `identical_call_streak_halt`, count 5, arguments hash
`5657c86af96934f0`. The official log and execution ledger show five identical
searches for `import jakarta.ws.rs`, each exiting 0. The guard detected a real
loop. The brief supplied an action for CrossOrigin but only diagnostics for the
missing Servlet response type. Native retry run 18 subsequently tried an
unavailable response class and repeatedly compiled through different output
filters. These observations identify guidance and recovery gaps; they do not
prove the model's internal cause or a task-partition defect.

Follow-up: run 18 also halted at five identical calls (arguments hash
`1c388ffd006371a0`), and native recovery ended at `gave_up`, two consecutive
failures. Its repeated command piped `mvn compile` into `grep`, then printed
`echo "EXIT: $?"`. That reports the filter's status rather than Maven's;
the final echo also makes the terminal call exit 0. The execution ledger confirms
those terminal exits, not successful compilation. No acceptance bypass was
established. A third unchanged retry is not a recovery strategy.

The same failure class also occurred on the independent Profile card
`t_dbde15ae`: run 19 repeated a compound search/count of `spring-data-jpa` five
times (arguments hash `87ba5a76f5b7da3e`) and halted. Native retry run 20 then
removed the Profile annotations/imports in its 15-file scope, cleared 30 owned
diagnostics (233 to 203 total), and was accepted at `14bb4e7871c9`; reviewer run
21 completed the card. This is a successful native recovery with a preceding
worker failure, not a first-run success. Redirect-specific guidance cannot
explain or fix every loop. The brief already forbids extra Maven runs outside
run-verify.sh, so adding that sentence again is not a sufficient correction.

Read-only session investigation subsequently confirmed a brief-ownership defect:
the Profile contract owns `worklist-absent` and `measure:compile`, but its digest
labels repository implementation/CDI checks as due now. `planned_requirements`
selects requirements by intersecting file paths; `brief_digest` labels checks by
prefix without consulting the issued outcome. Its full brief is reported as
137,237 characters (the worker received a digest, then selected sections).
Shared files must not silently assign another outcome's immediate acceptance.

All three failed sessions recorded the actual results and repeat warnings; no
compression was observed. Root's short results stayed in full, while Profile's
reference stubs pointed to a still-present original. Lost results are therefore
not the demonstrated explanation here. The same model completed Profile on its
native retry. Guidance defects and model failure to change course both need
qualification; adding another warning alone is insufficient. Selected evidence
and the bounded comparison design are in
`tmp/v25-loop-investigation/ANALYSIS.md` and `evidence.json` (local, not shipped).

DAO follow-up (`t_90e674d6`, runs 22/23): run 22 is another exact-repeat loop;
run 23 halts on growing grep windows even as new diagnostic IDs appear. The
installed near-duplicate guard calls output progress only when more than half
its lines are new. An installed-runtime, model-free reproduction halts at page
13 despite a different diagnostic ID on every page; the identical-read control
still halts at five. Its “no new output” claim is therefore not reliable. The
DAO brief also mislabels an active composite objective as no longer open by
looking for its synthetic ID among raw clusters, and supplies a reported 285,626
character full brief without a compact per-action query view. Both runs tried
inline JSON selection, were refused, then reconstructed it with shell filters.
Preserve the inline-Python restriction; make the existing brief usable through
bounded selectors. The evidence and reproduction are in the same local packet.

Implement five bounded changes:

1. **Qualified Servlet response/redirect guidance.** Extend the existing catalog
   and brief with an action for the supported source shape and selected target
   stack. Verify the public API against the pinned platform and preserve the
   source's redirect status, Location and context path. Do not guess an internal
   runtime class or widen the card's write set. Missing prerequisites remain
   explicit. This is a catalog/brief repair; it does not require a third
   deterministic transformation in V26-1.
2. **Useful native retry context.** Trace the existing retry handoff first. Add
   only missing information: task/run identity, the repeated command and result
   (sanitized and bounded), the last completed step, and whether edits or a
   verified candidate remain. Reuse native run metadata and brief attachments.
   Preserve the original stop, retry accounting and same-card lifecycle; add no
   rescue watcher, scheduler or extra retry allowance. An unchanged search
   result is evidence to use, not a reason to repeat the search.
3. **Inspect saved diagnostics.** Make the verified candidate's diagnostic paths
   and relevant errors easy to find in the brief. Read/filter those results
   without rebuilding. Re-verify when inputs change, evidence is missing or
   stale, or an actual transient failure justifies a retry. Never substitute
   an old successful verification for the current candidate. Preserve the
   producer's real exit code alongside the full diagnostic artifact; a filter,
   trailing echo or other successful wrapper must not be reported as a
   successful build. Prefer the existing verification producer over ad hoc
   shell pipelines.
4. **Make the brief agree with the issued contract.** Derive immediate checks
   from the owning outcome and issued scope, not path intersection or check-name
   prefixes. Lead with the qualified next action. Label other requirements on
   the same files as context with their owners and due gates. Retain all
   obligations, global regression checks and existing gates; an inconsistent
   ownership record must be reported, not silently resolved by dropping checks.
   Resolve selected-profile guidance and make refusal advice name genuinely
   permitted diagnostic paths. Do not widen filesystem permissions to compensate
   for incorrect advice. Supply exact file/symbol selection and stable bounded
   paging in the existing brief interface, with explicit totals and next page.
   Determine composite-objective liveness from constituent/item identities,
   not the absence of its synthetic ID from raw diagnostic clusters.
5. **Correct near-duplicate progress classification.** In runtime patch 0014,
   low novelty is not zero novelty. New diagnostic facts inside repeated JSON
   structure must not trigger a hard no-progress halt. Keep similarity warnings
   for inefficient investigation, and hard stops for established unchanged
   evidence. Account for the output actually delivered through previews/spills.
   Preserve the five-identical-result halt and genuine repeated-output cycles.
   This requires runtime qualification, a new baked image and pins alongside
   the golden; it is not a scaffold-only fix.

**v26 implementation status (2026-09-29).** The evidence is source-level (tests
and model-free reproductions) unless marked *live*. "Live" means observed on the
assisted v25 run after a harness rebase; that is directional, not a reliability
rate.

| Item | Status | Commits (release/v26) | Evidence |
|---|---|---|---|
| 1. Servlet response/redirect guidance | **Open**, not in v26 | — | none; v25's RootRestController card completed after native retries without it |
| 2. Useful native retry context | **Partial** | 0b130728, 2091e0f6, 9dad295b | retry state names the diagnostics the rejected patch introduced in the write set, files the revert deleted and the refusals (tests; *live*: the Root, DAO and controller retries on v25 reached review); a REVERTED no longer locks the worker out of reads and edits, bound to the latest invocation, run and issued unit (K2 selftest, 10 regressions). **Open:** the repeated command and result and the last completed step in the native retry handoff |
| 3. Inspect saved diagnostics | **Partial** | bb8e7cfd | `brief.py --file/--item/--symbol` answer from the measured work list, bounded, naming the measured candidate and whether the tree still is it (tests). **Open:** preserving the producer exit code through a worker's own filter or trailing echo |
| 4. Brief agrees with the issued contract | **Done** | bb8e7cfd, 0b130728, 507af709 | checks from the owning outcome; other owners' requirements marked not yours; objective liveness from constituents; every obligation listed; required architecture printed whole (tests) |
| 5. Near-duplicate progress classification | **Done** (runtime 0015) | 61d6b0ab | any new line is progress; printed identifiers, digests and timestamps are content; only the runtime's own notices are excluded; the page-13 reproduction and 25 distinct artifact pages no longer halt; identical calls and unchanged loops still halt (45 guard tests) |

The open parts above are implemented after v26 on `next/after-v26`
(source-level, not in the v26 golden): item 1 in 463dbd0a, the retry handoff
of item 2 in 657be426, the verifier exit record of item 3 in c02e319b, and V26-4
reporting from existing records in c3b3b80d. BACKLOG.md lists the rest of that
package.

Related defects found in v25 and fixed for v26, outside the five items:

- **Unchanged rework after a procedural change request** (01c68fde, 337af57f):
  - It is not judged or charged.
  - On a tree other cards have moved, it is re-judged on the current tree.
  - A rejection replays only on its own unit.
  - Evidence: native harness tests. *Live*, the unchanged-tree path on the ORM card.
- **Required skills preloaded on every run** (f0fdf159, 969d9434, runtime 0016):
  - This covers initial, retry and rework runs.
  - The native finalizer records what actually loaded.
  - An incomplete preload stops work, and the audit credits only a complete native preload of the current `SKILL.md`.
  - Evidence: runtime tests, the audit and hook tests, and an end-to-end check with the real finalizer.
- **Paved-road audit reads a required flag in a compound command** (07d2cca3).
  - Evidence: *live*, M1 of v25.

The model-profile screen of 2026-09-29 (`tmp/v25-run/profile-screen/`) is
inconclusive and is not a v26 requirement. v26 keeps the non-thinking profile:
temperature 0.7, top_p 0.8, top_k 20, min_p 0, presence_penalty 1.5,
repetition_penalty 1.0. Slow investigation that yields genuinely new facts is
recorded as an efficiency observation within the existing budgets and deadline.
No per-card cost bound is claimed.

Keep the five-repeat hard stop. Do not broadly exempt terminal commands or
evade detection by changing argument formatting. Prefer scaffold changes using
existing runtime records; if required context is unavailable there, identify the
small runtime change and its image qualification before publication.

Acceptance:

- A fixture with no local target-framework examples receives the qualified
  action; compilation and real HTTP redirect checks pass after the repair.
- An unsupported shape produces a named missing-capability result without
  guessed imports or expanded permissions.
- A native retry receives the exact prior stop and candidate state. Missing
  results remain unknown; changed files invalidate old diagnostics.
- A failing compiler behind a successful filter/trailing echo remains a failed
  compilation in diagnostics and handoff. Inspecting the saved output does not
  launch another build. Exhausted native retries stay exhausted until an
  explicitly recorded assisted recovery; no automatic third try is introduced.
- Tests retain the identical-call halt and distinguish changed commands/results
  and legitimate process polling from an unchanged search loop.
- One bounded worker replay exercises the no-local-example case through edit,
  verification and native review, or an honest capability block. Report repeated
  searches and redundant compilations; fixture tests alone do not establish that
  model looping is eliminated.
- Include the Profile case as an independent recovery fixture. Compare the
  failed and successful runs' actual brief, model-visible tool results and retry
  context before attributing the loop to missing guidance, result compression
  or model behaviour. Test that an available, correct action can lead to an edit
  rather than repeated discovery. Report worker halts separately from rejected
  candidates and semantic repair-budget spend, including on eventually done cards.
- A Profile card sharing repository paths does not advertise another owner's
  checks as due now; the actual repository owner retains them. The corrected
  brief conserves obligations, scope and budgets. Compare current and corrected
  inputs on both cases with the same model/runtime before claiming fewer loops;
  use a small declared request/token budget, not another full migration. A
  successful single continuation is directional evidence, not a reliability rate.
- The DAO fixture keeps its composite objective open while constituent items
  remain, and its compact selectors expose all 97 obligations without shell
  reconstruction, omission or extra scope. Test new IDs in repetitive JSON,
  overlapping pages, numeric file names and previously truncated output against
  the near-duplicate guard. These must not be called unchanged-output loops;
  truly repeated outputs must still stop. Include the installed-runtime paging
  counterexample and distinguish controller tests from a real worker replay.

Ship this with the next golden for new runs. Do not overlay it onto the active
v25 run or change its task state as part of this improvement.

## Integration locations and execution order

Paths below are relative to the scaffold's `.hermes/` unless stated otherwise:

- `planning/catalogs/compat-mapping.json`: qualified recipes and applicability.
- `lib/planner/{source_requirements,compatibility_objectives,requirement_checks}.py`:
  requirement/check ownership and preserved planning/scope contracts.
- `lib/planner/decided_repairs.py` and
  `skills/migration/bootstrap-destination/scripts/_decided_repairs.py`: inspect and
  reuse applicable existing contracts; retain bootstrap versus M3 provenance.
- `skills/migration/fix-until-green/scripts/{brief.py,run-verify.sh,advance.py}`:
  attach context, expose saved diagnostics, invoke scoped execution and retain
  independent acceptance; include the V26-6 recovery guidance in the existing
  migration and paved-road-m3 skills.
- Existing planner measurement/native outcome records and tests: extend for real
  results; rebase on the v24 package validated in v25 rather than duplicate it.
- Stage `SOLUTION-ARCHITECTURE.md`, affected skills and `BACKLOG.md`: document the
  selected executor, licensing inventory, evidence and limitations when implemented.

Sequence:

1. v25 is preserved as an assisted diagnostic run (21/36 cards): its plan, input
   pins, results and assistance record are retained as a partial baseline.
2. **v26 (reliability):** ship V26-6, the targeted V26-3 context and V26-4
   reporting from existing records. Run M1→M5 on a fresh run with no overlays or
   Operator rescues. A blocked or INCONCLUSIVE outcome stays such.
3. **Subsequent feature package:** select and pin eligible execution/test
   components and document the exact reuse. Implement V26-1 with V26-2 and the
   recipe-specific V26-4 reporting in reviewable increments. V26-5 remains
   deferred pending measurements.
4. Compare both execution paths on identical frozen inputs and starting candidates.
   Keep logical M3 objectives, writable scopes, checks and retry allowances equal.
5. Qualify the feature package, then prepare its validation run through the
   existing release/launch process. Never install into a running run.

## V26 acceptance and claim boundaries

The v26 reliability run reports from existing records: completed outcomes, worker
halts (including false halts), repeated investigation, retry and rework
correctness, verified behaviour, request/token/time cost and assisted
interventions. Unknown measurements stay unknown. The comparison below applies to
the subsequent feature package.

The bounded comparison must show identical logical M1/M2 plans, conserved
obligations/budgets, no scope expansion, repeatable patches and preserved behaviour.
Measure first-pass success, repeated edits/searches, blocked acceptance, verification
count/time, model requests/tokens, total elapsed time and assisted interventions.
Separate provider/runtime failures from transformation failures. Fewer cards is
not a success criterion, and a changed card partition would confound this comparison.

Run the initial recipes through real verification and native review. Report exactly
where a fixture, scratch replay or live run supplied evidence. Require an observable
reduction in agent work on the targeted repairs without a correctness regression;
do not invent a percentage target before measuring the baseline. Report executor
overhead and regressions even if model usage falls.

Full migration, M4 parity and M5 delivery remain governed by their existing gates.
Recipe qualification does not establish end-to-end migration success. No additional
isolation campaign, sidecar, scheduler, parallel M3 execution, whole-platform clone
or broad task repartitioning is part of this package.

## References

These are design/component references, not proof of performance in this project.
Verify selected release licenses and APIs when implementation begins.

- [R1 — OpenRewrite licensing](https://docs.openrewrite.org/licensing/openrewrite-licensing)
- [R2 — Lossless Semantic Trees](https://docs.openrewrite.org/concepts-and-explanations/lossless-semantic-trees)
- [R3 — Recipes and scanning phases](https://docs.openrewrite.org/concepts-and-explanations/recipes)
- [R4 — Recipe testing](https://docs.openrewrite.org/authoring-recipes/recipe-testing)
- [R5 — Moderne Prethink](https://docs.moderne.io/user-documentation/agent-tools/prethink/)
- [R6 — Spring Boot Data JPA to Quarkus Panache recipe](https://docs.openrewrite.org/recipes/quarkus/spring/springbootdatajpatoquarkus)
- [R7 — Recipe data tables](https://docs.openrewrite.org/authoring-recipes/data-tables)
