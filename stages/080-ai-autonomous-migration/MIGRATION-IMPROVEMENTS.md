# Migration improvements: a repeatable path from source to release

Updated 2026-09-30. This is the active improvement roadmap, independent of run
numbers. It replaces V26-IMPROVEMENTS.md; IDs V26-1 through V26-6 remain stable
for traceability. P-1 retains its separately approved two-card pilot scope.

**Architectural assessment:** we have improved individual repairs and planning,
but have not qualified a repeatable migration procedure through release. Too much
engineering and reporting has centred on getting the next card through its gates.
Known application gaps and the end-to-end completion path have received too little
attention. More local controls alone will not correct that imbalance.

**Priority:** organize the existing implementation around a supported migration
program with explicit application milestones (M-1 through M-7 below). Close the
known lifecycle defects, capture all known PetClinic repair requirements, and
qualify that program before buying another full validation run. Implement the
bounded typed-repair package within this program, not as a separate modernization
project. Keep native review, scope limits, conserved obligations and budgets.
This is an architecture and implementation roadmap, not a live recovery command,
an authorization to launch, or an additional runtime approval mechanism.

## Evidence basis and status

Assessment cutoff: 2026-09-30. Current source inspection uses `next/after-v28`
at `d003445c68771072989c3a5b5dd830b27dc75a43`, in the separate implementation
checkout. The main checkout may be older. The earlier architectural counterexample
tests ran against `0dd677ba`; this assessment does not claim a fresh test run of
`d003445c`. Uncommitted work is not counted as implemented.

Publication and installation are separate from implementation. The saved v29
record identifies published golden `ac8945a2` from main `de6c7ba6`, followed by
assisted harness overlays. I-11 records destination `8b73b8b5` after overlay 8;
the subsequent `d003445c` correction was authored but not yet installed at that
record's approximately 07:20Z cutoff. Calls to these source commits “golden” in
the intervention narrative are not proof of scaffold publication.
Do not describe that destination as an unchanged execution of the published golden.

Evidence used here is source inspection, saved regression results, independently
counted saved plan data, and official vendor documentation. There was no fresh
cluster inspection, model experiment or application execution for this assessment.
Local packets:

- `tmp/model-loop-root-cause-20260929/REPORT.md`: prompt delivery defects,
  corrected qualification claim and the four-request negative comparison.
- `tmp/v29-watch/INTERVENTIONS.md`, through I-11's continuation (about
  2026-09-30 07:20Z): assistance, repository recursion, lifecycle blockers and
  the false-green remeasurement.
- `tmp/v29-watch/v29-plan.r1.json`: saved initial graph, requirements, immediate
  and later checks, and unresolved verification responsibilities.
- `tmp/v29-watch/architect-review/{reproduce.py,results.json}`: three reproduced
  defects in the `0dd677ba` recovery implementation.
- `tmp/v26-corrections/`: preserved v26 state and correction evidence.

Local packets are ignored by Git. Release evidence must preserve the relevant
identities and results through the existing release process, not depend on a
local path as its only proof.
The watch folder is not a complete export of official logs and native state.
Its intervention narrative is saved reported evidence; its untimestamped
`state.txt` is not a fresh live-board observation.

| ID | Implementation (package `feat/migration-reliability-m1-m7`) | Publication / installation | Demonstrated evidence and remaining work |
|---|---|---|---|
| M-1 — supported migration and finish line | `lib/completion_map.py` (24b7f864): contract, milestones, every ship-blocking verification gap with owner, prerequisites and exit; ADR-025 scope limitation | Not published | v29 r1 recomputed: 80 requirements, 7 groups, 12 entry points, all owned by source-capture work. Source Git revision is not recorded by M1 (content digest only). |
| M-2 — executable milestones | check-schedule/v1 (2e8d99d7), executed by the native lifecycle at issue and at acceptance (9ca09fb6, 17d90c22); runtime findings a declared recipe discharges are its objective's (e55407c3) | Not published | Exit fixtures pass through the lifecycle; a scheduled row's own `after` orders issue only; crash between acceptance and schedule measurement is picked up at the next issue or M4. |
| M-3 — rehearse risky behavior | Reference qualification on PostgreSQL 16 against the frozen source oracle (91109348..a3dfc05c), rehearsal (28f39ec0, 03874abf) | Not published | Controls pass. v28 candidate: 19 of 47 comparisons match. Rehearsal (one patch per catalog repair): 47 of 47 (40 disabled-mode, 7 enabled-mode), 4 of them through ADR-025's declared equivalences. A manually prepared application result, not autonomous completion. CI/CD and deployed-route checks are live-only. |
| M-4 — reusable capability | Coverage table SAD §7.3; known guidance added (960a767c, c3067478, 962931d9); ADR-025 | Not published | Every known pattern is a qualified recipe, a tested bounded procedure or an ADR-025 ruling; no known gap without guidance. |
| M-5 — state ownership and evidence | 9fcd639b..2c2973cc | Not published | Architect counterexamples corrected; lifecycle replay passes; not exercised on a live board. |
| M-6 — end-to-end headline | run-report headline through M5 (ad5d059c) | Not published | False-green and deployed-INCONCLUSIVE fixtures render correctly; token totals stay unknown without a request ledger. |
| M-7 — frozen program | Integrated with the v29 corrections and ee7bc6d6; qualification PASS on `5280670b` (see Package status) | Owed: runtime image, golden, platform pins | Local only; the clean full run and its confirming repeat are the remaining claims. |
| V26-1 — typed repair execution | Executor on OpenRewrite 8.89.0 (Apache-2.0), both transformations, first action of the issued unit (481b4b0b, af47c117, 8ffdfd9d) | Image recipe step 2b ready (5d282010); no image built | Fixtures and the v28 specimen; real `run-verify.sh` + `advance.py` accept typed candidates and refuse the bad CDI and handler-parameter forms (`typed-repair-loop.test.py`, stand-in Maven/MTA/runtime gates); no live run has used it. |
| V26-2 — recipe qualification | 32 rewrite-test cases, loop-path and runtime package tests | Ships with V26-1 | Reproducible jar sha256 `66d1b6f4`; a second workspace with fresh run and cluster ids gets the same record and patch. |
| V26-3 — resolved task context | Targeted brief, actions, ownership, selectors and retry context; per-objective attachment `rhoai3.resolved-context/v1` (`planner/resolved_context.py`, written beside the brief, one digest index line) | Not published | Fixtures (`resolved_context.test.py`, renamed twin) answer the generated-DTO and inactive-profile cases and reject wrong-tree facts; classpath/API lookup and the matched-task search comparison remain open. |
| V26-4 — results and cost accounting | Typed-repair records (`rhoai3.typed-repair-record/v1`); run-report headline | Not published | Model requests/tokens remain unknown without a request ledger. |
| V26-5 — analysis reuse | Deferred | Not in scope | No measurement yet justifies it. |
| V26-6 — guidance and recovery | Unchanged by this package | As before | Recurring model repetition remains an open, measured-only risk. |
| V29-1 — void, deferral, admission | 6087c94d | Not published | Exact-condition reconcile, effective budget before/after, idempotent. |
| V29-2 — issuance liveness | 7fb8d98e | Not published | Concurrent-claim interleaving refuses `ISSUANCE_CHANGED`; the new projection survives. |
| V29-3 — rejected candidate cleanup | 8aa81b64, 919c01ae | Not published | Current-run edits survive repeated issue; interrupted rejection set aside by identity and restored. |
| V29-4 — media-type values | 9fcd639b | Not published | Distinct quoted values stay distinct; charset respelling still equal. |
| P-1 — one independent M3 pair | Unchanged scope | As before | Broader parallel execution is not authorized. |

