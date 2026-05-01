# Backlog

## Workarounds (revert when Red Hat OpenShift AI 3.4 GA ships)

The following items use manual configuration or post-deploy patches because the Red Hat OpenShift AI 3.3 operator's MaaS integration has gaps. When Red Hat OpenShift AI 3.4 GA ships, verify whether these are still needed and remove those that are handled natively.

- [ ] **Gateway AuthPolicy patch for user OAuth tokens** — The operator's `gateway-auth-policy` only accepts ServiceAccount tokens (`maas-default-gateway-sa` audience). The dashboard's `gen-ai-ui` forwards user OAuth tokens. The `configure-kuadrant` Job patches both `gateway-auth-policy` (adds `user-tokens` authentication) and `maas-api-auth-policy` (adds empty `authorization: {}` to override gateway-level tier-access check for `/maas-api/*` management endpoints).
  **Revert:** The 3.4 operator should configure AuthPolicies that accept dashboard-forwarded tokens natively.

- [ ] **Authorino SSL env vars** (`jobs/configure-kuadrant.yaml`) — Job sets `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` on Authorino deployment so it trusts OpenShift's internal service-ca.
  **Revert:** Verify if the 3.4 operator handles this natively.

- [ ] **Gateway hostname patch** (`jobs/patch-gateway-hostname.yaml`) — Job patches MaaS Gateway with cluster-specific hostname and TLS cert name.
  **Revert:** The 3.4 operator may parameterize the Gateway hostname.

- [ ] **Tier-to-group-mapping ConfigMap in `redhat-ods-applications`** — The Red Hat OpenShift AI validating webhook requires this ConfigMap when `LLMInferenceService` uses the `alpha.maas.opendatahub.io/tiers` annotation. The operator's `maas-api` does not create it in `redhat-ods-applications`; we deploy it at sync wave 9.
  **Revert:** The 3.4 operator should create this ConfigMap automatically.

- [ ] **Manual RateLimitPolicy, TokenRateLimitPolicy, TelemetryPolicy** — Created in `governance/` because 3.3 has no operator-managed MaaS policies.
  **Revert:** The 3.4 operator may manage these via `MaaSSubscription` CRDs.

- [ ] **Manual per-model RBAC** (`models/rbac.yaml`) — Roles granting tier ServiceAccounts access to `LLMInferenceService`.
  **Revert:** The 3.4 operator may manage RBAC via `MaaSAuthPolicy` CRDs.

- [ ] **Manual tier groups** (`governance/maas-groups.yaml`) — Groups `tier-free-users`, `tier-premium-users`, `tier-enterprise-users` with demo users.
  **Revert:** Verify if the 3.4 operator manages tier groups.

- [ ] **Model Registry NetworkPolicy** (`model-registry/registry/dashboard-networkpolicy.yaml`) — The operator's default NetworkPolicy only allows same-namespace access. We add a policy allowing `redhat-ods-applications` to reach the registry on port 8080.
  **Revert:** The 3.4 operator should create proper NetworkPolicies for the dashboard.

## Workarounds (upstream maas-controller coexistence with Red Hat OpenShift AI 3.3)

The following items maintain the hybrid architecture where the upstream `maas-controller` runs alongside the Red Hat OpenShift AI 3.3 operator. This is intentional for the demo: it shows external model registration through `ExternalModel` and `MaaSModelRef`, a capability available in the upstream models-as-a-service project and evaluated in Red Hat OpenShift AI 3.4 early access releases. When Red Hat OpenShift AI ships the capability natively in a supported release, these can be removed.

- [ ] **maas-api image pinning** (`jobs/patch-maas-api-storage.yaml`) — The Red Hat OpenShift AI 3.3 `maas-api` binary does not implement model discovery from `MaaSModelRef`/`ExternalModel` CRDs. A post-deploy Job pins the tenant-managed deployment to `quay.io/opendatahub/maas-api:latest` which has Kubernetes watchers for model discovery. The Red Hat OpenShift AI DSC may still report `ModelsAsServiceReady=False`.
  **Justification:** This deviation is deliberate. The demo needs to demonstrate governed external model registration before the capability is generally available through the supported Red Hat OpenShift AI 3.3 operator path.
  **Fragility:** If the Red Hat OpenShift AI operator recreates the deployment or rewrites `maas-parameters`, rerun the `job-patch-maas-api-storage` Job.

