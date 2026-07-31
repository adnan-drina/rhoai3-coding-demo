# V10 — future improvements bank

**Purpose:** bank harness gaps for Stage 080 after `stage-080-baseline`.
**⬜ = due before the next migration run** (blocks `v9-bank-gate.sh all`).
**📋 = later wave** (roadmap only — does not block preflight; see
`tmp/KAI-HARNESS-IMPROVEMENTS.md` §4). Mark ✅ when instruments prove the fix.

**Plan of record:** `tmp/KAI-HARNESS-IMPROVEMENTS.md`.
**Prior bank:** `tmp/docs-archive/V7-FUTURE-IMPROVEMENTS.md` (V7–V9 closed).

Default `BANK_DOC` is this file (`scripts/track-b/lib-quality-gates.sh`).

---

## KAI Wave 1 — shipped + follow-up defects

| ID | Status | Notes |
|----|--------|-------|
| K2 | ✅ | Analysis evidence in `task-packet.py` (caps + MiniMax escalation packet). |
| K1 | ✅ | Incident-file ownership lint + `Absorbs:` + package map + PLANNING.md. |
| K3 | ✅ | Non-mandatory decision table + roadmap adopt/defer (reason). |
| K1-OWN | ✅ | [HONESTY] Fixed 2026-07-30: ownership from Target/Absorbs/Owns only; OOS / “owned by T-” lines excluded; instruments. |
| K1-CONF | ✅ | Fixed with K1-OWN: OOS disclaimer no longer manufactures incident-conflict. |
| K2-RR | ✅ | Fixed 2026-07-30: round-robin one incident per matched Findings rule, then backfill to cap. |
| K2-MATCH | ✅ | Fixed 2026-07-30: exact → rule-id-shaped prefix (`-` required) → guarded substring; bare `springboot` no longer matches. |
| K2-CAP | ✅ | Fixed 2026-07-30: `MAX_EVIDENCE_CONTENT_CHARS = 6×400` combined message+code budget. |

## V10 run — harness honesty (from first live M3)

