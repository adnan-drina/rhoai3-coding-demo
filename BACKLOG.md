# Backlog

## RHOAI 3.4 upgrade watch items

As of 2026-05-18, the public Red Hat OpenShift AI 3.4 documentation describes the target MaaS model as subscription-based governance with API keys, group assignment, token limits, authorization policy, and usage tracking. The same release documentation still marks several MaaS-related surfaces as Technology Preview or Developer Preview. Do not remove demo workarounds automatically, because adjacent pieces still have narrower support scope or live-demo gaps: AI Available Assets with MaaS is Developer Preview, vLLM MaaS and MaaS observability are Technology Preview, external provider routing must keep its provider trust boundary explicit, and the current demo still carries compatibility glue for dashboard user-token handling and cluster-specific gateway setup.

Before upgrading this demo, verify the target RHOAI build against the following MaaS capability boundaries:

- [ ] **Governed model access support scope** — Confirm whether governed model access, dashboard discovery, subscription assignment, API-key access, quota enforcement, rate limits, token limits, and usage visibility are GA, Technology Preview, Developer Preview, or otherwise scoped for the target release.
- [x] **`MaaSSubscription` and `MaaSAuthPolicy` support** — Confirmed against the target RHOAI 3.4 build. The active GitOps path now uses these CRDs for model access and token limits instead of manual tier policy resources.
- [x] **`maas-api` API-key lifecycle** — Product `maas-api` supports subscription-bound API key creation and revocation through `/maas-api/v1/api-keys` in the target 3.4 build. The active GitOps path no longer deploys the demo tokens bridge.
- [x] **MaaS observability path** — Active GitOps now installs the documented observability operator prerequisites, enables `DSCInitialization.spec.monitoring`, enables the RHOAI observability dashboard flag, enables Kuadrant observability, and keeps MaaS telemetry on the `Tenant`.
- [ ] **External model and payload processing support** — Confirm whether `ExternalModel`, payload/request processing, provider credential injection, and external inference through the same MaaS subscription and policy surface are product-supported enough to remove the upstream `maas-controller` coexistence path.
- [x] **3.3 tier model removal** — Server-side dry-run validation confirmed the target RHOAI 3.4 build accepts local model resources without tier annotations. The active GitOps path now removes tier annotations, the `tier-to-group-mapping` ConfigMap, tier-named groups, tier ServiceAccount RBAC, manual tier policy resources, and the tier-shaped community Grafana dashboard.

## Workarounds (review when supported RHOAI 3.4 paths cover them natively)

The following items use manual configuration or post-deploy patches because the demo validates MaaS, dashboard, gateway, and observability behavior across several product surfaces. Review each item against the exact Red Hat OpenShift AI 3.4 build in the target cluster and remove it only after the replacement behavior has been validated in this demo.

- [ ] **IPP response passthrough EnvoyFilter** (`governance/base/ipp-response-passthrough-envoyfilter.yaml`) — RHOAI 3.4's Ingress Payload Processing buffers streaming responses through the MaaS gateway (KB: "MaaS streaming responses buffered through gateway"); external-model streams starve clients (~60s silence) and reset at ~310KB. Our variant keeps request-side IPP (external models need model resolution + key injection) and disables only response processing (all external providers are OpenAI-compatible).
  **Revert:** RHOAI 3.5 ships the product fix — delete the EnvoyFilter and this entry on upgrade.

- [ ] **Gateway AuthPolicy patch for user OAuth tokens** — The operator-managed gateway policy path accepts ServiceAccount tokens (`maas-default-gateway-sa` audience). The dashboard's `gen-ai-ui` forwards user OAuth tokens. The `configure-kuadrant` Job patches `gateway-default-auth` to add `user-tokens` authentication and patches `maas-api-auth-policy` to add empty `authorization: {}` so `/maas-api/*` management endpoints do not inherit the gateway-level access check.
  **Revert:** A supported MaaS operator path should configure AuthPolicies that accept dashboard-forwarded tokens natively.

