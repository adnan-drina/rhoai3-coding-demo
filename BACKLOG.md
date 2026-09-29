# Backlog

Open limitations, unfinished work, and the evidence needed to understand them.
Completed run narratives remain in Git history. Paths under `tmp/` are local
evidence, excluded from Git.

## v26 reliability release and the subsequent feature package (scope decided 2026-09-29)

v25 (`spring-petclinic-rest-legacy-v25`, the v24 package) is preserved as an
**assisted diagnostic run**: 21 of 36 cards, two recorded harness rebases and
four unblocks. It is a partial baseline for M1, M2 and part of M3, not an
end-to-end one.

**v26 is the reliability validation release:** M1→M5 without harness overlays or
Operator rescues, with every acceptance gate preserved. Scope and per-item
evidence status are in
[V26-IMPROVEMENTS.md](stages/080-ai-autonomous-migration/V26-IMPROVEMENTS.md).
Status there is source-level (tests, model-free reproductions) unless marked live.

In v26:

- [x] V26-6 known defects: brief ownership, liveness, selectors and whole
  architecture; retry-state diagnostics; the REVERTED lockout; unchanged rework;
  the preload of required skills; near-duplicate progress (runtime 0015).
  Source-level evidence; see V26-IMPROVEMENTS.md.
- [ ] V26-6 open items: Servlet response/redirect guidance (item 1); the repeated
  command/result and last step in the native retry handoff (item 2); the producer
  exit code through a worker's own filter or trailing echo (item 3).
- [x] V26-3 targeted context (instructions, selectors, owned obligations, saved
  diagnostics, retry context). The resolved-context attachment and a
  classpath/API lookup are deferred.
- [ ] V26-4: report actual verification, retries, assistance, requests, tokens
  and elapsed time from existing records at the close of the v26 run.

Subsequent feature package (V26-1 with V26-2), not scheduled for a numbered run:

- [ ] Execute two qualified repairs deterministically inside existing M3 scopes:
  selected repository CDI exposure and handler URI parameter translation.
- [ ] Qualify recipes with before/after, no-change, idempotence, type-resolution,
  scope and real behavioural checks; preserve native review and acceptance gates.
- [ ] Recipe-specific V26-4 reporting ships with the executor.
- [ ] Deferred pending measurements (V26-5): analysis reuse with complete cache
  invalidation.

Next reliability package, after v26 (recorded 2026-09-29, in priority order).
v26 is not changed by any of these (no overlay):

1. [x] **V26-6 item 1: Servlet response/redirect guidance.** Implemented on
   `next/after-v26` (463dbd0a, source-level): undocumented catalog rows for the
   jakarta and javax Servlet request/response types, routed to
   controller-request-boundary; redirect becomes `ResponseEntity` with 302 and the
   same `Location`.
   - It is live-relevant: v26 `t_4fd2dcec` run 1 (controller request boundaries,
     `RootRestController`) halted correctly on `read_cycle_no_new_content_halt`
     while cycling catalog greps for a Servlet rule that does not exist.
   - Add a qualified catalog and brief action for the supported source shape.
   - Preserve the redirect status, `Location` and context path.
2. [x] **V26-6 item 3: an authoritative verifier exit record.** Implemented
   (c02e319b): `run-verify.sh` writes `verification/loop/last-verify.json`; the
   brief prints it and the audit refuses when the verifier itself exited non-zero. Workers pipe
   `run-verify.sh | tail` or `mvn | grep; echo`, so the terminal and the ledger
   report the filter's exit code (seen on three v26 cards).
   - `run-verify.sh` should write its own exit record, and the brief should
     expose it.
   - `advance.py`'s verdict stays the authority, so acceptance is unaffected.
3. [x] **V26-6 item 2, remaining part: native retry handoff.** Implemented
   (657be426): the brief's PREVIOUS RUN block. Carry the repeated
   command and its result, and the last completed step, into the next native run.
   Introduced diagnostics, the REVERTED lockout and rework already ship in v26.
4. [x] **Card and handoff wording** (implemented, 398afb97) (v26 completed-task audit):
   - COMPILE bodies say "compile and pass its tests", while tests are owned by
     M4. Say that.
   - The M2 handoff says "34 children", while 31 are direct children. The
     reviewer then wrote that the M5 ids do not exist after Hermes's completion
     guard (`completion_blocked_hallucination`) rejected them as non-children.
     Name direct children and descendants separately.
5. [x] **Stale image values in the golden** (implemented, edb93305; validate.sh
   now refuses any rhoai3-ws-080 digest that differs from pins.json) (hygiene): `run-defaults.json`
   `workspace_overlay.digest` and the golden `devfile.yaml` still name
   `sha256:6a8a69a3…`. Nothing consumes them (workspaces render from the RHDH
   skeleton; launch compares `080.pins` with `pins.json`), but pin or remove them
   with each release.
6. [x] **V26-4 reporting tool.** Implemented (c3b3b80d): run-report's
   Reliability section, `--kanban-db` for a board copy. v26 is reported by hand from existing records:
   native runs, the execution ledger and the request ledger. Script the report
   without adding a receipt or an authority.
7. [ ] **Evidence gaps:**
   - Preloaded skill text cannot be corroborated from the session store (empty
     `system_prompt`; the ledger records `prompt_sha256`).
   - `test_stall_guards` and `test_cli_preloaded_skills` were not run for
     0015/0016 (missing local dependencies; identical on the base).
   - V26-6 acceptance still lacks a bounded worker replay of the no-local-example
     case and a same-model comparison of old and corrected brief inputs.