- [ ] **`models-as-a-service` namespace** — The upstream `maas-api` expects `MaaSAuthPolicy` and `MaaSSubscription` CRs in the `models-as-a-service` namespace (hardcoded in the kustomize overlay's `params.env`). The namespace and policy CRs are GitOps-managed under `models-maas-crds/`.

- [ ] **Dashboard Route** — The Red Hat OpenShift AI dashboard is accessed via the `rh-ai.*` hostname through the `data-science-gateway`. The operator's default `rhods-dashboard` Route redirects to the gateway.

- [ ] **ExternalModel credential Secret label** — Secrets referenced by `ExternalModel.spec.credentialRef` must have the label `inference.networking.k8s.io/bbr-managed=true` for the payload-processing (IPP) plugin to discover them.

- [ ] **Tokens-bridge** (`maas-controller-upstream/tokens-bridge/deployment.yaml`) — Translates `/maas-api/v1/tokens` to `/v1/api-keys` because the upstream `maas-api:latest` does not have the `/v1/tokens` endpoint that the Playground's `gen-ai-ui` calls.

## Known Limitations

- [ ] **ExternalModel name must match provider model name** — The payload-processing BBR plugin validates that `ExternalModel.spec.targetModel` matches the model name in the request body. Since LlamaStack sends the MaaS model name (the ExternalModel resource name), the ExternalModel must be named with the exact provider model name (e.g., `gpt-4o`, not `openai-gpt-4o`). Tracked upstream: [opendatahub-io/models-as-a-service#684](https://github.com/opendatahub-io/models-as-a-service/issues/684).

- [ ] **AI asset endpoints dropdown shows workspace namespaces** — The GenAI Studio AI asset endpoints project dropdown lists all namespaces where the user has any RBAC (including Dev Spaces workspace namespaces). The Projects page correctly filters by `opendatahub.io/dashboard: "true"`. This is a dashboard UI inconsistency.

- [ ] **Upstream `/v1/responses` support in BBR plugin** — The ODH BBR plugin ([opendatahub-io/ai-gateway-payload-processing](https://github.com/opendatahub-io/ai-gateway-payload-processing)) only supports `/chat/completions`. The upstream [Envoy AI Gateway](https://aigateway.envoyproxy.io/docs/capabilities/llm-integrations/supported-endpoints) supports `/v1/responses` natively. Models requiring `/v1/responses` (e.g., GPT-5 Codex) cannot be served through the standard MaaS pipeline until the ODH fork adds native support. See the Completed section for the proven routing workaround.

## Planned

- [ ] **OpenShift MCP — scoped RBAC per persona** — The OpenShift MCP ServiceAccount currently has cluster-wide `view` ClusterRole. Explore namespace-scoped RoleBindings.
- [ ] **Red Hat-aligned observability path** — The current Grafana dashboard was copied from a Red Hat quickstart repository and uses the community Grafana Operator. Prefer a Red Hat-supported monitoring or observability path for long-lived environments.
- [ ] **Grafana dashboard screenshots** — Add screenshots to Stage 040 README while the community Grafana demo add-on remains in use.
- [ ] **Multi-cluster support** — Parameterize cluster-specific values via overlay.

## Validated (2026-04-29)

- [x] **MaaS API — 4 models listed** — `/maas-api/v1/models` returns `gpt-oss-20b`, `nemotron-3-nano-30b-a3b`, `gpt-4o`, and `gpt-4o-mini` as `ready=true`. Uses upstream `maas-api` (`quay.io/opendatahub/maas-api:latest`) with PostgreSQL backend.
- [x] **API key generation** — `sk-oai-*` format keys via `/maas-api/v1/api-keys`. Playground uses `/maas-api/v1/tokens` through the tokens-bridge proxy.
- [x] **Local model inference** — Both GPU models respond in the Playground and via MaaS API.
- [x] **External model inference (GPT-4o/4o-mini)** — Working in Playground, Continue, OpenCode, and via MaaS API. The `payload-processing` BBR plugin injects OpenAI credentials from the `openai-api-key` Secret.
- [x] **MaaSAuthPolicy + MaaSSubscription** — CRDs in `models-as-a-service` namespace, both `Active`. Per-route AuthPolicies and TokenRateLimitPolicies auto-created by the controller for all 4 models.
- [x] **Continue — 4 models configured** — All 4 models working via `.vscode/config.yaml` with `sk-oai-*` API key auth.
- [x] **OpenCode — 4 models configured** — All 4 models working via `.opencode/opencode.json` (one provider per model) with `sk-oai-*` API key auth. Nemotron is the default model, gpt-4o-mini is the small model.

## Completed

- [x] ~~**GPT-5-Codex /v1/responses routing (PROVEN, REMOVED)** — The BBR plugin only supports `/chat/completions`, so a dedicated routing path was created for GPT-5-Codex: separate HTTPRoute, EnvoyFilter (disables `ext_proc.bbr` + injects OpenAI credential), AuthPolicy (accepts OpenShift tokens instead of `sk-oai-*` keys), and TokenRateLimitPolicy. Worked with Continue and OpenCode but was not Playground-compatible (gen-ai-ui limitation). Removed from the demo to simplify to a clean 4-model architecture where all models use the same auth method (`sk-oai-*` keys) and API (`/v1/chat/completions`). The routing solution is preserved in git history and can be reapplied when the BBR plugin adds native `/v1/responses` support.~~
- [x] ~~**remote::openai LlamaStack provider (INVESTIGATED)** — Verified that manually patching the LlamaStack ConfigMap to use `remote::openai` instead of `remote::vllm` enables GPT-5 model responses via `/v1/responses`. However, the `gen-ai-ui` overwrites the ConfigMap on Playground recreation. Investigation preserved in git history.~~
- [x] ~~**Automated MaaS API validation** — implemented in stage validation scripts.~~
- [x] ~~**Devfile-based Continue auto-configuration** — Created `adnan-drina/coding-exercises` repo with `devfile.yaml` that auto-copies Continue config via postStart.~~
- [x] ~~**OpenCode CLI in Dev Spaces** — Installed via postStart in DevWorkspace.~~
- [x] ~~**ExternalModel support** — Deployed upstream `maas-controller` alongside Red Hat OpenShift AI 3.3 operator. 2 OpenAI models (gpt-4o, gpt-4o-mini) registered as `ExternalModel` CRDs.~~
- [x] ~~**GitOps-ify upstream maas-controller** — Upstream CRDs, RBAC, controller, PostgreSQL, and MaaS CRs now live under `gitops/stages/040-governed-models-as-a-service/base/`.~~
- [x] ~~**Red Hat OpenShift AI 3.4 EA2 evaluation** — Tested operator-native MaaS. Found that the EA2 `maas-api` binary does not implement model discovery from Kubernetes resources. Reverted to Red Hat OpenShift AI 3.3 + upstream maas-controller.~~
