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

### Session-internals analysis (model logs, not just supervisor logs)

Full per-session times (metrics.csv), task-loop only:

| task | sessions (s) | wall | verdict |
|---|---|---|---|
| T-001..003 | batch 1156 | 385/task | clean |
| T-004..006 | batch 1478 | 493/task | clean |
| T-007..009 | batch 731 | 244/task | clean |
| T-010 | 672+867+202 | 1741 | plan-ordering defect + recovery |
| T-011 | 513 | 513 | clean |
| T-012 | 89 | 89 | resolved-by-scaffold |
| T-013 | 152+58+903 | 1113 | **sfix wedged at budget** |
| T-014 | 932+902 | 1834 | **sfix wedged, did NOT commit** |
| T-015 | 727 | 727 | clean |
| T-016 | 63+447 | 510 | resolved-by-scaffold on retry |

**#1 remaining time sink — wedged sfix sessions (root cause found in model logs):** T-014-sfix ran 902s → `rc=124` (budget kill) having made only ~10 tool calls — but **6 were maven** (`sensors.sh milestone` ×2 + `sensors.sh task` ×2 = four full `mvn clean verify` at ~60-90s each, plus 2 more mvn). The session was fix-one-violation → run-full-maven → repeat; maven cycles consumed the budget before the fixes converged. This is exactly improvement #15 (one-sensor-run discipline). The residual violations reaching sfix are design-level sonar rules autofix can't touch (S6813 field-injection, S2864, S3824) — and for a class still slated for proper conversion later (ShoppingCartServiceImpl → T-020), some of this sfix work duplicates upcoming task work.

**Levers this run surfaces (for the verdict, not applied mid-run):**
1. *One-sensor-run discipline, enforced not just advised* — sfix prompt must say "fix ALL listed violations (each has file:line) in one pass, then run the sensor ONCE"; iterating with full maven between single fixes is the wedge.
2. *Fast sonar-only re-check* — the residuals are sonar style rules; a `sensors.sh sonar` that skips the `mvn verify` (compile already known-green) would cut each verify loop from ~90s to the sonar scan alone.
3. *Field-injection caught early* — a wiring-sensor check for `@Inject` on a field in src/main flags S6813 at the cheap task sensor instead of the expensive milestone-sonar gate.
4. *Don't sfix a class a later task rewrites* — if the sonar-red class is in a not-yet-executed task's scope, defer its style residue to that task rather than spending an sfix now.
5. *Fidelity normalizer misses inner-punctuation spacing* — **found live at T-017**: harvest-fidelity flagged `ShoppingCart.java` for a "dropped" line `if ( sci != null ) {`, but the check is present in the converted class as `if (sci != null) {` — identical behavior, only legacy inner-paren spacing reformatted to standard. `normalize()` collapses whitespace runs (`\s+`→` `) but preserves spaces adjacent to `()[]{};,`, so `if ( x )` ≠ `if (x)` after normalization. This is a FALSE POSITIVE that fires on any converted class whose legacy source used `if ( x )` / `foo( a, b )` spacing — i.e. most services. Fix (next run): in `normalize()` add `s = re.sub(r"\s*([(){}\[\];,])\s*", r"\1", s)` after the whitespace collapse so token-equivalent lines compare equal. This is the second fidelity false-positive class (first: S03's deliberate hardening change → FIDELITY_CHECK waiver). Watched autonomously per the monitor-only mandate — no mid-run patch.
6. **HEADLINE FINDING — the sfix path verifies with the `task` sensor even when a `milestone` check triggered it, so the in-loop milestone gate (fidelity + sonar) is bypassed.** Traced through T-017 and T-020 (both milestone-triggered fidelity reds). Root cause in `supervisor.sh` `post_commit_verify`: the RED is detected with `$SENSOR_KIND` (line 201, = `milestone` on every 3rd task / pom-properties touch), but the sfix PROMPT (line 214) tells the model to "run `sensors.sh task` after each fix and commit when it passes," and the mechanical closure (line 218) also runs `sensors.sh task` — both hardcoded to `task`. The task sensor runs neither fidelity nor sonar. So a milestone red is "resolved" by a task-sensor green that never checked the failing dimension:
   - **T-017**: fidelity (milestone) red → sfix misdiagnosed it (added exception-handling to `ShoppingCartServiceImpl`, never touched the flagged `ShoppingCart`), verified `task`-green, committed. Fidelity still red; unplanned scope injected.
   - **T-020**: same fidelity false positive re-fired → sfix mechanical closure ran `sensors.sh task` (green, no fidelity), committed "sensor-green," advanced. Fidelity still red.
   - Because fidelity runs FIRST in `milestone_sensor`, a fidelity red also masks the sonar check — it never runs. And the same hardcoded-`task` closure would rubber-stamp a REAL sonar red identically.
   **Implication:** the "in-loop milestone gate holds the tree at 0 violations" property is weaker than believed — milestone-only reds (fidelity, sonar) can be papered over in-loop; the Phase E preflight (full milestone) is the true backstop. **Fix (next run):** replace the hardcoded `task` at lines 214 and 218 with `${SENSOR_KIND}`, and after any sfix commit re-run `$SENSOR_KIND`; if still red, burn a retry or record honest debt. This is independent of the false positive (#5) that exposed it — even a genuine milestone red is affected. Watched autonomously per the monitor-only mandate; no mid-run patch.

### T-020 checkpoint (positive — the convergence task)

`ShoppingCartServiceImpl` shipped production-grade wiring: `private final` collaborator fields, `@Inject` constructor injection, and `@RestClient CatalogService` on the constructor parameter — the historically fragile injection point, correct. The earlier S6813 field-injection violations (seen at T-014 on an intermediate state) are fully resolved by the proper conversion, vindicating the T-014 stand-down decision (no two-writer intervention). Constructor injection is the decided MAPPINGS shape and the plan absorbed it (T-017/T-018/T-020 titles say "with constructor injection"). Escalations: T-019, T-020, T-021 were orchestrator-implemented (packet-quality KPI — the endpoint/config tasks the worker packets didn't carry cleanly); T-019 shipped src/main with no test change (coverage-erosion flag, to be closed by T-023 or the factory gate).

## 6. Verdict

(final: wall-clock vs V3, quality gate + semantic review of the shipped service, remaining levers)
