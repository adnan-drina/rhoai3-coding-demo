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
| O-REVDOC | ✅ | O-DRV3/O-DRV5 clear requires Implementing note citing sha in active review doc (`tmp/KAI-WAVE2-REVIEW.md`; Wave 1 archive `tmp/KAI-WAVE1-REVIEW.md`) (`qg_require_wave1_review_note`); gate log alone insufficient — script-enforced handshake (2026-07-30; active doc → WAVE2 2026-07-31). |
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
| O-SFIXNOSPRING | ✅ | Fixed 2026-07-31 (F-21/wake24): after sfix commit, sfix-no-spring.py refuses NEW org.springframework imports / spring-* pom deps vs PRE_SFIX_HEAD (reset). Type-level fidelity inversion tripwire. |
| O-FIDELITYMAP | ⬜ | F-21: source harvest-fidelity approved transforms from MAPPINGS+task Findings (line-scoped); supersede per-incident skips long-term. O-FIDELITYVALID is the validation family instance. |
| O-FIDELITYVALID | ✅ | Fixed 2026-07-31 (wake23): harvest-fidelity skips when staging has BindingResult/FieldError and dest has ConstraintViolation (Spring→Jakarta validation conversion). Wave2 T-004 false RED. Instrument. |
| O-RESTBATCH | ⬜ | Wave2 T-012/T-013: Qwen JSON_STALE on multi-controller JAX-RS harvest; prefer mechanical harvest-from-staging + annotation recipe batch before worker/MiniMax (pair with O-HARVESTREPO). |
| O-ACREMULTI | ⬜ | Wave2 T-014: Remove-task already-complete skips on first absent leaf (ApplicationSwaggerConfig) without verifying all listed removals/refactors (Roles→@ApplicationScoped). Require all named targets absent/satisfied before absent-oracle skip. |
| O-ACRESTABS | ✅ | Fixed 2026-07-31: is_convert_task blocks absent-oracle for Convert/Port/Harvest/Migrate titles (Wave2 T-013 false PetRestController absent skip). |
| O-FIDSONAR | ✅ | Fixed 2026-07-31: harvest-fidelity strips all `throws …` clauses (T-015: IllegalArgumentException vs Exception still RED; broadened). |
| O-ACCREATE | ✅ | Fixed 2026-07-31 (wake45): Create/Add/Implement titles never already-complete via absent (is_removal_task short-circuit + findings-oracle absent gated). Wave2 T-009 body mentioned "removal" → false skip of missing EntityUtilsMigrationTest. Instrument. |
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
| O-INFERABSENT | ✅ | Fixed 2026-08-01 (R-231/G5): skip Qwen when `class=infer` + `Oracle:absent` (S03 T-007/T-012 wedge signature); escalate with O-ESCREOPENCODE MiniMax-owned edits. Instrument.  Retest-owed (F-70): proves on next infer+absent task; N13 READ_THRASH covered by O-FIRSTMUT ✅. |
| O-PCTFILE | ✅ | Fixed 2026-08-01 (R-230/F-68/T-012): `pct_file_contract` REDs `application-%*.properties` (literal `%` in filename). SHIPPING tip: use `application-{profile}.properties` or `%profile.key=` keys. Live tip `4032cdf` reset; instruments. |
| O-PLANPROP | ⬜ | R-226: extend O-PLANEXISTS to property conversion — WARN when converted property names a package/class with zero occurrences in target tree (T-009 `org.springframework` log category on Quarkus-only app). |
| O-T2ALREADYQ | ⬜ | S02 T-002 `2f7e02a`: task title 'remove Spring Boot' but scaffold was already Quarkus — worker only added hsqldb + datasource/root-path props. M3/plan-lint should detect already-satisfied BOM/deps (or AC) so packets don't overclaim Spring removal. |
| O-CLASSPROMPT | ✅ | Fixed 2026-08-01: TASK_CLASSES uses task-packet Class field parser (`**Class**: rewrite` no longer false-infer). Instrument. |
| O-BRIEFCONF | ⬜ | F-32: briefs have no conformance vs migration.yaml DB contract. When needsDatabase+dbService set, deploying story brief must name schema/seed deliverable and must not propose multi-DB primaries (S03 petclinic brief contradicts DECISION-DB). |
| O-SFIXWRONGDIM | ⬜ | Harness: sfix prompt + EXECUTION route FINDINGS→`sensors.sh findings`. Awaiting next FINDINGS-RED sfix to prove no ceremonial polish (witness was `2d095f2`). |
| O-SFIXMETRICS | ✅ | Fixed 2026-07-31: scaffold default + MAPPINGS tip + sfix FINDINGS route; live probe `9a9917f` → milestone FINDINGS GREEN (K5 metrics cleared). |
| O-AUTOFIXJSON | ⬜ | S02 T-002 `e4cf22d`: 'sensor autofix' commit is only `mta-findings-current.json` churn (kantra refresh), no style/code fix — mislabeled. Exclude findings-current from autofix commits; don't call JSON refresh autofix. Ties O-T1FINDINGS. |
| O-T1FINDINGS | ✅ | Fixed 2026-08-01 (R-219): `stage_for_task_commit` resets `migration/mta-findings-current.json` (with .hermes/staging). Wave2 S03 T-004 `4888bdc` was findings-only wrong-title mechan — excluded going forward. | R-223: instrument upgraded from grep to behavioural stage fixture.
| O-M3PRESERVE | ✅ | Fixed wake70: PLANNING.md — preserve tokens must appear **verbatim** in tasks; redesign §7 decisive tokens (`thread-safe`, etc.) in same task body as class. Hot-swapped; S02 draft tasks probe already plan-lint GREEN during O-M3QUOTA backoff. |
| O-SHAPEDECL | ✅ | Fixed 2026-08-01 (F-70/F-28): plan-lint **Shape** field; live M3 sets `PLAN_LINT_REQUIRE_SHAPE=1` (instruments WARN). PLANNING tip. Retest-owed: next M3. |
| O-ACORACLE | ✅ | Fixed 2026-07-31 (wake28): try_already_complete handles oracle-absent:. |
| O-ACFIRST | ✅ | Closed 2026-07-31 (F-24/F-25): T-005 vs T-006 asymmetry was **pre-fix vs post-fix of O-ACORACLE** (landed wake28), not late already-complete ordering. Post-fix path is oracle-before-dispatch. Residue: false debt-freeze ledger row → O-LEDGERFALSE only. |
| O-T6DREMOVAL | ✅ | Fixed 2026-07-31 (R-104): mechan-match accepts empty stage when removal targets absent. |
| O-T6DOWNERSHIP | ⬜ | F-20/R-103/R-104: O-T6d assumes create/modify; misfires on absent/removal. Predict T-006 reject, T-007/8/9 pass. F-20/R-103: invert O-T6d OR give structural tasks an explicit path manifest (Wave2: O-T6d rejects structure 2/2, passes harvest 2/2). F-20: invert O-T6d — refuse only on positive wrongness (other-task ownership / later-story / harness ignore). Reuse K1 plan-lint ownership map; stop whitelist-from-task-text. Fixtures: Wave2 unexpected-paths, empty-stage, structure-non-gitkeep; control T-002. Before more tolerance patches. |
| O-STRUCTINFO | ✅ | Fixed 2026-07-31 (wake17): mechan-match — package-info *tasks* (title) not structure-only; structure soft path allows package-info.java as well as .gitkeep. Wave2 T-003: Target "package structure" → structure-non-gitkeep after Qwen wrote package-info → false MiniMax guard-refused. Instruments. |
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
| O-ESCALCAUSE | ✅ | Fixed 2026-07-31: cause file + events (worker-failed|guard-refused|quota). F-20 P3: file also carries last O-T6d reason line + worker_rc (wake21). |
| O-SKEL-CATALOG | 📋 | R-87: RHDH migration skeleton still deploys `catalog-service` into non-Coolstore namespaces (seen in `petclinic-rest-v1-dev`). Gate behind values / specimen needs, or document always-on. Harmless at rest; avoid false wiring checks. |
| O-WAKE-GROK | ✅ | Fixed 2026-07-31 (F-5): `tmp/v10-smart-wake-loop.sh` W1 label pod (`V10_WS_NAME=petclinic-rest-v1`), W2 `V10-GROK-HEARTBEAT` idle default 600s, W3 `MIN_EMIT_GAP_S=120` (nudge exempt), W4 `MAX_QUIET_S=900` timer, W5 `V10-WAKE-EMIT.last` + redeliver + DELIVERY-BROKEN osascript. `lib-quality-gates.sh` `qg_ws_pod` label resolve. Lock + never `pgrep -f` wake path. Behavioral instrument suite still 📋 follow-on. |
| O-WAKE-CATCHUP | ✅ | Fixed 2026-07-31: wake emits refresh `scripts/track-b/v10-review-catchup.sh` → `tmp/V10-REVIEW-SINCE-LAST.md` (full slice after last Implementing note); opens `V10-REVIEW-CATCHUP-PENDING` (+R / reason=catchup) until newer Implementing note + `… catchup.sh ack`. Prompt + stage-080-track-b rule; not memory-only. |
| O-REVIEWDOC | ✅ | Fixed 2026-07-31 (operator): lead notes must identify **Agent: Grok (lead)**, list **Reviewed:** / `ACK:R-|F-|O-` for other agents' entries, state live action, close `— Grok (lead)`. `v10-review-catchup.sh ack|check` enforces; wake prompt + stage-080-track-b + AGENTS.md. Chat pulse ≠ audit trail. |
| O-STAMP-AUTO | ✅ | Fixed 2026-07-31 (F-4): `contract-stamp.py` at outer-loop entry before M1; RequestMapping GET + ResponseEntity&lt;Collection&gt;; getAll* rank; prefer existing path; refuse UNDECIDED overwrite; PyYAML-less load/dump preserves provenance. Dogfood `petclinic-rest-v1` @ `6de6c05` → `/petclinic/api/vets` `_array` + evidence targetContract. Instruments 229 (+ petclinic gate GREEN). |
| O-STAMP-GATE | ✅ | Fixed 2026-07-31: `contract-stamp-gate.py` + minimal YAML loader (no PyYAML); verifies package/path/UNDECIDED; wired in outer-loop after stamp. |
| O-STAMP-TEMPLATE | 📋 | Next specimen: template shrinks to name + legacy URL + neutral sentinels (not cart defaults); harness fills the rest. |
| O-GOLDENFRESH | ⬜ | F-6/F-20: publish-fp + repo/published/pod three-way in preflight (commit lag auditability). **2026-07-31 review correction:** live md5 "parity split" across R-95–R-105 was hot-swap-first development (working tree + `/tmp/harness-update`), not stale pod gates — withdraw false alarm; keep publish-fp for committed golden sync. **F-72 (2026-08-01):** Phase-1 landings live on v2 pod + uncommitted in local golden (`stages/080-…/scaffold-repo/…/.hermes`); demo-repo SoT lag is the real instance — commit golden before next provision/reset; three-way preflight still open. |
| O-SFIXS5853 | ⬜ | T-007: Qwen wrote consecutive `assertThat(x).a(); assertThat(x).b();` → java:S5853; rewrite sfix 0-file; MiniMax sfix chained AssertJ. Tip/worker packet: chain AssertJ on same subject in characterization tests so worker-direct avoids MiniMax sfix seat. |
| O-SFIXMSG | ⬜ | T-008 `325db8d` subject claimed "fidelity drift" but diff was sonar S1130 (+ BaseEntityTest assert). R-109: BaseEntityTest change was a *strengthening* and milestone-tree-wide repair is legitimate — keep bank for **subject/dimension mismatch** only, not the cross-file edit. |
| O-SFIXATTR | ⬜ | F-26/F-16: supervisor ✓ END after sfix credits coding worker even when MiniMax orch ran sensor-fix (T-007 `6aa8cd2`). Fix log/event actor for sfix path so seat accounting and review ledgers stay honest.
| O-DSKIND | ✅ | Fixed 2026-07-31 (S02 T-004): after JPA entity harvest, milestone verify needs `quarkus.datasource.db-kind` + `quarkus-jdbc-*` (not bare hsqldb jar); `sql-load-script=none` is invalid (use `no-file`); `generation=drop-and-create` until schema/seed story. Probe commit `aab2b81`. Tip/plan: wire JDBC extension when entities land, not only T-015. |
| O-FIDELITYDAO | ✅ | Fixed 2026-07-31: harvest-fidelity approves DataAccessException throw strip + PropertyComparator/MutableSortDefinition/ToStringCreator drops (JDK Comparator / plain toString). Instrument + hot-swap. Prevents MiniMax sfix Spring green-wash (O-SFIXNOSPRING). |
| O-T4SPRINGDATA | ⬜ | S02 T-004: task target listed SpringData* interfaces but Quarkus pom has no Spring Data — worker burned ~12m compiling, then correctly deferred springdatajpa/ to redesign (T-011). Plan-lint/tip: do not require Spring Data harvest in rewrite tasks unless spring deps are in-scope; split base interfaces vs Spring Data redesign. |
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
| O-DTOFIRST | ✅ | Fixed 2026-07-31 (Wave2 T-005 HOLD):  Planner/batch: harvest DTOs (type deps) **before** MapStruct mappers. T-005 Qwen RED on missing `com.demo.dto` owned by T-006 → MiniMax. Prefer reorder over soft compile. Do not invent stub DTOs / steal next-task scope. |
| O-GITBAK | ✅ | Fixed 2026-07-31 (Wave2 T-005 HOLD):  Refuse staging/commit `*.bak` / `*~` / `.orig` under src/ (`62413ff` committed 8 OpenAPI dumps as `.bak`). |
| O-SIMPLEDTO | ✅ | Fixed 2026-07-31 (Wave2 T-005 HOLD):  Refuse thin hand-rolled DTO beans when staging has OpenAPI-shaped DTO; do not rename harvest to `.bak` and invent stubs (`OwnerDto.java` vs `.bak` in `62413ff`). |
| O-WEDGESKIP | ✅ | Fixed 2026-07-31: clear_worker_wedge_skip after mechan/worker/escalation success; skip no longer sticky for whole story.  O-WORKERWEDGE-RCA skips **all** further worker seats for the story (Wave2 T-007 ClinicServiceImpl → MiniMax immediately after T-005 DTO wedge). Durable: scope skip to same failure class / same task pattern, or clear RCA after O-DTOSTAGING-class fix lands mid-story. |
| O-SCRATCHPY | ⬜ | Escalation invents scratch `harvest_*.py` instead of bundled `harvest-from-staging.sh` (Wave2 T-005 MiniMax). Tip+refuse commit of repo-root scratch harvesters. |
| O-DTOALLOF | ⬜ | MiniMax OpenAPI harvest skipped `*AllOfDto`/`*FieldsDto` required by composition DTOs (Wave2 T-005). Harvest must include all OpenAPI dto/*.java under package; tip never filter AllOf/Fields. |
| O-DTOSTAGING | ✅ | Fixed 2026-07-31: harvest-from-staging OpenAPI generated-sources fallback + javax.validation/annotation→jakarta; instrument DTOSTAGING_OK.  OpenAPI-generated DTOs live under legacy `target/generated-sources/openapi` not `migration/staging` — harvest-from-staging / O-HARVESTSTALL preseed misses them; worker wanders (Wave2 T-005 ~6m). Durable: M1/staging copy or harvest script path for openapi dto root from migration.yaml; preseed Targets from that tree.  Retest-owed (F-70 0.3): no fresh-run proof since land. |
| O-SPECREBASE | ✅ | Fixed 2026-07-31: O-M4REPLAY walks run_base back past pre-spec T-NNN when mid-story `S0N spec:` recommit hides them (Wave2 restart after T-007 sensor-fix used ef9dbd2^=aab2b81 → false T-002 OpenCode replay). |
| O-POMUNC | ✅ | Fixed 2026-07-31 (Wave2 T-005 HOLD):  Task GREEN must not rely on uncommitted pom deps — MapStruct left dirty while mappers committed (`62413ff`). Same-commit pom or RED. |
| O-TXDROP | ⬜ | Wave2 T-007 `30ff504`: Spring `@Transactional` dropped on *all* service methods (staging had ~29; target has 0 annotations — only a javadoc mention). Task said replace with jakarta/hibernate TX or remove for *read-only*; mutating save/delete lost TX. Durable: tip + optional commit-hygiene/sensor — preserve `jakarta.transaction.Transactional` on write methods when staging/legacy had Spring TX; findings `transaction-to-quarkus-*` not cleared by CDI-only. |
| O-SDJPA-SKIP | ⬜ | Wave2 T-011: when Spring Data task only needs Override delete helpers and Jpa* @ApplicationScoped already cover repos, prefer already-complete / mechanical harvest over Qwen READ_THRASH→MiniMax (pair with O-JDBCSKIP). |
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
| O-CHARREAD | ⬜ | Wave2 T-017/T-018: Qwen READ_THRASH on characterization/integration test tasks (reads≥30, mutates=0) → MiniMax every time. Tip/packet: start by writing one *Test.java skeleton from AS-IS service/REST signatures before broad reads; or mechanical test scaffold from interface method list. |
| O-CHARVOIDSAVE | ⬜ | Wave2 T-017: MiniMax stubbed `given(repo.save(x)).willReturn(y)` but harvested repos use `void save` → testCompile RED ('void type not allowed'). Tip: for void save/delete use `doNothing().when(repo).save(...)`; prefer real entity beans over mocks when characterizing mutating services (UserService ROLE_). Also mockito-junit-jupiter not on pom — use MockitoAnnotations.openMocks. |
| O-CHARWISH | ⬜ | Wave2 T-016: MiniMax characterization asserted wished Spring Petclinic semantics (Role.user wired, Role dedupe, getPet ignores-new-by-default, Visit null date, insertion-order specialties) instead of AS-IS modernized code. Tip: read entity methods before asserting; characterize actual behavior. Operator-aligned expectations then GREEN 428 tests (`40013bf`). |
| O-CHARREFLECT | ⬜ | Wave2 T-016: reflection tests (`getDeclaredField`/`getMethod`) omitted `throws Exception` → testCompile RED; MiniMax stalled ~20m. Tip/scaffold: characterization reflection helpers declare throws Exception or use assertDoesNotThrow. |
| O-SFIXDUPBASE | ⬜ | Wave2 T-015 sfix: MiniMax extracted BaseDto to clear DTO duplication, then Sonar RED worse (S1128 unused imports + S2160 equals-without-super). Duplication on Simple DTOs should not drive inheritance refactors mid-sensor-fix; prefer accept duplication debt or suppress, not BaseDto. |
| O-SFIXMISDIM | ⬜ | Wave2 T-007: style-autofix rewrote DTO unused-imports (c7e7e53) while milestone RED was Arc UnsatisfiedResolutionException — wrong dimension. Also O-SFIXDIRTY discarded good Jpa*Impl harvest after sfix broke OwnerDto. Wave2 T-011: autofix committed f8ff7df (run-log.md only) while 4× S6813 field @Inject remained — ceremonial no-op; do not count as partial fix. |
