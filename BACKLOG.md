# Backlog

Open limitations, unfinished work, and the evidence needed to understand them.
Completed run narratives remain in Git history. Paths under `tmp/` are local
evidence, excluded from Git.

## Fresh-environment migration gates (2026-10-05)

The [baseline inventory](docs/OPERATIONS.md#fresh-environment-baseline-2026-10-05) is read-only evidence on OCP 4.22.14, not a deployed stage verdict.

- [ ] Stage 010: finish real OpenID persona/dashboard acceptance; historical synthetic MLflow artifact/database persistence passed; fresh foundation source no longer installs it. RHOAI 3.5.1/ODF 4.22.5 installed; native registry, metrics, Perses transport and exact trace retrieval passed. The old COO hold and monitoring transport workarounds are retired; AutoRAG/AutoML remain disabled.
- [ ] Provisioner follow-up: Lightspeed 1.1.4 installed but API NotReady; cloud-credential missing parent credentials prevents future OCP minor/major upgrades. Preserve add-on/operator ownership; no credentials or resources were changed during inventory.
- [ ] Stage 020: native NFD 4.22, NVIDIA 26.7.1 and Kueue 1.4.2 readiness, two L40S workers, per-node CUDA/DCGM and UID-bound queue admission passed. Scoped native metrics repair permits genuine ai-admin queries and preserves developer denial; actual dashboard/profile browser confirmation remains pending. No CPU pool scaling or bucket changes occurred.
- [ ] Stage 070: resolve integration with the preinstalled OpenID/Keycloak (`keycloak`, namespace-scoped operator) before applying the separate project `rhbk` identity installation.
- [x] Stage 030: native serving/discovery is deployed at `147b6208` after the protected core `882f327f` handoff. Independent registry/database/credential/MLflow identity and existing-bucket preservation passed; both genuine personas passed verified-TLS registry, Model Catalog and Agent Catalog API checks. The user confirmed Model Catalog and Agent Catalog visual checks on 2026-10-05, completing Stage 030 acceptance. Stage 040 acceptance limits are recorded separately; Stage 050 service foundation is deployed. AutoRAG/AutoML remain excluded.

- [x] Stage 050 service foundation: native EvalHub/TrustyAI plus retained MLflow adopted after protected handoff; no evaluation or GPU restart.
- [ ] Stage 050 evaluation: select a native chat-compatible ten-sample benchmark, approve model resume, then prove completed results and exact FINISHED MLflow correlation. UI remains user-owned. See [the plan](docs/migration/050-model-evaluation-plan.md).

Zero-replica provider MachineSets, the preinstalled Keycloak PVC and platform revision pods are not project cleanup candidates. Historical validation stays historical; obsolete project resources need purpose, owner, replacement behavior and a validated removal condition before deletion.


## Migration reliability package M-1..M-7 (2026-09-30, unpublished)

Branch `feat/migration-reliability-m1-m7` (base `next/after-v28` `26bc9c2b`); status per ID in
[MIGRATION-IMPROVEMENTS.md](stages/130-ai-autonomous-migration/MIGRATION-IMPROVEMENTS.md).
Local evidence: `tmp/reliability-evidence/` in that worktree. Not validated against a live cluster.

- [x] Integrated with `next/after-v28` (`c9ab129d`) and architect commit `ee7bc6d6`; qualification PASS on
  `5280670b` (118/118 + 14/14 suites under python3.9, repeatability 26/0, M-3 CONTROLS PASS, rehearsal 47 of 47
  across both modes, ADR-026 qualified on PostgreSQL 16). Evidence: worktree `tmp/reliability-evidence/qualification-5280670b/`.
- [ ] MTA 8.2 fresh repeatability not run locally (host has 7.3); recorded findings are not a fresh execution.
- [ ] Release (release agent): build ws-080 with the typed-repair jar, re-pin its digest (pins, run-defaults, both
  devfiles, RELEASE.md), apply the Stage 040 gateway headroom first and observe it, publish platform and golden,
  bounded preflight without an isolation campaign.

## v26 reliability release and the subsequent feature package (scope decided 2026-09-29)

v25 (`spring-petclinic-rest-legacy-v25`, the v24 package) is preserved as an
**assisted diagnostic run**: 21 of 36 cards, two recorded harness rebases and
four unblocks. It is a partial baseline for M1, M2 and part of M3, not an
end-to-end one.

**v26 is the reliability validation release:** M1→M5 without harness overlays or
Operator rescues, with every acceptance gate preserved. Scope and per-item
evidence status are in
[MIGRATION-IMPROVEMENTS.md](stages/130-ai-autonomous-migration/MIGRATION-IMPROVEMENTS.md).
Status there is source-level (tests, model-free reproductions) unless marked live.

In v26:

- [x] V26-6 known defects: brief ownership, liveness, selectors and whole
  architecture; retry-state diagnostics; the REVERTED lockout; unchanged rework;
  the preload of required skills; near-duplicate progress (runtime 0015).
  Source-level evidence; see MIGRATION-IMPROVEMENTS.md.
- [x] V26-6 open items (Servlet redirect guidance, native retry handoff, producer
  exit code through a filter) were NOT in v26; they are implemented after it
  (source-level, unpublished): see the correction package table below.
- [x] V26-3 targeted context (instructions, selectors, owned obligations, saved
  diagnostics, retry context). The resolved-context attachment and a
  classpath/API lookup are deferred.
- [ ] V26-4: report actual verification, retries, assistance, requests, tokens
  and elapsed time from existing records. v26 was frozen at 12/36 cards; the
  scripted report (run-report Reliability) needs a copy of the preserved board.

Subsequent feature package (V26-1 with V26-2), not scheduled for a numbered run:

- [ ] Execute two qualified repairs deterministically inside existing M3 scopes:
  selected repository CDI exposure and handler URI parameter translation.
- [ ] Qualify recipes with before/after, no-change, idempotence, type-resolution,
  scope and real behavioural checks; preserve native review and acceptance gates.
- [ ] Recipe-specific V26-4 reporting ships with the executor.
- [ ] Deferred pending measurements (V26-5): analysis reuse with complete cache
  invalidation.

**v26 frozen (Operator-requested stop, 2026-09-29 10:53:48Z).** The workspace was
stopped through `spec.started=false` at 12 of 36 cards done (2 blocked, 2 ready, 1
running, 19 todo), destination HEAD `48b063c1`; PVC, board, logs, budgets and the
uncommitted state are preserved. It is not a successful validation run: the four
corrections below were known unfinished requirements. Snapshot and identities:
`tmp/v26-corrections/` (freeze-snapshot, devworkspace YAML, IMPLEMENTATION-REPORT.md).

Correction package after v26 (branch `next/after-v26`; source-level unless a live
column says otherwise; nothing overlaid on v26). Every included requirement:

| Requirement | Implementation | Regression evidence | Published | Live evidence |
|---|---|---|---|---|
| A. Servlet redirect guidance (V26-6 item 1) | catalog `handler_parameters` Servlet rows + `migration_recipes.servlet-redirect-response` (qualified by the handler's calls); `source_requirements.recipe_call_gap`; `worklist._response_verdict` and the jakarta ban; no `javax.servlet` rename; brief CAPABILITY GAP (78a74e69, d4592bdf) | `servlet-redirect-package.test.py` (pinned BOM, offline: rename does not compile, emptied and relative forms refused or differ, the recipe's form matches the recorded source 302 over HTTP, renamed equivalent); `source_requirements.test.py` servlet case (real + renamed applicable, getWriter and request unresolved with named gaps); worklist test | no (golden publish owed) | worker exercise only (below); none in a run |
| B. Native retry context (V26-6 item 2) | post-tool observer output tail; brief PREVIOUS RUN (halted investigation vs rejected candidate, repeated call and bounded result, last step, tree) and LAST VERIFICATION current/stale (d4592bdf, earlier 657be426) | `native_board.test.py` NativeRetryContext (a real native retry through the board path), `outcome-line.test.py` PreviousRun/VerificationState, `post_tool_call.test.py` | no | worker exercise only; a Hermes-dispatched retry is first observable in the next run |
| C. Command-status integrity (V26-6 item 3) | `verify_record.py` (`rhoai3.last-verify/v2`: procedure, compilation, tests apart; bound to the terminal call), `run-verify.sh` start/finish (fbeb51e1) | `verify_record.test.py` (real run-verify.sh behind `\| tail -1; echo`: pipeline 0, record keeps the failure; compile errors stay failed; skipped tests stay not-run) | no | none |
| D. Audit under shortened log display | `paved_road.evaluate_audit` ledger-first, completeness bound, call-bound verifier record (fbeb51e1) | `paved_road.test.py` LedgerFirstAudit (Profile shape both displays, failed build behind clean wrapper, newer unfinished or never-reached invocation, wrong run/card, lost ledger row); replay of v26 `t_d5579123` run 17 (`tmp/v26-corrections/replays/`) | no | none |
| Witness checkpoint gets no repair credit | run-report `step_relation`, `accepted_repairs`/`accepted_witnesses` (94dc4bbf, earlier a9d81a3b) | `run-report.test.py` with the v26 rows: 4 repairs, 1 witness (`93bf5c97`) | no | none |
| Unchanged worker re-issue records nothing | `native_control.issue(replay_unchanged)`, `native_gate.py issue` (94dc4bbf) | `family_budget.test.py`; replay: released 7 records for 7 calls, corrected 1 | no | none |
| Card/handoff wording, image pins, V26-4 report | 398afb97, edb93305, c3b3b80d | their suites | no | none |

Worker exercise (bounded, declared ceiling 4 requests / 300,000 tokens; used 4 /
232,354; production non-thinking profile; key created and revoked through the MaaS
workflow): the v25 Root card retry decision point, control vs corrected brief. Control:
2 of 2 kept investigating. Corrected: 2 of 2 edited the controller at once; 1 wrote the
qualified form, 1 dropped the redirect (a void handler). The second shape is now
refused by the structural check (added from this result). Two samples per arm: a
direction, not a rate. `tmp/v26-corrections/worker-exercise/`.

Next golden (branch `next/after-v28`, unpublished; v28 runs on golden `6bef18f5` untouched):

- [x] A read-only call after a required-argument step no longer fails the step (v28
  `t_c5ac91e7`: a bare `handoff_facts.py` read-back after the `--write` cost one review
  round). The audit grades the latest invocation that CARRIES the required arguments; a
  later invocation without them must have completed with exit 0, else it still refuses.
  Evidence: `paved_road.test.py` (clean read-back keeps the step; failed or unfinished
  read-back refuses; a plan-only call alone still refuses), paved-road selftests. Live: none.

- [x] The Servlet redirect recipe refuses a SpEL servlet-context field left on the handler's
  type (v28 `t_25819d9c`, commit `dfeda3d`: the verified redirect with
  `@Value("#{servletContext.contextPath}")` kept). The pinned platform refuses to package it
  ("SpEL expressions are not supported"), so v28 meets it at its first package gate as an
  `unsupported-spel` obligation. Architect review G3 narrowed the check: only a field whose
  Spring `@Value` (resolved through the type's imports) injects `#{servletContext…}` is
  refused; the same text in another annotation is data, and an annotation no import binds
  is left to the package gate. Evidence: `servlet-redirect-package.test.py` (the v28 form
  is refused structurally and does not package; the recipe form packages and answers the
  recorded 302), `response_injection.test.py` (renamed type and field, a `@JsonProperty`
  literal, unbound and foreign `Value`, `${…}` placeholders).

- [x] Worker information delivery (architect review G2 and the loop-root-cause change
  `793c344a`, integrated): every default brief is the human digest on stdout at any size;
  `--full` (alias `--json`) returns the complete JSON for programs, and persisted JSON is
  unchanged. The documented unit and item first actions are printed before the write set
  (`DOCUMENTED FIRST ACTIONS`; the earlier worker experiment inserted this action by hand,
  so it tested a better prompt than workers received). A missing reference is said to be
  missing, never a classpath conclusion. A card whose compile items are gone but whose
  planned requirement is still owed gets one NEXT ACTION, identical to its PROCEDURE; a
  retained or on-tree candidate keeps precedence. The retry history groups by the exact
  command (numeric operands preserved) and calls results identical only on complete
  recorded fingerprints and known exits. Evidence: `brief.test.py` (the real catalog ->
  sealed unit -> default CLI first action), `outcome-line.test.py` (36 tests, including
  WorkerInformation, OwedPlannedRequirement); five worker-visible regressions fail on
  `ac24504d` and pass after. Live: none.

- [x] Diagnostic ownership (architect ruling 5): selectors and the shared-file summary
  label each diagnostic as issued to this card or not in its sealed set, with its measured
  clusters (stable identities survive line shifts; foreign or missing issuance stays
  unknown). On a native card each item also names its plan owner and card, and whether it
  blocks this card. Nothing widens scope or exempts a regression. Evidence:
  `outcome-line.test.py` WorkerInformation and DiagnosticOwnership.

- [x] The K2 number-only repeat check is withdrawn (digit masking and equal output tails
  refused distinct source files and expanding reads). Runtime exact-call and
  unchanged-cycle protections remain. **Retained, for the architect's decision:** the
  narrow G1 rule the review permitted, which refuses only a PROVEN duplicate observation:
  the same recognized read-only query four times, differing only in the name of the scratch
  file it writes, with known exits, equal complete outputs and no edit between (the v28
  `t_564dfeaa` shape, 213 calls; the runtime counts a renamed scratch file as new
  output). Anything unproven is allowed. Evidence: `k2_selftest.py`
  duplicate_observation_checks, including the loop-root-cause change's counterexample
  cases; runtime retry-path check `tmp/v26-corrections/g-corrections/`.

- [x] The card that must repair a Servlet diagnostic is given its documented translation
  (v28 `t_25819d9c`, v26 Root17). M2 formed two outcomes for RootRestController: the file
  cluster `source:c:488e7e2d2ac4` owns all four compile diagnostics and no requirement;
  `objective:controller-request-boundary:1053f4400b4b` owns the `servlet-redirect-response`
  and CrossOrigin requirements, no diagnostic, and runs after it. The COMPILE card was
  issued `package javax.servlet.http does not exist` and `cannot find symbol
  HttpServletResponse` with no first action (only the CrossOrigin items had one), no
  REQUIRED SHAPE, and a line calling the recipe's requirements "not yours". The
  documented-first-action rendering could not help: there was no action to render. A
  compile item whose qualified type (explicit import, or the import a "package X does not
  exist" diagnostic stands on) has a compat-mapping `handler_parameters` row now carries
  that row's action as its first action. The other-owners line says the issued
  diagnostics are still this card's. DOCUMENTED FIRST ACTIONS now follow RETRY STATE,
  ahead of the checks, other diagnostics and REQUIRED SHAPE. Evidence: `brief.test.py`
  `_servlet_compile_item_first_action_case` (real catalog, default CLI output, a renamed
  specimen, both spellings) fails on `8c61115e` and passes after. Live: none.

- [ ] Residual model repetition is not qualified as fixed. The installed Qwen request
  profile serializes the published non-thinking sampling values. In a four-request
  same-profile probe, both original and both reformatted saved Root contexts repeated
  the empty search (284,177 tokens). Rendering alone did not solve that case; its
  missing Servlet translation must be distinguished from model capability. The
  documented first-action delivery correction was added after this probe. No production
  thinking switch, retry increase or new guard follows from this result. Evidence:
  `tmp/model-loop-root-cause-20260929/REPORT.md`. Qualify the actual completed task
  with its current recipes before claiming fewer loops or approving a model change.

- [x] Architect review F1: a skipped `run-verify.sh` invocation earlier in the run no
  longer refuses a later successful verification (the latest invocation is judged by its
  own call-bound record). F2: a current but failed or diagnostic-only verification asks
  for acceptance verification without a product edit, instead of forbidding it
  (`a7050053`; the architect's `architect-regressions.py` passes).
- [x] v27 M1: the source analysis copy is its own Maven project base (`MAVEN_BASEDIR`
  pinned by the build, source-packaging and MTA producers), so a source without `.mvn`
  no longer inherits the destination's `maven.config` (`beb8e4f7`;
  `maven-basedir-isolation.test.py` with real Maven on the nested layout).
- [x] **Parallel M3 pilot (scope decision 2026-09-29, supersedes the deferral for one
  pair):** exactly one pair of independent M3 repair outcomes runs concurrently in native
  worktrees; everything else stays serial. Requirements, implementation and evidence
  (synthetic, real-git, native-runtime) are in
  [PARALLEL-M3-PILOT.md](stages/130-ai-autonomous-migration/PARALLEL-M3-PILOT.md). On
  v28's real plan it selects RootRestController with `@Profile`. Live demonstration is
  owed by the next validation run: two overlapping workers and both changes verified
  after integration. Trade-off: in the pilot's chain, a blocked card holds back the cards
  after it.

Still open (not blockers of this package's source work):

- [ ] Publication: fast-forward `main` and publish the golden (Operator steps);
  the runtime is unchanged (image `9147834b`).
- [ ] Live evidence for A-D comes only from the next run.
- [x] An obligation no open card discharges no longer strands M3 BEHAVIOR (v28, an
  assisted diagnostic after the Operator unblocked PetType `t_1cec0a74`). Once compilation
  reached zero errors the package gate ran for the first time and failed at
  RootRestController.java (the SpEL field the accepted COMPILE card `t_25819d9c` kept;
  G3 now refuses it there). No plan node owned `rt:package:f4aa0ab756c50669`: M2 froze
  ownership before it existed, and M4's routing of later findings is never reached,
  because M4 waits on the BEHAVIOR cards. Five of the eight (Owner, Pet, PetType, Root,
  Specialty) were issued no write set, recorded witness checkpoints, stayed PENDING and
  blocked asking the Operator. Now `native_control.issue` on a behavior or runtime card
  first routes every open mandatory obligation no open outcome owns (only on a work
  list measured on the current tree), by M4's rules:
  - to its frozen owner, where `owner_of_finding` now also resolves the work-list
    cluster one outcome was formed from;
  - through a follow-up sharing that owner's budget when the owner is accepted, which
    becomes a prerequisite of every open behavior/runtime card and of M4 (the card ends
    with `OWNER_REPAIR_PENDING`, i.e. `kanban_block kind=dependency`, and native
    promotion resumes the waiting cards);
  - to the card itself when it owns the file;
  - otherwise to a named `ISSUE_ORPHANED_OBLIGATION` (`kind=needs_input`).
  FakeNative `link` now demotes a ready child as the pinned `kanban_db.link_tasks` does.
  Evidence: `native_m3_recovery.test.py` OrphanedObligations (5 tests); a replay on
  v28's plan r1 and live work list routes the one orphan to
  `followup:source:c:488e7e2d2ac4:m3g1` (RootRestController.java, the owner's budget),
  with all 8 BEHAVIOR cards and M4 waiting on it (`tmp/v26-corrections/orphan-route/`).
  Live: none.
- [ ] Evidence gaps kept from v26: preloaded skill text is not corroborated from the
  session store; `test_stall_guards` and `test_cli_preloaded_skills` were not run for
  0015/0016 (missing local dependencies).
- [ ] The v26 PVC was not copied after the stop (a read-only reader pod was refused by
  the permission classifier); the replays use the logs saved before the freeze.

Platform follow-ups (not package code):

- [ ] Plan the Qwen3.8 serving rollout for `c928d917` (non-thinking server
  defaults plus `--default-chat-template-kwargs`).
  - It is on `main`, but Argo 040 was deliberately not refreshed: the rollout
    needs a free GPU, and the Qwen3.6 pod is already Pending.
  - The flag is supported by vLLM `0.18.0+rhaiv.14`.
- [ ] Qwen3.6 serves the thinking-mode sampling defaults while its workers run
  with thinking off (the mismatch recorded for Qwen3.8 in v12). Out of v26 scope.
- [ ] Reconcile the shared checkout: local `main` holds pre-cherry-pick copies
  of the v26 commits, plus uncommitted edits the release has superseded.

Deliberately not planned (architect rulings, 2026-09-29):

- No guard for slow walks that yield a genuinely new line per call (v25 User run
  50: 18.9M input tokens). It stays an efficiency observation with no per-card
  cost bound; the causes (clipped text, no selectors) are fixed.
- No model-profile switch. The screen was inconclusive: 24 requests attempted,
  13 responses, 11 HTTP 429. A task-level comparison on the corrected harness is
  separate work.

Evidence history (v25):

- V26-6 as recorded on v25: qualify Servlet response/redirect
  guidance, carry actionable context into native retries, and expose saved
  verification diagnostics to prevent repeated searches and recompilation.
  Preserve the build's exit code through output filtering; run 18's final echo
  returned 0 while masking Maven's status, then the loop exhausted native retries.
  Keep the five-repeat guard and existing budgets; qualify the no-local-example
  and Profile recovery cases. Count worker halts even when native retry later
  completes the card. No overlay onto the active v25 run.
  Confirmed follow-up: derive the brief's immediate checks from its issued
  outcome; same-file repository requirements were incorrectly labelled as due
  now on the Profile compile card. Tool results and repeat warnings were present
  in all three failed sessions, with no observed compression. Qualify corrected
  inputs against both cases before attributing all loops to the model.
  DAO follow-up `t_90e674d6`: also fix composite-objective liveness and provide
  bounded brief selectors. Runtime patch 0014 falsely treats new diagnostic IDs
  in repeated JSON as no progress (installed-runtime reproduction: page 13).
  Its fix needs runtime tests and a new image alongside the golden; preserve
  the identical-repeat halt and the inline-Python restriction.

Licensing stays within the existing boundary: adopt eligible open-source
components under their licenses; avoid proprietary or restricted dependencies,
or independently implement similar behaviour from public contracts. Do not copy
restricted implementation code. No live overlay, isolation campaign, additional
scheduler, retry-budget increase, acceptance waiver or parallel M3 execution is
authorized by this plan.

## v24 package — golden `221de165` published; validation run `spring-petclinic-rest-legacy-v25`

The v24 validation run was named `spring-petclinic-rest-legacy-v25` by mistake when it was created
(2026-09-28). It is the v24 run: its destination's initial commit `1a26eab` carries a `.hermes` tree
identical to golden `221de165` (source `706e2fdd`, scaffold tree `9f271640`), `run_id`
`spring-petclinic-rest-legacy-v25`, `plan_semantics: v1`, `compatibility_objectives: v1`. No
`…-v24` run, record or repository exists. Records refer to it as "the v24 validation run (`…-v25`)".
`95ead23f` (tree `b0db84bd`) was superseded by `221de165` after the F1–F3 review and was never used
for a run.

Plan: `tmp/v23-run/V24-IMPLEMENTATION-PLAN.md`. Release identities and publication
notes: `tmp/v24-preparation/RELEASE-READINESS.md`. v23 is not changed by this package.

| Identity | Value | What it covers |
|---|---|---|
| Published golden | `95ead23f9e0d30c64df48203b7b61334a3bf2e87` | scaffold tree `b0db84bd24a361f76ac4a0ad253c52de8d6bdcd2` |
| Cleanup scaffold | `19db154b5b0d7876ed1bae1100d3bce78ecbe301` | refuses `rhoai3.run-budget/v1`; not published |
| Runtime | Hermes tree `498e2faf`, image `quay.io/rhoai3-coding-demo/rhoai3-ws-080@sha256:2ea8ebd6860519c450730f72550201b191beda7374275a79c79ec811689c93b7` | unchanged by the golden |

Do not attribute the `95ead23f` replay or validation to scaffold tree `19db154b`
or to any uncommitted working-tree correction.

Published in `95ead23f` (commits `e8c13adb`, `efb59233`, `9b3e1b92`, `e974e863`):

- WP1: the reviewer audit compares structured M1/M2 handoff facts. The narrative is not parsed.
- WP2: a measurement class is what the verification executed. Source-outcome `measure:tests` moves to M4. Outcome-board/v1 does not get that deferral; new runs use v2.
- WP3: M5 keeps `ship: false` until unresolved plan rows are resolved. The first published version accepted a hand-written resolution file and treated a lost plan as empty; that is what `95ead23f` contains.
- WP4: checkpoint and outcome lines are distinct; a satisfied outcome names a witness; the brief leads with retry state.
- WP5: `--json-output` is a boolean; a nonzero analyzer exit is accepted only for `MTA-8.2.1-DEPENDENCIES-JSON-MARSHAL` under the recorded conditions. Pinned rescan: `[4, 233, 0]`, 24 clusters.

- [x] **Decided (architect, revised 2026-09-28): the M2-published family budget governs v24** (`89005fe5`). One limit and one count on a governed outcome-board/v2 card: the issued contract's family key and limit (Pet family: 12 across the family, not 3, not 12 per card) and native `family_spent` (rejected candidates plus reviewer change requests). `advance.py` projects that count instead of adding its own; `decisions.max_attempts` stays an input to the initial budget and governs only the legacy serial/v1 loop. Cards, restarts and checkpoints never replenish the family; the twelfth charge exhausts it. No published budget refuses (`ISSUE_BUDGET_UNPUBLISHED`); an inconsistent account refuses (`LOOP_BUDGET_INCONSISTENT`). The published total is unchanged; v23 keeps its pinned rules. This supersedes the earlier "keep three" decision.
- [ ] **Republish with the F1–F3 review corrections** (committed as `b00585fd`, not in `95ead23f`). F1: M5 does not read `unresolved-resolutions.json`; resolution comes only from M4-bound parity receipts, per entry point and owed mode. F2: whether a plan is owed comes from pinned `loop.plan_semantics` and the admission seal; a missing, bare, list-less, duplicated, unsealed or re-bound plan blocks release; a declared legacy run and a valid empty admitted list pass. F3: the parity stage separates requested scope, execution and the verdict bound to this candidate and mode. Corrected reporting of the combined check: 93 executed checks and 2 skips; the replay proved equal derived plans, not two admitted native M2 runs.
- [x] **Harness defect found on the v24 validation run (…-v25) M1, fixed in the golden.** The `require_args` audit check tokenized the whole compound command, so `… --write; echo "EXIT=$?"` gave `--write;` and the reviewer's audit refused a correct M1 (both `handoff_facts.py --write` and `kanban_attach.py --exec` had run); the reviewer then looped reading the ledger and the loop guard halted it (card blocked). `args_of_run` now reads the tokens of the exact command that runs the script; the plan-only refusal is unchanged. With the fix, that M1's own log audits green (read-only check). Not in golden `221de165`.
- [ ] **WP6 live retirement is not measured.** Retire mode is authored on `19469a5d` and reverted on main by `915242c1`, so Argo CD cannot publish it before review. It removes the run's delivery PipelineRuns and pods, then `project-<run>` through its own finalizer, then `<run>-dev`, each ownership-checked by exact name. The tombstone names the kept repository. The admission policy `retired-migration-run-project` refuses recreation. Still required: one live retirement of a disposable run, and a security review of the cluster-wide delete grant `migration-run-retire-project`.
- [ ] Report the MTA 8.2.1 dependency-JSON defect to Red Hat support or upstream Konveyor. Draft: `tmp/v24-preparation/wp5-rescan/UPSTREAM-BUG.md`. YAML-only output and `--mode source-only` were not chosen.

## v23 comparison baseline — assisted where noted

`spring-petclinic-rest-legacy-v23` on golden `0ccb05e` (main `b77a6229`). M1 reproduced the fresh local derivation: 131 classpath entries, 100/100 types and 437/437 methods resolved, 34 entry points. Local facts: `tmp/v23-run/m1-facts.json`, `m2-facts.json`, and the `*.assisted.json` pair.

These results are not an autonomous success:

- M1 attach was plan-only until the six originals were attached to `t_56d38285` as operator-assisted attachments 36–41. Card result and verdict were unchanged.
- The Pet repository contract (`t_71d9117b`) was an assisted continuation. The Operator unblocked the card; run 3 rewrote `PetRepositoryImpl.java` and commit `439587bb` was accepted. Native review completed green. Retry accounting was not reset.
- M1/M2 prose contradicted the sealed artifacts (inventory is HTTP 34, non-HTTP 0; the plan keeps 7 ship-blocking groups). Correction comments and computed facts were added; the card histories were unchanged. Enforcement of that comparison is WP1, and the F1–F3 corrections above are not yet published.

## Open migration gaps

- [ ] Live Hermes board, M4 packaging, startup and parity on a migrated application, and the decided PostgreSQL. The application does not build yet.
- [ ] Product defects due at M4 parity: source override fragments' column-name JPQL, which Hibernate 7 rejects; the generated DTO's required `pets`; the `errors` objectName `OwnerDto` versus `ownerDto`.
- [ ] V17 follow-ups: a separator glued on both sides of an allowed path is still refused by K2 (fail-closed); a fragment unit's functional debt is recorded but the owner is not re-opened automatically; the V17-4 source generator is qualified only at openapi-generator 5.2.1 / 7.25.0; runtime proof of the null-Location and body cases was not run.
- [ ] Type-reference edges are in the golden (`type_refs` on destination type rows; regressions in `dest_model.test.py` and `worklist.test.py`). Not measured on a live partial tree. Still out of scope: dynamic entry points, reflection and `Class.forName`, annotation class literals, generated roots as modeled roots, and source-extractor intersection coverage.
- [ ] A packaging repair that exposes the next locatable cause should continue in the same card when that cause is a file of this tree. An unlocatable, set-wide or decision-shaped cause stays parked.
- [ ] A loop card that blocks without a verdict must leave the product tree as it found it: revert unaccepted edits in the write set, and refuse a block while paths outside `verification/` differ from HEAD.
- [ ] Automatic fragment-set handling is not implemented. The complete fragment-contract set must be derived and sealed from the type model, with one family identity, before automatic dispatch resumes. An incomplete type model yields unknown, never an invented set.
- [ ] Specimen independence remains required ([SOLUTION-ARCHITECTURE.md §2.1](stages/130-ai-autonomous-migration/SOLUTION-ARCHITECTURE.md)). PetClinic is the proving application. Build/start/reset, corpus derivation, behavioural qualification, guidance and executable invariance checks are still open. A text scan for application names is not proof.
- [ ] Measurement trust for outcome-board runs is `cooperative-receipts`: worker-produced build, test and parity evidence is trusted subject to binding checks. That is not independent verification. See [OUTCOME-BOARD-CONTRACT.md](stages/130-ai-autonomous-migration/OUTCOME-BOARD-CONTRACT.md).

Deferred from the v13 release, still not done: one bounded diagnostic action on an unproven handoff; attaching the source's own sort call (needs call-argument literals); upstream identical-cycle halt and a per-poller deadline; auto-generation when generated output is missing (`RESPONSE_TYPE_UNRESOLVED` today); producer regrouping.

Compatibility objectives (`loop.compatibility_objectives: v1`) and plan semantics v1 are selected for new runs and covered by the current tests. The measured PetClinic cases are in `tmp/v21-run/m3-partition-comparison/CASES-REPORT.md`. rgctl was not adopted.

## RHOAI 3.4 watch items

- [ ] Confirm whether governed model access, dashboard discovery, subscription assignment, API keys, quotas, rate limits, token limits and usage visibility are GA or a preview for the target release.
- [ ] Confirm whether `ExternalModel` and external inference through the same MaaS subscription are supported enough to drop any remaining upstream coexistence assumption.
- [ ] `qwen3-8-27b-int4` is local compatibility, not a Red Hat validated-model-matrix row. Do not relabel a passing local inference test as validation.

## Workarounds still required

- [ ] **MaaS gateway memory growth.** Release consolidation adds a GitOps-managed 1 GiB reservation / 2 GiB limit after a 912 MiB observation under the old 1 GiB limit. Resource rollout and bounded observation remain required; the cause of sustained growth is not established. Do not claim that extra capacity fixes a leak.

- [ ] **External-model streaming is buffered by IPP.** No viable 3.4 workaround. Internal models stream. `qwen3-235b` and `minimax-m2` stay off the gateway path until that changes. Diagnosis: [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).
- [ ] **Gateway AuthPolicy patch for user OAuth tokens** (`jobs/configure-kuadrant.yaml`): dashboard `gen-ai-ui` forwards user tokens; the operator policy accepts ServiceAccount tokens.
- [ ] **Authorino SSL env vars** on the same job, so Authorino trusts the OpenShift service CA.
- [ ] **Gateway hostname patch** (`jobs/patch-gateway-hostname.yaml`).
- [ ] **Model Registry NetworkPolicy** allowing `redhat-ods-applications` to port 8080.
- [ ] **Perses demo dashboard RBAC, Prometheus API gate, and MaaS tab labels.** Revert when the product opens the real Perses namespace and discovers the Cluster, Models and Usage tabs without demo labels.
- [ ] **`models-as-a-service` namespace** for `MaaSAuthPolicy` and `MaaSSubscription` until the operator-owned layout is confirmed.
- [ ] **Dashboard Route** via the `rh-ai.*` hostname through `data-science-gateway`.
- [ ] **ExternalModel credential Secret label** `inference.networking.k8s.io/bbr-managed=true`.
- [ ] **Community Grafana CRDs** may remain after the custom Grafana stack was removed. They are not active MaaS architecture unless Grafana custom resources reappear.
- [x] **Stage 010 monitoring transport cleanup.** Retired the COO 1.4 compatibility approval overlay, service-CA copy Job and Perses backend ingress workaround after native COO 1.5.3 installation, current Monitoring readiness, real metrics queries, native Perses backend queries and exact trace retrieval passed on RHOAI 3.5.1. Persona-dependent dashboard RBAC remains pending actual UI/access evidence.

Stage 040 validation must keep asserting that `maas-api` uses `registry.redhat.io/rhoai/odh-maas-api-rhel9`. Do not restore the tokens bridge, tier groups, or the upstream `maas-controller` image override.

## Known limitations

- [ ] GPUaaS dashboard metric names need live confirmation. Stage 020 warns rather than fails when DCGM or Kueue names differ.
- [ ] Full llm-d autoscaling and disaggregated prefill/decode are not implemented. The demo has two NVIDIA L4 GPUs, and the installed `LLMInferenceService` `v1alpha1` CRD does not expose `spec.scaling`.
- [ ] Single-endpoint body-based multi-model routing (agentgateway / GAIE) is not implemented.
- [ ] `ExternalModel` name must match the provider model name. Upstream: [opendatahub-io/models-as-a-service#684](https://github.com/opendatahub-io/models-as-a-service/issues/684).
- [ ] Gen AI Playground uses one MaaS request token per call path. Models that appear together need one consumer subscription.
- [ ] The AI asset endpoints dropdown lists every namespace where the user has RBAC, including Dev Spaces namespaces.
- [ ] Upstream ODH BBR supports `/chat/completions` only. Models that require `/v1/responses` cannot use the standard MaaS pipeline until that fork adds it.
- [ ] Dashboard workspace and editor creation is not atomic. The duplicate guard stops a second seat; it does not reconstruct a missing editor. Recover a partial creation under the original run name. See [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).
- [ ] llm-d router-scheduler pods carry the modelcar and no `ephemeral-storage` request, so two of them can fill one 100Gi worker. `scheduler.template` affinity and a namespace `LimitRange` were tried and reverted. Remaining options: bring-your-own endpoint picker, or larger CPU-worker disks.
- [ ] Ingress ELB idle timeout (`classicLoadBalancer.connectionIdleTimeout: 1h`) is cluster-local and must be reapplied on a fresh cluster.
- [ ] Kuadrant recreates `kuadrant-limitador-monitor` about every 10 minutes, which gaps the Usage dashboard.
- [ ] ExternalModel routes export no `model` label and no token-usage counters.
- [ ] Argo CD has twice applied a new SHA while rendering stale manifests. The recovery recipe is in troubleshooting; the cause is not identified.

## Planned

- [ ] Rewrite the Stage 010–040 sections of `docs/OPERATIONS.md` and `docs/TROUBLESHOOTING.md` from a fresh-environment deployment. Carry current MaaS quirks.
- [ ] TechDocs for Developer Hub reflecting the current stages (Kilo Code, OpenCode, spec-kit).
- [ ] Confirm final GPUaaS Prometheus metric names.
- [ ] Red Hat UDI-based `ai-tools` image. Until then, Stage 070 sets Java 21 at workspace start. The digest-pinned `quay.io/che-incubator/cli-ai-tools` image stays.
- [ ] Re-evaluate Cline if a release adds SDK file-based provider config. Kilo Code 7.4.7 is the IDE assistant.
- [ ] Remove stale `.continue` templates from the external `coolstore-inventory-service` repo.
- [ ] Scope the OpenShift MCP ServiceAccount below cluster-wide `view`.
- [ ] Parameterize cluster-specific values for a second cluster.
- [ ] `reset-coolstore-demo --prune-quay` for accumulated image tags.
- [ ] Reset stale-golden guard: `--golden <sha>` and a warning when `golden` is not the last blessed baseline.
- [ ] Kilo codebase indexing against `granite-embedding-english-r2`.
- [ ] Dev Spaces `devspace-ai-tools-init` via `mount-on-start`, including the GitOps `agentic-coolstore` DevWorkspace. Do not half-land it.
- [ ] Tekton Chains signed provenance on `app-platform-push` once a Securesign instance exists.
- [ ] Developer Lightspeed overlay for Developer Hub, after a live LCS-to-MaaS protocol check.
- [ ] Trusted-delivery stage: SLSA, sigstore, SBOM and TPA for the migrated app, after a concrete pipeline and validation path exist.
- [ ] `GITHUB_OWNER` substitution so a fresh environment is not tied to `adnan-drina`. Land as one change after the fork step is documented.
- [ ] Per-user MaaS subscriptions. `ai-developer` and `ai-admin` currently share one key set.
- [ ] Pick one scaffold source of truth so `scaffold-repo/` cannot drift from the live golden unnoticed. Stage 070 validate warns on drift.
- [ ] Developer Lightspeed / Kai stays removed until the demo needs it. Restoring it recouples MTA to a healthy model upstream. The console API-key path works without it.
- [ ] Quarkus MCP doc search needs a container runtime the workspace SCC does not allow. Core MCP tools stay workspace-local.
- [ ] Qwen3.6-35B NVFP4 stays parked: the official modelcar exists, and vLLM Marlin emulation garbles BF16 NVFP4 output on Ada (sm89).
- [ ] MTA Hub custom migration target stays out of scope until the Hub joins the demo flow.
- [ ] Monolith extraction of one bounded context stays deferred. Stage 080 is in-place migration of the pinned PetClinic REST specimen.
- [ ] Workspace pods can fail the API for roughly the first three minutes of a pod's life. The next fresh start should log seconds-since-start at the first HTTP 200 before changing the poll.
- [ ] `quarkusio/quarkus-skills` (`migrate-spring-to-quarkus`) is a candidate install for the migration workspace. Not installed.

Developer workflow topics 120–170 are not stages. Recreate one only with an implementation plan, validation, and GitOps ownership where the platform owns the resource. Stage 110's review discipline lives in Stage 070.

## Baseline comparison retained locally

| Record | Why it remains |
|---|---|
| `tmp/v23-run/V24-IMPLEMENTATION-PLAN.md` and the M1/M2 facts files | v24 plan and the assisted v23 classification |
| `tmp/v24-preparation/RELEASE-READINESS.md`, `architect-review/`, `wp5-rescan/`, replay summaries | publication identity and the check that must be repeated after republish |
| `tmp/v21-run/m3-partition-comparison/{CASES-REPORT,IMPLEMENTATION-DESIGN,RELEASE-MAPPING}.md` | measured compatibility-objective cases |
| `tmp/v21-run/v21-validation.md` | which image v21 actually ran |
| `tmp/hermes-runtime-review-2026-09-28/REVIEW.md` and `tmp/v21-fixes/` | qualification of the current image `2ea8ebd6` |
| `tmp/080-operator/build-130-runtime-image.sh` | rebuilds that image from `hermes-runtime/patches` |


### Stage 040 remaining acceptance (2026-10-05)

Native deployment, two private-model APIs/streaming, Red Hat MiniMax governed streaming, key lifecycle and isolated quota enforcement passed. The API-key-loading failure is repaired at the backend. Remaining: replenish GPT-6 Luna account credits (`credit_balance_exhausted`), qualify actual EPP execution (targeted counters remain absent), and user-check GenAI Studio key listing/project interaction. No browser pass or complete Stage 040 acceptance is claimed. Existing model quotas and workspace local-only access remain unchanged. [Evidence and boundaries](docs/migration/040-governed-serving-plan.md#final-bounded-runtime-evidence).

### Planned Stage 060 Agent Runtime and AgentOps

Stage 060 is a planned platform stage; Stage 070 retains developer services and requested Gitea integration. Qualify pinned OpenShell/runtime isolation, authenticated lifecycle, independent verifier and catalog ingestion before implementation. No AgentOps deployment or completed-agent claim follows from the numbering change. See [runtime design](docs/migration/060-agent-runtime-and-agentops-plan.md) and [developer/SCM design](docs/migration/070-developer-platform-and-scm-plan.md).

### Deferred optional MCP Gateway

The unused RHCL MCP Gateway prerequisite is removed from the demo source and cluster; direct native MCP lifecycle, Registry and Studio remain separate. Selected 0.7.1 private testing changed an unrelated health request 200→404 after filter insertion. A dedicated two-listener candidate reached configured policy conditions but failed MCP initialization with HTTP500, empty Registration status and WASM/router diagnostics. No gateway aggregation, MaaS-key governance or renewal capability is claimed. Revisit only with a concrete consumer and independently qualified native topology; do not attach the tested port-wide filter to the shared model Gateway. See the [recorded evidence](docs/migration/035-feature-completion.md#dedicated-mcp-gateway-authentication-qualification--2026-10-08).

### Claude Sonnet 5.5 and the gateway token-metering limitation (2026-10-09)

Claude Sonnet 5.5 is registered with `apiFormat: openai-chat` and `path: /v1/chat/completions` (Anthropic's OpenAI-compatible endpoint) after bounded JSON and SSE requests passed with exact token metering. The native `messages` registration is withdrawn: on RHOAI 3.5.1 with Connectivity Link 1.4.3 (wasm-shim 0.14.2) the gateway holds any response without `usage.total_tokens` until the client times out (Kuadrant/wasm-shim#425, fixed upstream in 0.14.3). Claude personal access does not expand DevSpaces beyond its retained local-only policy. MiniMax M2 and the `redhat-models` provider were removed from Stage 040 on 2026-10-09; the Stage 070 workspace AD-008 MiniMax escalation path (direct Red Hat portal) was removed the same day (workspace init no longer reads `REDHAT_MODELS_*`; the scaffold reviewer stays Qwen). Open items:

- Re-test the native Messages registration, error-response delivery and SSE streams whose usage precedes a trailing empty chunk when a Connectivity Link release with wasm-shim 0.14.3 or later reaches the `stable` channel; the AuthPolicy `x-api-key` CEL predicate (fixed upstream 2026-09-11) and the `stream-usage-enforcer` ordering for native Messages streaming need the same re-test.
- `validate-functional.py` stops reading SSE at `[DONE]`; add a bounded wait for stream closure so a held stream fails the check.
- Intermittent fast `503 upstream_reset_before_response_started` on reused provider connections (OpenAI and Anthropic); Istio default retries exclude `reset` and the DestinationRule is controller-owned.
- Parked Qwen 3.6 (`replicas: 0`) still reports `ready=true` in the MaaS catalog and returns 503.
- Gen AI Playground: the UI sends Temperature (default 0.1) and the BFF's provider-level `max_tokens` 4096; Claude 5.x rejects any temperature other than 1, gpt-6-luna rejects `max_tokens` and non-default temperature. GPT-4.1 (`gpt-4-1`) was registered on 2026-10-09 and accepted in the playground the same day; Claude works with Temperature set to 1 (verified through the gateway, playground acceptance pending); GPT-6 Luna waits for the RHOAIENG-90257 backport (provider `max_tokens` default) plus Temperature 1. Red Hat RFE: model-specific default sampling parameters in the playground (TROUBLESHOOTING "Gen AI Playground Gets No Answer From External Models").


### Common MaaS routing and Studio persistence checkpoint (2026-10-08)

Local hosting moved to internal-models; governance stays models-as-a-service. Common `/v1` passed bounded Qwen 3.8 SSE, GPT JSON and MiniMax JSON requests. Native catalog endpoints select the common API hostname. API-host namespace-qualified local legacy path returned HTTP 503, while the same path on the retained model hostname passed SSE; native listener-specific processing cause remains unresolved. Keep compatibility listeners pending explicit retirement acceptance; no generated route/Envoy patch. Parked Qwen 3.6 is not inference-qualified.

Native Studio PVC restoration preserved its exact saved response and profile UUIDs/settings; temporary restore resources are removed. Two historical cached model IDs remain unreferenced, with no supported unregister API exposed by the installed build. Fresh helper persistence is source-reviewed, fresh E2E untested. No Claude test was resumed and no quota was reset.
