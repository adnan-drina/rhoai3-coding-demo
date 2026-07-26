# Stage 080 harness — run #3 assessment and improvement plan

Status: written 2026-07-26 during run #3's final gate round; numbers as of
12:05 UTC. Run #3 = full autonomous migration, MiniMax M2 orchestrator +
Qwen3.6-27B worker, supervisor-driven (Phases A–E). Baselines: run #1
(M2, operator-driven endgame, ~8 h), run #2 (27B both seats,
operator-corrected endgame, ~11 h).

## 1. Honest assessment

**What run #3 proved:** a fully autonomous end-to-end migration is
*achievable* on this platform — 17/17 tasks resolved, findings delta
32/37, tests green in the factory, every failure class self-corrected
without a human migration decision.

**What it also proved:** the current harness achieves autonomy by
*discovering* defects late and paying for them in wall-clock. ~11.8 h
elapsed against run #1's ~8 h operator-assisted baseline, and the factory
rejected the push six times before (pending) success. That is autonomy as
brute-force convergence, not autonomy as engineering discipline. Both
criticisms — too slow, too many late-caught defects — are accurate.

### 1.1 Where the time went (measured)

| Bucket | Time | Notes |
|---|---|---|
| Orchestrator sessions (33) | ~8.1 h | mean ~15 min; Phase C alone ~6.3 h across 22 task sessions |
| Zombie-worker idle waits | ~1.7 h | eliminated mid-run (supervisor v2.3 kill-on-commit) |
| Pipeline waits + supervisor backoffs | ~0.8 h | 8 failed pipeline runs, one 15-min quota backoff |
| Supervisor restarts/patches (operator) | ~0.5 h | 5 harness defects fixed mid-run |
| Debt-task burn (T-005, T-011) | ~2.5 h inside session time | 3 stalled worker attempts each before honest failure |

### 1.2 Where the quality escaped (defect ledger, by discovery point)

| Defect | Introduced | Should have been caught | Actually caught |
|---|---|---|---|
| Workspace-only jar dependency (audit-logging) | T-012 | T-012 sensor | Factory build, Phase E r1 |
| Test NPEs (unwired constructor deps) | T-006/T-010 tests | task sensors | Factory build, Phase E r1–r3 |
| Schema/sequence drift (AUTO generators vs DDL) | T-002 | T-002/T-008 sensor | Phase E r1 (self-caught) |
| Seed-data SQL constraint violations | T-008/T-016 | task sensor | Factory build, Phase E r2 |
| 58 style violations | throughout | per-task gate bars | Factory sonar, Phase E r4 |
| REST + security design gaps | Phase B packets | Phase B | Worker budget exhaustion (debt) |

The pattern behind every row: **"green in the workspace" is not "green in
the factory."** The workspace sensor (`mvn clean test/verify` with a warm,
polluted local repo, no sonar profile, no runtime deploy) systematically
under-approximates the factory. The harness then uses the factory as its
first real sensor — at ~7 minutes and one full round per lesson.

### 1.3 Harness engineering debt (the supervisor's own defects)

Five supervisor bugs required operator fixes mid-run: heading-format
parser, zombie-wait cap behavior, kill-on-commit gap, missing
build-failure classification branch, round-prefix collision. All are
fixed and versioned, but the pattern is clear: the supervisor shipped
without its own test suite and learned in production.

## 2. Improvement plan, per phase

Ordered within each phase by expected wall-clock/quality impact.

### Phase A — ground truth (working; make it free)

- [ ] **A1. Deterministic Phase A.** Normalizing the newest analysis JSON
  is pure file mechanics; no model judgment is exercised. Move it from an
  orchestrator session (~20 min, ~1.3 K s measured) into a supervisor
  script step with a scripted summary + commit. Saves a session and
  removes a failure surface. *Effort: S. Impact: −20 min.*

### Phase B — planning (the highest-leverage quality fix)

- [ ] **B1. Design-in-packet contract** (BACKLOG, promoted): every infer
  task in `tasks.md` must carry the decided target design — signatures,
  annotations, file mappings, security/REST shape. The worker implements;
  it never decides architecture. Eliminates the T-005/T-011 class
  (~2.5 h + 2 debt entries in run #3). *Effort: M (runbook + Phase B
  prompt + plan template). Impact: −2 h, +2 tasks completed.*
