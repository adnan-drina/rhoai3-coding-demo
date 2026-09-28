# Backlog

Open limitations, unfinished work, and the evidence needed to understand them.
Completed run narratives remain in Git history. Paths under `tmp/` are local
evidence, excluded from Git.

## v26 improvements: reusable migration repairs — planned after v25 validation (2026-09-28)

The current validation run is `spring-petclinic-rest-legacy-v25` and validates the v24 package
(see the v24 section). The improvements formerly planned as v25 are now planned for v26.

Finish the current v25 validation run first. The detailed scope,
design decisions and acceptance criteria are in
[V26-IMPROVEMENTS.md](stages/080-ai-autonomous-migration/V26-IMPROVEMENTS.md).
This is a future improvement list, not an implementation or release claim.

- [ ] Execute two qualified repairs deterministically inside existing M3 scopes:
  selected repository CDI exposure and handler URI parameter translation.
- [ ] Qualify recipes with before/after, no-change, idempotence, type-resolution,
  scope and real behavioural checks; preserve native review and acceptance gates.
- [ ] Generate compact, evidence-bound objective context from existing analysis.
- [ ] Extend the v24 package's reporting, validated in v25, with actual transformation results and measured cost.
- [ ] Compare against the completed v25 validation baseline, then validate on a fresh v26 run.
- [ ] Later optimization only: analysis reuse with complete cache invalidation.

Licensing stays within the existing boundary: adopt eligible open-source
components under their licenses; avoid proprietary or restricted dependencies,
or independently implement similar behaviour from public contracts. Do not copy
restricted implementation code. No scope expansion of the current v25 run, live overlay, isolation
campaign, additional scheduler or parallel M3 execution is authorized by this plan.

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