- [ ] **Authorino SSL env vars** (`jobs/configure-kuadrant.yaml`) — Job sets `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` on Authorino deployment so it trusts OpenShift's internal service-ca.
  **Revert:** Verify if the supported operator path handles this natively.

- [ ] **Gateway hostname patch** (`jobs/patch-gateway-hostname.yaml`) — Job patches MaaS Gateway with cluster-specific hostname and TLS cert name.
  **Revert:** The supported operator path may parameterize the Gateway hostname.

- [ ] **Model Registry NetworkPolicy** (`model-registry/registry/dashboard-networkpolicy.yaml`) — The operator's default NetworkPolicy only allows same-namespace access. We add a policy allowing `redhat-ods-applications` to reach the registry on port 8080.
  **Revert:** The supported operator path should create proper NetworkPolicies for the dashboard.

- [ ] **Perses backend NetworkPolicy, demo dashboard RBAC, Prometheus API gate, and MaaS tab labels** (`observability-operators/perses-backend-operator-access.yaml`, `observability-operators/perses-dashboard-rbac.yaml`, `jobs/label-observability-dashboard-tabs.yaml`) — The generated RHOAI observability backend policy can allow the historical Cluster Observability Operator namespace while the Perses operator is installed by OLM in `openshift-operators`. The demo also grants the `rhoai-admins` persona read-only access to Perses dashboard resources and the narrow `prometheuses/api/k8s` get/create checks used by the observability frontend and Perses query path, so the non-cluster-admin admin user can open the RHOAI dashboard when the UI performs cluster-wide dashboard discovery and tab gating. Stage 040 labels the product-generated Cluster and Models dashboards for MaaS dashboard tab discovery.
  **Revert:** Remove these resources if a later RHOAI/observability operator build creates backend ingress for the actual Perses operator namespace, the demo uses a product-supported dashboard access role, and the product-generated Cluster, Models, and Usage tabs are discovered without demo labels.

## Retired pre-3.4 workarounds and remaining compatibility glue

The upstream `maas-controller` coexistence path and `maas-api` image override were used before the 3.4 operator-owned MaaS path was available in the demo. Keep these as historical context and do not reintroduce them unless a live 3.4 product gap is proven and documented.

- [x] ~~**maas-api image pinning** (`jobs/patch-maas-api-storage.yaml`) — The older workaround pinned the tenant-managed deployment to `quay.io/opendatahub/maas-api:latest` for model discovery. The 3.4 demo now expects operator-owned `registry.redhat.io/rhoai/odh-maas-api-rhel9` and `registry.redhat.io/rhoai/odh-maas-controller-rhel9` deployments.~~
  **Validation:** Stage 040 validation must continue to assert that `maas-api` uses a `registry.redhat.io/rhoai/odh-maas-api-rhel9` image.

- [ ] **`models-as-a-service` namespace** — The current 3.4 demo stores `MaaSAuthPolicy` and `MaaSSubscription` CRs in the `models-as-a-service` namespace. Keep this namespace until the operator-owned layout and validation rules are confirmed for the exact target build.

- [ ] **Dashboard Route** — The Red Hat OpenShift AI dashboard is accessed via the `rh-ai.*` hostname through the `data-science-gateway`. The operator's default `rhods-dashboard` Route redirects to the gateway.

- [ ] **ExternalModel credential Secret label** — Secrets referenced by `ExternalModel.spec.credentialRef` must have the label `inference.networking.k8s.io/bbr-managed=true` for the payload-processing (IPP) plugin to discover them.

- [x] ~~**Tokens-bridge** (`tokens-bridge/deployment.yaml`) — The compatibility bridge translated `/maas-api/v1/tokens` to `/v1/api-keys` for older Playground/dashboard call paths. The active GitOps path now relies on the product MaaS API key path and no longer deploys this bridge.~~

