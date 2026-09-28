# V25 improvement list: reusable migration repairs

Status: agreed direction, implementation pending. Recorded 2026-09-28.

Finish the agreed v24 package and its validation run first. This document adds no
v24 release or launch requirement. Use v24's final evidence to establish the
comparison baseline before implementing v25. Nothing here changes an existing
run, its pinned harness, task history, retry allowance or deadline.

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
proof that a new recipe executor improves the complete migration. V25 must
measure that improvement against the finished v24 baseline.

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

| ID | Priority | Improvement | Implementation choice |
|---|---|---|---|
| V25-1 | Required | Execute qualified known repairs | Small deterministic adapter inside the existing M3 flow; reuse eligible OpenRewrite components |
| V25-2 | Required, with V25-1 | Qualify each repair as a reusable capability | Before/after, no-change, repeatability, idempotence and behavioural tests |
| V25-3 | Required | Give workers resolved, task-specific context | Generate a compact attachment from existing evidence; borrow the Prethink pattern |
| V25-4 | Required | Report actual transformation and verification results | Extend existing records and reports, using data-table concepts |
| V25-5 | Later optimization | Reuse valid analysis/build metadata | Explicit cache identity and invalidation; not required for v25 |

### V25-1 — Executable, typed repairs

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

### V25-2 — Recipe qualification and repeatability

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

### V25-3 — Resolved context for each objective

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
explicit; measured searches/context use are compared with v24.

### V25-4 — Transformation results and honest cost accounting

Extend the v24 handoff/measurement work instead of creating another receipt or
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

### V25-5 — Analysis reuse, deferred

Consider reusing parsed/build metadata only after measuring where v25 spends time.
Cache keys must include source content, generated inputs, dependency/classpath
identities, JDK, active profiles, analysis options and producer version. Build-file
equality alone is insufficient. Missing or mismatched identity triggers recomputation.

Do not cache a past test/parity result as a fresh measurement, or remove the clean
M1/M2 repeatability qualification. This item is not a v25 launch prerequisite.

## Integration locations and execution order

Paths below are relative to the scaffold's `.hermes/` unless stated otherwise:

- `planning/catalogs/compat-mapping.json`: qualified recipes and applicability.
- `lib/planner/{source_requirements,compatibility_objectives,requirement_checks}.py`:
  requirement/check ownership and preserved planning/scope contracts.
- `lib/planner/decided_repairs.py` and
  `skills/migration/bootstrap-destination/scripts/_decided_repairs.py`: inspect and
  reuse applicable existing contracts; retain bootstrap versus M3 provenance.
- `skills/migration/fix-until-green/scripts/{brief.py,run-verify.sh,advance.py}`:
  attach context, invoke scoped execution and retain independent acceptance.
- Existing planner measurement/native outcome records and tests: extend for real
  results; rebase on the completed v24 implementation rather than duplicate it.
- Stage `SOLUTION-ARCHITECTURE.md`, affected skills and `BACKLOG.md`: document the
  selected executor, licensing inventory, evidence and limitations when implemented.

Sequence:

1. Finish v24 and retain its final plan, input pins, results and assistance record.
2. Select and pin eligible execution/test components; document the exact reuse.
3. Implement V25-1 with V25-2, then V25-3 and V25-4 in reviewable increments.
4. Compare both execution paths on identical frozen inputs and starting candidates.
   Keep logical M3 objectives, writable scopes, checks and retry allowances equal.
5. Qualify the combined package, then prepare the fresh v25 validation run through
   the existing release/launch process. Do not install into v24.

## V25 acceptance and claim boundaries

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
