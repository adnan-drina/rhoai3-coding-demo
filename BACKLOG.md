# Backlog

## RHOAI 3.4 upgrade watch items

As of 2026-05-18, the public Red Hat OpenShift AI 3.4 documentation describes the target MaaS model as subscription-based governance with API keys, group assignment, token limits, authorization policy, and usage tracking. The same release documentation still marks several MaaS-related surfaces as Technology Preview or Developer Preview. Do not remove demo workarounds automatically, because adjacent pieces still have narrower support scope or live-demo gaps: AI Available Assets with MaaS is Developer Preview, vLLM MaaS and MaaS observability are Technology Preview, external provider routing must keep its provider trust boundary explicit, and the current demo still carries compatibility glue for Playground token generation, dashboard user-token handling, and disposable observability.

Before upgrading this demo, verify the target RHOAI build against the following MaaS capability boundaries:

- [ ] **Governed model access support scope** — Confirm whether governed model access, dashboard discovery, subscription assignment, API-key access, quota enforcement, rate limits, token limits, and usage visibility are GA, Technology Preview, Developer Preview, or otherwise scoped for the target release.
- [ ] **`MaaSSubscription` and `MaaSAuthPolicy` support** — Confirm whether these CRDs are product-supported in the target RHOAI build and whether they replace this repo's manual `RateLimitPolicy`, `TokenRateLimitPolicy`, `TelemetryPolicy`, and per-model RBAC resources.
- [ ] **`maas-api` API-key lifecycle** — Confirm whether product `maas-api` supports subscription-bound key minting, binding, rotation, and revocation without the upstream image override or Playground tokens bridge.
- [ ] **MaaS observability path** — Confirm whether MaaS usage and health observability is product-supported or remains Technology Preview/demo glue, and whether this repo should replace community Grafana with a Red Hat-supported observability path.
- [ ] **External model and payload processing support** — Confirm whether `ExternalModel`, payload/request processing, provider credential injection, and external inference through the same MaaS subscription and policy surface are product-supported enough to remove the upstream `maas-controller` coexistence path.
- [ ] **3.3 tier model removal** — Confirm whether the target RHOAI 3.4 build can remove tier annotations, the `tier-to-group-mapping` ConfigMap, tier-named groups, tier ServiceAccount RBAC, and tier-shaped dashboard metrics in favor of subscription/group vocabulary and product-managed policy.

## Workarounds (review when supported RHOAI 3.4 paths cover them natively)

The following items use manual configuration or post-deploy patches because the demo validates MaaS, dashboard, gateway, and observability behavior across several product surfaces. Review each item against the exact Red Hat OpenShift AI 3.4 build in the target cluster and remove it only after the replacement behavior has been validated in this demo.

- [ ] **Gateway AuthPolicy patch for user OAuth tokens** — The operator-managed gateway policy path accepts ServiceAccount tokens (`maas-default-gateway-sa` audience). The dashboard's `gen-ai-ui` forwards user OAuth tokens. The `configure-kuadrant` Job patches `gateway-default-auth` to add `user-tokens` authentication and patches `maas-api-auth-policy` to add empty `authorization: {}` so `/maas-api/*` management endpoints do not inherit the gateway-level access check.
  **Revert:** A supported MaaS operator path should configure AuthPolicies that accept dashboard-forwarded tokens natively.

- [ ] **Authorino SSL env vars** (`jobs/configure-kuadrant.yaml`) — Job sets `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` on Authorino deployment so it trusts OpenShift's internal service-ca.
  **Revert:** Verify if the supported operator path handles this natively.

- [ ] **Gateway hostname patch** (`jobs/patch-gateway-hostname.yaml`) — Job patches MaaS Gateway with cluster-specific hostname and TLS cert name.
  **Revert:** The supported operator path may parameterize the Gateway hostname.

- [ ] **Tier-to-group-mapping ConfigMap in `redhat-ods-applications`** — This is 3.3 tier-model compatibility debt. The Red Hat OpenShift AI validating webhook has required this ConfigMap when `LLMInferenceService` uses the `alpha.maas.opendatahub.io/tiers` annotation. The operator's `maas-api` does not create it in `redhat-ods-applications`; we deploy it at sync wave 9.
  **Revert:** In the RHOAI 3.4 target model, subscriptions replace tiers and are managed through custom resources instead of ConfigMaps. Remove this ConfigMap and the tier annotations after live validation confirms model apply, model discovery, and MaaS subscription access still pass.

- [ ] **Manual RateLimitPolicy, TokenRateLimitPolicy, TelemetryPolicy** — Created in `governance/` to make the demo gateway, token-limit, and telemetry behavior explicit and reproducible.
  **Revert:** The supported operator path may manage these via `MaaSSubscription` CRDs.

- [ ] **Manual per-model RBAC** (`models/rbac.yaml`) — Roles granting tier ServiceAccounts access to `LLMInferenceService`. This is 3.3 tier-model compatibility debt until the 3.4 controller-generated access path is proven.
  **Revert:** The supported operator path may manage RBAC via `MaaSAuthPolicy` CRDs.

- [ ] **Manual tier groups** (`governance/maas-groups.yaml`) — Groups `tier-free-users`, `tier-premium-users`, `tier-enterprise-users` with demo users. In RHOAI 3.4, these should become subscription consumer groups if the live schema and controller behavior support the rename cleanly.
  **Revert:** Verify the supported subscription/group path and then replace tier vocabulary.

