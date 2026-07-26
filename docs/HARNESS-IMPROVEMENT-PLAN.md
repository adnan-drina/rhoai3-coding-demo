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