Found in v26 and implemented on `next/after-v26` (source-level):

- [x] The audit refused an abbreviated compound command (`💻 $ … + N commands`) as
  "silence: step run-verify" on `t_d5579123` (29df6451). It now credits the line
  only when the execution ledger records the loop script; prose is never a run.
- [x] An empty checkpoint was accepted as a repair (`t_4fd2dcec`, 93bf5c97).
  A checkpoint with no product change is now recorded as a witness (a9d81a3b).

Publication of `next/after-v26` (main fast-forward and golden) is the Operator's
step for a future run; no runtime patch changed, so the image stays 9147834b.

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
- [ ] Specimen independence remains required ([SOLUTION-ARCHITECTURE.md §2.1](stages/080-ai-autonomous-migration/SOLUTION-ARCHITECTURE.md)). PetClinic is the proving application. Build/start/reset, corpus derivation, behavioural qualification, guidance and executable invariance checks are still open. A text scan for application names is not proof.
- [ ] Measurement trust for outcome-board runs is `cooperative-receipts`: worker-produced build, test and parity evidence is trusted subject to binding checks. That is not independent verification. See [OUTCOME-BOARD-CONTRACT.md](stages/080-ai-autonomous-migration/OUTCOME-BOARD-CONTRACT.md).

Deferred from the v13 release, still not done: one bounded diagnostic action on an unproven handoff; attaching the source's own sort call (needs call-argument literals); upstream identical-cycle halt and a per-poller deadline; auto-generation when generated output is missing (`RESPONSE_TYPE_UNRESOLVED` today); producer regrouping.

Compatibility objectives (`loop.compatibility_objectives: v1`) and plan semantics v1 are selected for new runs and covered by the current tests. The measured PetClinic cases are in `tmp/v21-run/m3-partition-comparison/CASES-REPORT.md`. rgctl was not adopted.

## RHOAI 3.4 watch items

- [ ] Confirm whether governed model access, dashboard discovery, subscription assignment, API keys, quotas, rate limits, token limits and usage visibility are GA or a preview for the target release.
- [ ] Confirm whether `ExternalModel` and external inference through the same MaaS subscription are supported enough to drop any remaining upstream coexistence assumption.
- [ ] `qwen3-8-27b-int4` is local compatibility, not a Red Hat validated-model-matrix row. Do not relabel a passing local inference test as validation.

## Workarounds still required

- [ ] **External-model streaming is buffered by IPP.** No viable 3.4 workaround. Internal models stream. `qwen3-235b` and `minimax-m2` stay off the gateway path until that changes. Diagnosis: [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).
- [ ] **Gateway AuthPolicy patch for user OAuth tokens** (`jobs/configure-kuadrant.yaml`): dashboard `gen-ai-ui` forwards user tokens; the operator policy accepts ServiceAccount tokens.
- [ ] **Authorino SSL env vars** on the same job, so Authorino trusts the OpenShift service CA.
- [ ] **Gateway hostname patch** (`jobs/patch-gateway-hostname.yaml`).
- [ ] **Model Registry NetworkPolicy** allowing `redhat-ods-applications` to port 8080.
- [ ] **Perses backend NetworkPolicy, demo dashboard RBAC, Prometheus API gate, and MaaS tab labels.** Revert when the product opens the real Perses namespace and discovers the Cluster, Models and Usage tabs without demo labels.
- [ ] **`models-as-a-service` namespace** for `MaaSAuthPolicy` and `MaaSSubscription` until the operator-owned layout is confirmed.
- [ ] **Dashboard Route** via the `rh-ai.*` hostname through `data-science-gateway`.
- [ ] **ExternalModel credential Secret label** `inference.networking.k8s.io/bbr-managed=true`.
- [ ] **Community Grafana CRDs** may remain after the custom Grafana stack was removed. They are not active MaaS architecture unless Grafana custom resources reappear.
- [ ] **RHOAI monitoring service-ca Secret sync.** Stage 010 copies `ConfigMap/prometheus-web-tls-ca` into the Secret the generated `MonitoringStack` references. Remove the sync if a later build creates the Secret or points at the ConfigMap.

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
- [ ] Red Hat UDI-based `ai-tools` image. Until then, Stage 060 sets Java 21 at workspace start. The digest-pinned `quay.io/che-incubator/cli-ai-tools` image stays.
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

Developer workflow topics 120–170 are not stages. Recreate one only with an implementation plan, validation, and GitOps ownership where the platform owns the resource. Stage 110's review discipline lives in Stage 060.

## Baseline comparison retained locally

| Record | Why it remains |
|---|---|
| `tmp/v23-run/V24-IMPLEMENTATION-PLAN.md` and the M1/M2 facts files | v24 plan and the assisted v23 classification |
| `tmp/v24-preparation/RELEASE-READINESS.md`, `architect-review/`, `wp5-rescan/`, replay summaries | publication identity and the check that must be repeated after republish |
| `tmp/v21-run/m3-partition-comparison/{CASES-REPORT,IMPLEMENTATION-DESIGN,RELEASE-MAPPING}.md` | measured compatibility-objective cases |
| `tmp/v21-run/v21-validation.md` | which image v21 actually ran |
| `tmp/hermes-runtime-review-2026-09-28/REVIEW.md` and `tmp/v21-fixes/` | qualification of the current image `2ea8ebd6` |
| `tmp/080-operator/build-080-runtime-image.sh` | rebuilds that image from `hermes-runtime/patches` |
