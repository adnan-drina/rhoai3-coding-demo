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

## 2. S03 review (V3 hardening story)

(to be completed when the S03 run finishes)

## 3. V4 baseline (wipe)

(recorded at wipe time: baseline commit, what was kept vs removed)

## 4. Run timeline

| stage | session | start (UTC) | seconds | outcome | notes |
|---|---|---|---|---|---|

## 5. Per-task execution analysis (timing focus)

For every task: duration, sensor time vs model time, retries/fix cycles, and the concrete time lever it validates or refutes (style-autofix hits, batch savings vs the 12-min single-task mean, budget kills, scope reverts).

## 6. Verdict

(final: wall-clock vs V3, quality gate + semantic review of the shipped service, remaining levers)
