# V4 migration run log — outer loop, full improvement stack, timing focus

Mandate (2026-07-28): review S03, implement every remaining improvement, wipe the V3 artifacts, and rerun the migration end-to-end through the new outer loop — tracking the run closely, analyzing each task's execution for time reductions, while shipping a production-grade Quarkus service. This document is the run's operator log and timing ledger.

## 1. Build record (pre-run, 2026-07-28)

All 17 improvement-list items are implemented (status note in [DRYRUN-M-PROCESS.md](DRYRUN-M-PROCESS.md)). New for V4:

- `.hermes/harness/outer-loop.sh` — drives M1 (analyze.sh + rubric-gated profile) → M2 (lint-gated roadmap, one bounced revision) → per story: M3 spec session (plan-lint-gated) then one `supervisor.sh` child with computed story env (`RUN_BASE`, `PLAN_SCOPE`, `STORY_TASKS`, `STORY_SCOPE`, `PRESERVE_CHECK`, `STORY_DEPLOY`). Story state in `migration/story-state.csv`; failed story stops the run before dependents.
- `.hermes/harness/parse-roadmap.py` — machine roadmap→story-env projection (suite-tested).
- `.hermes/harness/analyze.sh` — Phase A extracted from the supervisor so both entry points share one analysis step.
- Supervisor: `scope_enforce` story-scope sensor (autonomous revert; repair rides the sfix path via `/tmp/scope-violation.txt`); `post_commit_verify` extracted; rewrite-class task batching (`BATCH_MAX`=3, one commit per task, shared post-batch verification); `FIX_PROVIDER`/`FIX_MODEL` routing hooks (inactive by default).
- `dependency-order.py` resolves same-package references (S01 regression case now a suite test). Graphify spike PASSED both bars ([redesign §10](MIGRATION-PROCESS-REDESIGN.md)); integration deferred to V5 where communities pay.
- Skills: MAPPINGS "Production-grade defaults" + SEQUENCING "Production-grade bar" — the six V3 post-ship review defect classes become default target shapes applied DURING migration, so V4 needs no separate hardening story for known classes.
- Instrument suite: 47/47.

## 2. S03 review (V3 hardening story) — SHIPPED AND ACCEPTED 2026-07-28 03:08 UTC

First run with the full improvement stack live. Wall clock 22:34→03:08 UTC (4h34m, including ~25 min of operator pause windows); 7 tasks + Phase D/E/F; pipeline green in 3 min; route `/` 200 and the new `GET /api/cart/acceptance-check` 200 live.

**Quality:** every brief shape landed one-to-one — `ConcurrentHashMap` + `carts.compute()` (T-001), 60s cache refresh-guard with no clear-on-miss (T-002), GET→404 idempotency via `Optional` (T-003), acceptance-check POST→GET with a real DTO (T-004), `@Min` validation + `ServiceExceptionMapper` 400/503 problem details (T-005), dedupe-before-pricing (T-006), and 1014 lines of characterization/concurrency/cache/error tests (T-007). The Phase F retro's artifact review found clean fidelity and no fabrication patterns.

