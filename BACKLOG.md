# Backlog

## Workarounds (revert when RHOAI 3.4 GA ships)

The following items use manual configuration or post-deploy patches because the RHOAI 3.3 operator's MaaS integration has gaps. When RHOAI 3.4 GA ships, verify whether these are still needed and remove those that are handled natively.

- [ ] **Gateway AuthPolicy patch for user OAuth tokens** — The operator's `gateway-auth-policy` only accepts ServiceAccount tokens (`maas-default-gateway-sa` audience). The dashboard's `gen-ai-ui` forwards user OAuth tokens. The `configure-kuadrant` Job patches both `gateway-auth-policy` (adds `user-tokens` authentication) and `maas-api-auth-policy` (adds empty `authorization: {}` to override gateway-level tier-access check for `/maas-api/*` management endpoints).
  **Revert:** The 3.4 operator should configure AuthPolicies that accept dashboard-forwarded tokens natively.

- [ ] **Authorino SSL env vars** (`jobs/configure-kuadrant.yaml`) — Job sets `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` on Authorino deployment so it trusts OpenShift's internal service-ca.
  **Revert:** Verify if the 3.4 operator handles this natively.

- [ ] **Gateway hostname patch** (`jobs/patch-gateway-hostname.yaml`) — Job patches MaaS Gateway with cluster-specific hostname and TLS cert name.
  **Revert:** The 3.4 operator may parameterize the Gateway hostname.

- [ ] **Tier-to-group-mapping ConfigMap in `redhat-ods-applications`** — The RHOAI validating webhook requires this ConfigMap when `LLMInferenceService` uses the `alpha.maas.opendatahub.io/tiers` annotation. The operator's `maas-api` does not create it in `redhat-ods-applications`; we deploy it at sync wave 9.
  **Revert:** The 3.4 operator should create this ConfigMap automatically.

- [ ] **Manual RateLimitPolicy, TokenRateLimitPolicy, TelemetryPolicy** — Created in `governance/` because 3.3 has no operator-managed MaaS policies.
  **Revert:** The 3.4 operator may manage these via `MaaSSubscription` CRDs.

- [ ] **Manual per-model RBAC** (`models/rbac.yaml`) — Roles granting tier ServiceAccounts access to `LLMInferenceService`.
  **Revert:** The 3.4 operator may manage RBAC via `MaaSAuthPolicy` CRDs.

- [ ] **Manual tier groups** (`governance/maas-groups.yaml`) — Groups `tier-free-users`, `tier-premium-users`, `tier-enterprise-users` with demo users.
  **Revert:** Verify if the 3.4 operator manages tier groups.

- [ ] **Model Registry NetworkPolicy** (`model-registry/registry/dashboard-networkpolicy.yaml`) — The operator's default NetworkPolicy only allows same-namespace access. We add a policy allowing `redhat-ods-applications` to reach the registry on port 8080.
  **Revert:** The 3.4 operator should create proper NetworkPolicies for the dashboard.

## Workarounds (upstream maas-controller coexistence with RHOAI 3.3)

The following items maintain the hybrid architecture where the upstream `maas-controller` runs alongside the RHOAI 3.3 operator. When RHOAI ships the `maas-controller` natively, these can be removed.

- [ ] **maas-api image pinning** (`jobs/patch-maas-api-storage.yaml`) — The RHOAI 3.3 `maas-api` binary does not implement model discovery from `MaaSModelRef`/`ExternalModel` CRDs. A post-deploy Job pins the tenant-managed deployment to `quay.io/opendatahub/maas-api:latest` which has Kubernetes watchers for model discovery. The RHOAI DSC may still report `ModelsAsServiceReady=False`.
  **Fragility:** If the RHOAI operator recreates the deployment or rewrites `maas-parameters`, rerun the `job-patch-maas-api-storage` Job.