- [ ] **B2. Plan lint gate.** The supervisor validates `tasks.md` before
  Phase C: parseable ids, every mandatory finding mapped, every infer
  task has a design section, UI surface covered or waived. One forced
  revision round on failure. Deterministic script — catches format drift
  (run #3's first abort) and design gaps at minute 40, not hour 6.
  *Effort: S–M. Impact: kills two observed failure classes.*
- [ ] **B3. Task templates.** Ship `tasks.md`/packet skeletons in the
  scaffold that the orchestrator fills, instead of free-form authoring —
  format compliance by construction. *Effort: S.*

### Phase C — execution (the wall-clock fix)

- [ ] **C1. Factory-parity sensors per task.** Replace the trusting
  sensor with the factory's own definition of green, locally:
  `mvn -q clean verify -Dmaven.repo.local=/tmp/m2-clean` (catches
  workspace-only dependencies at the introducing task — the audit-jar
  escape), plus a local sonar scan against the project profile on
  milestone boundaries (catches the 58-violation class before any push).
  This is the single biggest quality lever in the plan: it moves factory
  discovery from Phase E rounds (~30 min each) to task time.
  *Effort: M (sensor script + sonar-scanner in the tooling image;
  anonymous sonar reads already work). Impact: Phase E collapses to a
  confirmation round.*
- [ ] **C2. Worker ambiguity-stop rule** (BACKLOG, promoted): worker-side
  guide (AGENTS.md/opencode skill) — a packet requiring an architecture
  decision gets an immediate structured refusal, not a 25-min stall.
  Converts residual design gaps into fast re-packet loops.
  *Effort: S. Impact: −60 min per occurrence.*
- [ ] **C3. Session amortization for mechanical clusters.** Rewrite-class
  and config-class tasks that share a concern (e.g. T-R1..T-R3 style
  clusters) execute in one session with per-task commits. Run #3 spent
  ~1 h in session startup overhead across 33 sessions. *Effort: M.
  Impact: −45–60 min.*
- [ ] **C4. Orchestrator escalation valve** (BACKLOG, promoted): on worker
  budget exhaustion the orchestrator implements that one task directly;
  supervisor logs `escalated` as a packet-quality KPI. *Effort: S.*

### Phase D — final sensors (shift the factory left)

- [ ] **D1. Full factory pre-flight.** Phase D's exit criteria become the
  pipeline's exact stages run locally: clean-repo build, full test suite,
  sonar scan with gate thresholds, plus a container-profile boot check
  against the dev PostgreSQL (catches schema-validation drift — the
  sequence escape — before any push). Phase E's first push should be a
  formality. *Effort: M. Impact: −3–4 factory rounds ≈ −2 h.*

### Phase E — ship loop (already classified; make it converge in one)

- [ ] **E1. Per-class round budgets** (build/gate/deploy each get 2)
  instead of one shared counter — tonight's 3 build rounds consumed the
  budget sonar needed. *Effort: S.*
- [ ] **E2. Success = demo acceptance, not HTTP liveness.** The route
  check asserts the migration acceptance recorded in `migration.yaml`
  (index page 200 AND products API returning the legacy catalog count),
  and the UI-surface waive rule is bounded: the demo template's
  acceptance overrides a waive. *Effort: S.*
- [ ] **E3. Push only on green pre-flight** (with D1): Phase E pushes when
  local factory-parity checks pass; the pipeline confirms rather than
  discovers. *Effort: derived from C1/D1.*

### Cross-cutting — harness engineering discipline

- [ ] **X1. Supervisor test suite + CI.** shellcheck + bats unit tests for
  `classify`, task-id parsing, `committed` scoping, wait/kill logic; a
  dry-run mode (mock hermes/oc) exercising every branch. The five
  production-discovered bugs were all unit-testable. Wire into the
  repo's validation scripts. *Effort: M.*
- [ ] **X2. Version stamp + run report.** Supervisor logs its own git
  describe at start (removes wrong-version ambiguity — one operator error
  tonight) and renders `migration/run-report.md` from the metrics/events
  CSVs at exit (timings per phase, attempts, classifications, factory
  rounds) so every retro starts from data. *Effort: S.*
- [ ] **X3. Token/latency budget per phase.** Alert when a session exceeds
  2× the phase median (early wedge detection instead of timeout-cap
  discovery). *Effort: S.*

## 3. Projected profile after implementation

| Phase | Run #3 actual | Target |
|---|---|---|
| A | ~20 min (session) | ~2 min (scripted) |
| B | ~50 min, format abort | ~45 min incl. lint round |
| C | ~7.5 h incl. debt burns | ~4–4.5 h (17 tasks, no stalls) |
| D | ~20 min | ~35 min (full pre-flight) |
| E | ~2 h+, 6 factory rounds | ~30 min, 1–2 rounds |
| **Total** | **~11.8 h** | **~6–7 h, factory-green first push** |

The quality goal is stricter than the time goal: **zero defect classes
discovered by the factory** — the factory confirms, the harness catches.

## 4. Grounding in established practice

The plan is empirical in origin (three instrumented runs) but each pillar
implements a documented industry practice:

| Plan items | Practice | Source |
|---|---|---|
| Root cause ("workspace ≠ factory"); C1, D1, E3 | **Dev/prod parity** (12-Factor, Factor X): minimize the *tools gap*; same build process everywhere, environment differences via config only | [12factor.net/dev-prod-parity](https://12factor.net/dev-prod-parity) |
| C1, D1 (pre-flight = pipeline's own checks) | **CI fundamentals** (Fowler): single-command automated build, self-testing build, *test in a clone of the production environment*, fast feedback, broken builds fixed immediately | [martinfowler.com — Continuous Integration](https://martinfowler.com/articles/originalContinuousIntegration.html) |
| C1 clean-repo builds | **Maven CI practice**: per-build `-Dmaven.repo.local` isolation is the documented way to prove buildability against the real repository; locally-installed artifacts (`mvn install`) leaking into builds is a known CI hazard — precisely the audit-jar escape | [Sonatype — Maven CI best practices](https://www.sonatype.com/blog/2009/01/maven-continuous-integration-best-practices), [Maven reproducible builds guide](https://maven.apache.org/guides/mini/guide-reproducible-builds.html) |
| C1/D1 local gate checks; E2 acceptance gates | **Clean as You Code**: quality gate on *new code*; issues surfaced at edit/commit time (SonarLint connected mode is the documented shift-left channel — headless equivalent: sonar-scanner CLI against the server profile, which is what the harness scripts) | [SonarQube — Clean as You Code](https://docs.sonarsource.com/sonarqube-server/10.6/user-guide/clean-as-you-code), [SonarLint connected mode](https://docs.sonarsource.com/sonarqube/9.8/user-guide/sonarlint-connected-mode/) |
| B1 design-in-packet, C2 ambiguity stop, C4 escalation | **Orchestrator-workers pattern**: the central model decomposes and *specifies* subtasks, workers execute; **evaluator-optimizer** loops require *clear evaluation criteria* — which is exactly why evaluation must be cheap and local (C1/D1), not a 30-min factory round | [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) |
| Phase A–E structure; D1 re-analysis as validation | **Konveyor/MTA methodology**: assess → analyze (rulesets pinpoint the lines) → plan/waves → migrate → validate; the harness's findings-driven tasks and Phase D re-analysis implement its analyze/validate loop | [Konveyor methodology](https://github.com/konveyor/methodology), [Red Hat MTA docs](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/7.1/html/introduction_to_the_migration_toolkit_for_applications/mta-about-the-intro-to-mta-guide_getting-started-guide) |
| X1 supervisor tests, X2 run reports, E1 budgets | **CI discipline applied to the harness itself**: the supervisor is build infrastructure and gets the same bar — automated tests, versioned releases, measurable runs | Fowler CI (above) |

One refinement the sources forced: continuous *full* local sonar scans
per task would be over-heavy; the documented pattern is gate-scoped
new-code checking (Clean as You Code) at milestones and pre-push — which
is how C1/D1 are specified above.

## 5. Implementation plan

Validation vehicle: **run #4** — a fresh autonomous migration on the fully
hardened harness. Its target: ≤ 7 h wall-clock, factory-green first push,
zero factory-discovered defect classes. Already implemented (2026-07-26):
B1 design-in-packet, C2 ambiguity stop, C4 escalation valve, skill
restructure + MAPPINGS catalog + persistence conventions + AGENTS.md
indexes, supervisor layering cleanup.

### Tranche 0 — verification spikes (gate the design; ~1 h, after run #3)

| Spike | Question | Feeds |
|---|---|---|
| S1: timed `mvn clean verify -Dmaven.repo.local=/tmp/m2-run` (cold, then warm) | per-task cost of isolation; per-run seeded repo vs per-task | C1 design |
| S2: headless `sonar-scanner` from the workspace | is it in the image; does scan need a token (reads are anonymous) | C1/D1 design |
| S3: plan-lint prototype vs run #3's real `tasks.md` | would it have caught the heading drift + missing design sections | B2 |

Exit: each of C1/D1/B2 marked *verified / adjusted / rejected* with
measured numbers in this document.

Spike results so far (2026-07-26): **S3 VERIFIED** — the lint prototype
run against run #3's real tasks.md flags 12 infer tasks lacking decided
designs, including T-005 and T-011, the exact two that later exhausted
their worker budgets (~2.5 h + 2 debt entries); B2 is implemented and
wired into the supervisor (one forced revision round on lint failure).
**S2 VERIFIED (adjusted)** — no standalone scanner in the image; the
Maven sonar plugin (the factory's own instrument) works when invoked
fully-qualified, BUT anonymous analysis submission is DENIED ("not
authorized to analyze") — Tranche 1 must provision a SonarQube analysis
token into the workspace. **S1 VERIFIED** — cold isolated-repo seed
≈5–6 min (162 MB, 470 jars, one-time); warm isolated `clean verify` 36 s
vs ~12 s shared. Design: per-RUN seeded repo (`/tmp/m2-run`), seeded
once by the supervisor; per-task premium ≈ +24 s (~+7 min per 17-task
run) buys factory-parity dependency resolution at every sensor.

### Tranche 1 — factory parity (C1 + D1; the quality fix; ~half day)

1. `.hermes/harness/sensors.sh`: `sensor_task` (clean test, isolated
   repo per S1's verdict) and `sensor_milestone` (clean verify + new-code
   sonar check per S2's verdict), called from EXECUTION.md instead of raw
   mvn lines; provision a sonar token into the workspace Secret only if
   S2 proves it necessary.
2. Phase D pre-flight in SHIPPING.md + supervisor: isolated-repo verify,
   sonar gate check, container-profile boot against the dev PostgreSQL
   (catches schema drift pre-push).
3. Acceptance: a seeded defect of each escaped class (local-only jar,
   `@QuarkusTest`-shifted coverage, generator without DDL, style
   violation) is caught at task/Phase-D time in a rehearsal, not by the
   pipeline.

### Tranche 2 — plan hardening (A1 + B2 + B3; ~half day)

1. A1: Phase A becomes a supervisor script step (normalize + summarize +
   commit); orchestrator sessions start at Phase B.
2. B2: `.hermes/harness/plan-lint.py` — parseable ids, findings coverage,
   per-infer-task design section present, UI surface covered/waived;
   supervisor runs it after Phase B, one forced revision round on failure.
3. B3: `tasks.md` skeleton + packet template shipped in the skill
   (templates make B2's checks structural).
4. Acceptance: lint passes run #3's tasks.md only after its known gaps
   are corrected; a deliberately defective plan is bounced with a
   specific revision prompt.

### Tranche 3 — supervisor engineering (E1 + E2 + X1 + X2 + X3; ~half day)

1. E1: per-class round budgets (build/gate/deploy 2 each).
2. E2: success asserts `migration.yaml` acceptance (index page 200 +
   product count) — the waive rule bounded by template acceptance.
3. X1: shellcheck + bats tests for classify/parse/committed/wait-kill
   logic + a mock dry-run mode; wired into stage 080 validate.sh.
4. X2: supervisor logs its git version at start; renders
   `migration/run-report.md` from the CSVs at exit.
5. X3: warn event when a session exceeds 2× the phase median.
6. Acceptance: bats suite green; dry-run exercises every classification
   branch; a rehearsal run report renders.

### Tranche 4 — ecosystem and infra (parallel/backgroundable)

- Evaluate `quarkusio/quarkus-skills` (`migrate-spring-to-quarkus`) for
  adoptable content vs our MAPPINGS catalog; adopt or record why not.
- 27B modelcar graduation (kills the ~28 GB per-start pull) and the MTP
  speculative-decoding experiment (worker decode speedup) in a quiet
  window; T3.2 worker disk resize alongside.
- Keep the konveyor-skills watch item.

### Run #4 — validation

Fresh baseline reset, all tranches live, unattended end-to-end. Measured
against §3's target profile; its run-report (X2) becomes the next retro's
input. Success criterion: the factory confirms, it does not teach.


## 6. Cart-run findings (2026-07-26 evening — measured, not assumed)

Cart run final state: 13/13 tasks + Phase D committed; factory gate:
violations 0, duplication 0, **new-code coverage 24.4% vs 80** (283
lines to cover, 16 tests — 13 of them model-serialization). Two gate
rounds + one operator round consumed. Not shipped.

### Code-quality review verdict (files read, not sampled)

| Finding | Evidence | Class |
|---|---|---|
| **Functional regression: catalog integration erased** | `CatalogServiceImpl` returns a hardcoded fake product list ("Feign client removed during Spring annotation cleanup", invented items/prices); zero references to `CATALOG_ENDPOINT` anywhere; introduced by T-010, an ESCALATED M2 implementation. MAPPINGS decided Feign → MicroProfile REST client; ignored. | Severity 1 |
| Tests don't cover behavior | 24.4% coverage; services/endpoint essentially untested; boundary test is a single smoke | Severity 1 |
| JaCoCo wiring dropped by the pom rewrite | T-002 pom migration removed the scaffold's jacoco property/dep/plugin (repeat of run #2's identical escape); coverage read 0.0 until operator restore | Severity 2 |
| Dead/duplicated scaffolding | `CartServiceApplication` (empty main, should be deleted per MAPPINGS), `ICatalogService` + `CatalogService` duplicate interfaces, misnamed `JerseyConfig` (load-bearing only for `@ApplicationPath`) | Severity 3 |
| Shell-quoting artifact class | empty literal `*.java` files (S1220 trio) — now guarded by the tree-hygiene sensor | fixed |

### Run-behavior facts (from supervisor metrics/events + opencode.db)

- Worker (27B) escalation cause: **subagent-death, not stalls** (see
  `WORKER-ESCALATION-FORENSICS.md`); ~7 of 13 tasks + Phase D were
  implemented by the orchestrator through the valve.
- **Escalated implementations bypassed the quality bars**: no tests
  shipped with escalated code; the catalog regression and the pom
  wiring loss are both escalated-task products. The bars live in
  EXECUTION.md packets; the escalation path never restates them.
- run-log ESCALATED marking is inconsistent (2 rows vs 8 supervisor
  events) — the KPI undercounts at the source of record.
- Gate-fix sessions honored sensor-green-before-commit and burned
  budgets against real red (36 → 8 → 6 across rounds) — the loop
  converges but per-session iteration budgets cap ~10-15 fixes.

### New improvement items (evidence-driven)

- [x] **N1. Escalation carries the full acceptance.** — IMPLEMENTED 2026-07-26. The escalation
  valve prompt must restate the packet bars (tests WITH code, decided
  mappings honored, integrations preserved) and the supervisor's
  post-commit check on escalated commits should include a coverage
  delta, not just compilation.
- [x] **N2. Integration-preservation contract.** — IMPLEMENTED 2026-07-26. `migration.yaml` gains
  a `preserve:` list (external endpoints, env contracts — e.g.
  `CATALOG_ENDPOINT`); plan-lint requires every preserved item mapped to
  a task; the Phase D pre-flight greps the built artifact/config for
  each; acceptance must exercise at least one preserved integration
  (the cart acceptance passed while the catalog was fake — too weak).
- [x] **N3. Build-wiring invariants sensor.** — IMPLEMENTED 2026-07-26. sensors.sh fails if
  `pom.xml` loses the jacoco plugin/property or the sonar path config —
  the T-002 wiring-strip class, now twice observed, becomes a
  deterministic check instead of a factory surprise.
- [x] **N4. run-log/KPI reconciliation.** — IMPLEMENTED 2026-07-26. Supervisor counts ESCALATED
  from its own events (source of truth), and the runbook requires the
  ESCALATED marker in the row it already mandates.
