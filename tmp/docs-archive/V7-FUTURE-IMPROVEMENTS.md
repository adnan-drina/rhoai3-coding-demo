# V7 / V8 / V9 — future improvements bank

**Purpose:** capture **less-critical** defects and UX gaps so we harden the
harness methodically. **Policy (operator mandate):** before **each** new
migration run, implement **all** open polish rows here, then restart so the
run exercises them. Prefer abort/restart over shipping a compromised run.

**Status:** V9 migration run **complete** — this bank is archived under
`tmp/docs-archive/` with the V9 quality gate. New runs open a fresh bank under
`docs/`.

**Run history:** V7 aborted ([`V7-ABORT.md`](V7-ABORT.md)). V8 wiped for a
clean durability proof ([`V8-ABORT.md`](V8-ABORT.md)). V9 gate:
[`V9-QUALITY-GATE.md`](V9-QUALITY-GATE.md).

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
| L-SHIPLOG | ✅ | SHIP_ONLY mirrored bare `Models: … M4 coding` into outer-loop.log after RUN COMPLETE — looked live. Fixed 2026-07-30: SHIP_ONLY uses `> START SHIP_ONLY` / `OK END SHIP_ONLY`; outer-loop writes RUN COMPLETE footer; git push chatter → `/tmp/outer-git-push.log`. |
| L-M5e | ✅ | Evaluate prompt + post-evaluate `sensors.sh preflight` honesty log; SHIPPING.md forbids false “preflight green” (V8 S02) |

## Orchestration / efficiency

