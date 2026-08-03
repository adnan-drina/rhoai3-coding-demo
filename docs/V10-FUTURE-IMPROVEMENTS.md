# V10 — future improvements bank

**Purpose:** bank harness gaps for Stage 080 after `stage-080-baseline`.
**⬜ = due before the next migration run** (blocks `v9-bank-gate.sh all`).
**📋 = later wave** (roadmap only — does not block preflight; see
`tmp/KAI-HARNESS-IMPROVEMENTS.md` §4). Mark ✅ when instruments prove the fix.

**Calibration (Poll 76 F4):** post-run ✅ closes of 2026-07-31 are
instrument-proven durableizations; many await **first live exercise** on the
next run's early stories (temporary→durable→re-run). Do not over-read ✅ as
field-proven on a full cart remount.

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
| O-STAGEDPATH | ✅ | Fixed 2026-08-02 (W4-043b): task-packet emits Staged-source under migration/staging using LEGACY package paths from Source/Absorbs + O-STAGEDPATH tip (never targetPackage under staging). Prevents false already-complete on empty ls (v3 S02 T-008 User). Instrument stagedpath-ok. |
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
| O-REVDOC | ✅ | O-DRV3/O-DRV5 clear requires Implementing note citing sha in active review doc (`tmp/KAI-WAVE4-REVIEW.md`; Wave 1–3 archives `tmp/KAI-WAVE{1,2,3}-REVIEW.md`) (`qg_require_wave1_review_note`); gate log alone insufficient — script-enforced handshake (2026-07-30; active doc → WAVE2 2026-07-31; **→ WAVE4 2026-08-02** for Opus 5 shared review). |
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
| O-REDESIGNSIGANNOT | ✅ | Fixed 2026-08-01: `redesign-sig.py` strips comments/annotations before scrape — `@Query("...")` + license `2.0 (...)` were false method names (`Query`, `0`), blocking honest Spring-Data→CDI demotion. Instrument: `O-REDESIGNSIGANNOT`. |
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
| K10 | ✅ | Fixed 2026-07-31: `hint-inject.py` + `write-hint.py`; `task-packet.py` injects ≤3×400-char hints from `migration/hints/<rule-id>.md`; Retro prompt offers write-hint; specimen filter. Instruments. A/B default-on deferred to next live run. |
| K12 | ✅ | Fixed 2026-07-31: `refute-diff.py` + `refute_high_stakes` on MiniMax escalation tip and pre-push ship; REFUTED → reset/debt-freeze or ship-blocked-k12. Optional `REFUTE_LLM=1` orch session. Instruments. |
| K4 | ✅ | Fixed 2026-07-31: `gen-contract-rules.py` emits preserve/forbidden/acceptance/ExceptionMapper rules → `.hermes/rules/generated-contract-rules.yaml`; `analyze.sh` runs it before kantra. Instruments. |

## Post-V10 planning (Poll 76 F3 — bank is sole status authority)