| ID | Status | Notes |
|----|--------|-------|
| O-M3SKIP | ✅ | Fixed 2026-07-30: outer-loop re-lints present `tasks.md`; RED specs re-enter M3 (no skip-to-M4). |
| S-AC1-V10 | ✅ | Fixed 2026-07-30: plan-lint catches `MinimalAcceptanceEndpoint` / `platform_ready` / `Map.of("status"` (V10 S01 bypass of V9 S-AC1 phrases). |
| O-DRV2-FAILHOLD | ✅ | Fixed 2026-07-30: driver refuses auto-restart when latest outer phase line is `X FAIL`. |
| O-M3ACCLIT | ✅ | PLANNING.md: acceptance.path must appear as full literal; defer on non-deploy stories. |
| O-M3ACCEPT | ✅ | Fixed 2026-07-30: `plan-lint --story-deploy`; non-deploy may omit acceptance.path; deploy requires substance (Poll 11/12). |
| O-ACCEPTREC | ✅ | Poll 50/51: G-CAT + task_sensor; instruments **154/154**. |
| G-CAT-FIXTURES | ✅ | Poll 51: cases 57/93 CatalogService.products(); suite green. |
| G-CATBODY | ✅ |
| O-QJACOCO | ✅ | Root cause: (1) `quarkus-jacoco` must be a **direct test dep** (BOM alone → no `jacoco` feature; Sonar sees 0% on @QuarkusTest). (2) jacoco-maven-plugin: exclClassLoaders=*QuarkusClassLoader, shared jacoco-quarkus.exec, report→target/jacoco-report. (3) quarkus.jacoco.data-file/reuse-data-file/report-location in application.properties. Proved Wake 92: CartEndpoint 52.6% / Impl 93.9% / Acceptance 100% after wiring. |
| O-ACVERIFY | ✅ | Fixed 2026-07-31: `already-complete.py` never preserve-skips Verify/Ensure/Confirm/Validate titles (S05 T-003). Instrument: Verify acceptance + CATALOG_ENDPOINT → rc=1. |
| O-ESCALGPLACE | ✅ | Fixed 2026-07-31: `run_stage` early `committed` path runs `refuse_red_task_commit` (G-PLACE) before success; EXECUTION tip harvest-before-stubs + sensors before close. |
| O-HARVESTSTALL | ✅ | Fixed 2026-07-31: `harvest-from-staging.sh` supports src/test; `preseed-targets.py` + supervisor run_task mechan-preseed missing rewrite Target .java before worker; task-packet FIRST-action harvest (S05 T-001). Instruments: harvest test + preseed seeded. |
| O-M3GOK | ✅ | Fixed 2026-07-31: plan-lint S-AC1 catches `status/ok`, `return "ok"`, `AcceptanceStatus`, `@Path("status")` (S05 ceremonial CartEndpoint draft). Instrument green. |
| O-CATALOGENV | ✅ | S04 M5: in-cluster catalog needs `CATALOG_ENDPOINT=http://catalog-service:8080` on Deployment (not localhost:8081). Proved Wake 98 after Deploy fix r1 `e518a21` — acceptance HTTP 200, 4 products. |
| O-HANDCOMMIT | ✅ | Fixed 2026-07-31: `v9-handfix-detect.sh` also flags recent (30m) `src/` commits while agents idle (Poll 55 remounts). |
| O-WORKERREAD | ✅ | Fixed 2026-07-31: `worker-read-watch.py` + supervisor kill when reads+globs>20 with 0 edit/bash (Poll 55). |
| O-FAILOPEN-DTO | ✅ | Poll 52: catch→DTO/emptyList is fail-open 200; awk now flags any catch→return except throw/Response.status|serverError. | Live MiniMax: catalog fetch + AcceptanceStatus DTO evasion. Require return products()/getProducts(); reject AcceptanceStatus/accepted/degraded. |
| O-M3EVID | ✅ | Fixed 2026-07-30: outer splits existence vs lint — no `\|\| echo missing` on RED. |
| O-M3QUOTA | ✅ | Fixed 2026-07-30: M3 loop detects 429 in session log → sleep 900 → same attempt (not burned). |
| K2-LABEL | ✅ | Fixed 2026-07-30: packet aliases Finds/Finding; plan-lint requires **Findings:**; WARN on zero evidence (Poll 13). |
| O-SUPACCEPT | ✅ | Fixed 2026-07-30: supervisor plan-lint passes `--story-deploy $STORY_DEPLOY` (was re-REDing green non-deploy plans). |
| O-AC-NONJAVA | ✅ | already-complete skips non-Java Targets when preserve token exists anywhere; O-AC3 only guards missing Target .java — migration.yaml/props/k8s doc deliverables skip without file change (Poll 29 T-009). Generalise to missing_target_path + doc-acceptance requires target touched. |
| S-SOFT-NARROW | ✅ | Fixed 2026-07-31: plan-lint `soft_title` anchors `^\s*(verify|ensure|confirm|validate)\b` (Poll 29). Instrument: Verify-title → S-SOFT. |
| O-AC-K8S | ✅ | `tree_has` excludes k8s/; ENV preserve requires src/main (props), deploy adds k8s_has — not k8s-alone (V10 T-003 false already-complete). |
| O-M3QUOTA-GATE | ✅ | Check plan-lint GREEN before O-M3QUOTA 900s sleep / before re-dispatching mchat (V10 S02: green a7121c6 trapped in 429 backoff). |
| O-DELTASTAGING | ✅ | Fixed 2026-07-31: M5 after-analysis rsyncs to `/tmp/kantra-after-src` excluding `migration/staging/`, `.hermes/`, `target/`; SHIPPING.md updated. |
| O-DELTABASE | ✅ | Fixed 2026-07-31: `findings-delta.py` splits RESOLVED / ABSENT-NOT-LANDED / SCAFFOLD-PRESATISFIED + src_main_java/residual METRICs; M5 evaluate + SHIPPING consume `migration/findings-delta.txt` (harvest-nothing → 0 resolved). |
| O-DESTBASE | ✅ | Interim 2026-07-31: `scaffold-presatisfied.txt` + plan-lint omit those rules (like recipe-log); `already-complete` skips when Findings ⊆ presat + Quarkus pom. Full oracle remains **K6** (kantra-on-pristine). |
| O-POM-PRE | ✅ | *Symptom of O-DESTBASE* — closed by scaffold-presatisfied omit + already-complete (2026-07-31). |
| O-THIN-PAD | ✅ | *Symptom of O-DESTBASE* — closed by scaffold-presatisfied omit + already-complete (2026-07-31). |
| O-NOWAIT | ✅ | Implementing agent must not leave supervisor-pause / freeze for human GO — decide+execute resume/abort in-band (2026-07-30). |
| O-REVDOC | ✅ | O-DRV3/O-DRV5 clear requires Implementing note citing sha in `tmp/KAI-WAVE1-REVIEW.md` (`qg_require_wave1_review_note`); gate log alone insufficient — script-enforced handshake (2026-07-30). |
| O-FGRETRO | ✅ | Fixed 2026-07-31: `/tmp/probe-reeval-needed` → `fgretro-reeval.py` reopens ALREADY COMPLETE / Already satisfied skips the hardened probe refuses; `committed()` honors `/tmp/fgretro-reopen.txt`; HOTSWAP re-enter touches probe-reeval. |
| O-ESCWCONVERT | ✅ | Fixed earlier + instruments: WORKER_LAST_RC must be 0; escw-eligible requires @SessionScoped/@Inject when task asks (S04 T-005). |
| O-LATERCDI | ✅ | Fixed: supervisor keep-if-injected when STORY_SCOPE injects an interface the later class implements (S04 CartEndpoint→ShoppingCartService). |
| O-HOTSWAP | ✅ | Fixed 2026-07-31: `/tmp/harness-update` → supervisor pause + `harness-update-ack`; outer re-enters M4 (≤3) instead of S0N,failed on no-done-marker. |
| O-WORKERWEDGE | ✅ | Hung OpenCode burns full 1800s with frozen `/tmp/oc-T-NNN.json` (S04 T-005). Poll 46: sample JSON size in run_worker_task; kill after WORKER_JSON_STALE_SECS (default 300) and write reason to `.err` (also helps O-OCERR-SILENT). Scaffold patched 2026-07-31; live pod file synced — current supervisor process still has old in-memory fn until restart. Probe: killed T-005 at ~23m (rc=143).  Poll 47 DONE live.|
| O-OCSTALL | ✅ | Same class as O-WORKERWEDGE (alias). Prefer O-WORKERWEDGE.  Alias closed Poll 47.| OpenCode worker can hang mid-session with no further json events and no tree dirt for >10m (S04 T-005 ~22m, json stale ~14m). Timeout eventually escalates; need heartbeat/watchdog to kill sooner and/or surface stall in supervisor. |
| O-OCERR-SILENT | ✅ | O-OCERR leaves `/tmp/oc-T-NNN.err` empty on silent truncation (no ERROR/BUILD FAILURE pattern) exactly when escalation needs RCA; fallback: final text + last tools (Poll 32 T-003).  Discharged by O-WORKERWEDGE .err — Poll 47.|
| O-RESTCLIENTDEP | ✅ | Fixed 2026-07-31: MAPPINGS.md Feign row spells `org.eclipse.microprofile.rest.client.inject.RegisterRestClient` + `mvn -q compile` before exit (S03 T-003). |
| O-SONARBLEED | ✅ | Fixed 2026-07-31: `sonar-task-scope.py` — if in-loop Sonar RED is only out-of-task files, skip sfix (no MiniMax bleed). |
| O-SONARORDER | ✅ | Sensor-fix before convert can delete legacy-preserved serialVersionUID / Serializable that a later redesign needs for @SessionScoped passivation (S04 T-003 sfix 86ba62c vs T-005). Prefer transient field for S1948; refuse deleting serialVersionUID literals in sfix. Fidelity skips @Path classes so UID drift won't be caught.  Poll 48: this instance retired (@RequestScoped correct; no Serializable needed). General pre-convert sonar risk remains as O-SONARORDER shape — closed for S04.|
| O-SFIXCREDIT | ✅ | Fixed 2026-07-31: autofix commits use `sensor autofix:`; sfix credit requires HEAD≠PRE_SFIX_HEAD (S04 T-003 false GREEN). |
| O-RESTJSON | ✅ | Fixed: `restassured_contract` REDs root `.body("find {` (O-RESTGUIDE/Poll 53). Instrument green. |
| O-REDATTRIB | ✅ | Fixed 2026-07-31: `_redattrib_gcat` writes `/tmp/red-attrib.txt` (INHERITED-FROM:T-own) before G-CAT fail; supervisor exports CURRENT_TASK. |
| O-CHARWEDGE | ✅ | Fixed 2026-07-31: EXECUTION tip — Target Endpoint*Test first commit before WireMock/pom rabbit holes (S04 T-007). Paired with O-WORKERWEDGE/O-WORKERREAD kills. |
| O-RESTEMPTY | ✅ | Fixed 2026-07-31: `restassured_contract` REDs empty `pathParam("")` + `statusCode(400)` myth. |
| O-TESTISO | ✅ | Fixed: Endpoint*Test RestAssured suites (≥2 cases) require @BeforeEach/UUID/nanoTime; ParameterizedTest counted (O-SFIXCOUNT). |
| O-TESTISO-GETID | ✅ | Poll/remount: `getCartId()` returning `@BeforeEach` field made source==target in set(); sensor isolation false-GREEN. Fix: unique UUID per call. | Poll 53: T-007 no @BeforeEach/UUID; shared literal ids. Sensor requires isolation on *Endpoint*Test. Retest pending. |
| O-MSGCLAIM | ✅ | Fixed 2026-07-31: `msgclaim-check.py` + run_stage resets tip when subject names Service/Endpoint/Impl absent from changed paths. |
| O-ESCWSCOPE | ✅ | Fixed 2026-07-31: LATER_CLASSES guard covers adds+mods; checkout revert for mods; escalation prompt Owns-only + LATER_CLASSES ban. |
| O-REDESIGNREVERT | ✅ | Fixed 2026-07-31: harvest refuses overwrite of CDI/JAX-RS dest with Spring staging (exit 4; HARVEST_FORCE=1 escape). POJO diamond/comment silent revert still fidelity-skip — residual under K7 if needed. |
| O-HARVESTBRK | ✅ | Fixed 2026-07-31: harvest refuses Spring stereotypes into src/main when pom lacks spring-boot (exit 5). |
| O-M4REPLAY | ✅ | Fixed 2026-07-31: outer-loop auto-sets RUN_BASE to `${SID} spec` parent when T-NNN commits already follow the spec (mid-story restart). |
| O-SFIXCOUNT | ✅ | Fixed 2026-07-31: sensors O-TESTISO counts `@Test`+`@ParameterizedTest`+extra `@CsvSource` rows (S5976 parameterization ≠ thinning). sfix prompt: prefer ParameterizedTest. |
| O-SFIXDIRTY | ✅ | Fixed 2026-07-31: failed/no-commit sfix discards uncommitted `src/` dirt before next task (checkout+clean). |
| O-IFACERENAME | ✅ | Fixed 2026-07-31: covered by `redesign-sig.py` (interfaces + converted classes) on task/static sensors. |
| O-REDESIGNSIG | ✅ | Fixed 2026-07-31: `redesign-sig.py` compares public method names vs staging; wired into task_sensor + static. Seed constants still manual/fidelity. |
| O-PKGORD | ✅ | Fixed 2026-07-31: plan-lint rejects package-rename tasks when no `.java` in src/ or migration/staging (Poll 20). |
| K1-SHARED | ✅ | Fixed 2026-07-31: incident-conflict only for `src/**/*.java`; pom/props/k8s still require ownership (Poll 11). |
| S-AC1-NEG | ✅ | Fixed 2026-07-31: plan-lint S-AC1 skips negation lines (no/not/never/… MinimalAcceptance…). |
| K2-SNIP | ✅ | Fixed 2026-07-31: `format_evidence` dedups identical codeSnips; drops head-of-file pom/props/yaml snips (ln≤5 / xml headers). |