- [x] ~~**Community Grafana monitoring binding** (`ClusterRoleBinding/grafana-sa-cluster-monitoring-view`) — The older custom MaaS showback dashboard bound `grafana/grafana-sa` to `cluster-monitoring-view`. The `grafana` namespace and service account are gone, and the orphaned binding was removed from the live `cluster-t977r` sandbox on 2026-05-18.~~

- [ ] **Community Grafana CRDs** — Grafana Operator CRDs and generated aggregate ClusterRoles can remain after the historical custom Grafana stack is removed. Do not treat them as active MaaS architecture unless `grafana.*` custom resources, a `grafana` namespace, or demo-owned Grafana RBAC bindings reappear.

- [ ] **RHOAI monitoring service-ca Secret sync** — The generated RHOAI 3.4 `MonitoringStack` references `Secret/prometheus-web-tls-ca`, while the OpenShift service-ca injection path creates the CA bundle as `ConfigMap/prometheus-web-tls-ca`. Stage 010 syncs that bundle into the expected Secret at deploy time without committing certificate material.
  **Revert:** Remove the sync hook if a later RHOAI build creates the Secret natively or changes the generated `MonitoringStack` to reference the ConfigMap.

## 3.3 tier-model cleanup status

- [x] Removed `alpha.maas.opendatahub.io/tiers` annotations from local `LLMInferenceService` manifests.
- [x] Removed `tier-to-group-mapping` from the active GitOps path.
- [x] Replaced `tier-free-users`, `tier-premium-users`, and `tier-enterprise-users` with existing `rhoai-users` and `rhoai-admins` subscription consumer groups.
- [x] Removed manual tier ServiceAccount RBAC from the active GitOps path.
- [x] Removed manual tier-shaped gateway `RateLimitPolicy`, `TokenRateLimitPolicy`, `TelemetryPolicy`, and the community Grafana dashboard from the active GitOps path.
- [x] Preserved historical upstream `maas-controller` and `maas-api` override language only as completed historical context.
- [x] Added `scripts/audit-maas-cleanup.sh` and Stage 040 validation coverage so retired 3.3 tier resources, the tokens bridge, upstream MaaS controller/image overrides, and the old community Grafana binding are caught if they reappear.

## Cluster capacity watch items

- [x] **CPU workers disk-pressure eviction root cause resolved** — the growing component (Prometheus emptyDir TSDBs) is fixed by gp3-csi volumeClaimTemplates in `gitops/stages/030-.../monitoring/base/` (platform 2×40Gi 7d/8GB, UWM 2×20Gi 7d/5GB). The fixed cost (modelcar images ~30–37 GiB pinned by router-scheduler pods on CPU workers) remains, but no longer triggers eviction waves by itself. The `LLMInferenceService.spec.router.scheduler` has no scheduling fields — co-locating router-schedulers with GPU nodes is a product RFE candidate. Worker disk resize is NOT needed with the Prometheus PVC fix in place. Monitor `/var` headroom as a demo-prep check; do not work around it by removing the stage 020 taint.

## Deferred Developer Workflow Topics

