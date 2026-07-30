# V7 / V8 — future improvements bank

**Purpose:** capture **less-critical** defects and UX gaps so we harden the
harness methodically. **Policy (operator mandate):** before **each** new
migration run, implement **all** open polish rows here, then restart so the
run exercises them. Prefer abort/restart over shipping a compromised run.

**V7 aborted** (2026-07-29): see [`V7-ABORT.md`](V7-ABORT.md). **V8**
restarted after the polish bank below landed.

**Related:** [`V6-RUN-FINDINGS.md`](V6-RUN-FINDINGS.md),
[`V6-OUTER-LOOP-LOGGING-NOTES.md`](V6-OUTER-LOOP-LOGGING-NOTES.md).

---

## Logging / demo UX

| ID | Status | Notes |
|----|--------|-------|
| L-T1 | ✅ | Task id+title in `outer-loop.log` |
| L-A1 | ✅ | Actor lines (Qwen / MiniMax escalation) |
| L-R1 | ✅ | Outer heartbeat + supervisor quota → `waiting on MiniMax rate limit` |
| L-H1 | ✅ | `/tmp/outer-loop-heartbeat.sh`; single-instance guard ignores it |
| L-N1 | ✅ | Single sink `/tmp/outer-loop.log`; README updated |
| L-P1 | ✅ | `OUTER_LOOP_PLAIN=1` ascii markers |
| L-D1 | ✅ | M1/M2 END enumerates key deliverable paths |
| L-M5e | ⬜ | M5 evaluate must not claim factory/preflight green unless the same preflight bar has passed (V8 S02 overstated evaluate) |

## Orchestration / efficiency

| ID | Status | Notes |
|----|--------|-------|
| O-T6 | ✅ | `try_mechan_commit` when dirty tree + task sensor GREEN |
| O-T6b | ✅ | Mechan-commit / worker auto-commit: `git add -A` then `git reset -- .hermes` (V8 S02 T-002) |
| O-AC | ✅ | Prose `ALREADY COMPLETE` banned; supervisor/`already-complete.py` only |
| O-B1 | ✅ | `WORKER_FIRST` OpenCode/Qwen for rewrite+infer |
| O-CTX | ✅ | Tighter M1 profile prompt (cite paths, don’t paste whole files) |
| O-DRV | ✅ ops | Restart: `nohup bash tmp/v8-driver-loop.sh >> /tmp/v8-driver-loop.out &` |
| O-DRV2 | ✅ ops | Driver auto-restarts outer-loop on `outer=DOWN` (120s ticks); CRITICAL sentinel — V8 overnight dead-harness gap |
| O-RESUME | ✅ | Mid-story resume via `RESUME_STORY`+`RESUME_RUN_BASE` only (never sticky bare `RUN_BASE` — V8 S02 false-skip) |

## Story design / plan quality

| ID | Status | Notes |
|----|--------|-------|
| S-LC | ✅ | Scope revert mirrored to outer-loop; SEQUENCING staging-until-owning-story |
| S-RN | ✅ | SEQUENCING: per-path `harvest-from-staging.sh`, no mega package-rename |
| S-FND | ✅ | roadmap-lint: empty findings rejected; `-` HARVEST-only |
| S-SOFT | ✅ | plan-lint: soft prepare/verification-only titles rejected |
| S-CHAR | ⬜ | Model-harvest briefs that require characterization must keep model-level test tasks (deferring service tests ≠ empty `src/test`) — V8 S02 HOLD |

## Sensors / gates

| ID | Status | Notes |
|----|--------|-------|
| G-FID | ✅ | Milestone WARN when later-story classes present under `src/main` |
| G-AC2 | ✅ prior | Ceremonial status-map reject; products[] still ship bar |
| G-OK | ✅ | Static reject String/`"OK"` acceptance without catalog fetch |
| G-FAKE | ✅ | products must carry id/itemId; MockCatalogService / hardcoded List.of banned in src/main |
| G-PLACE | ✅ | Task/milestone/static RED on `assertThat(true)` / `assertTrue(true)` / Placeholder stubs (V8 S02 T-005 abort) |
| G-PKG | ✅ prior | `com.demo.coolstore` reject |

## Process / repo hygiene

| ID | Status | Notes |
|----|--------|-------|
| P-GIT | ✅ habit | Commit scaffold → `bootstrap-scaffold-repos.sh` (AGENTS + abort doc) |
| P-LOG | ✅ prior | `docs/*-RUN-POLL.log` gitignored |
| P-MON | ✅ | Dual diligence in AGENTS “before each new migration run” |

---

## How to use this file

1. When a run surfaces a **non-blocking** gap, append a row (open).
2. **Before the next run**, implement every open row, instruments, golden sync, restart.
3. Do **not** weaken sensors to clear rows — fix feedforward or probes.