- [ ] **Model Registry NetworkPolicy** (`model-registry/registry/dashboard-networkpolicy.yaml`) — The operator's default NetworkPolicy only allows same-namespace access. We add a policy allowing `redhat-ods-applications` to reach the registry on port 8080.
  **Revert:** The supported operator path should create proper NetworkPolicies for the dashboard.

## Retired pre-3.4 workarounds and remaining compatibility glue

The upstream `maas-controller` coexistence path and `maas-api` image override were used before the 3.4 operator-owned MaaS path was available in the demo. Keep these as historical context and do not reintroduce them unless a live 3.4 product gap is proven and documented.

- [x] ~~**maas-api image pinning** (`jobs/patch-maas-api-storage.yaml`) — The older workaround pinned the tenant-managed deployment to `quay.io/opendatahub/maas-api:latest` for model discovery. The 3.4 demo now expects operator-owned `registry.redhat.io/rhoai/odh-maas-api-rhel9` and `registry.redhat.io/rhoai/odh-maas-controller-rhel9` deployments.~~
  **Validation:** Stage 040 validation must continue to assert that `maas-api` uses a `registry.redhat.io/rhoai/odh-maas-api-rhel9` image.

- [ ] **`models-as-a-service` namespace** — The current 3.4 demo stores `MaaSAuthPolicy` and `MaaSSubscription` CRs in the `models-as-a-service` namespace. Keep this namespace until the operator-owned layout and validation rules are confirmed for the exact target build.

- [ ] **Dashboard Route** — The Red Hat OpenShift AI dashboard is accessed via the `rh-ai.*` hostname through the `data-science-gateway`. The operator's default `rhods-dashboard` Route redirects to the gateway.

- [ ] **ExternalModel credential Secret label** — Secrets referenced by `ExternalModel.spec.credentialRef` must have the label `inference.networking.k8s.io/bbr-managed=true` for the payload-processing (IPP) plugin to discover them.

- [ ] **Tokens-bridge** (`tokens-bridge/deployment.yaml`) — Translates `/maas-api/v1/tokens` to `/v1/api-keys` for Playground and older dashboard call paths. The bridge requests `demo-models-subscription` explicitly so the Gen AI Playground receives one request token that covers the private and approved external MaaS models selected together in the same Playground. Dashboard bundles have expected the generated credential in different response shapes (`key`, `token`, `data.key`, or `data.token`), so the bridge returns all four names with the same redacted-only logging. Do not route `/gen-ai/api/v1/maas/tokens` directly to this bridge; that bypasses the dashboard Gen AI proxy and loses the user headers needed by `maas-api`.

## 3.3 tier-model cleanup candidates

These items are not permanent RHOAI 3.4 design decisions. They remain in GitOps only until a live RHOAI 3.4 validation pass proves the subscription-based product path covers the same behavior.

- [ ] Remove `alpha.maas.opendatahub.io/tiers` annotations from local `LLMInferenceService` manifests after MaaS model discovery works without them.
- [ ] Remove `tier-to-group-mapping` after the webhook no longer requires tier data for model publication.
- [ ] Replace `tier-free-users`, `tier-premium-users`, and `tier-enterprise-users` with subscription consumer groups or another product-aligned group naming model.
- [ ] Remove manual tier ServiceAccount RBAC if `MaaSAuthPolicy` and controller-created resources grant the required access.
- [ ] Replace tier-shaped Grafana panels and `authorized_hits{tier=...}` compatibility metrics with subscription-level MaaS observability.
- [ ] Remove historical upstream `maas-controller` and `maas-api` override language from active stage narratives. Keep it only as historical context or in Git history.

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
- [ ] **Red Hat-aligned observability path** — The current Grafana dashboard was copied from a Red Hat quickstart repository and uses the community Grafana Operator. Prefer a Red Hat-supported monitoring or observability path for long-lived environments.
- [ ] **Grafana dashboard screenshots** — Add screenshots to Stage 040 README while the community Grafana demo add-on remains in use.
- [ ] **Multi-cluster support** — Parameterize cluster-specific values via overlay.

## Validated (2026-05-01 and 2026-05-02)

- [x] **MaaS API — local and external model records listed** — `/maas-api/v1/models` returns `gpt-oss-20b`, `nemotron-3-nano-30b-a3b`, `gpt-4o`, and `gpt-4o-mini` as registered MaaS model records. Current 3.4 validation expects the operator-owned `registry.redhat.io/rhoai/odh-maas-api-rhel9` deployment with PostgreSQL backend.
- [x] **API key generation** — `sk-oai-*` format keys via `/maas-api/v1/api-keys`. Playground uses `/maas-api/v1/tokens` through the tokens-bridge proxy.
- [x] **Local model inference** — Both GPU models responded through the private model serving and MaaS validation paths in the current demo environment.
- [x] **External model registration and credential-gated inference** — `gpt-4o` and `gpt-4o-mini` are registered as governed external model records. External inference remains credential-gated, but live validation on 2026-05-02 confirmed that an approved `OPENAI_API_KEY` provisioned into `maas/openai-api-key` can complete a `gpt-4o-mini` call through MaaS. The `payload-processing` BBR plugin injects provider credentials from the `openai-api-key` Secret when an approved key is supplied.
- [x] **MaaSAuthPolicy + MaaSSubscription** — CRDs in `models-as-a-service` namespace, both `Active`. Per-route AuthPolicies and TokenRateLimitPolicies auto-created by the controller for all 4 models. RHOAI 3.4 cleanup still needs to confirm whether these replace the remaining manual tier-model resources.
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
