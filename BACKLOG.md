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

## Planned

- [ ] **OpenCode CLI in Dev Spaces** — Add [OpenCode](https://github.com/opencode-ai/opencode) as a terminal-based agentic AI assistant alongside Continue. OpenCode is model-neutral (75+ providers) and works with any OpenAI-compatible endpoint, including our MaaS. The developer could use Continue for inline editing and OpenCode for terminal tasks (git diff review, code analysis, project scaffolding). Implementation: add the `opencode` binary to the DevWorkspace tooling container or use the [cli-ai-tools](https://github.com/che-incubator/cli-ai-tools/) devfile. See [Red Hat Developer article](https://developers.redhat.com/articles/2026/04/22/opencode-model-neutral-ai-coding-assistant-openshift-dev-spaces).
- [ ] **OpenShift MCP — scoped RBAC per persona** — The OpenShift MCP ServiceAccount currently has cluster-wide `view` ClusterRole (read-only access to all namespaces). Explore namespace-scoped RoleBindings or a custom ClusterRole for tighter security. See BACKLOG for design options.
- [ ] **Grafana dashboard screenshots** — Add screenshots to step-03 README.
- [ ] **Multi-cluster support** — Parameterize cluster-specific values via overlay.

## Completed

- [x] ~~**Automated MaaS API validation** — implemented in `step-03/validate.sh`.~~
- [x] ~~**Devfile-based Continue auto-configuration** — Created `adnan-drina/coding-exercises` repo with `devfile.yaml` that auto-copies Continue config via postStart. DevWorkspaces now clone this repo instead of the full quickstart.~~
- [x] ~~**Component-per-operator extraction** — Deferred; current structure works well for 4-step demo.~~
- [x] ~~**Multi-version overlay structure** — Deferred; only RHOAI 3.3 needed for now.~~