| ID | Status | Notes |
|----|--------|-------|
| O-T6 | ✅ | `try_mechan_commit` when dirty tree + task sensor GREEN |
| O-T6b | ✅ | Mechan-commit / worker auto-commit: `git add -A` then `git reset -- .hermes` (V8 S02 T-002) |
| O-ESCW | ✅ | Worker rc=0 + clean tree + task GREEN → allow-empty “Already satisfied” commit; no MiniMax (V9 S01) |
| O-AC | ✅ | Prose `ALREADY COMPLETE` banned; supervisor/`already-complete.py` only |
| O-B1 | ✅ | `WORKER_FIRST` OpenCode/Qwen for rewrite+infer |
| O-CTX | ✅ | Tighter M1 profile prompt (cite paths, don’t paste whole files) |
| O-DRV | ✅ ops | Restart: `nohup bash tmp/v8-driver-loop.sh >> /tmp/v8-driver-loop.out &` |
| O-DRV2 | ✅ ops | Driver auto-restarts outer-loop on `outer=DOWN` (120s ticks); CRITICAL sentinel — V8 overnight dead-harness gap |
| O-DRV3 | ✅ ops | Driver detects new `T-*` / anomalies → `tmp/V9-TASK-ANALYSIS-PENDING.md` + CRITICAL until detailed gate entry (V9: analysis deferred until human asked) |
| O-DRV4 | ✅ ops | Every tick CRITICAL until chat pulse + `tmp/V9-CHAT-PULSE.ack`; overdue if ack >~2.5× interval (V9 S02 ~12 min silence) |
| O-DRV5 | ✅ ops | Detect new M1–M5 / S0N spec / story-complete → `tmp/V9-M-ANALYSIS-PENDING.md` CRITICAL until comprehensive gate (was docs-only before) |
| O-STY | ✅ | style-autofix: discard `migration/staging/` mutations; `stage_for_task_commit` excludes staging + `.hermes` (V9 S02 T-005) |
| O-RESUME | ✅ | Mid-story resume via `RESUME_STORY`+`RESUME_RUN_BASE` only (never sticky bare `RUN_BASE` — V8 S02 false-skip) |
| O-T6c | ✅ | Escalation / sfix / exhausted-session mechan commits use `stage_for_task_commit` (no `.hermes/` or staging sweep — V9 S01 T-011) |
| O-T6d | ✅ | `mechan-match.py`: refuse mechan/worker auto-commit when staged paths mismatch task (characterization requires `src/test/` — V9 S02 T-006) |
| O-AC2 | ✅ | `already-complete.py`: preserve skip only if token is task subject (title/Goal/Acceptance); strip Story Scope Waivers; instruments lock (V9 S02 T-007) |
| O-AC3 | ✅ | already-complete: missing Target destination .java blocks preserve skip (V9 S03 T-006 CatalogService + CATALOG_ENDPOINT false complete). |
| O-ESCW2 | ✅ | `app_dirt` ignores `.hermes/` + `migration/staging/` for O-ESCW allow-empty (V9 S03 T-001/T-002). Re-run proof on next package/dep noop. |
| O-ESCW3 | ✅ | `escw-eligible.py`: never allow-empty when characterization lacks service tests / missing Target .java (V9 S03 T-008 false green on model-only tests). |
| O-SONARTIME | ✅ | [HONESTY] sfix MiniMax wraps `sensors.sh sonar` in `timeout 60` → exit 124 before sonar finishes (~2–3m). Fixed 2026-07-30: EXECUTION.md + sfix prompt ban timeout <600s on sensors.sh (O-SONARTIME). |
| O-GATE | ✅ ops | Script-cleared quality gates: `v9-clear-task/m-analysis.sh`, escalation/handfix/advance/bank/coolstore lint, debt freeze O-DEBTFRZ, driver watchdog — memory mandates closed (V9). |
| O-DEBTFRZ | ✅ | Supervisor freezes on `record_debt` for task/milestone/sonar (exit 78 / debt-freeze) — no T-002→T-003 silent advance (V9 S04). |
| O-RESTJSON | ✅ | EXECUTION: RestAssured JSON paths under collection (`shoppingCartItemList.find…`) not root `find` (V9 S04 T-002/T-003 — quantity Actual: null). |
| O-RESTEMPTY | ✅ | EXECUTION: empty `pathParam` ≠ 400 (JAX-RS routing 200/405); prefer query/invalid-id tests (V9 S04). |
| O-TESTISO | ✅ | EXECUTION: unique resource ids / `@BeforeEach` clear for RestAssured suites (V9 S04 getCart expected empty, actual size 1). |
| O-OCERR | ✅ | Supervisor extracts surefire/error slice from `/tmp/oc-T-NNN.json` into `.err` when stderr empty (V9 S04 RCA blocked by 0-byte `.err`). |
| O-SFIXSCOPE | ✅ | [HONESTY] Reset RED `T-NNN` / `sensor fix` commits (`refuse_red_task_commit` + sfix HEAD~1); sfix prompt bans out-of-scope-while-RED (V9 S04 T-003). |
| O-TGTNAME | ✅ | task-packet + EXECUTION: Target `.java` basename mandatory; no Endpoint→Resource renames (V9 S04 T-001 O-T6d false escalate). |
| O-HERMNEST | ✅ | supervisor `scrub_hermes_from_git` + app `.gitignore` `.hermes/`; remove nested `harness/harness` (V9 S04 T-001 MiniMax `git add -A` pollution). |
| O-DRV4BODY | ✅ | Chat pulse ack alone invalid — require `tmp/V9-CHAT-PULSE.body` + `tmp/v9-chat-pulse.sh` (V9 agent faked ack without chatting; driver was also DOWN). |
| O-DRV6 | ✅ | Driver emits `V9-DEBT-HOLD-PENDING` when HEAD is `debt: T-… RED` — must not silent-advance (V9 S04 T-002). |
| O-T6e | ✅ | Post-worker: log why auto-commit skipped; `ensure_trackable_packages` + second `try_mechan_commit` before MiniMax (V9 S03 T-007 RCA: worker rc=0 no commit; pre-worker O-T6b was correct). Re-run proof on next infer. |
| O-SFIXLOOP | ✅ | `/tmp/sensor-fix-mode` makes `sensors.sh milestone` exit 2 during sfix; prompt hardened (V9 S03 T-008: 5× milestone). Re-run proof: reset T-008. |
| O-SONARFIX | ✅ | EXECUTION.md teaches S5778/S5976/S2737/S2864/S2925/S1066 (migration-general). V9 T-008 re-run: Qwen wrote tests; autofix+pattern fixes → sonar/milestone GREEN. |
| O-S1066 | ✅ | `s1066-collapse.py` in style-autofix (OpenRewrite `CollapsibleIfStatements` absent from pinned rewrite-static-analysis:1.21.1 — adding it aborted the whole recipe run on V9 T-008). |
| O-PKGDIR | ✅ | plan-lint S-PKGDIR requires `.gitkeep`/`package-info.java`; supervisor drops `.gitkeep` into empty `src/**/java` dirs before mechan. |
| O-KILLREL | ✅ | `.hermes/harness/freeze-harness.sh` + polish-restart use `harness/outer-loo[p]\.sh` relative match. |
| O-M3KILL | ✅ | outer-loop: hermes_rc 137/143 does not spend an M3 plan-lint attempt. |
| O-DRV7DET | ✅ | [HONESTY] Fixed 2026-07-30: `refresh_escalation_pending` now greps `/tmp/supervisor.log` + `/tmp/outer-loop.log` for `committed via MiniMax escalation` / `Actor:.*escalation` (watermark `tmp/V9-ESCALATION-LOG.wm`); secondary commit-subject grep kept. Supervisor also amends escalation tips with `[via MiniMax escalation]` for symmetry with worker labels. |
| O-HANDNOISE | ✅ | [HONESTY] Fixed 2026-07-30: `qg_strip_oc_noise` in `lib-quality-gates.sh`; `v9-handfix-detect.sh` + `v9-capture-diff.sh --oc` pipe through it; agents match is `agents=(UP\|DOWN)/` (not anchored `^agents=`). Busy path clears false pendings. |
| O-ADVTASK | ✅ | [HONESTY] Fixed 2026-07-30: `story_has_advance` requires story id in **header**, rejects `T-\d+` headers, and requires story-level markers (`story complete` / `story gate` / `full-gate` / `ship` / `S0N ADVANCE\|HOLD\|ABORT`). |
| O-DRV3EV | ✅ | [HONESTY] Fixed 2026-07-30: dropped `or len(evid)>20` shortcut; require ≥2 evidence path citations in gate body (or 1 if only one path in the stat file). |
| O-TBTEST | ✅ | Added `scripts/track-b/tests/gate-instruments.sh` covering noise strip, task-vs-story ADVANCE, and uncited evidence rejection. |
| O-REDARCH | ✅ | Fixed 2026-07-30: `refuse_red_task_commit` archives `git show` + `format-patch` to `/tmp/strays/<tag>-red-<ts>/` before `git reset --hard HEAD~1`. |
| O-CATALOGDNS | ✅ | [HONESTY] S04 M5: pipeline green, acceptance 500/503 — `UnknownHostException: catalog-service`; inventory is **not** the catalog (`/api/inventory` ≠ `/api/products`). Fixed 2026-07-30: `k8s/catalog-service.yaml` co-deploy stub; `preserve_env_services_declared` + `root_index_present` in sensors; SHIPPING O-CATALOGDNS + META-INF index rule; specimen `META-INF/resources/index.html`. Trade-off: stub proves co-deployed `/api/products` reachability, not Coolstore inventory integration (gate-recorded). |
| O-CATALOGSVC | ✅ | [HONESTY] `preserve_env_services_declared` used independent `kind: Service` + `name:` greps → Deployment named like the host GREEN without a Service. Fixed 2026-07-30: same-document Python Service.name set only; instrument 17e2. FQDN `*.*` still skipped (wrong-ns soft spot — accepted). |
| O-SHIPNOPR | ✅ | [HONESTY] SHIP_ONLY / up-to-date push: wait_pipeline returned empty → false gate-fix MiniMax burn. Fixed 2026-07-30: fall back to newest PipelineRun; empty/no-trigger → acceptance-only recheck (no gate class). |
| O-FALSECOMPLETE | ✅ | [HONESTY] Agent wrote `S04,complete` / `story-gate-passed (…)` while supervisor-done was still `factory-failed`. Fixed 2026-07-30: `SHIP_ONLY=1`; `v9-ship-only.sh`; `v9-record-ship-only.sh` (reviewed commit author); `v9-ship-only-waiter.sh` waits on `outer-complete`/`S05,complete` only (not outer crash); lint rejects parenthetical subjects; gate-instruments cover record+ready. |

