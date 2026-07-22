# Stage 040: Governed Models-as-a-Service Plan

## Intent

- Stage identifier: `220`
- Stage family: `2xx Production GenAI and Private Data`
- Stage slug: `040-governed-models-as-a-service`
- Concept introduced: Governed model access through Red Hat OpenShift AI Models-as-a-Service.
- Target audience: Platform engineer, solution architect, AI governance owner, and application developer.
- Enterprise value: Turns validated model endpoints into governed shared services with subscriptions, authorization policies, API keys, quotas, usage tracking, and clear separation between internal GPU-backed models and external provider models.
- Depends on: `010-openshift-ai-platform-foundation`, `020-gpu-infrastructure-private-ai`, and `030-private-model-serving`.
- New components planned: MaaS enablement on the shared `DataScienceCluster`, Red Hat Connectivity Link and Kuadrant prerequisites, MaaS Gateway API resources, Authorino TLS setup, PostgreSQL-backed API-key storage, `Tenant`, `MaaSModelRef`, `MaaSSubscription`, `MaaSAuthPolicy`, `ExternalModel`, a MaaS-published Nemotron endpoint, and a read-only OpenShift MCP server registered for Gen AI Playground discovery.
- Phase-one implementation: cert-manager preflight validation, GitOps-managed RHCL, Kuadrant, Authorino TLS, `maas-default-gateway`, in-cluster PostgreSQL 16 demo database, `maas-db-config`, dashboard flags, DSC MaaS/Llama Stack enablement, and `Tenant`.
- Phase-two implementation: schema-validated external OpenAI `gpt-4o-mini` provider routing through a matching `gpt-4o-mini` `ExternalModel`, `MaaSModelRef`, `MaaSSubscription`, `MaaSAuthPolicy`, and MaaS namespace admin RoleBinding for `rhods-admins`. Live rollout requires a local provider key Secret; do not use placeholders.
- Local model implementation: schema-validated Nemotron `LLMInferenceService` and `MaaSModelRef` in `models-as-a-service`, with a MaaS namespace `LocalQueue` and a deploy-time cleanup guard that removes any stale direct Nemotron deployment from `demo-sandbox`.
- Namespace decision: MaaS model references must point at the namespace that contains the underlying backend. For the governed private model path, this project intentionally makes `models-as-a-service` the backend namespace for Nemotron rather than keeping the shared backend in the user-facing `demo-sandbox` project.
- Gateway TLS pattern: create stable `maas-gateway-tls` in `openshift-ingress` from the active OpenShift ingress certificate before applying `maas-default-gateway`; then patch listener hostnames to `maas.<apps-domain>`.
- External model planned: OpenAI `gpt-4o-mini` registered through the MaaS `ExternalModel` path with `gpt-4o-mini` as both the Kubernetes resource name and upstream provider model ID.
- Validation priority: deterministic API and CLI validation first, with the dashboard and Gen AI studio experience used as the audience-facing proof.
- User-facing experience: `ai-admin` administers MaaS; `ai-developer` does not get direct access to the `models-as-a-service` project and consumes models through Gen AI studio AI asset endpoints and MaaS API keys.
- Full experience scope: include MaaS subscriptions, authorization policies, API keys, governed local Nemotron, governed external OpenAI, Gen AI Playground consumption, read-only OpenShift MCP tool context, MaaS observability, and clear Technology Preview or Developer Preview labeling for preview features.
- Existing components reused: Stage 030 Nemotron vLLM configuration, Grafana/User Workload Monitoring, `demo-sandbox` as the consumer project, and Stage 020 GPU hardware profiles.

## Non-Goals

