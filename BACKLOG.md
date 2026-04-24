# Backlog

## Community Workarounds (revert when RHOAI 3.4 GA ships)

The following items use community components or manual configuration because RHOAI 3.3 does not include native MaaS support. When RHOAI 3.4 GA is released with full MaaS integration, these should be reverted to operator-native equivalents.

- [ ] **Dev-preview maas-api** (`quay.io/opendatahub/maas-api:latest-0681979`) — Deployed separately via `oc apply -k gitops/step-03-llm-serving-maas/base/maas-api/` because RHOAI 3.3 has no built-in MaaS API. The remote kustomize base comes from [opendatahub-io/models-as-a-service](https://github.com/opendatahub-io/models-as-a-service).
  **Revert:** Remove `maas-api/` directory and `oc apply -k` from `deploy.sh`. Set `modelsAsService: Managed` in the DSC — the 3.4 operator will deploy its own `maas-api` in `redhat-ods-applications`.

- [ ] **Manual RateLimitPolicy, TokenRateLimitPolicy, TelemetryPolicy** — Created in `governance/` because 3.3 has no operator-managed MaaS policies.
  **Revert:** Remove policy files from `governance/`. The 3.4 operator manages these via `MaaSSubscription` CRDs.

- [ ] **Manual per-model RBAC** (`models/rbac.yaml`) — Role/RoleBinding per model granting tier ServiceAccounts access to `LLMInferenceService`. References `system:serviceaccounts:maas-default-gateway-tier-{free,premium,enterprise}`.
  **Revert:** Remove `models/rbac.yaml`. The 3.4 operator manages RBAC via `MaaSAuthPolicy` CRDs.

- [ ] **Manual tier groups** (`governance/maas-groups.yaml`) — Groups `tier-free-users`, `tier-premium-users`, `tier-enterprise-users` with demo users.
  **Revert:** The 3.4 operator may manage tier groups from `MaaSSubscription` owner groups. Verify before removing.

- [ ] **Authorino SSL env vars** (`jobs/configure-kuadrant.yaml`) — Job sets `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` on Authorino deployment.
  **Revert:** The 3.4 operator's `install-maas.sh` equivalent may handle this natively. Verify before removing.

- [ ] **Gateway hostname patch** (`jobs/patch-gateway-hostname.yaml`) — Job patches MaaS Gateway with cluster-specific hostname and TLS cert.
  **Revert:** The 3.4 operator may parameterize the Gateway hostname via `ModelsAsService` CR spec. Verify before removing.

- [ ] **DashboardConfig patch** — The `genAiStudio: true` and `modelAsService: true` flags must be applied post-install because the 3.3 operator overwrites them.
  **Revert:** The 3.4 operator should properly reconcile these from the `OdhDashboardConfig` spec.

- [ ] **`alpha.maas.opendatahub.io/tiers` annotation** on `LLMInferenceService` — Used by the dev-preview `maas-api` to assign models to tiers.
  **Revert:** The 3.4 operator uses `MaaSSubscription` CRDs for tier-to-model mapping. Remove annotation from model YAML.

## Known Limitations

- [ ] **LlamaStack Distribution not deployed** — The Llama Stack Operator is `Managed` in the DSC but no `LlamaStackDistribution` CR is deployed. No RAG support in the Playground.
- [ ] **MCP servers not configured** — No `gen-ai-aa-mcp-servers` ConfigMap exists. MCP tool calling in the Playground is not available.
- [ ] **External models ConfigMap missing** — `gen-ai-aa-external-models` ConfigMap not created, causing non-fatal errors in `gen-ai-ui` logs.

## Planned

- [ ] **Component-per-operator extraction** — Refactor `gitops/` to extract operator install triads into reusable `components/operators/` bases. Steps become composition layers referencing shared components.
- [ ] **Multi-version overlay structure** — Create `versions/overlays/rhoai-3.3/` and `rhoai-3.4/` with channel patches. Adding a new RHOAI version = new overlay directory.
- [ ] **DevWorkspace template** — Pre-configured DevWorkspace with Continue extension and MaaS model endpoint pre-populated for zero-setup developer onboarding.
- [ ] **Automated MaaS API validation** — Add curl-based validation in `step-03/validate.sh` that tests the MaaS Gateway endpoint and verifies model listing.
- [ ] **Grafana dashboard screenshots** — Add screenshots of the MaaS usage Grafana dashboard to step-03 README.
- [ ] **Multi-cluster support** — Parameterize cluster-specific values (domain, cert name, GPU instance type) via overlay for easy deployment across different clusters.