## Story design / plan quality

| ID | Status | Notes |
|----|--------|-------|
| S-LC | ✅ | Scope revert mirrored to outer-loop; SEQUENCING staging-until-owning-story |
| S-RN | ✅ | SEQUENCING: per-path `harvest-from-staging.sh`, no mega package-rename |
| S-FND | ✅ | roadmap-lint: empty findings rejected; `-` HARVEST-only |
| S-SOFT | ✅ | plan-lint: soft prepare/verification-only titles rejected |
| S-CHAR | ✅ | plan-lint: `src/main/.../model/` without any `src/test/` → LINT:S-CHAR (V8 S02 HOLD) |
| S-AC1 | ✅ | plan-lint rejects ceremonial acceptance placeholder / “simple status” tasks (V9 S01 HOLD) |
| S-INFTEST | ✅ | PLANNING.md: after first infer, characterization/verify must be Class infer (V9 S03). M3 prompt still could echo — residual OK. |

## Sensors / gates

| ID | Status | Notes |
|----|--------|-------|
| G-FID | ✅ | Milestone WARN when later-story classes present under `src/main` |
| G-AC2 | ✅ prior | Ceremonial status-map reject; products[] still ship bar |
| G-OK | ✅ | Static reject String/`"OK"` acceptance without catalog fetch |
| G-FAKE | ✅ | products must carry id/itemId; MockCatalogService / hardcoded List.of banned in src/main |
| G-PLACE | ✅ | Task/milestone/static RED on `assertThat(true)` / `assertTrue(true)` / Placeholder stubs (V8 S02 T-005 abort) |
| G-AC3 | ✅ | `acceptance_ship_contract` also runs in milestone sensor (catch status-map OK before deploy; V9 S01) |
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
