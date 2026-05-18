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

- [ ] **Gateway AuthPolicy patch for user OAuth tokens** — The operator-managed gateway policy path accepts ServiceAccount tokens (`maas-default-gateway-sa` audience). The dashboard's `gen-ai-ui` forwards user OAuth tokens. The `configure-kuadrant` Job patches `gateway-default-auth` to add `user-tokens` authentication and patches `maas-api-auth-policy` to add empty `authorization: {}` so `/maas-api/*` management endpoints do not inherit the gateway-level access check.
  **Revert:** A supported MaaS operator path should configure AuthPolicies that accept dashboard-forwarded tokens natively.

- [ ] **Authorino SSL env vars** (`jobs/configure-kuadrant.yaml`) — Job sets `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` on Authorino deployment so it trusts OpenShift's internal service-ca.
  **Revert:** Verify if the supported operator path handles this natively.

- [ ] **Gateway hostname patch** (`jobs/patch-gateway-hostname.yaml`) — Job patches MaaS Gateway with cluster-specific hostname and TLS cert name.
  **Revert:** The supported operator path may parameterize the Gateway hostname.

- [ ] **Model Registry NetworkPolicy** (`model-registry/registry/dashboard-networkpolicy.yaml`) — The operator's default NetworkPolicy only allows same-namespace access. We add a policy allowing `redhat-ods-applications` to reach the registry on port 8080.
  **Revert:** The supported operator path should create proper NetworkPolicies for the dashboard.

## Retired pre-3.4 workarounds and remaining compatibility glue

The upstream `maas-controller` coexistence path and `maas-api` image override were used before the 3.4 operator-owned MaaS path was available in the demo. Keep these as historical context and do not reintroduce them unless a live 3.4 product gap is proven and documented.

- [x] ~~**maas-api image pinning** (`jobs/patch-maas-api-storage.yaml`) — The older workaround pinned the tenant-managed deployment to `quay.io/opendatahub/maas-api:latest` for model discovery. The 3.4 demo now expects operator-owned `registry.redhat.io/rhoai/odh-maas-api-rhel9` and `registry.redhat.io/rhoai/odh-maas-controller-rhel9` deployments.~~
  **Validation:** Stage 040 validation must continue to assert that `maas-api` uses a `registry.redhat.io/rhoai/odh-maas-api-rhel9` image.

- [ ] **`models-as-a-service` namespace** — The current 3.4 demo stores `MaaSAuthPolicy` and `MaaSSubscription` CRs in the `models-as-a-service` namespace. Keep this namespace until the operator-owned layout and validation rules are confirmed for the exact target build.

- [ ] **Dashboard Route** — The Red Hat OpenShift AI dashboard is accessed via the `rh-ai.*` hostname through the `data-science-gateway`. The operator's default `rhods-dashboard` Route redirects to the gateway.

- [ ] **ExternalModel credential Secret label** — Secrets referenced by `ExternalModel.spec.credentialRef` must have the label `inference.networking.k8s.io/bbr-managed=true` for the payload-processing (IPP) plugin to discover them.

- [x] ~~**Tokens-bridge** (`tokens-bridge/deployment.yaml`) — The compatibility bridge translated `/maas-api/v1/tokens` to `/v1/api-keys` for older Playground/dashboard call paths. The active GitOps path now relies on the product MaaS API key path and no longer deploys this bridge.~~

- [ ] **RHOAI monitoring service-ca Secret sync** — The generated RHOAI 3.4 `MonitoringStack` references `Secret/prometheus-web-tls-ca`, while the OpenShift service-ca injection path creates the CA bundle as `ConfigMap/prometheus-web-tls-ca`. Stage 010 syncs that bundle into the expected Secret at deploy time without committing certificate material.
  **Revert:** Remove the sync hook if a later RHOAI build creates the Secret natively or changes the generated `MonitoringStack` to reference the ConfigMap.

## 3.3 tier-model cleanup status

- [x] Removed `alpha.maas.opendatahub.io/tiers` annotations from local `LLMInferenceService` manifests.
- [x] Removed `tier-to-group-mapping` from the active GitOps path.
- [x] Replaced `tier-free-users`, `tier-premium-users`, and `tier-enterprise-users` with existing `rhoai-users` and `rhoai-admins` subscription consumer groups.
- [x] Removed manual tier ServiceAccount RBAC from the active GitOps path.
- [x] Removed manual tier-shaped gateway `RateLimitPolicy`, `TokenRateLimitPolicy`, `TelemetryPolicy`, and the community Grafana dashboard from the active GitOps path.
- [x] Preserved historical upstream `maas-controller` and `maas-api` override language only as completed historical context.

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
- [ ] **OpenShift MCP — scoped RBAC per persona** — The OpenShift MCP ServiceAccount currently has cluster-wide `view` ClusterRole. Explore namespace-scoped RoleBindings.
- [x] **Red Hat-aligned observability path** — Active GitOps installs the Red Hat observability prerequisites and configures the product MaaS observability path instead of the historical community Grafana add-on.
- [ ] **Multi-cluster support** — Parameterize cluster-specific values via overlay.

## Validated (2026-05-01 and 2026-05-02)

- [x] **MaaS API — local and external model records listed** — `/maas-api/v1/models` returns `gpt-oss-20b`, `nemotron-3-nano-30b-a3b`, `gpt-4o`, and `gpt-4o-mini` as registered MaaS model records. Current 3.4 validation expects the operator-owned `registry.redhat.io/rhoai/odh-maas-api-rhel9` deployment with PostgreSQL backend.
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
- [x] ~~**Red Hat Developer Hub catalog URL follows GitOps revision** — Stage 090 now derives `RHDH_CATALOG_URL` from the live Argo CD Application `repoURL` and `targetRevision`, avoiding hard-coded `main` branch catalog references.~~