- Do not run a second GPU-heavy Nemotron backend alongside the direct Stage 210 endpoint on the single default GPU node. Stage 040 must remove stale direct dashboard-created Nemotron serving resources from `demo-sandbox` before reconciling the MaaS-owned `LLMInferenceService`.
- Do not commit OpenAI provider API keys, MaaS API keys, database passwords, or generated tokens.
- Do not claim billing-grade metering. MaaS usage data is for demo showback and capacity planning.
- Do not claim llm-d monitoring or MaaS observability as GA. Label Technology Preview and Developer Preview surfaces explicitly.
- Do not use external OpenAI models for workloads where provider-side processing is not allowed by the demo scenario.
- Do not hide the external-provider boundary. Prompts, context, and generated content for `gpt-4o-mini` leave the cluster and must be limited to approved demo workloads.
- Do not use external `gpt-4o-mini` as the primary OpenShift MCP demo path. Direct MaaS Chat Completions function calling works for the external model, and bounded Playground MCP calls can work, but broad MCP prompts can produce large tool schemas or tool outputs that hit external provider TPM limits.
- Do not give `ai-developer` administrative access to the MaaS project. The user-facing path is through OpenShift AI dashboard assets and MaaS-governed API consumption, not namespace administration.
- Serve the MaaS-published Nemotron backend with the working `131072` context window for Gen AI Playground MCP/tool context headroom, but keep MaaS subscription limits, output-token defaults, and user guidance conservative until Stage 030/220 measurements justify higher shared-service usage.
- Do not enable write-capable MCP tools in Stage 040. The OpenShift MCP server is for read-only context inspection only, with Secrets, ConfigMaps, and RBAC resources denied by configuration.

## Acceptance Criteria

- [x] README explains MaaS value, subscriptions, quotas, API keys, and internal/external model governance without runbook detail.
- [x] Official RHOAI 3.4 MaaS, llm-d, Gateway/API, and dashboard feature-flag sources are captured.
- [x] Red Hat quickstart and sibling-demo references are bounded as implementation examples, not product API authority.
- [x] Live CRD/schema checks are completed after MaaS prerequisites are installed.
- [x] MaaS prerequisites are installed and healthy through GitOps.
- [x] Stage 010 remains the base `DataScienceCluster` owner; Stage 040 patches only the MaaS and Llama Stack component fields through a GitOps hook.
- [x] Local Nemotron is published through a schema-verified MaaS model reference.
- [x] External OpenAI `gpt-4o-mini` GitOps resources are published through an `ExternalModel` backed by a real Kubernetes Secret or approved secret store.
- [x] Demo users have both `MaaSSubscription` quota and `MaaSAuthPolicy` gateway authorization before access is claimed.
- [x] Validation proves model listing, API-key creation, local Nemotron tool-calling inference, external OpenAI function calling, generated rate-limit policy enforcement, token usage, and forbidden access for an unauthenticated subject.
- [x] `ai-admin` can administer MaaS resources and policies; `ai-developer` can discover and consume allowed MaaS models without direct access to the MaaS administration namespace.
- [x] Gen AI Playground can use the MaaS-published local and external models through AI asset endpoints.
- [x] OpenShift MCP server is registered in Gen AI Playground discovery and is validated as read-only with denied sensitive resources.
- [ ] MaaS observability is enabled and validates subscription/request/token signals where the installed Technology Preview components expose them.

## Source Capture