## KAI Wave 2 — objective completion (promote K6 for O-DESTBASE)

| ID | Status | Notes |
|----|--------|-------|
| K5 | ✅ | Fixed 2026-07-31: `findings-diff.py` + `sensors.sh findings` on milestone/preflight; scope via PLAN_SCOPE/FINDINGS_SCOPE; FINDINGS_SENSOR_JSON for offline. |
| K6 | ✅ | Fixed 2026-07-31: `findings-oracle.py` (absent→already-complete; present→block ESCW); M1 dest-baseline kantra + `dest-presatisfied.py` → `scaffold-presatisfied.generated.txt` (config/landed only); plan-lint merges generated+static. |
| K7 | ✅ | Fixed 2026-07-31: `failure-sig.py` capture/diff; sfix gets NEW delta; commit claiming pre-existing/out-of-scope while NEW keys exist → reset + debt (K7 refute). |

## KAI Wave 3 — force-multipliers (later)

| ID | Status | Notes |
|----|--------|-------|
| K8 | ✅ | Fixed 2026-07-31: `verify-dep.py` (Maven Central, timeout 5s, WARN offline/unknown); task-packet constraint before adding deps. |
| K9 | ✅ | Fixed 2026-07-31: `append-discovered.py` + task-packet; brief-refresh/retro/run-report consume `migration/discovered.md`. |
| K11 | ✅ | Fixed 2026-07-31: `record_rule_outcomes` → events `rule:<id>`; run-report ## Per-rule outcomes table. |

## KAI Wave 4 — learning & critic (later)

| ID | Status | Notes |
|----|--------|-------|
| K10 | 📋 | Solved-example hints keyed by rule id (after K11; A/B before default-on). |
| K12 | 📋 | Adversarial refute at MiniMax escalation + pre-push ship only. |
| K4 | 📋 | Contract-as-rules expansion from `migration.yaml` (incremental). |

## O-NOPUSHPR — empty-delta M5 ship reuses prior PipelineRun (✅)

**Seen:** S06 ship pushed evaluate SHA but supervisor reported *no new
PipelineRun* and judged an older Succeeded run (`…-push-7k7vn`).

**Fixed 2026-07-31:** `wait_pipeline` takes push-uptodate flag — only
O-SHIPNOPR (Everything up-to-date) may judge an existing PR. When commits
were pushed but no new PR appears (~6m wait), ship **FAIL**s (`none
no-trigger`) instead of greening on a stale Succeeded run.