## Package status (2026-09-30)

Qualified source: branch `feat/migration-reliability-m1-m7`, commit
`5280670b107304dd8a0f49fba5ac1c03e41612f0`, tree `038da64c2dd7ba0a801ff2e7a5fa109daba8a1c2`.
It contains the reliability roadmap work (`b0bbf60e`), `next/after-v28` through
`c9ab129d` (all v29 corrections after `26bc9c2b`), architect commit `ee7bc6d6`
(cherry-picked: launch checks without isolation campaigns, MaaS gateway memory
headroom) and remote `main` `de6c7ba6` (a fast-forward). Later commits on the
branch change documentation only. Nothing here is published, installed or
live-validated. Local evidence: `tmp/reliability-evidence/qualification-5280670b/`
in the implementation worktree (Git-ignored); the release record carries these
identities and results.

### Integration decisions

Both branches' behaviours were kept in the four overlapping files; where both
implemented the same correction, the architect-reviewed form on `next/after-v28`
was kept and the package's remaining guards were added to it:

- `native_control.py`: retirement is the lock-bound move of the judged digest
  (cf164288) plus the package's "a still-running native run of the card is live";
  parking uses the native successor proof; a re-issue over unjudged edits refuses
  `ISSUE_BASELINE_DRIFT`, replayed or not; verification-only issuance carries its
  sealed scope; the M-2 schedule, set-aside of interrupted rejections and
  effective-budget reconciliation are retained.
- `requirement_checks.py`: verification scope and producer checks both kept; one
  Location check measuring the covered scenarios; a repository effect is discharged
  only by the scenario's own PASS record in its expected mode, bound to the
  candidate, and header-only differences still do not fail it.
- `worklist.py`: the architect-reviewed Content-Type parser (parameter order kept,
  malformed never equal); authoritative FAIL history, recipe runtime ownership,
  per-mode clusters and planned checks after repair rows disappear all retained.
- `brief.py`: typed repair as first action, voided rejections and exact identities,
  bounded evidence selectors and unresolved history in one brief.

`lib/planner/merge_pairs.test.py` proves both behaviours per file on shared input.
Two defects surfaced by the merge were corrected: scenario ids normalised on one
side only (every repository effect read unmeasured), and an unreadable
post-request committed state read as FAIL instead of INCONCLUSIVE.

### End-to-end state

| Milestone | What is demonstrated | Evidence level |
|---|---|---|
| Source understood | M1 structure producer reproduces on two clean copies of the frozen v28 source; all 12 v29 missing-oracle entry points derive and qualify captures (41 disabled / 103 enabled scenarios, hsqldb baseline); User create through the ADR-026 committed-state read-back | Fresh local producer run; MTA findings are recorded evidence, not a fresh MTA 8.2 execution (host has 7.3) |
| Target structurally viable | Typed CDI exposure and URI translation qualified; servlet-redirect is the only edit the v28 tree needed to package | Recipe tests, package tests on the pinned platform |
| Persistence and one HTTP path | Reference repository port: fresh-transaction read-back, delete dependencies, recursion/stub/no-op/duplicate negatives rejected, PostgreSQL 16; ADR-026 destination path qualified on PostgreSQL 16 (committed write on a fresh connection PASS; no-op, rollback, wrong value, uncommitted FAIL; unreadable INCONCLUSIVE; both modes) | Local containers, component level |
| Application behavior preserved (Owner path) | v28 candidate 19 of 47 comparisons; rehearsal candidate (one patch per catalog repair, written from catalog text only) 47 of 47 across both modes (40 disabled, 7 enabled), 4 through ADR-025 equivalences | Manually prepared local rehearsal, not a migration output and not proof that workers reach it autonomously |
| Verification lifecycle | Repair accepted → live repair row gone → verification-only unit with sealed per-mode scope → run-verify routing → scoped comparisons replaying prerequisite state → acceptance → native review; wrong-mode, broken-setup, changed-corpus and foreign-candidate negatives refused | Fixture through the real run-verify and parity runner (one stated synthetic hop) |
| Delivered and usable | Not demonstrated: CI/CD, image, deployment and live checks need a cluster | None |

Evidence selectors work through the real K2 tool policy with inline Python still
refused; that establishes the retrieval path, not that model looping is solved.

### Qualification of `5280670b` (worker interpreter Python 3.9.25)

- 118/118 non-container suites and 14/14 container suites exit 0, including the
  merged-path regression, the conflict-pair tests and the ADR-026 PostgreSQL suite.
- Shell syntax clean for Stage 040/080 and shared scripts.
- Planning repeatability 26 pass, 0 fail, 1 NOT-RUN (fresh MTA 8.2).
- Typed-repair executor rebuilt to the pinned jar `66d1b6f4…6506ad`.
- M-3: CONTROLS PASS; v28 candidate NOT EQUIVALENT (28 steps); rehearsal EQUIVALENT
  on the measured corpus.