| Purpose | Source | Skill | Notes |
|---------|--------|-------|-------|
| Product authority | [RHOAI 3.4 - Govern LLM access with Models-as-a-Service](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/govern_llm_access_with_models-as-a-service/index) | `rhoai-maas-governance` | MaaS prerequisites, `Tenant`, `MaaSModelRef`, `ExternalModel`, `MaaSSubscription`, `MaaSAuthPolicy`, API keys, observability, external OIDC, and troubleshooting. |
| Local model backend | [RHOAI 3.4 - Deploy models using Distributed Inference with llm-d](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/deploy_models_using_distributed_inference_with_llm-d/index) | `rhoai-distributed-inference-llmd` | `LLMInferenceService`, Gateway references, Connectivity Link, auth, scheduler, WVA, and flow control. Use only after schema verification. |
| Distributed-inference prerequisite | [OpenShift 4.20 - Leader Worker Set Operator](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/ai_workloads/leader-worker-set-operator) | `ocp-ai-workloads`, `rhoai-distributed-inference-llmd` | Required prerequisite for the RHOAI `LLMInferenceService` path. Official docs set channel `stable-v1.0`, installation namespace `openshift-lws-operator`, and cert-manager prerequisite. |
| Serving prerequisite | [RHOAI 3.4 - Configuring your model-serving platform](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/configuring_your_model-serving_platform/index) | `rhoai-model-serving-platform` | KServe and vLLM platform context below MaaS. |
| Stage 030 evidence | `030-private-model-serving/README.md` and benchmark results under `runs/stage-030-guidellm/` | `rhoai-model-management-monitoring` | Source for current Nemotron endpoint readiness and operating-envelope evidence. |
| Red Hat quickstart | [Red Hat AI quickstart - MaaS code assistant](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant) | `project-red-hat-doc-alignment-review`, `rhoai-maas-governance` | Narrative and architecture reference for Nemotron, MaaS, vLLM/llm-d, Grafana, and AWS `g6e.2xlarge`/L40S context. |
| Red Hat Developer article | `/Users/adrina/Sandbox/rh-brain/Red Hat Brain/wiki/sources/2026-06-12 - Model-as-a-Service How to Run Your Own Private AI API.md` | `project-red-hat-doc-alignment-review`, `project-documentation-authoring` | Narrative source for MaaS as a governed internal private AI API product with developer self-service, monitoring, quota, security, and shadow-AI reduction. |
| Red Hat Developer gateway example | [Centralized routing for external and self-hosted LLMs on OpenShift AI](https://developers.redhat.com/articles/2026/05/25/route-external-and-local-llms-models-as-a-service) | `rhoai-maas-governance`, `project-red-hat-doc-alignment-review` | Supporting example for a unified OpenAI-compatible gateway, external OpenAI `gpt-4o-mini`, and self-hosted model routing. The article uses LiteLLM; this stage uses the native RHOAI MaaS `ExternalModel` path from official docs. |
| OpenShift MCP product direction | [Red Hat - Model Context Protocol server for Red Hat OpenShift now available as Technology Preview](https://www.redhat.com/en/blog/model-context-protocol-server-red-hat-openshift-now-available-technology-preview) | `rhoai-gen-ai-playground`, `rhoai-llama-stack` | Source for using the Red Hat/OpenShift MCP server pattern and for preview-status safety framing. |
| OpenShift MCP implementation | [openshift/openshift-mcp-server](https://github.com/openshift/openshift-mcp-server) | `rhoai-gen-ai-playground`, `project-gitops-authoring` | Source for image, HTTP `/mcp` endpoint, Helm chart defaults, read-only configuration, denied-resource guidance, and ServiceAccount/RBAC posture. |
| Red Hat implementation reference | [rh-ai-quickstart/maas-code-assistant `feat/upgrade-to-rhoai-3.4`](https://github.com/rh-ai-quickstart/maas-code-assistant/tree/feat/upgrade-to-rhoai-3.4) | `rhoai-maas-governance`, `rhoai-distributed-inference-llmd` | Implementation pattern for `LLMInferenceService`, Gateway, tier/RBAC, vLLM args, Grafana, and the known-good `rhcl-operator.v1.3.4` pin. Must be revalidated against RHOAI 3.4 CRDs. |
| Sibling demo reference | `/Users/adrina/Sandbox/rhoai3-coding-demo/gitops/stages/030-private-model-serving/base/models/nemotron-3-nano-30b.yaml` | `rhoai-distributed-inference-llmd`, `rhoai-model-serving-platform` | Concrete Nemotron vLLM/tool-calling configuration to preserve where schema-compatible. |
| Sibling MaaS reference | `/Users/adrina/Sandbox/rhoai3-coding-demo/gitops/stages/040-governed-models-as-a-service/base/models-maas-crds/local-modelrefs.yaml` | `rhoai-maas-governance` | MaaS model-reference pattern; example only until active CRD schema is verified. |
| API stability | `.agents/skills/rhoai-api-tiers/references/api-tier-map.md` | `rhoai-api-tiers` | `llminferenceservices.serving.kserve.io/v1alpha1` is Tier 2 by exception; other alpha Gateway/preview surfaces must be labeled carefully. |
| External provider model | [OpenAI API - GPT-4o mini model](https://developers.openai.com/api/docs/models/gpt-4o-mini) | `rhoai-maas-governance` | Official OpenAI source for the selected external model ID, endpoint compatibility, modalities, and feature support. |
| External provider pricing | [OpenAI API - pricing](https://developers.openai.com/api/docs/pricing) | `rhoai-maas-governance` | Confirms `gpt-4o-mini` pricing for the external MaaS path. Recheck before demo delivery. |

## Current Schema Findings

Read-only schema discovery on `cluster-klvxt` on 2026-06-12:

| Resource | Current state | Planning impact |
|----------|---------------|-----------------|
| `llminferenceservices.serving.kserve.io` | Present; `v1alpha1` and `v1alpha2` served, `v1alpha2` storage. | Stage 040 targets the live storage version after official-doc and schema review. Do not copy older `v1alpha1` examples blindly. |
| `leaderworkersets.leaderworkerset.x-k8s.io` | Required by the RHOAI llm-d/`LLMInferenceService` prerequisite path. | Stage 040 installs the LeaderWorkerSet Operator through GitOps before creating the Nemotron `LLMInferenceService`. |
| `llminferenceserviceconfigs.serving.kserve.io` | Present as `serving.kserve.io/v1alpha2`. | Review only if Stage 040 needs custom config resources. |
| Gateway API `GatewayClass`, `Gateway`, `HTTPRoute` | Present as `gateway.networking.k8s.io/v1`; `maas-default-gateway` is live with `maas-gateway-tls` and `maas.apps.cluster-klvxt.klvxt.sandbox279.opentlc.com`. | Use the deploy wrapper to inject the environment hostname into the Argo CD Application before sync. Do not hide Gateway listener fields with `RespectIgnoreDifferences` when they must be repaired through GitOps. |
| `kuadrants.kuadrant.io` and `authorinos.operator.authorino.kuadrant.io` | Present; `Kuadrant` and `Authorino` are Ready. | Gateway policy prerequisites are healthy for model publication and subscription work. |
| RHCL `Subscription` | Stage 040 pins `rhcl-operator.v1.3.4` with `installPlanApproval: Manual`, ignores ArgoCD health for the Subscription because OLM reports `UpgradePending` when newer plans remain unapproved, and uses a GitOps approval job for only the pinned CSV. | Do not use automatic RHCL upgrades for MaaS until the RHOAI/RHCL/Gateway path validates end to end on the newer CSV. |
| MaaS CRDs | `Tenant`, `MaaSModelRef`, `MaaSSubscription`, `MaaSAuthPolicy`, and `ExternalModel` are present as `maas.opendatahub.io/v1alpha1` with `v1alpha1` as storage. | Use `maas.opendatahub.io/v1alpha1`; do not use `models.opendatahub.io` examples from documentation or quickstarts without conversion. |
| `MaaSModelRef.spec.modelRef` | Requires `kind` enum `LLMInferenceService` or `ExternalModel`, and `name`. | Create one model ref for the local Nemotron `LLMInferenceService` and one for the external OpenAI `ExternalModel` after backend resources are ready. |
| `ExternalModel.spec` | Requires `provider`, `endpoint`, `targetModel`, and `credentialRef.name`; the referenced Secret must contain data key `api-key`. | OpenAI provider credentials remain local Secret material; GitOps may reference the Secret name but must not commit the key. |
| `MaaSSubscription.spec` | Requires `owner`, `modelRefs[]`, and per-model `tokenRateLimits[]`; groups are objects with `name`; windows support `s`, `m`, and `h`; `priority` and `tokenMetadata` are available. | Initial policies should encode Stage 030 chat/RAG limits and showback metadata with `organizationId`, `costCenter`, and labels. |
| `MaaSAuthPolicy.spec` | Requires `subjects` and `modelRefs[]`; `meteringMetadata` supports `organizationId`, `costCenter`, and labels. | Access claims require both subscription quota and auth-policy authorization. |
| `Tenant.spec` | Supports `apiKeys.maxExpirationDays`, `gatewayRef`, `externalOIDC`, and telemetry with `captureModelUsage`, `captureOrganization`, `captureGroup`, and `captureUser`. | Keep `captureUser` a deliberate privacy decision; enable model-usage telemetry for demo showback, not billing-grade invoicing. |
| `llamastackdistributions.llamastack.io` | Present after MaaS/Llama Stack Operator enablement. | Gen AI Studio and Playground flows can be validated in the next phase. |
| `OdhDashboardConfig.spec.dashboardConfig.vLLMDeploymentOnMaaS` | Present in live schema; exact casing confirmed. | Use `vLLMDeploymentOnMaaS`, not `vLLMDeploymentOnMaas`. |

Observed `LLMInferenceService` `v1alpha2` fields include `spec.model.uri`, `spec.model.name`, `spec.router.gateway.refs[]`, `spec.router.route`, `spec.router.scheduler`, `spec.replicas`, `spec.worker`, `spec.prefill`, `spec.parallelism`, `spec.scaling`, and `spec.storageInitializer`. Use `oc explain` again immediately before writing GitOps because the examples and active CRD version differ from some older published snippets.

## API Tier And Support Posture

| Area | Current posture | Stage 040 handling |
|------|-----------------|--------------------|
| `LLMInferenceService` | Captured API tier table lists `llminferenceservices.serving.kserve.io/v1alpha1` as Tier 2. The live cluster stores `v1alpha2`, which must be rechecked against current RHOAI 3.4 docs and CRD metadata before authoring. | Prefer the live storage version only after official-doc and `oc explain` validation. Record the support posture in the README and manifest comments if the active version is Technology Preview, Beta, Alpha, or unresolved. |
| MaaS CRDs | MaaS resources are product-documented for RHOAI 3.4, but the CRDs are not present on the current cluster yet. | Install/enable MaaS prerequisites first, then validate `Tenant`, `MaaSModelRef`, `ExternalModel`, `MaaSSubscription`, and `MaaSAuthPolicy` schemas before copying quickstart examples. |
| Gateway API | Gateway API resources are present as `gateway.networking.k8s.io/v1`. They are OpenShift/Kubernetes gateway resources, not RHOAI API-tier entries. | Validate listener, namespace, hostname, route, and ReferenceGrant behavior with live schema and official OpenShift/RHOAI docs before claiming MaaS access paths. |
| RBAC and access policy | Stage 040 needs both OpenShift RBAC/group membership and MaaS gateway authorization. | Do not claim access until both `MaaSSubscription` quota and `MaaSAuthPolicy` authorization are present and validated for allowed and denied subjects. |
| External OpenAI model | `gpt-4o-mini` is selected because it matches the Red Hat Developer gateway example and official OpenAI docs describe it as a stronger mini model for high-volume workloads. | Recheck model availability and pricing before demo delivery. Store provider credentials only in local Secret material, and document that prompts leave the cluster for this model. |

## Completed Schema Checks Before MaaS Model GitOps

Completed against `cluster-klvxt` on 2026-06-12 after the OpenShift safety guard confirmed the target cluster:

```bash
oc get crd llminferenceservices.serving.kserve.io \
  maasmodelrefs.maas.opendatahub.io \
  maassubscriptions.maas.opendatahub.io \
  maasauthpolicies.maas.opendatahub.io \
  externalmodels.maas.opendatahub.io \
  tenants.maas.opendatahub.io

oc explain llminferenceservice.spec --api-version=serving.kserve.io/v1alpha2
oc explain llminferenceservice.spec.model --api-version=serving.kserve.io/v1alpha2
oc explain llminferenceservice.spec.router.gateway --api-version=serving.kserve.io/v1alpha2

oc explain maasmodelrefs.maas.opendatahub.io.spec
oc explain maassubscriptions.maas.opendatahub.io.spec
oc explain maasauthpolicies.maas.opendatahub.io.spec
oc explain externalmodels.maas.opendatahub.io.spec
oc explain tenants.maas.opendatahub.io.spec
```

Rerun these checks after any RHOAI, RHCL, or OpenShift upgrade before changing model, subscription, or auth-policy manifests.

Phase-one deploy and validation commands:

```bash
./040-governed-models-as-a-service/deploy.sh
./040-governed-models-as-a-service/validate.sh
```

## GitOps Ownership Decision

- Shared RHOAI owner: `010-openshift-ai-platform-foundation` continues to own the single `DataScienceCluster`.
- Stage 040 should add a focused GitOps hook for MaaS component enablement instead of rendering a second `DataScienceCluster`.
- Stage 040 should own its independent prerequisites and policy resources under `gitops/stages/040-governed-models-as-a-service/base/` unless an operator or global platform component clearly belongs to an existing shared owner.
- Provider API keys, MaaS PostgreSQL credentials, and user API keys must be created from local `.env` or an approved secret store, never committed.
- Stage 040 creates an `LLMInferenceService` for Nemotron in `models-as-a-service`, uses the Stage 030 benchmark result to choose initial concurrency/token limits, and preserves the curated Nemotron vLLM/tool-calling configuration where the `v1alpha2` schema allows it.
- Stage 040 avoids running a second GPU-heavy Nemotron backend alongside the direct Stage 030 endpoint on the single default GPU node. The deploy wrapper deletes stale direct `demo-sandbox` Nemotron serving resources first, then lets Argo CD reconcile the MaaS-owned backend.
- Initial Nemotron policy should use the 2026-06-12 Stage 030 GuideLLM results: start the chat assistant lane at `8` active concurrent requests per replica with 256 output-token defaults; start the RAG lane at `2` active concurrent requests per replica for about 4k-token prompts and 512 output-token responses. Treat chat `12` and RAG `4` as burst or breakpoint candidates, not public default quotas.

## Planned Manifest Areas

| Area | Expected resources | Verification |
|------|--------------------|--------------|
| MaaS prerequisites | Pinned Connectivity Link Operator, `Kuadrant`, Gateway, `maas-gateway-tls`, Authorino TLS, `maas-db-config` Secret | Exact RHCL CSV, package/channel, and CRD checks; no secret values in Git |
| Shared RHOAI patch | `DataScienceCluster` MaaS enablement and dashboard feature flags | Kustomize render and live DSC status |
| Local model backend | `LLMInferenceService` for Nemotron, or another officially supported MaaS backend if schema requires it | `Ready=True`, authenticated inference, metrics |
| Local MaaS publication | `MaaSModelRef` for Nemotron | CRD schema and dashboard/API model listing |
| External provider | `ExternalModel` and `MaaSModelRef` named `gpt-4o-mini` with `spec.targetModel: gpt-4o-mini`, provider Secret supplied locally | OpenAI model availability, DNS-1035 resource-name compatibility, and Secret reference |
| Access governance | `rhods-admins` namespace admin RoleBinding, `MaaSSubscription`, `MaaSAuthPolicy`, group/user mapping, token limits, cost metadata | Allowed and denied inference tests |
| Observability | Tenant telemetry, MaaS/Kuadrant metrics, dashboard flag | Usage/rate-limit metrics visible; TP label in docs |
| Serving-health monitoring | `monitoring/base/`: `vllm-serving-health` PrometheusRule (UWM recording rules for TTFT/ITL p95 and KV-cache utilization; alerts for high TTFT, request-queue backlog, KV-cache pressure, parked-model info) and `monitoring-rules-view` RoleBinding for the demo user groups | Rules/alerts visible in Thanos; recording-rule series present after serving traffic (added 2026-07-05, aligns with the RHOAI managing-and-monitoring-models guide) |
| Gen AI Playground | Dashboard flags, Llama Stack Operator if required, AI asset endpoint visibility | `ai-developer` sees and uses MaaS models from AI asset endpoints/playground without MaaS namespace admin rights |

## Risks And Deferred Decisions

| Item | Type | Resolution |
|------|------|------------|
| Official docs group discrepancy | resolved for current cluster | The official RHOAI 3.4 guide lists `*.maas.opendatahub.io` CRDs but shows `models.opendatahub.io/v1alpha1` YAML for several MaaS resources. The live cluster exposes MaaS resources as `maas.opendatahub.io/v1alpha1`; use that group/version for current GitOps. |
| `LLMInferenceService` example version drift | risk | Active cluster stores `v1alpha2`; adapt examples only after schema checks. |
| External OpenAI provider data path | risk | Document that prompts sent to `gpt-4o-mini` leave the cluster and are subject to provider policy, region, and account settings. |
| Missing provider credential | blocker for live rollout | Do not push external-model GitOps into the Argo CD sync loop unless `openai-provider-api-key` exists in `models-as-a-service` or `OPENAI_API_KEY`/`RHOAI_OPENAI_API_KEY` is provided locally for `deploy.sh`. |
| Provider rate limits | risk | MaaS limits protect users from each other inside the demo, but the shared OpenAI provider key can still hit provider-level aggregate limits. |
| RHCL version drift | blocker | If a cluster already installed RHCL 1.4.x, remediate the operator lifecycle back to the pinned `rhcl-operator.v1.3.4` path before claiming MaaS gateway/dashboard readiness. Do not patch generated Kuadrant `AuthPolicy` or `EnvoyFilter` resources. |
| RHCL dependency upgrade drift | blocker | RHCL `1.3.4` is the validated boundary for this stage. On `cluster-xgg8t`, the broader dependency plan for DNS Operator `1.3.1`, Service Mesh `3.3.5`, and Authorino CRD changes failed because generated MaaS `AuthConfig` resources did not validate against the incoming Authorino schema. Do not approve additional MaaS dependency upgrades without Red Hat guidance and a full Stage 040 regression run. |
| MaaS observability support posture | risk | Label as Technology Preview and showback-only, not billing-grade metering. |
| Stage 030 operating envelope changes | dependency | Re-run the chat/RAG GuideLLM policy profiles whenever the Nemotron model, vLLM args, GPU shape, prompt size, or output-token defaults change. |