- [ ] **Stage 110 merged into Stage 060; developer workflow topics 120-170 moved out of `stages/`** — Stage `110` is no longer a separate stage. Its Continue prompt-pack, README/API alignment, gap-list, Code-to-Docs, trust-boundary, and human-review guidance now lives in Stage 060 as the review discipline for vibe coding. Topics `120` through `170` are intentionally no longer stage directories. Recreate each remaining topic as a stage only when it has an implementation plan, deploy and validate scripts if needed, GitOps ownership where applicable, and validation evidence.

  Deferred scope to revisit:

  - **Stage 120: Skills - Reusable Quality Gates** — Demonstrate a near miss, capture the review procedure, and turn it into reusable skill candidates such as `review-enterprise-readiness`, README/API alignment, dependency review, model-boundary review, and PR summary preparation.
  - **Stage 130: Agents - Agentic Engineering With OpenCode** — Introduce OpenCode only after specs and skills exist. Preserve scoped agent roles, explicit tool permissions, human approval points, and the first bounded feature candidate: `POST /api/inventory/{itemId}/reservations`.
  - **Stage 140: Golden Path Quarkus Service** — Build or seed a demo-owned `coolstore-inventory-service` with Red Hat build of Quarkus `3.27.x`, Java 21, tests, health, PostgreSQL configuration, app-local GitOps, and documentation. Do not claim a full Coolstore monolith conversion.
  - **Stage 150: Governed Pipeline And Deployment** — Add a Pipelines-as-Code first slice for `coolstore-inventory-service`: PR trigger, `./mvnw -B test package`, Buildah image build, push to the OpenShift internal registry, app-local Kustomize under `gitops/base` and `gitops/overlays/dev`, and no direct deployment in the first slice.
  - **Stage 155: Red Hat Trusted Software Supply Chain** — Define the minimum evidence bundle before implementation: SBOM, VEX posture, signature, provenance, scan result, registry location, policy decision, and rollback evidence. Start with the service image before adding MCP server, skill, model, or agent artifacts.
  - **Stage 160: Modernization At Scale With MTA And Developer Lightspeed** — Use `rhpds/mca-coolstore` as the likely brownfield source, review MTA findings, treat Developer Lightspeed output as suggested diffs, and decide whether custom-rule generation uses Scribe MCP, RAG-backed standards lookup, or a local reviewed skill.
  - **Stage 170: Agent Mesh Modernization Pattern** — Keep this as an architecture horizon until there is implementation evidence. Revisit after local stages can exchange evidence between modernization, testing, documentation, security, delivery, AgentOps, and supply-chain harnesses.

  Recreate the detailed supporting material from git history only when the exact implementation slice is selected. Do not add these topics back to `flows/default.yaml` until they have executable artifacts and a validation path.

## Known Limitations

- [ ] **GPUaaS dashboard metric names require live confirmation** — Stage 020 adds a dashboard with common DCGM and Kueue Prometheus metric names. Validation warns rather than fails when those metrics differ or are unavailable, because Red Hat build of Kueue metric names and scraping behavior can vary by operator version.

- [ ] **Full llm-d autoscaling and distributed inference topology not implemented** — Stage 030 uses the Red Hat OpenShift AI llm-d `LLMInferenceService` path with vLLM, scheduler enablement, single-GPU-per-replica deployment metadata, Kueue admission, LeaderWorkerSet prerequisites, and vLLM metric aliases. It does not yet deploy Workload Variant Autoscaler configuration, multi-node serving, or disaggregated prefill/decode workers because the disposable demo currently has two NVIDIA L4 GPUs and the installed `LLMInferenceService` `v1alpha1` CRD does not expose `spec.scaling`.

- [ ] **Single-endpoint body-based multi-model routing not implemented** — The Red Hat Developer multi-LLM MaaS article demonstrates agentgateway, Gateway API Inference Extension `InferencePool`, endpoint picker pods, and body-based routing on the OpenAI `model` field. This demo currently uses MaaS-published model-specific governed paths and focuses on policy, telemetry, vLLM runtime metrics, and repeatable GuideLLM comparison. Add the agentgateway/GAIE pattern only if it becomes important to the demo storyline and aligns with the Red Hat OpenShift AI support posture for the target release.