- Architect counterexamples corrected (current-run edit kept and its re-issue refused
  `ISSUE_BASELINE_DRIFT`; the new claim's projection kept; quoted values distinct).
- Aggregate `verdict.json`: PASS, 0 failures. The first attempt's container loop and
  identity check were harness defects in the new runner; after fixing them, the
  identity and reproduction steps were re-executed on the same snapshot and the
  verdict re-aggregated over that run's artifacts (both records kept).

### Release mapping

| Component | Source identity | Required step | Owner |
|---|---|---|---|
| Harness (golden `.hermes`) | `5280670b` (scaffold content) | fast-forward the platform `main` (never force-pushed); then the distinct golden-export publication `scripts/bootstrap-scaffold-repos.sh`; record the returned golden commit and compare its scaffold content | release agent |
| Hermes runtime | tree `37b147ba` unchanged (patches 0001–0016) | none | — |
| ws-080 image | new: adds typed-repair jar `66d1b6f4…` (17,684,782 bytes) | `build-080-runtime-image.sh 37b147baef0c2678507c52e59e3b9231ab6ab64f --push`; re-pin the new digest in `.hermes/pins.json`, `run-defaults.json`, scaffold `devfile.yaml`, Stage 050 `app-migration/skeleton/devfile.yaml` and `hermes-runtime/RELEASE.md`; confirm the `/opt/rhoai3/080.pins` stamp and `java -jar /opt/rhoai3/typed-repair/typed-repair.jar` as the worker | release agent |
| Stage 040 MaaS gateway | `maas-gateway-resources` (ee7bc6d6): istio-proxy 1 GiB request / 2 GiB limit | apply first through GitOps; read back resources, readiness, restarts and memory under ordinary traffic; headroom is mitigation, not proof that growth is fixed | release agent |
| Platform (Stage 050) | skeleton devfile digest | Argo CD sync at the intended commit; read back the served template and catalog re-stamp | release agent |
| Launch preflight | `run-preflight.sh` (ee7bc6d6) | **no isolation receipt or campaign**; live checks against the actual pod, the golden's pinned database/provisioner images and published pins | release agent |

### Remaining live validation (not claimed)

1. Build/pin/publish above; `release_gaps == []` in a new workspace.
2. One validation run on the published package with the full-release objective;
   M1 captures for the formerly missing entry points in both modes.
3. M5: candidate → PipelineRun → image digest → deployment → live checks, including
   a disposable persisted write/read/delete at the deployed route.
4. A confirming run without overlays or Operator rescue (repeatability claim).

### Verdict

**Code qualified; ready for the release agent's image build and publication** from
commit `5280670b`. Not launch-ready until the image is built and pinned, the golden
and platform are published and read back, the Stage 040 gateway is observed stable
and the bounded preflight passes. Nothing here is live-validated.

## Objective and comparison baseline

Make established migration knowledge executable so the model does not have to
rediscover the same repair on every run. Preserve deterministic M1/M2 planning,
bounded compatibility objectives and native Hermes lifecycle. Borrow useful
OpenRewrite/Moderne components and patterns within the licensing boundary;
do not adopt their architecture wholesale or add another planner or scheduler.

Compatibility-objective composition already borrows declarative composition,
applicability checks and table-style reporting. Several catalog repairs remain
`implementation.kind: agent-bounded`: the rule describes an edit that the worker
must implement. Existing decided-repairs also perform some bootstrap operations.
Extend these contracts; neither constitutes the proposed scoped M3 executor.

There is no clean, repeatable full-release baseline established by these runs.
This does not erase the earlier assisted v10 deployment and live checks: that
application was usable, while its release verdict remained INCONCLUSIVE. A
deployment, a full release ACCEPT and an unassisted repeat are different results.

- v25 stopped at 21/36 cards as an assisted diagnostic run.
- v26 was frozen at 12/36 cards; it did not validate this improvement list.
- v29 was reported at 25/37 done with assisted overlays and recoveries at I-11.
  Its narrow successes and failures are useful evidence, not clean repeatability.

Qualify the executor on identical frozen task inputs and starting candidates now;
do not require completion of those historical runs first. Use comparable measured
tasks as the baseline and state where they stop. End-to-end savings require later
end-to-end measurements. No existing run's history, allowance or deadline changes.

## What is improved, and what still prevents completion

The current planner is not random. `source_requirements.py`, `outcome_graph.py`
and `compatibility_objectives.py` derive a bounded plan from evidence; the latter
composes connected compatibility objectives and conserves the family budget.
Native cards retain ownership while concrete repair units can change. Existing
measurement code distinguishes unmeasured checks from passed checks. These are
useful foundations and should be retained.

Reproducible task formation does not make execution reproducible. The saved v29
initial plan makes the distinction concrete:

| Independently inspected fact | Architectural implication |
|---|---|
| 80 requirements; 30 repair outcomes; one M4 assessment and three M5 delivery nodes | The plan includes delivery, but a node's existence does not establish an executable route to it. These 34 graph nodes are not the whole native board's task count. |
| 18 source, three configuration, one build and eight behavior repair outcomes | The work has a useful structural/behavioral split; another wholesale repartition is not the next priority. |
| All eight behavior outcomes have 23 parents: the 22 non-behavior repairs plus M2 | Broad structural completion precedes application behavior. Some of this is necessary for a monolithic build, but it delays discovery of defects unless component behavior is qualified earlier. |
| Seven repository objectives carry between three and 34 later checks each | Structural acceptance preserves functional debt; it does not demonstrate a working repository. A later failure needs a planned owner and prerequisite path. |
| Seven unresolved verification groups cover 12 distinct entry points; all block shipment | M2 already knew substantial verification work was missing. Treating it only as a final M4/M5 qualification makes a full-release objective unreachable without additional planned work. This is the initial inventory, not a claim that all 12 remain unresolved in the live tree. |

Three shortcomings dominate the run evidence:

1. **Known migration knowledge still depends on rediscovery.** v29 reports the
   same fragment-to-repository recursion across seven implementations. Six have
   captured failing reads; User has the structural shape without a captured
   failing scenario. Endpoint-specific repair cards should not require the model
   to rediscover the common causal defect six times. Earlier validation, generated
   body, redirect and URI defects show the same need for reusable knowledge.
2. **Lifecycle projections can contradict both native state and measurements.**
   Restored budget did not lift exhaustion; ended issuance blocked recovery; a
   stale seal then replaced FAIL evidence with INCONCLUSIVE and produced an empty
   work list while reads still threw StackOverflowError. That last event is
   reported in I-11 and addressed in source `d003445c`; it is not qualified live
   by this review. This is a correctness problem, not an argument for more model
   reasoning or a higher retry allowance.
3. **Progress is being presented at the wrong level.** Card completion, reduced
   compiler counts and local suite counts are useful activity measures. None
   answers whether the application stores data correctly, passes the agreed
   behavior contract, deploys through CI/CD, and works at the deployed URL.
   `run-report.py` already has cost and milestone machinery, but its headline is
   centred on M4. It should consume existing M5 delivery evidence as well.

The architectural mistake was to let successive full runs become our default
integration laboratory. We should retain the successful planner and native
lifecycle work, but qualify a complete supported procedure and use future full
runs to validate it. We do not need a universally perfect migration engine first.

## What Moderne's end-to-end method contributes

Research reviewed official documentation on 2026-09-30. The six-module Spring
Boot workshop is a concrete migration procedure: assessment, dependency planning,
a working baseline, an early risky-transition probe, missing-recipe engineering,
and coordinated migration waves. It is a Spring Boot upgrade across repositories,
not proof of autonomous Spring Boot-to-Quarkus behavioral parity. The following
adaptations are our design decisions, not capabilities demonstrated by this project.

| Documented method | What we should borrow | Boundary |
|---|---|---|
| Assessment combines a migration dry run, compilation verification and targeted insight into dependencies, API use and generators. [R8] | Investigate the complete intended transition before spending a full run; include generators and missing verification in M2's work inventory. | A dry-run patch is neither a compiling application nor behavior proof. Use our existing MTA/JDK evidence; no extra analysis platform is required. |
| Wave planning orders independently released repositories by their dependencies. [R9] | Model the prerequisites that make a repair and its acceptance executable. | Java packages in PetClinic are not independently released repositories. Do not turn each architectural layer into one giant card. |
| Baseline preparation establishes a consistent build and refreshes analysis after changes. [R10] | Record reproducible tooling, dependencies, generated roots and source behavior; rebuild derived destination facts when relevant inputs change. | Keep the legacy source/oracle immutable. Do not upgrade it and silently compare against the upgraded behavior. |
| A controlled target-version smoke test exposes remaining blockers before wave execution. [R11] | Rehearse known risky transitions in a scratch candidate, then turn failures into release-package work. | This is bounded engineering qualification, not another long autonomous run or an isolation campaign. |
| The QueryDSL module converts a concrete missing capability into a specified, tested reusable recipe. [R12] | Ask an agent to implement reusable migration capability once, with fixtures and behavior checks, instead of rediscovering the same patch in each run. | AI-authored recipes still need review and independent tests; catalog prose alone is not execution. |
| The final module coordinates framework and QueryDSL changes that cannot compile independently, then builds, tests, commits/releases and refreshes analysis per wave. [R13] | Compose changes that are truly interdependent and establish a working milestone after them. | Preserve our scope bounds and budget. An oversized component requires an explicit plan decision, not hidden scope expansion. |
| DevCenter reports code-derived migration state; the separate commit-tracking guide distinguishes change-delivery status from migration status. [R14, R15] | Show application milestones from evidence, with delivery and release separately visible. | Extend `run-report`; no proprietary dashboard, PR workflow or new state authority is needed. |
| Prethink exports structured context, while CLI telemetry records execution/build results. [R5, R16] | Give workers the relevant facts and measure where time and tokens went. | Do not equate estimated manual effort saved with measured savings in our system. |

The important addition is the method around transformations. OpenRewrite gives us
useful typed editing and recipe-test infrastructure. Moderne demonstrates how to
organize discovery, dependency sequencing, capability development and campaign
visibility around it. Neither removes the need for our source behavior captures,
Quarkus augmentation, real database tests, security-mode parity or M5 delivery.

## Methodical improvement decisions

IDs M-1 through M-7 are implementation work packages, not new Kanban phases or
runtime authorities. They reuse M1–M5, the admitted plan, recipe catalog, existing
measurements and native Hermes. V26 items below supply components of this program.

### M-1 — Define the supported migration and its finish line

Make the M1/M2 handoff state the exact source revision, active profiles, build and
generator toolchains, target architecture, database, security modes and observable
behavior in scope. Most inputs already exist; compose them rather than introduce
another independent declaration. Distinguish:

- **Functional milestone:** the application packages, starts, and completes the
  selected HTTP/database path. Useful progress; not full migration acceptance.
- **Delivery milestone:** the named candidate goes through the actual pipeline
  and its image is deployed and live-tested. A remaining qualification may still
  prevent release ACCEPT.
- **Full release:** existing M4/M5 obligations are satisfied for the agreed scope.
- **Repeatability:** a clean run achieves that result with frozen inputs, followed
  by a confirming run without harness overlays or Operator rescue.

Every known ship-blocking verification gap must have a planned resolution: source
capture/fixture work, a destination behavior check, a named external dependency,
or an explicit scope decision with evidence. Start with the saved 12 entry points
and map them individually; do not invent test oracles from destination responses.
An unresolved source capability stays unknown. It cannot disappear because its
card has finished or a current work list is empty.

Unknowns discovered later remain possible. Record them as explained plan revisions
with ownership and conserved obligations. The requirement is a credible completion
path, not pretending all future failures can be predicted. A diagnostic run can
start with known qualifications if labelled that way; a full-release validation
should not knowingly start with no resolution path for a required qualification.

Do not claim that HTTP inventory establishes coverage of reflective, scheduled,
message-driven or other dynamic entry paths. Where applicable, expose those as
explicit scope/analysis limitations rather than silently treating them as absent.
This does not add unrelated application features to the PetClinic qualification.

**Exit:** the initial report answers what completion means, which known gaps can
prevent it, who resolves each gap and what observable evidence closes it. Missing
oracles cannot be reported as an empty successful plan. No gate is weakened.

### M-2 — Plan executable milestones, not just a legal graph

Retain coherent compatibility objectives and bounded repairs. Extend the existing
plan/check metadata to distinguish implementation dependencies from verification
prerequisites. A repository may be structurally converted while its behavior
check awaits a working database and application; record both states explicitly.

Use this progression as a derived view of the existing graph:

| Milestone | Work and evidence |
|---|---|
| Source understood | Source builds/runs on its supported toolchain; selected profiles, generated types and behavior captures are qualified. |
| Target structurally viable | Required dependency, generator, API, bean and configuration transitions are applied; target compilation and augmentation succeed. |
| Persistence and one HTTP path work | Repository contracts exercise real reads/writes; one controller→service→repository→database path behaves correctly. |
| Application behavior preserved | Remaining paths, validation, ordering, Location, CORS and required security modes pass their owned checks. |
| Delivered and usable | M4 results, M5 pipeline/image/deployment binding and live tests support the release decision and human walkthrough. |

This is not a replacement set of five mega-cards. Use the graph's existing owners;
derive the milestone from their checks. Do not remove the whole-application build
prerequisite just to run a slice early when unrelated sources still prevent
compilation. Before that point, qualify the same risky components in focused
fixtures; at the first viable package, run their real application checks promptly.

For known server errors, schedule the causal repository repair before dependent
response/header comparisons. Do not globally put all CORS behind all CRUD:
anonymous rejection and preflight checks may have different prerequisites. When
a common producer causes several failures, retain every endpoint obligation but
share the qualified repair and remeasure all affected paths. A repaired Owner
response is not automatic evidence for User or Visit.

If two transformations cannot produce an acceptable intermediate state, compose
them within existing bounds or explicitly plan a qualified intermediate. Never
silently defer a dependency cycle to M4, increase a family budget by regrouping,
or make a scope violation the worker's only route to acceptance.

**Exit:** fixtures cover the repository/DAO prerequisite conflict, generated-body
and controller coupling, and server-error-before-header cases. Every immediate
check is executable at issuance; every later check has an owner, prerequisites
and an earliest useful measurement point. The same frozen inputs yield identical
logical ownership, checks, dependencies and budgets.

### M-3 — Rehearse risky behavior before another full validation

Build one bounded reference qualification from our actual selected architecture,
not a simplified alternate migration. Reuse preserved evidence and existing tests
where admissible; fill their missing behavioral coverage. The program must cover:

1. The active source repository strategy, CDI exposure and generated delegation:
   reject recursion, throwing placeholders and no-op writes. Verify write effects
   through a fresh transaction, including delete dependencies.
2. A real Owner create/read/update/delete path through all layers on the pinned
   target stack and PostgreSQL. Include valid and invalid requests, omitted versus
   null/empty collections where the source establishes a contract, error headers
   and Location construction. H2-only results do not qualify PostgreSQL behavior.
3. Clean code generation and startup with the application root path, then CORS and
   authentication behavior in the required modes. Keep each comparison bound to
   the artifact and mode actually measured.
4. The existing CI/CD handoff and deployed route contract, including root-aware
   health/OpenAPI paths and a disposable persisted write/read/delete check.

Component tests provide early feedback while the full application cannot build.
They do not replace the application milestone. Once the first package works, use
it for the focused path and expand through the remaining contract. Do not spend
eight separate behavior cards rediscovering a shared broken repository pattern.

Use the existing assisted run only as diagnostic evidence unless further action
is separately authorized. No copied overlay, repaired receipt or old accepted
tree qualifies a new clean migration. A new defect found during rehearsal becomes
a reusable repair/test in the package before launching its validation run.

**Exit:** the known-risk cases have actual executable tests and measured outcomes;
the next full run is not their first integration test. Report unsupported cases
explicitly. This is a finite PetClinic qualification, not a requirement to solve
every possible Spring application or reproduce every infrastructure failure.

### M-4 — Turn each established fix into reusable capability

Implement V26-1/V26-2 using eligible OpenRewrite components, beginning with the
two selected transformations. Pin exact artifacts/options and retain type-aware
matching, dry-run diff inspection and existing acceptance. OpenRewrite's scanning
recipes gather facts before edits; composite authors must explicitly account for
that ordering instead of assuming one scan observes another recipe's edits. [R3]

For each known applicable pattern, the catalog must name its source semantics,
target/version/profile conditions, files/types affected, executable action or
bounded semantic work, independent checks and unsupported cases. Prioritize the
existing failures: repository exposure/delegation, servlet redirect/URI handling,
validation polarity and boolean logic, generated-body binding, transactions,
collection ordering, root-path configuration and security/CORS ordering.

This is a coverage requirement, not a promise that all these repairs fit one
generic recipe. Repository method behavior may require a source-specific port;
never substitute the inactive JPA implementation for the selected Spring Data
strategy. A guidance-only exception must carry the exact relevant facts and be
qualified through its real brief and verification path. Known missing guidance
for a target pattern is package work, not an observation to rediscover next run.

Use recipe tests for before/after, unchanged negatives and repeated application,
and our runtime tests for semantic correctness. A recipe's text diff or
idempotence cannot prove persistence or HTTP behavior. [R4]

Coverage table (2026-09-30): SAD §7.3. The three patterns that needed a contract decision are ruled by ADR-025.

**Exit:** a coverage table maps each known pattern to a qualified recipe or tested
bounded agent procedure. An unsupported shape returns an actionable result before
partial edits. Repeated runs reuse the same implementation and tests; they do not
need a new Operator instruction for the same established defect.

### M-5 — Simplify state ownership and preserve evidence through failure

Native Hermes owns task/run/review lifecycle and the governed attempt account.
`issued.json`, deferrals, admission and work-list projections must reconcile with
that ownership; none should remain an independent reason to block after its cause
has ended. Acceptance still belongs to the existing measured gates.

Complete V29-1/V29-2/V29-3 and the counterexamples below. Treat repeated operations
and crash boundaries as part of the same lifecycle implementation. Do not add a
second dispatcher, repair daemon, sidecar or another competing state journal.

Keep the last authoritative measured FAIL as history when a later measurement is
invalid or unavailable. Report the current check as unknown/pending, retaining
its outstanding obligation. Never reinterpret lack of authority as an empty
successful work list. Conversely, do not present an old FAIL as a fresh measurement
of a changed tree: history, current validity and outstanding work are distinct.

Classify a stop as product failure, harness inconsistency, source qualification,
or provider/runtime availability. Retry a transient provider failure through the
existing bounded native path; a deterministic harness defect should not cause a
worker to spend further attempts guessing how to repair control files.

**Exit:** one replay covers issue→edit→verify→accept/reject→review→continuation,
plus interruption and restart. Repeated issue preserves current edits; concurrent
new claims survive retirement; budget void, deferral and admission agree; a failed
comparison cannot erase a known obligation. Genuine rejection and review spending
remain conserved. This replay complements, rather than replaces, focused tests.

### M-6 — Make end-to-end state the headline

Extend the existing run report; do not build another dashboard service. Report
the last demonstrated application milestone, current candidate, next missing
prerequisite and oldest unresolved cause. Then show task activity as supporting
detail. Moderne's code-derived status and separate delivery tracking are the
useful patterns here. [R14, R15]

Include source qualification and missing oracles; planned versus added work;
structural versus behavioral acceptance; package/start/database results; per-mode
parity; and M5 candidate→PipelineRun→image digest→deployment→live results. A
deployed but INCONCLUSIVE application must remain visible as deployed and not
released. The human access URL and checks come from delivery evidence.

Measure total model requests/tokens, verification time, recipe execution time,
repeated searches, review/rework, provider wait and assisted interventions.
Separate model work from harness/infrastructure overhead. Unknown token usage
stays unknown; aggregate percentages of completed cards are not percentages of
completed migration. Refresh at existing lifecycle milestones or an actionable
stop, without a model repeatedly polling unchanged state. [R16]

Group repeated failures by a supported causal signature, with representative
evidence and affected owners, before counting them as separate repair problems.
Moderne's build-failure guide uses grouped diagnosis to prioritize common causes;
our extension to runtime failures must additionally prove the shared producer
relationship and retain each affected behavior check. [R17]

**Exit:** the false-green v29 snapshot displays “runtime behavior unresolved;
measurement invalid” even with an empty work list. A historical assisted deployment
with qualifications displays its URL and ship=false. The final report can answer
what works, what remains, why progress stopped and what the run cost.

### M-7 — Validate a frozen migration program, then demonstrate repeatability

Release one coherent combination of platform/runtime/golden, catalog/executor,
model profile, toolchains and verification inputs. Record source, published and
installed identities separately. Use the current license process and artifact
pins; do not download unpinned latest recipes during a run.

Qualification proceeds from cheap focused tests and saved failure replays to
the bounded reference behavior, then the end-to-end run. Reuse tests that already
prove the same unchanged code. A full run should answer whether the qualified
procedure composes end to end, not whether a known redirect rule exists.

Distinguish three claims:

| Claim | Required comparison |
|---|---|
| Repeatable planning | Two fresh M1/M2 derivations on the same frozen source, profiles, producers, captures and pins produce the same semantic inventory, ownership, checks, dependencies and budgets. Recorded MTA findings replayed twice are not two fresh MTA executions. |
| Repeatable transformations | Deterministic recipes produce equivalent patches and no second-application changes; agent-authored exceptions satisfy the same independent behavior contract. Exact LLM text or byte-identical generated timestamps are not required. |
| Repeatable migration | A clean M1→M5 full-release result, then one confirming run on the same supported inputs, with no harness overlays, manual repairs or Operator rescue. Report measured cost and variation; two successes do not prove universal reliability. |

The measurement is checked in. `qualify-repeatability.py` (build-worklist skill)
runs the M1 MTA producer on two clean frozen copies (`--source`) and compares
rule ids and locations; `--build-fresh SOURCE` builds both fresh M1 → M2 roots
with `rehearse-legacy.sh` and the offline corpus derivations, then compares
plans and MTA findings; `--patches A B` compares the typed-repair patch digests
of two independent applications. Source captures are reported NOT-RUN, as is
MTA when no CLI resolves. `stages/080-ai-autonomous-migration/qualify-release.sh`
runs the scaffold suites and this driver, then writes `verdict.json`. Each claim
in the table above is graded MEASURED, PARTIAL, NOT-MEASURED or FAILED, and the
verdict lists what each claim is missing. Repeatable migration stays
NOT-MEASURED until the two full runs exist.

Keep qualification and diagnostic spending visible and bounded. If a genuinely
new defect stops validation, preserve evidence and fix the reusable procedure;
do not rescue the same run and call it autonomous. Ordinary in-scope product
repairs and existing native transient recovery remain part of normal execution.
Keep the approved P-1 pair separate from this comparison; broader concurrency
would change the experiment before basic completion is demonstrated.

**Exit:** the release mapping names the complete procedure and measured known-risk
coverage. One full supported application completes before adding more application
families or a general parallel scheduler. Repeated full runs stop being a substitute
for finishing known implementation work.

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

## Reusable repair design

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
   annotation shape fits every repository. Include the v29 recursion negative:
   a fragment must not call back through the Spring Data repository that routes
   the call to that fragment. Correct CDI exposure alone does not prove behavior;
   retain the independent repository contract and runtime checks.
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
CDI, plus real HTTP handler/Location behaviour for the URI translation. For repository
checks, include duplicate beans, routed-back recursion, throwing stubs and no-op
writes, with effects read back across transaction boundaries. The executor must
not manufacture method bodies to make these checks pass. Source captures remain
the behavioural oracle. Do not replace runtime evidence with
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
explicit; compare searches and context use on matched tasks with the same inputs.
Historical v25 observations are partial diagnostic evidence, not a completed baseline.

### V26-4 — Transformation results and honest cost accounting

Extend existing handoff, verification-record and run-report machinery rather than
creating another receipt or acceptance authority. Its presence does not establish
complete live accounting. OpenRewrite data tables provide a useful reporting pattern
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

Consider reusing parsed/build metadata only after measuring avoidable producer
and build cost on the current workflow.
Cache keys must include source content, generated inputs, dependency/classpath
identities, JDK, active profiles, analysis options and producer version. Build-file
equality alone is insufficient. Missing or mismatched identity triggers recomputation.

Do not cache a past test/parity result as a fresh measurement, or remove the clean
M1/M2 repeatability qualification. This item is not a prerequisite for the current repair package.

### V26-6 — Repair guidance and recovery from tool loops

Keep the existing bounded runtime protections. A stop identifies a repeated-call
pattern, not its root cause. Fix missing or contradictory information and lifecycle
defects before adding warnings or another repetition heuristic. Preserve the
inline-Python restriction and current acceptance, scope and budget rules.

Specific corrections are implemented in the reviewed source:

- Qualified Servlet redirect guidance and checks; the compile item itself now
  carries the action even when a later objective owns the behavior requirement.
- Default brief output is a digest on stdout, with documented item/unit actions;
  `--full`/`--json` explicitly select JSON. Catalog advice hidden in an unused
  section is not equivalent to advice delivered to the model.
- Immediate checks and diagnostic ownership follow issuance, not shared paths.
  Planned requirements remain owed after compiler diagnostics disappear.
- PREVIOUS RUN and LAST VERIFICATION expose candidate state, prior stops,
  bounded results and current/stale verification; selectors use measured facts.
- Verification records retain producer status despite successful shell filters.
  Unchanged rework, the REVERTED lockout and native skill preload have targeted
  corrections. Their tests do not prove all recovery paths reliable.
- Runtime 0015 distinguishes low novelty from unchanged output. The broad K2
  number-masking check was withdrawn; exact operands and complete result evidence
  are preserved. A separate narrow duplicate-observation check exists in the
  implementation branch; its presence is not evidence of a root-cause fix.

**Corrected qualification claim.** The earlier worker exercise manually appended
`FIRST ACTION` after constructing the digest. Its 2/2 immediate edits therefore
used better instructions than the real renderer delivered; one also removed
behavior. It did not qualify production delivery or accepted task behavior.
The replacement regression follows the actual catalog -> sealed unit -> default
CLI path. Do not hand-insert repair guidance in the task-level qualification.

The approved four-request Root17 comparison held model settings and old facts
constant while changing brief rendering. All four continued the failed search;
284,177 tokens were used. Rendering alone did not fix that case. The later action
delivery correction was not included in that comparison. The earlier thinking
screen was partial and mixed; neither experiment qualifies a production profile
switch. The installed-code serialization probe confirmed the intended non-thinking
request overrides, not every real worker request. The old inference approval is
exhausted; subsequent experiments need their own applicable authorization and cap.

The saved v29 record supplies narrower positive evidence: Root implemented the
qualified redirect form in one run, while the ORM task still hit a read-cycle stop
before a successful native retry. Report both. Do not infer eliminated looping or
attribute all improvement to one prompt change from this assisted run.

Remaining qualification:

- Trace the actual delivered brief and tool results, including truncation,
  repeated-result substitution and retry reconstruction. Missing evidence stays
  unknown; partial tails do not prove complete results equal.
- Run one bounded real repair with the current catalog, actual brief and normal
  tools, verification and review. Include a successful control where affordable.
  Record accepted behavior, searches, rebuilds, scope compliance and total cost.
- Start with the existing model profile. If complete actionable guidance still
  fails, compare a justified alternative separately on matched task inputs. Do not
  change instructions and profile together and attribute the result to thinking.
- Preserve all obligations and distinguish worker crashes from rejected candidates
  and semantic budget spend. A guard not firing or a useful next action is not
  task acceptance. Do not launch a full migration just to diagnose this question.

## Current lifecycle repairs from v29

Recovery code exists in `0dd677ba`, with a further resealing correction in
`d003445c`. That changes their status from missing implementation to implemented
with unresolved qualification findings. The four supplied lifecycle regression
cases passed in the earlier independent review, but three additional counterexamples
reproduced defects. Do not restart the implementation or mark the package complete
from its existing green tests. Correct the specific gaps through native control
and loop tools; add no independent lifecycle authority.

### V29-1 — Voided rejections and exhaustion deferrals agree

`void-rejects` restores native budget credit but leaves a deferral caused by the
voided spending in place in the original failure. The new reconciliation must
lift only a budget-exhaustion deferral whose
condition is no longer true. Preserve genuine blockers, original rejections,
published limits and deadline. A reconciliation must not also grant the legacy
clearance's extra allowance. Report effective spending and allowance before/after.

Acceptance: an authorized void lifts only its now-invalid exhaustion hold;
a still-exhausted family or unrelated blocker remains held. Repetition and crash
recovery are idempotent: no double credit, extra allowance, automatic acceptance
or implicit minting. The same native card can be issued the correct repair again.
Include admission in the reconciliation: an interrupted or stale seal cannot
continue to name a lifted deferral. Source `d003445c` adds that reseal path and
a no-issued-card comparison guard; its installation was pending in the saved
record. Test that invalid comparisons leave existing obligations outstanding.

### V29-2 — Issuance liveness follows the native run

The original Operator path treated the presence of `issued.json` as proof of a
live worker. The new native liveness check addresses that failure, but retirement
still needs protection against the independently reproduced concurrent-claim race.
Retire an expired projection only after establishing its native run has ended,
no newer claim owns it and no surviving worker can write through that claim.
Keep historical issuance and retained-candidate evidence. Do not delete every
projection at a terminal event: review and recovery still need its history.

Acceptance: stale run 75 cannot hold recovery indefinitely; a live or unknown
claim refuses retirement; a delayed event cannot retire a newer issuance.
Retained candidates survive, and restart/repeated recovery is safe. Recovery
itself does not dispatch; explicit native unblock resumes the same task and its
official log is read after spawn.
The read/check/archive/remove operation must be conditional on the exact issuance
and native claim still matching at commit. A new run created between the liveness
check and retirement must keep its own `issued.json`. Test that interleaving,
not only sequential live-versus-ended cases.

### V29-3 — Rejected candidate cleanup survives interruption

I-11 attributes the leftover rejected CORS edits to a stopped worker executing no
terminator; `0dd677ba` adds parking on the next issue. The independent reproduction
found that repeated issue could instead park a current worker's legitimate edits
under an older run and reset them. Fix current-issuance idempotence before any
abandoned-candidate cleanup. Do not solve the old failure by discarding new work.

Acceptance: interruption after rejection cannot expose dirty rejected bytes as
an accepted baseline for a later card. Preserve the rejected patch and evidence,
require a verified restore before work continues, and test restart at the relevant
boundary. Do not silently discard a retained candidate or unrelated user edits.
Explicitly test old stopped run → new issue → new legitimate edit → repeated
issue: the new edit survives unchanged and is never attributed to the old run.

### V29-4 — Media-type normalization preserves values

The local counterexample at `0dd677ba` showed that splitting Content-Type on every
semicolon collapsed distinct quoted values, `note="A; X=Y"` and `note="A; x=Y"`.
Repair the parser using the applicable grammar; normalize only fields whose
comparison is defined as insensitive. Equivalent charset spellings should not
create false regressions, but distinct extension values must remain distinct.
This is a comparator correction, not a waiver of HTTP parity. Include quoted
delimiters, escaping, parameter ordering and genuinely different values in tests.

### Platform dependency — MaaS gateway stability

I-4/I-5 record request failures and gateway memory pressure followed by recovery
after a restart. The lasting resource/configuration correction belongs to Stage
040; the cause of memory growth still needs investigation. Keep gateway failures
separate from model loops and transformation correctness, and carry the platform
work through its own guarded GitOps validation. This roadmap does not authorize a
resource change or another isolation campaign.

## Integration locations and execution order

Paths below are relative to the scaffold's `.hermes/` unless stated otherwise:

- `planning/catalogs/compat-mapping.json`: qualified recipes and applicability.
- `lib/planner/{source_requirements,compatibility_objectives,requirement_checks}.py`:
  evidence, requirement/check ownership and preserved planning/scope contracts.
- `lib/planner/{outcome_graph,plan_semantics,measurement}.py`: unresolved
  verification work, executable prerequisites and measured milestone state.
- `lib/planner/decided_repairs.py` and
  `skills/migration/bootstrap-destination/scripts/_decided_repairs.py`: reuse
  applicable contracts; distinguish bootstrap operations from M3 transformations.
- `skills/migration/fix-until-green/scripts/{brief.py,run-verify.sh,advance.py}`:
  task context, scoped execution and independent acceptance.
- `kernel/native_gate.py`, `lib/planner/native_control.py` and
  `skills/migration/fix-until-green/scripts/operator-step.py`: native recovery and
  projection consistency; retain one budget authority.
- Existing measurement records and `skills/evaluation/run-report`: extend actual
  execution/cost accounting and the end-to-end headline. Consume delivery evidence
  through the existing contracts in `lib/m5_delivery.py`; create no new acceptance
  authority.
- Stage `SOLUTION-ARCHITECTURE.md`, affected skills and `BACKLOG.md`: document
  selected components, licensing, release identities and evidence limits.

Implementation handoff, in order:

The first report update is a short consolidation of evidence already held by the
harness. It must not become a dashboard project that delays the application fixes.
The existing cooperative-evidence trust boundary remains unchanged.

| Package | Existing code to extend | Concrete deliverable |
|---|---|---|
| M-1 and M-6 first | `source_requirements.py`, `outcome_graph.py`, `skills/evaluation/run-report/scripts/run-report.py`, `lib/m5_delivery.py` | An evidence-derived completion map for this specimen, including the initial missing oracles, actual milestones and M5 delivery state. A compact report, not another planning authority. |
| M-5 | `native_control.py`, `kernel/native_gate.py`, `run-verify.sh`, `advance.py` and the existing parity comparator | Correct the reproduced recovery races, current-edit loss and quoted-value comparison; qualify deferral/admission/measurement consistency together. Preserve native semantics and effective spending. |
| M-2 and M-4 | `compatibility_objectives.py`, `plan_semantics.py`, `requirement_checks.py`, the catalog and `brief.py` | Explicit acceptance prerequisites and known-pattern coverage. Deliver V26-1/V26-2's two typed actions through the real scoped executor; qualify remaining semantic procedures against their actual briefs. |
| M-3 | Existing fragment, controller, generated-body, parity and delivery test paths | One bounded reference qualification using the selected architecture and real database, with causal negatives and a working HTTP path. Reuse valid existing tests; fill gaps rather than rebuild all fixtures. |
| M-7 | Existing repeatability driver, release validation and publication mapping | Compare fresh planning, qualified repairs and conserved budgets; freeze the package and prepare one end-to-end validation with an explicit full-release objective. |

Work already implemented must be inspected and reused. Do not ask an implementation
agent to rediscover these architectural choices, rewrite the planner, or turn this
into a long series of new control mechanisms. Return the exact remaining behavioral
gap when a procedure cannot meet the stated exit; do not defer a known applicable
defect merely because a future live run could detect it.

Compare deterministic and agent execution on matched task inputs without changing
objectives, scope, acceptance or retry allowance. Count executor overhead as well
as saved model work. Keep V26-5 caching deferred until measurement justifies it.
Gateway stability is a separate platform correction, but a known unusable gateway
cannot be hidden in migration performance numbers.

This document selects no run number and performs no activation or publication.
Existing frozen/assisted runs keep their histories. Mid-run corrections remain
assisted continuation and cannot establish clean execution of the released package.

## Acceptance and claim boundaries

A bounded executor comparison must show identical logical M1/M2 plans, conserved
obligations/budgets, no scope expansion, repeatable patches and preserved behavior.
Measure first-pass success, repeated edits/searches, blocked acceptance, verification
count/time, requests/tokens, elapsed time and assistance. Keep provider failures
separate. Fewer cards is not success; repartitioning would confound this comparison.

Use real verification and native review. State whether evidence comes from a
fixture, scratch replay or a recorded live run. Require an observable reduction
in agent work on the targeted repairs without a correctness regression; do not
invent a percentage saving. Count executor startup/parsing overhead and failures.

Full migration, M4 parity and M5 delivery retain their existing gates. Local recipe
qualification is not end-to-end success. The licensing boundary is unchanged.
No additional isolation campaign, sidecar, scheduler, whole-platform clone or
broad task repartitioning is included. Parallel execution remains limited to the
separately approved P-1 pair in native worktrees; its assisted v29 demonstration
does not authorize general parallel M3 or establish unattended review reliability.

## References

These are design/component references, not proof of performance in this project.
Official documentation reviewed 2026-09-30. R15 and R17 explicitly describe the
legacy platform-v1 product; their methodological patterns are used here, not
claims that those interfaces are the current deployment contract. Verify exact
artifact licenses and APIs when implementation begins. Workshop repository waves
must not be confused with our within-application repair units.

- [R1 — OpenRewrite licensing](https://docs.openrewrite.org/licensing/openrewrite-licensing)
- [R2 — Lossless Semantic Trees](https://docs.openrewrite.org/concepts-and-explanations/lossless-semantic-trees)
- [R3 — Recipes and scanning phases](https://docs.openrewrite.org/concepts-and-explanations/recipes)
- [R4 — Recipe testing](https://docs.openrewrite.org/authoring-recipes/recipe-testing)
- [R5 — Moderne Prethink](https://docs.moderne.io/user-documentation/agent-tools/prethink/)
- [R6 — Spring Boot Data JPA to Quarkus Panache recipe](https://docs.openrewrite.org/recipes/quarkus/spring/springbootdatajpatoquarkus)
- [R7 — Recipe data tables](https://docs.openrewrite.org/authoring-recipes/data-tables)
- [R8 — Migration assessment](https://docs.moderne.io/hands-on-learning/spring-boot-migration/module-1-migration-assessment/)
- [R9 — Dependency and wave planning](https://docs.moderne.io/hands-on-learning/spring-boot-migration/module-2-wave-planning/)
- [R10 — Establishing a working baseline](https://docs.moderne.io/hands-on-learning/spring-boot-migration/module-3-establish-baseline/)
- [R11 — Controlled target-version smoke test](https://docs.moderne.io/hands-on-learning/spring-boot-migration/module-4-smoke-test/)
- [R12 — Engineering the missing QueryDSL recipe](https://docs.moderne.io/hands-on-learning/spring-boot-migration/module-5-build-querydsl-recipe/)
- [R13 — Coordinated migration and verification in waves](https://docs.moderne.io/hands-on-learning/spring-boot-migration/module-6-wave-migration/)
- [R14 — DevCenter migration visibility](https://docs.moderne.io/user-documentation/moderne-platform/getting-started/dev-center/)
- [R15 — Commit delivery versus migration progress, platform-v1](https://docs.moderne.io/user-documentation/moderne-platform-v1/how-to-guides/track-commits/)
- [R16 — CLI execution telemetry](https://docs.moderne.io/user-documentation/moderne-cli/how-to-guides/cli-telemetry/)
- [R17 — Grouping and investigating build failures, platform-v1](https://docs.moderne.io/administrator-documentation/moderne-platform-v1/how-to-guides/analyzing-build-failures/)
- [R18 — Type attribution and classpath requirements](https://docs.openrewrite.org/reference/type-attribution)
- [R19 — Module versions and individual license labels](https://docs.openrewrite.org/reference/latest-versions-of-every-openrewrite-module)

### Research decisions not adopted

- Do not use a proprietary Moderne platform, CLI, recipe or agent tool as an
  undeclared dependency. Reproduce useful public workflow concepts in our existing
  harness; reuse eligible artifacts only after checking exact licenses. [R1, R19]
- Do not replace the selected Spring compatibility architecture with Panache just
  because a broad migration recipe chooses it. [R6]
- Do not introduce repository-wave orchestration for one monolithic application,
  a new progress database, a PR requirement or another scheduling layer. [R9]
- Do not interpret a recipe with no edits as a satisfied requirement, or a
  successful build as application/release parity. Missing type attribution and
  generated classes need explicit handling. [R18]
- Do not infer a guaranteed success rate or token saving from vendor workshop
  examples. Our comparison must measure the supported application and actual costs.
