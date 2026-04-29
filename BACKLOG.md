# Backlog

## Known Limitations

- [ ] **AI asset endpoints dropdown shows workspace namespaces** — The GenAI Studio AI asset endpoints project dropdown lists all namespaces where the user has any RBAC (including Dev Spaces workspace namespaces). The Projects page correctly filters by `opendatahub.io/dashboard: "true"`. This is a dashboard UI inconsistency — candidate for upstream issue in `opendatahub-io/odh-dashboard`.

- [ ] **Playground shows no response for reasoning models** — Both `gpt-oss-20b` and `nemotron-3-nano-30b-a3b` produce output via `reasoning_text` streaming events (the model images have built-in reasoning parsers). The Playground UI renders `output_text` events only, so responses appear empty. LlamaStack correctly receives and returns the response (verified via direct `/v1/responses` calls). This is a UI rendering limitation — the Playground doesn't display `reasoning_text` content. The models work correctly via API (curl, Continue, OpenCode).

- [ ] **vLLM image tag may need updating for RHOAI 3.4** — Both model YAMLs use `registry.redhat.io/rhaiis/vllm-cuda-rhel9:3.3.0`. After RHOAI 3.4 installs, check if `maas-parameters` ConfigMap specifies a newer image, or if the LLMInferenceService controller overrides it automatically. The `3.3.0` image should be backward compatible.

## Planned

- [ ] **ExternalModel support** — RHOAI 3.4 documentation does not explicitly mention `ExternalModel` CRD. After operator install, check if the CRD exists natively. If not, evaluate deploying a minimal upstream `maas-controller` solely for the ExternalModel reconciler, or wait for GA.
- [ ] **OpenShift MCP — scoped RBAC per persona** — The OpenShift MCP ServiceAccount currently has cluster-wide `view` ClusterRole (read-only access to all namespaces). Explore namespace-scoped RoleBindings or a custom ClusterRole for tighter security.
- [ ] **Grafana dashboard screenshots** — Add screenshots to step-03 README.
- [ ] **Multi-cluster support** — Parameterize cluster-specific values via overlay.

## Completed (RHOAI 3.4 Upgrade — 2026-04-29)

The following items were workarounds for RHOAI 3.3 + upstream maas-controller hybrid architecture. They are no longer needed with RHOAI 3.4 operator-native MaaS.

- [x] ~~**Gateway AuthPolicy patch for user OAuth tokens** — The 3.4 operator configures AuthPolicies natively.~~
- [x] ~~**Authorino SSL env vars** — The 3.4 operator / RHCL handles this natively.~~
- [x] ~~**Gateway hostname patch** — Still needed as a Job (cluster-specific hostname), but AuthPolicy/SSL patches removed.~~
- [x] ~~**Tier-to-group-mapping ConfigMap** — Auto-created by operator when `modelsAsService: Managed`.~~
- [x] ~~**Manual RateLimitPolicy, TokenRateLimitPolicy, TelemetryPolicy** — Managed via dashboard tier UI in 3.4.~~
- [x] ~~**Manual per-model RBAC** — Auto-created by operator via `alpha.maas.opendatahub.io/tiers` annotation.~~
- [x] ~~**Manual tier groups** — Groups still created via GitOps, but tier assignment is dashboard-managed.~~
- [x] ~~**Upstream maas-controller deployment** — Removed; RHOAI 3.4 operator manages `maas-api` natively.~~
- [x] ~~**RHOAI `maas-api` scaled to 0** — No longer needed; single operator-managed instance.~~
- [x] ~~**Tenant reconciler errors** — Removed with upstream maas-controller.~~
- [x] ~~**`models-as-a-service` namespace** — Removed; no upstream CRDs.~~
- [x] ~~**Tokens bridge** — Removed; 3.4 `maas-api` handles token generation natively.~~
- [x] ~~**ExternalModel + MaaSModelRef + MaaSAuthPolicy + MaaSSubscription** — Removed for initial 3.4 deployment; evaluate ExternalModel support separately.~~
- [x] ~~**Model Registry NetworkPolicy** — Verify if 3.4 operator creates proper NetworkPolicies.~~

## Previously Completed

- [x] ~~**Automated MaaS API validation** — implemented in `step-03/validate.sh`.~~
- [x] ~~**Devfile-based Continue auto-configuration** — Created `adnan-drina/coding-exercises` repo with `devfile.yaml` that auto-copies Continue config via postStart. DevWorkspaces now clone this repo instead of the full quickstart.~~
- [x] ~~**Component-per-operator extraction** — Deferred; current structure works well for 4-step demo.~~
- [x] ~~**Multi-version overlay structure** — Deferred; only RHOAI 3.4 needed for now.~~
- [x] ~~**OpenCode CLI in Dev Spaces** — Installed via postStart in DevWorkspace. Binary downloaded from GitHub releases to `~/.local/bin/`. Developer uses `/connect` to configure MaaS endpoint.~~