- [ ] **`models-as-a-service` namespace** — The upstream `maas-api` expects `MaaSAuthPolicy` and `MaaSSubscription` CRs in the `models-as-a-service` namespace (hardcoded in the kustomize overlay's `params.env`). The namespace and policy CRs are GitOps-managed under `models-maas-crds/`.

- [ ] **Dashboard Route** — The RHOAI dashboard is accessed via the `rh-ai.*` hostname through the `data-science-gateway`. The operator's default `rhods-dashboard` Route redirects to the gateway.

- [ ] **ExternalModel credential Secret label** — Secrets referenced by `ExternalModel.spec.credentialRef` must have the label `inference.networking.k8s.io/bbr-managed=true` for the payload-processing (IPP) plugin to discover them.

- [ ] **Tokens-bridge** (`maas-controller-upstream/tokens-bridge/deployment.yaml`) — Translates `/maas-api/v1/tokens` to `/v1/api-keys` because the upstream `maas-api:latest` does not have the `/v1/tokens` endpoint that the Playground's `gen-ai-ui` calls.

## Known Limitations

- [ ] **ExternalModel name must match provider model name** — The payload-processing BBR plugin validates that `ExternalModel.spec.targetModel` matches the model name in the request body. Since LlamaStack sends the MaaS model name (the ExternalModel resource name), the ExternalModel must be named with the exact provider model name (e.g., `gpt-4o`, not `openai-gpt-4o`). Tracked upstream: [opendatahub-io/models-as-a-service#684](https://github.com/opendatahub-io/models-as-a-service/issues/684).

- [ ] **GPT-5 models: MaaS Gateway only supports `/chat/completions`** — GPT-5 models (`gpt-5-codex`, `gpt-5-mini`) require OpenAI's `/v1/responses` API, but the MaaS Gateway's `payload-processing` BBR plugin ([opendatahub-io/ai-gateway-payload-processing](https://github.com/opendatahub-io/ai-gateway-payload-processing)) only handles `/chat/completions` input. Inference requests through the MaaS Gateway fail with `"only /chat/completions input type is supported"`. This blocks GPT-5 from:
  - **Playground** — `gen-ai-ui` creates LlamaStack with `remote::vllm` (chat completions only). Manual `remote::openai` patching in the LlamaStack ConfigMap works but `gen-ai-ui` overwrites it on Playground recreation.
  - **Continue** — `provider: openai` correctly sends `/v1/responses` to the MaaS Gateway, but payload-processing rejects it.
  - **OpenCode / direct API** — same Gateway rejection.
  GPT-5 models appear in the MaaS tab and API keys can be generated, but inference through the Gateway is blocked.
  **Investigation (2026-04-29):**
  - Both `odh-stable` and `odh-pr` images reject `/v1/responses`. The upstream [Envoy AI Gateway](https://aigateway.envoyproxy.io/docs/capabilities/llm-integrations/supported-endpoints) supports `/v1/responses`, but the ODH BBR framework only parses `/chat/completions`.
  - The Envoy route name is `maas.gpt-5-codex.0` with `path_separated_prefix: /maas/gpt-5-codex`. The route correctly reaches `outbound|443||api.openai.com`.
  - The ext_proc filter name is `envoy.filters.http.ext_proc.bbr`. Credential injection (`apikey-injection` plugin) runs inside the ext_proc — **Case C**: disabling ext_proc also disables OpenAI key injection.
  - Attempted `ExtProcPerRoute` with `request_body_mode: NONE` to skip body parsing while keeping header processing. Result: ext_proc stalls waiting for body (504 timeout) because the `body-field-to-header` plugin expects body data.
  - **Remaining options:** (a) Fully disable ext_proc for the gpt-5-codex route and inject the OpenAI key via Envoy route-level `request_headers_to_add` or `BackendSecurityPolicy`. (b) Wait for ODH `payload-processing` to add `/v1/responses` support. (c) File issue on [opendatahub-io/ai-gateway-payload-processing](https://github.com/opendatahub-io/ai-gateway-payload-processing/issues).

- [ ] **AI asset endpoints dropdown shows workspace namespaces** — The GenAI Studio AI asset endpoints project dropdown lists all namespaces where the user has any RBAC (including Dev Spaces workspace namespaces). The Projects page correctly filters by `opendatahub.io/dashboard: "true"`. This is a dashboard UI inconsistency.

## Planned

- [ ] **OpenShift MCP — scoped RBAC per persona** — The OpenShift MCP ServiceAccount currently has cluster-wide `view` ClusterRole. Explore namespace-scoped RoleBindings.
- [ ] **Grafana dashboard screenshots** — Add screenshots to step-03 README.
- [ ] **Multi-cluster support** — Parameterize cluster-specific values via overlay.

## Validated (2026-04-29)

- [x] **MaaS API — 5 models listed** — `/maas-api/v1/models` returns `gpt-oss-20b`, `nemotron-3-nano-30b-a3b`, `gpt-4o`, `gpt-4o-mini`, and `gpt-5-codex` as `ready=true`. Uses upstream `maas-api` (`quay.io/opendatahub/maas-api:latest`) with PostgreSQL backend.
- [x] **API key generation** — `sk-oai-*` format keys via `/maas-api/v1/api-keys`. Playground uses `/maas-api/v1/tokens` through the tokens-bridge proxy.
- [x] **Local model inference** — Both GPU models respond in the Playground and via MaaS API.
- [x] **External model inference (GPT-4o/4o-mini)** — Working in Playground and via MaaS API. The `payload-processing` BBR plugin injects OpenAI credentials from the `openai-api-key` Secret.
- [x] **External model inference (GPT-5-Codex)** — Working via MaaS API key. Not compatible with Playground (uses `/v1/responses` API). Can be used by code agents through MaaS portal.
- [x] **MaaSAuthPolicy + MaaSSubscription** — CRDs in `models-as-a-service` namespace, both `Active`. Per-route AuthPolicies and TokenRateLimitPolicies auto-created by the controller.
- [x] **remote::openai LlamaStack provider** — Verified that manually patching the LlamaStack ConfigMap to use `remote::openai` instead of `remote::vllm` enables GPT-5 model responses via `/v1/responses`. However, the `gen-ai-ui` overwrites the ConfigMap on Playground recreation.

## Completed

- [x] ~~**Automated MaaS API validation** — implemented in `step-03/validate.sh`.~~
- [x] ~~**Devfile-based Continue auto-configuration** — Created `adnan-drina/coding-exercises` repo with `devfile.yaml` that auto-copies Continue config via postStart.~~
- [x] ~~**OpenCode CLI in Dev Spaces** — Installed via postStart in DevWorkspace.~~
- [x] ~~**ExternalModel support** — Deployed upstream `maas-controller` alongside RHOAI 3.3 operator. 3 OpenAI models (gpt-4o, gpt-4o-mini, gpt-5-codex) registered as `ExternalModel` CRDs.~~
- [x] ~~**GitOps-ify upstream maas-controller** — Upstream CRDs, RBAC, controller, PostgreSQL, and MaaS CRs in `gitops/step-03-llm-serving-maas/base/`.~~
- [x] ~~**RHOAI 3.4 EA2 evaluation** — Tested operator-native MaaS. Found that the EA2 `maas-api` binary does not implement model discovery from Kubernetes resources. Reverted to RHOAI 3.3 + upstream maas-controller.~~