| ID | Status | Notes |
|----|--------|-------|
| O-RETROAPPEND | ✅ | Fixed 2026-07-31: `archive-retro.py` + `phase_f_retro` archives prior `retro-proposals.md` → `migration/retro-history/` before overwrite; INDEX.md; instruments. |
| O-INSTQUAL | ✅ | Fixed 2026-07-31: suite header standard; behavioural fixtures for O-ESCALGPLACE (`early-commit-gate.py`), O-NOPUSHPR (`nopushpr-decide.py`), O-QJACOCO (`sensors.sh qjacoco`), K7 NEW-delta audit. Name-greps demoted to wiring companions. |
| O-WORKERWEDGE-RCA | ✅ | RCA 2026-07-31: V10 wedges were **three classes** — READ_THRASH (explore loop, no mutate), JSON_STALE (OpenCode hang after context burn), TRUNCATION (mid-thought cut on ~64K). Mitigations O-WORKERREAD/O-WORKERWEDGE remain; durable: `wedge-classify.py` + skip further worker seats this story + EXECUTION FIRST-mutate tip. Instruments. Full worker-tier revival (serving/context) remains strategic follow-on, not a cart remount. |
| O-SPECIMEN-CRIT | ✅ | **Wave 2 LIVE 2026-07-31T09:31Z:** outer-loop on `petclinic-rest-v1` (legacy freeze `517a399`). **Authoritative M1 baseline (R-96): 37 rules / 266 incidents** (kantra v0.10.0-beta.1) — replaces PROBE 29/151 (mta-cli 7.3.0); PROBE was selection-only. Cart idle. O-GOLDENFRESH advisory next provision. |
| O-ANALYZERPIN | ⬜ | R-96/F-9: stamp analyzer engine into baseline (`migration.yaml analysis.engine` or sidecar) at M1; `findings-delta.py` WARN/refuse before/after across different engines. Same pin reasoning as specimen SHA. Land before/with M2. |
| O-SIZING-RECIPE | ⬜ | F-9/F-11: gate line for javax-import N-of-113 recipe-covered + M3 ownership tally. Live: recipe-log lists `javax-to-jakarta-import-00001`; S01 scope=`springboot-annotations-to-quarkus-00002` only (9 tasks, plan-lint OK) — javax block likely S02/S03. Still need explicit N-of-113 + “266→owned/recipe/unowned” in M3 gate notes. |
| O-WEDGECTXMET | ⬜ | F-10: on every Wave-2 wedge record frozen JSON size + OpenCode finish/stop reason (opencode.db finish column); adjudicate ~190–196KB / 64K-ctx exhaustion hypothesis. Later (if confirmed): context budget (packet trim / fewer -f) not only liveness kill. |
| O-SFIXNOSPRING | ✅ | Fixed 2026-07-31 (F-21/wake24): after sfix commit, sfix-no-spring.py refuses NEW org.springframework imports / spring-* pom deps vs PRE_SFIX_HEAD (reset). Type-level fidelity inversion tripwire. **O-SFIXNOSPRINGSDATA** 2026-08-01: allow `org.springframework.data.*` imports when pom has `quarkus-spring-data-jpa` (v2 S04 T-005 false reset of fidelity tip restoring `Repository<T,ID>` → O-DEBTFRZ). |
| O-FIDELITYMAP | ⬜ | F-21: source harvest-fidelity approved transforms from MAPPINGS+task Findings (line-scoped); supersede per-incident skips long-term. O-FIDELITYVALID is the validation family instance. |
| O-FIDELITYVALID | ✅ | Fixed 2026-07-31 (wake23): harvest-fidelity skips when staging has BindingResult/FieldError and dest has ConstraintViolation (Spring→Jakarta validation conversion). Wave2 T-004 false RED. Instrument. |
| O-BINDERRDROP | ⬜ | S02 T-003: O-HARVESTSTALL preseed left Spring `BindingResult`/`FieldError` in Quarkus tree (compile RED). Worker deleted `addAllErrors(...)` to green compile instead of Spring→Jakarta `ConstraintViolation` conversion (O-FIDELITYVALID only waives when ConstraintViolation present). Tip/preseed: for validation DTO harvest, apply BindingResult→ConstraintViolation transform in preseed OR block delete-method compile escapes; EXECUTION tip for Harvest *Errors* classes. |
| O-ORFFSHIM | ⬜ | S02 T-007: harvest preseed left Spring `ObjectRetrievalFailureException`; worker added invented `com.demo.util.ObjectRetrievalFailureException` shim (not in staging) so EntityUtils compiles. Prefer approved transform: map Spring ORM exception → `IllegalArgumentException`/`NoResultException` (or task-declared replacement) without fabricating a same-named class; tip/preseed like O-BINDERRDROP. Fidelity may still GREEN if only EntityUtils compared. |
| O-T6dCHARSEC | ✅ | Fixed 2026-08-01: `mechan-match.py` + `escw-eligible.py` truncate task body at any `##` section heading so intermediate titles like `## Model Characterization Tests` (between T-008/T-009) do not leak into prior harvest tasks → false `wants_tests`/`need-src-test` → MiniMax guard-refused escalation despite Person.java already staged. Live S02 T-008: Qwen rc=0 + preseed; O-T6d blocked; MiniMax committed `c5fd34d`. Retest: T-008+Person path → mechan-match rc=0; T-009 still need-src-test. |
| O-SFIXFINDINGS | ⬜ | S02 T-004-sfix: Qwen sensor-fix for HARVEST FIDELITY RED committed `T-004 sensor fix: update findings tracking after scan` (findings JSON only) — BindingErrors `addAllErrors` still missing. Milestone stayed RED → MiniMax rescue. Durableize: refuse sfix commits that touch only `mta-findings*.json` / delta when fidelity/package/compile RED; tip must require dest.java fix first. |
| O-SFIXAUTOLOG | ⬜ | S02 T-008: style-autofix committed `T-008 sensor autofix: partial deterministic style-autofix` touching only `migration/run-log.md` while logging "fixed some violations"; Sonar still RED (S1118 EntityUtils, S1948 ORFF). Refuse autofix commits with no src/** delta when violations remain; do not claim partial fix on run-log-only. |
| O-SFIXSTALL | ⬜ | S02 T-008-sfix: OpenCode sat ~14m with log frozen (8 tool uses, 0 writes) on trivial S1118/S1948; operator killed seat → MiniMax rescue. Add sfix empty-write early-abort (like O-M3EMPTY) when write-count=0 for N min, or deterministic autofix recipes for S1118 (private ctor on abstract util) + S1948 (Serializable/transient on exception fields). |
| O-S1118ABSTRACT | ✅ | Fixed 2026-08-01 (probe+durable tip owed in style-autofix): S1118 on abstract util — keep `abstract` and add private ctor; MiniMax dropped `abstract` → harvest fidelity RED → O-SFIXSCOPE archived honest Sonar fix `8a3668b` and O-DEBTFRZ. Live recover: abstract+private ctor + ORFF transient → fidelity+sonar GREEN; commit after freeze. Add deterministic autofix recipe. |
| O-RESTBATCH | ⬜ | Wave2 T-012/T-013: Qwen JSON_STALE on multi-controller JAX-RS harvest; prefer mechanical harvest-from-staging + annotation recipe batch before worker/MiniMax (pair with O-HARVESTREPO). |
| O-ACREMULTI | ⬜ | Wave2 T-014: Remove-task already-complete skips on first absent leaf (ApplicationSwaggerConfig) without verifying all listed removals/refactors (Roles→@ApplicationScoped). Require all named targets absent/satisfied before absent-oracle skip. |
| O-ACRESTABS | ✅ | Fixed 2026-07-31: is_convert_task blocks absent-oracle for Convert/Port/Harvest/Migrate titles (Wave2 T-013 false PetRestController absent skip). |
| O-FIDSONAR | ✅ | Fixed 2026-07-31: harvest-fidelity strips all `throws …` clauses (T-015: IllegalArgumentException vs Exception still RED; broadened). |
| O-ACCREATE | ✅ | Fixed 2026-07-31 (wake45): Create/Add/Implement titles never already-complete via absent (is_removal_task short-circuit + findings-oracle absent gated). Wave2 T-009 body mentioned "removal" → false skip of missing EntityUtilsMigrationTest. Instrument. |
| O-ACHARVEST | ✅ | Fixed 2026-08-01: `already-complete.py` findings-oracle `absent:` skip now also requires `not is_convert_task(title)` and `not missing_target_path(body)` (O-ACCREATE already blocked Create). Live S02 T-002/T-003: Harvest BaseEntity/BindingErrorsResponse allow-empty ALREADY COMPLETE via `oracle-absent:javax-to-jakarta-import-00001` while target `.java` missing — finding absent because nothing harvested yet. Sensors GREEN (compile vacuous). HOLD→reset to T-001→retest. Related smell: harvest-fidelity GREEN with zero dest classes (bank O-FIDVACUOUS if still vacuous after retest). |
| O-ACSTRUCT | ✅ | Fixed 2026-08-02 (W4-024a): Shape=structure / Target package dir (`→ src/main/java/com/demo/dto/`) must never already-complete via finding-absent while `.gitkeep`/dir missing; `structure_gitkeep_targets` synthesizes `.gitkeep` from Target dirs so `committed()` / O-SCOPEBACKFILL refuse empty-tree skips. Live v3 S01 T-003 `a419d88` ALREADY COMPLETE on `removed-javaee-modules-00020` with `src_main_java=0`. Instrument. |
| O-STRUCTPRESAT | ✅ | Fixed 2026-08-02 (W4 wake42): mechan-match ignores `migration/scaffold-presatisfied*.txt` — dirty O-DESTBASE inventory was staged with `.gitkeep` → false `structure-non-gitkeep` → MiniMax after Qwen rc=0 (T-003). Supervisor reset too. |
| O-ACSTRUCTCOMMIT | ✅ | Fixed 2026-08-02 (W4 wake42): `committed()` refuses allow-empty `ALREADY COMPLETE` for structure Targets; `try_already_complete` stages+commits on-disk `.gitkeep` instead of allow-empty (a419d88/1b1dda7 empty tips while dto/.gitkeep untracked). |
| O-SHIPSTRAYSTRUCT | ✅ | Fixed 2026-08-02 (W4 wake42): M5 ship stray archive skips declared structure `.gitkeep` Targets (was sweeping T-003 deliverable as “fabrication pollution”). |
| O-PLANORDER | ✅ | Fixed 2026-08-01 (F-70/N11): plan-lint consumes `migration/dependency-order.md` + bean-uniqueness on Target paths. Instruments both directions. Retest-owed: re-lint archived S02/S03 plans on fresh M3. |
| O-RULETEST | ⬜ | F-70/N7: kantra test coverage for generated custom rules. |
| O-DEPDELTA | ⬜ | F-70/B7: mvn dependency:list diff at M5. |
| O-ARTIFACTSTATUS | ⬜ | F-70/B5: accepted/modified/rejected/pending per task artifact in K11. |
| O-MODELCANARY | ⬜ | F-70/B3: empirical model canary at preflight. |
| O-RULELINKS | ⬜ | F-70/N6: authoritative doc links into briefs/packets. |
| O-MAPGEN | ⬜ | F-70/N5: derive MAPPINGS from ruleset corpus into M1 bundle. |
| O-GATEACHIEVE | ✅ | Fixed 2026-08-01 (F-70/N14/D2 durable): `gate-achievability.py` classifies coverage-gap ≥15pt as decision-needed; M5 ship blocks without burning MiniMax. Factory keeps 80% bar. Instruments both directions. |
| O-SENSORGATE | ✅ | Fixed 2026-08-01 (F-70/N12): `sensor-gate.py` + commit-msg hook; refuse RED checkpoint commits. Instruments decide/needs-gate both directions. Retest-owed: live T-NNN path. |
| O-FIRSTMUT | ✅ | Fixed 2026-08-01 (R-222/N13): `worker-read-watch` FIRST-mutate — only edit/write count as mutates (bash no longer exempts). Also fix OpenCode `part.tool` parsing (was reading event `type=tool_use`). T-007 live: 23 read+2 bash+0 edit → would kill READ_THRASH before JSON_STALE. Instruments. |
| O-HIBORMGEN | ✅ | Fixed 2026-08-01 (R-223/T-008 `5beb9ec`): Qwen corrected `database-generation` → `database.generation` in all profile files. Main also set to `validate` (was `update`) — watch O-SEEDIMPORT/fresh-DB boot. Skill tip still valuable for MiniMax profile authors. |
| O-T1FINDESC | ✅ | Fixed 2026-08-01 (R-223): `scrub_findings_from_tip` rewrites T-NNN tips that include `mta-findings-current.json`. | S03 T-011 `86e2b61` swept findings again — zero O-T1FINDESC log lines: in-process hotswap resume kept stale functions. Probe scrub → `c42bcd1`. Closed by O-HOTSWAPRELOAD.
| O-HTTPPORT | ✅ | Fixed 2026-08-01 (R-220): `http_port_deploy_contract` in sensors (wiring + milestone) — `quarkus.http.port` must match non-DB k8s `containerPort` or `QUARKUS_HTTP_PORT` env. SHIPPING tip: do not copy legacy `server.port`. Instruments reject 9966≠8080. Live probe restored petclinic props to 8080 + preserve marker rewrite. |
| O-HTTPPORT-TIP | ✅ | Fixed 2026-08-02: task-packet injects hard O-HTTPPORT tip on properties tasks (never copy legacy server.port→quarkus.http.port). Instrument + hot-swap. Witness was v3 S01 T-001 9966→MiniMax. |
| O-INFERDOCEREM | ⬜ | v3 S01 T-004 `b2a97e1` (2026-08-02): Goal "Add Quarkus platform verification and legacy compatibility documentation" but tip is comment-only churn in `application.properties` (no README/docs/verify artifact). Plan-lint or already-complete/sensor: infer Shape=create doc/verify tasks must touch Target path or refuse ESCW/tip. Pair O-ACCREATE / O-ESCWCLAIM. |
| O-ESCALCAUSE-STALE | ✅ | Fixed 2026-08-02 wake#153–156: O-ESCALCAUSE prefers post-worker `sensor-red` (SENSOR RED / O-HTTPPORT logs) over stale pre-worker O-T6d `guard-refused`; guard-refused only when latest `${T}:` log line is still the mechan guard. Instrument escalcause-ok. Retest-owed: next escalate after worker+task RED must write sensor-red cause. |
| O-RECIPEPREPASS | ⬜ | F-65/N16: kantra/windup packaged OpenRewrite recipes (`sb-quarkus.Properties`, jakarta-imports, etc.) as once-per-story mechanical `pre-pass:` before M4 dispatch — zero-token Spring props/javax transforms; workers handle residue. Spec: `tmp/KAI-HARNESS-IMPROVEMENTS-V2.md` §N16. |
| O-NULLACTION | ✅ | Fixed 2026-08-01 (F-70/N17): RUN_CONTRACT + run_stage treats `/tmp/escalation-noaction-<tag>.txt` as guard-refused success (no burn). Instrument wiring. Retest-owed: live escalation. |
| O-ADDLINFO | ✅ | Fixed 2026-08-01 (F-70/N18): RUN_CONTRACT requires `ADDITIONAL-WORK:` section (K9 feed). Parsing into discovered.md still follow-on. Instrument wiring. |
| O-ANTISCOPE | ✅ | Fixed 2026-08-01 (F-65/N19): O-ANTISCOPE line in RUN_CONTRACT — subsequent-steps scope discipline. Instrument. |
| O-ANALYSISPROFILE | ⬜ | F-65/N20: commit `migration/analysis-profile.yaml` (rules/targets/scope); `analyze.sh` reads it; findings-delta refuses cross-profile compare. Companion to O-ANALYZERPIN. Spec §N20. |
| O-PLANEXISTS | ✅ | Fixed 2026-08-01 (F-66/N10): plan-lint RED when Spring→Quarkus BOM/plugin/deps tasks are already satisfied, or remove/@SpringBootApplication / Target .java already absent. Instruments. Measurement protocol: next-specimen before/after; S03 is baseline. |
| O-GENSEED | ✅ | Fixed 2026-08-01 (R-225/R-226): `gen_seed_contract` REDs `sql-load-script` + `database.generation` ∈ {validate,none}. SHIPPING tip. Live probe `5f07ae3` restored `update`. Instruments. |
| O-HOTSWAPRELOAD | ✅ | Fixed 2026-08-01 (R-227/T-011): `hotswap_pause_gate` exits after harness-update clears so outer re-execs fresh supervisor (in-process resume left O-T1FINDESC stale). Instrument. |
| O-PLANHEALTH | ✅ | Fixed 2026-08-01 (R-227/T-011): O-PLANEXISTS RED when actuator→health task and `quarkus-smallrye-health` present with no Spring actuator. Instrument. |
| O-PLANEXISTSSKIP | ✅ | Fixed 2026-08-01 (R-227): O-PLANEXISTS skips task ids already committed (`T-NNN:` in git log) so mid-story re-enter does not force destructive M3 revision. Instrument. |
| O-HOTSWAPLOCK | ✅ | Fixed 2026-08-01 (R-227): outer-loop drops `/tmp/supervisor.lock` and settles 15s before hotswap re-enter (was 5s race). Instrument. |
| O-SPECFROZEN | ✅ | Fixed 2026-08-01 (R-229): refuse mutate `specs/<complete-story>/` — `restore_frozen_specs` in `stage_for_task_commit`, `scrub_frozen_specs_from_tip` after worker/escalation commit, M3 revision prompt scoped to `STORY_TASKS` only. Live probe restored S01 9 tasks. Instrument. |
| O-INFERABSENT | ✅ | Fixed 2026-08-01 (R-231/G5); **Wave4 §2.2 closed 2026-08-03**: WARN→**LINT** — `infer` + *derived* Oracle:absent fails PLAN OK. Proceed paths: `Shape=create` \| `Shape=verify` \| one-line `Proceed: O-NULLACTION`. Supervisor skip + task-packet tip share `oracle_derive.inferabsent_blocks`. Instruments inferabsent-lint/create/proceed + corpus. **Corpus-fireable retest:** `plan-corpus-lint.sh --case s03-32812a6-final` → `hit O-INFERABSENT` (manifest EXPECT_CLASSES). |
| O-ORACLEDERIVE | ✅ | Fixed 2026-08-03 (Wave4 §2.1): `oracle_derive.py` computes Oracle present\|absent from filesystem (legacy test for Target? Target in destination?) — never silent undeclared→present. Wired plan-lint + supervisor `task_oracle` + task-packet. PLANNING.md. Instruments oraclederive-present + inferabsent-pkt. **Retest:** same corpus case + `defaults-inventory.sh --check` (seed refuses stale default-present). |
| O-PCTFILE | ✅ | Fixed 2026-08-01 (R-230/F-68/T-012): `pct_file_contract` REDs `application-%*.properties` (literal `%` in filename). SHIPPING tip: use `application-{profile}.properties` or `%profile.key=` keys. Live tip `4032cdf` reset; instruments. |
| O-PLANPROP | ⬜ | R-226: extend O-PLANEXISTS to property conversion — WARN when converted property names a package/class with zero occurrences in target tree (T-009 `org.springframework` log category on Quarkus-only app). |
| O-T2ALREADYQ | ⬜ | S02 T-002 `2f7e02a`: task title 'remove Spring Boot' but scaffold was already Quarkus — worker only added hsqldb + datasource/root-path props. M3/plan-lint should detect already-satisfied BOM/deps (or AC) so packets don't overclaim Spring removal. |
| O-CLASSPROMPT | ✅ | Fixed 2026-08-01: TASK_CLASSES uses task-packet Class field parser (`**Class**: rewrite` no longer false-infer). Instrument. |
| O-BRIEFCONF | ⬜ | F-32: briefs have no conformance vs migration.yaml DB contract. When needsDatabase+dbService set, deploying story brief must name schema/seed deliverable and must not propose multi-DB primaries (S03 petclinic brief contradicts DECISION-DB). |
| O-SFIXWRONGDIM | ⬜ | Harness: sfix prompt + EXECUTION route FINDINGS→`sensors.sh findings`. Awaiting next FINDINGS-RED sfix to prove no ceremonial polish (witness was `2d095f2`). |
| O-SFIXSKIPFIDELITY | ⬜ | v3 S02 T-003 (2026-08-02): after Qwen sfix `effd47c` (wrong-dim S6204), supervisor logged **O-SFIXWORKER — milestone GREEN after Qwen (skip MiniMax)** based on sonar-only GREEN, then full milestone still FIDELITY RED → O-SFIXSCOPE archive + **O-DEBTFRZ** `09e216a` without spending MiniMax rescue≤1. Durableize: skip-MiniMax only when the *triggering* RED dimension (fidelity here) is GREEN — never promote sonar-only to milestone GREEN. Pair O-SFIXHINTFIDELITY / O-SFIXWRONGDIM. |
| O-SFIXHINTFIDELITY | ✅ | Fixed 2026-08-02 (wake22): sensors.sh persists FIDELITY to /tmp/sensor-fidelity.log + sensor-milestone.log + /tmp/sensor-fix-dim before mvn; supervisor `sfix_red_dims` names primary dim; `sfix_loop_recheck` runs all cited cheap dims (not sonar-only). Hot-swapped. Retest-owed on next fidelity RED sfix. |

| O-SFIXMETRICS | ✅ | Fixed 2026-07-31: scaffold default + MAPPINGS tip + sfix FINDINGS route; live probe `9a9917f` → milestone FINDINGS GREEN (K5 metrics cleared). |
| O-AUTOFIXJSON | ⬜ | S02 T-002 `e4cf22d`: 'sensor autofix' commit is only `mta-findings-current.json` churn (kantra refresh), no style/code fix — mislabeled. Exclude findings-current from autofix commits; don't call JSON refresh autofix. Ties O-T1FINDINGS. |
| O-T1FINDINGS | ✅ | Fixed 2026-08-01 (R-219): `stage_for_task_commit` resets `migration/mta-findings-current.json` (with .hermes/staging). Wave2 S03 T-004 `4888bdc` was findings-only wrong-title mechan — excluded going forward. | R-223: instrument upgraded from grep to behavioural stage fixture.
| O-M3PRESERVE | ✅ | Fixed wake70: PLANNING.md — preserve tokens must appear **verbatim** in tasks; redesign §7 decisive tokens (`thread-safe`, etc.) in same task body as class. Hot-swapped; S02 draft tasks probe already plan-lint GREEN during O-M3QUOTA backoff. |
| O-SHAPEDECL | ✅ | Fixed 2026-08-01 (F-70/F-28): plan-lint **Shape** field; live M3 sets `PLAN_LINT_REQUIRE_SHAPE=1` (instruments WARN). PLANNING tip. Retest-owed: next M3. |
| O-SHAPELINT | ✅ | Fixed 2026-08-02 (W4 wake41): plan-lint RED when Shape=structure lacks package/.gitkeep Target — property converts must use modify/create. Live v3 S01 T-002 was Shape=structure → O-STRUCTTGT `.gitkeep`-only packet burned Qwen. Spec tip `169b3f3` Shape→modify; instrument. |
| O-ACORACLE | ✅ | Fixed 2026-07-31 (wake28): try_already_complete handles oracle-absent:. |
| O-ACFIRST | ✅ | Closed 2026-07-31 (F-24/F-25): T-005 vs T-006 asymmetry was **pre-fix vs post-fix of O-ACORACLE** (landed wake28), not late already-complete ordering. Post-fix path is oracle-before-dispatch. Residue: false debt-freeze ledger row → O-LEDGERFALSE only. |
| O-T6DREMOVAL | ✅ | Fixed 2026-07-31 (R-104): mechan-match accepts empty stage when removal targets absent. |
| O-T6DOWNERSHIP | ⬜ | F-20/R-103/R-104: O-T6d assumes create/modify; misfires on absent/removal. Predict T-006 reject, T-007/8/9 pass. F-20/R-103: invert O-T6d OR give structural tasks an explicit path manifest (Wave2: O-T6d rejects structure 2/2, passes harvest 2/2). F-20: invert O-T6d — refuse only on positive wrongness (other-task ownership / later-story / harness ignore). Reuse K1 plan-lint ownership map; stop whitelist-from-task-text. Fixtures: Wave2 unexpected-paths, empty-stage, structure-non-gitkeep; control T-002. Before more tolerance patches. |
| O-STRUCTINFO | ✅ | Fixed 2026-07-31 (wake17): mechan-match — package-info *tasks* (title) not structure-only; structure soft path allows package-info.java as well as .gitkeep. Wave2 T-003: Target "package structure" → structure-non-gitkeep after Qwen wrote package-info → false MiniMax guard-refused. Instruments. |
| O-REVERTFINDINGS | ✅ | Superseded/closed by **O-REVERTPURE** (2026-08-02): scope-revert commits stage only reverted paths via `stage_scope_revert_paths` (explicitly resets `mta-findings-current.json`). Was: v3 `5554158` bundled findings (+3699).
| O-REVERTPURE | ✅ | Fixed 2026-08-02 (W4-010): `scope_enforce` never `git add -A` on scope revert — `stage_scope_revert_paths` stages only reverted paths and unstages `migration/mta-findings-current.json` / `.hermes` / staging. Instruments. Closes O-REVERTFINDINGS.
| O-STRUCTREVERT | ✅ | Superseded/closed by **O-SCOPEBACKFILL** (2026-08-02): after scope revert, restore missing structure Target `.gitkeep` + refuse `committed()` while Target absent. Was: v3 S01 T-003 `5554158` left `com/demo/model/` absent while ledger ✓.
| O-SCOPEBACKFILL | ✅ | Fixed 2026-08-02 (W4-010): after `scope_enforce` / SCOPE REVERT, if Shape=structure or Target ends with `.gitkeep` and Target still missing → mkdir + touch `.gitkeep`, commit clear `${T}:` tip (not scope-revert subject alone); `committed()` returns false while structure Target absent. Instruments. Closes O-STRUCTREVERT. **Live v3 cleared 2026-08-02:** operator/`T-003:` tip `0b07664` created `model/.gitkeep` during O-HOTSWAP clear; durable path remains for future seats.
| O-STRUCTTGT | ✅ | Fixed 2026-08-02: task-packet gates O-TGTNAME on Shape=structure / Target `.gitkeep` — emit `.gitkeep` path only (no Absorbs `.java` scrape); O-STRUCTTGT tip + suppress harvest-first on structure seats; EXECUTION tip; instrument. Live proof was T-003 `b619fd5`→`5554158` scope revert. **Retest PASS 2026-08-02:** T-005/T-006/T-007/T-008 Qwen seats all `.gitkeep`-only (no Absorbs harvest / no scope revert). O-SCAFFOLDDIR remains backstop.
| O-ESCWSTRUCTTGT | ✅ | Fixed 2026-08-02: refuse allow-empty while structure Target absent; reset false Already-satisfied tip; escw-eligible missing-gitkeep. Witness wipe S02 T-001 `51dad87`→`f016532`. Pair O-SCOPEBACKFILL. |
| O-STRUCTPKGINFO | ✅ | Fixed 2026-08-02: `structure_gitkeep_targets` hyphen-safe + Owns/Target only — no `…/package/.gitkeep` ghosts from `package-info.java`, no legacy Source paths. Stops false `committed()` RED after real package-info tip (S02 T-001 MiniMax thrash). Instrument. |
| O-T6PARTIALHARVEST | ⬜ | v3 S02 T-002 (2026-08-02): mechanical O-T6 tip `f0a1008` claims Harvest BaseEntity/NamedEntity/Person but numstat only `BaseEntity.java` (+49); NamedEntity/Person absent on disk after GREEN task sensor. O-HARVESTSTALL preseeded only BaseEntity. Durableize: mechan verify-and-commit must require all Target basenames present (or fail/escalate) before `${T}:` tip; pair O-HARVESTSTALL multi-target preseed. |
| O-ESCW3LEGACYPKG | ⬜ | v3 S02 T-001 (2026-08-02): Target `src/main/java/com/demo/model/.gitkeep` already on disk from S01 (`0b07664`); Qwen wrote/verified (rc=0, write=1, no git dirt) → O-T6e → **O-ESCW3 skip allow-empty** citing `missing-pkgdir:src/main/java/org/springframework/samples/petclinic/model/` (legacy path) → false MiniMax escalation. Durableize: missing-pkgdir / ESCW3 deliverable checks must use Target/targetPackage paths from tasks.md (or migration.yaml targetPackage), never legacyPackage tree; if Target `.gitkeep` present → already-complete / ESCW allow-empty, not escalate. Pair O-ACCREATE / O-ESCWSTRUCTTGT. |
| O-ESCWCLAIM | ⬜ | W4-014 / v3 S01 T-009 `8ffd61f`: O-ESCW allow-empty on Goal "claim … incidents/findings" while `migration/findings-delta.txt` still lists REMAINING in that class (pom residuals 00030/00050). Worker named two already-clear rules and generalised. Durableize: refuse ESCW allow-empty when Goal/Findings reference incidents and after-scan (or findings-delta REMAINING) still has matching class — require residual enumeration or debt row. Sibling/extension of O-ESCWSTRUCTTGT.
| O-ESCW3PKGDIR | ✅ | Fixed 2026-08-02 (wake22): escw-eligible package-structure checks Target/→ dirs under targetPackage only; ignores legacyPackage Absorbs/Source paths. Instrument rc=0 + hot-swap. |
| O-T6COMPLETE | ✅ | Fixed 2026-08-02 (wake22): mechan-match create/harvest requires all Target basenames present (disk∪staged); partial→missing-targets rc=1. Instrument + hot-swap. |
| O-ESCEMPTYTGT | ⬜ | W4-016c / S02 T-001: Qwen already-satisfied `.gitkeep` (S01 backfill) → O-T6e + MiniMax escalation → empty tip `e1d6248`. Extend O-SFIXNODELTA / already-complete / ESCW to refuse MiniMax escalation when Target path already exists and tip would be empty. Pair O-ESCW3PKGDIR.
| O-LEDGERATTR | ⬜ | W4-014a: T-009 claim credited OpenRewrite M1 for metrics/pom clears actually landed by misattributed T-004 sfix `2550243`. Ledger correction note or one-line commit before treating S01 as history; pair O-SFIXNODELTA (prevents new) + O-SFIXNAMING.
| O-SFIXFIDELITY | ✅ | Fixed 2026-08-02 (wake22): when primary=fidelity, SFIX_PROMPT pastes FIDELITY: lines + O-FIDELITYSORT recipe and forbids sonar-first chase. Pair O-SFIXHINTFIDELITY. Hot-swapped. |
| O-SFIXFALSEGREEN | ✅ | Fixed 2026-08-02 (wake22): skip-MiniMax only after multi-dim `sfix_loop_recheck` GREEN (cited dims; default fidelity+sonar). Closes sonar-only false GREEN that skipped MiniMax while fidelity RED. Hot-swapped. |
| O-M5NEWAFT | ⬜ | W4-014b: M5 `new_after=2` (`demo-env-integration-00001`, `jakarta-jaxrs-to-quarkus-00010`) unowned while debt.md still shows `(none)`. new_after must land in debt.md or follow-up Owns before story ADVANCE.
| O-SCAFFOLDDIR | ✅ | Fixed 2026-07-31: mechan-match ignores migration/discovered.md (+ run-log/mta-findings-current); structure tasks accept gitkeep-only under src/{main,test}/java/ (test mirrors OK); refuse real .java in structure-only stage. Root cause T-001: discovered.md tripped unexpected-paths. Instruments. Stray/escalation packet + structure sensor remain O-STRAYSCAFFOLD. |
| O-PAUSEWORKER | ✅ | Fixed 2026-07-31: run_task() loops on /tmp/supervisor-pause (same as orch). Wave2 HOLD: pause only gated MiniMax orch — WORKER_FIRST OpenCode advanced T-002/T-003 anyway. Live freeze: debt-freeze + pause. |
| O-PAUSEREASON | ✅ | Fixed 2026-07-31 (R-100): pause/debt-freeze markers carry HOLD reason text (not timestamp-only); live markers rewritten. |
| O-SUPCMDLINE | ✅ | Fixed 2026-07-31 (wake14): abandon pgrep -f single-instance (false S01,failed on oc-exec -lc and residual matches). **O-SUPFLOCK**: exclusive flock on /tmp/supervisor.lock for process lifetime. |
| O-OUTERFLOCK | ✅ | Fixed 2026-07-31 (F-18/wake15): outer-loop single-instance uses flock /tmp/outer-loop.lock; probes supervisor.lock without retaining it. Replaces pgrep -f (observer-induced refuse). |
| O-PACKETFIELD | ✅ | Fixed 2026-07-31 (wake15): task-packet.field accepts **Class: rewrite** (colon inside bold). Was defaulting Class→infer for T-003 packet while supervisor routing still rewrite. |
| O-LEDGERFALSE | ✅ | Fixed 2026-08-01 (F-70/F-60): findings-delta splits DEFERRED-BY-DECISION via migration/deferred-by-decision.txt; reports in_scope_resolve_pct (ceiling 17/(28−N)). Retest-owed: next M5 evaluate with deferred list. |
| O-ESCALORACLE | ✅ | Fixed 2026-08-01: task-packet emits Shape+Oracle (+ O-ESCALORACLE constraint); supervisor escalation prompt surfaces them and forbids fabricate-delete. Instrument. Extends F-13 / O-ACORACLE. |
| O-PROCALIVE | ⬜ | F-18: consolidate flock/argv-alive helper for supervisor, outer, watchdogs, gate scripts + fixture for oc-exec-shaped cmdline. Cousin of O-GUARDCOMP. |
| O-HOTSWAPBUDGET | ✅ | Fixed 2026-08-01: hotswap re-enter budget 3→8 + 5s settle; rapid kill+re-enter race false-failed S03 (28d5cdc). Superseded in story-state. |
| O-HOTSWAP-INFLIGHT | ✅ | Fixed 2026-07-31 (wake14): /tmp/hotswap-inflight sticky across re-enter so clearing harness-update-ack cannot turn a failed re-exec into false S0N,failed on second no-done. |
| O-KILLREASON | ✅ | Fixed 2026-07-31 (R-100): run_worker_task kills on pause/debt-freeze and writes reason(+marker text) into oc-T-NNN.err; backfill if .err empty after freeze SIGTERM. |
| O-WEDGECLASS | ⬜ | F-12: wedge-classify.py must not return TRUNCATION without size/finish evidence (JSON near ~190–196KB ceiling band or opencode length finish). T-001 false-positive at 22KB mutation-positive rc=0. |
| O-STRAYPKGINFO | ✅ | Fixed 2026-07-31 (F-19/wake19): stray sweep keeps package-info.java under src/{main,test}/java/ (not only .gitkeep). Hazard was thin-escalation wipe of Qwen package-info; T-003 HEAD already had all 4 (caught-or-clean). KEPT-SCAFFOLD.txt. |
| O-STRAYSCAFFOLD | ✅ | Fixed 2026-07-31: post-commit stray sweep keeps src/{main,test}/java/**/*.gitkeep on disk (writes KEPT-GITKEEP.txt); archives other src/ strays only. R-100: discard proven harmful (9/12 recreated). Partial restore 2d6304d. Structure-task sensor acceptance still ⬜ follow-on. |
| O-GUARDCOMP | ⬜ | F-13/F-19/F-23: guard-interaction defects + **tolerance must widen never narrow** (O-SCAFFOLDDIR gitkeep-only → T-003). Composition fixtures + O-DRV3 diff-read. F-23: every oracle/guard needs **end-to-end branch fixtures** per verdict (absent → skip-before-worker; present → block-ESCW) — component stdout alone missed O-ACORACLE consumer wiring until T-005 burned MiniMax. Specimens: T-001 O-T6d×stray×fidelity; T-003 structure-non-gitkeep; T-005 oracle-ignored dispatch. |
| O-ESCALCAUSE | ✅ | Fixed 2026-07-31: cause file + events. **Re-fixed 2026-08-02 (W3-143):** classify from O-KILLREASON `.err` (`supervisor-pause`/`debt-freeze`/`read-thrash`/`worker-wedge`/`sigint`); **O-ESCALPAUSE** suppresses MiniMax on pause/debt kills (was constant worker-failed 11/11). |
| O-SKEL-CATALOG | 📋 | R-87: RHDH migration skeleton still deploys `catalog-service` into non-Coolstore namespaces (seen in `petclinic-rest-v1-dev`). Gate behind values / specimen needs, or document always-on. Harmless at rest; avoid false wiring checks. |
| O-WAKE-GROK | ✅ | Fixed 2026-07-31 (F-5): `tmp/v10-smart-wake-loop.sh` W1 label pod (`V10_WS_NAME=petclinic-rest-v1`), W2 `V10-GROK-HEARTBEAT` idle default 600s, W3 `MIN_EMIT_GAP_S=120` (nudge exempt), W4 `MAX_QUIET_S=900` timer, W5 `V10-WAKE-EMIT.last` + redeliver + DELIVERY-BROKEN osascript. `lib-quality-gates.sh` `qg_ws_pod` label resolve. Lock + never `pgrep -f` wake path. Behavioral instrument suite still 📋 follow-on. |
| O-WAKE-CATCHUP | ✅ | Fixed 2026-07-31: wake emits refresh `scripts/track-b/v10-review-catchup.sh` → `tmp/V10-REVIEW-SINCE-LAST.md` (full slice after last Implementing note); opens `V10-REVIEW-CATCHUP-PENDING` (+R / reason=catchup) until newer Implementing note + `… catchup.sh ack`. Prompt + stage-080-track-b rule; not memory-only. |
| O-REVIEWDOC | ✅ | Fixed 2026-07-31 (operator): lead notes must identify **Agent: Grok (lead)**, list **Reviewed:** / `ACK:R-|F-|O-` for other agents' entries, state live action, close `— Grok (lead)`. `v10-review-catchup.sh ack|check` enforces; wake prompt + stage-080-track-b + AGENTS.md. Chat pulse ≠ audit trail. |
| O-STAMP-AUTO | ✅ | Fixed 2026-07-31 (F-4): `contract-stamp.py` at outer-loop entry before M1; RequestMapping GET + ResponseEntity&lt;Collection&gt;; getAll* rank; prefer existing path; refuse UNDECIDED overwrite; PyYAML-less load/dump preserves provenance. Dogfood `petclinic-rest-v1` @ `6de6c05` → `/petclinic/api/vets` `_array` + evidence targetContract. Instruments 229 (+ petclinic gate GREEN). |
| O-STAMP-GATE | ✅ | Fixed 2026-07-31: `contract-stamp-gate.py` + minimal YAML loader (no PyYAML); verifies package/path/UNDECIDED; wired in outer-loop after stamp. |
| O-STAMP-TEMPLATE | 📋 | Next specimen: template shrinks to name + legacy URL + neutral sentinels (not cart defaults); harness fills the rest. |
| O-GOLDENFRESH | ✅ | Fixed 2026-08-03 wake#387: `scripts/track-b/v10-golden-fresh.sh` write/read `.hermes/harness/.published-fp` (digest excludes stamp); three-way repo==published==pod in `v9-preflight-outer-start.sh`; `bootstrap-scaffold-repos.sh` stamps staged+SoT before push. Instruments goldenfresh-wire/stamp/red. Skip: `V9_SKIP_GOLDEN_FRESH=1`. Distinct from O-HERMESPREFLIGHT. **Retest-owed:** next provision after bootstrap must GREEN three-way; unpublished harness edit must RED `--check-local`. |
| O-PKEXAMPLE | ✅ | Fixed 2026-08-01: outer-loop builds `PKG_RENAME_HINT` from migration.yaml `legacyPackage`/`targetPackage` (M2/M3 prompts). Retest-owed: next M2/M3 session packet shows specimen packages, not Coolstore. Was: hardcoded `com.redhat.coolstore.X → com.demo.X`. |
| O-M2CEREMONY | ✅ | Fixed 2026-08-01: SEQUENCING unique-ownership tip + M2 a1/a2 prompts name LINT:coverage/substance/deploy. Live v2 probe: dropped S07 dual-claim of `springboot-di-to-quarkus-00003` → lint GREEN (`753a3cc`); outer restart resumes M2-skip → stories. Retest-owed: next fresh M2 a1 avoids dual-owner without hand patch. |
| O-OUTERSTALE | ⬜ | Preflight/O-DRV2 restart can no-op when `/tmp/outer-loop.lock` holds a dead pid (v2 post-M2-fail: lock pid 2280 dead; `pgrep -f outer-loop` also false-positive on oc-exec). Fix: start path treats lock pid `kill -0` fail as stale and clears; avoid pgrep -f for liveness. 2026-08-01. |
| O-FLYWAYDEP | ⬜ | v2 S03 deploy tip `6fc1f51` added `quarkus-flyway` to pom without committed SQL migrations (MiniMax deploy-fix residue). Prefer drop unused dep or require real migration scripts; do not leave empty Flyway on classpath for readiness theater.
| O-ENTITYDSPROD | ✅ | Fixed 2026-08-01 v2 S03 deploy: O-ENTITYDS unprofiled H2 made factory inject postgres JDBC URL into H2 driver (`Driver does not support the provided URL`). Default=`postgresql`; H2 only `%dev`/`%test`. Live tip `5baa60d`. Refines O-PREFLIGHTH2 vs O-ENTITYDS conflict. Do not add Flyway to clear readiness.
| O-SHIPBUDGET | ✅ | Fixed 2026-08-03 wake#194–197: after fix-round budget, one untimed closing preflight; GREEN→push; still RED→`ship-blocked-preflight-budget` + debt (boot-specific when Schema-validation/missing table). Removed `pushing anyway (factory as arbiter)`. SHIPPING + instrument. Retest-owed: next M5 ship budget-exhaust path. |
| O-BOOTNOFLYWAY | ✅ | Fixed 2026-08-03 wake#194–197 (amended wake#198–199 as O-BOOTDEVPG): `boot_check` prod-validates DEV Postgres when schema provenance exists; else DEV Postgres + `QUARKUS_HIBERNATE_ORM_DATABASE_GENERATION=drop-and-create` — stops false `missing table [owners]`. First cut used `QUARKUS_PROFILE=dev`/H2 and hit driver mismatch (build-time postgresql). SHIPPING + instrument. Retest-owed: S02 M5 closing preflight boot. |
| O-BOOTDEVPG | ✅ | Fixed 2026-08-03 wake#198–199: entity-before-Flyway boot must NOT set `QUARKUS_PROFILE=dev` (H2 URL vs prod-baked postgresql driver → `Driver does not support the provided URL: jdbc:h2:…`). Keep `DEV_DB_URL` + override generation=drop-and-create. Hot-swapped. **Retest 2026-08-03 wakes#202–206:** closing preflight @`64881c8` **boot GREEN** (`O-BOOTDEVPG DEV Postgres drop-and-create`). |
| O-BOOTSQLPROV | ✅ | Fixed 2026-08-03 wake#201: `boot_check` schema provenance = Flyway/Liquibase migration files only — `sql-load-script` no longer sets `has_schema_prov` (keeps O-BOOTDEVPG drop-and-create). `gen_seed_contract` REDs `%prod.sql-load`+`%prod.validate`. SHIPPING tip + instruments. **Retest 2026-08-03 wakes#202–206:** clean tip `64881c8` closing preflight **boot GREEN** (O-BOOTDEVPG path; no import.sql / no sql-load). |
| O-SHIPNOPRSTALE | ✅ | Fixed 2026-08-03 wakes#202–206: M5 ship stamps `/tmp/ship-session-started`; uptodate O-SHIPNOPR judges a PipelineRun only when creation ≥ session start **and** `revision` matches HEAD (`shipnoprstale-decide.py`). Pre-session Failed/Succeeded → wait briefly for post-session PR else `ship-blocked-stale-pipeline` HOLD (no Deploy-fix). SHIPPING + instruments. Retest-owed: S02 M5 ship resume @`64881c8` with fresh PipelineRun. |
| O-SHIPFIXJACOCO | ✅ | Fixed 2026-08-03 wake#201: `wiring_invariants` REDs when `quarkus.jacoco.data-file` set without `report`/`report-location`. SHIPPING tip + instrument. Retest-owed: next Preflight tip must not strip O-QJACOCO wiring. |
| O-SHIPFIXFINDINGS | ✅ | Fixed 2026-08-03 wake#201: `scrub_findings_from_tip` also matches `Preflight fix`/`Gate fix`/`Build fix`/`Deploy fix` (was T-NNN/SNN only). SHIPPING tip + instrument. |
| O-PFCOUNTRM | ✅ | Fixed 2026-08-03 wake#185–186 with O-PREFDIMTHRASH: supervisor auto-resets `/tmp/preflight-count` at each preflight-fix round start and on REFUSED→closing path; sensors refuse text no longer teaches seats to `rm` the counter. Prior: Hermes sandbox blocked `rm`; live wake#179–180 count=5 REFUSED. |
| O-PFEVID | ✅ | Fixed 2026-08-03 wake#185–186: refuse appends `/tmp/preflight-refuse.log` only; prior QUALITYGATE evidence preserved or restored from `/tmp/sensor-sonar.log`; then one closing preflight after count reset (no seat burn on refuse). |
| O-PREFFLOORATT | ⬜ | **W4-064a residual (wake#182):** O-PREFCONT re-stamps char floor at round start (`pref-char-floor-preflightfix-rN.txt`: r1=34, r2=67) but not within-round across attempts — a1 can grow to 90 then a2 tip 70 and still clear floor 67. Re-stamp floor whenever an attempt's working tree exceeds it (not only at round open). Mitigated by O-PREFCONTUT (untracked-visible counts); residual if mid-attempt shrink below peak still possible. |
| O-PREFDIMTHRASH | ✅ | Fixed 2026-08-03 wake#185–186: (1) auto-reset `/tmp/preflight-count` at each fix-round start + refuse→reset→one closing preflight; (2) SHIPPING + preflight-fix prompts tip S5778 = arrange outside single-invocation `assertThrows` (no brace/assertj cosmetics); (3) refuse path no longer burns last-round seats on dim-cap thrash. Instruments + hot-swap. Retest-owed: next M5 ship preflight-fix. |
| O-SHIPROUNDBASE | ✅ | Fixed 2026-08-03 (W4-068a): M5 ship stamps `/tmp/ship-session-base`; Preflight/Gate/Build fix `committed()` uses that base **exclusive** (prior-session tips under story `RUN_BASE` do not auto-burn rounds). Diverged/abandoned `origin/main` is not authority (fetch-only; no pull/merge). Instrument + SHIPPING.md. Live reconcile: specimen `origin/main` `eaaa501` thrash → force-with-lease to honest `64881c8`. |
| O-SHIPFIXPOM | ✅ | Fixed 2026-08-03 wake#185–186: `pref_commit_green_dirt` requires `src/test/` dirt and stages **only** `src/test/` (never `stage_for_task_commit` / `git add -A`); logs when pom/non-test dirt left unpaid. SHIPPING + instrument. Retest-owed: next timeout mechan tip must not include orphan assertj pom. |
| O-PREFCONTUT | ✅ | Fixed 2026-08-03 wake#185–186: `count_test_annotations` uses `grep -rho --include='*.java' '@Test' src/test` (tracked+untracked) for floor snapshot + refuse check. SHIPPING + instrument. |
| O-DTOCOV | ✅ | Fixed 2026-08-01: scaffold+live pom `sonar.exclusions` + coverage/CPD exclusions = `**/dto/**` (OpenAPI harvest). Coverage-only was insufficient (54× S1128 unused imports). Live tip commits on v2 S03 ship. Do not invent BaseDto (O-SFIXDUPBASE) or ceremonial coverage theater. **2026-08-02:** instrument O-DTOCOV (test 203) used bare `grep` on `**/dto/**` → ERE repetition error; fixed `grep -Fq` in `instruments.sh` (ensure-dtocov-pom.py unchanged). |
| O-T6dPKGINFO | ✅ | Fixed 2026-08-01: mechan-match accepts package-info.java-only stages; build-verification titles that mention characterization/src/test no longer force need-src-test → MiniMax (v2 S03 T-008). Instrument. |
| O-MAPPRESEED | ✅ | Fixed 2026-08-01: after O-HARVESTSTALL MapStruct preseed, `ensure-mapstruct-pom.py` adds mapstruct 1.6.3 + annotationProcessorPaths and `@Mapper(componentModel="jakarta-cdi")` (O-MAPCDI). v2 T-006: Qwen READ_THRASH while pom lacked mapstruct → MiniMax; DTOs already present (O-DTOFIRST ok). |
| O-COMMITID | ✅ | Fixed 2026-08-01: `committed()` matches subject-leading `T-NNN:` only; O-SPECREBASE extracts only subject-leading task ids and floors search at prior story-complete (v2 plan message `(T-005)` + ancient T-005 → false skip all tasks → dishonest M5). |
| O-OUTERSTART | ✅ | Fixed 2026-08-01: `v9-preflight-outer-start.sh --start` now `disown`s + `stdbuf -oL` and verifies `kill -0` after 1s. Plain `nohup … &` under `oc exec bash -lc` returned a dead PID with no log append (v2 after O-DEBTFRZ). |
| O-M3EMPTY | ✅ | Fixed 2026-08-01 + tightened 2026-08-02: fresh prompt when tasks.md absent; default `M3_EMPTY_ABORT_SECS=360` (was 720); PLANNING requires **tasks.md first**. Retest-owed: next M3 without lead tip. |
| O-S6813MISREAD | ✅ | Fixed 2026-08-01: tip `4e4c378` ctor-inject EntityManager on all Jpa*RepositoryImpl (cleared 7× S6813); EXECUTION.md O-SONARFIX now states S6813 ≠ JPQL param theater. Probe: Qwen/MiniMax misread (`a5837a3`) burned seats — durable tip in skill.
| O-JPACTX | ✅ | Fixed 2026-08-01: tip `4e4c378` added `@Transactional` on JPA save/delete + ctor inject; EXECUTION.md O-SONARFIX documents mutating EntityManager methods need `jakarta.transaction.Transactional`.
| O-ACVERIFY2 | ✅ | Fixed 2026-08-01: `is_verify_task` matches characterization/package verify; block findings-oracle absent skip for verify titles; `preserve untouched` prose is not preserve-subject (v2 S04 T-006 false skip on `petclinic.security.enable` → dishonest M5). |
| O-ACCOMMITSKIP | ✅ | Fixed 2026-08-01: `committed()` ignores latest `T-NNN: ALREADY COMPLETE` when `already-complete.py` still exits must-run (v2 S04 T-004 false skip `b64e0bd` blocked JDBC harvest on M4 replay). |
| O-JDBCSKIPSTAGING | ✅ | Fixed 2026-08-01: `already-complete.py` O-JDBCSKIP no longer prints `present:JpaRepositoryImpl-cdi` when `migration/staging/**/jdbc/Jdbc*RepositoryImpl.java` still exists (v2 S04 T-004 false skip `b64e0bd` while jdbc dir empty). Wave2 JPA-only skip preserved when staging has no JDBC.
| O-M3KILLGREEN | ✅ | Fixed 2026-08-01: O-M3KILL (rc 137/143) now runs `m3_lint_green` before kill-retry — tip/operator green `tasks.md` no longer infinite-loops (v2 S04). outer-loop.sh worker path.
| O-M3QWENSTALL | ⬜ | Retest FAILED 2026-08-02 fresh S01 M3: preseed landed; Qwen `m3-S01-w1` still 0 writes (10×read + 1×bash) @120s → abort → MiniMax `m3-S01-orch1`. Preseed alone insufficient — need OpenCode forced first-tool write/edit of tasks.md (or mechan-complete lint-near skeleton from brief) before seat; do not mark ✅ on preseed-only. Mitigated by O-M3ROUTE (skip Qwen draft by default). |
| O-M3ROUTE | ✅ | Fixed 2026-08-02: `WORKER_M3_FIRST` default `false` — MiniMax drafts M3 first (`M3_ORCH_BACKSTOP=2`); Phase B uses fresh prompt when no tasks.md; seat tags `m3-SID-aN`. Set `WORKER_M3_FIRST=true` to restore Qwen-draft + backstop. Instrument O-M3ROUTE. Hot-swap + M3 re-run owed. |
| O-M3SHAPEPATCH | ✅ | Fixed 2026-08-02: O-M3QWENSTALL preseed includes `**Class**: rewrite` + `**Shape**: convert`; M3 prompts require Class/Shape on every T-NNN. Hot-swap + MiniMax M3 retest owed. |
| O-M3CLASSFMT | ✅ | Same as O-M3SHAPEPATCH — Class enum rewrite\|infer in preseed + prompts (Hermes used Shape verbs as Class). |
| O-M3PLANEXISTS | ✅ | Fixed 2026-08-02: M3 fresh/fix prompts tip O-M3PLANEXISTS — omit Spring Boot parent/BOM/actuator→Quarkus converts when Quarkus scaffold already satisfies (dead tasks burned MiniMax). Retest on next S01 M3. |
| O-M3DTOSCOPE | ✅ | Fixed 2026-08-02: plan-lint `--story-scope` skips incident-unowned outside roadmap scope; outer-loop passes SCOPE on all M3 lint paths. Unblocks S01 platform (removed-javaee dto/**). Instrument O-M3DTOSCOPE. |
| O-M3TASKSCOPE | ✅ | Fixed 2026-08-03: plan-lint REDs non-test Target/→ destinations outside `--story-scope` (legacy↔target remap; sibling dir OK; src/test + Absorbs deferrals skipped). Closes S03 T-004 service-under-repository false PLAN OK. Instruments + hot-swap md5 `8870a0a3`. |
| O-M3LINTPROCEED | ✅ | Fixed 2026-08-03: after m3-lint / plan-lint still RED → `m3-lint-hold` + pause + exit 1 (no M4). Outer fail_run on `m3-lint-hold`. Instrument m3lintproceed-ok. Pair O-M3GUARDRAIL still ⬜. |
| O-IDLEWSFP | ✅ | Fixed 2026-08-02 (W4-023a): dual clock — `run_idle` keys on `workspace_fp` only; `harness_fp` is agent-implementing. Rule `.agents/rules/stage-080-track-b.md` §12 + `scripts/track-b/v10-idle-clock.sh`. |
| O-SFIXDIMNONE | ✅ | Fixed 2026-08-02 (W4-022a): when `sfix dims=[none]` (sensor unavailable / O-SONAR401), supervisor refuses sfix seat + record_debt — does not default primary=sonar and burn Qwen/MiniMax. Auth failures excluded from sfix_red_dims sonar token. Re-fixed 2026-08-02 (v3 S02 T-007): Quarkus ConfigurationException/Datasource/JDBC/Agroal/HibernateOrmProcessor → task dim; empty dims + milestone config RED → remap none→task (never skip sfix / HOTSWAP-advance on RED).
| O-SONAR401 | ✅ | Fixed 2026-08-02: sensors tag `O-SONAR401` on HTTP 401; supervisor skips sfix + `record_debt` (S01 T-002: token set but invalid). Operator must refresh `SONAR_TOKEN`. Also skip MiniMax sfix rescue on 401/dims-none (W4-023). Extended wake43/44: M5 ship blocks preflight-fix (`ship-blocked-sonar-auth`) — no MiniMax on infra 401. |
| O-SHIPREMOTE | ✅ | Fixed 2026-08-02 (W4-026a/W4-027): non-fast-forward → `ship-blocked-remote-diverged` + debt; harness will not force-push. Hot-swapped. Instruments still O-SONAR401INST cluster. |
| O-SONAR401INST | ✅ | Fixed 2026-08-02 (W4-025a/W4-027): instruments wire O-SONAR401 / O-SFIXDIMNONE / O-SHIPREMOTE + behavioural 401 classify fixture + phrase fixtures in `instruments.sh`. |
| O-SONAR-INLOOP-VS-PREFLIGHT | ⬜ | W4-029b / Hermes-monitor 2026-08-02: milestone in-loop Sonar GREEN (analysis/version probe) while M5 ship Maven scanner still HTTP 401 — probe≠scanner token path. Unify: preflight/ship must use same auth check as in-loop, or fail-closed when probe 200 but `sonar:sonar` 401. Pair O-SONARMIRROR. |
| O-SONARMIRROR | ✅ | Fixed 2026-08-02 (W4-029a): PostSync reuses valid Sonar token (no blind revoke); workspace CronJob `reconcile-workspace-sonar-credentials` re-mirrors + bounces pods when token bytes change. |
| O-RESUMEHIDE | ✅ | Fixed 2026-08-02: outer-loop walks `RESUME_RUN_BASE` back when earlier in-story `T-NNN:` tips would be hidden (Wave4 S01 @1efdd65 ceremonial AC replay). Instrument O-RESUMEHIDE. |
| O-M2K3TABLE | ✅ | Fixed 2026-08-02: M2 SEQUENCE double-lint RED when planner mirrored inventory's markdown K3 table (`| id | defer | reason |`) but roadmap-lint only parsed bullet `- id: defer (reason)`. Accept both; instruments for table OK + empty reason RED. (alias O-M2K3FMT / O-M2K3PLACE from wipe monitors) |
| O-ORCH429BACKOFF | ✅ | Fixed 2026-08-03 wake#10: mchat no longer claims "supervisor backs off 15m"; callers must NOT-spend + sleep. M2 path sleeps `M2_429_BACKOFF_SECS` (default 900) on 429 (pair O-M2-429). M3 already had O-M3QUOTA sleep 900. |
| O-M2-429 | ✅ | Fixed 2026-08-03 wake#10: M2 loop uses while/ATTEMPT; on session-log 429 after lint RED, attempt is **NOT spent** and real `sleep M2_429_BACKOFF_SECS` (default 900) runs before resume — hermes_rc=0 ≠ gate. Instruments `m2429-wire-ok`. Pair O-ORCH429BACKOFF ✅. |
| O-M2FABRICATE | ⬜ | Wipe M2 a1: fabrication/coverage/briefs lint before K3; a2 cleared most but burned ~8m. Strengthen SEQUENCING + a1 prompt with legacy-quote + single-owner examples; surface lint class summary earlier (pair O-M3GUARDRAIL for M2). |
| O-M1SENSORGATE | ⬜ | Wipe start: O-SENSORGATE refused bad stamp / sensorgate churn before ANALYZE settled. Make stamp↔sensor gate idempotent + one clear log line (no multi-pass refuse thrash on fresh wipe). |
| O-M3SUPSCOPE | ✅ | Fixed 2026-08-02: (1) supervisor M3 revision omitted `--story-scope` → false-RED dto unowned after outer GREEN (`fcc506c`) → MiniMax M3 revision burn. Pass `STORY_SCOPE`. (2) plan-lint split scope only on `,` but parse-roadmap emits spaces → scope blob matched nothing → all incidents skipped (false PLAN OK). Split on `[\s,]+`; normalize `projects/legacy/pom.xml`→`pom.xml`. |
| O-M3GENSRC | ✅ | Fixed 2026-08-02 (wake29): plan-lint skips incident-unowned for `target/generated-sources/**` (MapStruct noise). Instrument O-M3GENSRC. Hot-swap with O-M3DTOSCOPE before M3 re-run. |
| O-M3UNOWNDIR | ⬜ | W4-022b: plan-lint `incident-unowned` treated as soft alongside GREEN when many files share one rule+directory (S01 removed-javaee dto×18). O-M3SUPSCOPE/story-scope should skip out-of-story dto; for *in-scope* single-rule directory blocks, make unowned fatal or require explicit deferral row. |
| O-M3ABSORBFORM | ⬜ | Hermes-monitor 2026-08-02: MiniMax expanded Absorbs to per-file list yet incident-unowned remained (claim form ineffective vs Target/Owns). Durableize: plan-lint tip or PLANNING — Absorbs alone may not own; require Target/Owns for K1. |
| O-M3GUARDRAIL | ⬜ | Hermes-monitor 2026-08-02: `repeated_exact_failure_block` ended MiniMax seat before strategy change (~8.5m / 100 tools / hermes_rc=0). Durableize: surface plan-lint class summary in prompt earlier, or escalate guardrail to force Class-enum / scope-skip strategy. |
| O-RUNRPTSESS | ⬜ | W4-015a: run-report/retro-metrics count only Hermes sessions (4) while OpenCode worker seats (T-002…T-009) are invisible — over-weights timeouts, erases clean Qwen path. Fold oc-T-* seats into metrics/report or label table orchestrator-only.
| O-HOTSWAPVER | ⬜ | W4-015b: SUPERVISOR_VERSION md5 stamped once at process start; O-HOTSWAP mid-run leaves run-report naming pre-swap binary (ed92a393 vs O-SFIXNODELTA). Record version@event trail on hotswap.
| O-REVHOLD | ✅ | Fixed 2026-08-02: `migration/HOLD` or `/tmp/review-hold` blocks supervisor story-gate-passed / acceptance success and outer-loop story-complete ledger write. W4-015d. Hot-swap. |
| O-DEBTNONE | ✅ | Fixed 2026-08-02: `record_debt` strips template `(none)` / `- (none)` lines before appending real `##` debt entries. W4-015c. Hot-swap. |
| O-M3SCHAR | ✅ | **Superseded by O-M3CHARSCOPE (2026-08-02):** same V3 S01 false **LINT:S-CHAR** on platform `deploy=false` plan — closed by S-CHAR scope to targetPackage Owns/Target + non-structure skip (not a separate deploy=false lint rule). Do not reopen unless S-CHAR fires on a fresh M3 seat after O-M3CHARSCOPE. |
| O-M3CHARSCOPE | ✅ | Fixed 2026-08-02: S-CHAR scopes to targetPackage `src/main/.../model/*.java` in Owns/Target (not **Absorbs** legacy cites); skips Shape=structure/verify. Unblocks platform S01 after MiniMax plan (petclinic v3 false RED). Instrument O-M3CHARSCOPE. |
| O-SFIXALREADYGREEN | ⬜ | S01 m3-lint sfix: Qwen `d1e0e80` cleared findings but supervisor still launched MiniMax rescue (stale post-session milestone RED). MiniMax then committed ceremonial `dc8dbf9` “no action needed”. Fix: re-run findings/milestone *after* worker commit before spending rescue seat; skip rescue when dimension already GREEN. Recurred v2 S04 T-003: tip already GREEN (`5186613`) yet MiniMax rescue burned ~9m and committed ceremonial findings-only `a6778fc` mistitled as S6813 SQL injection. 2026-08-01. |
| O-ESCNOCOMMIT | ✅ | Fixed 2026-08-01 (v2 S01 T-003): after MiniMax escalation, require HEAD subject `^T-NNN:` before END/K12. Findings-only tip → O-T1FINDESC undo left prior SHA; supervisor still logged “committed via MiniMax” on T-002 (`e2aa463`) + K12 PASS → false advance. On miss: try O-ESCW allow-empty, else debt-freeze. |
| O-ESCWFINDINGS | ✅ | Fixed 2026-08-01 (same T-003): `app_dirt` excludes `migration/mta-findings-current.json` so O-ESCW is not blocked by inventory dirt (worker rc=0 + absent Shape=remove → MiniMax burn). Aligns with O-T1FINDINGS. |
| O-M2DIORPHAN | ✅ | Fixed 2026-08-01 live (`0a9ab90`): M2 unique-ownership dropped DI dual-claim onto S01 without a task claiming `ApplicationSwaggerConfig` → outer restart plan-lint `incident-unowned` → false O-M3SKIP. Rule must stay with the story that scopes the incident file (moved `springboot-di-to-quarkus-00002` S01→S07). SEQUENCING tip owed if not already. |
| O-DUPPROP | ✅ | Fixed 2026-08-02: `commit-hygiene.py` refuses tips that leave duplicate keys in application.properties. |
| O-M5EVALDELETE | ✅ | Fixed 2026-08-01: SHIPPING + evaluate prompt forbid deleting landed src/main/java / required deps; supervisor restores deletions vs pre-eval HEAD and O-DEBTFRZ (v2 S04 MiniMax deleted springdatajpa + pom swap then shipped). |
| O-M5EVALHARVEST | ✅ | Fixed 2026-08-01 (v2 S01 M5): evaluate MiniMax harvested model/repo/rest/service/dto/mapper/util to chase REMAINING pom rules / ABSENT-NOT-LANDED. Prompt+SHIPPING forbid harvest; supervisor resets evaluate tip that adds those package trees on deploy=false POM stories. |
| O-BOOTPORTSTALE | ✅ | Fixed 2026-08-01: `boot_check` kills prior `quarkus-run.jar` when :8099 busy before start. |
| O-BOOTROOT | ✅ | Fixed 2026-08-01 (v2 S01): boot_check also curls `${quarkus.http.root-path}/q/health` (O-HEALTHROOT). Bare `/q/health` timed out 120s when `%prod` root-path=/petclinic; MiniMax thrash. Scaffold tip: `quarkus.http.non-application-root-path=/q`. |
| O-M5SHIPHARVEST | ✅ | Fixed 2026-08-01 (v2 S01 ship): preflight-fix MiniMax harvested staging to chase O-QJACOCO missing report on platform story (no @QuarkusTest). `qjacoco_check` SKIPs without @QuarkusTest (O-QJACOCONOTEST); preflightfix prompt forbids harvest. |
| O-SFIXS5853 | ⬜ | T-007: Qwen wrote consecutive `assertThat(x).a(); assertThat(x).b();` → java:S5853; rewrite sfix 0-file; MiniMax sfix chained AssertJ. Tip/worker packet: chain AssertJ on same subject in characterization tests so worker-direct avoids MiniMax sfix seat. |
| O-SFIXMSG | ⬜ | T-008 `325db8d` subject claimed "fidelity drift" but diff was sonar S1130 (+ BaseEntityTest assert). R-109: BaseEntityTest change was a *strengthening* and milestone-tree-wide repair is legitimate — keep bank for **subject/dimension mismatch** only, not the cross-file edit. |
| O-SFIXATTR | ⬜ | F-26/F-16: supervisor ✓ END after sfix credits coding worker even when MiniMax orch ran sensor-fix (T-007 `6aa8cd2`). Fix log/event actor for sfix path so seat accounting and review ledgers stay honest.
| O-DSKIND | ✅ | Fixed 2026-07-31 (S02 T-004): db-kind + quarkus-jdbc-* after JPA harvest; drop-and-create until seed. Re-fixed 2026-08-02 (v3 S02 T-007): `ensure-dskind.py` post-commit + task-packet tip + EXECUTION tip when hibernate/@Entity lands without jdbc (ConfigurationException); O-SFIXDIMNONE remaps config RED→task. Probe tips `c3e627c`/`ef91205` proven GREEN; harness path is durable. |
| O-FIDELITYDAO | ✅ | Fixed 2026-07-31: harvest-fidelity approves DataAccessException throw strip + PropertyComparator/MutableSortDefinition/ToStringCreator drops (JDK Comparator / plain toString). Instrument + hot-swap. Prevents MiniMax sfix Spring green-wash (O-SFIXNOSPRING). |
| O-FIDELITYSORT | ✅ | Fixed 2026-08-02: EXECUTION tip ArrayList+List.sort (not stream); fidelity FIX guide updated; probe GREEN on frozen tip. Retest on fresh outer (not hand-dirty resume). Pair O-FIDELITYDAO. |
| O-FIDELITYREWRITE | ⬜ | W4-017a / W4-018a: sensor remediation text ("re-harvest / REVERT") is a trap when staged lines still carry Spring support — literal re-harvest reintroduces org.springframework. Prefer O-FIDELITYSORT shape (keep ArrayList locals; replace only PropertyComparator line). Optional later: expand approved transform list so stream rewrite also GREEN — **not** required to clear freeze; do not change sensor under freeze pressure. Pair O-SFIXFIDELITY. |
| O-T4SPRINGDATA | ✅ | Fixed 2026-08-03: plan-lint `LINT:O-T4SPRINGDATA` REDs SpringData* Target on Quarkus pom without spring-data / quarkus-spring-data-* unless Port=reimplement / Panache / redesign/skip/defer / O-SDJPA-SKIP. task-packet + PLANNING tip. Instruments t4springdata×2. Retest-owed: next M3 with SpringData* harvest-only must RED before M4. |
| O-PREFLIGHTDIM | ✅ | Fixed 2026-08-01 (F-70/F-37): sensors.sh preflight caps full runs (default 3) via /tmp/preflight-count; M5 ship resets counter. Dimension sensors remain for sfix (O-SFIXLOOP). Instrument wiring. Retest-owed: next M5 ship. |
| O-SFIXS117 | ✅ | Fixed 2026-07-31 (EFF-1): style-autofix adds RenameLocalVariablesToCamelCase + RenamePrivateFieldsToCamelCase; instruments assert recipes present. Hot-swapped workspace. |

| O-SHIPPLACE | ⬜ | M5 ship-fix (wake55–56): MiniMax adds ceremonial BindingErrorsResponseTest “JSON serialization failure” that never fails ObjectMapper — asserts isNotNull with limitation comment. Ship-fix tip: refuse placeholder coverage for uncovered catch; require real fault injection or drop. |
| O-SHIPSONARPOM | ⬜ | M5 ship fix (wake53–54): MiniMax dirties `pom.xml` with pinned `sonar-maven-plugin` while quality-gate RED — plugin pin does not clear gate; pair with O-SONAROPAQUE (actionable violations list) + ship-fix tip: fix issues/coverage, never pin scanner plugin. |
| O-SONARHOTSPOT | ⬜ | M5 ship: QG `new_security_hotspots_reviewed` — one TO_REVIEW hotspot java:S4507 BindingErrorsResponse debug. Ship-fix tip + optional harness helper to print review URL/API; do not pin sonar-maven-plugin or add ceremonial tests. || O-SONAROPAQUE | ✅ | Fixed wake57: `sonar-report.py` emits QUALITYGATE FAIL conditions + HOTSPOTS TO_REVIEW (not issues-only). Root cause of M5 RED was `new_security_hotspots_reviewed=0` (java:S4507 BindingErrorsResponse:88), not violations. sensors.sh fail text → conditions above. Hot-swapped modernized; re-run ship-fix to dogfood. |
| O-SONARTIME | ⬜ | T-007 sfix: MiniMax wrapped `sensors.sh sonar` in `timeout 300` despite prompt O-SONARTIME (≥600s). Enforce in harness wrapper (strip/raise timeout) or refuse sfix dimension check under short timeout — prompt alone insufficient. |
| O-MAPPINGS-JAVAXSE | ⬜ | F-20/R-102: residue gates must not match bare javax.; javax.sql is SE — fold into MAPPINGS / findings-delta so false javax residuals do not block. |
| O-MAPPINGS-PETCLINIC | ✅ | Fixed 2026-07-31: MAPPINGS.md (AOP/derived-query/Elytron/MockMvc/deviations/metrics preserve); rubric `@Aspect`→REDESIGN; SKILL standards-vs-compat; EXECUTION MockMvc tip. |
| O-ACCEPTGEN | ✅ | Fixed 2026-07-31: `acceptance_config.py` + `acceptance.collection/service/endpointEnv/itemType`; sensors G-CAT/G-CATBODY + ship counter + coolstore-lint accept literals. |
| O-ACCEPTARRAY | ✅ | Fixed 2026-07-31 (Poll 81 B1): `acceptance.collection: _array` bare-array sentinel — `acceptance-products` counts only top-level JSON arrays (rejects `{vetList:[…]}` wrappers); instruments Poll 81 B1; sensors labels; coolstore-lint P3 line-level `ALLOWED: coolstore-default-fallback` on sensors fallbacks. Specimen contract path=`/petclinic/api/vets`, collection=`_array`, getter=`getAllVets`, service=`ClinicService`, itemType=`VetDto`, needsDatabase=true; preserve context-path + `petclinic.security.enable=false`; `analysis.mode` wired (E2); E3 schema seed early M4. |
| O-DEVDBURL | ✅ | Fixed 2026-07-31 (R-83 P2): `sensors.sh` DEV_DB_URL from `acceptance.dbService`/`dbName` (omit → `${PROJECT_KEY}-postgres` / `${PROJECT_KEY}`); `acceptance_config.py` exports ACC_DB_*; skeleton `k8s/app.yaml` JDBC + `postgres.yaml` DATABASE/pg_isready use `values.name`; coolstore-lint STRICT `coolstore-postgres`. **E3 decision:** M1 profile documents postgres schema+seed as REDESIGN deliverable; early M4 task owns the Flyway/data.sql implementation (preflight/plan-lint catch missing seed — addresses R-83 early-fail intent without doing DDL in analyze). |
| O-PKGPREFIX | ✅ | Fixed 2026-07-31: package-boundary rename in harvest + fidelity; instrument proves petclinic ↛ `org.springframework.boot.*`. |

## Demo log UX (Poll 77 — `/tmp/outer-loop.log` is the workshop view)

Wave A (⬜ before next demo run). Wave B/C (📋). Detail table in
`tmp/KAI-WAVE2-REVIEW.md` (migrated from Wave 1 archive Poll 77).

| ID | Status | Notes |
|----|--------|-------|
| O-UXLOG-TRUNC | ✅ | Fixed 2026-07-31: append (rotate >5MiB); RESUME banner + N-of-M stories from story-state.csv. |
| O-UXLOG-SENSE | ✅ | Fixed 2026-07-31: post_commit_verify GREEN → outer_log `✓ SENSE … GREEN after T-NNN (…s)`. |
| O-UXLOG-SHIP | ✅ | Fixed 2026-07-31: outer_log push/pipeline/rollout/acceptance/preflight-fix rounds. |
| O-UXLOG-ESCWHY | 📋 | U4: escalation lines carry wedge/rc reason + sparse worker heartbeat. |
| O-UXLOG-WRITERS | 📋 | U5: all writers through timestamped helper; dedupe WARN/roster/URL. |
| O-UXLOG-BUDGET | 📋 | U6: heartbeats show "Ns of budget". |
| O-UXLOG-LEGEND | 📋 | U7: cold-open legend (glyphs + M1–M5 one-liners). |
| O-UXLOG-SUMMARY | 📋 | U8: story END + RUN COMPLETE roll-ups. |
| O-UXLOG-WORDING | 📋 | U9: plain session≠gate wording; skips print oracle evidence. |
| O-LOGSTORY | ✅ | Wave4 Claude (wake#357); landed wake#375: `log()` prefixes `${STORY_TAG} ▸` when set; story loop sets `STORY_TAG=$SID` and clears after each story / before M3-ALL whole-set. M1/M2 unprefixed. Instruments: logstory-wire-ok + logstory-emit-ok. Pure emission — no restart. Heartbeats still bypass `log()` (O-LOGPROG). |
| O-LOGBRIEF | ✅ | Wave4 Claude (wake#357); landed wake#376: `emit_story_brief` after M4/M5 `phase_start` — GOAL (brief/spec/task; ≠slug) / SCOPE / OWNS (+ids dump) / PLAN (class×shape) / PORT / DONE. Instruments: logbrief-epilog-wire-ok + logbrief-emit-ok. Pure emission — no restart. |
| O-LOGEPILOG | ✅ | Wave4 Claude (wake#357); landed wake#376: `emit_story_epilog` on complete/debt-freeze/fail/hold — RESULT/CODE/TESTS/FIND/COST/HEAD; COST seats = `oc-<SID>-*.json` count. Instrument: logepilog-emit-ok. Pure emission — no restart. Supersedes thin U8 for story END. |
| O-LOGPROG | 📋 | Wave4 Claude (wake#357): heartbeats inside story are positional (`T-NNN running … · story N/M tasks · seats · elapsed · last sensor`). Follows O-LOGSTORY. |
| O-LOGRUN | 📋 | Wave4 Claude (wake#357): run-level position line at story boundaries (`RUN N/M stories · S01 ✓ … · S03 ▸ …`). Follows O-LOGEPILOG. |
| O-EVIDLIVE | ✅ | Wave4 R-A6 / §3.3 (wake#377): `evidence-liveness.sh` ledger + story-gate `evidence_liveness_blocks_ship` — active K1/K2/K3/K9/K11 each ≥1 row/story or RED (`evidlive-red`). Emitters: plan-lint PASS→K1, packet Analysis→`k2:evidence`, M2 roadmap-lint→K3, heartbeat none for K9/K11-no-Findings. **K10 retired** from liveness (optional ADVANCE hints — silence expected). Instruments: evidlive-wire/heartbeat/red. No restart. |
| O-EXECCORPUS | ✅ | Fixed 2026-08-03 wake#384 (ARCH-B1): `exec-corpus-lint.sh` + fixtures under `.hermes/harness/tests/fixtures/exec-corpus/` seeded from host `tmp/s03-clean-stop-20260803T052227Z/s03-run-archives.tgz` (`20260803T052227Z-clean-stop-s03/`). Cases: `s03-t004-sfixnodelta` (runtime K7 `SUMMARY new=0 gone=0` + structure tip → today's `sfix_nodelta_skip`; historic excerpt proves O-SFIXWORKER burn) and `s03-t004-escalation-cause` (archived gold `sensor-red` + STEPFINISHRED .err; read-thrash twin). Full `oc-*.json` bodies remain in host tarball (json.head + extract path in SOURCE.txt). Host gate `scripts/track-b/v10-exec-corpus-gate.sh`. Instruments execcorpus-wire/sfixnodelta/escalcause/sweep. **Retest:** `bash .hermes/harness/exec-corpus-lint.sh`. K7-vs-sonar / O-DELTABASE extra cases still open as follow-ons (not blocking this bank row). |
| O-GUARDMANIFEST | ✅ | Fixed 2026-08-03 wake#386 (ARCH-B2): `guard-manifest.sh` + `guard-manifest.md` — seed table stage×mechanism×verification (L1/L2/L3); `--check` refuses missing seed/columns/empty harvest; grep -nE harvest (no rg). Instruments guardmanifest-ok + guardmanifest-regen-ok. Retest-owed bank rows cite this file. **Retest:** `bash .hermes/harness/guard-manifest.sh --check`. |

## O-NOPUSHPR — empty-delta M5 ship reuses prior PipelineRun (✅)

**Seen:** S06 ship pushed evaluate SHA but supervisor reported *no new
PipelineRun* and judged an older Succeeded run (`…-push-7k7vn`).

**Fixed 2026-07-31:** `wait_pipeline` takes push-uptodate flag — only
O-SHIPNOPR (Everything up-to-date) may judge an existing PR. When commits
were pushed but no new PR appears (~6m wait), ship **FAIL**s (`none
no-trigger`) instead of greening on a stale Succeeded run.


## Wave2 S02 T-005 — DTO/mapper order + commit hygiene (from `62413ff`)

| ID | Status | Notes |
|----|--------|-------|
| O-DTOFIRST | ✅ | Fixed 2026-07-31 (Wave2 T-005 HOLD): DTO harvest before MapStruct mappers when both tasks exist. **Reopened gap 2026-08-01** (v2 S03): mapper-only story with `com.demo.dto` imports skipped the rule (`dto_tasks` empty) → Qwen compile RED → MiniMax. Closed: plan-lint also REDs mapper tasks that reference `/dto/`/`.dto.` when the story has no DTO harvest task. Instrument: mapper-only+dto-refs. Prefer reorder/defer — do not invent stub DTOs. |
| O-GITBAK | ✅ | Fixed 2026-07-31 (Wave2 T-005 HOLD):  Refuse staging/commit `*.bak` / `*~` / `.orig` under src/ (`62413ff` committed 8 OpenAPI dumps as `.bak`). |
| O-SIMPLEDTO | ✅ | Fixed 2026-07-31 (Wave2 T-005 HOLD):  Refuse thin hand-rolled DTO beans when staging has OpenAPI-shaped DTO; do not rename harvest to `.bak` and invent stubs (`OwnerDto.java` vs `.bak` in `62413ff`). |
| O-WEDGESKIP | ✅ | Fixed 2026-07-31: clear_worker_wedge_skip after mechan/worker/escalation success; skip no longer sticky for whole story.  O-WORKERWEDGE-RCA skips **all** further worker seats for the story (Wave2 T-007 ClinicServiceImpl → MiniMax immediately after T-005 DTO wedge). Durable: scope skip to same failure class / same task pattern, or clear RCA after O-DTOSTAGING-class fix lands mid-story. |
| O-SCRATCHPY | ⬜ | Escalation invents scratch `harvest_*.py` instead of bundled `harvest-from-staging.sh` (Wave2 T-005 MiniMax). Tip+refuse commit of repo-root scratch harvesters. |
| O-DTOALLOF | ⬜ | MiniMax OpenAPI harvest skipped `*AllOfDto`/`*FieldsDto` required by composition DTOs (Wave2 T-005). Harvest must include all OpenAPI dto/*.java under package; tip never filter AllOf/Fields. |
| O-DTOSTAGING | ✅ | Fixed 2026-07-31: harvest-from-staging OpenAPI generated-sources fallback + javax.validation/annotation→jakarta; instrument DTOSTAGING_OK.  OpenAPI-generated DTOs live under legacy `target/generated-sources/openapi` not `migration/staging` — harvest-from-staging / O-HARVESTSTALL preseed misses them; worker wanders (Wave2 T-005 ~6m). Durable: M1/staging copy or harvest script path for openapi dto root from migration.yaml; preseed Targets from that tree.  Retest-owed (F-70 0.3): no fresh-run proof since land. |
| O-SPECREBASE | ✅ | Fixed 2026-07-31: O-M4REPLAY walks run_base back past pre-spec T-NNN when mid-story `S0N spec:` recommit hides them. **Hardened 2026-08-01 (O-COMMITID):** subject-leading `T-NNN:` only + floor at prior story-complete — plan subjects with `(T-005)` no longer walk into ancient prior-story task commits. |
| O-POMUNC | ✅ | Fixed 2026-07-31 (Wave2 T-005 HOLD):  Task GREEN must not rely on uncommitted pom deps — MapStruct left dirty while mappers committed (`62413ff`). Same-commit pom or RED. |
| O-TXDROP | ⬜ | Wave2 T-007 `30ff504`: Spring `@Transactional` dropped on *all* service methods (staging had ~29; target has 0 annotations — only a javadoc mention). Task said replace with jakarta/hibernate TX or remove for *read-only*; mutating save/delete lost TX. Durable: tip + optional commit-hygiene/sensor — preserve `jakarta.transaction.Transactional` on write methods when staging/legacy had Spring TX; findings `transaction-to-quarkus-*` not cleared by CDI-only. |
| O-SDJPA-SKIP | ✅ | Fixed 2026-08-03: `already-complete.py` skips Override-only / redesign-skip Spring Data tasks when ≥3 Jpa*RepositoryImpl @ApplicationScoped, pom has no spring-data, and no pending staging Override Impl harvest (`present:JpaRepositoryImpl-cdi-sdjpa-skip`). Does NOT skip Port=reimplement Panache consolidate. Packet + PLANNING/EXECUTION tip (pair O-T4SPRINGDATA / O-JDBCSKIP). Instrument sdjpaskip×2. Retest-owed: next Override-only Spring Data seat with Jpa CDI cover must already-complete without MiniMax. |
| O-JDBCREGRESS | ✅ | Fixed 2026-07-31: commit-hygiene refuses spring-jdbc/tx/orm re-add under quarkus-maven-plugin; already-complete O-JDBCSKIP when ≥3 Jpa*RepositoryImpl @ApplicationScoped and no Jdbc* yet (Wave2 T-009 MiniMax Spring regress HOLD).  Retest-owed (F-70 0.3): no fresh-run proof since land. |
| O-TXKANTRA | ✅ | Fixed 2026-07-31: findings-diff treats transaction-to-quarkus-* as remediated when destination source has @Transactional (kantra false-survive after CDI TX). |
| O-HARVESTREPO | ✅ | Fixed 2026-07-31: harvest-from-staging converts Spring @Repository→@ApplicationScoped, strips @Profile, DataAccessException→PersistenceException, PersistenceContext→Inject when pom has no spring-boot. |
| O-CDIORDER | ✅ | Fixed 2026-07-31: plan-lint + PLANNING tip — repository CDI/Panache before service CDI that @Injects repos (Wave2 T-007 Arc RED). Instruments green.  Retest-owed (F-70 0.3): specimen literals stripped 2026-08-01; re-lint next M3. |
| O-TASKARC | ⬜ | Companion to O-CDIORDER: sensors.sh task greened T-007 without Arc validation; milestone then RED on UnsatisfiedResolutionException. Durable: when commit adds @ApplicationScoped/@Inject types, task sensor must exercise quarkus build/Arc. |
| O-SFIXPARTIAL | ✅ | Fixed 2026-08-01 (F-70 Tier-1#8): after O-SFIXSCOPE archive+reset, `sfix-partial-salvage.py` restores in-scope paths; recommit if sensor GREEN. Instrument (in-scope keep / oos drop). Retest-owed: next sfix RED tip. Unblocks DELEG-1 re-measure. |
| O-GATESCOPE | ✅ | Fixed 2026-07-31: `scope_enforce` keeps `src/main` paths named in `/tmp/gate-violations.txt` for Gate/Build/Preflight fix commits (SHIPPING.md). Wave2 freeze cause: gatefix-r1 `213d74e` DTO fixes reverted by story-scope → BV tests RED → O-DEBTFRZ. Hot-swapped; prove on ship resume. |
| O-RECORDBV | ⬜ | Companion: Jakarta BV on Java records — `@Min`/`@NotNull` on accessor methods often do not fire under `validator.validate(record)`; put constraints on record components. Gate tests assumed component-level constraints; scope-reverted DTOs left accessor-only `@Min` → 0 violations. Tip for DTO harvest/ship. |
| O-SQLLOAD | ✅ | Fixed 2026-07-31 (Wave2 M5): `quarkus.hibernate-orm.sql-load-script=NoSuchFile` is invalid — use `no-file`. Tip/T-015: never invent NoSuchFile; milestone build RED. |
| O-NATIVEPROF | ✅ | Fixed 2026-07-31 (Wave2 M5): Kantra `javaee-pom-to-quarkus-00060` matches `quarkus.package.type=native` — not `quarkus.native.enabled`. Live pom 223bcad; tip/scaffold should use Konveyor snippet verbatim. |
| O-SHIPQUOTA | ⬜ | Wave2 M5 ship: MiniMax preflight/gate fix hit quota mid-session (15m backoff) after writing uncommitted / broken coverage tests (wished Spring APIs, ceremonial acceptanceCheck). Gate fix-r1 also SLOW 2654s (45m budget) before commit. Prefer commit partial green tests before long coverage chase; operator landed 36a236b during backoff. |
| O-ACCEPTPROBE | ✅ | Fixed 2026-08-01: supervisor logs `ACC_INDEX_URL` (`/` or `${root-path}/`) on the acceptance probe line after O-ACCEPTROOT. Instrument + SHIPPING tip. |
| O-SFIXWORKER | ✅ | Fixed 2026-08-01: sensor-fix → Qwen first (`WORKER_SFIX_FIRST`, `run_worker_prompt`); MiniMax rescue loop capped by `SFIX_MINIMAX_RESCUE_MAX` (default 1, R-218). Events `sfix_worker_first` / `sfix_worker_green` / `sfix_minimax_rescue`. Keep sfix guards. Measure MiniMax minutes + M4 rescue rate. |
| O-M3WORKER | ✅ | Fixed 2026-08-01: M3 SPECIFY → Qwen draft/fix (`WORKER_M3_FIRST`, ≤`M3_WORKER_ATTEMPTS`=2) then MiniMax backstop (`M3_ORCH_BACKSTOP`=1). plan-lint remains gate. M1/M2/M5 stay on MiniMax. Set `WORKER_M3_FIRST=false` for legacy 2× MiniMax. |
| O-SHIPMECH | ⬜ | Wave2 M5 ship: after MiniMax deploy-fix sessions burned without commit, supervisor mechanical-committed `afc8729` sensor-GREEN theater (`preflight-*.sh` + mta-findings JSON) with **no** deploy root-cause change. Mechan ship commits must require touch of `src/main|pom|k8s` matching failure class, or refuse. |
| O-ACCEPTROOT | ✅ | Wave2 M5: ship curls `/` for index 200, but `quarkus.http.root-path` (servlet context-path preserve) serves index at `${root}/`. Supervisor fallback to `${root-path}/` when bare `/` ≠ 200. Do not replace root-path with rest.path in tests — RestAssured + dual prefix → 405. |
| O-CTXROOT | ✅ | Wave2 M5: preserve context-path as `quarkus.http.root-path` (RestAssured/tests expect it) + `non-application-root-path=/q`. Do **not** switch main/tests to `rest.path` alone (Owner POST 405). Ship index via supervisor O-ACCEPTROOT `${root-path}/`. |
| O-SEEDIMPORT | ✅ | Wave2 M5: `import.sql` from legacy postgresql populate used positional VALUES; Hibernate `pets` column order is id,name,birth_date,**owner_id**,**type_id** so type/owner swapped → FK error aborts whole script (empty acceptance). Tip: always use explicit column lists in import.sql; verify against ORM schema not legacy initDB order. |
| O-HEALTHROOT | ✅ | Wave2 M5 ship: preserving `server.servlet.context-path` as `quarkus.http.root-path=/petclinic` moves SmallRye health under `/petclinic/q/health*`; factory probes stay at `/q/health/ready|live`. Tip: set `quarkus.http.non-application-root-path=/q` (absolute). Do **not** use `/` — that serves `/health/ready` without `/q` and still fails probes. |
| O-PREFLIGHTH2 | ✅ | Wave2 M5 ship `a03d3c7`: MiniMax greened local preflight by setting `quarkus.datasource.db-kind=h2` as default; factory deploy then crash-looped (`Driver does not support the provided URL: jdbc:postgresql://…`). Tip/SHIPPING: never change default db-kind to H2 for preflight — use `%dev`/`%test` profile or env override; keep prod/default postgresql for factory deploy. |
| O-K12NEST | ✅ | Fixed 2026-07-31 (Wave2 T-019): WEAK-ASSERT strong detection no longer uses `assertThat([^)]+)` — nested `getOwner()` made isSameAs/extracting invisible, false debt-freeze on CircularGroupIntegrationTest. Substance = any non-isNotNull assertThat line. Instrument nest.diff. |
| O-K12WEAKTEST | ✅ | Fixed 2026-07-31 (Wave2 T-016): WEAK-ASSERT no longer REFUTEs characterization — exempt getAnnotation presence; ignore bare isNotNull when same diff has strong AssertJ (isEqualTo/hasSize/…). Bare isNotNull-only still REFUTES. Instruments. False debt-freeze on `262bc3d` → re-land `c2b02b5`. |
| O-MAPCDI | ✅ | Fixed 2026-07-31 (Wave2 T-018): MapStruct `@Mapper(componentModel="jakarta-cdi")` + `mapstruct-processor` 1.6.3 annotationProcessorPaths — without Impl/@ApplicationScoped, REST controllers UnsatisfiedResolutionException. |
| O-WEDGERESUME | ✅ | Fixed 2026-08-01: clear `/tmp/worker-wedge-skip` at supervisor start (stale skip after abort forced MiniMax). Instrument. |
| O-ESCREOPENCODE | ✅ | Fixed 2026-08-01 (T-007/T-012/T-018): after wedge/INFERABSENT, escalation prompt forbids re-dispatching opencode — MiniMax owns file edits. Instrument. |
| O-QTESTROOT | ⬜ | Tip: QuarkusTest RestAssured already applies quarkus.http.root-path — do not prefix `/petclinic` again (double path → 404). |
| O-CHARREAD | ⬜ | Wave2 T-017/T-018 + **v2 S05 T-005**: Qwen READ_THRASH on characterization (reads=21, mutates=0, O-WORKERREAD kill rc=143) → MiniMax every time. Tip/packet: start by writing one *Test.java skeleton from AS-IS service signatures before broad reads; or mechanical test scaffold from interface method list. |
| O-ESCTERM60 | ⬜ | Implemented 2026-08-01 (retest-owed → see `guard-manifest.md` L3 for commit-gated live discharge): `commit-gated.sh` runs `sensors.sh task` then `SKIP_SENSOR_GATE=1 git commit`; EXECUTION + escalation/continue prompts. Was: Hermes bare `git commit` killed at 60s by commit-msg sensor (v2 S05 T-005). |
| O-ESCW3SCOPE | ✅ | Fixed 2026-08-01: finding-scope ESCW skips later-story Target missing-target; Absorbs under rest/security/util must stay absent. Retest: v2 S05 T-006 → O-ESCW after O-ESCNOCOMMIT `61e8fcd`. Instrument. |
| O-ESCW3TGTPKG | ⬜ | v3 S02 T-001 (2026-08-02): Qwen wrote `com.demo.model/.gitkeep` (ttfw=5s, rc=0, mvn GREEN) but file already existed from S01 → O-T6e no dirt; O-ESCW3 refused allow-empty citing `missing-pkgdir:src/main/java/org/springframework/samples/petclinic/model/` (legacyPackage) instead of targetPackage `com/demo/model`. Escalated MiniMax worker-failed despite correct Target present. Durableize: ESCW3 missing-pkgdir must use targetPackage paths from migration.yaml; already-present structure Target → already-satisfied / skip not escalate; pair O-AC / O-ESCWSTRUCTTGT. |
| O-SONARLINEFIX | ✅ | Fixed 2026-08-02: S112 on throw-site NOSONAR; S1130 drop test throws; S2925 AtomicLong backdate (+ rewrite throws InterruptedException). Cleared S05 T-006 milestone (tip 93a5a2c). Retest: next style-autofix path. |
| O-FRZSIG | ✅ | Fixed 2026-08-02 (F-74/F1): `freeze-harness.sh` default = pause marker only (no TERM/KILL). `--hard` kills registered `/tmp/sessions/T-*.pid` only; defers if `/tmp/m5-round-active`. Retest-owed: next O-DEBTFRZ. |
| O-KILLLEDGER | ✅ | Fixed 2026-08-02 (F-74/F5): `harness-kill.sh` / `harness_kill` appends tag/pid/sig/cause to `/tmp/kill-ledger.log`. Wired into freeze `--hard`. Full kill-site conversion with O-PIDKILLREG at S05 boundary. |
| O-OCGROUP | ✅ | Fixed 2026-08-02 (F-74/F3): `session_reap_group` / `harness_kill_group` TERM→KILL process group — reaps opencode `serve` linger. |
| O-PIDREG | ✅ | Alias of O-PIDKILLREG — `/tmp/sessions/<tag>.pid` + setsid; instruments `pidreg-ok`. |
| O-FAILSIGFILE | ✅ | Fixed 2026-08-02 (W3-92): `failure-sig.py` parses `java:RULE (n): file:line[,…]` per line; same-line-only legacy. Stops sfix aiming at wrong *Impl/*Test file. Instrument `failsigfile-ok`. Retest: next sfix capture. |
| O-M4REPLAYNOSPEC | ✅ | Fixed 2026-08-02: when no \`^S0N spec:\` tip, O-M4REPLAY fell through to RUN_BASE=HEAD and re-dispatched all T-NNN. Now resume from T-001^ after prior story-complete. Live: RESUME_STORY=S05 RESUME_RUN_BASE=8cabda40. |
| O-PIDKILLREG | ✅ | Fixed 2026-08-02 (F-74/F2): `session-registry.sh` + setsid register; `wait_for_worker`/wedge/residual use identity kill only; unregistered opencode = finding. Retest: next worker session end. |
| O-SESSIONREG-PREFLIGHT | ✅ | Fixed 2026-08-02 (v3 proving): `qg_remote_orchestrator_preflight` in `lib-quality-gates.sh` + `v9-preflight-outer-start.sh`; full golden `.hermes/` tar-sync in `v10-prep-fresh-rerun.sh`. Requires `session-registry.sh`, `bash -n`, sourced `session_register`. |
| O-HERMES-CLI-PREFLIGHT | ✅ | Fixed 2026-08-02 (v3 proving): same preflight gate — `command -v hermes` + `--help`/`--version` in development-tooling before outer start. GitOps `ensure_hermes_xz_shim` when image lacks `xz` RPM (Hermes node extract). Live retest: petclinic-rest-v3 M1 PROFILE past rc=127. |
| O-CGMEM | ✅ | Fixed 2026-08-02 (F-74/F4): DevWorkspace + template `memoryLimit` 6Gi→12Gi (applies at S05 boundary; pod restart expected). GitOps RHDH skeleton in `b2aa626`; repo scaffold `quarkus-migration-scaffold/devfile.yaml` parity in follow-up commit (was 6Gi at HEAD). **Smell:** `b2aa626` mixed gitops + golden harness — split on next wave land. |
| O-MAPUSESEMPTY | ⬜ | v2 S05 T-005 MiniMax: cleared MapStruct `uses=` to `{}` on Owner/Pet/VetMapper during service char tests (claimed CDI UnsatisfiedDependency). May break nested mapping later. Tip: do not empty `uses` to green Arc for unrelated unit tests; fix test classpath/mocks or scope to service package only (pair O-ESCWSCOPE). |
| O-MECHANDOC | ⬜ | v2 S05 T-005 mechanical closure swept `migration/T-005-COMPLETION.md` + run-log into T-NNN tip. `stage_for_task_commit` should exclude ceremonial migration/*.md completion notes (keep tests/pom only). |
| O-CHARVOIDSAVE | ⬜ | Wave2 T-017: MiniMax stubbed `given(repo.save(x)).willReturn(y)` but harvested repos use `void save` → testCompile RED ('void type not allowed'). Tip: for void save/delete use `doNothing().when(repo).save(...)`; prefer real entity beans over mocks when characterizing mutating services (UserService ROLE_). Also mockito-junit-jupiter not on pom — use MockitoAnnotations.openMocks. |
| O-CHARWISH | ⬜ | Wave2 T-016: MiniMax characterization asserted wished Spring Petclinic semantics (Role.user wired, Role dedupe, getPet ignores-new-by-default, Visit null date, insertion-order specialties) instead of AS-IS modernized code. Tip: read entity methods before asserting; characterize actual behavior. Operator-aligned expectations then GREEN 428 tests (`40013bf`). |
| O-CHARREFLECT | ⬜ | Wave2 T-016: reflection tests (`getDeclaredField`/`getMethod`) omitted `throws Exception` → testCompile RED; MiniMax stalled ~20m. Tip/scaffold: characterization reflection helpers declare throws Exception or use assertDoesNotThrow. |
| O-SFIXDUPBASE | ⬜ | Wave2 T-015 sfix: MiniMax extracted BaseDto to clear DTO duplication, then Sonar RED worse (S1128 unused imports + S2160 equals-without-super). Duplication on Simple DTOs should not drive inheritance refactors mid-sensor-fix; prefer accept duplication debt or suppress, not BaseDto. |
| O-SFIXMISDIM | ⬜ | Wave2 T-007: style-autofix rewrote DTO unused-imports (c7e7e53) while milestone RED was Arc UnsatisfiedResolutionException — wrong dimension. Also O-SFIXDIRTY discarded good Jpa*Impl harvest after sfix broke OwnerDto. Wave2 T-011: autofix committed f8ff7df (run-log.md only) while 4× S6813 field @Inject remained — ceremonial no-op; do not count as partial fix. |

## O-M5EVALMUTATE ⬜ — M5 evaluate mutates harvested prod to satisfy invented tests

**Seen:** S02 M5 evaluate MiniMax (2026-08-01) opened `EntityUtils()` (was private)
and rewrote `BindingErrorsResponse` ctor chaining so new util/rest characterization
tests pass — production churn during evaluate, not story Owns rewrite.

**Wanted:** M5 evaluate must not weaken Sonar/fidelity shapes (private util ctor,
harvested API) to green invented tests; prefer fix tests or document residual.
Gate: refuse evaluate commit if src/main harvest diffs vs pre-M5 tip without
explicit residual-debt rationale.

## O-M5SHIPCOV ⬜ — M5 ship invents removed bootstrap for Jacoco coverage

**Seen:** S02 preflight r2 MiniMax recreated `PetClinicApplication` + tests after T-004
Remove, chasing coverage while ignoring O-M5EVALMUTATE harvest mutations and
O-PREFLIGHTDIM cap.

**Wanted:** If coverage RED and bootstrap intentionally absent, escalate-noaction /
document residual — never recreate removed Spring Boot entrypoint. Prefer fix tests
to match harvest over mutating prod (pair with O-M5EVALMUTATE refuse).

## O-M3DUPHARVEST ⬜ — M3 plan re-tasks already-shipped harvest from prior story

**Seen:** S03 MiniMax backstop plan (2026-08-01) T-002 harvests BaseEntity/NamedEntity/Person
already shipped in S02; T-008 is a meta "commit specs" task after M3 already committed.

**Wanted:** plan-lint / brief-diff: refuse tasks whose target paths already exist from
prior story-complete (or mark already-complete AC explicitly). M3 must not invent
ceremonial commit tasks for specs already on tip.

## O-GODNODEORDER ⬜ — god-node harvest before Owner forces scope creep

**Seen:** S03 T-003 (Pet/Visit/PetType) worker also landed Owner.java to satisfy
Pet.owner compile; fidelity RED after tip; style-autofix then touched unrelated
EntityUtils tests (1548dc4).

**Wanted:** plan-lint order: harvest Owner (and other Pet dependencies) before
or with god-nodes; or allow compile with stub only in staging. Scope sensor should
flag Owner as O-ESCWSCOPE when not in T-003 Owns unless explicitly paired.

## O-SFIXRESCUE ⬜ — MiniMax sfix rescue after Qwen already cleared RED dims

**Seen:** S03 T-003: Qwen sfix committed Pet.getVisits fidelity fix (`6264acd`);
dims fidelity+sonar GREEN; MiniMax rescue still launched because milestone was
RED at handoff / O-SFIXLOOP refused milestone, then thrash on GREEN findings.

**Wanted:** Before MiniMax rescue, re-run dimension sensors; skip rescue if
fidelity+sonar+task GREEN. Do not burn MiniMax on stale milestone RED.

## O-ENTITYDS ✅ — default-profile datasource required once @Entity lands

**Seen:** S03 T-003: task sensor GREEN (%dev H2) but milestone `mvn verify` RED —
Quarkus Hibernate could not find datasource `<default>` because JDBC was
`%dev.`-only. After god-node entities, package/verify failed → O-DEBTFRZ.

**Fixed:** unprofiled H2 defaults in `application.properties` (O-ENTITYDS comment).
Live tip commit on petclinic-rest-v2. Prefer same in scaffold for deploy=false
entity harvest stories.

## O-M5JDBCSONAR ✅ — M5 preflight Sonar GREEN after JDBC/JPA coverage tips

**Seen:** S04 M5 after dual-Arc tip (`quarkus-spring-data-jpa` removed): preflight
past Arc/fidelity; Sonar RED — ~27 new violations + ~0% new coverage on
`jdbc/*` `@Alternative` harvest. style-autofix only partial; MiniMax preflight
raced and corrupted pom / deleted JPA.

**Progress 2026-08-01:** violations cleared; new_coverage ~72% after JDBC+JPA
tests + O-JACOCOARGLINE/O-JACOCOREUSE. Still short of 80% (delete/save tails).

**Fixed 2026-08-01:** preflight GREEN after coverage tips + jacoco wiring
(O-JACOCOARGLINE/O-JACOCOREUSE). Supervisor-pause cleared for ship.

## O-JACOCOARGLINE ✅ — surefire must consume jacoco `@{argLine}`

**Seen:** S04 M5: `JdbcRepositoryCoverageTest` GREEN but Sonar/jacoco showed
jdbc/* at 0% after `@QuarkusTest` landed — surefire omitted jacoco agent
(`argLine`), so plain JUnit never wrote `jacoco-quarkus.exec`.

**Fixed:** empty `<argLine></argLine>` property + surefire `<argLine>@{argLine}</argLine>`
in live petclinic pom (tip). Mirror into scaffold default pom when present.


## O-JACOCOREUSE ✅ — QuarkusTest must not wipe plain-JUnit jacoco exec

**Fixed 2026-08-01:** `quarkus.jacoco.reuse-data-file=true` + shared
`target/jacoco-quarkus.exec` (with O-JACOCOARGLINE surefire `@{argLine}`).

## O-SHIPPFSTALE ⬜ — M5 ship preflight-fix ignores tip-GREEN between seats

**Seen:** S04 M5: tip made `sensors.sh preflight` GREEN (`08c9981`) while
supervisor was paused; on pause-clear MiniMax still launched on stale
`/tmp/preflight-failure.txt` RED and burned seats.

**Wanted:** Before each preflight-fix Hermes seat, re-run preflight (or trust
fresh GREEN log newer than failure file). If GREEN, skip MiniMax and proceed
to ship. Do not relaunch correction on stale RED evidence.

## O-SUREFIREIT ✅ — Surefire skips `*IT.java` by default

**Seen:** S04 M5 factory gate: local preflight GREEN with `JpaRepositoriesIT`
(@QuarkusTest) but Tekton maven-build never ran it (160 tests, no QuarkusTest)
→ Sonar new_coverage 66.7% with jpa/* at 0%.

**Fixed:** rename to `*Test.java` + surefire `<includes>` for `**/*IT.java`.

## O-MMRESET ✅ — MiniMax/hygiene must not reset honest Gate fix tips

**Seen:** S04 M5: after tip `605649d` Gate fix r1, MiniMax gate seat ran
`git reset --hard HEAD~1`, discarded the fix, added mockito test that does
not compile, then ship declared gate exhausted.

**Wanted:** Forbid hard reset in ship/gate prompts; sensor-gate on dirty/reset;
if tip commit matches `Gate fix rN:` prefix and milestone GREEN, skip MiniMax.


## O-JDBCREGRESSFALSE ✅ — hygiene only flags *new* spring-jdbc adds

**Seen:** S04 Gate fix r1 (surefire includes) touched pom.xml; O-JDBCREGRESS
reset the tip because spring-jdbc/tx already present for honest JDBC CDI.

**Fixed:** `commit-hygiene.py` compares tip pom vs parent — only net-new
spring-jdbc/tx/orm artifacts trip O-JDBCREGRESS.

## O-GODORDERUNSET ✅ — S-GODORDER mid-skip must not fire when RUN_BASE unset

**Seen:** v3 S03 M3 tip `573cc08` (2026-08-03): outer plan-lint GREEN while supervisor RED `LINT:S-GODORDER` (PetTypeRepository).
Root cause: `_tip_already_committed` used `git log HEAD --grep ^T-NNN:` when `RUN_BASE` unset → matched prior-story T-001 tips → false O-GODORDERMID skip.

**Fixed 2026-08-03 wakes #219–#224:** return False when RUN_BASE unset; mid-run skip only with `RUN_BASE..HEAD`. Hot-swapped pod plan-lint. Retest: tip tasks unset RUN_BASE → S-GODORDER RED (rc=1).

## O-M3TASKSCOPE ✅ — plan-lint must RED Target paths outside --story-scope

**Seen:** v3 S03 M3 tip `573cc08` (2026-08-03 wakes #219–#224): `PLAN OK` with `--story-scope` = repository paths only,
while T-004 Target design harvests `service/ClinicServiceImpl` + `UserServiceImpl` (later-story scope).
O-M3DTOSCOPE correctly skips out-of-scope *incidents*; it did **not** reject out-of-scope *task Targets*.

**Fixed 2026-08-03:** plan-lint `O-M3TASKSCOPE` — when `--story-scope` is set, RED any non-test Target/`→`
destination outside roadmap scope (legacy↔target package remap + sibling dir under scoped parents).
Characterization `src/test/` and Out-of-scope/Absorbs deferral lines skipped. Instruments RED+GREEN;
hot-swapped md5 `8870a0a3`. Retest: tip `573cc08` + parse-roadmap S03 SCOPE → 2× `LINT:O-M3TASKSCOPE` on service Targets.

## O-M3LINTPROCEED ✅ — m3-lint exhaustion must not enter M4 on RED plan

**Seen:** v3 S03 (2026-08-03 wakes #225–#228): tip `573cc08` false-green; supervisor `plan lint: revision required`;
MiniMax `m3-lint` a1 burned (Hermes `repeated_exact_failure_block`, no `M3 revision:` commit). Dirty
`tasks.md` still RED under fixed lint (`O-M3TASKSCOPE`×2 service Targets + `S-GODORDER`; Out-of-scope
waiver removed). `supervisor.sh` after `run_stage m3-lint` failure: *"revision round exhausted —
proceeding with the plan as-is"* then re-lint *"still failing after revision — proceeding"* → M4.

**Fixed 2026-08-03:** supervisor always re-lints before M4; on non-zero → log `O-M3LINTPROCEED`,
write `/tmp/plan-lint.txt`, set `/tmp/supervisor-pause`, `supervisor-done=m3-lint-hold`, exit 1
(no TASK_IDS / M4). Outer maps `m3-lint-hold*` → story HOLD + `fail_run` (re-M3, not advance).
Instrument `m3lintproceed-ok` (no proceed-as-is strings; O-M3LINTPROCEED + m3-lint-hold wired).
Hot-swap + abort/re-M3 under fixed lint owed this wake.

## O-M3DIABSORB ⬜ — multi-story findings-scope needs Absorbs help

**Seen:** S05 M3 (2026-08-01): `springboot-di-to-quarkus-00003` spans repos/services/REST/security.
Worker hung on plan-lint RED (O-M3ACCEPT path literal + K1 unowned prior/later files).
Absorbs bullet lists are ignored (parser only reads same-line tokens / `→ src/` claim lines);
legacy paths in Target position trip LINT:package.

**Wanted:** M3 fix prompt + PLANNING tip: for shared finding ids, emit Target `legacy → targetPackage/...`
arrows (or same-line Absorbs of target paths) for prior-story and later-story incidents; never put
acceptance.path literal in non-deploy tasks.md. Optional: plan-lint treat target-tree files from
completed stories as already owned.

## O-S112LEGACYTHROW ✅ — harvest `throws Exception` + NOSONAR / fidelity

**Seen:** S05 T-003 milestone sonar: `UserService.saveUser(... ) throws Exception` (faithful Spring harvest) → java:S112; style-autofix 0 files.

**Also S05:** T-003-sfix-w *removed* an existing tip NOSONAR on UserService (undo). Sfix prompts must not strip NOSONAR/preserve markers. MiniMax tip with findings.json churn → O-SFIXSCOPE reset; inline NOSONAR failed harvest-fidelity after O-FIDSONAR throws-strip (EOL comment left on normalized line).

**Fixed 2026-08-01:** tip NOSONAR on preserved signature (`a8466e1`); **O-FIDEOLCOMMENT** — `harvest-fidelity.py` strips end-of-line `//` comments so NOSONAR does not false-RED. Scaffold + live harness synced. Sfix-undo still a prompt smell (watch).

## O-FIDEOLCOMMENT ✅ — fidelity must strip end-of-line `//` comments

**Seen:** S05 T-003 — after O-FIDSONAR strips `throws …`, staged `void saveUser(User user);` ≠ dest `void saveUser(User user); // NOSONAR …` → FIDELITY RED / O-DEBTFRZ.

**Fixed 2026-08-01:** `normalize()` strips `\s*//.*$` after comment-only-line skip (scaffold + live `.hermes/harness/harvest-fidelity.py`).

## O-ESCTERM60 ⬜ — Hermes 60s terminal kills `git commit` + task-sensor hook

**Implemented 2026-08-01 (retest-owed on next Hermes gated commit):** `commit-gated.sh` + EXECUTION tip + escalation/continue prompt line.

**Seen:** v2 S05 T-005 MiniMax escalation (2026-08-01): staged Clinic/UserServiceImplTest + mockito pom;
`git commit` invoked via Hermes terminal timed out at 60s three times while commit-msg/pre-commit
runs full `sensors.sh task` (Quarkus test boot ~10s + suite). Tip stayed at T-004; agent also hit
MaaS 429 token limits mid-retry and `python3 -c` deny for jacoco XML.

**Wanted:** Longer terminal timeout for commit/sensor commands in escalation path, OR two-phase
commit (hook-skip + supervisor post-verify). Document so MiniMax does not thrash 60s commits.
| O-M3EMPTYTASKS | ✅ | Fixed 2026-08-02 with O-M3EMPTY: PLANNING.md + EXECUTION.md require `tasks.md` first; abort 360s. Retest-owed on fresh re-run M3. |
| O-T6WRONGTITLE | ✅ | Fixed 2026-08-02: Convert/Port/Migrate titles excluded from removal-already-absent; absent-removal requires empty stage after ignore. S06 T-001 false tip reset. Instrument t6wrongtitle-ok. Retest: next Convert mechan. |
| O-RESTCREATE | ⬜ | S06 T-001: Qwen rc=0 clean tree — never wrote OwnerRestController (Target absent); ESCW3 correctly blocked; MiniMax escalated. Tip/skill: Convert REST when dest missing = create from legacy harvest, not noop. Retest: next Convert REST with absent dest. |
| O-ESCWDEBT | ⬜ | S06 T-001: after O-DEBTFRZ, O-ESCW claimed already-satisfied with HEAD=`debt: T-001…` tip — must never ESCW against debt/scope-revert subjects. |
| O-SFIXTESTCOMP | ⬜ | S06 T-001 sfix added OwnerRestControllerTest with Mockito thenReturn Set type errors → task RED → debt; dirt discarded restored GREEN. sfix should not invent broken tests that poison the task sensor. |
| O-DEBTFRZRACE | ✅ | Fixed 2026-08-02: `discard_src_dirt` + `record_debt` re-runs task\|milestone\|sonar on clean tree; false-red averted skips debt/freeze. Post-sfix paths recheck after O-SFIXDIRTY. Instrument debtfrzrace-ok. Retest-owed: next sfix GREEN-then-orphan-dirt path. |
| O-ORPHANOC | ⬜ | After O-ESCW/already-satisfied, MiniMax/Qwen opencode (pid ~23m) stayed alive unregistered and kept writing broken tests. ESCW/complete must harness_kill registered + ledger-kill known session tags for that task. |
| O-RESTREADTHRASH | ⬜ | S06 T-002: Qwen READ_THRASH (21r/0w) on Convert VetRestController when Target absent — same O-RESTCREATE class as T-001; worker needs create-from-legacy tip before first mutate, or earlier FIRSTMUT kill with create brief. |
| O-RESTS2589 | ✅ | S06 T-004 milestone: Sonar S2589 on Visit/Pet RestControllers (redundant null/id checks harvested from Spring). Skill tip: after JAX-RS convert, drop always-true/false guards; style-autofix cleared S1128 but not S2589. |
| O-SFIXMILESTONE | ✅ | S06 T-004 sfix: Qwen ran sensors.sh milestone → REFUSED (O-SFIXLOOP); burned full 15m seat then MiniMax rescue. Sfix prompt must say sonar|task only for post-milestone RED; never instruct milestone re-run. |
| O-IFACERENAME-REST | ✅ | S06 T-005/T-007: Qwen renames legacy public methods for "correctness" (getAllSpecialtys→Specialties; addOwner→addUser) → redesign-sig RED → MiniMax. Tip must: copy legacy method names verbatim from staging/oracle; never rename for grammar/semantics. |
| O-QWENJUNKFILE | ⬜ | S06 T-007: Qwen left empty untracked \`CDI\` file at repo root. Worker/session cleanup should drop non-target artifacts before exit; O-SFIXDIRTY-style discard for stray root files. |
| O-RESTINVENTCRUD | ⬜ | S06 T-007: MiniMax expanded UserRestController beyond staging (only addOwner) inventing get/update/delete + missing UserService APIs → compile RED / bad tests. Escalation must stay staging-faithful for Shape=modify Oracle=present — do not invent CRUD surface. |
| O-SFIXDIRTYLEAD | ✅ | Lead discarded out-of-scope User* mapper/repo/service dirt + CDI + poison UserRestControllerTest during MiniMax 15m quota backoff; committed staging-faithful T-007. |
| O-WORKERSTALL | ⬜ | S06 T-008: Qwen wrote RootRestController+test then sat ~25m with no commit until lead killed (rc=143). Need FIRSTMUT/idle-after-dirt kill or post-write commit nudge when Target file exists and tree dirty. |
| O-CREATEFIRSTMUT | ✅ | Fixed 2026-08-02: Shape=create injects O-CREATEFIRSTMUT first-write tip + `WORKER_READ_GLOB_MAX=10`; EXECUTION.md + PLANNING.md updated. Retest-owed: next create task on re-run. |
| O-M3EMPTY | ✅ | Fixed 2026-08-02: default `M3_EMPTY_ABORT_SECS=360`; PLANNING.md requires `tasks.md` first. Prior empty-detect logic retained. Retest-owed: next M3 worker seat. |
| O-EXMAPSPRING | ✅ | Fixed 2026-08-02: lead tip `35b8197` maps PersistenceException→503 / ValidationException→400 / EntityNotFound+ObjectRetrieval→404 via ExceptionMapper&lt;Throwable&gt; (V6 R6 forbids ExceptionMapper&lt;Exception&gt;); no Spring DAO. Skill tip: ExceptionMapper create tasks prefer jakarta/app types. Retest: T-009 tip GREEN. |
| O-RESTAPIPREFIX | ⬜ | S06 T-001..T-008 Convert REST landed `@Path("/vets")` etc; staging is `api/vets`. Acceptance `/petclinic/api/vets` failed until T-010 added `/api` prefix. Tip: harvest `@RequestMapping("api/…")` into JAX-RS `@Path("/api/…")` on Convert. |
| O-ACCPATHROOT | ✅ | Fixed 2026-08-02: `acceptance_path_handler` stripped only full path / bare leaf — missed `@Path("/api/vets")` under `quarkus.http.root-path=/petclinic`. Now strips root-path and matches resource `@Path` / embedded leaf. Retest: STORY_DEPLOY=true sensors.sh static. |
| O-PRODSCHEMA | ✅ | Fixed 2026-08-02 seed path; **corrected 2026-08-02 Wave3**: unprofiled `drop-and-create` is forbidden (prod schema drop on boot — W3-131/132). Use `%dev`/`%test`/`%acceptancetest` only; `prod_schema_contract` + commit-hygiene enforce. |
| O-ACCEPTCRUD | ⬜ | S06 T-010: MiniMax wrote 15 CRUD/400 acceptance tests beyond migration.yaml acceptance.path; BindingErrorsResponse Jackson 500 → RED. Escalation must prefer GET acceptance.path + array body only. |
| O-BINDERRJSON | ✅ | Fixed 2026-08-02 tip `91eeca1`: BindingError + getBindingErrors getters so Quarkus Jackson can serialize entity(BindingErrorsResponse). Retest: preflight GREEN. |
| O-SFIXPOSTCOMMIT | ⬜ | S06 T-009: MiniMax tip `2f6e81c` GREEN at commit then post-commit task RED from untracked poison PetClinicExceptionMapperTest (ConstraintViolation ctor) → O-SFIXSCOPE archive+reset. Escalation must not leave inventing tests untracked after commit-gated; commit-gated should refuse if untracked test dirt under Owns. |
| O-ESCALAFTERRESET | ✅ | Fixed 2026-08-02: `post_reset_escalation_gate` after O-SFIXSCOPE reset — prefer mechan/ESCW on GREEN dirt, discard orphan src/ poison + re-sensor, CONTINUE injects invent ban. Instrument escalafterreset-ok. Retest-owed: next worker RED tip → reset → escalation. |
| O-SECJDBCDEP | ✅ | Fixed S07 T-002 lead `e7ce56d`: use **`quarkus-elytron-security-jdbc`** (BOM-managed); bare `quarkus-security-jdbc` fails POM (missing version). Tip/skill: JDBC basic-auth stories add elytron-jdbc with security. |

| O-WORKERWEDGESKIP | ⬜ | S07 T-002: O-WORKERWEDGE JSON_STALE → sticky skip further Qwen seats for story (MiniMax-only). Prefer first-write scaffold for Shape=create so wedge never fires; optionally clear sticky after lead tip GREEN so later tasks can retry worker. |
| O-ALREADYPROP | ✅ | Fixed 2026-08-02: `already-complete.py` — Target/Owns `.java` blocks preserve-token skip (`target_java_blocks_preserve`). Instrument: missing BasicAuth + preserve token → rc=1. Retest-owed: fresh re-run S07-class security story. |
| O-T6EEMPTYESC | ✅ | Fixed 2026-08-02: `escw-eligible.py` — pom/dep tasks with named `quarkus-*` artifactIds already in pom → `pom-deps-present` ESCW even if findings-oracle still present. Instrument + O-ESCW path. |
| O-KANTRAMISS | ✅ | Fixed 2026-08-02: M5 calls `kantra-ensure` then analyzes; if binary still missing, substitutes `mta-findings-current.json` / `mta-findings.json` as after-scan. |
| O-RESUMEBASEEXCL | ✅ | Fixed 2026-08-02: `committed()` includes `git log -1 $RUN_BASE` so tip at RESUME_RUN_BASE counts. Wire instrument. |
| O-ALREADYFINDING | ✅ | Fixed 2026-08-02: `annotation_work_incomplete` blocks oracle-absent skip when RolesAllowed/PreAuthorize work still missing on Owns/Target. Instrument: VetRestController without @RolesAllowed + oracle absent → rc=1. |
| O-WIREUP | ✅ | Fixed 2026-08-02 (W3-141): `wireup-check.py` — staging `@Around`/`@Aspect`/… requires dest CDI attachment or ≥1 consumer; empty `@ApplicationScoped` RED. Task/static sensor. Fixture: CallMonitoringAspect. **FP fix W3-150:** package-private `@ConfigProperty`/`@Inject` fields count as members (O-WIREUP-FP). |
| O-DESTBASE | ✅ | Re-fixed 2026-08-02: oracle-absent skip no longer blanket-blocked by `is_convert_task` — `missing_target_path` covers O-ACRESTABS; Convert+scaffold-presatisfied parent-pom may skip again. Expanded static list 2026-08-02 (W4-024 follow-up): `javaee-pom-00060`, `springboot-actuator-0100`, `springboot-metrics-0100`, `springboot-cache-00000` — S01 plan-lint was RED on unowned pom incidents after POM tasks dropped, forcing false O-M3SKIP MiniMax burns. |
| O-TMPARCHIVE | ✅ | Fixed 2026-08-02 (W3-150) success path; **fail-path 2026-08-03 wakes#207–218:** `archive_tmp_forensics` + `trap EXIT` so debt-freeze/X FAIL archive too (W4-029b). `migration/run-archives/` gitignored. |
| O-ALREADYREPL | ✅ | Fixed 2026-08-02 (W3-140): `replacement_constructs_missing` — named `quarkus-*` in Goal/Acceptance/Target must be in pom before already-complete skip. |
| O-M5STALE | ✅ | Fixed 2026-08-02 (W3-146): failed/substituted after-scan → `STALE-AFTER` + `stale_resolve_pct=UNSCORED`; no RESOLVED credit; drop "honest". |
| O-KANTRAPATH | ✅ | Fixed 2026-08-02 (W3-99/145): default `KANTRA_HOME=/projects/.tools/kantra` (PVC); `kantra-path.sh` + gitops kantra-ensure; /tmp fallback only. |
| O-SECAUTHTEST | ✅ | Fixed 2026-08-02 (W3-142): sensor requires 401/403 test when `@RolesAllowed` + `*.security.enable` present; EXECUTION tip `@TestProfile`. |
| O-SIGINT | ⬜ | Wave3: 8/15 non-zero exits are rc=130 SIGINT; harness kills use TERM/KILL only. O-ESCALCAUSE now labels `sigint`. Root source still unknown (OpenCode/session?) — watch kill-ledger on next run. |
| O-SFIXNOSPRINGSDATA | ✅ | Fixed 2026-08-02 (W3-70): `sfix-no-spring.py` keys on any `quarkus-spring-*` artifact, not only `quarkus-spring-data-jpa`. |

## Wave-3 close counsel (Fable 5 — banked 2026-08-02)

Strategic backlog after S01–S07 ship. **Honesty gates from the Wave-3 retro
(O-WIREUP…O-KANTRAPATH) are separate and already ✅.** These rows are the
quality / performance / durability frontier — do not treat full bank-gate
as a wipe blocker except where noted.

| ID | Status | Note |
|----|--------|------|
| O-COMMITSHRINK | ⬜ | F-75/A1: session→commit silent test shrink (T-010 413→90→29). Gate: undeclared net drop of tests/asserts vs session tree → refuse. **W4-059a:** also cover `git reset` / clean-resume paths (evaluate-authored Role/Specialty/User/Vet tests dropped on rewind past `edd3dd5` — coverage hole left with no task Owns). **Highest pre-rerun quality item that touches delivery.** One-time S06/S07 audit owed. |
| O-RESUMEPROV | ⬜ | W4-059b: clean resume that discards tips (debt-freeze / fidelity-RED / dishonest M5) must append a provenance block to `migration/run-log.md` before first new commit — SHAs discarded, why, files/tests/asserts lost. Else story-state + run-log erase the failure episode (v3 S02 70bda70 rewind left zero durable debt-freeze evidence). |
| O-DEGRADED | ✅ | F-75/A2 largely covered by **O-M5STALE** (STALE-AFTER / unscores). Extend stamp to run-report sections if needed. |
| O-FRZFALSE | ⬜ | F-75/A3: retry-before-freeze (2-of-2 RED) + flake ledger. |
| O-LOGCOLLIDE | ✅ | Fixed 2026-08-03 wakes#207–218: supervisor `oc_seat_base` keys `/tmp/oc-<STORY_ID>-<tag>.{json,err}`; outer exports `STORY_ID`. Prevents S03 T-001 clobbering S02 seat corpus. Instruments logcollide-ok. |
| O-HDRFIDELITY | ⬜ | F-75/A5: harvest-fidelity licence-header preservation. |
| O-PLANSKEL | ⬜ | G6: `plan-skeleton.py` at M3 — compile task universe from M1 artifacts; model fills judgment slots. Spec: `tmp/GENERAL-HARNESS-IMPROVEMENTS.md` §7. Retroactive validate vs W2/W3 plans before live. |
| O-DECIDE | ⬜ | G9: Decisions section in skeleton (with G6). Highest quality-per-effort for silent-choice losses. |
| O-MAPGEN | ⬜ | N5 — already banked above; land before specimen #3 M1. |
| O-RULELINKS | ⬜ | N6 — already banked above; same extraction pass as N5. |
| O-RECIPEPREPASS | ⬜ | G4/N16 — already banked; performance: kill whole mechanical worker seats. |
| O-GOLDENFRESH | ✅ | Closed wake#387 — see primary bank row (publish-fp + three-way preflight). Still pair wave-close commit + full golden `.hermes` tar-sync before next provision (O-HERMESSYNC). |
| O-HERMESSYNC | ✅ | Fixed operationally 2026-08-02: wipe/start recipe must tar-sync entire golden `.hermes/` (not a short file list). Documented in `tmp/V10-V3-RUN-STATUS.md`; bake into `v10-prep-fresh-rerun.sh` / preflight next. |
| O-M2-FREEZE-JUNK | ⬜ | v3 `10203cd`: M2 commit bundles **57** `.hermes/` paths (golden harness sync + AppleDouble `._*` / `__pycache__` junk) alongside `migration/roadmap.md` + briefs. `roadmap-lint` GREEN but commit hygiene dishonest. Durableize: `freeze-harness.sh` / outer M2 gate must refuse junk paths; split harness sync from `M2 sequence:` subject or use commit-gated allowlist (migration/ only). |
| O-DTOHARVEST-SONAR | ✅ | v3 S01 T-001: milestone Sonar RED (+79→coverage/CPD/S6353) on OpenAPI dto harvest; live pod lacked `sonar.*exclusions` for `**/dto/**`. Fixed 2026-08-02: `ensure-dtocov-pom.py` + supervisor post_commit_verify auto-commit before milestone sensor; golden scaffold pom already had O-DTOCOV props. Retest: resume v3 past debt with pom patch + sfix path. |
| O-SFIXNODELTA | ✅ | Fixed 2026-08-02 (W4-011): after K7 failure-delta / before O-SFIXWORKER, if `SUMMARY new=0 gone=0` AND tip is empty or structure-only (`.gitkeep` / `package-info.java` / 0 numstat) → log `O-SFIXNODELTA`, `sfix_nodelta_skip`, return without seat burn. Prefer skip+continue over task-attributed MiniMax. Instruments + EXECUTION tip. Was: v3 T-004 0-byte tip → sfix edited pom.xml. |
| O-SFIX-K7-vs-sonar | ⬜ | v3 S01 T-001-sfix: K7 failure-delta lists **8** new violations (S1874/S6353) but milestone sonar gate reports **22** (+ duplication QG lines). Worker sfix packet may under-scope work; durableize K7 capture to include all in-loop sonar blockers or align delta with sensors.sh sonar output. |
| O-K5MILESCOPE | ✅ | Fixed 2026-08-02 (v3 S01 T-001): in-loop milestone K5 used full `PLAN_SCOPE` → RED on 3 pom incidents (native/metrics) owned by later tasks. `findings-milestone-scope.py` + supervisor/sensors in-loop scope = **Findings** on completed T-NNN tips only; preflight `milestone full` keeps story scope. Instrument O-K5MILESCOPE. Retest: v3 @441d99c milestone after O-DTOCOV. |
| O-K5WAIVELEAK | ✅ | Fixed 2026-08-02 (v3 S02 T-007): empty in-loop Findings sets `FINDINGS_K5_WAIVED=1`; `findings_sensor` returns GREEN waive — no `${FINDINGS_SCOPE:-${PLAN_SCOPE}}` / `--scope-all` fallthrough (was false RED on `springboot-metrics-to-quarkus-0200` after K5 waived message). Instruments wired. W4-045b: fixture asserts `O-K5WAIVELEAK` tag + no FINDINGS RED (ok 290/291 @354/356). Was: v3 S01 T-004 same leak.

| S-GODORDER | ✅ | Fixed 2026-08-02 (Claude Round3 / lead): plan-lint requires earlier-indexed characterization naming each god-node class before harvest (marks from dependency-order.md). Fixtures inverted-RED / correct-GREEN / non-god-OK. Complements S-CHAR existence-only.
| O-GODORDERMID | ✅ | Fixed 2026-08-02 (W4-048a): mid-M4 hot-swap must not force MiniMax to renumber already-committed T-NNN tips. `plan-lint` S-GODORDER skips harvest tasks whose `T-NNN:` tip is already in `RUN_BASE..HEAD` (WARN only); fresh M3 (no tip) still REDs. Retest: v3 S02 discard dirty renumber + scoped lint → PLAN OK; resume T-008 worker-first.
| O-GODORDERMIDINST | ⬜ | W4-049a P3: `O-GODORDERMID` landed with **0 instruments** (plan-lint.py=2). Add fixture: mid-run plan with executed god-node harvest tips must WARN-skip S-GODORDER (not RED); fresh plan with same shape still RED. Conditional suppression of another guard — most likely to rot silently.
| O-OWNSTAGE | ✅ | Fixed 2026-08-03: `stage_for_task_commit` allowlists Owns/Target via `task-stage-paths.py` (no sibling `git add -A` scoop); `mechan-match.py` REDs `ownstage-extra` on create/harvest. EXECUTION tip. Instruments ownstage×2. Retest-owed: next multi-entity harvest tip must leave non-Owns siblings unstaged / refuse mechan tip with extras. |
| O-M3SHAPEHARD | ✅ | Fixed 2026-08-02: plan-lint Shape default HARD (O-SHAPEDECL RED). Grandfather PLAN_LINT_SHAPE_WARN=1 or PLAN_LINT_REQUIRE_SHAPE=0 for legacy fixtures. W4-045a: `instruments.sh` suite exports `PLAN_LINT_SHAPE_WARN=1` by default so ~20 pre-Shape fixtures stay WARN; dedicated O-M3SHAPEHARD case unsets the flag (ok 178). Suite 354/356 (residual O-QJACOCO + O-IFACERENAME only). outer-loop M3_LINT_CMD + drafter self-verify share the hard bar without env choreography.
| O-M4-OCJSON-STASIS | ⬜ | v3 T-001-sfix-w: OpenCode **900s** with `/tmp/oc-T-001-sfix-w.json` mtime frozen **≥14m** then timeout → MiniMax rescue. Supervisor should heartbeat on oc-json growth during sfix (like M3 log mtime) and early-abort empty-write seats (**O-SFIXSTALL**). |
| O-SFIX-PROMPT-CONFLICT | ✅ | v3 T-001-sfix-w: prompt opened with “milestone sensor RED” while O-SFIXLOOP refuses milestone; supervisor post-worker recheck also called `sensors.sh milestone` under fix-mode → REFUSED → false MiniMax rescue. Fixed 2026-08-02: `SFIX_RED_DESC` dimension copy + `sfix_loop_recheck` uses sonar|task|findings during sfix. Retest: T-001 sfix without 900s refuse loop. |
| O-DEMOREPLAY | ⬜ | B6: record blessed W3 run for workshop replay. Capture now while tip `d7a278b` + artifacts exist. |
| O-CGMEM | ✅ | Template `memoryLimit` 12Gi (gitops + repo scaffold). Counsel said 13Gi — confirm live cgroup; raise template if measured 13. Do not re-patch per workspace. Co-landed gitops slice in harness wave commit `b2aa626` — prefer separate gitops vs harness SHAs going forward. |
| O-W3RETROPROOF | ⬜ | Formal Wave-3 retro close: signal-death % vs &lt;10% target, corrections vs halving, kill-ledger ⨝ session table (every rc has cause). Credibility artifact for demo. |
| O-DOCPROMOTE | ⬜ | Promote V2/GENERAL/RAG + Wave retros + F-73 RCA from `tmp/` → `docs/`; archive wave reviews with V-series. D2 coverage bar → factory config. |
| O-MONSCHEMA | ✅ | Fixed 2026-08-02: `scripts/track-b/v10-monitor-seat-enrich.py` + dual-monitor loop emit tools/ttfw/sensor_delta (+ rc/signal/killer, budget_used, last_utterance, guard_refusals). Schema: `tmp/V10-V3-MONITOR-SCHEMA.md`. Cursor Hermes/Qwen monitors instructed to use enricher. Retest-owed: next T-NNN activity lines show enriched block. |
| O-MONNOWAVE4 | ✅ | Fixed 2026-08-02: dual-monitor + Cursor Hermes/Qwen monitors write **only** `tmp/V10-V3-MONITOR.md`; no more `### Monitor note` mirrors into `tmp/KAI-WAVE4-REVIEW.md`. Opus fingerprints MONITOR.md (Standing Rule #2). Schema + MONITOR header + WAVE4 O-REVDOC pointer updated.
| O-INSTREGRESS | ✅ | Fixed 2026-08-03 wakes#207–218: QJACOCO instrument seeds `@QuarkusTest` (O-QJACOCONOTEST SKIP was false-GREEN); redesign-sig IFACE_METHOD matches single-line `{ Type name(); }` (O-IFACERENAME fixture). |
| O-LOCKSTALE | ✅ | Fixed 2026-08-03 wakes#207–218: outer+supervisor `clear_stale_pid_lock` (`kill -0`) before flock; logs `O-LOCKSTALE cleared pid=<n>`. Instruments lockstale-ok. |
| O-SFIXTESTPAIR | ✅ | Fixed 2026-08-03 wakes#207–218 (W4-057a): fidelity sfix packet includes `sfix_test_pair_note` — `git grep` coupled `src/test` files for FIDELITY: classes; same-commit revise tests after harvest revert. Instruments sfixtestpair-ok. |
| O-SFIXMUTATE | ✅ | Fixed 2026-08-02 wake#153–156: `run_worker_prompt` *sfix* polls oc-json; kills on WORKER_MUTATE_DEADLINE_SECS (default 120) with 0 edit/write or JSON stale 180s; EXECUTION + SFIX_PROMPT first-mutate tip. Instruments sfixmutate-ok. Retest-owed: next fidelity sfix must mutate or early-escalate &lt;900s. |
| O-STYLEFIDELITY | ✅ | Fixed 2026-08-02 wake#153–156: `park_src_dirt_for_autofix` + `style_autofix_stage` (src-only, never git add -A scoop); fidelity pre/post revert src/main on worsen; refuse fidelity-RED main in partial tip. EXECUTION collection-getter tip. Instruments stylefidelity-ok. Retest-owed: autofix with dirty harvest leftovers must not tip Set.copyOf-style drift. |
| O-M5EVALTESTMAIN | ✅ | Fixed 2026-08-02 wake#153–156: after M5 evaluate tip, tests-without-main + task RED → reset tip + debt. Prompt forbids split. Instruments m5evalhonesty-ok. Retest-owed: evaluate must co-commit main+tests or omit tests. |
| O-M5PRECLAIM | ✅ | Fixed 2026-08-02 wake#153–156: after preflight RED, rewrite tip subject `preflight=GREEN` → `preflight=RED` (O-M5PRECLAIM). Paired with L-M5e. |
| O-M5EVALBURN | ✅ | Fixed 2026-08-02 wake#153–156: prompt requires findings-delta/run-log commit on preflight RED; mechan `O-M5EVALBURN` tip if model seat exits with no evaluate commit. |
| O-SFIXRESCUEDISCARD | ✅ | Fixed 2026-08-02 wake#152: `sfix_commit_green_dirt` tips cited-dim GREEN dirty tree before full milestone re-verify/O-SFIXDIRTY discard; keep tip + debt when cited dims GREEN but full sensor still RED. Instrument sfixrescuediscard-ok. Retest-owed: next MiniMax sfix rescue GREEN-on-dirty. |
| O-SFIXSIGINT | ✅ | Fixed 2026-08-02 wake#152 (paired with O-SFIXRESCUEDISCARD): after orch return (incl 124/130) always try tip/archive of cited-dim GREEN dirt before teardown/discard. |
| O-DEBTMSUBJ | ✅ | Fixed 2026-08-02 wake#152: host O-DRV3/O-DRV6 match `debt: .*RED` / `debt: ` (milestone m5-evaluate tips), not only `debt: T-NNN`. |
| O-DEBTSHIPRACE | ✅ | Fixed 2026-08-02 wake#152: M5 ship refuses when `/tmp/debt-freeze` present (exit 78) — no parallel preflight-fix round. |
| O-SHIPASSERTWEAK | ✅ | **Retest 2026-08-02 wake#175–177:** tip `14dd6c2` kept typed `assertThrows(UOE)` on Owner/Pet/Vet unmodifiable getters (no rename/drop). Fixed 2026-08-02 wake#172: `sensors.sh ship_assert_weaken` refuses `returnsListWithExpectedBehavior` + catch(Exception) “expected”; `refute-diff.py` REFUTES rename/UOE-drop (K12); EXECUTION S5778 tip keeps typed `assertThrows(UOE)` with arrange-outside-lambda. Instruments shipassertweak. **Live tip `eaaa501` still carries weaken — HOLD/REJECT ADVANCE; restore asserts or abort before unpause.** Retest-owed: next Preflight/sfix tip with S5778 must keep UOE contract (sensor RED on rename).
| O-SHIPFIXCOMMIT | ✅ | **Retest 2026-08-02 wake#175–177:** MiniMax tipped `14dd6c2` Preflight fix r1 on task-GREEN tests-only dirt before full preflight/sonar. Fixed 2026-08-03 wake#173–174: `pref_commit_green_dirt` tips task-GREEN tests-only dirt (`src/main` clean) on preflight/gate/build-fix timeout/`no_commit` and at attempt exhaustion — does not require full preflight GREEN. Prompt + SHIPPING require commit-before-sonar. Instrument shipfixcommit-prefcont-ok. **Live tip `eaaa501` still dishonest — HOLD; do not unpause.** Retest-owed: next Preflight fix seat timeout with green tests-only dirt must tip before a2 rewrite.
| O-PREFRETRY | ✅ | Closed 2026-08-03 wake#173–174 via **O-PREFCONT** (W4-062 correct diagnosis: `run_stage` already selected continuation; gap was CONTINUE text + floor). Keep forensic pointer: `scratchpad/forensics-S02/sup-preflightfix-r1-a1p0.log`.
| O-PREFCONT | ✅ | Fixed 2026-08-03 wake#173–174: preflight/gate/build-fix attempt≥2 CONTINUE injects O-PREFCONT (no invent / no rewrite dirty tip content + characterization floor + O-SHIPASSERTWEAK); `pref_snapshot_char_floor` + refuse tip when `@Test` count shrinks; rprompt + SHIPPING.md. Instrument shipfixcommit-prefcont-ok. Retest-owed: a2 must continue a1 dirty tests, not cold-rewrite thinner suite.
| O-HYGIENEWORKER | ✅ | Fixed 2026-08-03 wakes#232–234: `refuse_unhygienic_commit` on worker/mechan/ESCW/run_stage tip-accept — O-JDBCREGRESS (spring-tx) no longer run_stage-only. S03 T-001 `d7bde2a` false-GREEN reset. Instrument hygieneworker-ok. Retest-owed: T-001 must not land spring-tx. |
| O-ARCHIVESTAGE | ✅ | Fixed 2026-08-03 wakes#232–234: `stage_for_task_commit` resets `migration/run-archives` + `run-archives` (O-TMPARCHIVE forensic scoop into T-001). Paired O-HYGIENEWORKER instrument. |
| O-M3PRESERVEDAO | ✅ | Fixed 2026-08-03; **tightened W4-085a 2026-08-03**: plan-lint REDs “Preserve DataAccessException” / spring-tx greenwash **and** substring-only `DataAccessException→PersistenceException` one-liners without exact-symbol table (EmptyResult→NoResult, ObjectRetrieval→EntityNotFound, DAE→PersistenceException) — or omit throws. Packet tip ships full mapping table; forbids invented `*PersistenceException` under `org.springframework.*`. PLANNING + EXECUTION. Instruments preservedao×4. Retest-owed: next M3 DAO remap must carry table before M4. |
| O-ESCREOPENCODE-SENSORRED | ✅ | Fixed 2026-08-03 wake#320+: extends O-ESCREOPENCODE-ENFORCE — `escreopencode_should` also arms on `.err` `O-STEPFINISHRED` / `SENSOR RED` and cause-file `sensor-red` (W4-100a). MiniMax-owned routing + PATH refuse + kill watcher apply after false-complete under task sensor RED (not only wedge/thrash). EXECUTION + instrument `escreopencode-sensorred-ok`. Live T-004: nested Qwen hollow Panache killed (not nursed); hot-swap + clean retest. Retest-owed: next sensor-red MiniMax seat must log `O-ESCREOPENCODE-ENFORCE armed` and keep zero nested opencode. |
| O-ESCREOPENCODE-ENFORCE | ✅ | Fixed 2026-08-03: after wedge/thrash/INFERABSENT/CHARORACLE (**+ sensor-red via O-ESCREOPENCODE-SENSORRED**), `arm_escreopencode` + PATH refuse shim (`/tmp/escreopencode-deny/opencode` exit 75) + `escreopencode_kill_spawned` watcher during MiniMax `orch` escalation. Prompt no longer contradicts with “if you launch opencode”. EXECUTION + instrument. Retest-owed: next MiniMax-owned escalation must not keep a second Qwen/opencode seat. |
| O-STRUCTJAVA | ✅ | Fixed 2026-08-03 wake#302: plan-lint `LINT:O-STRUCTJAVA` REDs Shape=structure when Target/Target-design lists non-scaffold `.java` (allow package-info; Absorbs ignored); task-packet tips O-NULLACTION (no `.gitkeep` mandate / no O-STRUCTTGT harvest tip) so seats stop for re-M3 reshape to create/modify; PLANNING + EXECUTION. Instruments structjava×3. **Live evidence:** S03 T-001 + T-004 Shape=structure + Panache/harvest `.java` → Qwen READ_THRASH → MiniMax (T-004 in flight at fix). Retest-owed: next M3 must RED structure+`.java` before M4; HOLD tip if MiniMax lands `.gitkeep`+dep only. |
| O-SDJPAHARVEST | ✅ | Fixed 2026-08-03 wake#302 HOLD `b1eb764`: `sdjpa-harvest-check.py` + sensors/commit-hygiene RED dropped domain-repo extends, orphan `@NamedQuery` on repo ifaces, hollow finders, missing Override `*Impl`; task-packet tip + EXECUTION/PLANNING/MAPPINGS; instruments×4. Hot-swap before re-M3 reshape T-004 Shape→create + Qwen-first redo. Retest-owed: T-004 must tip with domain extends + Panache query bodies + Override Impls (sensor RED on hollow shells). |
| O-ALREADYCONS | ✅ | Fixed 2026-08-03 wake#302: after reset `b1eb764`→`ca57010`, already-complete false-skipped T-004 (`absent:SpringDataOwnerRepository`) — title `Consolidate…` not in convert verbs + Goal “delete bodies” near Target `.java` matched body-led removal. Fix: Consolidate/Implement in `is_convert_task`; Shape=create\|modify+missing Target never removal-skip; `(?! bodies?)` on delete. Instrument alreadycons-ok. Tip `310f352` REJECT/reset. **Retest GREEN wake#303–314:** after re-M3 `32812a6`, T-004 dispatched Qwen worker-first (no ALREADY COMPLETE); first-write `PetRepositoryOverride.java` in flight. |
| O-SDJPAHARVESTONLY | ✅ | Fixed 2026-08-03 wakes#303–314: S03 T-004 Qwen harvest-only Spring Data (Panache=0) rc=0 → O-STEPFINISHRED→MiniMax. Prior O-SDJPAHARVEST skipped non-Panache dests. Fix: `sdjpa-harvest-check` RED `O-SDJPAHARVESTONLY` on spring-data residue without Panache; packet tip + EXECUTION/PLANNING/MAPPINGS + sensors message; instrument harvestonly-red. Hot-swap mid MiniMax T-004 (leave seat; tip for next Qwen / tip-accept). Retest-owed: next Panache Shape=create worker must convert after harvest (not MiniMax for harvest-only). |
| O-ESCWVERIFYABS | ✅ | Fixed 2026-08-03 wakes#303–314: S03 T-000 Shape=verify Oracle=absent char-defer — Qwen verified phantoms absent (rc=0, 2×glob) but ESCW blocked (`?? migration/run-archives` in `app_dirt` + title `\bcharacterization\b` → escw-eligible `need-src-test`) → false MiniMax tip `b2bd34d` (run-log only). Fix: `app_dirt` excludes `migration/run-archives`; `escw-eligible` early `verify-absent-ok`; `already-complete` `absent:verify-absent` fast-path. Instrument verify-absent. Retest-owed: next Shape=verify Oracle=absent deferral must already-complete or ESCW without MiniMax. |
| O-CHARORACLE | ✅ | Fixed 2026-08-03: plan-lint `LINT:O-CHARORACLE` REDs characterization Source→Target / Source: / Legacy test: paths under `src/test/` when absent from `migration/staging` + legacy specimen roots. task-packet injects O-CHARORACLE tip → O-NULLACTION stop (no hollow/G-PLACE invent). PLANNING + EXECUTION. Instruments charoracle×3. **Retest 2026-08-03 wakes#251–253:** MiniMax ignored NULLACTION and reopened Qwen to invent phantom `JdbcOwnerRepositoryImplTest` — lead HOLD+kill; plan tip `be070fb` dropped phantom T-002 (renumber JDBC→T-002). |
| O-CDIPARTIAL | ✅ | Fixed 2026-08-03: `cdi-partial-check.py` + sensors/commit-hygiene/ESCW refuse `@ApplicationScoped`+`@Autowired` / missing `@Inject`; harvest-from-staging remaps `@Autowired`→`@Inject` when no spring-boot; task-packet + EXECUTION tip. Instruments cdipartial×3. Retest-owed: next JDBC/CDI harvest must not tip-accept partial CDI / force MiniMax for Autowired-only. |
| O-JDBCHARVESTAPI | ✅ | Fixed 2026-08-03 (paired O-CDIPARTIAL): same check REDs `org.springframework.jdbc|dao|orm` / `NamedParameterJdbcTemplate`/`SimpleJdbcInsert`/`JdbcTemplate` under quarkus pom without spring-jdbc; packet tip requires Agroal/`java.sql` rewrite (not naive harvest); never re-add spring-jdbc (O-JDBCREGRESS). Instruments share cdipartial cases. Retest-owed on T-002 resume. |
| O-SPRINGRESIDUE | ✅ | Fixed 2026-08-03: `cdi-partial-check.py` REDs any `org.springframework` under `src/main/java` (comments stripped) on Quarkus pom without spring-boot/spring-data bridge; also REDs invented `*PersistenceException` under `org.springframework.*` (W4-085a). Wired sensors/commit-hygiene/ESCW + packet/EXECUTION tip (peer O-CDIPARTIAL). Instruments springresidue×3. Retest-owed: next JDBC/CDI convert tip must refuse residue≠0 / invented EmptyResultPersistenceException. |
| O-PORTREIMPL | ✅ | Fixed 2026-08-03 wakes#324–328 S03 clean-stop consolidate: plan-lint `LINT:O-PORTREIMPL` requires `**Port**: rename\|reimplement` on Shape=create\|modify API-swap converts (Spring Data/Panache/JDBC/Agroal); Port=reimplement requires API mapping table or harvest-then-convert / O-SDJPAHARVEST prose. task-packet Port line + tip; PLANNING Port axis. Root cause of S03 T-004 burns (transliteration assumption). Instruments portreimpl×3. Retest-owed: next S03 M3 must declare Port=reimplement + mapping on T-004 before M4. **C remainder closed 2026-08-03:** see O-FIDELITYPORT + O-REIMPLCREATE. |
| O-FIDELITYPORT | ✅ | Fixed 2026-08-03 (charter §3.1 / C remainder): sensors scope harvest byte-match fidelity to `Port: rename` (default); on `Port: reimplement` fidelity dim runs `redesign-sig.py --mode=reimpl` (public signatures) — byte-match unsatisfiable on API swap (S03 T-001/T-004 deadlocks). `task_port_mode` + `run_port_scoped_fidelity` in sensors.sh; guide_for + EXECUTION/PLANNING. Instruments: rename serialVersionUID RED; reimplement Spring-body GREEN; reimplement method-rename SIG RED. **Retest:** fixture `instruments.sh` cases `O-FIDELITYPORT` (Port=rename Widget serial drift; Port=reimplement OwnerRepo) — also fires on next live Port=reimplement M4 seat. |
| O-REIMPLCREATE | ✅ | Fixed 2026-08-03 (charter §3.2 / C remainder / O-RESTCREATE class): Port=reimplement Shape=create **always** gets create-procedure tip in task-packet — (1) harvest-from-staging / write Target basename first, (2) cite+apply API mapping table, (3) first-write anchor (O-CREATEFIRSTMUT). plan-lint `LINT:O-REIMPLCREATE` when create-procedure prose absent. EXECUTION/PLANNING. Instruments: packet tip + plan-lint RED without procedure. **Retest:** fixture `instruments.sh` `O-REIMPLCREATE` / corpus `s03-post-port-good` keeps PLAN OK (has convert-after-harvest); next M3 Shape=create Port=reimplement without harvest/create prose must RED. |
| O-MMSCOPEQUIT | ✅ | Fixed 2026-08-03 wakes#268–269: task-packet + EXECUTION forbid MiniMax scope-quit / reclassification / task-splitting / human-approval when sibling Target already proves Agroal/`java.sql` (or O-JDBCHARVESTAPI / `org.springframework` residue remains) — continue until residue=0 or honest sensor-RED/O-NULLACTION without splitting the convert stack. Instrument mmscopequit. Retest-owed: next JDBC CDI MiniMax escalation must not scope-quit mid-stack. |
| O-HOTSWAPSTALE | ✅ | Fixed 2026-08-03 wakes#268–269: `hotswap_pause_gate` auto-clears zero-byte `/tmp/harness-update` when on-disk supervisor md5 matches process `SUPERVISOR_VERSION` (stale arm after deploy already applied); clears paired pause/ack/inflight when ack present. Arm after sync so md5 differs. Instrument hotswapstale. Retest-owed: stale empty marker must not park the run. |
| O-COLLABOWN | ✅ | Fixed 2026-08-03 wake#272: plan-lint REDs Shape=create/modify convert/harvest when staging same-package peers referenced by Target files are not owned/Absorbs/deferred; task-packet tip. Instruments treefixstub-wire. Retest-owed: next M3 with incomplete collaborator ownership must fail plan-lint before M4. |
| O-TREEFIXSTUB | ✅ | Fixed 2026-08-03 wake#272: `tree-fix-stub-check.py` sensor+commit-hygiene RED on comment-only/REMOVED husks and deleted owned Targets; Tree fix tips now pass `refuse_unhygienic_commit` (was bypass); tree-fix prompt + EXECUTION + packet forbid stub-nuke / require Agroal+java.sql full API or O-NULLACTION. Live tip `84632cf` REJECT+reset→`be070fb`. Instruments 396–398. Retest-owed: next tree-fix REMOVED tip must reset. |
| O-HARVESTFULLPATH | ✅ | Fixed 2026-08-03 wake#275–276: `harvest-from-staging.sh` normalizes Target-design full paths (`src/main/java/<legacyPackage>/…`) to package-relative before join (was FATAL double-prefix under `$LEGP/$rel`). task-packet + EXECUTION tip; instrument harvestfullpath-ok. Live S03 T-002 Qwen burned 11× FATAL with full jdbc Target paths — hot-sync script mid-seat; retest-owed: next harvest with full path must print `O-HARVESTFULLPATH: normalized` and land dest. |
| O-FIRSTMUTBASH | ✅ | Fixed 2026-08-03 wake#277–278: `worker-read-watch.py` counts bash `harvest-from-staging.sh` with stdout `harvested: … -> …` as mutates (plain bash still ignored — O-FIRSTMUT). Instruments firstmutbash; EXECUTION tip. Live S03 T-002: 25 reads + harvest bash + 0 edit → false READ_THRASH; retest-owed next harvest-first seat must not escalate on mutates=0. |
| O-INFERFIRSTWRITE | ✅ | Fixed 2026-08-03 wake#282: `task-packet.py` names leaf Target + concrete import/API first-write for multi-file Class=infer; EXECUTION tip; instrument inferfirstwrite-ok. Distinct from O-FIRSTMUTBASH. **Retest GREEN wake#299:** S03 T-003 tip `7d13fa7` — Qwen mutated `JpaOwnerRepositoryImpl` first then siblings; 7/7 CDI tip without MiniMax. |
| O-ESCWSCOPEUTIL | ✅ | Fixed 2026-08-03 wake#282: `scope_enforce` scrubs untracked LATER_CLASSES mid-convert; escalation prompt + packet/EXECUTION forbid util/non-Owns; instruments escwscopeutil-ok. Tip REJECT if util lands with convert. Retest-owed: next escalation must not keep EntityUtils dirt. |
| O-AGROALHELPERSIG | ✅ | Fixed 2026-08-03 wake#294: tip/EXECUTION require *exact public* helper names on Impl (forbid rename/privatize/RowMapper-only); redesign-sig tags rename smell (`mapRow`→`mapVetRow`); instrument agroalhelpersig-ok. Pair O-STEPFINISHRED. Retest-owed: next JDBC convert Qwen path must keep public `mapRow`/`create*ParameterSource` on Impl without MiniMax. |
| O-STEPFINISHRED | ✅ | Fixed 2026-08-03 wake#294: supervisor rewrites worker `rc=0`→`42` when uncommitted dirt (or clean tree) + task sensor RED after worker; O-ESCALCAUSE classifies `sensor-red` (not worker-failed/rc=0); packet+EXECUTION refuse step_finish/tip-accept/Already-satisfied under SENSOR RED; instrument stepfinishred-ok. Hot-swapped mid MiniMax T-002 (no harness-update pause). Retest-owed: next false-complete under SIG RED must escalate as sensor-red/rc=42. |
| O-POMDISCARD | ✅ | Fixed 2026-08-03 wakes#324–328 (W4-101a): `discard_orphan_pom` + `discard_src_dirt` revert dirty `pom.xml` panache/spring-data deps when src has no matching usage; `stage_for_task_commit` unstages/reverts orphan pom; commit-hygiene RED `O-POMDISCARD:orphan-pom-deps`. Instrument pomdiscard-ok. Retest-owed: next burned-seat discard must leave pom clean (no panache scoop into unrelated tip). |
| O-HARNESSFP-POD | ✅ | Fixed 2026-08-03 wake#388 (W4-106a): `v10-idle-clock.sh` emits `host_fp` + `pod_fp` and sets `harness_fp=hash(host\|pod)` so pod harness sync resets `agent_idle`; refreshes poll `last_activity` on move without touching `idle_note_level`. `--self-test` + instruments harnessfppod-wire/self. Caller-explicit `V10_WS_NAME` preserved across `load_env`. Distinct from O-IDLEWSFP (run clock) / O-HERMESPREFLIGHT (parity gate). **wake#389:** fixture/self-test skips `check_oc_logged_in` (exit 43) and detects FIXTURE before load_env so instruments mktemp cwd stays GREEN. **Retest-owed:** next poll after pod hot-sync must show `pod_fp` move + no false level-1 idle. |
| O-PLANCORPUS | ✅ | Fixed 2026-08-03 (Wave4 §1.1/§1.2 core): `plan-corpus-lint.sh` re-lints committed fixtures under `.hermes/harness/tests/fixtures/plan-corpus/` with **live M3 flag parity** (`--findings-scope --profile --story-deploy --story-scope`). Known-RED `s03-6348afe-class` expects O-STRUCTJAVA×2 + O-PORTREIMPL + O-M3PRESERVEDAO + O-COLLABOWN. Known-GREEN `s03-post-port-good` → PLAN OK. Parity-demo proves omitting `--story-scope` inflates LINT (false confirmation). Host gate `scripts/track-b/v10-plan-corpus-gate.sh` hooked into `v9-preflight-outer-start.sh`. Instruments plancorpus×4. **W4-108b closed 2026-08-03:** `s03-6348afe-class` now holds **real** `6348afe` tip text (101 lines; was 52-line reconstruction); archival dirs `s01-f7c1329` / `s02-ee834b1` / `s03-6348afe-real` / `s03-c164532` extracted from petclinic-rest-v3 before golden reset. **W4-109b progress 2026-08-03:** S03 revision-trace extracted (`s03-be070fb` / `s03-43d3a8e` / `s03-ca57010` / `s03-c9be4b0` / **`s03-32812a6-final`**); final accepted plan known-RED `O-PORTREIMPL`×2 under live flags; full corpus **11 cases** PASS. **Retest:** `bash .hermes/harness/plan-corpus-lint.sh` (or `bash scripts/track-b/v10-plan-corpus-gate.sh`). Every `plan-lint.py` change must keep corpus green / known-RED still RED. |
| O-M3ALL | ✅ | Claude/Wave4 RESTART CHARTER / HANDOFF ~07:04Z. Full land wakes#373–382: `m3-all-lint.sh` (K1 + **file Owns `O-M3ALL-FILE` (A4)** + Port + later-class + **projected-tree `O-M3ALL-TREE`** + **Oracle completeness `O-M3ALL-ORACLE`** + **Assumes closure `O-M3ALL-ASSUMES` (A6)** + amend stamps) + outer-loop two-pass + **freeze-predictions** + **OPERATOR_GATE** + **skeleton-first compose** (`m3-all-compose.py` — Owns/Oracle/Port/Assumes slots; never overwrites authored; author-pass hook; instruments compose-wire/emit). Waterfall antidotes mandatory. Pair ARCH A1–A5 ✅ (O-PORTDERIVE / O-SPECREIMPL / O-STORYKIND / O-M3ALL-FILE / O-SEATBUDGET) closed wakes#389–391. Charter pre-restart set ✅ wake#392; V4 ledger B1–B8 still open — Restart? NO. |
| O-PORTDERIVE | ✅ | Fixed 2026-08-03 wake#389 (ARCH A1): `roadmap-lint` gates REDESIGN target-contract when story owns OPEN DESIGN findings or scopes §7 REDESIGN class (LINT:O-PORTDERIVE); optional profile argv[4]/sibling. `plan-lint` derives Port: reimplement for §7 REDESIGN Shape create/modify targets (rename needs same-API justification); O-PORTREIMPL remains API-swap mapping check. Outer-loop M2 passes profile; instruments portderive-brief-red/green/wire. **Retest-owed:** next M2 with OPEN DESIGN / §7 REDESIGN brief must carry class+target; next M3 convert on §7 REDESIGN without Port must LINT:O-PORTDERIVE. |
| O-SPECREIMPL | ✅ | Fixed 2026-08-03 wake#390 (ARCH A2): `plan-lint` reads sibling `spec.md`; every REDESIGN/OPEN DESIGN CapWord class must appear in some task with `**Port**: reimplement` (`LINT:O-SPECREIMPL`). Soft when `spec.md` absent. PLANNING tip + outer-loop M3 prompt; instruments specreimpl-red/green/wire. **Retest-owed:** next M3 with spec.md REDESIGN class and no Port: reimplement task must LINT. |
| O-STORYKIND | ✅ | Fixed 2026-08-03 wake#390 (ARCH A3): `roadmap-lint` requires `- kind: rename\|reimplement\|mixed` when story owns OPEN DESIGN or scopes §7 REDESIGN; OPEN DESIGN forbids bare `rename`; `mixed` needs split/justification phrase. SEQUENCING format + outer-loop M2 prompt; instruments storykind-*. **Retest-owed:** next M2 OPEN DESIGN story without kind must LINT:O-STORYKIND. Pair O-SEATBUDGET ✅ wake#391. |
| O-SEATBUDGET | ✅ | Fixed 2026-08-03 wake#391 (ARCH A5): `seat-budget.py` derives N = rate(kind)×ceil(incidents/UNIT) (rename=1, reimplement/mixed=5, UNIT=10); `roadmap-lint` requires `- seat-budget: N` + brief publish; O-LOGBRIEF `BUDGET` line + `/tmp/story-seat-budget-S0N`; supervisor `check_seat_budget_overrun` → debt-freeze when actual > N×OVER_FACTOR (default 2). Instruments seatbudget-*. W4-120a pin flipped `.env`→v4; `load_env` O-ENVNOCLOBBER (W4-121a). **Retest-owed:** next M2 kind story without matching seat-budget must LINT; next M4 overrun must freeze. |
| O-DEFAULTAUDIT | ✅ | Fixed 2026-08-03 (Wave4 §2.3); **updated §2.1/§2.2**: seed now records O-INFERABSENT **LINT** (restrictive), Oracle **derived** (O-ORACLEDERIVE), `Proceed: O-NULLACTION` opt-in override. `--check` refuses stale WARN-tier / default-present seed text. Instrument defaultaudit-ok. **Retest:** `bash .hermes/harness/defaults-inventory.sh --check`. |
| O-DEFAULTINVROWS | 📋 | W4-138 (18th reminder): regenerate/seed `defaults-inventory.md` rows for `M3_ALL`, `V10_WS_NAME`, W4-127b at next boundary — absent mid-flight; do not edit harness during live M2. [next-boundary] |
| O-HERMESPREFLIGHT | ✅ | Fixed 2026-08-03: `scripts/track-b/v10-hermes-parity.sh` fail-closed digest of golden `.hermes` vs pod (key files + full-tree DIGEST/FILES); wired into `v9-preflight-outer-start.sh` before PREFLIGHT GREEN; refuses mismatch with clear sync message; does **not** auto-start outer. Instruments hermespreflight-wire-ok + hermespreflight-red-ok (local `--compare` RED on drift). Skip: `V9_SKIP_HERMES_PARITY=1`. Distinct from O-HERMESSYNC / O-HARNESSFP-POD. |
| O-HERMESPARITYSEM | ✅ | Fixed 2026-08-03: shared `qg_hermes_list_semantic_files` in `lib-quality-gates.sh` — both `v10-hermes-parity.sh` and `v10-golden-fresh.sh` (host + pod find) exclude `.published-fp`, `defaults-inventory.md`, `guard-manifest.md` (stamps / `_Generated:` catalogs; `.sh` generators remain hashed). Trimmed trailing blanks in plan-corpus `manifest.env`. Instrument hermesparitysem-ok (stamp churn GREEN; plan-lint drift still RED). Unblocks honest R1 without `V9_SKIP_HERMES_PARITY=1`. |
| O-CHANGEMANIFEST | ✅ | Fixed 2026-08-03 (R3/SC-1 / W4-130a): committed `docs/V10-CHANGE-MANIFEST.md` with UNDER-TEST / NOT-UNDER-TEST (R4 sfix corpus gaps, R6 O-LOGPROG/O-LOGRUN, R7 full guard build, R8 A-1/A-2/A-3, R9, ARCH-C2, PAUSE-1/2, non-honesty bank). `restart-readiness.sh` refuses GO unless file is tracked and lists those deferrals — silence forbidden. |
| O-HERMESWSRESOLVE | ✅ | Fixed 2026-08-03 wake#385 (W4-118a): `qg_ws_name` in `lib-quality-gates.sh` — explicit `V10_WS_NAME` or single Running DevWorkspace, else REFUSE (no `petclinic-rest-v*` / coolstore pod defaults). `qg_ws_pod` fail-closed on unresolved name/missing Running pod. Wired into `v10-hermes-parity.sh`, `v10-prep-fresh-rerun.sh`, `v10-idle-clock.sh`. Instruments in `gate-instruments.sh` (explicit/single/zero/multi + no named-default grep). **Retest:** `bash scripts/track-b/tests/gate-instruments.sh`; live `qg_ws_name` → Running DW. |
| O-PLANCORPUSSWEEP | ✅ | Fixed 2026-08-03: instrument `plancorpus-sweep-ok` runs bare `plan-corpus-lint.sh` (full sweep, no `--case`) and asserts rc=0 + ≥1 `PASS ` line. Pair O-PLANCORPUS ✅. |
| O-DEFAULTRG | ✅ | Fixed 2026-08-03: `defaults-inventory.sh` harvest via `grep -nE` (`_grepn`); no `rg -n`. `assert_fence_harvest` refuses empty plan-lint/supervisor fences on generate and `--check`. Instrument defaultrg-ok. |
| O-M3CASEINPUTS | ✅ | Fixed 2026-08-03 wake#383 (W4-109c): `plan-corpus-lint.sh` `resolve_case_inputs` prefers case-local findings/profile, else `migration/m3-inputs.env` pointers, else `_shared` stand-in. Real v3 M1 inputs under `_shared/live-v3/` (838KB findings + 24KB profile; SOURCE.md5). Archival S01/S02/S03 cases point at live-v3; synthetic `s03-post-port-good` keeps stand-in. `s02-ee834b1` EXPECT→green under live inputs (stand-in false-RED `incident-conflict` retired). Instruments `m3caseinputs-wire-ok` + `m3caseinputs-prefer-ok`. **Retest:** `bash .hermes/harness/plan-corpus-lint.sh` + focused instruments. |
| O-M2COMPOSE | ✅ | Fixed 2026-08-03 wake#10: `m2-compose.py` skeleton-first + fill — unique-owner partition (strip recipe), brief stubs, non-mandatory table, deploy-last, computed `seat-budget` via `seat-budget.py` when kind set. Wired in `outer-loop.sh` before M2 seat (skeleton if no roadmap) and after each seat (fill) before lint. SEQUENCING.md documents. Instruments `m2compose-wire-ok` / `m2compose-skeleton-ok` / `m2compose-fill-ok`. Judgment (fabrication/O-PORTDERIVE/O-STORYKIND/S-FND) left to model. |
| O-M2RETRYINLINE | ✅ | Fixed 2026-08-03 wake#11: M2 attempt≥2 prompt inlines bounded `/tmp/roadmap-lint.txt` (`M2_RETRY_LINT_LINES`/`BYTES`, `---BEGIN ROADMAP-LINT---` fence) — no path-only "read it with your file tools". Instrument `m2retryinline-wire-ok`. Retest-owed: next M2 a2 seat must see lint lines in the prompt without a file-read miss. |
| O-M2ATTEMPTS | 📋 | Opus Rec 3: M2 SEQUENCE attempts=2 / fail_run kills wave vs M3 up to 4 with orch backstop — budget inverted on global artefact. Prefer O-M2COMPOSE first (dissolves most burns); then consider M3-shaped attempts+backstop. ADR candidate (M2 counterpart of ADR-8 skeleton-first). [next-boundary] |
| O-M2CORPUS | ✅ | Fixed 2026-08-03 wake#11: seeded `tests/fixtures/m2-corpus/v4-m2-lintx2-10790d6/` (RED roadmap+5 briefs+M1 inputs+legacy leaves+EXPECTED_LINT) from v4 lint×2 FAIL @10790d6; `m2-corpus-lint.sh` re-lints with live argv; host `v10-m2-corpus-gate.sh` in preflight+LRR. Instrument `m2corpus-red-ok`. Retest: `bash .hermes/harness/m2-corpus-lint.sh`. |
| O-MONSTART | ✅ | Fixed 2026-08-03 wake#11: `v9-preflight-outer-start.sh --start` starts `tmp/v10-v3-dual-monitor-start.sh` after outer (and when already_running); LRR asserts wire. Skip: `V9_SKIP_MONSTART=1`. Instrument `monstart-wire-ok`. Retest-owed: next `--start` must leave dual-monitor pid alive before first M4. |