**Improvement-stack firsts, measured:** style-autofix fired pre-sfix (2 files mechanically fixed); the 900s fix budgets killed five wedged fix sessions (V3's worst case was 2702s — the same class now dies in a third of the time); mechanical closure salvaged three green-but-uncommitted fix sessions; the pause point gave two clean intervention windows; the stray sweep fired once (and exposed a design flaw — see below).

**Incidents → codified (all four in golden before run end):**
1. *Fidelity false-positive on hardening stories* — T-003's deliberate interface change tripped harvest-fidelity; the sfix session "fixed" it by editing the staged legacy snapshot. Response: staging restored to the true snapshot; `FIDELITY_CHECK=off` waiver added to sensors.sh (outer loop sets it for `findings: -` stories) + `/tmp/fidelity-off` live-run bridge. Live-proven twice in-run ("fidelity check WAIVED").
2. *Stray sweep destroyed salvageable work* — T-006's session left the brief-required `DedupeTest.java` uncommitted; the sweep deleted it (T-007 later self-healed). Sweep now archives to `/tmp/strays/<tag>/` instead of deleting.
3. *S5838 assertion-chain grind* — 24 of 26 preflight violations were one rule, burning ~57 min of budget-capped fix sessions. `SimplifyChainedAssertJAssertions` empirically validated and added to style-autofix; installed mid-run, it turned preflight green in one 4-minute deterministic pass.
4. *Timeout log lied about the budget* — printed 2700s for 900s-budget kills; now reports the actual budget.

**Timing verdict for V4:** primary task sessions averaged ~14.5 min (in line with V3) — the win came from the fix-path: budget kills + mechanical closures + deterministic autofix cut the fix-class tail. Biggest remaining lever, confirmed by the run's own retro ("sensor red post-commit epidemic," 12 events ≈ 8500s across V3+S03): style debt from test-heavy tasks. V4 attacks it from both ends — the widened autofix recipe set and the production-grade defaults that shape code correctly at authoring time.

## 3. V4 baseline (wipe) — commit `341d4da`, 2026-07-28 03:11 UTC

One commit on top of history (no force-push; V3 evidence stays in git). Removed: `migration/` (bundle, roadmap, briefs, retros, run reports), `specs/` (S01–S03), all V3 `src`. Restored: pristine scaffold `src` + `pom.xml` from golden HEAD, full V4 `.hermes` stack. Kept: round3-stamped `migration.yaml` contracts, devfile, catalog-info, k8s manifests. V3 telemetry archived to `/tmp/v3-archive/`; `/tmp/fidelity-off` and stray archives cleared (migration stories enforce fidelity again). Pod verification: suite 47/47, task sensor green on the pristine scaffold. Outer loop launched 03:12 UTC — the first run where M1→M5 needs no operator launch scripting.

## 4. Run timeline (S01 — the only story; monolith is one bounded context)

Launch 03:12 UTC. **M1→first task = 7 min, zero operator scripting** (V3 required manual launch scripting between every M-stage):

| M-stage | session | seconds | result |
|---|---|---|---|
| M1 analyze (kantra + bundle) | script | ~35 | 24 violations / 47 incidents, source-only |
| M1 profile | m1-profile-a1 | 92 | PROFILE OK (6 sections, rubric-green, 1st try) |
| M2 sequence | m2-sequence-a1 | 78 | ROADMAP OK (1 story, 23 findings, 1st try) |
| M3 specify | m3-S01-a1 | 215 | PLAN OK (27 tasks: 10 rewrite, 17 infer, 1st try) |

All four authoring gates passed on the first attempt — no lint bounces. The 23-finding contract came from the corrected analysis (full target set + custom rules, 1208 kantra rules loaded), versus V3's hand-curated smaller set.

## 5. Per-task execution analysis (timing focus)

Rewrite tasks were batched 3-per-session (improvement #17); infer tasks ran singly.

| task(s) | class | session(s) | wall | min/task | notes |
|---|---|---|---|---|---|
| T-001..003 | rewrite | 1 batch | 1156s | 6.4 | milestone GREEN (fidelity + 0 sonar) |
| T-004..006 | rewrite | 1 batch | 1478s | 8.2 | sensor GREEN |
| T-007..009 | rewrite | 1 batch | 731s | 4.1 | sensor GREEN |
| T-010 | infer (tests) | a1+a2+sfix | 1741s | — | **plan-ordering defect**: test conversion before its classes; session fabricated missing classes, stray sweep archived them, compile-error milestone → sfix pulled class creation forward (202s). Codified in PLANNING.md. |
| T-011 | infer | a1 | 513s | 8.6 | GREEN (classes now present from T-010 sfix) |
| T-012 | infer | a1 | 89s | 1.5 | resolved-by-scaffold |
| T-013 | infer | a1+a2+sfix | 1113s | — | milestone 33 sonar → **style-autofix cleared 25** (33→8) → sfix on residue 8, mechanical-closure committed at budget |

**Batching verdict (rewrite):** 3365s for 9 tasks = **6.2 min/task mean vs V3's 12-min single-task mean — ~48% cut** on mechanical work, exactly the #17 projection.

**Style-autofix verdict:** T-013's 33→8 (25 violations cleared mechanically, incl. the new AssertJ recipe) is the widened recipe set paying off in-loop — the residue that reaches the model is small.

**Recovery machinery (all autonomous, no human):** stray-archive fired (T-010, work preserved not destroyed), scope sensor correctly skipped FQN-form scope, mechanical closure committed 1 green-but-uncommitted session, and the T-010 ordering defect self-repaired. The one genuine cost was T-010's mis-ordered plan — now a PLANNING rule.

## 6. Verdict

(final: wall-clock vs V3, quality gate + semantic review of the shipped service, remaining levers)
