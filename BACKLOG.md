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

## Known Limitations

- [ ] **AI asset endpoints dropdown shows workspace namespaces** — The GenAI Studio AI asset endpoints project dropdown lists all namespaces where the user has any RBAC (including Dev Spaces workspace namespaces). The Projects page correctly filters by `opendatahub.io/dashboard: "true"`. This is a dashboard UI inconsistency — candidate for upstream issue in `opendatahub-io/odh-dashboard`.

- [ ] **Playground shows no response for reasoning models** — Both `gpt-oss-20b` and `nemotron-3-nano-30b-a3b` produce output via `reasoning_text` streaming events (the model images have built-in reasoning parsers). The RHOAI 3.3 Playground UI renders `output_text` events only, so responses appear empty. LlamaStack correctly receives and returns the response (verified via direct `/v1/responses` calls). This is a UI rendering limitation — the Playground doesn't display `reasoning_text` content. The models work correctly via API (curl, Continue, OpenCode).

- [ ] **Track upstream MaaS deployment alignment** — The [upstream models-as-a-service](https://github.com/opendatahub-io/models-as-a-service) repo has a `deploy.sh` script with `--operator-type rhoai`. This repo now GitOps-manages the key pieces directly (PostgreSQL, `maas-db-config`, `maas-controller`, upstream CRDs, and MaaS CRs), because the upstream script initially failed on this cluster due to operator version expectations. **Next step:** periodically compare the committed `maas-controller-upstream/` manifests with upstream changes and remove local copies once RHOAI ships equivalent native support.

## Workarounds (upstream maas-controller coexistence with RHOAI 3.3)

The following items maintain the hybrid architecture where the upstream `maas-controller` runs alongside the RHOAI 3.3 operator. When RHOAI ships the `maas-controller` natively, these can be removed.

- [ ] **RHOAI/upstream `maas-api` ownership conflict** — The RHOAI 3.3 operator and upstream tenant reconciler generate incompatible `maas-api` Deployment selectors. For this hybrid demo, the tenant-managed `maas-api` deployment is patched to `quay.io/opendatahub/maas-api:latest`, because the RHOAI 3.3 image does not list `ExternalModel` CRs. The RHOAI DSC may still report `ModelsAsServiceReady=False` because the 3.3 operator cannot apply its older selector.
  **Fragility:** If the RHOAI operator recreates the deployment or rewrites `maas-parameters`, rerun the `job-patch-maas-api-storage` Job.

- [ ] **RHOAI DSC status error (non-blocking)** — `DataScienceCluster/default-dsc` can remain `Ready=False` on `ModelsAsServiceReady` while the MaaS route, `maas-api`, `maas-controller`, and generated MaaS CRs are healthy. Validate the demo path through `/maas-api/v1/models` and the dashboard MaaS tab.

- [ ] **`models-as-a-service` namespace** — The upstream `maas-api` expects `MaaSAuthPolicy` and `MaaSSubscription` CRs in the `models-as-a-service` namespace (hardcoded in the kustomize overlay's `params.env`). The namespace and policy CRs are GitOps-managed under `models-maas-crds/`.

- [ ] **Dashboard Route** — The RHOAI dashboard is accessed via a manually created OpenShift Route (`passthrough` TLS to `rhods-dashboard:8443`). The operator's `data-science-gateway` uses ClusterIP only.

- [ ] **ExternalModel credential Secret label** — Secrets referenced by `ExternalModel.spec.credentialRef` must have the label `inference.networking.k8s.io/bbr-managed=true` for the payload-processing (IPP) plugin to discover them.

## Planned

- [ ] **OpenShift MCP — scoped RBAC per persona** — The OpenShift MCP ServiceAccount currently has cluster-wide `view` ClusterRole (read-only access to all namespaces). Explore namespace-scoped RoleBindings or a custom ClusterRole for tighter security.
- [ ] **Grafana dashboard screenshots** — Add screenshots to step-03 README.
- [ ] **Multi-cluster support** — Parameterize cluster-specific values via overlay.

## Validated (2026-04-29)

- [x] **Upstream MaaS API — 3 models listed** — `/maas-api/v1/models` returns `gpt-oss-20b`, `nemotron-3-nano-30b-a3b`, and `openai-gpt-4o` as `ready=true`. Uses upstream `maas-api` (`quay.io/opendatahub/maas-api:latest`) with PostgreSQL backend.
- [x] **API key generation** — API keys are generated via `/maas-api/v1/tokens`, bridged to the upstream `/v1/api-keys` endpoint, and stored in PostgreSQL.
- [x] **Local model inference** — Both GPU models respond HTTP 200 to `/v1/chat/completions` via MaaS Gateway. Nemotron uses `reasoning_content` field; GPT-OSS-20B produces clean output.
- [x] **External model inference** — OpenAI GPT-4o responds HTTP 200 via `/maas/openai-gpt-4o/v1/chat/completions`. The MaaS Gateway authenticates the user, strips their API key, injects the OpenAI provider credential, and forwards to `api.openai.com`. Requires `inference.networking.k8s.io/bbr-managed=true` label on the credential Secret.
- [x] **MaaSAuthPolicy + MaaSSubscription** — CRDs in `models-as-a-service` namespace, both `Active`. Per-route AuthPolicies and TokenRateLimitPolicies auto-created by the controller in `maas` namespace.

## Completed

- [x] ~~**Automated MaaS API validation** — implemented in `step-03/validate.sh`.~~
- [x] ~~**Devfile-based Continue auto-configuration** — Created `adnan-drina/coding-exercises` repo with `devfile.yaml` that auto-copies Continue config via postStart. DevWorkspaces now clone this repo instead of the full quickstart.~~
- [x] ~~**Component-per-operator extraction** — Deferred; current structure works well for 4-step demo.~~
- [x] ~~**Multi-version overlay structure** — Deferred; only RHOAI 3.3 needed for now.~~
- [x] ~~**OpenCode CLI in Dev Spaces** — Installed via postStart in DevWorkspace. Binary downloaded from GitHub releases to `~/.local/bin/`. Developer uses `/connect` to configure MaaS endpoint.~~
- [x] ~~**ExternalModel support** — Deployed upstream `maas-controller` alongside RHOAI 3.3 operator. OpenAI GPT-4o registered as `ExternalModel` CRD with `MaaSModelRef`, `MaaSAuthPolicy`, `MaaSSubscription`. All 3 models (2 local + 1 external) visible in MaaS API and serving inference.~~
- [x] ~~**GitOps-ify upstream maas-controller** — Upstream CRDs, RBAC, controller deployment, PostgreSQL, `models-as-a-service` namespace, ExternalModel CRs, and MaaS policy CRs are wired into `gitops/step-03-llm-serving-maas/base/` for repeatable deployment.~~