- [ ] **ExternalModel name must match provider model name** — The payload-processing BBR plugin validates that `ExternalModel.spec.targetModel` matches the model name in the request body. Since LlamaStack sends the MaaS model name (the ExternalModel resource name), the ExternalModel must be named with the exact provider model name (e.g., `gpt-4o`, not `openai-gpt-4o`). Tracked upstream: [opendatahub-io/models-as-a-service#684](https://github.com/opendatahub-io/models-as-a-service/issues/684).

- [ ] **Gen AI Playground uses one MaaS request token per Playground call path** — The dashboard BFF requests a MaaS token and passes it to Llama Stack as request provider data. Llama Stack `remote::vllm` providers prefer that per-request `vllm_api_token` over provider-specific environment tokens. Keep models that appear together in one Playground under one consumer subscription, or local/external split subscriptions can produce HTTP 403 errors for models not covered by the selected token.

- [ ] **AI asset endpoints dropdown shows workspace namespaces** — The GenAI Studio AI asset endpoints project dropdown lists all namespaces where the user has any RBAC (including Dev Spaces workspace namespaces). The Projects page correctly filters by `opendatahub.io/dashboard: "true"`. This is a dashboard UI inconsistency.

- [ ] **Upstream `/v1/responses` support in BBR plugin** — The ODH BBR plugin ([opendatahub-io/ai-gateway-payload-processing](https://github.com/opendatahub-io/ai-gateway-payload-processing)) only supports `/chat/completions`. The upstream [Envoy AI Gateway](https://aigateway.envoyproxy.io/docs/capabilities/llm-integrations/supported-endpoints) supports `/v1/responses` natively. Models requiring `/v1/responses` (e.g., GPT-5 Codex) cannot be served through the standard MaaS pipeline until the ODH fork adds native support. See the Completed section for the proven routing workaround.

## Planned

- [ ] **GPUaaS metrics validation pass** — Confirm the final Prometheus metric names and proxy query path for the GPUaaS dashboard. Stage 020 currently validates dashboard resources and warns on raw metric query failures.
- [ ] **Red Hat UDI-based AI tools image** — Build and publish a Red Hat OpenShift Dev Spaces UDI-derived `ai-tools` image with OpenCode, Kilo Code support tooling, OpenShift CLI tooling, Java 21 as the default Maven runtime, and demo-required MCP/client utilities. Replace the current digest-pinned `quay.io/che-incubator/cli-ai-tools` workspace image once the UDI-based image is built, scanned, documented, and validated in fresh Dev Spaces workspaces. Until then, Stage 060 configures Java 21 during workspace startup so the Quarkus prompt does not carry Java-selection workaround commands.
- [ ] **Cline release watch (SDK file config)** — Cline 4.0.8 keeps provider config in VS Code `globalState`, not in a headlessly provisionable file. If a future Cline release adds SDK-level file-based configuration, re-evaluate for Dev Spaces. Until then, Kilo Code 7.4.7 is the current IDE assistant.
- [ ] **`developer-hub-models` subscription activation** — the `developer-hub-models` MaaS subscription is reserved with rhods-admins/kube:admin ownership. Activate and wire it when the RHDH Developer Lightspeed integration lands in Stage 050.
- [ ] **Legacy eval/guardrails subscription owners** — the `model-evaluation` and `ai-safety-guardrails` subscriptions currently include `kube:admin` as an owner. Scope owner identity after checking which identity the eval and guardrails beats actually run as.
- [ ] **External coolstore repo `.continue` template cleanup** — the external `coolstore-inventory-service` repo no longer carries `.opencode` (cleaned up). Remaining `.continue` template files in the golden parasol overlay are stale and should be removed.
- [ ] **OpenShift MCP — scoped RBAC per persona** — The OpenShift MCP ServiceAccount currently has cluster-wide `view` ClusterRole. Explore namespace-scoped RoleBindings.
- [x] **Red Hat-aligned observability path** — Active GitOps installs the Red Hat observability prerequisites and configures the product MaaS observability path instead of the historical community Grafana add-on.
- [ ] **Multi-cluster support** — Parameterize cluster-specific values via overlay.

## Validated (2026-05-01 and 2026-05-02)

- [x] **MaaS API — local and external model records listed** — `/maas-api/v1/models` returns `qwen3-6-35b-a3b`, `nemotron-3-nano-30b-a3b`, `gpt-4o`, and `gpt-4o-mini` as registered MaaS model records. Current 3.4 validation expects the operator-owned `registry.redhat.io/rhoai/odh-maas-api-rhel9` deployment with PostgreSQL backend.
- [x] **API key generation** — `sk-oai-*` format keys are generated through the product `/maas-api/v1/api-keys` path.
- [x] **Local model inference** — Both GPU models responded through the private model serving and MaaS validation paths in the current demo environment.
- [x] **External model registration and credential-gated inference** — `gpt-4o` and `gpt-4o-mini` are registered as governed external model records. External inference remains credential-gated. The provider credential Secret now follows the RHOAI 3.4 documentation path in `redhat-ods-applications/openai-api-key`.
- [x] **MaaSAuthPolicy + MaaSSubscription** — CRDs in `models-as-a-service` namespace, both `Active`. Per-route AuthPolicies and TokenRateLimitPolicies auto-created by the controller for all 4 models.
- [x] **Continue and OpenCode configuration** — Developer workspace configuration is generated with MaaS endpoint and `sk-oai-*` API key auth. Current live validation covered local model access; external model execution still requires an approved provider key.
- [x] **Stage 020 GPUaaS foundation** — Live validation on 2026-05-02 confirmed Red Hat build of Kueue, OpenShift AI Kueue integration, queue-based NVIDIA L4 hardware profiles, ResourceFlavor, ClusterQueue, LocalQueue, KEDA readiness, GPU MachineSet readiness, GPU node labels/taints, allocatable GPUs, NVIDIA ClusterPolicy readiness, and GPUaaS dashboard ConfigMap. The OpenShift 4.20 catalog used `stable-v1.3` for Red Hat build of Kueue.
- [x] **Kueue `Workload` creation for `LLMInferenceService`** — Stage 030 live validation on 2026-05-02 observed two Kueue `Workload` objects for the private model-serving `LLMInferenceService` pods, both admitted through `private-model-serving-gpu`.

## Completed

- [x] ~~**GPT-5-Codex /v1/responses routing (PROVEN, REMOVED)** — The BBR plugin only supports `/chat/completions`, so a dedicated routing path was created for GPT-5-Codex: separate HTTPRoute, EnvoyFilter (disables `ext_proc.bbr` + injects OpenAI credential), AuthPolicy (accepts OpenShift tokens instead of `sk-oai-*` keys), and TokenRateLimitPolicy. Worked with Continue and OpenCode but was not Playground-compatible (gen-ai-ui limitation). Removed from the demo to simplify to a clean 4-model architecture where all models use the same auth method (`sk-oai-*` keys) and API (`/v1/chat/completions`). The routing solution is preserved in git history and can be reapplied when the BBR plugin adds native `/v1/responses` support.~~
- [x] ~~**remote::openai LlamaStack provider (INVESTIGATED)** — Verified that manually patching the LlamaStack ConfigMap to use `remote::openai` instead of `remote::vllm` enables GPT-5 model responses via `/v1/responses`. However, the `gen-ai-ui` overwrites the ConfigMap on Playground recreation. Investigation preserved in git history.~~
- [x] ~~**Automated MaaS API validation** — implemented in stage validation scripts.~~
- [x] ~~**Devfile-based Continue auto-configuration** — Created `adnan-drina/coolstore-inventory-service` repo with `devfile.yaml` that auto-copies Continue config via postStart.~~
- [x] ~~**OpenCode CLI in Dev Spaces** — Installed via postStart in DevWorkspace.~~
- [x] ~~**ExternalModel support on the older workaround path** — Deployed upstream `maas-controller` alongside Red Hat OpenShift AI 3.3 operator. 2 OpenAI models (gpt-4o, gpt-4o-mini) registered as `ExternalModel` CRDs. Historical context only; not the current RHOAI 3.4 target architecture.~~
- [x] ~~**GitOps-ify upstream maas-controller** — Upstream CRDs, RBAC, controller, PostgreSQL, and MaaS CRs lived under `gitops/stages/040-governed-models-as-a-service/base/` during the older workaround period. Historical context only.~~
- [x] ~~**Red Hat OpenShift AI 3.4 EA2 evaluation** — Tested operator-native MaaS. Found that the EA2 `maas-api` binary did not implement model discovery from Kubernetes resources. Historical context only; do not use this EA2 result as a current 3.4 GA design decision.~~
- [x] ~~**Red Hat Developer Hub catalog URL follows GitOps revision** — Stage 050 now derives `RHDH_CATALOG_URL` from the live Argo CD Application `repoURL` and `targetRevision`, avoiding hard-coded `main` branch catalog references.~~


## Post-migration documentation rewrite

- [ ] **Rewrite OPERATIONS.md and TROUBLESHOOTING.md per-stage sections for the migrated 010-040 foundation** — the current sections describe the pre-migration implementation. Rewrite with live evidence from the first fresh-environment deployment of the migrated stages. Carry over rhoai3-demo known-issue entries (COO 1.4 pin rationale, MaaS quirks) where they apply.
## Stage 060 demo reset enhancements

- [ ] **`reset-coolstore-demo --prune-quay`** — optional flag to delete per-SHA demo image tags accumulated in quay.io/rhoai3-coding-demo/coolstore-inventory-service (cosmetic; requires quay robot with delete permission).
- [ ] **Reset stale-golden guard** — the script rewinds to whatever `golden` points at with no sanity check (2026-07-15: a reset ran against a stale golden and silently dropped the jacoco fix until re-run). Add a `--golden <sha>` override and a warning when `golden` differs from the last blessed baseline.

## Items from the 2026-07-15 stage 060 dry-run

- [ ] **Pipeline re-rollout stage** — `app-push` republishes `:latest` but nothing rolls the dev Deployment; the guide documents a manual `oc rollout restart`. Add a final pipeline task (workshop parity: "Re-rollout app") with the pipeline SA granted deployment restart in `coolstore-dev`.
- [ ] **Dev Spaces git-credentials Secret** — fresh workspaces get git identity (init script) but no push credentials; developers are prompted for a GitHub PAT at guide step 8. Provision a `controller.devfile.io/git-credential` Secret in `wksp-*` namespaces so Commit & Push works out of the box.
- [ ] **Kilo codebase indexing wired to the governed embedder** — `granite-embedding-english-r2` serves `/v1/embeddings` through MaaS with a minted key in the workspace Secret; Kilo's indexing settings live under `kilo-code.new.indexing.*` VS Code settings (plus a secret-stored embedder key). Seed them from `init-ai-tools.sh`; prototype live in a workspace first.
- [ ] **Worker ephemeral disk resize to 200GiB** — three eviction incidents in two days (Prometheus TSDBs — fixed; modelcar transient pulls — structural; cached-image pressure evicting a mid-demo pipeline pod). MachineSet volume-size change with rolling node replacement.
- [ ] **RFE: kuadrant-operator PodMonitor churn** — the operator deletes/recreates `kuadrant-limitador-monitor` every ~10 min on resync, causing scrape gaps in the Usage dashboard (TROUBLESHOOTING has the log signature).
- [ ] **RFE: external-model token telemetry** — ExternalModel routes export no `model` label and no token-usage counters; external models are invisible in per-model consumption views (TROUBLESHOOTING has the diagnosis).
- [ ] **RFE/investigation: Argo CD repo-server stale render** — Synced-at-new-SHA with stale applied manifests, hit twice on 2026-07-15; recipe recorded, root cause unidentified.

## Stage 050 Phase 5 items (deferred from the restructure plan, 2026-07-10)

- [ ] **Tekton Chains signed provenance** — enable Tekton Chains on the stage 050 shared `app-platform-push` pipeline so every golden-path build gets SLSA provenance and sigstore signatures via the already-installed Trusted Artifact Signer stack (Securesign instance required first). Restores the "trusted delivery" claim materially; demo beat: `cosign verify-attestation` on a pipeline-built image.
- [ ] **Developer Lightspeed for RHDH overlay** — `overlays/lightspeed` for stage 050: Lightspeed + MCP dynamic plugins, LCS config, and the LCS↔MaaS protocol verification (LCS `llama_stack.url` likely requires a llama-stack API, not OpenAI-compatible; if so, ship a llama-stack Deployment fronting MaaS as a protocol adapter — MaaS stays the only model access point). Blocked on live verification.
- [ ] **Standalone platform RHBK (realm `platform`)** — replace the transitional RHDH↔MTA-Keycloak brokering with a platform-owned RHBK in stage 050 `identity/`; unblocks the `overlays/slim` variant (platform without MigIQ). Needs live validation of realm/client/OAuth wiring before it lands in GitOps.

## Stage 050 trusted-delivery implementation phase

- [ ] **Stage 050 implementation phase — Trusted Software Factory pattern** — base setup exists (stage dirs, Pipelines + RHTAS operators via GitOps). Remaining: anchor: [Trusted software factory: Building trust in the agentic AI era](https://developers.redhat.com/articles/2026/05/13/trusted-software-factory-building-trust-agentic-ai-era). Story: after Stage 080's autonomous agents produce code, the factory proves what was built and how — SLSA provenance and sigstore signatures/attestation for AI-generated changes, SBOMs, Trusted Profile Analyzer for vulnerability triage, Red Hat Trusted Software Supply Chain (Konflux-based) pipelines, hardened images and trusted libraries. The article is strategy-level with no reference implementation, so before implementing: identify deployable components for a demo sandbox (RHTSSC availability, TAS, TPA operators), a concrete pipeline for the Stage 080 migrated app, and a validation path.

## Stage 080 agentic migration provenance

- [ ] **MigIQ is experimental and Claude-Code-first** — the Stage 080 multi-agent migration follows the MigIQ pattern (github.com/sshaaf/migIQ, npm @sshaaf/migiq). Pin the npm version in workspace provisioning, document its experimental status in the stage README, and run an OpenCode-compatibility proving run inside Dev Spaces before the stage README promises OpenCode support. Models route through MaaS (qwen3-6-35b-a3b executor, nemotron long-context planning) so agent token usage is visible on the Stage 040 usage dashboards.

## Showroom-derived topics (adv-app-platform-demo-showroom mapping)

- [ ] **Stage 050 implementation recipe** — adopt showroom modules 5-6 as the reference: Tekton pipeline for the Stage 080 migrated app with SonarQube gate, Tekton Chains SLSA attestation, TAS signing, SBOM generation, TPA SBOM/vulnerability management.
- [ ] **Stage 050 self-service template** — RHDH software template scaffolding a component + governed workspace (showroom module 4 pattern) and topology wrap-up view (module 6).
- [ ] **Stage 070 demo beat** — pipeline/quality-gate fails, skills-guided agent fixes it (showroom module 2 loop adapted to OpenCode + skills).
- [ ] **Stage 060 workspace addition** — Dependency Analytics extension in the editor policy (showroom module 5 part 1).
- [ ] **AI-enhanced application development (future stage candidate)** — Quarkus + LangChain4j service consuming MaaS endpoints on the same golden path (showroom module 7 pattern; introduces the service-identity MaaSSubscription persona).

- [ ] **Stage 080 RHDH entry point (deferred)** — reintroduce a golden-path template (self-service per-run copy of `migiq-spring-boot-sample` + catalog registration) once the MigIQ migration flow is settled; until then MTA is the stage entry point (2026-07-13 decision).
